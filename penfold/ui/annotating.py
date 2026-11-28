"""Annotating from the window: the pencil, the annotation bar, and the tool and colour chosen.

The pencil shows and hides the bar; hiding it goes back to Select Text. A tool stays chosen after an annotation is made,
until another is chosen. A PDF is only annotated if it allows it: otherwise the pencil is greyed out.

The tools that mark text (highlight, underline, squiggly underline, strike through) mark what is selected when the
mouse is released. H and U mark the text selected without changing the tool, or else choose their tool. Rectangles,
circles and arrows are drawn by dragging, from where the drag starts to where it ends; a freehand stroke follows the
drag, and is smoothed a little when the mouse is released (document/freehand.py). A click places a comment, whose
text is written in a popover. A drag sets the width of a text box (a click gives it a usual width), whose text is
written on the page. The image tool first asks for the image's file; then a frame of its size follows the pointer, and
a click puts it on the page (ui/image_placing.py). Once it is put, or if the file is not chosen or cannot be
read, or with Esc, the tool chosen before comes back. The stamp tool does the same with the stamp chosen in its menu
(ui/annotation_toolbar.py), in its own colour, with its word in the interface's language; closing the menu without
choosing one brings the tool before back.
"""

from collections.abc import Callable
from dataclasses import replace
from gettext import gettext as _
from pathlib import Path

from gi.repository import Gdk, Gio, GLib, Gtk

from penfold.document.annotations import Annotation, Kind, default_style, new_annotation
from penfold.document.appearance import COMMENT_SIZE
from penfold.document.commands.annotations import AddAnnotations
from penfold.document.document import OpenDocument
from penfold.document.freehand import freehand_rectangle, smoothed
from penfold.document.geometry import Rectangle, bounds
from penfold.document.image_files import image_from_file
from penfold.document.reshaping import SMALLEST_SIZE
from penfold.document.stamps import STAMPS
from penfold.errors import ImageOpenError
from penfold.rendering.layout import ShownPage
from penfold.rendering.stamp_look import stamp_drawing, stamp_size
from penfold.rendering.text_box import DEFAULT_WIDTH, NARROWEST, text_box_pdf, text_height
from penfold.ui.annotation_icons import stamp_name
from penfold.ui.annotation_toolbar import AnnotationToolbar, Tool
from penfold.ui.comment_popover import CommentPopover
from penfold.ui.document_view import DocumentView, PageClick
from penfold.ui.file_dialogs import image_file_dialog
from penfold.ui.palette import ANNOTATION_COLORS, Color, hex_to_color

Point = tuple[float, float]
# Over the pages, the cursor of the tools that draw; the others select text, with the view's own cursor.
DRAWING_CURSOR = "crosshair"
DRAWING_TOOLS = frozenset(
    {Tool.RECTANGLE, Tool.CIRCLE, Tool.ARROW, Tool.FREEHAND, Tool.COMMENT, Tool.TEXT_BOX, Tool.IMAGE, Tool.STAMP}
)
# The tools that put one thing on a page, and then give way to the tool chosen before.
PLACING_TOOLS = frozenset({Tool.IMAGE, Tool.STAMP})
MARKING_TOOLS = frozenset({Tool.HIGHLIGHT, Tool.UNDERLINE, Tool.SQUIGGLY, Tool.STRIKE_OUT})
SHAPE_TOOLS = frozenset({Tool.RECTANGLE, Tool.CIRCLE, Tool.ARROW})


class Annotating:
    """The window's actions "annotate" (the pencil), "annotation-tool" and "annotation-color"."""

    def __init__(  # noqa: PLR0913 (the window, what it shows and what it is told)
        self,
        window: Gtk.ApplicationWindow,
        toolbar: AnnotationToolbar,
        document_view: DocumentView,
        document: Callable[[], OpenDocument | None],
        author: Callable[[], str],
        *,
        notify: Callable[[str], None],
    ) -> None:
        """Add the actions to the window.

        document gives the document shown, if any; author, the preference; notify shows a short message (a toast).
        """
        self._window = window
        self._notify = notify
        self._toolbar = toolbar
        self._author = author
        self._document_view = document_view
        self._document = document
        self._chosen_tool = Tool.SELECT
        # The tool that comes back once an image or a stamp is put; the image being put: its file, its size as seen
        # (points) and its drawings, by the turns of the page they are made for (the PDF's and Penfold's); and the
        # name of the stamp being put.
        self._before_placing = Tool.SELECT
        self._image: tuple[Path, tuple[float, float], dict[tuple[int, int], bytes]] | None = None
        self._stamp: str | None = None
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
        self._put_stamp_action = Gio.SimpleAction.new("put-stamp", GLib.VariantType.new("s"))
        self._put_stamp_action.connect("activate", lambda _action, name: self.place_stamp(name.get_string()))
        for action in (self._annotate, self._tool, self._color, self._put_stamp_action):
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

    def show_bar(self) -> None:
        """Show the annotation bar, as pressing the pencil does, if the document shown may be annotated."""
        if self.allowed and not self.bar_shown:
            self._annotate.change_state(GLib.Variant.new_boolean(True))

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

    def leave_tool(self) -> None:
        """Esc: from the image and stamp tools, back to the tool chosen before; from the others, to Select Text."""
        self.choose(self._before_placing if self.tool in PLACING_TOOLS else Tool.SELECT)

    def mark_or_choose(self, tool: Tool) -> bool:
        """H and U: mark the text selected with this tool's mark, or else choose it; return whether done."""
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
        if Tool(value.get_string()) in PLACING_TOOLS and self.tool not in PLACING_TOOLS:
            self._before_placing = self.tool
        action.set_state(value)
        self._chosen_tool = Tool(value.get_string())
        self._image = None
        self._stamp = None
        self._document_view.stop_placing_image()
        self._document_view.marking = self.tool in MARKING_TOOLS
        makers = {
            **dict.fromkeys(SHAPE_TOOLS, self._make_shape),
            Tool.FREEHAND: self._draw_freehand,
            Tool.TEXT_BOX: self._frame_text_box,
        }
        self._document_view.set_shape_maker(makers.get(self.tool))
        self._document_view.placing = self.tool is Tool.COMMENT
        self._document_view.set_fields_active(self.tool is Tool.SELECT)
        self._document_view.set_drawing_cursor(DRAWING_CURSOR if self.tool in DRAWING_TOOLS else None)
        if self.tool is Tool.IMAGE:
            image_file_dialog().open(self._window, None, self._on_image_file_chosen)
        elif self.tool is Tool.STAMP:
            self._toolbar.show_stamp_menu(self._on_stamp_menu_closed)

    def _on_image_file_chosen(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            chosen = dialog.open_finish(result)
        except GLib.Error:  # Cancelled.
            chosen = None
        path = None if chosen is None else chosen.get_path()
        if self.tool is not Tool.IMAGE:
            return  # Another tool was chosen meanwhile.
        if path is None:
            self.choose(self._before_placing)
            return
        self.place_image(Path(path))

    def place_image(self, path: Path) -> None:
        """Show where the image of a file goes, following the pointer, until a click puts it on a page."""
        try:
            drawing, size = image_from_file(path)
        except ImageOpenError:
            self._notify(_("The image could not be opened"))
            self.choose(self._before_placing)
            return
        self._image = (path, size, {(0, 0): drawing})
        self._document_view.place_image(size, self._put_image)

    def _put_image(self, page: ShownPage, shown: Rectangle) -> None:
        """Put the image being placed on a page, in a rectangle of the page as shown; the tool before comes back."""
        document, image = self._document(), self._image
        if document is None or image is None or not self.allowed:
            self.choose(self._before_placing)
            return
        path, _size, drawings = image
        turns = (document.own_rotation(page.source), page.rotation)
        try:
            drawing = drawings.get(turns) or image_from_file(path, *turns)[0]
        except ImageOpenError:
            self._notify(_("The image could not be opened"))
            self.choose(self._before_placing)
            return
        made = new_annotation(Kind.IMAGE, page.source, _unturned(page, shown), None, self._author(), drawing=drawing)
        document.execute(AddAnnotations(document, [made]))
        self.choose(self._before_placing)

    def place_stamp(self, name: str) -> None:
        """Show where one of Penfold's stamps goes, following the pointer, until a click puts it on a page.

        It is chosen in the stamp tool's menu, with the tool chosen.
        """
        if name not in STAMPS or not self.allowed or self.tool is not Tool.STAMP:
            return
        self._stamp = name
        self._document_view.place_image(stamp_size(stamp_name(name)), self._put_stamp)

    def _on_stamp_menu_closed(self) -> None:
        """Closed without choosing a stamp, the menu brings the tool chosen before back."""
        if self.tool is Tool.STAMP and self._stamp is None:
            self.choose(self._before_placing)

    def _put_stamp(self, page: ShownPage, shown: Rectangle) -> None:
        """Put the stamp being placed on a page, in a rectangle of the page as shown; the tool before comes back."""
        document, name = self._document(), self._stamp
        if document is None or name is None or not self.allowed:
            self.choose(self._before_placing)
            return
        color = STAMPS[name].color
        turns = (document.own_rotation(page.source), page.rotation)
        drawing, _size = stamp_drawing(stamp_name(name), color, *turns)
        rectangle = _unturned(page, shown)
        made = new_annotation(Kind.STAMP, page.source, rectangle, color, self._author(), drawing=drawing, stamp=name)
        document.execute(AddAnnotations(document, [made]))
        self.choose(self._before_placing)

    def _make_shape(self, page: ShownPage, trail: list[Point]) -> Annotation | None:
        """The shape of the tool chosen from one end of a drag to the other; None for a click."""
        kind = self.tool.kind
        start, end = page.to_source(*trail[0]), page.to_source(*trail[-1])
        if kind is None or max(abs(end[0] - start[0]), abs(end[1] - start[1])) < SMALLEST_SIZE:
            return None
        rectangle = (min(start[0], end[0]), min(start[1], end[1]), max(start[0], end[0]), max(start[1], end[1]))
        line = (*start, *end) if kind is Kind.ARROW else None
        return new_annotation(kind, page.source, rectangle, self.color, self._author(), line=line)

    def _draw_freehand(self, page: ShownPage, trail: list[Point]) -> Annotation | None:
        """The stroke a drag draws, as it goes (smoothed once made); None while smaller than a shape can be."""
        stroke = tuple(page.to_source(*point) for point in trail)
        xs, ys = [x for x, _y in stroke], [y for _x, y in stroke]
        if max(max(xs) - min(xs), max(ys) - min(ys)) < SMALLEST_SIZE:
            return None
        style = default_style(Kind.FREEHAND)
        rectangle = freehand_rectangle([stroke], style.line_width)
        return new_annotation(Kind.FREEHAND, page.source, rectangle, self.color, self._author(), strokes=(stroke,))

    def _frame_text_box(self, page: ShownPage, trail: list[Point]) -> Annotation:
        """The empty text box a drag frames: as wide as the drag (a click: the usual width), inside the page."""
        shown_start, shown_end = trail[0], trail[-1]
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
        if shape.kind is Kind.FREEHAND:
            strokes = tuple(smoothed(stroke) for stroke in shape.strokes)
            shape = replace(shape, strokes=strokes, rectangle=freehand_rectangle(strokes, shape.style.line_width))
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
        """With a tool that marks text, the text just selected is marked."""
        if self.tool in MARKING_TOOLS:
            self.mark_selection(self.tool)

    def _on_color_chosen(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        if value.get_string() in ANNOTATION_COLORS:
            action.set_state(value)
            self._chosen_color = value.get_string()
            self._toolbar.show_color(self._chosen_color)


def _unturned(page: ShownPage, shown: Rectangle) -> Rectangle:
    """A rectangle of a page as shown, on the page as its PDF shows it (Penfold's turn undone)."""
    left, top, right, bottom = shown
    corners = [page.to_source(left, top), page.to_source(right, bottom)]
    xs, ys = [x for x, _y in corners], [y for _x, y in corners]
    return min(xs), min(ys), max(xs), max(ys)
