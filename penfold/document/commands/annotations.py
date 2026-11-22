"""Annotation edits: making annotations (H1 to H4), an edit that can be undone like any other (D19, D65)."""

from collections.abc import Iterable

from penfold.document.annotations import Annotation
from penfold.document.document import OpenDocument
from penfold.document.history import Change


class AddAnnotations:
    """Add annotations made in Penfold to pages of the document, as one edit (a highlight over several pages)."""

    changes = Change.ANNOTATIONS

    def __init__(self, document: OpenDocument, annotations: Iterable[Annotation]) -> None:
        """Prepare the addition of new annotations.

        Raises:
            ValueError: none is given, one is not managed by Penfold, or its page is not in the document.
        """
        self.annotations = list(annotations)
        if not self.annotations:
            message = "no annotations given"
            raise ValueError(message)
        for annotation in self.annotations:
            if not annotation.managed:
                message = "only annotations made in Penfold can be added"
                raise ValueError(message)
            if document.page_position(annotation.page) is None:
                message = f"page {annotation.page} is not in the document"
                raise ValueError(message)
        self._document = document

    def apply(self) -> None:
        """Put the annotations on their pages."""
        self._document.annotations = [*self._document.annotations, *self.annotations]

    def revert(self) -> None:
        """Take them away again."""
        added = {id(annotation) for annotation in self.annotations}
        self._document.annotations = [item for item in self._document.annotations if id(item) not in added]
