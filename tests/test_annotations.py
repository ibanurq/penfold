"""Reading the annotations of a PDF for the side panel (ISO 32000-1, 12.5)."""

from pathlib import Path

import pikepdf
import pytest

from penfold.document.annotations import Annotation, AnnotationGroup, Kind, group_of, read_annotations
from tests.sample_pdfs import make_pdf


def annotation(subtype: str, rect: list[float], **entries: object) -> pikepdf.Dictionary:
    dictionary = pikepdf.Dictionary({"/Type": pikepdf.Name.Annot, "/Subtype": pikepdf.Name(subtype)})
    dictionary["/Rect"] = pikepdf.Array(rect)
    for key, value in entries.items():
        dictionary[f"/{key}"] = value
    return dictionary


@pytest.fixture
def annotations(tmp_path: Path) -> list[Annotation]:
    path = make_pdf(tmp_path / "annotated.pdf", page_count=2)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        first = [
            annotation(
                "/Text",
                [100, 700, 120, 720],
                Contents=pikepdf.String("Check this"),
                T=pikepdf.String("Penfold"),
                C=pikepdf.Array([1, 1, 0]),
            ),
            annotation(
                "/Highlight",
                [72, 790, 300, 810],
                QuadPoints=pikepdf.Array([72, 810, 300, 810, 72, 790, 300, 790]),
                T=pikepdf.String("Ana"),
            ),
            annotation("/Link", [0, 0, 10, 10]),
            annotation("/Square", [300, 300, 200, 100], C=pikepdf.Array([0.5])),
        ]
        second = [annotation("/Ink", [10, 10, 50, 50], Contents=pikepdf.String("  Scribble  "))]
        pdf.pages[0].Annots = pdf.make_indirect(pikepdf.Array([pdf.make_indirect(item) for item in first]))
        pdf.pages[1].Annots = pdf.make_indirect(pikepdf.Array([pdf.make_indirect(item) for item in second]))
        pdf.save(path)
    with pikepdf.open(path) as pdf:
        return read_annotations(pdf)


def test_lists_notes_but_not_links(annotations: list[Annotation]) -> None:
    assert [(item.page, item.kind) for item in annotations] == [
        (0, Kind.HIGHLIGHT),
        (0, Kind.COMMENT),
        (0, Kind.RECTANGLE),
        (1, Kind.OTHER),
    ]


def test_positions_are_from_the_top_left_corner(annotations: list[Annotation]) -> None:
    highlight, comment, rectangle, _ink = annotations
    assert comment.rectangle == (100.0, 842.0 - 720, 120.0, 842.0 - 700)
    assert rectangle.rectangle == (200.0, 842.0 - 300, 300.0, 842.0 - 100)  # an inverted rectangle, put right
    assert highlight.quads == ((72.0, 842.0 - 810, 300.0, 842.0 - 790),)


def test_text_author_colour_and_ownership(annotations: list[Annotation]) -> None:
    highlight, comment, rectangle, ink = annotations
    assert (comment.text, comment.author, comment.color, comment.is_own) == (
        "Check this",
        "Penfold",
        (1.0, 1.0, 0.0),
        True,
    )
    assert (highlight.author, highlight.is_own) == ("Ana", False)
    assert rectangle.color == (0.5, 0.5, 0.5)
    assert (ink.text, ink.subtype, ink.author) == ("Scribble", "Ink", "")


def test_every_listed_type_has_a_group(annotations: list[Annotation]) -> None:
    assert [item.group for item in annotations] == [
        AnnotationGroup.TEXT_MARKUPS,
        AnnotationGroup.TEXT_ELEMENTS,
        AnnotationGroup.SHAPES,
        AnnotationGroup.SHAPES,  # a freehand drawing is a shape, though Penfold does not make them
    ]
    assert group_of("/Squiggly") is AnnotationGroup.TEXT_MARKUPS
    assert group_of("/Stamp") is AnnotationGroup.TEXT_ELEMENTS
    assert group_of("/FileAttachment") is AnnotationGroup.OTHERS
    assert group_of("/Link") is None
    assert group_of("/Widget") is None


def test_pdf_without_annotations(tmp_path: Path) -> None:
    with pikepdf.open(make_pdf(tmp_path / "plain.pdf")) as pdf:
        assert read_annotations(pdf) == []
