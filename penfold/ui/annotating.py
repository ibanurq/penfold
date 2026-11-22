"""Annotating from the window (02-interfaz, 5; D65): the pencil, the annotation bar, and the tool and colour chosen.

The pencil shows and hides the bar; hiding it goes back to Select Text. A tool stays chosen after an annotation is
made, until another is chosen (D65). A PDF is only annotated if it allows it (D59, D61): otherwise the pencil is
greyed out.
"""

from collections.abc import Callable

from gi.repository import Adw, Gio, GLib, Gtk

from penfold.document.document import OpenDocument
from penfold.ui.annotation_toolbar import AnnotationToolbar, Tool
from penfold.ui.document_view import DocumentView
from penfold.ui.palette import ANNOTATION_COLORS, Color, hex_to_color

# Over the pages, the cursor of the tools that draw; the others select text, with the view's own cursor.
DRAWING_CURSOR = "crosshair"
DRAWING_TOOLS = frozenset({Tool.RECTANGLE, Tool.CIRCLE, Tool.ARROW, Tool.COMMENT, Tool.TEXT_BOX})
# On the toast overlay while the bar is shown: the toasts rise above the bar (D32).
BAR_SHOWN_CLASS = "annotation-bar-shown"


class Annotating:
    """The window's actions "annotate" (the pencil), "annotation-tool" and "annotation-color"."""

    def __init__(
        self,
        window: Gtk.ApplicationWindow,
        toolbar: AnnotationToolbar,
        document_view: DocumentView,
        toast_overlay: Adw.ToastOverlay,
        document: Callable[[], OpenDocument | None],
    ) -> None:
        """Add the actions to the window; document gives the document shown, if any."""
        self._toolbar = toolbar
        self._document_view = document_view
        self._toast_overlay = toast_overlay
        self._document = document
        self._chosen_tool = Tool.SELECT
        self._chosen_color = ANNOTATION_COLORS[0]
        self._bar_shown = False
        self._annotate = Gio.SimpleAction.new_stateful("annotate", None, GLib.Variant.new_boolean(False))
        self._annotate.set_enabled(False)
        self._annotate.connect("change-state", self._on_annotate)
        self._tool = Gio.SimpleAction.new_stateful(
            "annotation-tool", GLib.VariantType.new("s"), GLib.Variant.new_string(Tool.SELECT.value)
        )
        self._tool.connect("change-state", self._on_tool_chosen)
        self._color = Gio.SimpleAction.new_stateful(
            "annotation-color", GLib.VariantType.new("s"), GLib.Variant.new_string(ANNOTATION_COLORS[0])
        )
        self._color.connect("change-state", self._on_color_chosen)
        for action in (self._annotate, self._tool, self._color):
            window.add_action(action)

    @property
    def tool(self) -> Tool:
        """The tool chosen."""
        return self._chosen_tool

    @property
    def color(self) -> Color:
        """The colour of the annotations to make."""
        return hex_to_color(self._chosen_color)

    @property
    def bar_shown(self) -> bool:
        """Whether the annotation bar is shown."""
        return self._bar_shown

    def update_actions(self) -> None:
        """Let the pencil be used only with a document that may be annotated; otherwise hide the bar."""
        document = self._document()
        allowed = document is not None and document.permissions.annotate
        self._annotate.set_enabled(allowed)
        if not allowed and self.bar_shown:
            self._annotate.change_state(GLib.Variant.new_boolean(False))

    def choose(self, tool: Tool) -> None:
        """Choose a tool, as its button of the bar does."""
        self._tool.change_state(GLib.Variant.new_string(tool.value))

    def _on_annotate(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        action.set_state(value)
        self._bar_shown = value.get_boolean()
        self._toolbar.set_visible(self._bar_shown)
        if self._bar_shown:
            self._toast_overlay.add_css_class(BAR_SHOWN_CLASS)
        else:
            self._toast_overlay.remove_css_class(BAR_SHOWN_CLASS)
            self.choose(Tool.SELECT)

    def _on_tool_chosen(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        if value.get_string() not in {tool.value for tool in Tool}:
            return
        action.set_state(value)
        self._chosen_tool = Tool(value.get_string())
        self._document_view.set_drawing_cursor(DRAWING_CURSOR if self.tool in DRAWING_TOOLS else None)

    def _on_color_chosen(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        if value.get_string() in ANNOTATION_COLORS:
            action.set_state(value)
            self._chosen_color = value.get_string()
            self._toolbar.show_color(self._chosen_color)
