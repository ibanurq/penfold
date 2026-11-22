"""Menus shared by several parts of the interface."""

from gi.repository import Gio, Gtk

from penfold import config
from penfold.ui.style_selector import StyleSelector


def main_menu() -> Gio.MenuModel:
    """Return the main menu ☰ (02-interfaz, 3.3)."""
    builder = Gtk.Builder.new_from_resource(f"{config.RESOURCE_BASE_PATH}/ui/main_menu.ui")
    menu = builder.get_object("main_menu")
    assert isinstance(menu, Gio.MenuModel)
    return menu


def attach_main_menu(button: Gtk.MenuButton) -> None:
    """Give a button the main menu ☰, with the style circles at the top (D62)."""
    button.set_menu_model(main_menu())
    popover = button.get_popover()
    assert isinstance(popover, Gtk.PopoverMenu)
    popover.add_child(StyleSelector(), "style")
