"""Asking for the password of a PDF that needs one to be opened: an alert dialogue with a password box.

The dialogue stays open while the password is wrong: it says so in red, empties the box and waits for another. Penfold
never keeps the password beyond the open document.
"""

from collections.abc import Callable
from gettext import gettext as _

from gi.repository import Adw, GLib, Gtk

RESPONSE_CANCEL = "cancel"
RESPONSE_OPEN = "open"


def password_question(
    file_name: str, try_password: Callable[[str], bool], on_cancel: Callable[[], object] | None = None
) -> Adw.AlertDialog:
    """Return a dialogue that asks for the password of a file; present it to ask.

    Open is greyed out while the box is empty. try_password gets each password typed and says whether it opened the
    file; the dialogue closes when it did. Cancel or Esc close it and call on_cancel.
    """
    return _PasswordQuestion(file_name, try_password, on_cancel).dialog


class _PasswordQuestion:
    """The dialogue and what it does with each answer."""

    def __init__(
        self, file_name: str, try_password: Callable[[str], bool], on_cancel: Callable[[], object] | None
    ) -> None:
        self._try_password = try_password
        self._on_cancel = on_cancel
        self._answered = False
        self.entry = Gtk.PasswordEntry(show_peek_icon=True, activates_default=True, placeholder_text=_("Password"))
        self.wrong = Gtk.Label(label=_("Incorrect password"), visible=False, css_classes=["error"])
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.append(self.entry)
        box.append(self.wrong)
        self.dialog = Adw.AlertDialog(
            heading=_("Protected Document"),
            body=_("Opening “{name}” requires its password.").format(name=file_name),
            extra_child=box,
            # Choosing Open must not close it by itself: a wrong password keeps it open (it is closed by _finish).
            can_close=False,
        )
        dialog = self.dialog
        dialog.add_response(RESPONSE_CANCEL, _("_Cancel"))
        dialog.add_response(RESPONSE_OPEN, _("_Open"))
        dialog.set_response_appearance(RESPONSE_OPEN, Adw.ResponseAppearance.SUGGESTED)
        dialog.set_response_enabled(RESPONSE_OPEN, False)
        dialog.set_default_response(RESPONSE_OPEN)
        dialog.set_close_response(RESPONSE_CANCEL)
        self.entry.connect("changed", self._on_changed)
        dialog.connect("response", self._on_response)
        dialog.connect("close-attempt", self._on_close_attempt)
        dialog.connect("map", lambda _dialog: self.entry.grab_focus())

    def _on_changed(self, _entry: Gtk.PasswordEntry) -> None:
        self.dialog.set_response_enabled(RESPONSE_OPEN, bool(self.entry.get_text()))

    def _on_response(self, _dialog: Adw.AlertDialog, response: str) -> None:
        self._answered = True
        if response != RESPONSE_OPEN:
            self._cancel()
        elif self._try_password(self.entry.get_text()):
            self._finish()
        else:
            self.wrong.set_visible(True)
            self.entry.set_text("")
            self.entry.grab_focus()

    def _on_close_attempt(self, _dialog: Adw.AlertDialog) -> None:
        """A button answers right after this; Esc does not answer at all, and counts as Cancel."""
        self._answered = False
        GLib.idle_add(self._cancel_unless_answered)

    def _cancel_unless_answered(self) -> bool:
        if not self._answered:
            self._cancel()
        return GLib.SOURCE_REMOVE

    def _cancel(self) -> None:
        self._finish()
        if self._on_cancel is not None:
            self._on_cancel()

    def _finish(self) -> None:
        self.dialog.disconnect_by_func(self._on_response)
        self.dialog.disconnect_by_func(self._on_close_attempt)
        GLib.idle_add(self._close_if_shown)

    def _close_if_shown(self) -> bool:
        # It may be closing already (force_close answers with Cancel): closing it again from within aborts.
        if self.dialog.get_root() is not None:
            self.dialog.force_close()
        return GLib.SOURCE_REMOVE
