"""Editing bookmarks from the window (G3 to G7): the actions of the bar of the Bookmarks view (02-interfaz, 6.2; D23).

Each action runs a bookmark edit on the document, so it can be undone, and selects again the bookmarks it edited.
What cannot be done with the bookmarks selected is greyed out (D21).
"""

from collections.abc import Callable
from gettext import ngettext

from gi.repository import Gio, Gtk

from penfold.document.bookmarks import topmost
from penfold.document.commands.bookmarks import (
    DeleteBookmarks,
    IndentBookmarks,
    OutdentBookmarks,
    can_indent,
    can_outdent,
)
from penfold.document.document import OpenDocument
from penfold.document.history import Command
from penfold.ui.sidebar.bookmarks_view import BookmarksView


class BookmarkEditing:
    """The window's actions that edit the bookmarks selected in the Bookmarks view."""

    def __init__(
        self,
        window: Gtk.ApplicationWindow,
        view: BookmarksView,
        document: Callable[[], OpenDocument | None],
        show_undo_toast: Callable[[str, Command], None],
    ) -> None:
        """Add the actions to the window; document gives the document shown, if any."""
        self._view = view
        self._document = document
        self._show_undo_toast = show_undo_toast
        self._actions: dict[str, Gio.SimpleAction] = {}
        for name, handler in {
            "delete-bookmarks": self.delete_selected,
            "indent-bookmarks": self._indent_selected,
            "outdent-bookmarks": self._outdent_selected,
        }.items():
            action = Gio.SimpleAction(name=name, enabled=False)
            action.connect("activate", lambda _action, _parameter, handler=handler: handler())
            window.add_action(action)
            self._actions[name] = action
        for signal in ("selection-changed", "items-changed"):
            view.selection.connect(signal, lambda *_arguments: self.update_actions())

    def update_actions(self) -> None:
        """Turn on what can be done with the bookmarks selected, and off the rest (D21)."""
        document = self._document()
        outline = document.bookmarks if document is not None else []
        selected = self._view.selected_bookmarks() if document is not None else []
        for name, enabled in (
            ("delete-bookmarks", bool(selected)),
            ("indent-bookmarks", can_indent(outline, selected)),
            ("outdent-bookmarks", can_outdent(outline, selected)),
        ):
            self._actions[name].set_enabled(enabled)

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

    def _execute(self, document: OpenDocument, command: IndentBookmarks | OutdentBookmarks) -> None:
        """Make an edit and select the bookmarks it edited."""
        document.execute(command)
        self._view.select(command.bookmarks)
