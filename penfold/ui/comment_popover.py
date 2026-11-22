"""Writing the text of a comment (02-interfaz, 5; H5, D68): a popover pointing at its place on the page.

Enter starts a new line, Ctrl+Enter applies, Esc (or a click outside) cancels. Apply is greyed out while the text is
blank: an empty comment is not made.
"""

from collections.abc import Callable
from gettext import gettext as _

from gi.repository import Gdk, Gtk

TEXT_WIDTH = 280
TEXT_HEIGHT = 110


class CommentPopover(Gtk.Popover):
    """A box of several lines with Cancel and Apply; on_apply gets the text, stripped."""

    __gtype_name__ = "PenfoldCommentPopover"

    def __init__(self, on_apply: Callable[[str], object]) -> None:
        """Create the popover, empty; set its parent and the point it points at, then popup."""
        super().__init__(position=Gtk.PositionType.BOTTOM)
        self._on_apply = on_apply
        self.text_view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, accepts_tab=False)
        self.text_view.add_css_class("comment-text")
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key_pressed)
        self.text_view.add_controller(keys)
        scrolled = Gtk.ScrolledWindow(
            child=self.text_view,
            min_content_width=TEXT_WIDTH,
            min_content_height=TEXT_HEIGHT,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
        )
        scrolled.add_css_class("card")
        cancel = Gtk.Button(label=_("_Cancel"), use_underline=True)
        cancel.connect("clicked", lambda _button: self.popdown())
        self.apply_button = Gtk.Button(label=_("_Apply"), use_underline=True, sensitive=False)
        self.apply_button.add_css_class("suggested-action")
        self.apply_button.connect("clicked", lambda _button: self.apply())
        buttons = Gtk.Box(spacing=6, halign=Gtk.Align.END)
        buttons.append(cancel)
        buttons.append(self.apply_button)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content.append(scrolled)
        content.append(buttons)
        self.set_child(content)
        self.text_view.get_buffer().connect("changed", self._on_changed)
        self.connect("map", lambda _popover: self.text_view.grab_focus())

    @property
    def text(self) -> str:
        """The text written, without the spaces around it."""
        return self.text_view.get_buffer().props.text.strip()

    def apply(self) -> None:
        """Make the comment with the text written, if any, and close."""
        if self.text:
            self._on_apply(self.text)
            self.popdown()

    def _on_changed(self, _buffer: Gtk.TextBuffer) -> None:
        self.apply_button.set_sensitive(bool(self.text))

    def _on_key_pressed(
        self, _controller: Gtk.EventControllerKey, keyval: int, _keycode: int, state: Gdk.ModifierType
    ) -> bool:
        """Ctrl+Enter applies; Enter alone starts a new line, as in any box of several lines."""
        if keyval in {Gdk.KEY_Return, Gdk.KEY_KP_Enter} and state & Gdk.ModifierType.CONTROL_MASK:
            self.apply()
            return True
        return False
