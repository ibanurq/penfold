"""Annotations of other programs moved keeping the drawing their program made (D73): saved and shown."""

from pathlib import Path

import cairo
import pikepdf
import pytest

from penfold.document.annotations import Annotation, Kind, read_annotations
from penfold.document.commands.annotations import ChangeAnnotation
from penfold.document.commands.pages import RotatePages
from penfold.document.document import OpenDocument
from penfold.document.pdf_values import numbers
from penfold.document.reshaping import moved
from penfold.document.saving import save
from penfold.rendering.kept_look import KeptLooks, paint_look
from penfold.rendering.layout import ShownPage
from tests.test_annotation_menu import make_annotated_pdf

A4 = (595.0, 842.0)
# The drawing of the square, as its program made it: a red frame, 4 points wide, inside its rectangle.
SQUARE_DRAWING = b"1 0 0 RG 4 w 2 2 196 196 re S"


@pytest.fixture
def path(tmp_path: Path) -> Path:
    """The annotations of another program; the square with its own drawing, and the comment with a note window."""
    path = make_annotated_pdf(tmp_path / "annotated.pdf")
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        annots = pdf.pages[0].obj.Annots
        drawing = pdf.make_stream(SQUARE_DRAWING, BBox=[0, 0, 200, 200], Type=pikepdf.Name.XObject)
        drawing.Subtype = pikepdf.Name.Form
        annots[1].AP = pikepdf.Dictionary(N=drawing)
        window = pdf.make_indirect(
            pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Popup, Rect=[540, 700, 590, 780])
        )
        annots[3].Popup = window
        annots.append(window)  # Last, so that the others keep their places.
        pdf.save(path)
    return path


def of_kind(annotations: list[Annotation], kind: Kind) -> Annotation:
    return next(item for item in annotations if item.kind is kind)


def move(document: OpenDocument, kind: Kind, offset: tuple[float, float]) -> Annotation:
    """Move an annotation of the document by an offset on its unturned page (points, downwards)."""
    original = of_kind(document.annotations, kind)
    changed = moved(original, offset, A4)
    document.execute(ChangeAnnotation(document, original, changed))
    return changed


def test_saved_it_is_moved_in_its_page_with_its_own_drawing(path: Path, tmp_path: Path) -> None:
    document = OpenDocument.open(path)
    square = move(document, Kind.RECTANGLE, (30, 40))
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    with pikepdf.open(target) as pdf:
        saved = pdf.pages[0].obj.Annots[1]
        assert numbers(saved.Rect) == pytest.approx([130, 360, 330, 560])  # Up is down.
        assert saved.AP.N.read_bytes() == SQUARE_DRAWING
        assert "/BE" in saved  # Its cloudy border, which Penfold cannot draw, is still there.
        assert "/M" in saved
        others = [pdf.pages[0].obj.Annots[index] for index in (0, 2, 3, 4, 5)]
        assert [str(item.Subtype) for item in others] == ["/Highlight", "/Ink", "/Text", "/FreeText", "/Line"]
        read = read_annotations(pdf)
    assert of_kind(read, Kind.RECTANGLE).rectangle == pytest.approx(square.rectangle)


def test_a_comment_takes_its_note_window_along(path: Path, tmp_path: Path) -> None:
    document = OpenDocument.open(path)
    move(document, Kind.COMMENT, (-20, 10))
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    with pikepdf.open(target) as pdf:
        comment = pdf.pages[0].obj.Annots[3]
        assert numbers(comment.Rect) == pytest.approx([500, 770, 520, 790])
        assert numbers(comment.Popup.Rect) == pytest.approx([520, 690, 570, 770])


def test_an_arrow_takes_its_line_along(path: Path, tmp_path: Path) -> None:
    document = OpenDocument.open(path)
    move(document, Kind.ARROW, (5, 5))
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    with pikepdf.open(target) as pdf:
        arrow = pdf.pages[0].obj.Annots[5]
        assert numbers(arrow.L) == pytest.approx([315, 745, 415, 775])


def test_on_a_page_penfold_turned_it_moves_as_it_shows(path: Path, tmp_path: Path) -> None:
    document = OpenDocument.open(path)
    document.execute(RotatePages(document, [0], 90))
    square = move(document, Kind.RECTANGLE, (30, 40))
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    with pikepdf.open(target) as pdf:
        read = read_annotations(pdf)
    shown = ShownPage(0, A4, 90).from_source(square.rectangle)
    assert of_kind(read, Kind.RECTANGLE).rectangle == pytest.approx(shown)


def test_undone_it_is_saved_where_it_was(path: Path, tmp_path: Path) -> None:
    document = OpenDocument.open(path)
    move(document, Kind.RECTANGLE, (30, 40))
    document.undo()
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    with pikepdf.open(target) as pdf:
        assert numbers(pdf.pages[0].obj.Annots[1].Rect) == pytest.approx([100, 400, 300, 600])


def reddest_near(surface: cairo.ImageSurface, x: float, y: float) -> int:
    """How red the reddest pixel is within two points of a point: red minus green."""
    data, stride = surface.get_data(), surface.get_stride()
    best = 0
    for row in range(round(y) - 2, round(y) + 3):
        for column in range(round(x) - 2, round(x) + 3):
            _blue, green, red = data[row * stride + column * 4 : row * stride + column * 4 + 3]
            best = max(best, red - green)
    return best


def test_it_shows_with_its_own_drawing_where_it_was_moved(path: Path) -> None:
    document = OpenDocument.open(path)
    square = move(document, Kind.RECTANGLE, (30, 40))
    looks = KeptLooks(lambda: document.sources.spans)
    look = looks.look(square)
    assert look is not None
    assert looks.look(square) is look  # Recorded once.
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 595, 842)
    context = cairo.Context(surface)
    context.set_source_rgb(1, 1, 1)
    context.paint()
    paint_look(context, ShownPage(0, A4), square, look)
    surface.flush()
    left, top, _right, bottom = square.rectangle
    assert reddest_near(surface, left + 2, (top + bottom) / 2) > 200  # Its own 4-point frame, moved.
    assert reddest_near(surface, left - 28, (top + bottom) / 2) == 0  # Not where it was.
