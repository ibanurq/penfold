"""Smoke tests of the interface: the window opens and the actions are there (03-arquitectura, 8)."""

from typing import TYPE_CHECKING

from gi.repository import Adw

from tests.gtk_helpers import process_pending_events

if TYPE_CHECKING:
    from penfold.application import PenfoldApplication

WELCOME_WINDOW_SIZE = (620, 600)


def test_activating_opens_a_small_welcome_window(application: "PenfoldApplication") -> None:
    application.activate()
    process_pending_events()
    from penfold.ui.window import PenfoldWindow

    window = application.get_active_window()
    assert isinstance(window, PenfoldWindow)
    assert window.get_title() == "Penfold"
    assert window.get_default_size() == WELCOME_WINDOW_SIZE


def test_activating_again_reuses_the_window(application: "PenfoldApplication") -> None:
    application.activate()
    application.activate()
    process_pending_events()
    assert len(application.get_windows()) == 1


def test_menu_actions_are_enabled(application: "PenfoldApplication") -> None:
    for action in ("about", "shortcuts", "open", "new-window", "quit"):
        assert application.get_action_enabled(action), action


def test_shortcuts_window_shortcut(application: "PenfoldApplication") -> None:
    assert application.get_accels_for_action("app.shortcuts") == ["<Control>question"]


def test_about_dialog_opens(application: "PenfoldApplication") -> None:
    application.activate()
    application.activate_action("about", None)
    process_pending_events()
    window = application.get_active_window()
    assert isinstance(window, Adw.ApplicationWindow)
    dialog = window.get_visible_dialog()
    assert isinstance(dialog, Adw.AboutDialog)
    dialog.force_close()
