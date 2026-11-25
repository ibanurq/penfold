"""The floating annotation bar (02-interfaz, 5; D10, D32, D65): the tools, by group, and the colour.

It floats at the bottom of the document, centred, left of the zoom buttons. The pencil of the header shows and hides
it. The tools and the colour are the window's actions "annotation-tool" and "annotation-color", whose states it shows.
"""

import enum
from gettext import gettext as _

from gi.repository import GLib, Gtk

from penfold.document.annotations import Kind
from penfold.ui.annotation_icons import KIND_ICONS, SELECT_TEXT_ICON, kind_names
from penfold.ui.palette import ANNOTATION_COLORS, color_circle, color_swatch, show_color

TOOL_ACTION = "win.annotation-tool"
COLOR_ACTION = "win.annotation-color"
# The room the zoom buttons take at the right of the document, which the bar leaves free (D32).
ZOOM_BUTTONS_ROOM = 72
BAR_MARGIN = 18
# The space left between the bar and the zoom buttons when they rise above it.
ZOOM_LIFT_GAP = 12


class Tool(enum.Enum):
    """The tools of the bar; one is chosen at a time (02-interfaz, 5)."""

    SELECT = "select"
    HIGHLIGHT = "highlight"
    UNDERLINE = "underline"
    STRIKE_OUT = "strike-out"
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    ARROW = "arrow"
    COMMENT = "comment"
    TEXT_BOX = "text-box"

    @property
    def kind(self) -> Kind | None:
        """The type of annotation it makes; None for Select Text."""
        return TOOL_KINDS.get(self)


TOOL_KINDS = {
    Tool.HIGHLIGHT: Kind.HIGHLIGHT,
    Tool.UNDERLINE: Kind.UNDERLINE,
    Tool.STRIKE_OUT: Kind.STRIKE_OUT,
    Tool.RECTANGLE: Kind.RECTANGLE,
    Tool.CIRCLE: Kind.CIRCLE,
    Tool.ARROW: Kind.ARROW,
    Tool.COMMENT: Kind.COMMENT,
    Tool.TEXT_BOX: Kind.TEXT_BOX,
}
# The tools by group, in the order of the print dialogue (D64, D65).
TOOL_GROUPS = (
    (Tool.SELECT,),
    (Tool.HIGHLIGHT, Tool.UNDERLINE, Tool.STRIKE_OUT),
    (Tool.RECTANGLE, Tool.CIRCLE, Tool.ARROW),
    (Tool.COMMENT, Tool.TEXT_BOX),
)


def tool_icon(tool: Tool) -> str:
    """The icon of a tool: that of the annotation type it makes (D75)."""
    return KIND_ICONS[tool.kind] if tool.kind else SELECT_TEXT_ICON


def tool_names() -> dict[Tool, str]:
    """The name of each tool, for its tooltip (translated when called)."""
    kinds = kind_names()
    return {tool: kinds[tool.kind] if tool.kind else _("Select Text") for tool in Tool}


class AnnotationToolbar(Gtk.Box):
    """A card with the tool buttons, separated by group, and the colour button that opens the palette above.

    It has the zoom buttons' look (osd), so that it stands out on a white page (D71).
    """

    __gtype_name__ = "PenfoldAnnotationToolbar"

    def __init__(self) -> None:
        """Create the bar, hidden until the pencil shows it."""
        super().__init__(spacing=4, halign=Gtk.Align.START, valign=Gtk.Align.END, visible=False)
        self.set_margin_bottom(BAR_MARGIN)
        self.add_css_class("osd")
        self.add_css_class("annotation-bar")
        names = tool_names()
        self.tool_buttons: dict[Tool, Gtk.ToggleButton] = {}
        for index, group in enumerate(TOOL_GROUPS):
            if index:
                self.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
            for tool in group:
                button = Gtk.ToggleButton(icon_name=tool_icon(tool), tooltip_text=names[tool], action_name=TOOL_ACTION)
                button.set_action_target_value(GLib.Variant.new_string(tool.value))
                button.add_css_class("flat")
                self.tool_buttons[tool] = button
                self.append(button)
        self.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.swatch = color_swatch(ANNOTATION_COLORS[0])
        circles = Gtk.Box(spacing=9, margin_top=6, margin_bottom=6, margin_start=3, margin_end=3)
        for value in ANNOTATION_COLORS:
            circle = color_circle(value, COLOR_ACTION)
            # Choosing a colour closes the palette, so the page can be annotated at once (D71).
            circle.connect("clicked", lambda _circle: self.color_button.popdown())
            circles.append(circle)
        self.color_button = Gtk.MenuButton(
            child=self.swatch,
            tooltip_text=_("Color"),
            popover=Gtk.Popover(child=circles),
            direction=Gtk.ArrowType.UP,
            always_show_arrow=True,
        )
        self.color_button.add_css_class("flat")
        # Without a name of its own, screen readers would read the names of the colours in its open palette.
        self.color_button.update_property([Gtk.AccessibleProperty.LABEL], [_("Color")])
        self.append(self.color_button)

    def show_color(self, value: str) -> None:
        """Show the colour chosen on the colour button."""
        show_color(self.swatch, value)


def bar_position(document_width: int, bar_width: int) -> int:
    """Where the bar starts: centred on the document, or further left to leave the zoom buttons free (D32)."""
    centred = (document_width - bar_width) // 2
    widest = document_width - ZOOM_BUTTONS_ROOM - bar_width
    return max(0, min(centred, widest))


def fits_beside_zoom_buttons(document_width: int, bar_width: int) -> bool:
    """Whether the bar and the zoom buttons fit side by side; if not, the zoom buttons rise above the bar."""
    return bar_width + ZOOM_BUTTONS_ROOM <= document_width
