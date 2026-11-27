"""Annotations: the notes, marks and shapes of the pages (ISO 32000-1, 12.5), as the side panel lists them.

The annotations of the PDF are read and shown as they are; Poppler draws them. The ones made in Penfold are managed:
Penfold draws them and writes them into the PDF when it is saved. An annotation of the PDF of a type Penfold makes
becomes managed when it is changed; one deleted or changed is taken out of its page when the PDF is saved. Links, form
fields and pop-up windows are not annotations to list.
"""

import enum
import math
import re
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from itertools import pairwise

import pikepdf

from penfold.document.page_frame import PageFrame
from penfold.document.pdf_values import date, name, number, numbers, text

# The author of new annotations when none is set in the preferences.
DEFAULT_AUTHOR = "Penfold"
# How a new annotation looks: lines of 1 point (freehand drawings, 2: by hand, 1 point looks faint and shaky),
# highlights at 75 %, text boxes in 11 points.
LINE_WIDTH = 1.0
FREEHAND_LINE_WIDTH = 2.0
HIGHLIGHT_OPACITY = 0.75
TEXT_BOX_FONT_SIZE = 11.0
# How much of the colour the soft fill of rectangles and circles has, over white.
FILL_STRENGTH = 0.25
# Colours read from a PDF closer than this to Penfold's, in each component, are taken as Penfold's.
COLOR_TOLERANCE = 0.02
# In a text box's default appearance (/DA): its font and size ("/Helv 11 Tf"), and black letters ("0 g").
FONT_SETTING = re.compile(r"/([^\s/]+)\s+([\d.]+)\s+Tf")
BLACK_TEXT = re.compile(r"(?:^|\s)(?:0(?:\.0*)?\s+g|0(?:\.0*)?\s+0(?:\.0*)?\s+0(?:\.0*)?\s+rg)(?:\s|$)")
# Never listed: they are not notes (links, form fields, pop-up windows of notes…).
NOT_LISTED = frozenset({"/Link", "/Widget", "/Popup"})

Point = tuple[float, float]


class Kind(enum.Enum):
    """The types the panel groups annotations by, in the order of its filter, and the rest."""

    HIGHLIGHT = "Highlight"
    UNDERLINE = "Underline"
    SQUIGGLY = "Squiggly"
    STRIKE_OUT = "StrikeOut"
    COMMENT = "Text"
    TEXT_BOX = "FreeText"
    RECTANGLE = "Square"
    CIRCLE = "Circle"
    ARROW = "Line"
    FREEHAND = "Ink"
    OTHER = "Other"


class AnnotationGroup(enum.Enum):
    """The four groups of annotations, the same in the panel's filter and lists and when printing."""

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


class LineEnds(enum.Enum):
    """Where an arrow has arrowheads: at its end, at both ends, or none (a straight line)."""

    END = "end"
    BOTH = "both"
    NONE = "none"


@dataclass(frozen=True)
class Style:
    """How an annotation looks, as its Format panel changes it, and as the standard keeps it.

    Each type uses only some of it: the opacity (/CA) all but comments; the line width, the dashes (/BS) and the fill
    (/IC, a soft tint of the colour) rectangles, circles and arrows, which also have their arrowheads (/LE); the font
    size (/DA), the background and the border text boxes.
    """

    opacity: float = 1.0
    line_width: float = LINE_WIDTH
    dashed: bool = False
    filled: bool = False
    line_ends: LineEnds = LineEnds.END
    font_size: float = TEXT_BOX_FONT_SIZE
    background: bool = True
    border: bool = True


def default_style(kind: Kind) -> Style:
    """How a new annotation of a type looks."""
    if kind is Kind.HIGHLIGHT:
        return Style(opacity=HIGHLIGHT_OPACITY)
    if kind is Kind.FREEHAND:
        return Style(line_width=FREEHAND_LINE_WIDTH)
    return Style()


SUBTYPE_KINDS = {f"/{kind.value}": kind for kind in Kind if kind is not Kind.OTHER}
# Marks on text, whose list row shows the marked text when they have no text of their own.
TEXT_MARKUPS = frozenset({Kind.HIGHLIGHT, Kind.UNDERLINE, Kind.SQUIGGLY, Kind.STRIKE_OUT})


@dataclass(frozen=True)
class Annotation:
    """One annotation of a page.

    The rectangle is in PDF points from the top left corner of the page as shown (page_frame.py): left, top, right,
    bottom. The quads are the areas of the text it marks, in the same units, for highlights, underlines (also
    squiggly) and strikethroughs; the line goes from its start to its end (x, y, x, y) for arrows; the strokes are the
    paths of a freehand drawing, each the points it goes through in order (one alone is a dot).

    A managed annotation is drawn and written by Penfold, with a unique name (/NM), its creation date and, once changed,
    the date it was changed (/M; else the creation date). Its foreign look is what of its look as read from a PDF
    Penfold cannot draw again (a cloudy border, a closed arrowhead, another font…): changing it would lose that, so the
    interface warns first. One read from a PDF knows its origin, its place in the /Annots of its page there, so that
    saving can take it out of the page when it is deleted or changed (written again), and its drawn place, its place
    among the annotations of its type on the page, so that Poppler can find it (with its name, if it has one) and leave
    it out when Penfold draws it instead (Poppler skips those it cannot read, so the place among all of them would not
    do); those made in Penfold have neither. A text box reads turned clockwise by text_turn degrees from the page as
    shown (the turn Penfold gave the page when it was written, so that it was upright), and keeps its saved drawing: a
    one-page PDF with the fonts it uses inside.

    One read from a PDF that was only moved is not drawn again: it keeps the drawing its program made, moved by moved_by
    on its page (as its rectangle is), and saving moves it in its page instead of writing it again.
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
    strokes: tuple[tuple[Point, ...], ...] = ()
    name: str = ""
    created: datetime | None = None
    modified: datetime | None = None
    managed: bool = False
    origin: int | None = None
    drawn_place: int | None = None
    style: Style = field(default_factory=Style)
    foreign_look: tuple[str, ...] = ()
    text_turn: int = 0
    drawing: bytes = field(default=b"", repr=False)
    moved_by: tuple[float, float] = (0.0, 0.0)

    @property
    def moved_as_is(self) -> bool:
        """Whether it is one of a PDF that was moved keeping the drawing its program made."""
        return not self.managed and self.moved_by != (0.0, 0.0)

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
    strokes: tuple[tuple[Point, ...], ...] = (),
    text_turn: int = 0,
    drawing: bytes = b"",
    style: Style | None = None,
) -> Annotation:
    """Make an annotation in Penfold, now, by an author ("Penfold" if none is set), with a unique name.

    It looks as new annotations of its type do, unless a style is given.

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
        strokes=strokes,
        text_turn=text_turn,
        drawing=drawing,
        style=style or default_style(kind),
        name=_new_name(),
        created=datetime.now(UTC),
        managed=True,
    )


def managed_copy(annotation: Annotation) -> Annotation:
    """The annotation as Penfold draws and writes it, to change it: one read from a PDF becomes managed.

    It keeps its name, author and creation date (with a name and a date if it had none), and is changed now. One
    moved as it was is drawn again where it is now.

    Raises:
        ValueError: it is of a type Penfold does not make, so it cannot draw it.
    """
    if annotation.managed:
        return annotation
    if annotation.kind is Kind.OTHER:
        message = f"Penfold does not draw annotations of type {annotation.subtype}"
        raise ValueError(message)
    now = datetime.now(UTC)
    return replace(
        annotation,
        managed=True,
        name=annotation.name or _new_name(),
        created=annotation.created or now,
        modified=now,
        moved_by=(0.0, 0.0),
    )


def _new_name() -> str:
    return f"penfold-{uuid.uuid4()}"


class Hit(enum.IntEnum):
    """How much a point is on an annotation, to choose among several under the pointer."""

    NONE = 0
    INSIDE = 1
    """Inside a rectangle or circle with nothing inside: what is under it may be wanted instead."""
    ON = 2
    """On what it draws: its line, its fill, its marked text, its box."""


def hit(annotation: Annotation, x: float, y: float, reach: float) -> Hit:
    """How much a point of the page (as shown, like the annotation) is on an annotation, reach points around its lines.

    Comments stay upright on turned pages, so the interface places them itself; here their rectangle counts.
    """
    if annotation.kind in TEXT_MARKUPS and annotation.quads:
        return Hit.ON if any(_within(quad, x, y, 0.0) for quad in annotation.quads) else Hit.NONE
    if annotation.kind is Kind.ARROW and annotation.line is not None:
        width = annotation.style.line_width / 2 + reach
        return Hit.ON if _distance_to_line(annotation.line, x, y) <= width else Hit.NONE
    if annotation.kind is Kind.FREEHAND and annotation.strokes:
        width = annotation.style.line_width / 2 + reach
        return Hit.ON if _distance_to_strokes(annotation.strokes, x, y) <= width else Hit.NONE
    if annotation.kind in {Kind.RECTANGLE, Kind.CIRCLE}:
        return _shape_hit(annotation, x, y, reach)
    return Hit.ON if _within(annotation.rectangle, x, y, 0.0) else Hit.NONE


def _shape_hit(annotation: Annotation, x: float, y: float, reach: float) -> Hit:
    """On a rectangle's or circle's line (or anywhere inside, filled), or in its empty inside."""
    left, top, right, bottom = annotation.rectangle
    width = annotation.style.line_width + reach
    if annotation.kind is Kind.RECTANGLE:
        inside = _within(annotation.rectangle, x, y, 0.0)
        on_line = _within(annotation.rectangle, x, y, reach) and not _within(
            (left + width, top + width, right - width, bottom - width), x, y, 0.0
        )
    else:
        centre_x, centre_y = (left + right) / 2, (top + bottom) / 2
        half_x, half_y = max((right - left) / 2, 1e-6), max((bottom - top) / 2, 1e-6)
        distance = math.hypot((x - centre_x) / half_x, (y - centre_y) / half_y)
        inside = distance <= 1
        on_line = abs(distance - 1) * min(half_x, half_y) <= width
    if on_line or (inside and annotation.style.filled):
        return Hit.ON
    return Hit.INSIDE if inside else Hit.NONE


def _within(rectangle: tuple[float, float, float, float], x: float, y: float, margin: float) -> bool:
    left, top, right, bottom = rectangle
    return left - margin <= x <= right + margin and top - margin <= y <= bottom + margin


def _distance_to_line(line: tuple[float, float, float, float], x: float, y: float) -> float:
    """The distance from a point to a line segment."""
    start_x, start_y, end_x, end_y = line
    length = (end_x - start_x) ** 2 + (end_y - start_y) ** 2
    along = 0.0 if not length else ((x - start_x) * (end_x - start_x) + (y - start_y) * (end_y - start_y)) / length
    along = min(1.0, max(0.0, along))
    return math.hypot(x - (start_x + along * (end_x - start_x)), y - (start_y + along * (end_y - start_y)))


def _distance_to_strokes(strokes: tuple[tuple[Point, ...], ...], x: float, y: float) -> float:
    """The distance from a point to the nearest part of a freehand drawing's strokes."""
    return min(
        _distance_to_line((*first, *second), x, y)
        for stroke in strokes
        for first, second in (pairwise(stroke) if len(stroke) > 1 else [(stroke[0], stroke[0])])
    )


def topmost(annotations: list[Annotation], hits: dict[int, Hit]) -> Annotation | None:
    """The annotation a point is most on, among those it hits (by their place in the list), the one on top first.

    Those made or changed in Penfold are on top of those of the PDF, which are in the order of their pages' /Annots.
    """
    found = [(hits[index], annotation, index) for index, annotation in enumerate(annotations) if hits.get(index)]
    if not found:
        return None
    _hit, annotation, _index = max(found, key=lambda item: (item[0], item[1].managed, item[1].origin or 0, item[2]))
    return annotation


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
        of_type: dict[str, int] = {}
        for position in range(len(annots)):
            annotation = annots[position]
            if not isinstance(annotation, pikepdf.Dictionary):
                continue
            subtype = str(annotation.get("/Subtype"))
            drawn = of_type.get(subtype, 0)
            of_type[subtype] = drawn + 1
            read = _read_annotation(annotation, index, position, frame)
            if read is not None:
                annotations.append(replace(read, drawn_place=drawn))
    return sorted(annotations, key=lambda item: (item.page, item.rectangle[1], item.rectangle[0]))


def _read_annotation(annotation: pikepdf.Dictionary, page: int, origin: int, frame: PageFrame) -> Annotation | None:
    subtype = annotation.get("/Subtype")
    if not isinstance(subtype, pikepdf.Name) or str(subtype) in NOT_LISTED:
        return None
    area = frame.place(annotation.get("/Rect"))
    if area is None:
        return None
    kind = SUBTYPE_KINDS.get(str(subtype), Kind.OTHER)
    strokes = _strokes(annotation.get("/InkList"), frame) if kind is Kind.FREEHAND else ()
    if kind is Kind.FREEHAND and not strokes:
        kind = Kind.OTHER  # Without its strokes, Penfold cannot draw it.
    color = _color(annotation.get("/C"))
    look = _Look(annotation, kind, color)
    return Annotation(
        page=page,
        kind=kind,
        subtype=str(subtype)[1:],
        rectangle=area,
        text=text(annotation.get("/Contents")),
        author=text(annotation.get("/T")),
        color=color,
        quads=_quads(annotation.get("/QuadPoints"), frame),
        line=look.line(frame) if kind is Kind.ARROW else None,
        strokes=strokes,
        name=text(annotation.get("/NM")),
        created=date(annotation.get("/CreationDate")),
        modified=date(annotation.get("/M")),
        origin=origin,
        style=look.style,
        foreign_look=tuple(look.foreign),
    )


class _Look:
    """How an annotation of a PDF looks: its style, and what of it Penfold cannot draw again."""

    def __init__(self, annotation: pikepdf.Dictionary, kind: Kind, color: tuple[float, float, float] | None) -> None:
        self._annotation = annotation
        self.foreign: list[str] = []
        opacity = number(annotation.get("/CA"))
        width, dashed = self._border()
        filled = self._fill(kind, color)
        self._reversed = False
        line_ends = self._line_ends() if kind is Kind.ARROW else LineEnds.END
        font_size = self._font_size() if kind is Kind.TEXT_BOX else TEXT_BOX_FONT_SIZE
        if kind is Kind.COMMENT and name(annotation.get("/Name")) not in {"", "Comment", "Note"}:
            self.foreign.append("icon")
        if "/RD" in annotation and kind in {Kind.RECTANGLE, Kind.CIRCLE, Kind.TEXT_BOX}:
            self.foreign.append("inner margins")
        self.style = Style(
            opacity=min(1.0, max(0.0, opacity)) if opacity is not None else 1.0,
            line_width=width,
            dashed=dashed,
            filled=filled,
            line_ends=line_ends,
            font_size=font_size,
            background=kind is not Kind.TEXT_BOX or self._text_box_background(color),
            border=kind is not Kind.TEXT_BOX or width > 0,
        )

    def line(self, frame: PageFrame) -> tuple[float, float, float, float] | None:
        """The arrow's line on the page as shown, from its start to its end (turned round if its head was first)."""
        ends = numbers(self._annotation.get("/L"))
        if ends is None or len(ends) != 4:  # noqa: PLR2004 (two points)
            return None
        start, end = frame.point(*ends[:2]), frame.point(*ends[2:])
        if self._reversed:
            start, end = end, start
        return (*start, *end)

    def _border(self) -> tuple[float, bool]:
        """The width of the line and whether it is dashed (/BS; else the older /Border); 1 point, solid, if none."""
        effect = self._annotation.get("/BE")
        if isinstance(effect, pikepdf.Dictionary) and name(effect.get("/S")) == "C":
            self.foreign.append("cloudy border")
        border = self._annotation.get("/BS")
        if isinstance(border, pikepdf.Dictionary):
            width = number(border.get("/W"))
            style = name(border.get("/S")) or "S"
            if style not in {"S", "D"}:
                self.foreign.append("border style")
            return (LINE_WIDTH if width is None else max(0.0, width)), style == "D"
        old = numbers(self._annotation.get("/Border"))
        if old is not None and len(old) >= 3:  # noqa: PLR2004 (corner radii, then width)
            return max(0.0, old[2]), False
        return LINE_WIDTH, False

    def _fill(self, kind: Kind, color: tuple[float, float, float] | None) -> bool:
        """Whether a rectangle or circle is filled; one not filled with Penfold's soft tint has a foreign look."""
        inside = _color(self._annotation.get("/IC"))
        if inside is None or kind not in {Kind.RECTANGLE, Kind.CIRCLE}:
            return False
        soft = [1 - FILL_STRENGTH + FILL_STRENGTH * component for component in color or (0.0, 0.0, 0.0)]
        if any(abs(a - b) > COLOR_TOLERANCE for a, b in zip(inside, soft, strict=True)):
            self.foreign.append("fill colour")
        return True

    def _text_box_background(self, color: tuple[float, float, float] | None) -> bool:
        """Whether a text box has a background: its /IC, or else its colour (/C), which viewers paint as one.

        Penfold paints a soft tint of the colour: a background of the colour itself has a foreign look.
        """
        if "/IC" in self._annotation:
            return True
        if color is None:
            return False
        self.foreign.append("fill colour")
        return True

    def _line_ends(self) -> LineEnds:
        """The arrowheads (/LE); any other than an open one is drawn open, and has a foreign look."""
        value = self._annotation.get("/LE")
        ends = [name(value[index]) for index in range(len(value))] if isinstance(value, pikepdf.Array) else []
        start, end = [*ends, "", ""][:2]
        heads = [head not in {"", "None"} for head in (start, end)]
        if any(head not in {"", "None", "OpenArrow"} for head in (start, end)):
            self.foreign.append("arrowheads")
        if all(heads):
            return LineEnds.BOTH
        if heads[0]:
            self._reversed = True  # Its only head at the start: the same arrow, from its end.
        return LineEnds.END if any(heads) else LineEnds.NONE

    def _font_size(self) -> float:
        """The size of a text box's letters (/DA); another font or colour than black has a foreign look."""
        appearance = text(self._annotation.get("/DA"))
        found = FONT_SETTING.search(appearance)
        if found is None:
            return TEXT_BOX_FONT_SIZE
        font, size = found.groups()
        if font not in {"Helv", "Helvetica", "LiberationSans"} or not BLACK_TEXT.search(appearance):
            self.foreign.append("font")
        if "/RC" in self._annotation:
            self.foreign.append("rich text")
        return float(size) if float(size) > 0 else TEXT_BOX_FONT_SIZE


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


def _strokes(value: object, frame: PageFrame) -> tuple[tuple[Point, ...], ...]:
    """Turn /InkList (paths, each of points x, y, x, y…) into strokes on the page as shown, leaving out empty paths."""
    if not isinstance(value, pikepdf.Array):
        return ()
    strokes = []
    for index in range(len(value)):
        coordinates = numbers(value[index]) or []
        points = tuple(frame.point(x, y) for x, y in zip(coordinates[::2], coordinates[1::2], strict=False))
        if points:
            strokes.append(points)
    return tuple(strokes)


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
