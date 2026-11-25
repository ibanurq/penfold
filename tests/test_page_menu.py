"""The menu of the pages selected in the Pages view: a right click, the Menu key and Rotate 180° (D74)."""

from pathlib import Path
from typing import TYPE_CHECKING

from gi.repository import Gdk, Gtk

from tests.gtk_helpers import process_pending_events, wait_until
from tests.sample_pdfs import make_pdf
from tests.test_page_editing import enabled, select, window
from tests.test_sidebar import open_and_wait

if TYPE_CHECKING:
    from penfold.application import PenfoldApplication
    from penfold.ui.sidebar.pages_view import PageCell
    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]


def cell(window: "PenfoldWindow", page: int) -> "PageCell":
    pages = window.pages_view
    wait_until(lambda: page in pages._cells and pages._cells[page].get_mapped())
    return pages._cells[page]


def right_click(window: "PenfoldWindow", page: int) -> Gtk.PopoverMenu:
    """Right-click the middle of a page's thumbnail, and return the menu it opens."""
    thumbnail = cell(window, page)
    window.pages_view._ask_for_menu(thumbnail, thumbnail.get_width() / 2, thumbnail.get_height() / 2)
    menu = window.pages_view.menu
    assert menu is not None
    wait_until(menu.get_mapped)
    return menu


def close(menu: Gtk.PopoverMenu) -> None:
    menu.popdown()
    process_pending_events()


def labels(model: object) -> list[str]:
    from gi.repository import Gio

    assert isinstance(model, Gio.MenuModel)
    found = []
    for index in range(model.get_n_items()):
        section = model.get_item_link(index, "section")
        assert section is not None
        for item in range(section.get_n_items()):
            label = section.get_item_attribute_value(item, "label", None)
            if label is not None:
                found.append(label.get_string())
    return found


def test_the_menu_has_the_three_turns_extract_and_delete() -> None:
    from penfold.ui.sidebar.pages_view import pages_menu_model

    assert labels(pages_menu_model()) == ["Rotate _Left", "Rotate _Right", "Rotate _180°", "_Extract…", "_Delete"]


def test_a_right_click_on_a_page_not_selected_selects_it_alone(window: "PenfoldWindow") -> None:
    select(window, 0, 2)
    menu = right_click(window, 1)
    assert window.pages_view.selected_pages() == [1]
    assert (menu.get_has_arrow(), menu.get_parent()) == (False, window.pages_view)
    close(menu)
    wait_until(lambda: window.pages_view.menu is None and menu.get_parent() is None)


def test_a_right_click_on_a_page_selected_keeps_the_selection(window: "PenfoldWindow") -> None:
    select(window, 0, 1, 4)
    close(right_click(window, 1))
    assert window.pages_view.selected_pages() == [0, 1, 4]


def test_rotate_180_turns_the_pages_selected_and_is_undone(window: "PenfoldWindow") -> None:
    document = window.document
    assert document is not None
    select(window, 1, 3)
    assert enabled(window, "rotate-pages-180")
    window.activate_action("win.rotate-pages-180", None)
    assert [page.rotation for page in document.pages] == [0, 180, 0, 180, 0]
    assert window.pages_view.selected_pages() == [1, 3]
    window.activate_action("win.undo", None)
    assert [page.rotation for page in document.pages] == [0] * 5


def test_rotate_180_needs_pages_selected(window: "PenfoldWindow") -> None:
    assert not enabled(window, "rotate-pages-180")


def test_the_menu_key_opens_the_menu_of_the_selection(window: "PenfoldWindow") -> None:
    pages = window.pages_view
    cell(window, 1)
    select(window, 1, 4)
    assert not pages._on_key_pressed(Gtk.EventControllerKey(), Gdk.KEY_F10, 0, Gdk.ModifierType(0))
    assert pages._on_key_pressed(Gtk.EventControllerKey(), Gdk.KEY_F10, 0, Gdk.ModifierType.SHIFT_MASK)
    menu = pages.menu
    assert menu is not None
    assert pages.selected_pages() == [1, 4]
    close(menu)
    assert pages._on_key_pressed(Gtk.EventControllerKey(), Gdk.KEY_Menu, 0, Gdk.ModifierType(0))
    assert pages.menu is not None
    close(pages.menu)


def test_the_menu_key_does_nothing_without_a_selection(window: "PenfoldWindow") -> None:
    assert not window.pages_view._on_key_pressed(Gtk.EventControllerKey(), Gdk.KEY_Menu, 0, Gdk.ModifierType(0))
    assert window.pages_view.menu is None


def test_a_pdf_that_denies_assembling_shows_the_menu_greyed_out(
    application: "PenfoldApplication", tmp_path: Path
) -> None:
    from penfold.ui.window import PenfoldWindow

    new_window = PenfoldWindow(application)
    new_window.set_default_size(1100, 750)
    new_window.present()
    open_and_wait(new_window, make_pdf(tmp_path / "locked.pdf", page_count=3, passwords=("owner", "")))
    dialog = new_window.get_visible_dialog()
    if dialog is not None:
        dialog.force_close()
    close(right_click(new_window, 1))
    assert new_window.pages_view.selected_pages() == [1]
    for name in ("rotate-pages-left", "rotate-pages-right", "rotate-pages-180", "extract-pages", "delete-pages"):
        assert not enabled(new_window, name)
    new_window.destroy()
    process_pending_events()


def test_closing_the_menu_gives_the_focus_back_to_the_thumbnails(window: "PenfoldWindow") -> None:
    """Otherwise GTK gives it to another widget, and the Menu key does not reach the thumbnails again."""
    pages = window.pages_view
    select(window, 1)
    item = cell(window, 1).get_parent()
    assert item is not None
    item.grab_focus()
    assert pages.has_focus_inside()
    assert pages._on_key_pressed(Gtk.EventControllerKey(), Gdk.KEY_Menu, 0, Gdk.ModifierType(0))
    menu = pages.menu
    assert menu is not None
    wait_until(menu.get_mapped)
    close(menu)
    wait_until(lambda: menu.get_parent() is None)
    assert pages.has_focus_inside()


def test_the_menu_key_opens_the_menu_wherever_the_focus_is(window: "PenfoldWindow") -> None:
    """A click on a thumbnail leaves the focus in the document; the key acts on the view shown, as Delete."""
    from penfold.ui.sidebar import sidebar as sidebar_views

    pages = window.pages_view
    cell(window, 1)
    select(window, 1)
    window.document_view.grab_focus()
    assert window._on_menu_key(window, None)
    menu = pages.menu
    assert menu is not None
    wait_until(menu.get_mapped)
    close(menu)
    wait_until(lambda: menu.get_parent() is None)
    assert window.document_view.has_focus()  # Back where it was.
    window.sidebar.show_view(sidebar_views.ANNOTATIONS)
    assert not window._on_menu_key(window, None)
    window.sidebar.show_view(sidebar_views.PAGES)
    window.split_view.set_show_sidebar(False)
    assert not window._on_menu_key(window, None)
