"""The main window: the welcome page, or a PDF with its header and zoom buttons."""

import logging
import threading
from collections.abc import Callable
from gettext import gettext as _
from gettext import ngettext
from pathlib import Path

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

from penfold import config
from penfold.document.commands.pages import DeletePages, MovePages, RotatePages
from penfold.document.document import OpenDocument
from penfold.document.history import Change, Command
from penfold.document.saving import SavePlan, save
from penfold.errors import DocumentOpenError, SaveError
from penfold.rendering.renderer import Renderer
from penfold.rendering.text_search import ContextReader

# The template uses these widgets by name: importing them also registers their types with GTK.
from penfold.ui.document_header import UNSAVED_MARK, PenfoldDocumentHeader
from penfold.ui.document_view import DocumentView
from penfold.ui.file_dialogs import pdf_file_dialog
from penfold.ui.menus import main_menu
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
}
# Edits of the document; each is on only while there is something for it to do (D19, D21).
EDIT_ACTIONS = {
    "undo": ["<Control>z"],
    "redo": ["<Shift><Control>z"],
}
# Saving (J1): on while the document can be saved, which a protected PDF cannot (2.7), and not while saving.
SAVE_ACTIONS = {
    "save": ["<Control>s"],
    "save-as": ["<Shift><Control>s"],
}
# Answers to the question about unsaved changes (J5).
RESPONSE_CANCEL = "cancel"
RESPONSE_DISCARD = "discard"
RESPONSE_SAVE = "save"
QUARTER_TURN = 90
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
    protected_banner: Adw.Banner = Gtk.Template.Child()
    toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    document_view: DocumentView = Gtk.Template.Child()
    zoom_controls: PenfoldZoomControls = Gtk.Template.Child()

    def __init__(self, application: Gtk.Application) -> None:
        """Create a window of the application, showing the welcome page."""
        super().__init__(application=application)
        self.document: OpenDocument | None = None
        self.renderer: Renderer | None = None
        self._saving = False
        self._close_confirmed = False
        self._undo_toast: tuple[Adw.Toast, Command] | None = None
        self.welcome_menu_button.set_menu_model(main_menu())
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
            "delete-pages": self._delete_selected_pages,
            "save": self.save,
            "save-as": self.save_as,
        }
        for name, edit in editing.items():
            action = Gio.SimpleAction(name=name, enabled=False)
            action.connect("activate", lambda _action, _parameter, edit=edit: edit())
            self.add_action(action)
        self._add_delete_key()
        layout = Gio.SimpleAction.new_stateful(
            "layout", GLib.VariantType.new("s"), GLib.Variant.new_string(LAYOUT_CONTINUOUS)
        )
        layout.set_enabled(False)
        layout.connect("change-state", self._on_layout_changed)
        self.add_action(layout)

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
        """Undo or redo the last edit of the document; while typing in a field, its own text instead."""
        focus = self.get_focus()
        if isinstance(focus, Gtk.Text):
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
        """Let the Delete key delete what is selected in the panel (E3).

        It is handled after the focused widget, so that it still deletes text while typing in a field (L4).
        """
        controller = Gtk.ShortcutController(propagation_phase=Gtk.PropagationPhase.BUBBLE)
        controller.add_shortcut(
            Gtk.Shortcut(
                trigger=Gtk.ShortcutTrigger.parse_string("Delete"),
                action=Gtk.CallbackAction.new(self._on_delete_key),
            )
        )
        self.add_controller(controller)

    def _on_delete_key(self, _widget: Gtk.Widget, _arguments: GLib.Variant | None) -> bool:
        """Delete acts on the view of the panel shown, and never while a dialogue is open."""
        if self.get_visible_dialog() is not None or self.sidebar.visible_view != sidebar_views.PAGES:
            return False
        action = self.lookup_action("delete-pages")
        if action is None or not action.get_enabled():
            return False
        action.activate(None)
        return True

    def _update_page_actions(self) -> None:
        """Turning needs pages selected; deleting, too, and never all of them (E3, D21)."""
        selected = len(self.pages_view.selected_pages()) if self.document is not None else 0
        page_count = self.document.page_count if self.document is not None else 0
        for name, enabled in (
            ("rotate-pages-left", selected > 0),
            ("rotate-pages-right", selected > 0),
            ("delete-pages", 0 < selected < page_count),
        ):
            self._enable_action(name, enabled)

    def _rotate_selected_pages(self, degrees: int) -> None:
        if self.document is not None:
            self.document.execute(RotatePages(self.document, self.pages_view.selected_pages(), degrees))

    def _on_move_requested(self, _view: PagesView, positions: list[int], before: int) -> None:
        """Move dragged thumbnails (E1); dropping them where they already are changes nothing."""
        if self.document is None:
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

    def _show_undo_toast(self, title: str, command: Command) -> None:
        """Show a notice with Undo for an edit; it goes away as soon as the edit is no longer the last one."""
        toast = Adw.Toast(title=title, button_label=_("_Undo"))

        def undo(_toast: Adw.Toast) -> None:
            if self.document is not None and self.document.last_edit is command:
                self.document.undo()

        toast.connect("button-clicked", undo)
        toast.connect("dismissed", lambda _toast: setattr(self, "_undo_toast", None))
        self._undo_toast = (toast, command)
        self.toast_overlay.add_toast(toast)

    def _dismiss_stale_undo_toast(self) -> None:
        """Take away the notice to undo an edit once that edit was undone or another one came after it."""
        if self._undo_toast is None:
            return
        toast, command = self._undo_toast
        if self.document is None or self.document.last_edit is not command:
            self._undo_toast = None
            toast.dismiss()

    # Saving (J1).

    def save(self, then: Callable[[bool], object] | None = None) -> None:
        """Save over the document's file, in the background; then says whether it was saved."""
        if self.document is not None:
            self._write(self.document.save_plan(), then)

    def save_as(self, then: Callable[[bool], object] | None = None) -> None:
        """Choose a file and save the document there; it becomes the document's file (J1)."""
        if self.document is None:
            return
        dialog = pdf_file_dialog(_("Save As"), Gio.File.new_for_path(str(self.document.path)))
        dialog.save(self, None, self._on_save_as_chosen, then)

    def _on_save_as_chosen(
        self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, then: Callable[[bool], object] | None
    ) -> None:
        try:
            file = dialog.save_finish(result)
        except GLib.Error:
            file = None  # Cancelled.
        path = file.get_path() if file is not None else None
        if self.document is None or path is None:
            if then is not None:
                then(False)
            return
        self._write(self.document.save_plan(Path(path)), then)

    def _write(self, plan: SavePlan, then: Callable[[bool], object] | None) -> None:
        """Write a plan in a worker thread, keeping the window responsive; report how it went in the main thread."""
        document = self.document
        self._saving = True
        self._update_save_actions()

        def work() -> None:
            try:
                save(plan)
            except SaveError:
                logger.exception("Could not save %s", plan.target)
                GLib.idle_add(finish, False)
            else:
                GLib.idle_add(finish, True)

        def finish(saved: bool) -> bool:
            self._saving = False
            if document is not None and document is self.document:
                if saved:
                    document.mark_saved(plan)
                else:
                    self._show_message(_("Could not save “{name}”").format(name=plan.target.name))
            self._update_save_actions()
            if then is not None:
                then(saved)
            return GLib.SOURCE_REMOVE

        threading.Thread(target=work, name="penfold-save", daemon=True).start()

    def _update_save_actions(self) -> None:
        document = self.document
        enabled = document is not None and not document.is_protected and not self._saving
        for name in SAVE_ACTIONS:
            self._enable_action(name, enabled)

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
        self._update_save_actions()

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
        self._chosen_sidebar_width = clamp_width(self._settings().get_int("sidebar-width"))
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
        self.annotations_view = AnnotationsView()
        self.annotations_view.connect("annotation-activated", self._on_destination_activated)
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

        It closes Find, or else clears the selection of the panel view shown (02-interfaz, 5; D47).
        """
        if keyval != Gdk.KEY_Escape:
            return False
        if self.sidebar.visible_view == sidebar_views.SEARCH:
            self.close_find()
            return True
        return self._unselect_panel_view()

    def _unselect_panel_view(self) -> bool:
        """Clear the selection of Pages or Bookmarks, if shown; return whether anything was selected."""
        if not self.split_view.get_show_sidebar():
            return False
        views: dict[str, PagesView | BookmarksView] = {
            sidebar_views.PAGES: self.pages_view,
            sidebar_views.BOOKMARKS: self.bookmarks_view,
        }
        view = views.get(self.sidebar.visible_view)
        return view is not None and view.unselect_all()

    def _on_sidebar_resize_finished(self, _sidebar: PenfoldSidebar) -> None:
        """The zoom is fitted once, when the border is released, not while dragging (B4)."""
        self.document_view.defer_fit(False)
        self._settings().set_int("sidebar-width", self._chosen_sidebar_width)

    # Opening.

    def open_file(self, path: Path) -> bool:
        """Show a PDF in this window and return True; if it cannot be opened, say so and keep what was shown."""
        try:
            document = OpenDocument.open(path)
            renderer = Renderer(document.source_path)
        except (DocumentOpenError, GLib.Error) as error:
            logger.warning("Could not open %s (%s)", path, type(error).__name__)
            self._show_message(_("Could not open “{name}”").format(name=path.name))
            return False
        self._close_document()
        self.document, self.renderer = document, renderer
        document.add_listener(self._on_document_changed)
        self._grow_for_document()
        self._show_title()
        self.protected_banner.set_revealed(document.is_protected)
        self.stack.set_visible_child_name("document")
        # The panel opens by itself when a PDF is loaded, as in 0.6, once the window has grown to make room for it.
        self._show_sidebar_when_it_fits()
        self.document_view.set_document(document, renderer)
        self.pages_view.set_document(document, renderer)
        self.bookmarks_view.set_document(document, renderer)
        assert self.document_view.content is not None
        self.annotations_view.set_document(document, self.document_view.content, renderer)
        self.search_view.set_document(
            renderer.uri, lambda: renderer.layout, document.page_label, ContextReader(renderer.document).context
        )
        self.sidebar.close_search()
        self._set_document_actions_enabled(True)
        self.document_view.grab_focus()
        if document.is_protected:
            self._show_message(
                _("Protected PDF"),
                _(
                    "This PDF is protected. Any changes made to it cannot be saved. It cannot be printed and pages "
                    "cannot be extracted either."
                ),
            )
        return True

    def _on_document_changed(self, changes: Change) -> None:
        """Show what an edit, an undo or a redo changed."""
        if self.document is None or self.renderer is None:
            return
        self._update_edit_actions()
        self._dismiss_stale_undo_toast()
        self._show_title()
        if Change.PAGES in changes:
            self._update_page_actions()
            self.renderer.set_pages(self.document.pages)
            self.document_view.pages_changed()
            self.pages_view.pages_changed()
            self.search_view.pages_changed()
            self.annotations_view.pages_changed()
            self.bookmarks_view.pages_changed()
        if Change.BOOKMARKS in changes:
            self.bookmarks_view.bookmarks_changed()

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
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("ok", _("_OK"))
        dialog.present(self)

    def _on_drop(self, _target: Gtk.DropTarget, value: Gdk.FileList, _x: float, _y: float) -> bool:
        """A PDF dropped on the window opens in it, asking first about unsaved changes (A5, J4).

        Several at once will open Merge (phase 4).
        """
        files = value.get_files()
        path = files[0].get_path() if len(files) == 1 else None
        if path is None:
            return False
        self.confirm_discard(lambda proceed: proceed and self.open_file(Path(path)))
        return True

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
        dialog = Adw.AlertDialog(
            heading=_("Save changes to “{name}”?").format(name=document.file_name),
            body=_("If you don’t save, your changes will be lost."),
            close_response=RESPONSE_CANCEL,
            default_response=RESPONSE_SAVE,
        )
        dialog.add_response(RESPONSE_CANCEL, _("_Cancel"))
        dialog.add_response(RESPONSE_DISCARD, _("_Discard"))
        dialog.add_response(RESPONSE_SAVE, _("_Save"))
        dialog.set_response_appearance(RESPONSE_DISCARD, Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_response_appearance(RESPONSE_SAVE, Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", self._on_unsaved_response, then)
        self.present()
        dialog.present(self)

    def _on_unsaved_response(self, _dialog: Adw.AlertDialog, response: str, then: Callable[[bool], object]) -> None:
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
        settings = self._settings()
        if settings.get_boolean("window-maximized"):
            self.maximize()
        else:
            self.set_default_size(settings.get_int("window-width"), settings.get_int("window-height"))

    def _remember_size(self) -> None:
        if self.stack.get_visible_child_name() != "document":
            return
        settings = self._settings()
        settings.set_boolean("window-maximized", self.is_maximized())
        if not self.is_maximized():
            width, height = self.get_default_size()
            settings.set_int("window-width", width)
            settings.set_int("window-height", height)

    def _settings(self) -> Gio.Settings:
        return Gio.Settings(schema_id=config.APP_ID)

    def _on_close_request(self, _window: Gtk.Window) -> bool:
        """Closing the window (Ctrl+W, its button) asks first about unsaved changes (A8)."""
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
