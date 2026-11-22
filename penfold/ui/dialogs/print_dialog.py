"""The "Print" dialogue (D57, D64): which groups of annotations are printed, before the system's print dialogue.

The four groups are on by default. Continue closes it and emits "print-requested" with the groups left out; Cancel
or Esc print nothing. Form values are always printed.
"""

from typing import ClassVar

from gi.repository import Adw, GObject, Gtk

from penfold import config
from penfold.document.annotations import AnnotationGroup


@Gtk.Template(resource_path=f"{config.RESOURCE_BASE_PATH}/ui/dialogs/print_dialog.ui")
class PenfoldPrintDialog(Adw.Dialog):
    """Asks which annotations to print; "print-requested" is emitted with a frozenset of the groups left out."""

    __gtype_name__ = "PenfoldPrintDialog"
    __gsignals__: ClassVar = {
        "print-requested": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
    }

    continue_button: Gtk.Button = Gtk.Template.Child()
    text_markups_row: Adw.SwitchRow = Gtk.Template.Child()
    shapes_row: Adw.SwitchRow = Gtk.Template.Child()
    text_elements_row: Adw.SwitchRow = Gtk.Template.Child()
    others_row: Adw.SwitchRow = Gtk.Template.Child()

    def left_out(self) -> frozenset[AnnotationGroup]:
        """The groups whose switch is off."""
        rows = {
            AnnotationGroup.TEXT_MARKUPS: self.text_markups_row,
            AnnotationGroup.SHAPES: self.shapes_row,
            AnnotationGroup.TEXT_ELEMENTS: self.text_elements_row,
            AnnotationGroup.OTHERS: self.others_row,
        }
        return frozenset(group for group, row in rows.items() if not row.get_active())

    @Gtk.Template.Callback()
    def _on_cancel_clicked(self, _button: Gtk.Button) -> None:
        self.close()

    @Gtk.Template.Callback()
    def _on_continue_clicked(self, _button: Gtk.Button) -> None:
        self.emit("print-requested", self.left_out())
        self.close()
