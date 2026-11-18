"""Finding text in a PDF, in the background (D13; as 0.6's Find).

The search ignores case, accents and irregular line breaks: both the page text and what is searched are "folded"
(lower case, without accents, every run of spaces and line breaks as one space), and each folded character remembers
which character of the page it came from, to put the match back on the page. It runs in a thread with its own Poppler
document, and the results arrive in the main thread page by page, so the list fills while it searches.
"""

import threading
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from gi.repository import GLib, Poppler

from penfold.rendering.page_content import Rectangle

CONTEXT_CHARACTERS = 40
# Two character boxes are on the same line if their centres are this close, relative to their height.
SAME_LINE = 0.5


@dataclass(frozen=True)
class SearchResult:
    """One match: its page, the boxes of its text (in points from the top left corner) and the sentence around it.

    The sentence is split in three: before the match, the match as written in the PDF, and after it.
    """

    page: int
    rectangles: tuple[Rectangle, ...]
    before: str
    match: str
    after: str

    @property
    def top(self) -> float:
        """Height of the match, for going to it."""
        return min(rectangle[1] for rectangle in self.rectangles)


def fold(text: str) -> tuple[str, list[int]]:
    """Fold a text and return it with, for each folded character, the index of the character it came from."""
    folded: list[str] = []
    origins: list[int] = []
    for index, character in enumerate(text):
        for piece in unicodedata.normalize("NFKD", character):
            if unicodedata.category(piece) == "Mn":
                continue
            folded_piece = " " if piece.isspace() else piece.lower()
            if folded_piece == " " and (not folded or folded[-1] == " "):
                continue
            folded.append(folded_piece)
            origins.append(index)
    while folded and folded[-1] == " ":
        folded.pop()
        origins.pop()
    return "".join(folded), origins


def fold_query(query: str) -> str:
    """Fold what is searched, the same way as the page text."""
    return fold(query)[0].strip()


def find_in_page(page: int, text: str, boxes: list[Rectangle], query: str) -> list[SearchResult]:
    """Find a folded query in the text of a page, whose characters have these boxes."""
    if not query:
        return []
    folded, origins = fold(text)
    results = []
    start = folded.find(query)
    while start >= 0:
        first, last = origins[start], origins[start + len(query) - 1]
        rectangles = _merge_lines([boxes[index] for index in range(first, last + 1) if not text[index].isspace()])
        if rectangles:
            before = _whole_words(text, max(0, first - CONTEXT_CHARACTERS), first, at_start=True)
            after = _whole_words(text, last + 1, last + 1 + CONTEXT_CHARACTERS, at_start=False)
            results.append(
                SearchResult(
                    page=page,
                    rectangles=tuple(rectangles),
                    before=_context(before, keep_end=True),
                    match=" ".join(text[first : last + 1].split()),
                    after=_context(after, keep_end=False),
                )
            )
        start = folded.find(query, start + len(query))
    return results


def _whole_words(text: str, start: int, end: int, at_start: bool) -> str:
    """Return text[start:end] without the piece of word cut at its outer edge.

    The text before a match is cut at its start (at_start) and the text after it at its end; the edge that touches the
    match, and the edges of the page text, are kept.
    """
    piece = text[start:end]
    spaces = [index for index, character in enumerate(piece) if character.isspace()]
    if at_start and start > 0 and not text[start - 1].isspace() and not piece[:1].isspace():
        return piece[spaces[0] :] if spaces else ""
    if not at_start and end < len(text) and not text[end].isspace() and not piece[-1:].isspace():
        return piece[: spaces[-1] + 1] if spaces else ""
    return piece


def _context(text: str, keep_end: bool) -> str:
    """Return the words around a match on one line, keeping the space that touches the match.

    That is the space at the end of the text before the match, or at the start of the text after it.
    """
    words = " ".join(text.split())
    if keep_end and text[-1:].isspace():
        return f"{words} " if words else " "
    if not keep_end and text[:1].isspace():
        return f" {words}" if words else " "
    return words


def _merge_lines(boxes: list[Rectangle]) -> list[Rectangle]:
    """Join the boxes of consecutive characters on the same line into one box per line."""
    merged: list[Rectangle] = []
    for box in boxes:
        if merged:
            left, top, right, bottom = merged[-1]
            height = max(bottom - top, box[3] - box[1], 1.0)
            if abs((top + bottom) / 2 - (box[1] + box[3]) / 2) < height * SAME_LINE:
                merged[-1] = (min(left, box[0]), min(top, box[1]), max(right, box[2]), max(bottom, box[3]))
                continue
        merged.append(box)
    return merged


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

        on_results is called in the main thread with the results of each page that has any, in search order, and
        on_finished once at the end.
        """
        with self._lock:
            self._generation += 1
            generation = self._generation
        folded = fold_query(query)
        thread = threading.Thread(
            target=self._search,
            args=(generation, folded, first_page, on_results, on_finished),
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
        for step in range(count if query else 0):
            if not self._current(generation):
                return
            page = (first_page + step) % count
            poppler_page = document.get_page(page)
            text = poppler_page.get_text() or ""
            _found, layout = poppler_page.get_text_layout()
            boxes = [(box.x1, box.y1, box.x2, box.y2) for box in layout or []]
            if len(boxes) != len(text):
                continue
            results = find_in_page(page, text, boxes, query)
            if results:
                GLib.idle_add(self._deliver, generation, on_results, results)
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
