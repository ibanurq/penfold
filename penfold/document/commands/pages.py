"""Page edits: turn, delete and move pages (E1, E2, E3)."""

from collections.abc import Iterable

from penfold.document.bookmarks import Bookmark, without_pages
from penfold.document.document import OpenDocument
from penfold.document.history import Change
from penfold.document.pages import QUARTER_TURN, Page


def _sorted_positions(document: OpenDocument, positions: Iterable[int]) -> list[int]:
    """Return the positions without repeats and in order, checking that they are pages of the document.

    Raises:
        ValueError: no position is given, or one is outside the document.
    """
    unique = sorted(set(positions))
    if not unique:
        message = "no pages given"
        raise ValueError(message)
    if unique[0] < 0 or unique[-1] >= document.page_count:
        message = f"pages {unique} are not all in a document of {document.page_count} pages"
        raise ValueError(message)
    return unique


class RotatePages:
    """Turn some pages a quarter turn (or more) clockwise, or anticlockwise with negative degrees."""

    changes = Change.PAGES

    def __init__(self, document: OpenDocument, positions: Iterable[int], degrees: int) -> None:
        """Prepare the turn of the pages at these positions.

        Raises:
            ValueError: no pages, pages outside the document, or a turn that is not a multiple of 90 degrees.
        """
        if degrees % QUARTER_TURN:
            message = f"pages turn in quarter turns, not by {degrees} degrees"
            raise ValueError(message)
        self._document = document
        self._positions = _sorted_positions(document, positions)
        self._degrees = degrees

    def apply(self) -> None:
        """Turn the pages."""
        self._turn(self._degrees)

    def revert(self) -> None:
        """Turn them back."""
        self._turn(-self._degrees)

    def _turn(self, degrees: int) -> None:
        pages = self._document.pages
        for position in self._positions:
            pages[position] = pages[position].rotated(degrees)


class DeletePages:
    """Delete some pages, and the bookmarks that lead to them (as 0.6 does), keeping what undo needs."""

    changes = Change.PAGES | Change.BOOKMARKS

    def __init__(self, document: OpenDocument, positions: Iterable[int]) -> None:
        """Prepare the deletion of the pages at these positions.

        Raises:
            ValueError: no pages, pages outside the document, or every page (a PDF needs at least one, E3).
        """
        self._document = document
        self._positions = _sorted_positions(document, positions)
        if len(self._positions) == document.page_count:
            message = "a document cannot lose all its pages"
            raise ValueError(message)
        self._deleted: list[Page] = []
        self._bookmarks: list[Bookmark] = []

    @property
    def positions(self) -> list[int]:
        """The positions of the pages deleted, in order."""
        return list(self._positions)

    def apply(self) -> None:
        """Delete the pages and the bookmarks that lead to them."""
        pages = self._document.pages
        self._deleted = [pages[position] for position in self._positions]
        for position in reversed(self._positions):
            del pages[position]
        self._bookmarks = self._document.bookmarks
        deleted_sources = {page.source_index for page in self._deleted}
        self._document.bookmarks = without_pages(self._bookmarks, deleted_sources)

    def revert(self) -> None:
        """Put the pages back where they were, and the bookmarks as they were."""
        for position, page in zip(self._positions, self._deleted, strict=True):
            self._document.pages.insert(position, page)
        self._document.bookmarks = self._bookmarks


class MovePages:
    """Move some pages, together and in their order, to another place (dragging thumbnails, E1)."""

    changes = Change.PAGES

    def __init__(self, document: OpenDocument, positions: Iterable[int], before: int) -> None:
        """Prepare the move of the pages at these positions to just before the page now at position `before`.

        `before` can be the number of pages, to move them to the end.

        Raises:
            ValueError: no pages, or positions outside the document.
        """
        self._document = document
        self._positions = _sorted_positions(document, positions)
        if not 0 <= before <= document.page_count:
            message = f"cannot move pages before position {before} of {document.page_count}"
            raise ValueError(message)
        self._before = before
        self._previous_order: list[Page] = []

    @property
    def moves_anything(self) -> bool:
        """Whether the move changes the order (dropping pages on themselves does not)."""
        target = self._target()
        return self._positions != list(range(target, target + len(self._positions)))

    def apply(self) -> None:
        """Move the pages."""
        pages = self._document.pages
        self._previous_order = list(pages)
        chosen = set(self._positions)
        moved = [pages[position] for position in self._positions]
        staying = [page for position, page in enumerate(pages) if position not in chosen]
        target = self._target()
        pages[:] = staying[:target] + moved + staying[target:]

    def revert(self) -> None:
        """Put the pages back in their order."""
        self._document.pages[:] = self._previous_order

    def _target(self) -> int:
        """Where the moved pages start once taken out of the list: `before`, less the moved pages ahead of it."""
        return self._before - sum(1 for position in self._positions if position < self._before)
