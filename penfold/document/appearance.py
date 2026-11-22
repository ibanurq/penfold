"""Writing the annotations made in Penfold into a PDF, with their own drawing (/AP) and the standard's entries.

Every entry ISO 32000-1 (12.5) asks for is written (D67), so that any viewer shows them as Penfold does and any
editor can change them.

They look as in 0.6 (docs/specification.md, "Saving annotations with their own appearance"); the comment is the
speech bubble of GNOME's icon collection (D68). Texts are written in UTF-16, so that no character can break the file.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pikepdf

from penfold.document.annotations import Annotation, Kind
from penfold.document.geometry import Rectangle
from penfold.document.page_frame import PageFrame

# Line width of underlines, strikethroughs, rectangles, circles and arrows, and of the comment's outline, in points.
LINE_WIDTH = 1.0
COMMENT_LINE_WIDTH = 1.5
HIGHLIGHT_OPACITY = 0.75
# The arrowhead: the length of its two strokes, in points, and their angle with the line.
ARROWHEAD_LENGTH = 10.0
ARROWHEAD_ANGLE = math.pi / 6
# A comment is a square of this side, in points.
COMMENT_SIZE = 20.0
# Annotation flags (/F, 12.5.3): "Print", it is printed; "NoRotate", it stays upright when the page is turned.
PRINT_FLAG = 4
NO_ROTATE_FLAG = 16
# A circle drawn with four Bézier curves: how far the control points are from the ends.
KAPPA = 0.5522848
DECIMALS = 3
# The speech bubble of GNOME's icon collection (icon-development-kit, CC0; D68), in its 16-point grid from the top.
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
        ValueError: it is not one Penfold writes yet.
    """
    writers = {
        Kind.HIGHLIGHT: _text_markup,
        Kind.UNDERLINE: _text_markup,
        Kind.STRIKE_OUT: _text_markup,
        Kind.RECTANGLE: _rectangle_or_circle,
        Kind.CIRCLE: _rectangle_or_circle,
        Kind.ARROW: _arrow,
        Kind.COMMENT: _comment,
    }
    writer = writers.get(annotation.kind)
    if writer is None:
        message = f"annotations of type {annotation.subtype} are not written yet"
        raise ValueError(message)
    written = writer(annotation, frame)
    stream = pikepdf.Stream(pdf, "\n".join(written.drawing).encode())
    stream.Type = pikepdf.Name.XObject
    stream.Subtype = pikepdf.Name.Form
    stream.BBox = written.entries["/Rect"]
    stream.Resources = written.resources
    dictionary = pikepdf.Dictionary(_common_entries(annotation, page))
    for key, value in written.entries.items():
        dictionary[key] = value
    dictionary.AP = pikepdf.Dictionary(N=pdf.make_indirect(stream))
    annots = page.obj.get("/Annots")
    if not isinstance(annots, pikepdf.Array):
        page.obj.Annots = annots = pdf.make_indirect(pikepdf.Array())
    annots.append(pdf.make_indirect(dictionary))


@dataclass
class _Written:
    """The entries of one type of annotation, and its drawing, in the page's units inside its /Rect."""

    entries: dict[str, object]
    drawing: list[str]
    resources: pikepdf.Dictionary = field(default_factory=pikepdf.Dictionary)


def _common_entries(annotation: Annotation, page: pikepdf.Page) -> dict[str, object]:
    """What every annotation has: type, page, unique name, author, dates, flags, colour and text."""
    created = _date(annotation.created)
    entries: dict[str, object] = {
        "/Type": pikepdf.Name.Annot,
        "/Subtype": pikepdf.Name(f"/{annotation.subtype}"),
        "/P": page.obj,
        "/NM": pikepdf.String(annotation.name),
        "/T": utf16(annotation.author),
        "/CreationDate": created,
        "/M": created,
        "/F": PRINT_FLAG,
        "/C": pikepdf.Array(_rounded(annotation.color or (0.0, 0.0, 0.0))),
    }
    if annotation.text:
        entries["/Contents"] = utf16(annotation.text)
    return entries


def _text_markup(annotation: Annotation, frame: PageFrame) -> _Written:
    """Highlight: the marked areas filled, multiplied over the text. Underline and strikethrough: a line on each."""
    quads = [_corners(quad, frame) for quad in annotation.quads]
    color = _color(annotation)
    if annotation.kind is Kind.HIGHLIGHT:
        drawing = ["/Highlight gs", f"{color} rg"]
        drawing += [f"{_path([corners[0], corners[1], corners[3], corners[2]])} h f" for corners in quads]
    else:
        drawing = [f"{color} RG {LINE_WIDTH:g} w"]
        for upper_left, upper_right, lower_left, lower_right in quads:
            if annotation.kind is Kind.UNDERLINE:
                # On the bottom edge, lifted by half the line, so that it is all inside the area.
                lift = _towards(lower_left, upper_left, LINE_WIDTH / 2)
                start, end = _moved(lower_left, lift), _moved(lower_right, lift)
            else:
                start, end = _middle(upper_left, lower_left), _middle(upper_right, lower_right)
            drawing.append(f"{_path([start, end])} S")
    points = [point for quad in quads for point in quad]
    entries: dict[str, object] = {
        "/Rect": _bounds(points),
        "/QuadPoints": pikepdf.Array([coordinate for point in points for coordinate in _rounded(point)]),
    }
    written = _Written(entries, drawing)
    if annotation.kind is Kind.HIGHLIGHT:
        entries["/CA"] = HIGHLIGHT_OPACITY
        state = pikepdf.Dictionary(Type=pikepdf.Name.ExtGState, BM=pikepdf.Name.Multiply)
        # The opacity goes in the drawing too: Poppler and Ghostscript only paint the drawing's (as Poppler writes).
        state.ca = state.CA = HIGHLIGHT_OPACITY
        written.resources = pikepdf.Dictionary(ExtGState=pikepdf.Dictionary(Highlight=state))
    return written


def _rectangle_or_circle(annotation: Annotation, frame: PageFrame) -> _Written:
    """A line inside the rectangle, or the ellipse it holds; nothing inside (no /IC)."""
    bounds = _bounds(_rectangle_points(annotation.rectangle, frame))
    left, bottom, right, top = (float(bounds[index]) for index in range(4))
    inset = LINE_WIDTH / 2
    left, bottom, right, top = left + inset, bottom + inset, right - inset, top - inset
    drawing = [f"{_color(annotation)} RG {LINE_WIDTH:g} w"]
    if annotation.kind is Kind.RECTANGLE:
        drawing.append(f"{_numbers([left, bottom, right - left, top - bottom])} re S")
    else:
        drawing.append(_ellipse(left, bottom, right, top) + " S")
    return _Written({"/Rect": bounds, "/BS": _border()}, drawing)


def _arrow(annotation: Annotation, frame: PageFrame) -> _Written:
    """A line from its start to its end, with an open arrowhead at the end (/LE [/None /OpenArrow])."""
    if annotation.line is None:
        message = "an arrow needs its line"
        raise ValueError(message)
    start = frame.pdf_point(*annotation.line[:2])
    end = frame.pdf_point(*annotation.line[2:])
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    wings = [
        (end[0] - ARROWHEAD_LENGTH * math.cos(angle + turn), end[1] - ARROWHEAD_LENGTH * math.sin(angle + turn))
        for turn in (-ARROWHEAD_ANGLE, ARROWHEAD_ANGLE)
    ]
    drawing = [
        f"{_color(annotation)} RG {LINE_WIDTH:g} w",
        f"{_path([start, end])} S",
        "1 J 1 j",  # Round ends and corner for the arrowhead.
        f"{_path([wings[0], end, wings[1]])} S",
    ]
    margin = LINE_WIDTH
    points = [start, end, *wings]
    xs, ys = [x for x, _y in points], [y for _x, y in points]
    entries: dict[str, object] = {
        "/Rect": pikepdf.Array(_rounded((min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin))),
        "/L": pikepdf.Array(_rounded((*start, *end))),
        "/LE": pikepdf.Array([pikepdf.Name("/None"), pikepdf.Name.OpenArrow]),
        "/BS": _border(),
    }
    return _Written(entries, drawing)


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


def _date(moment: datetime | None) -> pikepdf.String:
    """A PDF date (7.9.4), in UTC; now if none is given."""
    return pikepdf.String(f"D:{(moment or datetime.now(UTC)).astimezone(UTC):%Y%m%d%H%M%S}Z")


def _border() -> pikepdf.Dictionary:
    """A solid border of the line width (12.5.4)."""
    return pikepdf.Dictionary(Type=pikepdf.Name.Border, W=LINE_WIDTH, S=pikepdf.Name.S)


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
