"""Penfold's stamps: the eight of them, their drawing, how they are saved, and changing one for another."""

from dataclasses import replace
from pathlib import Path

import cairo
import pikepdf
import pytest

from penfold.document.annotations import Annotation, AnnotationGroup, Kind, new_annotation, read_annotations
from penfold.document.commands.annotations import AddAnnotations
from penfold.document.document import OpenDocument
from penfold.document.pdf_values import numbers
from penfold.document.saving import save
from penfold.document.stamps import BLUE, GREEN, RED, STAMP_GROUPS, STAMPS
from penfold.rendering.annotation_painter import paint_annotations
from penfold.rendering.layout import ShownPage
from penfold.rendering.stamp_look import HEIGHT, stamp_drawing, stamp_size
from tests.sample_pdfs import make_pdf
from tests.test_images import near, only, pixel, render

CENTIMETRE = 72 / 2.54
GREEN_PIXEL = (38, 162, 105)


def penfold_stamp(name: str, word: str, corner: tuple[float, float], rotation: int = 0, turn: int = 0) -> Annotation:
    """One of Penfold's stamps with a word, its top left corner at a point of a page turned by rotation and turn."""
    color = STAMPS[name].color
    drawing, (width, height) = stamp_drawing(word, color, rotation, turn)
    left, top = corner
    rectangle = (left, top, left + width, top + height)
    return new_annotation(Kind.STAMP, 0, rectangle, color, "Iban", drawing=drawing, stamp=name)


def test_the_eight_stamps_in_three_groups_by_colour() -> None:
    names = [[stamp.name for stamp in group] for group in STAMP_GROUPS]
    assert names == [
        ["Approved", "Final", "Received", "Paid"],
        ["Draft", "ForComment"],
        ["NotApproved", "Confidential"],
    ]
    assert [{stamp.color for stamp in group} for group in STAMP_GROUPS] == [{GREEN}, {BLUE}, {RED}]
    assert len(STAMPS) == 8


def test_all_are_as_tall_and_as_wide_as_their_word() -> None:
    approved = stamp_size("Aprobado")
    assert approved == pytest.approx((4.1 * CENTIMETRE, HEIGHT), abs=1.5)  # About 4.1 by 1 cm on paper.
    assert pytest.approx(1.0 * CENTIMETRE, abs=0.5) == HEIGHT
    final, for_comment = stamp_size("Final"), stamp_size("Para comentarios")
    assert final[1] == for_comment[1] == HEIGHT
    assert final[0] < approved[0] < for_comment[0]
    assert stamp_size("aprobado") == approved  # In capitals.


def saved(tmp_path: Path, made: Annotation) -> Path:
    path = make_pdf(tmp_path / "plain.pdf", page_count=1)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        # A black band, 102 to 142 points from the top, to see through the background of the stamps put on it.
        pdf.pages[0].obj.Contents = pdf.make_stream(b"0 g 0 700 595 40 re f")
        pdf.save(path)
    document = OpenDocument.open(path)
    document.execute(AddAnnotations(document, [made]))
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    return target


def test_it_is_saved_with_its_name_its_colour_and_its_drawing(tmp_path: Path) -> None:
    made = penfold_stamp("Approved", "Approved", (100, 100))
    assert (made.kind, made.subtype, made.group, made.managed) == (
        Kind.STAMP,
        "Stamp",
        AnnotationGroup.IMAGES_AND_STAMPS,
        True,
    )
    target = saved(tmp_path, made)
    with pikepdf.open(target) as pdf:
        entry = only(pdf.pages[0].obj.Annots)
        assert (str(entry.Subtype), str(entry.Name), str(entry.IT), "/Contents" in entry) == (
            "/Stamp",
            "/Approved",
            "/Stamp",
            False,
        )
        assert numbers(entry.C) == pytest.approx(GREEN, abs=0.001)
        width, height = stamp_size("Approved")
        assert numbers(entry.Rect) == pytest.approx([100, 842 - 100 - height, 100 + width, 742], abs=0.01)
        (again,) = read_annotations(pdf)
    assert (again.kind, again.stamp, again.managed) == (Kind.STAMP, "Approved", False)
    assert again.color == pytest.approx(GREEN, abs=0.001)
    assert pikepdf.open(target).check() == []


def test_its_letters_go_inside(tmp_path: Path) -> None:
    target = saved(tmp_path, penfold_stamp("Paid", "Paid", (100, 100)))
    with pikepdf.open(target) as pdf:
        embedded = [
            str(item.FontName)
            for item in pdf.objects
            if isinstance(item, pikepdf.Dictionary) and item.get("/Type") == pikepdf.Name.FontDescriptor
            if "/FontFile2" in item
        ]
    assert any("LiberationSans-Bold" in name for name in embedded)  # Only with the letters used.


def test_viewers_show_its_border_and_its_faint_background(tmp_path: Path) -> None:
    shown = render(saved(tmp_path, penfold_stamp("Received", "Received", (100, 300))))
    red, green, blue = pixel(shown, 101, 314)  # Its outer border, on its left (a pixel a point: blurred).
    assert green > red + 60
    assert green > blue + 30
    assert green < 210  # Not the faint background.
    assert near(pixel(shown, 106, 314), (225, 242, 234))  # Its background, left of its word, over white: faint.


def test_what_is_under_it_shows_through(tmp_path: Path) -> None:
    # The black band is 102 to 142 points from the top: the stamp on it.
    shown = render(saved(tmp_path, penfold_stamp("Approved", "Approved", (100, 108))))
    assert max(pixel(shown, 106, 122)) < 60  # Dark: its background is faint, and lets the black show.


def painted_stamp(source_size: tuple[float, float], rotation: int, turn: int) -> cairo.ImageSurface:
    """A "Final" stamp painted with its top left corner 40 points in from the top left of a page, as it is seen."""
    page = ShownPage(0, source_size, turn)
    width, height = stamp_size("Final")
    corners = [page.to_source(40, 40), page.to_source(40 + width, 40 + height)]
    xs, ys = [x for x, _y in corners], [y for _x, y in corners]
    color = STAMPS["Final"].color
    drawing, _size = stamp_drawing("Final", color, rotation, turn)
    rectangle = (min(xs), min(ys), max(xs), max(ys))
    made = new_annotation(Kind.STAMP, 0, rectangle, color, "Iban", drawing=drawing, stamp="Final")
    shown_width, shown_height = page.size
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, round(shown_width), round(shown_height))
    context = cairo.Context(surface)
    context.set_source_rgb(1, 1, 1)
    context.paint()
    paint_annotations(context, page, [made])
    surface.flush()
    return surface


@pytest.mark.parametrize("rotation", [0, 90, 270])
@pytest.mark.parametrize("turn", [0, 90, 180])
def test_it_is_upright_as_the_page_is_seen(rotation: int, turn: int) -> None:
    """Painted on a page turned by its PDF and by Penfold, it looks as on a page that is not turned."""
    upright = painted_stamp((300.0, 200.0), 0, 0)
    # The page as its PDF shows it (turned by /Rotate already): Penfold's turn comes on top.
    turned = painted_stamp((300.0, 200.0), rotation, turn)
    width, height = stamp_size("Final")
    differences = [
        sum(abs(a - b) for a, b in zip(pixel(upright, x, y), pixel(turned, x, y), strict=True))
        for y in range(40, 40 + int(height))
        for x in range(40, 40 + int(width))
    ]
    assert sum(differences) / len(differences) < 6  # The same, but for the smoothing of edges.


def test_changed_for_another_it_keeps_its_centre_and_its_height() -> None:
    from penfold.rendering.stamp_look import restamped

    page = ShownPage(0, (595.0, 842.0))
    approved = penfold_stamp("Approved", "Approved", (100, 100))
    # Made twice as big with its handles first: the new one is as tall, and as wide as its word needs at that height.
    left, top, right, bottom = approved.rectangle
    approved = replace(approved, rectangle=(left, top, left + 2 * (right - left), top + 2 * (bottom - top)))
    draft = restamped(approved, STAMPS["Draft"], "Draft", page, 0)
    assert (draft.stamp, draft.color, draft.name, draft.managed) == ("Draft", BLUE, approved.name, True)
    assert draft.drawing != approved.drawing
    old_left, old_top, old_right, old_bottom = approved.rectangle
    new_left, new_top, new_right, new_bottom = draft.rectangle
    assert ((new_left + new_right) / 2, (new_top + new_bottom) / 2) == pytest.approx(
        ((old_left + old_right) / 2, (old_top + old_bottom) / 2)
    )
    assert new_bottom - new_top == pytest.approx(old_bottom - old_top)
    width, height = stamp_size("Draft")
    assert new_right - new_left == pytest.approx(2 * width * HEIGHT / height)


def test_changed_near_the_edge_it_stays_inside_the_page() -> None:
    from penfold.rendering.stamp_look import restamped

    page = ShownPage(0, (595.0, 842.0))
    final = penfold_stamp("Final", "Final", (595 - stamp_size("Final")[0], 100))  # At the right edge.
    longer = restamped(final, STAMPS["ForComment"], "For Comment", page, 0)
    assert longer.rectangle[2] == pytest.approx(595)
    assert longer.rectangle[2] - longer.rectangle[0] == pytest.approx(stamp_size("For Comment")[0])


@pytest.mark.parametrize("turn", [90, 270])
def test_changed_on_a_page_turned_in_penfold_it_keeps_its_height_as_seen(turn: int) -> None:
    from penfold.rendering.stamp_look import restamped

    page = ShownPage(0, (595.0, 842.0), turn)
    width, height = stamp_size("Paid")
    shown = (100.0, 100.0, 100 + width, 100 + height)
    paid = penfold_stamp("Paid", "Paid", (0, 0), turn=turn)
    paid = replace(paid, rectangle=page.to_source_rectangle(shown))
    received = restamped(paid, STAMPS["Received"], "Received", page, 0)
    left, top, right, bottom = page.from_source(received.rectangle)
    assert bottom - top == pytest.approx(height)
    assert right - left == pytest.approx(stamp_size("Received")[0])
    assert (left + right) / 2 == pytest.approx(100 + width / 2)
