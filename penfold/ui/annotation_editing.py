"""Editing annotations from their menu: a right click, or a long press, on an annotation of a page.

The menu has the six colours at the top (the annotation's own with a ring; greyed out for images, which have none, and
stamps, whose colour goes with the stamp) and,
below, what can be done with that type of annotation. A click on a colour changes it and closes the menu; Edit Text…
edits the text of a comment in its popover and that of a text box on the page; Format… opens its Format panel beside it,
whose changes show at once and are undone as one edit; Move and Resize shows its handles on the page, and the change is
one edit too; Rotate Left and Rotate Right turn an image a quarter around its centre, as one edit; Delete deletes it
without asking, with a toast to undo it. While the menu is open, the annotation is outlined. Annotations of types
Penfold does not make only have Delete; a stamp of a PDF without its drawing is only moved (Format… greyed out). A PDF
that does not allow annotating shows the menu with everything greyed out.

An annotation of a PDF that Penfold cannot draw again as it is (its foreign look) is only changed after a warning:
changing it would lose that look.
"""

from collections.abc import Callable
from dataclasses import replace
from gettext import gettext as _
from gettext import ngettext

from gi.repository import Adw, Gio, GLib, Gtk

from penfold.document.annotations import TEXT_MARKUPS, Annotation, Kind, managed_copy
from penfold.document.commands.annotations import ChangeAnnotation, DeleteAnnotations
from penfold.document.document import OpenDocument
from penfold.document.history import Command
from penfold.document.reshaping import can_move, can_resize, turned
from penfold.rendering.text_box import redrawn, with_text, written_frame
from penfold.ui.comment_popover import CommentPopover
from penfold.ui.context_menu import COLORS, SEPARATOR, color_row, context_menu, custom_item, separator
from penfold.ui.document_view import AnnotationClick, DocumentView
from penfold.ui.format_popover import UNCOLORED, FormatPopover, has_format
from penfold.ui.palette import ANNOTATION_COLORS, color_to_hex, hex_to_color

# No colour circle is ringed for a colour that is not one of the palette's.
NO_COLOR = ""
WITH_TEXT = frozenset({Kind.COMMENT, Kind.TEXT_BOX})
# Types that turn a quarter at a time.
TURNABLE = frozenset({Kind.IMAGE})


class AnnotationEditing:
    """The menu of the annotations of the pages, and the window's actions it uses."""

    def __init__(
        self,
        window: Gtk.ApplicationWindow,
        document_view: DocumentView,
        document: Callable[[], OpenDocument | None],
        show_undo_toast: Callable[[str, Command], None],
    ) -> None:
        """Add the menu's actions to the window: its colour, Edit Text…, Format… and Delete."""
        self._window = window
        self._document_view = document_view
        self._document = document
        self._show_undo_toast = show_undo_toast
        # The annotation whose menu is open.
        self.annotation: Annotation | None = None
        self.menu: Gtk.PopoverMenu | None = None
        self.comment_popover: CommentPopover | None = None
        self.format_popover: FormatPopover | None = None
        # The change the Format panel open has made, retouched by each later change of the panel (one edit).
        self._format_change: ChangeAnnotation | None = None
        # What to do once the menu has closed and given the focus back (editing a text, which takes the focus).
        self._after_menu: Callable[[], None] | None = None
        self._color = Gio.SimpleAction.new_stateful(
            "annotation-menu-color", GLib.VariantType.new("s"), GLib.Variant.new_string(NO_COLOR)
        )
        self._color.connect("activate", self._on_color_chosen)
        self._edit_text = Gio.SimpleAction.new("edit-annotation-text", None)
        self._edit_text.connect("activate", lambda _action, _parameter: self.edit_text())
        self._format = Gio.SimpleAction.new("format-annotation", None)
        self._format.connect("activate", lambda _action, _parameter: self.format())
        self._reshape = Gio.SimpleAction.new("reshape-annotation", None)
        self._reshape.connect("activate", lambda _action, _parameter: self.reshape())
        self._turn_left = Gio.SimpleAction.new("rotate-annotation-left", None)
        self._turn_left.connect("activate", lambda _action, _parameter: self.turn(clockwise=False))
        self._turn_right = Gio.SimpleAction.new("rotate-annotation-right", None)
        self._turn_right.connect("activate", lambda _action, _parameter: self.turn(clockwise=True))
        self._delete = Gio.SimpleAction.new("delete-annotation", None)
        self._delete.connect("activate", lambda _action, _parameter: self.delete())
        actions = (self._color, self._edit_text, self._format, self._reshape, self._turn_left, self._turn_right)
        for action in (*actions, self._delete):
            window.add_action(action)
        document_view.connect("annotation-menu-requested", self._on_menu_requested)

    def _on_menu_requested(self, _view: DocumentView, click: AnnotationClick) -> None:
        self.open_menu(click.annotation, click.x, click.y)

    def open_menu(self, annotation: Annotation, x: float, y: float, parent: Gtk.Widget | None = None) -> None:
        """Show the menu of an annotation at a point of a widget (the document view), outlining the annotation."""
        document = self._document()
        if document is None:
            return
        if self.menu is not None:
            self.menu.popdown()
        allowed = document.permissions.annotate
        colored = annotation.kind is not Kind.OTHER
        self.annotation = annotation
        color = color_to_hex(annotation.color) if annotation.color else NO_COLOR
        self._color.set_state(GLib.Variant.new_string(color if color in ANNOTATION_COLORS else NO_COLOR))
        self._color.set_enabled(allowed and colored and annotation.kind not in UNCOLORED)
        self._edit_text.set_enabled(allowed)
        self._format.set_enabled(allowed and annotation.drawable)
        self._reshape.set_enabled(allowed and self._can_reshape(annotation))
        for turn in (self._turn_left, self._turn_right):
            turn.set_enabled(allowed)
        self._delete.set_enabled(allowed)
        model = _menu_model(
            colored=colored,
            with_text=annotation.kind in WITH_TEXT,
            with_format=has_format(annotation.kind),
            reshape=_reshape_label(annotation),
            turnable=annotation.kind in TURNABLE,
        )
        custom = {SEPARATOR: separator()}
        if colored:
            custom[COLORS] = color_row(ANNOTATION_COLORS, "win.annotation-menu-color")
        # From the pointer to its right, it covers less of the annotation.
        menu = context_menu(model, parent or self._document_view, x, y, custom)
        menu.connect("closed", self._on_menu_closed)
        self.menu = menu
        self._document_view.set_marked(annotation)
        menu.popup()

    def _on_menu_closed(self, menu: Gtk.PopoverMenu) -> None:
        # After any action of the menu has run, and outside the popover's own signal (it is taken away).
        GLib.idle_add(self._forget_menu, menu)

    def _forget_menu(self, menu: Gtk.PopoverMenu) -> bool:
        menu.unparent()
        if self.menu is menu:
            self.menu = None
            self.annotation = None
            self._document_view.set_marked(None)
        after, self._after_menu = self._after_menu, None
        if after is not None:
            after()
        return GLib.SOURCE_REMOVE

    def _on_color_chosen(self, _action: Gio.SimpleAction, parameter: GLib.Variant | None) -> None:
        if parameter is not None:
            self.change_color(parameter.get_string())

    def change_color(self, value: str) -> None:
        """Give the annotation of the menu another colour (#rrggbb), and close the menu."""
        annotation = self.annotation
        if self.menu is not None:
            self.menu.popdown()
        if annotation is not None:
            self._change(annotation, lambda copy: replace(copy, color=hex_to_color(value)))

    def turn(self, *, clockwise: bool) -> None:
        """Turn the image of the menu a quarter around its centre, clockwise (Rotate Right) or not (Rotate Left)."""
        annotation = self.annotation
        page = None if annotation is None else self._document_view.shown_page(annotation.page)
        if self.menu is not None:
            self.menu.popdown()
        if annotation is not None and page is not None and annotation.kind in TURNABLE:
            self._change(annotation, lambda copy: turned(copy, clockwise, page.source_size))

    def edit_text(self) -> None:
        """Edit the text of the annotation of the menu: a comment in its popover, a text box on the page."""
        annotation = self.annotation
        if annotation is None or annotation.kind not in WITH_TEXT:
            return
        edit = self._edit_comment if annotation.kind is Kind.COMMENT else self._edit_text_box
        self._when_menu_closed(lambda: edit(annotation))

    def _when_menu_closed(self, then: Callable[[], None]) -> None:
        """Do something once the menu has closed.

        Closing it gives the focus back to the page, which would end an editing begun before.
        """
        if self.menu is None:
            then()
            return
        self._after_menu = then
        self.menu.popdown()

    def format(self) -> None:
        """Open the Format panel of the annotation of the menu beside it.

        One Penfold cannot draw again as it is is warned of first.
        """
        annotation = self.annotation
        if annotation is None or not has_format(annotation.kind):
            return

        def open_panel() -> None:
            if annotation.managed or not annotation.foreign_look:
                self._open_format(annotation)
            else:
                self._warn_of_foreign_look(lambda: self._open_format(annotation))

        self._when_menu_closed(open_panel)

    def reshape(self) -> None:
        """Show the handles of the annotation of the menu on its page, to move it or change its size."""
        annotation = self.annotation
        if annotation is not None and self._can_reshape(annotation):
            self._when_menu_closed(lambda: self._edit_shape(annotation))

    def _can_reshape(self, annotation: Annotation) -> bool:
        """Whether Move and Resize can be used on an annotation now.

        A mark on text needs text under it, and to be drawn again by Penfold: it changes the text it covers. Any other
        that moves can be moved: one of a PDF keeps its own drawing.
        """
        if annotation.kind in TEXT_MARKUPS:
            return _can_resize(annotation) and self._document_view.has_text_under(annotation)
        return can_move(annotation)

    def _edit_shape(self, annotation: Annotation) -> None:
        """Move an annotation, or resize it with handles, shown as it changes (Poppler leaves out one of the PDF).

        One of a PDF is moved as it is, and only has handles if Penfold can draw it again as it is.
        """
        view, document = self._document_view, self._document()
        renderer = view.renderer
        if document is None or renderer is None or not any(item is annotation for item in document.annotations):
            return
        if not annotation.managed:
            renderer.hide_annotations([*document.replaced_annotations, annotation])

        def done(changed: Annotation | None) -> None:
            if changed is not None and document.permissions.annotate:
                drawn = redrawn(changed) if changed.kind is Kind.TEXT_BOX and changed.managed else changed
                document.execute(ChangeAnnotation(document, annotation, drawn))
            elif not annotation.managed:
                renderer.hide_annotations(document.replaced_annotations)

        # A mark shows as Penfold draws it from the start: it will be drawn again, and Poppler's own drawing of it
        # multiplies its colour with the page under it, which it cannot do painted apart.
        shown = managed_copy(annotation) if annotation.kind in TEXT_MARKUPS else None
        view.edit_handles(annotation, done, resizable=_can_resize(annotation), shown=shown)

    def _open_format(self, annotation: Annotation) -> None:
        document, place = self._document(), self._document_view.view_rectangle(annotation)
        if document is None or place is None or not any(item is annotation for item in document.annotations):
            return
        self._format_change = None
        popover = FormatPopover(managed_copy(annotation), lambda changed: self._retouch(annotation, changed))
        popover.set_parent(self._document_view)
        popover.set_pointing_to(place)
        popover.connect("closed", self._on_format_closed)
        self.format_popover = popover
        popover.popup()

    def _retouch(self, annotation: Annotation, changed: Annotation) -> None:
        """Show a change of the Format panel: the first makes an edit, the next ones change it (one edit to undo)."""
        document = self._document()
        if document is None or not document.permissions.annotate:
            return
        if changed.kind is Kind.TEXT_BOX:
            changed = self._text_box_as_formatted(changed)
        change = self._format_change
        if change is not None and document.amend(change, lambda: change.retouch(changed)):
            return
        # The first change; or the last edit is another one (saved meanwhile): a new edit from the panel's last.
        current = annotation if change is None else change.changed
        if any(item is current for item in document.annotations):
            self._format_change = ChangeAnnotation(document, current, changed)
            document.execute(self._format_change)

    def _text_box_as_formatted(self, box: Annotation) -> Annotation:
        """A text box with its new format drawn again, as tall as its text needs with its letter size."""
        renderer = self._document_view.renderer
        document = self._document()
        position = None if renderer is None or document is None else document.page_position(box.page)
        if renderer is None or position is None:
            return redrawn(box)
        return redrawn(with_text(box, box.text, renderer.layout[position].source_size))

    def _on_format_closed(self, popover: Gtk.Popover) -> None:
        if self.format_popover is popover:
            self.format_popover = None
            self._format_change = None
        GLib.idle_add(popover.unparent)  # Once it has finished closing.

    def _edit_comment(self, annotation: Annotation) -> None:
        """The comment's popover, with its text, pointing at its bubble; Apply changes the text."""
        place = self._document_view.view_rectangle(annotation)
        if place is None:
            return
        popover = CommentPopover(
            lambda text: self._change(annotation, lambda copy: replace(copy, text=text)), annotation.text
        )
        popover.set_parent(self._document_view)
        popover.set_pointing_to(place)
        popover.connect("closed", self._on_comment_closed)
        self.comment_popover = popover
        popover.popup()

    def _on_comment_closed(self, popover: Gtk.Popover) -> None:
        if self.comment_popover is popover:
            self.comment_popover = None
        GLib.idle_add(popover.unparent)  # Once it has finished closing.

    def _edit_text_box(self, annotation: Annotation) -> None:
        """Write over the text box, upright as it was written, with its format and text; it is hidden meanwhile."""
        view, document = self._document_view, self._document()
        renderer = view.renderer
        position = None if document is None or renderer is None else document.page_position(annotation.page)
        if document is None or renderer is None or position is None:
            return
        source_size = renderer.layout[position].source_size
        corner, width = written_frame(annotation, source_size)
        page = renderer.layout[position]
        if page.rotation != annotation.text_turn:
            # Turned since it was written: the box is written upright where it shows, as wide as its text.
            left, top, _right, _bottom = view.annotation_bounds(page, annotation) or (0.0, 0.0, 0.0, 0.0)
            corner = (left, top)
        color = annotation.color or (0.0, 0.0, 0.0)
        view.set_hidden(annotation)
        if not annotation.managed:
            renderer.hide_annotations([*document.replaced_annotations, annotation])
        editor = view.write_text_box(position, corner, width, color, style=annotation.style, text=annotation.text)
        done = editor.on_done

        def write(text: str | None) -> None:
            done(text)
            view.set_hidden(None)
            renderer.hide_annotations(document.replaced_annotations)
            if text and text != annotation.text:
                self._change(annotation, lambda copy: with_text(copy, text, source_size))

        editor.on_done = write

    def delete(self, annotations: list[Annotation] | None = None) -> None:
        """Delete some annotations (by default, that of the menu), with a toast to undo it."""
        document = self._document()
        chosen = annotations if annotations is not None else [self.annotation] if self.annotation else []
        if self.menu is not None:
            self.menu.popdown()
        if document is None or not chosen or not document.permissions.annotate:
            return
        command = DeleteAnnotations(document, chosen)
        document.execute(command)
        count = len(chosen)
        self._show_undo_toast(
            ngettext("Annotation deleted", "{count} annotations deleted", count).format(count=count), command
        )

    def _change(self, annotation: Annotation, change: Callable[[Annotation], Annotation]) -> None:
        """Change an annotation as a managed copy, after a warning if Penfold cannot draw all its look."""
        document = self._document()
        if document is None or not document.permissions.annotate:
            return

        def apply() -> None:
            if not any(item is annotation for item in document.annotations):
                return  # Undone or deleted while the warning was shown.
            changed = change(managed_copy(annotation))
            if changed.kind is Kind.TEXT_BOX:
                changed = redrawn(changed)
            if changed != annotation:
                document.execute(ChangeAnnotation(document, annotation, changed))

        if annotation.managed or not annotation.foreign_look:
            apply()
        else:
            self._warn_of_foreign_look(apply)

    def _warn_of_foreign_look(self, apply: Callable[[], None]) -> None:
        """Ask before changing an annotation Penfold cannot draw again as it is."""
        dialog = Adw.AlertDialog(
            heading=_("Change This Annotation?"),
            body=_(
                "It was made with another program, and Penfold cannot draw all of its look. "
                "If it is changed, some of its look will be lost."
            ),
        )
        dialog.add_response("cancel", _("_Cancel"))
        dialog.add_response("change", _("C_hange"))
        dialog.set_response_appearance("change", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("change")
        dialog.set_close_response("cancel")

        def on_response(answered: Adw.AlertDialog, response: str) -> None:
            answered.disconnect_by_func(on_response)  # close() answers again (9.4).
            if response == "change":
                apply()

        dialog.connect("response", on_response)
        dialog.present(self._window)


def _can_resize(annotation: Annotation) -> bool:
    """Whether an annotation is resized with handles: of a type that has them, that Penfold can draw again as it is.

    Any that moves is moved, though: one of a PDF keeps its own drawing.
    """
    return can_resize(annotation) and (annotation.managed or not annotation.foreign_look)


def _reshape_label(annotation: Annotation) -> str | None:
    """The menu item that shows the handles, or None for a type without them.

    Move and Resize; Move for one of a fixed size (a comment); Adjust Ends for the marks on text, which follow the text
    instead of moving.
    """
    if can_resize(annotation):
        return _("_Adjust Ends") if annotation.kind in TEXT_MARKUPS else _("_Move and Resize")
    return _("_Move") if can_move(annotation) else None


def _menu_model(
    *, colored: bool, with_text: bool, with_format: bool, reshape: str | None, turnable: bool = False
) -> Gio.Menu:
    """The menu of an annotation: the colours, Edit Text…, Format…, the item of the handles, the turns, Delete.

    Each only if it has it.

    It is one section, with separators of its own between the groups (as every context menu, ui/context_menu.py).
    """
    items = Gio.Menu()
    if colored:
        items.append_item(custom_item(COLORS))
    if with_text:
        items.append(_("_Edit Text…"), "win.edit-annotation-text")
    if with_format:
        items.append(_("_Format…"), "win.format-annotation")
    if reshape:
        items.append(reshape, "win.reshape-annotation")
    if turnable:
        items.append(_("Rotate _Left"), "win.rotate-annotation-left")
        items.append(_("Rotate _Right"), "win.rotate-annotation-right")
    if with_text or with_format or reshape or turnable:
        items.append_item(custom_item(SEPARATOR))
    items.append(_("_Delete"), "win.delete-annotation")
    menu = Gio.Menu()
    menu.append_section(None, items)
    return menu
