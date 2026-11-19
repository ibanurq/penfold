"""Bookmarks: the outline of a PDF (ISO 32000-1, 12.3.3), read as a tree.

Each bookmark keeps its title, its style (bold, italic, colour), whether it starts open, and where it leads: a page
and, if the destination gives one, the height to show, in points from the top of the page.
"""

import bisect
from dataclasses import dataclass, field

import pikepdf

# /F flags of an outline item (ISO 32000-1, table 154).
ITALIC_FLAG = 1
BOLD_FLAG = 2
# Destinations whose arguments give the top of the area to show: [page /XYZ left top zoom], [page /FitH top]…
TOP_ARGUMENT = {"/XYZ": 1, "/FitH": 0, "/FitBH": 0, "/FitR": 3}
# A malformed outline could loop forever; no real outline is deeper or longer.
MAX_DEPTH = 64
MAX_ITEMS = 100_000


@dataclass
class Bookmark:
    """One bookmark and the ones under it."""

    title: str
    page: int | None = None
    top: float | None = None
    bold: bool = False
    italic: bool = False
    color: tuple[float, float, float] | None = None
    is_open: bool = False
    children: list["Bookmark"] = field(default_factory=list)


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
        page, top = self._destination(item)
        return Bookmark(
            title=str(title) if isinstance(title, pikepdf.String) else "",
            page=page,
            top=top,
            italic=bool(flags & ITALIC_FLAG),
            bold=bool(flags & BOLD_FLAG),
            color=_color(item.get("/C")),
            is_open=count > 0,
            children=self.read_siblings(item.get("/First"), depth + 1),
        )

    def _destination(self, item: pikepdf.Dictionary) -> tuple[int | None, float | None]:
        destination: object = item.get("/Dest")
        action = item.get("/A")
        if destination is None and isinstance(action, pikepdf.Dictionary) and action.get("/S") == pikepdf.Name.GoTo:
            destination = action.get("/D")
        destination = self._resolve_name(destination)
        if isinstance(destination, pikepdf.Dictionary):
            destination = destination.get("/D")
        if not isinstance(destination, pikepdf.Array) or len(destination) < 2:  # noqa: PLR2004 (page and type)
            return None, None
        target = destination[0]
        page = self._pages.get(target.objgen) if isinstance(target, pikepdf.Dictionary) else None
        if page is None:
            return None, None
        return page, self._top(destination, page)

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


def _color(value: object) -> tuple[float, float, float] | None:
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


class ReadingIndex:
    """Finds the bookmark of the section being read: the last one whose destination is before the reading point.

    Bookmarks are ordered by where they lead (page, then height), and by their place in the outline when they lead
    to the same point, so the deepest of several bookmarks at one place wins.
    """

    def __init__(self, bookmarks: list[Bookmark]) -> None:
        """Index the bookmarks of an outline (only those with a destination in the document)."""
        entries: list[tuple[tuple[int, float, int], Bookmark]] = []
        self.parents: dict[int, Bookmark | None] = {}
        order = 0

        def walk(items: list[Bookmark], parent: Bookmark | None) -> None:
            nonlocal order
            for bookmark in items:
                self.parents[id(bookmark)] = parent
                if bookmark.page is not None:
                    entries.append(((bookmark.page, bookmark.top or 0.0, order), bookmark))
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
