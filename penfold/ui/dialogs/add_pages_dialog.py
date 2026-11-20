"""The "Add Pages" dialogue (02-interfaz, 6.1 and 8; E4 to E6): the pages of a PDF or a blank page, and where.

As in 0.6, choosing a file, a size or a page number also chooses the option it belongs to. With pages selected, it
proposes to add the new ones after the last of them; otherwise at the end (D48).
"""

from dataclasses import dataclass
from gettext import gettext as _
from pathlib import Path
from typing import ClassVar

from gi.repository import Adw, Gio, GLib, GObject, Gtk

from penfold import config
from penfold.document.pages import PaperSize
from penfold.ui.file_dialogs import pdf_file_dialog


@dataclass(frozen=True)
class PagesToAdd:
    """What the user chose: a PDF or a blank page of a size, and the position of the page they go before."""

    source: Path | PaperSize
    position: int


def size_name(size: PaperSize) -> str:
    """The name of a paper size, as the list shows it."""
    return _("Letter") if size is PaperSize.LETTER else size.name


@Gtk.Template(resource_path=f"{config.RESOURCE_BASE_PATH}/ui/dialogs/add_pages_dialog.ui")
class PenfoldAddPagesDialog(Adw.Dialog):
    """Asks what to add and where; "add-requested" is emitted with a PagesToAdd when Add is pressed."""

    __gtype_name__ = "PenfoldAddPagesDialog"
    __gsignals__: ClassVar = {
        "add-requested": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
    }

    add_button: Gtk.Button = Gtk.Template.Child()
    pdf_row: Adw.ActionRow = Gtk.Template.Child()
    pdf_check: Gtk.CheckButton = Gtk.Template.Child()
    blank_check: Gtk.CheckButton = Gtk.Template.Child()
    size_dropdown: Gtk.DropDown = Gtk.Template.Child()
    start_check: Gtk.CheckButton = Gtk.Template.Child()
    end_check: Gtk.CheckButton = Gtk.Template.Child()
    after_check: Gtk.CheckButton = Gtk.Template.Child()
    page_spin: Gtk.SpinButton = Gtk.Template.Child()

    def __init__(self, page_count: int, current_page: int, selected_pages: list[int]) -> None:
        """Prepare the dialogue for a document of page_count pages; pages are positions from 0."""
        super().__init__()
        self._page_count = page_count
        self._file: Path | None = None
        # Filling in the dialogue must not choose options as the user's changes do.
        self._ready = False
        self.size_dropdown.set_model(Gtk.StringList.new([size_name(size) for size in PaperSize]))
        self.page_spin.get_adjustment().set_upper(page_count)
        if selected_pages:
            self.page_spin.set_value(max(selected_pages) + 1)
            self.after_check.set_active(True)
        else:
            self.page_spin.set_value(current_page + 1)
            self.end_check.set_active(True)
        self._ready = True
        self._update_add_button()

    @property
    def choice(self) -> PagesToAdd:
        """What is chosen now."""
        source: Path | PaperSize | None = self._file
        if self.blank_check.get_active() or source is None:
            source = list(PaperSize)[self.size_dropdown.get_selected()]
        if self.start_check.get_active():
            position = 0
        elif self.after_check.get_active():
            position = self.page_spin.get_value_as_int()
        else:
            position = self._page_count
        return PagesToAdd(source, position)

    def choose_file(self, path: Path) -> None:
        """Take the PDF whose pages will be added, and choose that option."""
        self._file = path
        self.pdf_row.set_subtitle(GLib.markup_escape_text(path.name))
        self.pdf_check.set_active(True)
        self._update_add_button()

    def _update_add_button(self) -> None:
        """Add needs a file when the pages come from a PDF."""
        self.add_button.set_sensitive(self.blank_check.get_active() or self._file is not None)

    @Gtk.Template.Callback()
    def _on_cancel_clicked(self, _button: Gtk.Button) -> None:
        self.close()

    @Gtk.Template.Callback()
    def _on_add_clicked(self, _button: Gtk.Button) -> None:
        self.emit("add-requested", self.choice)
        self.close()

    @Gtk.Template.Callback()
    def _on_choose_clicked(self, _button: Gtk.Button) -> None:
        root = self.get_root()
        parent = root if isinstance(root, Gtk.Window) else None
        pdf_file_dialog(_("Choose PDF")).open(parent, None, self._on_file_chosen)

    def _on_file_chosen(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return  # Cancelled.
        path = file.get_path() if file is not None else None
        if path is not None:
            self.choose_file(Path(path))

    @Gtk.Template.Callback()
    def _on_choice_toggled(self, _button: Gtk.CheckButton) -> None:
        self._update_add_button()

    @Gtk.Template.Callback()
    def _on_size_changed(self, _dropdown: Gtk.DropDown, _property: GObject.ParamSpec) -> None:
        if self._ready:
            self.blank_check.set_active(True)

    @Gtk.Template.Callback()
    def _on_page_changed(self, _spin: Gtk.SpinButton) -> None:
        if self._ready:
            self.after_check.set_active(True)
