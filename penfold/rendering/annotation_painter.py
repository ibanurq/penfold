"""Painting the annotations Penfold manages on the pages shown, with cairo, as they look once saved.

They are painted over the page.

The measurements are those of their drawing in the PDF (document/appearance.py). Poppler paints the PDF's own
annotations with the page; these are painted on top of it.
"""

import math
from collections.abc import Iterable

import cairo

from penfold.document.annotations import FILL_STRENGTH, Annotation, Kind
from penfold.document.appearance import (
    BUBBLE,
    BUBBLE_GRID,
    COMMENT_LINE_WIDTH,
    COMMENT_SIZE,
    arrowhead_wings,
    arrowheads,
    dashes,
    squiggle,
    stroke_curves,
    tint,
)
from penfold.document.geometry import Rectangle
from penfold.rendering.layout import ShownPage
from penfold.rendering.text_box import paint_text_box

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
        elif annotation.kind is Kind.TEXT_BOX:
            _paint_text_box(context, page, annotation)
        else:
            context.transform(turn_matrix(page))
            _paint_on_unturned_page(context, annotation)
        context.restore()


def highlight_tint(annotation: Annotation) -> tuple[float, float, float]:
    """What a highlight multiplies each colour of the page by: its colour, at its opacity."""
    red, green, blue = tint(annotation.color or BLACK, annotation.style.opacity)
    return red, green, blue


def highlight_areas(page: ShownPage, annotation: Annotation) -> list[Rectangle]:
    """The areas a highlight marks on the page as shown."""
    return [page.from_source(quad) for quad in annotation.quads]


def turn_matrix(page: ShownPage) -> cairo.Matrix:
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
    """Paint an annotation drawn with lines or areas, at its opacity, as each part is painted in the PDF."""
    context.set_source_rgba(*(annotation.color or BLACK), annotation.style.opacity)
    context.set_line_width(annotation.style.line_width)
    match annotation.kind:
        case Kind.HIGHLIGHT:
            _paint_highlight(context, annotation)
        case Kind.UNDERLINE | Kind.STRIKE_OUT:
            _paint_text_lines(context, annotation)
        case Kind.SQUIGGLY:
            _paint_squiggles(context, annotation)
        case Kind.RECTANGLE | Kind.CIRCLE:
            _paint_shape(context, annotation)
        case Kind.ARROW:
            _paint_arrow(context, annotation)
        case Kind.FREEHAND:
            _paint_freehand(context, annotation)


def _paint_highlight(context: cairo.Context, annotation: Annotation) -> None:
    """The marked areas, multiplied over the text, so that it stays as dark as it was."""
    context.set_operator(cairo.OPERATOR_MULTIPLY)
    for left, top, right, bottom in annotation.quads:
        context.rectangle(left, top, right - left, bottom - top)
    context.fill()


def _paint_text_lines(context: cairo.Context, annotation: Annotation) -> None:
    """A line under each marked area (lifted by half the line, inside it), or across its middle."""
    for left, top, right, bottom in annotation.quads:
        y = bottom - annotation.style.line_width / 2 if annotation.kind is Kind.UNDERLINE else (top + bottom) / 2
        context.move_to(left, y)
        context.line_to(right, y)
    context.stroke()


def _paint_squiggles(context: cairo.Context, annotation: Annotation) -> None:
    """A zigzag along the bottom of each marked area, inside it, with round corners."""
    context.set_line_join(cairo.LINE_JOIN_ROUND)
    for left, top, right, bottom in annotation.quads:
        first, *others = squiggle((left, bottom), (right, bottom), (left, top), annotation.style.line_width)
        context.move_to(*first)
        for point in others:
            context.line_to(*point)
    context.stroke()


def _paint_shape(context: cairo.Context, annotation: Annotation) -> None:
    """A line just inside the rectangle, or the ellipse it holds, with a soft fill inside if it has one.

    The paths start where the PDF's do, so that the dashes fall in the same places: the rectangle at its bottom left
    corner, going right; the ellipse at its top, clockwise.
    """
    context.set_dash(dashes(annotation.style))
    inset = annotation.style.line_width / 2
    left, top, right, bottom = annotation.rectangle
    left, top, right, bottom = left + inset, top + inset, right - inset, bottom - inset
    if annotation.kind is Kind.RECTANGLE:
        context.move_to(left, bottom)
        for corner in ((right, bottom), (right, top), (left, top)):
            context.line_to(*corner)
        context.close_path()
    elif right > left and bottom > top:
        context.save()
        context.translate((left + right) / 2, (top + bottom) / 2)
        context.scale((right - left) / 2, (bottom - top) / 2)
        context.arc(0, 0, 1, -math.pi / 2, 3 * math.pi / 2)
        context.restore()  # Before stroking, so that the line keeps its width all round.
    if annotation.style.filled:
        line = context.get_source()
        context.set_source_rgba(*tint(annotation.color or BLACK, FILL_STRENGTH), annotation.style.opacity)
        context.fill_preserve()
        context.set_source(line)
    context.stroke()


def _paint_arrow(context: cairo.Context, annotation: Annotation) -> None:
    """The line, then its open arrowheads, solid and with round ends."""
    if annotation.line is None:
        return
    start, end = annotation.line[:2], annotation.line[2:]
    context.set_dash(dashes(annotation.style))
    context.move_to(*start)
    context.line_to(*end)
    context.stroke()
    context.set_dash([])
    context.set_line_cap(cairo.LINE_CAP_ROUND)
    context.set_line_join(cairo.LINE_JOIN_ROUND)
    for tip, tail in arrowheads(start, end, annotation.style.line_ends):
        first, second = arrowhead_wings(tip, tail, annotation.style.line_width)
        context.move_to(*first)
        context.line_to(*tip)
        context.line_to(*second)
        context.stroke()


def _paint_freehand(context: cairo.Context, annotation: Annotation) -> None:
    """Each stroke as a smooth curve through its points, with round ends and corners (a lone point, a dot)."""
    context.set_dash(dashes(annotation.style))
    context.set_line_cap(cairo.LINE_CAP_ROUND)
    context.set_line_join(cairo.LINE_JOIN_ROUND)
    for stroke in annotation.strokes:
        first = stroke[0]
        context.move_to(*first)
        curves = stroke_curves(list(stroke))
        for curve in curves:
            context.curve_to(*(coordinate for point in curve for coordinate in point))
        if not curves:
            context.line_to(*first)
        context.stroke()


def _paint_text_box(context: cairo.Context, page: ShownPage, annotation: Annotation) -> None:
    """The text box, turned as its text reads: turned with the page since it was written (text_turn)."""
    left, top, right, bottom = page.from_source(annotation.rectangle)
    turn = (page.rotation - annotation.text_turn) % 360
    shown_width, shown_height = right - left, bottom - top
    size = (shown_height, shown_width) if turn % 180 else (shown_width, shown_height)
    context.translate((left + right) / 2, (top + bottom) / 2)
    context.rotate(math.radians(turn))
    context.translate(-size[0] / 2, -size[1] / 2)
    paint_text_box(context, annotation.text, size, annotation.color or BLACK, annotation.style)


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
