"""The page box of the document header (02-interfaz, 3.4; D14)."""

from gettext import gettext as _
from typing import ClassVar

from gi.repository import Gdk, GObject, Gtk

from penfold import config
from penfold.document.document import OpenDocument


@Gtk.Template(resource_path=f"{config.RESOURCE_BASE_PATH}/ui/page_entry.ui")
class PenfoldPageEntry(Gtk.Box):
    """Shows the current page and goes to the page typed in it.

    Without page labels it reads "3" and "of 113"; with labels, "ix" and "(11 of 800)". The label or the real number can
    be typed; Enter goes there, and anything that is not a page puts the current one back.
    """

    __gtype_name__ = "PenfoldPageEntry"
    __gsignals__: ClassVar = {
        "page-chosen": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    entry: Gtk.Entry = Gtk.Template.Child()
    position_label: Gtk.Label = Gtk.Template.Child()

    def __init__(self) -> None:
        """Create the box; it stays empty until show_page is called."""
        super().__init__()
        self._document: OpenDocument | None = None
        self._page = 0
        focus = Gtk.EventControllerFocus()
        focus.connect("leave", lambda _controller: self._show_current())
        self.entry.add_controller(focus)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key_pressed)
        self.entry.add_controller(keys)

    def show_page(self, document: OpenDocument, page: int) -> None:
        """Show this page of the document."""
        self._document = document
        self._page = page
        self._show_current()

    def focus(self) -> None:
        """Put the cursor in the box with its text selected (Ctrl+L)."""
        self.entry.grab_focus()

    def _show_current(self) -> None:
        document = self._document
        if document is None:
            return
        self.entry.set_text(document.page_label(self._page))
        count = document.page_count
        if document.has_page_labels:
            # Translators: position of the current page when the PDF names its pages, as in "ix (11 of 800)".
            position = _("({number} of {count})").format(number=self._page + 1, count=count)
        else:
            # Translators: next to the page number, as in "3 of 113".
            position = _("of {count}").format(count=count)
        self.position_label.set_label(position)

    @Gtk.Template.Callback()
    def _on_activate(self, _entry: Gtk.Entry) -> None:
        if self._document is None:
            return
        page = self._document.find_page(self.entry.get_text())
        if page is None:
            self.entry.error_bell()
            self._show_current()
            return
        self.emit("page-chosen", page)

    def _on_key_pressed(
        self, _controller: Gtk.EventControllerKey, keyval: int, _keycode: int, _state: Gdk.ModifierType
    ) -> bool:
        if keyval == Gdk.KEY_Escape:
            self._show_current()
            return True
        return False
