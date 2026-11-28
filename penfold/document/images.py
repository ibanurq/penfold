"""Images and stamps on the pages: stamp annotations (/Stamp, ISO 32000-1, 12.5.6.12) and the drawings they keep.

The standard has no annotation type for images: a stamp with an image as its drawing (/AP) is what viewers show as one.
PDF 2.0 (ISO 32000-2) says so with /IT /StampImage; older programs only draw the image. A stamp is taken as an image
when it says so, or when its drawing does nothing but paint one image (and set up how: clip, move, scale, opacity).
The other stamps are stamps: a word such as "Approved", named by /Name, that their drawing shows if they have one.

Penfold keeps the drawing of an image, or of a stamp of another program, as a one-page PDF of the size of the drawing,
the drawing filling it: on the screen it is painted stretched to the annotation's rectangle, as viewers stretch an
annotation's drawing to its /Rect, and it is written back as the drawing of the stamp. The page is turned as its source
page is (/Rotate), so that it is painted as it is seen on that page; what is written back is the page unturned, as the
drawing was.
"""

import io

import pikepdf

from penfold.document.pdf_values import name, numbers

# What PDF 2.0 says a stamp that is an image is (/IT).
STAMP_IMAGE = "StampImage"
# The name of the drawing inside the page of an image's drawing.
DRAWING = "/Drawing"
# What an image's drawing may do besides painting its image: keep and restore the state, move and scale, set its
# opacity, its line and its rendering, and clip (a path that paints nothing: "re W n").
SETTING_UP = frozenset(
    {"q", "Q", "cm", "gs", "w", "J", "j", "M", "d", "ri", "i", "re", "m", "l", "c", "v", "y", "h", "W", "W*", "n"}
)
# How deep a drawing may hold drawings (Form XObjects) inside, each painting only the image.
NESTING = 3
# The number of entries of a rectangle and of a matrix.
RECTANGLE_SIZE = 4
MATRIX_SIZE = 6

# A box in the PDF: left, bottom, right, top.
Box = tuple[float, float, float, float]
Matrix = tuple[float, float, float, float, float, float]


def image_drawing(annotation: pikepdf.Dictionary, rotation: int = 0) -> bytes | None:
    """The drawing of a stamp that is an image, as a one-page PDF turned by rotation; None if it is not an image.

    A stamp without a drawing, or whose drawing paints anything else, is not an image.
    """
    found = _image_appearance(annotation)
    return None if found is None else _kept(*found, rotation)


def stamp_drawing(annotation: pikepdf.Dictionary, rotation: int = 0) -> bytes | None:
    """The drawing of a stamp, whatever it paints, as a one-page PDF turned by rotation; None if it has none."""
    appearance = normal_appearance(annotation)
    box = None if appearance is None else _drawn_box(appearance)
    return None if appearance is None or box is None else _kept(appearance, box, rotation)


def _kept(appearance: pikepdf.Stream, box: Box, rotation: int) -> bytes:
    """A drawing as a one-page PDF as big as the box it fills, turned by rotation."""
    left, bottom, right, top = box
    with pikepdf.new() as pdf:
        pdf.add_blank_page(page_size=(right - left, top - bottom))
        page = pdf.pages[0].obj
        page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary({DRAWING: pdf.copy_foreign(appearance)}))
        page.Contents = pdf.make_stream(f"q 1 0 0 1 {-left:g} {-bottom:g} cm {DRAWING} Do Q".encode())
        if rotation % 360:
            page.Rotate = rotation % 360
        written = io.BytesIO()
        pdf.save(written)
    return written.getvalue()


def _image_appearance(annotation: pikepdf.Dictionary) -> tuple[pikepdf.Stream, Box] | None:
    """The drawing of a stamp that is an image, and the box it fills; None if it is not an image."""
    appearance = normal_appearance(annotation)
    if appearance is None:
        return None
    if name(annotation.get("/IT")) != STAMP_IMAGE and not _paints_one_image(appearance):
        return None
    box = _drawn_box(appearance)
    return None if box is None else (appearance, box)


def normal_appearance(annotation: pikepdf.Dictionary) -> pikepdf.Stream | None:
    """The drawing an annotation shows (its normal appearance, in the state /AS chooses), if it is a Form XObject."""
    appearances = annotation.get("/AP")
    if not isinstance(appearances, pikepdf.Dictionary):
        return None
    normal = appearances.get("/N")
    if isinstance(normal, pikepdf.Dictionary) and not isinstance(normal, pikepdf.Stream):
        state = annotation.get("/AS")
        normal = normal.get(str(state)) if isinstance(state, pikepdf.Name) else None
    if not isinstance(normal, pikepdf.Stream) or numbers(normal.get("/BBox")) is None:
        return None
    return normal


def _paints_one_image(form: pikepdf.Stream, depth: int = 0) -> bool:
    """Whether a drawing (a Form XObject) paints one image and nothing else, maybe through drawings inside it."""
    resources = form.get("/Resources")
    xobjects = resources.get("/XObject") if isinstance(resources, pikepdf.Dictionary) else None
    images = 0
    try:
        instructions = pikepdf.parse_content_stream(form)
    except pikepdf.PdfError:
        return False
    for instruction in instructions:
        operator = str(instruction.operator)
        if operator in SETTING_UP:
            continue
        if operator == "INLINE IMAGE":
            images += 1
        elif operator == "Do" and isinstance(xobjects, pikepdf.Dictionary) and instruction.operands:
            inner = xobjects.get(str(instruction.operands[0]))
            subtype = str(inner.get("/Subtype")) if isinstance(inner, pikepdf.Stream) else ""
            if subtype == "/Image" or (
                subtype == "/Form" and depth < NESTING and _paints_one_image(inner, depth + 1)  # type: ignore[arg-type]
            ):
                images += 1
            else:
                return False
        else:
            return False
    return images == 1


def _drawn_box(form: pikepdf.Stream) -> Box | None:
    """The box a drawing fills: its /BBox moved by its /Matrix (left, bottom, right, top); None if it is empty."""
    box = numbers(form.get("/BBox"))
    if box is None or len(box) != RECTANGLE_SIZE:
        return None
    matrix = numbers(form.get("/Matrix"))
    a, b, c, d, e, f = matrix if matrix is not None and len(matrix) == MATRIX_SIZE else (1, 0, 0, 1, 0, 0)
    corners = [(x, y) for x in (box[0], box[2]) for y in (box[1], box[3])]
    xs = [a * x + c * y + e for x, y in corners]
    ys = [b * x + d * y + f for x, y in corners]
    left, bottom, right, top = min(xs), min(ys), max(xs), max(ys)
    if right - left <= 0 or top - bottom <= 0:
        return None
    return left, bottom, right, top


def upright_matrix(seen: int, width: float, height: float) -> Matrix:
    """From the page as seen, turned clockwise by seen degrees, to the page unturned (both from the bottom left)."""
    return {
        0: (1, 0, 0, 1, 0, 0),
        90: (0, 1, -1, 0, height, 0),
        180: (-1, 0, 0, -1, width, height),
        270: (0, -1, 1, 0, 0, width),
    }[seen % 360]


def upright_drawing(drawing: bytes, rotation: int, turn: int) -> bytes:
    """A drawing made as it is to be seen (a one-page PDF), kept for a page its PDF turns by rotation (/Rotate).

    Penfold turns that page by turn too: the drawing goes inside its kept page turned so that it is seen upright on
    the page, and the kept page is turned as the page is (/Rotate), as the drawings of images are.
    """
    with pikepdf.open(io.BytesIO(drawing)) as made, pikepdf.new() as pdf:
        left, bottom, right, top = numbers(made.pages[0].obj.get("/MediaBox")) or (0.0, 0.0, 0.0, 0.0)
        width, height = right - left, top - bottom
        form = pdf.copy_foreign(made.make_indirect(made.pages[0].as_form_xobject(handle_transformations=False)))
        seen = (rotation + turn) % 360
        pdf.add_blank_page(page_size=(height, width) if seen % 180 else (width, height))
        page = pdf.pages[0].obj
        page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary({DRAWING: form}))
        matrix = " ".join(f"{value:g}" for value in upright_matrix(seen, width, height))
        move = f" 1 0 0 1 {-left:g} {-bottom:g} cm" if left or bottom else ""
        page.Contents = pdf.make_stream(f"q {matrix} cm{move} {DRAWING} Do Q".encode())
        if rotation % 360:
            page.Rotate = rotation % 360
        written = io.BytesIO()
        pdf.save(written)
    return written.getvalue()


def turned_drawing(drawing: bytes, clockwise: bool) -> bytes:
    """An image's drawing turned a quarter, clockwise or anticlockwise, as it is seen: its width and height swap.

    The drawing goes inside the new one as it was, turned; the page keeps its turn (/Rotate), which turns both alike.
    """
    with pikepdf.open(io.BytesIO(drawing)) as kept, pikepdf.new() as pdf:
        old = kept.pages[0]
        left, bottom, right, top = numbers(old.obj.get("/MediaBox")) or (0.0, 0.0, 0.0, 0.0)
        width, height = right - left, top - bottom
        form = pdf.copy_foreign(kept.make_indirect(old.as_form_xobject(handle_transformations=False)))
        pdf.add_blank_page(page_size=(height, width))
        page = pdf.pages[0].obj
        page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary({DRAWING: form}))
        # From the old page (from its corner) to the new one: a point x, y goes to y, width - x (clockwise).
        matrix = f"0 -1 1 0 0 {width:g}" if clockwise else f"0 1 -1 0 {height:g} 0"
        move = f"1 0 0 1 {-left:g} {-bottom:g} cm " if left or bottom else ""
        page.Contents = pdf.make_stream(f"q {matrix} cm {move}{DRAWING} Do Q".encode())
        rotation = old.obj.get("/Rotate")
        if rotation is not None:
            page.Rotate = rotation
        written = io.BytesIO()
        pdf.save(written)
    return written.getvalue()
