"""Painting the annotations Penfold manages on the pages shown, with cairo, as they look once saved.

They are painted over the page (03-arquitectura, 4.1).

The measurements are those of their drawing in the PDF (document/appearance.py). Poppler paints the PDF's own
annotations with the page; these are painted on top of it.
"""

import math
from collections.abc import Iterable

import cairo

from penfold.document.annotations import Annotation, Kind
from penfold.document.appearance import (
    ARROWHEAD_ANGLE,
    ARROWHEAD_LENGTH,
    BUBBLE,
    BUBBLE_GRID,
    COMMENT_LINE_WIDTH,
    COMMENT_SIZE,
    HIGHLIGHT_OPACITY,
    LINE_WIDTH,
)
from penfold.document.geometry import Rectangle
from penfold.rendering.layout import ShownPage

BLACK = (0.0, 0.0, 0.0)


def paint_annotations(
    context: cairo.Context, page: ShownPage, annotations: Iterable[Annotation], *, highlights: bool = True
) -> None:
    """Paint annotations of a page on a context measured in the page's points as shown, from its top left corner.

    Highlights multiply their colour with what is under them on the context. Where the page is not on the context
    (on the screen, GTK paints each node apart), leave them out and tint the page with highlight_tint instead.
    """
    for annotation in annotations:
        if annotation.kind is Kind.HIGHLIGHT and not highlights:
            continue
        context.save()
        if annotation.kind is Kind.COMMENT:
            _paint_comment(context, page, annotation)  # Upright, whatever the turn.
        else:
            context.transform(_turn(page))
            _paint_on_unturned_page(context, annotation)
        context.restore()


def highlight_tint(annotation: Annotation) -> tuple[float, float, float]:
    """What a highlight multiplies each colour of the page by: its colour, at its opacity."""
    red, green, blue = (1 - HIGHLIGHT_OPACITY * (1 - component) for component in annotation.color or BLACK)
    return red, green, blue


def highlight_areas(page: ShownPage, annotation: Annotation) -> list[Rectangle]:
    """The areas a highlight marks on the page as shown."""
    return [page.from_source(quad) for quad in annotation.quads]


def _turn(page: ShownPage) -> cairo.Matrix:
    """From the page unturned to the page as shown, turned clockwise by Penfold."""
    width, height = page.source_size
    match page.rotation:
        case 90:
            return cairo.Matrix(0, 1, -1, 0, height, 0)
        case 180:
            return cairo.Matrix(-1, 0, 0, -1, width, height)
        case 270:
            return cairo.Matrix(0, -1, 1, 0, 0, width)
        case _:
            return cairo.Matrix()


def _paint_on_unturned_page(context: cairo.Context, annotation: Annotation) -> None:
    context.set_source_rgb(*(annotation.color or BLACK))
    context.set_line_width(LINE_WIDTH)
    match annotation.kind:
        case Kind.HIGHLIGHT:
            _paint_highlight(context, annotation)
        case Kind.UNDERLINE | Kind.STRIKE_OUT:
            _paint_text_lines(context, annotation)
        case Kind.RECTANGLE | Kind.CIRCLE:
            _paint_shape(context, annotation)
        case Kind.ARROW:
            _paint_arrow(context, annotation)


def _paint_highlight(context: cairo.Context, annotation: Annotation) -> None:
    """The marked areas, multiplied over the text, so that it stays as dark as it was."""
    context.set_operator(cairo.OPERATOR_MULTIPLY)
    context.set_source_rgba(*(annotation.color or BLACK), HIGHLIGHT_OPACITY)
    for left, top, right, bottom in annotation.quads:
        context.rectangle(left, top, right - left, bottom - top)
    context.fill()


def _paint_text_lines(context: cairo.Context, annotation: Annotation) -> None:
    """A line under each marked area (lifted by half the line, inside it), or across its middle."""
    for left, top, right, bottom in annotation.quads:
        y = bottom - LINE_WIDTH / 2 if annotation.kind is Kind.UNDERLINE else (top + bottom) / 2
        context.move_to(left, y)
        context.line_to(right, y)
    context.stroke()


def _paint_shape(context: cairo.Context, annotation: Annotation) -> None:
    """A line just inside the rectangle, or the ellipse it holds."""
    inset = LINE_WIDTH / 2
    left, top, right, bottom = annotation.rectangle
    left, top, right, bottom = left + inset, top + inset, right - inset, bottom - inset
    if annotation.kind is Kind.RECTANGLE:
        context.rectangle(left, top, right - left, bottom - top)
    elif right > left and bottom > top:
        context.save()
        context.translate((left + right) / 2, (top + bottom) / 2)
        context.scale((right - left) / 2, (bottom - top) / 2)
        context.arc(0, 0, 1, 0, 2 * math.pi)
        context.restore()  # Before stroking, so that the line keeps its width all round.
    context.stroke()


def _paint_arrow(context: cairo.Context, annotation: Annotation) -> None:
    """The line, then an open arrowhead with round ends at its end."""
    if annotation.line is None:
        return
    start_x, start_y, end_x, end_y = annotation.line
    context.move_to(start_x, start_y)
    context.line_to(end_x, end_y)
    context.stroke()
    angle = math.atan2(end_y - start_y, end_x - start_x)
    context.set_line_cap(cairo.LINE_CAP_ROUND)
    context.set_line_join(cairo.LINE_JOIN_ROUND)
    for index, turn in enumerate((-ARROWHEAD_ANGLE, ARROWHEAD_ANGLE)):
        wing = end_x - ARROWHEAD_LENGTH * math.cos(angle + turn), end_y - ARROWHEAD_LENGTH * math.sin(angle + turn)
        if index:
            context.line_to(*wing)
        else:
            context.move_to(*wing)
            context.line_to(end_x, end_y)
    context.stroke()


def _paint_comment(context: cairo.Context, page: ShownPage, annotation: Annotation) -> None:
    """The speech bubble, filled with its colour and outlined in black.

    Upright, it keeps the corner that is its top left on the unturned page, as viewers do with NoRotate (12.5.3).
    """
    left, top, _right, _bottom = annotation.rectangle
    corner_x, corner_y, _x, _y = page.from_source((left, top, left, top))
    context.save()
    context.translate(corner_x, corner_y)
    context.scale(COMMENT_SIZE / BUBBLE_GRID, COMMENT_SIZE / BUBBLE_GRID)
    for operator, coordinates in BUBBLE:
        if operator == "m":
            context.move_to(*coordinates)
        elif operator == "l":
            context.line_to(*coordinates)
        else:
            context.curve_to(*coordinates)
    context.close_path()
    context.restore()  # The path stays; the outline is as wide in points as in the PDF.
    context.set_source_rgb(*(annotation.color or BLACK))
    context.fill_preserve()
    context.set_source_rgb(*BLACK)
    context.set_line_width(COMMENT_LINE_WIDTH)
    context.set_line_cap(cairo.LINE_CAP_ROUND)
    context.set_line_join(cairo.LINE_JOIN_ROUND)
    context.stroke()
