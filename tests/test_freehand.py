"""Smoothing a stroke drawn by hand, and the rectangle around a freehand drawing."""

import itertools
import math
import random

import pytest

from penfold.document.freehand import SPACING, TOLERANCE, freehand_rectangle, smoothed


def wobbly_wave(seed: int = 1) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """A wave drawn by a trembling hand, a point every half point, and the wave it means."""
    shaky = random.Random(seed)
    meant = [(100 + x / 2, 300 + 20 * math.sin(x / 40)) for x in range(400)]
    drawn = [(x + shaky.uniform(-0.5, 0.5), y + shaky.uniform(-0.5, 0.5)) for x, y in meant]
    return drawn, meant


def distance_to(points: list[tuple[float, float]], point: tuple[float, float]) -> float:
    return min(math.dist(point, other) for other in points)


def distance_to_line(points: tuple[tuple[float, float], ...], point: tuple[float, float]) -> float:
    """How far a point is from the straight lines joining some points."""
    found = math.inf
    for (start_x, start_y), (end_x, end_y) in itertools.pairwise(points):
        length = (end_x - start_x) ** 2 + (end_y - start_y) ** 2
        along = ((point[0] - start_x) * (end_x - start_x) + (point[1] - start_y) * (end_y - start_y)) / length
        along = min(1.0, max(0.0, along))
        found = min(found, math.dist(point, (start_x + along * (end_x - start_x), start_y + along * (end_y - start_y))))
    return found


def test_it_starts_and_ends_where_it_was_drawn() -> None:
    drawn, _meant = wobbly_wave()
    stroke = smoothed(drawn)
    assert (stroke[0], stroke[-1]) == (drawn[0], drawn[-1])


def test_it_trembles_less_with_fewer_points_and_keeps_its_shape() -> None:
    drawn, meant = wobbly_wave()
    stroke = smoothed(drawn)
    assert len(stroke) < len(drawn) / 4  # Far fewer points.
    trembling = sum(distance_to(meant, point) for point in drawn) / len(drawn)
    inside = stroke[1:-1]  # Its ends stay where they were drawn.
    assert sum(distance_to(meant, point) for point in inside) / len(inside) < trembling * 0.75  # It trembles less.
    assert max(distance_to(meant, point) for point in inside) < 0.45
    assert max(distance_to_line(stroke, point) for point in meant) < 1  # And all along it.


def test_a_straight_stroke_keeps_only_its_ends() -> None:
    assert smoothed([(0.0, 0.0), (5.0, 5.0), (10.0, 10.0), (20.0, 20.0)]) == ((0.0, 0.0), (20.0, 20.0))


def test_points_on_the_spot_are_left_out() -> None:
    corner = [(0.0, 0.0), (10.0, 0.0), *[(10.0 + index * SPACING / 10, 0.0) for index in range(5)], (10.0, 10.0)]
    stroke = smoothed(corner)
    assert stroke[0] == (0.0, 0.0)
    assert stroke[-1] == (10.0, 10.0)
    assert len(stroke) <= 3  # Its two ends and its corner.


def test_a_sharp_corner_is_kept_close_to_where_it_was() -> None:
    tick = [(float(x), float(x)) for x in range(20)] + [(19.0 + x, 19.0 - 2 * x) for x in range(1, 20)]
    stroke = smoothed(tick)
    assert distance_to(list(stroke), (19.0, 19.0)) < 2  # Rounded a little, not cut off.
    assert all(distance_to(tick, point) < TOLERANCE + 1 for point in stroke)


def test_very_short_strokes_stay() -> None:
    assert smoothed([(1.0, 1.0)]) == ((1.0, 1.0),)
    assert smoothed([(1.0, 1.0), (1.2, 1.0)]) == ((1.0, 1.0), (1.2, 1.0))
    assert smoothed([]) == ()


def test_the_rectangle_is_around_its_strokes_and_its_line() -> None:
    rectangle = freehand_rectangle([[(10.0, 20.0), (30.0, 5.0)], [(50.0, 40.0)]], 2.0)
    assert rectangle == pytest.approx((8, 3, 52, 42))
