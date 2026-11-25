"""PDFs with permissions (D58 to D60): the lock, the tools each one allows, Ctrl+P, changes, ignoring them."""

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
import pytest
from gi.repository import Adw, Gio, Gtk, Poppler

from penfold import config
from penfold.document.commands.pages import RotatePages
from penfold.ui.text_selection import PagePoint, TextSelection
from tests.gtk_helpers import process_pending_events, wait_until_stable
from tests.sample_pdfs import allowing, make_pdf, make_pdf_with_permissions
from tests.test_document_window import action_enabled, open_and_wait, window
from tests.test_forms import build_form

if TYPE_CHECKING:
    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]


TOOLS = ("save", "save-as", "print", "add-pages", "extract-pages", "add-bookmark", "annotate")


@pytest.fixture
def locked_window(window: "PenfoldWindow", tmp_path: Path) -> "PenfoldWindow":
    assert open_and_wait(window, make_pdf_with_permissions(tmp_path / "locked.pdf"))
    return window


def test_a_pdf_that_denies_something_has_a_red_lock_that_says_what_it_does_not_allow(
    window: "PenfoldWindow", tmp_path: Path
) -> None:
    assert open_and_wait(window, make_pdf_with_permissions(tmp_path / "locked.pdf", "print_lowres", "extract"))
    icon = window.document_header.protected_icon
    assert (icon.get_visible(), icon.has_css_class("error")) == (True, True)
    assert icon.get_tooltip_text() == (
        "User access permissions of this PDF:\n"
        "\n"
        "• Its forms cannot be filled in\n"
        "• It cannot be annotated\n"
        "• Its pages and bookmarks cannot be changed\n"
        "• Its form cannot be flattened\n"
        "\n"
        "They can be ignored in Preferences."
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


def test_changes_to_a_pdf_that_denies_something_are_offered_to_be_saved(locked_window: "PenfoldWindow") -> None:
    document = locked_window.document
    assert document is not None
    document.execute(RotatePages(document, [0], 90))
    locked_window.confirm_discard(lambda _proceed: None)
    dialog = locked_window.get_visible_dialog()
    assert isinstance(dialog, Adw.AlertDialog)
    assert dialog.get_heading() == "Save changes to “locked.pdf”?"
    dialog.force_close()


def allow_only(path: Path, *permissions: str) -> Path:
    """Give a PDF user access permissions that allow only these (pikepdf names)."""
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.save(path, encryption=pikepdf.Encryption(owner="owner", user="", allow=allowing(*permissions)))
    return path


def test_tools_follow_what_the_pdf_allows(window: "PenfoldWindow", tmp_path: Path) -> None:
    assert open_and_wait(window, make_pdf_with_permissions(tmp_path / "locked.pdf"))
    enabled = {name: action_enabled(window, name) for name in TOOLS}
    assert enabled == {
        "save": True,
        "save-as": True,
        "print": False,
        "add-pages": False,
        "extract-pages": False,
        "add-bookmark": False,
        "annotate": False,
    }
    assert open_and_wait(window, make_pdf_with_permissions(tmp_path / "open.pdf", "print_lowres", "modify_assembly"))
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
    assert open_and_wait(window, allow_only(build_form(tmp_path / "form.pdf"), "print_lowres"))
    editors = [item for item in window.document_view._form_layer._editors.values() if item.field.name == "notes"]
    assert editors
    view = editors[0].view
    assert isinstance(view, Gtk.TextView)
    assert not view.get_editable()


@pytest.fixture
def ignored() -> Iterator[Gio.Settings]:
    """Return Penfold's settings, with "Respect Document Permissions" turned back on afterwards."""
    settings = Gio.Settings(schema_id=config.APP_ID)
    yield settings
    settings.reset("respect-permissions")
    process_pending_events()


def test_ignoring_permissions_removes_the_lock_and_allows_everything_at_once(
    locked_window: "PenfoldWindow", ignored: Gio.Settings
) -> None:
    icon = locked_window.document_header.protected_icon
    ignored.set_boolean("respect-permissions", False)
    process_pending_events()
    assert not icon.get_visible()
    assert {name: action_enabled(locked_window, name) for name in TOOLS} == dict.fromkeys(TOOLS, True)
    ignored.set_boolean("respect-permissions", True)
    process_pending_events()
    assert icon.get_visible()
    assert not action_enabled(locked_window, "print")


def test_a_pdf_opened_while_permissions_are_ignored_allows_everything(
    window: "PenfoldWindow", tmp_path: Path, ignored: Gio.Settings
) -> None:
    ignored.set_boolean("respect-permissions", False)
    assert open_and_wait(window, make_pdf_with_permissions(tmp_path / "locked.pdf"))
    assert not window.document_header.protected_icon.get_visible()
    assert {name: action_enabled(window, name) for name in TOOLS} == dict.fromkeys(TOOLS, True)


def test_ignoring_permissions_lets_text_be_selected_and_fields_be_filled_in(
    window: "PenfoldWindow", tmp_path: Path, ignored: Gio.Settings
) -> None:
    assert open_and_wait(window, allow_only(build_form(tmp_path / "form.pdf"), "print_lowres"))
    ignored.set_boolean("respect-permissions", False)
    view = window.document_view
    # The fields are made again once GTK places them.
    wait_until_stable(lambda: sorted(view._form_layer._editors))
    point = PagePoint(0, 10.0, 10.0)
    view._set_selection(TextSelection(point, PagePoint(0, 500.0, 500.0), Poppler.SelectionStyle.GLYPH))
    assert view.selection is not None
    editors = [item for item in view._form_layer._editors.values() if item.field.name == "notes"]
    assert editors
    text_view = editors[0].view
    assert isinstance(text_view, Gtk.TextView)
    assert text_view.get_editable()
