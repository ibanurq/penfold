"""Form fields on the pages: a widget over each field, where the reader fills it in (I1, I2).

The fields are child widgets of the document view, placed over their pages for the current zoom and scroll. Only
the pages that can be seen get their widgets, so a long form costs nothing while it is off screen. Every change is an
edit that can be undone; typing in one field is a single edit (SetFieldValue.retype).
"""

from dataclasses import dataclass
from typing import Protocol

from gi.repository import Graphene, Gsk, Gtk

from penfold.document.commands.forms import SetFieldValue
from penfold.document.document import OpenDocument
from penfold.document.forms import FieldKind, FieldValue, FormField, Widget
from penfold.rendering.layout import PageLayout
from penfold.ui.form_choice import DropdownField, ListField
from penfold.ui.form_text import FieldEditor
from penfold.ui.form_toggle import ToggleField


class FieldWidget(Protocol):
    """What the layer needs of the widget of one place of a field, whatever its kind."""

    field: FormField
    widget: Widget

    @property
    def view(self) -> Gtk.Widget:
        """The widget shown over the page."""
        ...

    def show_value(self, value: FieldValue) -> None:
        """Show the value the field has now."""
        ...

    def set_zoom(self, zoom: float) -> None:
        """Fit what it draws to the zoom."""
        ...


@dataclass(frozen=True)
class ShownBox:
    """Where a page is shown in the view, in logical pixels from the view's top left corner."""

    position: int
    x: float
    y: float


class FormLayer:
    """The field widgets of the pages that can be seen, as children of the document view."""

    def __init__(self, view: Gtk.Widget) -> None:
        """Prepare the fields of a document view; set_document gives them a document."""
        self._view = view
        self._document: OpenDocument | None = None
        self._layout: PageLayout | None = None
        self._places: dict[int, list[tuple[FormField, Widget]]] = {}
        self._editors: dict[tuple[tuple[int, str], int], FieldWidget] = {}
        self._typing: SetFieldValue | None = None

    def set_document(self, document: OpenDocument, layout: PageLayout) -> None:
        """Show the fields of another document."""
        self.clear()
        self._document = document
        self.pages_changed(layout)

    def pages_changed(self, layout: PageLayout) -> None:
        """Take the pages as they are now: added pages may bring fields, and pages may be shown elsewhere."""
        self._layout = layout
        self._places = {}
        if self._document is None:
            return
        for field in self._document.form_fields:
            for widget in field.widgets:
                self._places.setdefault(widget.page, []).append((field, widget))

    def form_changed(self) -> None:
        """Show the values after an edit, an undo or a redo."""
        if self._document is None:
            return
        for editor in self._editors.values():
            editor.show_value(self._document.field_value(editor.field))
        if self._typing is not None and self._document.last_edit is not self._typing:
            self._typing = None

    def clear(self) -> None:
        """Take all the field widgets away."""
        for editor in self._editors.values():
            editor.view.unparent()
        self._editors = {}
        self._typing = None

    def allocate(self, boxes: list[ShownBox], zoom: float) -> None:
        """Place the widgets of the fields on these pages (the visible ones), and drop the others."""
        if self._document is None or self._layout is None:
            return
        wanted = set()
        for box in boxes:
            shown = self._layout[box.position]
            for field, widget in self._places.get(shown.source, []):
                left, top, right, bottom = shown.from_source(widget.rectangle)
                editor = self._editor(field, widget)
                wanted.add(id(editor))
                editor.set_zoom(zoom)
                width, height = max(1, round((right - left) * zoom)), max(1, round((bottom - top) * zoom))
                point = Graphene.Point().init(round(box.x + left * zoom), round(box.y + top * zoom))
                # GTK asks for a measure before every allocation; the field's own size is what counts.
                editor.view.measure(Gtk.Orientation.HORIZONTAL, -1)
                editor.view.measure(Gtk.Orientation.VERTICAL, width)
                editor.view.allocate(width, height, -1, Gsk.Transform().translate(point))
        root = self._view.get_root()
        focus = root.get_focus() if isinstance(root, Gtk.Window) else None
        for key, editor in list(self._editors.items()):
            if id(editor) not in wanted and not _contains(editor.view, focus):
                editor.view.unparent()
                del self._editors[key]

    def snapshot(self, snapshot: Gtk.Snapshot) -> None:
        """Draw the field widgets over the pages."""
        for editor in self._editors.values():
            self._view.snapshot_child(editor.view, snapshot)

    def _editor(self, field: FormField, widget: Widget) -> FieldWidget:
        key = (field.key, field.widgets.index(widget))
        editor = self._editors.get(key)
        if editor is None:
            assert self._document is not None
            editor = self._make_editor(field, widget)
            editor.show_value(self._document.field_value(field))
            editor.view.set_parent(self._view)
            self._editors[key] = editor
        return editor

    def _make_editor(self, field: FormField, widget: Widget) -> FieldWidget:
        match field.kind:
            case FieldKind.TEXT:
                return FieldEditor(field, widget, self._typed, self._end_typing)
            case FieldKind.DROPDOWN:
                return DropdownField(field, widget, self._chosen, self._typed, self._end_typing)
            case FieldKind.LIST:
                return ListField(field, widget, self._chosen)
            case _:
                return ToggleField(field, widget, self._chosen)

    def _chosen(self, field: FormField, value: FieldValue) -> None:
        """Make a choice (a click on a checkbox…) an edit of its own."""
        if self._document is not None:
            self._typing = None
            self._document.execute(SetFieldValue(self._document, field, value))

    def _end_typing(self) -> None:
        """Leaving a field ends the edit being typed: typing in it again is a new one."""
        self._typing = None

    def _typed(self, field: FormField, text: str) -> None:
        """Make the typing an edit, or part of the one being typed in the same field."""
        document = self._document
        if document is None:
            return
        typing = self._typing
        if typing is not None and typing.field == field and document.amend(typing, lambda: typing.retype(text)):
            return
        self._typing = SetFieldValue(document, field, text)
        document.execute(self._typing)


def _contains(widget: Gtk.Widget, focus: Gtk.Widget | None) -> bool:
    while focus is not None:
        if focus is widget:
            return True
        focus = focus.get_parent()
    return False
