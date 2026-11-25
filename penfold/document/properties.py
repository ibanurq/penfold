"""The properties of a document: what the Properties dialogue shows, read only.

They describe the PDF as it was opened (its document information, version and security) and the document as it is
now (its pages and their sizes, after the edits). Nothing here changes the document.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pikepdf

from penfold.document.pages import PaperSize

# How far two sizes may be apart, in points, and still be the same size (about a third of a millimetre).
SIZE_TOLERANCE = 1.0
# Points in an inch.
POINTS_PER_INCH = 72.0
# A PDF date (7.9.4): D:YYYYMMDDHHmmSSOHH'mm, where everything after the year may be left out.
PDF_DATE = re.compile(
    r"(?:D:)?(?P<year>\d{4})(?P<month>\d{2})?(?P<day>\d{2})?(?P<hour>\d{2})?(?P<minute>\d{2})?(?P<second>\d{2})?"
    r"(?:(?P<utc>Z)|(?P<sign>[+-])(?P<zone_hours>\d{2})'?(?P<zone_minutes>\d{2})?'?)?"
)


@dataclass(frozen=True)
class PdfInformation:
    """The document information of a PDF (/Info, 14.3.3); None for what it does not have."""

    title: str | None = None
    author: str | None = None
    subject: str | None = None
    keywords: str | None = None
    creator: str | None = None
    """The program that made the original document."""
    producer: str | None = None
    """The program that turned it into a PDF."""
    created: datetime | None = None
    modified: datetime | None = None

    @classmethod
    def of(cls, pdf: pikepdf.Pdf) -> "PdfInformation":
        """Read the document information of a PDF; values that are empty or cannot be read are left out."""
        info = pdf.docinfo
        return cls(
            title=info_text(info, "/Title"),
            author=info_text(info, "/Author"),
            subject=info_text(info, "/Subject"),
            keywords=info_text(info, "/Keywords"),
            creator=info_text(info, "/Creator"),
            producer=info_text(info, "/Producer"),
            created=_info_date(info, "/CreationDate"),
            modified=_info_date(info, "/ModDate"),
        )


@dataclass(frozen=True)
class DocumentProperties:
    """What the Properties dialogue shows about a document."""

    information: PdfInformation
    file: Path | None
    """The file of the document; None for a new document, not saved yet."""
    file_size: int | None
    """The size of the file in bytes, as it is now on disk; None without a file."""
    page_count: int
    page_size: tuple[float, float] | None
    """The width and height of every page as shown, in points; None if they are not all the same size."""
    pdf_version: str | None
    """The version of the PDF, such as "1.7"; None for a new document."""
    has_password: bool
    """Whether it needs a password to be opened."""
    denied: list[str]
    """The names of the user access permissions it denies (access_permissions.py), whether respected or not."""


def info_text(info: pikepdf.Dictionary, key: str) -> str | None:
    """A text of the document information, without spaces around it; None if it is missing, empty or not a text."""
    value = info.get(key)
    if not isinstance(value, pikepdf.String):
        return None
    text = str(value).strip()
    return text or None


def _info_date(info: pikepdf.Dictionary, key: str) -> datetime | None:
    """A date of the document information; None if it is missing or not a valid date."""
    text = info_text(info, key)
    return None if text is None else pdf_date(text)


def pdf_date(text: str) -> datetime | None:
    """Read a PDF date (7.9.4), in its time zone if it says one; None if it is not a valid date."""
    match = PDF_DATE.match(text)
    if match is None:
        return None
    parts = match.groupdict()
    zone = None
    if parts["utc"]:
        zone = UTC
    elif parts["sign"]:
        offset = timedelta(hours=int(parts["zone_hours"]), minutes=int(parts["zone_minutes"] or 0))
        zone = timezone(-offset if parts["sign"] == "-" else offset)
    try:
        return datetime(
            int(parts["year"]),
            int(parts["month"] or 1),
            int(parts["day"] or 1),
            int(parts["hour"] or 0),
            int(parts["minute"] or 0),
            int(parts["second"] or 0),
            tzinfo=zone,
        )
    except ValueError:  # Such as a 13th month.
        return None


def common_size(sizes: list[tuple[float, float]]) -> tuple[float, float] | None:
    """The size all the pages share, within SIZE_TOLERANCE; None if they differ or there are none."""
    if not sizes:
        return None
    width, height = sizes[0]
    for other_width, other_height in sizes[1:]:
        if abs(other_width - width) > SIZE_TOLERANCE or abs(other_height - height) > SIZE_TOLERANCE:
            return None
    return width, height


def paper_size(size: tuple[float, float]) -> PaperSize | None:
    """The known paper a page size is, upright or lying; None if it is none of them."""
    shorter, longer = sorted(size)
    for paper in PaperSize:
        paper_shorter, paper_longer = paper.value
        if abs(shorter - paper_shorter) <= SIZE_TOLERANCE and abs(longer - paper_longer) <= SIZE_TOLERANCE:
            return paper
    return None


def millimetres(points: float) -> float:
    """A length in points, in millimetres."""
    return points / POINTS_PER_INCH * 25.4
