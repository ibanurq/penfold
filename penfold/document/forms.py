"""Form fields (AcroForm, ISO 32000-1, 12.7): what can be filled in, where it is drawn and what it holds.

Penfold fills in text fields, checkboxes, radio buttons, dropdowns and lists (I1). Push buttons and signatures are
not filled in (I3), so they are not read. A field is identified by its source PDF and its full name, because PDFs
added to the document may use the same names.
"""

import enum
import re
from collections.abc import Iterator
from dataclasses import dataclass

import pikepdf

from penfold.document.pdf_values import number, page_height, rectangle, text

# A field tree deeper than this is broken (or circular): the rest of it is ignored.
MAX_DEPTH = 32
# Field flags (/Ff), ISO 32000-1, tables 221, 226, 228 and 230: bit n is 1 << (n - 1).
READ_ONLY = 1 << 0
MULTILINE = 1 << 12
PASSWORD = 1 << 13
RADIO = 1 << 15
PUSH_BUTTON = 1 << 16
COMBO = 1 << 17
EDIT = 1 << 18
MULTI_SELECT = 1 << 21
COMB = 1 << 24
# Annotation flags (/F), table 165.
HIDDEN = 1 << 1
# The state of a checkbox or radio button that is not selected (12.7.4.2.3).
OFF = "Off"
# The font size in a default appearance string, as in "/Helv 12 Tf 0 g" (12.7.3.3).
FONT_SIZE = re.compile(r"(\d+(?:\.\d+)?)\s+Tf\b")
# The appearance states of a checkbox or radio button as qpdf writes them: "<< /Off 12 0 R /Yes 13 0 R >>". Names come
# with every unusual byte #-escaped, so they have no spaces.
APPEARANCE_STATE = re.compile(rb"/(\S+) (?:\d+ \d+ R|[^\s/<>\[\]()]+)")
APPEARANCE_STATES = re.compile(rb"<<((?: " + APPEARANCE_STATE.pattern + rb")*) >>")


class FieldKind(enum.Enum):
    """The fields Penfold fills in."""

    TEXT = "text"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    DROPDOWN = "dropdown"
    LIST = "list"


class Alignment(enum.IntEnum):
    """How the text of a field is aligned (/Q)."""

    LEFT = 0
    CENTER = 1
    RIGHT = 2


@dataclass(frozen=True)
class Option:
    """One choice of a dropdown or list: the value saved in the PDF and the text shown."""

    value: str
    label: str


@dataclass(frozen=True)
class Widget:
    """Where a field is drawn: one per place, on one page.

    The page is its source index (sources.py); the rectangle is in PDF points from the top left corner of the page:
    left, top, right, bottom. The state is the name a checkbox or radio button has when this widget is selected, as
    the PDF writes it (see _name).
    """

    page: int
    rectangle: tuple[float, float, float, float]
    state: str = ""


@dataclass(frozen=True)
class FormField:
    """A field that can be filled in, with the value the PDF gives it.

    The value is a text for text fields and dropdowns, the selected state (or "Off") for checkboxes and radio buttons,
    and the selected values for lists.
    """

    source_start: int
    name: str
    kind: FieldKind
    widgets: tuple[Widget, ...]
    value: str | tuple[str, ...] = ""
    options: tuple[Option, ...] = ()
    read_only: bool = False
    multiline: bool = False
    password: bool = False
    editable: bool = False
    multi_select: bool = False
    max_length: int | None = None
    comb: bool = False
    alignment: Alignment = Alignment.LEFT
    font_size: float = 0.0

    @property
    def key(self) -> tuple[int, str]:
        """What identifies the field in the document: the first source index of its PDF and its full name."""
        return self.source_start, self.name


def read_form_fields(pdf: pikepdf.Pdf, first_page: int = 0) -> list[FormField]:
    """Return the fields that can be filled in and have a visible widget on a page, in the order of the form.

    The pages are numbered from first_page: their source indexes (sources.py).
    """
    form = pdf.Root.get("/AcroForm")
    if not isinstance(form, pikepdf.Dictionary):
        return []
    fields = form.get("/Fields")
    if not isinstance(fields, pikepdf.Array):
        return []
    places = _widget_places(pdf, first_page)
    defaults = _Inherited.of_form(form)
    read = []
    for node, name, inherited in _terminal_fields(fields, defaults):
        field = _read_field(node, name, inherited, places, first_page)
        if field is not None:
            read.append(field)
    return read


@dataclass(frozen=True)
class _Inherited:
    """The entries a field takes from its ancestors, or from the form, when it does not have them (12.7.3.1)."""

    field_type: str = ""
    flags: int = 0
    value: object = None
    appearance: str = ""
    alignment: int = 0
    max_length: int | None = None

    @classmethod
    def of_form(cls, form: pikepdf.Dictionary) -> "_Inherited":
        return cls(appearance=_string(form.get("/DA")), alignment=_integer(form.get("/Q")) or 0)

    def under(self, node: pikepdf.Dictionary) -> "_Inherited":
        """Return what a child node has: its own entries, or else these."""
        field_type = node.get("/FT")
        flags = _integer(node.get("/Ff"))
        alignment = _integer(node.get("/Q"))
        max_length = _integer(node.get("/MaxLen"))
        return _Inherited(
            field_type=str(field_type) if isinstance(field_type, pikepdf.Name) else self.field_type,
            flags=self.flags if flags is None else flags,
            value=node.get("/V") if "/V" in node else self.value,
            appearance=_string(node.get("/DA")) or self.appearance,
            alignment=self.alignment if alignment is None else alignment,
            max_length=self.max_length if max_length is None else max_length,
        )


def _terminal_fields(
    kids: pikepdf.Array, inherited: _Inherited, parent_name: str = "", depth: int = 0
) -> Iterator[tuple[pikepdf.Dictionary, str, _Inherited]]:
    """Walk the field tree and give each terminal field (the one whose kids are only widgets) with its full name."""
    if depth > MAX_DEPTH:
        return
    for position in range(len(kids)):
        node = kids[position]
        if not isinstance(node, pikepdf.Dictionary):
            continue
        partial = text(node.get("/T"))
        name = f"{parent_name}.{partial}" if parent_name and partial else partial or parent_name
        node_inherited = inherited.under(node)
        children = node.get("/Kids")
        if isinstance(children, pikepdf.Array) and any(_is_field(children[index]) for index in range(len(children))):
            yield from _terminal_fields(children, node_inherited, name, depth + 1)
        elif name:
            yield node, name, node_inherited


def _is_field(node: object) -> bool:
    """Whether a kid is a field rather than a widget: fields have a name, widgets do not (12.7.3.1)."""
    return isinstance(node, pikepdf.Dictionary) and "/T" in node


def _widget_places(pdf: pikepdf.Pdf, first_page: int) -> dict[tuple[int, int], tuple[int, float]]:
    """Map each widget on a page (by object number) to the source index and height of its page."""
    places = {}
    for index, page in enumerate(pdf.pages, start=first_page):
        annots = page.obj.get("/Annots")
        if not isinstance(annots, pikepdf.Array):
            continue
        height = page_height(page)
        for position in range(len(annots)):
            annotation = annots[position]
            if isinstance(annotation, pikepdf.Dictionary) and annotation.is_indirect:
                places[annotation.objgen] = (index, height)
    return places


def _read_field(
    node: pikepdf.Dictionary,
    name: str,
    inherited: _Inherited,
    places: dict[tuple[int, int], tuple[int, float]],
    first_page: int,
) -> FormField | None:
    kind = _kind(inherited.field_type, inherited.flags)
    if kind is None:
        return None
    widgets = tuple(_widgets(node, places))
    if not widgets:
        return None
    flags = inherited.flags
    options = _options(node.get("/Opt")) if kind in {FieldKind.DROPDOWN, FieldKind.LIST} else ()
    max_length = inherited.max_length if kind is FieldKind.TEXT else None
    return FormField(
        source_start=first_page,
        name=name,
        kind=kind,
        widgets=widgets,
        value=_value(kind, inherited.value),
        options=options,
        read_only=bool(flags & READ_ONLY),
        multiline=kind is FieldKind.TEXT and bool(flags & MULTILINE),
        password=kind is FieldKind.TEXT and bool(flags & PASSWORD),
        editable=kind is FieldKind.DROPDOWN and bool(flags & EDIT),
        multi_select=kind is FieldKind.LIST and bool(flags & MULTI_SELECT),
        max_length=max_length if max_length and max_length > 0 else None,
        comb=kind is FieldKind.TEXT and bool(flags & COMB) and bool(max_length),
        alignment=_alignment(inherited.alignment),
        font_size=_font_size(inherited.appearance),
    )


def _kind(field_type: str, flags: int) -> FieldKind | None:
    if field_type == "/Tx":
        return FieldKind.TEXT
    if field_type == "/Btn":
        if flags & PUSH_BUTTON:
            return None
        return FieldKind.RADIO if flags & RADIO else FieldKind.CHECKBOX
    if field_type == "/Ch":
        return FieldKind.DROPDOWN if flags & COMBO else FieldKind.LIST
    return None  # Signatures and unknown types.


def _widgets(node: pikepdf.Dictionary, places: dict[tuple[int, int], tuple[int, float]]) -> Iterator[Widget]:
    """Give the visible widgets of a field that are on a page: its kids, or the field itself when it is one."""
    kids = node.get("/Kids")
    candidates = [kids[index] for index in range(len(kids))] if isinstance(kids, pikepdf.Array) else [node]
    for widget in candidates:
        if not isinstance(widget, pikepdf.Dictionary) or not widget.is_indirect:
            continue
        place = places.get(widget.objgen)
        if place is None or (_integer(widget.get("/F")) or 0) & HIDDEN:
            continue
        page, height = place
        area = rectangle(widget.get("/Rect"), height)
        if area is not None:
            yield Widget(page=page, rectangle=area, state=_on_state(widget))


def _on_state(widget: pikepdf.Dictionary) -> str:
    """Return the name of the state that selects a checkbox or radio button widget (its appearance other than Off).

    The names are read from the dictionary as qpdf writes it, because pikepdf cannot list keys that are not UTF-8
    (real forms have states like "Sí" in Latin-1).
    """
    appearances = widget.get("/AP")
    normal = appearances.get("/N") if isinstance(appearances, pikepdf.Dictionary) else None
    if not isinstance(normal, pikepdf.Dictionary):
        return ""
    entries = APPEARANCE_STATES.fullmatch(normal.unparse())
    names = APPEARANCE_STATE.findall(entries.group(1)) if entries else []
    return next((name.decode("ascii") for name in names if name != OFF.encode()), "")


def _name(value: pikepdf.Name) -> str:
    """Return a name as the PDF writes it, without the slash: "Yes", or "S#ed" for bytes that are not plain ASCII.

    Names are bytes, not text (7.3.5). Keeping qpdf's #-escapes compares them exactly and writes them back unchanged.
    """
    return value.unparse().decode("ascii")[1:]


def _value(kind: FieldKind, value: object) -> str | tuple[str, ...]:
    if kind in {FieldKind.CHECKBOX, FieldKind.RADIO}:
        return _name(value) if isinstance(value, pikepdf.Name) else OFF
    if kind is FieldKind.LIST:
        if isinstance(value, pikepdf.Array):
            return tuple(_string(value[index]) for index in range(len(value)) if _string(value[index]))
        return (_string(value),) if _string(value) else ()
    return _string(value)


def _options(value: object) -> tuple[Option, ...]:
    """Read /Opt: each option is a text, or a pair of the value saved and the text shown (12.7.4.4)."""
    if not isinstance(value, pikepdf.Array):
        return ()
    options = []
    for index in range(len(value)):
        option = value[index]
        if isinstance(option, pikepdf.Array) and len(option) >= 2:  # noqa: PLR2004 (value and text)
            options.append(Option(value=_string(option[0]), label=_string(option[1])))
        elif isinstance(option, pikepdf.String):
            options.append(Option(value=str(option), label=str(option)))
    return tuple(options)


def _alignment(value: int) -> Alignment:
    try:
        return Alignment(value)
    except ValueError:
        return Alignment.LEFT


def _font_size(appearance: str) -> float:
    """Return the font size of a default appearance string; 0 means that the text fits the field."""
    sizes = FONT_SIZE.findall(appearance)
    return float(sizes[-1]) if sizes else 0.0


def _string(value: object) -> str:
    """Return a PDF text string as it is (spaces kept, unlike pdf_values.text), or "" if it is not one."""
    return str(value) if isinstance(value, pikepdf.String) else ""


def _integer(value: object) -> int | None:
    read = number(value)
    return None if read is None else int(read)
