"""Source PDFs: the files whose pages make up the open document, read with pikepdf.

A document is read from a private copy of its file, taken when it is opened. Saving over the file then leaves the
pages Penfold reads as they were: the edits, and undoing them after saving, still refer to the PDF as it was opened.
"""

import shutil
import tempfile
import weakref
from pathlib import Path

import pikepdf

from penfold.errors import DocumentOpenError, PasswordRequiredError

COPY_NAME = "source.pdf"


class SourceFile:
    """A private copy of a PDF as it was opened, and the PDF read from it with pikepdf.

    The copy lives in a temporary folder that only the user can read, removed when the source is closed (or, if
    Penfold stops before, when Python exits).
    """

    def __init__(self, path: Path) -> None:
        """Copy a PDF and open the copy.

        Raises:
            PasswordRequiredError: the PDF needs a password to be opened.
            DocumentOpenError: the file is missing, unreadable or not a PDF.
        """
        folder = Path(tempfile.mkdtemp(prefix="penfold-"))
        self._remove_folder = weakref.finalize(self, shutil.rmtree, folder, ignore_errors=True)
        self.path = folder / COPY_NAME
        try:
            shutil.copyfile(path, self.path)
            self.pdf = open_source(self.path)
        except DocumentOpenError:
            self._remove_folder()
            raise
        except OSError as error:
            self._remove_folder()
            raise DocumentOpenError(str(path)) from error

    def close(self) -> None:
        """Release the PDF and remove the copy."""
        self.pdf.close()
        self._remove_folder()


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
