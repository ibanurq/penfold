"""Making, changing and deleting annotations, and undoing it (H1 to H4, H9, H11, D19, D65, D72)."""

from dataclasses import replace
from pathlib import Path

import pytest

from penfold.document.annotations import Annotation, Kind, new_annotation
from penfold.document.commands.annotations import AddAnnotations, ChangeAnnotation, DeleteAnnotations
from penfold.document.commands.pages import DeletePages
from penfold.document.document import OpenDocument
from penfold.document.history import Change
from tests.sample_pdfs import make_pdf

YELLOW = (1.0, 0.9, 0.3)
BLUE = (0.4, 0.6, 1.0)
RED = (1.0, 0.4, 0.4)


@pytest.fixture
def document(tmp_path: Path) -> OpenDocument:
    return OpenDocument.open(make_pdf(tmp_path / "three.pdf", page_count=3))


def rectangle_on(page: int) -> Annotation:
    return new_annotation(Kind.RECTANGLE, page, (72, 72, 200, 150), YELLOW, "Iban")


def test_an_added_annotation_can_be_undone_and_redone(document: OpenDocument) -> None:
    changes: list[Change] = []
    document.add_listener(changes.append)
    annotation = rectangle_on(1)
    document.execute(AddAnnotations(document, [annotation]))
    assert (document.annotations, document.is_modified) == ([annotation], True)
    document.undo()
    assert (document.annotations, document.is_modified) == ([], False)
    document.redo()
    assert document.annotations == [annotation]
    assert changes == [Change.ANNOTATIONS] * 3


def test_undo_takes_away_only_its_own_annotation(document: OpenDocument) -> None:
    first, second = rectangle_on(0), rectangle_on(0)  # equal but for their names
    document.execute(AddAnnotations(document, [first]))
    document.execute(AddAnnotations(document, [second]))
    document.undo()
    assert document.annotations == [first]


def test_only_new_annotations_on_pages_of_the_document_are_added(document: OpenDocument) -> None:
    document.execute(DeletePages(document, [2]))
    with pytest.raises(ValueError, match="not in the document"):
        AddAnnotations(document, [rectangle_on(2)])
    read = Annotation(page=0, kind=Kind.RECTANGLE, subtype="Square", rectangle=(0, 0, 10, 10))
    with pytest.raises(ValueError, match="made in Penfold"):
        AddAnnotations(document, [read])


def test_deleted_annotations_come_back_in_their_place(document: OpenDocument) -> None:
    first, second, third = rectangle_on(0), rectangle_on(1), rectangle_on(2)
    document.execute(AddAnnotations(document, [first, second, third]))
    delete = DeleteAnnotations(document, [third, first])
    assert delete.annotations == [first, third]
    document.execute(delete)
    assert document.annotations == [second]
    document.undo()
    assert [id(item) for item in document.annotations] == [id(first), id(second), id(third)]
    document.redo()
    assert document.annotations == [second]


def test_only_annotations_of_the_document_are_deleted(document: OpenDocument) -> None:
    with pytest.raises(ValueError, match="no annotations"):
        DeleteAnnotations(document, [])
    with pytest.raises(ValueError, match="not in the document"):
        DeleteAnnotations(document, [rectangle_on(0)])


def test_a_changed_annotation_can_be_undone_and_redone(document: OpenDocument) -> None:
    first, second = rectangle_on(0), rectangle_on(1)
    document.execute(AddAnnotations(document, [first, second]))
    changes: list[Change] = []
    document.add_listener(changes.append)
    blue = replace(first, color=BLUE)
    document.execute(ChangeAnnotation(document, first, blue))
    assert document.annotations == [blue, second]
    document.undo()
    assert [id(item) for item in document.annotations] == [id(first), id(second)]
    document.redo()
    assert document.annotations == [blue, second]
    assert changes == [Change.ANNOTATIONS] * 3


def test_retouching_keeps_one_edit_to_undo(document: OpenDocument) -> None:
    annotation = rectangle_on(0)
    document.execute(AddAnnotations(document, [annotation]))
    change = ChangeAnnotation(document, annotation, replace(annotation, color=BLUE))
    document.execute(change)
    red = replace(annotation, color=RED)
    assert document.amend(change, lambda: change.retouch(red))
    assert (document.annotations, change.changed) == ([red], red)
    document.undo()
    assert document.annotations == [annotation]
    document.redo()
    assert document.annotations == [red]


def test_an_annotation_of_the_pdf_becomes_managed_when_changed(document: OpenDocument) -> None:
    read = Annotation(page=0, kind=Kind.RECTANGLE, subtype="Square", rectangle=(0, 0, 10, 10), origin=2)
    document.annotations = [read]
    changed = replace(read, color=BLUE, managed=True)
    document.execute(ChangeAnnotation(document, read, changed))
    assert document.annotations == [changed]
    with pytest.raises(ValueError, match="drawn and written by Penfold"):
        ChangeAnnotation(document, changed, replace(changed, managed=False))
    with pytest.raises(ValueError, match="keeps its page, kind and origin"):
        ChangeAnnotation(document, changed, replace(changed, origin=None))
    with pytest.raises(ValueError, match="keeps its page, kind and origin"):
        ChangeAnnotation(document, changed, replace(changed, kind=Kind.CIRCLE))
    with pytest.raises(ValueError, match="not in the document"):
        ChangeAnnotation(document, read, changed)
