"""Protected PDFs in phase 6 (D58, J6, K3): the red lock, Ctrl+P and the question about changes."""

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from gi.repository import Adw

from penfold.document.commands.pages import RotatePages
from tests.gtk_helpers import process_pending_events
from tests.sample_pdfs import make_pdf
from tests.test_document_window import action_enabled, open_and_wait, window

if TYPE_CHECKING:
    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]


@pytest.fixture
def locked_window(window: "PenfoldWindow", tmp_path: Path) -> "PenfoldWindow":
    assert open_and_wait(window, make_pdf(tmp_path / "locked.pdf", passwords=("owner", "")))
    notice = window.get_visible_dialog()
    assert notice is not None
    notice.force_close()
    process_pending_events()
    return window


def test_a_protected_pdf_has_a_red_lock_in_the_header(locked_window: "PenfoldWindow", tmp_path: Path) -> None:
    icon = locked_window.document_header.protected_icon
    assert (icon.get_visible(), icon.has_css_class("error")) == (True, True)
    assert open_and_wait(locked_window, make_pdf(tmp_path / "open.pdf"))
    assert not icon.get_visible()


def test_ctrl_p_says_why_a_protected_pdf_cannot_be_printed(
    locked_window: "PenfoldWindow", monkeypatch: pytest.MonkeyPatch
) -> None:
    toasts: list[str] = []
    monkeypatch.setattr(locked_window.toast_overlay, "add_toast", lambda toast: toasts.append(toast.get_title()))
    assert not action_enabled(locked_window, "print")
    assert action_enabled(locked_window, "print-shortcut")
    locked_window.activate_action("win.print-shortcut", None)
    assert toasts == [
        "This PDF is protected against changes: Penfold cannot save it, print it or extract pages from it yet."
    ]
    assert locked_window.get_visible_dialog() is None


def test_changes_to_a_protected_pdf_can_only_be_discarded(locked_window: "PenfoldWindow") -> None:
    document = locked_window.document
    assert document is not None
    document.execute(RotatePages(document, [0], 90))
    answers: list[bool] = []
    locked_window.confirm_discard(answers.append)
    dialog = locked_window.get_visible_dialog()
    assert isinstance(dialog, Adw.AlertDialog)
    assert dialog.get_heading() == "Discard the changes to “locked.pdf”?"
    assert (dialog.has_response("save"), dialog.get_default_response()) == (False, "cancel")
    dialog.emit("response", "discard")
    dialog.close()
    assert answers == [True]
