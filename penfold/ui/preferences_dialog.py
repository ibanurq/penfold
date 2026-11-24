"""The Preferences dialogue (D60, D61; 07-fase-12, 8 to 10): annotations, permissions and opening documents.

Each row is bound to its setting, so a change is kept as soon as it is made; there is nothing to accept or cancel.
"""

from gettext import gettext as _

from gi.repository import Adw, Gio, Gtk

from penfold import config
from penfold.document.annotations import DEFAULT_AUTHOR

AUTHOR_NAME_KEY = "author-name"
SHOW_ANNOTATION_BAR_KEY = "show-annotation-bar"
RESPECT_PERMISSIONS_KEY = "respect-permissions"
REMEMBER_POSITION_KEY = "remember-position"
OPEN_LAST_DOCUMENT_KEY = "open-last-document"
# Not shown: the path of the last document, which "Start With Last Document" opens.
LAST_DOCUMENT_KEY = "last-document"

# The author entry's icon: a pencil while it is empty, and a button that empties it once it has text (07-fase-12, 8).
EMPTY_AUTHOR_ICON = "document-edit-symbolic"
CLEAR_AUTHOR_ICON = "edit-clear-symbolic"


@Gtk.Template(resource_path=f"{config.RESOURCE_BASE_PATH}/ui/preferences_dialog.ui")
class PenfoldPreferencesDialog(Adw.PreferencesDialog):
    """Shows Penfold's preferences and keeps every change in its settings."""

    __gtype_name__ = "PenfoldPreferencesDialog"

    author_entry: Gtk.Entry = Gtk.Template.Child()
    annotation_bar_row: Adw.SwitchRow = Gtk.Template.Child()
    permissions_row: Adw.SwitchRow = Gtk.Template.Child()
    position_row: Adw.SwitchRow = Gtk.Template.Child()
    last_document_row: Adw.SwitchRow = Gtk.Template.Child()

    def __init__(self) -> None:
        """Create the dialogue showing the current settings."""
        super().__init__()
        # The hint is the name annotations really get when the entry is left empty.
        self.author_entry.set_placeholder_text(DEFAULT_AUTHOR)
        self.author_entry.connect("notify::text", self._on_author_changed)
        self.author_entry.connect("icon-press", self._on_author_icon_pressed)
        self._settings = Gio.Settings(schema_id=config.APP_ID)
        self._settings.bind(AUTHOR_NAME_KEY, self.author_entry, "text", Gio.SettingsBindFlags.DEFAULT)
        self._settings.bind(SHOW_ANNOTATION_BAR_KEY, self.annotation_bar_row, "active", Gio.SettingsBindFlags.DEFAULT)
        self._settings.bind(RESPECT_PERMISSIONS_KEY, self.permissions_row, "active", Gio.SettingsBindFlags.DEFAULT)
        self._settings.bind(REMEMBER_POSITION_KEY, self.position_row, "active", Gio.SettingsBindFlags.DEFAULT)
        self._settings.bind(OPEN_LAST_DOCUMENT_KEY, self.last_document_row, "active", Gio.SettingsBindFlags.DEFAULT)
        self._on_author_changed()

    def _on_author_changed(self, *_args: object) -> None:
        """Show the pencil while the author is empty, and the button that empties it otherwise."""
        has_text = bool(self.author_entry.get_text())
        position = Gtk.EntryIconPosition.SECONDARY
        self.author_entry.set_icon_from_icon_name(position, CLEAR_AUTHOR_ICON if has_text else EMPTY_AUTHOR_ICON)
        self.author_entry.set_icon_activatable(position, has_text)
        self.author_entry.set_icon_tooltip_text(position, _("Clear") if has_text else None)

    def _on_author_icon_pressed(self, entry: Gtk.Entry, _position: Gtk.EntryIconPosition) -> None:
        """Empty the author when its clear button is pressed (the pencil is not a button)."""
        entry.set_text("")
