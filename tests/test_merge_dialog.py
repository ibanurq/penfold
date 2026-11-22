"""The "Merge PDFs" dialogue and merging from the window (F1 to F6, D17, D50)."""

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from gi.repository import Adw, Gdk, Gio

from penfold.document.commands.pages import RotatePages
from tests.gtk_helpers import process_pending_events
from tests.sample_pdfs import make_pdf
from tests.test_adding_pages import outlined_pdf
from tests.test_document_window import open_and_wait

if TYPE_CHECKING:
    from penfold.application import PenfoldApplication
    from penfold.ui.dialogs.merge_dialog import PenfoldMergeDialog
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


def files(tmp_path: Path) -> list[Path]:
    (tmp_path / "notes.txt").write_text("not a PDF")
    return [
        make_pdf(tmp_path / "one.pdf", page_count=2),
        tmp_path / "notes.txt",
        make_pdf(tmp_path / "locked.pdf", passwords=("owner", "")),
        make_pdf(tmp_path / "two.pdf", page_count=3),
    ]


def names(dialog: "PenfoldMergeDialog") -> list[str]:
    return [file.path.name for file in dialog.files]


def test_the_list_shows_the_pdfs_and_which_cannot_be_merged(
    application: "PenfoldApplication",  # noqa: ARG001
    tmp_path: Path,
) -> None:
    from penfold.ui.dialogs.merge_dialog import PenfoldMergeDialog

    dialog = PenfoldMergeDialog()
    assert not dialog.merge_button.get_sensitive()
    dialog.add_files(files(tmp_path))
    assert names(dialog) == ["one.pdf", "locked.pdf", "two.pdf"]  # only PDFs
    rows = [dialog.file_list.get_row_at_index(index) for index in range(3)]
    assert [row.get_subtitle() for row in rows if isinstance(row, Adw.ActionRow)] == [
        "2 pages",
        "Cannot be merged",
        "3 pages",
    ]
    assert dialog.total_label.get_label() == "2 files · 5 pages in total"
    assert dialog.merge_button.get_sensitive()
    request = dialog.request
    assert [path.name for path in request.paths] == ["one.pdf", "two.pdf"]  # the protected one is left out
    assert (request.bookmark_per_file, request.keep_bookmarks) == (True, True)


def test_files_are_reordered_and_removed(application: "PenfoldApplication", tmp_path: Path) -> None:  # noqa: ARG001
    from penfold.ui.dialogs.merge_dialog import PenfoldMergeDialog

    dialog = PenfoldMergeDialog()
    dialog.add_files(files(tmp_path))
    dialog.move_file(0, 3)  # to the end
    assert names(dialog) == ["locked.pdf", "two.pdf", "one.pdf"]
    dialog.move_file(2, 0)
    assert names(dialog) == ["one.pdf", "locked.pdf", "two.pdf"]
    dialog.remove_file(2)
    assert names(dialog) == ["one.pdf", "locked.pdf"]
    assert not dialog.merge_button.get_sensitive()  # merging needs two files that can be merged (F3)


def test_merging_shows_the_new_document_with_its_bookmarks(
    window: "PenfoldWindow", tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from penfold.ui.dialogs.merge_dialog import PdfsToMerge
    from penfold.ui.sidebar import sidebar

    window.merge(PdfsToMerge([outlined_pdf(tmp_path / "one.pdf"), make_pdf(tmp_path / "two.pdf")], True, True))
    document = window.document
    assert document is not None
    assert (document.page_count, document.file_name, document.is_modified) == (8, "merged.pdf", True)
    assert window.sidebar.visible_view == sidebar.BOOKMARKS
    assert window.get_title() == "• merged.pdf — Penfold"
    saved_as: list[bool] = []
    monkeypatch.setattr(window, "save_as", lambda *_arguments: saved_as.append(True))
    window.save()
    assert saved_as == [True]  # a new document is saved where the user says (F6)


def test_merge_asks_first_about_unsaved_changes(window: "PenfoldWindow", tmp_path: Path) -> None:
    open_and_wait(window, make_pdf(tmp_path / "plain.pdf"))
    document = window.document
    assert document is not None
    document.execute(RotatePages(document, [0], 90))
    window.merge_files([])
    assert isinstance(window.get_visible_dialog(), Adw.AlertDialog)


def test_several_pdfs_dropped_open_merge_with_them(window: "PenfoldWindow", tmp_path: Path) -> None:
    from penfold.ui.dialogs.merge_dialog import PenfoldMergeDialog

    paths = [make_pdf(tmp_path / "one.pdf"), make_pdf(tmp_path / "two.pdf")]
    dropped = Gdk.FileList.new_from_list([Gio.File.new_for_path(str(path)) for path in paths])
    assert window._on_drop(None, dropped, 0, 0)  # type: ignore[arg-type]
    dialog = window.get_visible_dialog()
    assert isinstance(dialog, PenfoldMergeDialog)
    assert names(dialog) == ["one.pdf", "two.pdf"]


def test_merge_is_an_action_of_the_application(application: "PenfoldApplication") -> None:
    assert application.lookup_action("merge") is not None


def test_with_permissions_ignored_every_pdf_without_password_can_be_merged(
    application: "PenfoldApplication",  # noqa: ARG001
    tmp_path: Path,
) -> None:
    from penfold import config
    from penfold.ui.dialogs.merge_dialog import PenfoldMergeDialog

    settings = Gio.Settings(schema_id=config.APP_ID)
    settings.set_boolean("respect-permissions", False)
    try:
        dialog = PenfoldMergeDialog()
        dialog.add_files(files(tmp_path))
        assert [file.page_count for file in dialog.files] == [2, 3, 3]
        assert dialog.total_label.get_label() == "3 files · 8 pages in total"
    finally:
        settings.reset("respect-permissions")
