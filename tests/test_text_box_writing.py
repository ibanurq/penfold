"""Writing text boxes on the page."""

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from gi.repository import Gdk, GLib

from penfold.document.annotations import Annotation, Kind
from penfold.document.commands.pages import RotatePages
from penfold.rendering.text_box import DEFAULT_WIDTH, text_height
from penfold.ui.annotation_toolbar import Tool
from tests.gtk_helpers import process_pending_events, wait_until
from tests.sample_pdfs import make_pdf
from tests.test_document_window import open_and_wait, window
from tests.test_shape_drawing import drag

if TYPE_CHECKING:
    from penfold.ui.text_box_editor import TextBoxEditor
    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]


@pytest.fixture
def box_window(window: "PenfoldWindow", tmp_path: Path) -> "PenfoldWindow":
    assert open_and_wait(window, make_pdf(tmp_path / "plain.pdf", page_count=2))
    window.activate_action("win.annotation-tool", GLib.Variant.new_string(Tool.TEXT_BOX.value))
    return window


def editor_after(window: "PenfoldWindow", start: tuple[float, float], end: tuple[float, float]) -> "TextBoxEditor":
    drag(window, 0, start, end)
    process_pending_events()
    editor = window.document_view.text_editor
    assert editor is not None
    return editor


def made(window: "PenfoldWindow") -> list[Annotation]:
    assert window.document is not None
    return [annotation for annotation in window.document.annotations if annotation.managed]


def test_a_drag_sets_the_width_and_the_text_is_written_on_the_page(box_window: "PenfoldWindow") -> None:
    window = box_window
    editor = editor_after(window, (300, 100), (100, 130))  # Dragged to the left: from 100 to 300.
    assert (*editor.corner, editor.width) == pytest.approx((100, 100, 200), abs=0.5)
    assert editor.text_view.get_parent() is window.document_view
    editor.text_view.get_buffer().set_text("Pending\\nsignature")
    editor.finish(apply=True)
    (box,) = made(window)
    assert (box.kind, box.text, box.text_turn) == (Kind.TEXT_BOX, "Pending\\nsignature", 0)
    left, top, right, bottom = box.rectangle
    assert (left, top, right - left) == pytest.approx((100, 100, 200), abs=0.5)
    assert bottom - top == pytest.approx(text_height("Pending\\nsignature", right - left))
    assert box.drawing.startswith(b"%PDF")
    assert window.document_view.text_editor is None
    window.activate_action("win.undo", None)
    assert made(window) == []


def test_a_click_gives_the_usual_width(box_window: "PenfoldWindow") -> None:
    editor = editor_after(box_window, (100, 100), (100, 100))
    assert editor.width == pytest.approx(DEFAULT_WIDTH)


def test_escape_cancels_and_a_blank_box_makes_nothing(box_window: "PenfoldWindow") -> None:
    window = box_window
    editor = editor_after(window, (100, 100), (300, 100))
    editor.text_view.get_buffer().set_text("Gone")
    assert editor._on_key_pressed(None, Gdk.KEY_Escape, 0, Gdk.ModifierType(0))  # type: ignore[arg-type]
    editor = editor_after(window, (100, 200), (300, 200))
    editor.text_view.get_buffer().set_text("   ")
    assert editor._on_key_pressed(None, Gdk.KEY_Return, 0, Gdk.ModifierType.CONTROL_MASK)  # type: ignore[arg-type]
    assert made(window) == []


def test_the_box_grows_down_as_the_text_grows(box_window: "PenfoldWindow") -> None:
    window = box_window
    editor = editor_after(window, (100, 100), (250, 100))
    process_pending_events()
    one_line = editor.text_view.get_height()
    editor.text_view.get_buffer().set_text("A text that is long enough to need three or four lines in this box")
    wait_until(lambda: editor.text_view.get_height() > 2 * one_line - 20)


def test_on_a_turned_page_it_is_written_upright(box_window: "PenfoldWindow") -> None:
    window = box_window
    assert window.document is not None
    window.document.execute(RotatePages(window.document, [0], 90))
    editor = editor_after(window, (100, 100), (300, 100))
    editor.text_view.get_buffer().set_text("Turned")
    editor.finish(apply=True)
    (box,) = made(window)
    left, top, right, bottom = box.rectangle
    assert box.text_turn == 90
    assert (bottom - top, right - left) == pytest.approx((200, text_height("Turned", 200)), abs=0.5)


def test_a_click_outside_applies_the_box_and_starts_no_other(box_window: "PenfoldWindow") -> None:
    window = box_window
    editor = editor_after(window, (100, 100), (300, 100))
    editor.text_view.get_buffer().set_text("Applied")
    drag(window, 0, (400, 500), (400, 500))  # A click elsewhere on the page.
    process_pending_events()
    assert [box.text for box in made(window)] == ["Applied"]
    assert window.document_view.text_editor is None


def test_moving_the_focus_away_applies_the_box(box_window: "PenfoldWindow") -> None:
    window = box_window
    editor = editor_after(window, (100, 100), (300, 100))
    process_pending_events()
    editor.text_view.get_buffer().set_text("Focus left")
    window.annotation_toolbar.color_button.grab_focus()  # As a click on the bar does.
    wait_until(lambda: window.document_view.text_editor is None)
    assert [box.text for box in made(window)] == ["Focus left"]
