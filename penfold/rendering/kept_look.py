"""The drawing an annotation of a PDF has, as its program made it, to show it moved without drawing it again (D73).

Poppler draws the annotation alone: on a copy of its page with nothing else, neither the page's content nor its other
annotations. The drawing is recorded once, as vectors, and painted at any zoom wherever the annotation is moved.
"""

import io
from collections.abc import Callable

import cairo
import pikepdf
from gi.repository import GLib, Poppler

from penfold.document.annotations import Annotation
from penfold.document.sources import Spans, locate
from penfold.rendering.annotation_painter import turn_matrix
from penfold.rendering.layout import ShownPage
from penfold.rendering.renderer import POPPLER_DRAWING, SHOWN_ANNOTATIONS


class KeptLooks:
    """The drawings of the annotations of the source PDFs moved as they are, recorded once each."""

    def __init__(self, spans: Callable[[], Spans]) -> None:
        """Read the annotations' drawings from the source PDFs (their private copies) that a function gives."""
        self._spans = spans
        self._looks: dict[tuple[int, int | None], cairo.RecordingSurface | None] = {}

    def look(self, annotation: Annotation) -> cairo.RecordingSurface | None:
        """The drawing of an annotation of a PDF where it was read, in points of its unturned page (None: none)."""
        key = (annotation.page, annotation.origin)
        if key not in self._looks:
            alone = annotation_alone(self._spans(), annotation)
            with POPPLER_DRAWING:
                self._looks[key] = None if alone is None else record_look(alone)
        return self._looks[key]


def annotation_alone(spans: Spans, annotation: Annotation) -> bytes | None:
    """A one-page PDF with the annotation's page, empty but for the annotation; None if it is not in its page.

    The page keeps its size, crop box and turn, so that the annotation is where it is on its page.
    """
    if annotation.origin is None:
        return None
    source, index = locate(spans, annotation.page)
    span = spans[source]
    with pikepdf.open(span.path, password=span.password) as pdf, pikepdf.new() as alone:
        alone.pages.append(pdf.pages[index])
        page = alone.pages[0].obj
        annotations = page.get("/Annots")
        if not isinstance(annotations, pikepdf.Array) or annotation.origin >= len(annotations):
            return None
        page.Contents = alone.make_stream(b"")
        page.Annots = alone.make_indirect(pikepdf.Array([annotations[annotation.origin]]))
        written = io.BytesIO()
        alone.save(written)
    return written.getvalue()


def record_look(pdf: bytes) -> cairo.RecordingSurface:
    """Record what Poppler draws of the first page of a PDF, in its points (holding POPPLER_DRAWING: D45)."""
    page = Poppler.Document.new_from_bytes(GLib.Bytes.new(pdf), None).get_page(0)
    surface = cairo.RecordingSurface(cairo.CONTENT_COLOR_ALPHA, None)  # type: ignore[arg-type]  # None: unbounded
    page.render_full(cairo.Context(surface), False, SHOWN_ANNOTATIONS)  # type: ignore[attr-defined]  # not printing
    return surface


def paint_look(context: cairo.Context, page: ShownPage, annotation: Annotation, look: cairo.RecordingSurface) -> None:
    """Paint an annotation's own drawing where it is now (moved_by), on a context in its page's points as shown."""
    context.save()
    context.transform(turn_matrix(page))
    context.translate(*annotation.moved_by)
    context.set_source_surface(look)
    context.paint()
    context.restore()
