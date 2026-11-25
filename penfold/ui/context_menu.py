"""The pieces of the context menus of annotations, pages and bookmarks.

They open without an arrow, from the pointer to its right, and are one section with separators of their own between
the groups: GTK measures a menu with a custom item and several sections too short, and the menu then scrolls. A row
of colour circles is a custom item too.

In the lists of the side panel, a right click or a long press asks for the menu at the pointer, and the Menu key or
Shift+F10 at the item selected (menu_gestures, is_menu_key).
"""

from collections.abc import Callable, Iterable, Mapping

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

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
    """Colour circles bound to a text action with a state (#rrggbb), and a separator below, as a section's.

    A click on a colour changes it and closes the menu, as a click on an item does.
    """
    row = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER, homogeneous=True)
    row.add_css_class("context-menu-colors")
    for value in colors:
        circle = color_circle(value, action_name)
        circle.connect("clicked", _close_menu)
        row.append(circle)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.append(row)
    box.append(separator())
    return box


def _close_menu(circle: Gtk.Widget) -> None:
    menu = circle.get_ancestor(Gtk.Popover)
    if isinstance(menu, Gtk.Popover):
        menu.popdown()


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


def show_context_menu(
    model: Gio.MenuModel,
    parent: Gtk.Widget,
    point: tuple[float, float],
    custom: Mapping[str, Gtk.Widget] | None = None,
    *,
    focus_back: Gtk.Widget | None = None,
) -> Gtk.PopoverMenu:
    """Show a context menu at a point (x, y) of a widget; once it has closed, it is taken away from the widget.

    The keyboard focus goes back to where it was, or to focus_back (a list) if that widget has gone (an item
    deleted): otherwise GTK gives it to another widget when the menu goes away. It is left where an action of the menu
    has put it, in a dialogue.
    """
    root = parent.get_root()
    focused = root.get_focus() if isinstance(root, Gtk.Window) else None
    menu = context_menu(model, parent, *point, custom or {})
    # After the action chosen has run, and outside the popover's own signal.
    menu.connect("closed", lambda closed: GLib.idle_add(_take_away, closed, focus_back, focused))
    menu.popup()
    return menu


def _take_away(menu: Gtk.PopoverMenu, focus_back: Gtk.Widget | None, focused: Gtk.Widget | None) -> bool:
    root = menu.get_root()
    menu.unparent()
    if focus_back is not None and isinstance(root, Gtk.Window) and focus_back.get_mapped():
        focus = root.get_focus()
        dialog = isinstance(root, Adw.ApplicationWindow | Adw.Window) and root.get_visible_dialog() is not None
        if not dialog and focus is not focused:
            (focused if focused is not None and focused.get_mapped() else focus_back).grab_focus()
    return GLib.SOURCE_REMOVE


def menu_gestures(widget: Gtk.Widget, ask_for_menu: Callable[[float, float], None]) -> None:
    """Ask for a menu at the point of a widget where it is right-clicked, or long pressed on a touch screen."""
    right_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
    right_click.connect("pressed", lambda _gesture, _presses, x, y: ask_for_menu(x, y))
    widget.add_controller(right_click)
    long_press = Gtk.GestureLongPress(touch_only=True)
    long_press.connect("pressed", lambda _gesture, x, y: ask_for_menu(x, y))
    widget.add_controller(long_press)


def is_menu_key(keyval: int, state: Gdk.ModifierType) -> bool:
    """Whether a key asks for the menu of what is selected: the Menu key, or Shift+F10."""
    return keyval == Gdk.KEY_Menu or (keyval == Gdk.KEY_F10 and bool(state & Gdk.ModifierType.SHIFT_MASK))
