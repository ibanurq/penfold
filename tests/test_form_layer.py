"""Filling in text fields on the pages (I1, I2, J2)."""

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from gi.repository import Gtk, Pango

from penfold.ui.form_layer import FieldEditor, font_size
from penfold.ui.form_toggle import ToggleField
from tests.gtk_helpers import process_pending_events, wait_until
from tests.test_document_window import open_and_wait, window
from tests.test_forms import build_form

if TYPE_CHECKING:
    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]


@pytest.fixture
def form_window(window: "PenfoldWindow", tmp_path: Path) -> "PenfoldWindow":
    assert open_and_wait(window, build_form(tmp_path / "form.pdf"))
    return window


def editors(window: "PenfoldWindow") -> dict[str, FieldEditor]:
    """The text boxes shown, by field name."""
    shown = window.document_view._form_layer._editors.values()
    return {editor.field.name: editor for editor in shown if isinstance(editor, FieldEditor)}


def toggles(window: "PenfoldWindow") -> dict[str, ToggleField]:
    """The checkboxes and radio buttons shown, by field name and state."""
    shown = window.document_view._form_layer._editors.values()
    return {f"{item.field.name}={item.widget.state}": item for item in shown if isinstance(item, ToggleField)}


def size_of(editor: FieldEditor, window: "PenfoldWindow") -> tuple[int, int]:
    """The size of the box of a field, padding included."""
    found, bounds = editor.view.compute_bounds(window.document_view)
    assert found
    return round(bounds.get_width()), round(bounds.get_height())


def type_in(editor: FieldEditor, text: str) -> None:
    editor.view.grab_focus()
    if isinstance(editor.view, Gtk.Text):
        editor.view.set_text(text)
    else:
        editor.view.get_buffer().set_text(text)
    process_pending_events()


def test_text_fields_of_the_visible_page_get_a_box_over_them(form_window: "PenfoldWindow") -> None:
    shown = editors(form_window)
    assert set(shown) == {"name", "notes", "pin", "address.street"}
    name = shown["name"]
    assert isinstance(name.view, Gtk.Text)
    assert (name.text, name.view.get_max_length(), name.view.get_property("xalign")) == ("Ana ", 10, 1.0)
    assert isinstance(shown["notes"].view, Gtk.TextView)
    assert not shown["address.street"].view.get_editable()
    zoom = form_window.document_view.zoom
    assert size_of(name, form_window) == (round(200 * zoom), round(20 * zoom))


def test_typing_fills_in_the_field_as_one_edit(form_window: "PenfoldWindow") -> None:
    document = form_window.document
    assert document is not None
    notes = editors(form_window)["notes"]
    type_in(notes, "Hello")
    type_in(notes, "Hello there")
    assert (document.field_value(notes.field), document.is_modified) == ("Hello there", True)
    form_window.activate_action("win.undo", None)
    process_pending_events()
    assert (notes.text, document.can_undo, document.is_modified) == ("", False, False)
    form_window.activate_action("win.redo", None)
    process_pending_events()
    assert notes.text == "Hello there"


def test_leaving_a_field_ends_the_edit(form_window: "PenfoldWindow") -> None:
    document = form_window.document
    assert document is not None
    shown = editors(form_window)
    type_in(shown["pin"], "12")
    type_in(shown["notes"], "x")
    type_in(shown["pin"], "1234")
    form_window.activate_action("win.undo", None)
    process_pending_events()
    assert (shown["pin"].text, shown["notes"].text) == ("12", "x")


def test_fields_of_pages_out_of_sight_have_no_widgets(form_window: "PenfoldWindow") -> None:
    view = form_window.document_view
    assert set(toggles(form_window)) == {"agree=Yes", "size=S"}  # The other radio button is on page 2.
    adjustment = view.vadjustment
    assert adjustment is not None
    adjustment.set_value(adjustment.get_upper())
    wait_until(lambda: "name" not in editors(form_window))


def test_the_text_follows_the_zoom(form_window: "PenfoldWindow") -> None:
    name = editors(form_window)["name"]
    view = form_window.document_view
    view.zoom_in()
    wait_until(lambda: size_of(name, form_window)[0] == round(200 * view.zoom))
    assert isinstance(name.view, Gtk.Text)
    attributes = name.view.get_attributes()
    assert attributes is not None
    expected = round(font_size(name.field, name.widget) * view.zoom * Pango.SCALE)
    assert attributes.to_string().endswith(f"absolute-size {expected}")


def test_a_checkbox_is_ticked_and_unticked(form_window: "PenfoldWindow") -> None:
    document = form_window.document
    assert document is not None
    agree = toggles(form_window)["agree=Yes"]
    assert agree.selected
    agree.choose()
    process_pending_events()
    assert (agree.selected, document.field_value(agree.field), document.is_modified) == (False, "Off", True)
    form_window.activate_action("win.undo", None)
    process_pending_events()
    assert (agree.selected, document.is_modified) == (True, False)


def test_a_radio_button_is_chosen_but_not_unchosen(form_window: "PenfoldWindow") -> None:
    document = form_window.document
    assert document is not None
    small = toggles(form_window)["size=S"]
    assert not small.selected
    small.choose()
    process_pending_events()
    assert (small.selected, document.field_value(small.field)) == (True, "S")
    small.choose()
    process_pending_events()
    assert (small.selected, document.field_value(small.field)) == (True, "S")
    form_window.activate_action("win.undo", None)
    process_pending_events()
    assert (small.selected, document.field_value(small.field), document.can_undo) == (False, "L", False)
