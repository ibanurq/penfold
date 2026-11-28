"""Where the source pages are shown: in the order of the document and with the turn Penfold adds.

Poppler, bookmarks and annotations know a page by its source index (document/sources.py) and measure it unturned.
The interface shows the pages of the document by their position, turned. A layout translates one into the other.
Positions in a page are in points from its top left corner, before (source) or after (shown) the turn.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from penfold.document.geometry import HALF_TURN, Rectangle, Size, turn_rectangle, turned_size, unturn_point
from penfold.document.pages import Page


@dataclass(frozen=True)
class ShownPage:
    """A page as it is shown: which source page it is (its source index), its unturned size and its turn."""

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

    def to_source_rectangle(self, rectangle: Rectangle) -> Rectangle:
        """The rectangle of the unturned page under a rectangle of the page as shown."""
        left, top, right, bottom = rectangle
        corners = [self.to_source(left, top), self.to_source(right, bottom)]
        xs, ys = [x for x, _y in corners], [y for _x, y in corners]
        return min(xs), min(ys), max(xs), max(ys)

    def shown_top(self, top: float | None) -> float | None:
        """The height to show for a destination at a height of the unturned page.

        Turned a quarter, the height of the page runs across: the destination is the start of the page.
        """
        if top is None or self.rotation % HALF_TURN:
            return None
        return self.source_size[1] - top if self.rotation else top


class PageLayout:
    """The pages of the document as they are shown, by position."""

    def __init__(self, source_sizes: list[Size], pages: Iterable[Page] | None = None) -> None:
        """Lay out these pages, given the size of every source page; by default, all of them in order, unturned."""
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
        """Where a page is shown, by its source index, or None if it is not in the document."""
        return self._positions.get(source)

    def place(self, source: int, top: float | None) -> tuple[int, float | None] | None:
        """Where a destination (a page's source index and a height) is shown; None if its page is not shown."""
        position = self.position(source)
        if position is None:
            return None
        return position, self.pages[position].shown_top(top)
