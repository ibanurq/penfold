"""The menu of an annotation of a page: a right click on it, its colours and Delete (D72)."""

from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
import pytest
from gi.repository import Adw, GLib

from penfold.document.annotations import Annotation, Kind
from tests.gtk_helpers import process_pending_events
from tests.sample_pdfs import allowing, make_pdf
from tests.test_document_window import open_and_wait, window
from tests.test_shape_drawing import widget_point

if TYPE_CHECKING:
    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]

GREEN = "#8ff0a4"
PAGE_HEIGHT = 842


def entry(subtype: str, rect: list[float], **entries: object) -> pikepdf.Dictionary:
    dictionary = pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name(subtype), Rect=pikepdf.Array(rect))
    for key, value in entries.items():
        dictionary[f"/{key}"] = value
    return dictionary


def make_annotated_pdf(path: Path, *, permissions: tuple[str, ...] | None = None) -> Path:
    """A page with annotations of another program: a highlight, a cloudy square and a freehand drawing.

    They are near the top, so that the menu can point at them in the window.
    """
    make_pdf(path, page_count=1)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        annotations = [
            entry(
                "/Highlight",
                [100, 700, 300, 720],
                QuadPoints=pikepdf.Array([100, 720, 300, 720, 100, 700, 300, 700]),
                C=pikepdf.Array([0.976, 0.941, 0.42]),
            ),
            entry("/Square", [100, 400, 300, 600], C=pikepdf.Array([1, 0, 0]), BE=pikepdf.Dictionary(S=pikepdf.Name.C)),
            entry("/Ink", [400, 700, 500, 800], InkList=pikepdf.Array([pikepdf.Array([400, 700, 500, 800])])),
            entry("/Text", [520, 780, 540, 800], Contents=pikepdf.String("Old note"), C=pikepdf.Array([1, 1, 0])),
            entry(
                "/FreeText",
                [320, 620, 520, 660],
                Contents=pikepdf.String("Old box"),
                DA=pikepdf.String("0 g /Helv 11 Tf"),
                C=pikepdf.Array([0.6, 0.757, 0.945]),
            ),
        ]
        pdf.pages[0].obj.Annots = pdf.make_indirect(pikepdf.Array([pdf.make_indirect(item) for item in annotations]))
        if permissions is None:
            pdf.save(path)
        else:
            pdf.save(path, encryption=pikepdf.Encryption(owner="owner", user="", allow=allowing(*permissions)))
    return path


@pytest.fixture
def annotated_window(window: "PenfoldWindow", tmp_path: Path) -> "PenfoldWindow":
    assert open_and_wait(window, make_annotated_pdf(tmp_path / "annotated.pdf"))
    return window


def right_click(window: "PenfoldWindow", x: float, y: float) -> None:
    """Right-click a point of the first page as the PDF places it (from its bottom left corner)."""
    view = window.document_view
    view._ask_for_menu(*widget_point(window, 0, x, PAGE_HEIGHT - y))
    process_pending_events()


def annotation(window: "PenfoldWindow", kind: Kind) -> Annotation:
    assert window.document is not None
    return next(item for item in window.document.annotations if item.kind is kind)


def test_a_right_click_opens_the_menu_of_the_annotation_under_it(annotated_window: "PenfoldWindow") -> None:
    window = annotated_window
    editing = window.annotation_editing
    right_click(window, 200, 710)
    highlight = annotation(window, Kind.HIGHLIGHT)
    assert editing.menu is not None
    assert editing.menu.get_visible()
    assert (editing.annotation, window.document_view._marked) == (highlight, highlight)  # Outlined.
    color = window.lookup_action("annotation-menu-color")
    assert color is not None
    state = color.get_state()
    assert state is not None
    assert state.get_string() == "#f9f06b"  # Its yellow has the ring.
    menu = editing.menu
    menu.popdown()
    process_pending_events()
    assert (editing.menu is None, window.document_view._marked is None) == (True, True)  # mypy narrows menu


def test_a_right_click_elsewhere_does_nothing(annotated_window: "PenfoldWindow") -> None:
    right_click(annotated_window, 450, 500)
    assert annotated_window.annotation_editing.menu is None


def test_a_colour_changes_the_annotation_and_closes_the_menu(annotated_window: "PenfoldWindow") -> None:
    window = annotated_window
    assert window.document is not None
    right_click(window, 200, 710)
    window.activate_action("win.annotation-menu-color", GLib.Variant.new_string(GREEN))
    process_pending_events()
    changed = annotation(window, Kind.HIGHLIGHT)
    assert changed.managed
    assert changed.color == pytest.approx((0x8F / 255, 0xF0 / 255, 0xA4 / 255))
    assert window.annotation_editing.menu is None
    assert [item.kind for item in window.document.replaced_annotations] == [Kind.HIGHLIGHT]  # Poppler leaves it out.
    window.activate_action("win.undo")
    assert not annotation(window, Kind.HIGHLIGHT).managed


def test_delete_deletes_it_with_a_toast_to_undo_it(annotated_window: "PenfoldWindow") -> None:
    window = annotated_window
    assert window.document is not None
    right_click(window, 200, 710)
    window.activate_action("win.delete-annotation")
    process_pending_events()
    assert Kind.HIGHLIGHT not in [item.kind for item in window.document.annotations]
    assert window._undo_toast is not None
    toast, _command = window._undo_toast
    assert toast.get_title() == "Annotation deleted"
    toast.emit("button-clicked")
    assert annotation(window, Kind.HIGHLIGHT) is not None


def test_types_penfold_does_not_make_can_only_be_deleted(annotated_window: "PenfoldWindow") -> None:
    window = annotated_window
    right_click(window, 450, 750)
    assert window.annotation_editing.annotation == annotation(window, Kind.OTHER)
    color, delete = window.lookup_action("annotation-menu-color"), window.lookup_action("delete-annotation")
    assert color is not None
    assert delete is not None
    assert (color.get_enabled(), delete.get_enabled()) == (False, True)


def test_one_penfold_cannot_draw_again_is_changed_only_after_a_warning(annotated_window: "PenfoldWindow") -> None:
    window = annotated_window
    for response, changed in (("cancel", False), ("change", True)):
        right_click(window, 101, 500)  # On the cloudy square's line.
        window.activate_action("win.annotation-menu-color", GLib.Variant.new_string(GREEN))
        process_pending_events()
        dialog = window.get_visible_dialog()
        assert isinstance(dialog, Adw.AlertDialog)
        dialog.emit("response", response)
        dialog.close()
        process_pending_events()
        assert annotation(window, Kind.RECTANGLE).managed is changed


def test_without_permission_to_annotate_everything_is_greyed_out(window: "PenfoldWindow", tmp_path: Path) -> None:
    assert open_and_wait(window, make_annotated_pdf(tmp_path / "locked.pdf", permissions=("print_highres",)))
    right_click(window, 200, 710)
    assert window.annotation_editing.menu is not None
    for name in ("annotation-menu-color", "delete-annotation"):
        action = window.lookup_action(name)
        assert action is not None
        assert not action.get_enabled()


def test_edit_text_changes_a_comment_in_its_popover(annotated_window: "PenfoldWindow") -> None:
    window = annotated_window
    right_click(window, 530, 790)
    assert window.annotation_editing.annotation == annotation(window, Kind.COMMENT)
    window.activate_action("win.edit-annotation-text")
    process_pending_events()
    popover = window.annotation_editing.comment_popover
    assert popover is not None
    assert popover.text == "Old note"
    popover.text_view.get_buffer().set_text("New note")
    popover.apply_button.emit("clicked")
    process_pending_events()
    comment = annotation(window, Kind.COMMENT)
    assert (comment.text, comment.managed) == ("New note", True)


def test_edit_text_writes_a_text_box_on_the_page(annotated_window: "PenfoldWindow") -> None:
    window = annotated_window
    old = annotation(window, Kind.TEXT_BOX)
    right_click(window, 420, 640)
    window.activate_action("win.edit-annotation-text")
    process_pending_events()
    editor = window.document_view.text_editor
    assert editor is not None
    assert editor.text == "Old box"
    assert window.document_view._hidden is old  # Not painted under the editor.
    editor.text_view.get_buffer().set_text("A new text, long enough to need a few more lines in this box. " * 3)
    editor.finish(apply=True)
    process_pending_events()
    box = annotation(window, Kind.TEXT_BOX)
    assert box.text.startswith("A new text")
    assert (box.managed, bool(box.drawing), window.document_view._hidden is None) == (True, True, True)
    assert box.rectangle[:3] == pytest.approx(old.rectangle[:3])  # Same corner and width, taller.
    assert box.rectangle[3] > old.rectangle[3]


def test_only_comments_and_text_boxes_have_edit_text() -> None:
    from penfold.ui.annotation_editing import _menu_model

    texts = []
    for with_text in (False, True):
        model = _menu_model(colored=True, with_text=with_text)
        found = []
        for index in range(model.get_n_items()):
            section = model.get_item_link(index, "section")
            assert section is not None
            for item in range(section.get_n_items()):
                label = section.get_item_attribute_value(item, "label", None)
                if label is not None:
                    found.append(label.get_string())
        texts.append(found)
    assert texts == [["_Delete"], ["_Edit Text…", "_Delete"]]
