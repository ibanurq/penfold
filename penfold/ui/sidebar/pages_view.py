"""The Pages view of the side panel (02-interfaz, 6.1; D39, D41): thumbnails with their page labels.

Thumbnails have a size of their own, which the user changes with Ctrl and the wheel (or Ctrl++ and Ctrl+- while they
have the focus); the panel shows as many columns as fit, centred. Every page sits in the same cell, with the
proportions of an upright A4, fitted inside without being distorted, so an A3 looks like an A4 and a landscape page is
centred vertically. The thumbnail of the page being read is marked, with a soft box over the part shown in the
document.

With pages selected, a bar at the bottom turns or deletes them (02-interfaz, 6); a click away from the thumbnails, or
Esc, clears the selection (D47). Thumbnails are dragged to reorder the pages, several at once if the one dragged is
selected (E1). Adding and extracting come with phase 4.
"""

import math
from gettext import gettext as _
from gettext import npgettext
from typing import ClassVar

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Graphene, Gtk, Pango

from penfold import config
from penfold.document.document import OpenDocument
from penfold.rendering.page_content import Rectangle
from penfold.rendering.renderer import Renderer, TileKey, round_scale
from penfold.ui.autoscroll import DragAutoscroll
from penfold.ui.document_view import append_page_frame
from penfold.ui.sidebar.view_header import header_button, unselect_all, unselect_on_empty_click, view_header

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
DROP_LINE_WIDTH = 3


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


Box = tuple[float, float, float, float]  # x, y, width, height


def drop_place(cells: dict[int, Box], x: float, y: float) -> tuple[int, bool] | None:
    """Where pages dropped at a point of the list go: next to the nearest thumbnail, on the side of its half.

    The point may be in the gap between thumbnails, where people naturally drop them. Returns the page of that
    thumbnail and whether they go before it (its left half) or after it; None if no thumbnail is shown.
    """
    if not cells:
        return None

    def distance(page: int) -> tuple[float, float]:
        left, top, width, height = cells[page]
        across = max(left - x, 0.0, x - left - width)
        down = max(top - y, 0.0, y - top - height)
        # Rows first: in the gap between two rows, the nearest row; then the nearest thumbnail in it.
        return down, across

    page = min(cells, key=distance)
    left, _top, width, _height = cells[page]
    return page, x < left + width / 2


def drop_line_x(cells: dict[int, Box], page: int, before: bool) -> float:
    """Where the line of a drop goes, across the list.

    Halfway to the neighbouring thumbnail of the same row, or just outside the thumbnail at the end of a row.
    """
    left, top, width, _height = cells[page]
    neighbour = cells.get(page - 1 if before else page + 1)
    edge = left if before else left + width
    if neighbour is not None and neighbour[1] == top:
        neighbour_edge = neighbour[0] + neighbour[2] if before else neighbour[0]
        return (edge + neighbour_edge) / 2
    return edge - CELL_PADDING if before else edge + CELL_PADDING


class DraggedPages(GObject.Object):
    """The pages being dragged, by position: what a thumbnail carries while it is dragged."""

    __gtype_name__ = "PenfoldDraggedPages"

    def __init__(self, positions: list[int]) -> None:
        """Carry the pages at these positions."""
        super().__init__()
        self.positions = positions


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

    "page-activated" is emitted with a page index when a thumbnail is clicked without Ctrl or Shift, and
    "move-requested" with the positions of the pages dropped and the position they go before.
    """

    __gtype_name__ = "PenfoldPagesView"
    __gsignals__: ClassVar = {
        "page-activated": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "move-requested": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT, int)),
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
        # The pages selected, by their source index, to select them again once they have moved.
        self._selected_sources: set[int] = set()
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
        unselect_on_empty_click(self.scrolled, self.selection)
        self.append(self._add_drop_target())
        self.selection_label, self.action_bar = self._action_bar()
        self.append(self.action_bar)
        self.selection.connect("selection-changed", lambda *_arguments: self._update_action_bar())
        self.selection.connect("items-changed", lambda *_arguments: self._update_action_bar())
        zoom = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        zoom.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        zoom.connect("scroll", self._on_scroll)
        self.scrolled.add_controller(zoom)
        pinch = Gtk.GestureZoom()
        pinch.connect("begin", lambda _gesture, _sequence: setattr(self, "_pinch_width", self.chosen_width))
        pinch.connect("scale-changed", lambda _gesture, scale: self.set_thumbnail_width(self._pinch_width * scale))
        self.scrolled.add_controller(pinch)
        self._pinch_width = self.chosen_width
        # While thumbnails are dragged near the top or bottom of the list, it scrolls, so pages can go far.
        DragAutoscroll(self.scrolled)
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
        """Show the pages again after an edit, with their labels, keeping the same pages selected.

        The list keeps its items, so it stays where it was scrolled: only their number and labels change.
        """
        document = self.document
        if document is None:
            return
        selected_sources = set(self._selected_sources)
        old_count, new_count = self.pages.get_n_items(), document.page_count
        if new_count < old_count:
            self.pages.splice(new_count, old_count - new_count, [])
        elif new_count > old_count:
            self.pages.splice(old_count, 0, self._items(document)[old_count:])
        for position in range(new_count):
            item = self.pages.get_item(position)
            assert isinstance(item, PageItem)
            item.label = document.page_label(position)
        for position, cell in self._cells.items():
            cell.label.set_label(document.page_label(position))
            cell.thumbnail.queue_draw()
        self._select_sources(selected_sources)
        self.current_page = min(self.current_page, new_count - 1)
        self._request_thumbnails()

    def _select_sources(self, sources: set[int]) -> None:
        """Select the thumbnails of these pages (by source index), wherever they are now."""
        assert self.document is not None
        selected = Gtk.Bitset.new_empty()
        for position, page in enumerate(self.document.pages):
            if page.source_index in sources:
                selected.add(position)
        self.selection.set_selection(selected, Gtk.Bitset.new_range(0, self.pages.get_n_items()))

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

    def unselect_all(self) -> bool:
        """Clear the selection (Esc, D47); return whether any page was selected."""
        return unselect_all(self.selection)

    # Action bar (02-interfaz, 6.1).

    def _action_bar(self) -> tuple[Gtk.Label, Gtk.ActionBar]:
        """The bar shown with pages selected: how many, turn left, turn right and delete."""
        label = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        bar = Gtk.ActionBar(revealed=False)
        bar.pack_start(label)
        delete = Gtk.Button(icon_name="edit-delete-symbolic", tooltip_text=_("Delete"), action_name="win.delete-pages")
        delete.add_css_class("destructive-action")
        bar.pack_end(delete)
        for icon_name, tooltip, action_name in (
            ("object-rotate-right-symbolic", _("Rotate Right"), "win.rotate-pages-right"),
            ("object-rotate-left-symbolic", _("Rotate Left"), "win.rotate-pages-left"),
        ):
            button = Gtk.Button(icon_name=icon_name, tooltip_text=tooltip, action_name=action_name)
            # Until the user chooses icons that do not look like Undo and Redo (D19, D37).
            button.add_css_class("provisional-icon")
            bar.pack_end(button)
        return label, bar

    def _update_action_bar(self) -> None:
        selected = self.selected_pages()
        count = len(selected)
        self.action_bar.set_revealed(count > 0)
        self.selection_label.set_label(
            npgettext("pages", "{count} selected", "{count} selected", count).format(count=count)
        )
        pages = self.document.pages if self.document is not None else []
        self._selected_sources = {pages[position].source_index for position in selected if position < len(pages)}

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
        drag = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        drag.connect("prepare", self._on_drag_prepare, cell)
        drag.connect("drag-begin", self._on_drag_begin, cell)
        cell.add_controller(drag)
        item.set_child(cell)

    # Dragging thumbnails (E1).

    def _on_drag_prepare(
        self, _source: Gtk.DragSource, _x: float, _y: float, cell: PageCell
    ) -> Gdk.ContentProvider | None:
        """Drag the selected pages if the thumbnail is one of them; otherwise only its page.

        A PDF that does not allow assembling it does not let its pages move (D59).
        """
        if self.document is None or not self.document.restrictions.assemble:
            return None
        page = cell.thumbnail.page
        selected = self.selected_pages()
        return Gdk.ContentProvider.new_for_value(DraggedPages(selected if page in selected else [page]))

    def _on_drag_begin(self, source: Gtk.DragSource, _drag: Gdk.Drag, cell: PageCell) -> None:
        source.set_icon(Gtk.WidgetPaintable.new(cell.thumbnail), cell.thumbnail.get_width() // 2, 0)

    def _add_drop_target(self) -> Gtk.Overlay:
        """Let thumbnails be dropped anywhere on the list, gaps included, with a line where they will go.

        Returns the overlay that holds the list and, above it, the line.
        """
        self.drop_line = Gtk.Box(halign=Gtk.Align.START, valign=Gtk.Align.START, visible=False, can_target=False)
        self.drop_line.add_css_class("drop-line")
        overlay = Gtk.Overlay(child=self.scrolled)
        overlay.add_overlay(self.drop_line)
        self._drop_overlay = overlay
        drop = Gtk.DropTarget.new(DraggedPages, Gdk.DragAction.MOVE)
        drop.connect("motion", self._on_drop_motion)
        drop.connect("leave", lambda _target: self.drop_line.set_visible(False))
        drop.connect("drop", self._on_drop)
        overlay.add_controller(drop)
        return overlay

    def _cell_boxes(self) -> dict[int, Box]:
        """Where the thumbnails shown are, in the overlay that holds the list."""
        boxes = {}
        for page, cell in self._cells.items():
            found, bounds = cell.compute_bounds(self._drop_overlay)
            if found and cell.get_mapped():
                boxes[page] = (bounds.get_x(), bounds.get_y(), bounds.get_width(), bounds.get_height())
        return boxes

    def _on_drop_motion(self, _target: Gtk.DropTarget, x: float, y: float) -> Gdk.DragAction:
        boxes = self._cell_boxes()
        place = drop_place(boxes, x, y)
        if place is None:
            self.drop_line.set_visible(False)
            return Gdk.DragAction.MOVE
        page, before = place
        _left, top, _width, height = boxes[page]
        line_x = drop_line_x(boxes, page, before)
        self.drop_line.set_margin_start(max(0, round(line_x - DROP_LINE_WIDTH / 2)))
        self.drop_line.set_margin_top(max(0, round(top)))
        self.drop_line.set_size_request(DROP_LINE_WIDTH, round(height))
        self.drop_line.set_visible(True)
        return Gdk.DragAction.MOVE

    def _on_drop(self, _target: Gtk.DropTarget, value: object, x: float, y: float) -> bool:
        self.drop_line.set_visible(False)
        place = drop_place(self._cell_boxes(), x, y)
        if not isinstance(value, DraggedPages) or place is None:
            return False
        page, before = place
        self.emit("move-requested", value.positions, page if before else page + 1)
        return True

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
