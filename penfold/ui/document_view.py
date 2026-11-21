"""The PDF viewer: pages one under the other (Continuous) or in pairs (Two pages), with zoom.

It is a scrollable widget: the scrolled window around it moves the view, and the view draws only the pages that can be
seen, with the tiles the renderer has ready (03-arquitectura, 4.2). Measures are in logical pixels unless they say
"points" (PDF units) or "device pixels".
"""

import enum
import math
from dataclasses import dataclass
from typing import ClassVar

from gi.repository import Adw, Gdk, GObject, Graphene, Gsk, Gtk, Poppler

from penfold.document.document import OpenDocument
from penfold.rendering.page_content import ExternalTarget, InternalTarget, Link, PageContent
from penfold.rendering.renderer import Renderer, TileKey, grid, round_scale
from penfold.rendering.text_search import SearchResult
from penfold.ui.form_layer import FormLayer, ShownBox
from penfold.ui.text_selection import PagePoint, TextSelection, source_selection

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
# Ctrl + wheel: each step of the wheel multiplies or divides the zoom by this.
WHEEL_ZOOM_FACTOR = 1.1
# Pages drawn ahead of the visible ones, so they are ready when scrolling.
PRELOAD_PAGES = 2
SCROLL_STEP = 48
# A thin edge that fades outwards, like a soft shadow, drawn as plain rectangles: GTK's shadow and border nodes fail
# now and then with some of its renderers (invalid damage regions).
PAGE_EDGE_OPACITIES = (0.2, 0.08, 0.03)
WHITE = (1, 1, 1, 1)
SELECTION_OPACITY = 0.35
# Matches of Find on the page: all of them in yellow, the current one in orange (GNOME's palette).
MATCH_COLOR = (0.97, 0.89, 0.36, 0.45)
CURRENT_MATCH_COLOR = (1.0, 0.47, 0.0, 0.5)
# A press that moves less than this, in pixels, is a click (it follows links), not a drag.
DRAG_THRESHOLD = 3
SELECTION_STYLES = {1: Poppler.SelectionStyle.GLYPH, 2: Poppler.SelectionStyle.WORD, 3: Poppler.SelectionStyle.LINE}


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


def append_page_frame(snapshot: Gtk.Snapshot, x: float, y: float, width: float, height: float) -> None:
    """Draw white paper with an edge that fades outwards, like a soft shadow (the document and the thumbnails)."""
    for distance, opacity in enumerate(PAGE_EDGE_OPACITIES, start=1):
        color = rgba((0, 0, 0, opacity))
        left, top = x - distance, y - distance
        ring_width, ring_height = width + 2 * distance, height + 2 * distance
        for edge in (
            (left, top, ring_width, 1),
            (left, top + ring_height - 1, ring_width, 1),
            (left, top + 1, 1, ring_height - 2),
            (left + ring_width - 1, top + 1, 1, ring_height - 2),
        ):
            snapshot.append_color(color, Graphene.Rect().init(*edge))
    snapshot.append_color(rgba(WHITE), Graphene.Rect().init(x, y, width, height))


def clamp_zoom(zoom: float) -> float:
    """Keep a zoom between the limits."""
    return min(MAX_ZOOM, max(MIN_ZOOM, zoom))


class DocumentView(Gtk.Widget, Gtk.Scrollable):
    """Shows the pages of the open PDF and keeps track of the current page and the zoom."""

    __gtype_name__ = "PenfoldDocumentView"
    __gsignals__: ClassVar = {
        "current-page-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "zoom-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "viewport-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
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
        self._fit_deferred = False
        self.content: PageContent | None = None
        self.selection: TextSelection | None = None
        self._matches: dict[int, list[SearchResult]] = {}
        self._current_match: SearchResult | None = None
        self._press: PagePoint | None = None
        self._press_style = Poppler.SelectionStyle.GLYPH
        self._dragging = False
        self._pixel = 1.0
        self._scale = 1.0
        self._pointer: tuple[float, float] | None = None
        self._form_layer = FormLayer(self)
        # Set when the pages moved (scroll, zoom, layout) but the view kept its size: the next allocation only places
        # the form fields again (GTK places child widgets only while allocating).
        self._fields_moved = False
        self._allocated_height = 0
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self.set_focusable(True)
        self._add_controllers()

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
        self.content = PageContent(renderer.poppler)
        self._form_layer.set_document(document, renderer.layout)
        self.selection = None
        self.current_page = 0
        self.fit = Fit.PAGE if self.two_pages else Fit.WIDTH
        self._start_pending = True
        self._allocated_width = 0
        self.queue_allocate()
        self.emit("current-page-changed")

    def pages_changed(self) -> None:
        """Show the pages again after an edit (the renderer already has them), staying where the reader was.

        The zoom is fitted again unless it is manual, since the current page may now be turned.
        """
        self.selection = None
        if self.renderer is not None:
            self._form_layer.pages_changed(self.renderer.layout)
        self.current_page = min(self.current_page, self.page_count - 1)
        if self.fit is not Fit.MANUAL:
            self.zoom = self._fitting_zoom(self.fit)
            self.emit("zoom-changed")
        self._relayout(keep_position=True)
        self._update_current_page()
        self.emit("current-page-changed")

    def form_changed(self) -> None:
        """Show the values of the form fields after an edit, an undo or a redo."""
        self._form_layer.form_changed()

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

    def zoom_around(self, zoom: float, point: tuple[float, float] | None) -> None:
        """Set a manual zoom keeping the point of the document under the pointer where it is."""
        anchor = self.page_point(*point) if point is not None else None
        if self.renderer is None or anchor is None or self._hadjustment is None or self._vadjustment is None:
            self._set_zoom(zoom, Fit.MANUAL)
            return
        assert point is not None
        self.fit = Fit.MANUAL
        if not math.isclose(zoom, self.zoom):
            self.zoom = zoom
            self._layout()
            self._configure_adjustments(centre=False)
            box = self._box(anchor.page)
            if box is not None:
                self._hadjustment.set_value(box.x + anchor.x * zoom - point[0])
                self._vadjustment.set_value(box.y + anchor.y * zoom - point[1])
            self.queue_draw()
        self.emit("zoom-changed")

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

    def page_down(self) -> None:
        """Page Down: the next page; in Two pages with zoom, first down inside the pair, then the next pair (B2)."""
        if not self._scroll_inside_pair(1):
            self.next_page()

    def page_up(self) -> None:
        """Page Up: the previous page; in Two pages with zoom, first up inside the pair, then the previous pair."""
        if not self._scroll_inside_pair(-1):
            self.previous_page()

    def _scroll_inside_pair(self, direction: int) -> bool:
        """Scroll a screen inside a zoomed pair; return False at its edge (or if it fits), to change pair instead."""
        adjustment = self._vadjustment
        if not self.two_pages or adjustment is None:
            return False
        lowest = adjustment.get_lower()
        highest = adjustment.get_upper() - adjustment.get_page_size()
        value = adjustment.get_value()
        if (direction > 0 and value >= highest - 0.5) or (direction < 0 and value <= lowest + 0.5):
            return False
        adjustment.set_value(value + direction * adjustment.get_page_increment())
        return True

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
        self._move_fields()
        self.queue_draw()
        self.emit("viewport-changed")

    def _move_fields(self) -> None:
        """Have the form fields placed again over the pages, which moved."""
        self._fields_moved = True
        self.queue_allocate()

    def _anchor(self) -> tuple[int, float] | None:
        """The page on the top third of the viewer and how far down it is (0 at its top, 1 at its bottom)."""
        box = self._box(self.current_page)
        if box is None or self._vadjustment is None:
            return None
        line = self._vadjustment.get_value() + self.get_height() / 3
        return box.page, (line - box.y) / box.height

    def _configure_adjustments(self, centre: bool = True) -> None:
        """Tell the scrollbars the size of the content; with centre, pages wider than the viewer are centred."""
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
        if centre and self._hadjustment is not None and self._content_width > width:
            self._hadjustment.set_value(max(0, (self._content_width - width) / 2))

    def defer_fit(self, deferred: bool) -> None:
        """While the panel border is dragged, keep the zoom; when it is released, fit it once to the new width (B4)."""
        self._fit_deferred = deferred
        if not deferred:
            self._allocated_width = -1
            self.queue_allocate()

    def do_size_allocate(self, width: int, height: int, _baseline: int) -> None:
        """Fit the zoom again when the width of the viewer changes (B4), then place the pages and the form fields."""
        fields_moved, self._fields_moved = self._fields_moved, False
        if fields_moved and (width, height) == (self._allocated_width, self._allocated_height):
            self._allocate_fields()
            return
        self._allocated_height = height
        width_changed = width != self._allocated_width
        if not self._fit_deferred:
            self._allocated_width = width
        if self.renderer is not None and width_changed and not self._fit_deferred:
            if self.fit is Fit.MANUAL:
                self.fit = Fit.PAGE if self.two_pages else Fit.WIDTH
            self.zoom = self._fitting_zoom(self.fit)
            self.emit("zoom-changed")
        self._relayout(keep_position=not self._start_pending)
        if self._start_pending and self.renderer is not None and width > 0:
            self._start_pending = False
            if self._vadjustment is not None:
                self._vadjustment.set_value(0)
        self._allocate_fields()

    def _allocate_fields(self) -> None:
        """Place the form fields of the visible pages over them."""
        if self._hadjustment is None or self._vadjustment is None:
            return
        offset_x, offset_y = self._hadjustment.get_value(), self._vadjustment.get_value()
        boxes = [ShownBox(box.page, box.x - offset_x, box.y - offset_y) for box in self._visible_boxes()]
        self._form_layer.allocate(boxes, self.zoom)

    def do_measure(self, _orientation: object, _for_size: int) -> tuple[int, int, int, int]:
        """The view takes whatever space it is given; scrolling shows the rest."""
        return 0, 0, -1, -1

    # Current page.

    def _on_scrolled(self, _adjustment: Gtk.Adjustment) -> None:
        self._move_fields()
        self._update_current_page()
        self.queue_draw()
        self.emit("viewport-changed")

    def visible_areas(self) -> dict[int, tuple[float, float, float, float]]:
        """The part of each visible page that is shown, in points from the page's top left corner."""
        if self._hadjustment is None or self._vadjustment is None or self.zoom <= 0:
            return {}
        left, top = self._hadjustment.get_value(), self._vadjustment.get_value()
        right, bottom = left + self.get_width(), top + self.get_height()
        areas = {}
        for box in self._visible_boxes():
            areas[box.page] = (
                (max(left, box.x) - box.x) / self.zoom,
                (max(top, box.y) - box.y) / self.zoom,
                (min(right, box.x + box.width) - box.x) / self.zoom,
                (min(bottom, box.bottom) - box.y) / self.zoom,
            )
        return areas

    def reading_point(self) -> tuple[int, float]:
        """The page and the height, in points from its top, on the top third of the viewer: where the reader is."""
        box = self._box(self.current_page)
        if box is None or self._vadjustment is None or self.zoom <= 0:
            return self.current_page, 0.0
        line = self._vadjustment.get_value() + self.get_height() / 3
        return box.page, max(0.0, (line - box.y) / self.zoom)

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

    def _on_scroll(self, controller: Gtk.EventControllerScroll, _dx: float, dy: float) -> bool:
        """Ctrl + wheel zooms around the pointer; in Two pages, the wheel changes pair at its edges (B2)."""
        if dy == 0 or self._vadjustment is None:
            return False
        if controller.get_current_event_state() & Gdk.ModifierType.CONTROL_MASK:
            self.zoom_around(clamp_zoom(self.zoom * WHEEL_ZOOM_FACTOR ** (-dy)), self._pointer)
            return True
        if not self.two_pages:
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
        self._pixel = 1 / device_scale
        self._scale = scale
        for box in visible:
            # On whole device pixels, so tiles are copied pixel for pixel instead of resampled (sharp text).
            x = round((box.x - offset_x) * device_scale) / device_scale
            y = round((box.y - offset_y) * device_scale) / device_scale
            self._draw_page_frame(snapshot, x, y, box)
            ready, missing = [], False
            for key in self._visible_tiles(box, scale, offset_x, offset_y):
                texture = self.renderer.texture(key)
                if texture is None:
                    wanted[key] = abs(box.page - self.current_page)
                    missing = True
                else:
                    ready.append((key, texture))
            if missing:
                self._draw_placeholder(snapshot, x, y, box, scale)
            for key, texture in ready:
                self._append_tile(snapshot, x, y, key, texture)
            self._draw_matches(snapshot, x, y, box)
            self._draw_selection(snapshot, x, y, box)
        for page in self._nearby_pages(visible):
            for key in self._all_tiles(page, scale):
                wanted.setdefault(key, PRELOAD_PAGES + abs(page - self.current_page))
        self.renderer.request(wanted)
        self._form_layer.snapshot(snapshot)

    def _draw_page_frame(self, snapshot: Gtk.Snapshot, x: float, y: float, box: PageBox) -> None:
        """Draw the white page with its edge, before its tiles."""
        append_page_frame(snapshot, x, y, box.width, box.height)

    def _visible_tiles(self, box: PageBox, scale: float, offset_x: float, offset_y: float) -> list[TileKey]:
        """Tiles of a page that intersect the visible part of the view."""
        assert self.renderer is not None
        tiles = grid(self.renderer.page_sizes[box.page], scale)
        pixels_per_logical = scale / self.zoom
        left = max(0.0, (offset_x - box.x) * pixels_per_logical)
        top = max(0.0, (offset_y - box.y) * pixels_per_logical)
        right = min(tiles.width, (offset_x + self.get_width() - box.x) * pixels_per_logical)
        bottom = min(tiles.height, (offset_y + self.get_height() - box.y) * pixels_per_logical)
        return [
            self.renderer.tile_key(box.page, scale, column, row)
            for row in range(int(top // tiles.tile_size), min(tiles.rows, int(bottom // tiles.tile_size) + 1))
            for column in range(int(left // tiles.tile_size), min(tiles.columns, int(right // tiles.tile_size) + 1))
        ]

    def _all_tiles(self, page: int, scale: float) -> list[TileKey]:
        """Tiles of a page drawn ahead of time: only pages drawn whole, so preloading never eats much memory."""
        assert self.renderer is not None
        tiles = grid(self.renderer.page_sizes[page], scale)
        return [self.renderer.tile_key(page, scale)] if tiles.columns == tiles.rows == 1 else []

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
        """Draw a tile; exact tiles (at the current zoom) one texture pixel per device pixel, others stretched."""
        assert self.renderer is not None
        tile_x, tile_y, width, height = self.renderer.key_grid(key).tile_rectangle(key.column, key.row)
        exact = key.scale == self._scale
        logical = self._pixel if exact else self.zoom / key.scale
        bounds = Graphene.Rect().init(x + tile_x * logical, y + tile_y * logical, width * logical, height * logical)
        scaling = Gsk.ScalingFilter.NEAREST if exact else Gsk.ScalingFilter.LINEAR
        snapshot.append_scaled_texture(texture, scaling, bounds)

    def add_matches(self, results: list[SearchResult]) -> None:
        """Highlight more matches of Find on their pages."""
        for result in results:
            self._matches.setdefault(result.page, []).append(result)
        if any(box.page in self._matches for box in self._visible_boxes()):
            self.queue_draw()

    def set_current_match(self, result: SearchResult | None) -> None:
        """Highlight the current match of Find differently from the others."""
        self._current_match = result
        self.queue_draw()

    def clear_matches(self) -> None:
        """Remove every highlight of Find."""
        self._matches, self._current_match = {}, None
        self.queue_draw()

    @property
    def has_matches(self) -> bool:
        """Whether matches of Find are highlighted."""
        return bool(self._matches)

    def _draw_matches(self, snapshot: Gtk.Snapshot, x: float, y: float, box: PageBox) -> None:
        for result in self._matches.get(box.page, []):
            color = rgba(CURRENT_MATCH_COLOR if result is self._current_match else MATCH_COLOR)
            for left, top, right, bottom in result.rectangles:
                bounds = Graphene.Rect().init(
                    x + left * self.zoom, y + top * self.zoom, (right - left) * self.zoom, (bottom - top) * self.zoom
                )
                snapshot.append_color(color, bounds)

    def _draw_selection(self, snapshot: Gtk.Snapshot, x: float, y: float, box: PageBox) -> None:
        """Highlight the selected text of a page with the accent colour."""
        if self.selection is None or self.content is None or self.renderer is None:
            return
        selection = self.selection.page_selections(self.renderer.page_sizes).get(box.page)
        if selection is None:
            return
        color = Adw.StyleManager.get_default().get_accent_color_rgba()
        color.alpha = SELECTION_OPACITY
        page = self.renderer.layout[box.page]
        rectangles = self.content.selection_rectangles(
            page.source, source_selection(page, selection), self.selection.style
        )
        for left, top, right, bottom in (page.from_source(rectangle) for rectangle in rectangles):
            bounds = Graphene.Rect().init(
                x + left * self.zoom, y + top * self.zoom, (right - left) * self.zoom, (bottom - top) * self.zoom
            )
            snapshot.append_color(color, bounds)

    # Mouse and keyboard.

    def _add_controllers(self) -> None:
        scroll = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        scroll.connect("scroll", self._on_scroll)
        self.add_controller(scroll)
        click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
        click.connect("pressed", self._on_pressed)
        self.add_controller(click)
        drag = Gtk.GestureDrag(button=Gdk.BUTTON_PRIMARY)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self.add_controller(drag)
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        self.add_controller(motion)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key_pressed)
        self.add_controller(keys)

    def page_point(self, x: float, y: float, clamp: bool = False) -> PagePoint | None:
        """Convert a point of the widget to a point of a page; with clamp, the nearest page if it falls between."""
        if self._hadjustment is None or self._vadjustment is None or not self._boxes:
            return None
        content_x, content_y = x + self._hadjustment.get_value(), y + self._vadjustment.get_value()
        for box in self._boxes:
            if box.x <= content_x <= box.x + box.width and box.y <= content_y <= box.bottom:
                return PagePoint(box.page, (content_y - box.y) / self.zoom, (content_x - box.x) / self.zoom)
        if not clamp:
            return None
        box = min(self._boxes, key=lambda candidate: _distance(candidate, content_x, content_y))
        page_x = min(max(content_x, box.x), box.x + box.width)
        page_y = min(max(content_y, box.y), box.bottom)
        return PagePoint(box.page, (page_y - box.y) / self.zoom, (page_x - box.x) / self.zoom)

    def link_at(self, x: float, y: float) -> Link | None:
        """Return the link under a point of the widget, if any."""
        point = self.page_point(x, y)
        if point is None or self.content is None or self.renderer is None:
            return None
        page = self.renderer.layout[point.page]
        return self.content.link_at(page.source, *page.to_source(point.x, point.y))

    def _on_pressed(self, _gesture: Gtk.GestureClick, n_press: int, x: float, y: float) -> None:
        """A press starts a selection; a double click selects a word and a triple click a line."""
        self.grab_focus()
        self._press = self.page_point(x, y)
        self._press_style = SELECTION_STYLES.get(min(n_press, 3), Poppler.SelectionStyle.GLYPH)
        self._dragging = False
        if self._press is not None and n_press > 1:
            self._set_selection(TextSelection(self._press, self._press, self._press_style))

    def _on_drag_update(self, gesture: Gtk.GestureDrag, offset_x: float, offset_y: float) -> None:
        if self._press is None:
            return
        if not self._dragging and math.hypot(offset_x, offset_y) < DRAG_THRESHOLD:
            return
        self._dragging = True
        _found, start_x, start_y = gesture.get_start_point()
        focus = self.page_point(start_x + offset_x, start_y + offset_y, clamp=True)
        if focus is not None:
            self._set_selection(TextSelection(self._press, focus, self._press_style))

    def _on_drag_end(self, gesture: Gtk.GestureDrag, _offset_x: float, _offset_y: float) -> None:
        """A click without moving follows the link under it, or clears the selection."""
        if self._dragging or self._press_style is not Poppler.SelectionStyle.GLYPH:
            return
        _found, x, y = gesture.get_start_point()
        link = self.link_at(x, y)
        self._set_selection(None)
        if link is not None:
            self.follow_link(link)

    def follow_link(self, link: Link) -> None:
        """Go to an internal destination, or open a web address in the browser (B7)."""
        target = link.target
        if isinstance(target, InternalTarget):
            place = self.renderer.layout.place(target.page, target.top) if self.renderer is not None else None
            if place is not None:
                self.go_to(*place)
        elif isinstance(target, ExternalTarget):
            root = self.get_root()
            Gtk.UriLauncher(uri=target.uri).launch(root if isinstance(root, Gtk.Window) else None, None, None)

    def _on_motion(self, _controller: Gtk.EventControllerMotion, x: float, y: float) -> None:
        """A hand over links, the text cursor over pages."""
        self._pointer = (x, y)
        if self.link_at(x, y) is not None:
            self.set_cursor_from_name("pointer")
        elif self.page_point(x, y) is not None:
            self.set_cursor_from_name("text")
        else:
            self.set_cursor_from_name(None)

    def _set_selection(self, selection: TextSelection | None) -> None:
        self.selection = selection
        self.queue_draw()

    def selected_text(self) -> tuple[str, int] | None:
        """The text selected and the page where the selection starts; None if no text is selected."""
        if self.selection is None or self.content is None or self.renderer is None:
            return None
        text = self.selection.text(self.content, self.renderer.layout)
        return (text, min(self.selection.anchor, self.selection.focus).page) if text else None

    def copy_selection(self) -> bool:
        """Copy the selected text to the clipboard; return whether there was any."""
        selected = self.selected_text()
        if selected is None:
            return False
        self.get_clipboard().set(selected[0])
        return True

    def _on_key_pressed(
        self, _controller: Gtk.EventControllerKey, keyval: int, _keycode: int, state: Gdk.ModifierType
    ) -> bool:
        """Ctrl+C copies; the arrows scroll, and in Two pages left and right change pair (B2)."""
        # Keys a form field leaves (the arrows at the ends of its text…) are not for the view.
        if self.renderer is None or self._vadjustment is None or self._hadjustment is None or self.get_focus_child():
            return False
        control = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if control and keyval in {Gdk.KEY_c, Gdk.KEY_C}:
            return self.copy_selection()
        if control:
            return False
        vertical = {Gdk.KEY_Up: -SCROLL_STEP, Gdk.KEY_Down: SCROLL_STEP}.get(keyval)
        if vertical is not None:
            self._vadjustment.set_value(self._vadjustment.get_value() + vertical)
            return True
        horizontal = {Gdk.KEY_Left: -1, Gdk.KEY_Right: 1}.get(keyval)
        if horizontal is None:
            return False
        if self.two_pages and self._content_width <= self.get_width():
            (self.next_page if horizontal > 0 else self.previous_page)()
        else:
            self._hadjustment.set_value(self._hadjustment.get_value() + horizontal * SCROLL_STEP)
        return True


def _distance(box: PageBox, x: float, y: float) -> float:
    """Distance from a point of the content to a page box (0 inside it)."""
    dx = max(box.x - x, 0.0, x - box.x - box.width)
    dy = max(box.y - y, 0.0, y - box.bottom)
    return math.hypot(dx, dy)
