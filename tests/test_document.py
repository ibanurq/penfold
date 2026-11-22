"""Opening a PDF in the document layer: title, pages, labels and protection."""

from pathlib import Path

import pikepdf
import pytest

from penfold.document.access_permissions import AccessPermissions
from penfold.document.document import OpenDocument
from penfold.document.history import Change
from penfold.errors import DocumentOpenError, PasswordRequiredError
from tests.sample_pdfs import PERMISSIONS, make_pdf, make_pdf_with_permissions


@pytest.fixture
def labelled_document(tmp_path: Path) -> OpenDocument:
    path = make_pdf(
        tmp_path / "book.pdf",
        page_count=5,
        title="  A Book  ",
        label_ranges=[(0, pikepdf.Dictionary(S=pikepdf.Name.r)), (2, pikepdf.Dictionary(S=pikepdf.Name.D))],
    )
    return OpenDocument.open(path)


def test_opens_a_pdf_and_reads_what_the_header_shows(labelled_document: OpenDocument) -> None:
    assert labelled_document.file_name == "book.pdf"
    assert labelled_document.title == "A Book"
    assert labelled_document.page_count == 5
    assert labelled_document.has_page_labels
    assert [labelled_document.page_label(index) for index in range(5)] == ["i", "ii", "1", "2", "3"]
    assert not labelled_document.denies_anything


def test_without_title_or_labels(tmp_path: Path) -> None:
    document = OpenDocument.open(make_pdf(tmp_path / "plain.pdf", title=" "))
    assert document.title is None
    assert not document.has_page_labels
    assert document.page_label(2) == "3"


@pytest.mark.parametrize(
    ("typed", "expected"),
    [("ii", 1), ("II", 1), ("1", 2), (" 3 ", 4), ("5", 4), ("6", None), ("x", None), ("", None), ("0", None)],
)
def test_page_box_finds_labels_before_numbers(
    labelled_document: OpenDocument, typed: str, expected: int | None
) -> None:
    assert labelled_document.find_page(typed) == expected


@pytest.mark.parametrize(("typed", "expected"), [("1", 0), ("3", 2), ("4", None), ("-1", None), ("²", None)])
def test_page_box_finds_numbers_without_labels(tmp_path: Path, typed: str, expected: int | None) -> None:
    document = OpenDocument.open(make_pdf(tmp_path / "plain.pdf"))
    assert document.find_page(typed) == expected


def test_encrypted_pdf_without_open_password_opens_with_its_permissions(tmp_path: Path) -> None:
    document = OpenDocument.open(make_pdf_with_permissions(tmp_path / "locked.pdf", "print_lowres", "modify_form"))
    assert document.denies_anything
    assert document.access_permissions == AccessPermissions(annotate=False, assemble=False, copy=False, modify=False)
    assert document.access_permissions.denied == ["annotate", "assemble", "copy", "modify"]
    assert document.page_count == 3


def test_an_encrypted_pdf_that_allows_everything_denies_nothing(tmp_path: Path) -> None:
    document = OpenDocument.open(make_pdf_with_permissions(tmp_path / "open.pdf", *PERMISSIONS))
    assert not document.denies_anything


def test_pdf_with_open_password_is_refused(tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "secret.pdf", passwords=("owner", "user"))
    with pytest.raises(PasswordRequiredError):
        OpenDocument.open(path)


@pytest.mark.parametrize("content", [None, b"", b"not a PDF at all"])
def test_missing_or_damaged_file_is_reported(tmp_path: Path, content: bytes | None) -> None:
    path = tmp_path / "broken.pdf"
    if content is not None:
        path.write_bytes(content)
    with pytest.raises(DocumentOpenError):
        OpenDocument.open(path)


def test_labels_follow_the_pages_when_they_move(labelled_document: OpenDocument) -> None:
    labelled_document.pages.reverse()
    assert [labelled_document.page_label(index) for index in range(5)] == ["3", "2", "1", "ii", "i"]
    assert labelled_document.find_page("ii") == 3


def test_pages_without_labels_are_named_by_their_position(tmp_path: Path) -> None:
    document = OpenDocument.open(make_pdf(tmp_path / "plain.pdf"))
    del document.pages[0]
    assert document.page_count == 2
    assert [document.page_label(index) for index in range(2)] == ["1", "2"]


def test_a_document_that_ignores_permissions_allows_everything_and_says_so(tmp_path: Path) -> None:
    document = OpenDocument.open(make_pdf_with_permissions(tmp_path / "locked.pdf"))
    changes: list[Change] = []
    document.add_listener(changes.append)
    document.respect_permissions(False)
    assert (document.permissions, document.denies_anything) == (AccessPermissions(), False)
    assert document.access_permissions.denied == ["print", "fill_forms", "annotate", "assemble", "copy", "modify"]
    document.respect_permissions(False)
    document.respect_permissions(True)
    assert document.denies_anything
    assert changes == [Change.PERMISSIONS, Change.PERMISSIONS]
    document.close()
