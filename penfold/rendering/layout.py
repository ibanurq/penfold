"""Where the pages of the opened PDF are shown: in the order of the document and with the turn Penfold adds.

Poppler, bookmarks and annotations know a page by its index in the opened PDF (its source) and measure it unturned.
The interface shows the pages of the document by their position, turned. A layout translates one into the other.
Positions in a page are in points from its top left corner, before (source) or after (shown) the turn.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from penfold.document.pages import FULL_TURN, Page

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


@dataclass(frozen=True)
class ShownPage:
    """A page as it is shown: which page of the opened PDF it is, its unturned size and its turn."""

    source: int
    source_size: Size
    rotation: int = 0

    @property
    def size(self) -> Size:
        """Its size as shown."""
        return turned_size(self.source_size, self.rotation)

    def to_source(self, x: float, y: float) -> tuple[float, float]:
        """The point of the unturned page under a point of the page as shown."""
        return unturn_point(x, y, self.source_size, self.rotation)

    def from_source(self, rectangle: Rectangle) -> Rectangle:
        """Where a rectangle of the unturned page is shown."""
        return turn_rectangle(rectangle, self.source_size, self.rotation)

    def shown_top(self, top: float | None) -> float | None:
        """The height to show for a destination at a height of the unturned page (B8).

        Turned a quarter, the height of the page runs across: the destination is the start of the page.
        """
        if top is None or self.rotation % HALF_TURN:
            return None
        return self.source_size[1] - top if self.rotation else top


class PageLayout:
    """The pages of the document as they are shown, by position."""

    def __init__(self, source_sizes: list[Size], pages: Iterable[Page] | None = None) -> None:
        """Lay out these pages of a PDF whose pages have these sizes; by default, all of them in order, unturned."""
        chosen = pages if pages is not None else (Page(index) for index in range(len(source_sizes)))
        self.pages = [ShownPage(page.source_index, source_sizes[page.source_index], page.rotation) for page in chosen]
        self.sizes = [page.size for page in self.pages]
        self._positions = {page.source: position for position, page in enumerate(self.pages)}

    def __len__(self) -> int:
        """Number of pages shown."""
        return len(self.pages)

    def __getitem__(self, position: int) -> ShownPage:
        """The page shown at a position."""
        return self.pages[position]

    def position(self, source: int) -> int | None:
        """Where a page of the opened PDF is shown, or None if it was deleted."""
        return self._positions.get(source)

    def place(self, source: int, top: float | None) -> tuple[int, float | None] | None:
        """Where a destination of the opened PDF (a page and a height) is shown; None if its page was deleted."""
        position = self.position(source)
        if position is None:
            return None
        return position, self.pages[position].shown_top(top)
