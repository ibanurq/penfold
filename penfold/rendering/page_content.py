"""What a page holds besides its drawing: links and text, read with Poppler in the main thread.

Pages are named by their source index (document/sources.py). Positions are in PDF points from the top left corner of the
page, like the rest of the interface.
"""

from collections import OrderedDict
from dataclasses import dataclass

import cairo
from gi.repository import Poppler

from penfold.rendering.poppler_sources import PopplerSources

Rectangle = tuple[float, float, float, float]  # left, top, right, bottom
# Pages whose text, with the position of each character, is kept.
CACHED_PAGES = 8
# The selected area is measured to 1/8 of a point to tell which characters it covers.
CHARACTER_PRECISION = 8.0


@dataclass(frozen=True)
class InternalTarget:
    """A place in the same PDF: a page (its source index) and, if the link gives one, the height to show."""

    page: int
    top: float | None = None


@dataclass(frozen=True)
class ExternalTarget:
    """A web address, opened in the system's browser."""

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
    """Links and text of the pages of a document, read when first needed and then kept."""

    def __init__(self, sources: PopplerSources) -> None:
        """Read from Poppler's main-thread copies of the source PDFs."""
        self._sources = sources
        self._links: dict[int, list[Link]] = {}
        self._texts: OrderedDict[int, tuple[str, list[Rectangle]]] = OrderedDict()

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
        return self._sources.page(page).get_selected_text(style, _poppler_rectangle(selection)) or ""

    def text_in_areas(self, page: int, areas: list[Rectangle]) -> str:
        """Return the text inside some areas of a page (what a highlight marks), with runs of spaces as one.

        A letter belongs to an area when its centre is inside it. Poppler's own reading of an area works like a mouse
        selection, from corner to corner, and takes text from the next line when the area touches it.
        """
        text, boxes = self._page_text(page)
        letters = []
        for character, box in zip(text, boxes, strict=True):
            x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            inside = any(left <= x <= right and top <= y <= bottom for left, top, right, bottom in areas)
            letters.append(character if inside else " ")
        return " ".join("".join(letters).split())

    def _page_text(self, page: int) -> tuple[str, list[Rectangle]]:
        """The text of a page with the box of each character, kept for the last pages read."""
        if page not in self._texts:
            poppler_page = self._sources.page(page)
            text = poppler_page.get_text() or ""
            _found, layout = poppler_page.get_text_layout()
            boxes = [(box.x1, box.y1, box.x2, box.y2) for box in layout or []]
            self._texts[page] = (text, boxes) if len(boxes) == len(text) else ("", [])
            while len(self._texts) > CACHED_PAGES:
                self._texts.popitem(last=False)
        self._texts.move_to_end(page)
        return self._texts[page]

    def selection_rectangles(self, page: int, selection: Rectangle, style: Poppler.SelectionStyle) -> list[Rectangle]:
        """Return the areas to highlight for a selection on a page, in points."""
        region = self._sources.page(page).get_selected_region(1.0, style, _poppler_rectangle(selection))
        rectangles: list[Rectangle] = []
        for index in range(region.num_rectangles()):
            area: cairo.RectangleInt = region.get_rectangle(index)
            rectangles.append((area.x, area.y, area.x + area.width, area.y + area.height))
        return rectangles

    def selected_characters(self, page: int, selection: Rectangle, style: Poppler.SelectionStyle) -> list[Rectangle]:
        """Return the boxes of the characters a selection covers on a page, in points: what a mark covers.

        The selected area Poppler gives runs over the spaces between lines; the characters' own boxes fit the text.
        """
        poppler_page = self._sources.page(page)
        region = poppler_page.get_selected_region(CHARACTER_PRECISION, style, _poppler_rectangle(selection))
        _found, boxes = poppler_page.get_text_layout()
        return [
            (box.x1, box.y1, box.x2, box.y2)
            for box in boxes
            if box.x2 > box.x1
            and box.y2 > box.y1
            and region.contains_point(
                int((box.x1 + box.x2) / 2 * CHARACTER_PRECISION), int((box.y1 + box.y2) / 2 * CHARACTER_PRECISION)
            )
        ]

    def _read_links(self, page: int) -> list[Link]:
        poppler_page = self._sources.page(page)
        _width, height = poppler_page.get_size()
        links = []
        for mapping in poppler_page.get_link_mapping():
            target = self._target(mapping.action, page)
            if target is None:
                continue
            area = mapping.area
            # Poppler gives link areas from the bottom left corner of the page.
            links.append(Link((area.x1, height - area.y2, area.x2, height - area.y1), target))
        return links

    def _target(self, action: Poppler.Action, page: int) -> Target | None:
        """Where a link of a page leads."""
        if action.type == Poppler.ActionType.URI:
            uri = action.uri.uri
            return ExternalTarget(uri) if uri else None
        if action.type == Poppler.ActionType.GOTO_DEST:
            return self._internal_target(action.goto_dest.dest, page)
        return None

    def _internal_target(self, destination: Poppler.Dest | None, page: int) -> InternalTarget | None:
        """A destination of a page, in the PDF it comes from: a page of that PDF, named by its source index."""
        document, start = self._sources.document(page)
        if destination is not None and destination.type == Poppler.DestType.NAMED:
            destination = document.find_dest(destination.named_dest)
        if destination is None or not 1 <= destination.page_num <= document.get_n_pages():
            return None
        index = destination.page_num - 1
        top = None
        if destination.type in DESTINATIONS_WITH_TOP and (destination.change_top or destination.top):
            _width, height = document.get_page(index).get_size()
            top = max(0.0, height - destination.top)
        return InternalTarget(start + index, top)


def _poppler_rectangle(rectangle: Rectangle) -> Poppler.Rectangle:
    result = Poppler.Rectangle()
    result.x1, result.y1, result.x2, result.y2 = rectangle
    return result
