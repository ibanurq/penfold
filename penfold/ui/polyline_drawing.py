"""Drawing a polyline click by click on a page.

Each click puts a vertex, and a stretch of line goes from the last one to the pointer until the next click. A double
click or Enter finishes it (the double click puts the last vertex, once); Esc cancels it, and Backspace takes away the
last vertex. Every vertex stays inside the page of the first. It is shown as it will look, in the colour chosen, and
made once finished if it has two vertices or more and is not too small to be seen (document/reshaping.py,
SMALLEST_SIZE). The document view owns the drawer and passes it the mouse and the keys.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING

from gi.repository import Gdk

from penfold.document.annotations import FEWEST_VERTICES, Annotation
from penfold.document.reshaping import SMALLEST_SIZE
from penfold.rendering.layout import ShownPage

if TYPE_CHECKING:
    from penfold.ui.document_view import DocumentView

Point = tuple[float, float]
# Makes the polyline through vertices of a page (points as shown), to show it; None if it cannot be.
PolylineMaker = Callable[[ShownPage, list[Point]], Annotation | None]


class PolylineDrawer:
    """The polyline being drawn; on_drawn gets its page and its vertices (points as shown) once it is finished."""

    def __init__(
        self, view: "DocumentView", make: PolylineMaker, on_drawn: Callable[[ShownPage, list[Point]], None]
    ) -> None:
        """Draw polylines on the pages of a view, shown as make makes them."""
        self._view = view
        self._make = make
        self._on_drawn = on_drawn
        # The page of the polyline being drawn, its vertices, and where the pointer is on that page.
        self._page: ShownPage | None = None
        self.vertices: list[Point] = []
        self._pointer: Point | None = None

    @property
    def drawing(self) -> bool:
        """Whether a polyline is being drawn: it has a vertex at least."""
        return bool(self.vertices)

    def press(self, x: float, y: float, n_press: int) -> None:
        """A press, at a point of the view, puts a vertex there; the second of a double click finishes the polyline.

        The first vertex goes on the page under the press (none off the pages); the others, on that page, as near as
        they can be.
        """
        if n_press > 1 and self.drawing:
            self.finish()
            return
        if not self.drawing:
            found = self._view.page_point(x, y)
            renderer = self._view.renderer
            if found is None or renderer is None:
                return
            self._page = renderer.layout[found.page]
        point = self._on_page(x, y)
        if point is None:
            return
        if not self.vertices or point != self.vertices[-1]:
            self.vertices.append(point)
        self._pointer = point
        self._show()

    def hover(self, x: float, y: float) -> None:
        """Follow the pointer, at a point of the view, with the stretch of line from the last vertex."""
        if self.drawing:
            self._pointer = self._on_page(x, y)
            self._show()

    def key_pressed(self, keyval: int) -> bool:
        """Enter finishes the polyline, Esc cancels it and Backspace takes away its last vertex.

        Return whether the key was used: only while a polyline is being drawn.
        """
        if not self.drawing:
            return False
        if keyval in {Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_ISO_Enter}:
            self.finish()
        elif keyval == Gdk.KEY_Escape:
            self.cancel()
        elif keyval == Gdk.KEY_BackSpace:
            self.vertices.pop()
            self._show()
        else:
            return False
        return True

    def finish(self) -> None:
        """Make the polyline drawn, if it can be, and start again."""
        page, vertices = self._page, self.vertices
        self.cancel()
        if page is not None and len(vertices) >= FEWEST_VERTICES and _extent(vertices) >= SMALLEST_SIZE:
            self._on_drawn(page, vertices)

    def cancel(self) -> None:
        """Forget the polyline being drawn."""
        shown = self._page is not None
        self._page, self.vertices, self._pointer = None, [], None
        if shown:
            self._view.set_preview(None)

    def _on_page(self, x: float, y: float) -> Point | None:
        """A point of the view on the page of the polyline, as near as it can be inside it."""
        point = None if self._page is None else self._view.point_on_page(self._page, x, y)
        if self._page is None or point is None:
            return None
        width, height = self._page.size
        return min(max(point[0], 0.0), width), min(max(point[1], 0.0), height)

    def _show(self) -> None:
        """Show the polyline as it is, with a stretch from its last vertex to the pointer; nothing without vertices."""
        if self._page is None or not self.vertices:
            self.cancel()
            return
        points = list(self.vertices)
        if self._pointer is not None and self._pointer != points[-1]:
            points.append(self._pointer)
        self._view.set_preview(self._make(self._page, points) if len(points) >= FEWEST_VERTICES else None)


def _extent(points: list[Point]) -> float:
    """How far the points reach, across or down, whichever is more."""
    xs, ys = [x for x, _y in points], [y for _x, y in points]
    return max(max(xs) - min(xs), max(ys) - min(ys))
