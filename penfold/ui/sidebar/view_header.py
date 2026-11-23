"""Pieces shared by the views of the side panel.

Their header (02-interfaz, 6), noticing recent use (D40), clearing their selection (D47) and counting it (D74).
"""

import time

from gi.repository import Gtk, Pango

HEADER_MARGIN = 12


def view_header(title: str, *buttons: Gtk.Widget) -> Gtk.Box:
    """Return a header row with the title on the left and the buttons on the right, at the same height in every view."""
    header = Gtk.Box(spacing=6, margin_start=HEADER_MARGIN, margin_end=HEADER_MARGIN, margin_top=6, margin_bottom=6)
    header.set_size_request(-1, 34)
    label = Gtk.Label(label=title, xalign=0, hexpand=True)
    label.add_css_class("heading")
    header.append(label)
    for button in buttons:
        header.append(button)
    return header


def header_button(label: str, icon_name: str, action_name: str) -> Gtk.Button:
    """Return a button with an icon and a text; it is greyed out while its action does not exist (D21)."""
    content = Gtk.Box(spacing=6)
    content.append(Gtk.Image(icon_name=icon_name))
    content.append(Gtk.Label(label=label, use_underline=True))
    return Gtk.Button(child=content, action_name=action_name, valign=Gtk.Align.CENTER)


def selection_counter() -> Gtk.Label:
    """The counter of what is selected, floating at the bottom of a list with the look of a toast (D74).

    It is hidden until show_count gives it a number, and clicks go through it to the list.
    """
    counter = Gtk.Label(
        visible=False,
        can_target=False,
        halign=Gtk.Align.CENTER,
        valign=Gtk.Align.END,
        ellipsize=Pango.EllipsizeMode.END,
    )
    counter.add_css_class("osd")
    counter.add_css_class("selection-counter")
    return counter


def show_count(counter: Gtk.Label, count: int, text: str) -> None:
    """Show how many are selected, with this text ("{count} selected"), or hide the counter with none."""
    counter.set_visible(count > 0)
    counter.set_label(text.format(count=count))


def empty_label(text: str) -> Gtk.Label:
    """Return a centred, dimmed line for a view with nothing to show."""
    label = Gtk.Label(label=text, wrap=True, justify=Gtk.Justification.CENTER, margin_start=24, margin_end=24)
    label.add_css_class("dim-label")
    return label


class RecentUse:
    """Notices when the user is using a list (pointer over it, scrolling it).

    Following the reading then leaves the list where it is, so it does not move under the user (D40).
    """

    QUIET_SECONDS = 2.0

    def __init__(self, widget: Gtk.Widget) -> None:
        """Watch the pointer and the wheel over a widget."""
        self._last_use = 0.0
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", lambda _controller, _x, _y: self._used())
        widget.add_controller(motion)
        scroll = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.BOTH_AXES)
        scroll.connect("scroll", self._on_scroll)
        widget.add_controller(scroll)

    def _used(self) -> None:
        self._last_use = time.monotonic()

    def _on_scroll(self, _controller: Gtk.EventControllerScroll, _dx: float, _dy: float) -> bool:
        self._used()
        return False

    @property
    def recently(self) -> bool:
        """Whether the list was used in the last two seconds."""
        return time.monotonic() - self._last_use < self.QUIET_SECONDS


def unselect_all(selection: Gtk.SelectionModel) -> bool:
    """Clear a list's selection (Esc, D47); return whether anything was selected."""
    if selection.get_selection().is_empty():
        return False
    selection.unselect_all()
    return True


def unselect_on_empty_click(scrolled: Gtk.ScrolledWindow, selection: Gtk.SelectionModel) -> None:
    """Clear the selection when the list is clicked away from its rows, in its gaps or below them (D47)."""
    click = Gtk.GestureClick()

    def on_pressed(_gesture: Gtk.GestureClick, _presses: int, x: float, y: float) -> None:
        if is_away_from_rows(scrolled, x, y):
            unselect_all(selection)

    click.connect("pressed", on_pressed)
    scrolled.add_controller(click)


def is_away_from_rows(scrolled: Gtk.ScrolledWindow, x: float, y: float) -> bool:
    """Whether a point of a scrolled list is in no row (nor its scrollbar): in a gap, below the rows, in a margin.

    A row takes the whole box its selection shows, so the space beside a thumbnail belongs to it.
    """
    return scrolled.pick(x, y, Gtk.PickFlags.DEFAULT) in {scrolled, scrolled.get_child()}
