"""The style of the interface (D62): three circles in the main menu, kept and applied to every window at once."""

from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from gi.repository import Adw, Gio, GLib, Gtk

from penfold import config
from tests.gtk_helpers import process_pending_events

if TYPE_CHECKING:
    from penfold.application import PenfoldApplication
    from penfold.ui.window import PenfoldWindow


@pytest.fixture
def settings() -> Iterator[Gio.Settings]:
    """Return Penfold's settings, with the style put back to its default afterwards."""
    penfold_settings = Gio.Settings(schema_id=config.APP_ID)
    yield penfold_settings
    penfold_settings.reset("style")
    process_pending_events()


@pytest.fixture
def window(application: "PenfoldApplication") -> "PenfoldWindow":
    """Open Penfold's window."""
    application.activate()
    process_pending_events()
    active = application.get_active_window()
    from penfold.ui.window import PenfoldWindow

    assert isinstance(active, PenfoldWindow)
    return active


def circles(button: Gtk.MenuButton) -> list[Gtk.ToggleButton]:
    """Return the style circles of the menu of a button."""
    from penfold.ui.style_selector import StyleSelector

    popover = button.get_popover()
    assert popover is not None
    pending: list[Gtk.Widget] = [popover]
    while pending:
        widget = pending.pop()
        if isinstance(widget, StyleSelector):
            return [child for child in widget if isinstance(child, Gtk.ToggleButton)]
        pending += list(widget)
    return []


def chosen(button: Gtk.MenuButton) -> list[bool]:
    return [circle.get_active() for circle in circles(button)]


def test_by_default_the_style_follows_the_system(application: "PenfoldApplication", settings: Gio.Settings) -> None:
    assert settings.get_string("style") == "system"
    assert application.get_action_state("style") == GLib.Variant.new_string("system")
    assert Adw.StyleManager.get_default().get_color_scheme() == Adw.ColorScheme.DEFAULT


def test_every_main_menu_has_the_three_circles_with_the_system_chosen(
    window: "PenfoldWindow",
    settings: Gio.Settings,  # noqa: ARG001 (the default style)
) -> None:
    buttons = (window.welcome_menu_button, window.sidebar.main_menu_button, window.document_header.main_menu_button)
    for button in buttons:
        assert [circle.get_tooltip_text() for circle in circles(button)] == [
            "Follow System Style",
            "Light Style",
            "Dark Style",
        ]
        assert chosen(button) == [True, False, False]


def test_a_circle_applies_its_style_at_once_and_keeps_it(window: "PenfoldWindow", settings: Gio.Settings) -> None:
    circles(window.welcome_menu_button)[2].emit("clicked")
    process_pending_events()
    assert settings.get_string("style") == "dark"
    assert Adw.StyleManager.get_default().get_color_scheme() == Adw.ColorScheme.FORCE_DARK
    # The other menus show the same choice.
    assert chosen(window.sidebar.main_menu_button) == [False, False, True]
    circles(window.sidebar.main_menu_button)[1].emit("clicked")
    process_pending_events()
    assert settings.get_string("style") == "light"
    assert Adw.StyleManager.get_default().get_color_scheme() == Adw.ColorScheme.FORCE_LIGHT


def test_back_to_the_system_style(window: "PenfoldWindow", settings: Gio.Settings) -> None:
    settings.set_string("style", "dark")
    process_pending_events()
    circles(window.welcome_menu_button)[0].emit("clicked")
    process_pending_events()
    assert settings.get_string("style") == "system"
    assert Adw.StyleManager.get_default().get_color_scheme() == Adw.ColorScheme.DEFAULT
