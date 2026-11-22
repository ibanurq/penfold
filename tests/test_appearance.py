"""Writing the annotations made in Penfold into the PDF, with their drawing and the standard's entries (H14, D67)."""

from dataclasses import replace
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
from penfold.document.commands.annotations import AddAnnotations  # noqa: E402
from penfold.document.commands.pages import DeletePages, RotatePages  # noqa: E402
from penfold.document.document import OpenDocument  # noqa: E402
from penfold.document.geometry import turn_rectangle  # noqa: E402
from penfold.document.saving import save  # noqa: E402
from tests.sample_pdfs import make_pdf  # noqa: E402

YELLOW = (0.976, 0.941, 0.42)
RED = (0.965, 0.38, 0.318)
A4 = (595.0, 842.0)


def every_kind(page: int) -> list[Annotation]:
    return [
        new_annotation(Kind.HIGHLIGHT, page, (72, 72, 300, 90), YELLOW, "Iban", quads=((72, 72, 300, 90),)),
        new_annotation(Kind.UNDERLINE, page, (72, 100, 300, 118), RED, "Iban", quads=((72, 100, 300, 118),)),
        new_annotation(Kind.STRIKE_OUT, page, (72, 130, 300, 148), RED, "Iban", quads=((72, 130, 300, 148),)),
        new_annotation(Kind.RECTANGLE, page, (72, 200, 200, 280), RED, "Iban"),
        new_annotation(Kind.CIRCLE, page, (250, 200, 400, 280), RED, "Iban"),
        new_annotation(Kind.ARROW, page, (72, 320, 300, 400), RED, "Iban", line=(72, 400, 300, 320)),
        new_annotation(Kind.COMMENT, page, (400, 72, 420, 92), YELLOW, "Iban", text="Ñandú → ✓ (a) \\ 😀"),
    ]


def restyled(annotations: list[Annotation]) -> list[Annotation]:
    """The same annotations as their Format panel can leave them (D72): thick, dashed, filled, see-through."""
    style = Style(opacity=0.5, line_width=4.0, dashed=True, filled=True, line_ends=LineEnds.BOTH)
    return [
        annotation if annotation.kind is Kind.COMMENT else replace(annotation, style=style)
        for annotation in annotations
    ]


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
        highlight, underline, _strike, rectangle, _circle, arrow, comment = (written[index] for index in range(7))
        assert float(highlight.CA) == 0.75
        assert floats(highlight.QuadPoints) == [72, 770, 300, 770, 72, 752, 300, 752]
        assert floats(rectangle.Rect) == [72, 562, 200, 642]
        assert (float(rectangle.BS.W), str(rectangle.BS.S)) == (1.0, "/S")
        assert "/IC" not in rectangle  # nothing inside
        assert floats(arrow.L) == [72, 442, 300, 522]
        assert [str(arrow.LE[index]) for index in range(len(arrow.LE))] == ["/None", "/OpenArrow"]
        assert (str(comment.Name), str(comment.Contents)) == ("/Comment", "Ñandú → ✓ (a) \\ 😀")
        assert "/Contents" not in underline
        assert "/Popup" not in comment
    assert pikepdf.open(target).check() == []


def test_poppler_reads_them_with_their_author_and_text(document: OpenDocument, tmp_path: Path) -> None:
    add(document, every_kind(0))
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    page = Poppler.Document.new_from_file(target.as_uri(), None).get_page(0)
    read = {mapping.annot.get_annot_type().value_nick: mapping.annot for mapping in page.get_annot_mapping()}
    assert set(read) == {"highlight", "underline", "strike-out", "square", "circle", "line", "text"}
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
        if annotation.kind is not Kind.ARROW:  # Its rectangle holds the arrowhead too.
            assert by_name[annotation.kind].rectangle == pytest.approx(annotation.rectangle)
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
    add(document, [*every_kind(0)[:4], new_annotation(Kind.CIRCLE, 1, (72, 72, 100, 100), RED, "Iban")])
    save(document.extract_plan([1], tmp_path / "extracted.pdf"))
    assert subtypes(tmp_path / "extracted.pdf") == ["/Circle"]
    save(document.print_plan(tmp_path / "print.pdf", frozenset({AnnotationGroup.TEXT_MARKUPS})))
    assert subtypes(tmp_path / "print.pdf") == ["/Square", "/Circle"]


def test_their_format_is_written_as_the_standard_keeps_it(document: OpenDocument, tmp_path: Path) -> None:
    annotations = restyled(every_kind(0))
    straight = replace(annotations[5], style=Style(line_ends=LineEnds.NONE))
    add(document, [*annotations, straight])
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    with pikepdf.open(target) as pdf:
        written = pdf.pages[0].Annots
        highlight, _underline, _strike, rectangle, circle, arrow, comment, line = (written[index] for index in range(8))
        assert float(highlight.CA) == 0.5
        assert str(highlight.AP.N.Resources.ExtGState.Look.BM) == "/Multiply"
        for shape in (rectangle, circle, arrow):
            assert (float(shape.BS.W), str(shape.BS.S), floats(shape.BS.D)) == (4.0, "/D", [16.0, 12.0])
            assert float(shape.CA) == 0.5
            assert float(shape.AP.N.Resources.ExtGState.Look.ca) == 0.5
        assert floats(rectangle.IC) == [0.991, 0.845, 0.83]  # a soft red inside
        assert [str(arrow.LE[index]) for index in range(2)] == ["/OpenArrow", "/OpenArrow"]
        assert [str(line.LE[index]) for index in range(2)] == ["/None", "/None"]
        assert "/CA" not in line  # opaque
        assert "/CA" not in comment
    assert pikepdf.open(target).check() == []
