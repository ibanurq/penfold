"""Turning, deleting and moving pages, and undoing it (E1, E2, E3, D19)."""

from pathlib import Path

import pikepdf
import pytest

from penfold.document.bookmarks import Bookmark, without_pages
from penfold.document.commands.pages import DeletePages, MovePages, RotatePages
from penfold.document.document import OpenDocument
from penfold.document.history import Change
from tests.sample_pdfs import make_pdf


@pytest.fixture
def document(tmp_path: Path) -> OpenDocument:
    labels = [(0, pikepdf.Dictionary(S=pikepdf.Name.a))]
    return OpenDocument.open(make_pdf(tmp_path / "five.pdf", page_count=5, label_ranges=labels))


def labels(document: OpenDocument) -> list[str]:
    return [document.page_label(position) for position in range(document.page_count)]


def test_rotate_turns_the_chosen_pages_and_undo_turns_them_back(document: OpenDocument) -> None:
    document.execute(RotatePages(document, [3, 1, 1], 90))
    assert [page.rotation for page in document.pages] == [0, 90, 0, 90, 0]
    document.execute(RotatePages(document, [1], -90))
    assert document.pages[1].rotation == 0
    document.undo()
    document.undo()
    assert [page.rotation for page in document.pages] == [0] * 5
    assert not document.is_modified


@pytest.mark.parametrize(("positions", "degrees"), [([], 90), ([5], 90), ([-1], 90), ([0], 45)])
def test_rotate_refuses_wrong_pages_or_angles(document: OpenDocument, positions: list[int], degrees: int) -> None:
    with pytest.raises(ValueError, match="pages"):
        RotatePages(document, positions, degrees)


def test_delete_removes_the_pages_and_undo_puts_them_back(document: OpenDocument) -> None:
    document.execute(DeletePages(document, [4, 0, 2]))
    assert labels(document) == ["b", "d"]
    assert document.page_position(1) == 0
    assert document.page_position(0) is None
    document.undo()
    assert labels(document) == ["a", "b", "c", "d", "e"]
    assert document.page_position(4) == 4
    document.redo()
    assert labels(document) == ["b", "d"]


def test_delete_cannot_remove_every_page(document: OpenDocument) -> None:
    with pytest.raises(ValueError, match="all its pages"):
        DeletePages(document, range(5))


def test_delete_removes_the_bookmarks_of_the_deleted_pages(document: OpenDocument) -> None:
    chapter = Bookmark("Chapter", page=1, children=[Bookmark("Section", page=2), Bookmark("Other", page=3)])
    outline = [Bookmark("Cover", page=0), chapter, Bookmark("No destination")]
    document.bookmarks = outline
    heard: list[Change] = []
    document.add_listener(heard.append)
    document.execute(DeletePages(document, [1, 3]))
    assert [bookmark.title for bookmark in document.bookmarks] == ["Cover", "Section", "No destination"]
    assert Change.BOOKMARKS in heard[-1]
    document.undo()
    assert document.bookmarks is outline
    assert [child.title for child in chapter.children] == ["Section", "Other"]


def test_without_pages_keeps_the_branches_of_other_pages() -> None:
    outline = [Bookmark("A", page=0, children=[Bookmark("A1", page=0, children=[Bookmark("A1a", page=1)])])]
    assert without_pages(outline, {0}) == [Bookmark("A1a", page=1)]
    assert without_pages(outline, {1}) == [Bookmark("A", page=0, children=[Bookmark("A1", page=0)])]


@pytest.mark.parametrize(
    ("positions", "before", "expected"),
    [
        ([0], 3, "bcade"),
        ([3], 1, "adbce"),
        ([0, 2], 5, "bdeac"),
        ([1, 4], 0, "beacd"),
        ([1, 3], 3, "acbde"),
        ([4], 5, "abcde"),
    ],
)
def test_move_puts_the_pages_together_before_the_target(
    document: OpenDocument, positions: list[int], before: int, expected: str
) -> None:
    document.execute(MovePages(document, positions, before))
    assert "".join(labels(document)) == expected
    document.undo()
    assert "".join(labels(document)) == "abcde"


@pytest.mark.parametrize(
    ("positions", "before", "moves"),
    [([0], 0, False), ([0], 1, False), ([1, 2], 3, False), ([1, 2], 1, False), ([1, 3], 3, True), ([0], 2, True)],
)
def test_move_knows_when_it_changes_nothing(
    document: OpenDocument, positions: list[int], before: int, *, moves: bool
) -> None:
    assert MovePages(document, positions, before).moves_anything is moves


@pytest.mark.parametrize("before", [-1, 6])
def test_move_refuses_a_place_outside_the_document(document: OpenDocument, before: int) -> None:
    with pytest.raises(ValueError, match="before position"):
        MovePages(document, [0], before)


def test_moved_pages_keep_their_turn(document: OpenDocument) -> None:
    document.execute(RotatePages(document, [0], 180))
    document.execute(MovePages(document, [0], 5))
    assert (document.page_label(4), document.pages[4].rotation) == ("a", 180)
    assert document.page_position(0) == 4
