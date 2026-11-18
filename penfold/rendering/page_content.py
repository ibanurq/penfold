"""What a page holds besides its drawing: links and text, read with Poppler in the main thread.

Positions are in PDF points from the top left corner of the page, like the rest of the interface.
"""

from dataclasses import dataclass

import cairo
from gi.repository import Poppler

Rectangle = tuple[float, float, float, float]  # left, top, right, bottom


@dataclass(frozen=True)
class InternalTarget:
    """A place in the same PDF: a page and, if the link gives one, the height to show (B8)."""

    page: int
    top: float | None = None


@dataclass(frozen=True)
class ExternalTarget:
    """A web address, opened in the system's browser (B7, A12)."""

    uri: str


Target = InternalTarget | ExternalTarget


@dataclass(frozen=True)
class Link:
    """A clickable area of a page and where it leads."""

    area: Rectangle
    target: Target

    def contains(self, x: float, y: float) -> bool:
        """Whether a point of the page, in points, is inside the link."""
        left, top, right, bottom = self.area
        return left <= x <= right and top <= y <= bottom


# Destinations whose "top" gives the height to show.
DESTINATIONS_WITH_TOP = frozenset({Poppler.DestType.XYZ, Poppler.DestType.FITH, Poppler.DestType.FITBH})


class PageContent:
    """Links and text of the pages of one PDF, read when first needed and then kept."""

    def __init__(self, document: Poppler.Document) -> None:
        """Read from Poppler's main-thread copy of the document."""
        self._document = document
        self._links: dict[int, list[Link]] = {}

    def links(self, page: int) -> list[Link]:
        """Return the links of a page that Penfold follows: internal ones and web addresses."""
        if page not in self._links:
            self._links[page] = self._read_links(page)
        return self._links[page]

    def link_at(self, page: int, x: float, y: float) -> Link | None:
        """Return the link under a point of a page, if any."""
        return next((link for link in self.links(page) if link.contains(x, y)), None)

    def selected_text(self, page: int, selection: Rectangle, style: Poppler.SelectionStyle) -> str:
        """Return the text of a page between the two corners of a selection (from where it starts to where it ends)."""
        return self._document.get_page(page).get_selected_text(style, _poppler_rectangle(selection)) or ""

    def selection_rectangles(self, page: int, selection: Rectangle, style: Poppler.SelectionStyle) -> list[Rectangle]:
        """Return the areas to highlight for a selection on a page, in points."""
        region = self._document.get_page(page).get_selected_region(1.0, style, _poppler_rectangle(selection))
        rectangles: list[Rectangle] = []
        for index in range(region.num_rectangles()):
            area: cairo.RectangleInt = region.get_rectangle(index)
            rectangles.append((area.x, area.y, area.x + area.width, area.y + area.height))
        return rectangles

    def _read_links(self, page: int) -> list[Link]:
        poppler_page = self._document.get_page(page)
        _width, height = poppler_page.get_size()
        links = []
        for mapping in poppler_page.get_link_mapping():
            target = self._target(mapping.action)
            if target is None:
                continue
            area = mapping.area
            # Poppler gives link areas from the bottom left corner of the page.
            links.append(Link((area.x1, height - area.y2, area.x2, height - area.y1), target))
        return links

    def _target(self, action: Poppler.Action) -> Target | None:
        if action.type == Poppler.ActionType.URI:
            uri = action.uri.uri
            return ExternalTarget(uri) if uri else None
        if action.type == Poppler.ActionType.GOTO_DEST:
            return self._internal_target(action.goto_dest.dest)
        return None

    def _internal_target(self, destination: Poppler.Dest | None) -> InternalTarget | None:
        if destination is not None and destination.type == Poppler.DestType.NAMED:
            destination = self._document.find_dest(destination.named_dest)
        if destination is None or not 1 <= destination.page_num <= self._document.get_n_pages():
            return None
        page = destination.page_num - 1
        top = None
        if destination.type in DESTINATIONS_WITH_TOP and (destination.change_top or destination.top):
            _width, height = self._document.get_page(page).get_size()
            top = max(0.0, height - destination.top)
        return InternalTarget(page, top)


def _poppler_rectangle(rectangle: Rectangle) -> Poppler.Rectangle:
    result = Poppler.Rectangle()
    result.x1, result.y1, result.x2, result.y2 = rectangle
    return result
