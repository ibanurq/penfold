"""Adding, deleting, renaming, indenting, pointing, formatting and moving bookmarks, and undoing it."""

from pathlib import Path

import pikepdf
import pytest

from penfold.document.bookmarks import Bookmark, title_from_text, topmost
from penfold.document.commands.bookmarks import (
    AddBookmark,
    DeleteBookmarks,
    FormatBookmarks,
    IndentBookmarks,
    MoveBookmarks,
    OutdentBookmarks,
    Placement,
    PointBookmark,
    RenameBookmark,
    can_indent,
    can_move,
    can_outdent,
)
from penfold.document.commands.pages import MovePages
from penfold.document.document import OpenDocument
from penfold.document.history import Change
from penfold.document.saving import save
from tests.sample_pdfs import make_pdf
from tests.test_bookmarks import add_outline

Shape = list[str | tuple[str, "Shape"]]


def shape(bookmarks: list[Bookmark]) -> Shape:
    """The titles of an outline, with (title, children) for a bookmark with bookmarks under it."""
    return [
        (bookmark.title, shape(bookmark.children)) if bookmark.children else bookmark.title for bookmark in bookmarks
    ]


def find(bookmarks: list[Bookmark], title: str) -> Bookmark:
    """The first bookmark with this title, in outline order."""
    for bookmark in bookmarks:
        if bookmark.title == title:
            return bookmark
        try:
            return find(bookmark.children, title)
        except LookupError:
            pass
    raise LookupError(title)


@pytest.fixture
def document(tmp_path: Path) -> OpenDocument:
    """Six pages; the outline: A (page 1) holding A1 (2) and A2 (3), then B (5) and C (nowhere)."""
    document = OpenDocument.open(make_pdf(tmp_path / "six.pdf", page_count=6))
    document.bookmarks = [
        Bookmark("A", page=0, children=[Bookmark("A1", page=1), Bookmark("A2", page=2)]),
        Bookmark("B", page=4, origin=(10, 0), top=50.0),
        Bookmark("C"),
    ]
    return document


def bookmarks_of(document: OpenDocument, *titles: str) -> list[Bookmark]:
    return [find(document.bookmarks, title) for title in titles]


def test_every_edit_changes_the_bookmarks_only(document: OpenDocument) -> None:
    command = DeleteBookmarks(document, bookmarks_of(document, "C"))
    assert command.changes == Change.BOOKMARKS


def test_an_edit_leaves_the_outline_it_was_made_for_as_it_was(document: OpenDocument) -> None:
    before = document.bookmarks
    document.execute(IndentBookmarks(document, bookmarks_of(document, "B")))
    assert shape(before) == [("A", ["A1", "A2"]), "B", "C"]
    assert document.bookmarks is not before
    document.undo()
    assert document.bookmarks is before


def test_add_goes_after_the_last_bookmark_leading_to_that_page_or_before(document: OpenDocument) -> None:
    command = AddBookmark(document, "  New  ", 3)
    document.execute(command)
    assert shape(document.bookmarks) == [("A", ["A1", "A2", "New"]), "B", "C"]
    [added] = command.bookmarks
    assert (added.title, added.page, added.top, added.origin) == ("New", 3, None, None)
    assert document.bookmarks[0].is_open
    document.undo()
    assert shape(document.bookmarks) == [("A", ["A1", "A2"]), "B", "C"]
    assert not document.bookmarks[0].is_open


def test_add_goes_first_under_a_bookmark_with_children(document: OpenDocument) -> None:
    document.bookmarks[0].children[0].page = 3
    document.execute(AddBookmark(document, "New", 0))
    assert shape(document.bookmarks) == [("A", ["New", "A1", "A2"]), "B", "C"]


def test_bookmarks_leading_nowhere_do_not_count(document: OpenDocument) -> None:
    document.execute(AddBookmark(document, "New", 5))
    assert shape(document.bookmarks) == [("A", ["A1", "A2"]), "B", "New", "C"]


def test_add_goes_first_when_every_bookmark_leads_after(document: OpenDocument) -> None:
    document.bookmarks = [Bookmark("B", page=4)]
    document.execute(AddBookmark(document, "New", 1))
    assert shape(document.bookmarks) == ["New", "B"]


def test_add_follows_where_the_pages_are_now(document: OpenDocument) -> None:
    document.execute(MovePages(document, [4], 0))
    document.execute(AddBookmark(document, "New", 0))
    assert shape(document.bookmarks) == [("A", ["A1", "A2"]), "B", "New", "C"]


@pytest.mark.parametrize(("title", "position"), [(" ", 0), ("New", 6), ("New", -1)])
def test_add_needs_a_title_and_a_page(document: OpenDocument, title: str, position: int) -> None:
    with pytest.raises(ValueError, match=r"title|position"):
        AddBookmark(document, title, position)


def test_delete_takes_the_bookmarks_under_them_too(document: OpenDocument) -> None:
    document.execute(DeleteBookmarks(document, bookmarks_of(document, "A2", "A", "C")))
    assert shape(document.bookmarks) == ["B"]
    document.undo()
    assert shape(document.bookmarks) == [("A", ["A1", "A2"]), "B", "C"]
    document.redo()
    assert shape(document.bookmarks) == ["B"]


def test_delete_needs_bookmarks_of_the_outline(document: OpenDocument) -> None:
    with pytest.raises(ValueError, match="no bookmarks"):
        DeleteBookmarks(document, [])
    with pytest.raises(ValueError, match="not all in the outline"):
        DeleteBookmarks(document, [Bookmark("A")])


def test_rename_changes_only_the_title(document: OpenDocument) -> None:
    command = RenameBookmark(document, find(document.bookmarks, "B"), " Better ")
    document.execute(command)
    [renamed] = command.bookmarks
    assert (renamed.title, renamed.page, renamed.top, renamed.origin) == ("Better", 4, 50.0, (10, 0))
    assert renamed is document.bookmarks[1]
    document.undo()
    assert document.bookmarks[1].title == "B"


def test_rename_needs_a_title(document: OpenDocument) -> None:
    with pytest.raises(ValueError, match="title"):
        RenameBookmark(document, find(document.bookmarks, "B"), "\n")


def test_point_leads_to_the_start_of_the_page_and_forgets_the_original_destination(document: OpenDocument) -> None:
    document.execute(MovePages(document, [5], 0))
    command = PointBookmark(document, find(document.bookmarks, "B"), 0)
    document.execute(command)
    [pointed] = command.bookmarks
    assert (pointed.page, pointed.top, pointed.origin, pointed.view) == (5, None, None, None)
    document.undo()
    assert (document.bookmarks[1].page, document.bookmarks[1].origin) == (4, (10, 0))


def test_a_pointed_bookmark_is_saved_with_its_new_destination_only(tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "outline.pdf", page_count=5)
    add_outline(path)
    document = OpenDocument.open(path)
    action = find(document.bookmarks, "Action")
    document.execute(PointBookmark(document, action, 1))
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    with pikepdf.open(target) as pdf:
        item = pdf.Root.Outlines.Last
        assert str(item.Title) == "Action"
        assert "/A" not in item
        assert item.Dest[0].objgen == pdf.pages[1].obj.objgen
        assert item.Dest[1] == pikepdf.Name.Fit


def test_point_needs_a_page(document: OpenDocument) -> None:
    with pytest.raises(ValueError, match="position"):
        PointBookmark(document, find(document.bookmarks, "B"), 6)


def test_indent_puts_each_bookmark_last_under_the_one_before(document: OpenDocument) -> None:
    document.bookmarks[0].is_open = False
    command = IndentBookmarks(document, bookmarks_of(document, "B", "C"))
    document.execute(command)
    assert shape(document.bookmarks) == [("A", ["A1", "A2", "B", "C"])]
    assert document.bookmarks[0].is_open
    assert [bookmark.title for bookmark in command.bookmarks] == ["B", "C"]


def test_indent_leaves_the_first_of_a_level_and_moves_children_with_their_parent(document: OpenDocument) -> None:
    document.execute(IndentBookmarks(document, bookmarks_of(document, "A", "A1", "A2", "B")))
    assert shape(document.bookmarks) == [("A", ["A1", "A2", "B"]), "C"]


def test_indent_and_outdent_say_when_they_can_move_something(document: OpenDocument) -> None:
    outline = document.bookmarks
    assert not can_indent(outline, bookmarks_of(document, "A", "A1"))
    assert can_indent(outline, bookmarks_of(document, "A1", "A2"))
    assert not can_outdent(outline, bookmarks_of(document, "A", "A1", "B"))
    assert can_outdent(outline, bookmarks_of(document, "A2"))
    with pytest.raises(ValueError, match="indented"):
        IndentBookmarks(document, bookmarks_of(document, "A1"))
    with pytest.raises(ValueError, match="outdented"):
        OutdentBookmarks(document, bookmarks_of(document, "B"))


def test_outdent_puts_each_bookmark_just_after_its_parent_in_order(document: OpenDocument) -> None:
    document.execute(OutdentBookmarks(document, bookmarks_of(document, "A1", "A2", "C")))
    assert shape(document.bookmarks) == ["A", "A1", "A2", "B", "C"]
    document.undo()
    assert shape(document.bookmarks) == [("A", ["A1", "A2"]), "B", "C"]


def test_outdent_leaves_the_bookmarks_after_it_under_the_parent(document: OpenDocument) -> None:
    document.execute(OutdentBookmarks(document, bookmarks_of(document, "A1")))
    assert shape(document.bookmarks) == [("A", ["A2"]), "A1", "B", "C"]


def test_format_sets_only_what_it_is_given(document: OpenDocument) -> None:
    red = (1.0, 0.0, 0.0)
    document.execute(FormatBookmarks(document, bookmarks_of(document, "A", "A1"), bold=True, color=red))
    a, a1 = bookmarks_of(document, "A", "A1")
    assert (a.bold, a.italic, a.color, a1.bold, a1.color) == (True, False, red, True, red)
    assert shape(document.bookmarks) == [("A", ["A1", "A2"]), "B", "C"]
    command = FormatBookmarks(document, [a1], italic=True)
    document.execute(command)
    [a1] = command.bookmarks
    assert (a1.bold, a1.italic, a1.color) == (True, True, red)
    document.execute(FormatBookmarks(document, [a1], bold=False, italic=False, color=None))
    a1 = find(document.bookmarks, "A1")
    assert (a1.bold, a1.italic, a1.color) == (False, False, None)
    document.undo()
    document.undo()
    document.undo()
    assert not find(document.bookmarks, "A").bold
    assert not document.is_modified


def test_formatting_bookmarks_as_they_are_changes_nothing(document: OpenDocument) -> None:
    assert not FormatBookmarks(document, bookmarks_of(document, "B"), bold=False, color=None).changes_anything
    assert FormatBookmarks(document, bookmarks_of(document, "B"), bold=True).changes_anything


def test_move_before_after_and_inside(document: OpenDocument) -> None:
    a1, b, c = bookmarks_of(document, "A1", "B", "C")
    document.execute(MoveBookmarks(document, [c, a1], b, Placement.BEFORE))
    assert shape(document.bookmarks) == [("A", ["A2"]), "A1", "C", "B"]
    document.undo()
    a, b = bookmarks_of(document, "A", "B")
    document.execute(MoveBookmarks(document, [a], b, Placement.AFTER))
    assert shape(document.bookmarks) == ["B", ("A", ["A1", "A2"]), "C"]
    document.undo()
    command = MoveBookmarks(document, bookmarks_of(document, "B"), find(document.bookmarks, "C"), Placement.INSIDE)
    document.execute(command)
    assert shape(document.bookmarks) == [("A", ["A1", "A2"]), ("C", ["B"])]
    assert document.bookmarks[1].is_open
    assert [bookmark.title for bookmark in command.bookmarks] == ["B"]


def test_move_to_the_end(document: OpenDocument) -> None:
    document.execute(MoveBookmarks(document, bookmarks_of(document, "A1", "A"), None, Placement.AFTER))
    assert shape(document.bookmarks) == ["B", "C", ("A", ["A1", "A2"])]


def test_bookmarks_cannot_move_into_themselves(document: OpenDocument) -> None:
    a, a2 = bookmarks_of(document, "A", "A2")
    assert not can_move(document.bookmarks, [a], a2)
    assert can_move(document.bookmarks, [a2], a)
    with pytest.raises(ValueError, match="themselves"):
        MoveBookmarks(document, [a], a2, Placement.INSIDE)
    with pytest.raises(ValueError, match="themselves"):
        MoveBookmarks(document, [a], a, Placement.AFTER)


def test_dropping_bookmarks_where_they_are_changes_nothing(document: OpenDocument) -> None:
    a1, a2 = bookmarks_of(document, "A1", "A2")
    assert not MoveBookmarks(document, [a1], a2, Placement.BEFORE).changes_anything
    assert MoveBookmarks(document, [a1], a2, Placement.AFTER).changes_anything


def test_topmost_keeps_only_bookmarks_not_under_another_chosen(document: OpenDocument) -> None:
    chosen = bookmarks_of(document, "C", "A2", "A")
    assert [bookmark.title for bookmark in topmost(document.bookmarks, chosen)] == ["A", "C"]


@pytest.mark.parametrize(
    ("text", "title"),
    [("  Two\n lines\tof text ", "Two lines of text"), ("x" * 150, "x" * 150), ("x" * 151, "x" * 150 + "…")],
)
def test_title_from_selected_text(text: str, title: str) -> None:
    assert title_from_text(text) == title
