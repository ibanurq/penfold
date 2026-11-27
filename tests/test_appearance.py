"""Writing the annotations made in Penfold into the PDF, with their drawing and the standard's entries."""

from dataclasses import replace
from itertools import pairwise
from pathlib import Path

import gi
import pikepdf
import pytest

gi.require_version("Poppler", "0.18")
from gi.repository import Poppler  # noqa: E402

from penfold.document.annotations import (  # noqa: E402
    Annotation,
    AnnotationGroup,
    Kind,
    LineEnds,
    Style,
    new_annotation,
    read_annotations,
)
from penfold.document.appearance import SQUIGGLE_MINIMUM, squiggle, stroke_curves  # noqa: E402
from penfold.document.commands.annotations import AddAnnotations  # noqa: E402
from penfold.document.commands.pages import DeletePages, RotatePages  # noqa: E402
from penfold.document.document import OpenDocument  # noqa: E402
from penfold.document.geometry import turn_rectangle  # noqa: E402
from penfold.document.saving import save  # noqa: E402
from tests.sample_pdfs import make_pdf  # noqa: E402

YELLOW = (0.976, 0.941, 0.42)
RED = (0.965, 0.38, 0.318)
A4 = (595.0, 842.0)
# A freehand drawing: a wave and a dot.
FREEHAND_STROKES = (((350, 380), (380, 330), (410, 390), (440, 325), (470, 395), (500, 340)), ((420, 360),))


def every_kind(page: int) -> list[Annotation]:
    return [
        new_annotation(Kind.HIGHLIGHT, page, (72, 72, 300, 90), YELLOW, "Iban", quads=((72, 72, 300, 90),)),
        new_annotation(Kind.UNDERLINE, page, (72, 100, 300, 118), RED, "Iban", quads=((72, 100, 300, 118),)),
        new_annotation(Kind.SQUIGGLY, page, (72, 160, 300, 178), RED, "Iban", quads=((72, 160, 300, 178),)),
        new_annotation(Kind.STRIKE_OUT, page, (72, 130, 300, 148), RED, "Iban", quads=((72, 130, 300, 148),)),
        new_annotation(Kind.RECTANGLE, page, (72, 200, 200, 280), RED, "Iban"),
        new_annotation(Kind.CIRCLE, page, (250, 200, 400, 280), RED, "Iban"),
        new_annotation(Kind.ARROW, page, (72, 320, 300, 400), RED, "Iban", line=(72, 400, 300, 320)),
        new_annotation(Kind.FREEHAND, page, (350, 320, 500, 400), RED, "Iban", strokes=FREEHAND_STROKES),
        new_annotation(Kind.COMMENT, page, (400, 72, 420, 92), YELLOW, "Iban", text="Ñandú → ✓ (a) \\ 😀"),
    ]


def restyled(annotations: list[Annotation]) -> list[Annotation]:
    """The same annotations as their Format panel can leave them: see-through; thick, dashed, filled shapes."""
    shape = Style(opacity=0.5, line_width=4.0, dashed=True, filled=True)
    styles = {
        Kind.RECTANGLE: shape,
        Kind.CIRCLE: shape,
        Kind.ARROW: replace(shape, filled=False, line_ends=LineEnds.BOTH),
        Kind.FREEHAND: Style(opacity=0.5, line_width=4.0),
        Kind.COMMENT: Style(),
    }
    return [replace(annotation, style=styles.get(annotation.kind, Style(opacity=0.5))) for annotation in annotations]


@pytest.fixture
def document(tmp_path: Path) -> OpenDocument:
    return OpenDocument.open(make_pdf(tmp_path / "two.pdf", page_count=2))


def add(document: OpenDocument, annotations: list[Annotation]) -> None:
    for annotation in annotations:
        document.execute(AddAnnotations(document, [annotation]))


def floats(array: pikepdf.Object) -> list[float]:
    return [float(array[index]) for index in range(len(array))]


def subtypes(target: Path) -> list[str]:
    """The subtypes of the annotations of a PDF, page after page."""
    with pikepdf.open(target) as pdf:
        return [
            str(annots[index].Subtype)
            for page in pdf.pages
            if isinstance(annots := page.obj.get("/Annots"), pikepdf.Array)
            for index in range(len(annots))
        ]


def saved(document: OpenDocument, target: Path) -> list[str]:
    save(document.save_plan(target))
    return subtypes(target)


def test_every_type_is_written_with_the_standards_entries(document: OpenDocument, tmp_path: Path) -> None:
    annotations = every_kind(1)
    add(document, annotations)
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    with pikepdf.open(target) as pdf:
        written = pdf.pages[1].Annots
        assert len(written) == len(annotations)
        for index, annotation in enumerate(annotations):
            entry = written[index]
            assert str(entry.Subtype) == f"/{annotation.subtype}"
            assert bytes(entry.T).startswith(b"\xfe\xff")  # UTF-16, whatever the text
            assert (str(entry.T), str(entry.NM)) == ("Iban", annotation.name)
            assert int(entry.F) == (20 if annotation.kind is Kind.COMMENT else 4)  # printed; comments upright
            assert str(entry.M) == str(entry.CreationDate)
            assert str(entry.M).startswith("D:")
            assert str(entry.M).endswith("Z")
            assert entry.P.objgen == pdf.pages[1].obj.objgen
            assert entry.AP.N.Subtype == pikepdf.Name.Form
        highlight, underline, squiggly, _strike, rectangle, _circle, arrow, freehand, comment = (
            written[index] for index in range(9)
        )
        assert float(highlight.CA) == 0.75
        assert floats(highlight.QuadPoints) == [72, 770, 300, 770, 72, 752, 300, 752]
        assert floats(rectangle.Rect) == [72, 562, 200, 642]
        assert (float(rectangle.BS.W), str(rectangle.BS.S)) == (1.0, "/S")
        assert "/IC" not in rectangle  # nothing inside
        assert floats(arrow.L) == [72, 442, 300, 522]
        assert [str(arrow.LE[index]) for index in range(len(arrow.LE))] == ["/None", "/OpenArrow"]
        assert (str(comment.Name), str(comment.Contents)) == ("/Comment", "Ñandú → ✓ (a) \\ 😀")
        assert [floats(freehand.InkList[index]) for index in range(len(freehand.InkList))] == [
            [350, 462, 380, 512, 410, 452, 440, 517, 470, 447, 500, 502],
            [420, 482],
        ]
        assert (float(freehand.BS.W), str(freehand.BS.S)) == (2.0, "/S")  # As new ones are drawn.
        left, bottom, right, top = floats(freehand.Rect)
        assert (left, right) == (348, 502)  # The strokes and half their line, and a little more.
        assert bottom < 447
        assert top > 517
        assert "/Contents" not in underline
        assert floats(squiggly.QuadPoints) == [72, 682, 300, 682, 72, 664, 300, 664]
        assert "/Popup" not in comment
    assert pikepdf.open(target).check() == []


def test_a_squiggly_underline_zigzags_along_the_bottom_of_the_text() -> None:
    corners = squiggle((72, 100), (172, 100), (72, 118), 1.0)  # A line of text 18 points tall, upwards.
    assert len(corners) % 2 == 1  # An even number of strokes: it starts and ends low.
    assert corners[0] == pytest.approx((72, 100.5))  # Lifted by half the line, as an underline is.
    assert corners[-1] == pytest.approx((172, 100.5))
    assert {round(y, 6) for _x, y in corners} == {100.5, 103.5}  # As tall as a sixth of the text.
    steps = [second[0] - first[0] for first, second in pairwise(corners)]
    assert steps == pytest.approx([100 / 34] * 34)  # Each stroke about as long as it is tall, ending at the end.
    turned = squiggle((100, 72), (100, 172), (82, 72), 1.0)  # The same text, reading downwards.
    assert [coordinate for x, y in turned for coordinate in (y, 200 - x)] == pytest.approx(
        [coordinate for corner in corners for coordinate in corner]
    )
    tiny = squiggle((0, 0), (1, 0), (0, 2), 1.0)
    assert len(tiny) == 3  # Always one wave, at least.
    assert max(y for _x, y in tiny) == pytest.approx(0.5 + SQUIGGLE_MINIMUM)


def test_a_freehand_stroke_is_a_smooth_curve_through_its_points() -> None:
    points = [(0.0, 0.0), (10.0, 10.0), (20.0, 0.0), (30.0, 10.0)]
    curves = stroke_curves(points)
    assert [end for _first, _second, end in curves] == points[1:]  # Through every point, in order.
    for (_first, second, _end), (first, _second, _next_end), point in zip(curves, curves[1:], points[1:], strict=False):
        # No corner at a point: the curve leaves it in the direction it arrives.
        assert (point[0] - second[0], point[1] - second[1]) == pytest.approx((first[0] - point[0], first[1] - point[1]))
    assert stroke_curves([(5.0, 5.0)]) == []  # A dot.


def test_poppler_reads_them_with_their_author_and_text(document: OpenDocument, tmp_path: Path) -> None:
    add(document, every_kind(0))
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    page = Poppler.Document.new_from_file(target.as_uri(), None).get_page(0)
    read = {mapping.annot.get_annot_type().value_nick: mapping.annot for mapping in page.get_annot_mapping()}
    kinds = {"highlight", "underline", "squiggly", "strike-out", "square", "circle", "line", "ink", "text"}
    assert set(read) == kinds
    assert read["text"].get_contents() == "Ñandú → ✓ (a) \\ 😀"
    square = read["square"]
    assert isinstance(square, Poppler.AnnotMarkup)
    assert square.get_label() == "Iban"


def test_they_are_read_back_where_they_were_made(document: OpenDocument, tmp_path: Path) -> None:
    annotations = every_kind(0)
    add(document, annotations)
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    with pikepdf.open(target) as pdf:
        read = read_annotations(pdf)
    by_name = {annotation.kind: annotation for annotation in read}
    for annotation in annotations:
        if annotation.kind not in {Kind.ARROW, Kind.FREEHAND}:  # Their rectangle holds arrowheads, curves and lines.
            assert by_name[annotation.kind].rectangle == pytest.approx(annotation.rectangle)
    freehand = by_name[Kind.FREEHAND]
    assert [value for stroke in freehand.strokes for point in stroke for value in point] == pytest.approx(
        [value for stroke in FREEHAND_STROKES for point in stroke for value in point]
    )
    assert by_name[Kind.HIGHLIGHT].quads[0] == pytest.approx(annotations[0].quads[0])


def test_on_a_page_turned_in_penfold_they_turn_with_it(document: OpenDocument, tmp_path: Path) -> None:
    rectangle = new_annotation(Kind.RECTANGLE, 0, (72, 200, 200, 280), RED, "Iban")
    add(document, [rectangle])
    document.execute(RotatePages(document, [0], 90))
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    with pikepdf.open(target) as pdf:
        (read,) = read_annotations(pdf)
    assert read.rectangle == pytest.approx(turn_rectangle(rectangle.rectangle, A4, 90))


def test_saving_twice_writes_them_once(document: OpenDocument, tmp_path: Path) -> None:
    add(document, every_kind(0)[:2])
    first = saved(document, tmp_path / "first.pdf")
    second = saved(document, tmp_path / "second.pdf")
    assert len(first) == len(second) == 2


def test_undone_or_on_deleted_pages_they_are_not_written(document: OpenDocument, tmp_path: Path) -> None:
    first, second = every_kind(0)[:2]
    add(document, [first, new_annotation(Kind.RECTANGLE, 1, (72, 72, 100, 100), RED, "Iban"), second])
    document.undo()
    document.execute(DeletePages(document, [1]))
    assert saved(document, tmp_path / "saved.pdf") == ["/Highlight"]


def test_extracting_and_printing_write_them_too(document: OpenDocument, tmp_path: Path) -> None:
    add(document, [*every_kind(0)[:5], new_annotation(Kind.CIRCLE, 1, (72, 72, 100, 100), RED, "Iban")])
    save(document.extract_plan([1], tmp_path / "extracted.pdf"))
    assert subtypes(tmp_path / "extracted.pdf") == ["/Circle"]
    save(document.print_plan(tmp_path / "print.pdf", frozenset({AnnotationGroup.TEXT_MARKUPS})))
    assert subtypes(tmp_path / "print.pdf") == ["/Square", "/Circle"]


def test_their_format_is_written_as_the_standard_keeps_it(document: OpenDocument, tmp_path: Path) -> None:
    annotations = restyled(every_kind(0))
    straight = replace(annotations[6], style=Style(line_ends=LineEnds.NONE))
    add(document, [*annotations, straight])
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    with pikepdf.open(target) as pdf:
        written = pdf.pages[0].Annots
        highlight, _underline, _squiggly, _strike, rectangle, circle, arrow, freehand, comment, line = (
            written[index] for index in range(10)
        )
        assert float(highlight.CA) == 0.5
        assert str(highlight.AP.N.Resources.ExtGState.Look.BM) == "/Multiply"
        for shape in (rectangle, circle, arrow):
            assert (float(shape.BS.W), str(shape.BS.S), floats(shape.BS.D)) == (4.0, "/D", [16.0, 12.0])
            assert float(shape.CA) == 0.5
            assert float(shape.AP.N.Resources.ExtGState.Look.ca) == 0.5
        assert floats(rectangle.IC) == [0.991, 0.845, 0.83]  # a soft red inside
        assert [str(arrow.LE[index]) for index in range(2)] == ["/OpenArrow", "/OpenArrow"]
        assert [str(line.LE[index]) for index in range(2)] == ["/None", "/None"]
        assert (float(freehand.BS.W), str(freehand.BS.S), float(freehand.CA)) == (4.0, "/S", 0.5)
        assert "/CA" not in line  # opaque
        assert "/CA" not in comment
    assert pikepdf.open(target).check() == []


@pytest.mark.parametrize("formatted", [False, True])
def test_their_format_name_and_dates_are_read_back(document: OpenDocument, tmp_path: Path, *, formatted: bool) -> None:
    annotations = restyled(every_kind(0)) if formatted else every_kind(0)
    add(document, annotations)
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    with pikepdf.open(target) as pdf:
        read = sorted(read_annotations(pdf), key=lambda item: item.origin or 0)
    for written, again in zip(annotations, read, strict=True):
        assert (again.kind, again.name, again.style, again.foreign_look) == (
            written.kind,
            written.name,
            written.style,
            (),
        )
        assert written.created is not None
        assert again.created == written.created.replace(microsecond=0)
        assert again.modified == again.created
    assert read[5].line == pytest.approx(annotations[5].line)
