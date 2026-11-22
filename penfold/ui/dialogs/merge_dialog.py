"""The "Merge PDFs" dialogue (02-interfaz, 8; F1 to F4; D50): the files to merge, in order, and their bookmarks.

Files are added with the button or dropped on the dialogue; only PDFs are listed. Encrypted PDFs stay in the list, in
red, so it is clear that they will be left out (F4). At least two files that can be merged are needed (F3).
"""

from dataclasses import dataclass
from gettext import gettext as _
from gettext import ngettext
from pathlib import Path
from typing import ClassVar, cast

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

from penfold import config
from penfold.document.sources import count_pages
from penfold.errors import AssemblyNotAllowedError, DocumentOpenError
from penfold.ui.autoscroll import DragAutoscroll
from penfold.ui.file_dialogs import pdf_file_dialog
from penfold.ui.preferences_dialog import RESPECT_PERMISSIONS_KEY

PDF_SUFFIX = ".pdf"
DROP_ABOVE = "drop-above"
DROP_BELOW = "drop-below"


@dataclass(frozen=True)
class FileToMerge:
    """A file in the list: its path and how many pages it has; None for an encrypted PDF, which cannot be merged."""

    path: Path
    page_count: int | None


@dataclass(frozen=True)
class PdfsToMerge:
    """What the user chose: the files that can be merged, in order, and how their bookmarks are kept."""

    paths: list[Path]
    bookmark_per_file: bool
    keep_bookmarks: bool


class DraggedFile(GObject.Object):
    """A row of the list being dragged to another place, by its position."""

    __gtype_name__ = "PenfoldDraggedFile"

    def __init__(self, position: int) -> None:
        """Remember which row is dragged."""
        super().__init__()
        self.position = position


@Gtk.Template(resource_path=f"{config.RESOURCE_BASE_PATH}/ui/dialogs/merge_dialog.ui")
class PenfoldMergeDialog(Adw.Dialog):
    """Asks which PDFs to merge, in which order; "merge-requested" is emitted with a PdfsToMerge."""

    __gtype_name__ = "PenfoldMergeDialog"
    __gsignals__: ClassVar = {
        "merge-requested": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
    }

    merge_button: Gtk.Button = Gtk.Template.Child()
    scrolled: Gtk.ScrolledWindow = Gtk.Template.Child()
    file_list: Gtk.ListBox = Gtk.Template.Child()
    total_label: Gtk.Label = Gtk.Template.Child()
    bookmark_per_file_row: Adw.SwitchRow = Gtk.Template.Child()
    keep_bookmarks_row: Adw.SwitchRow = Gtk.Template.Child()

    def __init__(self) -> None:
        """Prepare an empty list."""
        super().__init__()
        self.files: list[FileToMerge] = []
        # A file dropped on another row, moved when its drag ends: its position and the one it goes before.
        self._pending_move: tuple[int, int] | None = None
        placeholder = Gtk.Label(
            label=_("Drag PDFs here or click “Add PDFs…”"), wrap=True, margin_top=48, margin_bottom=48
        )
        placeholder.add_css_class("dim-label")
        self.file_list.set_placeholder(placeholder)
        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_files_dropped)
        self.add_controller(drop)
        # One target for the whole list, as for the thumbnails: one per row made GTK warn as a drag crossed them.
        rows_drop = Gtk.DropTarget.new(DraggedFile, Gdk.DragAction.MOVE)
        rows_drop.connect("motion", self._on_row_motion)
        rows_drop.connect("leave", lambda _target: self._mark_drop(None))
        rows_drop.connect("drop", self._on_row_drop)
        self.file_list.add_controller(rows_drop)
        self._marked_row: Gtk.ListBoxRow | None = None
        DragAutoscroll(self.scrolled)
        self._show_files()

    @property
    def request(self) -> PdfsToMerge:
        """What is chosen now."""
        paths = [file.path for file in self.files if file.page_count is not None]
        return PdfsToMerge(paths, self.bookmark_per_file_row.get_active(), self.keep_bookmarks_row.get_active())

    def add_files(self, paths: list[Path]) -> None:
        """Add PDFs at the end of the list; files that are not PDFs are left out, and unreadable ones explained.

        A PDF whose permissions do not let it be merged is listed as such, unless they are ignored (D61).
        """
        respect_permissions = Gio.Settings(schema_id=config.APP_ID).get_boolean(RESPECT_PERMISSIONS_KEY)
        unreadable = []
        for path in paths:
            if path.suffix.lower() != PDF_SUFFIX:
                continue
            try:
                self.files.append(FileToMerge(path, count_pages(path, respect_permissions=respect_permissions)))
            except AssemblyNotAllowedError:
                self.files.append(FileToMerge(path, None))
            except DocumentOpenError:
                unreadable.append(path.name)
        self._show_files()
        if unreadable:
            heading = _("Could not open “{name}”").format(name=", ".join(unreadable))
            message = Adw.AlertDialog(heading=heading, default_response="ok", close_response="ok")
            message.add_response("ok", _("_OK"))
            message.present(self)

    def remove_file(self, position: int) -> None:
        """Take a file out of the list."""
        del self.files[position]
        self._show_files()

    def move_file(self, position: int, before: int) -> None:
        """Move a file to just before the one at another position (the length of the list: to the end)."""
        moved = self.files.pop(position)
        self.files.insert(before - 1 if before > position else before, moved)
        self._show_files()

    def _show_files(self) -> None:
        """List the files again, with the total and the Merge button as they now are."""
        self.file_list.remove_all()
        for position, file in enumerate(self.files):
            self.file_list.append(self._row(position, file))
        mergeable = [file.page_count for file in self.files if file.page_count is not None]
        files = ngettext("{count} file", "{count} files", len(mergeable)).format(count=len(mergeable))
        pages = ngettext("{count} page in total", "{count} pages in total", sum(mergeable)).format(count=sum(mergeable))
        self.total_label.set_label(f"{files} · {pages}" if mergeable else "")
        self.total_label.set_visible(bool(mergeable))
        self.merge_button.set_sensitive(len(mergeable) >= 2)  # noqa: PLR2004 (merging needs two files, F3)

    def _row(self, position: int, file: FileToMerge) -> Adw.ActionRow:
        """A row with the handle to drag it, the file's name and pages, and a button to remove it."""
        row = Adw.ActionRow(title=GLib.markup_escape_text(file.path.name), title_lines=1)
        row.set_tooltip_text(file.path.name)
        if file.page_count is None:
            row.set_subtitle(_("Cannot be merged"))
            row.add_css_class("error")
        else:
            row.set_subtitle(ngettext("{count} page", "{count} pages", file.page_count).format(count=file.page_count))
        handle = Gtk.Image(icon_name="list-drag-handle-symbolic")
        handle.add_css_class("dim-label")
        row.add_prefix(handle)
        remove = Gtk.Button(
            icon_name="window-close-symbolic", tooltip_text=_("Remove From List"), valign=Gtk.Align.CENTER
        )
        remove.add_css_class("flat")
        remove.add_css_class("circular")
        remove.connect("clicked", lambda _button: self.remove_file(position))
        row.add_suffix(remove)
        self._make_draggable(row, position)
        return row

    def _make_draggable(self, row: Adw.ActionRow, position: int) -> None:
        """Let a row be dragged to another place in the list."""
        drag = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        drag.connect("prepare", lambda _source, _x, _y: Gdk.ContentProvider.new_for_value(DraggedFile(position)))
        drag.connect("drag-begin", lambda source, _drag: source.set_icon(Gtk.WidgetPaintable.new(row), 0, 0))
        drag.connect("drag-end", self._on_drag_end)
        row.add_controller(drag)

    def _drop_place(self, y: float) -> tuple[Gtk.ListBoxRow, bool] | None:
        """The row under a point of the list, and whether the point is in its upper half (the file goes before it)."""
        row = self.file_list.get_row_at_y(int(y))
        if row is None:
            return None
        found, bounds = row.compute_bounds(self.file_list)
        return row, not found or y < bounds.get_y() + bounds.get_height() / 2

    def _mark_drop(self, place: tuple[Gtk.ListBoxRow, bool] | None) -> None:
        """Show a line above or below the row where a dragged file would go; none for None."""
        if self._marked_row is not None:
            _clear_drop_mark(self._marked_row)
        self._marked_row = place[0] if place is not None else None
        if place is not None:
            place[0].add_css_class(DROP_ABOVE if place[1] else DROP_BELOW)

    def _on_row_motion(self, _target: Gtk.DropTarget, _x: float, y: float) -> Gdk.DragAction:
        place = self._drop_place(y)
        self._mark_drop(place)
        return Gdk.DragAction.MOVE if place is not None else Gdk.DragAction(0)

    def _on_row_drop(self, _target: Gtk.DropTarget, value: object, _x: float, y: float) -> bool:
        place = self._drop_place(y)
        self._mark_drop(None)
        if not isinstance(value, DraggedFile) or place is None:
            return False
        row, before = place
        self._pending_move = (value.position, row.get_index() if before else row.get_index() + 1)
        return True

    def _on_drag_end(self, _source: Gtk.DragSource, _drag: Gdk.Drag, _delete_data: bool) -> None:
        """Move the file dropped once its drag has wholly ended.

        Making the rows again destroys the row dragged; on Wayland a drag ends a moment after the drop, and destroying
        its row before confuses GTK.
        """
        if self._pending_move is not None:
            position, before = self._pending_move
            self._pending_move = None
            GLib.idle_add(self._move_later, position, before)

    def _move_later(self, position: int, before: int) -> bool:
        self.move_file(position, before)
        return GLib.SOURCE_REMOVE

    def _on_files_dropped(self, _target: Gtk.DropTarget, value: Gdk.FileList, _x: float, _y: float) -> bool:
        paths = [Path(path) for file in value.get_files() if (path := file.get_path()) is not None]
        self.add_files(paths)
        return bool(paths)

    @Gtk.Template.Callback()
    def _on_add_clicked(self, _button: Gtk.Button) -> None:
        root = self.get_root()
        parent = root if isinstance(root, Gtk.Window) else None
        pdf_file_dialog(_("Add PDFs")).open_multiple(parent, None, self._on_files_chosen)

    def _on_files_chosen(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            files = dialog.open_multiple_finish(result)
        except GLib.Error:
            return  # Cancelled.
        # The items are Gio.File, an interface: they cannot be checked with isinstance.
        chosen = [cast("Gio.File", files.get_item(index)) for index in range(files.get_n_items())]
        self.add_files([Path(path) for file in chosen if (path := file.get_path()) is not None])

    @Gtk.Template.Callback()
    def _on_cancel_clicked(self, _button: Gtk.Button) -> None:
        self.close()

    @Gtk.Template.Callback()
    def _on_merge_clicked(self, _button: Gtk.Button) -> None:
        self.emit("merge-requested", self.request)
        self.close()


def _clear_drop_mark(row: Gtk.Widget) -> None:
    row.remove_css_class(DROP_ABOVE)
    row.remove_css_class(DROP_BELOW)
