"""Menus shared by several parts of the interface."""

from gi.repository import Gio, Gtk

from penfold import config


def main_menu() -> Gio.MenuModel:
    """Return the main menu ☰ (02-interfaz, 3.3)."""
    builder = Gtk.Builder.new_from_resource(f"{config.RESOURCE_BASE_PATH}/ui/main_menu.ui")
    menu = builder.get_object("main_menu")
    assert isinstance(menu, Gio.MenuModel)
    return menu
