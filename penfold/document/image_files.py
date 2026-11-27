"""Images from files, to put on a page: their drawing, as images.py keeps it, and the size they are printed at.

Pillow reads them (it comes with pikepdf). JPEG, PNG, WebP, GIF (its first picture), BMP and TIFF are read. A JPEG goes
into the PDF as it is, without losing anything nor growing; the others go in without loss, compressed as PNG compresses
them (PDF's Flate with PNG predictors), with their transparency as a mask (/SMask). An image is seen as its EXIF
orientation says (a photo taken with the phone turned), and upright on the page as it is seen, however the page is
turned.

Its size is the one it says it is printed at (its resolution, in dots per inch) or, if it says none, as big as on a
screen at 96 dots per inch.
"""

import io
import math
import struct
import zlib
from pathlib import Path

import pikepdf
from PIL import Image, ImageOps, UnidentifiedImageError

from penfold.errors import ImageOpenError

# The formats that can be inserted, as Pillow names them.
FORMATS = frozenset({"JPEG", "PNG", "WEBP", "GIF", "BMP", "TIFF"})
# The resolution of an image that says none, in dots per inch; less than the least is taken as none.
SCREEN_RESOLUTION = 96.0
LEAST_RESOLUTION = 10.0
POINTS_PER_INCH = 72.0
# The EXIF tag of the orientation, and how each orientation turns or mirrors the picture as stored, as a matrix of the
# square the picture fills (its top at 1), so that it is seen upright.
ORIENTATION_TAG = 0x0112
ORIENTATIONS = {
    1: (1, 0, 0, 1, 0, 0),
    2: (-1, 0, 0, 1, 1, 0),  # Mirrored across.
    3: (-1, 0, 0, -1, 1, 1),  # Upside down.
    4: (1, 0, 0, -1, 0, 1),  # Mirrored upside down.
    5: (0, -1, -1, 0, 1, 1),  # Mirrored along its diagonal.
    6: (0, -1, 1, 0, 0, 1),  # Turned a quarter clockwise to be seen.
    7: (0, 1, 1, 0, 0, 0),  # Mirrored along its other diagonal.
    8: (0, 1, -1, 0, 1, 0),  # Turned a quarter anticlockwise to be seen.
}
# Orientations that swap the picture's width and height.
ACROSS = frozenset({5, 6, 7, 8})
# PNG: its signature, and the chunks of compressed pixels, already filtered as PDF's PNG predictors expect.
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_PIXELS = b"IDAT"
PNG_PREDICTORS = 15
COLOR_SPACES = {"L": pikepdf.Name.DeviceGray, "RGB": pikepdf.Name.DeviceRGB, "CMYK": pikepdf.Name.DeviceCMYK}

Matrix = tuple[float, float, float, float, float, float]


def image_from_file(path: Path, rotation: int = 0, turn: int = 0) -> tuple[bytes, tuple[float, float]]:
    """The drawing of the image of a file, and its size as it is seen, in points.

    It is made for a page whose PDF turns it by rotation (/Rotate) and that Penfold turns by turn: the drawing is turned
    as its page (images.py), and the image in it is upright as the page is seen.

    Raises:
        ImageOpenError: the file is missing or unreadable, or not an image of one of the formats.
    """
    try:
        with Image.open(path) as image:
            if image.format not in FORMATS:
                message = f"{path} is not an image of a format Penfold inserts"
                raise ImageOpenError(message)
            image.load()
            return _drawing(path, image, rotation, turn)
    except (OSError, UnidentifiedImageError, ValueError, Image.DecompressionBombError) as error:
        message = f"{path} could not be read as an image"
        raise ImageOpenError(message) from error


def _drawing(path: Path, image: Image.Image, rotation: int, turn: int) -> tuple[bytes, tuple[float, float]]:
    orientation = image.getexif().get(ORIENTATION_TAG, 1)
    orientation = orientation if orientation in ORIENTATIONS else 1
    resolution = _resolution(image)
    with pikepdf.new() as pdf:
        if image.format == "JPEG" and image.mode in COLOR_SPACES:
            picture = _jpeg(pdf, path.read_bytes(), image)
        else:
            image = ImageOps.exif_transpose(image) or image
            orientation = 1  # Turned as it is seen already.
            picture = _lossless(pdf, image)
        width, height = image.size
        x_resolution, y_resolution = resolution
        if orientation in ACROSS:
            width, height, x_resolution, y_resolution = height, width, y_resolution, x_resolution
        size = (width / x_resolution * POINTS_PER_INCH, height / y_resolution * POINTS_PER_INCH)
        _add_page(pdf, picture, size, orientation, (rotation, turn))
        written = io.BytesIO()
        pdf.save(written)
    return written.getvalue(), size


def _resolution(image: Image.Image) -> tuple[float, float]:
    """The image's resolution across and down, in dots per inch; the screen's if it says none (or one too small)."""
    found = image.info.get("dpi")
    try:
        across, down = (float(value) for value in found) if found else (0.0, 0.0)
    except (TypeError, ValueError):
        across, down = 0.0, 0.0
    if not (math.isfinite(across) and math.isfinite(down)) or min(across, down) < LEAST_RESOLUTION:
        return SCREEN_RESOLUTION, SCREEN_RESOLUTION
    return across, down


def _jpeg(pdf: pikepdf.Pdf, data: bytes, image: Image.Image) -> pikepdf.Stream:
    """A JPEG as it is (DCTDecode); a CMYK one from Adobe programs has its colours inverted, as they write them."""
    picture = _picture(pdf, data, image.size, image.mode)
    picture.Filter = pikepdf.Name.DCTDecode
    if image.mode == "CMYK" and "adobe" in image.info:
        picture.Decode = pikepdf.Array([1, 0] * 4)
    return picture


def _lossless(pdf: pikepdf.Pdf, image: Image.Image) -> pikepdf.Stream:
    """An image without loss, in grey or in colour, with its transparency as a mask if it has any."""
    alpha = None
    if image.has_transparency_data:
        rgba = image.convert("RGBA")
        alpha = rgba.getchannel("A")
        if alpha.getextrema() == (255, 255):
            alpha = None  # Said to be transparent, but nowhere is.
        image = rgba.convert("RGB")
    elif image.mode.startswith(("I", "F")):
        image = image.convert("I").point(lambda value: value / 257).convert("L")  # 16 bits a dot, to 8.
    elif image.mode in {"1", "L"}:
        image = image.convert("L")
    else:
        image = image.convert("RGB")
    picture = _flate(pdf, image)
    if alpha is not None:
        picture.SMask = _flate(pdf, alpha)
    return picture


def _flate(pdf: pikepdf.Pdf, image: Image.Image) -> pikepdf.Stream:
    """An image in grey or colour compressed as PNG compresses it: Flate, each row filtered (PNG predictors)."""
    encoded = io.BytesIO()
    image.save(encoded, "PNG")
    picture = _picture(pdf, _png_pixels(encoded.getvalue()), image.size, image.mode)
    picture.Filter = pikepdf.Name.FlateDecode
    picture.DecodeParms = pikepdf.Dictionary(
        Predictor=PNG_PREDICTORS, Colors=len(image.getbands()), BitsPerComponent=8, Columns=image.size[0]
    )
    return picture


def _png_pixels(png: bytes) -> bytes:
    """The compressed pixels of a PNG (its IDAT chunks joined)."""
    if not png.startswith(PNG_SIGNATURE):
        message = "not a PNG"
        raise ValueError(message)
    pixels, offset = [], len(PNG_SIGNATURE)
    while offset + 8 <= len(png):
        length, kind = struct.unpack(">I4s", png[offset : offset + 8])
        if kind == PNG_PIXELS:
            pixels.append(png[offset + 8 : offset + 8 + length])
        offset += 12 + length  # Length, kind, data and checksum.
    joined = b"".join(pixels)
    zlib.decompressobj().decompress(joined, 1)  # Raises if it is not compressed data.
    return joined


def _picture(pdf: pikepdf.Pdf, data: bytes, size: tuple[int, int], mode: str) -> pikepdf.Stream:
    picture = pikepdf.Stream(pdf, data)
    picture.Type, picture.Subtype = pikepdf.Name.XObject, pikepdf.Name.Image
    picture.Width, picture.Height = size
    picture.ColorSpace = COLOR_SPACES[mode]
    picture.BitsPerComponent = 8
    return picture


def _add_page(
    pdf: pikepdf.Pdf, picture: pikepdf.Stream, size: tuple[float, float], orientation: int, turns: tuple[int, int]
) -> None:
    """The page of the drawing: the picture filling it, upright as the page is seen (turned by the PDF and by Penfold).

    The page is turned as the PDF turns its page (/Rotate).
    """
    rotation, turn = turns
    width, height = size
    seen = (rotation + turn) % 360
    unturned = (height, width) if seen % 180 else (width, height)
    pdf.add_blank_page(page_size=unturned)
    page = pdf.pages[0].obj
    page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary({"/Image": picture}))
    matrices = [_upright(seen, width, height), (width, 0, 0, height, 0, 0), ORIENTATIONS[orientation]]
    content = " ".join(f"{_numbers(matrix)} cm" for matrix in matrices)
    page.Contents = pdf.make_stream(f"q {content} /Image Do Q".encode())
    if rotation % 360:
        page.Rotate = rotation % 360


def _upright(seen: int, width: float, height: float) -> Matrix:
    """From the page as seen, turned clockwise by seen degrees, to the page unturned (both from the bottom left)."""
    return {
        0: (1, 0, 0, 1, 0, 0),
        90: (0, 1, -1, 0, height, 0),
        180: (-1, 0, 0, -1, width, height),
        270: (0, -1, 1, 0, 0, width),
    }[seen]


def _numbers(values: tuple[float, ...]) -> str:
    return " ".join(f"{round(value, 3):g}" for value in values)
