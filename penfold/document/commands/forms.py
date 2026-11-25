"""Form edits: filling in a field, an edit that can be undone like any other."""

from penfold.document.document import OpenDocument
from penfold.document.forms import FieldKind, FieldValue, FormField
from penfold.document.history import Change


class SetFieldValue:
    """Give a form field a new value; all its widgets show it, since they are one field."""

    changes = Change.FORM

    def __init__(self, document: OpenDocument, field: FormField, value: FieldValue) -> None:
        """Prepare the change of a field of the document.

        Raises:
            ValueError: the field is not one of the document's, or the value does not suit its kind.
        """
        if field not in document.form_fields:
            message = f"{field.name} is not a field of the document"
            raise ValueError(message)
        _check_value(field, value)
        self._document = document
        self.field = field
        self.value = value
        self._before = document.field_value(field)

    def apply(self) -> None:
        """Give the field its new value."""
        self._document.set_field_value(self.field, self.value)

    def revert(self) -> None:
        """Give the field back the value it had."""
        self._document.set_field_value(self.field, self._before)

    def retype(self, value: FieldValue) -> None:
        """Change the new value while it is being typed; use it through OpenDocument.amend, so it stays one edit.

        Raises:
            ValueError: the value does not suit the kind of field.
        """
        _check_value(self.field, value)
        self.value = value
        self.apply()


def _check_value(field: FormField, value: FieldValue) -> None:
    if isinstance(value, tuple) is not (field.kind is FieldKind.LIST):
        message = f"{value!r} is not a value for the {field.kind.value} field {field.name}"
        raise ValueError(message)
