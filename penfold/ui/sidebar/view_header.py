"""Pieces shared by the views of the side panel.

Their header (02-interfaz, 6), noticing recent use (D40), clearing their selection (D47), counting it (D74) and the
room after the last row that keeps the counter off it.
"""

import time
from collections.abc import Callable

from gi.repository import GLib, Gtk, Pango

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


class EndRoom:
    """Room after the last row of a list, as tall as its selection counter with its margin.

    The last row can then always be scrolled above the counter, whether it shows or not, so nothing moves when the
    selection changes. The room is a bottom margin on the widgets of the last row: it scrolls with the list and the
    highlight of a selected row does not cover it. Each list item's child sits in a row widget of GTK's, its parent,
    which is the one that takes the margin. The view's bind and unbind handlers call track and forget with that child.
    The list items themselves are not kept: GTK would not let go of the rows of items removed from the list.
    """

    def __init__(self, view: Gtk.ListView | Gtk.GridView, position_of: Callable[[Gtk.Widget], int]) -> None:
        """Keep the room in a list, or in a grid such as that of the thumbnails; position_of tells where a child is."""
        self._view = view
        self._position_of = position_of
        # GTK measures a hidden widget as nothing: the room is measured on a counter of its own, never shown.
        self._sample_counter = selection_counter()
        self._sample_counter.set_visible(True)
        self._sample_counter.set_label("1")
        self._children: set[Gtk.Widget] = set()
        # The row widgets that have the room now, to take it away when they show another row or none.
        self._rows_with_room: set[Gtk.Widget] = set()
        self._update_pending = False
        model = view.get_model()
        assert isinstance(model, Gtk.MultiSelection)
        self._model = model
        model.connect("items-changed", lambda *_arguments: self._update_soon())
        if isinstance(view, Gtk.GridView):
            view.connect("notify::max-columns", lambda *_arguments: self._update_soon())

    def track(self, child: Gtk.Widget) -> None:
        """Note the child of a row just bound; the row gets the room if it is in the last row."""
        self._children.add(child)
        self._update_soon()

    def forget(self, child: Gtk.Widget | None) -> None:
        """Note the child of a row being unbound; the row may show another item next."""
        self._children.discard(child)
        self._update_soon()

    @property
    def last_row_start(self) -> int:
        """Position of the first item in the last row."""
        count = self._model.get_n_items()
        columns = self._view.get_max_columns() if isinstance(self._view, Gtk.GridView) else 1
        return count - (count % columns or columns)

    def _update_soon(self) -> None:
        """Move the room once the list has laid out its rows: while it binds them, they are not to be resized."""
        if not self._update_pending:
            self._update_pending = True
            GLib.idle_add(self._update)

    def _update(self) -> bool:
        self._update_pending = False
        last_row_start = self.last_row_start
        last_children = [child for child in self._children if self._position_of(child) >= last_row_start]
        rows = {row for child in last_children if (row := child.get_parent()) is not None}
        for row in self._rows_with_room - rows:
            row.set_margin_bottom(0)
        height = self.height
        for row in rows:
            row.set_margin_bottom(height)
        self._rows_with_room = rows
        return GLib.SOURCE_REMOVE

    @property
    def height(self) -> int:
        """Height of the room: the counter's, with its margin."""
        return self._sample_counter.measure(Gtk.Orientation.VERTICAL, -1)[1]


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
