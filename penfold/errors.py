"""Errors that Penfold explains to the user.

Every error raised on purpose derives from PenfoldError, so the interface can tell them apart from programming errors.
"""


class PenfoldError(Exception):
    """An expected problem that Penfold reports to the user."""


class DocumentOpenError(PenfoldError):
    """The file could not be opened as a PDF (missing, unreadable or damaged)."""


class PasswordRequiredError(DocumentOpenError):
    """The PDF needs a password to be opened, which Penfold does not support until 1.2."""


class RestrictedPdfError(PenfoldError):
    """The PDF is encrypted (with restrictions), so its pages cannot be added to another or merged (2.7, D59).

    They would end up in a file without its encryption.
    """


class SaveError(PenfoldError):
    """The PDF could not be saved; the file that was there is left as it was."""
