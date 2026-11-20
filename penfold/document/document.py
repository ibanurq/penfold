"""The open document: one PDF and what Penfold knows about it."""

from collections.abc import Callable
from pathlib import Path
from typing import Self

import pikepdf

from penfold.document.annotations import Annotation, read_annotations
from penfold.document.bookmarks import Bookmark, read_bookmarks
from penfold.document.history import Change, Command, History
from penfold.document.page_labels import read_page_labels
from penfold.document.pages import Page, initial_pages
from penfold.document.sources import open_source


class OpenDocument:
    """A PDF opened in a window.

    Its pages are a list of Page that the edits change; the PDF itself is left as it is until it is saved. Every edit
    is a command run through execute, so it can be undone (D19), and every change is announced to the listeners.
    """

    def __init__(self, path: Path, pdf: pikepdf.Pdf) -> None:
        """Wrap a PDF already opened with pikepdf; use OpenDocument.open to open a file."""
        self.path = path
        self._pdf = pdf
        self.pages: list[Page] = initial_pages(len(pdf.pages), read_page_labels(pdf))
        self.title = _read_title(pdf)
        self.is_protected = pdf.is_encrypted
        self.bookmarks: list[Bookmark] = read_bookmarks(pdf)
        self.annotations: list[Annotation] = read_annotations(pdf)
        self._positions = self._index_positions()
        self._history = History()
        self._listeners: list[Callable[[Change], None]] = []

    @classmethod
    def open(cls, path: Path) -> Self:
        """Open a PDF file.

        Raises:
            PasswordRequiredError: the PDF needs a password to be opened.
            DocumentOpenError: the file is missing, unreadable or not a PDF.
        """
        return cls(path, open_source(path))

    @property
    def file_name(self) -> str:
        """Name of the file, without its folder."""
        return self.path.name

    @property
    def page_count(self) -> int:
        """Number of pages the document has now."""
        return len(self.pages)

    @property
    def has_page_labels(self) -> bool:
        """Whether some page has a label of its own (D14), so the page box shows labels and positions."""
        return any(page.label is not None for page in self.pages)

    def page_label(self, page_index: int) -> str:
        """Return the name of a page: its own label, or its number if it has none."""
        label = self.pages[page_index].label
        return str(page_index + 1) if label is None else label.text

    def page_position(self, source_index: int) -> int | None:
        """Return where a page of the opened PDF is now, or None if it was deleted.

        Bookmarks and annotations name their page by its index in the opened PDF, which never changes.
        """
        return self._positions.get(source_index)

    def _index_positions(self) -> dict[int, int]:
        return {page.source_index: position for position, page in enumerate(self.pages)}

    def find_page(self, text: str) -> int | None:
        """Find the page that someone typed in the page box: a label first, then a page number.

        Returns the page index, or None if no page matches.
        """
        text = text.strip()
        if not text:
            return None
        labels = [None if page.label is None else page.label.text for page in self.pages]
        if text in labels:
            return labels.index(text)
        lowered = text.casefold()
        for page_index, label in enumerate(labels):
            if label is not None and label.casefold() == lowered:
                return page_index
        if text.isdecimal() and 1 <= int(text) <= self.page_count:
            return int(text) - 1
        return None

    @property
    def can_undo(self) -> bool:
        """Whether there is an edit to undo."""
        return self._history.can_undo

    @property
    def can_redo(self) -> bool:
        """Whether there is an undone edit to redo."""
        return self._history.can_redo

    @property
    def is_modified(self) -> bool:
        """Whether the document has changes that are not saved (D16)."""
        return self._history.is_modified

    def add_listener(self, listener: Callable[[Change], None]) -> None:
        """Call a function after every edit, undo and redo, with the parts of the document that changed."""
        self._listeners.append(listener)

    def execute(self, command: Command) -> None:
        """Make an edit that can be undone."""
        self._history.execute(command)
        self._notify(command.changes)

    def undo(self) -> None:
        """Undo the last edit; there must be one (can_undo)."""
        self._notify(self._history.undo().changes)

    def redo(self) -> None:
        """Redo the last undone edit; there must be one (can_redo)."""
        self._notify(self._history.redo().changes)

    def _notify(self, changes: Change) -> None:
        if Change.PAGES in changes:
            self._positions = self._index_positions()
        for listener in self._listeners:
            listener(changes)

    def close(self) -> None:
        """Release the file."""
        self._pdf.close()


def _read_title(pdf: pikepdf.Pdf) -> str | None:
    """Return the title stored in the PDF, or None if it has none (then only the file name is shown)."""
    title = pdf.docinfo.get("/Title")
    if not isinstance(title, pikepdf.String):
        return None
    text = str(title).strip()
    return text or None
