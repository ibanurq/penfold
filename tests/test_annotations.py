"""Reading the annotations of a PDF for the side panel (ISO 32000-1, 12.5)."""

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pikepdf
import pytest

from penfold.document.annotations import (
    Annotation,
    AnnotationGroup,
    Hit,
    Kind,
    LineEnds,
    Style,
    default_style,
    group_of,
    hit,
    managed_copy,
    new_annotation,
    read_annotations,
    topmost,
)
from penfold.document.pdf_values import date
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
    # Read from the PDF, they are drawn by Poppler, even those Penfold wrote.
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
    assert (second.author, second.line) == ("Penfold", (10, 70, 110, 20))  # no author in the preferences
    assert first.name.startswith("penfold-")
    assert first.name != second.name
    assert first.origin is None  # in no PDF yet
    assert first.created is not None
    assert first.created.tzinfo is not None


def test_new_annotations_look_as_in_0_6() -> None:
    assert default_style(Kind.HIGHLIGHT) == Style(opacity=0.75)
    assert default_style(Kind.RECTANGLE) == Style(opacity=1.0, line_width=1.0, filled=False, dashed=False)
    assert default_style(Kind.FREEHAND) == Style(line_width=2.0)  # By hand, 1 point looks faint and shaky.
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


def read_one(tmp_path: Path, subtype: str, **entries: object) -> Annotation:
    """Read an annotation of another program, made with these entries, on an A4 page."""
    path = make_pdf(tmp_path / "other.pdf", page_count=1)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.pages[0].Annots = pdf.make_indirect(
            pikepdf.Array([pdf.make_indirect(annotation(subtype, [100, 100, 200, 200], **entries))])
        )
        pdf.save(path)
    with pikepdf.open(path) as pdf:
        (read,) = read_annotations(pdf)
    return read


def test_the_look_of_other_programs_is_read(tmp_path: Path) -> None:
    square = read_one(
        tmp_path,
        "/Square",
        C=pikepdf.Array([1, 0, 0]),
        CA=0.4,
        BS=pikepdf.Dictionary(W=3, S=pikepdf.Name.D),
        IC=pikepdf.Array([1, 0.75, 0.75]),  # Penfold's soft red
        NM=pikepdf.String("abc"),
        CreationDate=pikepdf.String("D:20250102030405+01'00'"),
    )
    assert square.style == Style(opacity=0.4, line_width=3, dashed=True, filled=True)
    assert (square.name, square.foreign_look) == ("abc", ())
    assert square.created == datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=1)))
    old = read_one(tmp_path, "/Circle", Border=pikepdf.Array([0, 0, 2]))
    assert (old.style.line_width, old.style.dashed, old.style.filled) == (2, False, False)


def test_what_penfold_cannot_draw_again_is_noted(tmp_path: Path) -> None:
    cloudy = read_one(
        tmp_path,
        "/Square",
        C=pikepdf.Array([1, 0, 0]),
        BE=pikepdf.Dictionary(S=pikepdf.Name.C, I=1),
        IC=pikepdf.Array([0, 0, 1]),
    )
    assert cloudy.foreign_look == ("cloudy border", "fill colour")
    text_box = read_one(tmp_path, "/FreeText", DA=pikepdf.String("/Cour 9 Tf 1 0 0 rg"))
    assert (text_box.style.font_size, text_box.style.background, text_box.foreign_look) == (9, False, ("font",))
    helvetica = read_one(tmp_path, "/FreeText", DA=pikepdf.String("0 g /Helv 14 Tf"), IC=pikepdf.Array([1, 1, 0.9]))
    assert (helvetica.style.font_size, helvetica.style.background, helvetica.foreign_look) == (14, True, ())
    filled = read_one(tmp_path, "/FreeText", C=pikepdf.Array([0.5, 0.7, 1]))  # The colour, painted as background.
    assert (filled.style.background, filled.foreign_look) == (True, ("fill colour",))
    bubble = read_one(tmp_path, "/Text", Name=pikepdf.Name.Help)
    assert bubble.foreign_look == ("icon",)


def test_arrowheads_are_read_and_a_head_at_the_start_turns_the_line_round(tmp_path: Path) -> None:
    line = pikepdf.Array([110, 110, 190, 190])
    heads = {
        ("/None", "/OpenArrow"): (LineEnds.END, (110, 732, 190, 652), ()),
        ("/OpenArrow", "/None"): (LineEnds.END, (190, 652, 110, 732), ()),
        ("/OpenArrow", "/OpenArrow"): (LineEnds.BOTH, (110, 732, 190, 652), ()),
        ("/None", "/None"): (LineEnds.NONE, (110, 732, 190, 652), ()),
        ("/None", "/ClosedArrow"): (LineEnds.END, (110, 732, 190, 652), ("arrowheads",)),
    }
    for (start, end), (ends, shown, foreign) in heads.items():
        arrow = read_one(tmp_path, "/Line", L=line, LE=pikepdf.Array([pikepdf.Name(start), pikepdf.Name(end)]))
        assert (arrow.style.line_ends, arrow.line, arrow.foreign_look) == (ends, shown, foreign)


def test_a_managed_copy_keeps_its_name_and_creation(tmp_path: Path) -> None:
    read = read_one(tmp_path, "/Square", NM=pikepdf.String("abc"), CreationDate=pikepdf.String("D:2025"))
    copy = managed_copy(read)
    assert (copy.managed, copy.name, copy.created, copy.origin) == (True, "abc", read.created, read.origin)
    assert copy.modified is not None
    assert copy.modified.year >= 2026
    nameless = managed_copy(read_one(tmp_path, "/Circle"))
    assert nameless.name.startswith("penfold-")
    assert nameless.created == nameless.modified
    assert managed_copy(copy) is copy
    with pytest.raises(ValueError, match="does not draw"):
        managed_copy(read_one(tmp_path, "/Ink"))


def test_squiggly_underlines_of_other_programs_can_be_changed(tmp_path: Path) -> None:
    squiggly = read_one(tmp_path, "/Squiggly", QuadPoints=pikepdf.Array([100, 200, 200, 200, 100, 180, 200, 180]))
    assert (squiggly.kind, squiggly.group) == (Kind.SQUIGGLY, AnnotationGroup.TEXT_MARKUPS)
    assert squiggly.quads[0] == pytest.approx((100, 642, 200, 662))
    assert managed_copy(squiggly).managed


def test_freehand_drawings_of_other_programs_can_be_changed(tmp_path: Path) -> None:
    strokes = pikepdf.Array([pikepdf.Array([110, 190, 150, 150, 190, 170]), pikepdf.Array([120, 120]), pikepdf.Array()])
    freehand = read_one(tmp_path, "/Ink", InkList=strokes, BS=pikepdf.Dictionary(W=3), CA=0.5)
    assert (freehand.kind, freehand.group) == (Kind.FREEHAND, AnnotationGroup.SHAPES)
    assert freehand.strokes == (((110.0, 652.0), (150.0, 692.0), (190.0, 672.0)), ((120.0, 722.0),))  # None empty.
    assert freehand.style == Style(opacity=0.5, line_width=3)
    assert managed_copy(freehand).managed
    broken = read_one(tmp_path, "/Ink")  # Without strokes, there is nothing to draw.
    assert (broken.kind, broken.subtype) == (Kind.OTHER, "Ink")


def test_pdf_dates() -> None:
    assert date(pikepdf.String("D:20261122103015Z")) == datetime(2026, 11, 22, 10, 30, 15, tzinfo=UTC)
    assert date(pikepdf.String("D:19990101120000-05'30'")) == datetime(
        1999, 1, 1, 12, tzinfo=timezone(-timedelta(hours=5, minutes=30))
    )
    assert date(pikepdf.String("D:2026")) == datetime(2026, 1, 1, tzinfo=UTC)
    assert date(pikepdf.String("D:20261399")) is None
    assert date(pikepdf.String("nonsense")) is None
    assert date(None) is None


def test_what_a_point_is_on() -> None:
    red = (1.0, 0.0, 0.0)
    square = new_annotation(Kind.RECTANGLE, 0, (100, 100, 200, 200), red, "")
    filled = new_annotation(Kind.CIRCLE, 0, (100, 100, 200, 200), red, "", style=Style(filled=True))
    arrow = new_annotation(Kind.ARROW, 0, (0, 0, 100, 100), red, "", line=(0, 0, 100, 100))
    marked = new_annotation(Kind.HIGHLIGHT, 0, (0, 0, 50, 20), red, "", quads=((0, 0, 50, 10), (0, 12, 30, 20)))
    drawn = new_annotation(
        Kind.FREEHAND, 0, (0, 0, 100, 100), red, "", strokes=(((0, 0), (100, 0), (100, 100)), ((50, 50),))
    )
    assert [hit(square, x, 150, 2) for x in (99, 101, 150, 250)] == [Hit.ON, Hit.ON, Hit.INSIDE, Hit.NONE]
    assert (hit(filled, 150, 150, 2), hit(filled, 100, 150, 2), hit(filled, 105, 105, 2)) == (Hit.ON, Hit.ON, Hit.NONE)
    assert (hit(arrow, 52, 50, 2), hit(arrow, 60, 50, 2), hit(arrow, 104, 104, 2)) == (Hit.ON, Hit.NONE, Hit.NONE)
    assert (hit(marked, 40, 5, 2), hit(marked, 40, 15, 2)) == (Hit.ON, Hit.NONE)  # Between its lines, nothing.
    on_strokes = [hit(drawn, x, y, 2) for x, y in ((50, 2), (102, 50), (51, 52), (30, 70), (70, 30))]
    assert on_strokes == [Hit.ON, Hit.ON, Hit.ON, Hit.NONE, Hit.NONE]  # Its lines and its dot, not its inside.


def test_the_one_most_hit_and_on_top_is_chosen(tmp_path: Path) -> None:
    red = (1.0, 0.0, 0.0)
    read = read_one(tmp_path, "/Square")
    first = new_annotation(Kind.RECTANGLE, 0, (0, 0, 9, 9), red, "")
    second = new_annotation(Kind.RECTANGLE, 0, (0, 0, 9, 9), red, "")
    annotations = [first, read, second]
    assert topmost(annotations, {0: Hit.ON, 1: Hit.ON, 2: Hit.ON}) is second
    assert topmost(annotations, {0: Hit.ON, 1: Hit.ON, 2: Hit.INSIDE}) is first  # On it beats inside it.
    assert topmost(annotations, {1: Hit.ON}) is read
    assert topmost(annotations, {0: Hit.NONE}) is None
