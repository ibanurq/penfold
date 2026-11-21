"""The "Save As" dialogue of a document with a form (I6): whether to flatten it, before choosing the file.

Flattening is off by default, as in 0.6. Continue closes it and emits "continue-requested" with the choice; Cancel or
Esc save nothing.
"""

from typing import ClassVar

from gi.repository import Adw, GObject, Gtk

from penfold import config


@Gtk.Template(resource_path=f"{config.RESOURCE_BASE_PATH}/ui/dialogs/save_as_dialog.ui")
class PenfoldSaveAsDialog(Adw.Dialog):
    """Asks whether to flatten the form; "continue-requested" is emitted with True to flatten it."""

    __gtype_name__ = "PenfoldSaveAsDialog"
    __gsignals__: ClassVar = {
        "continue-requested": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
    }

    continue_button: Gtk.Button = Gtk.Template.Child()
    flatten_row: Adw.SwitchRow = Gtk.Template.Child()

    @Gtk.Template.Callback()
    def _on_cancel_clicked(self, _button: Gtk.Button) -> None:
        self.close()

    @Gtk.Template.Callback()
    def _on_continue_clicked(self, _button: Gtk.Button) -> None:
        self.emit("continue-requested", self.flatten_row.get_active())
        self.close()
