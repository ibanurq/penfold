"""The Bookmarks view of the side panel (02-interfaz, 6.2; D23): the outline as a tree.

It shows each bookmark's style and page, lets the user unfold it and go to a bookmark, and follows the reading (D40).
With bookmarks selected, a bar at the bottom edits them through the window's actions. A click away from the rows, or
Esc, clears the selection (D47).
"""

from gettext import gettext as _
from typing import ClassVar

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

from penfold.document.bookmarks import Bookmark, ReadingIndex
from penfold.document.document import OpenDocument
from penfold.rendering.renderer import Renderer
from penfold.ui.sidebar.view_header import (
    RecentUse,
    empty_label,
    header_button,
    unselect_all,
    unselect_on_empty_click,
    view_header,
)


class BookmarkItem(GObject.Object):
    """One bookmark in the tree model."""

    __gtype_name__ = "PenfoldBookmarkItem"

    def __init__(self, bookmark: Bookmark) -> None:
        """Wrap a bookmark of the document."""
        super().__init__()
        self.bookmark = bookmark


def children_model(bookmarks: list[Bookmark]) -> Gio.ListStore:
    """Return a list model with these bookmarks."""
    store = Gio.ListStore.new(BookmarkItem)
    store.splice(0, 0, [BookmarkItem(bookmark) for bookmark in bookmarks])
    return store


def title_markup(bookmark: Bookmark) -> str:
    """Return the title with its bold, italic and colour, as Pango markup."""
    text = GLib.markup_escape_text(bookmark.title or _("Untitled"))
    if bookmark.color is not None:
        red, green, blue = (round(component * 255) for component in bookmark.color)
        text = f'<span foreground="#{red:02x}{green:02x}{blue:02x}">{text}</span>'
    if bookmark.italic:
        text = f"<i>{text}</i>"
    if bookmark.bold:
        text = f"<b>{text}</b>"
    return text


class BookmarkRow(Gtk.Box):
    """Expander arrow, title and page label."""

    __gtype_name__ = "PenfoldBookmarkRow"

    def __init__(self) -> None:
        """Create the row's widgets."""
        super().__init__(spacing=6)
        self.bookmark: Bookmark | None = None
        self.expander = Gtk.TreeExpander(hexpand=True)
        self.title = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self.expander.set_child(self.title)
        self.page = Gtk.Label(xalign=1)
        self.page.add_css_class("dim-label")
        self.page.add_css_class("numeric")
        self.append(self.expander)
        self.append(self.page)


class BookmarksView(Gtk.Box):
    """The outline tree; "destination-activated" is emitted with a page and a height (-1 for none) on a click."""

    __gtype_name__ = "PenfoldBookmarksView"
    __gsignals__: ClassVar = {
        "destination-activated": (GObject.SignalFlags.RUN_FIRST, None, (int, float)),
    }

    def __init__(self) -> None:
        """Create the view, empty until set_document."""
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.expand_button = Gtk.Button(
            icon_name="penfold-expand-all-symbolic", tooltip_text=_("Expand or Collapse All"), valign=Gtk.Align.CENTER
        )
        self.expand_button.add_css_class("provisional-icon")
        self.expand_button.connect("clicked", lambda _button: self.toggle_all())
        self.append(
            view_header(
                _("Bookmarks"),
                header_button(_("_Add"), "bookmark-new-symbolic", "win.add-bookmark"),
                self.expand_button,
            )
        )
        self.document: OpenDocument | None = None
        self.renderer: Renderer | None = None
        self.tree = Gtk.TreeListModel.new(Gio.ListStore.new(BookmarkItem), False, False, self._children)
        self.selection = Gtk.MultiSelection.new(self.tree)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_setup)
        factory.connect("bind", self._on_bind)
        factory.connect("unbind", self._on_unbind)
        self.list = Gtk.ListView(model=self.selection, factory=factory)
        self.list.add_css_class("navigation-sidebar")
        # The bookmarks selected, to select them again when the outline is shown again (after undo, for example).
        self._selected: list[Bookmark] = []
        for signal in ("selection-changed", "items-changed"):
            self.selection.connect(signal, lambda *_arguments: self._remember_selection())
        self._recent_use = RecentUse(self.list)
        # Following the reading (D40): the bookmark of the section read, and the row that shows it (the bookmark
        # itself, or the folded branch that holds it).
        self._index = ReadingIndex([])
        self._reading: Bookmark | None = None
        self._marked: Bookmark | None = None
        self._rows: dict[int, BookmarkRow] = {}
        self.empty = empty_label(_("This PDF has no bookmarks"))
        self.stack = Gtk.Stack(vexpand=True)
        scrolled = Gtk.ScrolledWindow(child=self.list, hscrollbar_policy=Gtk.PolicyType.NEVER)
        unselect_on_empty_click(scrolled, self.selection)
        self.stack.add_named(scrolled, "list")
        self.stack.add_named(self.empty, "empty")
        self.append(self.stack)
        self.action_bar = self._action_bar()
        self.append(self.action_bar)

    def set_document(self, document: OpenDocument, renderer: Renderer) -> None:
        """Show the bookmarks of a PDF, unfolded as the PDF says; the renderer says where their pages are shown."""
        self.document, self.renderer = document, renderer
        self.bookmarks_changed()

    def bookmarks_changed(self) -> None:
        """Show the outline again after an edit, unfolded as each bookmark says, keeping what is still selected."""
        if self.document is None:
            return
        bookmarks = self.document.bookmarks
        selected = self._selected
        # Forget the old rows first: GTK may bind the new ones as soon as the model changes.
        self._rows.clear()
        self._reading = self._marked = None
        self._index = ReadingIndex(bookmarks, self._place)
        self.tree = Gtk.TreeListModel.new(children_model(bookmarks), False, False, self._children)
        self.selection.set_model(self.tree)
        self._open_as_stored()
        self.tree.connect("items-changed", self._on_tree_changed)
        self.stack.set_visible_child_name("list" if bookmarks else "empty")
        self.expand_button.set_sensitive(any(bookmark.children for bookmark in bookmarks))
        self.select(selected, scroll=False)

    def pages_changed(self) -> None:
        """Show the new page of each bookmark after the pages were moved, turned or deleted."""
        if self.document is None:
            return
        self._index = ReadingIndex(self.document.bookmarks, self._place)
        self._reading = None
        for row in self._rows.values():
            self._show_page(row)

    def _place(self, page: int, top: float | None) -> tuple[int, float | None] | None:
        return self.renderer.layout.place(page, top) if self.renderer is not None else None

    def _on_tree_changed(self, tree: Gtk.TreeListModel, _position: int, _removed: int, _added: int) -> None:
        """Remember which branches are unfolded, to save it (G9); it may change which row shows the reading."""
        for index in range(tree.get_n_items()):
            row = tree.get_row(index)
            item = row.get_item() if row is not None else None
            if row is not None and isinstance(item, BookmarkItem) and row.is_expandable():
                item.bookmark.is_open = row.get_expanded()
        self._mark_reading(scroll=False)

    def follow(self, page: int, top: float) -> None:
        """Mark the bookmark of the section being read, and bring it into sight unless the list is in use (D40)."""
        reading = self._index.at(page, top)
        if reading is not self._reading:
            self._reading = reading
            self._mark_reading(scroll=True)

    @property
    def marked_bookmark(self) -> Bookmark | None:
        """The bookmark whose row is marked as the section being read."""
        return self._marked

    def _mark_reading(self, scroll: bool) -> None:
        """Mark the row of the section being read: its own, or that of the folded branch that holds it."""
        positions = {}
        for index in range(self.tree.get_n_items()):
            row = self.tree.get_row(index)
            item = row.get_item() if row is not None else None
            if isinstance(item, BookmarkItem):
                positions[id(item.bookmark)] = index
        target: Bookmark | None = None
        if self._reading is not None:
            for candidate in [self._reading, *self._index.ancestors(self._reading)]:
                if id(candidate) in positions:
                    target = candidate
                    break
        previous, self._marked = self._marked, target
        for bookmark in (previous, target):
            if bookmark is not None and id(bookmark) in self._rows:
                self._show_mark(self._rows[id(bookmark)], bookmark)
        if scroll and target is not None and not self._recent_use.recently:
            self.list.scroll_to(positions[id(target)], Gtk.ListScrollFlags.NONE, None)

    def _show_mark(self, row: "BookmarkRow", bookmark: Bookmark) -> None:
        # On the row itself: the list's own row widgets belong to GTK, which may be destroying them at this point.
        if bookmark is self._marked:
            row.add_css_class("reading-position")
        else:
            row.remove_css_class("reading-position")

    def unselect_all(self) -> bool:
        """Clear the selection (Esc, D47); return whether any bookmark was selected."""
        return unselect_all(self.selection)

    def selected_bookmarks(self) -> list[Bookmark]:
        """The bookmarks selected, in the order of the outline."""
        bitset = self.selection.get_selection()
        selected = []
        for nth in range(bitset.get_size()):
            row = self.tree.get_row(bitset.get_nth(nth))
            item = row.get_item() if row is not None else None
            if isinstance(item, BookmarkItem):
                selected.append(item.bookmark)
        return selected

    def select(self, bookmarks: list[Bookmark], *, scroll: bool = True) -> None:
        """Select these bookmarks, or their copies (by key), and bring the first into sight unless told not to.

        Only bookmarks whose rows are shown can be selected.
        """
        wanted = {bookmark.key for bookmark in bookmarks}
        selected = Gtk.Bitset.new_empty()
        for index in range(self.tree.get_n_items()):
            row = self.tree.get_row(index)
            item = row.get_item() if row is not None else None
            if isinstance(item, BookmarkItem) and item.bookmark.key in wanted:
                selected.add(index)
        self.selection.set_selection(selected, Gtk.Bitset.new_range(0, self.tree.get_n_items()))
        if scroll and not selected.is_empty():
            self.list.scroll_to(selected.get_minimum(), Gtk.ListScrollFlags.NONE, None)

    def _remember_selection(self) -> None:
        self._selected = self.selected_bookmarks()
        self.action_bar.set_revealed(bool(self._selected))

    def _action_bar(self) -> Gtk.ActionBar:
        """The bar shown with bookmarks selected (02-interfaz, 6.2; D23)."""
        bar = Gtk.ActionBar(revealed=False)
        delete = Gtk.Button(
            icon_name="edit-delete-symbolic", tooltip_text=_("Delete"), action_name="win.delete-bookmarks"
        )
        delete.add_css_class("destructive-action")
        bar.pack_end(delete)
        indenting = Gtk.Box(spacing=6)
        for icon_name, tooltip, action_name in (
            ("format-indent-less-symbolic", _("Decrease Indent"), "win.outdent-bookmarks"),
            ("format-indent-more-symbolic", _("Increase Indent"), "win.indent-bookmarks"),
        ):
            indenting.append(Gtk.Button(icon_name=icon_name, tooltip_text=tooltip, action_name=action_name))
        bar.set_center_widget(indenting)
        return bar

    def toggle_all(self) -> None:
        """Unfold every branch, or fold them all if they are all unfolded."""
        rows = [self.tree.get_row(index) for index in range(self.tree.get_n_items())]
        expandable = [row for row in rows if row is not None and row.is_expandable()]
        expand = not all(row.get_expanded() for row in expandable)
        if expand:
            index = 0
            while index < self.tree.get_n_items():
                row = self.tree.get_row(index)
                if row is not None and row.is_expandable():
                    row.set_expanded(True)
                index += 1
        else:
            for row in reversed(expandable):
                row.set_expanded(False)

    def _children(self, item: GObject.Object) -> Gio.ListModel | None:
        if isinstance(item, BookmarkItem) and item.bookmark.children:
            return children_model(item.bookmark.children)
        return None

    def _open_as_stored(self) -> None:
        """Unfold the branches the PDF marks as open (a positive /Count)."""
        index = 0
        while index < self.tree.get_n_items():
            row = self.tree.get_row(index)
            item = row.get_item() if row is not None else None
            if row is not None and isinstance(item, BookmarkItem) and item.bookmark.is_open and row.is_expandable():
                row.set_expanded(True)
            index += 1

    def _on_setup(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        row = BookmarkRow()
        click = Gtk.GestureClick()
        click.connect("released", self._on_row_clicked, item)
        row.add_controller(click)
        item.set_child(row)

    def _on_bind(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        tree_row = item.get_item()
        row = item.get_child()
        assert isinstance(tree_row, Gtk.TreeListRow)
        assert isinstance(row, BookmarkRow)
        bookmark_item = tree_row.get_item()
        assert isinstance(bookmark_item, BookmarkItem)
        bookmark = bookmark_item.bookmark
        row.expander.set_list_row(tree_row)
        row.title.set_markup(title_markup(bookmark))
        row.title.set_tooltip_text(bookmark.title)
        row.bookmark = bookmark
        self._show_page(row)
        self._rows[id(bookmark)] = row
        self._show_mark(row, bookmark)

    def _show_page(self, row: "BookmarkRow") -> None:
        """Show the label of the page a bookmark leads to, where that page is now."""
        page = row.bookmark.page if row.bookmark is not None else None
        place = self._place(page, None) if page is not None else None
        row.page.set_label("" if place is None or self.document is None else self.document.page_label(place[0]))

    def _on_unbind(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        row = item.get_child()
        if isinstance(row, BookmarkRow) and row.bookmark is not None and self._rows.get(id(row.bookmark)) is row:
            del self._rows[id(row.bookmark)]
            row.remove_css_class("reading-position")

    def _on_row_clicked(
        self, gesture: Gtk.GestureClick, _presses: int, _x: float, _y: float, item: Gtk.ListItem
    ) -> None:
        """A click without Ctrl or Shift goes to the bookmark's destination."""
        if gesture.get_current_event_state() & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK):
            return
        tree_row = item.get_item()
        bookmark_item = tree_row.get_item() if isinstance(tree_row, Gtk.TreeListRow) else None
        if not isinstance(bookmark_item, BookmarkItem) or bookmark_item.bookmark.page is None:
            return
        place = self._place(bookmark_item.bookmark.page, bookmark_item.bookmark.top)
        if place is not None:
            page, top = place
            self.emit("destination-activated", page, -1.0 if top is None else top)
