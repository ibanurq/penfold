"""Reading page labels (ISO 32000-1, 12.4.2; D14)."""

from pathlib import Path

import pikepdf
import pytest

from penfold.document.page_labels import format_number, page_labels, to_letters, to_roman
from tests.sample_pdfs import make_pdf


def labels_of(path: Path) -> list[str] | None:
    with pikepdf.open(path) as pdf:
        return page_labels(pdf)


@pytest.mark.parametrize(
    ("number", "expected"),
    [(1, "i"), (4, "iv"), (9, "ix"), (14, "xiv"), (40, "xl"), (90, "xc"), (400, "cd"), (1994, "mcmxciv")],
)
def test_roman_numerals(number: int, expected: str) -> None:
    assert to_roman(number) == expected


@pytest.mark.parametrize(("number", "expected"), [(1, "A"), (26, "Z"), (27, "AA"), (28, "BB"), (53, "AAA")])
def test_letters_double_after_z(number: int, expected: str) -> None:
    assert to_letters(number) == expected


@pytest.mark.parametrize(
    ("style", "expected"), [("D", "12"), ("R", "XII"), ("r", "xii"), ("A", "L"), ("a", "l"), (None, "")]
)
def test_numbering_styles(style: str | None, expected: str) -> None:
    assert format_number(12, style) == expected


def test_pdf_without_labels_has_none(tmp_path: Path) -> None:
    assert labels_of(make_pdf(tmp_path / "plain.pdf")) is None


def test_ranges_with_style_prefix_and_start(tmp_path: Path) -> None:
    path = make_pdf(
        tmp_path / "labels.pdf",
        page_count=7,
        label_ranges=[
            (0, pikepdf.Dictionary(S=pikepdf.Name.r)),
            (2, pikepdf.Dictionary(S=pikepdf.Name.D)),
            (4, pikepdf.Dictionary(S=pikepdf.Name.D, P=pikepdf.String("A-"), St=8)),
            (6, pikepdf.Dictionary(P=pikepdf.String("Cover"))),
        ],
    )
    assert labels_of(path) == ["i", "ii", "1", "2", "A-8", "A-9", "Cover"]


def test_pages_before_the_first_range_are_numbered(tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "late.pdf", page_count=4, label_ranges=[(2, pikepdf.Dictionary(S=pikepdf.Name.a))])
    assert labels_of(path) == ["1", "2", "a", "b"]


def test_entries_outside_the_document_or_of_the_wrong_type_are_ignored(tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "broken.pdf", page_count=2, label_ranges=[(0, pikepdf.Dictionary(S=pikepdf.Name.R))])
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        roman, decimal = pikepdf.Dictionary(S=pikepdf.Name.R), pikepdf.Dictionary(S=pikepdf.Name.D)
        pdf.Root.PageLabels.Nums = pikepdf.Array([0, roman, 5, decimal, 1, pikepdf.Array([1])])
        pdf.save(path)
    assert labels_of(path) == ["I", "II"]
