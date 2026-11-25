"""Highlighting, underlining and striking through the text selected."""

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from gi.repository import Gdk, Gio, GLib

from penfold import config
from penfold.document.annotations import Kind
from penfold.ui.annotation_toolbar import Tool
from penfold.ui.text_selection import PagePoint, TextSelection
from tests.gtk_helpers import process_pending_events
from tests.sample_pdfs import make_pdf_with_permissions
from tests.test_document_window import open_and_wait, window
from tests.test_page_content import make_text_pdf

if TYPE_CHECKING:
    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]


@pytest.fixture
def text_window(window: "PenfoldWindow", tmp_path: Path) -> "PenfoldWindow":
    assert open_and_wait(window, make_text_pdf(tmp_path / "text.pdf"))
    return window


@pytest.fixture
def author() -> Iterator[Gio.Settings]:
    """Penfold's settings, with the author's name cleared afterwards."""
    settings = Gio.Settings(schema_id=config.APP_ID)
    yield settings
    settings.reset("author-name")


def select(window: "PenfoldWindow", start: PagePoint, end: PagePoint) -> None:
    """Select text as a drag does, and release the mouse."""
    view = window.document_view
    view._set_selection(TextSelection(start, end))
    view.emit("text-selected")


def choose(window: "PenfoldWindow", tool: Tool) -> None:
    window.activate_action("win.annotation-tool", GLib.Variant.new_string(tool.value))


def made(window: "PenfoldWindow") -> list[tuple[Kind, int, int]]:
    """The annotations made, as (type, page, number of lines)."""
    document = window.document
    assert document is not None
    return [(item.kind, item.page, len(item.quads)) for item in document.annotations if item.managed]


def test_releasing_the_mouse_marks_the_text_line_by_line(text_window: "PenfoldWindow") -> None:
    window = text_window
    choose(window, Tool.HIGHLIGHT)
    select(window, PagePoint(0, 95, 70), PagePoint(0, 117, 200))  # Both lines of the first page.
    assert made(window) == [(Kind.HIGHLIGHT, 0, 2)]
    assert window.document_view.selection is None
    assert window.annotating.tool is Tool.HIGHLIGHT  # It stays.
    (highlight,) = window.document.annotations if window.document else []
    first, second = highlight.quads
    assert first[1] < second[1]  # From the top.
    assert first[0] == pytest.approx(72, abs=1)
    assert (highlight.color, highlight.author) == ((0xF9 / 255, 0xF0 / 255, 0x6B / 255), "Penfold")
    window.activate_action("win.undo", None)
    assert made(window) == []


def test_a_mark_over_several_pages_is_one_edit(text_window: "PenfoldWindow") -> None:
    window = text_window
    choose(window, Tool.STRIKE_OUT)
    select(window, PagePoint(0, 115, 70), PagePoint(1, 98, 200))
    assert made(window) == [(Kind.STRIKE_OUT, 0, 1), (Kind.STRIKE_OUT, 1, 1)]
    window.activate_action("win.undo", None)
    assert made(window) == []


def test_selecting_with_select_text_marks_nothing(text_window: "PenfoldWindow") -> None:
    select(text_window, PagePoint(0, 95, 70), PagePoint(0, 117, 200))
    assert made(text_window) == []
    assert text_window.document_view.selection is not None


def test_h_and_u_mark_the_selected_text_or_choose_their_tool(
    text_window: "PenfoldWindow", author: Gio.Settings
) -> None:
    window = text_window
    author.set_string("author-name", "Ana")
    select(window, PagePoint(0, 95, 70), PagePoint(0, 105, 200))
    assert window._on_marking_key(Tool.HIGHLIGHT)
    assert made(window) == [(Kind.HIGHLIGHT, 0, 1)]
    assert window.annotating.tool is Tool.SELECT  # Without changing the tool.
    assert window.document is not None
    assert [item.author for item in window.document.annotations] == ["Ana"]
    assert window._on_marking_key(Tool.UNDERLINE)  # No text selected now.
    assert (window.annotating.tool, window.annotation_toolbar.get_visible()) == (Tool.UNDERLINE, True)


def test_escape_goes_back_to_select_text(text_window: "PenfoldWindow") -> None:
    window = text_window
    choose(window, Tool.RECTANGLE)
    window.activate_action("win.annotate", None)
    process_pending_events()
    assert window._on_key_pressed(None, Gdk.KEY_Escape, 0, Gdk.ModifierType(0))  # type: ignore[arg-type]
    assert window.annotating.tool is Tool.SELECT
    assert not window._on_key_pressed(None, Gdk.KEY_Escape, 0, Gdk.ModifierType(0))  # type: ignore[arg-type]


def test_text_that_may_not_be_copied_can_still_be_marked(window: "PenfoldWindow", tmp_path: Path) -> None:
    assert open_and_wait(window, make_pdf_with_permissions(tmp_path / "locked.pdf", "modify_annotation"))
    view = window.document_view
    selection = TextSelection(PagePoint(0, 10, 10), PagePoint(0, 20, 20))
    view._set_selection(selection)
    to_copy = view.selection  # Selecting to copy is not allowed…
    choose(window, Tool.UNDERLINE)
    view._set_selection(selection)
    assert (to_copy, view.selection) == (None, selection)  # …but selecting to mark is.
    assert not view.copy_selection()
