"""Drawing polylines click by click with the Polyline tool."""

from typing import TYPE_CHECKING

import pytest
from gi.repository import Gdk

from penfold.document.annotations import Annotation, Kind, LineEnds
from penfold.document.commands.pages import RotatePages
from penfold.ui.annotation_toolbar import TOOL_GROUPS, Tool
from tests.gtk_helpers import process_pending_events
from tests.test_document_window import window
from tests.test_shape_drawing import choose, made, shape_window, widget_point

if TYPE_CHECKING:
    from penfold.ui.window import PenfoldWindow

__all__ = ["shape_window", "window"]


def click(window: "PenfoldWindow", point: tuple[float, float], n_press: int = 1, page: int = 0) -> None:
    """A press at a point of a page as shown (the pointer goes there first), as the mouse does."""
    x, y = widget_point(window, page, *point)
    view = window.document_view
    view._on_motion(None, x, y)  # type: ignore[arg-type]
    view._on_pressed(None, n_press, x, y)  # type: ignore[arg-type]
    process_pending_events()


def hover(window: "PenfoldWindow", point: tuple[float, float], page: int = 0) -> None:
    window.document_view._on_motion(None, *widget_point(window, page, *point))  # type: ignore[arg-type]


def press_key(window: "PenfoldWindow", keyval: int) -> bool:
    used = window.document_view._on_key_pressed(None, keyval, 0, Gdk.ModifierType(0))  # type: ignore[arg-type]
    process_pending_events()
    return used


def preview(window: "PenfoldWindow") -> Annotation | None:
    return window.document_view._preview


def flat(points: tuple[tuple[float, float], ...]) -> list[float]:
    return [value for point in points for value in point]


def test_it_comes_between_the_arrow_and_freehand() -> None:
    shapes = next(group for group in TOOL_GROUPS if Tool.ARROW in group)
    assert shapes.index(Tool.POLYLINE) == shapes.index(Tool.ARROW) + 1
    assert shapes.index(Tool.FREEHAND) == shapes.index(Tool.POLYLINE) + 1


def test_each_click_puts_a_vertex_and_a_double_click_finishes_it(shape_window: "PenfoldWindow") -> None:
    window = shape_window
    choose(window, Tool.POLYLINE)
    click(window, (100, 100))
    assert preview(window) is None  # One vertex: nothing to see yet.
    hover(window, (200, 150))
    shown = preview(window)
    assert shown is not None
    assert flat(shown.vertices) == pytest.approx([100, 100, 200, 150])  # A stretch to the pointer.
    click(window, (200, 150))
    click(window, (300, 100))
    click(window, (300, 100), n_press=2)  # The second press of a double click: it puts no vertex.
    (polyline,) = made(window)
    assert (polyline.kind, polyline.page) == (Kind.POLYLINE, 0)
    assert flat(polyline.vertices) == pytest.approx([100, 100, 200, 150, 300, 100])
    assert polyline.rectangle == pytest.approx((100, 100, 300, 150))
    assert (polyline.style.line_width, polyline.style.line_ends) == (1.0, LineEnds.NONE)  # As new ones are.
    assert preview(window) is None
    assert window.annotating.tool is Tool.POLYLINE  # It stays.
    window.activate_action("win.undo", None)
    assert made(window) == []


def test_enter_finishes_it_and_backspace_takes_away_the_last_vertex(shape_window: "PenfoldWindow") -> None:
    window = shape_window
    choose(window, Tool.POLYLINE)
    assert not press_key(window, Gdk.KEY_BackSpace)  # Nothing drawn: the key is not for it.
    for point in ((100, 100), (200, 200), (300, 100)):
        click(window, point)
    assert press_key(window, Gdk.KEY_BackSpace)
    shown = preview(window)
    assert shown is not None
    assert flat(shown.vertices) == pytest.approx([100, 100, 200, 200, 300, 100])  # To the pointer, still there.
    hover(window, (250, 300))
    assert press_key(window, Gdk.KEY_Return)
    (polyline,) = made(window)
    assert flat(polyline.vertices) == pytest.approx([100, 100, 200, 200])  # The pointer puts no vertex.


def test_esc_cancels_it_and_the_tool_stays(shape_window: "PenfoldWindow") -> None:
    window = shape_window
    choose(window, Tool.POLYLINE)
    click(window, (100, 100))
    click(window, (200, 200))
    assert press_key(window, Gdk.KEY_Escape)
    assert (made(window), preview(window), window.annotating.tool) == ([], None, Tool.POLYLINE)
    assert not press_key(window, Gdk.KEY_Escape)  # Nothing drawn: the window takes it (back to Select Text).


def test_with_fewer_than_two_vertices_or_too_small_nothing_is_made(shape_window: "PenfoldWindow") -> None:
    window = shape_window
    choose(window, Tool.POLYLINE)
    click(window, (100, 100))
    press_key(window, Gdk.KEY_Return)
    click(window, (100, 100))
    click(window, (101, 102))
    click(window, (101, 102), n_press=2)
    click(window, (100, 100))
    press_key(window, Gdk.KEY_BackSpace)  # Its only vertex: nothing is being drawn any more.
    assert (made(window), preview(window)) == ([], None)


def test_every_vertex_stays_inside_the_page_of_the_first(shape_window: "PenfoldWindow") -> None:
    window = shape_window
    choose(window, Tool.POLYLINE)
    view = window.document_view
    view._on_pressed(None, 1, 2, 2)  # type: ignore[arg-type]  # Off the pages: no vertex.
    assert view.polyline_drawer is not None
    assert not view.polyline_drawer.drawing
    click(window, (500, 800))
    click(window, (650, 900))  # Past the page's corner.
    press_key(window, Gdk.KEY_Return)
    (polyline,) = made(window)
    assert flat(polyline.vertices) == pytest.approx([500, 800, 595, 842])


def test_another_tool_cancels_it_and_saving_finishes_it(shape_window: "PenfoldWindow") -> None:
    window = shape_window
    choose(window, Tool.POLYLINE)
    click(window, (100, 100))
    click(window, (200, 200))
    choose(window, Tool.RECTANGLE)
    assert (made(window), preview(window), window.document_view.polyline_drawer) == ([], None, None)
    choose(window, Tool.POLYLINE)
    click(window, (100, 100))
    click(window, (200, 200))
    window.document_view.finish_editing()  # As before saving: as Enter.
    assert len(made(window)) == 1


def test_on_a_turned_page_it_is_kept_on_the_unturned_page(shape_window: "PenfoldWindow") -> None:
    window = shape_window
    assert window.document is not None
    window.document.execute(RotatePages(window.document, [0], 90))
    process_pending_events()
    choose(window, Tool.POLYLINE)
    click(window, (100, 100))
    click(window, (300, 200))
    press_key(window, Gdk.KEY_Return)
    (polyline,) = made(window)
    assert flat(polyline.vertices) == pytest.approx([100, 742, 200, 542])  # A quarter turn back.
