"""Header of the document."""

from gettext import gettext as _

from gi.repository import Adw, Gtk

from penfold import config
from penfold.document.access_permissions import AccessPermissions
from penfold.document.document import OpenDocument
from penfold.ui.menus import attach_main_menu

# The template uses this widget by name: importing it also registers its type with GTK.
from penfold.ui.page_entry import PenfoldPageEntry

# In front of the title while the document has unsaved changes.
UNSAVED_MARK = "• "


@Gtk.Template(resource_path=f"{config.RESOURCE_BASE_PATH}/ui/document_header.ui")
class PenfoldDocumentHeader(Adw.Bin):
    """Panel, pencil, undo and redo on the left; the title in the centre; page box and menus on the right."""

    __gtype_name__ = "PenfoldDocumentHeader"

    title_widget: Adw.WindowTitle = Gtk.Template.Child()
    protected_icon: Gtk.Image = Gtk.Template.Child()
    page_entry: PenfoldPageEntry = Gtk.Template.Child()
    main_menu_button: Gtk.MenuButton = Gtk.Template.Child()

    def __init__(self) -> None:
        """Create the header with the shared main menu."""
        super().__init__()
        attach_main_menu(self.main_menu_button)

    def show_document(self, document: OpenDocument) -> None:
        """Show the title of the PDF and, under it, the file name; without a title, only the file name.

        With unsaved changes, the title starts with "• "; a PDF with permissions that deny something has a red lock in
        front, whose tooltip says what they do not allow.
        """
        self.protected_icon.set_visible(document.denies_anything)
        self.protected_icon.set_tooltip_text(describe_denied_permissions(document.permissions))
        mark = UNSAVED_MARK if document.is_modified else ""
        if document.title:
            self.title_widget.set_title(mark + document.title)
            self.title_widget.set_subtitle(document.file_name)
        else:
            self.title_widget.set_title(mark + document.file_name)
            self.title_widget.set_subtitle("")


def describe_denied_permissions(permissions: AccessPermissions) -> str:
    """Say what the user access permissions of a PDF do not allow, one line each (the tooltip of the lock)."""
    lines = [f"• {sentence}" for sentence in denied_sentences(permissions.denied)]
    heading = _("User access permissions of this PDF:")
    # An empty line on each side of the list; the last line says that the option exists.
    return "\n".join([heading, "", *lines, "", _("They can be ignored in Preferences.")])


def denied_sentences(denied: list[str]) -> list[str]:
    """One sentence for each user access permission denied (AccessPermissions.denied), in the same order."""
    sentences = {
        "print": _("It cannot be printed"),
        "fill_forms": _("Its forms cannot be filled in"),
        "annotate": _("It cannot be annotated"),
        "assemble": _("Its pages and bookmarks cannot be changed"),
        "copy": _("Its text cannot be copied"),
        "modify": _("Its form cannot be flattened"),
    }
    return [sentences[name] for name in denied]
