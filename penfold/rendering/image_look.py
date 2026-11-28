"""Painting the images and stamps Penfold manages: the drawing each keeps (document/images.py), stretched to fit.

Poppler draws the drawing once, as vectors (an image stays an image, scaled when painted), and it is painted at any
zoom, at the annotation's opacity, as viewers paint a stamp's drawing stretched to its /Rect.
"""

import functools

import cairo
from gi.repository import GLib, Poppler

from penfold.document.annotations import Annotation
from penfold.rendering.renderer import POPPLER_DRAWING

# How many drawings are kept drawn: those of the images and stamps on the pages being looked at.
CACHED_DRAWINGS = 32


def paint_kept_drawing(context: cairo.Context, annotation: Annotation) -> None:
    """Paint an image or a stamp on a context in points of its unturned page, filling its rectangle, at its opacity."""
    if not annotation.drawing:
        return
    drawing, (width, height) = _drawn(annotation.drawing)
    left, top, right, bottom = annotation.rectangle
    if width <= 0 or height <= 0 or right <= left or bottom <= top:
        return
    context.save()
    context.translate(left, top)
    context.scale((right - left) / width, (bottom - top) / height)
    context.set_source_surface(drawing)
    context.paint_with_alpha(annotation.style.opacity)
    context.restore()


@functools.lru_cache(maxsize=CACHED_DRAWINGS)
def _drawn(pdf: bytes) -> tuple[cairo.RecordingSurface, tuple[float, float]]:
    """What Poppler draws of the page of a kept drawing, turned as it is seen, and its size as seen, in points."""
    with POPPLER_DRAWING:
        page = Poppler.Document.new_from_bytes(GLib.Bytes.new(pdf), None).get_page(0)
        size = page.get_size()
        surface = cairo.RecordingSurface(cairo.CONTENT_COLOR_ALPHA, None)  # type: ignore[arg-type]  # None: unbounded
        page.render(cairo.Context(surface))
    return surface, size
