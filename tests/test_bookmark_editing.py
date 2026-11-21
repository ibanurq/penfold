"""Editing bookmarks from the Bookmarks view: its bar, the Delete key and the notice to undo (fase 5)."""

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from gi.repository import Gtk

from tests.gtk_helpers import process_pending_events
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
