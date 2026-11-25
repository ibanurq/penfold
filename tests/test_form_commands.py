"""Filling in form fields as edits that can be undone."""

from pathlib import Path

import pytest

from penfold.document.commands.forms import SetFieldValue
from penfold.document.document import OpenDocument
from penfold.document.forms import FormField
from tests.test_forms import build_form


@pytest.fixture
def document(tmp_path: Path) -> OpenDocument:
    return OpenDocument.open(build_form(tmp_path / "form.pdf"))


def field(document: OpenDocument, name: str) -> FormField:
    return next(item for item in document.form_fields if item.name == name)


def test_a_value_is_filled_in_and_undone(document: OpenDocument) -> None:
    notes = field(document, "notes")
    document.execute(SetFieldValue(document, notes, "Hello"))
    assert (document.field_value(notes), document.is_modified) == ("Hello", True)
    document.undo()
    assert (document.field_value(notes), document.is_modified) == ("", False)
    document.redo()
    assert document.field_value(notes) == "Hello"


def test_only_values_that_differ_from_the_pdf_are_filled_in(document: OpenDocument) -> None:
    name = field(document, "name")
    document.execute(SetFieldValue(document, name, "Eva"))
    assert document.filled_fields == {name.key: "Eva"}
    document.execute(SetFieldValue(document, name, "Ana "))
    assert document.filled_fields == {}


def test_typing_is_one_edit(document: OpenDocument) -> None:
    notes = field(document, "notes")
    typing = SetFieldValue(document, notes, "H")
    document.execute(typing)
    assert document.amend(typing, lambda: typing.retype("Hi"))
    assert document.field_value(notes) == "Hi"
    document.undo()
    assert (document.field_value(notes), document.can_undo) == ("", False)


def test_typing_after_saving_or_another_edit_is_a_new_edit(document: OpenDocument) -> None:
    notes, pin = field(document, "notes"), field(document, "pin")
    typing = SetFieldValue(document, notes, "H")
    document.execute(typing)
    document.mark_saved(document.save_plan())
    assert not document.amend(typing, lambda: typing.retype("Hi"))
    document.execute(SetFieldValue(document, pin, "1234"))
    assert not document.amend(typing, lambda: typing.retype("Hi"))
    assert document.field_value(notes) == "H"


def test_values_must_suit_the_field(document: OpenDocument) -> None:
    with pytest.raises(ValueError, match="pets"):
        SetFieldValue(document, field(document, "pets"), "Cat")
    with pytest.raises(ValueError, match="notes"):
        SetFieldValue(document, field(document, "notes"), ("a",))
