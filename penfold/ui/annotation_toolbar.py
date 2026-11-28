"""The floating annotation bar: the tools, by group, and the colour.

It floats at the bottom of the document, centred, left of the zoom buttons. The pencil of the header shows and hides
it. The tools and the colour are the window's actions "annotation-tool" and "annotation-color", whose states it shows.
The stamp tool's button has an arrow: chosen, it opens the menu of Penfold's stamps above it, in their three groups;
each item is the window's action "put-stamp" with the stamp's name.
"""

import enum
from collections.abc import Callable
from gettext import gettext as _

from gi.repository import Gio, GLib, Gtk

from penfold.document.annotations import Kind
from penfold.document.stamps import STAMP_GROUPS
from penfold.ui.annotation_icons import KIND_ICONS, SELECT_TEXT_ICON, kind_names, stamp_name
from penfold.ui.palette import ANNOTATION_COLORS, color_circle, color_swatch, show_color

TOOL_ACTION = "win.annotation-tool"
COLOR_ACTION = "win.annotation-color"
STAMP_ACTION = "win.put-stamp"
# The arrow of the buttons that open something above them, as the colour button's.
UP_ARROW_ICON = "pan-up-symbolic"
# The room the zoom buttons take at the right of the document, which the bar leaves free.
ZOOM_BUTTONS_ROOM = 72
BAR_MARGIN = 18
# The space left between the bar and the zoom buttons when they rise above it.
ZOOM_LIFT_GAP = 12


class Tool(enum.Enum):
    """The tools of the bar; one is chosen at a time."""

    SELECT = "select"
    HIGHLIGHT = "highlight"
    UNDERLINE = "underline"
    SQUIGGLY = "squiggly"
    STRIKE_OUT = "strike-out"
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    ARROW = "arrow"
    FREEHAND = "freehand"
    COMMENT = "comment"
    TEXT_BOX = "text-box"
    IMAGE = "image"
    STAMP = "stamp"

    @property
    def kind(self) -> Kind | None:
        """The type of annotation it makes; None for Select Text."""
        return TOOL_KINDS.get(self)


TOOL_KINDS = {
    Tool.HIGHLIGHT: Kind.HIGHLIGHT,
    Tool.UNDERLINE: Kind.UNDERLINE,
    Tool.SQUIGGLY: Kind.SQUIGGLY,
    Tool.STRIKE_OUT: Kind.STRIKE_OUT,
    Tool.RECTANGLE: Kind.RECTANGLE,
    Tool.CIRCLE: Kind.CIRCLE,
    Tool.ARROW: Kind.ARROW,
    Tool.FREEHAND: Kind.FREEHAND,
    Tool.COMMENT: Kind.COMMENT,
    Tool.TEXT_BOX: Kind.TEXT_BOX,
    Tool.IMAGE: Kind.IMAGE,
    Tool.STAMP: Kind.STAMP,
}
# The tools by group, in the order of the print dialogue.
TOOL_GROUPS = (
    (Tool.SELECT,),
    (Tool.HIGHLIGHT, Tool.UNDERLINE, Tool.SQUIGGLY, Tool.STRIKE_OUT),
    (Tool.RECTANGLE, Tool.CIRCLE, Tool.ARROW, Tool.FREEHAND),
    (Tool.COMMENT, Tool.TEXT_BOX),
    (Tool.IMAGE, Tool.STAMP),
)


def tool_icon(tool: Tool) -> str:
    """The icon of a tool: that of the annotation type it makes."""
    return KIND_ICONS[tool.kind] if tool.kind else SELECT_TEXT_ICON


def tool_names() -> dict[Tool, str]:
    """The name of each tool, for its tooltip (translated when called)."""
    kinds = kind_names()
    return {tool: kinds[tool.kind] if tool.kind else _("Select Text") for tool in Tool}


class AnnotationToolbar(Gtk.Box):
    """A card with the tool buttons, separated by group, and the colour button that opens the palette above.

    It is grey, with a thin edge and a soft shadow, so that it stands out on a white page (style.css).
    """

    __gtype_name__ = "PenfoldAnnotationToolbar"

    def __init__(self) -> None:
        """Create the bar, hidden until the pencil shows it."""
        super().__init__(spacing=4, halign=Gtk.Align.START, valign=Gtk.Align.END, visible=False)
        self.set_margin_bottom(BAR_MARGIN)
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
                if tool is Tool.STAMP:
                    button.set_child(_with_arrow(tool_icon(tool)))
                    button.update_property([Gtk.AccessibleProperty.LABEL], [names[tool]])
                self.tool_buttons[tool] = button
                self.append(button)
        self.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.swatch = color_swatch(ANNOTATION_COLORS[0])
        circles = Gtk.Box(spacing=9, margin_top=6, margin_bottom=6, margin_start=3, margin_end=3)
        for value in ANNOTATION_COLORS:
            circle = color_circle(value, COLOR_ACTION)
            # Choosing a colour closes the palette, so the page can be annotated at once.
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

    def show_stamp_menu(self, on_closed: Callable[[], None]) -> Gtk.PopoverMenu:
        """Open the menu of the stamps above the stamp tool's button; on_closed is told once it has closed.

        It is told after the action of the item chosen, if one was, has run.
        """
        menu = Gtk.PopoverMenu.new_from_model(stamp_menu_model())
        menu.set_parent(self.tool_buttons[Tool.STAMP])
        menu.set_position(Gtk.PositionType.TOP)

        def closed(_menu: Gtk.PopoverMenu) -> None:
            GLib.idle_add(forget)  # After the item's action, and outside the popover's own signal.

        def forget() -> bool:
            menu.unparent()
            on_closed()
            return GLib.SOURCE_REMOVE

        menu.connect("closed", closed)
        menu.popup()
        return menu


def stamp_menu_model() -> Gio.Menu:
    """The menu of Penfold's stamps, by their names (translated), one section for each group of colour."""
    menu = Gio.Menu()
    for group in STAMP_GROUPS:
        section = Gio.Menu()
        for stamp in group:
            item = Gio.MenuItem.new(stamp_name(stamp.name), None)
            item.set_action_and_target_value(STAMP_ACTION, GLib.Variant.new_string(stamp.name))
            section.append_item(item)
        menu.append_section(None, section)
    return menu


def _with_arrow(icon: str) -> Gtk.Widget:
    """An icon with an arrow up beside it, for a button that opens something above it."""
    box = Gtk.Box(spacing=4)
    box.append(Gtk.Image(icon_name=icon))
    box.append(Gtk.Image(icon_name=UP_ARROW_ICON))
    return box


def bar_position(document_width: int, bar_width: int) -> int:
    """Where the bar starts: centred on the document, or further left to leave the zoom buttons free."""
    centred = (document_width - bar_width) // 2
    widest = document_width - ZOOM_BUTTONS_ROOM - bar_width
    return max(0, min(centred, widest))


def fits_beside_zoom_buttons(document_width: int, bar_width: int) -> bool:
    """Whether the bar and the zoom buttons fit side by side; if not, the zoom buttons rise above the bar."""
    return bar_width + ZOOM_BUTTONS_ROOM <= document_width
