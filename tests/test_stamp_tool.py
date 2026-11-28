"""The Stamp tool: its menu of stamps, the frame that follows the pointer, a click that puts it, and the tool before."""

from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
import pytest
from gi.repository import Gdk, Gio, GLib, Gtk

from penfold.document.annotations import Annotation, Kind
from penfold.document.stamps import GREEN, RED
from penfold.rendering.stamp_look import stamp_size
from penfold.ui.annotation_toolbar import Tool
from tests.gtk_helpers import process_pending_events, wait_until
from tests.sample_pdfs import make_pdf
from tests.test_document_window import open_and_wait, window
from tests.test_image_tool import choose, click, tool_of
from tests.test_shape_drawing import widget_point

if TYPE_CHECKING:
    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]


@pytest.fixture
def stamp_window(window: "PenfoldWindow", tmp_path: Path) -> "PenfoldWindow":
    """A two-page document, with the annotation bar shown."""
    assert open_and_wait(window, make_pdf(tmp_path / "plain.pdf", page_count=2))
    window.annotating.show_bar()
    process_pending_events()
    return window


def menu_of(window: "PenfoldWindow") -> Gtk.PopoverMenu:
    """The stamp tool's menu, open above its button."""
    button = window.annotation_toolbar.tool_buttons[Tool.STAMP]
    child = button.get_last_child()
    while child is not None and not isinstance(child, Gtk.PopoverMenu):
        child = child.get_prev_sibling()
    assert isinstance(child, Gtk.PopoverMenu)
    return child


def start(window: "PenfoldWindow", name: str | None, before: Tool = Tool.HIGHLIGHT) -> None:
    """Choose a tool, then the stamp tool, and a stamp in its menu (None: close it without choosing one)."""
    choose(window, before)
    choose(window, Tool.STAMP)
    menu = menu_of(window)
    assert menu.get_visible()
    if name is not None:
        window.activate_action("win.put-stamp", GLib.Variant.new_string(name))
    menu.popdown()
    process_pending_events()
    wait_until(lambda: menu.get_parent() is None)


def stamps(window: "PenfoldWindow") -> list[Annotation]:
    assert window.document is not None
    return [item for item in window.document.annotations if item.kind is Kind.STAMP]


def labels(model: Gio.MenuModel) -> list[list[str]]:
    """The labels of a menu, by section."""
    sections = []
    for index in range(model.get_n_items()):
        section = model.get_item_link(index, "section")
        assert section is not None
        names = [section.get_item_attribute_value(item, "label", None) for item in range(section.get_n_items())]
        sections.append([name.get_string() for name in names if name is not None])
    return sections


def test_its_button_follows_the_image_with_an_arrow(stamp_window: "PenfoldWindow") -> None:
    bar = stamp_window.annotation_toolbar
    button = bar.tool_buttons[Tool.STAMP]
    assert button.get_prev_sibling() is bar.tool_buttons[Tool.IMAGE]
    assert button.get_tooltip_text() == "Stamp"
    icons = [child.get_icon_name() for child in _children(button.get_child()) if isinstance(child, Gtk.Image)]
    assert icons == ["penfold-type-stamp-symbolic", "pan-up-symbolic"]


def _children(widget: Gtk.Widget | None) -> list[Gtk.Widget]:
    found = []
    child = widget.get_first_child() if widget is not None else None
    while child is not None:
        found.append(child)
        child = child.get_next_sibling()
    return found


def test_its_menu_has_the_eight_stamps_in_three_groups(stamp_window: "PenfoldWindow") -> None:
    window = stamp_window
    choose(window, Tool.STAMP)
    menu = menu_of(window)
    assert menu.get_position() is Gtk.PositionType.TOP
    model = menu.get_menu_model()
    assert model is not None
    assert labels(model) == [
        ["Approved", "Final", "Received", "Paid"],
        ["Draft", "For Comment"],
        ["Not Approved", "Confidential"],
    ]
    assert tool_of(window) is Tool.STAMP  # Its button stays pressed meanwhile.
    menu.popdown()


def test_a_frame_of_its_size_follows_the_pointer_and_a_click_puts_it_there(stamp_window: "PenfoldWindow") -> None:
    window = stamp_window
    start(window, "Approved", before=Tool.FREEHAND)
    view = window.document_view
    placer = view.image_placer
    assert placer is not None
    assert tool_of(window) is Tool.STAMP
    width, height = stamp_size("Approved")
    view._on_motion(None, *widget_point(window, 1, 200, 300))  # type: ignore[arg-type]
    assert placer.frame is not None
    position, frame = placer.frame
    assert position == 1
    assert frame == pytest.approx((200, 300, 200 + width, 300 + height), abs=0.1)  # Its top left corner there.
    click(window, 1, (200, 300))
    (made,) = stamps(window)
    assert (made.page, made.stamp, made.managed, made.text) == (1, "Approved", True, "")
    assert made.color == GREEN  # Its own colour, not the bar's.
    assert made.rectangle == pytest.approx((200, 300, 200 + width, 300 + height), abs=0.1)
    assert (tool_of(window), view.image_placer) == (Tool.FREEHAND, None)  # The tool before comes back.


def test_it_is_saved_with_its_drawing(stamp_window: "PenfoldWindow", tmp_path: Path) -> None:
    window = stamp_window
    start(window, "Confidential")
    click(window, 0, (100, 100))
    document = window.document
    assert document is not None
    from penfold.document.saving import save

    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    with pikepdf.open(target) as pdf:
        entry = pdf.pages[0].obj.Annots[0]
        assert (str(entry.Subtype), str(entry.Name), "/AP" in entry) == ("/Stamp", "/Confidential", True)
    assert stamps(window)[0].color == RED


def test_closing_its_menu_without_a_stamp_brings_back_the_tool_before(stamp_window: "PenfoldWindow") -> None:
    window = stamp_window
    start(window, None, before=Tool.ARROW)
    assert (tool_of(window), window.document_view.image_placer) == (Tool.ARROW, None)


def test_esc_or_another_tool_stops_putting_it(stamp_window: "PenfoldWindow") -> None:
    window = stamp_window
    start(window, "Draft", before=Tool.CIRCLE)
    window._on_key_pressed(None, Gdk.KEY_Escape, 0, Gdk.ModifierType(0))  # type: ignore[arg-type]
    assert (tool_of(window), window.document_view.image_placer) == (Tool.CIRCLE, None)
    start(window, "Draft")
    choose(window, Tool.ARROW)
    assert window.document_view.image_placer is None
    click(window, 0, (100, 100), (200, 200))  # An arrow, not a stamp.
    assert stamps(window) == []


def test_on_a_page_turned_in_penfold_it_is_put_upright_as_seen(stamp_window: "PenfoldWindow") -> None:
    from penfold.document.commands.pages import RotatePages

    window = stamp_window
    document = window.document
    assert document is not None
    document.execute(RotatePages(document, [0], 90))
    process_pending_events()
    start(window, "Final")
    click(window, 0, (100, 100))
    (made,) = stamps(window)
    page = window.document_view.shown_page(0)
    assert page is not None
    width, height = stamp_size("Final")
    assert page.from_source(made.rectangle) == pytest.approx((100, 100, 100 + width, 100 + height), abs=0.1)


def open_stamp_menu(window: "PenfoldWindow", made: Annotation) -> None:
    """Open the menu of a stamp by a right click on its middle."""
    left, top, right, bottom = made.rectangle
    view = window.document_view
    view._ask_for_menu(*widget_point(window, made.page, (left + right) / 2, (top + bottom) / 2))
    process_pending_events()


def test_change_stamp_gives_it_another_keeping_its_centre(stamp_window: "PenfoldWindow") -> None:
    window = stamp_window
    document = window.document
    assert document is not None
    start(window, "Approved")
    click(window, 0, (100, 100))
    (approved,) = stamps(window)
    open_stamp_menu(window, approved)
    editing = window.annotation_editing
    assert editing.menu is not None
    action = window.lookup_action("change-stamp")
    assert action is not None
    state = action.get_state()
    assert state is not None
    assert (action.get_enabled(), state.get_string()) == (True, "Approved")  # Its item marked.
    window.activate_action("win.change-stamp", GLib.Variant.new_string("NotApproved"))
    process_pending_events()
    (changed,) = stamps(window)
    assert (changed.stamp, changed.color, changed.name) == ("NotApproved", RED, approved.name)
    centre = (approved.rectangle[0] + approved.rectangle[2]) / 2
    assert (changed.rectangle[0] + changed.rectangle[2]) / 2 == pytest.approx(centre)
    document.undo()  # One edit.
    process_pending_events()
    assert stamps(window)[0].stamp == "Approved"


def test_change_stamp_is_in_its_menu_with_the_eight(stamp_window: "PenfoldWindow") -> None:
    window = stamp_window
    start(window, "Final")
    click(window, 0, (100, 100))
    open_stamp_menu(window, stamps(window)[0])
    menu = window.annotation_editing.menu
    assert menu is not None
    model = menu.get_menu_model()
    assert model is not None
    section = model.get_item_link(0, "section")
    assert section is not None
    found = [
        (label.get_string(), section.get_item_link(index, "submenu"))
        for index in range(section.get_n_items())
        if (label := section.get_item_attribute_value(index, "label", None)) is not None
    ]
    assert [label for label, _submenu in found] == ["_Format…", "Change _Stamp", "_Move and Resize", "_Delete"]
    submenu = dict(found)["Change _Stamp"]
    assert submenu is not None
    # One section, with separators of the menu's own between the groups: GTK measures several too short beside the
    # colours, and the menu would scroll.
    (items,) = labels(submenu)
    assert items == ["Approved", "Final", "Received", "Paid", "Draft", "For Comment", "Not Approved", "Confidential"]
    customs = [
        attribute.get_string()
        for index in range(stamps_section(submenu).get_n_items())
        if (attribute := stamps_section(submenu).get_item_attribute_value(index, "custom", None)) is not None
    ]
    assert customs == ["stamp-separator-1", "stamp-separator-2"]
    menu.popdown()


def stamps_section(menu: Gio.MenuModel) -> Gio.MenuModel:
    section = menu.get_item_link(0, "section")
    assert section is not None
    return section


def test_a_stamp_of_another_program_is_changed_only_after_a_warning(window: "PenfoldWindow", tmp_path: Path) -> None:
    from gi.repository import Adw

    from tests.test_stamps import bare, with_stamps

    path = tmp_path / "stamps.pdf"
    with_stamps(path, bare)  # Without a drawing: Penfold could not draw it before.
    assert open_and_wait(window, path)
    for response, changed in (("cancel", False), ("change", True)):
        open_stamp_menu(window, stamps(window)[0])
        window.activate_action("win.change-stamp", GLib.Variant.new_string("Paid"))
        process_pending_events()
        dialog = window.get_visible_dialog()
        assert isinstance(dialog, Adw.AlertDialog)
        dialog.emit("response", response)
        dialog.close()
        process_pending_events()
        (found,) = stamps(window)
        assert (found.managed, found.stamp, bool(found.drawing)) == (
            changed,
            "Paid" if changed else "Confidential",
            changed,
        )


def test_its_menu_on_the_page_grows_to_show_the_submenu(stamp_window: "PenfoldWindow") -> None:
    """A menu on the page follows its content: Change Stamp's list is taller than the menu it opens from."""
    window = stamp_window
    start(window, "Draft")
    click(window, 0, (100, 100))
    open_stamp_menu(window, stamps(window)[0])
    menu = window.annotation_editing.menu
    assert menu is not None
    wait_until(lambda: menu.get_height() > 0)
    closed = menu.get_height()
    menu.set_property("visible-submenu", "Change _Stamp")
    wait_until(lambda: menu.get_height() > closed + 50)  # Not cut short, scrolling inside.
    menu.popdown()
