"""Saving the values filled in, so that the form stays editable in other viewers (I5, I7, I8)."""

from dataclasses import replace
from pathlib import Path

import gi
import pikepdf
import pytest

from penfold.document.annotations import AnnotationGroup
from penfold.document.commands.forms import SetFieldValue
from penfold.document.commands.pages import AddPages, DeletePages
from penfold.document.document import OpenDocument
from penfold.document.form_filling import fill_in
from penfold.document.forms import FieldValue, FormField, field_dictionaries, read_form_fields, widget_dictionaries
from penfold.document.saving import save
from tests.test_forms import FIXTURES, build_form

gi.require_version("Poppler", "0.18")
from gi.repository import Gio, Poppler  # noqa: E402


@pytest.fixture
def document(tmp_path: Path) -> OpenDocument:
    return OpenDocument.open(build_form(tmp_path / "form.pdf"))


def field(document: OpenDocument, name: str, source_start: int = 0) -> FormField:
    return next(item for item in document.form_fields if item.key == (source_start, name))


def fill(document: OpenDocument, name: str, value: FieldValue, source_start: int = 0) -> None:
    document.execute(SetFieldValue(document, field(document, name, source_start), value))


def saved_values(path: Path) -> dict[str, FieldValue]:
    with pikepdf.open(path) as pdf:
        return {item.name: item.value for item in read_form_fields(pdf)}


def poppler_texts(path: Path) -> dict[str, str]:
    """The text of each text field as Poppler (and so Papers) reads it."""
    poppler = Poppler.Document.new_from_gfile(Gio.File.new_for_path(str(path)), None, None)
    texts = {}
    for index in range(poppler.get_n_pages()):
        for mapping in poppler.get_page(index).get_form_field_mapping():
            form_field = mapping.field
            if form_field.get_field_type() == Poppler.FormFieldType.TEXT:
                texts[form_field.get_name()] = form_field.text_get_text() or ""
    return texts


def test_every_kind_of_value_is_saved(document: OpenDocument, tmp_path: Path) -> None:
    fill(document, "name", "Eva")
    fill(document, "notes", "Two\nlines")
    fill(document, "agree", "Off")
    fill(document, "size", "S")
    fill(document, "colour", "Red")
    fill(document, "pets", ("Dog",))
    target = tmp_path / "filled.pdf"
    assert save(document.save_plan(target)) == 0
    values = saved_values(target)
    assert {name: values[name] for name in ("name", "notes", "agree", "size", "colour", "pets")} == {
        "name": "Eva",
        "notes": "Two\nlines",
        "agree": "Off",
        "size": "S",
        "colour": "Red",
        "pets": ("Dog",),
    }
    assert poppler_texts(target)["name"] == "Eva"


def test_checkboxes_and_radio_buttons_show_their_new_state(document: OpenDocument, tmp_path: Path) -> None:
    fill(document, "agree", "Off")
    fill(document, "size", "S")
    target = tmp_path / "filled.pdf"
    save(document.save_plan(target))
    with pikepdf.open(target) as pdf:
        fields = field_dictionaries(pdf)
        (agree,) = widget_dictionaries(fields["agree"])
        small, large = widget_dictionaries(fields["size"])
        assert (str(agree.AS), str(small.AS), str(large.AS)) == ("/Off", "/S", "/Off")


def appearances(path: Path) -> dict[str, bytes | None]:
    """The normal appearance of the first widget of each field, by name (None without one)."""
    with pikepdf.open(path) as pdf:
        found = {}
        for name, dictionary in field_dictionaries(pdf).items():
            widget = widget_dictionaries(dictionary)[0]
            normal = widget.AP.N if "/AP" in widget else None
            found[name] = normal.read_bytes() if isinstance(normal, pikepdf.Stream) else None
        return found


def test_only_changed_fields_get_a_new_appearance(tmp_path: Path) -> None:
    sample = tmp_path / "sample.pdf"
    sample.write_bytes((FIXTURES / "form.pdf").read_bytes())
    document = OpenDocument.open(sample)
    before = appearances(sample)
    fill(document, "name", "Eva")
    target = tmp_path / "filled.pdf"
    save(document.save_plan(target))
    after = appearances(target)
    assert b"(Eva) Tj" in (after["name"] or b"")
    assert after["notes"] == before["notes"]
    with pikepdf.open(target) as pdf:
        assert "/NeedAppearances" not in pdf.Root.AcroForm  # One line, in the fonts' encoding: drawn here.


def test_viewers_draw_what_qpdf_cannot(document: OpenDocument, tmp_path: Path) -> None:
    fill(document, "notes", "Two\nlines")
    target = tmp_path / "filled.pdf"
    save(document.save_plan(target))
    with pikepdf.open(target) as pdf:
        assert bool(pdf.Root.AcroForm.NeedAppearances)


def test_a_field_that_fails_does_not_stop_the_others(tmp_path: Path) -> None:
    path = build_form(tmp_path / "form.pdf")
    with pikepdf.open(path) as pdf:
        fields = {item.name: item for item in read_form_fields(pdf)}
        gone = replace(fields["name"], name="gone")
        assert fill_in(pdf, [(gone, "x"), (fields["notes"], "kept")]) == 1
        assert str(pdf.Root.AcroForm.Fields[1].V) == "kept"


def test_fields_of_added_pdfs_are_saved_with_their_new_names(document: OpenDocument, tmp_path: Path) -> None:
    added = document.add_source(FIXTURES / "form.pdf")
    document.execute(AddPages(document, added, document.page_count))
    fill(document, "name", "Opened")
    fill(document, "name", "Added", source_start=2)
    target = tmp_path / "filled.pdf"
    save(document.save_plan(target))
    values = saved_values(target)
    assert (values["name"], values["name_2"]) == ("Opened", "Added")


def test_extracted_pages_keep_their_values(document: OpenDocument, tmp_path: Path) -> None:
    fill(document, "name", "Eva")
    target = tmp_path / "extracted.pdf"
    save(document.extract_plan([0], target))
    assert saved_values(target)["name"] == "Eva"


def test_fields_of_deleted_pages_leave_the_form_with_their_values(document: OpenDocument, tmp_path: Path) -> None:
    fill(document, "name", "Eva")
    document.execute(DeletePages(document, [0]))
    target = tmp_path / "filled.pdf"
    save(document.save_plan(target))
    assert set(saved_values(target)) == {"size"}


def page_text(path: Path) -> str:
    poppler = Poppler.Document.new_from_gfile(Gio.File.new_for_path(str(path)), None, None)
    return poppler.get_page(0).get_text() or ""


def test_a_flattened_copy_draws_the_fields_and_drops_the_form(tmp_path: Path) -> None:
    path = tmp_path / "sample.pdf"
    with pikepdf.open(FIXTURES / "form.pdf") as pdf:  # A real form, with its fonts.
        note = pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Square, Rect=[10, 10, 50, 50])
        pdf.pages[0].Annots.append(pdf.make_indirect(note))
        pdf.save(path)
    document = OpenDocument.open(path)
    fill(document, "name", "Eva")
    target = tmp_path / "flattened.pdf"
    assert save(document.save_plan(target, flatten=True)) == 0
    with pikepdf.open(target) as pdf:
        assert "/AcroForm" not in pdf.Root
        annots = pdf.pages[0].Annots
        assert [str(annots[index].Subtype) for index in range(len(annots))] == ["/Square"]
    assert "Eva" in page_text(target)
    assert document.is_modified  # An exported copy: the document is not saved by it.


def test_printing_leaves_out_the_groups_not_chosen(tmp_path: Path) -> None:
    path = build_form(tmp_path / "form.pdf")
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        for subtype in ("/Highlight", "/Ink", "/Text", "/FileAttachment"):
            mark = pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name(subtype), Rect=[10, 10, 50, 50])
            pdf.pages[0].Annots.append(pdf.make_indirect(mark))
        note = pdf.pages[0].Annots[-2]
        popup = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Popup, Parent=note))
        pdf.pages[0].Annots.append(popup)
        pdf.save(path)
    document = OpenDocument.open(path)
    fill(document, "name", "Eva")
    target = tmp_path / "print.pdf"
    save(document.print_plan(target, frozenset({AnnotationGroup.SHAPES, AnnotationGroup.TEXT_ELEMENTS})))
    with pikepdf.open(target) as pdf:
        annots = pdf.pages[0].Annots
        subtypes = [str(annots[index].Subtype) for index in range(len(annots))]
        assert "/Outlines" not in pdf.Root
    assert [item for item in subtypes if item != "/Widget"] == ["/Highlight", "/FileAttachment"]
    assert saved_values(target)["name"] == "Eva"


def test_printing_can_leave_out_the_other_types_but_keeps_the_fields(tmp_path: Path) -> None:
    path = build_form(tmp_path / "form.pdf")
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        for subtype in ("/Highlight", "/FileAttachment", "/Link"):
            mark = pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name(subtype), Rect=[10, 10, 50, 50])
            pdf.pages[0].Annots.append(pdf.make_indirect(mark))
        pdf.save(path)
    target = tmp_path / "print.pdf"
    document = OpenDocument.open(path)  # Kept: closing it removes the private copy that is printed.
    save(document.print_plan(target, frozenset({AnnotationGroup.OTHERS})))
    with pikepdf.open(target) as pdf:
        annots = pdf.pages[0].Annots
        subtypes = [str(annots[index].Subtype) for index in range(len(annots))]
    assert "/Widget" in subtypes
    assert [item for item in subtypes if item != "/Widget"] == ["/Highlight", "/Link"]


def test_a_form_that_asks_viewers_to_draw_it_is_flattened_with_its_values(tmp_path: Path) -> None:
    path = tmp_path / "sample.pdf"
    with pikepdf.open(FIXTURES / "form.pdf") as pdf:
        pdf.Root.AcroForm.NeedAppearances = True  # As in forms made with OpenOffice.
        pdf.save(path)
    document = OpenDocument.open(path)
    fill(document, "name", "Eva")
    target = tmp_path / "flattened.pdf"
    save(document.save_plan(target, flatten=True))
    assert "Eva" in page_text(target)
