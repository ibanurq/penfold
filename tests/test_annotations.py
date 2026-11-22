"""Reading the annotations of a PDF for the side panel (ISO 32000-1, 12.5)."""

from pathlib import Path

import pikepdf
import pytest

from penfold.document.annotations import (
    Annotation,
    AnnotationGroup,
    Kind,
    Style,
    default_style,
    group_of,
    new_annotation,
    read_annotations,
)
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


def test_text_author_and_colour(annotations: list[Annotation]) -> None:
    highlight, comment, rectangle, ink = annotations
    assert (comment.text, comment.author, comment.color) == ("Check this", "Penfold", (1.0, 1.0, 0.0))
    assert highlight.author == "Ana"
    assert rectangle.color == (0.5, 0.5, 0.5)
    assert (ink.text, ink.subtype, ink.author) == ("Scribble", "Ink", "")
    # Read from the PDF, they are drawn by Poppler, even those Penfold wrote (D66).
    assert not any(item.managed for item in annotations)


def test_each_knows_its_place_in_its_page(annotations: list[Annotation]) -> None:
    highlight, comment, rectangle, ink = annotations
    # The link is not listed, but it has its place among the page's annotations.
    assert [item.origin for item in (comment, highlight, rectangle, ink)] == [0, 1, 3, 0]


def test_a_new_annotation_is_managed_and_named() -> None:
    first = new_annotation(Kind.RECTANGLE, 3, (10, 20, 110, 70), (1.0, 0.0, 0.0), "  Iban ")
    second = new_annotation(Kind.ARROW, 3, (10, 20, 110, 70), (1.0, 0.0, 0.0), "", line=(10, 70, 110, 20))
    assert (first.subtype, first.page, first.author, first.managed) == ("Square", 3, "Iban", True)
    assert first.group is AnnotationGroup.SHAPES
    assert (second.author, second.line) == ("Penfold", (10, 70, 110, 20))  # no author in the preferences (D60)
    assert first.name.startswith("penfold-")
    assert first.name != second.name
    assert first.origin is None  # in no PDF yet
    assert first.created is not None
    assert first.created.tzinfo is not None


def test_new_annotations_look_as_in_0_6() -> None:
    assert default_style(Kind.HIGHLIGHT) == Style(opacity=0.75)
    assert default_style(Kind.RECTANGLE) == Style(opacity=1.0, line_width=1.0, filled=False, dashed=False)
    assert new_annotation(Kind.HIGHLIGHT, 0, (0, 0, 9, 9), (1.0, 1.0, 0.0), "").style.opacity == 0.75
    bold = Style(line_width=4.0)
    assert new_annotation(Kind.CIRCLE, 0, (0, 0, 9, 9), (1.0, 1.0, 0.0), "", style=bold).style is bold


def test_penfold_makes_no_annotations_of_other_types() -> None:
    with pytest.raises(ValueError, match="other types"):
        new_annotation(Kind.OTHER, 0, (0, 0, 10, 10), (0.0, 0.0, 0.0), "")


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
