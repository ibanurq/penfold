"""Collapse All and Expand All in the Bookmarks view: what they do and when each is greyed out."""

import itertools
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
import pytest
from gi.repository import Gtk

from tests.gtk_helpers import process_pending_events
from tests.sample_pdfs import make_pdf
from tests.test_bookmark_editing import rows, select
from tests.test_bookmarks import add_outline, outline_item
from tests.test_sidebar import open_and_wait

if TYPE_CHECKING:
    from penfold.application import PenfoldApplication
    from penfold.ui.sidebar.bookmarks_view import BookmarksView
    from penfold.ui.window import PenfoldWindow

# Bookmarks as (title, stored open, the bookmarks under it).
type Outline = list[tuple[str, bool, Outline]]

# A tree three levels deep: Part 1 and Chapter 1 are stored open; Chapter 2 and Part 2, folded.
DEEP_OUTLINE: Outline = [
    ("Cover", False, []),
    (
        "Part 1",
        True,
        [("Chapter 1", True, [("Section 1.1", False, [])]), ("Chapter 2", False, [("Section 2.1", False, [])])],
    ),
    ("Part 2", False, [("Chapter 3", False, [])]),
    ("End", False, []),
]
DEEP_ROWS_STORED = ["Cover", "Part 1", "  Chapter 1", "    Section 1.1", "  Chapter 2", "Part 2", "End"]
DEEP_ROWS_ALL = [
    "Cover",
    "Part 1",
    "  Chapter 1",
    "    Section 1.1",
    "  Chapter 2",
    "    Section 2.1",
    "Part 2",
    "  Chapter 3",
    "End",
]
DEEP_ROWS_NONE = ["Cover", "Part 1", "Part 2", "End"]


def write_outline(path: Path, outline: Outline) -> Path:
    """Give a PDF this outline, every bookmark leading to its first page; return the path."""
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        root = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Outlines))
        first_page = pdf.pages[0].obj

        def add(parent: pikepdf.Dictionary, entries: Outline) -> int:
            """Add the entries under the parent and return how many items are shown under it."""
            items = []
            shown = 0
            for title, is_open, children in entries:
                item = outline_item(pdf, parent, title, Dest=pikepdf.Array([first_page, pikepdf.Name.Fit]))
                if children:
                    under = add(item, children)
                    item.Count = under if is_open else -len(children)
                    shown += under if is_open else 0
                items.append(item)
                shown += 1
            for previous, following in itertools.pairwise(items):
                previous.Next, following.Prev = following, previous
            parent.First, parent.Last = items[0], items[-1]
            return shown

        root.Count = add(root, outline)
        pdf.Root.Outlines = root
        pdf.save(path)
    return path


@pytest.fixture
def window(application: "PenfoldApplication") -> Iterator["PenfoldWindow"]:
    from penfold.ui.window import PenfoldWindow

    new_window = PenfoldWindow(application)
    new_window.set_default_size(1100, 750)
    new_window.present()
    yield new_window
    new_window.destroy()
    process_pending_events()


def show_bookmarks(window: "PenfoldWindow", path: Path) -> "BookmarksView":
    from penfold.ui.sidebar import sidebar as sidebar_views

    open_and_wait(window, path)
    window.sidebar.show_view(sidebar_views.BOOKMARKS)
    return window.bookmarks_view


def buttons(view: "BookmarksView") -> tuple[bool, bool]:
    """Whether Collapse All and Expand All can be pressed."""
    return view.collapse_button.get_sensitive(), view.expand_button.get_sensitive()


def tree_row(view: "BookmarksView", title: str) -> Gtk.TreeListRow:
    """The row shown of the bookmark with this title."""
    from penfold.ui.sidebar.bookmarks_view import BookmarkItem

    for index in range(view.tree.get_n_items()):
        row = view.tree.get_row(index)
        item = row.get_item() if row is not None else None
        if row is not None and isinstance(item, BookmarkItem) and item.bookmark.title == title:
            return row
    raise AssertionError(title)


def open_flags(window: "PenfoldWindow") -> dict[str, bool]:
    """Whether each bookmark with bookmarks under it is stored as unfolded."""
    from penfold.document.bookmarks import Bookmark

    assert window.document is not None
    flags = {}

    def walk(bookmarks: list[Bookmark]) -> None:
        for bookmark in bookmarks:
            if bookmark.children:
                flags[bookmark.title] = bookmark.is_open
                walk(bookmark.children)

    walk(window.document.bookmarks)
    return flags


def test_with_some_branches_unfolded_both_buttons_work(window: "PenfoldWindow", tmp_path: Path) -> None:
    view = show_bookmarks(window, write_outline(make_pdf(tmp_path / "deep.pdf"), DEEP_OUTLINE))
    assert rows(window) == DEEP_ROWS_STORED
    assert buttons(view) == (True, True)
    view.expand_button.emit("clicked")
    assert rows(window) == DEEP_ROWS_ALL
    assert buttons(view) == (True, False)
    assert open_flags(window) == dict.fromkeys(["Part 1", "Chapter 1", "Chapter 2", "Part 2"], True)
    view.collapse_button.emit("clicked")
    assert rows(window) == DEEP_ROWS_NONE
    assert buttons(view) == (False, True)
    # Every branch remembers it is folded, also those under another (the innermost are folded first).
    assert open_flags(window) == dict.fromkeys(["Part 1", "Chapter 1", "Chapter 2", "Part 2"], False)
    assert not window.document.is_modified  # type: ignore[union-attr]  # folding is not an edit


def test_collapse_all_from_the_stored_state_folds_the_inner_branches_too(
    window: "PenfoldWindow", tmp_path: Path
) -> None:
    view = show_bookmarks(window, write_outline(make_pdf(tmp_path / "deep.pdf"), DEEP_OUTLINE))
    view.collapse_all()
    assert rows(window) == DEEP_ROWS_NONE
    assert open_flags(window) == dict.fromkeys(["Part 1", "Chapter 1", "Chapter 2", "Part 2"], False)
    view.expand_all()
    assert rows(window) == DEEP_ROWS_ALL


def test_the_arrow_of_each_branch_updates_the_buttons(window: "PenfoldWindow", tmp_path: Path) -> None:
    view = show_bookmarks(window, write_outline(make_pdf(tmp_path / "deep.pdf"), DEEP_OUTLINE))
    view.collapse_all()
    tree_row(view, "Part 1").set_expanded(True)
    assert buttons(view) == (True, True)
    for title in ("Chapter 1", "Chapter 2", "Part 2"):
        tree_row(view, title).set_expanded(True)
    assert rows(window) == DEEP_ROWS_ALL
    assert buttons(view) == (True, False)
    tree_row(view, "Chapter 2").set_expanded(False)
    assert buttons(view) == (True, True)
    for title in ("Chapter 1", "Part 1", "Part 2"):
        tree_row(view, title).set_expanded(False)
    assert rows(window) == DEEP_ROWS_NONE
    assert buttons(view) == (False, True)


def test_a_pdf_with_every_branch_unfolded_greys_out_expand_all(window: "PenfoldWindow", tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "outline.pdf", page_count=5)
    add_outline(path)  # its only branch, "1. Intro", is stored open
    view = show_bookmarks(window, path)
    assert buttons(view) == (True, False)
    view.collapse_all()
    assert buttons(view) == (False, True)


@pytest.mark.parametrize(
    "outline", [[], [("Cover", False, []), ("End", False, [])]], ids=["no bookmarks", "no branches"]
)
def test_without_branches_both_buttons_are_greyed_out(
    window: "PenfoldWindow", tmp_path: Path, outline: Outline
) -> None:
    path = make_pdf(tmp_path / "plain.pdf")
    view = show_bookmarks(window, write_outline(path, outline) if outline else path)
    assert buttons(view) == (False, False)
    view.collapse_all()
    view.expand_all()
    assert buttons(view) == (False, False)


def test_before_a_pdf_is_open_both_buttons_are_greyed_out(window: "PenfoldWindow") -> None:
    assert buttons(window.bookmarks_view) == (False, False)


def test_opening_another_pdf_shows_its_own_state(window: "PenfoldWindow", tmp_path: Path) -> None:
    view = show_bookmarks(window, write_outline(make_pdf(tmp_path / "deep.pdf"), DEEP_OUTLINE))
    view.expand_all()
    assert buttons(view) == (True, False)
    flat = write_outline(make_pdf(tmp_path / "flat.pdf"), [("Cover", False, []), ("End", False, [])])
    open_and_wait(window, flat)
    assert buttons(view) == (False, False)


def test_edits_update_the_buttons(window: "PenfoldWindow", tmp_path: Path) -> None:
    from penfold.document.commands.bookmarks import Placement

    path = make_pdf(tmp_path / "outline.pdf", page_count=5)
    add_outline(path)
    view = show_bookmarks(window, path)
    assert buttons(view) == (True, False)
    # Indenting "Broken" puts it in the unfolded "1. Intro": still nothing to unfold.
    select(window, 3)
    window.activate_action("win.indent-bookmarks", None)
    assert rows(window) == ["Cover", "1. Intro", "  1.1 Scope", "  Broken", "Action"]
    assert buttons(view) == (True, False)
    window.activate_action("win.undo", None)
    assert buttons(view) == (True, False)
    # Deleting the only branch leaves nothing to fold or unfold; undoing it brings it back unfolded.
    select(window, 1)
    window.activate_action("win.delete-bookmarks", None)
    assert rows(window) == ["Cover", "Broken", "Action"]
    assert buttons(view) == (False, False)
    window.activate_action("win.undo", None)
    assert rows(window) == ["Cover", "1. Intro", "  1.1 Scope", "Broken", "Action"]
    assert buttons(view) == (True, False)
    window.activate_action("win.redo", None)
    assert buttons(view) == (False, False)
    # Dropping "Action" on "Cover" makes a new branch: the buttons follow what it shows.
    document = window.document
    assert document is not None
    cover, action = document.bookmarks[0], document.bookmarks[-1]
    view.emit("move-requested", [action], cover, Placement.INSIDE)
    process_pending_events()
    assert rows(window)[0] == "Cover"
    assert "Action" not in [bookmark.title for bookmark in document.bookmarks]
    shown = tree_row(view, "Cover").get_expanded()
    assert buttons(view) == (shown, not shown)


def test_a_folded_branch_keeps_the_buttons_right_after_an_edit(window: "PenfoldWindow", tmp_path: Path) -> None:
    view = show_bookmarks(window, write_outline(make_pdf(tmp_path / "deep.pdf"), DEEP_OUTLINE))
    view.collapse_all()
    select(window, 0)  # "Cover"
    window.activate_action("win.bookmark-bold", None)  # shows the outline again, folded as it was
    assert rows(window) == DEEP_ROWS_NONE
    assert buttons(view) == (False, True)
    view.expand_all()
    assert buttons(view) == (True, False)
    window.activate_action("win.undo", None)  # brings back the outline as it was before the edit, folded
    assert rows(window) == DEEP_ROWS_NONE
    assert buttons(view) == (False, True)


def test_the_focus_goes_to_the_other_button_when_one_greys_out(window: "PenfoldWindow", tmp_path: Path) -> None:
    view = show_bookmarks(window, write_outline(make_pdf(tmp_path / "deep.pdf"), DEEP_OUTLINE))
    assert view.collapse_button.grab_focus()
    view.collapse_button.emit("clicked")
    assert view.expand_button.is_focus()
    view.expand_button.emit("clicked")
    assert view.collapse_button.is_focus()
