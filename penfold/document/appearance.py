"""Writing the annotations made in Penfold into a PDF, with their own drawing (/AP) and the standard's entries.

Every entry ISO 32000-1 (12.5) asks for is written, so that any viewer shows them as Penfold does and any editor can
change them.

New ones look as docs/specification.md describes ("Annotation types and how they are saved"); the comment is the speech
bubble of GNOME's icon collection. Their style changes the opacity, the lines, the fill, the arrowheads and the text
box's letters, background and border. Texts are written in UTF-16, so that no character can break the file. An image
is written with the drawing it keeps (images.py), stretched to its rectangle, and so is a stamp of another program.
"""

import io
import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pikepdf

from penfold.document.annotations import FILL_STRENGTH, KEPT_DRAWINGS, Annotation, Kind, LineEnds, Style
from penfold.document.geometry import HALF_TURN, Rectangle
from penfold.document.images import DRAWING, STAMP_IMAGE
from penfold.document.page_frame import PageFrame

# The line width of the comment's outline, in points (the others are in each annotation's style).
COMMENT_LINE_WIDTH = 1.5
# The arrowhead: the length of its two strokes with a line of 1 point, how much more for each point wider, and their
# angle with the line.
ARROWHEAD_LENGTH = 10.0
ARROWHEAD_GROWTH = 2.5
ARROWHEAD_ANGLE = math.pi / 6
# Dashed lines: the length of each dash and of each gap, for each point of width.
DASH = 4.0
GAP = 3.0
# The zigzag of a squiggly underline: how tall it is, as a share of the height of the marked text, and at least, in
# points. Each of its strokes goes up or down as much as it goes along.
SQUIGGLE_SHARE = 1 / 6
SQUIGGLE_MINIMUM = 1.5
# The text box's background strength (its drawing is made with Pango, in the rendering layer).
TEXT_BOX_BACKGROUND = 0.14
# A comment is a square of this side, in points.
COMMENT_SIZE = 20.0
# What PDF 2.0 says a stamp that is not an image is (/IT).
STAMP_INTENT = "Stamp"
# Annotation flags (/F, 12.5.3): "Print", it is printed; "NoRotate", it stays upright when the page is turned.
PRINT_FLAG = 4
NO_ROTATE_FLAG = 16
# A circle drawn with four Bézier curves: how far the control points are from the ends.
KAPPA = 0.5522848
DECIMALS = 3
# The speech bubble of GNOME's icon collection (icon-development-kit, CC0), in its 16-point grid from the top.
BUBBLE_GRID = 16.0
BUBBLE: tuple[tuple[str, tuple[float, ...]], ...] = (
    ("m", (1, 4)),
    ("l", (1, 10)),
    ("c", (1, 11.1045694, 1.89543045, 12, 3, 12)),
    ("l", (3.6, 12)),
    ("c", (4.37319851, 12, 5, 12.6268015, 5, 13.4)),
    ("l", (5, 14.1715727)),
    ("c", (5, 14.5929308, 5.26614189, 14.9683294, 5.66374731, 15.1078014)),
    ("c", (6.06135273, 15.2472744, 6.50368404, 15.1203947, 6.76690435, 14.7913694)),
    ("l", (8.37530518, 12.7808685)),
    ("c", (8.77015018, 12.2873125, 9.36793995, 12, 10, 12)),
    ("l", (13, 12)),
    ("c", (14.1045694, 12, 15, 11.1045694, 15, 10)),
    ("l", (15, 4)),
    ("c", (15, 2.89543056, 14.1045694, 2, 13, 2)),
    ("l", (3, 2)),
    ("c", (1.89543045, 2, 1, 2.89543056, 1, 4)),
)

Point = tuple[float, float]


def write_annotation(pdf: pikepdf.Pdf, annotation: Annotation, page: pikepdf.Page, frame: PageFrame) -> None:
    """Add an annotation made in Penfold to a page of the PDF, placed with the frame of the page as shown.

    Raises:
        ValueError: it is not one Penfold writes, or a text box has no drawing.
    """
    if annotation.kind is Kind.TEXT_BOX:
        entries, appearance = _text_box(pdf, annotation, frame)
    elif annotation.kind in KEPT_DRAWINGS:
        entries, appearance = _kept_drawing(pdf, annotation, frame)
    else:
        entries, appearance = _drawn(pdf, annotation, frame)
    dictionary = pikepdf.Dictionary(_common_entries(annotation, page))
    for key, value in entries.items():
        dictionary[key] = value
    dictionary.AP = pikepdf.Dictionary(N=appearance)
    annots = page.obj.get("/Annots")
    if not isinstance(annots, pikepdf.Array):
        page.obj.Annots = annots = pdf.make_indirect(pikepdf.Array())
    annots.append(pdf.make_indirect(dictionary))


def _drawn(pdf: pikepdf.Pdf, annotation: Annotation, frame: PageFrame) -> tuple[dict[str, object], pikepdf.Object]:
    """The entries of an annotation drawn here, and its drawing in the page's units inside its /Rect."""
    writers = {
        Kind.HIGHLIGHT: _text_markup,
        Kind.UNDERLINE: _text_markup,
        Kind.SQUIGGLY: _text_markup,
        Kind.STRIKE_OUT: _text_markup,
        Kind.RECTANGLE: _rectangle_or_circle,
        Kind.CIRCLE: _rectangle_or_circle,
        Kind.ARROW: _arrow,
        Kind.FREEHAND: _freehand,
        Kind.COMMENT: _comment,
    }
    writer = writers.get(annotation.kind)
    if writer is None:
        message = f"annotations of type {annotation.subtype} are not written yet"
        raise ValueError(message)
    written = writer(annotation, frame)
    opacity = annotation.style.opacity
    if annotation.kind is not Kind.COMMENT and (opacity < 1 or annotation.kind is Kind.HIGHLIGHT):
        written.entries["/CA"] = opacity
        # The opacity goes in the drawing too: Poppler and Ghostscript only paint the drawing's (as Poppler writes).
        state = pikepdf.Dictionary(Type=pikepdf.Name.ExtGState, CA=opacity)
        state.ca = opacity
        if annotation.kind is Kind.HIGHLIGHT:
            state.BM = pikepdf.Name.Multiply
        written.resources = pikepdf.Dictionary(ExtGState=pikepdf.Dictionary(Look=state))
        written.drawing.insert(0, "/Look gs")
    stream = pikepdf.Stream(pdf, "\n".join(written.drawing).encode())
    stream.Type = pikepdf.Name.XObject
    stream.Subtype = pikepdf.Name.Form
    stream.BBox = written.entries["/Rect"]
    stream.Resources = written.resources
    return written.entries, pdf.make_indirect(stream)


def _text_box(pdf: pikepdf.Pdf, annotation: Annotation, frame: PageFrame) -> tuple[dict[str, object], pikepdf.Object]:
    """A text box (FreeText): its entries, and its drawing made with Pango, with the fonts it uses inside.

    The drawing is upright in its own box; its matrix turns it as the text reads on the page (12.5.5).
    """
    if not annotation.drawing:
        message = "a text box needs its drawing"
        raise ValueError(message)
    bounds = _bounds(_rectangle_points(annotation.rectangle, frame))
    left, top, right, bottom = annotation.rectangle
    across = annotation.text_turn % HALF_TURN != 0
    width, height = (bottom - top, right - left) if across else (right - left, bottom - top)
    with pikepdf.open(io.BytesIO(annotation.drawing)) as box:
        appearance = pdf.copy_foreign(box.make_indirect(box.pages[0].as_form_xobject()))
    appearance.BBox = pikepdf.Array(_rounded((0, 0, width, height)))
    angle = math.radians(annotation.text_turn + frame.rotation)
    cos, sin = round(math.cos(angle)), round(math.sin(angle))
    appearance.Matrix = pikepdf.Array([cos, sin, -sin, cos, 0, 0])
    style = annotation.style
    entries: dict[str, object] = {
        "/Rect": bounds,
        "/BS": _border(style.line_width if style.border else 0),
        "/DA": pikepdf.String(f"0 g /Helv {style.font_size:g} Tf"),
        "/DS": pikepdf.String(f"font: {style.font_size:g}pt 'Liberation Sans'; color: #000000"),
        "/Q": 0,
    }
    if style.background:
        entries["/IC"] = pikepdf.Array(_rounded(tint(annotation.color or (0.0, 0.0, 0.0), TEXT_BOX_BACKGROUND)))
    return entries, appearance


def _kept_drawing(
    pdf: pikepdf.Pdf, annotation: Annotation, frame: PageFrame
) -> tuple[dict[str, object], pikepdf.Object]:
    """An image or a stamp (Stamp): its entries, and its drawing, which viewers stretch from its box to its /Rect.

    The drawing kept is painted unturned, as it was in its page; its opacity goes in the drawing too, as with the
    others. A stamp keeps its name (/Name).
    """
    if not annotation.drawing:
        message = "an image or a stamp needs its drawing"
        raise ValueError(message)
    with pikepdf.open(io.BytesIO(annotation.drawing)) as kept:
        drawing = pdf.copy_foreign(kept.make_indirect(kept.pages[0].as_form_xobject(handle_transformations=False)))
    entries: dict[str, object] = {"/Rect": _bounds(_rectangle_points(annotation.rectangle, frame))}
    if annotation.kind is Kind.IMAGE:
        entries["/IT"] = pikepdf.Name(f"/{STAMP_IMAGE}")
    else:
        entries["/IT"] = pikepdf.Name(f"/{STAMP_INTENT}")
        entries["/Name"] = pikepdf.Name(f"/{annotation.stamp}")
    resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary({DRAWING: drawing}))
    content = f"q {DRAWING} Do Q"
    opacity = annotation.style.opacity
    if opacity < 1:
        entries["/CA"] = opacity
        state = pikepdf.Dictionary(Type=pikepdf.Name.ExtGState, CA=opacity)
        state.ca = opacity
        resources.ExtGState = pikepdf.Dictionary(Look=state)
        content = f"q /Look gs {DRAWING} Do Q"
    stream = pikepdf.Stream(pdf, content.encode())
    stream.Type = pikepdf.Name.XObject
    stream.Subtype = pikepdf.Name.Form
    stream.BBox = drawing.BBox
    stream.Resources = resources
    return entries, pdf.make_indirect(stream)


@dataclass
class _Written:
    """The entries of one type of annotation, and its drawing, in the page's units inside its /Rect."""

    entries: dict[str, object]
    drawing: list[str]
    resources: pikepdf.Dictionary = field(default_factory=pikepdf.Dictionary)


def _common_entries(annotation: Annotation, page: pikepdf.Page) -> dict[str, object]:
    """What every annotation has: type, page, unique name, author, dates, flags, colour and text."""
    created = pdf_date(annotation.created)
    entries: dict[str, object] = {
        "/Type": pikepdf.Name.Annot,
        "/Subtype": pikepdf.Name(f"/{annotation.subtype}"),
        "/P": page.obj,
        "/NM": pikepdf.String(annotation.name),
        "/T": utf16(annotation.author),
        "/CreationDate": created,
        "/M": pdf_date(annotation.modified) if annotation.modified else created,
        "/F": PRINT_FLAG,
    }
    if annotation.kind is not Kind.IMAGE and (annotation.color or annotation.kind is not Kind.STAMP):
        # An image has no colour, nor a stamp of another program that had none.
        entries["/C"] = pikepdf.Array(_rounded(annotation.color or (0.0, 0.0, 0.0)))
    if annotation.text:
        entries["/Contents"] = utf16(annotation.text)
    return entries


def _text_markup(annotation: Annotation, frame: PageFrame) -> _Written:
    """Highlight: the marked areas filled, multiplied over the text. The others: a line on each.

    Underline: on its bottom edge. Squiggly: a zigzag there, with round corners, so that they do not stick out of the
    area. Strikethrough: across its middle.
    """
    quads = [_corners(quad, frame) for quad in annotation.quads]
    color = _color(annotation)
    width = annotation.style.line_width
    if annotation.kind is Kind.HIGHLIGHT:
        drawing = [f"{color} rg"]
        drawing += [f"{_path([corners[0], corners[1], corners[3], corners[2]])} h f" for corners in quads]
    else:
        drawing = [f"{color} RG {width:g} w"]
        if annotation.kind is Kind.SQUIGGLY:
            drawing.append("1 j")
        for upper_left, upper_right, lower_left, lower_right in quads:
            if annotation.kind is Kind.SQUIGGLY:
                drawing.append(f"{_path(squiggle(lower_left, lower_right, upper_left, width))} S")
                continue
            if annotation.kind is Kind.UNDERLINE:
                # On the bottom edge, lifted by half the line, so that it is all inside the area.
                lift = _towards(lower_left, upper_left, width / 2)
                start, end = _moved(lower_left, lift), _moved(lower_right, lift)
            else:
                start, end = _middle(upper_left, lower_left), _middle(upper_right, lower_right)
            drawing.append(f"{_path([start, end])} S")
    points = [point for quad in quads for point in quad]
    entries: dict[str, object] = {
        "/Rect": _bounds(points),
        "/QuadPoints": pikepdf.Array([coordinate for point in points for coordinate in _rounded(point)]),
    }
    return _Written(entries, drawing)


def _rectangle_or_circle(annotation: Annotation, frame: PageFrame) -> _Written:
    """A line inside the rectangle, or the ellipse it holds; inside, a soft tint of the colour (/IC) or nothing."""
    bounds = _bounds(_rectangle_points(annotation.rectangle, frame))
    left, bottom, right, top = (float(bounds[index]) for index in range(4))
    style = annotation.style
    inset = style.line_width / 2
    left, bottom, right, top = left + inset, bottom + inset, right - inset, top - inset
    entries: dict[str, object] = {"/Rect": bounds, "/BS": _border(style.line_width, dashed=style.dashed)}
    drawing = [_line_style(annotation)]
    if annotation.kind is Kind.RECTANGLE:
        drawing.append(f"{_numbers([left, bottom, right - left, top - bottom])} re")
    else:
        drawing.append(_ellipse(left, bottom, right, top))
    if style.filled:
        fill = tint(annotation.color or (0.0, 0.0, 0.0), FILL_STRENGTH)
        entries["/IC"] = pikepdf.Array(_rounded(fill))
        drawing.insert(0, f"{_numbers(fill)} rg")
    drawing.append("B" if style.filled else "S")
    return _Written(entries, drawing)


def _arrow(annotation: Annotation, frame: PageFrame) -> _Written:
    """A line from its start to its end, with open arrowheads at its end, at both ends or none (/LE)."""
    if annotation.line is None:
        message = "an arrow needs its line"
        raise ValueError(message)
    start = frame.pdf_point(*annotation.line[:2])
    end = frame.pdf_point(*annotation.line[2:])
    style = annotation.style
    drawing = [_line_style(annotation), f"{_path([start, end])} S", "[] 0 d 1 J 1 j"]  # Solid, round arrowheads.
    points = [start, end]
    for tip, tail in arrowheads(start, end, style.line_ends):
        wings = arrowhead_wings(tip, tail, style.line_width)
        drawing.append(f"{_path([wings[0], tip, wings[1]])} S")
        points += wings
    margin = style.line_width
    xs, ys = [x for x, _y in points], [y for _x, y in points]
    ends = {LineEnds.END: ("/None", "/OpenArrow"), LineEnds.BOTH: ("/OpenArrow",) * 2, LineEnds.NONE: ("/None",) * 2}
    entries: dict[str, object] = {
        "/Rect": pikepdf.Array(_rounded((min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin))),
        "/L": pikepdf.Array(_rounded((*start, *end))),
        "/LE": pikepdf.Array([pikepdf.Name(name) for name in ends[style.line_ends]]),
        "/BS": _border(style.line_width, dashed=style.dashed),
    }
    return _Written(entries, drawing)


def _freehand(annotation: Annotation, frame: PageFrame) -> _Written:
    """Each stroke as a smooth curve through its points, with round ends and corners (a lone point, a dot)."""
    if not annotation.strokes:
        message = "a freehand drawing needs its strokes"
        raise ValueError(message)
    strokes = [[frame.pdf_point(*point) for point in stroke] for stroke in annotation.strokes]
    drawing = [_line_style(annotation), "1 J 1 j"]
    reached = []
    for stroke in strokes:
        curves = stroke_curves(stroke)
        drawing.append(f"{_numbers(stroke[0])} m")
        drawing += [f"{_numbers(coordinate for point in curve for coordinate in point)} c" for curve in curves]
        if not curves:
            drawing.append(f"{_numbers(stroke[0])} l")
        drawing.append("S")
        reached += [stroke[0], *(point for curve in curves for point in curve)]
    margin = annotation.style.line_width
    xs, ys = [x for x, _y in reached], [y for _x, y in reached]
    entries: dict[str, object] = {
        "/Rect": pikepdf.Array(_rounded((min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin))),
        "/InkList": pikepdf.Array(
            [pikepdf.Array([value for point in stroke for value in _rounded(point)]) for stroke in strokes]
        ),
        "/BS": _border(annotation.style.line_width, dashed=annotation.style.dashed),
    }
    return _Written(entries, drawing)


def stroke_curves(points: list[Point]) -> list[tuple[Point, Point, Point]]:
    """The Bézier curves of a smooth line through points, from the first: two control points and the end of each.

    Each curve leaves a point in the direction from the point before it to the point after it (a Catmull-Rom spline),
    so that the line has no corners at the points. A curve stays inside its control points, and so does the line.
    """
    curves = []
    for index in range(len(points) - 1):
        before, start, end = points[max(index - 1, 0)], points[index], points[index + 1]
        after = points[min(index + 2, len(points) - 1)]
        first = (start[0] + (end[0] - before[0]) / 6, start[1] + (end[1] - before[1]) / 6)
        second = (end[0] - (after[0] - start[0]) / 6, end[1] - (after[1] - start[1]) / 6)
        curves.append((first, second, end))
    return curves


def arrowheads(start: Point, end: Point, line_ends: LineEnds) -> list[tuple[Point, Point]]:
    """The arrowheads of an arrow: the point of each, and the other end of the line, which it points away from."""
    return {LineEnds.END: [(end, start)], LineEnds.BOTH: [(end, start), (start, end)], LineEnds.NONE: []}[line_ends]


def arrowhead_wings(tip: Point, tail: Point, line_width: float) -> tuple[Point, Point]:
    """The ends of the two strokes of an open arrowhead, longer for wider lines."""
    length = ARROWHEAD_LENGTH + ARROWHEAD_GROWTH * (line_width - 1)
    angle = math.atan2(tip[1] - tail[1], tip[0] - tail[0])
    first, second = (
        (tip[0] - length * math.cos(angle + turn), tip[1] - length * math.sin(angle + turn))
        for turn in (-ARROWHEAD_ANGLE, ARROWHEAD_ANGLE)
    )
    return first, second


def squiggle(lower_left: Point, lower_right: Point, upper_left: Point, line_width: float) -> list[Point]:
    """The corners of a squiggly underline's zigzag along the bottom edge of a marked area, inside it.

    It starts and ends low, lifted by half the line as an underline is, with an even number of strokes, as many as fit.
    The area is given by three of its corners, as the text reads, so that it serves on turned pages too.
    """
    up = _towards(lower_left, upper_left, 1.0)
    tall = max(SQUIGGLE_MINIMUM, math.dist(lower_left, upper_left) * SQUIGGLE_SHARE)
    strokes = max(2, 2 * round(math.dist(lower_left, lower_right) / (2 * tall)))
    points = []
    for index in range(strokes + 1):
        along = index / strokes
        lift = line_width / 2 + (tall if index % 2 else 0.0)
        points.append(
            (
                lower_left[0] + (lower_right[0] - lower_left[0]) * along + up[0] * lift,
                lower_left[1] + (lower_right[1] - lower_left[1]) * along + up[1] * lift,
            )
        )
    return points


def dashes(style: Style) -> list[float]:
    """The dash pattern of a line: a dash and a gap, as long as the line is wide; none for a solid line."""
    return [DASH * style.line_width, GAP * style.line_width] if style.dashed else []


def tint(color: tuple[float, float, float], strength: float) -> tuple[float, float, float]:
    """A colour at some strength over white: the soft fill of shapes and the background of text boxes."""
    red, green, blue = (1 - strength + strength * component for component in color)
    return red, green, blue


def _line_style(annotation: Annotation) -> str:
    """The colour, width and dashes of an annotation's line."""
    style = annotation.style
    return f"{_color(annotation)} RG {style.line_width:g} w [{_numbers(dashes(style))}] 0 d"


def _comment(annotation: Annotation, frame: PageFrame) -> _Written:
    """The speech bubble filled with the colour and outlined in black, upright however the page is turned.

    Viewers keep comments upright (NoRotate): Poppler and Acrobat do even without the flag, which is set anyway.
    """
    left, top, right, bottom = annotation.rectangle
    centre_x, centre_y = frame.pdf_point((left + right) / 2, (top + bottom) / 2)
    scale = COMMENT_SIZE / BUBBLE_GRID
    operations = []
    for operator, coordinates in BUBBLE:
        # From the grid (from its top left corner) to the page (from the bottom), around the comment's centre.
        points = [
            (centre_x + (x - BUBBLE_GRID / 2) * scale, centre_y + (BUBBLE_GRID / 2 - y) * scale)
            for x, y in zip(coordinates[::2], coordinates[1::2], strict=True)
        ]
        operations.append(f"{_numbers(coordinate for point in points for coordinate in point)} {operator}")
    half = COMMENT_SIZE / 2
    entries: dict[str, object] = {
        "/Rect": pikepdf.Array(_rounded((centre_x - half, centre_y - half, centre_x + half, centre_y + half))),
        "/F": PRINT_FLAG | NO_ROTATE_FLAG,
        "/Name": pikepdf.Name.Comment,
        "/Open": False,
    }
    return _Written(entries, [f"{_color(annotation)} rg 0 G {COMMENT_LINE_WIDTH:g} w 1 J 1 j", *operations, "h B"])


def utf16(text: str) -> pikepdf.String:
    """A text string in UTF-16 with its byte order mark (7.9.2.2), whatever characters it has."""
    return pikepdf.String(b"\xfe\xff" + text.encode("utf-16-be"))


def pdf_date(moment: datetime | None) -> pikepdf.String:
    """A PDF date (7.9.4), in UTC; now if none is given."""
    return pikepdf.String(f"D:{(moment or datetime.now(UTC)).astimezone(UTC):%Y%m%d%H%M%S}Z")


def _border(width: float, *, dashed: bool = False) -> pikepdf.Dictionary:
    """A border of some width, solid or dashed (12.5.4)."""
    border = pikepdf.Dictionary(Type=pikepdf.Name.Border, W=width, S=pikepdf.Name.D if dashed else pikepdf.Name.S)
    if dashed:
        border.D = pikepdf.Array([DASH * width, GAP * width])
    return border


def _corners(quad: Rectangle, frame: PageFrame) -> tuple[Point, Point, Point, Point]:
    """The corners of a marked area in the PDF, in the order viewers expect.

    Upper left, upper right, lower left, lower right, as the text reads on the page as shown.
    """
    left, top, right, bottom = quad
    return (
        frame.pdf_point(left, top),
        frame.pdf_point(right, top),
        frame.pdf_point(left, bottom),
        frame.pdf_point(right, bottom),
    )


def _rectangle_points(rectangle: Rectangle, frame: PageFrame) -> list[Point]:
    left, top, right, bottom = rectangle
    return [frame.pdf_point(left, top), frame.pdf_point(right, bottom)]


def _bounds(points: Iterable[Point]) -> pikepdf.Array:
    listed = list(points)
    xs, ys = [x for x, _y in listed], [y for _x, y in listed]
    return pikepdf.Array(_rounded((min(xs), min(ys), max(xs), max(ys))))


def _ellipse(left: float, bottom: float, right: float, top: float) -> str:
    """An ellipse in a rectangle, with four Bézier curves from its top."""
    x, y = (left + right) / 2, (bottom + top) / 2
    rx, ry = (right - left) / 2, (top - bottom) / 2
    kx, ky = rx * KAPPA, ry * KAPPA
    curves = [
        (x + kx, y + ry, x + rx, y + ky, x + rx, y),
        (x + rx, y - ky, x + kx, y - ry, x, y - ry),
        (x - kx, y - ry, x - rx, y - ky, x - rx, y),
        (x - rx, y + ky, x - kx, y + ry, x, y + ry),
    ]
    return "\n".join([f"{_numbers([x, y + ry])} m", *(f"{_numbers(curve)} c" for curve in curves)])


def _path(points: list[Point]) -> str:
    """Points joined by straight lines: "x y m x y l …"."""
    first, *others = points
    return " ".join([f"{_numbers(first)} m", *(f"{_numbers(point)} l" for point in others)])


def _towards(start: Point, end: Point, distance: float) -> Point:
    """A move of some distance from one point towards another."""
    length = math.hypot(end[0] - start[0], end[1] - start[1]) or 1.0
    return (end[0] - start[0]) / length * distance, (end[1] - start[1]) / length * distance


def _moved(point: Point, move: Point) -> Point:
    return point[0] + move[0], point[1] + move[1]


def _middle(first: Point, second: Point) -> Point:
    return (first[0] + second[0]) / 2, (first[1] + second[1]) / 2


def _color(annotation: Annotation) -> str:
    return _numbers(annotation.color or (0.0, 0.0, 0.0))


def _rounded(values: Iterable[float]) -> list[float]:
    return [round(value, DECIMALS) for value in values]


def _numbers(values: Iterable[float]) -> str:
    return " ".join(f"{value:g}" for value in _rounded(values))
