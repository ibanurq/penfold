"""The drawing of Penfold's stamps, as a rubber stamp leaves it: a double rounded border and a word, in its colour.

The border is thick outside and thin inside, with a faint background of the colour that lets what is under it show; the
word, in capitals, is in Liberation Sans Bold, spaced out a little. All stamps are as tall; each is as wide as its word
needs. The drawing is made with Pango and cairo, as a one-page PDF with the letters used inside, and kept as the drawing
of the stamp (document/images.py), turned for its page.
"""

import io
import math

import cairo
from gi.repository import Pango, PangoCairo

from penfold.document.geometry import Size
from penfold.document.images import upright_drawing

FONT = "Liberation Sans Bold"
# Measures in points: the letters, the height of every stamp, the space at each side of the word, the borders (outside,
# the space between them, inside), the roundness of the outer corners, and how much the letters are spaced out.
FONT_SIZE = 14.0
HEIGHT = 28.0
SIDE_PADDING = 11.0
OUTER_BORDER = 1.6
BORDER_GAP = 1.4
INNER_BORDER = 0.5
CORNER_RADIUS = 4.0
LETTER_SPACING = 1.4
# How much of the colour the background has; what is under it shows through.
BACKGROUND_OPACITY = 0.14

Color = tuple[float, float, float]


def stamp_size(word: str) -> Size:
    """How big a stamp with a word is, in points: as tall as all, as wide as its word needs."""
    ink = _ink(_layout(_measuring_context(), word))
    return ink.width / Pango.SCALE + 2 * (SIDE_PADDING + OUTER_BORDER), HEIGHT


def stamp_drawing(word: str, color: Color, rotation: int = 0, turn: int = 0) -> tuple[bytes, Size]:
    """The drawing of a stamp with a word in a colour, kept for a page (document/images.py), and its size as seen.

    The page is turned by its PDF by rotation (/Rotate) and by Penfold by turn: the stamp is upright as it is seen.
    """
    size = stamp_size(word)
    output = io.BytesIO()
    surface = cairo.PDFSurface(output, *size)
    paint_stamp(cairo.Context(surface), word, color, size)
    surface.finish()
    return upright_drawing(output.getvalue(), rotation, turn), size


def paint_stamp(context: cairo.Context, word: str, color: Color, size: Size) -> None:
    """Paint a stamp from the context's origin, measured in points: its background, its borders and its word."""
    width, height = size
    context.save()
    half = OUTER_BORDER / 2
    _rounded_rectangle(context, size, half, CORNER_RADIUS)
    context.set_source_rgba(*color, BACKGROUND_OPACITY)
    context.fill_preserve()
    context.set_source_rgb(*color)
    context.set_line_width(OUTER_BORDER)
    context.stroke()
    inset = OUTER_BORDER + BORDER_GAP + INNER_BORDER / 2
    radius = max(0.0, CORNER_RADIUS - (inset - half))
    _rounded_rectangle(context, size, inset, radius)
    context.set_line_width(INNER_BORDER)
    context.stroke()
    layout = _layout(context, word)
    ink = _ink(layout)
    # The word in the middle, by what its letters cover (capitals have no descenders).
    context.move_to(
        (width - ink.width / Pango.SCALE) / 2 - ink.x / Pango.SCALE,
        (height - ink.height / Pango.SCALE) / 2 - ink.y / Pango.SCALE,
    )
    PangoCairo.show_layout(context, layout)
    context.restore()


def _rounded_rectangle(context: cairo.Context, size: Size, inset: float, radius: float) -> None:
    """A rectangle with round corners as the current path, inset from the edges of a stamp of a size."""
    x = y = inset
    width, height = size[0] - 2 * inset, size[1] - 2 * inset
    context.new_sub_path()
    quarter = math.pi / 2
    context.arc(x + width - radius, y + radius, radius, -quarter, 0)
    context.arc(x + width - radius, y + height - radius, radius, 0, quarter)
    context.arc(x + radius, y + height - radius, radius, quarter, 2 * quarter)
    context.arc(x + radius, y + radius, radius, 2 * quarter, 3 * quarter)
    context.close_path()


def _measuring_context() -> cairo.Context:
    return cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1))


def _layout(context: cairo.Context, word: str) -> Pango.Layout:
    """The word in capitals, laid out on one line, measured as in the PDF at any zoom."""
    options = cairo.FontOptions()
    options.set_hint_metrics(cairo.HINT_METRICS_OFF)
    options.set_hint_style(cairo.HINT_STYLE_NONE)
    layout = PangoCairo.create_layout(context)
    PangoCairo.context_set_font_options(layout.get_context(), options)
    layout.get_context().set_round_glyph_positions(False)
    layout.context_changed()
    font = Pango.FontDescription.from_string(FONT)
    font.set_absolute_size(FONT_SIZE * Pango.SCALE)
    layout.set_font_description(font)
    attributes = Pango.AttrList()
    attributes.insert(Pango.attr_letter_spacing_new(round(LETTER_SPACING * Pango.SCALE)))
    layout.set_attributes(attributes)
    layout.set_text(word.upper(), -1)
    return layout


def _ink(layout: Pango.Layout) -> Pango.Rectangle:
    """What the letters of a layout cover."""
    ink, _logical = layout.get_extents()
    return ink
