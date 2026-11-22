"""The drawing of a text box (H3, D69): a faint background and a border in its colour, and black Liberation Sans.

New ones have both and 11-point letters; its Format panel can take away the background or the border and change the
size of the letters (D72).

The same drawing is shown on the screen and saved in the PDF: Pango lays out the text in both, with the same font and
the same measures, so the lines break in the same places. Characters Liberation Sans lacks are drawn with other fonts
of the system (fallback); in the PDF, every font used goes inside it, only with the characters used.
"""

import io
from dataclasses import replace

import cairo
from gi.repository import Pango, PangoCairo

from penfold.document.annotations import TEXT_BOX_FONT_SIZE, Annotation, Style
from penfold.document.appearance import TEXT_BOX_BACKGROUND, tint
from penfold.document.geometry import Size
from penfold.rendering.layout import ShownPage

FONT_FAMILY = "Liberation Sans"
FONT_SIZE = TEXT_BOX_FONT_SIZE
# Measures in points: inner space, border, and how much of the colour the background has (as in 0.6).
PADDING = 6.0
BORDER = 1.0
BACKGROUND_STRENGTH = TEXT_BOX_BACKGROUND
BLACK = (0.0, 0.0, 0.0)
# The width a text box gets with a click instead of a drag, and the narrowest one, in points.
DEFAULT_WIDTH = 200.0
NARROWEST = 2 * (PADDING + BORDER) + FONT_SIZE

Color = tuple[float, float, float]


def background(color: Color) -> Color:
    """The faint colour of the background: the colour at 14 % over white."""
    return tint(color, BACKGROUND_STRENGTH)


def text_height(text: str, width: float, font_size: float = FONT_SIZE) -> float:
    """The height of a text box of this width with this text, in points: it grows with the text (H3)."""
    layout = _layout(cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)), text, width, font_size)
    _ink, logical = layout.get_extents()
    return 2 * (PADDING + BORDER) + logical.height / Pango.SCALE


def paint_text_box(
    context: cairo.Context, text: str, size: tuple[float, float], color: Color, style: Style | None = None
) -> None:
    """Paint a text box from the context's origin, measured in points: background, border and text.

    The border keeps its place without a border, so that taking it away does not move the text.
    """
    style = style or Style()
    width, height = size
    context.save()
    if style.background:
        context.set_source_rgb(*background(color))
        context.rectangle(0, 0, width, height)
        context.fill()
    if style.border:
        context.set_source_rgb(*color)
        context.set_line_width(BORDER)
        context.rectangle(BORDER / 2, BORDER / 2, width - BORDER, height - BORDER)
        context.stroke()
    context.set_source_rgb(*BLACK)
    context.move_to(BORDER + PADDING, BORDER + PADDING)
    PangoCairo.show_layout(context, _layout(context, text, width, style.font_size))
    context.restore()


def text_box_pdf(text: str, size: tuple[float, float], color: Color, style: Style | None = None) -> bytes:
    """A one-page PDF of the size of a text box with its drawing, the fonts it uses inside: its saved appearance."""
    output = io.BytesIO()
    surface = cairo.PDFSurface(output, *size)
    paint_text_box(cairo.Context(surface), text, size, color, style)
    surface.finish()
    return output.getvalue()


def redrawn(annotation: Annotation) -> Annotation:
    """A text box with its saved drawing made again, after its text, colour or format changed.

    It is drawn upright in its own box: across the page if its text reads turned a quarter (text_turn).
    """
    left, top, right, bottom = annotation.rectangle
    width, height = right - left, bottom - top
    size = (height, width) if annotation.text_turn % 180 else (width, height)
    return replace(annotation, drawing=text_box_pdf(annotation.text, size, annotation.color or BLACK, annotation.style))


def written_frame(annotation: Annotation, source_size: Size) -> tuple[tuple[float, float], float]:
    """Where a text box's text starts and how wide it is, on its page turned as when it was written (text_turn).

    On that page the box is upright: its top left corner, in points, and its width.
    """
    left, top, right, _bottom = ShownPage(annotation.page, source_size, annotation.text_turn).from_source(
        annotation.rectangle
    )
    return (left, top), right - left


def with_text(annotation: Annotation, text: str, source_size: Size) -> Annotation:
    """A text box with another text: as wide, from the same corner, as tall as the text needs (draw it with redrawn).

    It grows or shrinks downwards as its text reads, whatever the turn of the page now.
    """
    (left, top), width = written_frame(annotation, source_size)
    height = text_height(text, width, annotation.style.font_size)
    written = ShownPage(annotation.page, source_size, annotation.text_turn)
    corners = [written.to_source(left, top), written.to_source(left + width, top + height)]
    rectangle = (
        min(x for x, _y in corners),
        min(y for _x, y in corners),
        max(x for x, _y in corners),
        max(y for _x, y in corners),
    )
    return replace(annotation, text=text, rectangle=rectangle)


def _layout(context: cairo.Context, text: str, width: float, font_size: float) -> Pango.Layout:
    """The text laid out for a box of this width, split into lines by words (or within a word too long)."""
    options = cairo.FontOptions()
    # Measures that do not depend on the screen, so that the lines break as in the PDF at any zoom.
    options.set_hint_metrics(cairo.HINT_METRICS_OFF)
    options.set_hint_style(cairo.HINT_STYLE_NONE)
    layout = PangoCairo.create_layout(context)
    PangoCairo.context_set_font_options(layout.get_context(), options)
    # Glyphs placed to the fraction of a point, not rounded to whole units (points, in the PDF).
    layout.get_context().set_round_glyph_positions(False)
    layout.context_changed()
    font = Pango.FontDescription.from_string(FONT_FAMILY)
    font.set_absolute_size(font_size * Pango.SCALE)
    layout.set_font_description(font)
    layout.set_width(round(max(1.0, width - 2 * (PADDING + BORDER)) * Pango.SCALE))
    layout.set_wrap(Pango.WrapMode.WORD_CHAR)
    layout.set_text(text, -1)
    return layout
