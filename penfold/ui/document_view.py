"""The PDF viewer: pages one under the other (Continuous) or in pairs (Two pages), with zoom.

It is a scrollable widget: the scrolled window around it moves the view, and the view draws only the pages that can be
seen, with the tiles the renderer has ready (03-arquitectura, 4.2). Measures are in logical pixels unless they say
"points" (PDF units) or "device pixels".
"""

import enum
import math
from dataclasses import dataclass
from typing import ClassVar

from gi.repository import Gdk, GObject, Graphene, Gsk, Gtk

from penfold.document.document import OpenDocument
from penfold.rendering.renderer import Renderer, TileKey, round_scale

# Zoom limits and step, as in 0.6: from 30 % to 400 %, 20 points at a time.
MIN_ZOOM = 0.3
MAX_ZOOM = 4.0
ZOOM_STEP = 0.2
# Space around and between pages, as in 0.6.
SIDE_MARGIN = 20
TOP_MARGIN = 15
PAGE_GAP = 12
PAIR_GAP = 14
PAIR_TOP_MARGIN = 24
# Pages drawn ahead of the visible ones, so they are ready when scrolling.
PRELOAD_PAGES = 2
SCROLL_STEP = 48
# A thin edge that fades outwards, like a soft shadow, drawn as plain rectangles: GTK's shadow and border nodes fail
# now and then with some of its renderers (invalid damage regions).
PAGE_EDGE_OPACITIES = (0.2, 0.08, 0.03)
WHITE = (1, 1, 1, 1)


class Fit(enum.Enum):
    """How the zoom follows the width of the viewer."""

    WIDTH = "width"
    PAGE = "page"
    MANUAL = "manual"


@dataclass(frozen=True)
class PageBox:
    """Where a page is drawn in the view, in logical pixels from the top left corner of the content."""

    page: int
    x: float
    y: float
    width: float
    height: float

    @property
    def bottom(self) -> float:
        """Lower edge."""
        return self.y + self.height


def rgba(color: tuple[float, float, float, float]) -> Gdk.RGBA:
    """Build a Gdk.RGBA from red, green, blue and opacity between 0 and 1."""
    value = Gdk.RGBA()
    value.red, value.green, value.blue, value.alpha = color
    return value


def clamp_zoom(zoom: float) -> float:
    """Keep a zoom between the limits."""
    return min(MAX_ZOOM, max(MIN_ZOOM, zoom))


class DocumentView(Gtk.Widget, Gtk.Scrollable):
    """Shows the pages of the open PDF and keeps track of the current page and the zoom."""

    __gtype_name__ = "PenfoldDocumentView"
    __gsignals__: ClassVar = {
        "current-page-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "zoom-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    hscroll_policy = GObject.Property(type=Gtk.ScrollablePolicy, default=Gtk.ScrollablePolicy.MINIMUM)
    vscroll_policy = GObject.Property(type=Gtk.ScrollablePolicy, default=Gtk.ScrollablePolicy.MINIMUM)

    def __init__(self) -> None:
        """Create an empty view; set_document shows a PDF."""
        super().__init__()
        self._hadjustment: Gtk.Adjustment | None = None
        self._vadjustment: Gtk.Adjustment | None = None
        self.document: OpenDocument | None = None
        self.renderer: Renderer | None = None
        self._rendered_handler = 0
        self.zoom = 1.0
        self.fit = Fit.WIDTH
        self.two_pages = False
        self.current_page = 0
        self._boxes: list[PageBox] = []
        self._content_width = 0.0
        self._content_height = 0.0
        self._allocated_width = 0
        self._start_pending = False
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self.set_focusable(True)
        scroll = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        scroll.connect("scroll", self._on_scroll)
        self.add_controller(scroll)

    # Scrollable interface: the scrolled window gives the view its adjustments.

    @GObject.Property(type=Gtk.Adjustment)
    def hadjustment(self) -> Gtk.Adjustment | None:
        """Horizontal position of the visible part."""
        return self._hadjustment

    @hadjustment.setter  # type: ignore[no-redef]
    def hadjustment(self, adjustment: Gtk.Adjustment | None) -> None:
        self._hadjustment = adjustment
        if adjustment is not None:
            adjustment.connect("value-changed", self._on_scrolled)
        self._configure_adjustments()

    @GObject.Property(type=Gtk.Adjustment)
    def vadjustment(self) -> Gtk.Adjustment | None:
        """Vertical position of the visible part."""
        return self._vadjustment

    @vadjustment.setter  # type: ignore[no-redef]
    def vadjustment(self, adjustment: Gtk.Adjustment | None) -> None:
        self._vadjustment = adjustment
        if adjustment is not None:
            adjustment.connect("value-changed", self._on_scrolled)
        self._configure_adjustments()

    def do_get_border(self) -> tuple[bool, Gtk.Border]:
        """The view has no border of its own."""
        return False, Gtk.Border()

    # Document.

    def set_document(self, document: OpenDocument, renderer: Renderer) -> None:
        """Show a PDF from its first page, fitted to the width (Two pages: the whole page), as in 0.6."""
        if self.renderer is not None:
            self.renderer.disconnect(self._rendered_handler)
        self.document = document
        self.renderer = renderer
        self._rendered_handler = renderer.connect("tile-rendered", lambda _renderer, _page: self.queue_draw())
        self.current_page = 0
        self.fit = Fit.PAGE if self.two_pages else Fit.WIDTH
        self._start_pending = True
        self._allocated_width = 0
        self.queue_allocate()
        self.emit("current-page-changed")

    @property
    def page_count(self) -> int:
        """Number of pages of the shown PDF (0 without one)."""
        return len(self.renderer.page_sizes) if self.renderer else 0

    # Zoom.

    def zoom_in(self) -> None:
        """Enlarge by one step."""
        self._set_zoom(clamp_zoom(self.zoom + ZOOM_STEP), Fit.MANUAL)

    def zoom_out(self) -> None:
        """Reduce by one step."""
        self._set_zoom(clamp_zoom(self.zoom - ZOOM_STEP), Fit.MANUAL)

    def fit_width(self) -> None:
        """Fit the current page (Two pages: the pair) to the width of the viewer."""
        self._set_zoom(self._fitting_zoom(Fit.WIDTH), Fit.WIDTH)

    def fit_page(self) -> None:
        """Fit the whole current page (Two pages: the pair) in the viewer."""
        self._set_zoom(self._fitting_zoom(Fit.PAGE), Fit.PAGE)

    @property
    def can_zoom_in(self) -> bool:
        """Whether the zoom is below the maximum."""
        return self.renderer is not None and self.zoom < MAX_ZOOM - 1e-6

    @property
    def can_zoom_out(self) -> bool:
        """Whether the zoom is above the minimum."""
        return self.renderer is not None and self.zoom > MIN_ZOOM + 1e-6

    def _set_zoom(self, zoom: float, fit: Fit) -> None:
        if self.renderer is None:
            return
        self.fit = fit
        if math.isclose(zoom, self.zoom):
            self.emit("zoom-changed")
            return
        self.zoom = zoom
        self._relayout(keep_position=True)
        self.emit("zoom-changed")

    def _shown_pages(self) -> list[int]:
        """Pages that the fitting zoom has to make room for: the current page, or its pair."""
        if not self.two_pages:
            return [self.current_page]
        first = self.current_page - self.current_page % 2
        return [page for page in (first, first + 1) if page < self.page_count]

    def _fitting_zoom(self, fit: Fit) -> float:
        """Zoom that fits the current page or pair to the width, or whole, in the viewer (as 0.6's setFit)."""
        if self.renderer is None:
            return self.zoom
        sizes = [self.renderer.page_sizes[page] for page in self._shown_pages()]
        total_width = sum(width for width, _height in sizes)
        if self.two_pages and len(sizes) == 1:
            total_width += sizes[0][0]
        tallest = max(height for _width, height in sizes)
        width = self.get_width() - 2 * SIDE_MARGIN - (PAIR_GAP if self.two_pages else 0)
        height = self.get_height() - 2 * (PAIR_TOP_MARGIN if self.two_pages else TOP_MARGIN)
        fit_width = width / total_width
        zoom = fit_width if fit is Fit.WIDTH else min(fit_width, height / tallest)
        return clamp_zoom(zoom)

    # Moving around.

    def set_two_pages(self, two_pages: bool) -> None:
        """Switch between Continuous and Two pages; the whole page (or the width) is fitted again, as in 0.6."""
        if two_pages == self.two_pages:
            return
        self.two_pages = two_pages
        if self.renderer is None:
            return
        self.fit = Fit.PAGE if two_pages else Fit.WIDTH
        self.zoom = self._fitting_zoom(self.fit)
        self._relayout(keep_position=False)
        self.go_to(self.current_page)
        self.emit("zoom-changed")

    def go_to(self, page: int, y_points: float | None = None) -> None:
        """Show a page, with the height y_points (from its top) on the top third of the viewer (B8).

        Without a height it goes to the start of the page, and it never scrolls above the start of the page.
        """
        if self.renderer is None or self._vadjustment is None or not 0 <= page < self.page_count:
            return
        if self.two_pages and page - page % 2 != self.current_page - self.current_page % 2:
            self.current_page = page
            self._relayout(keep_position=False)
            if self.fit is not Fit.MANUAL:
                self._set_zoom(self._fitting_zoom(self.fit), self.fit)
            self.emit("current-page-changed")
            return
        box = self._box(page)
        if box is None:
            return
        target = box.y - TOP_MARGIN
        if y_points is not None:
            target = max(target, box.y + y_points * self.zoom - self.get_height() / 3)
        self._vadjustment.set_value(target)
        self._update_current_page(force=page)

    def next_page(self) -> None:
        """Go to the next page (Two pages: the next pair)."""
        self.go_to(min(self.page_count - 1, self.current_page + (2 - self.current_page % 2 if self.two_pages else 1)))

    def previous_page(self) -> None:
        """Go to the previous page (Two pages: the previous pair)."""
        step = 2 + self.current_page % 2 if self.two_pages else 1
        self.go_to(max(0, self.current_page - step))

    def first_page(self) -> None:
        """Go to the first page."""
        self.go_to(0)

    def last_page(self) -> None:
        """Go to the last page."""
        self.go_to(self.page_count - 1)

    # Layout.

    def _box(self, page: int) -> PageBox | None:
        return next((box for box in self._boxes if box.page == page), None)

    def _layout(self) -> None:
        """Place the pages for the current zoom and width."""
        if self.renderer is None:
            self._boxes, self._content_width, self._content_height = [], 0.0, 0.0
            return
        sizes = self.renderer.page_sizes
        viewer_width = self.get_width()
        if self.two_pages:
            self._layout_pair(sizes, viewer_width)
            return
        widest = max(width for width, _height in sizes) * self.zoom
        self._content_width = max(viewer_width, widest + 2 * SIDE_MARGIN)
        boxes = []
        y = float(TOP_MARGIN)
        for page, (width, height) in enumerate(sizes):
            box_width, box_height = width * self.zoom, height * self.zoom
            boxes.append(PageBox(page, round((self._content_width - box_width) / 2), round(y), box_width, box_height))
            y += box_height + PAGE_GAP
        self._boxes = boxes
        self._content_height = y - PAGE_GAP + TOP_MARGIN

    def _layout_pair(self, sizes: list[tuple[float, float]], viewer_width: int) -> None:
        """Place the current pair side by side, centred; an odd last page keeps the place of the left page."""
        pages = self._shown_pages()
        widths = [sizes[page][0] * self.zoom for page in pages]
        heights = [sizes[page][1] * self.zoom for page in pages]
        pair_width = widths[0] * 2 + PAIR_GAP if len(pages) == 1 else sum(widths) + PAIR_GAP
        self._content_width = max(viewer_width, pair_width + 2 * SIDE_MARGIN)
        self._content_height = max(self.get_height(), max(heights) + 2 * PAIR_TOP_MARGIN)
        x = round((self._content_width - pair_width) / 2)
        top = max(PAIR_TOP_MARGIN, (self._content_height - max(heights)) / 2)
        self._boxes = []
        for page, width, height in zip(pages, widths, heights, strict=True):
            self._boxes.append(PageBox(page, x, round(top), width, height))
            x += round(width + PAIR_GAP)

    def _relayout(self, keep_position: bool) -> None:
        """Lay the pages out again, keeping the point on the top third of the viewer where it was."""
        anchor = self._anchor() if keep_position else None
        self._layout()
        self._configure_adjustments()
        if anchor is not None and self._vadjustment is not None:
            page, fraction = anchor
            box = self._box(page)
            if box is not None:
                self._vadjustment.set_value(box.y + fraction * box.height - self.get_height() / 3)
        self.queue_draw()

    def _anchor(self) -> tuple[int, float] | None:
        """The page on the top third of the viewer and how far down it is (0 at its top, 1 at its bottom)."""
        box = self._box(self.current_page)
        if box is None or self._vadjustment is None:
            return None
        line = self._vadjustment.get_value() + self.get_height() / 3
        return box.page, (line - box.y) / box.height

    def _configure_adjustments(self) -> None:
        width, height = self.get_width(), self.get_height()
        for adjustment, size, content in (
            (self._hadjustment, width, self._content_width),
            (self._vadjustment, height, self._content_height),
        ):
            if adjustment is None:
                continue
            upper = max(content, size)
            value = min(adjustment.get_value(), upper - size)
            adjustment.configure(value, 0, upper, SCROLL_STEP, size * 0.9, size)
        if self._hadjustment is not None and self._content_width > width:
            self._hadjustment.set_value(max(0, (self._content_width - width) / 2))

    def do_size_allocate(self, width: int, _height: int, _baseline: int) -> None:
        """Fit the zoom again when the width of the viewer changes (B4), then place the pages."""
        width_changed = width != self._allocated_width
        self._allocated_width = width
        if self.renderer is not None and width_changed:
            if self.fit is Fit.MANUAL:
                self.fit = Fit.PAGE if self.two_pages else Fit.WIDTH
            self.zoom = self._fitting_zoom(self.fit)
            self.emit("zoom-changed")
        self._relayout(keep_position=not self._start_pending)
        if self._start_pending and self.renderer is not None and width > 0:
            self._start_pending = False
            if self._vadjustment is not None:
                self._vadjustment.set_value(0)

    def do_measure(self, _orientation: object, _for_size: int) -> tuple[int, int, int, int]:
        """The view takes whatever space it is given; scrolling shows the rest."""
        return 0, 0, -1, -1

    # Current page.

    def _on_scrolled(self, _adjustment: Gtk.Adjustment) -> None:
        self._update_current_page()
        self.queue_draw()

    def _update_current_page(self, force: int | None = None) -> None:
        """The current page is the one crossing the top third of the viewer (B1)."""
        if self.two_pages or self._vadjustment is None or not self._boxes:
            page = self.current_page if force is None else force
        elif force is not None:
            page = force
        else:
            line = self._vadjustment.get_value() + self.get_height() / 3
            page = self._boxes[0].page
            for box in self._boxes:
                if box.y > line:
                    break
                page = box.page
        if page != self.current_page:
            self.current_page = page
            self.emit("current-page-changed")

    def _on_scroll(self, _controller: Gtk.EventControllerScroll, _dx: float, dy: float) -> bool:
        """In Two pages, the wheel changes pair at the edges of the pair (or always, if it fits) (B2)."""
        if not self.two_pages or self._vadjustment is None or dy == 0:
            return False
        adjustment = self._vadjustment
        at_top = adjustment.get_value() <= adjustment.get_lower() + 0.5
        at_bottom = adjustment.get_value() >= adjustment.get_upper() - adjustment.get_page_size() - 0.5
        if dy > 0 and at_bottom:
            self.next_page()
            return True
        if dy < 0 and at_top:
            self.previous_page()
            return True
        return False

    # Drawing.

    def _visible_boxes(self) -> list[PageBox]:
        if self._vadjustment is None:
            return []
        top = self._vadjustment.get_value()
        bottom = top + self.get_height()
        return [box for box in self._boxes if box.bottom >= top and box.y <= bottom]

    def _device_scale(self) -> float:
        """Device pixels per logical pixel (2 on a HiDPI screen, 1.25 with fractional scaling…)."""
        native = self.get_native()
        surface = native.get_surface() if native else None
        return surface.get_scale() if surface else float(self.get_scale_factor())

    def do_snapshot(self, snapshot: Gtk.Snapshot) -> None:
        """Draw the visible pages and ask the renderer for the tiles they need."""
        if self.renderer is None or self._hadjustment is None or self._vadjustment is None:
            return
        offset_x, offset_y = self._hadjustment.get_value(), self._vadjustment.get_value()
        device_scale = self._device_scale()
        scale = round_scale(self.zoom * device_scale)
        visible = self._visible_boxes()
        wanted: dict[TileKey, int] = {}
        for box in visible:
            x, y = box.x - offset_x, box.y - offset_y
            self._draw_page_frame(snapshot, x, y, box)
            ready = []
            for key in self._visible_tiles(box, scale, offset_x, offset_y):
                texture = self.renderer.texture(key)
                if texture is None:
                    wanted[key] = abs(box.page - self.current_page)
                else:
                    ready.append((key, texture))
            if any(key.page == box.page for key in wanted):
                self._draw_placeholder(snapshot, x, y, box, scale)
            for key, texture in ready:
                self._append_tile(snapshot, x, y, key, texture)
        for page in self._nearby_pages(visible):
            for key in self._all_tiles(page, scale):
                wanted.setdefault(key, PRELOAD_PAGES + abs(page - self.current_page))
        self.renderer.request(wanted)

    def _draw_page_frame(self, snapshot: Gtk.Snapshot, x: float, y: float, box: PageBox) -> None:
        """Draw the white page with its edge, before its tiles."""
        for distance, opacity in enumerate(PAGE_EDGE_OPACITIES, start=1):
            color = rgba((0, 0, 0, opacity))
            left, top = x - distance, y - distance
            width, height = box.width + 2 * distance, box.height + 2 * distance
            for edge in (
                (left, top, width, 1),
                (left, top + height - 1, width, 1),
                (left, top + 1, 1, height - 2),
                (left + width - 1, top + 1, 1, height - 2),
            ):
                snapshot.append_color(color, Graphene.Rect().init(*edge))
        snapshot.append_color(rgba(WHITE), Graphene.Rect().init(x, y, box.width, box.height))

    def _visible_tiles(self, box: PageBox, scale: float, offset_x: float, offset_y: float) -> list[TileKey]:
        """Tiles of a page that intersect the visible part of the view."""
        assert self.renderer is not None
        grid = self.renderer.grid(self.renderer.page_sizes[box.page], scale)
        pixels_per_logical = scale / self.zoom
        left = max(0.0, (offset_x - box.x) * pixels_per_logical)
        top = max(0.0, (offset_y - box.y) * pixels_per_logical)
        right = min(grid.width, (offset_x + self.get_width() - box.x) * pixels_per_logical)
        bottom = min(grid.height, (offset_y + self.get_height() - box.y) * pixels_per_logical)
        return [
            TileKey(box.page, scale, column, row)
            for row in range(int(top // grid.tile_size), min(grid.rows, int(bottom // grid.tile_size) + 1))
            for column in range(int(left // grid.tile_size), min(grid.columns, int(right // grid.tile_size) + 1))
        ]

    def _all_tiles(self, page: int, scale: float) -> list[TileKey]:
        """Tiles of a page drawn ahead of time: only pages drawn whole, so preloading never eats much memory."""
        assert self.renderer is not None
        grid = self.renderer.grid(self.renderer.page_sizes[page], scale)
        return [TileKey(page, scale)] if grid.columns == grid.rows == 1 else []

    def _nearby_pages(self, visible: list[PageBox]) -> list[int]:
        if not visible:
            return []
        first, last = visible[0].page, visible[-1].page
        return [
            page
            for page in range(max(0, first - PRELOAD_PAGES), min(self.page_count, last + PRELOAD_PAGES + 1))
            if not first <= page <= last
        ]

    def _draw_placeholder(self, snapshot: Gtk.Snapshot, x: float, y: float, box: PageBox, scale: float) -> None:
        """While tiles of a page are missing, show the same page drawn at another zoom, stretched."""
        assert self.renderer is not None
        snapshot.push_clip(Graphene.Rect().init(x, y, box.width, box.height))
        for key, texture in self.renderer.closest_textures(box.page, scale):
            if key.scale != scale:
                self._append_tile(snapshot, x, y, key, texture)
        snapshot.pop()

    def _append_tile(self, snapshot: Gtk.Snapshot, x: float, y: float, key: TileKey, texture: Gdk.Texture) -> None:
        assert self.renderer is not None
        grid = self.renderer.grid(self.renderer.page_sizes[key.page], key.scale)
        tile_x, tile_y, width, height = grid.tile_rectangle(key.column, key.row)
        logical = self.zoom / key.scale
        bounds = Graphene.Rect().init(x + tile_x * logical, y + tile_y * logical, width * logical, height * logical)
        snapshot.append_scaled_texture(texture, Gsk.ScalingFilter.LINEAR, bounds)
