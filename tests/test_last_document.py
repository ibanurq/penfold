"""Start With Last Document (07-fase-12, 9): the last document shown opens again when Penfold starts without files."""

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from gi.repository import Gio

from penfold import config
from penfold.ui.document_view import Fit, ReadingPosition
from penfold.ui.reading_positions import ReadingPositions
from tests.gtk_helpers import process_pending_events, wait_until
from tests.sample_pdfs import make_pdf
from tests.test_document_window import open_and_wait, window

if TYPE_CHECKING:
    from penfold.application import PenfoldApplication
    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]


@pytest.fixture
def settings(application: "PenfoldApplication") -> Iterator[Gio.Settings]:  # noqa: ARG001 (the tests' settings)
    """Penfold's settings, with no last document; afterwards, the option off again, as in all tests (conftest)."""
    penfold_settings = Gio.Settings(schema_id=config.APP_ID)
    penfold_settings.reset("last-document")
    yield penfold_settings
    penfold_settings.reset("last-document")
    penfold_settings.set_boolean("open-last-document", False)


def test_the_option_is_on_by_default(settings: Gio.Settings) -> None:
    default = settings.get_default_value("open-last-document")
    assert default is not None
    assert default.get_boolean()


def test_the_document_shown_is_noted_as_the_last_one(
    window: "PenfoldWindow", tmp_path: Path, settings: Gio.Settings
) -> None:
    first, second = make_pdf(tmp_path / "first.pdf"), make_pdf(tmp_path / "second.pdf")
    assert open_and_wait(window, first)
    assert settings.get_string("last-document") == str(first)
    assert open_and_wait(window, second)
    assert settings.get_string("last-document") == str(second)


def test_the_last_document_opens_where_it_was_left(
    window: "PenfoldWindow", tmp_path: Path, settings: Gio.Settings
) -> None:
    report = make_pdf(tmp_path / "report.pdf", 8)
    ReadingPositions().remember(report, ReadingPosition(5, 0.3, Fit.WIDTH, 1.0))
    settings.set_string("last-document", str(report))
    assert window.open_last_document()
    view = window.document_view
    wait_until(lambda: bool(view._boxes))
    process_pending_events()
    assert window.document is not None
    assert (window.document.path, view.current_page) == (report, 5)


@pytest.mark.parametrize("last", ["", "missing.pdf", "damaged.pdf"])
def test_without_a_last_document_that_opens_the_welcome_page_stays_saying_nothing(
    window: "PenfoldWindow", tmp_path: Path, settings: Gio.Settings, last: str
) -> None:
    (tmp_path / "damaged.pdf").write_text("not a PDF")
    settings.set_string("last-document", str(tmp_path / last) if last else "")
    assert not window.open_last_document()
    process_pending_events()
    assert (window.document, window.stack.get_visible_child_name(), window.get_visible_dialog()) == (
        None,
        "welcome",
        None,
    )


def first_window(application: "PenfoldApplication") -> "PenfoldWindow":
    """Close every window and start Penfold without files, as from the desktop; return its window."""
    from penfold.ui.window import PenfoldWindow

    for old in application.get_windows():
        old.destroy()
    process_pending_events()
    application.activate()
    process_pending_events()
    started = application.get_active_window()
    assert isinstance(started, PenfoldWindow)
    return started


@pytest.mark.parametrize("wanted", [True, False])
def test_starting_without_files_opens_the_last_document_if_wanted(
    application: "PenfoldApplication", tmp_path: Path, settings: Gio.Settings, wanted: bool
) -> None:
    report = make_pdf(tmp_path / "report.pdf")
    settings.set_string("last-document", str(report))
    settings.set_boolean("open-last-document", wanted)
    started = first_window(application)
    try:
        assert (started.document is not None) == wanted
    finally:
        started.destroy()
        process_pending_events()


def test_a_new_window_starts_empty(application: "PenfoldApplication", tmp_path: Path, settings: Gio.Settings) -> None:
    settings.set_string("last-document", str(make_pdf(tmp_path / "report.pdf")))
    settings.set_boolean("open-last-document", True)
    started = first_window(application)
    try:
        application.activate_action("new-window", None)
        process_pending_events()
        new = [other for other in application.get_windows() if other is not started]
        assert [getattr(other, "document", "missing") for other in new] == [None]
    finally:
        for other in application.get_windows():
            other.destroy()
        process_pending_events()
