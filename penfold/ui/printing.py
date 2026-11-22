"""Printing (D57): the PDF prepared as saving does, then the system's print dialogue.

The PDF to print has the form values and only the groups of annotations chosen; it is written in a worker thread to a
private temporary folder, drawn page by page with Poppler and removed when the printing is over.
"""

import logging
import shutil
import tempfile
import threading
from collections.abc import Callable
from gettext import gettext as _
from pathlib import Path

from gi.repository import Gio, GLib, Gtk, Poppler

from penfold.document.annotations import PrintGroup
from penfold.document.document import OpenDocument
from penfold.document.saving import save
from penfold.errors import SaveError
from penfold.rendering.renderer import POPPLER_DRAWING

logger = logging.getLogger(__name__)


class DocumentPrinting:
    """One print job, from the PDF prepared to the system's print dialogue; on_failed is told what went wrong."""

    def __init__(self, parent: Gtk.Window, document: OpenDocument, on_failed: Callable[[str], None]) -> None:
        """Prepare to print a document from a window."""
        self._parent = parent
        self._document = document
        self._on_failed = on_failed
        self._folder: Path | None = None
        self._poppler: Poppler.Document | None = None

    def start(self, left_out: frozenset[PrintGroup]) -> None:
        """Write the PDF to print in a worker thread; the print dialogue opens when it is ready."""
        self._folder = Path(tempfile.mkdtemp(prefix="penfold-print-"))
        plan = self._document.print_plan(self._folder / self._document.file_name, left_out)

        def work() -> None:
            try:
                save(plan)
            except SaveError:
                logger.exception("Could not prepare %s for printing", plan.target)
                GLib.idle_add(self._fail)
            else:
                GLib.idle_add(self._show_print_dialog, plan.target)

        threading.Thread(target=work, name="penfold-print", daemon=True).start()

    def _show_print_dialog(self, path: Path) -> bool:
        operation = self.make_operation(path)
        if operation is None:
            self._fail()
            return GLib.SOURCE_REMOVE
        try:
            operation.run(Gtk.PrintOperationAction.PRINT_DIALOG, self._parent)
        except GLib.Error:
            logger.exception("Could not print %s", path)
            self._fail()
        return GLib.SOURCE_REMOVE

    def make_operation(self, path: Path) -> Gtk.PrintOperation | None:
        """Prepare the printing of the PDF written to path; None if it cannot be read."""
        try:
            # The PDF to print keeps the passwords of the opened one (D61).
            password = self._document.sources.spans[0].password or None
            self._poppler = Poppler.Document.new_from_gfile(Gio.File.new_for_path(str(path)), password, None)
        except GLib.Error:
            logger.exception("Could not read %s for printing", path)
            return None
        operation = Gtk.PrintOperation(
            n_pages=self._poppler.get_n_pages(), job_name=self._document.file_name, allow_async=True
        )
        operation.connect("request-page-setup", self._on_request_page_setup)
        operation.connect("draw-page", self._on_draw_page)
        operation.connect("done", self._on_done)
        return operation

    def _on_request_page_setup(
        self, _operation: Gtk.PrintOperation, _context: Gtk.PrintContext, index: int, setup: Gtk.PageSetup
    ) -> None:
        """Each page is printed upright or across, as it is wider or taller."""
        assert self._poppler is not None
        width, height = self._poppler.get_page(index).get_size()
        landscape = width > height
        setup.set_orientation(Gtk.PageOrientation.LANDSCAPE if landscape else Gtk.PageOrientation.PORTRAIT)

    def _on_draw_page(self, _operation: Gtk.PrintOperation, context: Gtk.PrintContext, index: int) -> None:
        """Draw a page as large as it fits in the printable area, centred."""
        assert self._poppler is not None
        page = self._poppler.get_page(index)
        width, height = page.get_size()
        area_width, area_height = context.get_width(), context.get_height()
        scale = min(area_width / width, area_height / height)
        cairo_context = context.get_cairo_context()
        cairo_context.translate((area_width - width * scale) / 2, (area_height - height * scale) / 2)
        cairo_context.scale(scale, scale)
        with POPPLER_DRAWING:
            page.render_for_printing(cairo_context)

    def _on_done(self, _operation: Gtk.PrintOperation, result: Gtk.PrintOperationResult) -> None:
        if result is Gtk.PrintOperationResult.ERROR:
            logger.error("Printing %s failed", self._document.file_name)
            self._on_failed(_("Could not print “{name}”").format(name=self._document.file_name))
        self._clean_up()

    def _fail(self) -> bool:
        self._clean_up()
        self._on_failed(_("Could not print “{name}”").format(name=self._document.file_name))
        return GLib.SOURCE_REMOVE

    def _clean_up(self) -> None:
        self._poppler = None
        if self._folder is not None:
            shutil.rmtree(self._folder, ignore_errors=True)
            self._folder = None
