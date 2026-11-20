"""The "Extract Pages" dialogue and extracting from the window (E7 to E9, D51)."""

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
import pytest
from gi.repository import Adw

from tests.gtk_helpers import process_pending_events, wait_until
from tests.sample_pdfs import make_pdf
from tests.test_document_window import action_enabled, open_and_wait

if TYPE_CHECKING:
    from penfold.application import PenfoldApplication
    from penfold.ui.dialogs.extract_pages_dialog import PagesToExtract, PenfoldExtractPagesDialog
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


def make_dialog(page_count: int, selected: list[int]) -> "PenfoldExtractPagesDialog":
    from penfold.ui.dialogs.extract_pages_dialog import PenfoldExtractPagesDialog

    return PenfoldExtractPagesDialog(page_count, selected)


def requests_of(dialog: "PenfoldExtractPagesDialog") -> list["PagesToExtract"]:
    requests: list[PagesToExtract] = []
    dialog.connect("extract-requested", lambda _dialog, request: requests.append(request))
    return requests


def test_it_starts_with_the_selected_pages(application: "PenfoldApplication") -> None:  # noqa: ARG001
    dialog = make_dialog(20, [0, 4, 9, 10, 11])
    assert dialog.pages_row.get_text() == "1, 5, 10-12"
    requests = requests_of(dialog)
    dialog.separate_row.set_active(True)
    dialog.extract_button.emit("clicked")
    [request] = requests
    assert (request.positions, request.separate, request.delete_after) == ([0, 4, 9, 10, 11], True, False)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "Enter at least one page."),
        ("1, x", "Invalid format: “x”."),
        ("5-2", "Invalid range: “5-2”."),
        ("4-30", "Page 30 does not exist (the document has 20)."),
    ],
)
def test_a_wrong_list_is_explained_and_nothing_is_extracted(
    application: "PenfoldApplication",  # noqa: ARG001
    text: str,
    message: str,
) -> None:
    dialog = make_dialog(20, [])
    requests = requests_of(dialog)
    dialog.pages_row.set_text(text)
    dialog.extract_button.emit("clicked")
    assert requests == []
    assert dialog.error_label.get_visible()
    assert dialog.error_label.get_label() == message
    dialog.pages_row.set_text("1")
    assert not dialog.error_label.get_visible()  # it goes away while the list is corrected


def test_every_page_cannot_be_deleted_after(application: "PenfoldApplication") -> None:  # noqa: ARG001
    dialog = make_dialog(3, [0, 1, 2])
    requests = requests_of(dialog)
    dialog.delete_row.set_active(True)
    dialog.extract_button.emit("clicked")
    assert requests == []
    assert "turn off" in dialog.error_label.get_label()


def extraction(window: "PenfoldWindow", request: "PagesToExtract") -> tuple[object, list[bool]]:
    from penfold.ui.extraction import PageExtraction

    assert window.document is not None
    finished: list[bool] = []
    return PageExtraction(window, window.document, request, finished.append), finished


def test_files_are_written_in_the_folder(window: "PenfoldWindow", tmp_path: Path) -> None:
    from penfold.ui.dialogs.extract_pages_dialog import PagesToExtract

    open_and_wait(window, make_pdf(tmp_path / "five.pdf", page_count=5))
    folder = tmp_path / "out"
    folder.mkdir()
    job, finished = extraction(window, PagesToExtract([1, 3], separate=True, delete_after=False))
    job.extract_into(folder)  # type: ignore[attr-defined]
    wait_until(lambda: bool(finished))
    assert finished == [True]
    assert sorted(path.name for path in folder.iterdir()) == ["extracted_01.pdf", "extracted_02.pdf"]
    with pikepdf.open(folder / "extracted_02.pdf") as extracted:
        assert len(extracted.pages) == 1


@pytest.mark.parametrize(
    ("response", "names"), [("rename", ["extracted (2).pdf", "extracted.pdf"]), ("cancel", ["extracted.pdf"])]
)
def test_names_taken_are_asked_about(window: "PenfoldWindow", tmp_path: Path, response: str, names: list[str]) -> None:
    from penfold.ui.dialogs.extract_pages_dialog import PagesToExtract

    open_and_wait(window, make_pdf(tmp_path / "five.pdf", page_count=5))
    folder = tmp_path / "out"
    folder.mkdir()
    (folder / "extracted.pdf").write_bytes(b"there before")
    job, finished = extraction(window, PagesToExtract([0, 1], separate=False, delete_after=False))
    job.extract_into(folder)  # type: ignore[attr-defined]
    question = window.get_visible_dialog()
    assert isinstance(question, Adw.AlertDialog)
    assert "extracted.pdf" in question.get_body()
    question.emit("response", response)
    question.close()
    wait_until(lambda: bool(finished))
    assert sorted(path.name for path in folder.iterdir()) == names
    assert (folder / "extracted.pdf").read_bytes() == b"there before"


def test_overwriting_replaces_the_file(window: "PenfoldWindow", tmp_path: Path) -> None:
    from penfold.ui.dialogs.extract_pages_dialog import PagesToExtract

    open_and_wait(window, make_pdf(tmp_path / "five.pdf", page_count=5))
    (tmp_path / "extracted.pdf").write_bytes(b"there before")
    job, finished = extraction(window, PagesToExtract([0], separate=False, delete_after=False))
    job.extract_into(tmp_path)  # type: ignore[attr-defined]
    question = window.get_visible_dialog()
    assert isinstance(question, Adw.AlertDialog)
    question.emit("response", "overwrite")
    question.close()
    wait_until(lambda: bool(finished))
    with pikepdf.open(tmp_path / "extracted.pdf") as extracted:
        assert len(extracted.pages) == 1


def test_pages_extracted_are_deleted_after_if_asked(window: "PenfoldWindow", tmp_path: Path) -> None:
    from penfold.ui.dialogs.extract_pages_dialog import PagesToExtract

    open_and_wait(window, make_pdf(tmp_path / "five.pdf", page_count=5))
    document = window.document
    assert document is not None
    window._after_extracting(document, PagesToExtract([1, 2], separate=False, delete_after=True), [1, 2])
    assert document.page_count == 3
    document.undo()
    assert document.page_count == 5


def test_pages_of_a_protected_pdf_cannot_be_extracted(window: "PenfoldWindow", tmp_path: Path) -> None:
    open_and_wait(window, make_pdf(tmp_path / "locked.pdf", passwords=("owner", "")))
    assert not action_enabled(window, "extract-pages")
    open_and_wait(window, make_pdf(tmp_path / "plain.pdf"))
    assert action_enabled(window, "extract-pages")
