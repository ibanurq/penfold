"""Finding text in a PDF, in the background (D13; as 0.6's Find).

Poppler finds the text itself, ignoring case and accents and across line breaks (0.6's rules); runs of spaces in
what is searched count as one. The search runs in a thread with its own Poppler document and sends the matches to the
main thread in batches, so the list fills while it searches. The sentence around a match is read only when its row is
shown, from the text of its page in Poppler's main-thread copy of the document.
"""

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from gi.repository import GLib, Poppler

from penfold.rendering.page_content import Rectangle

FIND_FLAGS = Poppler.FindFlags.IGNORE_DIACRITICS | Poppler.FindFlags.MULTILINE
# Results are sent to the main thread in batches, at most this often (seconds), so a common word does not flood it.
BATCH_INTERVAL = 0.1
CONTEXT_CHARACTERS = 40
# Pages whose text is kept for the sentences of the rows shown.
CACHED_PAGES = 8


@dataclass(frozen=True)
class SearchResult:
    """One match: its page and the boxes of its text, one per line, in points from the top left corner."""

    page: int
    rectangles: tuple[Rectangle, ...]

    @property
    def top(self) -> float:
        """Height of the match, for going to it."""
        return min(rectangle[1] for rectangle in self.rectangles)


@dataclass(frozen=True)
class MatchContext:
    """The sentence around a match: the words before it, the match as written in the PDF and the words after it.

    The flags say whether the line goes on beyond the words shown (so the row shows "…").
    """

    before: str
    match: str
    after: str
    more_before: bool = False
    more_after: bool = False


def normalize_query(query: str) -> str:
    """What is searched, with runs of spaces and line breaks as one space."""
    return " ".join(query.split())


def find_in_page(page: Poppler.Page, page_index: int, query: str) -> list[SearchResult]:
    """Find a text in a page; a match across a line break has one box per line."""
    _width, height = page.get_size()
    results = []
    boxes: list[Rectangle] = []
    for box in page.find_text_with_options(query, FIND_FLAGS):
        # Poppler gives boxes from the bottom left corner of the page.
        boxes.append((box.x1, height - box.y2, box.x2, height - box.y1))
        if not box.find_get_match_continued():
            results.append(SearchResult(page_index, tuple(boxes)))
            boxes = []
    if boxes:
        results.append(SearchResult(page_index, tuple(boxes)))
    return results


class ContextReader:
    """Reads the sentence around matches from the text of their pages, keeping the last pages read."""

    def __init__(self, document: Poppler.Document) -> None:
        """Read from Poppler's main-thread copy of the document."""
        self._document = document
        self._pages: OrderedDict[int, tuple[str, list[Rectangle]]] = OrderedDict()

    def context(self, result: SearchResult) -> MatchContext:
        """Return the rest of the first line of a match before it, the match and the rest of its last line."""
        text, boxes = self._page_text(result.page)
        inside = [index for index, box in enumerate(boxes) if not text[index].isspace() and _inside(box, result)]
        if not inside:
            return MatchContext("", "", "")
        first, last = inside[0], inside[-1]
        line_start = text.rfind("\n", 0, first) + 1
        line_end = text.find("\n", last + 1)
        line_end = len(text) if line_end < 0 else line_end
        before, more_before = _last_words(" ".join(text[line_start:first].split()))
        after, more_after = _first_words(" ".join(text[last + 1 : line_end].split()))
        return MatchContext(before, " ".join(text[first : last + 1].split()), after, more_before, more_after)

    def _page_text(self, page: int) -> tuple[str, list[Rectangle]]:
        if page not in self._pages:
            poppler_page = self._document.get_page(page)
            text = poppler_page.get_text() or ""
            _found, layout = poppler_page.get_text_layout()
            boxes = [(box.x1, box.y1, box.x2, box.y2) for box in layout or []]
            if len(boxes) != len(text):
                text, boxes = "", []
            self._pages[page] = (text, boxes)
            while len(self._pages) > CACHED_PAGES:
                self._pages.popitem(last=False)
        self._pages.move_to_end(page)
        return self._pages[page]


def _inside(box: Rectangle, result: SearchResult) -> bool:
    """Whether the centre of a character box is inside one of the boxes of a match."""
    x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return any(left <= x <= right and top <= y <= bottom for left, top, right, bottom in result.rectangles)


def _last_words(text: str) -> tuple[str, bool]:
    """The end of a text, up to CONTEXT_CHARACTERS, in whole words, and whether something was left out."""
    if len(text) <= CONTEXT_CHARACTERS:
        return text, False
    piece = text[-CONTEXT_CHARACTERS:]
    space = piece.find(" ")
    return (piece[space + 1 :] if space >= 0 else piece), True


def _first_words(text: str) -> tuple[str, bool]:
    """The start of a text, up to CONTEXT_CHARACTERS, in whole words, and whether something was left out."""
    if len(text) <= CONTEXT_CHARACTERS:
        return text, False
    piece = text[:CONTEXT_CHARACTERS]
    space = piece.rfind(" ")
    return (piece[:space] if space >= 0 else piece), True


class TextSearch:
    """Searches a PDF in a thread; only the latest search runs, starting at a given page and wrapping around."""

    def __init__(self, uri: str) -> None:
        """Prepare to search the PDF at this address (its own Poppler document is opened in the thread)."""
        self._uri = uri
        self._generation = 0
        self._lock = threading.Lock()

    def start(
        self,
        query: str,
        first_page: int,
        on_results: Callable[[list[SearchResult]], None],
        on_finished: Callable[[], None],
    ) -> None:
        """Search for a text from a page on, wrapping around to the start; any earlier search stops.

        on_results is called in the main thread with batches of results, in search order (each page's results
        together), and on_finished once at the end.
        """
        with self._lock:
            self._generation += 1
            generation = self._generation
        thread = threading.Thread(
            target=self._search,
            args=(generation, normalize_query(query), first_page, on_results, on_finished),
            name="penfold-search",
            daemon=True,
        )
        thread.start()

    def cancel(self) -> None:
        """Stop the running search, if any."""
        with self._lock:
            self._generation += 1

    def _current(self, generation: int) -> bool:
        with self._lock:
            return generation == self._generation

    def _search(
        self,
        generation: int,
        query: str,
        first_page: int,
        on_results: Callable[[list[SearchResult]], None],
        on_finished: Callable[[], None],
    ) -> None:
        document = Poppler.Document.new_from_file(self._uri, None)
        count = document.get_n_pages()
        batch: list[SearchResult] = []
        sent = 0.0
        for step in range(count if query else 0):
            if not self._current(generation):
                return
            page = (first_page + step) % count
            batch.extend(find_in_page(document.get_page(page), page, query))
            # The first match goes at once, so the view can jump to it; then in batches.
            if batch and time.monotonic() - sent >= BATCH_INTERVAL:
                GLib.idle_add(self._deliver, generation, on_results, batch)
                batch, sent = [], time.monotonic()
        if batch:
            GLib.idle_add(self._deliver, generation, on_results, batch)
        GLib.idle_add(self._finish, generation, on_finished)

    def _deliver(
        self, generation: int, on_results: Callable[[list[SearchResult]], None], results: list[SearchResult]
    ) -> bool:
        if self._current(generation):
            on_results(results)
        return GLib.SOURCE_REMOVE

    def _finish(self, generation: int, on_finished: Callable[[], None]) -> bool:
        if self._current(generation):
            on_finished()
        return GLib.SOURCE_REMOVE
