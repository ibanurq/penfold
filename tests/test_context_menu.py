"""The pieces shared by the context menus of annotations, pages and bookmarks (D72, D74)."""

from collections.abc import Iterator

import pytest
from gi.repository import Gio, GLib, Gtk

from penfold.ui.context_menu import COLORS, SEPARATOR, color_row, context_menu, custom_item, separator
from penfold.ui.palette import COLORS as PALETTE
from tests.gtk_helpers import wait_until, wait_until_stable


@pytest.fixture
def parent() -> Iterator[Gtk.Box]:
    box = Gtk.Box(width_request=600, height_request=500)
    window = Gtk.Window(child=box)
    window.present()
    yield box
    window.destroy()


def children(widget: Gtk.Widget) -> list[Gtk.Widget]:
    found = []
    child = widget.get_first_child()
    while child is not None:
        found.append(child)
        child = child.get_next_sibling()
    return found


def menu_model() -> Gio.Menu:
    """One section: the colours, two items, a separator and Delete."""
    items = Gio.Menu()
    items.append_item(custom_item(COLORS))
    items.append("First", "test.first")
    items.append("Second", "test.second")
    items.append_item(custom_item(SEPARATOR))
    items.append("Delete", "test.delete")
    model = Gio.Menu()
    model.append_section(None, items)
    return model


def test_a_custom_item_names_its_widget() -> None:
    item = custom_item("colors")
    value = item.get_attribute_value("custom", GLib.VariantType.new("s"))
    assert value is not None
    assert value.get_string() == "colors"


def test_the_colour_row_has_a_circle_for_each_colour_and_a_separator_below() -> None:
    box = color_row(PALETTE, "win.bookmark-color")
    row, line = children(box)
    circles = [circle for circle in children(row) if isinstance(circle, Gtk.ToggleButton)]
    assert len(circles) == len(children(row))
    targets = [circle.get_action_target_value() for circle in circles]
    assert [target.get_string() if target is not None else None for target in targets] == list(PALETTE)
    assert {circle.get_action_name() for circle in circles} == {"win.bookmark-color"}
    assert isinstance(line, Gtk.Separator)
    assert line.has_css_class("context-menu-separator")
    assert separator().has_css_class("context-menu-separator")


def test_the_menu_opens_from_the_pointer_without_an_arrow(parent: Gtk.Box) -> None:
    menu = context_menu(menu_model(), parent, 120.4, 80.6, {})
    assert menu.get_parent() is parent
    assert (menu.get_has_arrow(), menu.get_halign()) == (False, Gtk.Align.START)
    found, place = menu.get_pointing_to()
    assert found
    assert (place.x, place.y, place.width, place.height) == (120, 81, 1, 1)
    menu.unparent()


def test_the_menu_with_colours_and_separators_does_not_scroll(parent: Gtk.Box) -> None:
    """GTK measures a menu with custom items in several sections too short (9.4): one section shows it whole."""
    custom = {COLORS: color_row(PALETTE, "win.bookmark-color"), SEPARATOR: separator()}
    menu = context_menu(menu_model(), parent, 20, 20, custom)
    menu.popup()
    wait_until(menu.get_mapped)
    scrolled = [widget for widget in all_widgets(menu) if isinstance(widget, Gtk.ScrolledWindow)]
    assert scrolled
    adjustment = scrolled[0].get_vadjustment()
    # GTK may measure the menu again in the next frames (after its style, for example).
    wait_until_stable(lambda: (adjustment.get_upper(), adjustment.get_page_size()))
    assert adjustment.get_upper() == pytest.approx(adjustment.get_page_size())
    menu.popdown()
    menu.unparent()


def all_widgets(widget: Gtk.Widget) -> Iterator[Gtk.Widget]:
    yield widget
    for child in children(widget):
        yield from all_widgets(child)
