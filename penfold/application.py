"""The application: a single instance that owns every Penfold window."""

from collections.abc import Callable, Sequence
from gettext import gettext as _
from pathlib import Path

from gi.repository import Adw, Gio, GLib, Gtk

from penfold import config
from penfold.ui.about import present_about_dialog
from penfold.ui.file_dialogs import pdf_file_dialog
from penfold.ui.preferences_dialog import PenfoldPreferencesDialog
from penfold.ui.shortcuts_dialog import present_shortcuts_dialog
from penfold.ui.style_selector import STYLE_KEY, apply_style
from penfold.ui.window import WINDOW_ACCELERATORS, PenfoldWindow

ACCELERATORS = {
    "app.open": ["<Control>o"],
    "app.quit": ["<Control>q"],
    "app.preferences": ["<Control>comma"],
    "app.shortcuts": ["<Control>question"],
    **WINDOW_ACCELERATORS,
}


class PenfoldApplication(Adw.Application):
    """Penfold's single running instance.

    Launching Penfold again hands the files (or the request for a new window) to the instance already running.
    """

    def __init__(self) -> None:
        """Create the application with Penfold's identifier, its actions and its command-line options."""
        super().__init__(application_id=config.APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.set_resource_base_path(config.RESOURCE_BASE_PATH)
        self._add_action("about", self._on_about)
        self._add_action("preferences", self._on_preferences)
        self._add_action("shortcuts", self._on_shortcuts)
        self._add_action("open", self._on_open)
        self._add_action("merge", self._on_merge)
        self._add_action("new-window", self.new_window)
        self._add_action("quit", self._on_quit)
        for action, accelerators in ACCELERATORS.items():
            self.set_accels_for_action(action, accelerators)
        self.add_main_option(
            "new-window",
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            _("Open a new window"),
            None,
        )

    def do_startup(self) -> None:
        """Show the style chosen in the main menu, and follow its changes (D62)."""
        Adw.Application.do_startup(self)
        self._settings = Gio.Settings(schema_id=config.APP_ID)
        self.add_action(self._settings.create_action(STYLE_KEY))
        self._settings.connect(f"changed::{STYLE_KEY}", lambda settings, key: apply_style(settings.get_string(key)))
        apply_style(self._settings.get_string(STYLE_KEY))

    def do_handle_local_options(self, options: GLib.VariantDict) -> int:
        """Open an empty window with --new-window (New Window in the dock's menu, A6), even from a second launch."""
        if options.contains("new-window"):
            self.register(None)
            self.activate_action("new-window", None)
            return 0
        return -1

    def do_activate(self) -> None:
        """Bring the open window to the front, or open the first one (A7)."""
        window = self.get_active_window() or self.new_window()
        window.present()

    def do_open(self, files: Sequence[Gio.File], _n_files: int, _hint: str) -> None:
        """Open a PDF from the desktop in an empty window, the active one first, or else in a new window (A4).

        Several at once open Merge PDFs with them in the list, in such a window (D17).
        """
        paths = [Path(path) for file in files if (path := file.get_path()) is not None]
        if len(paths) > 1:
            self._empty_window().merge_files(paths)
        elif paths:
            self._empty_window().open_file(paths[0])

    def new_window(self) -> PenfoldWindow:
        """Open an empty window and return it."""
        window = PenfoldWindow(self)
        window.present()
        return window

    def _empty_window(self) -> PenfoldWindow:
        windows = [window for window in self.get_windows() if isinstance(window, PenfoldWindow) and window.is_empty]
        active = self.get_active_window()
        if active in windows:
            assert isinstance(active, PenfoldWindow)
            return active
        return windows[0] if windows else self.new_window()

    def _add_action(self, name: str, callback: Callable[[], object]) -> None:
        action = Gio.SimpleAction(name=name)
        action.connect("activate", lambda _action, _parameter: callback())
        self.add_action(action)

    def _on_about(self) -> None:
        present_about_dialog(self.get_active_window())

    def _on_preferences(self) -> None:
        PenfoldPreferencesDialog().present(self.get_active_window())

    def _on_shortcuts(self) -> None:
        present_shortcuts_dialog(self.get_active_window(), self)

    def _on_open(self) -> None:
        """Choose a PDF and open it in the active window (Ctrl+O, A1), asking first about unsaved changes (J4)."""
        window = self.get_active_window()

        def choose(proceed: bool) -> None:
            if proceed:
                pdf_file_dialog(_("Open a PDF")).open(window, None, self._on_open_chosen, window)

        if isinstance(window, PenfoldWindow):
            window.confirm_discard(choose)
        else:
            choose(True)

    def _on_merge(self) -> None:
        """Open Merge PDFs in the active window, asking first about unsaved changes (F5, J4)."""
        window = self.get_active_window()
        target = window if isinstance(window, PenfoldWindow) else self._empty_window()
        target.merge_files([])

    def _on_open_chosen(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, window: Gtk.Window | None) -> None:
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return  # Cancelled.
        path = file.get_path() if file else None
        if path is None:
            return
        target = window if isinstance(window, PenfoldWindow) else self._empty_window()
        target.open_file(Path(path))

    def _on_quit(self) -> None:
        """Close every window in turn (Ctrl+Q), asking in each with unsaved changes; Cancel stops quitting (A8)."""
        windows = [window for window in self.get_windows() if isinstance(window, PenfoldWindow)]

        def close_next(proceed: bool = True) -> None:
            if proceed and windows:
                windows.pop(0).close_after_asking(close_next)

        close_next()
