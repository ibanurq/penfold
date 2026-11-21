"""The Keyboard Shortcuts window.

libadwaita 1.8 brings its own shortcuts dialog; with older versions (Debian 13 has 1.7), GTK's window is used.
"""

from dataclasses import dataclass
from gettext import gettext as _

from gi.repository import Adw, Gtk


@dataclass(frozen=True)
class Shortcut:
    """One row of the window: what the keys do, and the keys."""

    description: str
    accelerator: str


@dataclass(frozen=True)
class ShortcutGroup:
    """A titled list of shortcuts shown together."""

    title: str
    shortcuts: tuple[Shortcut, ...]


def shortcut_groups(application: Gtk.Application) -> tuple[ShortcutGroup, ...]:
    """Return the groups in the order they are shown, with the keys the application assigns to each action."""

    def shortcuts(*descriptions_and_actions: tuple[str, str]) -> tuple[Shortcut, ...]:
        return tuple(
            Shortcut(description, accelerators[0])
            for description, action in descriptions_and_actions
            if (accelerators := application.get_accels_for_action(action))
        )

    # The groups and texts of 0.6 (L2). A row appears once its action has keys, so later phases only add the keys.
    groups = (
        ShortcutGroup(
            _("General"),
            shortcuts(
                (_("Open a PDF"), "app.open"),
                (_("Save"), "win.save"),
                (_("Save as"), "win.save-as"),
                (_("Print"), "win.print"),
                (_("Undo"), "win.undo"),
                (_("Redo"), "win.redo"),
                (_("Show the keyboard shortcuts"), "app.shortcuts"),
                (_("Close the window"), "win.close"),
                (_("Quit"), "app.quit"),
            ),
        ),
        ShortcutGroup(
            _("View"),
            shortcuts(
                (_("Zoom in"), "win.zoom-in"),
                (_("Zoom out"), "win.zoom-out"),
                (_("Fit to page width"), "win.fit-width"),
                # The same keys zoom the thumbnails while they have the focus; so does Ctrl and the wheel (D39).
                (_("Larger thumbnails (with the focus on them)"), "win.zoom-in"),
                (_("Smaller thumbnails (with the focus on them)"), "win.zoom-out"),
            ),
        ),
        ShortcutGroup(
            _("Moving around"),
            shortcuts(
                (_("Next page"), "win.next-page"),
                (_("Previous page"), "win.previous-page"),
                (_("First page"), "win.first-page"),
                (_("Last page"), "win.last-page"),
                (_("Go to page"), "win.focus-page-entry"),
            ),
        ),
    )
    return tuple(group for group in groups if group.shortcuts)


def present_shortcuts_dialog(parent: Gtk.Window | None, application: Gtk.Application) -> None:
    """Show the shortcuts of the application's actions over a window."""
    groups = shortcut_groups(application)
    if hasattr(Adw, "ShortcutsDialog"):
        _present_adwaita_dialog(parent, groups)
    else:
        _present_gtk_window(parent, groups)


def _present_adwaita_dialog(parent: Gtk.Window | None, groups: tuple[ShortcutGroup, ...]) -> None:
    dialog = Adw.ShortcutsDialog()
    for group in groups:
        section = Adw.ShortcutsSection(title=group.title)
        for shortcut in group.shortcuts:
            section.add(Adw.ShortcutsItem(title=shortcut.description, accelerator=shortcut.accelerator))
        dialog.add(section)
    dialog.present(parent)


def _present_gtk_window(parent: Gtk.Window | None, groups: tuple[ShortcutGroup, ...]) -> None:
    window = Gtk.ShortcutsWindow(transient_for=parent, modal=True)
    section = Gtk.ShortcutsSection()
    for group in groups:
        gtk_group = Gtk.ShortcutsGroup(title=group.title)
        for shortcut in group.shortcuts:
            gtk_group.add_shortcut(Gtk.ShortcutsShortcut(title=shortcut.description, accelerator=shortcut.accelerator))
        section.add_group(gtk_group)
    window.add_section(section)
    window.present()
