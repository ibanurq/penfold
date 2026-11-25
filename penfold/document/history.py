"""Undo and redo.

Every change to the document is a command that knows how to apply itself and how to revert itself. The history keeps the
commands applied and the commands undone, and remembers where the document was last saved, so that undoing back to that
point leaves nothing to save.
"""

import enum
from collections.abc import Callable
from typing import Protocol


class Change(enum.Flag):
    """The parts of the document a command changes, so the interface only refreshes what it must."""

    PAGES = enum.auto()
    ANNOTATIONS = enum.auto()
    BOOKMARKS = enum.auto()
    FORM = enum.auto()
    FILE = enum.auto()
    """Where the document is saved, or whether it has changes to save."""
    PERMISSIONS = enum.auto()
    """What the document allows: whether its user access permissions are respected."""


class Command(Protocol):
    """A change to the document that can be undone.

    A command keeps only what it needs to revert itself, never a copy of the PDF. It is created for one document and
    applied to it.
    """

    @property
    def changes(self) -> Change:
        """The parts of the document the command changes."""
        ...

    def apply(self) -> None:
        """Make the change (the first time, and again on redo)."""
        ...

    def revert(self) -> None:
        """Undo the change, leaving the document exactly as it was before apply."""
        ...


class History:
    """The commands applied to a document, in order, and those undone that can be redone."""

    def __init__(self, *, saved: bool = True) -> None:
        """Start an empty history for a document just opened, which has nothing to save.

        A document that was never saved (merged) has changes to save until it is, even with nothing to undo.
        """
        self._applied: list[Command] = []
        self._undone: list[Command] = []
        # How many commands were applied when the document was last saved; None once that state cannot come back.
        self._saved_at: int | None = 0 if saved else None

    @property
    def can_undo(self) -> bool:
        """Whether there is a change to undo."""
        return bool(self._applied)

    @property
    def can_redo(self) -> bool:
        """Whether there is an undone change to redo."""
        return bool(self._undone)

    @property
    def is_modified(self) -> bool:
        """Whether the document differs from the file it was last saved to (or opened from)."""
        return self._saved_at != len(self._applied)

    def execute(self, command: Command) -> None:
        """Apply a new command and record it; the undone commands can no longer be redone.

        If the command fails, nothing is recorded and the error goes up.
        """
        command.apply()
        if self._saved_at is not None and self._saved_at > len(self._applied):
            self._saved_at = None
        self._applied.append(command)
        self._undone.clear()

    def amend(self, command: Command, change: Callable[[], None]) -> bool:
        """Change the last command applied in place, if it is this one and the document was not saved after it.

        Typing in a form field changes its value many times: amending keeps all of it as one edit to undo. Returns
        whether the command was amended; if not, nothing is done, and the change goes in a new command.
        """
        if not self._applied or self._applied[-1] is not command or self._saved_at == len(self._applied):
            return False
        change()
        return True

    def undo(self) -> Command:
        """Revert the last command applied and return it.

        Raises:
            IndexError: there is nothing to undo.
        """
        command = self._applied[-1]
        command.revert()
        self._undone.append(self._applied.pop())
        return command

    def redo(self) -> Command:
        """Apply again the last command undone and return it.

        Raises:
            IndexError: there is nothing to redo.
        """
        command = self._undone[-1]
        command.apply()
        self._applied.append(self._undone.pop())
        return command

    def checkpoint(self) -> Command | None:
        """Return the last command applied (None for none), to say later which state was saved."""
        return self._applied[-1] if self._applied else None

    def mark_saved(self, checkpoint: Command | None) -> None:
        """Remember that the document was saved as it was at a checkpoint.

        Saving takes a while, and the document may change meanwhile: what counts is the state that was written. If
        that state can no longer come back (it was undone and replaced), the document has changes to save whatever
        is done.
        """
        # The states in order: none applied, each applied command, then the undone ones as redo would apply them.
        states = [None, *self._applied, *reversed(self._undone)]
        self._saved_at = next((depth for depth, state in enumerate(states) if state is checkpoint), None)
