"""Writing the values filled in into the form of a PDF, so that it stays editable (I5, I7), or flattening it (I6).

Only the fields that were changed are written. Each gets its value and, where qpdf can draw it, a new appearance,
so every viewer shows it; the other fields keep their appearance as it was. Where qpdf cannot draw a value well
(several lines, lists, letters its fonts lack), the form asks viewers to draw it (/NeedAppearances), as 0.6 did.
"""

from typing import TypeGuard

import pikepdf

from penfold.document.forms import (
    OFF,
    FieldKind,
    FieldValue,
    FormField,
    field_dictionaries,
    on_state,
    widget_dictionaries,
)

# The encoding of the standard fonts qpdf draws text with (WinAnsiEncoding is close to it).
DRAWN_ENCODING = "cp1252"
# Kinds whose appearance qpdf draws: one line of text.
DRAWN_KINDS = frozenset({FieldKind.TEXT, FieldKind.DROPDOWN})


def fill_in(pdf: pikepdf.Pdf, values: list[tuple[FormField, FieldValue]]) -> int:
    """Write values into the fields of a PDF (the source PDF of those fields); return how many could not be written.

    A field that fails does not stop the others (I5).
    """
    dictionaries = field_dictionaries(pdf)
    failed = 0
    written: list[pikepdf.Dictionary] = []
    viewers_draw = False
    for field, value in values:
        dictionary = dictionaries.get(field.name)
        try:
            if dictionary is None:
                raise _FieldError(field.name)
            _write_value(dictionary, field, value)
        except (_FieldError, pikepdf.PdfError, ValueError):
            failed += 1
            continue
        written.append(dictionary)
        viewers_draw = viewers_draw or not _drawn_well(field, value)
    if any(_kind_of(dictionary) in {"/Tx", "/Ch"} for dictionary in written):
        _draw_appearances(pdf, written, viewers_draw=viewers_draw)
    return failed


class _FieldError(Exception):
    """A field of the document is not in its PDF any more."""


def _write_value(dictionary: pikepdf.Dictionary, field: FormField, value: FieldValue) -> None:
    match field.kind:
        case FieldKind.TEXT:
            dictionary.V = pikepdf.String(_text(value))
        case FieldKind.DROPDOWN:
            dictionary.V = pikepdf.String(_text(value))
            if "/I" in dictionary:
                del dictionary.I
        case FieldKind.LIST:
            chosen = value if isinstance(value, tuple) else (value,)
            values = [pikepdf.String(item) for item in chosen]
            dictionary.V = values[0] if len(values) == 1 else pikepdf.Array(values)
            indexes = [index for index, option in enumerate(field.options) if option.value in chosen]
            dictionary.I = pikepdf.Array(indexes)
        case FieldKind.CHECKBOX | FieldKind.RADIO:
            state = _text(value)
            dictionary.V = _name(state)
            for widget in widget_dictionaries(dictionary):
                widget.AS = _name(state if state != OFF and on_state(widget) == state else OFF)


def _text(value: FieldValue) -> str:
    if not isinstance(value, str):
        message = f"{value!r} is not a text"
        raise ValueError(message)
    return value


def _name(state: str) -> pikepdf.Object:
    """A name from a state as forms.py keeps it, with qpdf's #-escapes, so its bytes are written back unchanged."""
    return pikepdf.Object.parse(b"/" + state.encode("ascii"))


def _kind_of(dictionary: pikepdf.Dictionary) -> str:
    node: pikepdf.Object | None = dictionary
    while isinstance(node, pikepdf.Dictionary):
        if "/FT" in node:
            return str(node.FT)
        node = node.get("/Parent")
    return ""


def _drawn_well(field: FormField, value: FieldValue) -> bool:
    """Whether qpdf draws this value as viewers would: one line, in the encoding of its fonts."""
    if field.kind not in DRAWN_KINDS:
        return field.kind is not FieldKind.LIST
    if field.multiline or field.comb or not isinstance(value, str):
        return False
    try:
        value.encode(DRAWN_ENCODING)
    except UnicodeEncodeError:
        return False
    return True


def _draw_appearances(pdf: pikepdf.Pdf, written: list[pikepdf.Dictionary], *, viewers_draw: bool) -> None:
    """Draw the appearance of the fields written, leaving the others as they were.

    qpdf draws every text and choice field of the form at once, rewriting their appearance streams in place. The
    others are taken away from their appearance while it draws, so it draws new ones that are then dropped, and get
    their own back untouched.
    """
    form = pdf.Root.AcroForm
    asked_before = bool(form.get("/NeedAppearances"))
    touched = {widget.objgen for dictionary in written for widget in widget_dictionaries(dictionary)}
    kept = [(widget, widget.get("/AP"), widget.get("/AS")) for widget in _widgets(pdf) if widget.objgen not in touched]
    for widget, appearance, _state in kept:
        if appearance is not None:
            del widget.AP
    form.NeedAppearances = True
    pdf.generate_appearance_streams()
    for widget, appearance, state in kept:
        _restore(widget, "/AP", appearance)
        _restore(widget, "/AS", state)
    if asked_before or viewers_draw:
        form.NeedAppearances = True
    elif "/NeedAppearances" in form:
        del form.NeedAppearances


def _widgets(pdf: pikepdf.Pdf) -> list[pikepdf.Dictionary]:
    widgets = []
    for page in pdf.pages:
        annots = page.obj.get("/Annots")
        if not isinstance(annots, pikepdf.Array):
            continue
        for index in range(len(annots)):
            annotation = annots[index]
            if _is_widget(annotation):
                widgets.append(annotation)
    return widgets


def _restore(widget: pikepdf.Dictionary, key: str, value: pikepdf.Object | None) -> None:
    if value is None:
        if key in widget:
            del widget[key]
    else:
        widget[key] = value


def flatten_form(pdf: pikepdf.Pdf) -> None:
    """Draw every form field as fixed page content and remove the form (I6); the other annotations stay as they are.

    qpdf flattens every annotation with an appearance, so the others are set aside while it works. Hidden fields are
    dropped, as viewers do not show them.
    """
    set_aside = []
    for page in pdf.pages:
        annots = page.obj.get("/Annots")
        if not isinstance(annots, pikepdf.Array):
            continue
        items = [annots[index] for index in range(len(annots))]
        widgets = [item for item in items if _is_widget(item)]
        set_aside.append((page, [item for item in items if not _is_widget(item)]))
        page.obj.Annots = pdf.make_indirect(pikepdf.Array(widgets))
    pdf.flatten_annotations("all")
    for page, others in set_aside:
        if others:
            page.obj.Annots = pdf.make_indirect(pikepdf.Array(others))
        elif "/Annots" in page.obj:
            del page.obj.Annots
    if "/AcroForm" in pdf.Root:
        del pdf.Root.AcroForm


def _is_widget(annotation: object) -> TypeGuard[pikepdf.Dictionary]:
    return isinstance(annotation, pikepdf.Dictionary) and annotation.get("/Subtype") == pikepdf.Name.Widget
