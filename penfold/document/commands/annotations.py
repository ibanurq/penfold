"""Annotation edits: making an annotation (H1 to H4), an edit that can be undone like any other (D19, D65)."""

from penfold.document.annotations import Annotation
from penfold.document.document import OpenDocument
from penfold.document.history import Change


class AddAnnotation:
    """Add an annotation made in Penfold to a page of the document."""

    changes = Change.ANNOTATIONS

    def __init__(self, document: OpenDocument, annotation: Annotation) -> None:
        """Prepare the addition of a new annotation.

        Raises:
            ValueError: the annotation is not managed by Penfold, or its page is not in the document.
        """
        if not annotation.managed:
            message = "only annotations made in Penfold can be added"
            raise ValueError(message)
        if document.page_position(annotation.page) is None:
            message = f"page {annotation.page} is not in the document"
            raise ValueError(message)
        self._document = document
        self.annotation = annotation

    def apply(self) -> None:
        """Put the annotation on its page."""
        self._document.annotations = [*self._document.annotations, self.annotation]

    def revert(self) -> None:
        """Take it away again."""
        self._document.annotations = [item for item in self._document.annotations if item is not self.annotation]
