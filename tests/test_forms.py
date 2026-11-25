"""Reading the form fields of a PDF (AcroForm, ISO 32000-1, 12.7)."""

from pathlib import Path

import pikepdf
import pytest

from penfold.document.forms import (
    OFF,
    Alignment,
    FieldKind,
    FormField,
    Option,
    Widget,
    read_form_fields,
)
from tests.sample_pdfs import make_pdf

FIXTURES = Path(__file__).parent / "fixtures"


def widget(pdf: pikepdf.Pdf, rect: list[float], **entries: object) -> pikepdf.Dictionary:
    dictionary = pikepdf.Dictionary({"/Type": pikepdf.Name.Annot, "/Subtype": pikepdf.Name.Widget})
    dictionary["/Rect"] = pikepdf.Array(rect)
    for key, value in entries.items():
        dictionary[f"/{key}"] = value
    return pdf.make_indirect(dictionary)


def on_off(pdf: pikepdf.Pdf, state: str) -> pikepdf.Dictionary:
    """An appearance dictionary with the states of a checkbox or radio button."""
    empty = pdf.make_stream(b"")
    return pikepdf.Dictionary(N=pikepdf.Dictionary({f"/{state}": empty, "/Off": empty}))


def build_form(path: Path) -> Path:
    """Two pages with one field of each kind, a push button, a signature and a few unusual cases."""
    make_pdf(path, page_count=2)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        first: list[pikepdf.Dictionary] = []
        second: list[pikepdf.Dictionary] = []

        def field(page: list[pikepdf.Dictionary], rect: list[float], **entries: object) -> pikepdf.Dictionary:
            made = widget(pdf, rect, **entries)
            page.append(made)
            return made

        name = field(first, [72, 772, 272, 792], T=pikepdf.String("name"), FT=pikepdf.Name.Tx)
        name.V = pikepdf.String("Ana ")
        name.MaxLen = 10
        name.Q = 2
        name.DA = pikepdf.String("/Helv 11 Tf 0 g")
        notes = field(first, [72, 600, 272, 700], T=pikepdf.String("notes"), FT=pikepdf.Name.Tx, Ff=1 << 12)
        secret = field(first, [72, 560, 272, 580], T=pikepdf.String("pin"), FT=pikepdf.Name.Tx, Ff=1 << 13)
        agree = field(first, [72, 500, 92, 520], T=pikepdf.String("agree"), FT=pikepdf.Name.Btn)
        agree.AP = on_off(pdf, "Yes")
        agree.V = pikepdf.Name.Yes
        # A radio group whose two buttons are on different pages.
        small = field(first, [72, 400, 92, 420], AP=on_off(pdf, "S"))
        large = field(second, [72, 400, 92, 420], AP=on_off(pdf, "L"))
        size = pdf.make_indirect(
            pikepdf.Dictionary(
                T=pikepdf.String("size"), FT=pikepdf.Name.Btn, Ff=1 << 15, V=pikepdf.Name.L, Kids=[small, large]
            )
        )
        small.Parent = large.Parent = size
        colour = field(
            first, [300, 772, 400, 792], T=pikepdf.String("colour"), FT=pikepdf.Name.Ch, Ff=(1 << 17) | (1 << 18)
        )
        colour.Opt = pikepdf.Array(
            [pikepdf.String("Red"), pikepdf.Array([pikepdf.String("b"), pikepdf.String("Blue")])]
        )
        colour.V = pikepdf.String("b")
        pets = field(first, [300, 600, 400, 700], T=pikepdf.String("pets"), FT=pikepdf.Name.Ch, Ff=1 << 21)
        pets.Opt = pikepdf.Array([pikepdf.String("Cat"), pikepdf.String("Dog")])
        pets.V = pikepdf.Array([pikepdf.String("Cat"), pikepdf.String("Dog")])
        # Not filled in, hidden, or with no widget on a page.
        push = field(first, [300, 500, 400, 520], T=pikepdf.String("send"), FT=pikepdf.Name.Btn, Ff=1 << 16)
        signature = field(first, [300, 400, 400, 420], T=pikepdf.String("sign"), FT=pikepdf.Name.Sig)
        hidden = field(first, [300, 300, 400, 320], T=pikepdf.String("hidden"), FT=pikepdf.Name.Tx, F=2)
        orphan = widget(pdf, [0, 0, 10, 10], T=pikepdf.String("orphan"), FT=pikepdf.Name.Tx)
        # A field inside a named group, with its type and flags inherited from the group.
        street = widget(pdf, [72, 200, 272, 220], T=pikepdf.String("street"), V=pikepdf.String("Main"))
        first.append(street)
        address = pdf.make_indirect(
            pikepdf.Dictionary(T=pikepdf.String("address"), FT=pikepdf.Name.Tx, Ff=1 << 0, Kids=[street])
        )
        street.Parent = address
        pdf.pages[0].Annots = pdf.make_indirect(pikepdf.Array(first))
        pdf.pages[1].Annots = pdf.make_indirect(pikepdf.Array(second))
        fields = [name, notes, secret, agree, size, colour, pets, push, signature, hidden, orphan, address]
        pdf.Root.AcroForm = pikepdf.Dictionary(Fields=pikepdf.Array(fields), DA=pikepdf.String("/Helv 0 Tf 0 g"))
        pdf.save(path)
    return path


@pytest.fixture
def fields(tmp_path: Path) -> dict[str, FormField]:
    with pikepdf.open(build_form(tmp_path / "form.pdf")) as pdf:
        return {field.name: field for field in read_form_fields(pdf)}


def test_reads_only_the_fields_that_can_be_filled_in(fields: dict[str, FormField]) -> None:
    assert list(fields) == ["name", "notes", "pin", "agree", "size", "colour", "pets", "address.street"]


def test_text_fields(fields: dict[str, FormField]) -> None:
    name, notes, pin = fields["name"], fields["notes"], fields["pin"]
    assert (name.kind, name.value, name.max_length, name.alignment, name.font_size) == (
        FieldKind.TEXT,
        "Ana ",
        10,
        Alignment.RIGHT,
        11.0,
    )
    assert name.widgets == (Widget(page=0, rectangle=(72.0, 842.0 - 792, 272.0, 842.0 - 772)),)
    assert (notes.multiline, notes.password, notes.value, notes.font_size) == (True, False, "", 0.0)
    assert (pin.multiline, pin.password) == (False, True)


def test_checkboxes_and_radio_buttons(fields: dict[str, FormField]) -> None:
    agree, size = fields["agree"], fields["size"]
    assert (agree.kind, agree.value, [item.state for item in agree.widgets]) == (FieldKind.CHECKBOX, "Yes", ["Yes"])
    assert (size.kind, size.value) == (FieldKind.RADIO, "L")
    assert [(item.page, item.state) for item in size.widgets] == [(0, "S"), (1, "L")]


def test_dropdowns_and_lists(fields: dict[str, FormField]) -> None:
    colour, pets = fields["colour"], fields["pets"]
    assert (colour.kind, colour.editable, colour.value) == (FieldKind.DROPDOWN, True, "b")
    assert colour.options == (Option("Red", "Red"), Option("b", "Blue"))
    assert (pets.kind, pets.multi_select, pets.value) == (FieldKind.LIST, True, ("Cat", "Dog"))


def test_inherits_from_the_parents(fields: dict[str, FormField]) -> None:
    street = fields["address.street"]
    assert (street.kind, street.read_only, street.value) == (FieldKind.TEXT, True, "Main")


def test_pages_are_numbered_from_the_first_source_index(tmp_path: Path) -> None:
    with pikepdf.open(build_form(tmp_path / "form.pdf")) as pdf:
        size = next(field for field in read_form_fields(pdf, first_page=5) if field.name == "size")
    assert [item.page for item in size.widgets] == [5, 6]
    assert size.key == (5, "size")


def test_a_pdf_without_a_form_has_no_fields(tmp_path: Path) -> None:
    with pikepdf.open(make_pdf(tmp_path / "plain.pdf")) as pdf:
        assert read_form_fields(pdf) == []


def test_reads_the_form_of_the_sample_pdf() -> None:
    with pikepdf.open(FIXTURES / "form.pdf") as pdf:
        fields = read_form_fields(pdf)
    assert [(field.name, field.kind) for field in fields] == [
        ("name", FieldKind.TEXT),
        ("notes", FieldKind.TEXT),
        ("agree", FieldKind.CHECKBOX),
        ("size", FieldKind.RADIO),
        ("colour", FieldKind.DROPDOWN),
    ]
    size, colour = fields[3], fields[4]
    assert (size.value, [item.state for item in size.widgets]) == (OFF, ["0", "1"])
    assert [option.label for option in colour.options] == ["Red", "Green", "Blue"]


def test_states_that_are_not_utf8_are_kept_as_the_pdf_writes_them(tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "latin.pdf", page_count=1)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        # "Sí" in Latin-1, as in a real form.
        states = pikepdf.Dictionary(N=pikepdf.Object.parse(b"<< /Off 1 /S#ED 2 >>"))
        yes = widget(pdf, [72, 700, 92, 720], T=pikepdf.String("yes"), FT=pikepdf.Name.Btn, AP=states)
        yes.V = pikepdf.Object.parse(b"/S#ED")
        pdf.pages[0].Annots = pdf.make_indirect(pikepdf.Array([yes]))
        pdf.Root.AcroForm = pikepdf.Dictionary(Fields=pikepdf.Array([yes]))
        pdf.save(path)
    with pikepdf.open(path) as pdf:
        (field,) = read_form_fields(pdf)
    assert (field.value, field.widgets[0].state) == ("S#ed", "S#ed")


def test_widgets_are_placed_on_the_page_as_poppler_shows_it(tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "turned.pdf", page_count=1)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        page = pdf.pages[0]
        page.CropBox = pikepdf.Array([10, 20, 410, 620])  # 400 x 600
        pdf.Root.Pages.Rotate = 90  # inherited by the page
        box = widget(pdf, [110, 500, 210, 520], T=pikepdf.String("box"), FT=pikepdf.Name.Tx)
        page.Annots = pdf.make_indirect(pikepdf.Array([box]))
        pdf.Root.AcroForm = pikepdf.Dictionary(Fields=pikepdf.Array([box]))
        pdf.save(path)
    with pikepdf.open(path) as pdf:
        (field,) = read_form_fields(pdf)
    # Unturned: left 100, top 100, right 200, bottom 120 on a 400 x 600 page; a quarter turn clockwise.
    assert field.widgets[0].rectangle == (600.0 - 120, 100.0, 600.0 - 100, 200.0)
