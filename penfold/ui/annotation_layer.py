"""The annotations Penfold paints over a drawn page: on the pages of the document and on their thumbnails.

Poppler draws a page with the annotations of its PDF that are left as they are. Penfold paints the others on top: those
it manages (made or changed in Penfold) and those of the PDF moved as they are, with the drawing their program made
(D73). The page and its thumbnail paint the same ones the same way (07-fase-12, 12).
"""

from collections.abc import Callable, Iterable

from gi.repository import Graphene, Gtk

from penfold.document.annotations import Annotation, Kind
from penfold.rendering.annotation_painter import highlight_areas, highlight_tint, paint_annotations
from penfold.rendering.kept_look import KeptLooks, paint_look
from penfold.rendering.layout import ShownPage

# Where a page is drawn: the left and top of the page, and how many pixels a point of the page takes.
Placement = tuple[float, float, float]


class AnnotationLayer:
    """The annotations Penfold paints over the pages, by the source index of their page."""

    def __init__(self) -> None:
        """Start with none; update gives them, and kept_looks the drawings of those moved as they are."""
        self.painted: dict[int, list[Annotation]] = {}
        self.kept_looks: KeptLooks | None = None

    def update(self, annotations: Iterable[Annotation], left_out: Annotation | None = None) -> set[int]:
        """Paint these annotations, but for one left out (being edited); return the source pages that changed."""
        old, self.painted = self.painted, {}
        for annotation in annotations:
            if (annotation.managed or annotation.moved_as_is) and annotation is not left_out:
                self.painted.setdefault(annotation.page, []).append(annotation)
        return {source for source in {*old, *self.painted} if old.get(source) != self.painted.get(source)}

    def snapshot(
        self,
        snapshot: Gtk.Snapshot,
        page: ShownPage,
        placement: Placement,
        draw_page: Callable[[Gtk.Snapshot], None],
        *,
        also: Annotation | None = None,
    ) -> None:
        """Paint the annotations of a page over it, as they will be saved, and one more (being made) if given.

        A highlight multiplies the page under it by its colour: GTK paints a node apart from what is under it, so the
        page is drawn again (draw_page) in each area, tinted.
        """
        annotations = self.painted.get(page.source, [])
        if also is not None and also.page == page.source:
            annotations = [*annotations, also]
        x, y, zoom = placement
        no_offset = Graphene.Vec4().init(0, 0, 0, 0)
        for annotation in annotations:
            if annotation.kind is not Kind.HIGHLIGHT or not annotation.managed:
                continue
            tint = Graphene.Matrix().init_scale(*highlight_tint(annotation))
            for left, top, right, bottom in highlight_areas(page, annotation):
                snapshot.push_clip(
                    Graphene.Rect().init(x + left * zoom, y + top * zoom, (right - left) * zoom, (bottom - top) * zoom)
                )
                snapshot.push_color_matrix(tint, no_offset)
                draw_page(snapshot)
                snapshot.pop()
                snapshot.pop()
        if any(annotation.kind is not Kind.HIGHLIGHT or not annotation.managed for annotation in annotations):
            width, height = page.size
            context = snapshot.append_cairo(Graphene.Rect().init(x, y, width * zoom, height * zoom))
            context.translate(x, y)
            context.scale(zoom, zoom)
            for annotation in annotations:
                look = None if annotation.managed or self.kept_looks is None else self.kept_looks.look(annotation)
                if look is not None:
                    paint_look(context, page, annotation, look)
            paint_annotations(context, page, [item for item in annotations if item.managed], highlights=False)
