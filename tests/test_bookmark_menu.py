"""The menu of the bookmarks selected in the Bookmarks view: a right click, the Menu key and F2 (D74)."""

from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
from gi.repository import Adw, Gdk, GLib, Gtk

from tests.gtk_helpers import process_pending_events, wait_until
from tests.sample_pdfs import allowing, make_pdf
from tests.test_bookmark_editing import rows, select, selected_titles, window
from tests.test_bookmarks import add_outline
from tests.test_page_editing import enabled
from tests.test_page_menu import close, labels
from tests.test_sidebar import open_and_wait

if TYPE_CHECKING:
    from penfold.application import PenfoldApplication
    from penfold.ui.sidebar.bookmarks_view import BookmarkRow
    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]


def row(window: "PenfoldWindow", position: int) -> "BookmarkRow":
    """The row shown at a position of the list."""
    view = window.bookmarks_view

    def shown() -> "BookmarkRow | None":
        for bookmark_row in view._rows.values():
            if bookmark_row.get_mapped() and position_of(window, bookmark_row) == position:
                return bookmark_row
        return None

    wait_until(lambda: shown() is not None)
    found = shown()
    assert found is not None
    return found


def position_of(window: "PenfoldWindow", bookmark_row: "BookmarkRow") -> int:
    from penfold.ui.sidebar.bookmarks_view import BookmarkItem

    tree = window.bookmarks_view.tree
    for index in range(tree.get_n_items()):
        tree_row = tree.get_row(index)
        item = tree_row.get_item() if tree_row is not None else None
        if isinstance(item, BookmarkItem) and item.bookmark is bookmark_row.bookmark:
            return index
    return -1


def right_click(window: "PenfoldWindow", position: int) -> Gtk.PopoverMenu:
    """Right-click the middle of the row at a position of the list, and return the menu it opens."""
    bookmark_row = row(window, position)
    window.bookmarks_view._ask_for_menu(
        bookmark_row, position, bookmark_row.get_width() / 2, bookmark_row.get_height() / 2
    )
    menu = window.bookmarks_view.menu
    assert menu is not None
    wait_until(menu.get_mapped)
    return menu


def state(window: "PenfoldWindow", name: str) -> object:
    action = window.lookup_action(name)
    assert action is not None
    value = action.get_state()
    assert value is not None
    return value.unpack()


def test_the_menu_has_the_formats_and_the_edits_in_order() -> None:
    from penfold.ui.sidebar.bookmarks_view import bookmarks_menu_model

    model = bookmarks_menu_model()
    assert labels(model) == [
        "_Bold",
        "_Italic",
        "_Clear Formatting",
        "_Rename…",
        "_Point to the Current Page",
        "Increase Inden_t",
        "Decrea_se Indent",
        "_Delete",
    ]
    section = model.get_item_link(0, "section")
    assert section is not None
    accel = section.get_item_attribute_value(4, "accel", GLib.VariantType.new("s"))
    assert accel is not None
    assert accel.get_string() == "F2"


def test_a_right_click_on_a_bookmark_not_selected_selects_it_alone(window: "PenfoldWindow") -> None:
    select(window, 0, 1)
    menu = right_click(window, 3)
    assert selected_titles(window) == ["Broken"]
    assert (menu.get_has_arrow(), menu.get_parent()) == (False, window.bookmarks_view)
    close(menu)
    wait_until(lambda: window.bookmarks_view.menu is None and menu.get_parent() is None)


def test_a_right_click_on_a_bookmark_selected_keeps_the_selection(window: "PenfoldWindow") -> None:
    select(window, 0, 2)
    close(right_click(window, 2))
    assert selected_titles(window) == ["Cover", "1.1 Scope"]


def test_the_menu_shows_the_style_and_colour_of_the_selection(window: "PenfoldWindow") -> None:
    select(window, 1)
    window.activate_action("win.bookmark-bold", None)
    window.activate_action("win.bookmark-color", GLib.Variant.new_string("#606971"))
    menu = right_click(window, 1)
    # 1. Intro was italic already.
    assert (state(window, "bookmark-bold"), state(window, "bookmark-italic")) == (True, True)
    assert state(window, "bookmark-color") == "#606971"
    close(menu)


def test_renaming_and_pointing_are_greyed_out_with_several(window: "PenfoldWindow") -> None:
    select(window, 0, 1)
    close(right_click(window, 1))
    assert not enabled(window, "rename-bookmark")
    assert not enabled(window, "point-bookmark")
    assert enabled(window, "delete-bookmarks")


def test_f2_renames_the_bookmark_selected_in_the_bookmarks_view(window: "PenfoldWindow") -> None:
    from penfold.ui.dialogs.text_question import RESPONSE_CONFIRM
    from penfold.ui.sidebar import sidebar as sidebar_views

    select(window, 2)
    window.sidebar.show_view(sidebar_views.PAGES)
    assert not window._on_rename_key(window, None)
    assert window.get_visible_dialog() is None
    window.sidebar.show_view(sidebar_views.BOOKMARKS)
    window.split_view.set_show_sidebar(False)
    assert not window._on_rename_key(window, None)
    window.split_view.set_show_sidebar(True)
    assert window._on_rename_key(window, None)
    dialog = window.get_visible_dialog()
    assert isinstance(dialog, Adw.AlertDialog)
    assert dialog.get_heading() == "Rename"
    assert not window._on_rename_key(window, None)  # Not while the dialogue is open.
    entry = dialog.get_extra_child()
    assert isinstance(entry, Gtk.Entry)
    entry.set_text("1.1 Purpose")
    dialog.emit("response", RESPONSE_CONFIRM)
    dialog.close()
    assert rows(window)[2] == "  1.1 Purpose"


def test_f2_does_nothing_with_several_selected(window: "PenfoldWindow") -> None:
    select(window, 0, 1)
    assert not window._on_rename_key(window, None)
    assert window.get_visible_dialog() is None


def test_the_menu_key_opens_the_menu_of_the_selection(window: "PenfoldWindow") -> None:
    view = window.bookmarks_view
    row(window, 1)
    select(window, 1, 3)
    assert not view._on_key_pressed(Gtk.EventControllerKey(), Gdk.KEY_F10, 0, Gdk.ModifierType(0))
    assert view._on_key_pressed(Gtk.EventControllerKey(), Gdk.KEY_F10, 0, Gdk.ModifierType.SHIFT_MASK)
    menu = view.menu
    assert menu is not None
    assert selected_titles(window) == ["1. Intro", "Broken"]
    close(menu)
    assert view._on_key_pressed(Gtk.EventControllerKey(), Gdk.KEY_Menu, 0, Gdk.ModifierType(0))
    assert view.menu is not None
    close(view.menu)


def test_the_menu_key_does_nothing_without_a_selection(window: "PenfoldWindow") -> None:
    view = window.bookmarks_view
    assert not view._on_key_pressed(Gtk.EventControllerKey(), Gdk.KEY_Menu, 0, Gdk.ModifierType(0))
    assert view.menu is None


def test_a_pdf_that_denies_assembling_shows_the_menu_greyed_out(
    application: "PenfoldApplication", tmp_path: Path
) -> None:
    from penfold.ui.sidebar import sidebar as sidebar_views
    from penfold.ui.window import PenfoldWindow

    locked = make_pdf(tmp_path / "locked.pdf", page_count=5)
    add_outline(locked)
    with pikepdf.open(locked, allow_overwriting_input=True) as pdf:
        pdf.save(locked, encryption=pikepdf.Encryption(owner="owner", user="", allow=allowing("print_highres")))
    new_window = PenfoldWindow(application)
    new_window.set_default_size(1100, 750)
    new_window.present()
    open_and_wait(new_window, locked)
    dialog = new_window.get_visible_dialog()
    if dialog is not None:
        dialog.force_close()
    new_window.sidebar.show_view(sidebar_views.BOOKMARKS)
    close(right_click(new_window, 1))
    assert selected_titles(new_window) == ["1. Intro"]
    for name in (
        "bookmark-color",
        "bookmark-bold",
        "bookmark-italic",
        "clear-bookmark-format",
        "rename-bookmark",
        "point-bookmark",
        "indent-bookmarks",
        "outdent-bookmarks",
        "delete-bookmarks",
    ):
        assert not enabled(new_window, name), name
    new_window.destroy()
    process_pending_events()


def test_the_menu_key_opens_the_menu_of_the_bookmarks_wherever_the_focus_is(window: "PenfoldWindow") -> None:
    row(window, 2)
    select(window, 2)
    window.document_view.grab_focus()
    assert window._on_menu_key(window, None)
    menu = window.bookmarks_view.menu
    assert menu is not None
    close(menu)
