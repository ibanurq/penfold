"""Text selected with the mouse, possibly across several pages.

A selection is made on the pages as they are shown; Poppler reads the text from the unturned pages of the PDF.
"""

from dataclasses import dataclass

from gi.repository import Poppler

from penfold.rendering.layout import PageLayout, ShownPage
from penfold.rendering.page_content import PageContent, Rectangle


@dataclass(frozen=True, order=True)
class PagePoint:
    """A point of a page, in PDF points from its top left corner."""

    page: int
    y: float
    x: float


@dataclass(frozen=True)
class TextSelection:
    """From where the mouse was pressed to where it is now; Poppler finds the text in between.

    The style says what a drag selects: glyphs (a drag), whole words (double click) or whole lines (triple click).
    """

    anchor: PagePoint
    focus: PagePoint
    style: Poppler.SelectionStyle = Poppler.SelectionStyle.GLYPH

    def page_selections(self, page_sizes: list[tuple[float, float]]) -> dict[int, Rectangle]:
        """Return, for each page it covers, the selection on that page as (start x, start y, end x, end y).

        The first page is selected from the start to its end, the pages in between whole, and the last one from its
        top to the end of the selection.
        """
        start, end = (self.anchor, self.focus) if self.anchor.page <= self.focus.page else (self.focus, self.anchor)
        selections = {}
        for page in range(start.page, end.page + 1):
            width, height = page_sizes[page]
            from_x, from_y = (start.x, start.y) if page == start.page else (0.0, 0.0)
            to_x, to_y = (end.x, end.y) if page == end.page else (width, height)
            selections[page] = (from_x, from_y, to_x, to_y)
        return selections

    def text(self, content: PageContent, layout: PageLayout) -> str:
        """Return the selected text, one page after another."""
        texts = [
            content.selected_text(layout[page].source, source_selection(layout[page], selection), self.style)
            for page, selection in self.page_selections(layout.sizes).items()
        ]
        return "\n".join(text for text in texts if text)


def source_selection(page: ShownPage, selection: Rectangle) -> Rectangle:
    """The selection of a page as shown (from a point to another) on the unturned page of the PDF."""
    start_x, start_y = page.to_source(selection[0], selection[1])
    end_x, end_y = page.to_source(selection[2], selection[3])
    return start_x, start_y, end_x, end_y
