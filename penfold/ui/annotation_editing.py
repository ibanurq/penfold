"""Editing annotations from their menu (D72): a right click, or a long press, on an annotation of a page.

The menu has the six colours at the top (the annotation's own with a ring) and, below, what can be done with that
type of annotation. A click on a colour changes it and closes the menu; Delete deletes it without asking, with a
toast to undo it. While the menu is open, the annotation is outlined. Annotations of types Penfold does not make only
have Delete. A PDF that does not allow annotating shows the menu with everything greyed out.

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
from penfold.rendering.text_box import redrawn
from penfold.ui.document_view import AnnotationClick, DocumentView
from penfold.ui.palette import ANNOTATION_COLORS, color_circle, color_to_hex, hex_to_color

# No colour circle is ringed for a colour that is not one of the palette's.
NO_COLOR = ""


class AnnotationEditing:
    """The menu of the annotations of the pages, and the window's actions it uses."""

    def __init__(
        self,
        window: Gtk.ApplicationWindow,
        document_view: DocumentView,
        document: Callable[[], OpenDocument | None],
        show_undo_toast: Callable[[str, Command], None],
    ) -> None:
        """Add the actions "annotation-menu-color" and "delete-annotation" to the window."""
        self._window = window
        self._document_view = document_view
        self._document = document
        self._show_undo_toast = show_undo_toast
        # The annotation whose menu is open.
        self.annotation: Annotation | None = None
        self.menu: Gtk.PopoverMenu | None = None
        self._color = Gio.SimpleAction.new_stateful(
            "annotation-menu-color", GLib.VariantType.new("s"), GLib.Variant.new_string(NO_COLOR)
        )
        self._color.connect("activate", self._on_color_chosen)
        self._delete = Gio.SimpleAction.new("delete-annotation", None)
        self._delete.connect("activate", lambda _action, _parameter: self.delete())
        for action in (self._color, self._delete):
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
        self._delete.set_enabled(allowed)
        menu = Gtk.PopoverMenu.new_from_model(_menu_model(colored=colored))
        if colored:
            menu.add_child(_color_row(), "colors")
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


def _menu_model(*, colored: bool) -> Gio.Menu:
    """The menu of an annotation: the colours (if it has them) and Delete.

    The colours go in the same section as the first items, with their own separator below: GTK measures a section
    with only a custom item too short, and the menu then scrolls.
    """
    menu = Gio.Menu()
    actions = Gio.Menu()
    if colored:
        item = Gio.MenuItem()
        item.set_attribute_value("custom", GLib.Variant.new_string("colors"))
        actions.append_item(item)
    actions.append(_("_Delete"), "win.delete-annotation")
    menu.append_section(None, actions)
    return menu


def _color_row() -> Gtk.Widget:
    """The six colour circles, bound to the action of the menu's colour, and a separator below, as a section's."""
    row = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER, homogeneous=True)
    row.add_css_class("annotation-menu-colors")
    for value in ANNOTATION_COLORS:
        row.append(color_circle(value, "win.annotation-menu-color"))
    colors = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    colors.append(row)
    colors.append(Gtk.Separator(css_classes=["annotation-menu-separator"]))
    return colors
