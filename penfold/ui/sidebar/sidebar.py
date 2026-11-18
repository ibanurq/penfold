"""The side panel (02-interfaz, 2, 3.1 and 6): header, views and view switcher."""

from typing import ClassVar

from gi.repository import Adw, GObject, Graphene, Gtk

from penfold import config
from penfold.ui.menus import main_menu

PAGES = "pages"
BOOKMARKS = "bookmarks"
ANNOTATIONS = "annotations"
SEARCH = "search"
# Width limits, as in 0.6: wide enough for the Bookmarks header, and up to four columns of thumbnails.
MIN_WIDTH = 265
MAX_WIDTH = 1301


def clamp_width(width: float) -> int:
    """Keep a panel width between its limits."""
    return round(min(MAX_WIDTH, max(MIN_WIDTH, width)))


@Gtk.Template(resource_path=f"{config.RESOURCE_BASE_PATH}/ui/sidebar/sidebar.ui")
class PenfoldSidebar(Adw.Bin):
    """Pages, Bookmarks and Annotations, chosen at the bottom, and Find, opened with the magnifier.

    Dragging its right edge changes its width: "resize-started", "resized" (with the new width) and "resize-finished"
    let the window follow.
    """

    __gtype_name__ = "PenfoldSidebar"
    __gsignals__: ClassVar = {
        "resize-started": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "resized": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "resize-finished": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "view-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    views: Gtk.Stack = Gtk.Template.Child()
    search_button: Gtk.ToggleButton = Gtk.Template.Child()
    main_menu_button: Gtk.MenuButton = Gtk.Template.Child()
    pages_button: Gtk.ToggleButton = Gtk.Template.Child()
    bookmarks_button: Gtk.ToggleButton = Gtk.Template.Child()
    annotations_button: Gtk.ToggleButton = Gtk.Template.Child()
    resize_handle: Gtk.Box = Gtk.Template.Child()

    def __init__(self) -> None:
        """Create the panel with its views empty until a document is shown."""
        super().__init__()
        self.main_menu_button.set_menu_model(main_menu())
        self._previous_view = PAGES
        self._grab_offset = 0.0
        self._updating = False
        self.resize_handle.set_cursor_from_name("col-resize")
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._on_resize_begin)
        drag.connect("drag-update", self._on_resize_update)
        drag.connect("drag-end", lambda _gesture, _x, _y: self.emit("resize-finished"))
        self.resize_handle.add_controller(drag)

    def add_view(self, name: str, view: Gtk.Widget) -> None:
        """Add one of the four views."""
        self.views.add_named(view, name)

    @property
    def visible_view(self) -> str:
        """Name of the view shown."""
        return self.views.get_visible_child_name() or PAGES

    def show_view(self, name: str) -> None:
        """Show a view and press its button; Find remembers the view it covers, to go back to it."""
        if name == self.visible_view:
            return
        if name == SEARCH:
            self._previous_view = self.visible_view
        self._updating = True
        self.views.set_visible_child_name(name)
        self.search_button.set_active(name == SEARCH)
        buttons = {PAGES: self.pages_button, BOOKMARKS: self.bookmarks_button, ANNOTATIONS: self.annotations_button}
        if name in buttons:
            buttons[name].set_active(True)
        else:
            for button in buttons.values():
                button.set_active(False)
        self._updating = False
        self.emit("view-changed")

    def close_search(self) -> None:
        """Leave Find and go back to the view it covered (Esc)."""
        if self.visible_view == SEARCH:
            self.show_view(self._previous_view)

    @Gtk.Template.Callback()
    def _on_search_toggled(self, button: Gtk.ToggleButton) -> None:
        if self._updating:
            return
        if button.get_active():
            self.show_view(SEARCH)
        else:
            self.close_search()

    @Gtk.Template.Callback()
    def _on_switcher_toggled(self, button: Gtk.ToggleButton) -> None:
        if self._updating or not button.get_active():
            return
        names = {self.pages_button: PAGES, self.bookmarks_button: BOOKMARKS, self.annotations_button: ANNOTATIONS}
        self.show_view(names[button])

    def _pointer_x(self, gesture: Gtk.GestureDrag) -> float | None:
        """Where the pointer is, from the left edge of the panel (which does not move while its width changes)."""
        found, x, y = gesture.get_point(None)
        if not found:
            return None
        found, point = self.resize_handle.compute_point(self, Graphene.Point().init(x, y))
        return point.x if found else None

    def _on_resize_begin(self, gesture: Gtk.GestureDrag, _x: float, _y: float) -> None:
        # Keep the edge where it was grabbed under the pointer: remember how far from the edge the press was.
        pointer = self._pointer_x(gesture)
        self._grab_offset = self.get_width() - pointer if pointer is not None else 0.0
        self.emit("resize-started")

    def _on_resize_update(self, gesture: Gtk.GestureDrag, _offset_x: float, _offset_y: float) -> None:
        """Make the edge follow the pointer exactly.

        The width is measured from the panel's left edge, not from the handle, which moves with the edge.
        """
        pointer = self._pointer_x(gesture)
        if pointer is not None:
            self.emit("resized", clamp_width(pointer + self._grab_offset))
