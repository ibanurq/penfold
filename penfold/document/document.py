"""The open document: one PDF and what Penfold knows about it."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Self

import pikepdf

from penfold.document.annotations import Annotation, read_annotations
from penfold.document.bookmarks import Bookmark, for_added_pages, read_bookmarks
from penfold.document.history import Change, Command, History
from penfold.document.page_labels import read_page_labels
from penfold.document.pages import Page, initial_pages
from penfold.document.saving import SavePlan
from penfold.document.sources import SourceFile, Sources
from penfold.errors import ProtectedPdfError


@dataclass(frozen=True)
class AddedPdf:
    """A PDF ready to have its pages added to the document (E4): its pages, with their labels, and its bookmarks."""

    pages: list[Page]
    bookmarks: list[Bookmark]


class OpenDocument:
    """A PDF opened in a window.

    Its pages are a list of Page that the edits change; the PDF itself is left as it is until it is saved. Every edit
    is a command run through execute, so it can be undone (D19), and every change is announced to the listeners.
    """

    def __init__(self, path: Path, source: SourceFile) -> None:
        """Wrap a PDF already copied and opened; use OpenDocument.open to open a file."""
        self.path = path
        self.sources = Sources(source)
        pdf = source.pdf
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
        return cls(path, SourceFile(path))

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
        """Return where a page is now, by its source index (sources.py), or None if it is not in the document.

        Bookmarks and annotations name their page by its source index, which never changes.
        """
        return self._positions.get(source_index)

    def _index_positions(self) -> dict[int, int]:
        return {page.source_index: position for position, page in enumerate(self.pages)}

    def add_source(self, path: Path) -> AddedPdf:
        """Copy and open a PDF whose pages will be added (by the AddPages command).

        Its annotations are listed from now on, while their pages are in the document.

        Raises:
            ProtectedPdfError: the PDF is protected, and its pages cannot be added (2.7).
            PasswordRequiredError: the PDF needs a password to be opened.
            DocumentOpenError: the file is missing, unreadable or not a PDF.
        """
        source = SourceFile(path)
        pdf = source.pdf
        if pdf.is_encrypted:
            source.close()
            raise ProtectedPdfError(str(path))
        start = self.sources.add(source).start
        self.annotations = [*self.annotations, *read_annotations(pdf, start)]
        labels = read_page_labels(pdf)
        pages = [
            Page(start + index, label=None if labels is None else labels[index]) for index in range(len(pdf.pages))
        ]
        return AddedPdf(pages, for_added_pages(read_bookmarks(pdf), start))

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

    @property
    def last_edit(self) -> Command | None:
        """The edit that undo would undo now, if any."""
        return self._history.checkpoint()

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

    def save_plan(self, target: Path | None = None) -> SavePlan:
        """Take what saving needs, to write it in another thread with saving.save; by default, over the file.

        Raises:
            ValueError: the PDF is protected, and Penfold cannot save it (2.7).
        """
        if self.is_protected:
            message = "protected PDFs cannot be saved"
            raise ValueError(message)
        return SavePlan.take(
            self.sources.spans, target or self.path, self.pages, self.bookmarks, self._history.checkpoint()
        )

    def mark_saved(self, plan: SavePlan) -> None:
        """Record that a plan was saved: the document now belongs to its file, and has nothing to save up to it."""
        self.path = plan.target
        self._history.mark_saved(plan.checkpoint)
        self._notify(Change.FILE)

    def _notify(self, changes: Change) -> None:
        if Change.PAGES in changes:
            self._positions = self._index_positions()
        for listener in self._listeners:
            listener(changes)

    def close(self) -> None:
        """Release the source PDFs and their private copies."""
        self.sources.close()


def _read_title(pdf: pikepdf.Pdf) -> str | None:
    """Return the title stored in the PDF, or None if it has none (then only the file name is shown)."""
    title = pdf.docinfo.get("/Title")
    if not isinstance(title, pikepdf.String):
        return None
    text = str(title).strip()
    return text or None
