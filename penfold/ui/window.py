"""The main window: the welcome page, or a PDF with its header and zoom buttons."""

import logging
import threading
from collections.abc import Callable
from gettext import gettext as _
from gettext import ngettext
from pathlib import Path

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

from penfold import config
from penfold.document.annotations import Annotation
from penfold.document.commands.pages import AddPages, DeletePages, MovePages, RotatePages
from penfold.document.document import OpenDocument
from penfold.document.history import Change, Command
from penfold.document.pages import PaperSize
from penfold.document.saving import SavePlan, save
from penfold.errors import AssemblyNotAllowedError, DocumentOpenError, PasswordRequiredError, PenfoldError, SaveError
from penfold.rendering.renderer import Renderer
from penfold.rendering.text_search import ContextReader
from penfold.ui.annotating import Annotating
from penfold.ui.annotation_editing import AnnotationEditing
from penfold.ui.annotation_toolbar import AnnotationToolbar, Tool, bar_position
from penfold.ui.bookmark_editing import BookmarkEditing

# The template uses these widgets by name: importing them also registers their types with GTK.
from penfold.ui.dialogs.add_pages_dialog import PagesToAdd, PenfoldAddPagesDialog
from penfold.ui.dialogs.extract_pages_dialog import PagesToExtract, PenfoldExtractPagesDialog
from penfold.ui.dialogs.merge_dialog import PdfsToMerge, PenfoldMergeDialog
from penfold.ui.dialogs.password_question import password_question
from penfold.ui.dialogs.print_dialog import PenfoldPrintDialog
from penfold.ui.dialogs.save_as_dialog import PenfoldSaveAsDialog
from penfold.ui.document_header import UNSAVED_MARK, PenfoldDocumentHeader
from penfold.ui.document_view import DocumentView
from penfold.ui.extraction import PageExtraction
from penfold.ui.file_dialogs import pdf_file_dialog
from penfold.ui.menus import attach_main_menu
from penfold.ui.preferences_dialog import AUTHOR_NAME_KEY, RESPECT_PERMISSIONS_KEY
from penfold.ui.printing import DocumentPrinting
from penfold.ui.sidebar import sidebar as sidebar_views
from penfold.ui.sidebar.annotations_view import AnnotationsView
from penfold.ui.sidebar.bookmarks_view import BookmarksView
from penfold.ui.sidebar.pages_view import PagesView
from penfold.ui.sidebar.search_view import SearchView
from penfold.ui.sidebar.sidebar import PenfoldSidebar, clamp_width
from penfold.ui.welcome_page import PenfoldWelcomePage  # noqa: F401
from penfold.ui.zoom_controls import PenfoldZoomControls

logger = logging.getLogger(__name__)

WELCOME_SIZE = (620, 600)
LAYOUT_CONTINUOUS = "continuous"
LAYOUT_TWO_PAGES = "two-pages"
# Room the document keeps beside the panel, besides what its header needs (0.6 kept 160 pixels).
DOCUMENT_ROOM = 160
# How long the panel waits, at most, for a growing window to make room for it.
SIDEBAR_WAIT_MICROSECONDS = 500_000

# Window actions and their shortcuts (0.6, apartado 2.8). They need a document, so they are off without one (A2).
DOCUMENT_ACTIONS = {
    "zoom-in": ["<Control>plus", "<Control>equal", "<Control>KP_Add"],
    "zoom-out": ["<Control>minus", "<Control>KP_Subtract"],
    "fit-width": ["<Control>0"],
    "fit-page": [],
    "next-page": ["Page_Down"],
    "previous-page": ["Page_Up"],
    "first-page": ["<Control>Home"],
    "last-page": ["<Control>End"],
    "focus-page-entry": ["<Control>l"],
    "find": ["<Control>f"],
    "find-next": ["<Control>g"],
    "find-previous": ["<Shift><Control>g"],
    # Ctrl+P: prints, or in a PDF that does not allow it says so (K3, D59); the menu item is win.print.
    "print-shortcut": ["<Control>p"],
}
# Edits of the document; each is on only while there is something for it to do (D19, D21).
EDIT_ACTIONS = {
    "undo": ["<Control>z"],
    "redo": ["<Shift><Control>z"],
}
# Saving (J1) and printing (D57): on while not saving; printing, also if the PDF allows it (D59).
SAVE_ACTIONS = {
    "save": ["<Control>s"],
    "save-as": ["<Shift><Control>s"],
    "print": [],
}
# Answers to the question about unsaved changes (J5).
RESPONSE_CANCEL = "cancel"
RESPONSE_DISCARD = "discard"
RESPONSE_SAVE = "save"
QUARTER_TURN = 90
HALF_TURN = 180
WINDOW_ACCELERATORS = {
    "win.close": ["<Control>w"],
    **{f"win.{name}": keys for name, keys in EDIT_ACTIONS.items()},
    **{f"win.{name}": keys for name, keys in SAVE_ACTIONS.items()},
    "win.show-sidebar": ["F9"],
    **{f"win.{name}": keys for name, keys in DOCUMENT_ACTIONS.items()},
}
# Keys without Ctrl do nothing while typing in a field (L4).
KEYS_WITHOUT_CONTROL = frozenset({"next-page", "previous-page"})


@Gtk.Template(resource_path=f"{config.RESOURCE_BASE_PATH}/ui/window.ui")
class PenfoldWindow(Adw.ApplicationWindow):
    """A Penfold window, with or without a PDF."""

    __gtype_name__ = "PenfoldWindow"

    stack: Gtk.Stack = Gtk.Template.Child()
    split_view: Adw.OverlaySplitView = Gtk.Template.Child()
    sidebar: PenfoldSidebar = Gtk.Template.Child()
    welcome_menu_button: Gtk.MenuButton = Gtk.Template.Child()
    document_header: PenfoldDocumentHeader = Gtk.Template.Child()
    toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    document_view: DocumentView = Gtk.Template.Child()
    zoom_controls: PenfoldZoomControls = Gtk.Template.Child()
    document_overlay: Gtk.Overlay = Gtk.Template.Child()

    def __init__(self, application: Gtk.Application) -> None:
        """Create a window of the application, showing the welcome page."""
        super().__init__(application=application)
        self.document: OpenDocument | None = None
        self.renderer: Renderer | None = None
        self._saving = False
        self._close_confirmed = False
        self._edit_toast: tuple[Adw.Toast, Command] | None = None
        self._settings = Gio.Settings(schema_id=config.APP_ID)
        self._settings.connect(f"changed::{RESPECT_PERMISSIONS_KEY}", self._on_respect_permissions_changed)
        attach_main_menu(self.welcome_menu_button)
        self._add_actions()
        self.document_view.connect("current-page-changed", self._on_current_page_changed)
        self.document_view.connect("zoom-changed", self._on_zoom_changed)
        self.document_view.connect("viewport-changed", self._on_viewport_changed)
        self.document_header.page_entry.connect("page-chosen", self._on_page_chosen)
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_drop)
        self.add_controller(drop_target)
        self.connect("close-request", self._on_close_request)
        self._set_up_sidebar()

    @property
    def is_empty(self) -> bool:
        """Whether the window shows no document (a PDF from the desktop opens in an empty window, A4)."""
        return self.document is None

    # Actions.

    def _add_actions(self) -> None:
        close = Gio.SimpleAction(name="close")
        close.connect("activate", lambda _action, _parameter: self.close())
        self.add_action(close)
        handlers = {
            "zoom-in": self.document_view.zoom_in,
            "zoom-out": self.document_view.zoom_out,
            "fit-width": self.document_view.fit_width,
            "fit-page": self.document_view.fit_page,
            "next-page": self.document_view.page_down,
            "previous-page": self.document_view.page_up,
            "first-page": self.document_view.first_page,
            "last-page": self.document_view.last_page,
            "focus-page-entry": self.document_header.page_entry.focus,
            "find": self.open_find,
            "find-next": lambda: self._find_step(1),
            "find-previous": lambda: self._find_step(-1),
            "print-shortcut": self._print_shortcut,
        }
        for name, handler in handlers.items():
            action = Gio.SimpleAction(name=name, enabled=False)
            action.connect("activate", self._on_document_action, name, handler)
            self.add_action(action)
        editing: dict[str, Callable[[], object]] = {
            "undo": lambda: self._undo_or_redo(redo=False),
            "redo": lambda: self._undo_or_redo(redo=True),
            "rotate-pages-left": lambda: self._rotate_selected_pages(-QUARTER_TURN),
            "rotate-pages-right": lambda: self._rotate_selected_pages(QUARTER_TURN),
            "rotate-pages-180": lambda: self._rotate_selected_pages(HALF_TURN),
            "delete-pages": self._delete_selected_pages,
            "add-pages": self._open_add_pages_dialog,
            "extract-pages": self._open_extract_pages_dialog,
            "save": self.save,
            "save-as": self.save_as,
            "print": self._open_print_dialog,
        }
        for name, edit in editing.items():
            action = Gio.SimpleAction(name=name, enabled=False)
            action.connect("activate", self._on_editing_action, name, edit)
            self.add_action(action)
        self._add_delete_key()
        layout = Gio.SimpleAction.new_stateful(
            "layout", GLib.VariantType.new("s"), GLib.Variant.new_string(LAYOUT_CONTINUOUS)
        )
        layout.set_enabled(False)
        layout.connect("change-state", self._on_layout_changed)
        self.add_action(layout)

    def _on_editing_action(
        self, _action: Gio.SimpleAction, _parameter: None, name: str, edit: Callable[[], object]
    ) -> None:
        """Save, print, change the pages…: first accept what is being edited on a page (a text box, a move).

        Undo and redo do not: in a text box being written, they undo its own typing (_undo_or_redo).
        """
        if name not in {"undo", "redo"}:
            self.document_view.finish_editing()
        edit()

    def _on_document_action(self, _action: Gio.SimpleAction, _parameter: None, name: str, handler: object) -> None:
        if name in KEYS_WITHOUT_CONTROL and isinstance(self.get_focus(), Gtk.Editable | Gtk.Text):
            return
        # With the focus on the thumbnails, Ctrl++ and Ctrl+- zoom them instead of the document (D39).
        if name in {"zoom-in", "zoom-out"} and self.pages_view.has_focus_inside():
            (self.pages_view.zoom_in if name == "zoom-in" else self.pages_view.zoom_out)()
            return
        assert callable(handler)
        handler()

    def _enable_action(self, name: str, enabled: bool) -> None:
        action = self.lookup_action(name)
        assert isinstance(action, Gio.SimpleAction)
        action.set_enabled(enabled)

    def _undo_or_redo(self, *, redo: bool) -> None:
        """Undo or redo the last edit of the document; while typing in a field, its own text instead.

        Form fields on the pages are part of the document: what is typed in them is undone as an edit (J2).
        """
        focus = self.get_focus()
        if isinstance(focus, Gtk.Text) and not focus.is_ancestor(self.document_view):
            focus.activate_action("text.redo" if redo else "text.undo", None)
        elif self.document is not None:
            (self.document.redo if redo else self.document.undo)()

    def _update_edit_actions(self) -> None:
        """Undo and Redo are on while there is something to undo or redo (D21)."""
        document = self.document
        for name, enabled in (
            ("undo", document is not None and document.can_undo),
            ("redo", document is not None and document.can_redo),
        ):
            self._enable_action(name, enabled)

    def _add_delete_key(self) -> None:
        """Add the keys without Control: Delete, F2, the Menu key (or Shift+F10), and H and U.

        Delete deletes what is selected in the panel (E3); F2 renames a bookmark and the Menu key opens the menu of the
        pages or bookmarks selected (D74); H and U mark text (H7). They are handled after the focused widget, so that
        they still delete or type while typing in a field (L4).
        """
        controller = Gtk.ShortcutController(propagation_phase=Gtk.PropagationPhase.BUBBLE)
        for trigger, callback in (
            ("Delete", self._on_delete_key),
            ("F2", self._on_rename_key),
            ("Menu|<Shift>F10", self._on_menu_key),
            ("h", lambda _widget, _arguments: self._on_marking_key(Tool.HIGHLIGHT)),
            ("u", lambda _widget, _arguments: self._on_marking_key(Tool.UNDERLINE)),
        ):
            controller.add_shortcut(
                Gtk.Shortcut(trigger=Gtk.ShortcutTrigger.parse_string(trigger), action=Gtk.CallbackAction.new(callback))
            )
        self.add_controller(controller)

    def _on_marking_key(self, tool: Tool) -> bool:
        """H or U: mark the text selected, or choose the tool; never while a dialogue is open."""
        if self.get_visible_dialog() is not None or self.document is None:
            return False
        return self.annotating.mark_or_choose(tool)

    def _on_delete_key(self, _widget: Gtk.Widget, _arguments: GLib.Variant | None) -> bool:
        """Delete acts on the view of the panel shown, and never while a dialogue is open."""
        if self.get_visible_dialog() is not None:
            return False
        if self.sidebar.visible_view == sidebar_views.BOOKMARKS and self.bookmark_editing.can_delete():
            self.bookmark_editing.delete_selected()
            return True
        if self.sidebar.visible_view == sidebar_views.ANNOTATIONS:
            selected = self.annotations_view.selected_annotations()
            if not selected or self.document is None or not self.document.permissions.annotate:
                return False
            self.annotation_editing.delete(selected)
            return True
        action = self.lookup_action("delete-pages")
        if self.sidebar.visible_view != sidebar_views.PAGES or action is None or not action.get_enabled():
            return False
        action.activate(None)
        return True

    def _on_menu_key(self, _widget: Gtk.Widget, _arguments: GLib.Variant | None) -> bool:
        """The Menu key, or Shift+F10, opens the menu of what is selected in Pages or Bookmarks, if shown (D74).

        As Delete, wherever the focus is: a click on a thumbnail or a bookmark leaves it in the document.
        """
        if self.get_visible_dialog() is not None or not self.split_view.get_show_sidebar():
            return False
        if self.sidebar.visible_view == sidebar_views.PAGES:
            return self.pages_view.open_menu()
        if self.sidebar.visible_view == sidebar_views.BOOKMARKS:
            return self.bookmarks_view.open_menu()
        return False

    def _on_rename_key(self, _widget: Gtk.Widget, _arguments: GLib.Variant | None) -> bool:
        """F2 renames the bookmark selected while the Bookmarks view is shown, and never while a dialogue is open."""
        action = self.lookup_action("rename-bookmark")
        if (
            self.get_visible_dialog() is not None
            or not self.split_view.get_show_sidebar()
            or self.sidebar.visible_view != sidebar_views.BOOKMARKS
            or action is None
            or not action.get_enabled()
        ):
            return False
        action.activate(None)
        return True

    def _update_page_actions(self) -> None:
        """Turning needs pages selected; deleting, too, and never all of them (E3, D21).

        A PDF that does not allow assembling it has all of them off (D59).
        """
        document = self.document
        assemble = document is not None and document.permissions.assemble
        selected = len(self.pages_view.selected_pages()) if assemble else 0
        page_count = document.page_count if document is not None else 0
        for name, enabled in (
            ("rotate-pages-left", selected > 0),
            ("rotate-pages-right", selected > 0),
            ("rotate-pages-180", selected > 0),
            ("delete-pages", 0 < selected < page_count),
            ("add-pages", assemble),
            ("extract-pages", assemble),
        ):
            self._enable_action(name, enabled)

    def _rotate_selected_pages(self, degrees: int) -> None:
        if self.document is not None:
            self.document.execute(RotatePages(self.document, self.pages_view.selected_pages(), degrees))

    def _on_move_requested(self, _view: PagesView, positions: list[int], before: int) -> None:
        """Move dragged thumbnails (E1); dropping them where they already are changes nothing."""
        if self.document is None or not self.document.permissions.assemble:
            return
        command = MovePages(self.document, positions, before)
        if command.moves_anything:
            self.document.execute(command)

    def _delete_selected_pages(self) -> None:
        """Delete the selected pages at once, with a notice to undo it (D19)."""
        document = self.document
        if document is None:
            return
        command = DeletePages(document, self.pages_view.selected_pages())
        document.execute(command)
        count = len(command.positions)
        self._show_undo_toast(ngettext("Page deleted", "{count} pages deleted", count).format(count=count), command)

    def _open_add_pages_dialog(self) -> None:
        """Ask what pages to add and where (E4 to E6, D48)."""
        if self.document is None:
            return
        document = self.document
        dialog = PenfoldAddPagesDialog(
            document.page_count,
            self.document_view.current_page,
            self.pages_view.selected_pages(),
            document.page_label if document.has_page_labels else None,
        )
        dialog.connect("add-requested", lambda _dialog, choice: self.add_pages(choice))
        dialog.present(self)

    def add_pages(self, choice: PagesToAdd) -> None:
        """Add the pages chosen in the dialogue and go to the first of them; say so, or why they cannot be added."""
        document = self.document
        if document is None:
            return
        source = choice.source
        try:
            added = (
                document.add_blank_page(source)
                if isinstance(source, PaperSize)
                else document.add_source(source, choice.password)
            )
        except AssemblyNotAllowedError:
            message = _("The user access permissions of “{name}” do not allow adding its pages")
            self._show_message(message.format(name=source.name))
            return
        except DocumentOpenError:
            self._show_message(_("Could not open “{name}”").format(name=source.name))
            return
        command = AddPages(document, added, choice.position)
        document.execute(command)
        self.document_view.go_to(choice.position)
        count = len(added.pages)
        if isinstance(source, PaperSize):
            message = _("Blank page added")
        else:
            message = ngettext("{count} page added", "{count} pages added", count)
        self._show_edit_toast(Adw.Toast(title=message.format(count=count)), command)

    def _open_extract_pages_dialog(self) -> None:
        """Ask which pages to extract and how, starting with the selected ones (E7, E8)."""
        if self.document is None:
            return
        dialog = PenfoldExtractPagesDialog(
            self.document.page_count,
            self.pages_view.selected_pages(),
            has_page_labels=self.document.has_page_labels,
        )
        dialog.connect("extract-requested", lambda _dialog, request: self.extract_pages(request))
        dialog.present(self)

    def extract_pages(self, request: PagesToExtract) -> None:
        """Extract the pages chosen into a folder; then say so, and delete them if asked, with Undo (E8, E9)."""
        document = self.document
        if document is None:
            return
        # The pages to delete after, by source index: the document may change while the files are written.
        sources = [document.pages[position].source_index for position in request.positions]

        def finished(extracted: bool) -> None:
            if extracted and document is self.document:
                self._after_extracting(document, request, sources)

        PageExtraction(self, document, request, finished).start()

    def _after_extracting(self, document: OpenDocument, request: PagesToExtract, sources: list[int]) -> None:
        count = len(request.positions)
        if request.separate:
            message = ngettext(
                "{count} page extracted into its own file", "{count} pages extracted, one file each", count
            )
        else:
            message = ngettext("{count} page extracted", "{count} pages extracted", count)
        positions = [position for source in sources if (position := document.page_position(source)) is not None]
        if not request.delete_after or not positions or len(positions) == document.page_count:
            self.toast_overlay.add_toast(Adw.Toast(title=message.format(count=count)))
            return
        command = DeletePages(document, positions)
        document.execute(command)
        deleted = ngettext("{count} page extracted and deleted", "{count} pages extracted and deleted", count)
        self._show_undo_toast(deleted.format(count=count), command)

    def _show_undo_toast(self, title: str, command: Command) -> None:
        """Show a notice with Undo for an edit."""
        toast = Adw.Toast(title=title, button_label=_("_Undo"))

        def undo(_toast: Adw.Toast) -> None:
            if self.document is not None and self.document.last_edit is command:
                self.document.undo()

        toast.connect("button-clicked", undo)
        self._show_edit_toast(toast, command)

    def _show_edit_toast(self, toast: Adw.Toast, command: Command) -> None:
        """Show a notice about an edit; it goes away as soon as the edit is no longer the last one (D76)."""

        def forget(dismissed: Adw.Toast) -> None:
            if self._edit_toast is not None and self._edit_toast[0] is dismissed:
                self._edit_toast = None

        toast.connect("dismissed", forget)
        self._edit_toast = (toast, command)
        self.toast_overlay.add_toast(toast)

    def _dismiss_stale_edit_toast(self) -> None:
        """Take away the notice about an edit once that edit was undone or another one came after it."""
        if self._edit_toast is None:
            return
        toast, command = self._edit_toast
        if self.document is None or self.document.last_edit is not command:
            self._edit_toast = None
            toast.dismiss()

    # Saving (J1).

    def save(self, then: Callable[[bool], object] | None = None) -> None:
        """Save over the document's file, in the background; then says whether it was saved.

        A new document (merged) has no file yet: it is saved as Save As does (F6).
        """
        if self.document is not None and self.document.is_new:
            self.save_as(then)
        elif self.document is not None:
            self._write(self.document.save_plan(), then)

    def save_as(self, then: Callable[[bool], object] | None = None) -> None:
        """Choose a file and save the document there; it becomes the document's file (J1).

        Asked by the user (without then) for a document with a form, it first asks whether to flatten it (I6), if the
        PDF allows changing its content (D59).
        """
        if self.document is None:
            return
        if then is None and self.document.form_fields and self.document.permissions.modify:
            dialog = PenfoldSaveAsDialog()
            dialog.connect("continue-requested", lambda _dialog, flatten: self._choose_target(None, flatten=flatten))
            dialog.present(self)
        else:
            self._choose_target(then, flatten=False)

    def _choose_target(self, then: Callable[[bool], object] | None, *, flatten: bool) -> None:
        """Choose where to save; a flattened copy is proposed as "name_flattened.pdf", as in 0.6."""
        if self.document is None:
            return
        path = self.document.path
        if flatten:
            path = path.with_name(path.stem + _("_flattened.pdf"))
        dialog = pdf_file_dialog(_("Save As"), Gio.File.new_for_path(str(path)))
        dialog.save(self, None, self._on_save_as_chosen, (then, flatten))

    def _on_save_as_chosen(
        self,
        dialog: Gtk.FileDialog,
        result: Gio.AsyncResult,
        request: tuple[Callable[[bool], object] | None, bool],
    ) -> None:
        then, flatten = request
        try:
            file = dialog.save_finish(result)
        except GLib.Error:
            file = None  # Cancelled.
        path = file.get_path() if file is not None else None
        if self.document is None or path is None:
            if then is not None:
                then(False)
            return
        self._write(self.document.save_plan(Path(path), flatten=flatten), then)

    def _print_shortcut(self) -> None:
        """Ctrl+P prints; in a PDF that does not allow it, where Print is greyed out, it says so (K3, D59)."""
        if self.document is not None and not self.document.permissions.print:
            self.toast_overlay.add_toast(Adw.Toast(title=_("This PDF does not allow printing")))
        else:
            self.activate_action("win.print", None)

    def _open_print_dialog(self) -> None:
        """Ask which annotations to print, then print with the system's dialogue (D57)."""
        document = self.document
        if document is None:
            return
        dialog = PenfoldPrintDialog()
        printing = DocumentPrinting(self, document, self._show_message)
        dialog.connect("print-requested", lambda _dialog, left_out: printing.start(left_out))
        dialog.present(self)

    def _write(self, plan: SavePlan, then: Callable[[bool], object] | None) -> None:
        """Write a plan in a worker thread, keeping the window responsive; report how it went in the main thread."""
        document = self.document
        self._saving = True
        self._update_save_actions()

        def work() -> None:
            try:
                failed = save(plan)
            except SaveError:
                logger.exception("Could not save %s", plan.target)
                GLib.idle_add(finish, False, 0)
            else:
                GLib.idle_add(finish, True, failed)

        def finish(saved: bool, failed_fields: int) -> bool:
            self._saving = False
            if failed_fields:
                # A field that fails does not stop the save, but the reader must know (I5).
                message = ngettext(
                    "The value of {count} form field could not be saved",
                    "The values of {count} form fields could not be saved",
                    failed_fields,
                )
                self.toast_overlay.add_toast(Adw.Toast(title=message.format(count=failed_fields)))
            if document is not None and document is self.document:
                if saved and plan.flatten:
                    # An exported copy: the document keeps its file and its changes (I6).
                    message = _("Flattened copy saved as “{name}”").format(name=plan.target.name)
                    self.toast_overlay.add_toast(Adw.Toast(title=message))
                elif saved:
                    document.mark_saved(plan)
                else:
                    self._show_message(_("Could not save “{name}”").format(name=plan.target.name))
            self._update_save_actions()
            if then is not None:
                then(saved)
            return GLib.SOURCE_REMOVE

        threading.Thread(target=work, name="penfold-save", daemon=True).start()

    def _update_save_actions(self) -> None:
        """Save while not saving; a PDF with permissions too, keeping them. Print only if the PDF allows it (D59)."""
        document = self.document
        enabled = document is not None and not self._saving
        for name in SAVE_ACTIONS:
            allowed = name != "print" or (document is not None and document.permissions.print)
            self._enable_action(name, enabled and allowed)

    def _show_title(self) -> None:
        """The document's title and file name in the header, and in the window's title, with "• " for changes."""
        document = self.document
        if document is None:
            self.set_title("Penfold")
            return
        self.document_header.show_document(document)
        mark = UNSAVED_MARK if document.is_modified else ""
        self.set_title(mark + _("{file_name} — Penfold").format(file_name=document.file_name))

    def _on_layout_changed(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        action.set_state(value)
        self.document_view.set_two_pages(value.get_string() == LAYOUT_TWO_PAGES)

    def _set_document_actions_enabled(self, enabled: bool) -> None:
        for name in [*DOCUMENT_ACTIONS, "layout"]:
            self._enable_action(name, enabled)
        self._update_zoom_actions()
        self._update_edit_actions()
        self._update_page_actions()
        self.bookmark_editing.update_actions()
        self.annotating.update_actions()
        self._update_save_actions()

    def _on_annotation_toolbar_shown(self, toolbar: AnnotationToolbar, _property: GObject.ParamSpec) -> None:
        """While the annotation bar is shown, the toasts rise above it (D32)."""
        if toolbar.get_visible():
            self.toast_overlay.add_css_class("annotation-bar-shown")
        else:
            self.toast_overlay.remove_css_class("annotation-bar-shown")

    def _place_annotation_toolbar(self, overlay: Gtk.Overlay, child: Gtk.Widget, area: Gdk.Rectangle) -> bool:
        """Put the annotation bar at the bottom of the document, centred, left of the zoom buttons (D32)."""
        if child is not self.annotation_toolbar:
            return False
        _minimum, natural = child.get_preferred_size()
        area.width, area.height = natural.width, natural.height
        area.x = bar_position(overlay.get_width(), natural.width)
        area.y = overlay.get_height() - natural.height - child.get_margin_bottom()
        return True

    def _update_zoom_actions(self) -> None:
        for name, enabled in (
            ("zoom-in", self.document_view.can_zoom_in),
            ("zoom-out", self.document_view.can_zoom_out),
        ):
            self._enable_action(name, enabled)

    # Side panel.

    def _set_up_sidebar(self) -> None:
        """F9 shows or hides the panel; its width is remembered; the main menu ☰ follows it (D36)."""
        self.add_action(Gio.PropertyAction.new("show-sidebar", self.split_view, "show-sidebar"))
        self.split_view.bind_property(
            "show-sidebar",
            self.document_header.main_menu_button,
            "visible",
            GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.INVERT_BOOLEAN,
        )
        self._chosen_sidebar_width = clamp_width(self._settings.get_int("sidebar-width"))
        self._fit_sidebar_width()
        # The window's new width is known as soon as it is asked for (default-width); maximized and full-screen
        # windows get theirs from the screen, once they are laid out.
        self.connect("notify::default-width", lambda _window, _property: self._fit_sidebar_width())
        for size_property in ("notify::maximized", "notify::fullscreened"):
            self.connect(size_property, lambda _window, _property: GLib.idle_add(self._fit_sidebar_width))
        self.sidebar.connect("resize-started", lambda _sidebar: self.document_view.defer_fit(True))
        self.sidebar.connect("resized", self._on_sidebar_resized)
        self.sidebar.connect("resize-finished", self._on_sidebar_resize_finished)
        self.pages_view = PagesView()
        self.pages_view.connect("page-activated", lambda _view, page: self.document_view.go_to(page))
        self.pages_view.selection.connect("selection-changed", lambda *_arguments: self._update_page_actions())
        self.pages_view.connect("move-requested", self._on_move_requested)
        self.sidebar.add_view(sidebar_views.PAGES, self.pages_view)
        self.bookmarks_view = BookmarksView()
        self.bookmarks_view.connect("destination-activated", self._on_destination_activated)
        self.sidebar.add_view(sidebar_views.BOOKMARKS, self.bookmarks_view)
        self.bookmark_editing = BookmarkEditing(
            self, self.bookmarks_view, self.document_view, lambda: self.document, self._show_undo_toast
        )
        self.annotation_toolbar = AnnotationToolbar()
        self.document_overlay.add_overlay(self.annotation_toolbar)
        self.document_overlay.connect("get-child-position", self._place_annotation_toolbar)
        self.annotation_toolbar.connect("notify::visible", self._on_annotation_toolbar_shown)
        self.annotating = Annotating(
            self,
            self.annotation_toolbar,
            self.document_view,
            lambda: self.document,
            lambda: self._settings.get_string(AUTHOR_NAME_KEY),
        )
        self.annotation_editing = AnnotationEditing(
            self, self.document_view, lambda: self.document, self._show_undo_toast
        )
        self.annotations_view = AnnotationsView()
        self.annotations_view.connect("annotation-activated", self._on_destination_activated)
        self.annotations_view.connect("menu-requested", self._on_annotation_menu_requested)
        self.sidebar.add_view(sidebar_views.ANNOTATIONS, self.annotations_view)
        self.search_view = SearchView()
        self.search_view.connect("result-chosen", self._on_result_chosen)
        self.search_view.connect("results-added", self._on_results_added)
        self.search_view.connect("results-cleared", lambda _view: self.document_view.clear_matches())
        self.search_view.connect("close-requested", lambda _view: self.close_find())
        self.sidebar.add_view(sidebar_views.SEARCH, self.search_view)
        self.sidebar.connect("view-changed", self._on_sidebar_view_changed)
        escape = Gtk.EventControllerKey()
        escape.connect("key-pressed", self._on_key_pressed)
        self.add_controller(escape)

    def _on_sidebar_resized(self, _sidebar: PenfoldSidebar, width: int) -> None:
        self._chosen_sidebar_width = min(clamp_width(width), self._widest_sidebar())
        self._fit_sidebar_width()

    def _widest_sidebar(self) -> int:
        """The widest the panel can be in this window: the document keeps the room its header needs (as in 0.6)."""
        content = self.split_view.get_content()
        document_minimum = content.measure(Gtk.Orientation.HORIZONTAL, -1)[0] if content is not None else 0
        free = not (self.is_maximized() or self.is_fullscreen())
        window_width = self.get_default_size()[0] if free else self.get_width()
        return clamp_width(window_width - document_minimum - DOCUMENT_ROOM)

    def _fit_sidebar_width(self) -> bool:
        """Give the panel the width chosen, or less if the window is too narrow for it (it is not forgotten)."""
        width = min(self._chosen_sidebar_width, self._widest_sidebar())
        self.split_view.set_min_sidebar_width(width)
        self.split_view.set_max_sidebar_width(width)
        return GLib.SOURCE_REMOVE

    # Find (D13).

    def open_find(self) -> None:
        """Show the panel with Find and put the cursor in its box (Ctrl+F)."""
        self.split_view.set_show_sidebar(True)
        self.sidebar.show_view(sidebar_views.SEARCH)
        self.search_view.focus()

    def close_find(self) -> None:
        """Go back to the view Find covered (Esc) and to the document."""
        self.sidebar.close_search()
        self.document_view.grab_focus()

    def _find_step(self, direction: int) -> None:
        """Ctrl+G and Shift+Ctrl+G: the next or previous match; they open Find if it is closed."""
        if self.sidebar.visible_view != sidebar_views.SEARCH or not self.split_view.get_show_sidebar():
            self.open_find()
            return
        self.search_view.current_page = self.document_view.current_page
        if direction > 0:
            self.search_view.next_result()
        else:
            self.search_view.previous_result()

    def _on_result_chosen(self, view: SearchView, index: int) -> None:
        result = view.result_list[index]
        self.document_view.go_to(result.page, result.top)
        self.document_view.set_current_match(result)

    def _on_results_added(self, view: SearchView) -> None:
        if self.sidebar.visible_view == sidebar_views.SEARCH:
            self.document_view.add_matches(view.last_added)

    def _on_sidebar_view_changed(self, sidebar: PenfoldSidebar) -> None:
        """Matches are highlighted while Find is shown."""
        self.document_view.clear_matches()
        if sidebar.visible_view == sidebar_views.SEARCH:
            self.search_view.current_page = self.document_view.current_page
            self.search_view.focus()
            self.document_view.add_matches(self.search_view.result_list)
            current = self.search_view.current
            if 0 <= current < len(self.search_view.result_list):
                self.document_view.set_current_match(self.search_view.result_list[current])

    def _on_key_pressed(
        self, _controller: Gtk.EventControllerKey, keyval: int, _keycode: int, _state: Gdk.ModifierType
    ) -> bool:
        """Esc, when nothing in the window used the key before (a menu, a dialogue…), does the first that applies.

        It closes Find, or else clears the selection of the panel view shown (D47), or else goes back to the tool
        Select Text (02-interfaz, 5; H8).
        """
        if keyval != Gdk.KEY_Escape:
            return False
        if self.sidebar.visible_view == sidebar_views.SEARCH:
            self.close_find()
            return True
        if self._unselect_panel_view():
            return True
        if self.annotating.tool is not Tool.SELECT:
            self.annotating.choose(Tool.SELECT)
            return True
        return False

    def _on_annotation_menu_requested(self, view: AnnotationsView, annotation: Annotation, x: float, y: float) -> None:
        """The menu of an annotation of the panel, at its row; the document goes to it first, as a click does."""
        if self.renderer is not None:
            place = self.renderer.layout.place(annotation.page, annotation.rectangle[1])
            if place is not None:
                page, top = place
                self._on_destination_activated(view, page, -1.0 if top is None else top)
        self.annotation_editing.open_menu(annotation, x, y, view)

    def _unselect_panel_view(self) -> bool:
        """Clear the selection of Pages, Bookmarks or Annotations, if shown; return whether anything was selected."""
        if not self.split_view.get_show_sidebar():
            return False
        views: dict[str, PagesView | BookmarksView | AnnotationsView] = {
            sidebar_views.PAGES: self.pages_view,
            sidebar_views.BOOKMARKS: self.bookmarks_view,
            sidebar_views.ANNOTATIONS: self.annotations_view,
        }
        view = views.get(self.sidebar.visible_view)
        return view is not None and view.unselect_all()

    def _on_sidebar_resize_finished(self, _sidebar: PenfoldSidebar) -> None:
        """The zoom is fitted once, when the border is released, not while dragging (B4)."""
        self.document_view.defer_fit(False)
        self._settings.set_int("sidebar-width", self._chosen_sidebar_width)

    # Opening.

    def open_file(self, path: Path) -> bool:
        """Show a PDF in this window and return True; if it cannot be opened, say so and keep what was shown.

        A PDF that needs a password is shown once it is typed (D61): False until then.
        """
        try:
            document = OpenDocument.open(path)
        except PasswordRequiredError:
            self._ask_password(path)
            return False
        except DocumentOpenError as error:
            self._cannot_open(path, error)
            return False
        return self._show_document(document)

    def _ask_password(self, path: Path) -> None:
        """Ask for the password of a PDF until it opens it, or until Cancel (D61, 4)."""

        def try_password(password: str) -> bool:
            try:
                document = OpenDocument.open(path, password)
            except PasswordRequiredError:
                return False
            except DocumentOpenError as error:
                self._cannot_open(path, error)
                return True
            self._show_document(document)
            return True

        password_question(path.name, try_password).present(self)

    def _cannot_open(self, path: Path, error: DocumentOpenError) -> None:
        logger.warning("Could not open %s (%s)", path, type(error).__name__)
        self._show_message(_("Could not open “{name}”").format(name=path.name))

    def merge_files(self, paths: list[Path]) -> None:
        """Open Merge PDFs, with these files in the list, asking first about unsaved changes (F5, J4, D17)."""

        def open_dialog(proceed: bool) -> None:
            if not proceed:
                return
            dialog = PenfoldMergeDialog()
            dialog.add_files(paths)
            dialog.connect("merge-requested", lambda _dialog, request: self.merge(request))
            dialog.present(self)

        self.confirm_discard(open_dialog)

    def merge(self, request: PdfsToMerge) -> None:
        """Show the merged PDFs, unsaved, with its bookmarks in sight (F2, F6); say so, or why they cannot be merged."""
        proposed = request.paths[0].parent / _("merged.pdf")
        try:
            document = OpenDocument.merge(
                request.files,
                proposed,
                bookmark_per_file=request.bookmark_per_file,
                keep_bookmarks=request.keep_bookmarks,
                respect_permissions=self._settings.get_boolean(RESPECT_PERMISSIONS_KEY),
            )
        except PenfoldError as error:
            logger.warning("Could not merge (%s)", type(error).__name__)
            self._show_message(_("Could not merge the PDFs"))
            return
        if self._show_document(document):
            self.sidebar.show_view(sidebar_views.BOOKMARKS)
            count = document.page_count
            self.toast_overlay.add_toast(
                Adw.Toast(
                    title=ngettext("PDFs merged: {count} page", "PDFs merged: {count} pages", count).format(count=count)
                )
            )

    def _show_document(self, document: OpenDocument) -> bool:
        """Show a document in this window, instead of the one shown, and return True; False if it cannot be drawn."""
        try:
            renderer = Renderer(document.sources.spans)
        except GLib.Error:
            logger.warning("Poppler could not open %s", document.path)
            self._show_message(_("Could not open “{name}”").format(name=document.file_name))
            document.close()
            return False
        self._close_document()
        self.document, self.renderer = document, renderer
        document.respect_permissions(self._settings.get_boolean(RESPECT_PERMISSIONS_KEY))
        document.add_listener(self._on_document_changed)
        self._grow_for_document()
        self._show_title()
        self.stack.set_visible_child_name("document")
        # The panel opens by itself when a PDF is loaded, as in 0.6, once the window has grown to make room for it.
        self._show_sidebar_when_it_fits()
        self.document_view.set_document(document, renderer)
        self.pages_view.set_document(document, renderer)
        self.bookmarks_view.set_document(document, renderer)
        assert self.document_view.content is not None
        self.annotations_view.set_document(document, self.document_view.content, renderer)
        self.search_view.set_document(
            lambda: renderer.sources,
            lambda: renderer.layout,
            document.page_label,
            ContextReader(renderer.poppler).context,
        )
        self.sidebar.close_search()
        self._set_document_actions_enabled(True)
        self.document_view.grab_focus()
        return True

    def _on_document_changed(self, changes: Change) -> None:
        """Show what an edit, an undo or a redo changed."""
        if self.document is None or self.renderer is None:
            return
        self._update_edit_actions()
        self._dismiss_stale_edit_toast()
        self._show_title()
        if Change.PAGES in changes:
            self._update_page_actions()
            self.renderer.set_pages(self.document.pages, self.document.sources.spans)
            self.document_view.pages_changed()
            self.pages_view.pages_changed()
            self.search_view.pages_changed()
            self.annotations_view.pages_changed()
            self.bookmarks_view.pages_changed()
        if Change.ANNOTATIONS in changes:
            self.renderer.hide_annotations(self.document.replaced_annotations)
            self.annotations_view.annotations_changed()
            self.document_view.annotations_changed()
        if Change.BOOKMARKS in changes:
            self.bookmarks_view.bookmarks_changed()
            self.bookmark_editing.update_actions()
        if Change.FORM in changes:
            self.document_view.form_changed()
        if Change.PERMISSIONS in changes:
            self._update_page_actions()
            self._update_save_actions()
            self.bookmark_editing.update_actions()
            self.annotating.update_actions()
            self.document_view.permissions_changed()

    def _on_respect_permissions_changed(self, settings: Gio.Settings, key: str) -> None:
        """Turning "Respect Document Permissions" on or off applies at once (D60): the lock and the tools follow."""
        if self.document is not None:
            self.document.respect_permissions(settings.get_boolean(key))

    def _show_sidebar_when_it_fits(self) -> None:
        """Show the panel as soon as the window is wide enough for it and the document (or after half a second).

        A window that grows from the small welcome size takes a moment to do so; showing the panel before would ask
        for more room than the window has.
        """
        if self.split_view.get_show_sidebar():
            return
        started = GLib.get_monotonic_time()

        def check(_widget: Gtk.Widget, _clock: Gdk.FrameClock) -> bool:
            content = self.split_view.get_content()
            needed = self.split_view.get_max_sidebar_width() + (
                content.measure(Gtk.Orientation.HORIZONTAL, -1)[0] if content is not None else 0
            )
            waited = GLib.get_monotonic_time() - started > SIDEBAR_WAIT_MICROSECONDS
            if self.get_width() >= needed or self.split_view.get_collapsed() or waited:
                self.split_view.set_show_sidebar(True)
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE

        self.add_tick_callback(check)

    def _close_document(self) -> None:
        if self.renderer is not None:
            self.renderer.close()
        if self.document is not None:
            self.document.close()
        self.document, self.renderer = None, None

    def _show_message(self, heading: str, body: str = "") -> None:
        # A single button answers both Enter and Esc, as GNOME's guidelines say.
        dialog = Adw.AlertDialog(heading=heading, body=body, default_response="ok", close_response="ok")
        dialog.add_response("ok", _("_OK"))
        dialog.present(self)

    def _on_drop(self, _target: Gtk.DropTarget, value: Gdk.FileList, _x: float, _y: float) -> bool:
        """A PDF dropped on the window opens in it, asking first about unsaved changes (A5, J4).

        Several at once open Merge PDFs with them in the list (D17).
        """
        paths = [Path(path) for file in value.get_files() if (path := file.get_path()) is not None]
        if len(paths) > 1:
            self.merge_files(paths)
        elif paths:
            self.confirm_discard(lambda proceed: proceed and self.open_file(paths[0]))
        return bool(paths)

    # Unsaved changes (J4, J5).

    def confirm_discard(self, then: Callable[[bool], object]) -> None:
        """Before the document is replaced or closed, ask what to do with unsaved changes; then says whether to go on.

        Without unsaved changes nothing is asked. Save saves (asking where if it has to) and goes on only if it was
        saved; Discard goes on; Cancel, or closing the question, does not (D16, 0.6).
        """
        document = self.document
        if document is None or not document.is_modified:
            then(True)
            return
        dialog = _save_question(document.file_name)
        dialog.connect("response", self._on_unsaved_response, then)
        self.present()
        dialog.present(self)

    def _on_unsaved_response(self, dialog: Adw.AlertDialog, response: str, then: Callable[[bool], object]) -> None:
        # Closing the question answers again with the close response: only the first answer counts.
        dialog.disconnect_by_func(self._on_unsaved_response)
        if response == RESPONSE_SAVE:
            self.save(then)
        else:
            then(response == RESPONSE_DISCARD)

    def close_after_asking(self, then: Callable[[bool], object] | None = None) -> None:
        """Close the window, asking first about unsaved changes; then says whether it closed (Ctrl+Q, A8)."""

        def close(proceed: bool) -> None:
            if proceed:
                self._close_confirmed = True
                # The window refuses to close while the question is still on it: close once it has gone.
                question = self.get_visible_dialog()
                if question is None:
                    self.close()
                else:
                    question.connect("closed", lambda _question: self.close())
            if then is not None:
                then(proceed)

        self.confirm_discard(close)

    # Window size (D17): small without a document; with one, the size it had the last time.

    def _grow_for_document(self) -> None:
        if self.document is not None and self.stack.get_visible_child_name() == "document":
            return
        settings = self._settings
        if settings.get_boolean("window-maximized"):
            self.maximize()
        else:
            self.set_default_size(settings.get_int("window-width"), settings.get_int("window-height"))

    def _remember_size(self) -> None:
        if self.stack.get_visible_child_name() != "document":
            return
        settings = self._settings
        settings.set_boolean("window-maximized", self.is_maximized())
        if not self.is_maximized():
            width, height = self.get_default_size()
            settings.set_int("window-width", width)
            settings.set_int("window-height", height)

    def _on_close_request(self, _window: Gtk.Window) -> bool:
        """Closing the window (Ctrl+W, its button) asks first about unsaved changes (A8).

        What is being edited on a page counts: it is accepted first.
        """
        self.document_view.finish_editing()
        if not self._close_confirmed and self.document is not None and self.document.is_modified:
            self.close_after_asking()
            return True
        self._remember_size()
        self._close_document()
        return False

    # Following the view.

    def _on_current_page_changed(self, view: DocumentView) -> None:
        if self.document is not None:
            self.document_header.page_entry.show_page(self.document, view.current_page)
            self.pages_view.show_current_page(view.current_page)
            self.annotations_view.show_reading_page(view.current_page)

    def _on_zoom_changed(self, view: DocumentView) -> None:
        self.zoom_controls.show_fit(view.fit)
        self._update_zoom_actions()

    def _on_destination_activated(self, _view: Gtk.Widget, page: int, top: float) -> None:
        """Go to a destination from the panel, with its height on the top third (B8); -1 means no height."""
        self.document_view.go_to(page, None if top < 0 else top)

    def _on_viewport_changed(self, view: DocumentView) -> None:
        """The panel follows the reading: the part shown on the thumbnails (D41)."""
        self.pages_view.show_visible_areas(view.visible_areas())
        self.bookmarks_view.follow(*view.reading_point())

    def _on_page_chosen(self, _entry: Gtk.Widget, page: int) -> None:
        self.document_view.go_to(page)
        self.document_view.grab_focus()


def _save_question(name: str) -> Adw.AlertDialog:
    """Save, discard or keep the unsaved changes of a document (J5)."""
    dialog = Adw.AlertDialog(
        heading=_("Save changes to “{name}”?").format(name=name),
        body=_("If you don’t save, your changes will be lost."),
        close_response=RESPONSE_CANCEL,
        default_response=RESPONSE_SAVE,
    )
    dialog.add_response(RESPONSE_CANCEL, _("_Cancel"))
    dialog.add_response(RESPONSE_DISCARD, _("_Discard"))
    dialog.add_response(RESPONSE_SAVE, _("_Save"))
    dialog.set_response_appearance(RESPONSE_DISCARD, Adw.ResponseAppearance.DESTRUCTIVE)
    dialog.set_response_appearance(RESPONSE_SAVE, Adw.ResponseAppearance.SUGGESTED)
    return dialog
