"""Moving an annotation and changing its size on its page, with handles.

While it is edited, the annotation shows as it is being changed, over a thin frame in the accent colour and with its
handles. Dragging a handle changes its size; dragging it from anywhere else on it moves it. Enter or a click
outside it accept the change; Esc cancels it. The document view owns the editor and passes it the mouse and the keys.

Rectangles, circles and freehand drawings have a handle at each corner (document/reshaping.py); text boxes one at each
side, which change only their width: the text is laid out again as it is dragged, and the box is as tall as it needs
(text_box.py); arrows one at each end, and they move when their line is dragged (anywhere else, a press accepts the
change). Comments have no handles: they keep their size, and are only moved. Marks on text have a handle where they
start and one where they end: each covers the text up to the other, letter by letter, as a selection does; they do not
move. Theirs are drops, as the touch selection handles of GNOME: the start one above the first letter, the end one
below the last.
"""

import math
from collections.abc import Callable
from typing import TYPE_CHECKING

from gi.repository import Adw, Gdk, Graphene, Gsk, Gtk, Poppler

from penfold.document.annotations import TEXT_MARKUPS, Annotation, Hit, Kind, hit, managed_copy
from penfold.document.geometry import merge_lines, turn_point
from penfold.document.reshaping import (
    Handle,
    Point,
    corner_handles,
    end_handles,
    mark_handles,
    mark_tips,
    moved,
    with_corner,
    with_end,
    with_lines,
)
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
CORNER_KINDS = frozenset({Kind.RECTANGLE, Kind.CIRCLE, Kind.FREEHAND})
SIDE_KINDS = frozenset({Kind.TEXT_BOX})
END_KINDS = frozenset({Kind.ARROW})
# The frame is left out where the handles show the annotation well enough, or it would be an empty box around it.
UNFRAMED_KINDS = END_KINDS | TEXT_MARKUPS
# The drop handles of marks on text: Adwaita's icons, drawn this big in pixels; where their tip is, and the part of them
# that a press takes (left, top, right, bottom), as fractions of their size. Their tip is on the text.
DROP_SIZE = 32
DROP_ICONS = {Handle.START: "selection-start-symbolic", Handle.END: "selection-end-symbolic"}
DROP_TIPS = {Handle.START: (11 / 16, 13.6 / 16), Handle.END: (5 / 16, 2.4 / 16)}
DROP_BODY = (3 / 16, 1 / 16, 13 / 16, 15 / 16)
# How far inside the text a mark keeps the end not dragged, in points, so that its first or last letter stays in.
INSIDE_THE_TEXT = 1.0


class HandleEditor:
    """The handles of an annotation of a page, and the change they are making to it."""

    def __init__(
        self,
        view: "DocumentView",
        annotation: Annotation,
        on_done: Callable[[Annotation | None], None],
        *,
        resizable: bool,
        shown: Annotation | None = None,
    ) -> None:
        """Edit an annotation of the document on its page; without handles if it is not resizable (it only moves).

        on_done receives the annotation changed when the change is accepted, or None if it is cancelled or nothing
        changed. One of a PDF that Penfold does not manage is moved as it is, keeping its drawing; a handle makes it
        managed, drawn again by Penfold. It shows as shown (by default, as it is) until it changes.
        """
        self._view = view
        self.original = annotation
        self.annotation = shown or annotation
        self.on_done = on_done
        self._resizable = resizable
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
        on_annotation = self._is_on_annotation(page, point)
        if grabbed is None and not on_annotation:
            self.finish(apply=True)
            return
        if grabbed is None and self.annotation.kind in TEXT_MARKUPS:
            return  # Marks do not move: a press on one does nothing.
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
            self._view.set_preview(self.annotation)
            return
        handle_x, handle_y = _handles(page, begun_with)[self._grabbed]
        target = (handle_x + offset[0], handle_y + offset[1])
        if begun_with.kind in TEXT_MARKUPS:
            self.annotation = self._marking(page, managed_copy(begun_with), self._grabbed, target)
        else:
            self.annotation = _dragged(page, managed_copy(begun_with), self._grabbed, target)
        self._view.set_preview(self.annotation)

    def _marking(self, page: ShownPage, mark: Annotation, end: Handle, point: Point) -> Annotation:
        """A mark covering the text from its end not dragged to a point of its page, letter by letter.

        Without text there, it stays as it was.
        """
        content = self._view.content
        if content is None:
            return mark
        width, height = page.source_size
        focus = (min(max(point[0], 0.0), width), min(max(point[1], 0.0), height))
        handles = mark_handles(mark)
        kept_x, kept_y = handles[Handle.END if end is Handle.START else Handle.START]
        kept_x += -INSIDE_THE_TEXT if end is Handle.START else INSIDE_THE_TEXT
        selection = (kept_x, kept_y, *focus) if end is Handle.END else (*focus, kept_x, kept_y)
        characters = content.selected_characters(page.source, selection, Poppler.SelectionStyle.GLYPH)
        return with_lines(mark, merge_lines(characters))

    def release(self) -> None:
        """The end of a drag."""
        self._grabbed = None
        self._drag_start = None

    def finish(self, *, apply: bool) -> None:
        """Stop editing: accept the change (if its place or size changed) or cancel it.

        A handle taken back where it was changes nothing: one of a PDF stays as its program made it.
        """
        self.release()
        self._view.stop_handle_editing(self)
        now, before = self.annotation, self.original
        changed = apply and _place(now) != _place(before)
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
        if self.annotation.kind in TEXT_MARKUPS:
            return self._drop_at(page, x, y)
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
        if bounds is None or self.annotation.kind in UNFRAMED_KINDS:
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
        if self.annotation.kind in TEXT_MARKUPS:
            for handle, (tip_x, tip_y) in self._shown_tips(page).items():
                self._append_drop(snapshot, handle, (x + tip_x * zoom, y + tip_y * zoom), page.rotation, color)
            return
        for handle_x, handle_y in self._shown_handles(page).values():
            _append_handle(snapshot, (x + handle_x * zoom, y + handle_y * zoom), color)

    def _append_drop(self, snapshot: Gtk.Snapshot, handle: Handle, tip: Point, rotation: int, color: Gdk.RGBA) -> None:
        """A drop handle with its tip at a point (pixels of the view), turned as its page."""
        icon = Gtk.IconTheme.get_for_display(self._view.get_display()).lookup_icon(
            DROP_ICONS[handle],
            None,
            DROP_SIZE,
            self._view.get_scale_factor(),
            Gtk.TextDirection.NONE,
            Gtk.IconLookupFlags(0),
        )
        tip_x, tip_y = DROP_TIPS[handle]
        snapshot.save()
        snapshot.translate(Graphene.Point().init(*tip))
        snapshot.rotate(rotation)
        snapshot.translate(Graphene.Point().init(-tip_x * DROP_SIZE, -tip_y * DROP_SIZE))
        icon.snapshot_symbolic(snapshot, DROP_SIZE, DROP_SIZE, [color] * 4)
        snapshot.restore()

    def _shown_tips(self, page: ShownPage) -> dict[Handle, Point]:
        """Where the tips of a mark's drops are on the page as shown, in points."""
        if not self._resizable:
            return {}
        return {
            handle: turn_point(*point, page.source_size, page.rotation)
            for handle, point in mark_tips(self.annotation).items()
        }

    def _drop_at(self, page: ShownPage, x: float, y: float) -> Handle | None:
        """The drop under a point of the view, if any (the one whose middle is nearest)."""
        reached = []
        for handle, tip in self._shown_tips(page).items():
            distance = _distance_into_drop(handle, self._view.point_in_view(page, tip), page.rotation, (x, y))
            if distance is not None:
                reached.append((distance, handle))
        return min(reached, key=lambda item: item[0])[1] if reached else None

    def _shown_handles(self, page: ShownPage) -> dict[Handle, Point]:
        """Where the handles are on the page as shown, in points: none if the annotation only moves."""
        return _shown_handles(page, self.annotation) if self._resizable else {}

    def _view_handles(self, page: ShownPage) -> dict[Handle, Point]:
        """Where the handles are in the view, in pixels."""
        return {handle: self._view.point_in_view(page, point) for handle, point in self._shown_handles(page).items()}

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
        handle_x, handle_y = self._shown_handles(page)[handle]
        if bounds is None:
            return "move"
        left, top, right, bottom = bounds
        across, down = handle_x - (left + right) / 2, handle_y - (top + bottom) / 2
        if handle in {Handle.START, Handle.END}:  # An end of a mark follows the text; that of an arrow goes anywhere.
            return "text" if self.annotation.kind in TEXT_MARKUPS else "crosshair"
        if handle in {Handle.LEFT, Handle.RIGHT}:  # In the middle of a side: it stretches one way only.
            return "ew-resize" if abs(across) > abs(down) else "ns-resize"
        return "nwse-resize" if (across > 0) == (down > 0) else "nesw-resize"


def _place(annotation: Annotation) -> tuple[object, ...]:
    """Where an annotation is and how big: what moving it or its handles changes."""
    return annotation.rectangle, annotation.line, annotation.quads, annotation.strokes


def _handles(page: ShownPage, annotation: Annotation) -> dict[Handle, Point]:
    """Where an annotation's handles are, on its unturned page."""
    if annotation.kind in CORNER_KINDS:
        return corner_handles(annotation)
    if annotation.kind in SIDE_KINDS:
        return side_handles(annotation, page.source_size)
    if annotation.kind in END_KINDS:
        return end_handles(annotation)
    if annotation.kind in TEXT_MARKUPS:
        return mark_handles(annotation)
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


def _distance_into_drop(handle: Handle, tip: Point, rotation: int, point: Point) -> float | None:
    """How far a point is from the middle of a drop with its tip at a point and turned clockwise; None if off it."""
    angle = math.radians(rotation)
    across, down = point[0] - tip[0], point[1] - tip[1]
    # The point in the drop's own square, before it was turned around its tip.
    tip_x, tip_y = DROP_TIPS[handle]
    x = across * math.cos(angle) + down * math.sin(angle) + tip_x * DROP_SIZE
    y = down * math.cos(angle) - across * math.sin(angle) + tip_y * DROP_SIZE
    left, top, right, bottom = (side * DROP_SIZE for side in DROP_BODY)
    if not (left <= x <= right and top <= y <= bottom):
        return None
    return math.hypot(x - (left + right) / 2, y - (top + bottom) / 2)
