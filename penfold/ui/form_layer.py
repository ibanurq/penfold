"""Form fields on the pages: a text box over each text field, where the reader fills it in (I1, I2).

The fields are child widgets of the document view, placed over their pages for the current zoom and scroll. Only
the pages that can be seen get their widgets, so a long form costs nothing while it is off screen. Every change is an
edit that can be undone; typing in one field is a single edit (SetFieldValue.retype).
"""

from collections.abc import Callable
from dataclasses import dataclass

from gi.repository import Graphene, Gsk, Gtk, Pango

from penfold.document.commands.forms import SetFieldValue
from penfold.document.document import OpenDocument
from penfold.document.forms import Alignment, FieldKind, FieldValue, FormField, Widget
from penfold.rendering.layout import PageLayout

# Text fields with an automatic font size (0 in the PDF): a share of the height of a one-line field, and a fixed size
# for fields of several lines, in points, as most viewers do.
AUTOMATIC_SIZE_SHARE = 0.65
AUTOMATIC_MULTILINE_SIZE = 10.0
MIN_FONT_SIZE = 4.0
MAX_AUTOMATIC_SIZE = 12.0
X_ALIGNMENTS = {Alignment.LEFT: 0.0, Alignment.CENTER: 0.5, Alignment.RIGHT: 1.0}
JUSTIFICATIONS = {
    Alignment.LEFT: Gtk.Justification.LEFT,
    Alignment.CENTER: Gtk.Justification.CENTER,
    Alignment.RIGHT: Gtk.Justification.RIGHT,
}


@dataclass(frozen=True)
class ShownBox:
    """Where a page is shown in the view, in logical pixels from the view's top left corner."""

    position: int
    x: float
    y: float


def font_size(field: FormField, widget: Widget) -> float:
    """The size of the text of a field, in points: the PDF's, or one that fits the field."""
    if field.font_size > 0:
        return field.font_size
    if field.multiline:
        return AUTOMATIC_MULTILINE_SIZE
    height = widget.rectangle[3] - widget.rectangle[1]
    return min(MAX_AUTOMATIC_SIZE, max(MIN_FONT_SIZE, height * AUTOMATIC_SIZE_SHARE))


class FieldEditor:
    """The widget that fills in one place (widget) of a text field."""

    def __init__(
        self,
        field: FormField,
        widget: Widget,
        on_typed: Callable[["FieldEditor", str], None],
        on_left: Callable[[], None],
    ) -> None:
        """Make the text box for a place of a field.

        on_typed is called with every change the reader types, and on_left when the box loses the focus.
        """
        self.field = field
        self.widget = widget
        self._on_typed = on_typed
        self._updating = False
        self._size = 0.0
        self.view: Gtk.Text | Gtk.TextView
        if field.multiline:
            self.view = self._make_text_view()
        else:
            self.view = self._make_text()
        self.view.add_css_class("form-field")
        self.view.set_tooltip_text(field.name)
        if field.read_only:
            self.view.add_css_class("read-only")
        focus = Gtk.EventControllerFocus()
        focus.connect("leave", lambda _controller: on_left())
        self.view.add_controller(focus)

    def _make_text(self) -> Gtk.Text:
        text = Gtk.Text(
            editable=not self.field.read_only,
            visibility=not self.field.password,
            max_length=self.field.max_length or 0,
            xalign=X_ALIGNMENTS[self.field.alignment],
            propagate_text_width=False,
            width_chars=0,
            enable_undo=False,  # Undo is the document's (window._undo_or_redo).
        )
        text.connect("changed", lambda _text: self._typed(text.get_text()))
        return text

    def _make_text_view(self) -> Gtk.TextView:
        view = Gtk.TextView(
            editable=not self.field.read_only,
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            justification=JUSTIFICATIONS[self.field.alignment],
            accepts_tab=False,
        )
        buffer = view.get_buffer()
        buffer.set_enable_undo(False)  # Undo is the document's (window._undo_or_redo).
        self._size_tag = buffer.create_tag("size")
        buffer.connect("insert-text", self._limit_length)
        buffer.connect("changed", lambda _buffer: self._buffer_changed(view))
        return view

    def show_value(self, value: FieldValue) -> None:
        """Show the value of the field, unless it is already there (the reader's own typing)."""
        text = value if isinstance(value, str) else ""
        if text == self.text:
            return
        self._updating = True
        if isinstance(self.view, Gtk.Text):
            self.view.set_text(text)
        else:
            self.view.get_buffer().set_text(text)
        self._updating = False

    @property
    def text(self) -> str:
        """The text in the box."""
        if isinstance(self.view, Gtk.Text):
            return self.view.get_text()
        buffer = self.view.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), include_hidden_chars=True)

    def set_zoom(self, zoom: float) -> None:
        """Draw the text at the size of the field for this zoom."""
        size = font_size(self.field, self.widget) * zoom
        if size == self._size:
            return
        self._size = size
        if isinstance(self.view, Gtk.Text):
            attributes = Pango.AttrList()
            attributes.insert(Pango.attr_size_new_absolute(round(size * Pango.SCALE)))
            self.view.set_attributes(attributes)
        else:
            self._size_tag.set_property("size-points", size * 72 / 96)
            self._tag_all(self.view.get_buffer())

    def _typed(self, text: str) -> None:
        if not self._updating:
            self._on_typed(self, text)

    def _buffer_changed(self, view: Gtk.TextView) -> None:
        self._tag_all(view.get_buffer())
        self._typed(self.text)

    def _tag_all(self, buffer: Gtk.TextBuffer) -> None:
        buffer.apply_tag(self._size_tag, buffer.get_start_iter(), buffer.get_end_iter())

    def _limit_length(self, buffer: Gtk.TextBuffer, location: Gtk.TextIter, text: str, _length: int) -> None:
        """Keep a field of several lines within its maximum length, as Gtk.Text does for one line."""
        limit = self.field.max_length
        if limit is None or self._updating:
            return
        room = limit - buffer.get_char_count()
        if len(text) > room:
            buffer.stop_emission_by_name("insert-text")
            if room > 0:
                buffer.insert(location, text[:room])


class FormLayer:
    """The field widgets of the pages that can be seen, as children of the document view."""

    def __init__(self, view: Gtk.Widget) -> None:
        """Prepare the fields of a document view; set_document gives them a document."""
        self._view = view
        self._document: OpenDocument | None = None
        self._layout: PageLayout | None = None
        self._places: dict[int, list[tuple[FormField, Widget]]] = {}
        self._editors: dict[tuple[tuple[int, str], int], FieldEditor] = {}
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
            if field.kind is not FieldKind.TEXT:
                continue
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

    def _editor(self, field: FormField, widget: Widget) -> FieldEditor:
        key = (field.key, field.widgets.index(widget))
        editor = self._editors.get(key)
        if editor is None:
            assert self._document is not None
            editor = FieldEditor(field, widget, self._typed, self._end_typing)
            editor.show_value(self._document.field_value(field))
            editor.view.set_parent(self._view)
            self._editors[key] = editor
        return editor

    def _end_typing(self) -> None:
        """Leaving a field ends the edit being typed: typing in it again is a new one."""
        self._typing = None

    def _typed(self, editor: FieldEditor, text: str) -> None:
        """Make the typing an edit, or part of the one being typed in the same field."""
        document = self._document
        if document is None:
            return
        typing = self._typing
        if typing is not None and typing.field == editor.field and document.amend(typing, lambda: typing.retype(text)):
            return
        self._typing = SetFieldValue(document, editor.field, text)
        document.execute(self._typing)


def _contains(widget: Gtk.Widget, focus: Gtk.Widget | None) -> bool:
    while focus is not None:
        if focus is widget:
            return True
        focus = focus.get_parent()
    return False
