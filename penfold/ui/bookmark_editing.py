"""Editing bookmarks from the window (G3 to G7): the actions of the bar of the Bookmarks view (02-interfaz, 6.2; D23).

Each action runs a bookmark edit on the document, so it can be undone, and selects again the bookmarks it edited.
What cannot be done with the bookmarks selected is greyed out (D21).
"""

from collections.abc import Callable
from gettext import gettext as _
from gettext import ngettext

from gi.repository import Gio, GLib, Gtk

from penfold.document.bookmarks import Bookmark, title_from_text, topmost
from penfold.document.commands.bookmarks import (
    AddBookmark,
    BookmarkEdit,
    DeleteBookmarks,
    FormatBookmarks,
    IndentBookmarks,
    MoveBookmarks,
    OutdentBookmarks,
    Placement,
    PointBookmark,
    RenameBookmark,
    can_indent,
    can_outdent,
)
from penfold.document.document import OpenDocument
from penfold.document.history import Command
from penfold.ui.dialogs.text_question import text_question
from penfold.ui.document_view import DocumentView
from penfold.ui.sidebar.bookmark_format import color_to_hex, hex_to_color
from penfold.ui.sidebar.bookmarks_view import BookmarksView


class BookmarkEditing:
    """The window's actions that edit the bookmarks selected in the Bookmarks view."""

    def __init__(
        self,
        window: Gtk.ApplicationWindow,
        view: BookmarksView,
        document_view: DocumentView,
        document: Callable[[], OpenDocument | None],
        show_undo_toast: Callable[[str, Command], None],
    ) -> None:
        """Add the actions to the window; document gives the document shown, if any."""
        self._window = window
        self._view = view
        self._document_view = document_view
        self._document = document
        self._show_undo_toast = show_undo_toast
        self._actions: dict[str, Gio.SimpleAction] = {}
        for name, handler in {
            "add-bookmark": self._add,
            "delete-bookmarks": self.delete_selected,
            "indent-bookmarks": self._indent_selected,
            "outdent-bookmarks": self._outdent_selected,
            "rename-bookmark": self._rename_selected,
            "point-bookmark": self._point_selected,
            "clear-bookmark-format": self._clear_format,
        }.items():
            action = Gio.SimpleAction(name=name, enabled=False)
            action.connect("activate", lambda _action, _parameter, handler=handler: handler())
            window.add_action(action)
            self._actions[name] = action
        for signal in ("selection-changed", "items-changed"):
            view.selection.connect(signal, lambda *_arguments: self.update_actions())
        view.connect("move-requested", self._on_move_requested)
        # The style the bookmarks selected share, shown by the Format panel (G7).
        for name, state in (
            ("bookmark-bold", GLib.Variant.new_boolean(False)),
            ("bookmark-italic", GLib.Variant.new_boolean(False)),
        ):
            action = Gio.SimpleAction.new_stateful(name, None, state)
            action.connect("activate", lambda _action, _parameter, name=name: self._toggle_style(name))
            window.add_action(action)
            self._actions[name] = action
        color = Gio.SimpleAction.new_stateful("bookmark-color", GLib.VariantType.new("s"), GLib.Variant.new_string(""))
        color.connect("activate", lambda _action, parameter: self._color(parameter.get_string()))
        window.add_action(color)
        self._actions["bookmark-color"] = color

    def update_actions(self) -> None:
        """Turn on what can be done with the bookmarks selected, and off the rest (D21)."""
        document = self._document()
        outline = document.bookmarks if document is not None else []
        selected = self._view.selected_bookmarks() if document is not None else []
        for name, enabled in (
            ("add-bookmark", document is not None),
            ("delete-bookmarks", bool(selected)),
            ("indent-bookmarks", can_indent(outline, selected)),
            ("outdent-bookmarks", can_outdent(outline, selected)),
            ("rename-bookmark", len(selected) == 1),
            ("point-bookmark", len(selected) == 1),
            ("clear-bookmark-format", bool(selected)),
            ("bookmark-bold", bool(selected)),
            ("bookmark-italic", bool(selected)),
            ("bookmark-color", bool(selected)),
        ):
            self._actions[name].set_enabled(enabled)
        colors = {color_to_hex(bookmark.color) if bookmark.color is not None else "" for bookmark in selected}
        self._actions["bookmark-bold"].set_state(GLib.Variant.new_boolean(_all_bold(selected)))
        self._actions["bookmark-italic"].set_state(GLib.Variant.new_boolean(_all_italic(selected)))
        self._actions["bookmark-color"].set_state(GLib.Variant.new_string(colors.pop() if len(colors) == 1 else ""))

    def _add(self) -> None:
        """Add a bookmark titled with the text selected in the document, at its page (G3).

        With no text selected, ask for the title of a bookmark at the current page, proposing "Page N".
        """
        document = self._document()
        if document is None:
            return
        selected = self._document_view.selected_text()
        title = title_from_text(selected[0]) if selected is not None else ""
        if title and selected is not None:
            self.add(title, selected[1])
            return
        position = self._document_view.current_page
        proposed = _("Page {label}").format(label=document.page_label(position))
        text_question(_("Add Bookmark"), proposed, _("_Add"), lambda answer: self.add(answer, position)).present(
            self._window
        )

    def add(self, title: str, position: int) -> None:
        """Add a bookmark with this title leading to the page at a position, and select it."""
        document = self._document()
        if document is not None and 0 <= position < document.page_count:
            self._execute(document, AddBookmark(document, title, position))

    def can_delete(self) -> bool:
        """Whether some bookmarks are selected to delete (with the Delete key, for example)."""
        return self._actions["delete-bookmarks"].get_enabled()

    def delete_selected(self) -> None:
        """Delete the bookmarks selected at once, with a notice to undo it (G4, D19)."""
        document = self._document()
        if document is None:
            return
        selected = self._view.selected_bookmarks()
        count = len(topmost(document.bookmarks, selected))
        command = DeleteBookmarks(document, selected)
        document.execute(command)
        message = ngettext("Bookmark deleted", "{count} bookmarks deleted", count).format(count=count)
        self._show_undo_toast(message, command)

    def _indent_selected(self) -> None:
        document = self._document()
        if document is not None:
            self._execute(document, IndentBookmarks(document, self._view.selected_bookmarks()))

    def _outdent_selected(self) -> None:
        document = self._document()
        if document is not None:
            self._execute(document, OutdentBookmarks(document, self._view.selected_bookmarks()))

    def _rename_selected(self) -> None:
        """Ask for a new title for the bookmark selected (G5)."""
        document = self._document()
        if document is None:
            return
        [bookmark] = self._view.selected_bookmarks()

        def rename(title: str) -> None:
            if document is self._document():
                self._execute(document, RenameBookmark(document, bookmark, title))

        text_question(_("Edit Text"), bookmark.title, _("_Save"), rename).present(self._window)

    def _point_selected(self) -> None:
        """Make the bookmark selected lead to the start of the current page (G5)."""
        document = self._document()
        if document is not None:
            [bookmark] = self._view.selected_bookmarks()
            self._execute(document, PointBookmark(document, bookmark, self._document_view.current_page))

    def _toggle_style(self, name: str) -> None:
        """Make the bookmarks selected bold (or italic), or not if they all are, as 0.6 does (G7)."""
        document = self._document()
        if document is None:
            return
        selected = self._view.selected_bookmarks()
        if name == "bookmark-bold":
            command = FormatBookmarks(document, selected, bold=not _all_bold(selected))
        else:
            command = FormatBookmarks(document, selected, italic=not _all_italic(selected))
        self._execute(document, command)

    def _color(self, value: str) -> None:
        """Give the bookmarks selected a colour of the Format panel (G7)."""
        document = self._document()
        if document is not None:
            selected = self._view.selected_bookmarks()
            self._execute(document, FormatBookmarks(document, selected, color=hex_to_color(value)))

    def _clear_format(self) -> None:
        """Take bold, italic and colour away from the bookmarks selected (G7)."""
        document = self._document()
        if document is not None:
            selected = self._view.selected_bookmarks()
            self._execute(document, FormatBookmarks(document, selected, bold=False, italic=False, color=None))

    def _on_move_requested(
        self, _view: BookmarksView, dragged: list[Bookmark], target: Bookmark | None, placement: Placement
    ) -> None:
        """Move dragged bookmarks (G6); dropping them where they already are changes nothing."""
        document = self._document()
        if document is not None:
            self._execute(document, MoveBookmarks(document, dragged, target, placement))

    def _execute(self, document: OpenDocument, command: BookmarkEdit) -> None:
        """Make an edit, unless it changes nothing, and select the bookmarks it edited."""
        if command.changes_anything:
            document.execute(command)
            self._view.select(command.bookmarks)


def _all_bold(bookmarks: list[Bookmark]) -> bool:
    """Whether there are bookmarks and all of them are bold."""
    return bool(bookmarks) and all(bookmark.bold for bookmark in bookmarks)


def _all_italic(bookmarks: list[Bookmark]) -> bool:
    """Whether there are bookmarks and all of them are italic."""
    return bool(bookmarks) and all(bookmark.italic for bookmark in bookmarks)
