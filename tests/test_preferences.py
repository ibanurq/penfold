"""The Preferences dialogue (D60, D61): where it opens from, and every change kept at once."""

from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from gi.repository import Adw, Gio, Gtk

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
    for key in ("author-name", "show-annotation-bar", "respect-permissions", "remember-position"):
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
            if action is not None:  # the style circles have none (D62)
                actions.append(action.get_string())
    assert actions[actions.index("app.preferences") + 1] == "app.shortcuts"


def test_the_keyboard_shortcuts_list_preferences(application: "PenfoldApplication") -> None:
    from penfold.ui.shortcuts_dialog import shortcut_groups

    annotations, general = shortcut_groups(application)[:2]
    # Annotations first, as in 0.6 (L2): H, U and Esc.
    assert [shortcut.accelerator for shortcut in annotations.shortcuts] == ["h", "u", "Escape"]
    assert ("Open the preferences", "<Control>comma") in [
        (shortcut.description, shortcut.accelerator) for shortcut in general.shortcuts
    ]


def test_by_default_there_is_no_author_and_permissions_are_respected(
    dialog: "PenfoldPreferencesDialog", settings: Gio.Settings
) -> None:
    assert (settings.get_string("author-name"), settings.get_boolean("respect-permissions")) == ("", True)
    assert (dialog.author_entry.get_text(), dialog.permissions_row.get_active()) == ("", True)


def test_changes_are_kept_at_once(dialog: "PenfoldPreferencesDialog", settings: Gio.Settings) -> None:
    dialog.author_entry.set_text("Ana")
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
    assert (dialog.author_entry.get_text(), dialog.permissions_row.get_active()) == ("Ana", False)


def test_the_empty_author_hints_at_the_name_annotations_get(dialog: "PenfoldPreferencesDialog") -> None:
    from penfold.document.annotations import DEFAULT_AUTHOR

    assert dialog.author_entry.get_placeholder_text() == DEFAULT_AUTHOR


def test_the_author_shows_a_pencil_while_empty_and_a_clear_button_once_written(
    dialog: "PenfoldPreferencesDialog",
    settings: Gio.Settings,  # noqa: ARG001 (puts the author back afterwards)
) -> None:
    entry, icon = dialog.author_entry, Gtk.EntryIconPosition.SECONDARY

    def shown() -> tuple[str | None, bool]:
        return entry.get_icon_name(icon), entry.get_icon_activatable(icon)

    assert shown() == ("document-edit-symbolic", False)
    entry.set_text("Ana")
    assert shown() == ("edit-clear-symbolic", True)


def test_the_clear_button_empties_the_author(dialog: "PenfoldPreferencesDialog", settings: Gio.Settings) -> None:
    dialog.author_entry.set_text("Ana")
    dialog.author_entry.emit("icon-press", Gtk.EntryIconPosition.SECONDARY)
    assert (settings.get_string("author-name"), dialog.author_entry.get_icon_name(Gtk.EntryIconPosition.SECONDARY)) == (
        "",
        "document-edit-symbolic",
    )


def test_the_permissions_option_has_no_explanation(dialog: "PenfoldPreferencesDialog") -> None:
    assert not dialog.permissions_row.get_subtitle()


def test_the_annotation_bar_option_is_off_by_default_and_kept_at_once(
    dialog: "PenfoldPreferencesDialog", settings: Gio.Settings
) -> None:
    assert dialog.annotation_bar_row.get_active() is False
    dialog.annotation_bar_row.set_active(True)
    assert settings.get_boolean("show-annotation-bar")


def test_remembering_the_position_is_on_by_default_and_kept_at_once(
    dialog: "PenfoldPreferencesDialog", settings: Gio.Settings
) -> None:
    assert dialog.position_row.get_active() is True
    dialog.position_row.set_active(False)
    assert settings.get_boolean("remember-position") is False


def test_the_last_document_option_follows_its_setting(
    dialog: "PenfoldPreferencesDialog",
    settings: Gio.Settings,  # noqa: ARG001 (puts it back afterwards)
) -> None:
    penfold_settings = Gio.Settings(schema_id=config.APP_ID)
    dialog.last_document_row.set_active(True)
    assert penfold_settings.get_boolean("open-last-document")
    dialog.last_document_row.set_active(False)  # Off, as in all tests (conftest).
    assert not penfold_settings.get_boolean("open-last-document")
