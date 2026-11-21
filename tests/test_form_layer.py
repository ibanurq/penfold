"""Filling in text fields on the pages (I1, I2, J2)."""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
import pytest
from gi.repository import Gio, Gtk, Pango

from penfold.ui.form_choice import DropdownField, ListField
from penfold.ui.form_text import FieldEditor, font_size
from penfold.ui.form_toggle import ToggleField
from tests.gtk_helpers import process_pending_events, wait_until
from tests.sample_pdfs import make_pdf
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


def shown_field(window: "PenfoldWindow", name: str) -> object:
    """The widget shown for the only place of a field."""
    shown = window.document_view._form_layer._editors.values()
    return next(item for item in shown if item.field.name == name)


def undo(window: "PenfoldWindow") -> None:
    window.activate_action("win.undo", None)
    process_pending_events()


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


def test_a_dropdown_shows_and_chooses_options(form_window: "PenfoldWindow") -> None:
    document = form_window.document
    assert document is not None
    colour = shown_field(form_window, "colour")
    assert isinstance(colour, DropdownField)
    assert colour.text == "Blue"  # The value is "b"; the option shows "Blue".
    colour.choose(colour.field.options[0])
    process_pending_events()
    assert (colour.text, document.field_value(colour.field)) == ("Red", "Red")
    undo(form_window)
    assert (colour.text, document.field_value(colour.field)) == ("Blue", "b")


def test_a_dropdown_that_lets_the_reader_write_takes_a_text(form_window: "PenfoldWindow") -> None:
    document = form_window.document
    assert document is not None
    colour = shown_field(form_window, "colour")
    assert isinstance(colour, DropdownField)
    assert colour._text is not None
    colour._text.grab_focus()
    colour._text.set_text("Green")
    process_pending_events()
    assert document.field_value(colour.field) == "Green"
    undo(form_window)
    assert (colour.text, document.can_undo) == ("Blue", False)


def test_a_list_chooses_several_options(form_window: "PenfoldWindow") -> None:
    document = form_window.document
    assert document is not None
    pets = shown_field(form_window, "pets")
    assert isinstance(pets, ListField)
    chosen = [pets.chosen]
    pets.choose(("Dog",))
    process_pending_events()
    chosen.append(pets.chosen)
    undo(form_window)
    chosen.append(pets.chosen)
    assert chosen == [("Cat", "Dog"), ("Dog",), ("Cat", "Dog")]
    assert document.field_value(pets.field) == ("Cat", "Dog")


class ChosenFile:
    """Stands for the system's file dialog: it "chooses" a file at once, and remembers the name it proposed."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.proposed = ""

    def __call__(self, _title: str, initial_file: Gio.File | None = None) -> "ChosenFile":
        self.proposed = (initial_file.get_basename() if initial_file is not None else None) or ""
        return self

    def save(self, _parent: object, _cancellable: object, callback: Callable[..., None], data: object) -> None:
        callback(self, None, data)

    def save_finish(self, _result: object) -> Gio.File:
        return Gio.File.new_for_path(str(self.path))


def test_save_as_offers_to_flatten_and_makes_an_exported_copy(
    form_window: "PenfoldWindow", tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Imported here: the dialogue's template needs the interface files the application fixture loads.
    from penfold.ui.dialogs.save_as_dialog import PenfoldSaveAsDialog

    document = form_window.document
    assert document is not None
    type_in(editors(form_window)["notes"], "Hello")
    chosen = ChosenFile(tmp_path / "copy.pdf")
    monkeypatch.setattr("penfold.ui.window.pdf_file_dialog", chosen)
    form_window.activate_action("win.save-as", None)
    dialog = form_window.get_visible_dialog()
    assert isinstance(dialog, PenfoldSaveAsDialog)
    assert not dialog.flatten_row.get_active()
    dialog.flatten_row.set_active(True)
    dialog.continue_button.emit("clicked")
    wait_until(lambda: chosen.path.exists() and not form_window._saving)
    assert chosen.proposed == "form_flattened.pdf"
    with pikepdf.open(chosen.path) as pdf:
        assert "/AcroForm" not in pdf.Root
    assert (document.path.name, document.is_modified) == ("form.pdf", True)


def test_save_as_without_a_form_goes_straight_to_the_file(
    window: "PenfoldWindow", tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert open_and_wait(window, make_pdf(tmp_path / "plain.pdf"))
    chosen = ChosenFile(tmp_path / "copy.pdf")
    monkeypatch.setattr("penfold.ui.window.pdf_file_dialog", chosen)
    window.activate_action("win.save-as", None)
    wait_until(lambda: chosen.path.exists() and not window._saving)
    assert window.get_visible_dialog() is None
    assert window.document is not None
    assert window.document.path == chosen.path
