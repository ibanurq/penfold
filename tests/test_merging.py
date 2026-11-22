"""Merging PDFs into a new document, and the forms of pages that come from other PDFs (F1, F2, F4, F6, F7, D50)."""

from pathlib import Path

import pikepdf
import pytest

from penfold.document.commands.pages import AddPages, DeletePages
from penfold.document.document import OpenDocument
from penfold.document.saving import save
from penfold.errors import AssemblyNotAllowedError
from tests.sample_pdfs import make_pdf, make_pdf_with_permissions
from tests.test_adding_pages import outlined_pdf


def form_pdf(path: Path, names: list[str], font: str = "/Helv") -> Path:
    """One page per name, each with a text field of that name, and a form with a font of its own."""
    pdf = pikepdf.new()
    fields = []
    for name in names:
        pdf.add_blank_page()
        page = pdf.pages[-1]
        widget = pdf.make_indirect(
            pikepdf.Dictionary(
                Type=pikepdf.Name.Annot,
                Subtype=pikepdf.Name.Widget,
                FT=pikepdf.Name.Tx,
                T=pikepdf.String(name),
                Rect=[0, 0, 50, 20],
                P=page.obj,
            )
        )
        page.obj.Annots = pdf.make_indirect(pikepdf.Array([widget]))
        fields.append(widget)
    resources = pikepdf.Dictionary(
        Font=pikepdf.Dictionary({font: pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Font))})
    )
    pdf.Root.AcroForm = pdf.make_indirect(
        pikepdf.Dictionary(Fields=pikepdf.Array(fields), DR=resources, DA=pikepdf.String(f"{font} 0 Tf 0 g"))
    )
    pdf.save(path)
    return path


def merge(
    paths: list[Path], tmp_path: Path, *, per_file: bool = True, keep: bool = True, respect: bool = True
) -> OpenDocument:
    return OpenDocument.merge(
        paths, tmp_path / "merged.pdf", bookmark_per_file=per_file, keep_bookmarks=keep, respect_permissions=respect
    )


def save_and_open(document: OpenDocument) -> pikepdf.Pdf:
    plan = document.save_plan()
    save(plan)
    document.mark_saved(plan)
    return pikepdf.open(plan.target)


def test_the_files_are_merged_in_order_into_a_new_document(tmp_path: Path) -> None:
    paths = [make_pdf(tmp_path / f"{name}.pdf", page_count=count) for name, count in (("a", 2), ("b", 3), ("c", 1))]
    document = merge(paths, tmp_path)
    assert document.page_count == 6
    assert [page.source_index for page in document.pages] == [0, 1, 2, 3, 4, 5]
    assert (document.file_name, document.title) == ("merged.pdf", None)
    assert document.is_new
    assert document.is_modified  # unsaved until it is saved (F6)
    assert not document.can_undo
    with save_and_open(document) as saved:
        assert len(saved.pages) == 6
    assert (document.is_new, document.is_modified) == (False, False)


@pytest.mark.parametrize(
    ("per_file", "keep", "top", "under_first"),
    [
        (True, True, ["one", "two"], ["Cover", "1. Intro", "Action"]),
        (True, False, ["one", "two"], []),
        (False, True, ["Cover", "1. Intro", "Action", "Cover", "1. Intro", "Action"], ["1.1 Scope"]),
        (False, False, [], []),
    ],
)
def test_the_bookmarks_of_the_files_as_chosen(
    tmp_path: Path, per_file: bool, keep: bool, top: list[str], under_first: list[str]
) -> None:
    paths = [outlined_pdf(tmp_path / "one.pdf"), outlined_pdf(tmp_path / "two.pdf")]
    document = merge(paths, tmp_path, per_file=per_file, keep=keep)
    assert [bookmark.title for bookmark in document.bookmarks] == top
    if per_file:
        assert [bookmark.page for bookmark in document.bookmarks] == [0, 5]
        assert all(bookmark.is_open for bookmark in document.bookmarks)  # unfolded (D50)
    first_children = document.bookmarks[1 if not per_file else 0].children if top else []
    assert [bookmark.title for bookmark in first_children] == under_first


def test_a_pdf_whose_permissions_deny_assembling_cannot_be_merged(tmp_path: Path) -> None:
    paths = [make_pdf(tmp_path / "plain.pdf"), make_pdf(tmp_path / "locked.pdf", passwords=("owner", ""))]
    with pytest.raises(AssemblyNotAllowedError):
        merge(paths, tmp_path)


def test_a_pdf_whose_permissions_allow_assembling_is_merged(tmp_path: Path) -> None:
    paths = [make_pdf(tmp_path / "plain.pdf"), make_pdf_with_permissions(tmp_path / "open.pdf", "modify_assembly")]
    document = merge(paths, tmp_path)
    assert document.page_count == 3 + 3
    document.close()


def test_with_permissions_ignored_any_pdf_without_password_is_merged_and_the_result_has_none(tmp_path: Path) -> None:
    locked = make_pdf(tmp_path / "locked.pdf", page_count=2, passwords=("owner", ""))
    document = merge([make_pdf(tmp_path / "plain.pdf"), locked], tmp_path, respect=False)
    assert document.page_count == 3 + 2
    with save_and_open(document) as pdf:
        assert not pdf.is_encrypted
        assert len(pdf.pages) == 3 + 2
    document.close()


def test_fields_with_the_same_name_are_numbered(tmp_path: Path) -> None:
    paths = [
        form_pdf(tmp_path / "first.pdf", ["name", "city"]),
        form_pdf(tmp_path / "second.pdf", ["name", "name_2"], font="/Cour"),
        form_pdf(tmp_path / "third.pdf", ["name"]),
    ]
    with save_and_open(merge(paths, tmp_path)) as saved:
        form = saved.Root.AcroForm
        fields = form.Fields
        assert [str(fields[index].T) for index in range(len(fields))] == [
            "name",
            "city",
            "name_2",
            "name_2_2",
            "name_3",
        ]
        for index, page in enumerate(saved.pages):
            assert fields[index].objgen == page.obj.Annots[0].objgen  # the field on its page, not a loose copy
        assert set(form.DR.Font.keys()) == {"/Helv", "/Cour"}
        assert str(form.DA) == "/Helv 0 Tf 0 g"


def test_the_fields_of_added_pages_join_the_form(tmp_path: Path) -> None:
    document = OpenDocument.open(form_pdf(tmp_path / "own.pdf", ["name"]))
    added = document.add_source(form_pdf(tmp_path / "added.pdf", ["name", "left out"]))
    document.execute(AddPages(document, added, 1))
    document.execute(DeletePages(document, [2]))
    with save_and_open(document) as saved:
        fields = saved.Root.AcroForm.Fields
        assert [str(fields[index].T) for index in range(len(fields))] == ["name", "name_2"]
