"""The open document: one PDF and what Penfold knows about it."""

import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Self

import pikepdf

from penfold.document.annotations import Annotation, PrintGroup, read_annotations
from penfold.document.bookmarks import Bookmark, for_added_pages, leading_to, read_bookmarks
from penfold.document.forms import FieldValue, FormField, read_form_fields
from penfold.document.history import Change, Command, History
from penfold.document.page_labels import read_page_labels
from penfold.document.pages import Page, PaperSize, initial_pages, write_blank_pdf, write_empty_pdf
from penfold.document.restrictions import Restrictions
from penfold.document.saving import SavePlan
from penfold.document.sources import SourceFile, Sources
from penfold.errors import PenfoldError, ProtectedPdfError


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

    def __init__(self, path: Path, source: SourceFile, *, is_new: bool = False) -> None:
        """Wrap a PDF already copied and opened; use OpenDocument.open to open a file, or merge to merge several.

        A new document (merged) is not saved yet: path is where it is proposed to save it.
        """
        self.path = path
        self.is_new = is_new
        self.sources = Sources(source)
        pdf = source.pdf
        self.pages: list[Page] = initial_pages(len(pdf.pages), read_page_labels(pdf))
        self.title = _read_title(pdf)
        self.restrictions = Restrictions.of(pdf)
        self.bookmarks: list[Bookmark] = read_bookmarks(pdf)
        self.annotations: list[Annotation] = read_annotations(pdf)
        self.form_fields: list[FormField] = read_form_fields(pdf)
        # The values filled in that differ from the PDF's, by field key; a field set back to its value is not here (I5).
        self._form_values: dict[tuple[int, str], FieldValue] = {}
        self._positions = self._index_positions()
        self._history = History(saved=not is_new)
        self._listeners: list[Callable[[Change], None]] = []

    @classmethod
    def open(cls, path: Path) -> Self:
        """Open a PDF file.

        Raises:
            PasswordRequiredError: the PDF needs a password to be opened.
            DocumentOpenError: the file is missing, unreadable or not a PDF.
        """
        return cls(path, SourceFile(path))

    @classmethod
    def merge(cls, paths: list[Path], proposed: Path, *, bookmark_per_file: bool, keep_bookmarks: bool) -> Self:
        """Merge PDFs, in order, into a new document that is not saved yet (F1, F2, F6); proposed is its file.

        It is built on a PDF of its own, as 0.6 does, so it takes nothing from the first file but its pages. With
        bookmark_per_file, each file has an unfolded bookmark named after it (D50), holding the file's own bookmarks if
        keep_bookmarks; without it, the files' own bookmarks, if kept, go one after another.

        Raises:
            ProtectedPdfError: a PDF is protected, and cannot be merged (F4).
            PasswordRequiredError: a PDF needs a password to be opened.
            DocumentOpenError: a file is missing, unreadable or not a PDF.
        """
        with tempfile.TemporaryDirectory(prefix="penfold-") as folder:
            empty = Path(folder) / "empty.pdf"
            write_empty_pdf(empty)
            document = cls(proposed, SourceFile(empty), is_new=True)
        try:
            for path in paths:
                document._append_merged(path, bookmark_per_file=bookmark_per_file, keep_bookmarks=keep_bookmarks)
        except PenfoldError:
            document.close()
            raise
        document._positions = document._index_positions()
        return document

    def _append_merged(self, path: Path, *, bookmark_per_file: bool, keep_bookmarks: bool) -> None:
        """Put the pages of a PDF at the end of a document being merged, with the bookmarks chosen."""
        added = self.add_source(path)
        self.pages.extend(added.pages)
        [file_bookmark] = added.bookmarks
        own = file_bookmark.children if keep_bookmarks else []
        if bookmark_per_file:
            file_bookmark.children = own
            self.bookmarks.append(file_bookmark)
        else:
            self.bookmarks.extend(own)

    @property
    def is_restricted(self) -> bool:
        """Whether the PDF denies something (D59); an encrypted PDF that allows everything has no restrictions."""
        return self.restrictions.any

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

        Its pages come with a new bookmark, unfolded and named after the file, that leads to the first of them and
        holds the PDF's own bookmarks (D50). Its annotations are listed from now on, while their pages are in the
        document.

        Raises:
            ProtectedPdfError: the PDF is protected, and its pages cannot be added (2.7).
            PasswordRequiredError: the PDF needs a password to be opened.
            DocumentOpenError: the file is missing, unreadable or not a PDF.
        """
        start, pdf = self._take_source(path)
        own_bookmarks = for_added_pages(read_bookmarks(pdf), start)
        return AddedPdf(_pages_of(pdf, start), [Bookmark(path.stem, page=start, is_open=True, children=own_bookmarks)])

    def add_blank_page(self, size: PaperSize) -> AddedPdf:
        """Make a blank page of a size, ready to be added (by the AddPages command) like the pages of a PDF (E5)."""
        with tempfile.TemporaryDirectory(prefix="penfold-") as folder:
            path = Path(folder) / "blank.pdf"
            write_blank_pdf(path, size)
            start, pdf = self._take_source(path)
            return AddedPdf(_pages_of(pdf, start), [])

    def _take_source(self, path: Path) -> tuple[int, pikepdf.Pdf]:
        """Copy and open a PDF as a new source, listing its annotations and fields; return its first index and the PDF.

        Raises:
            ProtectedPdfError: the PDF is protected (2.7).
            PasswordRequiredError: the PDF needs a password to be opened.
            DocumentOpenError: the file is missing, unreadable or not a PDF.
        """
        source = SourceFile(path)
        if source.pdf.is_encrypted:
            source.close()
            raise ProtectedPdfError(str(path))
        start = self.sources.add(source).start
        self.annotations = [*self.annotations, *read_annotations(source.pdf, start)]
        self.form_fields = [*self.form_fields, *read_form_fields(source.pdf, start)]
        return start, source.pdf

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

    def amend(self, command: Command, change: Callable[[], None]) -> bool:
        """Change the last edit in place instead of making a new one (typing in a field); see History.amend."""
        if not self._history.amend(command, change):
            return False
        self._notify(command.changes)
        return True

    def field_value(self, field: FormField) -> FieldValue:
        """The value a field has now: the one filled in, or else the PDF's."""
        return self._form_values.get(field.key, field.value)

    def set_field_value(self, field: FormField, value: FieldValue) -> None:
        """Give a field a value; only for commands, which make it an edit that can be undone."""
        if value == field.value:
            self._form_values.pop(field.key, None)
        else:
            self._form_values[field.key] = value

    @property
    def filled_fields(self) -> dict[tuple[int, str], FieldValue]:
        """The values filled in that differ from the PDF's, by field key (I5)."""
        return dict(self._form_values)

    def save_plan(self, target: Path | None = None, *, flatten: bool = False) -> SavePlan:
        """Take what saving needs, to write it in another thread with saving.save; by default, over the file.

        With flatten, the form fields become fixed page content (I6): the file is an exported copy, and the document
        keeps its own file and its changes (do not mark it saved).

        A PDF with restrictions is saved too, keeping them (D59): its tools only make the changes it allows.

        Raises:
            ValueError: flattening was asked of a PDF that does not allow changing its content (D59).
        """
        if flatten and not self.restrictions.modify:
            message = "this PDF does not allow flattening its form"
            raise ValueError(message)
        plan = SavePlan.take(
            self.sources.spans, target or self.path, self.pages, self.bookmarks, self._history.checkpoint()
        )
        return replace(plan, form_values=self._filled_in(), flatten=flatten)

    def print_plan(self, target: Path, left_out: frozenset[PrintGroup]) -> SavePlan:
        """Take what writing the PDF to print needs (D57), to write it with saving.save.

        It has every page, with the form values, but no bookmarks and none of the groups of annotations left out.

        Raises:
            ValueError: the PDF does not allow printing (D59).
        """
        if not self.restrictions.print:
            message = "this PDF does not allow printing"
            raise ValueError(message)
        plan = SavePlan.take(self.sources.spans, target, self.pages, [], None)
        return replace(plan, form_values=self._filled_in(), left_out=left_out)

    def extract_plan(self, positions: list[int], target: Path) -> SavePlan:
        """Take what writing some pages to another file needs (E8), to write it with saving.save.

        The file gets those pages as they are now, in that order, with the bookmarks that lead to them.

        Raises:
            ValueError: the PDF does not allow assembling it, so neither extracting its pages (D59).
        """
        if not self.restrictions.assemble:
            message = "this PDF does not allow extracting its pages"
            raise ValueError(message)
        pages = [self.pages[position] for position in positions]
        bookmarks = leading_to(self.bookmarks, {page.source_index for page in pages})
        plan = SavePlan.take(self.sources.spans, target, pages, bookmarks, None)
        return replace(plan, form_values=self._filled_in())

    def _filled_in(self) -> tuple[tuple[FormField, FieldValue], ...]:
        """The fields whose values differ from the PDF's, with those values, to write them (I5, I7)."""
        return tuple(
            (field, self._form_values[field.key]) for field in self.form_fields if field.key in self._form_values
        )

    def mark_saved(self, plan: SavePlan) -> None:
        """Record that a plan was saved: the document now belongs to its file, and has nothing to save up to it."""
        self.path = plan.target
        self.is_new = False
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


def _pages_of(pdf: pikepdf.Pdf, start: int) -> list[Page]:
    """The pages of a source whose first source index is start, with their labels if it has any."""
    labels = read_page_labels(pdf)
    return [Page(start + index, label=None if labels is None else labels[index]) for index in range(len(pdf.pages))]


def _read_title(pdf: pikepdf.Pdf) -> str | None:
    """Return the title stored in the PDF, or None if it has none (then only the file name is shown)."""
    title = pdf.docinfo.get("/Title")
    if not isinstance(title, pikepdf.String):
        return None
    text = str(title).strip()
    return text or None
