"""The open document: one PDF and what Penfold knows about it."""

import tempfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Self

import pikepdf

from penfold.document.access_permissions import AccessPermissions
from penfold.document.annotations import Annotation, AnnotationGroup, read_annotations
from penfold.document.bookmarks import Bookmark, for_added_pages, leading_to, read_bookmarks
from penfold.document.forms import FieldValue, FormField, read_form_fields
from penfold.document.history import Change, Command, History
from penfold.document.page_labels import read_page_labels
from penfold.document.pages import Page, PaperSize, initial_pages, write_blank_pdf, write_empty_pdf
from penfold.document.saving import SavePlan
from penfold.document.sources import SourceFile, Sources, check_assembly
from penfold.errors import AssemblyNotAllowedError, PenfoldError


@dataclass(frozen=True)
class AddedPdf:
    """A PDF ready to have its pages added to the document (E4): its pages, with their labels, and its bookmarks."""

    pages: list[Page]
    bookmarks: list[Bookmark]


@dataclass(frozen=True)
class PdfToMerge:
    """A PDF to merge, with its open password if it has one (D61); the password is kept out of any log."""

    path: Path
    password: str = field(default="", repr=False)


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
        self.access_permissions = AccessPermissions.of(pdf)
        # Opened with the owner password: the PDF's permissions do not bind its owner (D61, 7).
        self.opened_by_owner = pdf.is_encrypted and pdf.owner_password_matched
        self._respects_permissions = True
        self.bookmarks: list[Bookmark] = read_bookmarks(pdf)
        self.annotations: list[Annotation] = read_annotations(pdf)
        # The annotations of the source PDFs as they were read, by page and origin, to know which were removed.
        self._read_annotations = _by_origin(self.annotations)
        self.form_fields: list[FormField] = read_form_fields(pdf)
        # The values filled in that differ from the PDF's, by field key; a field set back to its value is not here (I5).
        self._form_values: dict[tuple[int, str], FieldValue] = {}
        self._positions = self._index_positions()
        self._history = History(saved=not is_new)
        self._listeners: list[Callable[[Change], None]] = []

    @classmethod
    def open(cls, path: Path, password: str = "") -> Self:
        """Open a PDF file, with its password if it needs one (D61).

        Raises:
            PasswordRequiredError: the PDF needs a password to be opened, and this one is missing or wrong.
            DocumentOpenError: the file is missing, unreadable or not a PDF.
        """
        return cls(path, SourceFile(path, password))

    @classmethod
    def merge(
        cls,
        files: Sequence[PdfToMerge],
        proposed: Path,
        *,
        bookmark_per_file: bool,
        keep_bookmarks: bool,
        respect_permissions: bool,
    ) -> Self:
        """Merge PDFs, in order, into a new document that is not saved yet (F1, F2, F6); proposed is its file.

        It is built on a PDF of its own, as 0.6 does, so it takes nothing from the first file but its pages. With
        bookmark_per_file, each file has an unfolded bookmark named after it (D50), holding the file's own bookmarks if
        keep_bookmarks; without it, the files' own bookmarks, if kept, go one after another. With respect_permissions
        off, a PDF that does not allow assembling it is merged too, and the result has no permissions (D61). A PDF
        with an open password comes with it; the result has none.

        Raises:
            AssemblyNotAllowedError: a PDF's permissions, respected, do not let it be merged (F4, D59, D61).
            PasswordRequiredError: a PDF needs a password to be opened, and its one is missing or wrong.
            DocumentOpenError: a file is missing, unreadable or not a PDF.
        """
        with tempfile.TemporaryDirectory(prefix="penfold-") as folder:
            empty = Path(folder) / "empty.pdf"
            write_empty_pdf(empty)
            document = cls(proposed, SourceFile(empty), is_new=True)
        document.respect_permissions(respect_permissions)
        try:
            for file in files:
                document._append_merged(file, bookmark_per_file=bookmark_per_file, keep_bookmarks=keep_bookmarks)
        except PenfoldError:
            document.close()
            raise
        document._positions = document._index_positions()
        return document

    def _append_merged(self, file: PdfToMerge, *, bookmark_per_file: bool, keep_bookmarks: bool) -> None:
        """Put the pages of a PDF at the end of a document being merged, with the bookmarks chosen."""
        added = self.add_source(file.path, file.password)
        self.pages.extend(added.pages)
        [file_bookmark] = added.bookmarks
        own = file_bookmark.children if keep_bookmarks else []
        if bookmark_per_file:
            file_bookmark.children = own
            self.bookmarks.append(file_bookmark)
        else:
            self.bookmarks.extend(own)

    @property
    def permissions(self) -> AccessPermissions:
        """What Penfold lets the user do with the document: every tool asks this (D59, D60).

        The PDF's user access permissions while they are respected; everything once they are not, or if the PDF was
        opened with its owner password (D61).
        """
        if self.opened_by_owner or not self._respects_permissions:
            return AccessPermissions()
        return self.access_permissions

    def respect_permissions(self, respect: bool) -> None:
        """Follow the PDF's user access permissions, or ignore them ("Respect Document Permissions", D60)."""
        if respect != self._respects_permissions:
            self._respects_permissions = respect
            self._notify(Change.PERMISSIONS)

    @property
    def denies_anything(self) -> bool:
        """Whether Penfold denies something with the document (D59, D60); an encrypted PDF may allow everything."""
        return self.permissions.denies_anything

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

    def add_source(self, path: Path, password: str = "") -> AddedPdf:
        """Copy and open a PDF whose pages will be added (by the AddPages command).

        A PDF with an open password needs it (D61). Its pages come with a new bookmark, unfolded and named after the
        file, that leads to the first of them and holds the PDF's own bookmarks (D50). Its annotations are listed from
        now on, while their pages are in the document.

        Raises:
            AssemblyNotAllowedError: the PDF's permissions, respected, do not let its pages be added (2.7, D59, D61).
            PasswordRequiredError: the PDF needs a password to be opened.
            DocumentOpenError: the file is missing, unreadable or not a PDF.
        """
        start, pdf = self._take_source(path, password)
        own_bookmarks = for_added_pages(read_bookmarks(pdf), start)
        return AddedPdf(_pages_of(pdf, start), [Bookmark(path.stem, page=start, is_open=True, children=own_bookmarks)])

    def add_blank_page(self, size: PaperSize) -> AddedPdf:
        """Make a blank page of a size, ready to be added (by the AddPages command) like the pages of a PDF (E5)."""
        with tempfile.TemporaryDirectory(prefix="penfold-") as folder:
            path = Path(folder) / "blank.pdf"
            write_blank_pdf(path, size)
            start, pdf = self._take_source(path)
            return AddedPdf(_pages_of(pdf, start), [])

    def _take_source(self, path: Path, password: str = "") -> tuple[int, pikepdf.Pdf]:
        """Copy and open a PDF as a new source, listing its annotations and fields; return its first index and the PDF.

        Raises:
            AssemblyNotAllowedError: the PDF's permissions, respected, do not allow it (2.7, D59, D61).
            PasswordRequiredError: the PDF needs a password to be opened.
            DocumentOpenError: the file is missing, unreadable or not a PDF.
        """
        source = SourceFile(path, password)
        try:
            check_assembly(source.pdf, path, respect_permissions=self._respects_permissions)
        except AssemblyNotAllowedError:
            source.close()
            raise
        start = self.sources.add(source).start
        read = read_annotations(source.pdf, start)
        self.annotations = [*self.annotations, *read]
        self._read_annotations |= _by_origin(read)
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

        A PDF with permissions is saved too, keeping them (D59): its tools only make the changes it allows.

        Raises:
            ValueError: flattening was asked of a PDF that does not allow changing its content (D59).
        """
        if flatten and not self.permissions.modify:
            message = "this PDF does not allow flattening its form"
            raise ValueError(message)
        plan = SavePlan.take(
            self.sources.spans, target or self.path, self.pages, self.bookmarks, self._history.checkpoint()
        )
        return replace(self._with_annotation_edits(plan), form_values=self._filled_in(), flatten=flatten)

    def print_plan(self, target: Path, left_out: frozenset[AnnotationGroup]) -> SavePlan:
        """Take what writing the PDF to print needs (D57), to write it with saving.save.

        It has every page, with the form values, but no bookmarks and none of the groups of annotations left out.

        Raises:
            ValueError: the PDF does not allow printing (D59).
        """
        if not self.permissions.print:
            message = "this PDF does not allow printing"
            raise ValueError(message)
        plan = SavePlan.take(self.sources.spans, target, self.pages, [], None)
        return replace(self._with_annotation_edits(plan), form_values=self._filled_in(), left_out=left_out)

    def extract_plan(self, positions: list[int], target: Path) -> SavePlan:
        """Take what writing some pages to another file needs (E8), to write it with saving.save.

        The file gets those pages as they are now, in that order, with the bookmarks that lead to them.

        Raises:
            ValueError: the PDF does not allow assembling it, so neither extracting its pages (D59).
        """
        if not self.permissions.assemble:
            message = "this PDF does not allow extracting its pages"
            raise ValueError(message)
        pages = [self.pages[position] for position in positions]
        bookmarks = leading_to(self.bookmarks, {page.source_index for page in pages})
        plan = SavePlan.take(self.sources.spans, target, pages, bookmarks, None)
        return replace(self._with_annotation_edits(plan), form_values=self._filled_in())

    def _with_annotation_edits(self, plan: SavePlan) -> SavePlan:
        """Add to a plan what saving changes in the annotations of the pages.

        Saving writes the managed annotations (made or changed in Penfold), takes out of their pages those of the PDFs
        that were deleted or changed, and moves in their pages those only moved (D73); the rest are in their pages
        already.
        """
        managed = tuple(annotation for annotation in self.annotations if annotation.managed)
        moved = tuple(annotation for annotation in self.annotations if annotation.moved_as_is)
        kept = {(annotation.page, annotation.origin) for annotation in moved}
        removed = frozenset(
            (annotation.page, annotation.origin or 0)
            for annotation in self.replaced_annotations
            if (annotation.page, annotation.origin) not in kept
        )
        return replace(plan, annotations=managed, removed=removed, moved=moved)

    @property
    def replaced_annotations(self) -> list[Annotation]:
        """The annotations of the source PDFs, as they were read, that were deleted, changed or moved since.

        Poppler leaves them out when it draws the pages (03-arquitectura 4.1); saving takes those deleted or changed out
        of their pages, and moves those only moved (D73).
        """
        unchanged = _by_origin(
            annotation for annotation in self.annotations if not annotation.managed and not annotation.moved_as_is
        )
        return [annotation for key, annotation in self._read_annotations.items() if key not in unchanged]

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


def _by_origin(annotations: Iterable[Annotation]) -> dict[tuple[int, int], Annotation]:
    """The annotations read from a PDF, by their page and origin (annotations.py)."""
    return {
        (annotation.page, annotation.origin): annotation for annotation in annotations if annotation.origin is not None
    }


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
