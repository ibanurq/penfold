"""PDFs with restrictions (D58, D59): the red lock, the tools each one allows, Ctrl+P and the question about changes."""

from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
import pytest
from gi.repository import Adw, Gtk, Poppler

from penfold.document.commands.pages import RotatePages
from penfold.ui.text_selection import PagePoint, TextSelection
from tests.gtk_helpers import process_pending_events
from tests.sample_pdfs import allowing, make_pdf, make_restricted_pdf
from tests.test_document_window import action_enabled, open_and_wait, window
from tests.test_forms import build_form

if TYPE_CHECKING:
    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]


TOOLS = ("save", "save-as", "print", "add-pages", "extract-pages", "add-bookmark")


def close_notice(window: "PenfoldWindow") -> None:
    notice = window.get_visible_dialog()
    assert notice is not None
    notice.force_close()
    process_pending_events()


@pytest.fixture
def locked_window(window: "PenfoldWindow", tmp_path: Path) -> "PenfoldWindow":
    assert open_and_wait(window, make_restricted_pdf(tmp_path / "locked.pdf"))
    close_notice(window)
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


def restrict(path: Path, *permissions: str) -> Path:
    """Give a PDF restrictions that allow only these (pikepdf names)."""
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.save(path, encryption=pikepdf.Encryption(owner="owner", user="", allow=allowing(*permissions)))
    return path


def test_tools_follow_what_the_pdf_allows(window: "PenfoldWindow", tmp_path: Path) -> None:
    assert open_and_wait(window, make_restricted_pdf(tmp_path / "locked.pdf"))
    close_notice(window)
    enabled = {name: action_enabled(window, name) for name in TOOLS}
    assert enabled == {
        "save": True,
        "save-as": True,
        "print": False,
        "add-pages": False,
        "extract-pages": False,
        "add-bookmark": False,
    }
    assert open_and_wait(window, make_restricted_pdf(tmp_path / "open.pdf", "print_lowres", "modify_assembly"))
    close_notice(window)
    assert {name: action_enabled(window, name) for name in ("print", "add-pages", "add-bookmark")} == dict.fromkeys(
        ("print", "add-pages", "add-bookmark"), True
    )


def test_text_cannot_be_selected_if_the_pdf_does_not_allow_copying(locked_window: "PenfoldWindow") -> None:
    view = locked_window.document_view
    point = PagePoint(0, 10.0, 10.0)
    view._set_selection(TextSelection(point, PagePoint(0, 500.0, 500.0), Poppler.SelectionStyle.GLYPH))
    assert view.selection is None
    assert not view.copy_selection()


def test_fields_are_read_only_if_the_pdf_does_not_allow_filling_them(window: "PenfoldWindow", tmp_path: Path) -> None:
    assert open_and_wait(window, restrict(build_form(tmp_path / "form.pdf"), "print_lowres"))
    close_notice(window)
    editors = [item for item in window.document_view._form_layer._editors.values() if item.field.name == "notes"]
    assert editors
    view = editors[0].view
    assert isinstance(view, Gtk.TextView)
    assert not view.get_editable()
