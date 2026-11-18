"""The page shown in a window without a document."""

from gi.repository import Adw, Gtk

from penfold import config


@Gtk.Template(resource_path=f"{config.RESOURCE_BASE_PATH}/ui/welcome_page.ui")
class PenfoldWelcomePage(Adw.Bin):
    """Invites the user to open a PDF or to merge several."""

    __gtype_name__ = "PenfoldWelcomePage"
