"""The PDF viewer: pages one under the other (Continuous) or in pairs (Two pages), with zoom.

It is a scrollable widget: the scrolled window around it moves the view, and the view draws only the pages that can be
seen, with the tiles the renderer has ready (03-arquitectura, 4.2). Measures are in logical pixels unless they say
"points" (PDF units) or "device pixels".
"""

import enum
import functools
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

from gi.repository import Adw, Gdk, GLib, GObject, Graphene, Gsk, Gtk, Poppler

from penfold.document.annotations import Annotation, Hit, Kind, Style, hit, topmost
from penfold.document.document import OpenDocument
from penfold.document.geometry import Rectangle, merge_lines
from penfold.rendering.annotation_painter import highlight_areas, highlight_tint, paint_annotations
from penfold.rendering.kept_look import KeptLooks, paint_look
from penfold.rendering.layout import ShownPage
from penfold.rendering.page_content import ExternalTarget, InternalTarget, Link, PageContent
from penfold.rendering.renderer import Renderer, TileKey, grid, round_scale
from penfold.rendering.text_box import Color
from penfold.rendering.text_search import SearchResult
from penfold.ui.form_layer import FormLayer, ShownBox
from penfold.ui.handle_editor import HandleEditor
from penfold.ui.text_box_editor import TextBoxEditor
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
# Makes the annotation of a shape from its page and its two ends on the page as shown; None for one too small to keep
# (a click).
ShapeMaker = Callable[[ShownPage, tuple[float, float], tuple[float, float]], Annotation | None]
# How far from a line a click still reaches it, in pixels of the screen (D72).
HIT_REACH = 4.0
# The outline of the annotation whose menu is open: its margin, width and corner radius, in pixels.
MARK_MARGIN = 3.0
MARK_WIDTH = 2.0
MARK_RADIUS = 4.0
# A comment's tooltip shows at most this many lines and characters, then "…" (D76).
TOOLTIP_LINES = 10
TOOLTIP_CHARACTERS = 500
# How long a remembered manual zoom is kept while the window settles after opening (the panel appears, the window
# grows), instead of fitting the zoom to each new width (07-fase-12, 9).
START_HOLD_MILLISECONDS = 1500
SELECTION_STYLES = {1: Poppler.SelectionStyle.GLYPH, 2: Poppler.SelectionStyle.WORD, 3: Poppler.SelectionStyle.LINE}


class Fit(enum.Enum):
    """How the zoom follows the width of the viewer."""

    WIDTH = "width"
    PAGE = "page"
    MANUAL = "manual"


@dataclass(frozen=True)
class ReadingPosition:
    """Where a document was being read (07-fase-12, 9).

    The page on the top third of the viewer, how far down it is (0 at its top, 1 at its bottom), and the zoom.
    """

    page: int
    depth: float
    fit: Fit
    zoom: float


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


@dataclass(frozen=True)
class PageClick:
    """A click on a page: the source index of the page, the point on the unturned page and the point in the view."""

    page: int
    point: tuple[float, float]
    view_point: tuple[float, float]


@dataclass(frozen=True)
class AnnotationClick:
    """A right click or a long press on an annotation: the annotation and the point in the view."""

    annotation: Annotation
    x: float
    y: float


def tooltip_text(text: str) -> str:
    """A comment's text for its tooltip: cut after some lines, and some characters for a long line, with "…"."""
    lines = text.strip().splitlines()
    whole = "\n".join(lines)
    short = "\n".join(lines[:TOOLTIP_LINES])[:TOOLTIP_CHARACTERS].rstrip()
    return whole if short == whole else short + "…"


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
        # A drag, or a double or triple click, has just selected text.
        "text-selected": (GObject.SignalFlags.RUN_FIRST, None, ()),
        # A drag with a tool that draws shapes has just drawn one: the annotation made.
        "shape-drawn": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        # A click on a page with a tool that places things (comments): a PageClick.
        "page-clicked": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        # A right click (or a long press) on an annotation, for its menu (D72): an AnnotationClick.
        "annotation-menu-requested": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
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
        # The annotations Penfold paints, by the source index of their page: those it manages, and those of the PDFs
        # moved as they are, with the drawings their programs made (D73).
        self._managed: dict[int, list[Annotation]] = {}
        self._kept_looks: KeptLooks | None = None
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
        self._start_position: ReadingPosition | None = None
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
        # The cursor over the pages while a tool that draws is chosen (02-interfaz, 5).
        self._drawing_cursor: str | None = None
        # While a tool marks text (highlight…), text is selected even if the PDF does not let it be copied.
        self.marking = False
        # While a tool draws shapes, a drag draws one instead of selecting text (H4).
        self._shape_maker: ShapeMaker | None = None
        self._shape_start: PagePoint | None = None
        # While a tool places things, a click on a page is told (page-clicked) instead of selecting text.
        self.placing = False
        self._click: PagePoint | None = None
        # An annotation being made (a shape being dragged, a comment being written), shown over its page.
        self._preview: Annotation | None = None
        # The annotation whose menu is open, outlined so that it is clear which one it is (D72).
        self._marked: Annotation | None = None
        # The annotation whose text is being edited on the page, not painted under its editor.
        self._hidden: Annotation | None = None
        # A text box being written on a page (H3).
        self.text_editor: TextBoxEditor | None = None
        # An annotation being moved or resized with handles (D73).
        self.handle_editor: HandleEditor | None = None
        self._form_layer = FormLayer(self)
        # Set when the pages moved (scroll, zoom, layout) but the view kept its size: the next allocation only places
        # the form fields again (GTK places child widgets only while allocating).
        self._fields_moved = False
        self._allocated_height = 0
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self.set_focusable(True)
        # The text of a comment, when the pointer is over it (H2).
        self.set_has_tooltip(True)
        self.connect("query-tooltip", self._on_query_tooltip)
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

    def set_document(self, document: OpenDocument, renderer: Renderer, position: ReadingPosition | None = None) -> None:
        """Show a PDF where it was left, if a position is given (07-fase-12, 9).

        Otherwise it starts on its first page, fitted to the width (Two pages: the whole page), as in 0.6.
        """
        if self.renderer is not None:
            self.renderer.disconnect(self._rendered_handler)
        self.document = document
        self.renderer = renderer
        self._rendered_handler = renderer.connect("tile-rendered", lambda _renderer, _page: self.queue_draw())
        self.content = PageContent(renderer.poppler)
        self._kept_looks = KeptLooks(lambda: renderer.sources)
        self._form_layer.set_document(document, renderer.layout)
        self.annotations_changed()
        self.selection = None
        start = position if position is not None and 0 <= position.page < self.page_count else None
        self._start_position = start
        self.current_page = 0 if start is None else start.page
        self.fit = self._default_fit if start is None else start.fit
        if start is not None:
            if start.fit is Fit.MANUAL:
                self.zoom = clamp_zoom(start.zoom)
            GLib.timeout_add(START_HOLD_MILLISECONDS, self._release_start, start)
        self._start_pending = True
        self._allocated_width = 0
        self.queue_allocate()
        self.emit("current-page-changed")

    def reading_position(self) -> ReadingPosition | None:
        """Where the document is being read, to come back to it when it is opened again; None without one."""
        anchor = self._anchor()
        return None if anchor is None else ReadingPosition(anchor[0], anchor[1], self.fit, self.zoom)

    @property
    def _default_fit(self) -> Fit:
        return Fit.PAGE if self.two_pages else Fit.WIDTH

    def _release_start(self, start: ReadingPosition) -> bool:
        """From now on, a new width fits the zoom again, even a remembered manual one (B4)."""
        if self._start_position is start:
            self._start_position = None
        return GLib.SOURCE_REMOVE

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

    def annotations_changed(self) -> None:
        """Paint the annotations Penfold manages again, after one was made or the change undone."""
        self._managed = {}
        if self.document is not None:
            for annotation in self.document.annotations:
                if (annotation.managed or annotation.moved_as_is) and annotation is not self._hidden:
                    self._managed.setdefault(annotation.page, []).append(annotation)
        editor = self.handle_editor
        annotations = [] if self.document is None else self.document.annotations
        if editor is not None and not any(item is editor.original for item in annotations):
            editor.finish(apply=False)  # Undone or deleted meanwhile.
        self.queue_draw()

    def form_changed(self) -> None:
        """Show the values of the form fields after an edit, an undo or a redo."""
        self._form_layer.form_changed()

    def permissions_changed(self) -> None:
        """Follow what the document allows now (D60): the fields to fill in, and selecting text."""
        if self.renderer is not None:
            self._form_layer.permissions_changed(self.renderer.layout)
        if not self._can_copy:
            self.selection = None
        self._move_fields()
        self.queue_draw()

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
            # A remembered manual zoom is kept while the window settles after opening.
            if self.fit is Fit.MANUAL and self._start_position is None:
                self.fit = self._default_fit
            if self.fit is not Fit.MANUAL:
                self.zoom = self._fitting_zoom(self.fit)
            self.emit("zoom-changed")
        self._relayout(keep_position=not self._start_pending)
        if self._start_pending and self.renderer is not None and width > 0:
            self._start_pending = False
            self._show_start()
        self._allocate_fields()

    def _show_start(self) -> None:
        """Show the first page, or the place where the document was left."""
        if self._vadjustment is None:
            return
        start = self._start_position
        box = None if start is None else self._box(start.page)
        if start is None or box is None:
            self._vadjustment.set_value(0)
            return
        self._vadjustment.set_value(box.y + start.depth * box.height - self.get_height() / 3)
        self._update_current_page()
        self.emit("current-page-changed")

    def _allocate_fields(self) -> None:
        """Place the form fields of the visible pages over them."""
        if self._hadjustment is None or self._vadjustment is None:
            return
        offset_x, offset_y = self._hadjustment.get_value(), self._vadjustment.get_value()
        boxes = [ShownBox(box.page, box.x - offset_x, box.y - offset_y) for box in self._visible_boxes()]
        self._form_layer.allocate(boxes, self.zoom)
        editor = self.text_editor
        page_box = self._box(editor.page) if editor is not None else None
        if editor is not None and page_box is not None:
            editor.allocate((page_box.x - offset_x, page_box.y - offset_y), self.zoom)

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
            draw_tiles = functools.partial(self._draw_tiles, origin=(x, y), box=box, ready=ready, missing=missing)
            draw_tiles(snapshot)
            shown = self.renderer.layout[box.page]
            if self.handle_editor is not None:
                self.handle_editor.snapshot_frame(snapshot, shown, (x, y), self.zoom)
            self._draw_annotations(snapshot, x, y, box, draw_tiles)
            self._draw_mark(snapshot, x, y, box)
            if self.handle_editor is not None:
                self.handle_editor.snapshot_handles(snapshot, shown, (x, y), self.zoom)
            self._draw_matches(snapshot, x, y, box)
            self._draw_selection(snapshot, x, y, box)
        for page in self._nearby_pages(visible):
            for key in self._all_tiles(page, scale):
                wanted.setdefault(key, PRELOAD_PAGES + abs(page - self.current_page))
        self.renderer.request(wanted)
        self._form_layer.snapshot(snapshot)
        if self.text_editor is not None:
            self.text_editor.snapshot(snapshot)

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

    def _draw_tiles(
        self,
        snapshot: Gtk.Snapshot,
        *,
        origin: tuple[float, float],
        box: PageBox,
        ready: list[tuple[TileKey, Gdk.Texture]],
        missing: bool,
    ) -> None:
        """Draw the tiles of a page at the current zoom, over the page at another zoom if some are missing."""
        x, y = origin
        if missing:
            self._draw_placeholder(snapshot, x, y, box, self._scale)
        for key, texture in ready:
            self._append_tile(snapshot, x, y, key, texture)

    def _draw_annotations(
        self, snapshot: Gtk.Snapshot, x: float, y: float, box: PageBox, draw_tiles: Callable[[Gtk.Snapshot], None]
    ) -> None:
        """Paint the annotations Penfold manages of a page over it, as they will be saved.

        A highlight multiplies the page under it by its colour: GTK paints a node apart from what is under it, so the
        page is drawn again in each area, tinted.
        """
        assert self.renderer is not None
        page = self.renderer.layout[box.page]
        annotations = self._managed.get(page.source, [])
        if self._preview is not None and self._preview.page == page.source:
            annotations = [*annotations, self._preview]
        no_offset = Graphene.Vec4().init(0, 0, 0, 0)
        for annotation in annotations:
            if annotation.kind is not Kind.HIGHLIGHT or not annotation.managed:
                continue
            tint = Graphene.Matrix().init_scale(*highlight_tint(annotation))
            for left, top, right, bottom in highlight_areas(page, annotation):
                zoom = self.zoom
                snapshot.push_clip(
                    Graphene.Rect().init(x + left * zoom, y + top * zoom, (right - left) * zoom, (bottom - top) * zoom)
                )
                snapshot.push_color_matrix(tint, no_offset)
                draw_tiles(snapshot)
                snapshot.pop()
                snapshot.pop()
        if any(annotation.kind is not Kind.HIGHLIGHT or not annotation.managed for annotation in annotations):
            context = snapshot.append_cairo(Graphene.Rect().init(x, y, box.width, box.height))
            context.translate(x, y)
            context.scale(self.zoom, self.zoom)
            for annotation in annotations:
                look = None if annotation.managed or self._kept_looks is None else self._kept_looks.look(annotation)
                if look is not None:
                    paint_look(context, page, annotation, look)
            paint_annotations(context, page, [item for item in annotations if item.managed], highlights=False)

    def _draw_mark(self, snapshot: Gtk.Snapshot, x: float, y: float, box: PageBox) -> None:
        """Outline the marked annotation, if it is on this page, in the accent colour."""
        if self._marked is None or self.renderer is None:
            return
        page = self.renderer.layout[box.page]
        bounds = self.annotation_bounds(page, self._marked)
        if bounds is None:
            return
        left, top, right, bottom = bounds
        zoom = self.zoom
        outline = Gsk.RoundedRect()  # init_from_rect fills it in place (what it returns is empty in Python).
        outline.init_from_rect(
            Graphene.Rect().init(
                x + left * zoom - MARK_MARGIN,
                y + top * zoom - MARK_MARGIN,
                (right - left) * zoom + 2 * MARK_MARGIN,
                (bottom - top) * zoom + 2 * MARK_MARGIN,
            ),
            MARK_RADIUS,
        )
        color = Adw.StyleManager.get_default().get_accent_color_rgba()
        snapshot.append_border(outline, [MARK_WIDTH] * 4, [color] * 4)

    def annotation_bounds(self, page: ShownPage, annotation: Annotation) -> Rectangle | None:
        """Where an annotation is on a page as shown, in points (None if it is on another page)."""
        if annotation.page != page.source:
            return None
        if annotation.kind is Kind.COMMENT:
            return self._upright_rectangle(page, annotation)
        return page.from_source(annotation.rectangle)

    def view_rectangle(self, annotation: Annotation) -> Gdk.Rectangle | None:
        """Where an annotation is in the view, in pixels (None if its page is not laid out)."""
        if self.renderer is None or self._hadjustment is None or self._vadjustment is None:
            return None
        position = self.renderer.layout.position(annotation.page)
        box = None if position is None else self._box(position)
        bounds = None if box is None else self.annotation_bounds(self.renderer.layout[box.page], annotation)
        if box is None or bounds is None:
            return None
        left, top, right, bottom = bounds
        place = Gdk.Rectangle()
        place.x = round(box.x - self._hadjustment.get_value() + left * self.zoom)
        place.y = round(box.y - self._vadjustment.get_value() + top * self.zoom)
        place.width, place.height = max(1, round((right - left) * self.zoom)), max(1, round((bottom - top) * self.zoom))
        return place

    def shown_page(self, source: int) -> ShownPage | None:
        """A page as shown, by its source index (None if it is not in the document)."""
        position = None if self.renderer is None else self.renderer.layout.position(source)
        return None if self.renderer is None or position is None else self.renderer.layout[position]

    def point_on_page(self, page: ShownPage, x: float, y: float) -> tuple[float, float] | None:
        """A point of the view on a page as shown, in points, even outside the page (None if it is not laid out)."""
        box = self._page_box(page)
        if box is None or self._hadjustment is None or self._vadjustment is None:
            return None
        return (
            (x + self._hadjustment.get_value() - box.x) / self.zoom,
            (y + self._vadjustment.get_value() - box.y) / self.zoom,
        )

    def point_in_view(self, page: ShownPage, point: tuple[float, float]) -> tuple[float, float]:
        """Where a point of a page as shown, in points, is in the view, in pixels."""
        box = self._page_box(page)
        if box is None or self._hadjustment is None or self._vadjustment is None:
            return (math.inf, math.inf)
        x, y = point
        return (
            box.x - self._hadjustment.get_value() + x * self.zoom,
            box.y - self._vadjustment.get_value() + y * self.zoom,
        )

    def _page_box(self, page: ShownPage) -> PageBox | None:
        position = None if self.renderer is None else self.renderer.layout.position(page.source)
        return None if position is None else self._box(position)

    def edit_handles(
        self,
        annotation: Annotation,
        on_done: Callable[[Annotation | None], None],
        *,
        resizable: bool,
        shown: Annotation | None = None,
    ) -> HandleEditor:
        """Start moving an annotation, and resizing it with handles if it is resizable (D73); shown as it changes.

        on_done receives the annotation changed, or None if the change was cancelled or nothing changed. Until it
        changes, it shows as shown (by default, as it is).
        """
        if self.text_editor is not None:
            self.text_editor.finish(apply=True)
        if self.handle_editor is not None:
            self.handle_editor.finish(apply=True)
        self.handle_editor = HandleEditor(self, annotation, on_done, resizable=resizable, shown=shown)
        self.set_hidden(annotation)
        self.set_preview(self.handle_editor.annotation)
        self.grab_focus()
        return self.handle_editor

    def has_text_under(self, annotation: Annotation) -> bool:
        """Whether there is text under a mark on text, to cover more or less of it (D73)."""
        if self.content is None or self.renderer is None or self.renderer.layout.position(annotation.page) is None:
            return False
        return bool(self.content.text_in_areas(annotation.page, list(annotation.quads)))

    def finish_editing(self) -> None:
        """Accept what is being edited on a page, as Enter does: a text box being written, an annotation being moved.

        Before the document is saved, printed or changed otherwise, so that what shows is what the document has.
        """
        if self.text_editor is not None:
            self.text_editor.finish(apply=True)
        if self.handle_editor is not None:
            self.handle_editor.finish(apply=True)

    def stop_handle_editing(self, editor: HandleEditor) -> None:
        """Stop showing an annotation's handles, and show it as it is in the document."""
        if self.handle_editor is not editor:
            return
        self.handle_editor = None
        self.set_preview(None)
        self.set_hidden(None)
        if self._pointer is not None:
            self._show_cursor(*self._pointer)

    def set_hidden(self, annotation: Annotation | None) -> None:
        """Leave out of the painting an annotation being edited on the page (None: none), under its editor."""
        self._hidden = annotation
        self.annotations_changed()

    def set_marked(self, annotation: Annotation | None) -> None:
        """Outline an annotation (None: none), while its menu is open."""
        self._marked = annotation
        self.queue_draw()

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
        right_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right_click.connect("pressed", lambda _gesture, _presses, x, y: self._ask_for_menu(x, y))
        self.add_controller(right_click)
        long_press = Gtk.GestureLongPress(touch_only=True)
        long_press.connect("pressed", lambda _gesture, x, y: self._ask_for_menu(x, y))
        self.add_controller(long_press)
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

    def comment_at(self, x: float, y: float) -> Annotation | None:
        """Return the comment with text under a point of the widget, if any."""
        point = self.page_point(x, y)
        if point is None or self.document is None or self.renderer is None:
            return None
        page = self.renderer.layout[point.page]
        for annotation in reversed(self.document.annotations):  # The last made is on top.
            if annotation.kind is Kind.COMMENT and annotation.text and annotation.page == page.source:
                left, top, right, bottom = self._upright_rectangle(page, annotation)
                if left <= point.x <= right and top <= point.y <= bottom:
                    return annotation
        return None

    def annotation_at(self, x: float, y: float) -> Annotation | None:
        """Return the annotation under a point of the widget, if any: the one it is most on, then the one on top."""
        point = self.page_point(x, y)
        if point is None or self.document is None or self.renderer is None:
            return None
        page = self.renderer.layout[point.page]
        source_x, source_y = page.to_source(point.x, point.y)
        reach = HIT_REACH / self.zoom
        hits: dict[int, Hit] = {}
        for index, annotation in enumerate(self.document.annotations):
            if annotation.page != page.source:
                continue
            if annotation.kind is Kind.COMMENT:
                left, top, right, bottom = self._upright_rectangle(page, annotation)
                hits[index] = Hit.ON if left <= point.x <= right and top <= point.y <= bottom else Hit.NONE
            else:
                hits[index] = hit(annotation, source_x, source_y, reach)
        return topmost(self.document.annotations, hits)

    def _upright_rectangle(self, page: ShownPage, annotation: Annotation) -> Rectangle:
        """Where a comment is on a page as shown: upright, keeping the corner that is its top left unturned."""
        left, top, right, bottom = annotation.rectangle
        corner_x, corner_y, _x, _y = page.from_source((left, top, left, top))
        return corner_x, corner_y, corner_x + right - left, corner_y + bottom - top

    def _ask_for_menu(self, x: float, y: float) -> None:
        """Ask for the menu of the annotation under a point, if there is one; elsewhere, nothing happens (D72)."""
        if self.text_editor is not None:
            self.text_editor.finish(apply=True)
        if self.handle_editor is not None:
            self.handle_editor.finish(apply=True)
        annotation = self.annotation_at(x, y)
        if annotation is not None:
            self.grab_focus()
            self.emit("annotation-menu-requested", AnnotationClick(annotation, x, y))

    def upright_square(self, source: int, x: float, y: float, side: float) -> Rectangle | None:
        """The square, on the unturned page, of an upright mark (a comment) shown centred on a point of it."""
        if self.renderer is None:
            return None
        position = self.renderer.layout.position(source)
        if position is None:
            return None
        page = self.renderer.layout[position]
        shown_x, shown_y, _x, _y = page.from_source((x, y, x, y))
        left, top = page.to_source(shown_x - side / 2, shown_y - side / 2)
        return left, top, left + side, top + side

    def _on_query_tooltip(self, _view: Gtk.Widget, x: int, y: int, _keyboard: bool, tooltip: Gtk.Tooltip) -> bool:
        comment = self.comment_at(x, y)
        if comment is None:
            return False
        tooltip.set_text(tooltip_text(comment.text))
        return True

    def link_at(self, x: float, y: float) -> Link | None:
        """Return the link under a point of the widget, if any."""
        point = self.page_point(x, y)
        if point is None or self.content is None or self.renderer is None:
            return None
        page = self.renderer.layout[point.page]
        return self.content.link_at(page.source, *page.to_source(point.x, point.y))

    def set_fields_active(self, active: bool) -> None:
        """Let the form fields answer the mouse (Select Text), or annotate over them (the other tools, I4)."""
        self._form_layer.set_active(active)

    def set_shape_maker(self, maker: "ShapeMaker | None") -> None:
        """Draw shapes with drags, made by maker from the page and the two ends; None to select text again."""
        self._shape_maker = maker
        self._shape_start = None
        self.set_preview(None)
        self.queue_draw()

    def write_text_box(  # noqa: PLR0913 (where, how wide, how it looks and what it says)
        self,
        page: int,
        corner: tuple[float, float],
        width: float,
        color: Color,
        *,
        style: Style | None = None,
        text: str = "",
    ) -> TextBoxEditor:
        """Start writing a text box on a page (by position), from a corner (points as shown); set its on_done.

        To edit one (D72), it has its format and starts with its text.
        """
        if self.text_editor is not None:
            self.text_editor.finish(apply=True)
        editor = TextBoxEditor(self, page, corner, width, color, style=style, text=text)
        self.text_editor = editor

        def done(_text: str | None) -> None:
            if self.text_editor is editor:
                self.text_editor = None
            self.grab_focus()

        editor.on_done = done
        self.queue_allocate()
        editor.grab_focus()
        return editor

    def set_preview(self, annotation: Annotation | None) -> None:
        """Show an annotation being made over its page (None: none)."""
        self._preview = annotation
        self.queue_draw()

    def _on_pressed(self, _gesture: Gtk.GestureClick, n_press: int, x: float, y: float) -> None:
        """A press starts a selection (or a shape); a double click selects a word and a triple click a line.

        While a text box is being written, a press outside it only applies it (H3).
        """
        if self.text_editor is not None:
            self.text_editor.finish(apply=True)
            return
        self.grab_focus()
        if self.handle_editor is not None:
            self.handle_editor.press(x, y)
            return
        if self._shape_maker is not None:
            self._set_selection(None)
            self._shape_start = self.page_point(x, y)
            return
        if self.placing:
            self._set_selection(None)
            self._click = self.page_point(x, y)
            return
        self._press = self.page_point(x, y)
        self._press_style = SELECTION_STYLES.get(min(n_press, 3), Poppler.SelectionStyle.GLYPH)
        self._dragging = False
        if self._press is not None and n_press > 1:
            self._set_selection(TextSelection(self._press, self._press, self._press_style))

    def _on_drag_update(self, gesture: Gtk.GestureDrag, offset_x: float, offset_y: float) -> None:
        if self.handle_editor is not None:
            _found, start_x, start_y = gesture.get_start_point()
            self.handle_editor.drag(start_x + offset_x, start_y + offset_y)
            return
        if self._shape_start is not None:
            self._draw_shape(gesture, offset_x, offset_y)
            return
        if self._press is None:
            return
        if not self._dragging and math.hypot(offset_x, offset_y) < DRAG_THRESHOLD:
            return
        self._dragging = True
        _found, start_x, start_y = gesture.get_start_point()
        focus = self.page_point(start_x + offset_x, start_y + offset_y, clamp=True)
        if focus is not None:
            self._set_selection(TextSelection(self._press, focus, self._press_style))

    def _draw_shape(self, gesture: Gtk.GestureDrag, offset_x: float, offset_y: float) -> None:
        """Show the shape from where the drag started to where it is now, kept inside the page it started on."""
        start = self._shape_start
        if start is None or self._shape_maker is None or self.renderer is None or self._hadjustment is None:
            return
        assert self._vadjustment is not None
        box = self._box(start.page)
        if box is None:
            return
        _found, start_x, start_y = gesture.get_start_point()
        page = self.renderer.layout[start.page]
        width, height = page.size
        end_x = (start_x + offset_x + self._hadjustment.get_value() - box.x) / self.zoom
        end_y = (start_y + offset_y + self._vadjustment.get_value() - box.y) / self.zoom
        end = (min(max(end_x, 0.0), width), min(max(end_y, 0.0), height))
        self.set_preview(self._shape_maker(page, (start.x, start.y), end))

    def _on_drag_end(self, gesture: Gtk.GestureDrag, offset_x: float, offset_y: float) -> None:
        """The end of a selection or a shape; a click without moving follows a link, or clears the selection."""
        if self.handle_editor is not None:
            self._on_drag_update(gesture, offset_x, offset_y)
            if self.handle_editor is not None:
                self.handle_editor.release()
            return
        if self._shape_start is not None:
            self._draw_shape(gesture, offset_x, offset_y)
            shape, self._shape_start = self._preview, None
            self.set_preview(None)
            if shape is not None:
                self.emit("shape-drawn", shape)
            return
        if self._click is not None:
            click, self._click = self._click, None
            _found, x, y = gesture.get_start_point()
            if self.renderer is not None and math.hypot(offset_x, offset_y) < DRAG_THRESHOLD:
                page = self.renderer.layout[click.page]
                source_x, source_y = page.to_source(click.x, click.y)
                self.emit("page-clicked", PageClick(page.source, (source_x, source_y), (x, y)))
            return
        if self._dragging or self._press_style is not Poppler.SelectionStyle.GLYPH:
            if self.selection is not None:
                self.emit("text-selected")
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

    def set_drawing_cursor(self, name: str | None) -> None:
        """Show this cursor over the pages, for a tool that draws; None for the usual ones (text, links)."""
        self._drawing_cursor = name
        if self._pointer is not None:
            self._show_cursor(*self._pointer)

    def _on_motion(self, _controller: Gtk.EventControllerMotion, x: float, y: float) -> None:
        self._pointer = (x, y)
        self._show_cursor(x, y)

    def _show_cursor(self, x: float, y: float) -> None:
        """The drawing tool's cursor over pages; without one, a hand over links and the text cursor over pages.

        The text cursor only if the PDF lets its text be copied (D59).
        """
        on_page = self.page_point(x, y) is not None
        if self.handle_editor is not None:
            self.set_cursor_from_name(self.handle_editor.cursor_at(x, y))
        elif self._drawing_cursor is not None:
            self.set_cursor_from_name(self._drawing_cursor if on_page else None)
        elif self.link_at(x, y) is not None:
            self.set_cursor_from_name("pointer")
        elif (self._can_copy or self.marking) and on_page:
            self.set_cursor_from_name("text")
        else:
            self.set_cursor_from_name(None)

    @property
    def _can_copy(self) -> bool:
        return self.document is None or self.document.permissions.copy

    def clear_selection(self) -> None:
        """Select no text."""
        self._set_selection(None)

    def selected_areas(self) -> dict[int, list[Rectangle]]:
        """The lines of text selected, by the source index of their pages, on the pages unturned (to mark them)."""
        if self.selection is None or self.content is None or self.renderer is None:
            return {}
        layout = self.renderer.layout
        areas = {}
        for position, selection in self.selection.page_selections(layout.sizes).items():
            page = layout[position]
            characters = self.content.selected_characters(
                page.source, source_selection(page, selection), self.selection.style
            )
            if characters:
                areas[page.source] = merge_lines(characters)
        return areas

    def _set_selection(self, selection: TextSelection | None) -> None:
        """Select text; a PDF that does not let its text be copied has none selected (D59), unless to mark it."""
        if selection is not None and not (self._can_copy or self.marking):
            return
        self.selection = selection
        self.queue_draw()

    def selected_text(self) -> tuple[str, int] | None:
        """The text selected and the page where the selection starts; None if no text is selected."""
        if self.selection is None or self.content is None or self.renderer is None:
            return None
        text = self.selection.text(self.content, self.renderer.layout)
        return (text, min(self.selection.anchor, self.selection.focus).page) if text else None

    def copy_selection(self) -> bool:
        """Copy the selected text to the clipboard, if the PDF allows it (D59); return whether there was any."""
        selected = self.selected_text() if self._can_copy else None
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
        if self.handle_editor is not None and self.handle_editor.key_pressed(keyval):
            return True
        control = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if control:
            return keyval in {Gdk.KEY_c, Gdk.KEY_C} and self.copy_selection()
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
