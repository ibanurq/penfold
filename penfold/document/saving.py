"""Saving: writing the document to a PDF file (03-arquitectura, 6).

The PDF as it was opened is changed, not rebuilt (D15): its pages are put in their new order and turn, the pages added
from other PDFs copied in, their labels written again (D14), the outline written from the bookmarks, and everything
else is left as it was. The result is written to a temporary file next to the target, checked, and only then put in
the target's place, so a failure never damages the file that was there.

Saving runs in a worker thread: the main thread takes a SavePlan, a copy of all it needs, and keeps working.
"""

import contextlib
import copy
import os
import secrets
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pikepdf

from penfold.document.bookmarks import BOLD_FLAG, ITALIC_FLAG, Bookmark, View
from penfold.document.history import Command
from penfold.document.page_labels import PageLabel, write_page_labels
from penfold.document.pages import Page
from penfold.document.sources import Spans, locate
from penfold.errors import SaveError

# Keys of an outline item that tie it into the tree; the others (destination, action…) are kept on saving.
OUTLINE_LINKS = frozenset({"/Parent", "/Prev", "/Next", "/First", "/Last", "/Count"})
NEW_FILE_MODE = 0o666  # Narrowed by the user's umask, as for any new file.
RANDOM_NAME_BYTES = 6


@dataclass(frozen=True)
class SavePlan:
    """What saving needs, copied from the document at the moment the user saves.

    Attributes:
        sources: the private copies of the source PDFs, the one opened first, and where their pages are numbered.
        target: the file to write.
        pages: the pages in their order, with their turn and label.
        bookmarks: the outline, copied so that later edits do not reach it.
        checkpoint: the last edit included, so the document knows what was saved even if it changes meanwhile.
    """

    sources: Spans
    target: Path
    pages: tuple[Page, ...]
    bookmarks: tuple[Bookmark, ...]
    checkpoint: Command | None

    @classmethod
    def take(
        cls,
        sources: Spans,
        target: Path,
        pages: list[Page],
        bookmarks: list[Bookmark],
        checkpoint: Command | None,
    ) -> "SavePlan":
        """Copy what will be saved, so that the document can keep changing while it is written."""
        return cls(sources, target, tuple(pages), tuple(copy.deepcopy(bookmarks)), checkpoint)


def save(plan: SavePlan) -> None:
    """Write the document to its target file (in any thread).

    Raises:
        SaveError: the PDF could not be written or the result is not valid; the target is left as it was.
    """
    try:
        with pikepdf.open(plan.sources[0].path) as pdf, _OtherSources(plan.sources) as others:
            originals = list(pdf.pages)
            placed = _arrange_pages(pdf, originals, plan.pages, others)
            deleted = [original for index, original in enumerate(originals) if index not in placed]
            _write_labels(pdf, plan.pages)
            _remove_fields_of_pages(pdf, deleted)
            _write_outline(pdf, list(plan.bookmarks), placed)
            _write_safely(pdf, plan.target, len(plan.pages))
    except (pikepdf.PdfError, OSError) as error:
        raise SaveError(str(plan.target)) from error


class _OtherSources(contextlib.ExitStack):
    """The source PDFs other than the opened one, opened when one of their pages is needed and closed at the end."""

    def __init__(self, spans: Spans) -> None:
        super().__init__()
        self._spans = spans
        self._opened: dict[int, pikepdf.Pdf] = {}

    def page(self, source_index: int) -> pikepdf.Page:
        """The page of an added PDF with this source index."""
        source, index = locate(self._spans, source_index)
        if source not in self._opened:
            self._opened[source] = self.enter_context(pikepdf.open(self._spans[source].path))
        return self._opened[source].pages[index]


def _arrange_pages(
    pdf: pikepdf.Pdf, originals: list[pikepdf.Page], pages: tuple[Page, ...], others: _OtherSources
) -> dict[int, pikepdf.Page]:
    """Put the pages in their new order and turn, copying in those of other PDFs; return them by source index."""
    for index in reversed(range(len(originals))):
        del pdf.pages[index]
    placed = {}
    for page in pages:
        opened = page.source_index < len(originals)
        # pikepdf copies a page of another PDF, with all it uses, when it is appended.
        pdf.pages.append(originals[page.source_index] if opened else others.page(page.source_index))
        placed[page.source_index] = pdf.pages[-1]
        if page.rotation:
            placed[page.source_index].rotate(page.rotation, relative=True)
    return placed


def _write_labels(pdf: pikepdf.Pdf, pages: tuple[Page, ...]) -> None:
    """Write the labels in the new order (D14); pages without a label of their own are named by their number."""
    if all(page.label is None for page in pages):
        if "/PageLabels" in pdf.Root:
            del pdf.Root.PageLabels
        return
    write_page_labels(pdf, [page.label or PageLabel(number=position + 1) for position, page in enumerate(pages)])


def _remove_fields_of_pages(pdf: pikepdf.Pdf, pages: list[pikepdf.Page]) -> None:
    """Take out of the form the fields whose widgets were all on deleted pages (I8)."""
    form = pdf.Root.get("/AcroForm")
    if not pages or not isinstance(form, pikepdf.Dictionary):
        return
    fields = form.get("/Fields")
    if not isinstance(fields, pikepdf.Array):
        return
    widgets = {annotation.objgen for page in pages for annotation in _items(page.obj.get("/Annots"))}
    form.Fields = pikepdf.Array(_fields_without(fields, widgets))


def _items(array: object) -> Iterator[pikepdf.Object]:
    """The items of a PDF array; nothing if it is not one."""
    if isinstance(array, pikepdf.Array):
        yield from (array[index] for index in range(len(array)))


def _fields_without(fields: pikepdf.Array, widgets: set[tuple[int, int]]) -> list[pikepdf.Object]:
    """Return the fields that still have a widget, with their kids on deleted pages left out."""
    kept = []
    for field in _items(fields):
        if not isinstance(field, pikepdf.Dictionary):
            kept.append(field)
            continue
        if field.objgen in widgets:
            continue
        kids = field.get("/Kids")
        if isinstance(kids, pikepdf.Array) and len(kids):
            remaining = _fields_without(kids, widgets)
            if not remaining:
                continue
            if len(remaining) != len(kids):
                field.Kids = pikepdf.Array(remaining)
        kept.append(field)
    return kept


def _write_outline(pdf: pikepdf.Pdf, bookmarks: list[Bookmark], placed: dict[int, pikepdf.Page]) -> None:
    """Write the outline from the bookmarks, opening the PDF on it as 0.6 does (G9); remove it if there are none."""
    if not bookmarks:
        if "/Outlines" in pdf.Root:
            del pdf.Root.Outlines
        return
    root = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Outlines))
    items = _write_items(pdf, bookmarks, root, placed)
    root.First, root.Last, root.Count = items[0], items[-1], _visible_count(bookmarks)
    pdf.Root.Outlines = root
    pdf.Root.PageMode = pikepdf.Name.UseOutlines


def _write_items(
    pdf: pikepdf.Pdf, bookmarks: list[Bookmark], parent: pikepdf.Dictionary, placed: dict[int, pikepdf.Page]
) -> list[pikepdf.Dictionary]:
    """Write one level of the outline, linked to its parent and to each other, and the levels under it."""
    items = [_outline_item(pdf, bookmark, placed) for bookmark in bookmarks]
    for position, (item, bookmark) in enumerate(zip(items, bookmarks, strict=True)):
        item.Parent = parent
        if position > 0:
            item.Prev = items[position - 1]
        if position < len(items) - 1:
            item.Next = items[position + 1]
        if bookmark.children:
            children = _write_items(pdf, bookmark.children, item, placed)
            item.First, item.Last = children[0], children[-1]
            count = _visible_count(bookmark.children)
            # ISO 32000-1, 12.3.3: negative when closed, counting what would show if it were opened.
            item.Count = count if bookmark.is_open else -count
    return items


def _outline_item(pdf: pikepdf.Pdf, bookmark: Bookmark, placed: dict[int, pikepdf.Page]) -> pikepdf.Dictionary:
    """Make the item of one bookmark: what its original item had, with the title and style of the bookmark."""
    item = pikepdf.Dictionary()
    original = pdf.get_object(bookmark.origin) if bookmark.origin is not None else None
    if isinstance(original, pikepdf.Dictionary):
        for key, value in original.items():
            if key not in OUTLINE_LINKS:
                item[key] = value
    elif bookmark.page in placed:
        item.Dest = _destination(placed[bookmark.page], bookmark.top, bookmark.view)
    item.Title = pikepdf.String(bookmark.title)
    _set_or_remove(item, "/F", (ITALIC_FLAG if bookmark.italic else 0) | (BOLD_FLAG if bookmark.bold else 0) or None)
    _set_or_remove(item, "/C", None if bookmark.color is None else pikepdf.Array(bookmark.color))
    return pdf.make_indirect(item)


def _destination(page: pikepdf.Page, top: float | None, view: View | None) -> pikepdf.Array:
    """A destination to a page (ISO 32000-1, 12.3.2.2): as its view says, or else at a height from its top if any."""
    if view is not None:
        kind, numbers = view
        return pikepdf.Array([page.obj, pikepdf.Name(kind), *numbers])
    if top is None:
        return pikepdf.Array([page.obj, pikepdf.Name.Fit])
    height = float(page.mediabox[3])
    return pikepdf.Array([page.obj, pikepdf.Name.XYZ, None, height - top, None])


def _set_or_remove(item: pikepdf.Dictionary, key: str, value: object) -> None:
    if value is None:
        if key in item:
            del item[key]
    else:
        item[key] = value


def _visible_count(bookmarks: list[Bookmark]) -> int:
    """How many items show at this level and under the open ones."""
    return sum(1 + (_visible_count(bookmark.children) if bookmark.is_open else 0) for bookmark in bookmarks)


def _write_safely(pdf: pikepdf.Pdf, target: Path, page_count: int) -> None:
    """Write to a new file next to the target, check it, and put it in the target's place."""
    temporary = _new_file_next_to(target)
    try:
        pdf.save(temporary)
        _check(temporary, page_count)
        if target.exists():
            shutil.copymode(target, temporary)
        temporary.replace(target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _new_file_next_to(target: Path) -> Path:
    """Create an empty hidden file in the target's folder, with the permissions of a new file."""
    while True:
        candidate = target.with_name(f".{target.name}.{secrets.token_hex(RANDOM_NAME_BYTES)}.part")
        try:
            descriptor = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, NEW_FILE_MODE)
        except FileExistsError:
            continue
        os.close(descriptor)
        return candidate


def _check(path: Path, page_count: int) -> None:
    """Open the written PDF again and read every page, so a broken result is never put in place.

    Raises:
        SaveError: the PDF does not have the pages it should.
    """
    with pikepdf.open(path) as written:
        if len(written.pages) != page_count:
            message = f"{path} has {len(written.pages)} pages instead of {page_count}"
            raise SaveError(message)
        for page in written.pages:
            _ = page.mediabox
