"""Images: stamps whose drawing is an image, read, edited, saved, printed and painted (ISO 32000-1, 12.5.6.12)."""

import io
import zlib
from dataclasses import replace
from pathlib import Path

import cairo
import gi
import pikepdf
import pytest

from penfold.document.annotations import Annotation, AnnotationGroup, Kind, group_of, managed_copy, read_annotations
from penfold.document.commands.annotations import ChangeAnnotation
from penfold.document.document import OpenDocument
from penfold.document.images import image_drawing
from penfold.document.pdf_values import numbers
from penfold.document.saving import save
from penfold.rendering.annotation_painter import paint_annotations
from penfold.rendering.layout import ShownPage
from tests.sample_pdfs import make_pdf

gi.require_version("Poppler", "0.18")
from gi.repository import Poppler  # noqa: E402

A4 = (595.0, 842.0)
# The image of the stamps: blue on its left, orange on its right.
BLUE = (40, 90, 220)
ORANGE = (240, 90, 40)


def image(pdf: pikepdf.Pdf) -> pikepdf.Stream:
    """An image 2 pixels wide and 1 tall: blue, then orange."""
    stream = pikepdf.Stream(pdf, zlib.compress(bytes([*BLUE, *ORANGE])))
    stream.Type, stream.Subtype = pikepdf.Name.XObject, pikepdf.Name.Image
    stream.Width, stream.Height, stream.BitsPerComponent = 2, 1, 8
    stream.ColorSpace, stream.Filter = pikepdf.Name.DeviceRGB, pikepdf.Name.FlateDecode
    return stream


def form(pdf: pikepdf.Pdf, content: str, size: tuple[float, float], **xobjects: pikepdf.Object) -> pikepdf.Stream:
    stream = pdf.make_stream(content.encode(), Type=pikepdf.Name.XObject, BBox=[0, 0, *size])
    stream.Subtype = pikepdf.Name.Form
    stream.Resources = pikepdf.Dictionary(
        XObject=pikepdf.Dictionary({f"/{key}": value for key, value in xobjects.items()})
    )
    return stream


def stamp(pdf: pikepdf.Pdf, rect: list[float], content: str = "", **entries: object) -> pikepdf.Dictionary:
    """A stamp whose drawing paints the image filling it (or does what content says), as other programs make them."""
    size = (rect[2] - rect[0], rect[3] - rect[1])
    drawing = form(pdf, content or f"q {size[0]:g} 0 0 {size[1]:g} 0 0 cm /Im0 Do Q", size, Im0=image(pdf))
    dictionary = pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Stamp, Rect=rect)
    dictionary.AP = pikepdf.Dictionary(N=drawing)
    for key, value in entries.items():
        dictionary[f"/{key}"] = value
    return dictionary


def annotated(path: Path, stamps: list[pikepdf.Dictionary] | None = None, rotation: int = 0) -> Path:
    """A one-page PDF with stamps (made with its own pdf) on its page, turned by rotation."""
    make_pdf(path, page_count=1)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        added = stamps if stamps is not None else [stamp(pdf, [100, 600, 220, 680])]
        pdf.pages[0].obj.Annots = pdf.make_indirect(pikepdf.Array([pdf.make_indirect(item) for item in added]))
        if rotation:
            pdf.pages[0].obj.Rotate = rotation
        pdf.save(path)
    return path


def read(path: Path) -> list[Annotation]:
    with pikepdf.open(path) as pdf:
        return read_annotations(pdf)


def with_stamps(path: Path, *makers: object) -> list[Annotation]:
    """The annotations read from a page with the stamps that each maker (pdf → dictionary) makes."""
    make_pdf(path, page_count=1)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        made = [maker(pdf) for maker in makers]  # type: ignore[operator]
        pdf.pages[0].obj.Annots = pdf.make_indirect(pikepdf.Array([pdf.make_indirect(item) for item in made]))
        pdf.save(path)
    return read(path)


def test_a_stamp_that_paints_an_image_is_an_image(tmp_path: Path) -> None:
    (found,) = read(annotated(tmp_path / "image.pdf"))
    assert (found.kind, found.subtype, found.group, found.color) == (
        Kind.IMAGE,
        "Stamp",
        AnnotationGroup.IMAGES_AND_STAMPS,
        None,
    )
    assert found.rectangle == pytest.approx((100, 162, 220, 242))
    with pikepdf.open(io.BytesIO(found.drawing)) as drawing:
        assert numbers(drawing.pages[0].MediaBox) == pytest.approx([0, 0, 120, 80])  # As big as its drawing.


def test_clipped_or_inside_another_drawing_it_is_still_an_image(tmp_path: Path) -> None:
    clipped = "q 0 0 120 80 re W n q 120 0 0 80 0 0 cm /Im0 Do Q Q"

    def nested(pdf: pikepdf.Pdf) -> pikepdf.Dictionary:
        inner = form(pdf, "q 60 0 0 40 0 0 cm /Im0 Do Q", (60, 40), Im0=image(pdf))
        made = stamp(pdf, [300, 600, 360, 640])
        made.AP.N = form(pdf, "/Inner Do", (60, 40), Inner=inner)
        return made

    found = with_stamps(tmp_path / "images.pdf", lambda pdf: stamp(pdf, [100, 600, 220, 680], clipped), nested)
    assert [item.kind for item in found] == [Kind.IMAGE, Kind.IMAGE]


def test_pdf_2_says_a_stamp_is_an_image(tmp_path: Path) -> None:
    framed = "q 120 0 0 80 0 0 cm /Im0 Do Q 0 G 2 w 0 0 120 80 re S"  # An image with a frame drawn round it.
    found = with_stamps(
        tmp_path / "stamps.pdf",
        lambda pdf: stamp(pdf, [100, 600, 220, 680], framed, IT=pikepdf.Name.StampImage),
        lambda pdf: stamp(pdf, [300, 600, 420, 680], framed),
    )
    assert [item.kind for item in found] == [Kind.IMAGE, Kind.STAMP]


def test_a_stamp_without_a_drawing_is_not_an_image(tmp_path: Path) -> None:
    def bare(pdf: pikepdf.Pdf) -> pikepdf.Dictionary:
        made = stamp(pdf, [300, 600, 420, 680], IT=pikepdf.Name.StampImage)
        del made["/AP"]  # Without a drawing, each viewer draws its own.
        return made

    (found,) = with_stamps(tmp_path / "stamps.pdf", bare)
    assert (found.kind, found.group) == (Kind.STAMP, AnnotationGroup.IMAGES_AND_STAMPS)


def test_the_drawing_of_its_state_is_the_one_shown(tmp_path: Path) -> None:
    def with_states(pdf: pikepdf.Pdf) -> pikepdf.Dictionary:
        made = stamp(pdf, [100, 600, 220, 680])
        made.AP.N = pikepdf.Dictionary(On=made.AP.N, Off=form(pdf, "0 G 0 0 120 80 re S", (120, 80)))
        made.AS = pikepdf.Name.On
        return made

    (found,) = with_stamps(tmp_path / "states.pdf", with_states)
    assert found.kind is Kind.IMAGE


def test_the_group_of_an_annotation_of_a_pdf(tmp_path: Path) -> None:
    make_pdf(tmp_path / "plain.pdf", page_count=1)
    with pikepdf.open(tmp_path / "plain.pdf") as pdf:
        assert group_of(stamp(pdf, [0, 0, 120, 80])) is AnnotationGroup.IMAGES_AND_STAMPS
        assert group_of(stamp(pdf, [0, 0, 120, 80], "0 G 0 0 120 80 re S")) is AnnotationGroup.IMAGES_AND_STAMPS


def render(path: Path) -> cairo.ImageSurface:
    """The first page of a PDF as Poppler draws it, one pixel a point, on white (turned as the PDF says)."""
    page = Poppler.Document.new_from_file(path.as_uri(), None).get_page(0)
    width, height = page.get_size()
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, round(width), round(height))
    context = cairo.Context(surface)
    context.set_source_rgb(1, 1, 1)
    context.paint()
    page.render(context)
    surface.flush()
    return surface


def pixel(surface: cairo.ImageSurface, x: float, y: float) -> tuple[int, int, int]:
    data, stride = surface.get_data(), surface.get_stride()
    offset = round(y) * stride + round(x) * 4
    blue, green, red = data[offset : offset + 3]
    return red, green, blue


def only(annots: pikepdf.Object) -> pikepdf.Object:
    """The only annotation of a page's /Annots."""
    assert isinstance(annots, pikepdf.Array)
    assert len(annots) == 1
    return annots[0]


def near(color: tuple[int, int, int], expected: tuple[int, int, int], tolerance: int = 12) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(color, expected, strict=True))


@pytest.mark.parametrize("rotation", [0, 90])
def test_written_again_it_looks_as_it_did(tmp_path: Path, rotation: int) -> None:
    path = annotated(tmp_path / "image.pdf", rotation=rotation)
    document = OpenDocument.open(path)
    (original,) = document.annotations
    document.execute(ChangeAnnotation(document, original, managed_copy(original)))
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    before, after = render(path), render(target)
    # Where the left and the right of the image are shown (the page turned clockwise, its left is at the top).
    left, right = ((130, 202), (190, 202)) if rotation == 0 else ((640, 130), (640, 190))
    for x, y in (left, right):
        assert pixel(after, x, y) == pixel(before, x, y)
    assert near(pixel(after, *left), BLUE)
    assert near(pixel(after, *right), ORANGE)
    with pikepdf.open(target) as pdf:
        saved = only(pdf.pages[0].obj.Annots)
        assert (str(saved.Subtype), str(saved.IT), "/C" in saved) == ("/Stamp", "/StampImage", False)
        assert numbers(saved.Rect) == pytest.approx([100, 600, 220, 680])
        (again,) = read_annotations(pdf)
    assert again.kind is Kind.IMAGE
    assert again.rectangle == pytest.approx(original.rectangle)


def test_its_opacity_goes_in_its_drawing_too(tmp_path: Path) -> None:
    path = annotated(tmp_path / "image.pdf")
    document = OpenDocument.open(path)
    (original,) = document.annotations
    faint = managed_copy(original)
    faint = replace(faint, style=replace(faint.style, opacity=0.5))
    document.execute(ChangeAnnotation(document, original, faint))
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    with pikepdf.open(target) as pdf:
        saved = only(pdf.pages[0].obj.Annots)
        assert float(saved.CA) == 0.5
        assert float(saved.AP.N.Resources.ExtGState.Look.ca) == 0.5
        (again,) = read_annotations(pdf)
    assert again.style.opacity == 0.5
    shown = pixel(render(target), 130, 202)
    assert shown == pytest.approx(tuple((255 + value) / 2 for value in BLUE), abs=12)  # Half over white.


def test_printing_can_leave_images_and_stamps_out(tmp_path: Path) -> None:
    def approved(pdf: pikepdf.Pdf) -> pikepdf.Dictionary:
        return stamp(pdf, [300, 600, 420, 680], "0 G 0 0 120 80 re S", Name=pikepdf.Name.Approved)

    def attachment(_pdf: pikepdf.Pdf) -> pikepdf.Dictionary:
        return pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.FileAttachment, Rect=[0, 0, 20, 20])

    path = tmp_path / "stamps.pdf"
    with_stamps(path, lambda pdf: stamp(pdf, [100, 600, 220, 680]), approved, attachment)
    document = OpenDocument.open(path)
    for left_out, kept in (
        (AnnotationGroup.IMAGES_AND_STAMPS, ["/FileAttachment"]),
        (AnnotationGroup.OTHERS, ["/Stamp", "/Stamp"]),
    ):
        target = tmp_path / f"{left_out.value}.pdf"
        save(document.print_plan(target, frozenset({left_out})))
        with pikepdf.open(target) as pdf:
            annots = pdf.pages[0].obj.Annots
            assert sorted(str(annots[index].Subtype) for index in range(len(annots))) == kept


def painted(annotation: Annotation, page: ShownPage) -> cairo.ImageSurface:
    width, height = page.size
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, round(width), round(height))
    context = cairo.Context(surface)
    context.set_source_rgb(1, 1, 1)
    context.paint()
    paint_annotations(context, page, [annotation])
    surface.flush()
    return surface


def test_it_is_painted_stretched_to_its_rectangle_at_its_opacity(tmp_path: Path) -> None:
    (original,) = read(annotated(tmp_path / "image.pdf"))
    image_shown = managed_copy(original)
    image_shown = replace(image_shown, rectangle=(100, 100, 340, 260))  # Twice as big.
    surface = painted(image_shown, ShownPage(0, A4))
    assert near(pixel(surface, 130, 180), BLUE)
    assert near(pixel(surface, 310, 180), ORANGE)
    assert pixel(surface, 350, 180) == (255, 255, 255)
    faint = replace(image_shown, style=replace(image_shown.style, opacity=0.5))
    assert pixel(painted(faint, ShownPage(0, A4)), 130, 180) == pytest.approx(
        tuple((255 + value) / 2 for value in BLUE), abs=12
    )


@pytest.mark.parametrize(("rotation", "turn"), [(90, 0), (0, 90)])
def test_it_is_painted_as_poppler_draws_it_on_turned_pages(tmp_path: Path, rotation: int, turn: int) -> None:
    """Turned by its PDF (/Rotate) or by Penfold, it is painted where and as Poppler draws its page."""
    path = annotated(tmp_path / "image.pdf", rotation=rotation)
    (original,) = read(path)
    source_size = A4 if rotation == 0 else (A4[1], A4[0])  # Annotations are placed on the page as its PDF shows it.
    page = ShownPage(0, source_size, turn)
    surface = painted(managed_copy(original), page)
    left, right = (640, 130), (640, 190)  # Turned clockwise, its left is at the top.
    assert near(pixel(surface, *left), BLUE)
    assert near(pixel(surface, *right), ORANGE)
    if turn == 0:
        assert pixel(surface, *left) == pixel(render(path), *left)


def test_its_drawing_is_turned_as_its_page() -> None:
    with pikepdf.new() as pdf:
        pdf.add_blank_page()
        made = stamp(pdf, [0, 0, 120, 80])
        drawing = image_drawing(made, 270)
    assert drawing is not None
    with pikepdf.open(io.BytesIO(drawing)) as kept:
        assert int(kept.pages[0].Rotate) == 270
