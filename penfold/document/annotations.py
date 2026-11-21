"""Annotations: the notes, marks and shapes of the pages (ISO 32000-1, 12.5), as the side panel lists them.

Phase 2 only reads them. Penfold's own annotations are the ones whose author (/T) is "Penfold", as in 0.6; the
others are shown but not edited (D24). Links, form fields and pop-up windows are not annotations to list.
"""

import enum
from dataclasses import dataclass

import pikepdf

from penfold.document.pdf_values import numbers, page_height, rectangle, text

OWN_AUTHOR = "Penfold"
# Never listed: they are not notes (links, form fields, pop-up windows of notes…).
NOT_LISTED = frozenset({"/Link", "/Widget", "/Popup"})


class Kind(enum.Enum):
    """The types the panel groups annotations by, in the order of 0.6's filter, and the rest."""

    HIGHLIGHT = "Highlight"
    UNDERLINE = "Underline"
    STRIKE_OUT = "StrikeOut"
    COMMENT = "Text"
    TEXT_BOX = "FreeText"
    RECTANGLE = "Square"
    CIRCLE = "Circle"
    ARROW = "Line"
    OTHER = "Other"


SUBTYPE_KINDS = {f"/{kind.value}": kind for kind in Kind if kind is not Kind.OTHER}
# Marks on text, whose list row shows the marked text when they have no text of their own.
TEXT_MARKUPS = frozenset({Kind.HIGHLIGHT, Kind.UNDERLINE, Kind.STRIKE_OUT})


@dataclass(frozen=True)
class Annotation:
    """One annotation of a page.

    The rectangle is in PDF points from the top left corner of the page: left, top, right, bottom. The quads are the
    areas of the text it marks, in the same units, for highlights, underlines and strikethroughs.
    """

    page: int
    kind: Kind
    subtype: str
    rectangle: tuple[float, float, float, float]
    text: str = ""
    author: str = ""
    color: tuple[float, float, float] | None = None
    quads: tuple[tuple[float, float, float, float], ...] = ()

    @property
    def is_own(self) -> bool:
        """Whether Penfold made it (and can edit it)."""
        return self.author == OWN_AUTHOR


def read_annotations(pdf: pikepdf.Pdf, first_page: int = 0) -> list[Annotation]:
    """Return the annotations of every page, sorted by page and position (top to bottom, then left to right).

    The pages are numbered from first_page: their source indexes (sources.py).
    """
    annotations = []
    for index, page in enumerate(pdf.pages, start=first_page):
        height = page_height(page)
        annots = page.obj.get("/Annots")
        if not isinstance(annots, pikepdf.Array):
            continue
        for position in range(len(annots)):
            annotation = annots[position]
            if isinstance(annotation, pikepdf.Dictionary):
                read = _read_annotation(annotation, index, height)
                if read is not None:
                    annotations.append(read)
    return sorted(annotations, key=lambda item: (item.page, item.rectangle[1], item.rectangle[0]))


def _read_annotation(annotation: pikepdf.Dictionary, page: int, height: float) -> Annotation | None:
    subtype = annotation.get("/Subtype")
    if not isinstance(subtype, pikepdf.Name) or str(subtype) in NOT_LISTED:
        return None
    area = rectangle(annotation.get("/Rect"), height)
    if area is None:
        return None
    return Annotation(
        page=page,
        kind=SUBTYPE_KINDS.get(str(subtype), Kind.OTHER),
        subtype=str(subtype)[1:],
        rectangle=area,
        text=text(annotation.get("/Contents")),
        author=text(annotation.get("/T")),
        color=_color(annotation.get("/C")),
        quads=_quads(annotation.get("/QuadPoints"), height),
    )


def _quads(value: object, height: float) -> tuple[tuple[float, float, float, float], ...]:
    """Turn /QuadPoints (groups of four corners) into the rectangles around each group."""
    corners = numbers(value)
    if not corners:
        return ()
    quads = []
    for start in range(0, len(corners) - 7, 8):
        xs, ys = corners[start : start + 8 : 2], corners[start + 1 : start + 8 : 2]
        quads.append((min(xs), height - max(ys), max(xs), height - min(ys)))
    return tuple(quads)


def _color(value: object) -> tuple[float, float, float] | None:
    """Return an RGB colour (/C with three numbers), a grey (one number), or None for none or other colour spaces."""
    components = numbers(value)
    if components is None:
        return None
    if len(components) == 1:
        return components[0], components[0], components[0]
    if len(components) == 3:  # noqa: PLR2004 (red, green, blue)
        red, green, blue = (min(1.0, max(0.0, component)) for component in components)
        return red, green, blue
    return None
