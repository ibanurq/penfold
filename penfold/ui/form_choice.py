"""Dropdowns and lists of a form on the pages.

A dropdown shows the chosen option and opens the options below it; one that lets the reader write (/Ff Edit) is a
text box with the options beside it. A list shows its options inside the field, with one or several chosen.
"""

from collections.abc import Callable

from gi.repository import Gtk, Pango

from penfold.document.forms import FieldValue, FormField, Option, Widget
from penfold.ui.form_text import X_ALIGNMENTS, font_size, size_attributes

# The arrow of a dropdown, as a share of the height of the field.
ARROW_SHARE = 0.7


def option_label(field: FormField, value: str) -> str:
    """The text shown for a value: its option's, or the value itself (a text written by the reader)."""
    return next((option.label for option in field.options if option.value == value), value)


class DropdownField:
    """One place (widget) of a dropdown field."""

    def __init__(
        self,
        field: FormField,
        widget: Widget,
        on_chosen: Callable[[FormField, FieldValue], None],
        on_typed: Callable[[FormField, str], None],
        on_left: Callable[[], None],
    ) -> None:
        """Make the dropdown for a place of a field.

        on_chosen is called with an option the reader chooses; on_typed with every change typed in a dropdown that
        lets the reader write, and on_left when it loses the focus.
        """
        self.field = field
        self.widget = widget
        self._on_chosen = on_chosen
        self._on_typed = on_typed
        self._updating = False
        self._size = 0.0
        self._arrow = Gtk.Image.new_from_icon_name("pan-down-symbolic")
        self._button = Gtk.MenuButton(popover=self._make_options(), sensitive=not field.read_only)
        self._button.set_tooltip_text(field.name)
        self._label: Gtk.Label | None = None
        self._text: Gtk.Text | None = None
        if field.editable:
            self._text = Gtk.Text(
                editable=not field.read_only,
                hexpand=True,
                propagate_text_width=False,
                width_chars=0,
                xalign=X_ALIGNMENTS[field.alignment],
                enable_undo=False,  # Undo is the document's (window._undo_or_redo).
            )
            self._text.connect("changed", lambda text: self._typed(text.get_text()))
            focus = Gtk.EventControllerFocus()
            focus.connect("leave", lambda _controller: on_left())
            self._text.add_controller(focus)
            self._button.set_child(self._arrow)
            self._view: Gtk.Widget = Gtk.Box()
            self._view.append(self._text)
            self._view.append(self._button)
        else:
            self._label = Gtk.Label(
                hexpand=True, xalign=X_ALIGNMENTS[field.alignment], ellipsize=Pango.EllipsizeMode.END
            )
            content = Gtk.Box()
            content.append(self._label)
            content.append(self._arrow)
            self._button.set_child(content)
            self._view = self._button
        self._view.add_css_class("form-field")
        self._view.add_css_class("dropdown")
        if field.read_only:
            self._view.add_css_class("read-only")

    @property
    def view(self) -> Gtk.Widget:
        """The widget shown on the page."""
        return self._view

    @property
    def text(self) -> str:
        """What the dropdown shows."""
        if self._text is not None:
            return self._text.get_text()
        assert self._label is not None
        return self._label.get_text()

    def show_value(self, value: FieldValue) -> None:
        """Show the option chosen (or the text written)."""
        shown = option_label(self.field, value) if isinstance(value, str) else ""
        if shown == self.text:
            return
        self._updating = True
        if self._text is not None:
            self._text.set_text(shown)
        elif self._label is not None:
            self._label.set_text(shown)
        self._updating = False

    def set_zoom(self, zoom: float) -> None:
        """Draw the text and the arrow at the size of the field for this zoom."""
        size = font_size(self.field, self.widget) * zoom
        if size == self._size:
            return
        self._size = size
        shown = self._text or self._label
        assert shown is not None
        shown.set_attributes(size_attributes(size))
        height = (self.widget.rectangle[3] - self.widget.rectangle[1]) * zoom
        self._arrow.set_pixel_size(max(1, round(height * ARROW_SHARE)))

    def choose(self, option: Option) -> None:
        """Choose an option, as a click on it in the dropdown does."""
        self._button.popdown()
        self._on_chosen(self.field, option.value)

    def _make_options(self) -> Gtk.Popover:
        options = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        options.add_css_class("navigation-sidebar")
        for option in self.field.options:
            options.append(Gtk.Label(label=option.label, xalign=0))
        options.connect("row-activated", lambda _list, row: self.choose(self.field.options[row.get_index()]))
        scrolled = Gtk.ScrolledWindow(
            child=options, hscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_height=True, max_content_height=320
        )
        return Gtk.Popover(child=scrolled, has_arrow=False, halign=Gtk.Align.START)

    def _typed(self, text: str) -> None:
        if not self._updating:
            self._on_typed(self.field, text)


class ListField:
    """One place (widget) of a list field: its options inside the field, with one or several chosen."""

    def __init__(self, field: FormField, widget: Widget, on_chosen: Callable[[FormField, FieldValue], None]) -> None:
        """Make the list for a place of a field; on_chosen is called with the values the reader chooses."""
        self.field = field
        self.widget = widget
        self._on_chosen = on_chosen
        self._updating = False
        self._size = 0.0
        mode = Gtk.SelectionMode.MULTIPLE if field.multi_select else Gtk.SelectionMode.SINGLE
        self._list = Gtk.ListBox(selection_mode=mode, sensitive=not field.read_only)
        self._labels = [Gtk.Label(label=option.label, xalign=0) for option in field.options]
        for label in self._labels:
            self._list.append(label)
        self._list.connect("selected-rows-changed", lambda _list: self._chosen())
        self._view = Gtk.ScrolledWindow(child=self._list, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self._view.set_tooltip_text(field.name)
        self._view.add_css_class("form-field")
        self._view.add_css_class("list")
        if field.read_only:
            self._view.add_css_class("read-only")

    @property
    def view(self) -> Gtk.Widget:
        """The widget shown on the page."""
        return self._view

    @property
    def chosen(self) -> tuple[str, ...]:
        """The values of the options chosen, in the order of the list."""
        rows = sorted(row.get_index() for row in self._list.get_selected_rows())
        return tuple(self.field.options[index].value for index in rows)

    def show_value(self, value: FieldValue) -> None:
        """Choose the options of the value."""
        values = value if isinstance(value, tuple) else (value,)
        if values == self.chosen:
            return
        self._updating = True
        self._list.unselect_all()
        for index, option in enumerate(self.field.options):
            row = self._list.get_row_at_index(index)
            if option.value in values and row is not None:
                self._list.select_row(row)
        self._updating = False

    def set_zoom(self, zoom: float) -> None:
        """Draw the options at the size of the field for this zoom."""
        size = font_size(self.field, self.widget) * zoom
        if size != self._size:
            self._size = size
            for label in self._labels:
                label.set_attributes(size_attributes(size))

    def choose(self, values: tuple[str, ...]) -> None:
        """Choose these options, as clicks in the list do."""
        self.show_value(values)
        self._on_chosen(self.field, self.chosen)

    def _chosen(self) -> None:
        if not self._updating:
            self._on_chosen(self.field, self.chosen)
