"""The Preferences dialogue (D60, D61): where it opens from, and every change kept at once."""

from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from gi.repository import Adw, Gio

from penfold import config
from tests.gtk_helpers import process_pending_events

if TYPE_CHECKING:
    from penfold.application import PenfoldApplication
    from penfold.ui.preferences_dialog import PenfoldPreferencesDialog


@pytest.fixture
def settings() -> Iterator[Gio.Settings]:
    """Return Penfold's settings, put back to their defaults afterwards (they are shared by the whole session)."""
    penfold_settings = Gio.Settings(schema_id=config.APP_ID)
    yield penfold_settings
    for key in ("author-name", "respect-permissions"):
        penfold_settings.reset(key)


@pytest.fixture
def dialog(application: "PenfoldApplication") -> Iterator["PenfoldPreferencesDialog"]:
    """Open Preferences from the menu's action, over Penfold's window."""
    from penfold.ui.preferences_dialog import PenfoldPreferencesDialog

    application.activate()
    application.activate_action("preferences", None)
    process_pending_events()
    window = application.get_active_window()
    assert isinstance(window, Adw.ApplicationWindow)
    preferences = window.get_visible_dialog()
    assert isinstance(preferences, PenfoldPreferencesDialog)
    yield preferences
    preferences.force_close()


def test_preferences_open_with_ctrl_comma(application: "PenfoldApplication") -> None:
    assert application.get_accels_for_action("app.preferences") == ["<Control>comma"]


def test_preferences_come_before_the_keyboard_shortcuts_in_the_main_menu() -> None:
    from penfold.ui.menus import main_menu

    menu = main_menu()
    actions = []
    for section in range(menu.get_n_items()):
        items = menu.get_item_link(section, Gio.MENU_LINK_SECTION)
        assert items is not None
        for item in range(items.get_n_items()):
            action = items.get_item_attribute_value(item, "action")
            assert action is not None
            actions.append(action.get_string())
    assert actions[actions.index("app.preferences") + 1] == "app.shortcuts"


def test_the_keyboard_shortcuts_list_preferences(application: "PenfoldApplication") -> None:
    from penfold.ui.shortcuts_dialog import shortcut_groups

    general = shortcut_groups(application)[0]
    assert ("Open the preferences", "<Control>comma") in [
        (shortcut.description, shortcut.accelerator) for shortcut in general.shortcuts
    ]


def test_by_default_there_is_no_author_and_permissions_are_respected(
    dialog: "PenfoldPreferencesDialog", settings: Gio.Settings
) -> None:
    assert (settings.get_string("author-name"), settings.get_boolean("respect-permissions")) == ("", True)
    assert (dialog.author_row.get_text(), dialog.permissions_row.get_active()) == ("", True)


def test_changes_are_kept_at_once(dialog: "PenfoldPreferencesDialog", settings: Gio.Settings) -> None:
    dialog.author_row.set_text("Ana")
    dialog.permissions_row.set_active(False)
    assert (settings.get_string("author-name"), settings.get_boolean("respect-permissions")) == ("Ana", False)


def test_the_dialogue_shows_the_kept_settings(
    application: "PenfoldApplication",  # noqa: ARG001 (loads the interface files)
    settings: Gio.Settings,
) -> None:
    settings.set_string("author-name", "Ana")
    settings.set_boolean("respect-permissions", False)
    from penfold.ui.preferences_dialog import PenfoldPreferencesDialog

    dialog = PenfoldPreferencesDialog()
    assert (dialog.author_row.get_text(), dialog.permissions_row.get_active()) == ("Ana", False)
