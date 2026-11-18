"""The application: a single instance that owns every Penfold window."""

from gi.repository import Adw, Gio

from penfold import config
from penfold.ui.window import PenfoldWindow


class PenfoldApplication(Adw.Application):
    """Penfold's single running instance."""

    def __init__(self) -> None:
        """Create the application with Penfold's identifier."""
        super().__init__(application_id=config.APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.set_resource_base_path(config.RESOURCE_BASE_PATH)

    def do_activate(self) -> None:
        """Bring the open window to the front, or open the first one."""
        window = self.get_active_window() or PenfoldWindow(application=self)
        window.present()
