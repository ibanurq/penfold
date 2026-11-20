"""The Pages view of the side panel (02-interfaz, 6.1; D39, D41): thumbnails with their page labels.

Thumbnails have a size of their own, which the user changes with Ctrl and the wheel (or Ctrl++ and Ctrl+- while they
have the focus); the panel shows as many columns as fit, centred. Every page sits in the same cell, with the
proportions of an upright A4, fitted inside without being distorted, so an A3 looks like an A4 and a landscape page is
centred vertically. The thumbnail of the page being read is marked, with a soft box over the part shown in the
document.

Phase 2 shows them and lets the user select them and go to a page; adding, extracting, rotating, deleting and
reordering come with phases 3 and 4.
"""

import math
from gettext import gettext as _
from typing import ClassVar

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Graphene, Gtk

from penfold import config
from penfold.document.document import OpenDocument
from penfold.rendering.page_content import Rectangle
from penfold.rendering.renderer import Renderer, TileKey, round_scale
from penfold.ui.document_view import append_page_frame
from penfold.ui.sidebar.view_header import header_button, view_header

# The cell of every thumbnail has the proportions of an upright A4.
CELL_RATIO = math.sqrt(2)
# Room around each thumbnail inside its cell (the selection shows it), between cells and to the edges of the panel.
CELL_PADDING = 8
CELL_GAP = 8
LIST_MARGIN = 12
# Room kept for the vertical scrollbar (it overlays the list in GNOME, but appears while scrolling).
SCROLLBAR_WIDTH = 14
# Thumbnail widths: the smallest the user can choose, and how much each step of the wheel changes them.
MIN_THUMBNAIL_WIDTH = 72
ZOOM_FACTOR = 1.1
# A cell accepts being this narrow while the panel shrinks, until the columns are laid out again.
SHRINKING_WIDTH = 24
CHANNEL = "thumbnails"
VISIBLE_AREA_FILL = 0.12
VISIBLE_AREA_EDGE = 0.6


def column_count(available_width: float, thumbnail_width: float) -> int:
    """How many cells of a thumbnail width fit in a width, with their gaps; at least one."""
    cell = thumbnail_width + 2 * CELL_PADDING
    return max(1, math.floor((available_width + CELL_GAP) / (cell + CELL_GAP)))


def widest_thumbnail(available_width: float) -> int:
    """The widest thumbnail for a width: one column that fills it."""
    return max(MIN_THUMBNAIL_WIDTH, int(available_width - 2 * CELL_PADDING))


def fit_page(page_size: tuple[float, float], box_width: float, box_height: float) -> tuple[float, float, float, float]:
    """Where a page goes in its cell: x, y, width and height, as large as fits, without distortion, centred."""
    page_width, page_height = page_size
    scale = min(box_width / page_width, box_height / page_height)
    width, height = page_width * scale, page_height * scale
    return (box_width - width) / 2, (box_height - height) / 2, width, height


def rgba(red: float, green: float, blue: float, alpha: float) -> Gdk.RGBA:
    """Build a Gdk.RGBA from its parts, between 0 and 1."""
    color = Gdk.RGBA()
    color.red, color.green, color.blue, color.alpha = red, green, blue, alpha
    return color


class PageItem(GObject.Object):
    """One page in the list: its index and its label."""

    __gtype_name__ = "PenfoldPageItem"

    def __init__(self, page: int, label: str) -> None:
        """Create the item of a page."""
        super().__init__()
        self.page = page
        self.label = label


class Thumbnail(Gtk.Widget):
    """The cell of a page: the page drawn small, fitted in the middle, and the part shown in the document."""

    __gtype_name__ = "PenfoldThumbnail"

    def __init__(self, view: "PagesView") -> None:
        """Create an empty thumbnail; bind gives it a page."""
        super().__init__()
        self._view = view
        self.page = -1

    def do_measure(self, orientation: object, _for_size: int) -> tuple[int, int, int, int]:
        """Every cell is as large as the thumbnail width, with the proportions of an upright A4.

        It accepts being narrower for a moment, so the list can shrink with the panel until it is laid out again.
        """
        width = self._view.thumbnail_width
        if orientation == Gtk.Orientation.HORIZONTAL:
            return SHRINKING_WIDTH, width, -1, -1
        height = round(width * CELL_RATIO)
        return height, height, -1, -1

    def do_snapshot(self, snapshot: Gtk.Snapshot) -> None:
        """Draw the page edge, white paper, the drawn page and the box of the part shown."""
        renderer = self._view.renderer
        if renderer is None or not 0 <= self.page < len(renderer.page_sizes):
            return
        x, y, width, height = fit_page(renderer.page_sizes[self.page], self.get_width(), self.get_height())
        append_page_frame(snapshot, x, y, width, height)
        texture = self._view.texture(self.page)
        if texture is not None:
            snapshot.append_texture(texture, Graphene.Rect().init(x, y, width, height))
        area = self._view.visible_areas.get(self.page)
        if area is not None:
            self._draw_visible_area(snapshot, area, (x, y, width, height))

    def _draw_visible_area(
        self, snapshot: Gtk.Snapshot, area: Rectangle, page_box: tuple[float, float, float, float]
    ) -> None:
        """A soft box in the accent colour over the part of the page shown in the document (D41)."""
        renderer = self._view.renderer
        assert renderer is not None
        x, y, width, height = page_box
        page_width, page_height = renderer.page_sizes[self.page]
        left = x + max(0.0, area[0]) / page_width * width
        top = y + max(0.0, area[1]) / page_height * height
        right = x + min(page_width, area[2]) / page_width * width
        bottom = y + min(page_height, area[3]) / page_height * height
        if right - left < 1 or bottom - top < 1:
            return
        accent = Adw.StyleManager.get_default().get_accent_color_rgba()
        accent.alpha = VISIBLE_AREA_FILL
        bounds = Graphene.Rect().init(left, top, right - left, bottom - top)
        snapshot.append_color(accent, bounds)
        edge = Adw.StyleManager.get_default().get_accent_color_rgba()
        edge.alpha = VISIBLE_AREA_EDGE
        for line in (
            (left, top, right - left, 1),
            (left, bottom - 1, right - left, 1),
            (left, top + 1, 1, bottom - top - 2),
            (right - 1, top + 1, 1, bottom - top - 2),
        ):
            snapshot.append_color(edge, Graphene.Rect().init(*line))


class PageCell(Gtk.Box):
    """A thumbnail with its page label under it."""

    __gtype_name__ = "PenfoldPageCell"

    def __init__(self, view: "PagesView") -> None:
        """Create the cell's widgets."""
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6, halign=Gtk.Align.CENTER)
        self.set_margin_top(CELL_PADDING)
        self.set_margin_bottom(CELL_PADDING)
        self.set_margin_start(CELL_PADDING)
        self.set_margin_end(CELL_PADDING)
        self.thumbnail = Thumbnail(view)
        self.thumbnail.set_halign(Gtk.Align.CENTER)
        self.label = Gtk.Label()
        self.label.add_css_class("caption")
        self.label.add_css_class("dim-label")
        self.append(self.thumbnail)
        self.append(self.label)


class PagesView(Gtk.Box):
    """Thumbnails of every page, in as many columns as fit, following the page being read.

    "page-activated" is emitted with a page index when a thumbnail is clicked without Ctrl or Shift.
    """

    __gtype_name__ = "PenfoldPagesView"
    __gsignals__: ClassVar = {
        "page-activated": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self) -> None:
        """Create the view, empty until set_document."""
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.append(
            view_header(
                _("Pages"),
                header_button(_("_Add"), "list-add-symbolic", "win.add-pages"),
                header_button(_("_Extract"), "document-send-symbolic", "win.extract-pages"),
            )
        )
        self.document: OpenDocument | None = None
        self.renderer: Renderer | None = None
        self._rendered_handler = 0
        self._settings = Gio.Settings(schema_id=config.APP_ID)
        # The size the user chose, and the one shown (smaller if the panel is too narrow for it).
        self.chosen_width = max(MIN_THUMBNAIL_WIDTH, self._settings.get_int("thumbnail-size"))
        self.thumbnail_width = self.chosen_width
        self.current_page = 0
        self.visible_areas: dict[int, Rectangle] = {}
        self._cells: dict[int, PageCell] = {}
        self._request_pending = False
        self.pages = Gio.ListStore.new(PageItem)
        self.selection = Gtk.MultiSelection.new(self.pages)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_setup)
        factory.connect("bind", self._on_bind)
        factory.connect("unbind", self._on_unbind)
        self.grid = Gtk.GridView(
            model=self.selection, factory=factory, margin_start=LIST_MARGIN, margin_end=LIST_MARGIN
        )
        self.grid.add_css_class("navigation-sidebar")
        self.scrolled = Gtk.ScrolledWindow(child=self.grid, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.append(self.scrolled)
        zoom = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        zoom.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        zoom.connect("scroll", self._on_scroll)
        self.scrolled.add_controller(zoom)
        pinch = Gtk.GestureZoom()
        pinch.connect("begin", lambda _gesture, _sequence: setattr(self, "_pinch_width", self.chosen_width))
        pinch.connect("scale-changed", lambda _gesture, scale: self.set_thumbnail_width(self._pinch_width * scale))
        self.scrolled.add_controller(pinch)
        self._pinch_width = self.chosen_width
        # Check the width at every frame (a cheap comparison) and lay the columns out again when it changes.
        self._fitted_width = -1
        self.add_tick_callback(self._on_tick)

    # Document.

    def set_document(self, document: OpenDocument, renderer: Renderer) -> None:
        """Show the thumbnails of a PDF."""
        if self.renderer is not None:
            self.renderer.disconnect(self._rendered_handler)
        self.document, self.renderer = document, renderer
        self._rendered_handler = renderer.connect("tile-rendered", self._on_tile_rendered)
        self._cells.clear()
        self.visible_areas = {}
        self.pages.splice(0, self.pages.get_n_items(), self._items(document))
        self.current_page = 0
        self._request_thumbnails()

    def pages_changed(self) -> None:
        """Show the pages again after an edit, with their labels."""
        if self.document is None:
            return
        self._cells.clear()
        self.pages.splice(0, self.pages.get_n_items(), self._items(self.document))
        self.current_page = min(self.current_page, self.document.page_count - 1)
        self._request_thumbnails()

    @staticmethod
    def _items(document: OpenDocument) -> list[PageItem]:
        return [PageItem(page, document.page_label(page)) for page in range(document.page_count)]

    def show_current_page(self, page: int) -> None:
        """Mark the thumbnail of the page being read and keep it in sight."""
        previous, self.current_page = self.current_page, page
        for index in (previous, page):
            cell = self._cells.get(index)
            if cell is not None:
                self._mark_current(cell, index)
        if 0 <= page < self.pages.get_n_items():
            self.grid.scroll_to(page, Gtk.ListScrollFlags.NONE, None)

    def show_visible_areas(self, areas: dict[int, Rectangle]) -> None:
        """Show which part of each page is shown in the document, in points from the page's top left corner (D41)."""
        changed = set(self.visible_areas) | set(areas)
        self.visible_areas = areas
        for page in changed:
            cell = self._cells.get(page)
            if cell is not None:
                cell.thumbnail.queue_draw()

    def selected_pages(self) -> list[int]:
        """Indexes of the selected thumbnails, in page order."""
        bitset = self.selection.get_selection()
        return [bitset.get_nth(index) for index in range(bitset.get_size())]

    # Zoom of the thumbnails (D39).

    @property
    def available_width(self) -> float:
        """Room for the cells: the panel without its margins and the scrollbar."""
        return self.get_width() - SCROLLBAR_WIDTH - 2 * LIST_MARGIN

    def has_focus_inside(self) -> bool:
        """Whether the keyboard focus is on the thumbnails (then Ctrl++ and Ctrl+- zoom them)."""
        root = self.get_root()
        focus = root.get_focus() if isinstance(root, Gtk.Window) else None
        return focus is not None and (focus == self.grid or focus.is_ancestor(self.grid))

    def zoom_in(self) -> None:
        """Make the thumbnails one step larger (fewer columns)."""
        self.set_thumbnail_width(self.thumbnail_width * ZOOM_FACTOR)

    def zoom_out(self) -> None:
        """Make the thumbnails one step smaller (more columns)."""
        self.set_thumbnail_width(self.thumbnail_width / ZOOM_FACTOR)

    def set_thumbnail_width(self, width: float) -> None:
        """Choose a thumbnail width, between the minimum and one column that fills the panel, and remember it."""
        widest = widest_thumbnail(self.available_width) if self.get_width() > 0 else int(width)
        chosen = round(min(max(width, MIN_THUMBNAIL_WIDTH), max(widest, MIN_THUMBNAIL_WIDTH)))
        if chosen != self.chosen_width:
            self.chosen_width = chosen
            self._settings.set_int("thumbnail-size", chosen)
            self._lay_out(self.get_width())

    def _on_scroll(self, controller: Gtk.EventControllerScroll, _dx: float, dy: float) -> bool:
        """Ctrl and the wheel over the thumbnails zoom them; without Ctrl, the list scrolls."""
        if dy == 0 or not controller.get_current_event_state() & Gdk.ModifierType.CONTROL_MASK:
            return False
        self.set_thumbnail_width(self.thumbnail_width * ZOOM_FACTOR ** (-dy))
        return True

    # Thumbnails.

    def _device_scale(self) -> float:
        native = self.get_native()
        surface = native.get_surface() if native else None
        return surface.get_scale() if surface else float(self.get_scale_factor())

    def _key(self, page: int, device_scale: float | None = None) -> TileKey | None:
        """The tile of a page's thumbnail: the whole page at the scale that fits it in its cell."""
        if self.renderer is None or not 0 <= page < len(self.renderer.page_sizes):
            return None
        box_width = self.thumbnail_width
        _x, _y, width, _height = fit_page(self.renderer.page_sizes[page], box_width, box_width * CELL_RATIO)
        page_width, _page_height = self.renderer.page_sizes[page]
        scale = self._device_scale() if device_scale is None else device_scale
        return self.renderer.tile_key(page, round_scale(width / page_width * scale))

    def texture(self, page: int) -> Gdk.Texture | None:
        """The drawn thumbnail of a page, or a drawing of it at another size while it is being drawn."""
        key = self._key(page)
        if key is None or self.renderer is None:
            return None
        texture = self.renderer.texture(key)
        if texture is not None:
            return texture
        stand_ins = self.renderer.closest_textures(page, key.scale)
        whole = [texture for stand_in, texture in stand_ins if stand_in.column == stand_in.row == 0]
        return whole[0] if len(stand_ins) == 1 and whole else None

    def _request_thumbnails(self) -> None:
        """Ask for the thumbnails of the cells shown, once, after the list has placed them."""
        if not self._request_pending:
            self._request_pending = True
            GLib.idle_add(self._send_request)

    def _send_request(self) -> bool:
        self._request_pending = False
        if self.renderer is None:
            return GLib.SOURCE_REMOVE
        device_scale = self._device_scale()
        wanted = {}
        for page in self._cells:
            key = self._key(page, device_scale)
            if key is not None and self.renderer.texture(key) is None:
                wanted[key] = abs(page - self.current_page)
        self.renderer.request(wanted, CHANNEL)
        return GLib.SOURCE_REMOVE

    def _on_tile_rendered(self, renderer: Renderer, source: int) -> None:
        position = renderer.layout.position(source)
        cell = self._cells.get(position) if position is not None else None
        if cell is not None:
            cell.thumbnail.queue_draw()

    def _on_tick(self, _widget: Gtk.Widget, _clock: Gdk.FrameClock) -> bool:
        width = self.get_width()
        if width != self._fitted_width:
            self._fitted_width = width
            self._lay_out(width)
        return GLib.SOURCE_CONTINUE

    def _lay_out(self, width: int) -> None:
        """Show as many columns as fit; the thumbnails keep their size, unless the panel is too narrow for it."""
        available = width - SCROLLBAR_WIDTH - 2 * LIST_MARGIN
        if available <= 0:
            return
        thumbnail_width = min(self.chosen_width, widest_thumbnail(available))
        columns = column_count(available, thumbnail_width)
        resized = thumbnail_width != self.thumbnail_width
        if columns != self.grid.get_min_columns() or columns != self.grid.get_max_columns() or resized:
            self.grid.set_min_columns(columns)
            self.grid.set_max_columns(columns)
            self.thumbnail_width = thumbnail_width
            if resized:
                for cell in self._cells.values():
                    cell.thumbnail.queue_resize()
                self._request_thumbnails()

    # List items.

    def _on_setup(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        cell = PageCell(self)
        click = Gtk.GestureClick()
        click.connect("released", self._on_cell_clicked, item)
        cell.add_controller(click)
        item.set_child(cell)

    def _on_bind(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        page_item = item.get_item()
        cell = item.get_child()
        assert isinstance(page_item, PageItem)
        assert isinstance(cell, PageCell)
        cell.thumbnail.page = page_item.page
        cell.thumbnail.queue_resize()
        cell.label.set_label(page_item.label)
        self._mark_current(cell, page_item.page)
        self._cells[page_item.page] = cell
        self._request_thumbnails()

    def _on_unbind(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        page_item = item.get_item()
        if isinstance(page_item, PageItem) and self._cells.get(page_item.page) is item.get_child():
            del self._cells[page_item.page]

    def _mark_current(self, cell: PageCell, page: int) -> None:
        if page == self.current_page:
            cell.label.add_css_class("current-page")
        else:
            cell.label.remove_css_class("current-page")

    def _on_cell_clicked(
        self, gesture: Gtk.GestureClick, _presses: int, _x: float, _y: float, item: Gtk.ListItem
    ) -> None:
        """A click without Ctrl or Shift goes to the page; with them it only changes the selection."""
        state = gesture.get_current_event_state()
        if state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK):
            return
        page_item = item.get_item()
        if isinstance(page_item, PageItem):
            self.emit("page-activated", page_item.page)
