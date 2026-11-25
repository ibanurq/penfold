"""The colours of the app: one palette for annotations and another for bookmarks.

Annotations take six light tones, soft under the text. A bookmark's colour tints its title, so bookmarks take four
darker tones that can be read on white, which is what most viewers show behind the outline; in the panel, Penfold
adjusts any bookmark colour to its background, light or dark, without changing the file (color_contrast.readable_on).
"""

import functools
from gettext import gettext as _

from gi.repository import Gdk, GLib, Gtk

from penfold.ui.color_contrast import Color

ANNOTATION_COLORS = ("#f9f06b", "#8ff0a4", "#99c1f1", "#ffbe6f", "#f66151", "#dc8add")
# Burgundy and the orange, green and blue accent colours of libadwaita (#ed5b00, #3a944a, #3584e4) darkened just enough
# to be read on white: color_contrast.readable_on(colour, WHITE).
BOOKMARK_COLORS = ("#ad182e", "#d54400", "#2c873e", "#2676d5")
COLORS = ANNOTATION_COLORS + BOOKMARK_COLORS
BYTE = 255


def color_names() -> dict[str, str]:
    """The name of each colour of the palettes, by its value (translated when called)."""
    annotation_names = (_("Yellow"), _("Green"), _("Blue"), _("Orange"), _("Red"), _("Lilac"))
    names = (*annotation_names, _("Burgundy"), _("Orange"), _("Green"), _("Blue"))
    return dict(zip(COLORS, names, strict=True))


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
    circle = Gtk.ToggleButton(tooltip_text=color_names()[value], action_name=action_name)
    circle.set_action_target_value(GLib.Variant.new_string(value))
    circle.add_css_class("color-circle")
    circle.add_css_class(f"palette-color-{COLORS.index(value)}")
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
