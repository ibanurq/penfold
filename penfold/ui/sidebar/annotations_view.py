"""The Annotations view of the side panel (02-interfaz, 6.3; D24, D25, D64): annotations in four groups.

It lists them, filters them by group and goes to one on a click. Rows are selected as in Pages and Bookmarks, and
the selection is cleared the same way (D47). A right click on a row, a long press, or the Menu key (or Shift+F10)
asks for the menu of its annotation, the same as on the page (D72).
"""

import time
from gettext import gettext as _
from typing import ClassVar

from gi.repository import Gdk, Gio, GLib, GObject, Graphene, Gtk, Pango

from penfold.document.annotations import TEXT_MARKUPS, Annotation, AnnotationGroup, Kind
from penfold.document.document import OpenDocument
from penfold.rendering.page_content import PageContent
from penfold.rendering.renderer import Renderer
from penfold.ui.annotation_icons import KIND_ICONS
from penfold.ui.context_menu import is_menu_key
from penfold.ui.sidebar.view_header import RecentUse, empty_label, unselect_all, unselect_on_empty_click, view_header

# Foreign annotations without a colour, or white, are shown in this orange so they can be seen (as in 0.6).
FALLBACK_COLOR = (0xC6 / 255, 0x46 / 255, 0)
COLOR_BAR_WIDTH = 3
ROW_TEXT_LINES = 4
# Marked texts are read a few at a time, for at most this long (seconds) each time, so the window never waits.
TEXT_TIME_SLICE = 0.008
# The actions of the filter's menu, one for each group: "annotations-filter.shapes".
FILTER_ACTIONS = "annotations-filter"
# Shown by default: all four groups (D76).
DEFAULT_GROUPS = frozenset(AnnotationGroup)


def group_names() -> dict[AnnotationGroup, str]:
    """Name of each group, as in the print dialogue (translated when called)."""
    return {
        AnnotationGroup.TEXT_MARKUPS: _("Text Highlights"),
        AnnotationGroup.SHAPES: _("Shapes"),
        AnnotationGroup.TEXT_ELEMENTS: _("Text Elements"),
        AnnotationGroup.OTHERS: _("Other Types"),
    }


def display_color(annotation: Annotation) -> tuple[float, float, float]:
    """The colour of the line next to the row: the annotation's, or orange if it has none or is white."""
    color = annotation.color
    if color is None or (not annotation.managed and min(color) > 0.95):  # noqa: PLR2004 (white)
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
    """Like Papers, with the type's icon before "Page N"; the author on the right; under them, the coloured text."""

    __gtype_name__ = "PenfoldAnnotationRow"

    def __init__(self) -> None:
        """Create the row's widgets; the list fills them for each annotation it shows."""
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin_top=6, margin_bottom=6)
        self.add_css_class("annotation-row")
        self.annotation: Annotation | None = None
        top = Gtk.Box(spacing=6)
        self.icon = Gtk.Image()
        self.page = Gtk.Label(xalign=0, hexpand=True)
        self.page.add_css_class("heading")
        self.author = Gtk.Label(xalign=1, ellipsize=Pango.EllipsizeMode.END)
        self.author.add_css_class("dim-label")
        top.append(self.icon)
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

    def show_kind(self, kind: Kind) -> None:
        """Show the icon of the annotation's type."""
        self.icon.set_from_icon_name(KIND_ICONS[kind])

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
    """Annotations in four groups, with a filter; "annotation-activated" gives a page and a height on a click.

    The list only makes rows for the annotations in sight, so a PDF with thousands of them costs no more than one
    with a few; the text a highlight marks is read for the rows shown, a few at a time.
    """

    __gtype_name__ = "PenfoldAnnotationsView"
    __gsignals__: ClassVar = {
        "annotation-activated": (GObject.SignalFlags.RUN_FIRST, None, (int, float)),
        # The menu of an annotation is wanted at a point of the view: the annotation, x and y.
        "menu-requested": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT, float, float)),
    }

    def __init__(self) -> None:
        """Create the view, empty until set_document."""
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.shown_groups: set[AnnotationGroup] = set(DEFAULT_GROUPS)
        self.filter_button = Gtk.MenuButton(
            icon_name="penfold-filter-symbolic", tooltip_text=_("Filter"), valign=Gtk.Align.CENTER
        )
        self.insert_action_group(FILTER_ACTIONS, self._filter_actions())
        self.filter_button.set_popover(self._filter_popover())
        self.append(view_header(_("Annotations"), self.filter_button))
        self.document: OpenDocument | None = None
        self.content: PageContent | None = None
        self.renderer: Renderer | None = None
        # The annotations of the pages the document still has, and where each page is now.
        self._present: list[Annotation] = []
        self._positions: dict[int, int] = {}
        self._group_names = group_names()
        self._page_format = _("Page {label}")
        self._counts: dict[AnnotationGroup, int] = {}
        # Every annotation, in the order of the groups; a filter keeps the groups shown and a sorter makes the sections.
        self.store = Gio.ListStore.new(AnnotationItem)
        self.filter = Gtk.CustomFilter.new(self._is_shown)
        filtered = Gtk.FilterListModel(model=self.store, filter=self.filter)
        groups = Gtk.CustomSorter.new(_compare, list(AnnotationGroup))
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
        unselect_on_empty_click(self.scrolled, self.selection)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key_pressed)
        self.list.add_controller(keys)
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
        order = list(AnnotationGroup)
        self._present = sorted(
            (annotation for annotation in document.annotations if annotation.page in self._positions),
            key=lambda item: (
                order.index(item.group),
                self._positions[item.page],
                item.rectangle[1],
                item.rectangle[0],
            ),
        )
        self._count()  # Before the rows, so that their headings show the new counts.
        self.store.splice(0, self.store.get_n_items(), [AnnotationItem(annotation) for annotation in self._present])
        self.refresh()

    def annotations_changed(self) -> None:
        """List the annotations again after one was added (or the addition undone)."""
        self.pages_changed()

    def position(self, annotation: Annotation) -> int:
        """Where the page of a listed annotation is now."""
        return self._positions[annotation.page]

    def refresh(self) -> None:
        """Show the annotations of the groups chosen in the filter, without building the list again."""
        document = self.document
        if document is None:
            return
        self._count()
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

    def _count(self) -> None:
        """Count the annotations of each group shown, for the headings."""
        self._counts = {}
        for annotation in self._present:
            if annotation.group in self.shown_groups:
                self._counts[annotation.group] = self._counts.get(annotation.group, 0) + 1

    def shown_annotations(self) -> list[Annotation]:
        """The annotations in the list, in their order."""
        items = [self.model.get_item(index) for index in range(self.model.get_n_items())]
        return [item.annotation for item in items if isinstance(item, AnnotationItem)]

    def selected_annotations(self) -> list[Annotation]:
        """The annotations selected, in the order of the list."""
        selected = self.selection.get_selection()
        items = [self.model.get_item(selected.get_nth(index)) for index in range(selected.get_size())]
        return [item.annotation for item in items if isinstance(item, AnnotationItem)]

    def unselect_all(self) -> bool:
        """Clear the selection (Esc, D47); return whether anything was selected."""
        return unselect_all(self.selection)

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
            row.add_css_class("reading-section")
        else:
            row.remove_css_class("reading-section")

    def _is_shown(self, item: GObject.Object) -> bool:
        return isinstance(item, AnnotationItem) and item.annotation.group in self.shown_groups

    # Rows.

    def _on_setup(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        row = AnnotationRow()
        click = Gtk.GestureClick()
        click.connect("released", self._on_row_clicked, row)
        row.add_controller(click)
        right_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right_click.connect("pressed", lambda _gesture, _presses, x, y: self._ask_for_menu(row, x, y))
        row.add_controller(right_click)
        long_press = Gtk.GestureLongPress(touch_only=True)
        long_press.connect("pressed", lambda _gesture, x, y: self._ask_for_menu(row, x, y))
        row.add_controller(long_press)
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
        row.show_kind(annotation.kind)
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
            row.remove_css_class("reading-section")

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

    def _ask_for_menu(self, row: AnnotationRow, x: float, y: float) -> None:
        """Ask for the menu of a row's annotation at a point of the row; a row not selected is selected alone."""
        annotation = row.annotation
        if annotation is None:
            return
        if not any(item is annotation for item in self.selected_annotations()):
            index = next((i for i, item in enumerate(self.shown_annotations()) if item is annotation), None)
            if index is not None:
                self.selection.select_item(index, True)
        found, point = row.compute_point(self, Graphene.Point().init(x, y))
        if found:
            self.emit("menu-requested", annotation, point.x, point.y)

    def _on_key_pressed(
        self, _controller: Gtk.EventControllerKey, keyval: int, _keycode: int, state: Gdk.ModifierType
    ) -> bool:
        """The Menu key, or Shift+F10, asks for the menu of the first annotation selected."""
        return is_menu_key(keyval, state) and self.open_menu()

    def open_menu(self) -> bool:
        """Ask for the menu of the first annotation selected, at its row if it is shown; return whether it did."""
        selected = self.selected_annotations()
        row = self._rows.get(id(selected[0])) if selected else None
        if row is None or not row.get_mapped():
            return False
        self._ask_for_menu(row, row.get_width() / 2, row.get_height() / 2)
        return True

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
        """A heading with the group and its count above each section: "Text Elements (2)"."""
        item = header.get_item()
        label = header.get_child()
        if isinstance(item, AnnotationItem) and isinstance(label, Gtk.Label):
            group = item.annotation.group
            # Translators: heading of a group of annotations, as in "Text Elements (2)".
            label.set_label(
                _("{group} ({count})").format(group=self._group_names[group], count=self._counts.get(group, 0))
            )

    def _filter_actions(self) -> Gio.SimpleActionGroup:
        """One action with a true or false state for each group: whether the list shows it."""
        actions = Gio.SimpleActionGroup()
        for group in AnnotationGroup:
            action = Gio.SimpleAction.new_stateful(
                group.value, None, GLib.Variant.new_boolean(group in self.shown_groups)
            )
            action.connect("change-state", self._on_group_toggled, group)
            actions.add_action(action)
        return actions

    def _filter_popover(self) -> Gtk.Popover:
        """A box for each group (D64). Unlike a menu, it stays open to tick several; Esc or a click outside close it."""
        boxes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_top=6, margin_bottom=6)
        for group, name in group_names().items():
            boxes.append(Gtk.CheckButton(label=name, action_name=f"{FILTER_ACTIONS}.{group.value}"))
        return Gtk.Popover(child=boxes)

    def _on_group_toggled(self, action: Gio.SimpleAction, state: GLib.Variant, group: AnnotationGroup) -> None:
        action.set_state(state)
        if state.get_boolean():
            self.shown_groups.add(group)
        else:
            self.shown_groups.discard(group)
        self.refresh()


def _compare(first: object, second: object, order: list[AnnotationGroup]) -> int:
    """Order two annotations by their group (the order of the filter)."""
    assert isinstance(first, AnnotationItem)
    assert isinstance(second, AnnotationItem)
    difference = order.index(first.annotation.group) - order.index(second.annotation.group)
    return (difference > 0) - (difference < 0)
