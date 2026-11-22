"""The style of the interface (D62): follow the system, light or dark, chosen with three circles in the main menu.

The choice is the "style" setting; the application turns it into the stateful action app.style, so every menu shows
the same choice and a change applies at once to every window. The pages of the PDF keep their own colours.
"""

from gettext import gettext as _

from gi.repository import Adw, GLib, Gtk

STYLE_KEY = "style"
COLOR_SCHEMES = {
    "system": Adw.ColorScheme.DEFAULT,
    "light": Adw.ColorScheme.FORCE_LIGHT,
    "dark": Adw.ColorScheme.FORCE_DARK,
}


def apply_style(style: str) -> None:
    """Show every window in a style: "system", "light" or "dark"."""
    Adw.StyleManager.get_default().set_color_scheme(COLOR_SCHEMES[style])


class StyleSelector(Gtk.Box):
    """Three circles, one for each style; the chosen one has a ring."""

    __gtype_name__ = "PenfoldStyleSelector"

    def __init__(self) -> None:
        """Create the circles, bound to app.style."""
        super().__init__(spacing=18, halign=Gtk.Align.CENTER, homogeneous=True)
        self.add_css_class("style-selector")
        descriptions = {
            "system": _("Follow System Style"),
            "light": _("Light Style"),
            "dark": _("Dark Style"),
        }
        for style, description in descriptions.items():
            circle = Gtk.ToggleButton(
                action_name=f"app.{STYLE_KEY}",
                action_target=GLib.Variant.new_string(style),
                tooltip_text=description,
                css_classes=["style-circle", style],
            )
            circle.update_property([Gtk.AccessibleProperty.LABEL], [description])
            self.append(circle)
