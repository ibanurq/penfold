"""The main window."""

from gi.repository import Adw, Gtk

from penfold import config

# The template uses these widgets by name: importing them registers their types with GTK.
from penfold.ui import welcome_page  # noqa: F401


@Gtk.Template(resource_path=f"{config.RESOURCE_BASE_PATH}/ui/window.ui")
class PenfoldWindow(Adw.ApplicationWindow):
    """A Penfold window."""

    __gtype_name__ = "PenfoldWindow"
