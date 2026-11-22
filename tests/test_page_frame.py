"""Where things are on a page as Poppler shows it: its crop box and its own turn."""

from pathlib import Path

import pikepdf
import pytest

from penfold.document.annotations import read_annotations
from penfold.document.page_frame import PageFrame
from tests.sample_pdfs import make_pdf

# A crop box that does not start at the corner of the page: 400 by 600 points.
CROP_BOX = (50.0, 100.0, 450.0, 700.0)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_a_point_goes_to_the_page_as_shown_and_back(rotation: int) -> None:
    frame = PageFrame(CROP_BOX, rotation)
    shown = frame.point(80, 650)
    assert frame.pdf_point(*shown) == pytest.approx((80, 650))


def test_points_are_measured_from_the_top_left_corner_of_the_crop_box() -> None:
    assert PageFrame(CROP_BOX).point(50, 700) == (0, 0)
    assert PageFrame(CROP_BOX).point(450, 100) == (400, 600)
    assert PageFrame(CROP_BOX, 90).point(50, 700) == (600, 0)  # the top left corner goes to the top right one


def test_a_rectangle_is_placed_on_the_turned_page() -> None:
    assert PageFrame(CROP_BOX, 90).place(pikepdf.Array([50, 600, 150, 700])) == (500, 0, 600, 100)
    assert PageFrame(CROP_BOX).place(pikepdf.Array([1, 2])) is None


def test_annotations_are_read_on_the_page_as_shown(tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "turned.pdf", page_count=1)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        page = pdf.pages[0]
        page.obj.CropBox = pikepdf.Array(CROP_BOX)
        page.obj.Rotate = 90
        highlight = pikepdf.Dictionary(
            Type=pikepdf.Name.Annot,
            Subtype=pikepdf.Name.Highlight,
            Rect=[50, 600, 150, 700],
            QuadPoints=[50, 700, 150, 700, 50, 600, 150, 600],
        )
        page.obj.Annots = pdf.make_indirect(pikepdf.Array([pdf.make_indirect(highlight)]))
        pdf.save(path)
    with pikepdf.open(path) as pdf:
        (annotation,) = read_annotations(pdf)
    assert (annotation.rectangle, annotation.quads) == ((500, 0, 600, 100), ((500, 0, 600, 100),))
