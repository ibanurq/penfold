"""Source PDFs: the files whose pages make up the open document, read with pikepdf.

A document is read from a private copy of its file, taken when it is opened. Saving over the file then leaves the
pages Penfold reads as they were: the edits, and undoing them after saving, still refer to the PDF as it was opened.
PDFs whose pages are added to the document are copied in the same way.

Every page of every source has a number of its own, its source index: the pages of the opened PDF are numbered first,
from 0, then those of each PDF added, in turn. Bookmarks, annotations and the pages of the document name a page by its
source index, which never changes, whatever is added, moved or deleted.
"""

import bisect
import shutil
import tempfile
import weakref
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pikepdf

from penfold.document.access_permissions import AccessPermissions
from penfold.errors import AssemblyNotAllowedError, DocumentOpenError, PasswordRequiredError

COPY_NAME = "source.pdf"


class SourceFile:
    """A private copy of a PDF as it was opened, and the PDF read from it with pikepdf.

    The copy lives in a temporary folder that only the user can read, removed when the source is closed (or, if
    Penfold stops before, when Python exits). The copy is as encrypted as the file; the password that opens it is kept
    only in memory, never written anywhere (D61).
    """

    def __init__(self, path: Path, password: str = "") -> None:
        """Copy a PDF and open the copy, with its password if it needs one.

        Raises:
            PasswordRequiredError: the PDF needs a password to be opened, and this one is missing or wrong.
            DocumentOpenError: the file is missing, unreadable or not a PDF.
        """
        folder = Path(tempfile.mkdtemp(prefix="penfold-"))
        self._remove_folder = weakref.finalize(self, shutil.rmtree, folder, ignore_errors=True)
        self.path = folder / COPY_NAME
        self.password = password
        try:
            shutil.copyfile(path, self.path)
            self.pdf = open_source(self.path, password)
        except DocumentOpenError:
            self._remove_folder()
            raise
        except OSError as error:
            self._remove_folder()
            raise DocumentOpenError(str(path)) from error

    def close(self) -> None:
        """Release the PDF and remove the copy."""
        self.pdf.close()
        self._remove_folder()


def open_source(path: Path, password: str = "") -> pikepdf.Pdf:
    """Open a PDF for reading, with its password if it needs one; the file itself is never changed here.

    Raises:
        PasswordRequiredError: the PDF needs a password to be opened, and this one is missing or wrong.
        DocumentOpenError: the file is missing, unreadable or not a PDF.
    """
    try:
        return pikepdf.open(path, password=password)
    except pikepdf.PasswordError as error:
        raise PasswordRequiredError(str(path)) from error
    except (pikepdf.PdfError, OSError, ValueError) as error:
        raise DocumentOpenError(str(path)) from error


@dataclass(frozen=True)
class SourceSpan:
    """Where the pages of one source are numbered: its file, the source index of its first page and how many.

    A PDF with an open password carries it, to be read again by Poppler, saving and printing (D61).
    """

    path: Path
    start: int
    page_count: int
    password: str = field(default="", repr=False)


# The sources of a document, the opened PDF first.
Spans = tuple[SourceSpan, ...]


def locate(spans: Sequence[SourceSpan], source_index: int) -> tuple[int, int]:
    """Return which source a page comes from (its position in spans) and its index in that PDF.

    Raises:
        IndexError: no source has a page with this source index.
    """
    source = bisect.bisect_right([span.start for span in spans], source_index) - 1
    if source < 0 or source_index >= spans[source].start + spans[source].page_count:
        message = f"no source has the page {source_index}"
        raise IndexError(message)
    return source, source_index - spans[source].start


class Sources:
    """The source PDFs of a document: the opened one first, then the ones added, never removed while it is open.

    Undoing an addition takes its pages out of the document, but its source stays, so redoing it finds them.
    """

    def __init__(self, opened: SourceFile) -> None:
        """Start with the PDF that was opened."""
        self._files = [opened]
        self.spans: Spans = (SourceSpan(opened.path, 0, len(opened.pdf.pages), opened.password),)

    def add(self, added: SourceFile) -> SourceSpan:
        """Take another PDF, already copied and opened, numbering its pages after those of the last source."""
        last = self.spans[-1]
        span = SourceSpan(added.path, last.start + last.page_count, len(added.pdf.pages), added.password)
        self._files.append(added)
        self.spans = (*self.spans, span)
        return span

    def pdf(self, source: int) -> pikepdf.Pdf:
        """The PDF of a source, by its position."""
        return self._files[source].pdf

    def close(self) -> None:
        """Release every PDF and remove their copies."""
        for source in self._files:
            source.close()


def count_pages(path: Path, *, respect_permissions: bool) -> int:
    """Return how many pages a PDF has, to list it before merging it (F1).

    Raises:
        AssemblyNotAllowedError: the PDF's permissions, if respected, do not let it be merged (F4, D59, D61).
        DocumentOpenError: the file is missing, unreadable or not a PDF.
    """
    try:
        pdf = open_source(path)
    except PasswordRequiredError as error:
        raise AssemblyNotAllowedError(str(path)) from error
    with pdf:
        if respect_permissions and not AccessPermissions.of(pdf).assemble:
            raise AssemblyNotAllowedError(str(path))
        return len(pdf.pages)
