"""The "Properties" dialogue: what is known about the document, to read and copy, never to change.

Rows are grouped as Document, File, Content, History and Security; a row without a value is left out, and so is a
group left empty. Values can be selected, and dates and sizes follow the language.
"""

from datetime import datetime
from gettext import gettext as _

from gi.repository import Adw, GLib

from penfold.document.properties import DocumentProperties, millimetres, paper_size
from penfold.ui.dialogs.add_pages_dialog import size_name
from penfold.ui.document_header import denied_sentences

# Narrow, as Preferences; the height follows the rows, up to what the window allows.
CONTENT_WIDTH = 460


class PenfoldPropertiesDialog(Adw.PreferencesDialog):
    """Shows the properties of a document as they are when the dialogue opens; it does not follow later changes."""

    __gtype_name__ = "PenfoldPropertiesDialog"

    def __init__(self, properties: DocumentProperties) -> None:
        """Create the dialogue with the rows that have a value."""
        super().__init__(title=_("Properties"), content_width=CONTENT_WIDTH, search_enabled=False)
        page = Adw.PreferencesPage()
        for title, rows in _groups(properties):
            shown = [(name, value) for name, value in rows if value]
            if not shown:
                continue
            group = Adw.PreferencesGroup(title=title)
            for name, value in shown:
                group.add(_property_row(name, value))
            page.add(group)
        self.add(page)


def _groups(properties: DocumentProperties) -> list[tuple[str, list[tuple[str, str | None]]]]:
    """Each group's title and its rows, as a name and a value (None or empty to leave the row out)."""
    information = properties.information
    file = properties.file
    return [
        (
            _("Document"),
            [
                (_("Title"), information.title),
                (_("Author"), information.author),
                (_("Subject"), information.subject),
                (_("Keywords"), information.keywords),
            ],
        ),
        (
            _("File"),
            [
                (_("Name"), None if file is None else file.name),
                (_("Folder"), None if file is None else str(file.absolute().parent)),
                (_("Size"), None if properties.file_size is None else GLib.format_size(properties.file_size)),
            ],
        ),
        (
            _("Content"),
            [
                (_("Pages"), str(properties.page_count)),
                (_("Page Size"), describe_page_size(properties.page_size) if properties.page_count else None),
                (_("PDF Version"), properties.pdf_version),
            ],
        ),
        (
            _("History"),
            [
                (_("Created"), format_date(information.created)),
                (_("Modified"), format_date(information.modified)),
                (_("Creator"), information.creator),
                (_("Producer"), information.producer),
            ],
        ),
        (
            _("Security"),
            [
                (_("Password"), _("Yes") if properties.has_password else _("No")),
                (_("Permissions"), "\n".join(denied_sentences(properties.denied)) or _("Unrestricted")),
            ],
        ),
    ]


def _property_row(name: str, value: str) -> Adw.ActionRow:
    """A row that shows a value under its name, both as plain text, and lets the value be selected."""
    row = Adw.ActionRow(title=name, subtitle=value, use_markup=False, subtitle_selectable=True)
    # The value stands out and the name is the small text above it, as in GNOME's own property rows.
    row.add_css_class("property")
    return row


def describe_page_size(size: tuple[float, float] | None) -> str:
    """A page size as shown, such as "A4, 210 × 297 mm"; "Various" if the pages are not all the same size."""  # noqa: RUF002
    if size is None:
        return _("Various")
    width, height = size
    # The real multiplication sign, as GNOME writes sizes.
    measured = _("{width} × {height} mm").format(  # noqa: RUF001
        width=round(millimetres(width)), height=round(millimetres(height))
    )
    paper = paper_size(size)
    if paper is None:
        return measured
    return _("{paper}, {size}").format(paper=size_name(paper), size=measured)


def format_date(date: datetime | None) -> str | None:
    """A date and time in the language's format, in the local time zone; None without a date."""
    if date is None:
        return None
    shown = GLib.DateTime.new_from_unix_local(int(date.timestamp()))
    if shown is None:
        return None
    # Translators: how a date and time is written (GLib's format, such as "November 5, 2023, 12:00").
    return shown.format(_("%B %-d, %Y, %H:%M"))
