"""The "Extract Pages" dialogue (02-interfaz, 6.1 and 8; E7 and E8; D51): which pages, and how.

It starts with the selected pages written as a list. A list that cannot be read is explained under it, and the
dialogue stays open until the list is right.
"""

from dataclasses import dataclass
from gettext import gettext as _
from typing import ClassVar

from gi.repository import Adw, GObject, Gtk

from penfold import config
from penfold.document.extracting import (
    InvalidFormatError,
    InvalidRangeError,
    MissingPageError,
    PageRangeError,
    format_page_ranges,
    parse_page_ranges,
)


@dataclass(frozen=True)
class PagesToExtract:
    """What the user chose: the positions of the pages, one file per page or one for all, and deleting them after."""

    positions: list[int]
    separate: bool
    delete_after: bool


def describe(error: PageRangeError) -> str:
    """Say what is wrong with a list of pages, as 0.6 does."""
    match error:
        case InvalidFormatError(part=part):
            return _("Invalid format: “{part}”.").format(part=part)
        case InvalidRangeError(part=part):
            return _("Invalid range: “{part}”.").format(part=part)
        case MissingPageError(page=page, page_count=page_count):
            return _("Page {page} does not exist (the document has {count}).").format(page=page, count=page_count)
        case _:
            return _("Enter at least one page.")


@Gtk.Template(resource_path=f"{config.RESOURCE_BASE_PATH}/ui/dialogs/extract_pages_dialog.ui")
class PenfoldExtractPagesDialog(Adw.Dialog):
    """Asks which pages to extract and how; "extract-requested" is emitted with a PagesToExtract."""

    __gtype_name__ = "PenfoldExtractPagesDialog"
    __gsignals__: ClassVar = {
        "extract-requested": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
    }

    extract_button: Gtk.Button = Gtk.Template.Child()
    pages_row: Adw.EntryRow = Gtk.Template.Child()
    error_label: Gtk.Label = Gtk.Template.Child()
    separate_row: Adw.SwitchRow = Gtk.Template.Child()
    delete_row: Adw.SwitchRow = Gtk.Template.Child()

    def __init__(self, page_count: int, selected_pages: list[int]) -> None:
        """Prepare the dialogue for a document of page_count pages, with the selected ones (positions from 0)."""
        super().__init__()
        self._page_count = page_count
        self.pages_row.set_text(format_page_ranges(selected_pages))

    def request(self) -> PagesToExtract:
        """What is chosen now.

        Raises:
            PageRangeError: the list of pages cannot be read.
        """
        positions = parse_page_ranges(self.pages_row.get_text(), self._page_count)
        return PagesToExtract(positions, self.separate_row.get_active(), self.delete_row.get_active())

    def _show_error(self, message: str) -> None:
        self.error_label.set_label(message)
        self.error_label.set_visible(True)
        self.pages_row.add_css_class("error")

    @Gtk.Template.Callback()
    def _on_pages_changed(self, _row: Adw.EntryRow) -> None:
        self.error_label.set_visible(False)
        self.pages_row.remove_css_class("error")

    @Gtk.Template.Callback()
    def _on_cancel_clicked(self, _button: Gtk.Button) -> None:
        self.close()

    @Gtk.Template.Callback()
    def _on_extract_clicked(self, _button: Gtk.Button) -> None:
        try:
            request = self.request()
        except PageRangeError as error:
            self._show_error(describe(error))
            return
        if request.delete_after and len(request.positions) >= self._page_count:
            self._show_error(_("You can’t delete all the pages: turn off “Delete Pages After Extraction”."))
            return
        self.emit("extract-requested", request)
        self.close()
