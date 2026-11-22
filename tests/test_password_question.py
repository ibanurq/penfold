"""Opening a PDF with an open password from the window (D61, 4): the dialogue that asks for it."""

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from gi.repository import Adw, Gtk

from tests.gtk_helpers import process_pending_events, wait_until
from tests.sample_pdfs import OWNER_PASSWORD, USER_PASSWORD, make_pdf, make_pdf_with_password
from tests.test_document_window import action_enabled, open_and_wait, window

if TYPE_CHECKING:
    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]


@pytest.fixture
def secret(tmp_path: Path) -> Path:
    return make_pdf_with_password(tmp_path / "secret.pdf", "print_lowres")


def asked(window: "PenfoldWindow", path: Path) -> Adw.AlertDialog:
    """Open a PDF with a password, and return the dialogue that asks for it."""
    assert not window.open_file(path)
    dialog = window.get_visible_dialog()
    assert isinstance(dialog, Adw.AlertDialog)
    return dialog


def parts(dialog: Adw.AlertDialog) -> tuple[Gtk.PasswordEntry, Gtk.Label]:
    """The password box and the line that says it was wrong."""
    box = dialog.get_extra_child()
    assert box is not None
    entry, wrong = list(box)
    assert isinstance(entry, Gtk.PasswordEntry)
    assert isinstance(wrong, Gtk.Label)
    return entry, wrong


def answer(dialog: Adw.AlertDialog, password: str) -> None:
    entry, _wrong = parts(dialog)
    entry.set_text(password)
    dialog.emit("response", "open")
    process_pending_events()


def test_a_pdf_with_a_password_asks_for_it(window: "PenfoldWindow", secret: Path) -> None:
    dialog = asked(window, secret)
    entry, wrong = parts(dialog)
    assert dialog.get_heading() == "Protected Document"
    assert dialog.get_body() == "Opening “secret.pdf” requires its password."
    assert entry.get_property("show-peek-icon")
    assert not wrong.get_visible()
    assert not dialog.get_response_enabled("open")  # nothing typed yet
    entry.set_text("x")
    assert dialog.get_response_enabled("open")
    dialog.force_close()


def test_a_wrong_password_keeps_asking_and_the_right_one_opens_it(window: "PenfoldWindow", secret: Path) -> None:
    dialog = asked(window, secret)
    answer(dialog, "wrong")
    entry, wrong = parts(dialog)
    assert window.get_visible_dialog() is dialog
    assert (wrong.get_visible(), wrong.has_css_class("error"), entry.get_text()) == (True, True, "")
    assert window.is_empty
    answer(dialog, USER_PASSWORD)
    wait_until(lambda: window.get_visible_dialog() is None)
    assert window.document is not None
    assert window.document.file_name == "secret.pdf"


def test_the_open_password_shows_the_lock(window: "PenfoldWindow", secret: Path) -> None:
    answer(asked(window, secret), USER_PASSWORD)
    assert window.document_header.protected_icon.get_visible()
    assert not action_enabled(window, "add-bookmark")  # the PDF does not allow editing its bookmarks


def test_the_owner_password_opens_it_with_every_tool_and_no_lock(window: "PenfoldWindow", secret: Path) -> None:
    answer(asked(window, secret), OWNER_PASSWORD)
    assert window.document is not None
    assert not window.document_header.protected_icon.get_visible()
    assert action_enabled(window, "add-bookmark")


@pytest.mark.parametrize("how", ["cancel", "escape"])
def test_cancel_or_escape_open_nothing_and_keep_what_was_shown(
    window: "PenfoldWindow", secret: Path, tmp_path: Path, how: str
) -> None:
    assert open_and_wait(window, make_pdf(tmp_path / "book.pdf"))
    dialog = asked(window, secret)
    if how == "cancel":
        dialog.emit("response", "cancel")
    else:
        dialog.close()  # what Esc does
    wait_until(lambda: window.get_visible_dialog() is None)
    assert window.document is not None
    assert window.document.file_name == "book.pdf"


def test_a_pdf_opened_with_its_password_can_be_printed(window: "PenfoldWindow", secret: Path, tmp_path: Path) -> None:
    from penfold.document.saving import save
    from penfold.ui.printing import DocumentPrinting

    answer(asked(window, secret), USER_PASSWORD)
    document = window.document
    assert document is not None
    to_print = tmp_path / "print.pdf"
    save(document.print_plan(to_print, frozenset()))
    assert DocumentPrinting(window, document, pytest.fail).make_operation(to_print) is not None
