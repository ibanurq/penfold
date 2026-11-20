"""The "Add Pages" dialogue and adding pages from the window (E4 to E6, D48)."""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from gi.repository import Adw

from penfold.document.pages import PaperSize
from tests.gtk_helpers import process_pending_events
from tests.sample_pdfs import make_pdf
from tests.test_document_window import action_enabled, open_and_wait

if TYPE_CHECKING:
    from penfold.application import PenfoldApplication
    from penfold.ui.dialogs.add_pages_dialog import PenfoldAddPagesDialog
    from penfold.ui.window import PenfoldWindow


@pytest.fixture
def window(application: "PenfoldApplication") -> Iterator["PenfoldWindow"]:
    from penfold.ui.window import PenfoldWindow

    new_window = PenfoldWindow(application)
    new_window.set_default_size(1100, 750)
    new_window.present()
    yield new_window
    dialog = new_window.get_visible_dialog()
    if dialog is not None:
        dialog.force_close()
    new_window.destroy()
    process_pending_events()


def make_dialog(
    page_count: int, current_page: int, selected: list[int], page_label: Callable[[int], str] | None = None
) -> "PenfoldAddPagesDialog":
    from penfold.ui.dialogs.add_pages_dialog import PenfoldAddPagesDialog

    return PenfoldAddPagesDialog(page_count, current_page, selected, page_label)


def test_without_selection_it_proposes_the_end(application: "PenfoldApplication") -> None:  # noqa: ARG001
    dialog = make_dialog(10, 3, [])
    assert dialog.end_check.get_active()
    assert dialog.page_spin.get_value_as_int() == 4  # the page being read, as 0.6
    assert not dialog.add_button.get_sensitive()  # no file chosen yet
    dialog.blank_check.set_active(True)
    assert dialog.add_button.get_sensitive()
    assert dialog.choice.position == 10
    assert dialog.choice.source is PaperSize.A4


def test_with_pages_selected_it_proposes_after_the_last_one(application: "PenfoldApplication") -> None:  # noqa: ARG001
    dialog = make_dialog(10, 0, [2, 7, 4])
    assert dialog.after_check.get_active()
    assert dialog.page_spin.get_value_as_int() == 8
    dialog.choose_file(Path("/some/where/other.pdf"))
    assert dialog.choice.position == 8  # before the page after the eighth
    assert dialog.choice.source == Path("/some/where/other.pdf")
    assert dialog.pdf_row.get_subtitle() == "other.pdf"


def test_choosing_a_size_or_a_page_chooses_its_option(application: "PenfoldApplication") -> None:  # noqa: ARG001
    dialog = make_dialog(5, 0, [])
    dialog.size_dropdown.set_selected(1)
    assert dialog.blank_check.get_active()
    assert dialog.choice.source is PaperSize.LETTER
    dialog.page_spin.set_value(2)
    assert dialog.after_check.get_active()
    dialog.start_check.set_active(True)
    assert dialog.choice.position == 0


def test_the_window_adds_the_chosen_pages(window: "PenfoldWindow", tmp_path: Path) -> None:
    from penfold.ui.dialogs.add_pages_dialog import PagesToAdd

    open_and_wait(window, make_pdf(tmp_path / "plain.pdf", page_count=3))
    document = window.document
    assert document is not None
    assert action_enabled(window, "add-pages")
    window.add_pages(PagesToAdd(make_pdf(tmp_path / "two.pdf", page_count=2), 1))
    assert document.page_count == 5
    assert window.document_view.current_page == 1
    window.add_pages(PagesToAdd(PaperSize.A5, 5))
    assert document.page_count == 6
    document.undo()
    assert document.page_count == 5


@pytest.mark.parametrize("name", ["locked.pdf", "missing.pdf"])
def test_the_window_says_why_pages_cannot_be_added(window: "PenfoldWindow", tmp_path: Path, name: str) -> None:
    from penfold.ui.dialogs.add_pages_dialog import PagesToAdd

    open_and_wait(window, make_pdf(tmp_path / "plain.pdf"))
    if name == "locked.pdf":
        make_pdf(tmp_path / name, passwords=("owner", ""))
    window.add_pages(PagesToAdd(tmp_path / name, 0))
    assert window.document is not None
    assert window.document.page_count == 3
    message = window.get_visible_dialog()
    assert isinstance(message, Adw.AlertDialog)
    assert name in (message.get_heading() or "")


def test_pages_cannot_be_added_to_a_protected_pdf(window: "PenfoldWindow", tmp_path: Path) -> None:
    open_and_wait(window, make_pdf(tmp_path / "locked.pdf", passwords=("owner", "")))
    assert not action_enabled(window, "add-pages")


def test_with_page_labels_the_label_of_the_page_is_shown(application: "PenfoldApplication") -> None:  # noqa: ARG001
    labels = ["i", "ii", "1", "2", "3"]
    dialog = make_dialog(5, 0, [3], labels.__getitem__)
    assert dialog.after_row.get_subtitle() == "Page 2 (4 of 5)"
    dialog.page_spin.set_value(1)
    assert dialog.after_row.get_subtitle() == "Page i (1 of 5)"
    assert make_dialog(5, 0, [3]).after_row.get_subtitle() in {None, ""}  # nothing without labels
