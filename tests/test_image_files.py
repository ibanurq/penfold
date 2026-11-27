"""Images from files: their drawing (each format, transparency, orientation), their size, and saved on a page."""

import io
import zlib
from pathlib import Path
from typing import Any

import cairo
import gi
import pikepdf
import pytest
from PIL import Image, ImageOps

from penfold.document.annotations import Annotation, Kind, new_annotation, read_annotations
from penfold.document.commands.annotations import AddAnnotations
from penfold.document.document import OpenDocument
from penfold.document.image_files import image_from_file
from penfold.document.saving import save
from penfold.errors import ImageOpenError
from penfold.rendering.annotation_painter import paint_annotations
from penfold.rendering.layout import ShownPage
from tests.sample_pdfs import make_pdf

gi.require_version("Poppler", "0.18")
from gi.repository import GLib, Poppler  # noqa: E402

RED, GREEN, BLUE, YELLOW = (230, 30, 30), (30, 200, 60), (40, 60, 230), (240, 220, 40)
# The colours of the quarters of the picture, as it is seen: top left, top right, bottom left, bottom right.
QUARTERS = (RED, GREEN, BLUE, YELLOW)
WIDTH, HEIGHT = 64, 48


def picture(mode: str = "RGB") -> Image.Image:
    """A picture 64 by 48, in four coloured quarters."""
    image = Image.new("RGB", (WIDTH, HEIGHT))
    for index, color in enumerate(QUARTERS):
        left, top = (index % 2) * WIDTH // 2, (index // 2) * HEIGHT // 2
        image.paste(color, (left, top, left + WIDTH // 2, top + HEIGHT // 2))
    return image.convert(mode)


def written(tmp_path: Path, image: Image.Image, name: str, **options: Any) -> Path:
    path = tmp_path / name
    image.save(path, **options)
    return path


def the_picture(drawing: bytes) -> tuple[list[str], str, Image.Image]:
    """The picture in a drawing: its filters, its colour space and its pixels."""
    with pikepdf.open(io.BytesIO(drawing)) as pdf:
        stream = pdf.pages[0].Resources.XObject["/Image"]
        assert isinstance(stream, pikepdf.Stream)
        found = pikepdf.PdfImage(stream)
        return [str(item) for item in found.filters], str(found.colorspace), found.as_pil_image()


def drawn(drawing: bytes) -> cairo.ImageSurface:
    """The page of a drawing as Poppler draws it (turned as it says), four pixels a point, on white."""
    page = Poppler.Document.new_from_bytes(GLib.Bytes.new(drawing), None).get_page(0)
    width, height = page.get_size()
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, round(width * 4), round(height * 4))
    context = cairo.Context(surface)
    context.set_source_rgb(1, 1, 1)
    context.paint()
    context.scale(4, 4)
    page.render(context)
    surface.flush()
    return surface


def color_at(surface: cairo.ImageSurface, x: float, y: float) -> tuple[int, int, int]:
    """The colour at a share of the width and the height of a surface."""
    data, stride = surface.get_data(), surface.get_stride()
    offset = int(y * surface.get_height()) * stride + int(x * surface.get_width()) * 4
    blue, green, red = data[offset : offset + 3]
    return red, green, blue


def quarters(surface: cairo.ImageSurface) -> list[tuple[int, int, int]]:
    """The colours in the middle of the four quarters: top left, top right, bottom left, bottom right."""
    return [color_at(surface, x, y) for y in (0.25, 0.75) for x in (0.25, 0.75)]


# How far a colour drawn may be from the one expected, in each of red, green and blue (JPEG and scaling blur them).
TOLERANCE = 24


def close(found: list[tuple[int, int, int]], expected: tuple[tuple[int, int, int], ...] = QUARTERS) -> bool:
    pairs = [(a, b) for color, wanted in zip(found, expected, strict=True) for a, b in zip(color, wanted, strict=True)]
    return all(abs(a - b) <= TOLERANCE for a, b in pairs)


def test_a_jpeg_goes_in_as_it_is(tmp_path: Path) -> None:
    path = written(tmp_path, picture(), "photo.jpg", quality=95)
    drawing, _size = image_from_file(path)
    with pikepdf.open(io.BytesIO(drawing)) as pdf:
        stream = pdf.pages[0].Resources.XObject["/Image"]
        assert (str(stream.Filter), str(stream.ColorSpace)) == ("/DCTDecode", "/DeviceRGB")
        assert stream.read_raw_bytes() == path.read_bytes()  # Nothing lost, nothing grown.
    assert close(quarters(drawn(drawing)))


@pytest.mark.parametrize(
    ("name", "options"),
    [
        ("image.png", {}),
        ("image.webp", {"lossless": True}),
        ("image.gif", {}),
        ("image.bmp", {}),
        ("image.tif", {}),
        ("image.tiff", {"compression": "tiff_lzw"}),
    ],
)
def test_the_other_formats_go_in_without_loss(tmp_path: Path, name: str, options: dict[str, object]) -> None:
    path = written(tmp_path, picture(), name, **options)
    drawing, _size = image_from_file(path)
    filters, _space, inserted = the_picture(drawing)
    assert filters == ["/FlateDecode"]
    with Image.open(path) as original:
        assert inserted.convert("RGB").tobytes() == original.convert("RGB").tobytes()
    assert close(quarters(drawn(drawing)))


def test_grey_stays_grey_and_16_bits_become_8(tmp_path: Path) -> None:
    grey = written(tmp_path, picture("L"), "grey.png")
    assert the_picture(image_from_file(grey)[0])[1] == "/DeviceGray"
    row = [0x8080] * (WIDTH // 2) + [0xFFFF] * (WIDTH // 2)  # Half grey, half white, 16 bits a dot.
    deep = Image.frombytes("I;16", (WIDTH, HEIGHT), b"".join(value.to_bytes(2, "little") for value in row * HEIGHT))
    inserted = the_picture(image_from_file(written(tmp_path, deep, "deep.png"))[0])[2]
    assert (inserted.mode, inserted.getpixel((0, 0)), inserted.getpixel((WIDTH - 1, 0))) == ("L", 128, 255)


def test_transparency_goes_in_as_a_mask(tmp_path: Path) -> None:
    clear = picture("RGBA")
    clear.putalpha(Image.new("L", (WIDTH, HEIGHT), 255))
    clear.paste((0, 0, 0, 0), (0, 0, WIDTH // 2, HEIGHT // 2))  # Its top left quarter, see-through.
    drawing, _size = image_from_file(written(tmp_path, clear, "logo.png"))
    with pikepdf.open(io.BytesIO(drawing)) as pdf:
        smask = pdf.pages[0].Resources.XObject["/Image"].SMask
        assert isinstance(smask, pikepdf.Stream)
        mask = pikepdf.PdfImage(smask).as_pil_image()
        assert (mask.getpixel((0, 0)), mask.getpixel((WIDTH - 1, HEIGHT - 1))) == (0, 255)
    assert quarters(drawn(drawing))[0] == (255, 255, 255)  # The page shows through.
    opaque = written(tmp_path, picture("RGBA"), "opaque.png")
    with pikepdf.open(io.BytesIO(image_from_file(opaque)[0])) as pdf:
        assert "/SMask" not in pdf.pages[0].Resources.XObject["/Image"]  # Said to be transparent, but nowhere is.


def test_a_gif_with_a_transparent_colour_and_only_its_first_picture(tmp_path: Path) -> None:
    first, second = picture("P"), Image.new("P", (WIDTH, HEIGHT))
    path = tmp_path / "moving.gif"
    first.save(path, save_all=True, append_images=[second], transparency=0, duration=100)
    drawing, _size = image_from_file(path)
    shown = quarters(drawn(drawing))
    assert sum(color == (255, 255, 255) for color in shown) <= 1  # The first picture, not the black second one.


def test_a_cmyk_jpeg_keeps_its_colours(tmp_path: Path) -> None:
    path = written(tmp_path, picture("CMYK"), "print.jpg", quality=95)
    drawing, _size = image_from_file(path)
    assert the_picture(drawing)[1] == "/DeviceCMYK"
    # Not inverted: each quarter is still of its colour (CMYK to the screen's colours shifts them a little).
    strongest = [max(range(3), key=color.__getitem__) for color in quarters(drawn(drawing))]
    assert strongest == [0, 1, 2, 0]  # Red, green, blue; yellow, as much red as green.


@pytest.mark.parametrize(
    ("dpi", "size"),
    [(None, (48, 36)), ((144, 144), (32, 24)), ((72, 36), (64, 96)), ((1, 1), (48, 36))],
)
def test_its_size_is_its_printed_size_or_as_on_a_screen(
    tmp_path: Path, dpi: tuple[int, int] | None, size: tuple[float, float]
) -> None:
    path = written(tmp_path, picture(), "sized.png", **({"dpi": dpi} if dpi else {}))
    assert image_from_file(path)[1] == pytest.approx(size, abs=0.1)


@pytest.mark.parametrize("orientation", range(1, 9))
@pytest.mark.parametrize("name", ["photo.jpg", "photo.tif"])
def test_a_photo_is_seen_as_its_orientation_says(tmp_path: Path, orientation: int, name: str) -> None:
    """A phone stores a photo as its camera took it, and says how to turn it (EXIF): it goes in as it is seen."""
    stored = picture()
    exif = stored.getexif()
    exif[0x0112] = orientation
    options = {"quality": 95} if name.endswith("jpg") else {}
    path = written(tmp_path, stored, name, exif=exif, dpi=(96, 96), **options)
    drawing, size = image_from_file(path)
    seen = _seen(stored, orientation)
    assert size == pytest.approx((seen.width * 0.75, seen.height * 0.75))
    expected = tuple(
        seen.getpixel((int(x * seen.width), int(y * seen.height))) for y in (0.25, 0.75) for x in (0.25, 0.75)
    )
    assert close(quarters(drawn(drawing)), expected)  # type: ignore[arg-type]


def _seen(stored: Image.Image, orientation: int) -> Image.Image:
    """The picture as its orientation says it is seen, turned by Pillow."""
    copy = stored.copy()
    copy.getexif()[0x0112] = orientation
    return ImageOps.exif_transpose(copy) or copy


def image(drawing: bytes, rectangle: tuple[float, float, float, float]) -> Annotation:
    return new_annotation(Kind.IMAGE, 0, rectangle, (0.0, 0.0, 0.0), "Iban", drawing=drawing)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("turn", [0, 90, 270])
def test_it_is_upright_on_the_page_as_it_is_seen(tmp_path: Path, rotation: int, turn: int) -> None:
    """Painted where it goes on a page turned by its PDF and by Penfold, it is upright as the page is seen."""
    drawing, (width, height) = image_from_file(written(tmp_path, picture(), "image.png"), rotation, turn)
    source_size = (600.0, 800.0)  # The page as its PDF shows it: Penfold's turn comes on top.
    page = ShownPage(0, source_size, turn)
    left, top = page.to_source(100, 100)
    right, bottom = page.to_source(100 + width * 4, 100 + height * 4)  # Four times as big, as it is seen.
    shown_size = page.size
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, round(shown_size[0]), round(shown_size[1]))
    context = cairo.Context(surface)
    context.set_source_rgb(1, 1, 1)
    context.paint()
    rectangle = (min(left, right), min(top, bottom), max(left, right), max(top, bottom))
    paint_annotations(context, page, [image(drawing, rectangle)])
    surface.flush()
    found = [
        color_at(surface, (100 + width * 4 * x) / shown_size[0], (100 + height * 4 * y) / shown_size[1])
        for y in (0.25, 0.75)
        for x in (0.25, 0.75)
    ]
    assert close(found)


def test_a_new_image_is_saved_and_read_back(tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "plain.pdf", page_count=1)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.pages[0].obj.Rotate = 90
        pdf.save(path)
    drawing, (width, height) = image_from_file(written(tmp_path, picture(), "image.png"), rotation=90)
    document = OpenDocument.open(path)
    made = image(drawing, (100, 100, 100 + width * 4, 100 + height * 4))
    assert (made.color, made.managed, made.group.value) == (None, True, "images-and-stamps")
    document.execute(AddAnnotations(document, [made]))
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    with pikepdf.open(target) as pdf:
        saved = pdf.pages[0].obj.Annots[0]
        assert (str(saved.Subtype), str(saved.IT), "/C" in saved) == ("/Stamp", "/StampImage", False)
        (again,) = read_annotations(pdf)
    assert again.kind is Kind.IMAGE
    assert again.rectangle == pytest.approx(made.rectangle)
    page = Poppler.Document.new_from_file(target.as_uri(), None).get_page(0)
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, 842, 595)  # Turned by its PDF: as wide as A4 is tall.
    context = cairo.Context(surface)
    context.set_source_rgb(1, 1, 1)
    context.paint()
    page.render(context)
    surface.flush()
    found = [
        color_at(surface, (100 + width * 4 * x) / 842, (100 + height * 4 * y) / 595)
        for y in (0.25, 0.75)
        for x in (0.25, 0.75)
    ]
    assert close(found)  # Upright, as Penfold showed it, in another viewer.


@pytest.mark.parametrize("content", [b"not an image", b"", zlib.compress(b"nothing")])
def test_what_is_not_an_image_says_so(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "picture.png"
    path.write_bytes(content)
    with pytest.raises(ImageOpenError):
        image_from_file(path)


def test_a_missing_file_or_another_format_says_so(tmp_path: Path) -> None:
    with pytest.raises(ImageOpenError):
        image_from_file(tmp_path / "missing.png")
    with pytest.raises(ImageOpenError):
        image_from_file(written(tmp_path, picture(), "icon.ico"))
