"""Header of the document (02-interfaz, 3.2)."""

from gi.repository import Adw, Gtk

from penfold import config
from penfold.document.document import OpenDocument
from penfold.ui.menus import main_menu

# The template uses this widget by name: importing it also registers its type with GTK.
from penfold.ui.page_entry import PenfoldPageEntry

# In front of the title while the document has unsaved changes (D16).
UNSAVED_MARK = "• "


@Gtk.Template(resource_path=f"{config.RESOURCE_BASE_PATH}/ui/document_header.ui")
class PenfoldDocumentHeader(Adw.Bin):
    """Panel, pencil, undo and redo on the left; the title in the centre; page box and menus on the right."""

    __gtype_name__ = "PenfoldDocumentHeader"

    title_widget: Adw.WindowTitle = Gtk.Template.Child()
    page_entry: PenfoldPageEntry = Gtk.Template.Child()
    main_menu_button: Gtk.MenuButton = Gtk.Template.Child()

    def __init__(self) -> None:
        """Create the header with the shared main menu."""
        super().__init__()
        self.main_menu_button.set_menu_model(main_menu())

    def show_document(self, document: OpenDocument) -> None:
        """Show the title of the PDF and, under it, the file name; without a title, only the file name.

        With unsaved changes, the title starts with "• " (D16).
        """
        mark = UNSAVED_MARK if document.is_modified else ""
        if document.title:
            self.title_widget.set_title(mark + document.title)
            self.title_widget.set_subtitle(document.file_name)
        else:
            self.title_widget.set_title(mark + document.file_name)
            self.title_widget.set_subtitle("")
