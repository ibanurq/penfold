"""Annotations: the notes, marks and shapes of the pages (ISO 32000-1, 12.5), as the side panel lists them.

The annotations of the PDF are read and shown as they are; Poppler draws them. The ones made in Penfold are managed:
Penfold draws them and writes them into the PDF when it is saved (03-arquitectura, 4.1). From phase 9, the
annotations of the types Penfold makes will be managed too (D60). Links, form fields and pop-up windows are not
annotations to list.
"""

import enum
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pikepdf

from penfold.document.page_frame import PageFrame
from penfold.document.pdf_values import numbers, text

# The author of new annotations when none is set in the preferences (D60).
DEFAULT_AUTHOR = "Penfold"
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


class AnnotationGroup(enum.Enum):
    """The four groups of annotations, the same in the panel's filter and lists and when printing (D57, D64)."""

    TEXT_MARKUPS = "text-markups"
    """Highlights, underlines (also squiggly), strikethroughs."""
    SHAPES = "shapes"
    """Rectangles, circles, arrows and lines, polygons, polylines and freehand drawings."""
    TEXT_ELEMENTS = "text-elements"
    """Comments, text boxes, stamps and insert-text marks."""
    OTHERS = "others"
    """Every other type that is listed: attachments, sounds, redactions, watermarks…"""


SUBTYPE_GROUPS = {
    **dict.fromkeys(("/Highlight", "/Underline", "/Squiggly", "/StrikeOut"), AnnotationGroup.TEXT_MARKUPS),
    **dict.fromkeys(("/Square", "/Circle", "/Line", "/Polygon", "/PolyLine", "/Ink"), AnnotationGroup.SHAPES),
    **dict.fromkeys(("/Text", "/FreeText", "/Stamp", "/Caret"), AnnotationGroup.TEXT_ELEMENTS),
}


def group_of(subtype: str) -> AnnotationGroup | None:
    """The group of an annotation subtype ("/Ink"), or None for those that are not listed (links, form fields…)."""
    if subtype in NOT_LISTED:
        return None
    return SUBTYPE_GROUPS.get(subtype, AnnotationGroup.OTHERS)


SUBTYPE_KINDS = {f"/{kind.value}": kind for kind in Kind if kind is not Kind.OTHER}
# Marks on text, whose list row shows the marked text when they have no text of their own.
TEXT_MARKUPS = frozenset({Kind.HIGHLIGHT, Kind.UNDERLINE, Kind.STRIKE_OUT})


@dataclass(frozen=True)
class Annotation:
    """One annotation of a page.

    The rectangle is in PDF points from the top left corner of the page as shown (page_frame.py): left, top, right,
    bottom. The quads are the
    areas of the text it marks, in the same units, for highlights, underlines and strikethroughs; the line goes from
    its start to its end (x, y, x, y) for arrows.

    A managed annotation is drawn and written by Penfold, with a unique name (/NM) and its creation date.
    """

    page: int
    kind: Kind
    subtype: str
    rectangle: tuple[float, float, float, float]
    text: str = ""
    author: str = ""
    color: tuple[float, float, float] | None = None
    quads: tuple[tuple[float, float, float, float], ...] = ()
    line: tuple[float, float, float, float] | None = None
    name: str = ""
    created: datetime | None = None
    managed: bool = False

    @property
    def group(self) -> AnnotationGroup:
        """The group it is listed and printed in."""
        return SUBTYPE_GROUPS.get(f"/{self.subtype}", AnnotationGroup.OTHERS)


def new_annotation(  # noqa: PLR0913 (what an annotation is made of)
    kind: Kind,
    page: int,
    rectangle: tuple[float, float, float, float],
    color: tuple[float, float, float],
    author: str,
    *,
    text: str = "",
    quads: tuple[tuple[float, float, float, float], ...] = (),
    line: tuple[float, float, float, float] | None = None,
) -> Annotation:
    """Make an annotation in Penfold, now, by an author ("Penfold" if none is set), with a unique name.

    Raises:
        ValueError: the kind is not one Penfold makes.
    """
    if kind is Kind.OTHER:
        message = "Penfold does not make annotations of other types"
        raise ValueError(message)
    return Annotation(
        page=page,
        kind=kind,
        subtype=kind.value,
        rectangle=rectangle,
        text=text,
        author=author.strip() or DEFAULT_AUTHOR,
        color=color,
        quads=quads,
        line=line,
        name=f"penfold-{uuid.uuid4()}",
        created=datetime.now(UTC),
        managed=True,
    )


def read_annotations(pdf: pikepdf.Pdf, first_page: int = 0) -> list[Annotation]:
    """Return the annotations of every page, sorted by page and position (top to bottom, then left to right).

    The pages are numbered from first_page: their source indexes (sources.py).
    """
    annotations = []
    for index, page in enumerate(pdf.pages, start=first_page):
        frame = PageFrame.of(page)
        annots = page.obj.get("/Annots")
        if not isinstance(annots, pikepdf.Array):
            continue
        for position in range(len(annots)):
            annotation = annots[position]
            if isinstance(annotation, pikepdf.Dictionary):
                read = _read_annotation(annotation, index, frame)
                if read is not None:
                    annotations.append(read)
    return sorted(annotations, key=lambda item: (item.page, item.rectangle[1], item.rectangle[0]))


def _read_annotation(annotation: pikepdf.Dictionary, page: int, frame: PageFrame) -> Annotation | None:
    subtype = annotation.get("/Subtype")
    if not isinstance(subtype, pikepdf.Name) or str(subtype) in NOT_LISTED:
        return None
    area = frame.place(annotation.get("/Rect"))
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
        quads=_quads(annotation.get("/QuadPoints"), frame),
    )


def _quads(value: object, frame: PageFrame) -> tuple[tuple[float, float, float, float], ...]:
    """Turn /QuadPoints (groups of four corners) into the rectangles around each group, on the page as shown."""
    corners = numbers(value)
    if not corners:
        return ()
    quads = []
    for start in range(0, len(corners) - 7, 8):
        points = [frame.point(corners[index], corners[index + 1]) for index in range(start, start + 8, 2)]
        xs, ys = [x for x, _y in points], [y for _x, y in points]
        quads.append((min(xs), min(ys), max(xs), max(ys)))
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
