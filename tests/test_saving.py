"""Saving: the PDF changed in place, nothing lost, never a damaged file (03-arquitectura 6, D14, D15, J1)."""

import stat
from pathlib import Path

import pikepdf
import pytest

from penfold.document.commands.pages import DeletePages, MovePages, RotatePages
from penfold.document.document import OpenDocument
from penfold.document.pages import Page
from penfold.document.saving import save
from penfold.document.sources import SourceFile
from penfold.errors import SaveError
from tests.sample_pdfs import make_pdf, make_pdf_with_permissions

PAGE_WIDTHS = [100, 101, 102, 103, 104]
URI = "https://example.org/"


def make_rich_pdf(path: Path) -> Path:
    """Five pages told apart by their width, with labels, an outline, a form and a note from another program."""
    pdf = pikepdf.new()
    for width in PAGE_WIDTHS:
        pdf.add_blank_page(page_size=(width, 200))
    pages = pdf.pages
    pages[3].obj.Rotate = 90
    pdf.Root.PageLabels = pikepdf.Dictionary(
        Nums=pikepdf.Array([0, pikepdf.Dictionary(S=pikepdf.Name.r), 2, pikepdf.Dictionary(S=pikepdf.Name.D)])
    )
    _add_outline(pdf)
    _add_form(pdf)
    note = pikepdf.Dictionary(
        Type=pikepdf.Name.Annot,
        Subtype=pikepdf.Name.Text,
        Rect=[10, 10, 30, 30],
        Contents=pikepdf.String("Hello"),
        T=pikepdf.String("Someone"),
    )
    pages[4].obj.Annots = pdf.make_indirect(pikepdf.Array([pdf.make_indirect(note)]))
    pdf.save(path)
    return path


def _add_outline(pdf: pikepdf.Pdf) -> None:
    pages = pdf.pages
    with pdf.open_outline() as outline:
        chapter = pikepdf.OutlineItem("Chapter", pikepdf.Array([pages[2].obj, pikepdf.Name.FitH, 150]))
        chapter.children.append(pikepdf.OutlineItem("Section", pikepdf.Array([pages[3].obj, pikepdf.Name.Fit])))
        chapter.children.append(pikepdf.OutlineItem("Deleted", pikepdf.Array([pages[1].obj, pikepdf.Name.Fit])))
        chapter.is_closed = True
        cover = pikepdf.OutlineItem("Cover", pikepdf.Array([pages[0].obj, pikepdf.Name.XYZ, 0, 180, 2]))
        web = pikepdf.OutlineItem("Web", action=pikepdf.Dictionary(S=pikepdf.Name.URI, URI=pikepdf.String(URI)))
        outline.root.extend([cover, chapter, web])
    pdf.Root.Outlines.First.C = pikepdf.Array([1, 0, 0])
    pdf.Root.Outlines.First.F = 2  # Bold.


def _add_form(pdf: pikepdf.Pdf) -> None:
    fields = []
    for name, page in (("kept", pdf.pages[0]), ("gone", pdf.pages[1])):
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
    pdf.Root.AcroForm = pdf.make_indirect(pikepdf.Dictionary(Fields=pikepdf.Array(fields)))


@pytest.fixture
def document(tmp_path: Path) -> OpenDocument:
    return OpenDocument.open(make_rich_pdf(tmp_path / "rich.pdf"))


def save_over(document: OpenDocument, target: Path | None = None) -> pikepdf.Pdf:
    """Save the document and open the result to look at it."""
    plan = document.save_plan(target)
    save(plan)
    document.mark_saved(plan)
    return pikepdf.open(plan.target)


def widths(pdf: pikepdf.Pdf) -> list[int]:
    return [int(page.mediabox[2]) for page in pdf.pages]


def outline_titles(pdf: pikepdf.Pdf) -> list[str]:
    with pdf.open_outline() as outline:
        return [item.title for item in outline.root] + [item.title for item in outline.root[1].children]


def test_pages_are_saved_in_their_order_and_turn(document: OpenDocument) -> None:
    document.execute(RotatePages(document, [3], 90))
    document.execute(MovePages(document, [3], 0))
    document.execute(DeletePages(document, [2]))
    with save_over(document) as pdf:
        assert widths(pdf) == [103, 100, 102, 104]
        assert [page.obj.get("/Rotate") for page in pdf.pages] == [180, None, None, None]
        assert not pdf.check()
    assert not document.is_modified


def test_each_page_keeps_its_label(document: OpenDocument) -> None:
    document.execute(MovePages(document, [0, 1], 5))
    document.execute(DeletePages(document, [0]))
    with save_over(document) as pdf:
        assert pdf.Root.PageLabels.Nums == pikepdf.Array(
            [0, pikepdf.Dictionary(S=pikepdf.Name.D, St=2), 2, pikepdf.Dictionary(S=pikepdf.Name.r)]
        )
    reopened = OpenDocument.open(document.path)
    assert [reopened.page_label(position) for position in range(4)] == ["2", "3", "i", "ii"]


def test_a_pdf_without_labels_gets_none(tmp_path: Path) -> None:
    document = OpenDocument.open(make_pdf(tmp_path / "plain.pdf"))
    document.execute(MovePages(document, [0], 3))
    with save_over(document) as pdf:
        assert "/PageLabels" not in pdf.Root


def test_the_outline_keeps_destinations_actions_and_style(document: OpenDocument) -> None:
    document.execute(MovePages(document, [0], 5))
    with save_over(document) as pdf, pdf.open_outline() as outline:
        cover, chapter, web = outline.root
        assert (cover.title, int(cover.obj.F), list(cover.obj.C)) == ("Cover", 2, [1, 0, 0])
        assert list(cover.destination)[1:] == [pikepdf.Name.XYZ, 0, 180, 2]
        assert cover.destination[0].objgen == pdf.pages[4].obj.objgen
        assert list(chapter.destination)[1:] == [pikepdf.Name.FitH, 150]
        assert (chapter.is_closed, int(chapter.obj.Count)) == (True, -2)
        assert web.action.URI == URI
        assert pdf.Root.PageMode == pikepdf.Name.UseOutlines
        assert not pdf.check()


def test_bookmarks_of_deleted_pages_are_left_out(document: OpenDocument) -> None:
    document.execute(DeletePages(document, [1]))
    with save_over(document) as pdf:
        assert outline_titles(pdf) == ["Cover", "Chapter", "Web", "Section"]
        assert int(pdf.Root.Outlines.Count) == 3


def test_notes_of_other_programs_are_kept_as_they_were(document: OpenDocument) -> None:
    document.execute(MovePages(document, [4], 0))
    with save_over(document) as pdf:
        note = pdf.pages[0].obj.Annots[0]
        assert (note.Subtype, str(note.Contents), str(note.T)) == (pikepdf.Name.Text, "Hello", "Someone")


def test_form_fields_of_deleted_pages_are_removed(document: OpenDocument) -> None:
    document.execute(DeletePages(document, [1]))
    with save_over(document) as pdf:
        fields = pdf.Root.AcroForm.Fields
        assert [str(fields[index].T) for index in range(len(fields))] == ["kept"]
        assert not pdf.check()


def test_saving_again_starts_from_the_pdf_as_it_was_opened(document: OpenDocument) -> None:
    document.execute(DeletePages(document, [0]))
    save_over(document).close()
    document.undo()
    document.execute(DeletePages(document, [4]))
    assert document.is_modified
    with save_over(document) as pdf:
        assert widths(pdf) == [100, 101, 102, 103]


def test_undoing_after_saving_brings_back_the_changes_to_save(document: OpenDocument) -> None:
    document.execute(DeletePages(document, [0]))
    save_over(document).close()
    document.undo()
    assert document.is_modified
    document.redo()
    assert not document.is_modified


def test_save_as_writes_another_file_that_becomes_the_document(document: OpenDocument, tmp_path: Path) -> None:
    original = document.path
    before = original.read_bytes()
    document.execute(DeletePages(document, [0]))
    with save_over(document, tmp_path / "copy.pdf") as pdf:
        assert len(pdf.pages) == 4
    assert document.path == tmp_path / "copy.pdf"
    assert document.file_name == "copy.pdf"
    assert original.read_bytes() == before


def test_saving_over_a_file_keeps_its_permissions(document: OpenDocument) -> None:
    document.path.chmod(0o640)
    save_over(document).close()
    assert stat.S_IMODE(document.path.stat().st_mode) == 0o640


def test_a_failed_save_leaves_the_file_as_it_was(document: OpenDocument, monkeypatch: pytest.MonkeyPatch) -> None:
    before = document.path.read_bytes()
    document.execute(DeletePages(document, [0]))

    def broken_check(path: Path, page_count: int, _password: str) -> None:
        raise SaveError(f"{path} has no {page_count} pages")

    monkeypatch.setattr("penfold.document.saving._check", broken_check)
    with pytest.raises(SaveError):
        save(document.save_plan())
    assert document.path.read_bytes() == before
    assert [path.name for path in document.path.parent.iterdir()] == [document.path.name]
    assert document.is_modified


def test_a_folder_that_cannot_be_written_is_reported(document: OpenDocument, tmp_path: Path) -> None:
    with pytest.raises(SaveError):
        save(document.save_plan(tmp_path / "missing" / "copy.pdf"))


def test_pdfs_with_permissions_are_saved_keeping_them(tmp_path: Path) -> None:
    document = OpenDocument.open(make_pdf_with_permissions(tmp_path / "locked.pdf", "modify_form"))
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    with pikepdf.open(target) as pdf:
        assert pdf.is_encrypted
        assert (pdf.allow.modify_form, pdf.allow.print_highres, pdf.allow.modify_assembly) == (True, False, False)
    with pytest.raises(ValueError, match="flatten"):
        document.save_plan(target, flatten=True)
    with pytest.raises(ValueError, match="printing"):
        document.print_plan(target, frozenset())


def test_fields_with_kids_lose_only_the_kids_of_deleted_pages(tmp_path: Path) -> None:
    pdf = pikepdf.new()
    for _ in range(3):
        pdf.add_blank_page()
    parent = pdf.make_indirect(pikepdf.Dictionary(T=pikepdf.String("group"), FT=pikepdf.Name.Btn))
    kids = []
    for page in pdf.pages[:2]:
        widget = pdf.make_indirect(
            pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Widget, Rect=[0, 0, 9, 9], Parent=parent)
        )
        page.obj.Annots = pdf.make_indirect(pikepdf.Array([widget]))
        kids.append(widget)
    parent.Kids = pikepdf.Array(kids)
    only_on_two = pdf.make_indirect(
        pikepdf.Dictionary(T=pikepdf.String("solo"), Kids=pikepdf.Array([pdf.make_indirect(pikepdf.Dictionary())]))
    )
    pdf.pages[2].obj.Annots = pdf.make_indirect(pikepdf.Array([only_on_two.Kids[0]]))
    pdf.Root.AcroForm = pdf.make_indirect(pikepdf.Dictionary(Fields=pikepdf.Array([parent, only_on_two, 7])))
    path = tmp_path / "form.pdf"
    pdf.save(path)
    document = OpenDocument.open(path)
    document.execute(DeletePages(document, [1, 2]))
    with save_over(document) as saved:
        fields = saved.Root.AcroForm.Fields
        assert len(fields) == 2  # the group with one kid left, and a stray number kept as it was
        assert len(fields[0].Kids) == 1


def test_an_outline_without_bookmarks_left_is_removed(document: OpenDocument) -> None:
    document.execute(DeletePages(document, [0, 1, 2, 3]))
    document.bookmarks = [bookmark for bookmark in document.bookmarks if bookmark.page is not None]
    with save_over(document) as pdf:
        assert "/Outlines" not in pdf.Root


def test_bookmarks_keep_the_style_they_have_now(document: OpenDocument) -> None:
    cover = document.bookmarks[0]
    cover.bold, cover.color = False, None
    with save_over(document) as pdf:
        item = pdf.Root.Outlines.First
        assert ("/F" in item, "/C" in item) == (False, False)


def test_new_bookmarks_lead_to_their_page_and_height(document: OpenDocument) -> None:
    from penfold.document.bookmarks import Bookmark

    document.bookmarks = [Bookmark("Top", page=4, top=50), Bookmark("Whole", page=3)]
    with save_over(document) as pdf, pdf.open_outline() as outline:
        top, whole = outline.root
        assert list(top.destination)[1:] == [pikepdf.Name.XYZ, None, 150, None]
        assert top.destination[0].objgen == pdf.pages[4].obj.objgen
        assert list(whole.destination)[1:] == [pikepdf.Name.Fit]


def test_a_result_with_the_wrong_pages_is_not_put_in_place(
    document: OpenDocument, monkeypatch: pytest.MonkeyPatch
) -> None:
    from penfold.document import saving

    before = document.path.read_bytes()
    plan = document.save_plan()
    monkeypatch.setattr(saving, "_arrange_pages", lambda _pdf, _originals, _pages, _others: {})
    document.execute(DeletePages(document, [0]))
    with pytest.raises(SaveError):
        save(saving.SavePlan(plan.sources, plan.target, tuple(document.pages), (), None))
    assert document.path.read_bytes() == before


def test_pages_of_other_pdfs_are_copied_in_with_what_they_hold(document: OpenDocument, tmp_path: Path) -> None:
    other = pikepdf.new()
    other.add_blank_page(page_size=(300, 200))
    other.add_blank_page(page_size=(301, 200))
    link = pikepdf.Dictionary(
        Type=pikepdf.Name.Annot,
        Subtype=pikepdf.Name.Link,
        Rect=[0, 0, 10, 10],
        Dest=pikepdf.Array([other.pages[1].obj, pikepdf.Name.Fit]),
    )
    other.pages[0].obj.Annots = other.make_indirect(pikepdf.Array([other.make_indirect(link)]))
    other.save(tmp_path / "other.pdf")
    added = document.sources.add(SourceFile(tmp_path / "other.pdf"))
    document.pages = [document.pages[0], Page(added.start + 1, rotation=90), Page(added.start)]
    with save_over(document) as saved:
        assert widths(saved) == [100, 301, 300]
        assert saved.pages[1].obj.Rotate == 90
        saved_link = saved.pages[2].obj.Annots[0]
        assert saved_link.Dest[0].objgen == saved.pages[1].obj.objgen  # it still leads to its page
    reopened = OpenDocument.open(document.path)
    assert [reopened.page_label(position) for position in range(3)] == ["i", "2", "3"]
