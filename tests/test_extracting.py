"""Extracting pages: reading the list of pages, naming the files and writing them (E7 to E9, D51)."""

from pathlib import Path

import pikepdf
import pytest

from penfold.document.commands.pages import RotatePages
from penfold.document.document import OpenDocument
from penfold.document.extracting import (
    InvalidFormatError,
    InvalidRangeError,
    MissingPageError,
    NoPagesError,
    PageRangeError,
    file_names,
    format_page_ranges,
    free_name,
    parse_page_ranges,
)
from penfold.document.saving import save
from tests.test_saving import make_rich_pdf, widths


@pytest.mark.parametrize(
    ("text", "positions"),
    [
        ("1, 5, 10-12, 56-", [0, 4, 9, 10, 11, 55, 56, 57, 58, 59]),
        ("3", [2]),
        (" 7 - 9 ;2", [1, 6, 7, 8]),
        ("2, 2, 1-3", [0, 1, 2]),  # without repeats, in order
        ("60-", [59]),
    ],
)
def test_lists_of_pages_are_read_as_0_6_reads_them(text: str, positions: list[int]) -> None:
    assert parse_page_ranges(text, 60) == positions


@pytest.mark.parametrize(
    ("text", "error"),
    [
        (" , ", NoPagesError()),
        ("a", InvalidFormatError("a")),
        ("3 4", InvalidFormatError("3 4")),
        ("5-2", InvalidRangeError("5-2")),
        ("0", MissingPageError(0, 60)),
        ("58-61", MissingPageError(61, 60)),
        ("61-", MissingPageError(61, 60)),
    ],
)
def test_wrong_lists_say_what_is_wrong(text: str, error: PageRangeError) -> None:
    with pytest.raises(PageRangeError) as raised:
        parse_page_ranges(text, 60)
    assert type(raised.value) is type(error)
    assert vars(raised.value) == vars(error)


def test_selected_pages_are_written_as_a_list() -> None:
    assert format_page_ranges([0, 4, 9, 10, 11]) == "1, 5, 10-12"
    assert format_page_ranges([]) == ""


def test_file_names() -> None:
    assert file_names("extracted", 3, separate=False) == ["extracted.pdf"]
    assert file_names("extracted", 3, separate=True) == ["extracted_01.pdf", "extracted_02.pdf", "extracted_03.pdf"]
    assert file_names("x", 120, separate=True)[0] == "x_001.pdf"


def test_a_free_name_is_found_like_the_given_one() -> None:
    assert free_name("extracted.pdf", ["other.pdf"]) == "extracted.pdf"
    assert free_name("extracted.pdf", ["extracted.pdf", "extracted (2).pdf"]) == "extracted (3).pdf"


def test_extracted_pages_keep_what_they_hold_and_their_bookmarks(tmp_path: Path) -> None:
    document = OpenDocument.open(make_rich_pdf(tmp_path / "rich.pdf"))
    document.execute(RotatePages(document, [2], 90))
    target = tmp_path / "out" / "extracted.pdf"
    target.parent.mkdir()
    save(document.extract_plan([2, 3, 4], target))
    with pikepdf.open(target) as extracted:
        assert widths(extracted) == [102, 103, 104]
        assert extracted.pages[0].obj.Rotate == 90
        assert extracted.pages[2].obj.Annots[0].Contents == "Hello"  # notes are kept (D51)
        with extracted.open_outline() as outline:
            assert [item.title for item in outline.root] == ["Chapter"]
            assert [item.title for item in outline.root[0].children] == ["Section"]
    reopened = OpenDocument.open(target)
    assert [reopened.page_label(position) for position in range(3)] == ["1", "2", "3"]
    assert document.page_count == 5  # extracting does not change the document
    assert document.last_edit is not None
    assert isinstance(document.last_edit, RotatePages)


def test_protected_pdfs_cannot_have_pages_extracted(tmp_path: Path) -> None:
    from tests.sample_pdfs import make_pdf

    document = OpenDocument.open(make_pdf(tmp_path / "locked.pdf", passwords=("owner", "")))
    with pytest.raises(ValueError, match="protected"):
        document.extract_plan([0], tmp_path / "out.pdf")
