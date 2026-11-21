"""Bookmark edits: add, delete, rename, indent, outdent, point, format and move bookmarks (G3 to G7).

Each edit works on a copy of the outline, made when the edit is created, and keeps both: applying puts the copy in
the document, reverting puts the outline it had back. Nothing is changed in the outline the document had, so undo
does not depend on anyone else leaving it alone; the view only unfolds and folds bookmarks, which is not an edit (J2)
and is copied as it is.

An edit is made for the outline the document has when it is created, and executed at once. The bookmarks it is given
are bookmarks of that outline; its `bookmarks` are their copies, for the view to select them again.
"""

import enum
from collections.abc import Iterable
from dataclasses import replace

from penfold.document.bookmarks import Bookmark, Color, topmost
from penfold.document.document import OpenDocument
from penfold.document.history import Change


class Placement(enum.Enum):
    """Where moved bookmarks go next to the bookmark they are dropped on (G6)."""

    BEFORE = enum.auto()
    AFTER = enum.auto()
    INSIDE = enum.auto()
    """As its last children, unfolding it."""


class KeepColor(enum.Enum):
    """Says that formatting leaves the colour of each bookmark as it is."""

    KEEP = enum.auto()


class _BookmarkEdit:
    """What every bookmark edit shares: the outline before and after, and applying or reverting it."""

    changes = Change.BOOKMARKS

    def __init__(self, document: OpenDocument, chosen: Iterable[Bookmark] = ()) -> None:
        """Copy the outline of the document, finding the copies of the bookmarks chosen.

        Raises:
            ValueError: a bookmark chosen is not in the outline.
        """
        self._document = document
        self._before = document.bookmarks
        self._after, self._copies = _copied(self._before)
        self.bookmarks = [self._copy_of(bookmark) for bookmark in chosen]

    def _copy_of(self, bookmark: Bookmark) -> Bookmark:
        """The copy of a bookmark of the outline the document had.

        Raises:
            ValueError: the bookmark is not in that outline.
        """
        copy = self._copies.get(id(bookmark))
        if copy is None:
            message = "the bookmarks given are not all in the outline"
            raise ValueError(message)
        return copy

    def _replace(self, bookmark: Bookmark, **changes: object) -> Bookmark:
        """Put in the copy of the outline a bookmark like this one with some changes, and return it."""
        new = replace(bookmark, **changes)  # type: ignore[arg-type]
        _swap(self._after, bookmark, new)
        return new

    @property
    def changes_anything(self) -> bool:
        """Whether the outline is different after the edit (formatting bookmarks as they are, for example, is not)."""
        return self._after != self._before

    def apply(self) -> None:
        """Put the edited outline in the document."""
        self._document.bookmarks = self._after

    def revert(self) -> None:
        """Put back the outline the document had."""
        self._document.bookmarks = self._before


class AddBookmark(_BookmarkEdit):
    """Add a bookmark to the start of a page, placed in page order as 0.6 does (G3)."""

    def __init__(self, document: OpenDocument, title: str, position: int) -> None:
        """Prepare a bookmark with this title leading to the page at a position.

        It goes after the last bookmark, in reading order of the outline, that leads to that page or before it, or
        as the first under it if it has bookmarks under it; bookmarks that lead nowhere do not count (D54). The
        bookmarks above it are unfolded, so it can be seen.

        Raises:
            ValueError: the title is blank, or the position is outside the document.
        """
        if not 0 <= position < document.page_count:
            message = f"no page at position {position} of {document.page_count}"
            raise ValueError(message)
        super().__init__(document)
        bookmark = Bookmark(_checked_title(title), page=document.pages[position].source_index)
        self.bookmarks = [bookmark]
        previous: list[Bookmark] = []
        for path in _paths(self._after):
            page = path[-1].page
            place = document.page_position(page) if page is not None else None
            if place is not None and place <= position:
                previous = path
        if not previous:
            self._after.insert(0, bookmark)
            return
        for ancestor in previous[:-1]:
            ancestor.is_open = True
        last = previous[-1]
        if last.children:
            last.children.insert(0, bookmark)
            last.is_open = True
        else:
            level = previous[-2].children if len(previous) > 1 else self._after
            level.insert(_index(level, last) + 1, bookmark)


class DeleteBookmarks(_BookmarkEdit):
    """Delete some bookmarks, with the bookmarks under them (G4)."""

    def __init__(self, document: OpenDocument, chosen: Iterable[Bookmark]) -> None:
        """Prepare the deletion of these bookmarks.

        Raises:
            ValueError: no bookmarks, or some not in the outline.
        """
        super().__init__(document, chosen)
        if not self.bookmarks:
            message = "no bookmarks given"
            raise ValueError(message)
        for bookmark in topmost(self._after, self.bookmarks):
            _take_out(self._after, bookmark)
        self.bookmarks = []


class RenameBookmark(_BookmarkEdit):
    """Change the title of a bookmark (G5)."""

    def __init__(self, document: OpenDocument, bookmark: Bookmark, title: str) -> None:
        """Prepare the new title of a bookmark.

        Raises:
            ValueError: the title is blank, or the bookmark is not in the outline.
        """
        super().__init__(document, [bookmark])
        self.bookmarks = [self._replace(self.bookmarks[0], title=_checked_title(title))]


class PointBookmark(_BookmarkEdit):
    """Make a bookmark lead to the start of the page at a position (G5); it loses its original destination (G8)."""

    def __init__(self, document: OpenDocument, bookmark: Bookmark, position: int) -> None:
        """Prepare the new destination of a bookmark.

        Raises:
            ValueError: the position is outside the document, or the bookmark is not in the outline.
        """
        if not 0 <= position < document.page_count:
            message = f"no page at position {position} of {document.page_count}"
            raise ValueError(message)
        super().__init__(document, [bookmark])
        page = document.pages[position].source_index
        self.bookmarks = [self._replace(self.bookmarks[0], page=page, top=None, origin=None, view=None)]


class IndentBookmarks(_BookmarkEdit):
    """Put each bookmark under the one before it, as its last child, as 0.6 does (G5).

    Of the bookmarks chosen, those under another chosen one move with it, and those first in their level stay.
    """

    def __init__(self, document: OpenDocument, chosen: Iterable[Bookmark]) -> None:
        """Prepare the indent of these bookmarks.

        Raises:
            ValueError: none of them can be indented, or some are not in the outline.
        """
        super().__init__(document, chosen)
        movable = [bookmark for bookmark in topmost(self._after, self.bookmarks) if _can_indent(self._after, bookmark)]
        if not movable:
            message = "none of these bookmarks can be indented"
            raise ValueError(message)
        for bookmark in movable:
            level = _level(self._after, bookmark)
            index = _index(level, bookmark)
            previous = level[index - 1]
            del level[index]
            previous.children.append(bookmark)
            previous.is_open = True


class OutdentBookmarks(_BookmarkEdit):
    """Put each bookmark just after the one it is under, as 0.6 does (G5).

    Of the bookmarks chosen, those under another chosen one move with it, and those at the top level stay.
    """

    def __init__(self, document: OpenDocument, chosen: Iterable[Bookmark]) -> None:
        """Prepare the outdent of these bookmarks.

        Raises:
            ValueError: none of them can be outdented, or some are not in the outline.
        """
        super().__init__(document, chosen)
        movable = [bookmark for bookmark in topmost(self._after, self.bookmarks) if _can_outdent(self._after, bookmark)]
        if not movable:
            message = "none of these bookmarks can be outdented"
            raise ValueError(message)
        # From the last, so that several under one bookmark keep their order after it.
        for bookmark in reversed(movable):
            parent = _parent(self._after, bookmark)
            assert parent is not None
            parent.children.remove(bookmark)
            level = _level(self._after, parent)
            level.insert(_index(level, parent) + 1, bookmark)


class FormatBookmarks(_BookmarkEdit):
    """Make some bookmarks bold or not, italic or not, or of a colour or none (G7)."""

    def __init__(
        self,
        document: OpenDocument,
        chosen: Iterable[Bookmark],
        *,
        bold: bool | None = None,
        italic: bool | None = None,
        color: Color | KeepColor | None = KeepColor.KEEP,
    ) -> None:
        """Prepare the new style of these bookmarks; bold or italic None leaves it as each one has it.

        Raises:
            ValueError: no bookmarks, or some not in the outline.
        """
        super().__init__(document, chosen)
        if not self.bookmarks:
            message = "no bookmarks given"
            raise ValueError(message)
        self.bookmarks = [
            self._replace(
                bookmark,
                bold=bookmark.bold if bold is None else bold,
                italic=bookmark.italic if italic is None else italic,
                color=bookmark.color if isinstance(color, KeepColor) else color,
            )
            for bookmark in self.bookmarks
        ]


class MoveBookmarks(_BookmarkEdit):
    """Move some bookmarks, together and in their order, next to another or inside it (dragging them, G6)."""

    def __init__(
        self, document: OpenDocument, chosen: Iterable[Bookmark], target: Bookmark | None, placement: Placement
    ) -> None:
        """Prepare the move of these bookmarks before, after or inside a target; with no target, to the end.

        Those under another chosen one move with it.

        Raises:
            ValueError: no bookmarks, some not in the outline, or a target among them or under one of them.
        """
        super().__init__(document, chosen)
        moved = topmost(self._after, self.bookmarks)
        if not moved:
            message = "no bookmarks given"
            raise ValueError(message)
        copied_target = self._copy_of(target) if target is not None else None
        if copied_target is not None and any(_holds(bookmark, copied_target) for bookmark in moved):
            message = "bookmarks cannot be moved next to or inside themselves"
            raise ValueError(message)
        self.bookmarks = moved
        for bookmark in moved:
            _take_out(self._after, bookmark)
        if copied_target is None:
            self._after.extend(moved)
        elif placement is Placement.INSIDE:
            copied_target.children.extend(moved)
            copied_target.is_open = True
        else:
            level = _level(self._after, copied_target)
            index = _index(level, copied_target) + (placement is Placement.AFTER)
            level[index:index] = moved


def can_indent(bookmarks: list[Bookmark], chosen: Iterable[Bookmark]) -> bool:
    """Whether IndentBookmarks can move some of these bookmarks of an outline."""
    return any(_can_indent(bookmarks, bookmark) for bookmark in topmost(bookmarks, chosen))


def can_outdent(bookmarks: list[Bookmark], chosen: Iterable[Bookmark]) -> bool:
    """Whether OutdentBookmarks can move some of these bookmarks of an outline."""
    return any(_can_outdent(bookmarks, bookmark) for bookmark in topmost(bookmarks, chosen))


def can_move(bookmarks: list[Bookmark], chosen: Iterable[Bookmark], target: Bookmark) -> bool:
    """Whether these bookmarks of an outline can be moved next to or inside a target: not among them nor under one."""
    return not any(_holds(bookmark, target) for bookmark in topmost(bookmarks, chosen))


def _can_indent(bookmarks: list[Bookmark], bookmark: Bookmark) -> bool:
    return _index(_level(bookmarks, bookmark), bookmark) > 0


def _can_outdent(bookmarks: list[Bookmark], bookmark: Bookmark) -> bool:
    return _parent(bookmarks, bookmark) is not None


def _checked_title(title: str) -> str:
    title = title.strip()
    if not title:
        message = "a bookmark needs a title"
        raise ValueError(message)
    return title


def _copied(bookmarks: list[Bookmark]) -> tuple[list[Bookmark], dict[int, Bookmark]]:
    """Copy an outline, every bookmark in it; return the copy and the copy of each bookmark, by its id."""
    copies: dict[int, Bookmark] = {}

    def copy_level(level: list[Bookmark]) -> list[Bookmark]:
        copied = []
        for bookmark in level:
            copy = replace(bookmark, children=copy_level(bookmark.children))
            copies[id(bookmark)] = copy
            copied.append(copy)
        return copied

    return copy_level(bookmarks), copies


def _paths(bookmarks: list[Bookmark], above: tuple[Bookmark, ...] = ()) -> Iterable[list[Bookmark]]:
    """Each bookmark of an outline in reading order, as the list of bookmarks from the top level down to it."""
    for bookmark in bookmarks:
        path = [*above, bookmark]
        yield path
        yield from _paths(bookmark.children, tuple(path))


def _parent(bookmarks: list[Bookmark], bookmark: Bookmark) -> Bookmark | None:
    """The bookmark a bookmark is directly under; None at the top level."""
    for path in _paths(bookmarks):
        if path[-1] is bookmark:
            return path[-2] if len(path) > 1 else None
    message = "the bookmark is not in the outline"
    raise ValueError(message)


def _level(bookmarks: list[Bookmark], bookmark: Bookmark) -> list[Bookmark]:
    """The list that holds a bookmark: the top level or the children of its parent."""
    parent = _parent(bookmarks, bookmark)
    return parent.children if parent is not None else bookmarks


def _index(level: list[Bookmark], bookmark: Bookmark) -> int:
    """Where a bookmark is in its level, by identity (equal bookmarks may be side by side)."""
    return next(index for index, other in enumerate(level) if other is bookmark)


def _take_out(bookmarks: list[Bookmark], bookmark: Bookmark) -> None:
    level = _level(bookmarks, bookmark)
    del level[_index(level, bookmark)]


def _swap(bookmarks: list[Bookmark], old: Bookmark, new: Bookmark) -> None:
    level = _level(bookmarks, old)
    level[_index(level, old)] = new


def _holds(bookmark: Bookmark, other: Bookmark) -> bool:
    """Whether other is this bookmark or under it."""
    return bookmark is other or any(_holds(child, other) for child in bookmark.children)
