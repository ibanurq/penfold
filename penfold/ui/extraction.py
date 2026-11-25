"""Extracting pages from the window: choosing the folder, asking about names taken and writing the files.

The files are written in a worker thread, as saving is, so the window keeps responding. If a file name is already in the
folder, the user chooses to overwrite it, to give the new file a free name, or to stop.
"""

import logging
import threading
from collections.abc import Callable
from gettext import gettext as _
from gettext import ngettext
from pathlib import Path

from gi.repository import Adw, Gio, GLib, Gtk

from penfold.document.document import OpenDocument
from penfold.document.extracting import file_names, free_name
from penfold.document.saving import SavePlan, save
from penfold.errors import SaveError
from penfold.ui.dialogs.extract_pages_dialog import PagesToExtract

logger = logging.getLogger(__name__)

RESPONSE_CANCEL = "cancel"
RESPONSE_RENAME = "rename"
RESPONSE_OVERWRITE = "overwrite"
# Names listed in the question about names taken; the rest are counted.
LISTED_NAMES = 6


class PageExtraction:
    """One extraction, from choosing the folder to the files written; on_finished then says whether it went well."""

    def __init__(
        self,
        parent: Gtk.Window,
        document: OpenDocument,
        request: PagesToExtract,
        on_finished: Callable[[bool], object],
    ) -> None:
        """Prepare to extract pages of a document, asking in a window."""
        self._parent = parent
        self._document = document
        self._request = request
        self._on_finished = on_finished
        positions = request.positions
        self._groups = [[position] for position in positions] if request.separate else [positions]

    def start(self) -> None:
        """Ask for the folder, starting at the document's own."""
        dialog = Gtk.FileDialog(title=_("Choose a Folder"))
        dialog.set_initial_folder(Gio.File.new_for_path(str(self._document.path.parent)))
        dialog.select_folder(self._parent, None, self._on_folder_chosen)

    def _on_folder_chosen(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            folder = None  # Cancelled.
        path = folder.get_path() if folder is not None else None
        if path is None:
            self._on_finished(False)
        else:
            self.extract_into(Path(path))

    def extract_into(self, folder: Path) -> None:
        """Write the files in a folder, asking first if some of their names are taken."""
        names = file_names(_("extracted"), len(self._groups), separate=self._request.separate)
        taken = [name for name in names if (folder / name).exists()]
        if taken:
            self._ask_about_taken(folder, names, taken)
        else:
            self._write(folder, names)

    def _ask_about_taken(self, folder: Path, names: list[str], taken: list[str]) -> None:
        """Ask whether to overwrite the files already in the folder or to give the new ones free names."""
        listed = "\n".join(f"• {name}" for name in taken[:LISTED_NAMES])
        more = len(taken) - LISTED_NAMES
        if more > 0:
            listed += "\n" + ngettext("…and {count} more", "…and {count} more", more).format(count=more)
        dialog = Adw.AlertDialog(
            heading=_("Files Already in the Folder"),
            body=_("{names}\n\nDo you want to overwrite them or rename the new ones?").format(names=listed),
            close_response=RESPONSE_CANCEL,
            default_response=RESPONSE_RENAME,
        )
        dialog.add_response(RESPONSE_CANCEL, _("_Cancel"))
        dialog.add_response(RESPONSE_RENAME, _("_Rename"))
        dialog.add_response(RESPONSE_OVERWRITE, _("_Overwrite"))
        dialog.set_response_appearance(RESPONSE_OVERWRITE, Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._on_taken_answered, folder, names)
        dialog.present(self._parent)

    def _on_taken_answered(self, dialog: Adw.AlertDialog, response: str, folder: Path, names: list[str]) -> None:
        # Only the first answer counts: closing the dialogue afterwards could answer again.
        dialog.disconnect_by_func(self._on_taken_answered)
        if response == RESPONSE_CANCEL:
            self._on_finished(False)
            return
        if response == RESPONSE_RENAME:
            names = free_names(names, {path.name for path in folder.iterdir()})
        self._write(folder, names)

    def _write(self, folder: Path, names: list[str]) -> None:
        """Write the files in a worker thread; report how it went in the main thread."""
        plans = [
            self._document.extract_plan(group, folder / name) for group, name in zip(self._groups, names, strict=True)
        ]
        threading.Thread(target=self._work, args=(plans,), name="penfold-extract", daemon=True).start()

    def _work(self, plans: list[SavePlan]) -> None:
        for plan in plans:
            try:
                save(plan)
            except SaveError:
                logger.exception("Could not extract to %s", plan.target)
                GLib.idle_add(self._finish, plan.target.name)
                return
        GLib.idle_add(self._finish, None)

    def _finish(self, failed_name: str | None) -> bool:
        if failed_name is not None:
            heading = _("Could not save “{name}”").format(name=failed_name)
            dialog = Adw.AlertDialog(heading=heading, default_response="ok", close_response="ok")
            dialog.add_response("ok", _("_OK"))
            dialog.present(self._parent)
        self._on_finished(failed_name is None)
        return GLib.SOURCE_REMOVE


def free_names(names: list[str], taken: set[str]) -> list[str]:
    """Give each name a free one like it, also free among the names given before it."""
    used = set(taken)
    free = []
    for name in names:
        chosen = free_name(name, used)
        used.add(chosen)
        free.append(chosen)
    return free
