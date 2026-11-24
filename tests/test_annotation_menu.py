"""The menu of an annotation of a page: a right click on it, its colours and Delete (D72)."""

from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
import pytest
from gi.repository import Adw, Gdk, GLib, Gtk

from penfold.document.annotations import Annotation, Kind, LineEnds
from penfold.rendering.text_box import text_height
from penfold.ui.palette import color_to_hex
from tests.gtk_helpers import process_pending_events, wait_until
from tests.sample_pdfs import allowing, make_pdf
from tests.test_document_window import open_and_wait, window
from tests.test_shape_drawing import widget_point

if TYPE_CHECKING:
    from penfold.ui.format_popover import FormatPopover
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
                IC=pikepdf.Array([0.944, 0.966, 0.992]),  # Penfold's soft background
            ),
            entry(
                "/Line",
                [300, 740, 420, 790],
                L=pikepdf.Array([310, 750, 410, 780]),
                LE=pikepdf.Array([pikepdf.Name("/None"), pikepdf.Name.OpenArrow]),
                BS=pikepdf.Dictionary(W=3),
                C=pikepdf.Array([1, 0, 0]),
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
    assert window._edit_toast is not None
    toast, _command = window._edit_toast
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
    editor.text_view.get_buffer().set_text("Two lines\nof text")
    process_pending_events()
    zoom = window.document_view.zoom
    assert editor.height(zoom) == pytest.approx(text_height("Two lines\nof text", 200) * zoom, abs=1)
    editor.text_view.get_buffer().set_text("A new text, long enough to need a few more lines in this box. " * 3)
    editor.finish(apply=True)
    process_pending_events()
    box = annotation(window, Kind.TEXT_BOX)
    assert box.text.startswith("A new text")
    assert (box.managed, bool(box.drawing), window.document_view._hidden is None) == (True, True, True)
    assert box.rectangle[:3] == pytest.approx(old.rectangle[:3])  # Same corner and width, taller.
    assert box.rectangle[3] > old.rectangle[3]


def test_the_menu_has_the_items_of_the_type() -> None:
    from penfold.ui.annotation_editing import _menu_model

    texts = []
    for with_text, with_format, moved, resized in (
        (False, False, False, False),
        (True, False, False, False),
        (False, True, False, False),
        (True, True, False, False),
        (False, True, True, True),
        (True, False, True, False),
    ):
        model = _menu_model(colored=True, with_text=with_text, with_format=with_format, moved=moved, resized=resized)
        found = []
        for index in range(model.get_n_items()):
            section = model.get_item_link(index, "section")
            assert section is not None
            for item in range(section.get_n_items()):
                label = section.get_item_attribute_value(item, "label", None)
                if label is not None:
                    found.append(label.get_string())
        texts.append(found)
    assert texts == [
        ["_Delete"],
        ["_Edit Text…", "_Delete"],
        ["_Format…", "_Delete"],
        ["_Edit Text…", "_Format…", "_Delete"],
        ["_Format…", "_Move and Resize", "_Delete"],
        ["_Edit Text…", "_Move", "_Delete"],
    ]


def open_format(window: "PenfoldWindow", x: float, y: float) -> "FormatPopover":
    right_click(window, x, y)
    window.activate_action("win.format-annotation")
    process_pending_events()
    popover = window.annotation_editing.format_popover
    assert popover is not None
    return popover


def rows_of(popover: "FormatPopover") -> dict[str, Gtk.Widget]:
    """The rows of the panel, by their title."""
    rows: dict[str, Gtk.Widget] = {}
    child = popover.get_child()
    assert child is not None
    list_box = child.get_last_child()
    assert isinstance(list_box, Gtk.ListBox)
    index = 0
    while (row := list_box.get_row_at_index(index)) is not None:
        assert isinstance(row, Adw.PreferencesRow)
        rows[row.get_title()] = row
        index += 1
    return rows


def test_format_changes_show_at_once_and_are_undone_as_one(annotated_window: "PenfoldWindow") -> None:
    window = annotated_window
    assert window.document is not None
    popover = open_format(window, 200, 710)  # The highlight.
    assert list(rows_of(popover)) == ["Opacity"]
    opacity = rows_of(popover)["Opacity"]
    assert isinstance(opacity, Adw.ActionRow)
    scale = next(widget for widget in _descendants(opacity) if isinstance(widget, Gtk.Scale))
    scale.set_value(50)
    scale.set_value(30)
    popover.activate_action("format.color", GLib.Variant.new_string(GREEN))
    highlight = annotation(window, Kind.HIGHLIGHT)
    assert (highlight.managed, highlight.style.opacity, color_to_hex(highlight.color or (0, 0, 0))) == (
        True,
        0.3,
        GREEN,
    )
    popover.popdown()
    process_pending_events()
    window.activate_action("win.undo")  # All of it, at once.
    original = annotation(window, Kind.HIGHLIGHT)
    assert (original.managed, original.style.opacity) == (False, 1.0)


def test_shapes_rows_and_a_value_of_another_program(annotated_window: "PenfoldWindow") -> None:
    window = annotated_window
    popover = open_format(window, 360, 765)  # The arrow, 3 points wide.
    rows = rows_of(popover)
    assert list(rows) == ["Line Width", "Line", "Arrowheads", "Opacity"]
    width = rows["Line Width"]
    assert isinstance(width, Adw.ComboRow)
    labels = width.get_model()
    assert isinstance(labels, Gtk.StringList)
    assert [labels.get_string(index) for index in range(labels.get_n_items())] == ["Thin", "Medium", "3 pt", "Thick"]
    assert width.get_selected() == 2  # Its own width, kept until another is chosen.
    width.set_selected(3)
    heads = rows["Arrowheads"]
    assert isinstance(heads, Adw.ComboRow)
    heads.set_selected(1)
    arrow = annotation(window, Kind.ARROW)
    assert (arrow.style.line_width, arrow.style.line_ends) == (4.0, LineEnds.BOTH)


def test_a_text_box_grows_with_its_letters(annotated_window: "PenfoldWindow") -> None:
    window = annotated_window
    old = annotation(window, Kind.TEXT_BOX)
    popover = open_format(window, 420, 640)
    rows = rows_of(popover)
    assert list(rows) == ["Letter Size", "Background", "Border"]
    size, background = rows["Letter Size"], rows["Background"]
    assert isinstance(size, Adw.ComboRow)
    assert isinstance(background, Adw.SwitchRow)
    size.set_selected(3)  # Very large.
    background.set_active(False)
    box = annotation(window, Kind.TEXT_BOX)
    assert (box.style.font_size, box.style.background, bool(box.drawing)) == (18.0, False, True)
    assert box.rectangle[3] - box.rectangle[1] == pytest.approx(text_height("Old box", 200, 18))  # As its text needs.
    assert box.rectangle[:3] == pytest.approx(old.rectangle[:3])


def _descendants(widget: Gtk.Widget) -> list[Gtk.Widget]:
    found = []
    child = widget.get_first_child()
    while child is not None:
        found += [child, *_descendants(child)]
        child = child.get_next_sibling()
    return found


@pytest.fixture
def panel_window(annotated_window: "PenfoldWindow") -> "PenfoldWindow":
    """The annotated window with the Annotations view of the panel shown (comments and text boxes listed)."""
    from penfold.ui.sidebar import sidebar as sidebar_views

    annotated_window.split_view.set_show_sidebar(True)
    annotated_window.sidebar.show_view(sidebar_views.ANNOTATIONS)
    for group in ("text-markups", "shapes", "others"):  # All four are shown by default (D76).
        annotated_window.annotations_view.activate_action(f"annotations-filter.{group}", None)
    process_pending_events()
    return annotated_window


def select_all_listed(window: "PenfoldWindow") -> list[Annotation]:
    view = window.annotations_view
    view.selection.select_all()
    return view.selected_annotations()


def test_delete_deletes_the_annotations_selected_in_the_panel(panel_window: "PenfoldWindow") -> None:
    window = panel_window
    assert window.document is not None
    selected = select_all_listed(window)
    assert [item.kind for item in selected] == [Kind.COMMENT, Kind.TEXT_BOX]
    assert window._on_delete_key(window, None)
    assert [item.kind for item in window.document.annotations if item.kind in {Kind.COMMENT, Kind.TEXT_BOX}] == []
    assert window._edit_toast is not None
    toast, _command = window._edit_toast
    assert toast.get_title() == "2 annotations deleted"
    window.activate_action("win.undo")
    assert len(window.annotations_view.shown_annotations()) == 2


def test_esc_clears_the_selection_of_the_panel(panel_window: "PenfoldWindow") -> None:
    window = panel_window
    select_all_listed(window)
    assert window._unselect_panel_view()
    assert window.annotations_view.selected_annotations() == []
    assert not window._on_delete_key(window, None)  # Nothing selected: Delete does nothing here.


def test_a_right_click_on_a_row_opens_the_menu_of_its_annotation(panel_window: "PenfoldWindow") -> None:
    window = panel_window
    view = window.annotations_view
    wait_until(lambda: len(view.bound_rows()) == 2)
    row = next(row for row in view.bound_rows() if row.annotation is not None and row.annotation.kind is Kind.TEXT_BOX)
    view._ask_for_menu(row, 10, 10)
    process_pending_events()
    editing = window.annotation_editing
    assert editing.annotation is row.annotation
    assert editing.menu is not None
    assert editing.menu.get_parent() is view
    assert view.selected_annotations() == [row.annotation]  # Selected alone.
    editing.menu.popdown()
    process_pending_events()
    view.selection.unselect_all()
    assert not view._on_key_pressed(None, Gdk.KEY_Menu, 0, Gdk.ModifierType(0))  # type: ignore[arg-type]
    view.selection.select_item(0, True)
    assert view._on_key_pressed(None, Gdk.KEY_F10, 0, Gdk.ModifierType.SHIFT_MASK)  # type: ignore[arg-type]
    process_pending_events()
    assert editing.annotation is view.selected_annotations()[0]


def test_the_headings_count_what_is_left(panel_window: "PenfoldWindow") -> None:
    window = panel_window
    view = window.annotations_view
    window.annotation_editing.delete([annotation(window, Kind.COMMENT)])
    process_pending_events()
    headings = [
        widget.get_label()
        for widget in _descendants(view.list)
        if isinstance(widget, Gtk.Label) and widget.has_css_class("caption-heading")
    ]
    assert headings == ["Text Elements (1)"]
