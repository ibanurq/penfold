"""PDFs with an open password: opened with it, drawn, and saved or extracted keeping passwords and permissions."""

from pathlib import Path

import pikepdf
import pytest

from penfold.document.commands.pages import RotatePages
from penfold.document.document import OpenDocument
from penfold.document.saving import save
from penfold.errors import PasswordRequiredError
from penfold.rendering.poppler_sources import PopplerSources
from tests.sample_pdfs import OWNER_PASSWORD, USER_PASSWORD, make_pdf_with_password, make_pdf_with_permissions


@pytest.fixture
def secret(tmp_path: Path) -> Path:
    return make_pdf_with_password(tmp_path / "secret.pdf", "print_lowres", "modify_form", page_count=4)


def test_it_needs_its_password(secret: Path) -> None:
    for password in ("", "wrong"):
        with pytest.raises(PasswordRequiredError):
            OpenDocument.open(secret, password)


def test_it_opens_with_its_password_and_its_pages_are_drawn(secret: Path) -> None:
    document = OpenDocument.open(secret, USER_PASSWORD)
    assert document.page_count == 4
    assert document.access_permissions.denied == ["annotate", "assemble", "copy", "modify"]
    assert PopplerSources(lambda: document.sources.spans).page(0) is not None
    assert USER_PASSWORD not in repr(document.sources.spans)  # never shown in a log
    document.close()


def assert_keeps_passwords_and_permissions(path: Path, page_count: int) -> None:
    with pytest.raises(pikepdf.PasswordError):
        pikepdf.open(path)
    for password in (USER_PASSWORD, OWNER_PASSWORD):
        with pikepdf.open(path, password=password) as pdf:
            assert len(pdf.pages) == page_count
            assert (pdf.allow.print_lowres, pdf.allow.modify_form, pdf.allow.modify_assembly) == (True, True, False)


def test_saving_keeps_its_passwords_and_permissions(secret: Path) -> None:
    document = OpenDocument.open(secret, USER_PASSWORD)
    document.respect_permissions(False)
    document.execute(RotatePages(document, [0], 90))
    plan = document.save_plan()
    save(plan)
    document.mark_saved(plan)
    assert_keeps_passwords_and_permissions(secret, 4)
    document.close()


def test_save_as_and_extracting_keep_its_passwords_and_permissions(secret: Path, tmp_path: Path) -> None:
    document = OpenDocument.open(secret, USER_PASSWORD)
    document.respect_permissions(False)
    save(document.save_plan(tmp_path / "copy.pdf"))
    assert_keeps_passwords_and_permissions(tmp_path / "copy.pdf", 4)
    save(document.extract_plan([1, 2], tmp_path / "extracted.pdf"))
    assert_keeps_passwords_and_permissions(tmp_path / "extracted.pdf", 2)
    document.close()


def test_the_pdf_to_print_keeps_its_password(secret: Path, tmp_path: Path) -> None:
    document = OpenDocument.open(secret, USER_PASSWORD)
    save(document.print_plan(tmp_path / "print.pdf", frozenset()))
    with pikepdf.open(tmp_path / "print.pdf", password=USER_PASSWORD) as pdf:
        assert len(pdf.pages) == 4
    document.close()


def test_the_owner_password_allows_everything_and_saving_keeps_both_passwords(secret: Path) -> None:
    document = OpenDocument.open(secret, OWNER_PASSWORD)
    assert document.opened_by_owner
    assert not document.denies_anything
    assert document.access_permissions.denied == ["annotate", "assemble", "copy", "modify"]  # what others get
    document.execute(RotatePages(document, [0], 90))
    plan = document.save_plan()
    save(plan)
    document.mark_saved(plan)
    assert_keeps_passwords_and_permissions(secret, 4)
    document.close()


def test_the_open_password_is_not_the_owners(secret: Path, tmp_path: Path) -> None:
    document = OpenDocument.open(secret, USER_PASSWORD)
    assert (document.opened_by_owner, document.denies_anything) == (False, True)
    document.close()
    locked = OpenDocument.open(make_pdf_with_permissions(tmp_path / "locked.pdf"))
    assert (locked.opened_by_owner, locked.denies_anything) == (False, True)
    locked.close()
