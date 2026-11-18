"""The Annotations view of the side panel (02-interfaz, 6.3; D24, D25): annotations grouped by type.

Phase 2 lists them, filters them by type and goes to one on a click. Selecting them to edit their colour or text, and
deleting them, come with phase 6.
"""

from gettext import gettext as _
from typing import ClassVar

from gi.repository import Gdk, GObject, Graphene, Gtk, Pango

from penfold.document.annotations import TEXT_MARKUPS, Annotation, Kind
from penfold.document.document import OpenDocument
from penfold.rendering.page_content import PageContent
from penfold.ui.sidebar.view_header import empty_label, view_header

# Foreign annotations without a colour, or white, are shown in this orange so they can be seen (as in 0.6).
FALLBACK_COLOR = (0xC6 / 255, 0x46 / 255, 0)
COLOR_BAR_WIDTH = 3
ROW_TEXT_LINES = 4
# Shown by default, as in 0.6: the types with text of their own.
DEFAULT_KINDS = frozenset({Kind.COMMENT, Kind.TEXT_BOX})
# Icon of each type: Adwaita's when it has one, otherwise a provisional one (D37).
KIND_ICONS = {
    Kind.HIGHLIGHT: ("penfold-type-highlight-symbolic", True),
    Kind.UNDERLINE: ("format-text-underline-symbolic", False),
    Kind.STRIKE_OUT: ("format-text-strikethrough-symbolic", False),
    Kind.COMMENT: ("penfold-type-comment-symbolic", True),
    Kind.TEXT_BOX: ("penfold-type-text-box-symbolic", True),
    Kind.RECTANGLE: ("penfold-type-rectangle-symbolic", True),
    Kind.CIRCLE: ("penfold-type-circle-symbolic", True),
    Kind.ARROW: ("penfold-type-arrow-symbolic", True),
    Kind.OTHER: ("penfold-type-other-symbolic", True),
}


def kind_names() -> dict[Kind, str]:
    """Plural name of each type, as in the filter (translated when called)."""
    return {
        Kind.HIGHLIGHT: _("Highlights"),
        Kind.UNDERLINE: _("Underlines"),
        Kind.STRIKE_OUT: _("Strikethroughs"),
        Kind.COMMENT: _("Comments"),
        Kind.TEXT_BOX: _("Text Boxes"),
        Kind.RECTANGLE: _("Rectangles"),
        Kind.CIRCLE: _("Circles"),
        Kind.ARROW: _("Arrows"),
        Kind.OTHER: _("Other Types"),
    }


def display_color(annotation: Annotation) -> tuple[float, float, float]:
    """The colour of the line next to the row: the annotation's, or orange if it has none or is white."""
    color = annotation.color
    if color is None or (not annotation.is_own and min(color) > 0.95):  # noqa: PLR2004 (white)
        return FALLBACK_COLOR
    return color


class ColorBar(Gtk.Widget):
    """The thin vertical line in the colour of an annotation."""

    __gtype_name__ = "PenfoldColorBar"

    def __init__(self, color: tuple[float, float, float]) -> None:
        """Create the line in a colour."""
        super().__init__()
        self._color = Gdk.RGBA()
        self._color.red, self._color.green, self._color.blue = color
        self._color.alpha = 1.0
        self.set_size_request(COLOR_BAR_WIDTH, -1)

    def do_snapshot(self, snapshot: Gtk.Snapshot) -> None:
        """Fill the whole widget with the colour."""
        snapshot.append_color(self._color, Graphene.Rect().init(0, 0, self.get_width(), self.get_height()))


class AnnotationRow(Gtk.ListBoxRow):
    """Like Papers: "Page N" in bold and the author on the right; under them, the text next to a colour line."""

    __gtype_name__ = "PenfoldAnnotationRow"

    def __init__(self, annotation: Annotation, page_label: str, text: str) -> None:
        """Create the row of an annotation, with the text to show for it."""
        super().__init__()
        self.annotation = annotation
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin_top=6, margin_bottom=6)
        top = Gtk.Box(spacing=6)
        page = Gtk.Label(label=_("Page {label}").format(label=page_label), xalign=0, hexpand=True)
        page.add_css_class("heading")
        author = Gtk.Label(label=annotation.author or _("(External)"), xalign=1, ellipsize=Pango.EllipsizeMode.END)
        author.add_css_class("dim-label")
        top.append(page)
        top.append(author)
        bottom = Gtk.Box(spacing=8)
        bottom.append(ColorBar(display_color(annotation)))
        body = Gtk.Label(
            xalign=0,
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
            lines=ROW_TEXT_LINES,
            ellipsize=Pango.EllipsizeMode.END,
            hexpand=True,
        )
        if text:
            body.set_label(text)
        else:
            body.set_markup(f"<i>{_('No text')}</i>")
            body.add_css_class("dim-label")
        bottom.append(body)
        box.append(top)
        box.append(bottom)
        self.set_child(box)


class AnnotationsView(Gtk.Box):
    """Annotations grouped by type, with a filter; "annotation-activated" gives a page and a height on a click."""

    __gtype_name__ = "PenfoldAnnotationsView"
    __gsignals__: ClassVar = {
        "annotation-activated": (GObject.SignalFlags.RUN_FIRST, None, (int, float)),
    }

    def __init__(self) -> None:
        """Create the view, empty until set_document."""
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.shown_kinds: set[Kind] = set(DEFAULT_KINDS)
        self.filter_button = Gtk.MenuButton(
            icon_name="penfold-filter-symbolic", tooltip_text=_("Filter"), valign=Gtk.Align.CENTER
        )
        self.filter_button.add_css_class("provisional-icon")
        self.filter_button.set_popover(self._filter_popover())
        self.append(view_header(_("Annotations"), self.filter_button))
        self.document: OpenDocument | None = None
        self.content: PageContent | None = None
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.MULTIPLE, activate_on_single_click=True)
        self.list.add_css_class("navigation-sidebar")
        self.list.set_header_func(self._header)
        self.list.connect("row-activated", self._on_row_activated)
        self.empty = empty_label("")
        self.stack = Gtk.Stack(vexpand=True)
        self.stack.add_named(Gtk.ScrolledWindow(child=self.list, hscrollbar_policy=Gtk.PolicyType.NEVER), "list")
        self.stack.add_named(self.empty, "empty")
        self.append(self.stack)

    def set_document(self, document: OpenDocument, content: PageContent) -> None:
        """List the annotations of a PDF."""
        self.document, self.content = document, content
        self.refresh()

    def refresh(self) -> None:
        """Fill the list again with the annotations of the types shown."""
        self.list.remove_all()
        document = self.document
        if document is None or self.content is None:
            return
        shown = [item for item in document.annotations if item.kind in self.shown_kinds]
        order = list(Kind)
        for annotation in sorted(shown, key=lambda item: order.index(item.kind)):
            row = AnnotationRow(annotation, document.page_label(annotation.page), self._row_text(annotation))
            self.list.append(row)
        if shown:
            self.stack.set_visible_child_name("list")
        else:
            self.empty.set_label(
                _("No annotations of the types shown") if document.annotations else _("This PDF has no annotations")
            )
            self.stack.set_visible_child_name("empty")

    def _row_text(self, annotation: Annotation) -> str:
        """The annotation's own text; for marks on text without one, the marked text in quotes."""
        if annotation.text or annotation.kind not in TEXT_MARKUPS or self.content is None:
            return annotation.text
        marked = self.content.text_in_areas(annotation.page, list(annotation.quads) or [annotation.rectangle])
        return f"“{marked}”" if marked else ""

    def _counts(self) -> dict[Kind, int]:
        counts: dict[Kind, int] = {}
        if self.document is not None:
            for annotation in self.document.annotations:
                if annotation.kind in self.shown_kinds:
                    counts[annotation.kind] = counts.get(annotation.kind, 0) + 1
        return counts

    def _header(self, row: Gtk.ListBoxRow, before: Gtk.ListBoxRow | None) -> None:
        """A heading with the type and its count above the first row of each type: "Comments (2)"."""
        assert isinstance(row, AnnotationRow)
        kind = row.annotation.kind
        if isinstance(before, AnnotationRow) and before.annotation.kind == kind:
            row.set_header(None)
            return
        # Translators: heading of a group of annotations, as in "Comments (2)".
        text = _("{kind} ({count})").format(kind=kind_names()[kind], count=self._counts().get(kind, 0))
        label = Gtk.Label(
            label=text,
            xalign=0,
            margin_start=12,
            margin_top=12,
            margin_bottom=2,
        )
        label.add_css_class("caption-heading")
        label.add_css_class("dim-label")
        row.set_header(label)

    def _on_row_activated(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        if isinstance(row, AnnotationRow):
            self.emit("annotation-activated", row.annotation.page, row.annotation.rectangle[1])

    def _filter_popover(self) -> Gtk.Popover:
        """The list "Show" with a box and an icon for each type (D24)."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_top=6, margin_bottom=6)
        title = Gtk.Label(label=_("Show"), xalign=0, margin_start=6, margin_bottom=4)
        title.add_css_class("dim-label")
        box.append(title)
        names = kind_names()
        for kind in Kind:
            row = Gtk.Box(spacing=8)
            check = Gtk.CheckButton(active=kind in self.shown_kinds)
            check.connect("toggled", self._on_kind_toggled, kind)
            icon_name, provisional = KIND_ICONS[kind]
            icon = Gtk.Image(icon_name=icon_name)
            if provisional:
                icon.add_css_class("provisional-icon")
            row.append(icon)
            row.append(Gtk.Label(label=names[kind], xalign=0))
            check.set_child(row)
            box.append(check)
        return Gtk.Popover(child=box)

    def _on_kind_toggled(self, check: Gtk.CheckButton, kind: Kind) -> None:
        if check.get_active():
            self.shown_kinds.add(kind)
        else:
            self.shown_kinds.discard(kind)
        self.refresh()
