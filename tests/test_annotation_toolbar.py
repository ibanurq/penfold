"""The pencil and the floating annotation bar (02-interfaz, 5; D10, D32, D65)."""

from pathlib import Path
from typing import TYPE_CHECKING

from gi.repository import GLib, Gtk

from penfold.document.annotations import Kind
from penfold.ui.annotation_icons import KIND_ICONS, SELECT_TEXT_ICON
from penfold.ui.annotation_toolbar import ZOOM_BUTTONS_ROOM, Tool, bar_position
from penfold.ui.palette import ANNOTATION_COLORS
from tests.gtk_helpers import process_pending_events
from tests.sample_pdfs import make_pdf, make_pdf_with_permissions
from tests.test_document_window import action_enabled, open_and_wait, window

if TYPE_CHECKING:
    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]


def choose(window: "PenfoldWindow", tool: Tool) -> None:
    window.activate_action("win.annotation-tool", GLib.Variant.new_string(tool.value))


def test_the_pencil_shows_and_hides_the_bar(window: "PenfoldWindow", tmp_path: Path) -> None:
    assert not action_enabled(window, "annotate")  # No document yet.
    assert open_and_wait(window, make_pdf(tmp_path / "plain.pdf"))
    bar = window.annotation_toolbar
    assert (action_enabled(window, "annotate"), bar.get_visible()) == (True, False)
    window.activate_action("win.annotate", None)
    process_pending_events()
    assert bar.get_visible()
    assert window.toast_overlay.has_css_class("annotation-bar-shown")  # The toasts rise above the bar.
    assert bar.tool_buttons[Tool.SELECT].get_active()  # Select Text, by default.
    window.activate_action("win.annotate", None)
    assert not bar.get_visible()
    assert not window.toast_overlay.has_css_class("annotation-bar-shown")


def test_one_tool_is_chosen_and_stays_until_the_bar_is_hidden(window: "PenfoldWindow", tmp_path: Path) -> None:
    assert open_and_wait(window, make_pdf(tmp_path / "plain.pdf"))
    window.activate_action("win.annotate", None)
    choose(window, Tool.ARROW)
    process_pending_events()
    buttons = window.annotation_toolbar.tool_buttons
    assert [tool for tool, button in buttons.items() if button.get_active()] == [Tool.ARROW]
    assert (window.annotating.tool, window.document_view._drawing_cursor) == (Tool.ARROW, "crosshair")
    choose(window, Tool.HIGHLIGHT)
    # It selects text, with the text cursor.
    assert (window.annotating.tool, window.document_view._drawing_cursor) == (Tool.HIGHLIGHT, None)
    window.activate_action("win.annotate", None)  # Hiding the bar goes back to Select Text.
    assert window.annotating.tool == Tool.SELECT


def test_the_colour_starts_yellow_and_shows_on_its_button(window: "PenfoldWindow", tmp_path: Path) -> None:
    assert open_and_wait(window, make_pdf(tmp_path / "plain.pdf"))
    annotating, swatch = window.annotating, window.annotation_toolbar.swatch
    assert (annotating.color, swatch.has_css_class("palette-color-0")) == ((0xF9 / 255, 0xF0 / 255, 0x6B / 255), True)
    window.activate_action("win.annotation-color", GLib.Variant.new_string(ANNOTATION_COLORS[2]))
    assert (swatch.has_css_class("palette-color-2"), swatch.has_css_class("palette-color-0")) == (True, False)
    window.activate_action("win.annotation-color", GLib.Variant.new_string("#000000"))  # Not one of the six.
    assert swatch.has_css_class("palette-color-2")


def test_choosing_a_colour_closes_the_palette(window: "PenfoldWindow", tmp_path: Path) -> None:
    assert open_and_wait(window, make_pdf(tmp_path / "plain.pdf"))
    window.activate_action("win.annotate", None)
    bar = window.annotation_toolbar
    assert bar.has_css_class("osd")  # The zoom buttons' look, to stand out on a white page (D71).
    bar.color_button.popup()
    process_pending_events()
    popover = bar.color_button.get_popover()
    assert popover is not None
    circles = popover.get_child()
    assert circles is not None
    assert popover.get_visible()
    red = next(circle for circle in circles if circle.has_css_class("palette-color-4"))
    assert isinstance(red, Gtk.ToggleButton)
    red.emit("clicked")
    process_pending_events()
    assert (window.annotating.color, popover.get_visible()) == ((0xF6 / 255, 0x61 / 255, 0x51 / 255), False)


def test_a_pdf_that_does_not_allow_annotating_greys_out_the_pencil(window: "PenfoldWindow", tmp_path: Path) -> None:
    assert open_and_wait(window, make_pdf(tmp_path / "plain.pdf"))
    window.activate_action("win.annotate", None)
    assert open_and_wait(window, make_pdf_with_permissions(tmp_path / "locked.pdf", "modify_form"))
    assert (action_enabled(window, "annotate"), window.annotation_toolbar.get_visible()) == (False, False)
    assert open_and_wait(window, make_pdf_with_permissions(tmp_path / "notes.pdf", "modify_annotation"))
    assert action_enabled(window, "annotate")


def test_the_bar_is_centred_left_of_the_zoom_buttons() -> None:
    assert bar_position(1000, 400) == 300
    assert bar_position(520, 400) == 520 - ZOOM_BUTTONS_ROOM - 400  # Moved left to leave them free.
    assert bar_position(300, 400) == 0


def test_each_tool_has_the_icon_of_its_type_in_the_panel(window: "PenfoldWindow") -> None:
    for tool, button in window.annotation_toolbar.tool_buttons.items():
        expected = KIND_ICONS[tool.kind] if tool.kind else SELECT_TEXT_ICON
        assert button.get_icon_name() == expected
    assert set(KIND_ICONS) == set(Kind)
