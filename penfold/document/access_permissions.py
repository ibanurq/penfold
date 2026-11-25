"""What a PDF allows: the user access permissions of an encrypted PDF opened without a password.

Each tool of Penfold depends on one permission, and is off without it. Saving keeps the encryption and the
permissions as they are (saving.py), so Penfold never lifts a permission.
"""

from dataclasses import dataclass, fields

import pikepdf


@dataclass(frozen=True)
class AccessPermissions:
    """The permissions of a PDF; a PDF that is not encrypted allows everything."""

    print: bool = True
    """Print."""
    fill_forms: bool = True
    """Fill in form fields."""
    annotate: bool = True
    """Add, change and delete annotations."""
    assemble: bool = True
    """Turn, delete, move and add pages, edit bookmarks, and extract pages."""
    copy: bool = True
    """Select and copy text."""
    modify: bool = True
    """Change the rest of the content: flatten the form."""

    @classmethod
    def of(cls, pdf: pikepdf.Pdf) -> "AccessPermissions":
        """Read what a PDF allows."""
        if not pdf.is_encrypted:
            return cls()
        allow = pdf.allow
        return cls(
            print=allow.print_lowres or allow.print_highres,
            fill_forms=allow.modify_form,
            annotate=allow.modify_annotation,
            assemble=allow.modify_assembly,
            copy=allow.extract,
            modify=allow.modify_other,
        )

    @property
    def denies_anything(self) -> bool:
        """Whether the PDF denies something."""
        return not all(getattr(self, field.name) for field in fields(self))

    @property
    def denied(self) -> list[str]:
        """The names of the permissions denied, in the order of the class."""
        return [field.name for field in fields(self) if not getattr(self, field.name)]
