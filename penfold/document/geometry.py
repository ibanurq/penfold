"""Turning pages: where sizes, points and rectangles of a page go when it is turned clockwise.

Positions are in points from the top left corner of the page; rectangles are left, top, right, bottom.
"""

from collections.abc import Iterable

from penfold.document.pages import FULL_TURN

Size = tuple[float, float]
Rectangle = tuple[float, float, float, float]  # left, top, right, bottom
HALF_TURN = 180


def turned_size(size: Size, rotation: int) -> Size:
    """The size of a page after turning it clockwise by 0, 90, 180 or 270 degrees."""
    width, height = size
    return (height, width) if rotation % HALF_TURN else (width, height)


def turn_point(x: float, y: float, size: Size, rotation: int) -> tuple[float, float]:
    """Where a point of an unturned page of this size goes once the page is turned clockwise."""
    width, height = size
    match rotation % FULL_TURN:
        case 90:
            return height - y, x
        case 180:
            return width - x, height - y
        case 270:
            return y, width - x
        case _:
            return x, y


def unturn_point(x: float, y: float, size: Size, rotation: int) -> tuple[float, float]:
    """Where a point of a turned page was before the turn; size is the unturned one."""
    return turn_point(x, y, turned_size(size, rotation), -rotation % FULL_TURN)


def turn_rectangle(rectangle: Rectangle, size: Size, rotation: int) -> Rectangle:
    """Where a rectangle of an unturned page goes once the page is turned clockwise."""
    left, top, right, bottom = rectangle
    x1, y1 = turn_point(left, top, size, rotation)
    x2, y2 = turn_point(right, bottom, size, rotation)
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def bounds(rectangles: Iterable[Rectangle]) -> Rectangle:
    """The rectangle around some rectangles (the lines a mark covers); there must be at least one."""
    chosen = list(rectangles)
    return (
        min(item[0] for item in chosen),
        min(item[1] for item in chosen),
        max(item[2] for item in chosen),
        max(item[3] for item in chosen),
    )


def merge_lines(rectangles: Iterable[Rectangle]) -> list[Rectangle]:
    """Join the areas of selected text that are on the same line into one rectangle per line.

    Two areas are on one line when they overlap by at least half the height of the lower one. Lines go from the top.
    """
    lines: list[Rectangle] = []
    for left, top, right, bottom in sorted(rectangles, key=lambda area: (area[1], area[0])):
        if lines:
            line_left, line_top, line_right, line_bottom = lines[-1]
            overlap = min(bottom, line_bottom) - max(top, line_top)
            if overlap >= min(bottom - top, line_bottom - line_top) / 2:
                lines[-1] = (min(left, line_left), min(top, line_top), max(right, line_right), max(bottom, line_bottom))
                continue
        lines.append((left, top, right, bottom))
    return lines
