"""The Format panel of the Bookmarks view (G7; 02-interfaz, 6.2; D23, D33).

Bold, italic, a row of eight colour circles and Clear Formatting, acting on the bookmarks selected through the
window's actions. Their states show the style the selected bookmarks share: bold and italic are on if all of them have
it, and a circle has a ring if all of them have its colour.
"""

from gettext import gettext as _

from gi.repository import Adw, Gtk

from penfold.ui.palette import COLORS, color_circle


def format_button() -> Gtk.MenuButton:
    """Return the Format button of the bar, which opens the panel above it."""
    button = Gtk.MenuButton(
        icon_name="format-text-rich-symbolic",
        tooltip_text=_("Format"),
        popover=Gtk.Popover(child=_format_panel()),
        direction=Gtk.ArrowType.UP,
    )
    # Until the user chooses the icon (D37).
    button.add_css_class("provisional-icon")
    return button


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
    for value in COLORS:
        colors.append(color_circle(value, "win.bookmark-color"))
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
