"""The Format panel of the Bookmarks view (G7; 02-interfaz, 6.2; D23, D33).

Bold, italic, a row of eight colour circles and Clear Formatting, acting on the bookmarks selected through the
window's actions. Their states show the style the selected bookmarks share: bold and italic are on if all of them have
it, and a circle has a ring if all of them have its colour.
"""

import functools
from gettext import gettext as _

from gi.repository import Adw, Gdk, GLib, Gtk

from penfold.document.bookmarks import Color

# The bookmark colours of 0.6 (docs/specification.md, BOOKMARK_PALETTE; D33): those of the annotations, then grey and
# burgundy.
BOOKMARK_COLORS = ("#f9f06b", "#8ff0a4", "#99c1f1", "#ffbe6f", "#f66151", "#dc8add", "#606971", "#ad182e")
BYTE = 255


def color_to_hex(color: Color) -> str:
    """Return an outline colour as #rrggbb."""
    red, green, blue = (round(component * BYTE) for component in color)
    return f"#{red:02x}{green:02x}{blue:02x}"


def hex_to_color(text: str) -> Color:
    """Return #rrggbb as an outline colour.

    Raises:
        ValueError: the text is not a colour written so.
    """
    if len(text) != len("#rrggbb") or not text.startswith("#"):
        message = f"{text!r} is not a colour"
        raise ValueError(message)
    red, green, blue = (int(text[index : index + 2], 16) / BYTE for index in (1, 3, 5))
    return red, green, blue


def format_button() -> Gtk.MenuButton:
    """Return the Format button of the bar, which opens the panel above it."""
    display = Gdk.Display.get_default()
    if display is not None:
        _paint_circles(display)
    button = Gtk.MenuButton(
        icon_name="format-text-rich-symbolic",
        tooltip_text=_("Format"),
        popover=Gtk.Popover(child=_format_panel()),
        direction=Gtk.ArrowType.UP,
    )
    # Until the user chooses the icon (D37).
    button.add_css_class("provisional-icon")
    return button


@functools.cache
def _paint_circles(display: Gdk.Display) -> None:
    """Give each colour circle its colour (.bookmark-color-N), once; the rest of their look is in style.css."""
    provider = Gtk.CssProvider()
    rules = (f".bookmark-color-{index} {{ background-color: {value}; }}" for index, value in enumerate(BOOKMARK_COLORS))
    provider.load_from_string("\n".join(rules))
    Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def _format_panel() -> Gtk.Box:
    panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    styles = Gtk.Box(spacing=6)
    for icon_name, tooltip, action_name in (
        ("format-text-bold-symbolic", _("Bold"), "win.bookmark-bold"),
        ("format-text-italic-symbolic", _("Italic"), "win.bookmark-italic"),
    ):
        toggle = Gtk.ToggleButton(icon_name=icon_name, tooltip_text=tooltip, action_name=action_name)
        toggle.add_css_class("flat")
        styles.append(toggle)
    panel.append(styles)
    colors = Gtk.Box(spacing=9, margin_top=6, margin_bottom=6)
    names = (_("Yellow"), _("Green"), _("Blue"), _("Orange"), _("Red"), _("Lilac"), _("Grey"), _("Burgundy"))
    for index, (value, name) in enumerate(zip(BOOKMARK_COLORS, names, strict=True)):
        circle = Gtk.ToggleButton(tooltip_text=name, action_name="win.bookmark-color")
        circle.set_action_target_value(GLib.Variant.new_string(value))
        circle.add_css_class("color-circle")
        circle.add_css_class(f"bookmark-color-{index}")
        colors.append(circle)
    panel.append(colors)
    panel.append(Gtk.Separator())
    clear = Gtk.Button(
        child=Adw.ButtonContent(icon_name="edit-clear-symbolic", label=_("Clear Formatting")),
        action_name="win.clear-bookmark-format",
        halign=Gtk.Align.START,
    )
    clear.add_css_class("flat")
    panel.append(clear)
    return panel
