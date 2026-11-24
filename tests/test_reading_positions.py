"""Where each document was left (07-fase-12, 9): the file that keeps it, and documents opening there again."""

import json
import math
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from gi.repository import Gio

from penfold import config
from penfold.ui.document_view import Fit, ReadingPosition
from penfold.ui.reading_positions import REMEMBERED_DOCUMENTS, ReadingPositions
from tests.gtk_helpers import process_pending_events, wait_until_stable
from tests.sample_pdfs import make_pdf
from tests.test_document_window import open_and_wait, window

if TYPE_CHECKING:
    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]

POSITION = ReadingPosition(page=4, depth=0.25, fit=Fit.MANUAL, zoom=1.6)


def test_a_position_is_remembered_by_the_documents_path(tmp_path: Path) -> None:
    positions = ReadingPositions(tmp_path / "data" / "positions.json")  # The folder is made when needed.
    assert positions.get(tmp_path / "a.pdf") is None
    positions.remember(tmp_path / "a.pdf", POSITION)
    assert ReadingPositions(positions.path).get(tmp_path / "a.pdf") == POSITION
    assert positions.get(tmp_path / "b.pdf") is None


def test_only_the_most_recent_documents_are_remembered(tmp_path: Path) -> None:
    positions = ReadingPositions(tmp_path / "positions.json")
    for number in range(REMEMBERED_DOCUMENTS + 1):
        positions.remember(tmp_path / f"{number}.pdf", POSITION)
    positions.remember(tmp_path / "1.pdf", POSITION)  # Opened again: now the most recent.
    positions.remember(tmp_path / "new.pdf", POSITION)
    assert [positions.get(tmp_path / f"{name}.pdf") is not None for name in ("0", "1", "2", "3", "new")] == [
        False,
        True,
        False,
        True,
        True,
    ]


@pytest.mark.parametrize("content", ["not json", '["a list"]', '{"documents": 3}'])
def test_a_damaged_file_remembers_nothing_and_is_replaced(tmp_path: Path, content: str) -> None:
    path = tmp_path / "positions.json"
    path.write_text(content)
    positions = ReadingPositions(path)
    assert positions.get(tmp_path / "a.pdf") is None
    positions.remember(tmp_path / "a.pdf", POSITION)
    assert positions.get(tmp_path / "a.pdf") == POSITION


def test_invalid_positions_in_the_file_are_left_out(tmp_path: Path) -> None:
    path = tmp_path / "positions.json"
    good = {"page": 2, "depth": 0.5, "fit": "width", "zoom": 1}
    documents = {
        "/good.pdf": good,
        "/negative.pdf": {**good, "page": -1},
        "/fit.pdf": {**good, "fit": "sideways"},
        "/zoom.pdf": {**good, "zoom": 0},
        "/missing.pdf": {"page": 2},
    }
    path.write_text(json.dumps({"documents": documents}))
    positions = ReadingPositions(path)
    assert [positions.get(Path(name)) is not None for name in documents] == [True, False, False, False, False]
    assert positions.get(Path("/good.pdf")) == ReadingPosition(2, 0.5, Fit.WIDTH, 1.0)


def test_a_file_that_cannot_be_written_is_only_logged(tmp_path: Path) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("a file where the folder should be")
    ReadingPositions(blocked / "positions.json").remember(tmp_path / "a.pdf", POSITION)


@pytest.fixture
def remembering(reading_positions_file: Path) -> Iterator[Gio.Settings]:
    """Start with nothing remembered; give the settings, put back to their defaults afterwards."""
    reading_positions_file.unlink(missing_ok=True)
    settings = Gio.Settings(schema_id=config.APP_ID)
    yield settings
    settings.reset("remember-position")


def read_on(window: "PenfoldWindow", page: int) -> None:
    """Go to a page and zoom in by hand, as a reader would."""
    view = window.document_view
    view.go_to(page)
    view.zoom_in()
    process_pending_events()


def test_a_document_opens_again_where_it_was_left(
    window: "PenfoldWindow",
    tmp_path: Path,
    remembering: Gio.Settings,  # noqa: ARG001
) -> None:
    report, other = make_pdf(tmp_path / "report.pdf", 12), make_pdf(tmp_path / "other.pdf")
    assert open_and_wait(window, report)
    read_on(window, 6)
    view = window.document_view
    left = view.reading_position()
    assert left is not None
    assert (left.page, left.fit) == (6, Fit.MANUAL)
    assert open_and_wait(window, other)  # Replacing it keeps where it was left.
    assert (view.current_page, view.fit) == (0, Fit.WIDTH)  # Never opened before: from the start.
    assert open_and_wait(window, report)
    wait_until_stable(lambda: (view.current_page, view.zoom))
    shown = view.reading_position()
    assert shown is not None
    assert (shown.page, shown.fit, math.isclose(shown.zoom, left.zoom)) == (6, Fit.MANUAL, True)
    assert math.isclose(shown.depth, left.depth, abs_tol=0.01)
    assert window.document_header.page_entry.entry.get_text() == "7"


def test_without_the_preference_documents_open_from_the_start(
    window: "PenfoldWindow", tmp_path: Path, remembering: Gio.Settings
) -> None:
    report, other = make_pdf(tmp_path / "report.pdf", 12), make_pdf(tmp_path / "other.pdf")
    remembering.set_boolean("remember-position", False)
    assert open_and_wait(window, report)
    read_on(window, 6)
    assert open_and_wait(window, other)
    remembering.set_boolean("remember-position", True)
    assert open_and_wait(window, report)  # Nothing was kept while it was off.
    assert window.document_view.current_page == 0


def test_a_remembered_page_beyond_the_end_opens_from_the_start(
    window: "PenfoldWindow",
    tmp_path: Path,
    remembering: Gio.Settings,  # noqa: ARG001
) -> None:
    report = make_pdf(tmp_path / "report.pdf")
    ReadingPositions().remember(report, POSITION)  # Page 5 of a PDF that now has 3.
    assert open_and_wait(window, report)
    assert (window.document_view.current_page, window.document_view.fit) == (0, Fit.WIDTH)
