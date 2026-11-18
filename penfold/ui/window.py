"""The main window: the welcome page, or a PDF with its header and zoom buttons."""

import logging
from gettext import gettext as _
from pathlib import Path

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

from penfold import config
from penfold.document.document import OpenDocument
from penfold.errors import DocumentOpenError
from penfold.rendering.renderer import Renderer

# The template uses these widgets by name: importing them also registers their types with GTK.
from penfold.ui.document_header import PenfoldDocumentHeader
from penfold.ui.document_view import DocumentView
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
WINDOW_ACCELERATORS = {
    "win.close": ["<Control>w"],
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
    document_view: DocumentView = Gtk.Template.Child()
    zoom_controls: PenfoldZoomControls = Gtk.Template.Child()

    def __init__(self, application: Gtk.Application) -> None:
        """Create a window of the application, showing the welcome page."""
        super().__init__(application=application)
        self.document: OpenDocument | None = None
        self.renderer: Renderer | None = None
        self.welcome_menu_button.set_menu_model(main_menu())
        self._add_actions()
        self.document_view.connect("current-page-changed", self._on_current_page_changed)
        self.document_view.connect("zoom-changed", self._on_zoom_changed)
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
        layout = Gio.SimpleAction.new_stateful(
            "layout", GLib.VariantType.new("s"), GLib.Variant.new_string(LAYOUT_CONTINUOUS)
        )
        layout.set_enabled(False)
        layout.connect("change-state", self._on_layout_changed)
        self.add_action(layout)

    def _on_document_action(self, _action: Gio.SimpleAction, _parameter: None, name: str, handler: object) -> None:
        if name in KEYS_WITHOUT_CONTROL and isinstance(self.get_focus(), Gtk.Editable | Gtk.Text):
            return
        assert callable(handler)
        handler()

    def _on_layout_changed(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        action.set_state(value)
        self.document_view.set_two_pages(value.get_string() == LAYOUT_TWO_PAGES)

    def _set_document_actions_enabled(self, enabled: bool) -> None:
        for name in [*DOCUMENT_ACTIONS, "layout"]:
            action = self.lookup_action(name)
            assert isinstance(action, Gio.SimpleAction)
            action.set_enabled(enabled)
        self._update_zoom_actions()

    def _update_zoom_actions(self) -> None:
        for name, enabled in (
            ("zoom-in", self.document_view.can_zoom_in),
            ("zoom-out", self.document_view.can_zoom_out),
        ):
            action = self.lookup_action(name)
            assert isinstance(action, Gio.SimpleAction)
            action.set_enabled(enabled)

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
        self._set_sidebar_width(self._settings().get_int("sidebar-width"))
        self.sidebar.connect("resize-started", lambda _sidebar: self.document_view.defer_fit(True))
        self.sidebar.connect("resized", lambda _sidebar, width: self._set_sidebar_width(width))
        self.sidebar.connect("resize-finished", self._on_sidebar_resize_finished)
        self.pages_view = PagesView()
        self.pages_view.connect("page-activated", lambda _view, page: self.document_view.go_to(page))
        self.sidebar.add_view(sidebar_views.PAGES, self.pages_view)
        self.bookmarks_view = BookmarksView()
        self.bookmarks_view.connect("destination-activated", self._on_destination_activated)
        self.sidebar.add_view(sidebar_views.BOOKMARKS, self.bookmarks_view)
        self.annotations_view = AnnotationsView()
        self.annotations_view.connect("annotation-activated", self._on_destination_activated)
        self.sidebar.add_view(sidebar_views.ANNOTATIONS, self.annotations_view)
        self.search_view = SearchView()
        self.search_view.connect("result-chosen", self._on_result_chosen)
        self.search_view.connect("results-changed", lambda _view: self._show_matches())
        self.search_view.connect("close-requested", lambda _view: self.close_find())
        self.sidebar.add_view(sidebar_views.SEARCH, self.search_view)
        self.sidebar.connect("view-changed", self._on_sidebar_view_changed)
        escape = Gtk.EventControllerKey()
        escape.connect("key-pressed", self._on_key_pressed)
        self.add_controller(escape)

    def _set_sidebar_width(self, width: int) -> None:
        width = clamp_width(width)
        self.split_view.set_min_sidebar_width(width)
        self.split_view.set_max_sidebar_width(width)

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
        self._show_matches()

    def _show_matches(self) -> None:
        searching = self.sidebar.visible_view == sidebar_views.SEARCH
        results = self.search_view.result_list if searching else []
        self.document_view.show_matches(results, self.search_view.current)

    def _on_sidebar_view_changed(self, sidebar: PenfoldSidebar) -> None:
        if sidebar.visible_view == sidebar_views.SEARCH:
            self.search_view.current_page = self.document_view.current_page
            self.search_view.focus()
        self._show_matches()

    def _on_key_pressed(
        self, _controller: Gtk.EventControllerKey, keyval: int, _keycode: int, _state: Gdk.ModifierType
    ) -> bool:
        """Esc closes Find, when nothing in the window used the key before (a menu, a dialogue…)."""
        if keyval == Gdk.KEY_Escape and self.sidebar.visible_view == sidebar_views.SEARCH:
            self.close_find()
            return True
        return False

    def _on_sidebar_resize_finished(self, _sidebar: PenfoldSidebar) -> None:
        """The zoom is fitted once, when the border is released, not while dragging (B4)."""
        self.document_view.defer_fit(False)
        self._settings().set_int("sidebar-width", round(self.split_view.get_max_sidebar_width()))

    # Opening.

    def open_file(self, path: Path) -> bool:
        """Show a PDF in this window and return True; if it cannot be opened, say so and keep what was shown."""
        try:
            document = OpenDocument.open(path)
            renderer = Renderer(path)
        except (DocumentOpenError, GLib.Error) as error:
            logger.warning("Could not open %s (%s)", path, type(error).__name__)
            self._show_message(_("Could not open “{name}”").format(name=path.name))
            return False
        self._close_document()
        self.document, self.renderer = document, renderer
        self._grow_for_document()
        self.document_header.show_document(document)
        self.set_title(_("{file_name} — Penfold").format(file_name=document.file_name))
        self.protected_banner.set_revealed(document.is_protected)
        self.stack.set_visible_child_name("document")
        # The panel opens by itself when a PDF is loaded, as in 0.6.
        self.split_view.set_show_sidebar(True)
        self.document_view.set_document(document, renderer)
        self.pages_view.set_document(document, renderer)
        self.bookmarks_view.set_document(document)
        assert self.document_view.content is not None
        self.annotations_view.set_document(document, self.document_view.content)
        self.search_view.set_document(renderer.uri, document.page_label)
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
        """A PDF dropped on the window opens in it (A5); several at once will open Merge (phase 4)."""
        files = value.get_files()
        path = files[0].get_path() if len(files) == 1 else None
        return path is not None and self.open_file(Path(path))

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
        self._remember_size()
        self._close_document()
        return False

    # Following the view.

    def _on_current_page_changed(self, view: DocumentView) -> None:
        if self.document is not None:
            self.document_header.page_entry.show_page(self.document, view.current_page)
            self.pages_view.show_current_page(view.current_page)

    def _on_zoom_changed(self, view: DocumentView) -> None:
        self.zoom_controls.show_fit(view.fit)
        self._update_zoom_actions()

    def _on_destination_activated(self, _view: Gtk.Widget, page: int, top: float) -> None:
        """Go to a destination from the panel, with its height on the top third (B8); -1 means no height."""
        self.document_view.go_to(page, None if top < 0 else top)

    def _on_page_chosen(self, _entry: Gtk.Widget, page: int) -> None:
        self.document_view.go_to(page)
        self.document_view.grab_focus()
