"""Source PDFs: the files whose pages make up the open document, read with pikepdf."""

from pathlib import Path

import pikepdf

from penfold.errors import DocumentOpenError, PasswordRequiredError


def open_source(path: Path) -> pikepdf.Pdf:
    """Open a PDF for reading; the file itself is never changed here.

    Raises:
        PasswordRequiredError: the PDF needs a password to be opened.
        DocumentOpenError: the file is missing, unreadable or not a PDF.
    """
    try:
        return pikepdf.open(path)
    except pikepdf.PasswordError as error:
        raise PasswordRequiredError(str(path)) from error
    except (pikepdf.PdfError, OSError, ValueError) as error:
        raise DocumentOpenError(str(path)) from error
