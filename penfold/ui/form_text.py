"""Text fields of a form on the pages: a text box over each place of the field, and the size of its text."""

from collections.abc import Callable

from gi.repository import Gtk, Pango

from penfold.document.forms import Alignment, FieldValue, FormField, Widget

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


def font_size(field: FormField, widget: Widget) -> float:
    """The size of the text of a field, in points: the PDF's, or one that fits the field."""
    if field.font_size > 0:
        return field.font_size
    if field.multiline:
        return AUTOMATIC_MULTILINE_SIZE
    height = widget.rectangle[3] - widget.rectangle[1]
    return min(MAX_AUTOMATIC_SIZE, max(MIN_FONT_SIZE, height * AUTOMATIC_SIZE_SHARE))


def size_attributes(size: float) -> Pango.AttrList:
    """Text attributes for a size in logical pixels (points at the zoom of the page)."""
    attributes = Pango.AttrList()
    attributes.insert(Pango.attr_size_new_absolute(round(size * Pango.SCALE)))
    return attributes


class FieldEditor:
    """The widget that fills in one place (widget) of a text field."""

    def __init__(
        self,
        field: FormField,
        widget: Widget,
        on_typed: Callable[[FormField, str], None],
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
            self.view.set_attributes(size_attributes(size))
        else:
            self._size_tag.set_property("size-points", size * 72 / 96)
            self._tag_all(self.view.get_buffer())

    def _typed(self, text: str) -> None:
        if not self._updating:
            self._on_typed(self.field, text)

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
