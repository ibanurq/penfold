"""Making annotations, and undoing it (H1 to H4, D19, D65)."""

from pathlib import Path

import pytest

from penfold.document.annotations import Annotation, Kind, new_annotation
from penfold.document.commands.annotations import AddAnnotation
from penfold.document.commands.pages import DeletePages
from penfold.document.document import OpenDocument
from penfold.document.history import Change
from tests.sample_pdfs import make_pdf

YELLOW = (1.0, 0.9, 0.3)


@pytest.fixture
def document(tmp_path: Path) -> OpenDocument:
    return OpenDocument.open(make_pdf(tmp_path / "three.pdf", page_count=3))


def rectangle_on(page: int) -> Annotation:
    return new_annotation(Kind.RECTANGLE, page, (72, 72, 200, 150), YELLOW, "Iban")


def test_an_added_annotation_can_be_undone_and_redone(document: OpenDocument) -> None:
    changes: list[Change] = []
    document.add_listener(changes.append)
    annotation = rectangle_on(1)
    document.execute(AddAnnotation(document, annotation))
    assert (document.annotations, document.is_modified) == ([annotation], True)
    document.undo()
    assert (document.annotations, document.is_modified) == ([], False)
    document.redo()
    assert document.annotations == [annotation]
    assert changes == [Change.ANNOTATIONS] * 3


def test_undo_takes_away_only_its_own_annotation(document: OpenDocument) -> None:
    first, second = rectangle_on(0), rectangle_on(0)  # equal but for their names
    document.execute(AddAnnotation(document, first))
    document.execute(AddAnnotation(document, second))
    document.undo()
    assert document.annotations == [first]


def test_only_new_annotations_on_pages_of_the_document_are_added(document: OpenDocument) -> None:
    document.execute(DeletePages(document, [2]))
    with pytest.raises(ValueError, match="not in the document"):
        AddAnnotation(document, rectangle_on(2))
    read = Annotation(page=0, kind=Kind.RECTANGLE, subtype="Square", rectangle=(0, 0, 10, 10))
    with pytest.raises(ValueError, match="made in Penfold"):
        AddAnnotation(document, read)
