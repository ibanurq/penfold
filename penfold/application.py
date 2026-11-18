"""The application: a single instance that owns every Penfold window."""

from collections.abc import Callable

from gi.repository import Adw, Gio

from penfold import config
from penfold.ui.about import present_about_dialog
from penfold.ui.shortcuts_dialog import present_shortcuts_dialog
from penfold.ui.window import PenfoldWindow

ACCELERATORS = {
    "app.shortcuts": ["<Control>question"],
}


class PenfoldApplication(Adw.Application):
    """Penfold's single running instance."""

    def __init__(self) -> None:
        """Create the application with Penfold's identifier and its actions."""
        super().__init__(application_id=config.APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.set_resource_base_path(config.RESOURCE_BASE_PATH)
        self._add_action("about", self._on_about)
        self._add_action("shortcuts", self._on_shortcuts)
        for action, accelerators in ACCELERATORS.items():
            self.set_accels_for_action(action, accelerators)

    def do_activate(self) -> None:
        """Bring the open window to the front, or open the first one."""
        window = self.get_active_window() or PenfoldWindow(application=self)
        window.present()

    def _add_action(self, name: str, callback: Callable[[], None]) -> None:
        action = Gio.SimpleAction(name=name)
        action.connect("activate", lambda _action, _parameter: callback())
        self.add_action(action)

    def _on_about(self) -> None:
        present_about_dialog(self.get_active_window())

    def _on_shortcuts(self) -> None:
        present_shortcuts_dialog(self.get_active_window(), self)
