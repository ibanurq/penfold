"""Asking for a short text, such as the title of a bookmark: an alert dialogue with a text box."""

from collections.abc import Callable
from gettext import gettext as _

from gi.repository import Adw, Gtk

RESPONSE_CANCEL = "cancel"
RESPONSE_CONFIRM = "confirm"


def text_question(heading: str, text: str, confirm_label: str, on_answer: Callable[[str], object]) -> Adw.AlertDialog:
    """Return a dialogue that asks for a text, starting with this one selected; present it to ask.

    Enter confirms and Esc cancels. on_answer gets the text, stripped, when it is confirmed; the confirm button is
    greyed out while the text is blank.
    """
    entry = Gtk.Entry(text=text, activates_default=True)
    dialog = Adw.AlertDialog(heading=heading, extra_child=entry)
    dialog.add_response(RESPONSE_CANCEL, _("_Cancel"))
    dialog.add_response(RESPONSE_CONFIRM, confirm_label)
    dialog.set_response_appearance(RESPONSE_CONFIRM, Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response(RESPONSE_CONFIRM)
    dialog.set_close_response(RESPONSE_CANCEL)

    def on_changed(_entry: Gtk.Entry) -> None:
        dialog.set_response_enabled(RESPONSE_CONFIRM, bool(entry.get_text().strip()))

    def on_response(_dialog: Adw.AlertDialog, response: str) -> None:
        # Closing the dialogue answers again, with the close response: only the first counts.
        dialog.disconnect_by_func(on_response)
        if response == RESPONSE_CONFIRM:
            on_answer(entry.get_text().strip())

    entry.connect("changed", on_changed)
    dialog.connect("response", on_response)
    dialog.connect("map", lambda _dialog: entry.grab_focus())
    return dialog
