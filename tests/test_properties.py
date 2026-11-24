"""Document properties (07-fase-12, 18): what is read from the PDF and how the Properties dialogue shows it."""

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
import pytest
from gi.repository import Adw, Gio, Gtk

from penfold.document.commands.pages import RotatePages
from penfold.document.document import OpenDocument, PdfToMerge
from penfold.document.pages import PaperSize
from penfold.document.properties import common_size, paper_size, pdf_date
from tests.gtk_helpers import process_pending_events
from tests.sample_pdfs import USER_PASSWORD, make_pdf, make_pdf_with_password, make_pdf_with_permissions
from tests.test_document_window import action_enabled, open_and_wait, window

if TYPE_CHECKING:
    from penfold.ui.window import PenfoldWindow

__all__ = ["window"]

A4 = PaperSize.A4.value
A5 = PaperSize.A5.value


@pytest.fixture
def described_pdf(tmp_path: Path) -> Path:
    """A PDF of three A4 pages with every kind of document information."""
    path = make_pdf(tmp_path / "report.pdf", title="Annual Report")
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.docinfo["/Author"] = "Ana Pérez"
        pdf.docinfo["/Subject"] = "  "
        pdf.docinfo["/Keywords"] = "budget, 2026"
        pdf.docinfo["/Creator"] = "Writer"
        pdf.docinfo["/Producer"] = "Some PDF library"
        pdf.docinfo["/CreationDate"] = "D:20261105120000Z"
        pdf.docinfo["/ModDate"] = "not a date"
        pdf.save(path, min_version="1.7")
    return path


def test_reads_the_document_information(described_pdf: Path) -> None:
    properties = OpenDocument.open(described_pdf).properties()
    information = properties.information
    assert (information.title, information.author, information.keywords) == (
        "Annual Report",
        "Ana Pérez",
        "budget, 2026",
    )
    assert information.subject is None  # Only spaces.
    assert (information.creator, information.producer) == ("Writer", "Some PDF library")
    assert information.created == datetime(2026, 11, 5, 12, tzinfo=UTC)
    assert information.modified is None  # Not a valid date.
    assert properties.pdf_version == "1.7"


def test_reads_the_file_and_the_pages(described_pdf: Path) -> None:
    properties = OpenDocument.open(described_pdf).properties()
    assert properties.file == described_pdf
    assert properties.file_size == described_pdf.stat().st_size
    assert properties.page_count == 3
    assert properties.page_size == pytest.approx(A4, abs=1)  # The sample's A4 is rounded to whole points.
    assert not properties.has_password
    assert properties.denied == []


def test_the_pages_are_described_as_they_are_now(described_pdf: Path) -> None:
    document = OpenDocument.open(described_pdf)
    document.execute(RotatePages(document, [0, 1, 2], 90))
    assert document.properties().page_size == pytest.approx(A4[::-1], abs=1)
    document.undo()
    document.execute(RotatePages(document, [0], 90))
    assert document.properties().page_size is None  # One lies, the others stand.


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("D:20261118155021+01'00'", datetime(2026, 11, 18, 15, 50, 21, tzinfo=timezone(timedelta(hours=1)))),
        ("D:20261118155021+01'00", datetime(2026, 11, 18, 15, 50, 21, tzinfo=timezone(timedelta(hours=1)))),
        ("D:202611181550-05'30'", datetime(2026, 11, 18, 15, 50, tzinfo=timezone(-timedelta(hours=5, minutes=30)))),
        ("D:20261118Z", datetime(2026, 11, 18, tzinfo=UTC)),
        ("D:2026", datetime(2026, 1, 1)),
        ("20261118", datetime(2026, 11, 18)),
        ("D:20261318", None),
        ("yesterday", None),
    ],
)
def test_pdf_dates_may_leave_out_everything_after_the_year(text: str, expected: datetime | None) -> None:
    assert pdf_date(text) == expected


def test_pages_of_different_sizes_have_no_common_size() -> None:
    assert common_size([A4, (A4[0] + 0.5, A4[1])]) == A4
    assert common_size([A4, A5]) is None
    assert common_size([]) is None


@pytest.mark.parametrize(
    ("size", "expected"),
    [(A4, PaperSize.A4), (A4[::-1], PaperSize.A4), ((612.4, 791.8), PaperSize.LETTER), ((500.0, 700.0), None)],
)
def test_known_papers_are_named_upright_or_lying(size: tuple[float, float], expected: PaperSize | None) -> None:
    assert paper_size(size) is expected


def test_security_says_whether_it_has_a_password_and_what_it_denies(tmp_path: Path) -> None:
    protected = OpenDocument.open(make_pdf_with_password(tmp_path / "secret.pdf", "print_highres"), USER_PASSWORD)
    assert protected.properties().has_password
    restricted = OpenDocument.open(make_pdf_with_permissions(tmp_path / "locked.pdf", "print_lowres", "extract"))
    properties = restricted.properties()
    assert not properties.has_password
    assert properties.denied == ["fill_forms", "annotate", "assemble", "modify"]


def test_a_merged_document_has_no_file_information_or_version(described_pdf: Path, tmp_path: Path) -> None:
    merged = OpenDocument.merge(
        [PdfToMerge(described_pdf)],
        tmp_path / "merged.pdf",
        bookmark_per_file=False,
        keep_bookmarks=False,
        respect_permissions=True,
    )
    properties = merged.properties()
    assert properties.information.title is None
    assert (properties.file, properties.file_size, properties.pdf_version) == (None, None, None)
    assert properties.page_count == 3


@pytest.mark.usefixtures("application")
def test_page_sizes_and_dates_are_written_for_people() -> None:
    from penfold.ui.dialogs.properties_dialog import describe_page_size, format_date

    assert describe_page_size(A4) == "A4, 210 × 297 mm"  # noqa: RUF001
    assert describe_page_size(PaperSize.LETTER.value[::-1]) == "Letter, 279 × 216 mm"  # noqa: RUF001
    assert describe_page_size((500.0, 700.0)) == "176 × 247 mm"  # noqa: RUF001
    assert describe_page_size(None) == "Various"
    assert format_date(None) is None
    written = format_date(datetime(2026, 11, 5, 12, tzinfo=UTC))
    assert written is not None
    assert "2026" in written


def descendants(widget: Gtk.Widget) -> list[Gtk.Widget]:
    """A widget and all the widgets inside it, each before its children."""
    found = [widget]
    child = widget.get_first_child()
    while child is not None:
        found.extend(descendants(child))
        child = child.get_next_sibling()
    return found


def property_rows(dialog: Adw.PreferencesDialog) -> dict[str, dict[str, str]]:
    """The rows of a dialogue, as name and value, by the title of their group."""
    groups: dict[str, dict[str, str]] = {}
    for group in descendants(dialog):
        if isinstance(group, Adw.PreferencesGroup):
            rows = [row for row in descendants(group) if isinstance(row, Adw.ActionRow)]
            groups[group.get_title()] = {row.get_title(): row.get_subtitle() or "" for row in rows}
    return groups


def test_properties_is_the_last_item_of_the_document_menu(window: "PenfoldWindow") -> None:
    [button] = [
        widget
        for widget in descendants(window.document_header)
        if isinstance(widget, Gtk.MenuButton) and widget.get_icon_name() == "view-more-symbolic"
    ]
    menu = button.get_menu_model()
    assert menu is not None
    last = menu.get_item_link(menu.get_n_items() - 1, Gio.MENU_LINK_SECTION)
    assert last is not None
    action = last.get_item_attribute_value(last.get_n_items() - 1, "action")
    assert action is not None
    assert action.get_string() == "win.properties"


def test_the_dialogue_shows_only_the_rows_with_a_value(window: "PenfoldWindow", described_pdf: Path) -> None:
    from penfold.ui.dialogs.properties_dialog import PenfoldPropertiesDialog

    assert not action_enabled(window, "properties")  # Without a document.
    assert open_and_wait(window, described_pdf)
    window.activate_action("win.properties", None)
    process_pending_events()
    dialog = window.get_visible_dialog()
    assert isinstance(dialog, PenfoldPropertiesDialog)
    rows = property_rows(dialog)
    assert rows["Document"] == {"Title": "Annual Report", "Author": "Ana Pérez", "Keywords": "budget, 2026"}
    assert rows["File"]["Name"] == "report.pdf"
    assert rows["File"]["Folder"] == str(described_pdf.parent)
    assert rows["Content"] == {"Pages": "3", "Page Size": "A4, 210 × 297 mm", "PDF Version": "1.7"}  # noqa: RUF001
    assert set(rows["History"]) == {"Created", "Creator", "Producer"}
    assert rows["Security"] == {"Password": "No", "Permissions": "Unrestricted"}
    dialog.force_close()
