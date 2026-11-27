"""The Format panel of an annotation: a popover beside it, with its colours and the rows of its type.

Every change shows at once, without an Apply button; Esc or a click outside closes it. Only the rows that suit the type
are shown:

- highlights, underlines and strikethroughs: opacity;
- rectangles and circles: line width, line style, fill and opacity;
- arrows: line width, line style, arrowheads and opacity;
- freehand drawings: line width and opacity;
- text boxes: letter size, background and border (their colours are those of the background and the border).

A value read from another program that is not one of the options (a line of 3 points) is shown as one more option,
chosen, and kept while another is not chosen.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from gettext import gettext as _

from gi.repository import Adw, Gio, GLib, Gtk

from penfold.document.annotations import TEXT_MARKUPS, Annotation, Kind, LineEnds, Style
from penfold.ui.palette import ANNOTATION_COLORS, color_circle, color_to_hex, hex_to_color

# The options of the rows: line widths and letter sizes in points.
LINE_WIDTHS = (1.0, 2.0, 4.0)
FONT_SIZES = (9.0, 11.0, 14.0, 18.0)
LINE_ENDS = (LineEnds.END, LineEnds.BOTH, LineEnds.NONE)
# The opacity slider, in per cent.
LEAST_OPACITY = 10
OPACITY_STEP = 5
OPACITY_WIDTH = 150
SHAPES = frozenset({Kind.RECTANGLE, Kind.CIRCLE})
FORMATTED = frozenset({*TEXT_MARKUPS, *SHAPES, Kind.ARROW, Kind.FREEHAND, Kind.TEXT_BOX})
# No colour circle is ringed for a colour that is not one of the palette's.
NO_COLOR = ""


def has_format(kind: Kind) -> bool:
    """Whether annotations of a type have a Format panel (comments only have their colours)."""
    return kind in FORMATTED


class FormatPopover(Gtk.Popover):
    """The Format panel of one annotation; on_change gets the annotation as it is after each change."""

    __gtype_name__ = "PenfoldFormatPopover"

    def __init__(self, annotation: Annotation, on_change: Callable[[Annotation], object]) -> None:
        """Create the panel for an annotation; set its parent and what it points at, then popup."""
        super().__init__(position=Gtk.PositionType.RIGHT)
        self.add_css_class("format-popover")
        self.annotation = annotation
        self._on_change = on_change
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.append(self._colors())
        rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        for row in self._rows():
            rows.append(row)
        content.append(rows)
        self.set_child(content)

    def _change(self, **style: object) -> None:
        """Give the annotation another style (only what is given changes), and tell it."""
        self.annotation = replace(self.annotation, style=replace(self.annotation.style, **style))  # type: ignore[arg-type]
        self._on_change(self.annotation)

    def _colors(self) -> Gtk.Widget:
        """The six colour circles, bound to an action of the panel's own."""
        color = color_to_hex(self.annotation.color) if self.annotation.color else NO_COLOR
        action = Gio.SimpleAction.new_stateful(
            "color", GLib.VariantType.new("s"), GLib.Variant.new_string(color if color in ANNOTATION_COLORS else "")
        )
        action.connect("activate", self._on_color_chosen)
        group = Gio.SimpleActionGroup()
        group.add_action(action)
        self.insert_action_group("format", group)
        row = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER, homogeneous=True)
        for value in ANNOTATION_COLORS:
            row.append(color_circle(value, "format.color"))
        return row

    def _on_color_chosen(self, action: Gio.SimpleAction, value: GLib.Variant | None) -> None:
        if value is None:
            return
        action.set_state(value)
        self.annotation = replace(self.annotation, color=hex_to_color(value.get_string()))
        self._on_change(self.annotation)

    def _rows(self) -> list[Gtk.Widget]:
        kind, style = self.annotation.kind, self.annotation.style
        if kind is Kind.TEXT_BOX:
            return [
                self._font_size_row(style),
                self._switch_row(_("Background"), "background", active=style.background),
                self._switch_row(_("Border"), "border", active=style.border),
            ]
        rows: list[Gtk.Widget] = []
        if kind in SHAPES or kind in {Kind.ARROW, Kind.FREEHAND}:
            rows.append(self._line_width_row(style))
        if kind in SHAPES or kind is Kind.ARROW:
            rows.append(self._line_style_row(style))
        if kind in SHAPES:
            rows.append(self._switch_row(_("Fill"), "filled", active=style.filled))
        if kind is Kind.ARROW:
            rows.append(self._line_ends_row(style))
        rows.append(self._opacity_row(style))
        return rows

    def _line_width_row(self, style: Style) -> Gtk.Widget:
        names = {1.0: _("Thin"), 2.0: _("Medium"), 4.0: _("Thick")}
        return self._choice_row(
            _("Line Width"), _with_value(LINE_WIDTHS, style.line_width), style.line_width, "line_width", names
        )

    def _font_size_row(self, style: Style) -> Gtk.Widget:
        names = {9.0: _("Small"), 11.0: _("Normal"), 14.0: _("Large"), 18.0: _("Very Large")}
        return self._choice_row(
            _("Letter Size"), _with_value(FONT_SIZES, style.font_size), style.font_size, "font_size", names
        )

    def _line_style_row(self, style: Style) -> Gtk.Widget:
        names = {False: _("Solid"), True: _("Dashed")}
        return self._choice_row(_("Line"), [False, True], style.dashed, "dashed", names)

    def _line_ends_row(self, style: Style) -> Gtk.Widget:
        names = {LineEnds.END: _("At the End"), LineEnds.BOTH: _("At Both Ends"), LineEnds.NONE: _("None")}
        return self._choice_row(_("Arrowheads"), list(LINE_ENDS), style.line_ends, "line_ends", names)

    def _choice_row[Value](
        self, title: str, values: Sequence[Value], chosen: Value, field: str, names: Mapping[Value, str]
    ) -> Gtk.Widget:
        """A drop-down row; a value without a name (one read from another program) shows as itself, in points."""
        labels = [names.get(value) or _("{size:g} pt").format(size=value) for value in values]
        row = Adw.ComboRow(title=title, model=Gtk.StringList.new(labels), selected=list(values).index(chosen))
        row.connect("notify::selected", lambda combo, _spec: self._change(**{field: values[combo.get_selected()]}))
        return row

    def _switch_row(self, title: str, field: str, *, active: bool) -> Gtk.Widget:
        row = Adw.SwitchRow(title=title, active=active)
        row.connect("notify::active", lambda switch, _spec: self._change(**{field: switch.get_active()}))
        return row

    def _opacity_row(self, style: Style) -> Gtk.Widget:
        """A slider from 10 to 100 per cent."""
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, LEAST_OPACITY, 100, OPACITY_STEP)
        scale.set_value(round(style.opacity * 100))
        scale.set_hexpand(True)
        scale.set_draw_value(True)
        scale.set_value_pos(Gtk.PositionType.RIGHT)
        scale.set_format_value_func(lambda _scale, value: _("{percent} %").format(percent=round(value)))
        scale.set_size_request(OPACITY_WIDTH, -1)
        scale.update_property([Gtk.AccessibleProperty.LABEL], [_("Opacity")])
        scale.connect("value-changed", lambda slider: self._change(opacity=round(slider.get_value()) / 100))
        row = Adw.ActionRow(title=_("Opacity"))
        row.add_suffix(scale)
        return row


def _with_value(options: Sequence[float], value: float) -> list[float]:
    """The options, with a value that is not one of them in its place by size."""
    return sorted({*options, value})
