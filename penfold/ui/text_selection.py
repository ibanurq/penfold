"""Text selected with the mouse, possibly across several pages (B9)."""

from dataclasses import dataclass

from gi.repository import Poppler

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

    def text(self, content: PageContent, page_sizes: list[tuple[float, float]]) -> str:
        """Return the selected text, one page after another."""
        texts = [
            content.selected_text(page, selection, self.style)
            for page, selection in self.page_selections(page_sizes).items()
        ]
        return "\n".join(text for text in texts if text)
