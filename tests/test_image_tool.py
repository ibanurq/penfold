"""The Image tool: choosing the file, the frame that follows the pointer, a click or a drag, and the tool before."""

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from gi.repository import Gio, GLib, Gtk
from PIL import Image

from penfold.document.annotations import Annotation, Kind
from penfold.document.reshaping import SMALLEST_SIZE, dragged, placed
from penfold.ui.annotation_toolbar import TOOL_GROUPS, Tool
from tests.gtk_helpers import process_pending_events
from tests.sample_pdfs import make_pdf
from tests.test_document_window import open_and_wait, window
from tests.test_shape_drawing import FakeDrag, widget_point

if TYPE_CHECKING:
    from collections.abc import Callable

    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]
A4 = (595.0, 842.0)


class FakeFileDialog:
    """A file chooser that answers as the test says: with a file, or cancelled."""

    opened: "FakeFileDialog | None" = None

    def __init__(self) -> None:
        self.callback: Callable[[FakeFileDialog, object], None] | None = None
        self.answer: Gio.File | None = None
        FakeFileDialog.opened = self

    def open(self, _window: object, _cancellable: object, callback: "Callable[[FakeFileDialog, object], None]") -> None:
        self.callback = callback

    def open_finish(self, _result: object) -> Gio.File:
        if self.answer is None:
            raise GLib.Error("Dismissed by user")
        return self.answer

    def choose(self, path: Path | None) -> None:
        """Answer with a file (None: cancelled)."""
        self.answer = None if path is None else Gio.File.new_for_path(str(path))
        assert self.callback is not None
        self.callback(self, None)
        process_pending_events()


@pytest.fixture
def image_window(window: "PenfoldWindow", tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> "PenfoldWindow":
    """A two-page document, with the file chooser of the image tool answering as each test says."""
    monkeypatch.setattr("penfold.ui.annotating.image_file_dialog", FakeFileDialog)
    assert open_and_wait(window, make_pdf(tmp_path / "plain.pdf", page_count=2))
    return window


def picture(tmp_path: Path, size: tuple[int, int] = (120, 80), name: str = "image.png") -> Path:
    """A picture of a size in pixels, at 72 dots per inch: as many points as pixels (PNG keeps it per metre: almost)."""
    path = tmp_path / name
    Image.new("RGB", size, (40, 90, 220)).save(path, dpi=(72, 72))
    return path


def choose(window: "PenfoldWindow", tool: Tool) -> None:
    window.activate_action("win.annotation-tool", GLib.Variant.new_string(tool.value))
    process_pending_events()


def start(window: "PenfoldWindow", path: Path | None, before: Tool = Tool.HIGHLIGHT) -> FakeFileDialog:
    """Choose a tool, then the image tool, and answer its file chooser with a file (None: cancelled)."""
    choose(window, before)
    choose(window, Tool.IMAGE)
    dialog = FakeFileDialog.opened
    assert dialog is not None
    dialog.choose(path)
    return dialog


def tool_of(window: "PenfoldWindow") -> Tool:
    return window.annotating.tool


def images(window: "PenfoldWindow") -> list[Annotation]:
    assert window.document is not None
    return [item for item in window.document.annotations if item.kind is Kind.IMAGE]


def click(window: "PenfoldWindow", page: int, at: tuple[float, float], to: tuple[float, float] | None = None) -> None:
    """Press at a point of a page as shown and release there (a click) or at another point (a drag)."""
    view = window.document_view
    x, y = widget_point(window, page, *at)
    end_x, end_y = widget_point(window, page, *(to or at))
    gesture = FakeDrag(x, y)
    view._on_motion(None, x, y)  # type: ignore[arg-type]
    view._on_pressed(None, 1, x, y)  # type: ignore[arg-type]
    view._on_drag_update(gesture, (end_x - x) / 2, (end_y - y) / 2)  # type: ignore[arg-type]
    view._on_drag_end(gesture, end_x - x, end_y - y)  # type: ignore[arg-type]
    process_pending_events()


def test_the_image_tool_has_a_group_of_its_own_before_the_colour(image_window: "PenfoldWindow") -> None:
    assert TOOL_GROUPS[-1] == (Tool.IMAGE,)
    bar = image_window.annotation_toolbar
    button = bar.tool_buttons[Tool.IMAGE]
    before, after = button.get_prev_sibling(), button.get_next_sibling()
    assert isinstance(before, Gtk.Separator)
    assert before.get_prev_sibling() is bar.tool_buttons[Tool.TEXT_BOX]
    assert isinstance(after, Gtk.Separator)
    assert after.get_next_sibling() is bar.color_button
    assert (button.get_icon_name(), button.get_tooltip_text()) == ("image-x-generic-symbolic", "Image")


def test_a_frame_of_its_size_follows_the_pointer_and_a_click_puts_it_there(
    image_window: "PenfoldWindow", tmp_path: Path
) -> None:
    window = image_window
    start(window, picture(tmp_path))
    view = window.document_view
    placer = view.image_placer
    assert placer is not None
    assert tool_of(window) is Tool.IMAGE  # Its button stays pressed meanwhile.
    view._on_motion(None, *widget_point(window, 1, 200, 300))  # type: ignore[arg-type]
    assert placer.frame is not None
    position, frame = placer.frame
    assert position == 1
    assert frame == pytest.approx((200, 300, 320, 380), abs=0.1)  # Its top left corner at the pointer.
    click(window, 1, (200, 300))
    (image,) = images(window)
    assert (image.page, image.managed, image.color) == (1, True, None)
    assert image.rectangle == pytest.approx((200, 300, 320, 380), abs=0.1)
    assert tool_of(window) is Tool.HIGHLIGHT  # The tool before comes back.
    assert view.image_placer is None
    window.activate_action("win.undo", None)
    assert images(window) == []


def test_a_drag_frames_it_keeping_its_proportion(image_window: "PenfoldWindow", tmp_path: Path) -> None:
    window = image_window
    start(window, picture(tmp_path), before=Tool.SELECT)
    click(window, 0, (100, 100), (340, 120))  # Taken furthest across: twice as wide.
    (image,) = images(window)
    assert image.rectangle == pytest.approx((100, 100, 340, 260), abs=0.1)
    assert window.annotating.tool is Tool.SELECT


def test_at_the_edge_it_moves_in_and_bigger_than_the_page_it_shrinks(
    image_window: "PenfoldWindow", tmp_path: Path
) -> None:
    window = image_window
    start(window, picture(tmp_path))
    click(window, 0, (550, 800))
    start(window, picture(tmp_path, (1190, 842), "big.png"))
    click(window, 0, (300, 300))
    near_the_edge, big = images(window)
    assert near_the_edge.rectangle == pytest.approx((475, 762, 595, 842), abs=0.1)
    assert big.rectangle == pytest.approx((0, 300, 595, 721), abs=0.1)  # Half as big, moved in from the right.


def test_cancelling_the_file_chooser_brings_back_the_tool_before(image_window: "PenfoldWindow") -> None:
    window = image_window
    start(window, None, before=Tool.RECTANGLE)
    assert (window.annotating.tool, window.document_view.image_placer, images(window)) == (Tool.RECTANGLE, None, [])


def test_a_file_that_is_not_an_image_says_so(image_window: "PenfoldWindow", tmp_path: Path) -> None:
    window = image_window
    path = tmp_path / "notes.png"
    path.write_text("not an image")
    toasts: list[str] = []
    window.annotating._notify = toasts.append
    start(window, path)
    assert toasts == ["The image could not be opened"]
    assert (window.annotating.tool, images(window)) == (Tool.HIGHLIGHT, [])


def test_esc_or_another_tool_stops_putting_it(image_window: "PenfoldWindow", tmp_path: Path) -> None:
    from gi.repository import Gdk

    window = image_window
    start(window, picture(tmp_path), before=Tool.FREEHAND)
    window._on_key_pressed(None, Gdk.KEY_Escape, 0, Gdk.ModifierType(0))  # type: ignore[arg-type]
    assert (window.annotating.tool, window.document_view.image_placer) == (Tool.FREEHAND, None)
    start(window, picture(tmp_path))
    choose(window, Tool.ARROW)
    assert window.document_view.image_placer is None
    click(window, 0, (100, 100), (200, 200))  # An arrow, not an image.
    assert images(window) == []


def test_on_a_page_turned_in_penfold_it_is_put_as_seen(image_window: "PenfoldWindow", tmp_path: Path) -> None:
    from penfold.document.commands.pages import RotatePages

    window = image_window
    document = window.document
    assert document is not None
    document.execute(RotatePages(document, [0], 90))
    process_pending_events()
    start(window, picture(tmp_path))
    click(window, 0, (100, 100))
    (image,) = images(window)
    page = window.document_view.shown_page(0)
    assert page is not None
    assert page.from_source(image.rectangle) == pytest.approx((100, 100, 220, 180), abs=0.1)  # 120 wide as seen.


def test_where_a_click_and_a_drag_put_it() -> None:
    assert placed((10, 20), (100, 50), A4) == (10, 20, 110, 70)
    assert placed((-5, 820), (100, 50), A4) == (0, 792, 100, 842)
    assert dragged((10, 20), (11, 21), (100, 50), A4) is None  # A click.
    assert dragged((10, 20), (60, 30), (100, 50), A4) == pytest.approx((10, 20, 60, 45))
    assert dragged((10, 20), (0, 0), (100, 50), A4) == pytest.approx(
        (10, 20, 10 + 2 * SMALLEST_SIZE, 20 + SMALLEST_SIZE)
    )
    assert dragged((500, 20), (2000, 30), (100, 50), A4) == pytest.approx((500, 20, 595, 67.5))  # As far as fits.
