"""The Find view of the side panel: the search box and the list of every match.

The list fills while the PDF is searched, in page order. Enter and Shift+Enter (and Ctrl+G, Shift+Ctrl+G) go to the
next and previous match, from the current page on; Esc goes back to the view Find covered.
"""

import bisect
import time
from collections.abc import Callable
from gettext import gettext as _
from gettext import ngettext
from typing import ClassVar

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

from penfold.document.sources import Spans
from penfold.rendering.layout import PageLayout
from penfold.rendering.text_search import MatchContext, SearchResult, TextSearch
from penfold.ui.sidebar.view_header import HEADER_MARGIN, name_row

ROW_TEXT_LINES = 2
# Sentences are read a few at a time, for at most this long (seconds) each time, so the window never waits.
CONTEXT_TIME_SLICE = 0.008


class ResultItem(GObject.Object):
    """One match in the list model."""

    __gtype_name__ = "PenfoldResultItem"

    def __init__(self, result: SearchResult, page_label: str) -> None:
        """Wrap a match with the label of its page."""
        super().__init__()
        self.result = result
        self.page_label = page_label


def result_markup(context: MatchContext) -> str:
    """The sentence of a match with the match highlighted, as Pango markup: "…words before match words after…"."""
    escape = GLib.markup_escape_text
    before = after = ""
    if context.before:
        # As in the PDF: no space inside a word ("Lí<match>nea"), one between words.
        gap = " " if context.space_before else ""
        before = f"{'…' if context.more_before else ''}{escape(context.before)}{gap}"
    if context.after:
        gap = " " if context.space_after else ""
        after = f"{gap}{escape(context.after)}{'…' if context.more_after else ''}"
    return f'{before}<span background="#f8e45c" foreground="#000000">{escape(context.match)}</span>{after}'


class SearchView(Gtk.Box):
    """Search box, number of results and their list.

    "result-chosen" is emitted with the index of the match to show; "close-requested" when Esc is pressed.
    """

    __gtype_name__ = "PenfoldSearchView"
    __gsignals__: ClassVar = {
        "result-chosen": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "close-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "results-cleared": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "results-added": (GObject.SignalFlags.RUN_FIRST, None, ()),
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
        # The placeholder goes away when typing: screen readers need a name that stays.
        self.entry.update_property([Gtk.AccessibleProperty.LABEL], [_("Find in Document")])
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
        # The matches in page order, and the page of each, to place a new batch with a binary search.
        self._found: list[SearchResult] = []
        self._found_pages: list[int] = []
        self.last_added: list[SearchResult] = []
        self._page_label: Callable[[int], str] = str
        self._layout: Callable[[], PageLayout] | None = None
        self._context: Callable[[SearchResult], MatchContext] | None = None
        # Rows are bound again whenever matches are inserted above them: read each sentence only once.
        self._contexts: dict[SearchResult, MatchContext] = {}
        self._page_format = _("Page {label}")
        # Rows waiting for their sentence: the label to fill and the match it must show.
        # The rows whose sentence is still to be read: their label for it, with the result and the list item.
        self._pending_contexts: dict[Gtk.Label, tuple[SearchResult, Gtk.ListItem]] = {}
        self._filling = False
        self.current_page = 0
        self.current = -1
        self._jump_to_first = False
        self._searching = False
        self._choosing = False

    def set_document(
        self,
        sources: Callable[[], Spans],
        layout: Callable[[], PageLayout],
        page_label: Callable[[int], str],
        context: Callable[[SearchResult], MatchContext],
    ) -> None:
        """Search this PDF.

        Args:
            sources: gives the source PDFs when a search starts.
            layout: gives the pages of the document as they are shown when a search starts.
            page_label: names a page by its position.
            context: reads the sentence of a match.
        """
        if self._search is not None:
            self._search.cancel()
        self._search = TextSearch(sources)
        self._layout = layout
        self._page_label = page_label
        self._context = context
        self.entry.set_text("")
        self._clear()

    def focus(self) -> None:
        """Put the cursor in the search box, with its text selected."""
        self.entry.grab_focus()
        self.entry.select_region(0, -1)

    @property
    def result_list(self) -> list[SearchResult]:
        """The matches found so far, in page order."""
        return self._found

    def search(self, show_first: bool = True) -> None:
        """Search for the text of the box, from the current page on; the first match from there is shown."""
        self._clear()
        query = self.entry.get_text()
        if self._search is None or self._layout is None or not query.strip():
            self._update_count()
            return
        self._searching = True
        self._jump_to_first = show_first
        self._update_count()
        self._search.start(query, self.current_page, self._layout(), self._on_results, self._on_finished)

    def pages_changed(self) -> None:
        """Search again after an edit of the pages, without moving the view to a match."""
        self.search(show_first=False)

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
            first_later = bisect.bisect_left(self._found_pages, self.current_page)
            index = first_later if direction > 0 else first_later - 1
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

    def _clear(self) -> None:
        if self._search is not None:
            self._search.cancel()
        self._searching = False
        self.current = -1
        self._found, self._found_pages, self.last_added = [], [], []
        self._contexts.clear()
        self._pending_contexts.clear()
        self.results.remove_all()
        self.emit("results-cleared")

    def _on_results(self, results: list[SearchResult]) -> None:
        """Put a batch of matches in their place: the search starts at the current page and wraps around."""
        first_position = -1
        start = 0
        while start < len(results):
            end = start
            while end < len(results) and results[end].page >= results[start].page:
                end += 1
            run = results[start:end]
            position = bisect.bisect_left(self._found_pages, run[0].page)
            self._found[position:position] = run
            self._found_pages[position:position] = [result.page for result in run]
            if self.current >= position:
                self.current += len(run)
            self.results.splice(position, 0, [ResultItem(result, self._page_label(result.page)) for result in run])
            if first_position < 0:
                first_position = position
            start = end
        self.last_added = results
        self._update_count()
        self.emit("results-added")
        if self._jump_to_first and first_position >= 0:
            self._jump_to_first = False
            self.choose(first_position)

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
        page.set_label(self._page_format.format(label=result_item.page_label))
        result = result_item.result
        if result in self._contexts:
            text.set_markup(result_markup(self._contexts[result]))
            self._pending_contexts.pop(text, None)
        else:
            text.set_label("")
            self._pending_contexts[text] = (result, item)
            if not self._filling:
                self._filling = True
                GLib.idle_add(self._fill_contexts)
        name_row(item, page.get_text(), text.get_text())

    def _fill_contexts(self) -> bool:
        """Read the sentences of the rows waiting for one, for a short time; go on later if some are left."""
        deadline = time.monotonic() + CONTEXT_TIME_SLICE
        while self._pending_contexts and time.monotonic() < deadline and self._context is not None:
            label, (result, item) = next(iter(self._pending_contexts.items()))
            del self._pending_contexts[label]
            if result not in self._contexts:
                self._contexts[result] = self._context(result)
            label.set_markup(result_markup(self._contexts[result]))
            page = label.get_prev_sibling()
            assert isinstance(page, Gtk.Label)
            name_row(item, page.get_text(), label.get_text())
        if self._pending_contexts and self._context is not None:
            return GLib.SOURCE_CONTINUE
        self._filling = False
        return GLib.SOURCE_REMOVE

    def _on_key_pressed(
        self, _controller: Gtk.EventControllerKey, keyval: int, _keycode: int, state: Gdk.ModifierType
    ) -> bool:
        """Shift+Enter goes to the previous match."""
        if keyval in {Gdk.KEY_Return, Gdk.KEY_KP_Enter} and state & Gdk.ModifierType.SHIFT_MASK:
            self.previous_result()
            return True
        return False
