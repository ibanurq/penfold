"""Moving annotations and changing their size with handles (D72, D73).

Rectangles and circles have a handle at each corner, arrows one at each end; text boxes have one at each side, which
change only their width (rendering/text_box.py: their height follows the text). Comments are only moved. Marks on text
(highlights, underlines, strikethroughs) have one where they start and one where they end, and they cover the text
from one to the other (the interface asks Poppler for it); they do not move. Everything stays inside the annotation's
page.

Points and rectangles are those of the annotations: in points of the unturned page, from its top left corner.
"""

import enum
import math
from dataclasses import replace

from penfold.document.annotations import TEXT_MARKUPS, Annotation, Kind
from penfold.document.geometry import Rectangle, Size, bounds

Point = tuple[float, float]
# The smallest width or height of a shape, and the shortest arrow, in points: a smaller one would hardly be seen.
SMALLEST_SIZE = 3.0
MOVABLE = frozenset({Kind.RECTANGLE, Kind.CIRCLE, Kind.ARROW, Kind.COMMENT, Kind.TEXT_BOX})
RESIZABLE = frozenset({Kind.RECTANGLE, Kind.CIRCLE, Kind.ARROW, Kind.TEXT_BOX, *TEXT_MARKUPS})


class Handle(enum.Enum):
    """What a handle changes: a corner of a rectangle or circle, an end of an arrow, a side of a text box."""

    TOP_LEFT = "top-left"
    TOP_RIGHT = "top-right"
    BOTTOM_RIGHT = "bottom-right"
    BOTTOM_LEFT = "bottom-left"
    START = "start"
    END = "end"
    LEFT = "left"
    """The side where a text box's lines start, as its text reads."""
    RIGHT = "right"
    """The side where a text box's lines end, as its text reads."""


CORNERS = (Handle.TOP_LEFT, Handle.TOP_RIGHT, Handle.BOTTOM_RIGHT, Handle.BOTTOM_LEFT)


def can_move(annotation: Annotation) -> bool:
    """Whether an annotation is of a type that is moved as a whole."""
    return annotation.kind in MOVABLE


def can_resize(annotation: Annotation) -> bool:
    """Whether an annotation is of a type whose size or ends change with handles (marks: the text they cover)."""
    return annotation.kind in RESIZABLE


def moved(annotation: Annotation, offset: Point, page_size: Size) -> Annotation:
    """The annotation moved by an offset, as far as it stays inside its page (it is not pushed in if already out).

    Everything moves with it: its rectangle, the areas of its text, its line. Nothing else changes: one of a PDF that
    Penfold does not manage keeps the drawing its program made, moved as far (moved_by, D73).
    """
    dx, dy = _shift_inside(annotation.rectangle, offset, page_size)
    moved_x, moved_y = annotation.moved_by
    return replace(
        annotation,
        rectangle=_shifted(annotation.rectangle, dx, dy),
        quads=tuple(_shifted(quad, dx, dy) for quad in annotation.quads),
        line=None if annotation.line is None else _shifted(annotation.line, dx, dy),
        moved_by=annotation.moved_by if annotation.managed else (moved_x + dx, moved_y + dy),
    )


def corner_handles(annotation: Annotation) -> dict[Handle, Point]:
    """Where the handles of a rectangle or circle are: its corners."""
    left, top, right, bottom = annotation.rectangle
    return {
        Handle.TOP_LEFT: (left, top),
        Handle.TOP_RIGHT: (right, top),
        Handle.BOTTOM_RIGHT: (right, bottom),
        Handle.BOTTOM_LEFT: (left, bottom),
    }


def end_handles(annotation: Annotation) -> dict[Handle, Point]:
    """Where the handles of an arrow are: its start and its end."""
    if annotation.line is None:
        return {}
    start_x, start_y, end_x, end_y = annotation.line
    return {Handle.START: (start_x, start_y), Handle.END: (end_x, end_y)}


def mark_handles(annotation: Annotation) -> dict[Handle, Point]:
    """Where the handles of a mark on text are: the middle of the start of its first line and of the end of its last."""
    if not annotation.quads:
        return {}
    lines = sorted(annotation.quads, key=lambda line: (line[1], line[0]))
    first_left, first_top, _right, first_bottom = lines[0]
    _left, last_top, last_right, last_bottom = lines[-1]
    return {
        Handle.START: (first_left, (first_top + first_bottom) / 2),
        Handle.END: (last_right, (last_top + last_bottom) / 2),
    }


def mark_tips(annotation: Annotation) -> dict[Handle, Point]:
    """Where the tips of a mark's drops go (D76): the top left of its first line, the bottom right of its last."""
    if not annotation.quads:
        return {}
    lines = sorted(annotation.quads, key=lambda line: (line[1], line[0]))
    first_left, first_top, _right, _bottom = lines[0]
    _left, _top, last_right, last_bottom = lines[-1]
    return {Handle.START: (first_left, first_top), Handle.END: (last_right, last_bottom)}


def with_lines(annotation: Annotation, lines: list[Rectangle]) -> Annotation:
    """A mark on text covering other lines of text (as selected); with none, it stays as it was."""
    if not lines:
        return annotation
    return replace(annotation, quads=tuple(lines), rectangle=bounds(lines))


def with_corner(annotation: Annotation, corner: Handle, point: Point, page_size: Size) -> Annotation:
    """A rectangle or circle with a corner taken to a point of its page; the opposite corner stays where it was.

    Taken past the opposite corner, the shape turns over; it never gets smaller than SMALLEST_SIZE.

    Raises:
        ValueError: the handle is not a corner.
    """
    if corner not in CORNERS:
        message = f"{corner} is not a corner"
        raise ValueError(message)
    opposite = CORNERS[(CORNERS.index(corner) + 2) % len(CORNERS)]
    fixed_x, fixed_y = corner_handles(annotation)[opposite]
    width, height = page_size
    x, y = _reach(fixed_x, point[0], width), _reach(fixed_y, point[1], height)
    return replace(annotation, rectangle=(min(x, fixed_x), min(y, fixed_y), max(x, fixed_x), max(y, fixed_y)))


def with_end(annotation: Annotation, end: Handle, point: Point, page_size: Size) -> Annotation:
    """An arrow with one of its ends taken to a point of its page; the other end stays where it was.

    Closer to the other end than SMALLEST_SIZE, the arrow stays as it was.

    Raises:
        ValueError: the handle is not an end, or the annotation has no line.
    """
    ends = end_handles(annotation)
    if end not in ends:
        message = f"{end} is not an end of this annotation"
        raise ValueError(message)
    width, height = page_size
    x, y = min(max(point[0], 0.0), width), min(max(point[1], 0.0), height)
    other_x, other_y = ends[Handle.END if end is Handle.START else Handle.START]
    if math.hypot(x - other_x, y - other_y) < SMALLEST_SIZE:
        return annotation
    line = (x, y, other_x, other_y) if end is Handle.START else (other_x, other_y, x, y)
    return replace(
        annotation, line=line, rectangle=(min(x, other_x), min(y, other_y), max(x, other_x), max(y, other_y))
    )


def _shift_inside(rectangle: Rectangle, offset: Point, page_size: Size) -> Point:
    """How far a rectangle can move by an offset without going (further) out of the page."""
    left, top, right, bottom = rectangle
    width, height = page_size
    dx, dy = offset
    return (
        min(max(dx, min(0.0, -left)), max(0.0, width - right)),
        min(max(dy, min(0.0, -top)), max(0.0, height - bottom)),
    )


def _shifted(rectangle: Rectangle, dx: float, dy: float) -> Rectangle:
    left, top, right, bottom = rectangle
    return left + dx, top + dy, right + dx, bottom + dy


def _reach(fixed: float, to: float, limit: float) -> float:
    """Where a side taken towards a coordinate ends up, kept in the page (0 to limit) and SMALLEST_SIZE from fixed."""
    to = min(max(to, 0.0), limit)
    if abs(to - fixed) >= SMALLEST_SIZE:
        return to
    nearest = fixed + SMALLEST_SIZE if to >= fixed else fixed - SMALLEST_SIZE
    # Too close to the edge of the page on that side: on the other side of the fixed one.
    return nearest if 0.0 <= nearest <= limit else 2 * fixed - nearest
