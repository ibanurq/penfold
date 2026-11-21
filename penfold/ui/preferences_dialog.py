"""The Preferences dialogue (D60, D61): the author of new annotations and whether to respect a PDF's permissions.

Each row is bound to its setting, so a change is kept as soon as it is made; there is nothing to accept or cancel.
"""

from gi.repository import Adw, Gio, Gtk

from penfold import config

AUTHOR_NAME_KEY = "author-name"
RESPECT_PERMISSIONS_KEY = "respect-permissions"


@Gtk.Template(resource_path=f"{config.RESOURCE_BASE_PATH}/ui/preferences_dialog.ui")
class PenfoldPreferencesDialog(Adw.PreferencesDialog):
    """Shows Penfold's preferences and keeps every change in its settings."""

    __gtype_name__ = "PenfoldPreferencesDialog"

    author_row: Adw.EntryRow = Gtk.Template.Child()
    permissions_row: Adw.SwitchRow = Gtk.Template.Child()

    def __init__(self) -> None:
        """Create the dialogue showing the current settings."""
        super().__init__()
        self._settings = Gio.Settings(schema_id=config.APP_ID)
        self._settings.bind(AUTHOR_NAME_KEY, self.author_row, "text", Gio.SettingsBindFlags.DEFAULT)
        self._settings.bind(RESPECT_PERMISSIONS_KEY, self.permissions_row, "active", Gio.SettingsBindFlags.DEFAULT)
