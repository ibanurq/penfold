"""Extracting pages to new PDFs: which pages, as one file or one per page, and with what names.

Pages are given as numbers and ranges separated by commas, such as "1, 5, 10-12, 56-", where "56-" runs to the last
page. The numbers are positions in the document, from 1.

Each file extracted is written as saving writes the document: its pages as they are now, in order and turned, with their
labels, annotations and form fields, and the bookmarks that lead to them.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from penfold.errors import PenfoldError

# A part of the list: a page, or a range with its last page or without it (to the end).
RANGE_PATTERN = re.compile(r"(\d+)\s*(-)?\s*(\d+)?")
SEPARATORS = re.compile(r"[,;]")
MIN_NAME_DIGITS = 2


class PageRangeError(PenfoldError):
    """The list of pages to extract cannot be read; the subclasses say why, for the interface to explain it."""


class NoPagesError(PageRangeError):
    """Nothing was written."""


@dataclass
class InvalidFormatError(PageRangeError):
    """A part is neither a page nor a range of pages."""

    part: str


@dataclass
class InvalidRangeError(PageRangeError):
    """A range ends before it starts."""

    part: str


@dataclass
class MissingPageError(PageRangeError):
    """A page is not in the document."""

    page: int
    page_count: int


def parse_page_ranges(text: str, page_count: int) -> list[int]:
    """Return the positions (from 0) of the pages a list such as "1, 5, 10-12, 56-" names, in order, without repeats.

    Raises:
        NoPagesError: the list is empty.
        InvalidFormatError: a part is not a page or a range.
        InvalidRangeError: a range ends before it starts.
        MissingPageError: a page is not in the document.
    """
    parts = [part.strip() for part in SEPARATORS.split(text) if part.strip()]
    if not parts:
        raise NoPagesError
    pages: set[int] = set()
    for part in parts:
        first, last = _read_range(part, page_count)
        pages.update(range(first, last + 1))
    return [page - 1 for page in sorted(pages)]


def _read_range(part: str, page_count: int) -> tuple[int, int]:
    """The first and last page numbers of one part of the list, checked against the document."""
    match = RANGE_PATTERN.fullmatch(part)
    if match is None or (match.group(3) and not match.group(2)):
        raise InvalidFormatError(part)
    first = int(match.group(1))
    last = (int(match.group(3)) if match.group(3) else page_count) if match.group(2) else first
    if not 1 <= first <= page_count:
        raise MissingPageError(first, page_count)
    if last < first:
        raise InvalidRangeError(part)
    if last > page_count:
        raise MissingPageError(last, page_count)
    return first, last


def format_page_ranges(positions: Iterable[int]) -> str:
    """Return the list of pages for some positions (from 0), joining runs into ranges: "1, 5, 10-12"."""
    numbers = sorted({position + 1 for position in positions})
    parts = []
    start = 0
    while start < len(numbers):
        end = start
        while end + 1 < len(numbers) and numbers[end + 1] == numbers[end] + 1:
            end += 1
        parts.append(f"{numbers[start]}-{numbers[end]}" if end > start else str(numbers[start]))
        start = end + 1
    return ", ".join(parts)


def file_names(base: str, file_count: int, *, separate: bool) -> list[str]:
    """The names of the files extracted, from a base name: "extracted.pdf", or "extracted_01.pdf" and so on."""
    if not separate:
        return [f"{base}.pdf"]
    digits = max(MIN_NAME_DIGITS, len(str(file_count)))
    return [f"{base}_{number:0{digits}d}.pdf" for number in range(1, file_count + 1)]


def free_name(name: str, taken: Iterable[str]) -> str:
    """A name not taken, like the given one: "extracted.pdf", or else "extracted (2).pdf", and so on."""
    used = set(taken)
    stem = name.removesuffix(".pdf")
    candidate, number = name, 2
    while candidate in used:
        candidate = f"{stem} ({number}).pdf"
        number += 1
    return candidate
