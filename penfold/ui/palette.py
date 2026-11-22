"""The colours of the app (D33): one list for bookmarks and annotations, shown as rows of colour circles.

They are those of 0.6 (docs/specification.md, PALETTE and BOOKMARK_PALETTE): six for annotations, and two more,
grey and burgundy, for bookmarks.
"""

import functools
from gettext import gettext as _

from gi.repository import Gdk, GLib, Gtk

Color = tuple[float, float, float]

COLORS = ("#f9f06b", "#8ff0a4", "#99c1f1", "#ffbe6f", "#f66151", "#dc8add", "#606971", "#ad182e")
ANNOTATION_COLORS = COLORS[:6]
BYTE = 255


def color_names() -> tuple[str, ...]:
    """The name of each colour, in order (translated when called)."""
    return (_("Yellow"), _("Green"), _("Blue"), _("Orange"), _("Red"), _("Lilac"), _("Grey"), _("Burgundy"))


def color_to_hex(color: Color) -> str:
    """Return a colour as #rrggbb."""
    red, green, blue = (round(component * BYTE) for component in color)
    return f"#{red:02x}{green:02x}{blue:02x}"


def hex_to_color(text: str) -> Color:
    """Return #rrggbb as a colour.

    Raises:
        ValueError: the text is not a colour written so.
    """
    if len(text) != len("#rrggbb") or not text.startswith("#"):
        message = f"{text!r} is not a colour"
        raise ValueError(message)
    red, green, blue = (int(text[index : index + 2], 16) / BYTE for index in (1, 3, 5))
    return red, green, blue


def color_circle(value: str, action_name: str) -> Gtk.ToggleButton:
    """A colour circle that sets a text action with a state to its colour; the circle of the state has a ring."""
    display = Gdk.Display.get_default()
    if display is not None:
        _paint_circles(display)
    index = COLORS.index(value)
    circle = Gtk.ToggleButton(tooltip_text=color_names()[index], action_name=action_name)
    circle.set_action_target_value(GLib.Variant.new_string(value))
    circle.add_css_class("color-circle")
    circle.add_css_class(f"palette-color-{index}")
    return circle


def color_swatch(value: str) -> Gtk.Widget:
    """A small round sample of a colour, for a button that opens a palette."""
    swatch = Gtk.Box(valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
    swatch.add_css_class("color-swatch")
    show_color(swatch, value)
    return swatch


def show_color(swatch: Gtk.Widget, value: str) -> None:
    """Give a colour sample another colour."""
    display = Gdk.Display.get_default()
    if display is not None:
        _paint_circles(display)
    for index in range(len(COLORS)):
        swatch.remove_css_class(f"palette-color-{index}")
    swatch.add_css_class(f"palette-color-{COLORS.index(value)}")


@functools.cache
def _paint_circles(display: Gdk.Display) -> None:
    """Give each colour circle its colour (.palette-color-N), once; the rest of their look is in style.css."""
    provider = Gtk.CssProvider()
    rules = (f".palette-color-{index} {{ background-color: {value}; }}" for index, value in enumerate(COLORS))
    provider.load_from_string("\n".join(rules))
    Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
