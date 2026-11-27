"""Freehand drawings: the stroke a drag draws, smoothed a little, and the rectangle around strokes.

A stroke drawn with a mouse or a pen trembles a little and has many points, one for each move. When it is finished it
is smoothed, so that it does not look jagged, without changing its shape: points too close together are left out, the
others are averaged with their neighbours (the ends stay where they are), and those not needed to keep its shape within
a fraction of a point are left out.

Points are in points of the page, as those of the annotations.
"""

import math
from collections.abc import Iterable

from penfold.document.geometry import Rectangle

Point = tuple[float, float]
# Points closer than this to the last one kept are left out: the trembling of the hand, and many moves on the spot.
SPACING = 0.75
# How many times each point is averaged with its neighbours (half itself, a quarter each of them).
SMOOTHING_PASSES = 2
# How far, at most, the stroke left may be from the points left out at the end.
TOLERANCE = 0.2


def smoothed(points: Iterable[Point]) -> tuple[Point, ...]:
    """A stroke drawn by hand, smoothed a little without changing its shape; it starts and ends where it did."""
    kept = _spaced(list(points))
    for _ in range(SMOOTHING_PASSES):
        kept = _averaged(kept)
    return tuple(_simplified(kept))


def freehand_rectangle(strokes: Iterable[Iterable[Point]], line_width: float) -> Rectangle:
    """The rectangle around a freehand drawing's strokes and their line: as far from them as its line is wide.

    It is how far the rectangle of a saved one is from its strokes (document/appearance.py).
    """
    points = [point for stroke in strokes for point in stroke]
    xs, ys = [x for x, _y in points], [y for _x, y in points]
    return min(xs) - line_width, min(ys) - line_width, max(xs) + line_width, max(ys) + line_width


def _spaced(points: list[Point]) -> list[Point]:
    """The points without those too close to the one before; the last one is always kept, as the end of the stroke."""
    if not points:
        return []
    kept = [points[0]]
    for point in points[1:]:
        if math.dist(point, kept[-1]) >= SPACING:
            kept.append(point)
    if len(points) > 1 and kept[-1] != points[-1]:
        if len(kept) > 1:
            kept[-1] = points[-1]  # Too close to the last one kept: it takes its place.
        else:
            kept.append(points[-1])
    return kept


def _averaged(points: list[Point]) -> list[Point]:
    """Each point between the ends, averaged with its neighbours."""
    if len(points) < 3:  # noqa: PLR2004 (two ends and something between them)
        return points
    inside = [
        ((before[0] + 2 * point[0] + after[0]) / 4, (before[1] + 2 * point[1] + after[1]) / 4)
        for before, point, after in zip(points, points[1:], points[2:], strict=False)
    ]
    return [points[0], *inside, points[-1]]


def _simplified(points: list[Point]) -> list[Point]:
    """The points needed for the stroke to pass within TOLERANCE of all of them (Ramer-Douglas-Peucker)."""
    if len(points) < 3:  # noqa: PLR2004 (two ends and something between them)
        return points
    needed = [False] * len(points)
    needed[0] = needed[-1] = True
    spans = [(0, len(points) - 1)]
    while spans:
        first, last = spans.pop()
        farthest, distance = first, 0.0
        for index in range(first + 1, last):
            away = _distance_to_segment(points[index], points[first], points[last])
            if away > distance:
                farthest, distance = index, away
        if distance > TOLERANCE:
            needed[farthest] = True
            spans += [(first, farthest), (farthest, last)]
    return [point for point, keep in zip(points, needed, strict=True) if keep]


def _distance_to_segment(point: Point, start: Point, end: Point) -> float:
    length = math.dist(start, end) ** 2
    if not length:
        return math.dist(point, start)
    along = ((point[0] - start[0]) * (end[0] - start[0]) + (point[1] - start[1]) * (end[1] - start[1])) / length
    along = min(1.0, max(0.0, along))
    return math.dist(point, (start[0] + along * (end[0] - start[0]), start[1] + along * (end[1] - start[1])))
