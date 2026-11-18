"""The main window."""

from gi.repository import Adw, Gtk

from penfold import config


@Gtk.Template(resource_path=f"{config.RESOURCE_BASE_PATH}/ui/window.ui")
class PenfoldWindow(Adw.ApplicationWindow):
    """A Penfold window."""

    __gtype_name__ = "PenfoldWindow"
