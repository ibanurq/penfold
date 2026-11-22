"""Editing annotations from their menu (D72): a right click, or a long press, on an annotation of a page.

The menu has the six colours at the top (the annotation's own with a ring) and, below, what can be done with that
type of annotation. A click on a colour changes it and closes the menu; Edit Text… edits the text of a comment in
its popover and that of a text box on the page; Delete deletes it without asking, with a toast to undo it. While
the menu is open, the annotation is outlined. Annotations of types Penfold does not make only have Delete. A PDF that
does not allow annotating shows the menu with everything greyed out.

An annotation of a PDF that Penfold cannot draw again as it is (its foreign look) is only changed after a warning:
changing it would lose that look.
"""

from collections.abc import Callable
from dataclasses import replace
from gettext import gettext as _

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from penfold.document.annotations import Annotation, Kind, managed_copy
from penfold.document.commands.annotations import ChangeAnnotation, DeleteAnnotations
from penfold.document.document import OpenDocument
from penfold.document.history import Command
from penfold.rendering.text_box import redrawn, with_text, written_frame
from penfold.ui.comment_popover import CommentPopover
from penfold.ui.document_view import AnnotationClick, DocumentView
from penfold.ui.palette import ANNOTATION_COLORS, color_circle, color_to_hex, hex_to_color

# No colour circle is ringed for a colour that is not one of the palette's.
NO_COLOR = ""
WITH_TEXT = frozenset({Kind.COMMENT, Kind.TEXT_BOX})


class AnnotationEditing:
    """The menu of the annotations of the pages, and the window's actions it uses."""

    def __init__(
        self,
        window: Gtk.ApplicationWindow,
        document_view: DocumentView,
        document: Callable[[], OpenDocument | None],
        show_undo_toast: Callable[[str, Command], None],
    ) -> None:
        """Add the actions "annotation-menu-color", "edit-annotation-text" and "delete-annotation" to the window."""
        self._window = window
        self._document_view = document_view
        self._document = document
        self._show_undo_toast = show_undo_toast
        # The annotation whose menu is open.
        self.annotation: Annotation | None = None
        self.menu: Gtk.PopoverMenu | None = None
        self.comment_popover: CommentPopover | None = None
        # What to do once the menu has closed and given the focus back (editing a text, which takes the focus).
        self._after_menu: Callable[[], None] | None = None
        self._color = Gio.SimpleAction.new_stateful(
            "annotation-menu-color", GLib.VariantType.new("s"), GLib.Variant.new_string(NO_COLOR)
        )
        self._color.connect("activate", self._on_color_chosen)
        self._edit_text = Gio.SimpleAction.new("edit-annotation-text", None)
        self._edit_text.connect("activate", lambda _action, _parameter: self.edit_text())
        self._delete = Gio.SimpleAction.new("delete-annotation", None)
        self._delete.connect("activate", lambda _action, _parameter: self.delete())
        for action in (self._color, self._edit_text, self._delete):
            window.add_action(action)
        document_view.connect("annotation-menu-requested", self._on_menu_requested)

    def _on_menu_requested(self, _view: DocumentView, click: AnnotationClick) -> None:
        self.open_menu(click.annotation, click.x, click.y)

    def open_menu(self, annotation: Annotation, x: float, y: float) -> None:
        """Show the menu of an annotation at a point of the document view, outlining the annotation."""
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
        self._color.set_enabled(allowed and colored)
        self._edit_text.set_enabled(allowed)
        self._delete.set_enabled(allowed)
        menu = Gtk.PopoverMenu.new_from_model(_menu_model(colored=colored, with_text=annotation.kind in WITH_TEXT))
        if colored:
            menu.add_child(_color_row(), "colors")
        menu.add_child(_separator(), "separator")
        menu.set_parent(self._document_view)
        # As context menus open: without an arrow, from the pointer to its right, covering less of the annotation.
        menu.set_has_arrow(False)
        menu.set_halign(Gtk.Align.START)
        place = Gdk.Rectangle()
        place.x, place.y, place.width, place.height = round(x), round(y), 1, 1
        menu.set_pointing_to(place)
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

    def edit_text(self) -> None:
        """Edit the text of the annotation of the menu: a comment in its popover, a text box on the page (D72)."""
        annotation = self.annotation
        if annotation is None or annotation.kind not in WITH_TEXT:
            return
        edit = self._edit_comment if annotation.kind is Kind.COMMENT else self._edit_text_box
        if self.menu is None:
            edit(annotation)
            return
        # After the menu has closed: closing gives the focus back to the page, which would end the editing at once.
        self._after_menu = lambda: edit(annotation)
        self.menu.popdown()

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

    def delete(self) -> None:
        """Delete the annotation of the menu, with a toast to undo it (D72)."""
        document, annotation = self._document(), self.annotation
        if self.menu is not None:
            self.menu.popdown()
        if document is None or annotation is None or not document.permissions.annotate:
            return
        command = DeleteAnnotations(document, [annotation])
        document.execute(command)
        self._show_undo_toast(_("Annotation deleted"), command)

    def _change(self, annotation: Annotation, change: Callable[[Annotation], Annotation]) -> None:
        """Change an annotation as a managed copy (D60), after a warning if Penfold cannot draw all its look."""
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
        """Ask before changing an annotation Penfold cannot draw again as it is (D72)."""
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


def _menu_model(*, colored: bool, with_text: bool) -> Gio.Menu:
    """The menu of an annotation: the colours (if it has them), Edit Text… (if it has text), and Delete apart.

    It is one section, with separators of its own between the groups: GTK measures a menu with a custom item and
    several sections too short, and the menu then scrolls.
    """
    items = Gio.Menu()
    if colored:
        items.append_item(_custom_item("colors"))
    if with_text:
        items.append(_("_Edit Text…"), "win.edit-annotation-text")
        items.append_item(_custom_item("separator"))
    items.append(_("_Delete"), "win.delete-annotation")
    menu = Gio.Menu()
    menu.append_section(None, items)
    return menu


def _custom_item(name: str) -> Gio.MenuItem:
    """A place in the menu for a widget of the popover's own (add_child with this name)."""
    item = Gio.MenuItem()
    item.set_attribute_value("custom", GLib.Variant.new_string(name))
    return item


def _separator() -> Gtk.Widget:
    """A separator between groups of items, as those between sections."""
    return Gtk.Separator(css_classes=["annotation-menu-separator"])


def _color_row() -> Gtk.Widget:
    """The six colour circles, bound to the action of the menu's colour, and a separator below, as a section's."""
    row = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER, homogeneous=True)
    row.add_css_class("annotation-menu-colors")
    for value in ANNOTATION_COLORS:
        row.append(color_circle(value, "win.annotation-menu-color"))
    colors = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    colors.append(row)
    colors.append(_separator())
    return colors
