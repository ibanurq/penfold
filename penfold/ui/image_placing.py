"""Putting an image on a page: a thin frame of its size follows the pointer, and a click or a drag puts it there.

Once its file is chosen, the frame shows where the image goes and how big it is, with its top left corner at the
pointer, all inside the page (document/reshaping.py, placed). A click puts it there; a drag frames it from where it
started, keeping its proportion (dragged). The document view owns the placer and passes it the mouse.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING

from gi.repository import Adw, Graphene, Gsk, Gtk

from penfold.document.geometry import Rectangle, Size
from penfold.document.reshaping import dragged, placed
from penfold.rendering.layout import ShownPage

if TYPE_CHECKING:
    from penfold.ui.document_view import DocumentView

Point = tuple[float, float]
# The frame's line, in pixels.
FRAME_WIDTH = 1.0


class ImagePlacer:
    """The frame of an image being put on a page; on_placed gets the page and the rectangle (points as shown)."""

    def __init__(self, view: "DocumentView", size: Size, on_placed: Callable[[ShownPage, Rectangle], None]) -> None:
        """Place an image of a size (points as it is seen) on the pages of a view."""
        self._view = view
        self._size = size
        self._on_placed = on_placed
        # The page the frame is on (its position) and where it is on it; and, while dragging, where the drag started.
        self.frame: tuple[int, Rectangle] | None = None
        self._start: tuple[ShownPage, Point] | None = None

    def hover(self, x: float, y: float) -> None:
        """Follow the pointer, at a point of the view: over a page, the frame is there; elsewhere, none."""
        if self._start is not None:
            return
        found = self._view.page_point(x, y)
        renderer = self._view.renderer
        if found is None or renderer is None:
            self._show(None)
            return
        page = renderer.layout[found.page]
        self._show((found.page, placed((found.x, found.y), self._size, page.size)))

    def leave(self) -> None:
        """The pointer left the view: no frame, unless dragging."""
        if self._start is None:
            self._show(None)

    def press(self, x: float, y: float) -> None:
        """A press on a page starts the image there (a click puts it as the frame shows it)."""
        found = self._view.page_point(x, y)
        renderer = self._view.renderer
        if found is None or renderer is None:
            return
        page = renderer.layout[found.page]
        self._start = (page, (found.x, found.y))
        self._show((found.page, placed((found.x, found.y), self._size, page.size)))

    def drag(self, x: float, y: float) -> None:
        """Frame the image from where the drag started to the pointer, at a point of the view."""
        if self._start is None:
            return
        page, start = self._start
        point = self._view.point_on_page(page, x, y)
        position = self._position(page)
        if point is None or position is None:
            return
        rectangle = dragged(start, point, self._size, page.size) or placed(start, self._size, page.size)
        self._show((position, rectangle))

    def release(self, x: float, y: float) -> None:
        """Put the image where the frame is."""
        self.drag(x, y)
        if self._start is None or self.frame is None:
            return
        page, _start = self._start
        _position, rectangle = self.frame
        self._start = None
        self._on_placed(page, rectangle)

    def snapshot(self, snapshot: Gtk.Snapshot, position: int, origin: Point, zoom: float) -> None:
        """Draw the frame, if it is on the page at a position, drawn from origin (pixels of the view)."""
        if self.frame is None or self.frame[0] != position:
            return
        left, top, right, bottom = self.frame[1]
        x, y = origin
        frame = Gsk.RoundedRect()  # init_from_rect fills it in place (what it returns is empty in Python).
        frame.init_from_rect(
            Graphene.Rect().init(x + left * zoom, y + top * zoom, (right - left) * zoom, (bottom - top) * zoom), 0
        )
        color = Adw.StyleManager.get_default().get_accent_color_rgba()
        snapshot.append_border(frame, [FRAME_WIDTH] * 4, [color] * 4)

    def _position(self, page: ShownPage) -> int | None:
        renderer = self._view.renderer
        return None if renderer is None else renderer.layout.position(page.source)

    def _show(self, frame: tuple[int, Rectangle] | None) -> None:
        if frame != self.frame:
            self.frame = frame
            self._view.queue_draw()
