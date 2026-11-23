"""The pieces of the context menus of annotations, pages and bookmarks (D72, D74).

They open without an arrow, from the pointer to its right, and are one section with separators of their own between
the groups: GTK measures a menu with a custom item and several sections too short, and the menu then scrolls. A row
of colour circles is a custom item too.
"""

from collections.abc import Iterable, Mapping

from gi.repository import Gdk, Gio, GLib, Gtk

from penfold.ui.palette import color_circle

# The name of the custom items that separate groups of items, and of the row of colours.
SEPARATOR = "separator"
COLORS = "colors"


def custom_item(name: str) -> Gio.MenuItem:
    """A place in the menu for a widget of the popover's own (given to context_menu with this name)."""
    item = Gio.MenuItem()
    item.set_attribute_value("custom", GLib.Variant.new_string(name))
    return item


def separator() -> Gtk.Widget:
    """A separator between groups of items, as those between sections."""
    return Gtk.Separator(css_classes=["context-menu-separator"])


def color_row(colors: Iterable[str], action_name: str) -> Gtk.Widget:
    """Colour circles bound to a text action with a state (#rrggbb), and a separator below, as a section's."""
    row = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER, homogeneous=True)
    row.add_css_class("context-menu-colors")
    for value in colors:
        row.append(color_circle(value, action_name))
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.append(row)
    box.append(separator())
    return box


def context_menu(
    model: Gio.MenuModel, parent: Gtk.Widget, x: float, y: float, custom: Mapping[str, Gtk.Widget]
) -> Gtk.PopoverMenu:
    """A context menu at a point of a widget, with the widgets of its custom items; popup() shows it.

    It has no arrow and opens from the pointer to its right, as context menus do. Whoever opens it takes it away
    from its parent (unparent) once it has closed.
    """
    menu = Gtk.PopoverMenu.new_from_model(model)
    for name, widget in custom.items():
        menu.add_child(widget, name)
    menu.set_parent(parent)
    menu.set_has_arrow(False)
    menu.set_halign(Gtk.Align.START)
    place = Gdk.Rectangle()
    place.x, place.y, place.width, place.height = round(x), round(y), 1, 1
    menu.set_pointing_to(place)
    return menu
