"""Moving an annotation and changing its size on its page, with handles (D72, D73).

While it is edited, the annotation shows as it is being changed, over a thin frame in the accent colour and with its
handles. Dragging a handle changes its size; dragging it from anywhere else on it moves it. Enter or a click
outside it accept the change; Esc cancels it. The document view owns the editor and passes it the mouse and the keys.

Rectangles and circles have a handle at each corner (document/reshaping.py); text boxes one at each side, which change
only their width: the text is laid out again as it is dragged, and the box is as tall as it needs (text_box.py);
arrows one at each end, and they move when their line is dragged (anywhere else, a press accepts the change).
"""

from collections.abc import Callable
from typing import TYPE_CHECKING

from gi.repository import Adw, Gdk, Graphene, Gsk, Gtk

from penfold.document.annotations import Annotation, Hit, Kind, hit
from penfold.document.geometry import turn_point
from penfold.document.reshaping import Handle, Point, corner_handles, end_handles, moved, with_corner, with_end
from penfold.rendering.layout import ShownPage
from penfold.rendering.text_box import side_handles, with_side

if TYPE_CHECKING:
    from penfold.ui.document_view import DocumentView

# The handles: their radius and the width of their ring, and how far from one a press still takes it, in pixels.
HANDLE_RADIUS = 5.0
HANDLE_RING = 1.5
HANDLE_REACH = 9.0
# The frame around the annotation, in pixels.
FRAME_WIDTH = 1.0
WHITE = (1.0, 1.0, 1.0, 1.0)
CORNER_KINDS = frozenset({Kind.RECTANGLE, Kind.CIRCLE})
SIDE_KINDS = frozenset({Kind.TEXT_BOX})
END_KINDS = frozenset({Kind.ARROW})


def has_handles(annotation: Annotation) -> bool:
    """Whether an annotation is edited with handles."""
    return annotation.kind in CORNER_KINDS | SIDE_KINDS | END_KINDS


class HandleEditor:
    """The handles of an annotation of a page, and the change they are making to it."""

    def __init__(
        self,
        view: "DocumentView",
        annotation: Annotation,
        original: Annotation,
        on_done: Callable[[Annotation | None], None],
    ) -> None:
        """Edit an annotation (a managed copy of the original in the document) on its page.

        on_done receives the annotation changed when the change is accepted, or None if it is cancelled or nothing
        changed.
        """
        self._view = view
        self.original = original
        self.annotation = annotation
        self._started_with = annotation
        self.on_done = on_done
        # While dragging: the handle taken (None: moving the whole annotation), the annotation and the point (on the
        # unturned page) where the drag started.
        self._grabbed: Handle | None = None
        self._drag_start: tuple[Annotation, Point] | None = None

    @property
    def dragging(self) -> bool:
        """Whether a handle, or the annotation, is being dragged."""
        return self._drag_start is not None

    def press(self, x: float, y: float) -> None:
        """A press on the view: on a handle or on the annotation, a drag starts; elsewhere, the change is accepted."""
        page = self._view.shown_page(self.annotation.page)
        point = None if page is None else self._view.point_on_page(page, x, y)
        if page is None or point is None:
            self.finish(apply=True)
            return
        grabbed = self.handle_at(x, y)
        if grabbed is None and not self._is_on_annotation(page, point):
            self.finish(apply=True)
            return
        self._grabbed = grabbed
        self._drag_start = (self.annotation, page.to_source(*point))

    def drag(self, x: float, y: float) -> None:
        """Follow the pointer, at a point of the view, while dragging."""
        page = self._view.shown_page(self.annotation.page)
        point = None if page is None else self._view.point_on_page(page, x, y)
        if self._drag_start is None or page is None or point is None:
            return
        begun_with, (start_x, start_y) = self._drag_start
        now_x, now_y = page.to_source(*point)
        offset = (now_x - start_x, now_y - start_y)
        if self._grabbed is None:
            self.annotation = moved(begun_with, offset, page.source_size)
        else:
            handle_x, handle_y = _handles(page, begun_with)[self._grabbed]
            target = (handle_x + offset[0], handle_y + offset[1])
            self.annotation = _dragged(page, begun_with, self._grabbed, target)
        self._view.set_preview(self.annotation)

    def release(self) -> None:
        """The end of a drag."""
        self._grabbed = None
        self._drag_start = None

    def finish(self, *, apply: bool) -> None:
        """Stop editing: accept the change (if anything changed) or cancel it."""
        self.release()
        self._view.stop_handle_editing(self)
        changed = apply and self.annotation != self._started_with
        self.on_done(self.annotation if changed else None)

    def key_pressed(self, keyval: int) -> bool:
        """Enter accepts the change and Esc cancels it; return whether the key was used."""
        if keyval in {Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_ISO_Enter}:
            self.finish(apply=True)
            return True
        if keyval == Gdk.KEY_Escape:
            self.finish(apply=False)
            return True
        return False

    def handle_at(self, x: float, y: float) -> Handle | None:
        """The handle under a point of the view, if any (the nearest)."""
        page = self._view.shown_page(self.annotation.page)
        if page is None:
            return None
        reached = []
        for handle, (handle_x, handle_y) in self._view_handles(page).items():
            distance = max(abs(x - handle_x), abs(y - handle_y))
            if distance <= HANDLE_REACH:
                reached.append((distance, handle))
        return min(reached, key=lambda item: item[0])[1] if reached else None

    def cursor_at(self, x: float, y: float) -> str | None:
        """The cursor over a point of the view: one that resizes over a handle, one that moves over the annotation."""
        page = self._view.shown_page(self.annotation.page)
        point = None if page is None else self._view.point_on_page(page, x, y)
        if page is None or point is None:
            return None
        handle = self._grabbed if self.dragging else self.handle_at(x, y)
        if handle is not None:
            return self._resize_cursor(page, handle)
        if (self.dragging and self._grabbed is None) or self._is_on_annotation(page, point):
            return "move"
        return None

    def snapshot_frame(self, snapshot: Gtk.Snapshot, page: ShownPage, origin: Point, zoom: float) -> None:
        """Draw the frame around the annotation, under it, over a page drawn from origin (pixels of the view).

        Under it, so that the frame shows only where the annotation has no line of its own (around a circle).
        """
        bounds = self._view.annotation_bounds(page, self.annotation)
        if bounds is None or self.annotation.kind in END_KINDS:  # Its handles at its ends show it well enough.
            return
        left, top, right, bottom = bounds
        x, y = origin
        frame = Gsk.RoundedRect()  # init_from_rect fills it in place (what it returns is empty in Python).
        frame.init_from_rect(
            Graphene.Rect().init(x + left * zoom, y + top * zoom, (right - left) * zoom, (bottom - top) * zoom), 0
        )
        color = Adw.StyleManager.get_default().get_accent_color_rgba()
        snapshot.append_border(frame, [FRAME_WIDTH] * 4, [color] * 4)

    def snapshot_handles(self, snapshot: Gtk.Snapshot, page: ShownPage, origin: Point, zoom: float) -> None:
        """Draw the handles over the annotation, if it is on this page drawn from origin (pixels of the view)."""
        if self.annotation.page != page.source:
            return
        color = Adw.StyleManager.get_default().get_accent_color_rgba()
        x, y = origin
        for handle_x, handle_y in _shown_handles(page, self.annotation).values():
            _append_handle(snapshot, (x + handle_x * zoom, y + handle_y * zoom), color)

    def _view_handles(self, page: ShownPage) -> dict[Handle, Point]:
        """Where the handles are in the view, in pixels."""
        return {
            handle: self._view.point_in_view(page, point)
            for handle, point in _shown_handles(page, self.annotation).items()
        }

    def _is_on_annotation(self, page: ShownPage, point: Point) -> bool:
        """Whether a point of the page as shown is on the annotation: on an arrow's line, or anywhere in its frame."""
        if self.annotation.kind in END_KINDS:
            reach = HANDLE_REACH / self._view.zoom
            return hit(self.annotation, *page.to_source(*point), reach) is not Hit.NONE
        bounds = self._view.annotation_bounds(page, self.annotation)
        if bounds is None:
            return False
        left, top, right, bottom = bounds
        x, y = point
        return left <= x <= right and top <= y <= bottom

    def _resize_cursor(self, page: ShownPage, handle: Handle) -> str:
        """The cursor of a handle, by where it is from the middle of the annotation as shown (pages turn)."""
        bounds = self._view.annotation_bounds(page, self.annotation)
        handle_x, handle_y = _shown_handles(page, self.annotation)[handle]
        if bounds is None:
            return "move"
        left, top, right, bottom = bounds
        across, down = handle_x - (left + right) / 2, handle_y - (top + bottom) / 2
        if handle in {Handle.START, Handle.END}:  # An end goes anywhere.
            return "crosshair"
        if handle in {Handle.LEFT, Handle.RIGHT}:  # In the middle of a side: it stretches one way only.
            return "ew-resize" if abs(across) > abs(down) else "ns-resize"
        return "nwse-resize" if (across > 0) == (down > 0) else "nesw-resize"


def _handles(page: ShownPage, annotation: Annotation) -> dict[Handle, Point]:
    """Where an annotation's handles are, on its unturned page."""
    if annotation.kind in CORNER_KINDS:
        return corner_handles(annotation)
    if annotation.kind in SIDE_KINDS:
        return side_handles(annotation, page.source_size)
    if annotation.kind in END_KINDS:
        return end_handles(annotation)
    return {}


def _dragged(page: ShownPage, annotation: Annotation, handle: Handle, point: Point) -> Annotation:
    """The annotation with one of its handles taken to a point of its unturned page."""
    if annotation.kind in SIDE_KINDS:
        return with_side(annotation, handle, point, page.source_size)
    if annotation.kind in END_KINDS:
        return with_end(annotation, handle, point, page.source_size)
    return with_corner(annotation, handle, point, page.source_size)


def _shown_handles(page: ShownPage, annotation: Annotation) -> dict[Handle, Point]:
    """Where an annotation's handles are on its page as shown, in points."""
    return {
        handle: turn_point(*point, page.source_size, page.rotation)
        for handle, point in _handles(page, annotation).items()
    }


def _append_handle(snapshot: Gtk.Snapshot, centre: Point, color: Gdk.RGBA) -> None:
    """A handle: a white dot with a ring in the accent colour."""
    x, y = centre
    square = Graphene.Rect().init(x - HANDLE_RADIUS, y - HANDLE_RADIUS, 2 * HANDLE_RADIUS, 2 * HANDLE_RADIUS)
    circle = Gsk.RoundedRect()
    circle.init_from_rect(square, HANDLE_RADIUS)
    snapshot.push_rounded_clip(circle)
    white = Gdk.RGBA()
    white.red, white.green, white.blue, white.alpha = WHITE
    snapshot.append_color(white, square)
    snapshot.pop()
    snapshot.append_border(circle, [HANDLE_RING] * 4, [color] * 4)
