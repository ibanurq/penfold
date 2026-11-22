"""Annotating from the window (02-interfaz, 5; D65): the pencil, the annotation bar, and the tool and colour chosen.

The pencil shows and hides the bar; hiding it goes back to Select Text. A tool stays chosen after an annotation is
made, until another is chosen (D65). A PDF is only annotated if it allows it (D59, D61): otherwise the pencil is
greyed out.

The tools that mark text (highlight, underline, strike through) mark what is selected when the mouse is released
(H1). H and U mark the text selected without changing the tool, or else choose their tool (H7). Rectangles, circles
and arrows are drawn by dragging, from where the drag starts to where it ends (H4).
"""

from collections.abc import Callable

from gi.repository import Gio, GLib, Gtk

from penfold.document.annotations import Annotation, Kind, new_annotation
from penfold.document.commands.annotations import AddAnnotations
from penfold.document.document import OpenDocument
from penfold.document.geometry import Rectangle
from penfold.ui.annotation_toolbar import AnnotationToolbar, Tool
from penfold.ui.document_view import DocumentView
from penfold.ui.palette import ANNOTATION_COLORS, Color, hex_to_color

Point = tuple[float, float]
# Over the pages, the cursor of the tools that draw; the others select text, with the view's own cursor.
DRAWING_CURSOR = "crosshair"
DRAWING_TOOLS = frozenset({Tool.RECTANGLE, Tool.CIRCLE, Tool.ARROW, Tool.COMMENT, Tool.TEXT_BOX})
MARKING_TOOLS = frozenset({Tool.HIGHLIGHT, Tool.UNDERLINE, Tool.STRIKE_OUT})
SHAPE_TOOLS = frozenset({Tool.RECTANGLE, Tool.CIRCLE, Tool.ARROW})
# A drag shorter than this, in points, is a click: it draws nothing.
SMALLEST_SHAPE = 3.0


class Annotating:
    """The window's actions "annotate" (the pencil), "annotation-tool" and "annotation-color"."""

    def __init__(
        self,
        window: Gtk.ApplicationWindow,
        toolbar: AnnotationToolbar,
        document_view: DocumentView,
        document: Callable[[], OpenDocument | None],
        author: Callable[[], str],
    ) -> None:
        """Add the actions to the window; document gives the document shown, if any, and author the preference."""
        self._toolbar = toolbar
        self._author = author
        self._document_view = document_view
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
        document_view.connect("text-selected", self._on_text_selected)
        document_view.connect("shape-drawn", self._on_shape_drawn)

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

    @property
    def allowed(self) -> bool:
        """Whether the document shown may be annotated."""
        document = self._document()
        return document is not None and document.permissions.annotate

    def choose(self, tool: Tool) -> None:
        """Choose a tool, as its button of the bar does, showing the bar."""
        if tool is not Tool.SELECT and not self.bar_shown:
            self._annotate.change_state(GLib.Variant.new_boolean(True))
        self._tool.change_state(GLib.Variant.new_string(tool.value))

    def mark_or_choose(self, tool: Tool) -> bool:
        """H and U (H7): mark the text selected with this tool's mark, or else choose it; return whether done."""
        if not self.allowed or tool not in MARKING_TOOLS:
            return False
        if not self.mark_selection(tool):
            self.choose(tool)
        return True

    def mark_selection(self, tool: Tool) -> bool:
        """Mark the text selected (one annotation on each page), as one edit; return whether any was selected."""
        document = self._document()
        kind = tool.kind
        areas = self._document_view.selected_areas()
        if document is None or kind is None or not areas or not self.allowed:
            return False
        author = self._author()
        annotations = [
            new_annotation(kind, page, _bounds(lines), self.color, author, quads=tuple(lines))
            for page, lines in areas.items()
        ]
        self._document_view.clear_selection()
        document.execute(AddAnnotations(document, annotations))
        return True

    def _on_annotate(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        action.set_state(value)
        self._bar_shown = value.get_boolean()
        self._toolbar.set_visible(self._bar_shown)
        if not self._bar_shown:
            self.choose(Tool.SELECT)

    def _on_tool_chosen(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        if value.get_string() not in {tool.value for tool in Tool}:
            return
        action.set_state(value)
        self._chosen_tool = Tool(value.get_string())
        self._document_view.marking = self.tool in MARKING_TOOLS
        self._document_view.set_shape_maker(self._make_shape if self.tool in SHAPE_TOOLS else None)
        self._document_view.set_drawing_cursor(DRAWING_CURSOR if self.tool in DRAWING_TOOLS else None)

    def _make_shape(self, page: int, start: Point, end: Point) -> Annotation | None:
        """The shape of the tool chosen from one end of a drag to the other; None for a click."""
        kind = self.tool.kind
        if kind is None or max(abs(end[0] - start[0]), abs(end[1] - start[1])) < SMALLEST_SHAPE:
            return None
        rectangle = (min(start[0], end[0]), min(start[1], end[1]), max(start[0], end[0]), max(start[1], end[1]))
        line = (*start, *end) if kind is Kind.ARROW else None
        return new_annotation(kind, page, rectangle, self.color, self._author(), line=line)

    def _on_shape_drawn(self, _view: DocumentView, shape: Annotation) -> None:
        document = self._document()
        if document is not None and self.allowed:
            document.execute(AddAnnotations(document, [shape]))

    def _on_text_selected(self, _view: DocumentView) -> None:
        """With a tool that marks text, the text just selected is marked (H1)."""
        if self.tool in MARKING_TOOLS:
            self.mark_selection(self.tool)

    def _on_color_chosen(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        if value.get_string() in ANNOTATION_COLORS:
            action.set_state(value)
            self._chosen_color = value.get_string()
            self._toolbar.show_color(self._chosen_color)


def _bounds(lines: list[Rectangle]) -> Rectangle:
    """The rectangle around the lines a mark covers."""
    return (
        min(line[0] for line in lines),
        min(line[1] for line in lines),
        max(line[2] for line in lines),
        max(line[3] for line in lines),
    )
