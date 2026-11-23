"""Annotating from the window (02-interfaz, 5; D65): the pencil, the annotation bar, and the tool and colour chosen.

The pencil shows and hides the bar; hiding it goes back to Select Text. A tool stays chosen after an annotation is
made, until another is chosen (D65). A PDF is only annotated if it allows it (D59, D61): otherwise the pencil is
greyed out.

The tools that mark text (highlight, underline, strike through) mark what is selected when the mouse is released
(H1). H and U mark the text selected without changing the tool, or else choose their tool (H7). Rectangles, circles
and arrows are drawn by dragging, from where the drag starts to where it ends (H4). A click places a comment, whose
text is written in a popover (H2, H5, D68). A drag sets the width of a text box (a click gives it a usual width),
whose text is written on the page (H3, D69).
"""

from collections.abc import Callable

from gi.repository import Gdk, Gio, GLib, Gtk

from penfold.document.annotations import Annotation, Kind, new_annotation
from penfold.document.appearance import COMMENT_SIZE
from penfold.document.commands.annotations import AddAnnotations
from penfold.document.document import OpenDocument
from penfold.document.geometry import bounds
from penfold.document.reshaping import SMALLEST_SIZE
from penfold.rendering.layout import ShownPage
from penfold.rendering.text_box import DEFAULT_WIDTH, NARROWEST, text_box_pdf, text_height
from penfold.ui.annotation_toolbar import AnnotationToolbar, Tool
from penfold.ui.comment_popover import CommentPopover
from penfold.ui.document_view import DocumentView, PageClick
from penfold.ui.palette import ANNOTATION_COLORS, Color, hex_to_color

Point = tuple[float, float]
# Over the pages, the cursor of the tools that draw; the others select text, with the view's own cursor.
DRAWING_CURSOR = "crosshair"
DRAWING_TOOLS = frozenset({Tool.RECTANGLE, Tool.CIRCLE, Tool.ARROW, Tool.COMMENT, Tool.TEXT_BOX})
MARKING_TOOLS = frozenset({Tool.HIGHLIGHT, Tool.UNDERLINE, Tool.STRIKE_OUT})
SHAPE_TOOLS = frozenset({Tool.RECTANGLE, Tool.CIRCLE, Tool.ARROW})


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
        self.comment_popover: CommentPopover | None = None
        # Where the last drag of the text box tool framed it: the page, the corner and the width, as shown.
        self._text_box_frame: tuple[ShownPage, Point, float] = (ShownPage(0, (0.0, 0.0)), (0.0, 0.0), 0.0)
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
        document_view.connect("page-clicked", self._on_page_clicked)

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
            new_annotation(kind, page, bounds(lines), self.color, author, quads=tuple(lines))
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
        makers = {**dict.fromkeys(SHAPE_TOOLS, self._make_shape), Tool.TEXT_BOX: self._frame_text_box}
        self._document_view.set_shape_maker(makers.get(self.tool))
        self._document_view.placing = self.tool is Tool.COMMENT
        self._document_view.set_fields_active(self.tool is Tool.SELECT)
        self._document_view.set_drawing_cursor(DRAWING_CURSOR if self.tool in DRAWING_TOOLS else None)

    def _make_shape(self, page: ShownPage, shown_start: Point, shown_end: Point) -> Annotation | None:
        """The shape of the tool chosen from one end of a drag to the other; None for a click."""
        kind = self.tool.kind
        start, end = page.to_source(*shown_start), page.to_source(*shown_end)
        if kind is None or max(abs(end[0] - start[0]), abs(end[1] - start[1])) < SMALLEST_SIZE:
            return None
        rectangle = (min(start[0], end[0]), min(start[1], end[1]), max(start[0], end[0]), max(start[1], end[1]))
        line = (*start, *end) if kind is Kind.ARROW else None
        return new_annotation(kind, page.source, rectangle, self.color, self._author(), line=line)

    def _frame_text_box(self, page: ShownPage, shown_start: Point, shown_end: Point) -> Annotation:
        """The empty text box a drag frames: as wide as the drag (a click: the usual width), inside the page."""
        page_width, _page_height = page.size
        left = min(shown_start[0], shown_end[0])
        width = abs(shown_end[0] - shown_start[0])
        if width < SMALLEST_SIZE:
            left, width = shown_start[0], DEFAULT_WIDTH
        width = max(NARROWEST, min(width, page_width - left))
        left = min(left, page_width - width)
        self._text_box_frame = (page, (left, shown_start[1]), width)
        return self._text_box(page, (left, shown_start[1]), width, "")

    def _text_box(self, page: ShownPage, corner: Point, width: float, text: str) -> Annotation:
        """A text box with this text, upright on the page as shown: its height follows the text."""
        height = text_height(text, width)
        left, top = corner
        corners = [page.to_source(left, top), page.to_source(left + width, top + height)]
        rectangle = (
            min(x for x, _y in corners),
            min(y for _x, y in corners),
            max(x for x, _y in corners),
            max(y for _x, y in corners),
        )
        drawing = text_box_pdf(text, (width, height), self.color) if text else b""
        return new_annotation(
            Kind.TEXT_BOX,
            page.source,
            rectangle,
            self.color,
            self._author(),
            text=text,
            text_turn=page.rotation,
            drawing=drawing,
        )

    def _on_shape_drawn(self, view: DocumentView, shape: Annotation) -> None:
        document = self._document()
        if document is None or not self.allowed:
            return
        if shape.kind is not Kind.TEXT_BOX:
            document.execute(AddAnnotations(document, [shape]))
            return
        page, corner, width = self._text_box_frame
        position = document.page_position(page.source)
        if position is None:
            return
        editor = view.write_text_box(position, corner, width, self.color)
        done = editor.on_done

        def write(text: str | None) -> None:
            done(text)
            if text and self.allowed:
                document.execute(AddAnnotations(document, [self._text_box(page, corner, width, text)]))

        editor.on_done = write

    def _on_page_clicked(self, view: DocumentView, click: PageClick) -> None:
        """With the comment tool, a click shows where the comment goes and asks for its text."""
        page = click.page
        square = view.upright_square(page, *click.point, COMMENT_SIZE)
        if self.tool is not Tool.COMMENT or square is None or not self.allowed:
            return
        color, author = self.color, self._author()
        view.set_preview(new_annotation(Kind.COMMENT, page, square, color, author))

        def make(text: str) -> None:
            document = self._document()
            if document is not None and self.allowed:
                comment = new_annotation(Kind.COMMENT, page, square, color, author, text=text)
                document.execute(AddAnnotations(document, [comment]))

        popover = CommentPopover(make)
        popover.set_parent(view)
        # Pointing at the whole bubble, so that the popover opens below it without covering it.
        side = COMMENT_SIZE * view.zoom
        place = Gdk.Rectangle()
        place.x, place.y = (int(value - side / 2) for value in click.view_point)
        place.width = place.height = int(side)
        popover.set_pointing_to(place)
        popover.connect("closed", self._on_comment_closed)
        self.comment_popover = popover
        popover.popup()

    def _on_comment_closed(self, popover: Gtk.Popover) -> None:
        """Whether the comment was made or cancelled, it is no longer being made."""
        self._document_view.set_preview(None)
        self.comment_popover = None
        # Taken from the view once closed, after the popover has finished closing.
        GLib.idle_add(popover.unparent)

    def _on_text_selected(self, _view: DocumentView) -> None:
        """With a tool that marks text, the text just selected is marked (H1)."""
        if self.tool in MARKING_TOOLS:
            self.mark_selection(self.tool)

    def _on_color_chosen(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        if value.get_string() in ANNOTATION_COLORS:
            action.set_state(value)
            self._chosen_color = value.get_string()
            self._toolbar.show_color(self._chosen_color)
