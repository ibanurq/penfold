"""Drawing rectangles, circles and arrows by dragging (H4)."""

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from gi.repository import GLib

from penfold.document.annotations import Annotation, Kind
from penfold.document.commands.pages import RotatePages
from penfold.ui.annotation_toolbar import Tool
from tests.sample_pdfs import make_pdf
from tests.test_document_window import open_and_wait, window

if TYPE_CHECKING:
    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]
A4 = (595.0, 842.0)


class FakeDrag:
    """Where a drag started, as a Gtk.GestureDrag says."""

    def __init__(self, x: float, y: float) -> None:
        self.start = (x, y)

    def get_start_point(self) -> tuple[bool, float, float]:
        return True, *self.start


@pytest.fixture
def shape_window(window: "PenfoldWindow", tmp_path: Path) -> "PenfoldWindow":
    assert open_and_wait(window, make_pdf(tmp_path / "plain.pdf", page_count=2))
    return window


def widget_point(window: "PenfoldWindow", page: int, x: float, y: float) -> tuple[float, float]:
    """Where a point of a page as shown is in the view."""
    view = window.document_view
    assert view.hadjustment is not None
    assert view.vadjustment is not None
    box = view._box(page)
    assert box is not None
    return box.x - view.hadjustment.get_value() + x * view.zoom, box.y - view.vadjustment.get_value() + y * view.zoom


def drag(window: "PenfoldWindow", page: int, start: tuple[float, float], end: tuple[float, float]) -> None:
    """Drag from a point of a page as shown to another, as the mouse does."""
    view = window.document_view
    start_x, start_y = widget_point(window, page, *start)
    end_x, end_y = widget_point(window, page, *end)
    gesture = FakeDrag(start_x, start_y)
    view._on_pressed(None, 1, start_x, start_y)  # type: ignore[arg-type]
    view._on_drag_update(gesture, (end_x - start_x) / 2, (end_y - start_y) / 2)  # type: ignore[arg-type]
    view._on_drag_end(gesture, end_x - start_x, end_y - start_y)  # type: ignore[arg-type]


def choose(window: "PenfoldWindow", tool: Tool) -> None:
    window.activate_action("win.annotation-tool", GLib.Variant.new_string(tool.value))


def made(window: "PenfoldWindow") -> list[Annotation]:
    assert window.document is not None
    return [annotation for annotation in window.document.annotations if annotation.managed]


def test_a_drag_draws_the_shape_from_where_it_starts_to_where_it_ends(shape_window: "PenfoldWindow") -> None:
    window = shape_window
    choose(window, Tool.RECTANGLE)
    drag(window, 1, (300, 200), (100, 150))  # Dragged up and left.
    (rectangle,) = made(window)
    assert (rectangle.kind, rectangle.page) == (Kind.RECTANGLE, 1)
    assert rectangle.rectangle == pytest.approx((100, 150, 300, 200), abs=0.5)
    assert window.annotating.tool is Tool.RECTANGLE  # It stays (D65).
    window.activate_action("win.undo", None)
    assert made(window) == []


def test_an_arrow_points_where_the_drag_ends(shape_window: "PenfoldWindow") -> None:
    window = shape_window
    choose(window, Tool.ARROW)
    drag(window, 0, (300, 400), (100, 300))
    (arrow,) = made(window)
    assert arrow.line == pytest.approx((300, 400, 100, 300), abs=0.5)
    choose(window, Tool.CIRCLE)
    drag(window, 0, (50, 50), (150, 100))
    assert [annotation.kind for annotation in made(window)] == [Kind.ARROW, Kind.CIRCLE]


def test_a_click_draws_nothing_and_a_shape_stays_on_its_page(shape_window: "PenfoldWindow") -> None:
    window = shape_window
    choose(window, Tool.RECTANGLE)
    drag(window, 0, (100, 100), (101, 101))
    assert made(window) == []
    drag(window, 0, (500, 800), (700, 900))  # Beyond the corner of the page.
    (rectangle,) = made(window)
    assert rectangle.rectangle == pytest.approx((500, 800, *A4), abs=0.5)


def test_on_a_turned_page_the_shape_is_kept_on_the_unturned_page(shape_window: "PenfoldWindow") -> None:
    window = shape_window
    assert window.document is not None
    window.document.execute(RotatePages(window.document, [0], 90))
    choose(window, Tool.RECTANGLE)
    drag(window, 0, (100, 50), (200, 150))  # As shown: the page is 842 points wide.
    (rectangle,) = made(window)
    assert rectangle.rectangle == pytest.approx((50, 842 - 200, 150, 842 - 100), abs=0.5)


def test_the_shape_is_shown_while_dragging(shape_window: "PenfoldWindow") -> None:
    window = shape_window
    view = window.document_view
    choose(window, Tool.CIRCLE)
    start_x, start_y = widget_point(window, 0, 100, 100)
    view._on_pressed(None, 1, start_x, start_y)  # type: ignore[arg-type]
    view._on_drag_update(FakeDrag(start_x, start_y), 80, 60)  # type: ignore[arg-type]
    assert view._preview is not None
    assert (view._preview.kind, made(window)) == (Kind.CIRCLE, [])  # Not made until the mouse is released.


def test_with_select_text_a_drag_selects_text(shape_window: "PenfoldWindow") -> None:
    window = shape_window
    choose(window, Tool.RECTANGLE)
    choose(window, Tool.SELECT)
    drag(window, 0, (100, 100), (300, 200))
    assert made(window) == []
