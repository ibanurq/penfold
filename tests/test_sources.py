"""Source PDFs: private copies, and every page of every source numbered by its source index (D44, phase 4)."""

from pathlib import Path

import pytest

from penfold.document.sources import SourceFile, Sources, SourceSpan, count_pages, locate
from penfold.errors import AssemblyNotAllowedError, DocumentOpenError
from tests.sample_pdfs import make_pdf, make_pdf_with_permissions

SPANS = (SourceSpan(Path("a.pdf"), 0, 3), SourceSpan(Path("b.pdf"), 3, 2), SourceSpan(Path("c.pdf"), 5, 1))


@pytest.mark.parametrize(
    ("source_index", "expected"), [(0, (0, 0)), (2, (0, 2)), (3, (1, 0)), (4, (1, 1)), (5, (2, 0))]
)
def test_a_source_index_tells_the_pdf_and_its_page(source_index: int, expected: tuple[int, int]) -> None:
    assert locate(SPANS, source_index) == expected


@pytest.mark.parametrize("source_index", [-1, 6])
def test_a_page_of_no_source_is_refused(source_index: int) -> None:
    with pytest.raises(IndexError):
        locate(SPANS, source_index)


def test_added_pdfs_are_copied_and_numbered_after_the_others(tmp_path: Path) -> None:
    opened = make_pdf(tmp_path / "opened.pdf", page_count=3)
    sources = Sources(SourceFile(opened))
    first = sources.add(SourceFile(make_pdf(tmp_path / "first.pdf", page_count=2)))
    second = sources.add(SourceFile(make_pdf(tmp_path / "second.pdf", page_count=4)))
    assert [(span.start, span.page_count) for span in sources.spans] == [(0, 3), (3, 2), (5, 4)]
    assert sources.spans[1:] == (first, second)
    assert first.path.parent != tmp_path  # a private copy
    assert len(sources.pdf(2).pages) == 4
    sources.close()
    assert not first.path.exists()
    assert not sources.spans[0].path.exists()


def test_pages_are_counted_before_merging(tmp_path: Path) -> None:
    assert count_pages(make_pdf(tmp_path / "four.pdf", page_count=4), respect_permissions=True) == 4
    with pytest.raises(DocumentOpenError):
        count_pages(tmp_path / "missing.pdf", respect_permissions=True)


def test_pdfs_that_deny_assembling_are_counted_only_with_permissions_ignored(tmp_path: Path) -> None:
    locked = make_pdf(tmp_path / "locked.pdf", page_count=3, passwords=("owner", ""))
    with pytest.raises(AssemblyNotAllowedError):
        count_pages(locked, respect_permissions=True)
    assert count_pages(locked, respect_permissions=False) == 3
    allowed = make_pdf_with_permissions(tmp_path / "allowed.pdf", "modify_assembly")
    assert count_pages(allowed, respect_permissions=True) == 3


def test_pdfs_that_need_a_password_cannot_be_merged_yet(tmp_path: Path) -> None:
    protected = make_pdf(tmp_path / "protected.pdf", passwords=("owner", "user"))
    for respect in (True, False):
        with pytest.raises(AssemblyNotAllowedError):
            count_pages(protected, respect_permissions=respect)
