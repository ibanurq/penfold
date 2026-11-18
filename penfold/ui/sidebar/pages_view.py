"""The Pages view of the side panel (02-interfaz, 6.1): thumbnails with their page labels.

Phase 2 shows them and lets the user select them and go to a page; adding, extracting, rotating, deleting and
reordering come with phases 3 and 4.
"""

import math
from gettext import gettext as _
from typing import ClassVar

from gi.repository import Gdk, Gio, GLib, GObject, Graphene, Gtk

from penfold.document.document import OpenDocument
from penfold.rendering.renderer import Renderer, TileKey, round_scale
from penfold.ui.sidebar.view_header import header_button, view_header

# As in 0.6: a thumbnail cell is at most 310 pixels wide, with 10 between cells, in 1 to 4 columns.
THUMBNAIL_MAX_WIDTH = 310
THUMBNAIL_GAP = 10
MAX_COLUMNS = 4
CELL_PADDING = 8
LIST_MARGIN = 8
CHANNEL = "thumbnails"
EDGE_COLOR = (0, 0, 0, 0.2)


def column_count(available_width: float) -> int:
    """Number of thumbnail columns for the width of the list, as 0.6's updateThumbColumns."""
    return max(
        1, min(MAX_COLUMNS, math.ceil((available_width + THUMBNAIL_GAP) / (THUMBNAIL_MAX_WIDTH + THUMBNAIL_GAP)))
    )


class PageItem(GObject.Object):
    """One page in the list: its index and its label."""

    __gtype_name__ = "PenfoldPageItem"

    def __init__(self, page: int, label: str) -> None:
        """Create the item of a page."""
        super().__init__()
        self.page = page
        self.label = label


class Thumbnail(Gtk.Widget):
    """A page drawn small, with the tile the renderer has ready (or white while it is drawn)."""

    __gtype_name__ = "PenfoldThumbnail"

    def __init__(self, view: "PagesView") -> None:
        """Create an empty thumbnail; bind gives it a page."""
        super().__init__()
        self._view = view
        self.page = -1

    def do_measure(self, orientation: object, _for_size: int) -> tuple[int, int, int, int]:
        """As wide as the view says; as tall as the page's proportions ask."""
        width = self._view.thumbnail_width
        if orientation == Gtk.Orientation.HORIZONTAL:
            return width, width, -1, -1
        height = round(width * self._view.page_ratio(self.page))
        return height, height, -1, -1

    def do_snapshot(self, snapshot: Gtk.Snapshot) -> None:
        """Draw the page edge, white paper and the drawn page on top."""
        width, height = self.get_width(), self.get_height()
        edge = Gdk.RGBA()
        edge.red, edge.green, edge.blue, edge.alpha = EDGE_COLOR
        snapshot.append_color(edge, Graphene.Rect().init(-1, -1, width + 2, height + 2))
        white = Gdk.RGBA()
        white.red = white.green = white.blue = white.alpha = 1.0
        snapshot.append_color(white, Graphene.Rect().init(0, 0, width, height))
        texture = self._view.texture(self.page)
        if texture is not None:
            snapshot.append_texture(texture, Graphene.Rect().init(0, 0, width, height))


class PageCell(Gtk.Box):
    """A thumbnail with its page label under it."""

    __gtype_name__ = "PenfoldPageCell"

    def __init__(self, view: "PagesView") -> None:
        """Create the cell's widgets."""
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6, halign=Gtk.Align.CENTER)
        self.set_margin_top(CELL_PADDING)
        self.set_margin_bottom(CELL_PADDING)
        self.thumbnail = Thumbnail(view)
        self.thumbnail.set_halign(Gtk.Align.CENTER)
        self.label = Gtk.Label()
        self.label.add_css_class("caption")
        self.label.add_css_class("dim-label")
        self.append(self.thumbnail)
        self.append(self.label)


class PagesView(Gtk.Box):
    """Thumbnails of every page in 1 to 4 columns, following the current page.

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
        self.thumbnail_width = THUMBNAIL_MAX_WIDTH - 2 * CELL_PADDING
        self.current_page = 0
        self._cells: dict[int, PageCell] = {}
        self._request_pending = False
        self.pages = Gio.ListStore.new(PageItem)
        self.selection = Gtk.MultiSelection.new(self.pages)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_setup)
        factory.connect("bind", self._on_bind)
        factory.connect("unbind", self._on_unbind)
        self.grid = Gtk.GridView(model=self.selection, factory=factory, max_columns=MAX_COLUMNS)
        self.grid.add_css_class("navigation-sidebar")
        self.scrolled = Gtk.ScrolledWindow(child=self.grid, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.append(self.scrolled)

    # Document.

    def set_document(self, document: OpenDocument, renderer: Renderer) -> None:
        """Show the thumbnails of a PDF."""
        if self.renderer is not None:
            self.renderer.disconnect(self._rendered_handler)
        self.document, self.renderer = document, renderer
        self._rendered_handler = renderer.connect("tile-rendered", self._on_tile_rendered)
        self._cells.clear()
        self.pages.splice(
            0,
            self.pages.get_n_items(),
            [PageItem(page, document.page_label(page)) for page in range(document.page_count)],
        )
        self.current_page = 0
        self._request_thumbnails()

    def page_ratio(self, page: int) -> float:
        """Height of a page divided by its width (A4 while there is no page)."""
        if self.renderer is None or not 0 <= page < len(self.renderer.page_sizes):
            return math.sqrt(2)
        width, height = self.renderer.page_sizes[page]
        return height / width

    def show_current_page(self, page: int) -> None:
        """Mark the thumbnail of the current page and keep it in sight."""
        previous, self.current_page = self.current_page, page
        for index in (previous, page):
            cell = self._cells.get(index)
            if cell is not None:
                self._mark_current(cell, index)
        if 0 <= page < self.pages.get_n_items():
            self.grid.scroll_to(page, Gtk.ListScrollFlags.NONE, None)

    def selected_pages(self) -> list[int]:
        """Indexes of the selected thumbnails, in page order."""
        bitset = self.selection.get_selection()
        return [bitset.get_nth(index) for index in range(bitset.get_size())]

    # Thumbnails.

    def _device_scale(self) -> float:
        native = self.get_native()
        surface = native.get_surface() if native else None
        return surface.get_scale() if surface else float(self.get_scale_factor())

    def _key(self, page: int, device_scale: float | None = None) -> TileKey | None:
        if self.renderer is None or not 0 <= page < len(self.renderer.page_sizes):
            return None
        width, _height = self.renderer.page_sizes[page]
        scale = self._device_scale() if device_scale is None else device_scale
        return TileKey(page, round_scale(self.thumbnail_width * scale / width))

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

    def _on_tile_rendered(self, _renderer: Renderer, page: int) -> None:
        cell = self._cells.get(page)
        if cell is not None:
            cell.thumbnail.queue_draw()

    def do_size_allocate(self, width: int, height: int, baseline: int) -> None:
        """Choose the columns and the thumbnail width for the width of the panel."""
        available = width - 2 * LIST_MARGIN
        columns = column_count(available)
        cell_width = min(THUMBNAIL_MAX_WIDTH, (available - (columns - 1) * THUMBNAIL_GAP) / columns)
        thumbnail_width = max(40, int(cell_width - 2 * CELL_PADDING))
        if columns != self.grid.get_min_columns() or thumbnail_width != self.thumbnail_width:
            self.grid.set_min_columns(columns)
            self.grid.set_max_columns(columns)
            self.thumbnail_width = thumbnail_width
            for cell in self._cells.values():
                cell.thumbnail.queue_resize()
            self._request_thumbnails()
        Gtk.Box.do_size_allocate(self, width, height, baseline)

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
