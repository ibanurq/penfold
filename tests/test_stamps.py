"""Stamps of other programs: stamps that are not images, read, listed, edited and saved (ISO 32000-1, 12.5.6.12)."""

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
import pytest

from penfold.document.annotations import Annotation, AnnotationGroup, Kind, managed_copy, read_annotations
from penfold.document.commands.annotations import ChangeAnnotation
from penfold.document.document import OpenDocument
from penfold.document.pdf_values import numbers
from penfold.document.reshaping import Handle, can_move, can_resize, with_corner
from penfold.document.saving import save
from penfold.rendering.layout import ShownPage
from tests.gtk_helpers import process_pending_events, wait_until
from tests.test_annotation_menu import _descendants, annotation, right_click, rows_of
from tests.test_document_window import open_and_wait, window
from tests.test_images import near, only, painted, pixel, read, render, stamp, with_stamps

if TYPE_CHECKING:
    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]

A4 = (595.0, 842.0)
GREEN = (0.15, 0.64, 0.41)
GREEN_PIXEL = (38, 163, 105)
# A stamp's drawing: a green frame, filled green on its left half, as a word in a frame would be.
FRAMED = "0.15 0.64 0.41 RG 0.15 0.64 0.41 rg 4 w 2 2 116 36 re S 0 0 60 40 re f"


def approved(pdf: pikepdf.Pdf, rect: list[float] | None = None, **entries: object) -> pikepdf.Dictionary:
    """An "Approved" stamp of another program, 120 by 40 points, green, with its drawing."""
    entries = {"Name": pikepdf.Name.Approved, "C": pikepdf.Array(GREEN), **entries}
    return stamp(pdf, rect or [100, 600, 220, 640], FRAMED, **entries)


def bare(pdf: pikepdf.Pdf) -> pikepdf.Dictionary:
    """A stamp without its drawing: each viewer draws its own, from its name."""
    made = approved(pdf, [300, 600, 420, 640], Name=pikepdf.Name.Confidential)
    del made["/AP"]
    return made


def test_a_stamp_that_is_not_an_image_is_a_stamp(tmp_path: Path) -> None:
    found, without = with_stamps(tmp_path / "stamps.pdf", approved, bare)
    assert (found.kind, found.subtype, found.group, found.stamp) == (
        Kind.STAMP,
        "Stamp",
        AnnotationGroup.IMAGES_AND_STAMPS,
        "Approved",
    )
    assert found.color == pytest.approx(GREEN)
    assert found.drawing  # Kept as it is, as an image's.
    assert found.drawable
    assert (without.kind, without.stamp, without.drawing, without.drawable) == (Kind.STAMP, "Confidential", b"", False)


def test_a_stamp_without_a_name_is_a_draft(tmp_path: Path) -> None:
    (found,) = with_stamps(tmp_path / "stamp.pdf", lambda pdf: stamp(pdf, [100, 600, 220, 640], FRAMED))
    assert (found.kind, found.stamp) == (Kind.STAMP, "Draft")  # As the standard says.


def test_a_stamp_without_its_drawing_is_only_moved(tmp_path: Path) -> None:
    found, without = with_stamps(tmp_path / "stamps.pdf", approved, bare)
    assert (can_move(found), can_resize(found)) == (True, True)
    assert (can_move(without), can_resize(without)) == (True, False)
    with pytest.raises(ValueError, match="cannot draw"):
        managed_copy(without)


def test_it_keeps_its_proportion_when_resized(tmp_path: Path) -> None:
    (found,) = with_stamps(tmp_path / "stamp.pdf", approved)
    left, top, _right, _bottom = found.rectangle
    bigger = with_corner(found, Handle.BOTTOM_RIGHT, (left + 240, top + 30), A4)
    assert bigger.rectangle == pytest.approx((left, top, left + 240, top + 80))


def saved_again(tmp_path: Path, change: object = None) -> tuple[Path, Path, Annotation]:
    """The stamp written again by Penfold, changed as change says (annotation → annotation), and both PDFs."""
    path = tmp_path / "stamp.pdf"
    with_stamps(path, approved)
    document = OpenDocument.open(path)
    (original,) = document.annotations
    changed = managed_copy(original)
    if change is not None:
        changed = change(changed)  # type: ignore[operator]
    document.execute(ChangeAnnotation(document, original, changed))
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    return path, target, original


def test_written_again_it_looks_as_it_did(tmp_path: Path) -> None:
    path, target, original = saved_again(tmp_path)
    before, after = render(path), render(target)
    for x, y in ((130, 222), (190, 205)):  # On its fill, and on its frame.
        assert pixel(after, x, y) == pixel(before, x, y)
    assert near(pixel(after, 130, 222), GREEN_PIXEL)
    with pikepdf.open(target) as pdf:
        saved = only(pdf.pages[0].obj.Annots)
        assert (str(saved.Subtype), str(saved.IT), str(saved.Name)) == ("/Stamp", "/Stamp", "/Approved")
        assert numbers(saved.C) == pytest.approx(GREEN)
        assert numbers(saved.Rect) == pytest.approx([100, 600, 220, 640])
        (again,) = read_annotations(pdf)
    assert (again.kind, again.stamp) == (Kind.STAMP, "Approved")
    assert again.rectangle == pytest.approx(original.rectangle)


def test_its_opacity_goes_in_its_drawing_too(tmp_path: Path) -> None:
    def faint(stamped: Annotation) -> Annotation:
        return replace(stamped, style=replace(stamped.style, opacity=0.5))

    _path, target, _original = saved_again(tmp_path, faint)
    with pikepdf.open(target) as pdf:
        saved = only(pdf.pages[0].obj.Annots)
        assert float(saved.CA) == 0.5
        assert float(saved.AP.N.Resources.ExtGState.Look.ca) == 0.5
    shown = pixel(render(target), 130, 222)
    assert shown == pytest.approx(tuple(round((1 + value) / 2 * 255) for value in GREEN), abs=12)  # Half over white.


def test_one_without_a_colour_is_written_without_one(tmp_path: Path) -> None:
    path = tmp_path / "stamp.pdf"
    with_stamps(path, lambda pdf: stamp(pdf, [100, 600, 220, 640], FRAMED, Name=pikepdf.Name.Final))
    document = OpenDocument.open(path)
    (original,) = document.annotations
    document.execute(ChangeAnnotation(document, original, managed_copy(original)))
    save(document.save_plan(tmp_path / "saved.pdf"))
    with pikepdf.open(tmp_path / "saved.pdf") as pdf:
        assert "/C" not in only(pdf.pages[0].obj.Annots)
    assert read(tmp_path / "saved.pdf")[0].color is None


@pytest.fixture
def stamp_window(window: "PenfoldWindow", tmp_path: Path) -> "PenfoldWindow":
    """A page with two stamps of another program near its top: one with its drawing, one without."""
    path = tmp_path / "stamps.pdf"

    def without(pdf: pikepdf.Pdf) -> pikepdf.Dictionary:
        made = approved(pdf, [300, 700, 420, 740], Name=pikepdf.Name.Confidential)
        del made["/AP"]
        return made

    with_stamps(path, lambda pdf: approved(pdf, [100, 700, 220, 740]), without)
    assert open_and_wait(window, path)
    return window


def enabled(window: "PenfoldWindow") -> dict[str, bool]:
    names = ("annotation-menu-color", "format-annotation", "reshape-annotation")
    return {name: action.get_enabled() for name in names if (action := window.lookup_action(name)) is not None}


def test_its_colour_is_greyed_out_but_its_opacity_changes(stamp_window: "PenfoldWindow") -> None:
    window = stamp_window
    assert window.document is not None
    right_click(window, 160, 720)
    editing = window.annotation_editing
    assert editing.annotation is not None
    assert editing.annotation.stamp == "Approved"
    assert enabled(window) == {"annotation-menu-color": False, "format-annotation": True, "reshape-annotation": True}
    window.activate_action("win.format-annotation")
    process_pending_events()
    popover = editing.format_popover
    assert popover is not None
    assert list(rows_of(popover)) == ["Opacity"]
    circles = popover.get_child().get_first_child()  # type: ignore[union-attr]  # The row of colours.
    assert circles is not None
    assert [circle.get_sensitive() for circle in _descendants(circles) if circle.get_parent() is circles] == [False] * 6
    popover.popdown()
    process_pending_events()


def test_one_without_its_drawing_is_only_moved_or_deleted(stamp_window: "PenfoldWindow") -> None:
    window = stamp_window
    right_click(window, 360, 720)
    editing = window.annotation_editing
    assert editing.annotation is not None
    assert editing.annotation.stamp == "Confidential"
    assert enabled(window) == {"annotation-menu-color": False, "format-annotation": False, "reshape-annotation": True}
    assert editing.menu is not None
    labels = _labels(editing.menu.get_menu_model())
    assert "_Move" in labels
    assert "_Move and Resize" not in labels
    editing.menu.popdown()
    process_pending_events()


def _labels(model: object) -> list[str]:
    """The labels of a menu model, inside its sections too."""
    from gi.repository import Gio

    assert isinstance(model, Gio.MenuModel)
    found = []
    for index in range(model.get_n_items()):
        label = model.get_item_attribute_value(index, "label", None)
        if label is not None:
            found.append(label.get_string())
        section = model.get_item_link(index, "section")
        if section is not None:
            found += _labels(section)
    return found


def test_the_panel_lists_it_with_its_icon_and_name(stamp_window: "PenfoldWindow") -> None:
    from penfold.ui.sidebar import sidebar

    window = stamp_window
    window.split_view.set_show_sidebar(True)
    window.sidebar.show_view(sidebar.ANNOTATIONS)
    view = window.annotations_view
    wait_until(lambda: len(view._rows) == 2)
    rows = [view._rows[id(item)] for item in view.shown_annotations()]
    assert [row.icon.get_icon_name() for row in rows] == ["penfold-type-stamp-symbolic"] * 2
    assert [row.body.get_label() for row in rows] == ["Approved", "Confidential"]
    assert [row.color_bar.get_opacity() for row in rows] == [1, 1]  # In its colour.
    assert annotation(window, Kind.STAMP).group is AnnotationGroup.IMAGES_AND_STAMPS


def test_its_own_text_is_listed_instead_of_its_name(window: "PenfoldWindow", tmp_path: Path) -> None:
    from penfold.ui.sidebar import sidebar

    path = tmp_path / "stamp.pdf"
    with_stamps(path, lambda pdf: approved(pdf, [100, 700, 220, 740], Contents=pikepdf.String("Signed by Ann")))
    assert open_and_wait(window, path)
    window.split_view.set_show_sidebar(True)
    window.sidebar.show_view(sidebar.ANNOTATIONS)
    view = window.annotations_view
    wait_until(lambda: len(view._rows) == 1)
    (row,) = view._rows.values()
    assert row.body.get_label() == "Signed by Ann"


def test_its_drawing_is_painted_when_penfold_manages_it(tmp_path: Path) -> None:
    (found,) = with_stamps(tmp_path / "stamp.pdf", approved)
    shown = replace(managed_copy(found), rectangle=(100, 100, 340, 180))  # Twice as big.
    surface = painted(shown, ShownPage(0, A4))
    assert near(pixel(surface, 160, 140), GREEN_PIXEL)  # Its fill, stretched.
    assert pixel(surface, 280, 140) == (255, 255, 255)  # Inside its frame, unfilled.
    assert pixel(surface, 350, 140) == (255, 255, 255)
