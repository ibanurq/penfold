"""Checkboxes and radio buttons of a form on the pages (I1): a box that shows a black tick or dot, as in 0.6.

They are drawn here instead of with Gtk.CheckButton so they take exactly the size of the field, however small, at
any zoom.
"""

import functools
from collections.abc import Callable

from gi.repository import Gdk, GObject, Graphene, Gsk, Gtk

from penfold.document.forms import OFF, FieldKind, FieldValue, FormField, Widget

# The mark takes this share of the shorter side of the field; the tick is drawn with a line of this share of it.
MARK_SHARE = 0.7
TICK_WIDTH_SHARE = 0.17


@functools.cache
def _black() -> Gdk.RGBA:
    black = Gdk.RGBA()
    black.parse("black")
    return black


class ToggleField(Gtk.Widget):
    """One place (widget) of a checkbox or radio button field: selected when the field has its state."""

    __gtype_name__ = "PenfoldToggleField"

    def __init__(self, field: FormField, widget: Widget, on_chosen: Callable[[FormField, FieldValue], None]) -> None:
        """Make the box for a place of a field; on_chosen is called with the value the reader gives the field."""
        self.is_radio = field.kind is FieldKind.RADIO
        role = Gtk.AccessibleRole.RADIO if self.is_radio else Gtk.AccessibleRole.CHECKBOX
        super().__init__(focusable=True, accessible_role=role)
        self.field = field
        self.widget = widget
        self._on_chosen = on_chosen
        self._selected = False
        self.add_css_class("form-field")
        self.add_css_class("radio" if self.is_radio else "checkbox")
        if field.read_only:
            self.add_css_class("read-only")
        else:
            self.set_cursor_from_name("pointer")
        self.set_tooltip_text(field.name)
        self.update_property([Gtk.AccessibleProperty.LABEL], [field.name])
        click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
        click.connect("pressed", self._on_pressed)
        click.connect("released", lambda _gesture, _n, _x, _y: self.choose())
        self.add_controller(click)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key_pressed)
        self.add_controller(keys)

    @property
    def view(self) -> Gtk.Widget:
        """The widget shown on the page: this one."""
        return self

    @property
    def selected(self) -> bool:
        """Whether this place shows the mark."""
        return self._selected

    def show_value(self, value: FieldValue) -> None:
        """Show the mark if the field has the state of this place."""
        selected = value != OFF and value == self.widget.state
        if selected != self._selected:
            self._selected = selected
            # PyGObject passes the state as a GValue; GTK reads a tristate as an int.
            checked = int(Gtk.AccessibleTristate.TRUE if selected else Gtk.AccessibleTristate.FALSE)
            self.update_state([Gtk.AccessibleState.CHECKED], [GObject.Value(GObject.TYPE_INT, checked)])
            self.queue_draw()

    def set_zoom(self, _zoom: float) -> None:
        """The mark follows the size of the box, so the zoom needs nothing else."""

    def choose(self) -> None:
        """Do what a click does: a checkbox changes; a radio button is chosen (choosing it again does nothing)."""
        if self.field.read_only or (self.is_radio and self._selected):
            return
        self._on_chosen(self.field, OFF if self._selected else self.widget.state)

    def do_snapshot(self, snapshot: Gtk.Snapshot) -> None:
        """Draw the tick or the dot in the middle of the box (the box itself is the CSS background)."""
        if not self._selected:
            return
        width, height = self.get_width(), self.get_height()
        side = min(width, height) * MARK_SHARE
        left, top = (width - side) / 2, (height - side) / 2
        if self.is_radio:
            dot = Gsk.RoundedRect()
            dot.init_from_rect(Graphene.Rect().init(left, top, side, side), side / 2)
            snapshot.push_rounded_clip(dot)
            snapshot.append_color(_black(), dot.bounds)
            snapshot.pop()
            return
        builder = Gsk.PathBuilder()
        builder.move_to(left, top + side * 0.55)
        builder.line_to(left + side * 0.38, top + side * 0.9)
        builder.line_to(left + side, top + side * 0.1)
        stroke = Gsk.Stroke.new(max(1.0, side * TICK_WIDTH_SHARE))
        stroke.set_line_cap(Gsk.LineCap.ROUND)
        stroke.set_line_join(Gsk.LineJoin.ROUND)
        snapshot.append_stroke(builder.to_path(), stroke, _black())

    def _on_pressed(self, gesture: Gtk.GestureClick, _n_press: int, _x: float, _y: float) -> None:
        """The press is the field's, not the start of a text selection on the page."""
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        self.grab_focus()

    def _on_key_pressed(
        self, _controller: Gtk.EventControllerKey, keyval: int, _keycode: int, _state: Gdk.ModifierType
    ) -> bool:
        if keyval in {Gdk.KEY_space, Gdk.KEY_KP_Space}:
            self.choose()
            return True
        return False
