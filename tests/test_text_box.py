"""Text boxes: their height follows the text, and the screen shows what is saved, fonts inside (H3, D69)."""

from pathlib import Path

import gi
import pikepdf
import pytest

gi.require_foreign("cairo")

from penfold.document.annotations import Annotation, Kind, Style, new_annotation  # noqa: E402
from penfold.document.commands.annotations import AddAnnotations  # noqa: E402
from penfold.document.commands.pages import RotatePages  # noqa: E402
from penfold.document.document import OpenDocument  # noqa: E402
from penfold.document.reshaping import Handle  # noqa: E402
from penfold.document.saving import save  # noqa: E402
from penfold.rendering.layout import ShownPage  # noqa: E402
from penfold.rendering.text_box import (  # noqa: E402
    BORDER,
    NARROWEST,
    PADDING,
    side_handles,
    text_box_pdf,
    text_height,
    with_side,
    with_text,
    written_frame,
    written_height,
)
from tests.sample_pdfs import make_pdf  # noqa: E402

BLUE = (0.6, 0.757, 0.945)
A4_SIZE = (595.0, 842.0)
TEXT = "Ñandú → ✓ Ωμέγα Привет, a text long enough to need a few lines in a narrow box"


def text_box(
    page: int, corner: tuple[float, float], width: float, *, text_turn: int = 0, style: Style | None = None
) -> Annotation:
    """A text box as Penfold makes it: its height follows the text; turned a quarter, it is taller than wide."""
    style = style or Style()
    left, top = corner
    text = TEXT
    height = text_height(text, width, style.font_size)
    size = (width, height)
    across = text_turn % 180 != 0
    rectangle = (left, top, left + (height if across else width), top + (width if across else height))
    drawing = text_box_pdf(text, size, BLUE, style)
    return new_annotation(
        Kind.TEXT_BOX, page, rectangle, BLUE, "Iban", text=text, text_turn=text_turn, drawing=drawing, style=style
    )


def font_descriptor(font: pikepdf.Object) -> pikepdf.Object:
    """The descriptor of a simple font, or of the font of a composite one (Type0)."""
    if "/DescendantFonts" in font:
        return font.DescendantFonts[0].FontDescriptor
    return font.FontDescriptor


def font_name(font: pikepdf.Object) -> str:
    return str(font_descriptor(font).FontName)


def test_the_height_follows_the_text() -> None:
    one_line = text_height("Short", 200)
    assert one_line == pytest.approx(2 * (PADDING + BORDER) + 12.6, abs=1.5)  # About 1.15 of 11 points per line.
    assert text_height(TEXT, 200) > 2 * one_line - 2 * (PADDING + BORDER)
    assert text_height(TEXT, 120) > text_height(TEXT, 200)
    assert text_height("Short", 200, 18) > one_line  # bigger letters (D72)


def test_it_is_saved_with_its_entries_and_its_fonts_inside(tmp_path: Path) -> None:
    document = OpenDocument.open(make_pdf(tmp_path / "one.pdf", page_count=1))
    document.execute(AddAnnotations(document, [text_box(0, (72, 100), 200)]))
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    with pikepdf.open(target) as pdf:
        entry = pdf.pages[0].Annots[0]
        assert (str(entry.Subtype), str(entry.Contents), int(entry.Q)) == ("/FreeText", TEXT, 0)
        assert str(entry.DA) == "0 g /Helv 11 Tf"
        assert "Liberation Sans" in str(entry.DS)
        assert [round(float(entry.IC[index]), 3) for index in range(3)] == [0.944, 0.966, 0.992]
        fonts = entry.AP.N.Resources.Font
        names = [font_name(fonts[name]) for name in fonts.keys() if "/FontFile2" in font_descriptor(fonts[name])]  # noqa: SIM118 (a PDF dictionary)
        assert any("LiberationSans" in name for name in names)  # Inside, only with the characters used.
    assert pikepdf.open(target).check() == []


def test_its_format_is_saved(tmp_path: Path) -> None:
    document = OpenDocument.open(make_pdf(tmp_path / "one.pdf", page_count=1))
    plain = Style(font_size=18, background=False, border=False)
    document.execute(AddAnnotations(document, [text_box(0, (72, 100), 200, style=plain)]))
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    with pikepdf.open(target) as pdf:
        entry = pdf.pages[0].Annots[0]
        assert str(entry.DA) == "0 g /Helv 18 Tf"
        assert "18pt" in str(entry.DS)
        assert "/IC" not in entry  # no background
        assert float(entry.BS.W) == 0  # no border


@pytest.mark.parametrize(
    ("turned_before", "turned_after", "style"),
    [(0, 0, None), (90, 0, None), (0, 90, None), (90, 180, None), (0, 0, Style(font_size=14, background=False))],
)
def test_the_screen_shows_what_is_saved(
    tmp_path: Path, turned_before: int, turned_after: int, style: Style | None
) -> None:
    from gi.repository import Poppler

    from penfold.rendering.annotation_painter import paint_annotations
    from penfold.rendering.layout import ShownPage
    from tests.test_annotation_painter import A4, differing_pixels, white_surface

    document = OpenDocument.open(make_pdf(tmp_path / "one.pdf", page_count=1))
    if turned_before:
        document.execute(RotatePages(document, [0], turned_before))
    box = text_box(0, (100, 150), 160, text_turn=turned_before, style=style)  # Upright on the page as turned then.
    document.execute(AddAnnotations(document, [box]))
    if turned_after:
        document.execute(RotatePages(document, [0], turned_after))
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    page = ShownPage(0, A4, (turned_before + turned_after) % 360)
    painted, context = white_surface(page.size)
    paint_annotations(context, page, [box])
    saved, context = white_surface(page.size)
    Poppler.Document.new_from_file(target.as_uri(), None).get_page(0).render_for_printing(context)
    different, total = differing_pixels(painted, saved)
    assert total > 5_000  # Something is painted (less without a background).
    assert different / total < 0.03


@pytest.mark.parametrize("text_turn", [0, 90, 180, 270])
def test_another_text_keeps_where_it_starts_and_its_width(text_turn: int) -> None:
    box = text_box(0, (100, 150), 160, text_turn=text_turn)
    longer = with_text(box, TEXT + " " + TEXT, A4_SIZE)
    (corner, width), (new_corner, new_width) = written_frame(box, A4_SIZE), written_frame(longer, A4_SIZE)
    assert new_corner == pytest.approx(corner)
    assert new_width == pytest.approx(width)
    area = (box.rectangle[2] - box.rectangle[0]) * (box.rectangle[3] - box.rectangle[1])
    new_area = (longer.rectangle[2] - longer.rectangle[0]) * (longer.rectangle[3] - longer.rectangle[1])
    assert new_area > area  # Taller as it reads, for the longer text.
    assert longer.text == TEXT + " " + TEXT


def frame(box: Annotation) -> tuple[float, float, float]:
    """Where a box's text starts and how wide it is, as its text reads: left, top, width."""
    (left, top), width = written_frame(box, A4_SIZE)
    return left, top, width


def written_point(box: Annotation, x: float, y: float) -> tuple[float, float]:
    """A point of the box's page given as its text reads, in points of the unturned page."""
    return ShownPage(box.page, A4_SIZE, box.text_turn).to_source(x, y)


@pytest.mark.parametrize("text_turn", [0, 90, 180, 270])
def test_the_handles_of_a_text_box_are_in_the_middle_of_its_sides(text_turn: int) -> None:
    box = text_box(0, (100, 150), 160, text_turn=text_turn)
    (left, top), width = written_frame(box, A4_SIZE)
    middle = top + written_height(box) / 2
    handles = side_handles(box, A4_SIZE)
    assert handles[Handle.LEFT] == pytest.approx(written_point(box, left, middle))
    assert handles[Handle.RIGHT] == pytest.approx(written_point(box, left + width, middle))


@pytest.mark.parametrize("text_turn", [0, 90, 180, 270])
def test_narrower_from_the_right_side_it_is_taller_and_starts_where_it_did(text_turn: int) -> None:
    box = text_box(0, (100, 150), 160, text_turn=text_turn)
    left, top, _width = frame(box)
    narrower = with_side(box, Handle.RIGHT, written_point(box, left + 120, top + 300), A4_SIZE)
    assert frame(narrower) == pytest.approx((left, top, 120))
    assert written_height(narrower) == pytest.approx(text_height(TEXT, 120))
    assert written_height(narrower) > written_height(box)
    assert narrower.drawing == box.drawing  # Drawn again by whoever uses it, once it is done.


@pytest.mark.parametrize("text_turn", [0, 90])
def test_wider_from_the_left_side_its_height_follows_the_text_and_it_ends_where_it_did(text_turn: int) -> None:
    box = text_box(0, (100, 150), 160, text_turn=text_turn)
    left, top, width = frame(box)
    wider = with_side(box, Handle.LEFT, written_point(box, left - 60, top - 40), A4_SIZE)
    assert frame(wider) == pytest.approx((left - 60, top, width + 60))
    assert written_height(wider) == pytest.approx(text_height(TEXT, width + 60))


def test_a_text_box_is_never_narrower_than_the_narrowest() -> None:
    box = text_box(0, (100, 150), 160)
    assert frame(with_side(box, Handle.RIGHT, (20, 160), A4_SIZE)) == pytest.approx((100, 150, NARROWEST))
    assert frame(with_side(box, Handle.LEFT, (400, 160), A4_SIZE)) == pytest.approx((260 - NARROWEST, 150, NARROWEST))


@pytest.mark.parametrize("text_turn", [0, 90])
def test_a_text_box_is_never_wider_than_its_page(text_turn: int) -> None:
    box = text_box(0, (100, 150), 160, text_turn=text_turn)
    left, top, _width = frame(box)
    page_width, _height = ShownPage(0, A4_SIZE, text_turn).size
    widest = with_side(box, Handle.RIGHT, written_point(box, page_width, top), A4_SIZE)
    beyond = with_side(box, Handle.RIGHT, written_point(box, 5000, top), A4_SIZE)
    assert frame(beyond) == pytest.approx(frame(widest))
    assert frame(widest) == pytest.approx((left, top, page_width - left))
    assert frame(with_side(box, Handle.LEFT, written_point(box, -90, top), A4_SIZE))[0] == pytest.approx(0)


def test_only_the_sides_change_a_text_box() -> None:
    with pytest.raises(ValueError, match="not a side"):
        with_side(text_box(0, (100, 150), 160), Handle.TOP_LEFT, (0, 0), A4_SIZE)
