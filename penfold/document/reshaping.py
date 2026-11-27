"""Moving annotations and changing their size with handles.

Rectangles, circles, freehand drawings and images have a handle at each corner (images keep their proportion), arrows
one at each end; text boxes have one at each side, which change only their width (rendering/text_box.py: their height
follows the text). Comments are only moved. Marks on text (highlights, underlines, strikethroughs) have one where they
start and one where they end, and they cover the text from one to the other (the interface asks Poppler for it); they do
not move. Everything stays inside the annotation's page. An image being put on a page goes where placed or dragged
say.

Points and rectangles are those of the annotations: in points of the unturned page, from its top left corner.
"""

import enum
import math
from dataclasses import replace

from penfold.document.annotations import TEXT_MARKUPS, Annotation, Kind
from penfold.document.freehand import freehand_rectangle
from penfold.document.geometry import Rectangle, Size, bounds

Point = tuple[float, float]
# The smallest width or height of a shape, and the shortest arrow, in points: a smaller one would hardly be seen. A
# freehand drawing's strokes are kept this big, inside its line.
SMALLEST_SIZE = 3.0
# Less wide or tall than this, in points, a freehand drawing (a straight stroke) is not stretched that way.
FLAT = 1e-6
MOVABLE = frozenset({Kind.RECTANGLE, Kind.CIRCLE, Kind.ARROW, Kind.FREEHAND, Kind.COMMENT, Kind.TEXT_BOX, Kind.IMAGE})
RESIZABLE = frozenset(
    {Kind.RECTANGLE, Kind.CIRCLE, Kind.ARROW, Kind.FREEHAND, Kind.TEXT_BOX, Kind.IMAGE, *TEXT_MARKUPS}
)


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

    Everything moves with it: its rectangle, the areas of its text, its line, its strokes. Nothing else changes: one of
    a PDF that Penfold does not manage keeps the drawing its program made, moved as far (moved_by).
    """
    dx, dy = _shift_inside(annotation.rectangle, offset, page_size)
    moved_x, moved_y = annotation.moved_by
    return replace(
        annotation,
        rectangle=_shifted(annotation.rectangle, dx, dy),
        quads=tuple(_shifted(quad, dx, dy) for quad in annotation.quads),
        line=None if annotation.line is None else _shifted(annotation.line, dx, dy),
        strokes=tuple(tuple((x + dx, y + dy) for x, y in stroke) for stroke in annotation.strokes),
        moved_by=annotation.moved_by if annotation.managed else (moved_x + dx, moved_y + dy),
    )


def corner_handles(annotation: Annotation) -> dict[Handle, Point]:
    """Where the handles of a rectangle, circle, freehand drawing or image are: the corners of its rectangle."""
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
    """Where the tips of a mark's drops go: the top left of its first line, the bottom right of its last."""
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
    """A rectangle, circle, freehand drawing or image with a corner taken to a point of its page; the opposite stays.

    Taken past the opposite corner, the shape turns over; it never gets smaller than SMALLEST_SIZE. A freehand drawing's
    strokes are stretched or shrunk to fill its new rectangle, inside its line, which keeps its width; they do not turn
    over, so that it is never seen mirrored. An image keeps its proportion (_scaled).

    Raises:
        ValueError: the handle is not a corner.
    """
    if corner not in CORNERS:
        message = f"{corner} is not a corner"
        raise ValueError(message)
    opposite = CORNERS[(CORNERS.index(corner) + 2) % len(CORNERS)]
    fixed_x, fixed_y = corner_handles(annotation)[opposite]
    if annotation.kind is Kind.IMAGE:
        return _scaled(annotation, corner, (fixed_x, fixed_y), point, page_size)
    width, height = page_size
    smallest = SMALLEST_SIZE + 2 * _margin(annotation) if annotation.kind is Kind.FREEHAND else SMALLEST_SIZE
    x, y = _reach(fixed_x, point[0], width, smallest), _reach(fixed_y, point[1], height, smallest)
    rectangle = (min(x, fixed_x), min(y, fixed_y), max(x, fixed_x), max(y, fixed_y))
    if annotation.kind is Kind.FREEHAND:
        return _stretched(annotation, rectangle)
    return replace(annotation, rectangle=rectangle)


def _scaled(annotation: Annotation, corner: Handle, fixed: Point, point: Point, page_size: Size) -> Annotation:
    """An image grown or shrunk from its fixed corner towards a point, keeping its proportion.

    It follows the pointer along the side it is taken furthest by, as much as it fits in the page, and never turns over
    (it is never seen mirrored); its shorter side never gets smaller than SMALLEST_SIZE.
    """
    left, top, right, bottom = annotation.rectangle
    width, height = max(right - left, FLAT), max(bottom - top, FLAT)
    corner_x, corner_y = corner_handles(annotation)[corner]
    towards_x, towards_y = (1 if corner_x >= fixed[0] else -1), (1 if corner_y >= fixed[1] else -1)
    scale = max((point[0] - fixed[0]) * towards_x / width, (point[1] - fixed[1]) * towards_y / height)
    page_width, page_height = page_size
    room_x = page_width - fixed[0] if towards_x > 0 else fixed[0]
    room_y = page_height - fixed[1] if towards_y > 0 else fixed[1]
    scale = max(min(scale, room_x / width, room_y / height), SMALLEST_SIZE / min(width, height))
    x, y = fixed[0] + towards_x * width * scale, fixed[1] + towards_y * height * scale
    return replace(annotation, rectangle=(min(x, fixed[0]), min(y, fixed[1]), max(x, fixed[0]), max(y, fixed[1])))


def _stretched(annotation: Annotation, rectangle: Rectangle) -> Annotation:
    """A freehand drawing with its strokes stretched or shrunk to fill a rectangle, inside its line.

    Its rectangle is then that of its strokes and their line around: where its handles are next.
    """
    margin = _margin(annotation)
    points = [point for stroke in annotation.strokes for point in stroke]
    old = bounds([(x, y, x, y) for x, y in points])
    left, top, right, bottom = rectangle
    new = (left + margin, top + margin, right - margin, bottom - margin)
    strokes = tuple(tuple(_fitted(point, old, new) for point in stroke) for stroke in annotation.strokes)
    return replace(annotation, strokes=strokes, rectangle=freehand_rectangle(strokes, margin))


def _fitted(point: Point, old: Rectangle, new: Rectangle) -> Point:
    """A point of one rectangle at the same place in another; along a side the old one does not have, in the middle."""
    fitted = []
    for axis in (0, 1):
        old_start, old_end, new_start, new_end = old[axis], old[axis + 2], new[axis], new[axis + 2]
        if old_end - old_start < FLAT:
            fitted.append((new_start + new_end) / 2)
        else:
            fitted.append(new_start + (point[axis] - old_start) * (new_end - new_start) / (old_end - old_start))
    return fitted[0], fitted[1]


def _margin(annotation: Annotation) -> float:
    """How far a freehand drawing's rectangle is from its strokes: as far as its line is wide, as when it is saved."""
    return annotation.style.line_width


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


def _reach(fixed: float, to: float, limit: float, smallest: float = SMALLEST_SIZE) -> float:
    """Where a side taken towards a coordinate ends up, kept in the page (0 to limit) and smallest from fixed."""
    to = min(max(to, 0.0), limit)
    if abs(to - fixed) >= smallest:
        return to
    nearest = fixed + smallest if to >= fixed else fixed - smallest
    # Too close to the edge of the page on that side: on the other side of the fixed one.
    return nearest if 0.0 <= nearest <= limit else 2 * fixed - nearest


def placed(corner: Point, size: Size, page_size: Size) -> Rectangle:
    """Where an image of a size goes with its top left corner at a point of a page.

    It is as big as it is, unless it is bigger than the page: then it is shrunk to fit, keeping its proportion. It is
    moved in from the edges of the page as far as it needs, so that it is all inside.
    """
    width, height = max(size[0], FLAT), max(size[1], FLAT)
    page_width, page_height = page_size
    scale = min(1.0, page_width / width, page_height / height)
    width, height = width * scale, height * scale
    left = min(max(corner[0], 0.0), page_width - width)
    top = min(max(corner[1], 0.0), page_height - height)
    return left, top, left + width, top + height


def dragged(start: Point, point: Point, size: Size, page_size: Size) -> Rectangle | None:
    """The rectangle a drag frames for an image of a size: from where it started, keeping the image's proportion.

    Its top left corner is where the drag started and its bottom right corner follows the pointer, along the side it is
    taken furthest by: further right or down, bigger; back left or up, smaller, never smaller than SMALLEST_SIZE nor
    out of the page. A drag shorter than SMALLEST_SIZE is a click: None.
    """
    if max(abs(point[0] - start[0]), abs(point[1] - start[1])) < SMALLEST_SIZE:
        return None
    width, height = max(size[0], FLAT), max(size[1], FLAT)
    page_width, page_height = page_size
    scale = max((point[0] - start[0]) / width, (point[1] - start[1]) / height)
    scale = min(scale, (page_width - start[0]) / width, (page_height - start[1]) / height)
    scale = max(scale, SMALLEST_SIZE / min(width, height))
    return start[0], start[1], start[0] + width * scale, start[1] + height * scale
