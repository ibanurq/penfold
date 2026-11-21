"""PDFs with restrictions (D58, D59): the red lock, the tools each one allows, Ctrl+P and the question about changes."""

from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
import pytest
from gi.repository import Adw, Gtk, Poppler

from penfold.document.commands.pages import RotatePages
from penfold.ui.text_selection import PagePoint, TextSelection
from tests.sample_pdfs import allowing, make_pdf, make_restricted_pdf
from tests.test_document_window import action_enabled, open_and_wait, window
from tests.test_forms import build_form

if TYPE_CHECKING:
    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]


TOOLS = ("save", "save-as", "print", "add-pages", "extract-pages", "add-bookmark")


@pytest.fixture
def locked_window(window: "PenfoldWindow", tmp_path: Path) -> "PenfoldWindow":
    assert open_and_wait(window, make_restricted_pdf(tmp_path / "locked.pdf"))
    return window


def test_a_pdf_with_restrictions_has_a_red_lock_that_says_what_it_does_not_allow(
    window: "PenfoldWindow", tmp_path: Path
) -> None:
    assert open_and_wait(window, make_restricted_pdf(tmp_path / "locked.pdf", "print_lowres", "extract"))
    icon = window.document_header.protected_icon
    assert (icon.get_visible(), icon.has_css_class("error")) == (True, True)
    assert icon.get_tooltip_text() == (
        "This PDF has restrictions:\n"
        "• Its forms cannot be filled in\n"
        "• It cannot be annotated\n"
        "• Its pages and bookmarks cannot be changed\n"
        "• Its form cannot be flattened"
    )
    assert open_and_wait(window, make_pdf(tmp_path / "open.pdf"))
    assert not icon.get_visible()


def test_ctrl_p_says_a_pdf_does_not_allow_printing(
    locked_window: "PenfoldWindow", monkeypatch: pytest.MonkeyPatch
) -> None:
    toasts: list[str] = []
    monkeypatch.setattr(locked_window.toast_overlay, "add_toast", lambda toast: toasts.append(toast.get_title()))
    assert not action_enabled(locked_window, "print")
    assert action_enabled(locked_window, "print-shortcut")
    locked_window.activate_action("win.print-shortcut", None)
    assert toasts == ["This PDF does not allow printing"]
    assert locked_window.get_visible_dialog() is None


def test_changes_to_a_pdf_with_restrictions_are_offered_to_be_saved(locked_window: "PenfoldWindow") -> None:
    document = locked_window.document
    assert document is not None
    document.execute(RotatePages(document, [0], 90))
    locked_window.confirm_discard(lambda _proceed: None)
    dialog = locked_window.get_visible_dialog()
    assert isinstance(dialog, Adw.AlertDialog)
    assert dialog.get_heading() == "Save changes to “locked.pdf”?"
    dialog.force_close()


def restrict(path: Path, *permissions: str) -> Path:
    """Give a PDF restrictions that allow only these (pikepdf names)."""
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.save(path, encryption=pikepdf.Encryption(owner="owner", user="", allow=allowing(*permissions)))
    return path


def test_tools_follow_what_the_pdf_allows(window: "PenfoldWindow", tmp_path: Path) -> None:
    assert open_and_wait(window, make_restricted_pdf(tmp_path / "locked.pdf"))
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
    editors = [item for item in window.document_view._form_layer._editors.values() if item.field.name == "notes"]
    assert editors
    view = editors[0].view
    assert isinstance(view, Gtk.TextView)
    assert not view.get_editable()
