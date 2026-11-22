"""Writing a text box on the page (02-interfaz, 5; H3, H5, D69): a box of text over the page, as it will look.

It has the font, the size, the background and the border of the text box, at the zoom of the view, and grows down
as the text grows. Ctrl+Enter, or a click outside it, applies; Esc cancels; Enter starts a new line. Blank, nothing
is made.
"""

from collections.abc import Callable

from gi.repository import Gdk, GLib, Graphene, Gsk, Gtk

from penfold.rendering.text_box import BORDER, FONT_FAMILY, FONT_SIZE, PADDING, Color, background
from penfold.ui.palette import color_to_hex


class TextBoxEditor:
    """A text box being written: a Gtk.TextView, a child of the document view, over a page as shown.

    on_done gets the text (stripped) when it is applied, or None when it is cancelled or left blank.
    """

    def __init__(self, view: Gtk.Widget, page: int, corner: tuple[float, float], width: float, color: Color) -> None:
        """Start writing over the page at this position, from this corner (points of the page as shown)."""
        self.page = page
        self.corner = corner
        self.width = width
        self._color = color
        self._view = view
        self._zoom = 0.0
        self.on_done: Callable[[str | None], object] = lambda _text: None
        self.text_view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, accepts_tab=False)
        # Its look depends on its colour and the zoom: rules of its own, for a class of its own.
        self._class = f"text-box-editor-{id(self)}"
        self.text_view.add_css_class(self._class)
        self._style = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            view.get_display(), self._style, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key_pressed)
        self.text_view.add_controller(keys)
        focus = Gtk.EventControllerFocus()
        # Not at once: GTK is still moving the focus away from the box, which must not be taken away meanwhile.
        focus.connect("leave", lambda _controller: GLib.idle_add(self._finish_after_leaving))
        self.text_view.add_controller(focus)
        self.text_view.get_buffer().connect("changed", lambda _buffer: view.queue_allocate())
        self.text_view.set_parent(view)
        self._finished = False

    @property
    def text(self) -> str:
        """The text written, without the spaces around it."""
        return self.text_view.get_buffer().props.text.strip()

    def grab_focus(self) -> None:
        """Put the cursor in the box, to write."""
        self.text_view.grab_focus()

    def allocate(self, page_origin: tuple[float, float], zoom: float) -> None:
        """Place the box over its page, shown at this point of the view, at this zoom; its height follows the text."""
        if zoom != self._zoom:
            self._show_zoom(zoom)
        width = max(1, round(self.width * zoom))
        _minimum, natural, _baseline_minimum, _baseline_natural = self.text_view.measure(
            Gtk.Orientation.VERTICAL, width
        )
        self.text_view.measure(Gtk.Orientation.HORIZONTAL, -1)
        point = Graphene.Point().init(
            round(page_origin[0] + self.corner[0] * zoom), round(page_origin[1] + self.corner[1] * zoom)
        )
        self.text_view.allocate(width, natural, -1, Gsk.Transform().translate(point))

    def snapshot(self, snapshot: Gtk.Snapshot) -> None:
        """Draw the box over the page."""
        self._view.snapshot_child(self.text_view, snapshot)

    def finish(self, *, apply: bool) -> None:
        """Stop writing, once: apply the text (if not blank) or cancel, and take the box away."""
        if self._finished:
            return
        self._finished = True
        text = self.text if apply else ""
        if self.text_view.has_focus():
            self._view.grab_focus()  # Before the box goes, so that the focus never stays on a widget taken away.
        self.text_view.unparent()
        Gtk.StyleContext.remove_provider_for_display(self._view.get_display(), self._style)
        self.on_done(text or None)

    def _finish_after_leaving(self) -> bool:
        """A click outside the box applies it (H3), once GTK has moved the focus elsewhere."""
        self.finish(apply=True)
        return GLib.SOURCE_REMOVE

    def _show_zoom(self, zoom: float) -> None:
        """The font, the inner space and the border at the zoom of the view, to the fraction of a pixel.

        The lines must break where they will in the drawing saved, which has the same measures in points.
        """
        self._zoom = zoom
        fill = color_to_hex(background(self._color))
        self._style.load_from_string(
            f".{self._class} {{ font-family: '{FONT_FAMILY}'; font-size: {FONT_SIZE * zoom:.3f}px;"
            f" padding: {PADDING * zoom:.3f}px; caret-color: black;"
            f" border: {BORDER * zoom:.3f}px solid {color_to_hex(self._color)}; background: {fill}; }}"
            f" .{self._class} text {{ background: {fill}; color: black; }}"
        )

    def _on_key_pressed(
        self, _controller: Gtk.EventControllerKey, keyval: int, _keycode: int, state: Gdk.ModifierType
    ) -> bool:
        """Ctrl+Enter applies and Esc cancels; Enter alone starts a new line."""
        if keyval in {Gdk.KEY_Return, Gdk.KEY_KP_Enter} and state & Gdk.ModifierType.CONTROL_MASK:
            self.finish(apply=True)
            return True
        if keyval == Gdk.KEY_Escape:
            self.finish(apply=False)
            return True
        return False
