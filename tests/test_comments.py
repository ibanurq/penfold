"""Placing comments with a click and writing their text in a popover (H2, H5, D68)."""

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from gi.repository import Gdk, GLib

from penfold.document.annotations import Annotation, Kind
from penfold.document.commands.pages import RotatePages
from penfold.ui.annotation_toolbar import Tool
from tests.gtk_helpers import process_pending_events
from tests.sample_pdfs import make_pdf
from tests.test_document_window import open_and_wait, window
from tests.test_shape_drawing import FakeDrag, widget_point

if TYPE_CHECKING:
    from penfold.ui.comment_popover import CommentPopover
    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]


@pytest.fixture
def comment_window(window: "PenfoldWindow", tmp_path: Path) -> "PenfoldWindow":
    assert open_and_wait(window, make_pdf(tmp_path / "plain.pdf", page_count=2))
    window.activate_action("win.annotation-tool", GLib.Variant.new_string(Tool.COMMENT.value))
    return window


def click(window: "PenfoldWindow", page: int, x: float, y: float) -> "CommentPopover":
    """Click on a point of a page as shown, and return the popover that opens."""
    view = window.document_view
    view_x, view_y = widget_point(window, page, x, y)
    view._on_pressed(None, 1, view_x, view_y)  # type: ignore[arg-type]
    view._on_drag_end(FakeDrag(view_x, view_y), 0, 0)  # type: ignore[arg-type]
    process_pending_events()
    popover = window.annotating.comment_popover
    assert popover is not None
    return popover


def made(window: "PenfoldWindow") -> list[Annotation]:
    assert window.document is not None
    return [annotation for annotation in window.document.annotations if annotation.managed]


def test_a_click_asks_for_the_text_and_apply_makes_the_comment(comment_window: "PenfoldWindow") -> None:
    window = comment_window
    popover = click(window, 0, 200, 300)
    assert popover.get_visible()
    assert window.document_view._preview is not None  # Where it goes is shown while writing.
    assert not popover.apply_button.get_sensitive()  # Nothing written yet.
    popover.text_view.get_buffer().set_text("  Check\\nthis  ")
    popover.apply_button.emit("clicked")
    process_pending_events()
    (comment,) = made(window)
    assert (comment.kind, comment.page, comment.text) == (Kind.COMMENT, 0, "Check\\nthis")
    assert comment.rectangle == pytest.approx((190, 290, 210, 310))  # Centred on the click.
    assert (popover.get_visible(), window.annotating.tool) == (False, Tool.COMMENT)  # The tool stays (D65).
    assert window.document_view._preview is None


def test_ctrl_enter_applies_and_cancelling_makes_nothing(comment_window: "PenfoldWindow") -> None:
    window = comment_window
    popover = click(window, 0, 100, 100)
    popover.popdown()  # As Esc or a click outside do.
    process_pending_events()
    assert (made(window), window.document_view._preview) == ([], None)
    popover = click(window, 0, 100, 100)
    popover.text_view.get_buffer().set_text("Note")
    assert popover._on_key_pressed(None, Gdk.KEY_Return, 0, Gdk.ModifierType.CONTROL_MASK)  # type: ignore[arg-type]
    assert not popover._on_key_pressed(None, Gdk.KEY_Return, 0, Gdk.ModifierType(0))  # type: ignore[arg-type]
    assert [comment.text for comment in made(window)] == ["Note"]


def test_the_text_of_a_comment_shows_when_the_pointer_is_over_it(comment_window: "PenfoldWindow") -> None:
    window = comment_window
    popover = click(window, 0, 200, 300)
    popover.text_view.get_buffer().set_text("Hello")
    popover.apply()
    view = window.document_view
    assert view.comment_at(*widget_point(window, 0, 205, 305)) == made(window)[0]
    assert view.comment_at(*widget_point(window, 0, 250, 305)) is None


def test_on_a_turned_page_the_comment_is_shown_centred_on_the_click(comment_window: "PenfoldWindow") -> None:
    window = comment_window
    assert window.document is not None
    window.document.execute(RotatePages(window.document, [0], 90))
    popover = click(window, 0, 300, 100)
    popover.text_view.get_buffer().set_text("Turned")
    popover.apply()
    view = window.document_view
    (comment,) = made(window)
    assert view.comment_at(*widget_point(window, 0, 291, 91)) == comment
    assert view.comment_at(*widget_point(window, 0, 309, 109)) == comment
    assert view.comment_at(*widget_point(window, 0, 315, 100)) is None


def test_a_long_comment_is_cut_in_its_tooltip() -> None:
    from penfold.ui.document_view import TOOLTIP_CHARACTERS, TOOLTIP_LINES, tooltip_text

    assert tooltip_text("Check this\r\nand that\n") == "Check this\nand that"
    many_lines = "\n".join(f"Line {number}" for number in range(1, 15))
    assert tooltip_text(many_lines) == "\n".join(f"Line {number}" for number in range(1, TOOLTIP_LINES + 1)) + "…"
    one_long_line = "word " * 200
    assert tooltip_text(one_long_line) == one_long_line[:TOOLTIP_CHARACTERS].rstrip() + "…"
