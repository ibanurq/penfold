"""Editing bookmarks from the Bookmarks view: its bar, the Delete key and the notice to undo (fase 5)."""

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from gi.repository import Gtk

from tests.gtk_helpers import process_pending_events, wait_until_stable
from tests.sample_pdfs import make_pdf
from tests.test_bookmarks import add_outline
from tests.test_page_editing import enabled
from tests.test_sidebar import open_and_wait

if TYPE_CHECKING:
    from penfold.application import PenfoldApplication
    from penfold.ui.window import PenfoldWindow


@pytest.fixture
def window(application: "PenfoldApplication", tmp_path: Path) -> Iterator["PenfoldWindow"]:
    """A window with the outline of add_outline, its rows: Cover, 1. Intro, 1.1 Scope, Broken, Action."""
    from penfold.ui.sidebar import sidebar as sidebar_views
    from penfold.ui.window import PenfoldWindow

    path = make_pdf(tmp_path / "outline.pdf", page_count=5)
    add_outline(path)
    new_window = PenfoldWindow(application)
    new_window.set_default_size(1100, 750)
    new_window.present()
    open_and_wait(new_window, path)
    new_window.sidebar.show_view(sidebar_views.BOOKMARKS)
    yield new_window
    new_window.destroy()
    process_pending_events()


def rows(window: "PenfoldWindow") -> list[str]:
    """The titles of the rows shown, indented by two spaces for each level."""
    from penfold.ui.sidebar.bookmarks_view import BookmarkItem

    tree = window.bookmarks_view.tree
    titles = []
    for index in range(tree.get_n_items()):
        row = tree.get_row(index)
        assert row is not None
        item = row.get_item()
        assert isinstance(item, BookmarkItem)
        titles.append("  " * row.get_depth() + item.bookmark.title)
    return titles


def select(window: "PenfoldWindow", *indexes: int) -> None:
    selected = Gtk.Bitset.new_empty()
    for index in indexes:
        selected.add(index)
    view = window.bookmarks_view
    view.selection.set_selection(selected, Gtk.Bitset.new_range(0, view.tree.get_n_items()))


def selected_titles(window: "PenfoldWindow") -> list[str]:
    return [bookmark.title for bookmark in window.bookmarks_view.selected_bookmarks()]


def test_the_bar_appears_with_bookmarks_selected(window: "PenfoldWindow") -> None:
    view = window.bookmarks_view
    assert not view.action_bar.get_revealed()
    assert not enabled(window, "delete-bookmarks")
    select(window, 0)
    assert view.action_bar.get_revealed()
    assert enabled(window, "delete-bookmarks")
    assert not enabled(window, "indent-bookmarks")  # the first of its level
    assert not enabled(window, "outdent-bookmarks")  # at the top level
    select(window, 2, 3)
    assert enabled(window, "indent-bookmarks")
    assert enabled(window, "outdent-bookmarks")


def test_indenting_and_outdenting_keep_the_bookmarks_selected(window: "PenfoldWindow") -> None:
    document = window.document
    assert document is not None
    select(window, 3, 4)
    window.activate_action("win.indent-bookmarks", None)
    assert rows(window) == ["Cover", "1. Intro", "  1.1 Scope", "  Broken", "  Action"]
    assert selected_titles(window) == ["Broken", "Action"]
    assert document.is_modified
    window.activate_action("win.outdent-bookmarks", None)
    assert rows(window) == ["Cover", "1. Intro", "  1.1 Scope", "Broken", "Action"]
    assert selected_titles(window) == ["Broken", "Action"]
    assert not enabled(window, "outdent-bookmarks")


def test_undo_selects_the_bookmarks_as_they_were(window: "PenfoldWindow") -> None:
    document = window.document
    assert document is not None
    select(window, 3)
    window.activate_action("win.indent-bookmarks", None)
    window.activate_action("win.undo", None)
    assert rows(window) == ["Cover", "1. Intro", "  1.1 Scope", "Broken", "Action"]
    assert selected_titles(window) == ["Broken"]
    assert not document.is_modified


def test_deleting_shows_a_notice_that_undoes_it(window: "PenfoldWindow", monkeypatch: pytest.MonkeyPatch) -> None:
    from gi.repository import Adw

    toasts: list[Adw.Toast] = []
    monkeypatch.setattr(window.toast_overlay, "add_toast", toasts.append)
    select(window, 1, 2, 4)
    window.activate_action("win.delete-bookmarks", None)
    assert rows(window) == ["Cover", "Broken"]
    assert not window.bookmarks_view.action_bar.get_revealed()
    [toast] = toasts
    assert toast.get_title() == "2 bookmarks deleted"
    toast.emit("button-clicked")
    assert rows(window) == ["Cover", "1. Intro", "  1.1 Scope", "Broken", "Action"]


def test_the_delete_key_deletes_the_selected_bookmarks(window: "PenfoldWindow") -> None:
    document = window.document
    assert document is not None
    select(window, 0)
    assert window._on_delete_key(window, None)
    assert rows(window) == ["1. Intro", "  1.1 Scope", "Broken", "Action"]
    assert document.page_count == 5
    assert not window._on_delete_key(window, None)  # nothing selected any more


def test_the_delete_key_deletes_bookmarks_only_in_their_view(window: "PenfoldWindow") -> None:
    from penfold.ui.sidebar import sidebar as sidebar_views

    select(window, 0)
    window.sidebar.show_view(sidebar_views.PAGES)
    assert not window._on_delete_key(window, None)
    assert len(rows(window)) == 5


def test_add_titles_the_bookmark_with_the_selected_text(
    window: "PenfoldWindow", monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(window.document_view, "selected_text", lambda: ("Terms\n of  use", 3))
    window.activate_action("win.add-bookmark", None)
    assert window.get_visible_dialog() is None
    assert rows(window) == ["Cover", "1. Intro", "  1.1 Scope", "  Terms of use", "Broken", "Action"]
    assert selected_titles(window) == ["Terms of use"]
    [added] = window.bookmarks_view.selected_bookmarks()
    assert added.page == 3


def test_add_asks_for_a_title_proposing_the_current_page(window: "PenfoldWindow") -> None:
    from gi.repository import Adw

    from penfold.ui.dialogs.text_question import RESPONSE_CONFIRM

    window.document_view.go_to(4)
    process_pending_events()
    window.activate_action("win.add-bookmark", None)
    dialog = window.get_visible_dialog()
    assert isinstance(dialog, Adw.AlertDialog)
    entry = dialog.get_extra_child()
    assert isinstance(entry, Gtk.Entry)
    assert entry.get_text() == "Page 5"
    entry.set_text(" Last page ")
    dialog.emit("response", RESPONSE_CONFIRM)
    dialog.close()
    assert rows(window)[-1] == "Last page"
    assert selected_titles(window) == ["Last page"]


def test_cancelling_the_title_adds_nothing(window: "PenfoldWindow") -> None:
    from gi.repository import Adw

    from penfold.ui.dialogs.text_question import RESPONSE_CANCEL

    document = window.document
    assert document is not None
    window.activate_action("win.add-bookmark", None)
    dialog = window.get_visible_dialog()
    assert isinstance(dialog, Adw.AlertDialog)
    dialog.emit("response", RESPONSE_CANCEL)
    dialog.close()
    assert len(rows(window)) == 5
    assert not document.is_modified


def test_a_blank_title_cannot_be_confirmed() -> None:
    from penfold.ui.dialogs.text_question import RESPONSE_CONFIRM, text_question

    answers: list[str] = []
    dialog = text_question("Title", "Page 1", "_Add", answers.append)
    entry = dialog.get_extra_child()
    assert isinstance(entry, Gtk.Entry)
    entry.set_text("  ")
    assert not dialog.get_response_enabled(RESPONSE_CONFIRM)
    entry.set_text("Done")
    assert dialog.get_response_enabled(RESPONSE_CONFIRM)
    dialog.emit("response", RESPONSE_CONFIRM)
    dialog.emit("response", RESPONSE_CONFIRM)
    assert answers == ["Done"]


def test_editing_the_text_and_pointing_need_one_bookmark(window: "PenfoldWindow") -> None:
    select(window, 0)
    assert enabled(window, "rename-bookmark")
    assert enabled(window, "point-bookmark")
    select(window, 0, 3)
    assert not enabled(window, "rename-bookmark")
    assert not enabled(window, "point-bookmark")


def test_editing_the_text_asks_for_it_starting_with_the_title(window: "PenfoldWindow") -> None:
    from gi.repository import Adw

    from penfold.ui.dialogs.text_question import RESPONSE_CONFIRM

    document = window.document
    assert document is not None
    select(window, 2)
    window.activate_action("win.rename-bookmark", None)
    dialog = window.get_visible_dialog()
    assert isinstance(dialog, Adw.AlertDialog)
    entry = dialog.get_extra_child()
    assert isinstance(entry, Gtk.Entry)
    assert entry.get_text() == "1.1 Scope"
    entry.set_text("1.1 Purpose")
    dialog.emit("response", RESPONSE_CONFIRM)
    dialog.close()
    assert rows(window) == ["Cover", "1. Intro", "  1.1 Purpose", "Broken", "Action"]
    assert selected_titles(window) == ["1.1 Purpose"]
    window.activate_action("win.undo", None)
    assert rows(window)[2] == "  1.1 Scope"
    assert not document.is_modified


def test_pointing_leads_to_the_start_of_the_current_page(window: "PenfoldWindow") -> None:
    document = window.document
    assert document is not None
    window.document_view.go_to(3)
    process_pending_events()
    select(window, 1)
    window.activate_action("win.point-bookmark", None)
    [pointed] = window.bookmarks_view.selected_bookmarks()
    assert (pointed.title, pointed.page, pointed.top, pointed.origin) == ("1. Intro", 3, None, None)
    assert document.is_modified
    window.activate_action("win.point-bookmark", None)  # already there: nothing to undo twice
    window.activate_action("win.undo", None)
    assert not document.is_modified


def state(window: "PenfoldWindow", name: str) -> object:
    action = window.lookup_action(name)
    assert action is not None
    value = action.get_state()
    assert value is not None
    return value.unpack()


def test_the_format_panel_shows_the_style_the_selection_shares(window: "PenfoldWindow") -> None:
    select(window, 0)  # Cover: bold and red
    assert (state(window, "bookmark-bold"), state(window, "bookmark-italic")) == (True, False)
    assert state(window, "bookmark-color") == "#ff0000"
    select(window, 0, 1)  # with 1. Intro: italic, no colour
    assert (state(window, "bookmark-bold"), state(window, "bookmark-italic")) == (False, False)
    assert state(window, "bookmark-color") == ""


def test_bold_and_italic_turn_on_unless_all_have_them(window: "PenfoldWindow") -> None:
    document = window.document
    assert document is not None
    select(window, 0, 1)
    window.activate_action("win.bookmark-bold", None)
    assert [bookmark.bold for bookmark in window.bookmarks_view.selected_bookmarks()] == [True, True]
    assert state(window, "bookmark-bold") is True
    window.activate_action("win.bookmark-bold", None)
    assert [bookmark.bold for bookmark in window.bookmarks_view.selected_bookmarks()] == [False, False]
    window.activate_action("win.bookmark-italic", None)
    assert [bookmark.italic for bookmark in window.bookmarks_view.selected_bookmarks()] == [True, True]
    assert selected_titles(window) == ["Cover", "1. Intro"]


def test_a_colour_and_clearing_the_format(window: "PenfoldWindow") -> None:
    from gi.repository import GLib

    document = window.document
    assert document is not None
    select(window, 1, 3)
    window.activate_action("win.bookmark-color", GLib.Variant.new_string("#606971"))
    assert state(window, "bookmark-color") == "#606971"
    assert {bookmark.color for bookmark in window.bookmarks_view.selected_bookmarks()} == {
        (0x60 / 255, 0x69 / 255, 0x71 / 255)
    }
    select(window, 0, 1)
    window.activate_action("win.clear-bookmark-format", None)
    cleared = window.bookmarks_view.selected_bookmarks()
    assert [(bookmark.bold, bookmark.italic, bookmark.color) for bookmark in cleared] == [(False, False, None)] * 2
    window.activate_action("win.undo", None)
    window.activate_action("win.undo", None)
    assert not document.is_modified


def test_colours_go_to_and_from_hex() -> None:
    from penfold.ui.sidebar.bookmark_format import BOOKMARK_COLORS, color_to_hex, hex_to_color

    assert [color_to_hex(hex_to_color(value)) for value in BOOKMARK_COLORS] == list(BOOKMARK_COLORS)
    with pytest.raises(ValueError, match="not a colour"):
        hex_to_color("red")


@pytest.mark.parametrize(
    ("y", "expected"), [(10, "BEFORE"), (15.9, "BEFORE"), (16.1, "INSIDE"), (23.9, "INSIDE"), (24.1, "AFTER")]
)
def test_dropping_on_a_row_goes_before_inside_or_after_by_height(y: float, expected: str) -> None:
    from penfold.document.commands.bookmarks import Placement
    from penfold.ui.sidebar.bookmarks_view import drop_placement

    assert drop_placement(y, 10, 20) is Placement[expected]


def row_middle(window: "PenfoldWindow", title: str, share: float = 0.5) -> float:
    """A height of the list over the row of a bookmark: share 0 is its top, 1 its bottom."""
    view = window.bookmarks_view
    for row in view._rows.values():
        if row.bookmark is not None and row.bookmark.title == title:
            found, bounds = row.compute_bounds(view.scrolled)
            assert found
            return bounds.get_y() + bounds.get_height() * share
    raise LookupError(title)


def test_bookmarks_dropped_on_a_row_move_once_the_drag_ends(window: "PenfoldWindow") -> None:
    from penfold.document.commands.bookmarks import Placement
    from penfold.ui.sidebar.bookmarks_view import DraggedBookmarks

    view = window.bookmarks_view
    wait_until_stable(lambda: row_middle(window, "Action"))
    document = window.document
    assert document is not None
    action, cover = document.bookmarks[3], document.bookmarks[0]
    assert view._drop_place([action], row_middle(window, "Cover", 0.5)) == (cover, Placement.INSIDE)
    assert view._drop_place([action], row_middle(window, "Cover", 0.1)) == (cover, Placement.BEFORE)
    assert view._drop_place([cover], row_middle(window, "Cover")) is None  # on itself
    assert view._on_drop(Gtk.DropTarget(), DraggedBookmarks([action]), 0, row_middle(window, "Cover", 0.1))
    assert rows(window)[0] == "Cover"  # not before the drag has ended
    view._on_drag_end(Gtk.DragSource(), None, False)  # type: ignore[arg-type]
    process_pending_events()
    assert rows(window) == ["Action", "Cover", "1. Intro", "  1.1 Scope", "Broken"]
    assert selected_titles(window) == ["Action"]


def test_bookmarks_dropped_below_the_rows_go_to_the_end(window: "PenfoldWindow") -> None:
    from penfold.document.commands.bookmarks import Placement

    view = window.bookmarks_view
    wait_until_stable(lambda: row_middle(window, "Action"))
    document = window.document
    assert document is not None
    scope = document.bookmarks[1].children[0]
    assert view._drop_place([scope], row_middle(window, "Action", 1) + 50) == (None, Placement.AFTER)
    view.emit("move-requested", [scope], None, Placement.AFTER)
    assert rows(window) == ["Cover", "1. Intro", "Broken", "Action", "1.1 Scope"]


def test_dropping_bookmarks_where_they_are_changes_nothing(window: "PenfoldWindow") -> None:
    from penfold.document.commands.bookmarks import Placement

    document = window.document
    assert document is not None
    cover, intro = document.bookmarks[0], document.bookmarks[1]
    window.bookmarks_view.emit("move-requested", [cover], intro, Placement.BEFORE)
    assert not document.can_undo
