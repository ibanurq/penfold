"""Editing pages from the side panel: the action bar, the Delete key and the notice to undo (fase 3)."""

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from gi.repository import Adw, Gtk

from tests.gtk_helpers import process_pending_events
from tests.sample_pdfs import make_pdf
from tests.test_sidebar import open_and_wait

if TYPE_CHECKING:
    from penfold.application import PenfoldApplication
    from penfold.ui.window import PenfoldWindow


@pytest.fixture
def window(application: "PenfoldApplication", tmp_path: Path) -> Iterator["PenfoldWindow"]:
    from penfold.ui.window import PenfoldWindow

    new_window = PenfoldWindow(application)
    new_window.set_default_size(1100, 750)
    new_window.present()
    open_and_wait(new_window, make_pdf(tmp_path / "five.pdf", page_count=5))
    yield new_window
    new_window.destroy()
    process_pending_events()


def select(window: "PenfoldWindow", *positions: int) -> None:
    selected = Gtk.Bitset.new_empty()
    for position in positions:
        selected.add(position)
    pages = window.pages_view
    pages.selection.set_selection(selected, Gtk.Bitset.new_range(0, pages.pages.get_n_items()))


def enabled(window: "PenfoldWindow", name: str) -> bool:
    action = window.lookup_action(name)
    assert action is not None
    return bool(action.get_enabled())


def test_the_bar_appears_with_pages_selected(window: "PenfoldWindow") -> None:
    pages = window.pages_view
    assert not pages.action_bar.get_revealed()
    assert not enabled(window, "rotate-pages-left")
    select(window, 1, 3)
    assert pages.action_bar.get_revealed()
    assert pages.selection_label.get_label() == "2 selected"
    assert enabled(window, "rotate-pages-left")
    assert enabled(window, "delete-pages")


def test_every_page_cannot_be_deleted(window: "PenfoldWindow") -> None:
    select(window, 0, 1, 2, 3, 4)
    assert enabled(window, "rotate-pages-right")
    assert not enabled(window, "delete-pages")


def test_turning_keeps_the_selection(window: "PenfoldWindow") -> None:
    document = window.document
    assert document is not None
    select(window, 1, 3)
    window.activate_action("win.rotate-pages-right", None)
    window.activate_action("win.rotate-pages-right", None)
    window.activate_action("win.rotate-pages-left", None)
    assert [page.rotation for page in document.pages] == [0, 90, 0, 90, 0]
    assert window.pages_view.selected_pages() == [1, 3]
    assert document.is_modified


def test_moved_pages_stay_selected(window: "PenfoldWindow") -> None:
    from penfold.document.commands.pages import MovePages

    document = window.document
    assert document is not None
    select(window, 3)
    document.execute(MovePages(document, [3], 0))
    assert window.pages_view.selected_pages() == [0]


def test_deleting_shows_a_notice_that_undoes_it(window: "PenfoldWindow", monkeypatch: pytest.MonkeyPatch) -> None:
    toasts: list[Adw.Toast] = []
    monkeypatch.setattr(window.toast_overlay, "add_toast", toasts.append)
    document = window.document
    assert document is not None
    select(window, 0, 4)
    window.activate_action("win.delete-pages", None)
    assert document.page_count == 3
    assert window.pages_view.pages.get_n_items() == 3
    assert window.pages_view.selected_pages() == []
    assert not window.pages_view.action_bar.get_revealed()
    assert toasts[0].get_title() == "2 pages deleted"
    toasts[0].emit("button-clicked")
    assert document.page_count == 5


def test_the_notice_does_not_undo_a_later_edit(window: "PenfoldWindow", monkeypatch: pytest.MonkeyPatch) -> None:
    toasts: list[Adw.Toast] = []
    monkeypatch.setattr(window.toast_overlay, "add_toast", toasts.append)
    document = window.document
    assert document is not None
    select(window, 0)
    window.activate_action("win.delete-pages", None)
    assert toasts[0].get_title() == "Page deleted"
    select(window, 0)
    window.activate_action("win.rotate-pages-right", None)
    toasts[0].emit("button-clicked")
    assert (document.page_count, document.pages[0].rotation) == (4, 90)


def test_the_delete_key_deletes_the_selected_pages(window: "PenfoldWindow") -> None:
    document = window.document
    assert document is not None
    select(window, 2)
    assert window._on_delete_key(window, None)
    assert document.page_count == 4
    assert not window._on_delete_key(window, None)  # nothing selected any more


def test_the_delete_key_belongs_to_the_view_shown(window: "PenfoldWindow") -> None:
    from penfold.ui.sidebar import sidebar as sidebar_views

    document = window.document
    assert document is not None
    select(window, 2)
    window.sidebar.show_view(sidebar_views.BOOKMARKS)
    assert not window._on_delete_key(window, None)
    assert document.page_count == 5


@pytest.mark.parametrize(("x", "expected"), [(10, 3), (49, 3), (51, 4), (90, 4)])
def test_dropping_on_a_thumbnail_puts_the_pages_on_that_side(x: float, expected: int) -> None:
    from penfold.ui.sidebar.pages_view import drop_position

    assert drop_position(3, x, 100) == expected


def test_dropped_thumbnails_move_their_pages(window: "PenfoldWindow") -> None:
    document = window.document
    assert document is not None
    select(window, 0, 1)
    window.pages_view.emit("move-requested", [0, 1], 5)
    assert [page.source_index for page in document.pages] == [2, 3, 4, 0, 1]
    assert window.pages_view.selected_pages() == [3, 4]
    window.pages_view.emit("move-requested", [3], 3)
    assert not document.can_redo
    document.undo()
    assert [page.source_index for page in document.pages] == [0, 1, 2, 3, 4]
    assert not document.can_undo


def test_changes_are_marked_and_saving_clears_the_mark(window: "PenfoldWindow") -> None:
    import pikepdf

    from tests.gtk_helpers import wait_until

    document = window.document
    assert document is not None
    assert window.get_title() == "five.pdf — Penfold"
    select(window, 0)
    window.activate_action("win.rotate-pages-right", None)
    assert window.get_title() == "• five.pdf — Penfold"
    assert window.document_header.title_widget.get_title() == "• five.pdf"
    window.activate_action("win.save", None)
    wait_until(lambda: not document.is_modified)
    assert window.get_title() == "five.pdf — Penfold"
    with pikepdf.open(document.path) as pdf:
        assert pdf.pages[0].obj.Rotate == 90
    window.activate_action("win.undo", None)
    assert window.get_title() == "• five.pdf — Penfold"


def test_saving_to_another_file_makes_it_the_document(window: "PenfoldWindow", tmp_path: Path) -> None:
    from tests.gtk_helpers import wait_until

    document = window.document
    assert document is not None
    saved: list[bool] = []
    window._write(document.save_plan(tmp_path / "copy.pdf"), saved.append)
    wait_until(lambda: bool(saved))
    assert saved == [True]
    assert window.get_title() == "copy.pdf — Penfold"


def test_a_failed_save_is_reported_and_keeps_the_changes(window: "PenfoldWindow", tmp_path: Path) -> None:
    from tests.gtk_helpers import wait_until

    document = window.document
    assert document is not None
    select(window, 0)
    window.activate_action("win.rotate-pages-right", None)
    saved: list[bool] = []
    window._write(document.save_plan(tmp_path / "missing" / "copy.pdf"), saved.append)
    wait_until(lambda: bool(saved))
    assert saved == [False]
    assert document.is_modified
    dialog = window.get_visible_dialog()
    assert isinstance(dialog, Adw.AlertDialog)
    assert dialog.get_heading() == "Could not save “copy.pdf”"
    dialog.force_close()


def test_protected_pdfs_cannot_be_saved(application: "PenfoldApplication", tmp_path: Path) -> None:
    from penfold.ui.window import PenfoldWindow

    new_window = PenfoldWindow(application)
    new_window.present()
    open_and_wait(new_window, make_pdf(tmp_path / "locked.pdf", passwords=("owner", "")))
    assert not enabled(new_window, "save")
    assert not enabled(new_window, "save-as")
    dialog = new_window.get_visible_dialog()
    if dialog is not None:
        dialog.force_close()
    new_window.destroy()
    process_pending_events()
