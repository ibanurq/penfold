"""Moving annotations and changing their size with handles on the page (D72, D73)."""

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from gi.repository import Gdk

from penfold.document.annotations import Annotation, Kind, new_annotation
from penfold.document.commands.annotations import AddAnnotations
from penfold.document.commands.pages import RotatePages
from penfold.document.reshaping import Handle
from penfold.rendering.text_box import text_box_pdf, text_height, written_frame
from penfold.ui.annotation_toolbar import Tool
from tests.gtk_helpers import process_pending_events, wait_until
from tests.test_annotation_menu import annotated_window, make_annotated_pdf
from tests.test_document_window import open_and_wait, window
from tests.test_shape_drawing import drag, widget_point

if TYPE_CHECKING:
    from penfold.ui.handle_editor import HandleEditor
    from penfold.ui.window import PenfoldWindow

__all__ = ["annotated_window", "window"]
RED = (0.965, 0.38, 0.318)
SQUARE = (100.0, 100.0, 300.0, 200.0)


@pytest.fixture
def square_window(window: "PenfoldWindow", tmp_path: Path) -> "PenfoldWindow":
    """A document with a rectangle made in Penfold on its first page."""
    from tests.sample_pdfs import make_pdf

    assert open_and_wait(window, make_pdf(tmp_path / "plain.pdf", page_count=2))
    document = window.document
    assert document is not None
    document.execute(AddAnnotations(document, [new_annotation(Kind.RECTANGLE, 0, SQUARE, RED, "Iban")]))
    process_pending_events()
    return window


def the_square(window: "PenfoldWindow") -> Annotation:
    assert window.document is not None
    return next(item for item in window.document.annotations if item.kind is Kind.RECTANGLE)


def start_editing(window: "PenfoldWindow", at: tuple[float, float]) -> "HandleEditor":
    """Right-click a point of the first page as shown, and choose Move and Resize."""
    view = window.document_view
    view._ask_for_menu(*widget_point(window, 0, *at))
    process_pending_events()
    window.activate_action("win.reshape-annotation", None)
    process_pending_events()
    editor = view.handle_editor
    assert editor is not None
    return editor


def press_key(window: "PenfoldWindow", keyval: int) -> None:
    window.document_view._on_key_pressed(None, keyval, 0, Gdk.ModifierType(0))  # type: ignore[arg-type]
    process_pending_events()


def test_a_corner_changes_the_size_and_enter_accepts_it_as_one_edit(square_window: "PenfoldWindow") -> None:
    window = square_window
    original = the_square(window)
    editor = start_editing(window, (100, 150))
    assert window.document_view._hidden is original  # Shown as it changes instead.
    drag(window, 0, (300, 200), (350, 260))
    assert editor.annotation.rectangle == pytest.approx((100, 100, 350, 260))
    assert the_square(window) is original  # Not changed until accepted.
    press_key(window, Gdk.KEY_Return)
    view = window.document_view
    assert (view.handle_editor, view._hidden) == (None, None)
    assert the_square(window).rectangle == pytest.approx((100, 100, 350, 260))
    window.activate_action("win.undo", None)
    assert the_square(window) is original


def test_dragging_it_from_inside_moves_it_and_a_click_outside_accepts(square_window: "PenfoldWindow") -> None:
    window = square_window
    start_editing(window, (100, 150))
    drag(window, 0, (200, 150), (230, 190))
    view = window.document_view
    view._on_pressed(None, 1, *widget_point(window, 0, 500, 600))  # type: ignore[arg-type]
    process_pending_events()
    assert view.handle_editor is None
    assert the_square(window).rectangle == pytest.approx((130, 140, 330, 240))


def test_esc_cancels_the_change(square_window: "PenfoldWindow") -> None:
    window = square_window
    original = the_square(window)
    assert window.document is not None
    last_edit = window.document.last_edit
    start_editing(window, (100, 150))
    drag(window, 0, (100, 100), (20, 40))
    press_key(window, Gdk.KEY_Escape)
    assert window.document_view.handle_editor is None
    assert the_square(window) is original
    assert window.document.last_edit is last_edit  # Nothing to undo.


def test_undoing_meanwhile_cancels_the_handles(square_window: "PenfoldWindow") -> None:
    window = square_window
    start_editing(window, (100, 150))
    window.activate_action("win.undo", None)  # Takes the rectangle away.
    process_pending_events()
    assert window.document_view.handle_editor is None


def test_the_handles_follow_a_turned_page(square_window: "PenfoldWindow") -> None:
    window = square_window
    document = window.document
    assert document is not None
    document.execute(RotatePages(document, [0], 90))
    process_pending_events()
    # Turned clockwise, the rectangle's top left corner (100, 100) shows at the top right, at (842 - 100, 100).
    editor = start_editing(window, (842 - 150, 100))
    assert editor.handle_at(*widget_point(window, 0, 742, 100)) is Handle.TOP_LEFT
    drag(window, 0, (742, 100), (702, 60))  # Left and up as shown: left and down on the unturned page.
    press_key(window, Gdk.KEY_Return)
    assert the_square(window).rectangle == pytest.approx((60, 140, 300, 200))


def test_the_cursor_says_what_a_drag_does(square_window: "PenfoldWindow") -> None:
    window = square_window
    editor = start_editing(window, (100, 150))
    assert editor.cursor_at(*widget_point(window, 0, 300, 200)) == "nwse-resize"
    assert editor.cursor_at(*widget_point(window, 0, 300, 100)) == "nesw-resize"
    assert editor.cursor_at(*widget_point(window, 0, 200, 150)) == "move"
    assert editor.cursor_at(*widget_point(window, 0, 500, 500)) is None


def plain_square_window(window: "PenfoldWindow", tmp_path: Path) -> "PenfoldWindow":
    """The annotations of another program, with a plain square, which Penfold can draw again as it is."""
    import pikepdf

    path = make_annotated_pdf(tmp_path / "annotated.pdf")
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        del pdf.pages[0].obj.Annots[1]["/BE"]
        pdf.save(path)
    assert open_and_wait(window, path)
    return window


def test_one_of_another_program_moves_keeping_its_own_drawing(window: "PenfoldWindow", tmp_path: Path) -> None:
    window = plain_square_window(window, tmp_path)
    original = the_square(window)
    left, top, right, bottom = original.rectangle
    start_editing(window, (left, top + 50))
    drag(window, 0, (left + 50, top + 50), (left + 60, top + 70))
    press_key(window, Gdk.KEY_Return)
    moved = the_square(window)
    assert (moved.managed, moved.moved_as_is, moved.origin) == (False, True, original.origin)
    assert moved.moved_by == pytest.approx((10, 20))
    assert moved.rectangle == pytest.approx((left + 10, top + 20, right + 10, bottom + 20))
    assert window.document is not None
    assert original in window.document.replaced_annotations  # Poppler leaves it out: Penfold paints it moved.
    assert window.document_view._managed[0].count(moved) == 1
    window.activate_action("win.undo", None)
    assert the_square(window) is original


def test_a_handle_makes_one_of_another_program_penfolds(window: "PenfoldWindow", tmp_path: Path) -> None:
    window = plain_square_window(window, tmp_path)
    original = the_square(window)
    left, top, right, bottom = original.rectangle
    start_editing(window, (left, top + 50))
    drag(window, 0, (right, bottom), (right + 30, bottom + 10))
    press_key(window, Gdk.KEY_Return)
    changed = the_square(window)
    assert (changed.managed, changed.origin, changed.moved_by) == (True, original.origin, (0.0, 0.0))
    assert changed.rectangle == pytest.approx((left, top, right + 30, bottom + 10))


def test_one_penfold_cannot_draw_again_only_moves_without_a_warning(annotated_window: "PenfoldWindow") -> None:
    window = annotated_window
    original = the_square(window)  # With a cloudy border.
    left, top, _right, _bottom = original.rectangle
    editor = start_editing(window, (left, top + 50))
    assert editor.handle_at(*widget_point(window, 0, left, top)) is None  # No handles.
    drag(window, 0, (left + 50, top + 50), (left + 40, top + 45))
    press_key(window, Gdk.KEY_Return)
    moved = the_square(window)
    assert (moved.moved_as_is, moved.foreign_look) == (True, original.foreign_look)
    assert moved.moved_by == pytest.approx((-10, -5))


def test_the_menu_says_move_and_resize_or_move(annotated_window: "PenfoldWindow") -> None:
    from penfold.document.reshaping import can_move
    from penfold.ui.annotation_editing import _can_resize

    window = annotated_window
    assert window.document is not None
    moved = {item.kind: can_move(item) for item in window.document.annotations}
    resized = {item.kind: _can_resize(item) for item in window.document.annotations}
    assert moved == {
        Kind.HIGHLIGHT: False,  # Marks follow the text instead.
        Kind.RECTANGLE: True,
        Kind.OTHER: False,
        Kind.COMMENT: True,
        Kind.TEXT_BOX: True,
        Kind.ARROW: True,
    }
    assert resized == {
        Kind.HIGHLIGHT: True,  # The text it covers.
        Kind.RECTANGLE: False,  # A cloudy border: Penfold would lose it (D73).
        Kind.OTHER: False,
        Kind.COMMENT: False,  # Its size is fixed.
        Kind.TEXT_BOX: True,  # Plain, as Penfold draws them.
        Kind.ARROW: True,
    }


TEXT = "A text long enough to need a few lines in a box of this width, and then some more words."
A4 = (595.0, 842.0)


@pytest.fixture
def text_box_window(window: "PenfoldWindow", tmp_path: Path) -> "PenfoldWindow":
    """A document with a text box made in Penfold on its first page, 200 points wide from (100, 100)."""
    from tests.sample_pdfs import make_pdf

    assert open_and_wait(window, make_pdf(tmp_path / "plain.pdf", page_count=1))
    document = window.document
    assert document is not None
    height = text_height(TEXT, 200)
    box = new_annotation(
        Kind.TEXT_BOX,
        0,
        (100, 100, 300, 100 + height),
        RED,
        "Iban",
        text=TEXT,
        drawing=text_box_pdf(TEXT, (200, height), RED),
    )
    document.execute(AddAnnotations(document, [box]))
    process_pending_events()
    return window


def the_box(window: "PenfoldWindow") -> Annotation:
    assert window.document is not None
    return next(item for item in window.document.annotations if item.kind is Kind.TEXT_BOX)


def test_a_text_box_has_a_handle_at_each_side(text_box_window: "PenfoldWindow") -> None:
    window = text_box_window
    box = the_box(window)
    middle = (box.rectangle[1] + box.rectangle[3]) / 2
    editor = start_editing(window, (200, box.rectangle[1] + 5))
    assert editor.handle_at(*widget_point(window, 0, 100, middle)) is Handle.LEFT
    assert editor.handle_at(*widget_point(window, 0, 300, middle)) is Handle.RIGHT
    assert editor.handle_at(*widget_point(window, 0, 300, box.rectangle[1])) is None  # No corners.
    assert editor.cursor_at(*widget_point(window, 0, 300, middle)) == "ew-resize"


def test_narrower_it_grows_taller_as_it_is_dragged_and_is_drawn_again(text_box_window: "PenfoldWindow") -> None:
    window = text_box_window
    box = the_box(window)
    middle = (box.rectangle[1] + box.rectangle[3]) / 2
    editor = start_editing(window, (200, box.rectangle[1] + 5))
    drag(window, 0, (300, middle), (220, middle + 40))
    shown = editor.annotation  # As the drag ends, before it is accepted: the text laid out again.
    (left, top), width = written_frame(shown, A4)
    assert (left, top, width) == pytest.approx((100, 100, 120))  # The left side stays.
    assert shown.rectangle[3] - shown.rectangle[1] == pytest.approx(text_height(TEXT, 120))
    press_key(window, Gdk.KEY_Return)
    changed = the_box(window)
    assert changed.rectangle == pytest.approx(shown.rectangle)
    assert changed.drawing != box.drawing  # Its saved drawing, made again for the new width.
    window.activate_action("win.undo", None)
    assert the_box(window) is box


def test_a_text_box_moves_as_a_whole(text_box_window: "PenfoldWindow") -> None:
    window = text_box_window
    box = the_box(window)
    start_editing(window, (200, box.rectangle[1] + 5))
    drag(window, 0, (200, box.rectangle[1] + 5), (250, box.rectangle[1] + 35))
    press_key(window, Gdk.KEY_Return)
    left, top, right, bottom = box.rectangle
    assert the_box(window).rectangle == pytest.approx((left + 50, top + 30, right + 50, bottom + 30))


LINE = (100.0, 300.0, 400.0, 500.0)


@pytest.fixture
def arrow_window(window: "PenfoldWindow", tmp_path: Path) -> "PenfoldWindow":
    """A document with an arrow made in Penfold on its first page, from (100, 300) to (400, 500)."""
    from tests.sample_pdfs import make_pdf

    assert open_and_wait(window, make_pdf(tmp_path / "plain.pdf", page_count=1))
    document = window.document
    assert document is not None
    arrow = new_annotation(Kind.ARROW, 0, (100, 300, 400, 500), RED, "Iban", line=LINE)
    document.execute(AddAnnotations(document, [arrow]))
    process_pending_events()
    return window


def the_arrow(window: "PenfoldWindow") -> Annotation:
    assert window.document is not None
    return next(item for item in window.document.annotations if item.kind is Kind.ARROW)


def test_an_arrow_has_a_handle_at_each_end(arrow_window: "PenfoldWindow") -> None:
    window = arrow_window
    editor = start_editing(window, (250, 400))
    assert editor.handle_at(*widget_point(window, 0, 100, 300)) is Handle.START
    assert editor.handle_at(*widget_point(window, 0, 400, 500)) is Handle.END
    assert editor.handle_at(*widget_point(window, 0, 400, 300)) is None  # No corners.
    assert editor.cursor_at(*widget_point(window, 0, 400, 500)) == "crosshair"
    assert editor.cursor_at(*widget_point(window, 0, 250, 400)) == "move"
    assert editor.cursor_at(*widget_point(window, 0, 350, 320)) is None  # Off its line, though within its frame.


def test_an_end_goes_where_it_is_dragged_and_the_other_stays(arrow_window: "PenfoldWindow") -> None:
    window = arrow_window
    original = the_arrow(window)
    start_editing(window, (250, 400))
    drag(window, 0, (400, 500), (450, 250))
    press_key(window, Gdk.KEY_Return)
    changed = the_arrow(window)
    assert changed.line == pytest.approx((100, 300, 450, 250))
    assert changed.rectangle == pytest.approx((100, 250, 450, 300))
    window.activate_action("win.undo", None)
    assert the_arrow(window) is original


def test_dragging_its_line_moves_it_and_a_press_off_its_line_accepts(arrow_window: "PenfoldWindow") -> None:
    window = arrow_window
    start_editing(window, (250, 400))
    drag(window, 0, (250, 400), (270, 380))
    view = window.document_view
    view._on_pressed(None, 1, *widget_point(window, 0, 350, 320))  # type: ignore[arg-type]
    process_pending_events()
    assert view.handle_editor is None
    assert the_arrow(window).line == pytest.approx((120, 280, 420, 480))


COMMENT_SQUARE = (200.0, 200.0, 220.0, 220.0)


@pytest.fixture
def comment_window(window: "PenfoldWindow", tmp_path: Path) -> "PenfoldWindow":
    """A document with a comment made in Penfold on its first page."""
    from tests.sample_pdfs import make_pdf

    assert open_and_wait(window, make_pdf(tmp_path / "plain.pdf", page_count=1))
    document = window.document
    assert document is not None
    comment = new_annotation(Kind.COMMENT, 0, COMMENT_SQUARE, RED, "Iban", text="A note")
    document.execute(AddAnnotations(document, [comment]))
    process_pending_events()
    return window


def the_comment(window: "PenfoldWindow") -> Annotation:
    assert window.document is not None
    return next(item for item in window.document.annotations if item.kind is Kind.COMMENT)


def test_a_comment_has_no_handles_and_moves_keeping_its_size(comment_window: "PenfoldWindow") -> None:
    window = comment_window
    original = the_comment(window)
    editor = start_editing(window, (210, 210))
    assert editor.handle_at(*widget_point(window, 0, 200, 200)) is None
    assert editor.cursor_at(*widget_point(window, 0, 210, 210)) == "move"
    drag(window, 0, (210, 210), (300, 260))
    press_key(window, Gdk.KEY_Return)
    assert the_comment(window).rectangle == pytest.approx((290, 250, 310, 270))
    assert the_comment(window).text == "A note"
    window.activate_action("win.undo", None)
    assert the_comment(window) is original


def test_a_comment_on_a_turned_page_moves_as_the_pointer(comment_window: "PenfoldWindow") -> None:
    window = comment_window
    document = window.document
    assert document is not None
    document.execute(RotatePages(document, [0], 90))
    process_pending_events()
    # Upright on the turned page, it keeps the corner that is its top left unturned: (200, 200) shows at (642, 200).
    start_editing(window, (652, 210))
    drag(window, 0, (652, 210), (612, 250))  # 40 left and 40 down as shown: 40 down and 40 right unturned.
    press_key(window, Gdk.KEY_Return)
    assert the_comment(window).rectangle == pytest.approx((240, 240, 260, 260))


def test_a_handle_taken_back_where_it_was_changes_nothing(window: "PenfoldWindow", tmp_path: Path) -> None:
    window = plain_square_window(window, tmp_path)
    original = the_square(window)
    _left, top, right, bottom = original.rectangle
    start_editing(window, (original.rectangle[0], top + 50))
    drag(window, 0, (right, bottom), (right, bottom))
    press_key(window, Gdk.KEY_Return)
    assert the_square(window) is original


def test_saving_accepts_a_move_not_accepted_yet(square_window: "PenfoldWindow") -> None:
    """Saving with the handles still shown saves what shows (it happened with the Save button)."""
    import pikepdf

    window = square_window
    document = window.document
    assert document is not None
    start_editing(window, (100, 150))
    drag(window, 0, (200, 150), (230, 190))
    window.activate_action("win.save", None)
    assert window.document_view.handle_editor is None
    wait_until(lambda: not document.is_modified)
    with pikepdf.open(document.path) as pdf:
        square = pdf.pages[0].obj.Annots[0]
        assert float(square.Rect[0]) == pytest.approx(130 - 0.5, abs=1)  # Its line, half a point outside.


def test_saving_accepts_a_text_box_being_written(window: "PenfoldWindow", tmp_path: Path) -> None:
    import pikepdf

    from penfold.ui.annotation_toolbar import Tool
    from tests.sample_pdfs import make_pdf
    from tests.test_shape_drawing import choose

    assert open_and_wait(window, make_pdf(tmp_path / "plain.pdf", page_count=1))
    document = window.document
    assert document is not None
    choose(window, Tool.TEXT_BOX)
    drag(window, 0, (100, 100), (300, 120))
    process_pending_events()
    editor = window.document_view.text_editor
    assert editor is not None
    editor.text_view.get_buffer().set_text("Written, not applied yet")
    window.activate_action("win.save", None)
    wait_until(lambda: not document.is_modified)
    with pikepdf.open(document.path) as pdf:
        annotations = pdf.pages[0].obj.Annots
        assert [str(annotations[index].Subtype) for index in range(len(annotations))] == ["/FreeText"]


@pytest.fixture
def mark_window(window: "PenfoldWindow", tmp_path: Path) -> "PenfoldWindow":
    """A page with two lines of text, "Page 1 line 1" and "Page 1 line 2", and the first one highlighted."""
    from penfold.ui.text_selection import PagePoint, TextSelection
    from tests.test_page_content import make_text_pdf

    assert open_and_wait(window, make_text_pdf(tmp_path / "text.pdf"))
    window.document_view._set_selection(TextSelection(PagePoint(0, 95, 70), PagePoint(0, 97, 300)))
    assert window.annotating.mark_selection(Tool.HIGHLIGHT)
    return window


def the_mark(window: "PenfoldWindow") -> Annotation:
    assert window.document is not None
    return next(item for item in window.document.annotations if item.kind is Kind.HIGHLIGHT)


def marked_text(window: "PenfoldWindow") -> str:
    content = window.document_view.content
    assert content is not None
    return content.text_in_areas(0, list(the_mark(window).quads))


def test_the_end_of_a_mark_covers_more_text_letter_by_letter(mark_window: "PenfoldWindow") -> None:
    from penfold.document.reshaping import mark_handles

    window = mark_window
    original = the_mark(window)
    assert marked_text(window) == "Page 1 line 1"
    editor = start_editing(window, (90, 96))
    end_x, end_y = mark_handles(original)[Handle.END]
    assert editor.handle_at(*widget_point(window, 0, end_x, end_y)) is Handle.END
    assert editor.cursor_at(*widget_point(window, 0, end_x, end_y)) == "text"
    drag(window, 0, (end_x, end_y), (100, 116))  # Into the second line, just before its "1".
    press_key(window, Gdk.KEY_Return)
    assert marked_text(window) == "Page 1 line 1 Page"
    assert len(the_mark(window).quads) == 2
    window.activate_action("win.undo", None)
    assert the_mark(window) is original


def test_the_start_of_a_mark_covers_less_text(mark_window: "PenfoldWindow") -> None:
    from penfold.document.reshaping import mark_handles

    window = mark_window
    start_x, start_y = mark_handles(the_mark(window))[Handle.START]
    start_editing(window, (90, 96))
    drag(window, 0, (start_x, start_y), (start_x + 40, start_y))  # Past "Page 1 ".
    press_key(window, Gdk.KEY_Return)
    assert marked_text(window) == "line 1"


def test_a_press_on_a_mark_does_not_move_it(mark_window: "PenfoldWindow") -> None:
    window = mark_window
    original = the_mark(window)
    start_editing(window, (90, 96))
    drag(window, 0, (100, 96), (150, 200))
    view = window.document_view
    assert view.handle_editor is not None  # Still editing.
    press_key(window, Gdk.KEY_Return)
    assert the_mark(window) is original


def test_a_mark_without_text_under_it_cannot_change(mark_window: "PenfoldWindow") -> None:
    window = mark_window
    document = window.document
    assert document is not None
    empty = new_annotation(Kind.UNDERLINE, 0, (100, 400, 200, 412), RED, "Iban", quads=((100, 400, 200, 412),))
    document.execute(AddAnnotations(document, [empty]))
    process_pending_events()
    view = window.document_view
    view._ask_for_menu(*widget_point(window, 0, 150, 406))
    process_pending_events()
    action = window.lookup_action("reshape-annotation")
    assert action is not None
    assert not action.get_enabled()
    assert window.annotation_editing.menu is not None
    window.annotation_editing.menu.popdown()


def test_move_and_resize_from_the_annotations_panel(annotated_window: "PenfoldWindow") -> None:
    """From a row of the panel, the handles show on the page, and the page has the focus for Enter and Esc."""
    from penfold.ui.sidebar import sidebar as sidebar_views

    window = annotated_window
    window.split_view.set_show_sidebar(True)
    window.sidebar.show_view(sidebar_views.ANNOTATIONS)
    process_pending_events()
    panel = window.annotations_view
    wait_until(lambda: len(panel.bound_rows()) == 2)
    row = next(row for row in panel.bound_rows() if row.annotation is not None and row.annotation.kind is Kind.TEXT_BOX)
    panel._ask_for_menu(row, 10, 10)
    process_pending_events()
    window.activate_action("win.reshape-annotation", None)
    process_pending_events()
    view = window.document_view
    assert view.handle_editor is not None
    assert view.handle_editor.original is row.annotation
    assert view.has_focus()
    press_key(window, Gdk.KEY_Escape)
    assert view.handle_editor is None
