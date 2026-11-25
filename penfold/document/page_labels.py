"""Page labels: the page names a PDF shows instead of its numbers (i, ii, 1, 2, A-1…).

They are stored in the /PageLabels number tree of the catalog (ISO 32000-1, 12.4.2). Each entry starts a range at a page
index and gives a numbering style, a prefix and the first number of the range. Penfold reads the label of every page
and, on saving, writes the ranges again for the pages in their new order.
"""

from dataclasses import dataclass

import pikepdf

ROMAN_NUMERALS = (
    (1000, "m"),
    (900, "cm"),
    (500, "d"),
    (400, "cd"),
    (100, "c"),
    (90, "xc"),
    (50, "l"),
    (40, "xl"),
    (10, "x"),
    (9, "ix"),
    (5, "v"),
    (4, "iv"),
    (1, "i"),
)
LETTERS_IN_ALPHABET = 26


@dataclass(frozen=True)
class PageLabel:
    """The label of one page: its numbering style (D, R, r, A, a, or None for the prefix alone), prefix and number."""

    style: str | None = "D"
    prefix: str = ""
    number: int = 1

    @property
    def text(self) -> str:
        """The label as it is shown."""
        return self.prefix + format_number(self.number, self.style)

    def follows(self, previous: "PageLabel") -> bool:
        """Whether a range that gives the previous page its label gives this one to the next page."""
        if self.style != previous.style or self.prefix != previous.prefix:
            return False
        return self.style is None or self.number == previous.number + 1


@dataclass(frozen=True)
class LabelRange:
    """One entry of /PageLabels: the pages from first_page on, up to the next range."""

    first_page: int
    style: str | None = None
    prefix: str = ""
    start: int = 1

    def label(self, page_index: int) -> PageLabel:
        """Return the label of a page of this range, given its index in the document."""
        return PageLabel(self.style, self.prefix, self.start + page_index - self.first_page)


def format_number(number: int, style: str | None) -> str:
    """Write a page number in a /PageLabels numbering style (D, R, r, A, a, or none)."""
    if style == "D":
        return str(number)
    if style in {"R", "r"}:
        roman = to_roman(number)
        return roman.upper() if style == "R" else roman
    if style in {"A", "a"}:
        letters = to_letters(number)
        return letters if style == "A" else letters.lower()
    return ""


def to_roman(number: int) -> str:
    """Write a positive number in lowercase Roman numerals."""
    numerals = []
    for value, numeral in ROMAN_NUMERALS:
        count, number = divmod(number, value)
        numerals.append(numeral * count)
    return "".join(numerals)


def to_letters(number: int) -> str:
    """Write a positive number as the standard asks: A to Z, then AA to ZZ, then AAA to ZZZ, and so on."""
    repetitions, position = divmod(number - 1, LETTERS_IN_ALPHABET)
    return chr(ord("A") + position) * (repetitions + 1)


def read_label_ranges(pdf: pikepdf.Pdf) -> list[LabelRange]:
    """Read the label ranges of a PDF, sorted by their first page; an empty list if it has none.

    Entries that break the standard (outside the document, with the wrong types) are left out, as other viewers do.
    """
    if "/PageLabels" not in pdf.Root:
        return []
    page_count = len(pdf.pages)
    ranges = []
    for first_page, entry in pikepdf.NumberTree(pdf.Root.PageLabels).items():
        if not 0 <= first_page < page_count or not isinstance(entry, pikepdf.Dictionary):
            continue
        style = entry.get("/S")
        prefix = entry.get("/P")
        start = entry.get("/St")
        ranges.append(
            LabelRange(
                first_page=first_page,
                style=str(style)[1:] if isinstance(style, pikepdf.Name) else None,
                prefix=str(prefix) if isinstance(prefix, pikepdf.String) else "",
                start=_positive_integer(start),
            )
        )
    return sorted(ranges, key=lambda label_range: label_range.first_page)


def _positive_integer(value: object) -> int:
    """Return a range's first number if it is valid (an integer from 1 on), otherwise 1, the default."""
    if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
        return value
    return 1


def read_page_labels(pdf: pikepdf.Pdf) -> list[PageLabel] | None:
    """Return the label of every page, or None if the PDF has no page labels.

    Pages before the first range have no label of their own: they are named by their number.
    """
    ranges = read_label_ranges(pdf)
    if not ranges:
        return None
    labels = []
    current: LabelRange | None = None
    remaining = iter(ranges)
    upcoming = next(remaining, None)
    for page_index in range(len(pdf.pages)):
        while upcoming is not None and upcoming.first_page == page_index:
            current, upcoming = upcoming, next(remaining, None)
        labels.append(current.label(page_index) if current else PageLabel(number=page_index + 1))
    return labels


def write_page_labels(pdf: pikepdf.Pdf, labels: list[PageLabel]) -> None:
    """Replace the page labels of a PDF with these, one per page, grouped in as few ranges as possible."""
    numbers: list[int | pikepdf.Dictionary] = []
    previous: PageLabel | None = None
    for page_index, label in enumerate(labels):
        if previous is None or not label.follows(previous):
            numbers += [page_index, _range_entry(label)]
        previous = label
    pdf.Root.PageLabels = pikepdf.Dictionary(Nums=pikepdf.Array(numbers))


def _range_entry(label: PageLabel) -> pikepdf.Dictionary:
    """The /PageLabels entry of a range that starts with this label, leaving out what is the default."""
    entry = pikepdf.Dictionary()
    if label.style is not None:
        entry.S = pikepdf.Name(f"/{label.style}")
        if label.number != 1:
            entry.St = label.number
    if label.prefix:
        entry.P = pikepdf.String(label.prefix)
    return entry
