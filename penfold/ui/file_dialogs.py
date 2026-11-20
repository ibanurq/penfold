"""The system's file chooser, set up for PDFs (D18)."""

from gettext import gettext as _

from gi.repository import Gio, Gtk

PDF_MIME_TYPE = "application/pdf"


def pdf_file_dialog(title: str, initial_file: Gio.File | None = None) -> Gtk.FileDialog:
    """Return a file chooser that shows PDFs; for saving, initial_file proposes the folder and the name."""
    pdf_filter = Gtk.FileFilter(name=_("PDF Documents"))
    pdf_filter.add_mime_type(PDF_MIME_TYPE)
    filters = Gio.ListStore.new(Gtk.FileFilter)
    filters.append(pdf_filter)
    dialog = Gtk.FileDialog(title=title, filters=filters, default_filter=pdf_filter)
    if initial_file is not None:
        dialog.set_initial_file(initial_file)
    return dialog
