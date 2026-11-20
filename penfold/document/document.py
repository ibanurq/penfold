"""The open document: one PDF and what Penfold knows about it."""

from pathlib import Path
from typing import Self

import pikepdf

from penfold.document.annotations import Annotation, read_annotations
from penfold.document.bookmarks import Bookmark, read_bookmarks
from penfold.document.page_labels import page_labels
from penfold.document.pages import Page, initial_pages
from penfold.document.sources import open_source


class OpenDocument:
    """A PDF opened in a window.

    Its pages are a list of Page that the edits change; the PDF itself is left as it is until it is saved.
    """

    def __init__(self, path: Path, pdf: pikepdf.Pdf) -> None:
        """Wrap a PDF already opened with pikepdf; use OpenDocument.open to open a file."""
        self.path = path
        self._pdf = pdf
        self.pages: list[Page] = initial_pages(len(pdf.pages), page_labels(pdf))
        self.title = _read_title(pdf)
        self.is_protected = pdf.is_encrypted
        self.bookmarks: list[Bookmark] = read_bookmarks(pdf)
        self.annotations: list[Annotation] = read_annotations(pdf)

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
        return str(page_index + 1) if label is None else label

    def find_page(self, text: str) -> int | None:
        """Find the page that someone typed in the page box: a label first, then a page number.

        Returns the page index, or None if no page matches.
        """
        text = text.strip()
        if not text:
            return None
        labels = [page.label for page in self.pages]
        if text in labels:
            return labels.index(text)
        lowered = text.casefold()
        for page_index, label in enumerate(labels):
            if label is not None and label.casefold() == lowered:
                return page_index
        if text.isdecimal() and 1 <= int(text) <= self.page_count:
            return int(text) - 1
        return None

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
