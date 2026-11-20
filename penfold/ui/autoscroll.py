"""Scrolling a list by itself while something is dragged near its top or bottom, so it can be dropped far (E1, F1)."""

from gi.repository import Gdk, GLib, Gtk

# How close to the edge the pointer starts the scrolling, and the fastest it scrolls (at the edge), in pixels.
EDGE = 48
SPEED = 18


class DragAutoscroll:
    """Scrolls a scrolled window while a drag goes over it near its top or bottom edge, faster nearer the edge."""

    def __init__(self, scrolled: Gtk.ScrolledWindow) -> None:
        """Watch drags over a scrolled window."""
        self._scrolled = scrolled
        self._drag_y: float | None = None
        motion = Gtk.DropControllerMotion()
        motion.connect("enter", self._on_motion)
        motion.connect("motion", self._on_motion)
        motion.connect("leave", lambda _motion: setattr(self, "_drag_y", None))
        scrolled.add_controller(motion)

    def _on_motion(self, _motion: Gtk.DropControllerMotion, _x: float, y: float) -> None:
        if self._drag_y is None:
            self._scrolled.add_tick_callback(self._scroll)
        self._drag_y = y

    def _scroll(self, _widget: Gtk.Widget, _clock: Gdk.FrameClock) -> bool:
        if self._drag_y is None:
            return GLib.SOURCE_REMOVE
        height = self._scrolled.get_height()
        distance = min(self._drag_y, height - self._drag_y)
        if distance < EDGE:
            direction = -1 if self._drag_y < height / 2 else 1
            adjustment = self._scrolled.get_vadjustment()
            step = SPEED * (1 - max(0.0, distance) / EDGE)
            adjustment.set_value(adjustment.get_value() + direction * step)
        return GLib.SOURCE_CONTINUE
