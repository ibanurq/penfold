"""Printing: the "Print" dialogue, the PDF prepared and its pages drawn for the printer."""

from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
import pytest
from gi.repository import Gtk

from penfold.document.annotations import AnnotationGroup
from tests.gtk_helpers import process_pending_events, wait_until
from tests.test_document_window import action_enabled, open_and_wait, window
from tests.test_forms import build_form

if TYPE_CHECKING:
    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]


@pytest.fixture
def form_window(window: "PenfoldWindow", tmp_path: Path) -> "PenfoldWindow":
    path = build_form(tmp_path / "form.pdf")
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        mark = pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Ink, Rect=[10, 10, 50, 50])
        pdf.pages[0].Annots.append(pdf.make_indirect(mark))
        pdf.save(path)
    assert open_and_wait(window, path)
    return window


def test_ctrl_p_asks_which_annotations_to_print(form_window: "PenfoldWindow") -> None:
    # Imported here: the dialogue's template needs the interface files the application fixture loads.
    from penfold.ui.dialogs.print_dialog import PenfoldPrintDialog

    assert action_enabled(form_window, "print")
    form_window.activate_action("win.print", None)
    dialog = form_window.get_visible_dialog()
    assert isinstance(dialog, PenfoldPrintDialog)
    assert dialog.left_out() == frozenset()
    dialog.shapes_row.set_active(False)
    dialog.others_row.set_active(False)
    assert dialog.left_out() == frozenset({AnnotationGroup.SHAPES, AnnotationGroup.OTHERS})
    dialog.close()


def test_without_annotations_ctrl_p_prints_at_once(
    window: "PenfoldWindow", tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from penfold.ui.printing import DocumentPrinting

    started: list[frozenset[AnnotationGroup]] = []
    monkeypatch.setattr(DocumentPrinting, "start", lambda _self, left_out: started.append(left_out))
    assert open_and_wait(window, build_form(tmp_path / "form.pdf"))  # Form fields are not annotations.
    window.activate_action("win.print", None)
    assert window.get_visible_dialog() is None
    assert started == [frozenset()]  # Nothing left out.


def test_the_pdf_printed_leaves_out_the_groups_and_has_every_page(
    form_window: "PenfoldWindow", tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from penfold.ui.printing import DocumentPrinting

    document = form_window.document
    assert document is not None
    prepared: list[Path] = []
    monkeypatch.setattr(DocumentPrinting, "_show_print_dialog", lambda _self, path: prepared.append(path))
    printing = DocumentPrinting(form_window, document, pytest.fail)
    printing.start(frozenset({AnnotationGroup.SHAPES}))
    wait_until(lambda: bool(prepared))
    with pikepdf.open(prepared[0]) as pdf:
        annots = pdf.pages[0].Annots
        assert "/Ink" not in [str(annots[index].Subtype) for index in range(len(annots))]
    operation = printing.make_operation(prepared[0])
    assert operation is not None
    exported = tmp_path / "printed.pdf"
    operation.set_export_filename(str(exported))
    operation.set_allow_async(False)
    result = operation.run(Gtk.PrintOperationAction.EXPORT, form_window)
    process_pending_events()
    assert result is Gtk.PrintOperationResult.APPLY
    with pikepdf.open(exported) as pdf:
        assert len(pdf.pages) == document.page_count
    assert not prepared[0].parent.exists()  # The temporary PDF is removed once printed.
