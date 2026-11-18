"""The Find view of the side panel (02-interfaz, 6.4; D13): the search box and the list of every match.

The list fills while the PDF is searched, in page order. Enter and Shift+Enter (and Ctrl+G, Shift+Ctrl+G) go to the
next and previous match, from the current page on; Esc goes back to the view Find covered.
"""

from collections.abc import Callable
from gettext import gettext as _
from gettext import ngettext
from typing import ClassVar

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

from penfold.rendering.text_search import SearchResult, TextSearch
from penfold.ui.sidebar.view_header import HEADER_MARGIN

ROW_TEXT_LINES = 2


class ResultItem(GObject.Object):
    """One match in the list model."""

    __gtype_name__ = "PenfoldResultItem"

    def __init__(self, result: SearchResult, page_label: str) -> None:
        """Wrap a match with the label of its page."""
        super().__init__()
        self.result = result
        self.page_label = page_label


def result_markup(result: SearchResult) -> str:
    """The sentence of a match with the match highlighted, as Pango markup."""
    escape = GLib.markup_escape_text
    before = f"…{escape(result.before)}" if result.before.strip() else escape(result.before)
    after = f"{escape(result.after)}…" if result.after.strip() else escape(result.after)
    return f'{before}<span background="#f8e45c" foreground="#000000">{escape(result.match)}</span>{after}'


class SearchView(Gtk.Box):
    """Search box, number of results and their list.

    "result-chosen" is emitted with the index of the match to show; "close-requested" when Esc is pressed.
    """

    __gtype_name__ = "PenfoldSearchView"
    __gsignals__: ClassVar = {
        "result-chosen": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "close-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "results-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self) -> None:
        """Create the view; set_document gives it a PDF to search."""
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.entry = Gtk.SearchEntry(
            placeholder_text=_("Find in Document"),
            margin_start=HEADER_MARGIN,
            margin_end=HEADER_MARGIN,
            margin_top=6,
            margin_bottom=6,
        )
        self.entry.connect("search-changed", lambda _entry: self.search())
        self.entry.connect("activate", lambda _entry: self.next_result())
        self.entry.connect("stop-search", lambda _entry: self.emit("close-requested"))
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key_pressed)
        self.entry.add_controller(keys)
        self.append(self.entry)
        self.count_label = Gtk.Label(xalign=0, margin_start=HEADER_MARGIN, margin_bottom=4)
        self.count_label.add_css_class("caption-heading")
        self.count_label.add_css_class("dim-label")
        self.append(self.count_label)
        self.results = Gio.ListStore.new(ResultItem)
        self.selection = Gtk.SingleSelection(model=self.results, autoselect=False, can_unselect=True)
        self.selection.connect("selection-changed", self._on_selection_changed)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_setup)
        factory.connect("bind", self._on_bind)
        self.list = Gtk.ListView(model=self.selection, factory=factory, single_click_activate=False)
        self.list.add_css_class("navigation-sidebar")
        self.append(Gtk.ScrolledWindow(child=self.list, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER))
        self._search: TextSearch | None = None
        self._page_label: Callable[[int], str] = str
        self.current_page = 0
        self.current = -1
        self._jump_to_first = False
        self._searching = False
        self._choosing = False

    def set_document(self, uri: str, page_label: Callable[[int], str]) -> None:
        """Search this PDF; page_label names a page by its index (D14)."""
        if self._search is not None:
            self._search.cancel()
        self._search = TextSearch(uri)
        self._page_label = page_label
        self.entry.set_text("")
        self._clear()

    def focus(self) -> None:
        """Put the cursor in the search box, with its text selected."""
        self.entry.grab_focus()
        self.entry.select_region(0, -1)

    @property
    def result_list(self) -> list[SearchResult]:
        """The matches found so far, in page order."""
        return [item.result for item in self._items()]

    def search(self) -> None:
        """Search for the text of the box, from the current page on; the first match from there is shown."""
        self._clear()
        query = self.entry.get_text()
        if self._search is None or not query.strip():
            self._update_count()
            return
        self._searching = True
        self._jump_to_first = True
        self._update_count()
        self._search.start(query, self.current_page, self._on_results, self._on_finished)

    def next_result(self) -> None:
        """Go to the next match (Enter, Ctrl+G); the first one from the current page if none is chosen yet."""
        self._step(1)

    def previous_result(self) -> None:
        """Go to the previous match (Shift+Enter, Shift+Ctrl+G)."""
        self._step(-1)

    def _step(self, direction: int) -> None:
        count = self.results.get_n_items()
        if count == 0:
            return
        if self.current < 0:
            later = [index for index, item in enumerate(self._items()) if item.result.page >= self.current_page]
            index = later[0] if later and direction > 0 else (later[0] - 1 if later else count - 1)
            self.choose(index % count)
        else:
            self.choose((self.current + direction) % count)

    def choose(self, index: int) -> None:
        """Make a match the current one, select its row and tell the window to show it."""
        if not 0 <= index < self.results.get_n_items():
            return
        self.current = index
        self._choosing = True
        self.selection.set_selected(index)
        self._choosing = False
        self.list.scroll_to(index, Gtk.ListScrollFlags.NONE, None)
        self.emit("result-chosen", index)

    def _items(self) -> list[ResultItem]:
        items = [self.results.get_item(index) for index in range(self.results.get_n_items())]
        return [item for item in items if isinstance(item, ResultItem)]

    def _clear(self) -> None:
        if self._search is not None:
            self._search.cancel()
        self._searching = False
        self.current = -1
        self.results.remove_all()
        self.emit("results-changed")

    def _on_results(self, results: list[SearchResult]) -> None:
        """Add the matches of a page in their place (the search starts at the current page and wraps around)."""
        page = results[0].page
        position = sum(1 for item in self._items() if item.result.page < page)
        if self.current >= position:
            self.current += len(results)
        self.results.splice(position, 0, [ResultItem(result, self._page_label(result.page)) for result in results])
        self._update_count()
        self.emit("results-changed")
        if self._jump_to_first:
            self._jump_to_first = False
            self.choose(position)

    def _on_finished(self) -> None:
        self._searching = False
        self._update_count()

    def _update_count(self) -> None:
        count = self.results.get_n_items()
        if not self.entry.get_text().strip():
            self.count_label.set_label("")
        elif count == 0 and not self._searching:
            self.count_label.set_label(_("No results"))
        else:
            self.count_label.set_label(ngettext("{count} result", "{count} results", count).format(count=count))

    def _on_selection_changed(self, selection: Gtk.SingleSelection, _position: int, _count: int) -> None:
        index = selection.get_selected()
        if not self._choosing and index not in (Gtk.INVALID_LIST_POSITION, self.current):
            self.choose(index)

    def _on_setup(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_top=4, margin_bottom=4)
        page = Gtk.Label(xalign=0)
        page.add_css_class("heading")
        text = Gtk.Label(
            xalign=0,
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
            lines=ROW_TEXT_LINES,
            ellipsize=Pango.EllipsizeMode.END,
        )
        text.add_css_class("dim-label")
        box.append(page)
        box.append(text)
        item.set_child(box)

    def _on_bind(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        result_item = item.get_item()
        box = item.get_child()
        assert isinstance(result_item, ResultItem)
        assert isinstance(box, Gtk.Box)
        page, text = box.get_first_child(), box.get_last_child()
        assert isinstance(page, Gtk.Label)
        assert isinstance(text, Gtk.Label)
        page.set_label(_("Page {label}").format(label=result_item.page_label))
        text.set_markup(result_markup(result_item.result))

    def _on_key_pressed(
        self, _controller: Gtk.EventControllerKey, keyval: int, _keycode: int, state: Gdk.ModifierType
    ) -> bool:
        """Shift+Enter goes to the previous match."""
        if keyval in {Gdk.KEY_Return, Gdk.KEY_KP_Enter} and state & Gdk.ModifierType.SHIFT_MASK:
            self.previous_result()
            return True
        return False
