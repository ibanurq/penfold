"""Adding the pages of another PDF, with its bookmarks, and undoing it (E4, E6, D19)."""

from pathlib import Path

import pikepdf
import pytest

from penfold.document.bookmarks import Bookmark, for_added_pages, read_bookmarks, with_inserted
from penfold.document.commands.pages import AddPages
from penfold.document.document import OpenDocument
from penfold.document.pages import PaperSize
from penfold.document.saving import save
from penfold.errors import RestrictedPdfError
from tests.sample_pdfs import make_pdf
from tests.test_bookmarks import add_outline

FORM = Path(__file__).parent / "fixtures" / "form.pdf"


@pytest.fixture
def document(tmp_path: Path) -> OpenDocument:
    labels = [(0, pikepdf.Dictionary(S=pikepdf.Name.a))]
    return OpenDocument.open(make_pdf(tmp_path / "five.pdf", page_count=5, label_ranges=labels))


def labels(document: OpenDocument) -> list[str]:
    return [document.page_label(position) for position in range(document.page_count)]


def outlined_pdf(path: Path) -> Path:
    """Five pages with the outline of test_bookmarks: Cover, 1. Intro (1.1 Scope), Broken, Action."""
    make_pdf(path, page_count=5)
    add_outline(path)
    return path


def test_pages_are_added_at_the_position_and_undo_takes_them_out(document: OpenDocument, tmp_path: Path) -> None:
    added = document.add_source(make_pdf(tmp_path / "three.pdf", page_count=3))
    command = AddPages(document, added, 2)
    document.execute(command)
    assert labels(document) == ["a", "b", "3", "4", "5", "c", "d", "e"]  # pages without labels go by position
    assert command.positions == range(2, 5)
    assert document.page_position(5) == 2  # the first page added comes after the five of the opened PDF
    document.undo()
    assert labels(document) == ["a", "b", "c", "d", "e"]
    assert not document.is_modified
    document.redo()
    assert document.page_count == 8


def test_added_pages_keep_their_labels(document: OpenDocument, tmp_path: Path) -> None:
    roman = [(0, pikepdf.Dictionary(S=pikepdf.Name.R))]
    added = document.add_source(make_pdf(tmp_path / "roman.pdf", page_count=2, label_ranges=roman))
    document.execute(AddPages(document, added, 5))
    assert labels(document)[5:] == ["I", "II"]


@pytest.mark.parametrize("position", [-1, 6])
def test_a_position_outside_the_document_is_refused(document: OpenDocument, tmp_path: Path, position: int) -> None:
    added = document.add_source(make_pdf(tmp_path / "one.pdf", page_count=1))
    with pytest.raises(ValueError, match="position"):
        AddPages(document, added, position)


def test_protected_pdfs_cannot_be_added(document: OpenDocument, tmp_path: Path) -> None:
    with pytest.raises(RestrictedPdfError):
        document.add_source(make_pdf(tmp_path / "locked.pdf", passwords=("owner", "")))
    assert len(document.sources.spans) == 1


def test_the_annotations_of_the_added_pages_are_listed(document: OpenDocument, tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "noted.pdf", page_count=2)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        note = pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Text, Rect=[10, 10, 30, 30])
        pdf.pages[1].Annots = pdf.make_indirect(pikepdf.Array([pdf.make_indirect(note)]))
        pdf.save(path)
    document.add_source(path)
    assert [annotation.page for annotation in document.annotations] == [6]


def test_the_pages_of_a_pdf_come_with_a_bookmark_named_after_it(document: OpenDocument, tmp_path: Path) -> None:
    added = document.add_source(outlined_pdf(tmp_path / "Report 2025.pdf"))
    [file_bookmark] = added.bookmarks
    assert (file_bookmark.title, file_bookmark.page, file_bookmark.is_open) == ("Report 2025", 5, True)
    assert [child.title for child in file_bookmark.children] == ["Cover", "1. Intro", "Action"]
    without_outline = document.add_source(make_pdf(tmp_path / "plain.pdf", page_count=1))
    assert [(bookmark.title, bookmark.children) for bookmark in without_outline.bookmarks] == [("plain", [])]
    assert document.add_blank_page(PaperSize.A4).bookmarks == []


def test_added_bookmarks_lead_to_the_new_pages_and_those_without_a_page_go(tmp_path: Path) -> None:
    with pikepdf.open(outlined_pdf(tmp_path / "outline.pdf")) as pdf:
        added = for_added_pages(read_bookmarks(pdf), 5)
    assert [(bookmark.title, bookmark.page) for bookmark in added] == [("Cover", 5), ("1. Intro", 6), ("Action", 9)]
    assert [(child.title, child.page) for child in added[1].children] == [("1.1 Scope", 7)]
    assert all(bookmark.origin is None for bookmark in added)
    assert added[2].view == ("/FitH", (500.0,))


def outline(titles_and_pages: list[tuple[str, int | None]], children: list[Bookmark] | None = None) -> list[Bookmark]:
    bookmarks = [Bookmark(title, page) for title, page in titles_and_pages]
    if children is not None:
        bookmarks[1].children = children
    return bookmarks


@pytest.mark.parametrize(
    ("first", "expected"),
    [
        (0, ["new", "A", "B", "C"]),  # before every bookmark
        (5, ["A", "B", "new", "C"]),  # after B, whose bookmarks all lead before
        (7, ["A", "B", "C", "new"]),
    ],
)
def test_inserted_bookmarks_go_after_the_last_one_before(first: int, expected: list[str]) -> None:
    bookmarks = outline([("A", 0), ("B", 2), ("C", 6)], outline([("B1", 2), ("B2", 4)]))
    inserted = with_inserted(bookmarks, [Bookmark("new")], first, lambda page: page)
    assert [bookmark.title for bookmark in inserted] == expected


def test_inserted_bookmarks_go_inside_a_branch_that_leads_past_them() -> None:
    bookmarks = outline([("A", 0), ("B", 2), ("C", 6)], outline([("B1", 2), ("B2", 4)]))
    inserted = with_inserted(bookmarks, [Bookmark("new")], 3, lambda page: page)
    assert [bookmark.title for bookmark in inserted] == ["A", "B", "C"]
    assert [child.title for child in inserted[1].children] == ["B1", "new", "B2"]
    assert inserted[1].is_open
    assert not bookmarks[1].is_open  # the outline given is left as it was
    assert [child.title for child in bookmarks[1].children] == ["B1", "B2"]


def test_bookmarks_without_a_page_count_as_before() -> None:
    inserted = with_inserted(outline([("Web", None), ("A", 4)]), [Bookmark("new")], 2, lambda page: page)
    assert [bookmark.title for bookmark in inserted] == ["Web", "new", "A"]


def test_added_pages_and_bookmarks_are_saved(document: OpenDocument, tmp_path: Path) -> None:
    added = document.add_source(outlined_pdf(tmp_path / "outline.pdf"))
    document.execute(AddPages(document, added, 5))
    plan = document.save_plan()
    save(plan)
    with pikepdf.open(plan.target) as saved:
        assert len(saved.pages) == 10
        with saved.open_outline() as saved_outline:
            [file_item] = saved_outline.root
            assert file_item.title == "outline"
            assert [item.title for item in file_item.children] == ["Cover", "1. Intro", "Action"]
            assert not file_item.is_closed
        assert saved.Root.Outlines.First.Dest[0].objgen == saved.pages[5].obj.objgen
        action = saved.Root.Outlines.First.Last
        assert action.Dest[0].objgen == saved.pages[9].obj.objgen
        assert str(action.Dest[1]) == "/FitH"
        assert int(action.Dest[2]) == 500


@pytest.mark.parametrize(
    ("size", "points"),
    [
        (PaperSize.A4, (595.28, 841.89)),
        (PaperSize.LETTER, (612, 792)),
        (PaperSize.A5, (419.53, 595.28)),
        (PaperSize.A3, (841.89, 1190.55)),
    ],
)
def test_a_blank_page_of_each_size_is_added_and_saved(
    document: OpenDocument, size: PaperSize, points: tuple[float, float]
) -> None:
    document.execute(AddPages(document, document.add_blank_page(size), 1))
    assert labels(document) == ["a", "2", "b", "c", "d", "e"]
    plan = document.save_plan()
    save(plan)
    with pikepdf.open(plan.target) as saved:
        width, height = (float(saved.pages[1].mediabox[index]) for index in (2, 3))
        assert (width, height) == pytest.approx(points)
        assert not saved.pages[1].obj.get("/Annots")
    document.undo()
    assert document.page_count == 5


def test_the_fields_of_added_pdfs_are_told_apart_by_their_source(document: OpenDocument) -> None:
    document.add_source(FORM)
    document.add_source(FORM)
    assert [field.key for field in document.form_fields if field.name == "name"] == [(5, "name"), (6, "name")]
