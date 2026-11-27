"""Moving annotations and changing their size with handles."""

from dataclasses import replace

import pytest

from penfold.document.annotations import Annotation, Kind, Style, new_annotation
from penfold.document.reshaping import (
    SMALLEST_SIZE,
    Handle,
    can_move,
    can_resize,
    corner_handles,
    end_handles,
    mark_handles,
    mark_tips,
    moved,
    with_corner,
    with_end,
    with_lines,
)

PAGE = (600.0, 800.0)
RED = (0.9, 0.2, 0.2)


def shape(
    kind: Kind = Kind.RECTANGLE, rectangle: tuple[float, float, float, float] = (100, 100, 200, 150)
) -> Annotation:
    return new_annotation(kind, 0, rectangle, RED, "Iban")


def arrow(line: tuple[float, float, float, float] = (100, 100, 200, 150)) -> Annotation:
    start_x, start_y, end_x, end_y = line
    rectangle = (min(start_x, end_x), min(start_y, end_y), max(start_x, end_x), max(start_y, end_y))
    return new_annotation(Kind.ARROW, 0, rectangle, RED, "Iban", line=line)


def test_which_types_move_and_which_change_their_size() -> None:
    marks = new_annotation(Kind.HIGHLIGHT, 0, (10, 10, 50, 20), RED, "Iban", quads=((10, 10, 50, 20),))
    comment = shape(Kind.COMMENT, (10, 10, 30, 30))
    drawn = new_annotation(Kind.FREEHAND, 0, (10, 10, 30, 30), RED, "Iban", strokes=(((10, 10), (30, 30)),))
    assert [can_move(item) for item in (shape(), arrow(), comment, marks, drawn)] == [True, True, True, False, True]
    assert [can_resize(item) for item in (shape(), arrow(), comment, marks, drawn)] == [True, True, False, True, True]
    assert (can_move(image()), can_resize(image())) == (True, True)


def test_moving_takes_everything_along_and_keeps_the_rest() -> None:
    marks = new_annotation(Kind.UNDERLINE, 0, (10, 10, 50, 40), RED, "Iban", quads=((10, 10, 50, 20), (10, 30, 40, 40)))
    assert moved(marks, (5, 7), PAGE).quads == ((15, 17, 55, 27), (15, 37, 45, 47))
    assert moved(marks, (5, 7), PAGE).rectangle == (15, 17, 55, 47)
    original = arrow()
    pointing = moved(original, (-20, 30), PAGE)
    assert (pointing.line, pointing.rectangle) == ((80, 130, 180, 180), (80, 130, 180, 180))
    assert (pointing.name, pointing.color, pointing.style) == (original.name, original.color, original.style)
    drawn = new_annotation(Kind.FREEHAND, 0, (10, 10, 40, 30), RED, "Iban", strokes=(((10, 10), (40, 30)), ((20, 20),)))
    assert moved(drawn, (5, 7), PAGE).strokes == (((15, 17), (45, 37)), ((25, 27),))


def test_moving_stops_at_the_edges_of_the_page() -> None:
    assert moved(shape(), (-500, -500), PAGE).rectangle == (0, 0, 100, 50)
    assert moved(shape(), (900, 900), PAGE).rectangle == (500, 750, 600, 800)


def test_one_already_out_of_the_page_is_not_pushed_in_but_goes_no_further() -> None:
    out = shape(rectangle=(-30, 100, 70, 150))
    assert moved(out, (0, 10), PAGE).rectangle == (-30, 110, 70, 160)
    assert moved(out, (-10, 0), PAGE).rectangle == (-30, 100, 70, 150)
    assert moved(out, (10, 0), PAGE).rectangle == (-20, 100, 80, 150)


def test_the_handles_of_a_shape_are_its_corners_and_of_an_arrow_its_ends() -> None:
    assert corner_handles(shape()) == {
        Handle.TOP_LEFT: (100, 100),
        Handle.TOP_RIGHT: (200, 100),
        Handle.BOTTOM_RIGHT: (200, 150),
        Handle.BOTTOM_LEFT: (100, 150),
    }
    assert end_handles(arrow()) == {Handle.START: (100, 100), Handle.END: (200, 150)}


@pytest.mark.parametrize(
    ("corner", "point", "expected"),
    [
        (Handle.BOTTOM_RIGHT, (250, 180), (100, 100, 250, 180)),
        (Handle.TOP_LEFT, (50, 60), (50, 60, 200, 150)),
        (Handle.TOP_RIGHT, (300, 20), (100, 20, 300, 150)),
        (Handle.BOTTOM_LEFT, (90, 400), (90, 100, 200, 400)),
    ],
)
def test_a_corner_goes_where_it_is_taken_and_the_opposite_one_stays(
    corner: Handle, point: tuple[float, float], expected: tuple[float, float, float, float]
) -> None:
    assert with_corner(shape(), corner, point, PAGE).rectangle == expected


def test_taken_past_the_opposite_corner_the_shape_turns_over() -> None:
    assert with_corner(shape(Kind.CIRCLE), Handle.BOTTOM_RIGHT, (40, 20), PAGE).rectangle == (40, 20, 100, 100)


def test_a_corner_stays_inside_the_page() -> None:
    assert with_corner(shape(), Handle.BOTTOM_RIGHT, (900, 1000), PAGE).rectangle == (100, 100, 600, 800)
    assert with_corner(shape(), Handle.TOP_LEFT, (-50, -9), PAGE).rectangle == (0, 0, 200, 150)


def test_a_shape_never_gets_smaller_than_the_smallest_size() -> None:
    squeezed = with_corner(shape(), Handle.BOTTOM_RIGHT, (101, 99), PAGE).rectangle
    assert squeezed == (100, 100 - SMALLEST_SIZE, 100 + SMALLEST_SIZE, 100)


def test_at_the_edge_of_the_page_the_smallest_shape_goes_the_other_way() -> None:
    at_edge = shape(rectangle=(0, 0, 50, 50))
    assert with_corner(at_edge, Handle.TOP_RIGHT, (-20, 30), PAGE).rectangle == (0, 30, SMALLEST_SIZE, 50)


def image(rectangle: tuple[float, float, float, float] = (100, 100, 220, 180)) -> Annotation:
    """An image 3 wide for 2 tall (its drawing does not matter here)."""
    return replace(shape(rectangle=rectangle), kind=Kind.IMAGE, subtype="Stamp", color=None)


@pytest.mark.parametrize(
    ("corner", "point", "expected"),
    [
        (Handle.BOTTOM_RIGHT, (340, 200), (100, 100, 340, 260)),  # Taken furthest across: it follows across.
        (Handle.BOTTOM_RIGHT, (230, 340), (100, 100, 460, 340)),  # Taken furthest down: it follows down.
        (Handle.TOP_LEFT, (160, 170), (160, 140, 220, 180)),  # Shrunk towards the opposite corner.
        (Handle.TOP_RIGHT, (280, 120), (100, 60, 280, 180)),
        (Handle.BOTTOM_LEFT, (40, 180), (40, 100, 220, 220)),
    ],
)
def test_an_image_keeps_its_proportion(
    corner: Handle, point: tuple[float, float], expected: tuple[float, float, float, float]
) -> None:
    assert with_corner(image(), corner, point, PAGE).rectangle == pytest.approx(expected)


def test_an_image_does_not_turn_over_and_stays_inside_the_page() -> None:
    past = with_corner(image(), Handle.BOTTOM_RIGHT, (50, 50), PAGE).rectangle
    assert past == pytest.approx((100, 100, 100 + SMALLEST_SIZE * 1.5, 100 + SMALLEST_SIZE))  # Smallest, not mirrored.
    assert with_corner(image(), Handle.BOTTOM_RIGHT, (2000, 900), PAGE).rectangle == pytest.approx(
        (100, 100, 600, 100 + 500 * 2 / 3)  # As far as the right edge of the page lets it.
    )


def drawing(*strokes: tuple[tuple[float, float], ...]) -> Annotation:
    """A freehand drawing 2 points wide, its rectangle around its strokes as wide as its line."""
    points = [point for stroke in strokes for point in stroke]
    xs, ys = [x for x, _y in points], [y for _x, y in points]
    rectangle = (min(xs) - 2, min(ys) - 2, max(xs) + 2, max(ys) + 2)
    return new_annotation(Kind.FREEHAND, 0, rectangle, RED, "Iban", strokes=strokes, style=Style(line_width=2))


def test_a_freehand_drawing_is_stretched_inside_its_line_and_keeps_its_width() -> None:
    original = drawing(((100, 100), (150, 120), (200, 100)), ((150, 150),))  # Its rectangle: (98, 98, 202, 152).
    stretched = with_corner(original, Handle.BOTTOM_RIGHT, (302, 202), PAGE)  # Twice as wide and as tall.
    assert stretched.strokes == (((100.0, 100.0), (200.0, 140.0), (300.0, 100.0)), ((200.0, 200.0),))
    assert stretched.rectangle == (98.0, 98.0, 302.0, 202.0)
    assert stretched.style.line_width == 2
    # Half as wide and as tall, from the other corner.
    shrunk = with_corner(original, Handle.TOP_LEFT, (148, 123), PAGE)
    assert shrunk.strokes == (((150.0, 125.0), (175.0, 135.0), (200.0, 125.0)), ((175.0, 150.0),))


def test_a_freehand_drawing_does_not_turn_over_nor_vanish() -> None:
    original = drawing(((100, 100), (200, 150)))
    past = with_corner(original, Handle.BOTTOM_RIGHT, (48, 50), PAGE)  # Past its top left corner.
    assert past.strokes == (((50.0, 52.0), (96.0, 96.0)),)  # Not mirrored.
    squeezed = with_corner(original, Handle.BOTTOM_RIGHT, (99, 99), PAGE)
    assert squeezed.rectangle == (98, 98, 98 + SMALLEST_SIZE + 4, 98 + SMALLEST_SIZE + 4)  # Its strokes, 3 points.


def test_a_straight_stroke_is_not_stretched_across() -> None:
    flat = drawing(((100, 100), (200, 100)))
    taller = with_corner(flat, Handle.BOTTOM_RIGHT, (302, 202), PAGE)
    assert taller.strokes == (((100.0, 150.0), (300.0, 150.0)),)  # Longer, in the middle of its new height.


def test_only_corners_change_a_shape() -> None:
    with pytest.raises(ValueError, match="not a corner"):
        with_corner(shape(), Handle.START, (0, 0), PAGE)


def test_an_end_of_an_arrow_goes_where_it_is_taken_and_the_other_stays() -> None:
    longer = with_end(arrow(), Handle.END, (300, 50), PAGE)
    assert (longer.line, longer.rectangle) == ((100, 100, 300, 50), (100, 50, 300, 100))
    assert with_end(arrow(), Handle.START, (250, 400), PAGE).line == (250, 400, 200, 150)


def test_an_end_stays_inside_the_page() -> None:
    assert with_end(arrow(), Handle.START, (-40, 900), PAGE).line == (0, 800, 200, 150)


def test_an_arrow_too_short_stays_as_it_was() -> None:
    original = arrow()
    assert with_end(original, Handle.END, (101, 101), PAGE) is original


def test_only_the_ends_of_an_arrow_change_it() -> None:
    with pytest.raises(ValueError, match="not an end"):
        with_end(arrow(), Handle.TOP_LEFT, (0, 0), PAGE)
    with pytest.raises(ValueError, match="not an end"):
        with_end(shape(), Handle.START, (0, 0), PAGE)


def test_the_handles_of_a_mark_are_where_its_text_starts_and_ends() -> None:
    lines = ((72, 110, 140, 122), (72, 90, 150, 102))  # Read from the PDF, not in order.
    marks = new_annotation(Kind.STRIKE_OUT, 0, (72, 90, 150, 122), RED, "Iban", quads=lines)
    assert mark_handles(marks) == {Handle.START: (72, 96), Handle.END: (140, 116)}
    # The drops point at its first letter from above and at its last from below.
    assert mark_tips(marks) == {Handle.START: (72, 90), Handle.END: (140, 122)}


def test_a_mark_covers_other_lines_and_its_rectangle_follows() -> None:
    marks = new_annotation(Kind.HIGHLIGHT, 0, (72, 90, 150, 102), RED, "Iban", quads=((72, 90, 150, 102),))
    longer = with_lines(marks, [(72, 90, 150, 102), (72, 110, 100, 122)])
    assert (longer.quads, longer.rectangle) == (((72, 90, 150, 102), (72, 110, 100, 122)), (72, 90, 150, 122))
    assert with_lines(marks, []) is marks  # No text: as it was.
