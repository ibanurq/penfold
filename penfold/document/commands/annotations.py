"""Annotation edits: making (H1 to H4) and deleting annotations (H9), edits that can be undone like any other (D19)."""

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


class DeleteAnnotations:
    """Delete annotations of the document, those made in Penfold or read from the PDF (H9, D72), as one edit."""

    changes = Change.ANNOTATIONS

    def __init__(self, document: OpenDocument, annotations: Iterable[Annotation]) -> None:
        """Prepare the deletion of annotations of the document.

        Raises:
            ValueError: none is given, or one is not in the document.
        """
        chosen = {id(annotation) for annotation in annotations}
        if not chosen:
            message = "no annotations given"
            raise ValueError(message)
        # Where each one is, to put it back in its place.
        self._places = [
            (place, annotation) for place, annotation in enumerate(document.annotations) if id(annotation) in chosen
        ]
        if len(self._places) != len(chosen):
            message = "an annotation to delete is not in the document"
            raise ValueError(message)
        self._document = document

    @property
    def annotations(self) -> list[Annotation]:
        """The annotations deleted, in the order of the document."""
        return [annotation for _place, annotation in self._places]

    def apply(self) -> None:
        """Take the annotations away."""
        deleted = {id(annotation) for annotation in self.annotations}
        self._document.annotations = [item for item in self._document.annotations if id(item) not in deleted]

    def revert(self) -> None:
        """Put them back where they were."""
        annotations = list(self._document.annotations)
        for place, annotation in self._places:
            annotations.insert(place, annotation)
        self._document.annotations = annotations
