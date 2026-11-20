"""Undo, redo and the unsaved-changes mark (D16, D19)."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from penfold.document.document import OpenDocument
from penfold.document.history import Change, History
from tests.sample_pdfs import make_pdf


@dataclass
class Append:
    """A command that adds a value to a list."""

    values: list[int]
    value: int
    changes: Change = Change.PAGES

    def apply(self) -> None:
        """Add the value."""
        self.values.append(self.value)

    def revert(self) -> None:
        """Take the value out again."""
        self.values.pop()


@dataclass
class Failing:
    """A command that cannot be applied."""

    changes: Change = Change.PAGES

    def apply(self) -> None:
        """Fail."""
        raise RuntimeError("cannot apply")

    def revert(self) -> None:
        """Never called: the command was never applied."""


def test_new_history_has_nothing_to_undo_redo_or_save() -> None:
    history = History()
    assert not history.can_undo
    assert not history.can_redo
    assert not history.is_modified


def test_undo_and_redo_walk_the_commands_in_order() -> None:
    values: list[int] = []
    history = History()
    history.execute(Append(values, 1))
    history.execute(Append(values, 2))
    assert values == [1, 2]
    history.undo()
    history.undo()
    assert values == []
    assert (history.can_undo, history.can_redo) == (False, True)
    history.redo()
    assert values == [1]
    assert (history.can_undo, history.can_redo) == (True, True)


def test_a_new_command_drops_what_was_undone() -> None:
    values: list[int] = []
    history = History()
    history.execute(Append(values, 1))
    history.undo()
    history.execute(Append(values, 2))
    assert values == [2]
    assert not history.can_redo


def test_undoing_back_to_the_saved_point_leaves_nothing_to_save() -> None:
    values: list[int] = []
    history = History()
    steps = [
        lambda: history.execute(Append(values, 1)),
        lambda: history.mark_saved(history.checkpoint()),
        lambda: history.execute(Append(values, 2)),
        history.undo,
        history.undo,
        history.redo,
    ]
    modified = []
    for step in steps:
        step()
        modified.append(history.is_modified)
    assert modified == [True, False, True, False, True, False]


def test_the_saved_point_is_lost_when_its_branch_is_replaced() -> None:
    values: list[int] = []
    history = History()
    history.execute(Append(values, 1))
    history.mark_saved(history.checkpoint())
    history.undo()
    history.execute(Append(values, 2))
    history.undo()
    assert history.is_modified
    assert values == []


def test_saving_marks_the_state_that_was_written_even_if_it_changed_since() -> None:
    values: list[int] = []
    history = History()
    first, second = Append(values, 1), Append(values, 2)
    history.execute(first)
    written = history.checkpoint()
    history.execute(second)
    history.mark_saved(written)
    assert history.is_modified
    history.undo()
    assert not history.is_modified


def test_saving_a_state_undone_meanwhile_is_reached_by_redo() -> None:
    values: list[int] = []
    history = History()
    history.execute(Append(values, 1))
    history.execute(Append(values, 2))
    written = history.checkpoint()
    history.undo()
    history.undo()
    history.mark_saved(written)
    history.redo()
    assert history.is_modified
    history.redo()
    assert not history.is_modified


def test_saving_a_state_that_cannot_come_back_leaves_changes_to_save() -> None:
    values: list[int] = []
    history = History()
    history.execute(Append(values, 1))
    written = history.checkpoint()
    history.undo()
    history.execute(Append(values, 2))
    history.mark_saved(written)
    history.undo()
    assert history.is_modified


def test_saving_the_empty_history_is_the_state_before_any_edit() -> None:
    values: list[int] = []
    history = History()
    written = history.checkpoint()
    history.execute(Append(values, 1))
    history.mark_saved(written)
    history.undo()
    assert not history.is_modified


def test_a_failing_command_is_not_recorded() -> None:
    history = History()
    command = Failing()
    with pytest.raises(RuntimeError):
        history.execute(command)
    assert not history.can_undo
    assert not history.is_modified


def test_undo_or_redo_with_nothing_to_do_is_an_error() -> None:
    history = History()
    with pytest.raises(IndexError):
        history.undo()
    with pytest.raises(IndexError):
        history.redo()


def test_the_document_tells_its_listeners_what_changed(tmp_path: Path) -> None:
    document = OpenDocument.open(make_pdf(tmp_path / "plain.pdf"))
    heard: list[Change] = []
    document.add_listener(heard.append)
    values: list[int] = []
    document.execute(Append(values, 1, Change.BOOKMARKS))
    assert (document.can_undo, document.can_redo, document.is_modified) == (True, False, True)
    document.undo()
    assert (document.can_undo, document.can_redo, document.is_modified) == (False, True, False)
    document.redo()
    assert heard == [Change.BOOKMARKS] * 3
    assert values == [1]
