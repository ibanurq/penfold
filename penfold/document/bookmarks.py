"""Bookmarks: the outline of a PDF (ISO 32000-1, 12.3.3), read as a tree.

Each bookmark keeps its title, its style (bold, italic, colour), whether it starts open, and where it leads: a page and,
if the destination gives one, the height to show, in points from the top of the page. Bookmarks of a PDF whose pages are
added come with them.
"""

import bisect
import itertools
import re
from collections.abc import Callable, Iterable, Set
from dataclasses import dataclass, field, replace

import pikepdf

# /F flags of an outline item (ISO 32000-1, table 154).
ITALIC_FLAG = 1
BOLD_FLAG = 2
# Destinations whose arguments give the top of the area to show: [page /XYZ left top zoom], [page /FitH top]…
TOP_ARGUMENT = {"/XYZ": 1, "/FitH": 0, "/FitBH": 0, "/FitR": 3}
# A malformed outline could loop forever; no real outline is deeper or longer.
MAX_DEPTH = 64
MAX_ITEMS = 100_000
# How a destination shows its page (ISO 32000-1, 12.3.2.2): its type (/XYZ, /FitH…) and its numbers (None for null).
View = tuple[str, tuple[float | None, ...]]
# An outline colour: red, green and blue, from 0 to 1.
Color = tuple[float, float, float]
# Gives each bookmark read or made its key.
_keys = itertools.count()
# A title taken from text selected in the document is cut at this length.
MAX_TITLE_FROM_TEXT = 150


@dataclass
class Bookmark:
    """One bookmark and the ones under it.

    Its page is the source index of the page it leads to (sources.py), and its origin the object number of the outline
    item it was read from in the opened PDF, whose destination or action is kept on saving. A bookmark of a PDF added
    has no origin: its view keeps how its destination shows the page, to write it again on saving.

    Its key stays the same in its copies, which edits make (commands/bookmarks.py), so the view can select it again
    after an edit, an undo or a redo; it is not part of the bookmark, and leaves equality alone.
    """

    title: str
    page: int | None = None
    top: float | None = None
    bold: bool = False
    italic: bool = False
    color: Color | None = None
    is_open: bool = False
    children: list["Bookmark"] = field(default_factory=list)
    origin: tuple[int, int] | None = None
    view: View | None = None
    key: int = field(default_factory=lambda: next(_keys), compare=False, repr=False)


def title_from_text(text: str) -> str:
    """Return a bookmark title from text selected in the document: on one line, and cut if it is long."""
    title = re.sub(r"\s+", " ", text).strip()
    return title if len(title) <= MAX_TITLE_FROM_TEXT else title[:MAX_TITLE_FROM_TEXT] + "…"


def topmost(bookmarks: list[Bookmark], chosen: Iterable[Bookmark]) -> list[Bookmark]:
    """Return those of the chosen bookmarks of an outline that are not under another chosen one, in outline order.

    They are the ones to move, since each takes the bookmarks under it along.
    """
    wanted = {id(bookmark) for bookmark in chosen}
    found = []

    def walk(level: list[Bookmark]) -> None:
        for bookmark in level:
            if id(bookmark) in wanted:
                found.append(bookmark)
            else:
                walk(bookmark.children)

    walk(bookmarks)
    return found


def without_pages(bookmarks: list[Bookmark], source_indexes: Set[int]) -> list[Bookmark]:
    """Return the outline without the bookmarks that lead to these pages of the PDF, when they are deleted.

    The bookmarks under a removed one move up to its place. The outline given is left as it was: the bookmarks kept
    are new copies, so it can be put back on undo.
    """
    kept = []
    for bookmark in bookmarks:
        children = without_pages(bookmark.children, source_indexes)
        if bookmark.page is not None and bookmark.page in source_indexes:
            kept.extend(children)
        else:
            kept.append(replace(bookmark, children=children))
    return kept


def leading_to(bookmarks: list[Bookmark], source_indexes: Set[int]) -> list[Bookmark]:
    """Return only the bookmarks that lead to these pages, when they are extracted.

    The bookmarks under a bookmark left out move up to its place. The outline given is left as it was.
    """
    kept = []
    for bookmark in bookmarks:
        children = leading_to(bookmark.children, source_indexes)
        if bookmark.page is not None and bookmark.page in source_indexes:
            kept.append(replace(bookmark, children=children))
        else:
            kept.extend(children)
    return kept


def for_added_pages(bookmarks: list[Bookmark], first_page: int) -> list[Bookmark]:
    """Return the bookmarks of a PDF read to be added to another, whose pages are numbered from first_page.

    Only those that lead to a page are kept; the bookmarks under a removed one move up to its place. They lose their
    origin, which belongs to their own PDF.
    """
    kept = []
    for bookmark in bookmarks:
        children = for_added_pages(bookmark.children, first_page)
        if bookmark.page is None:
            kept.extend(children)
        else:
            kept.append(replace(bookmark, page=first_page + bookmark.page, origin=None, children=children))
    return kept


def with_inserted(
    bookmarks: list[Bookmark], inserted: list[Bookmark], first: int, position: Callable[[int], int | None]
) -> list[Bookmark]:
    """Return the outline with some bookmarks put where pages were inserted.

    They go after the last bookmark of the level that leads before the first page inserted, or inside it (unfolding
    it) if some bookmark under it leads to that page or after; first is the position of that page and position says
    where a page is now. Bookmarks without a page count as leading before. The outline given is left as it was.
    """

    def before(bookmark: Bookmark) -> bool:
        place = position(bookmark.page) if bookmark.page is not None else None
        return place is None or place < first

    def leads_from_first(level: list[Bookmark]) -> bool:
        return any(not before(bookmark) or leads_from_first(bookmark.children) for bookmark in level)

    earlier = [index for index, bookmark in enumerate(bookmarks) if before(bookmark)]
    if not earlier:
        return [*inserted, *bookmarks]
    last = earlier[-1]
    previous = bookmarks[last]
    if leads_from_first(previous.children):
        children = with_inserted(previous.children, inserted, first, position)
        return [*bookmarks[:last], replace(previous, is_open=True, children=children), *bookmarks[last + 1 :]]
    return [*bookmarks[: last + 1], *inserted, *bookmarks[last + 1 :]]


def read_bookmarks(pdf: pikepdf.Pdf) -> list[Bookmark]:
    """Return the top-level bookmarks of a PDF, each with its children; an empty list if it has none."""
    outlines = pdf.Root.get("/Outlines")
    if not isinstance(outlines, pikepdf.Dictionary):
        return []
    reader = _OutlineReader(pdf)
    return reader.read_siblings(outlines.get("/First"), depth=0)


class _OutlineReader:
    """Walks the outline items, guarding against loops and broken links."""

    def __init__(self, pdf: pikepdf.Pdf) -> None:
        self._pdf = pdf
        self._pages = {page.obj.objgen: index for index, page in enumerate(pdf.pages)}
        self._seen: set[tuple[int, int]] = set()

    def read_siblings(self, item: object, depth: int) -> list[Bookmark]:
        bookmarks = []
        while isinstance(item, pikepdf.Dictionary) and depth < MAX_DEPTH and len(self._seen) < MAX_ITEMS:
            if item.objgen != (0, 0):
                if item.objgen in self._seen:
                    break
                self._seen.add(item.objgen)
            bookmarks.append(self._read_item(item, depth))
            item = item.get("/Next")
        return bookmarks

    def _read_item(self, item: pikepdf.Dictionary, depth: int) -> Bookmark:
        title = item.get("/Title")
        flags = _integer(item.get("/F"))
        count = _integer(item.get("/Count"))
        page, top, view = self._destination(item)
        return Bookmark(
            title=str(title) if isinstance(title, pikepdf.String) else "",
            page=page,
            top=top,
            italic=bool(flags & ITALIC_FLAG),
            bold=bool(flags & BOLD_FLAG),
            color=_color(item.get("/C")),
            is_open=count > 0,
            children=self.read_siblings(item.get("/First"), depth + 1),
            origin=item.objgen if item.is_indirect else None,
            view=view,
        )

    def _destination(self, item: pikepdf.Dictionary) -> tuple[int | None, float | None, View | None]:
        """Where an item leads: the page, the height to show and how it shows the page; all None if nowhere."""
        destination: object = item.get("/Dest")
        action = item.get("/A")
        if destination is None and isinstance(action, pikepdf.Dictionary) and action.get("/S") == pikepdf.Name.GoTo:
            destination = action.get("/D")
        destination = self._resolve_name(destination)
        if isinstance(destination, pikepdf.Dictionary):
            destination = destination.get("/D")
        if not isinstance(destination, pikepdf.Array) or len(destination) < 2:  # noqa: PLR2004 (page and type)
            return None, None, None
        target, kind = destination[0], destination[1]
        page = self._pages.get(target.objgen) if isinstance(target, pikepdf.Dictionary) else None
        if page is None:
            return None, None, None
        view = (str(kind), tuple(_number(destination[index]) for index in range(2, len(destination))))
        return page, self._top(destination, page), view if isinstance(kind, pikepdf.Name) else None

    def _resolve_name(self, destination: object) -> object:
        """Look a named destination up in the catalog (/Names /Dests, or the older /Dests dictionary)."""
        if isinstance(destination, pikepdf.Name):
            destination = pikepdf.String(str(destination)[1:])
        if not isinstance(destination, pikepdf.String):
            return destination
        name = str(destination)
        names = self._pdf.Root.get("/Names")
        if isinstance(names, pikepdf.Dictionary) and isinstance(names.get("/Dests"), pikepdf.Dictionary):
            tree = pikepdf.NameTree(names.Dests)
            if name in tree:
                return tree[name]
        old_dests = self._pdf.Root.get("/Dests")
        if isinstance(old_dests, pikepdf.Dictionary):
            return old_dests.get(f"/{name}")
        return None

    def _top(self, destination: pikepdf.Array, page: int) -> float | None:
        kind = destination[1]
        index = TOP_ARGUMENT.get(str(kind)) if isinstance(kind, pikepdf.Name) else None
        if index is None or len(destination) <= index + 2:
            return None
        value = _number(destination[index + 2])
        height = _number(self._pdf.pages[page].mediabox[3])
        if value is None or height is None:
            return None
        return max(0.0, height - value)


def _integer(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _number(value: object) -> float | None:
    """Return a PDF number as a float; None for null or anything else."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _color(value: object) -> Color | None:
    """Return an outline colour (/C, three numbers from 0 to 1), or None if it has none or it is black."""
    if not isinstance(value, pikepdf.Array) or len(value) != 3:  # noqa: PLR2004 (red, green, blue)
        return None
    components = [_number(value[index]) for index in range(3)]
    if None in components:
        return None
    red, green, blue = (min(1.0, max(0.0, component or 0.0)) for component in components)
    if red == green == blue == 0:
        return None
    return red, green, blue


# Where a destination (its page's source index and a height) is in the document now; None if its page is not in it.
Place = Callable[[int, float | None], tuple[int, float | None] | None]


def _unchanged(page: int, top: float | None) -> tuple[int, float | None]:
    return page, top


class ReadingIndex:
    """Finds the bookmark of the section being read: the last one whose destination is before the reading point.

    Bookmarks are ordered by where they lead (page, then height), and by their place in the outline when they lead
    to the same point, so the deepest of several bookmarks at one place wins.
    """

    def __init__(self, bookmarks: list[Bookmark], place: Place = _unchanged) -> None:
        """Index the bookmarks of an outline (only those with a destination in the document).

        place says where each destination is now, after the pages were moved or turned.
        """
        entries: list[tuple[tuple[int, float, int], Bookmark]] = []
        self.parents: dict[int, Bookmark | None] = {}
        order = 0

        def walk(items: list[Bookmark], parent: Bookmark | None) -> None:
            nonlocal order
            for bookmark in items:
                self.parents[id(bookmark)] = parent
                placed = place(bookmark.page, bookmark.top) if bookmark.page is not None else None
                if placed is not None:
                    entries.append(((placed[0], placed[1] or 0.0, order), bookmark))
                order += 1
                walk(bookmark.children, bookmark)

        walk(bookmarks, None)
        entries.sort(key=lambda entry: entry[0])
        self._keys = [key for key, _bookmark in entries]
        self._bookmarks = [bookmark for _key, bookmark in entries]

    def at(self, page: int, top: float) -> Bookmark | None:
        """The bookmark of the section that contains this point (a page and a height from its top), if any."""
        position = bisect.bisect_right(self._keys, (page, top, MAX_ITEMS))
        return self._bookmarks[position - 1] if position > 0 else None

    def ancestors(self, bookmark: Bookmark) -> list[Bookmark]:
        """The bookmarks that contain this one, from its parent up to the top of the outline."""
        chain = []
        parent = self.parents.get(id(bookmark))
        while parent is not None:
            chain.append(parent)
            parent = self.parents.get(id(parent))
        return chain
