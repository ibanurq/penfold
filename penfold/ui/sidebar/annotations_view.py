"""The Annotations view of the side panel (02-interfaz, 6.3; D24, D25): annotations grouped by type.

Phase 2 lists them, filters them by type and goes to one on a click. Selecting them to edit their colour or text, and
deleting them, come with phase 6.
"""

import time
from gettext import gettext as _
from typing import ClassVar

from gi.repository import Gdk, Gio, GLib, GObject, Graphene, Gtk, Pango

from penfold.document.annotations import TEXT_MARKUPS, Annotation, Kind
from penfold.document.document import OpenDocument
from penfold.rendering.page_content import PageContent
from penfold.rendering.renderer import Renderer
from penfold.ui.sidebar.view_header import RecentUse, empty_label, view_header

# Foreign annotations without a colour, or white, are shown in this orange so they can be seen (as in 0.6).
FALLBACK_COLOR = (0xC6 / 255, 0x46 / 255, 0)
COLOR_BAR_WIDTH = 3
ROW_TEXT_LINES = 4
# Marked texts are read a few at a time, for at most this long (seconds) each time, so the window never waits.
TEXT_TIME_SLICE = 0.008
# Shown by default, as in 0.6: the types with text of their own.
DEFAULT_KINDS = frozenset({Kind.COMMENT, Kind.TEXT_BOX})
# Icon of each type: Adwaita's when it has one, otherwise a provisional one (D37).
KIND_ICONS = {
    Kind.HIGHLIGHT: ("penfold-type-highlight-symbolic", True),
    Kind.UNDERLINE: ("format-text-underline-symbolic", False),
    Kind.STRIKE_OUT: ("format-text-strikethrough-symbolic", False),
    Kind.COMMENT: ("penfold-type-comment-symbolic", True),
    Kind.TEXT_BOX: ("penfold-type-text-box-symbolic", True),
    Kind.RECTANGLE: ("penfold-type-rectangle-symbolic", True),
    Kind.CIRCLE: ("penfold-type-circle-symbolic", True),
    Kind.ARROW: ("penfold-type-arrow-symbolic", True),
    Kind.OTHER: ("penfold-type-other-symbolic", True),
}


def kind_names() -> dict[Kind, str]:
    """Plural name of each type, as in the filter (translated when called)."""
    return {
        Kind.HIGHLIGHT: _("Highlights"),
        Kind.UNDERLINE: _("Underlines"),
        Kind.STRIKE_OUT: _("Strikethroughs"),
        Kind.COMMENT: _("Comments"),
        Kind.TEXT_BOX: _("Text Boxes"),
        Kind.RECTANGLE: _("Rectangles"),
        Kind.CIRCLE: _("Circles"),
        Kind.ARROW: _("Arrows"),
        Kind.OTHER: _("Other Types"),
    }


def display_color(annotation: Annotation) -> tuple[float, float, float]:
    """The colour of the line next to the row: the annotation's, or orange if it has none or is white."""
    color = annotation.color
    if color is None or (not annotation.is_own and min(color) > 0.95):  # noqa: PLR2004 (white)
        return FALLBACK_COLOR
    return color


class ColorBar(Gtk.Widget):
    """The thin vertical line in the colour of an annotation."""

    __gtype_name__ = "PenfoldColorBar"

    def __init__(self) -> None:
        """Create the line; set_color gives it its colour."""
        super().__init__()
        self._color = Gdk.RGBA()
        self.set_size_request(COLOR_BAR_WIDTH, -1)

    def set_color(self, color: tuple[float, float, float]) -> None:
        """Paint the line in a colour."""
        self._color.red, self._color.green, self._color.blue = color
        self._color.alpha = 1.0
        self.queue_draw()

    def do_snapshot(self, snapshot: Gtk.Snapshot) -> None:
        """Fill the whole widget with the colour."""
        snapshot.append_color(self._color, Graphene.Rect().init(0, 0, self.get_width(), self.get_height()))


class AnnotationItem(GObject.Object):
    """One annotation in the list model."""

    __gtype_name__ = "PenfoldAnnotationItem"

    def __init__(self, annotation: Annotation) -> None:
        """Wrap an annotation of the document."""
        super().__init__()
        self.annotation = annotation


class AnnotationRow(Gtk.Box):
    """Like Papers: "Page N" in bold and the author on the right; under them, the text next to a colour line."""

    __gtype_name__ = "PenfoldAnnotationRow"

    def __init__(self) -> None:
        """Create the row's widgets; the list fills them for each annotation it shows."""
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin_top=6, margin_bottom=6)
        self.annotation: Annotation | None = None
        top = Gtk.Box(spacing=6)
        self.page = Gtk.Label(xalign=0, hexpand=True)
        self.page.add_css_class("heading")
        self.author = Gtk.Label(xalign=1, ellipsize=Pango.EllipsizeMode.END)
        self.author.add_css_class("dim-label")
        top.append(self.page)
        top.append(self.author)
        bottom = Gtk.Box(spacing=8)
        self.color_bar = ColorBar()
        self.body = Gtk.Label(xalign=0, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR, lines=ROW_TEXT_LINES)
        self.body.set_ellipsize(Pango.EllipsizeMode.END)
        self.body.set_hexpand(True)
        bottom.append(self.color_bar)
        bottom.append(self.body)
        self.append(top)
        self.append(bottom)

    def show_text(self, text: str | None) -> None:
        """Show the annotation's text, "No text" if it has none, or nothing while it is being read (None)."""
        if text:
            self.body.set_label(text)
            self.body.remove_css_class("dim-label")
        elif text is None:
            self.body.set_label("")
        else:
            self.body.set_markup(f"<i>{GLib.markup_escape_text(_('No text'))}</i>")
            self.body.add_css_class("dim-label")


class AnnotationsView(Gtk.Box):
    """Annotations grouped by type, with a filter; "annotation-activated" gives a page and a height on a click.

    The list only makes rows for the annotations in sight, so a PDF with thousands of them costs no more than one
    with a few; the text a highlight marks is read for the rows shown, a few at a time.
    """

    __gtype_name__ = "PenfoldAnnotationsView"
    __gsignals__: ClassVar = {
        "annotation-activated": (GObject.SignalFlags.RUN_FIRST, None, (int, float)),
    }

    def __init__(self) -> None:
        """Create the view, empty until set_document."""
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.shown_kinds: set[Kind] = set(DEFAULT_KINDS)
        self.filter_button = Gtk.MenuButton(
            icon_name="penfold-filter-symbolic", tooltip_text=_("Filter"), valign=Gtk.Align.CENTER
        )
        self.filter_button.add_css_class("provisional-icon")
        self.filter_button.set_popover(self._filter_popover())
        self.append(view_header(_("Annotations"), self.filter_button))
        self.document: OpenDocument | None = None
        self.content: PageContent | None = None
        self.renderer: Renderer | None = None
        # The annotations of the pages the document still has, and where each page is now.
        self._present: list[Annotation] = []
        self._positions: dict[int, int] = {}
        self._kind_names = kind_names()
        self._page_format = _("Page {label}")
        self._counts: dict[Kind, int] = {}
        # Every annotation, in the order of the groups; a filter keeps the types shown and a sorter makes the groups.
        self.store = Gio.ListStore.new(AnnotationItem)
        self.filter = Gtk.CustomFilter.new(self._is_shown)
        filtered = Gtk.FilterListModel(model=self.store, filter=self.filter)
        order = list(Kind)
        groups = Gtk.CustomSorter.new(_compare, order)
        self.model = Gtk.SortListModel(model=filtered, section_sorter=groups)
        self.selection = Gtk.MultiSelection(model=self.model)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_setup)
        factory.connect("bind", self._on_bind)
        factory.connect("unbind", self._on_unbind)
        headers = Gtk.SignalListItemFactory()
        headers.connect("setup", self._on_header_setup)
        headers.connect("bind", self._on_header_bind)
        self.list = Gtk.ListView(model=self.selection, factory=factory, header_factory=headers)
        self.list.add_css_class("navigation-sidebar")
        self._recent_use = RecentUse(self.list)
        self.reading_page = -1
        self._rows: dict[int, AnnotationRow] = {}
        self._texts: dict[int, str] = {}
        self._pending_texts: dict[AnnotationRow, Annotation] = {}
        self._filling = False
        self.empty = empty_label("")
        self.stack = Gtk.Stack(vexpand=True)
        self.scrolled = Gtk.ScrolledWindow(child=self.list, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.stack.add_named(self.scrolled, "list")
        self.stack.add_named(self.empty, "empty")
        self.append(self.stack)

    def set_document(self, document: OpenDocument, content: PageContent, renderer: Renderer) -> None:
        """List the annotations of a PDF; the renderer says where their pages are shown."""
        self.document, self.content, self.renderer = document, content, renderer
        self._texts.clear()
        self.pages_changed()

    def pages_changed(self) -> None:
        """List the annotations again after the pages were moved, turned or deleted: by group, page and position."""
        document = self.document
        if document is None:
            return
        self._rows.clear()
        self._pending_texts.clear()
        self._positions = {}
        for annotation in document.annotations:
            position = document.page_position(annotation.page)
            if position is not None:
                self._positions[annotation.page] = position
        order = list(Kind)
        self._present = sorted(
            (annotation for annotation in document.annotations if annotation.page in self._positions),
            key=lambda item: (order.index(item.kind), self._positions[item.page], item.rectangle[1], item.rectangle[0]),
        )
        self.store.splice(0, self.store.get_n_items(), [AnnotationItem(annotation) for annotation in self._present])
        self.refresh()

    def position(self, annotation: Annotation) -> int:
        """Where the page of a listed annotation is now."""
        return self._positions[annotation.page]

    def refresh(self) -> None:
        """Show the annotations of the types chosen in the filter, without building the list again."""
        document = self.document
        if document is None:
            return
        self._counts = {}
        for annotation in self._present:
            if annotation.kind in self.shown_kinds:
                self._counts[annotation.kind] = self._counts.get(annotation.kind, 0) + 1
        self.filter.changed(Gtk.FilterChange.DIFFERENT)
        if self._counts:
            self.stack.set_visible_child_name("list")
            if self.reading_page >= 0:
                page, self.reading_page = self.reading_page, -1
                self.show_reading_page(page)
        else:
            self.empty.set_label(
                _("No annotations of the types shown") if self._present else _("This PDF has no annotations")
            )
            self.stack.set_visible_child_name("empty")

    def shown_annotations(self) -> list[Annotation]:
        """The annotations in the list, in their order."""
        items = [self.model.get_item(index) for index in range(self.model.get_n_items())]
        return [item.annotation for item in items if isinstance(item, AnnotationItem)]

    def bound_rows(self) -> list[AnnotationRow]:
        """The rows the list has made for the annotations in sight."""
        return list(self._rows.values())

    def show_reading_page(self, page: int) -> None:
        """Mark the annotations of the page being read, and bring the first into sight unless the list is in use."""
        changed = page != self.reading_page
        self.reading_page = page
        for row in self._rows.values():
            self._show_mark(row)
        if not changed or self._recent_use.recently:
            return
        for index, annotation in enumerate(self.shown_annotations()):
            if self.position(annotation) == page:
                self.list.scroll_to(index, Gtk.ListScrollFlags.NONE, None)
                break

    def _show_mark(self, row: AnnotationRow) -> None:
        if row.annotation is not None and self.position(row.annotation) == self.reading_page:
            row.add_css_class("reading-position")
        else:
            row.remove_css_class("reading-position")

    def _is_shown(self, item: GObject.Object) -> bool:
        return isinstance(item, AnnotationItem) and item.annotation.kind in self.shown_kinds

    # Rows.

    def _on_setup(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        row = AnnotationRow()
        click = Gtk.GestureClick()
        click.connect("released", self._on_row_clicked, row)
        row.add_controller(click)
        item.set_child(row)

    def _on_bind(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        annotation_item = item.get_item()
        row = item.get_child()
        assert isinstance(annotation_item, AnnotationItem)
        assert isinstance(row, AnnotationRow)
        annotation = annotation_item.annotation
        row.annotation = annotation
        position = self.position(annotation)
        label = self.document.page_label(position) if self.document is not None else str(position + 1)
        row.page.set_label(self._page_format.format(label=label))
        row.author.set_label(annotation.author or _("(External)"))
        row.color_bar.set_color(display_color(annotation))
        self._rows[id(annotation)] = row
        self._show_mark(row)
        if id(annotation) in self._texts or not self._needs_marked_text(annotation):
            row.show_text(self._texts.get(id(annotation), annotation.text))
        else:
            row.show_text(None)
            self._pending_texts[row] = annotation
            if not self._filling:
                self._filling = True
                GLib.idle_add(self._fill_texts)

    def _on_unbind(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        row = item.get_child()
        if isinstance(row, AnnotationRow) and row.annotation is not None:
            if self._rows.get(id(row.annotation)) is row:
                del self._rows[id(row.annotation)]
            self._pending_texts.pop(row, None)
            row.remove_css_class("reading-position")

    def _needs_marked_text(self, annotation: Annotation) -> bool:
        return not annotation.text and annotation.kind in TEXT_MARKUPS and self.content is not None

    def _fill_texts(self) -> bool:
        """Read the text marked by the highlights shown, for a short time; go on later if some are left."""
        deadline = time.monotonic() + TEXT_TIME_SLICE
        while self._pending_texts and time.monotonic() < deadline and self.content is not None:
            row, annotation = next(iter(self._pending_texts.items()))
            del self._pending_texts[row]
            if id(annotation) not in self._texts:
                areas = list(annotation.quads) or [annotation.rectangle]
                marked = self.content.text_in_areas(annotation.page, areas)
                self._texts[id(annotation)] = f"“{marked}”" if marked else ""
            if row.annotation is annotation:
                row.show_text(self._texts[id(annotation)])
        if self._pending_texts and self.content is not None:
            return GLib.SOURCE_CONTINUE
        self._filling = False
        return GLib.SOURCE_REMOVE

    def _on_row_clicked(
        self, gesture: Gtk.GestureClick, _presses: int, _x: float, _y: float, row: AnnotationRow
    ) -> None:
        """A click without Ctrl or Shift goes to the annotation (its height on the top third, B8)."""
        if gesture.get_current_event_state() & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK):
            return
        annotation = row.annotation
        if annotation is None or self.renderer is None:
            return
        place = self.renderer.layout.place(annotation.page, annotation.rectangle[1])
        if place is not None:
            page, top = place
            self.emit("annotation-activated", page, -1.0 if top is None else top)

    # Group headings.

    def _on_header_setup(self, _factory: Gtk.SignalListItemFactory, header: Gtk.ListHeader) -> None:
        label = Gtk.Label(xalign=0, margin_start=6, margin_top=12, margin_bottom=2)
        label.add_css_class("caption-heading")
        label.add_css_class("dim-label")
        header.set_child(label)

    def _on_header_bind(self, _factory: Gtk.SignalListItemFactory, header: Gtk.ListHeader) -> None:
        """A heading with the type and its count above each group: "Comments (2)"."""
        item = header.get_item()
        label = header.get_child()
        if isinstance(item, AnnotationItem) and isinstance(label, Gtk.Label):
            kind = item.annotation.kind
            # Translators: heading of a group of annotations, as in "Comments (2)".
            label.set_label(_("{kind} ({count})").format(kind=self._kind_names[kind], count=self._counts.get(kind, 0)))

    def _filter_popover(self) -> Gtk.Popover:
        """The list "Show" with a box and an icon for each type (D24)."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_top=6, margin_bottom=6)
        title = Gtk.Label(label=_("Show"), xalign=0, margin_start=6, margin_bottom=4)
        title.add_css_class("dim-label")
        box.append(title)
        names = kind_names()
        for kind in Kind:
            row = Gtk.Box(spacing=8)
            check = Gtk.CheckButton(active=kind in self.shown_kinds)
            check.connect("toggled", self._on_kind_toggled, kind)
            icon_name, provisional = KIND_ICONS[kind]
            icon = Gtk.Image(icon_name=icon_name)
            if provisional:
                icon.add_css_class("provisional-icon")
            row.append(icon)
            row.append(Gtk.Label(label=names[kind], xalign=0))
            check.set_child(row)
            box.append(check)
        return Gtk.Popover(child=box)

    def _on_kind_toggled(self, check: Gtk.CheckButton, kind: Kind) -> None:
        if check.get_active():
            self.shown_kinds.add(kind)
        else:
            self.shown_kinds.discard(kind)
        self.refresh()


def _compare(first: object, second: object, order: list[Kind]) -> int:
    """Order two annotations by the group of their type (the order of the filter)."""
    assert isinstance(first, AnnotationItem)
    assert isinstance(second, AnnotationItem)
    difference = order.index(first.annotation.kind) - order.index(second.annotation.kind)
    return (difference > 0) - (difference < 0)
