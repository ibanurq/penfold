"""The "Print" dialogue (D57): which groups of annotations are printed, before the system's print dialogue.

The three groups are on by default. Continue closes it and emits "print-requested" with the groups left out; Cancel
or Esc print nothing. Form values and annotations of no group are always printed.
"""

from typing import ClassVar

from gi.repository import Adw, GObject, Gtk

from penfold import config
from penfold.document.annotations import PrintGroup


@Gtk.Template(resource_path=f"{config.RESOURCE_BASE_PATH}/ui/dialogs/print_dialog.ui")
class PenfoldPrintDialog(Adw.Dialog):
    """Asks which annotations to print; "print-requested" is emitted with a frozenset of the PrintGroup left out."""

    __gtype_name__ = "PenfoldPrintDialog"
    __gsignals__: ClassVar = {
        "print-requested": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
    }

    continue_button: Gtk.Button = Gtk.Template.Child()
    text_markups_row: Adw.SwitchRow = Gtk.Template.Child()
    shapes_row: Adw.SwitchRow = Gtk.Template.Child()
    text_elements_row: Adw.SwitchRow = Gtk.Template.Child()

    def left_out(self) -> frozenset[PrintGroup]:
        """The groups whose switch is off."""
        rows = {
            PrintGroup.TEXT_MARKUPS: self.text_markups_row,
            PrintGroup.SHAPES: self.shapes_row,
            PrintGroup.TEXT_ELEMENTS: self.text_elements_row,
        }
        return frozenset(group for group, row in rows.items() if not row.get_active())

    @Gtk.Template.Callback()
    def _on_cancel_clicked(self, _button: Gtk.Button) -> None:
        self.close()

    @Gtk.Template.Callback()
    def _on_continue_clicked(self, _button: Gtk.Button) -> None:
        self.emit("print-requested", self.left_out())
        self.close()
