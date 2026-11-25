"""Annotation edits: making, changing and deleting them.

Each is an edit that can be undone like any other.
"""

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
    """Delete annotations of the document, those made in Penfold or read from the PDF, as one edit."""

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


class ChangeAnnotation:
    """Put a changed copy of an annotation in its place: another colour, format, text, place or size.

    The copy is managed: Penfold draws it and writes it when the document is saved. One read from a PDF keeps its
    origin, so that saving takes the original out of its page; or else it was only moved, keeping its drawing, and
    saving moves it in its page.
    """

    changes = Change.ANNOTATIONS

    def __init__(self, document: OpenDocument, annotation: Annotation, changed: Annotation) -> None:
        """Prepare the change of an annotation of the document.

        Raises:
            ValueError: the annotation is not in the document, or the copy is not a managed copy of it.
        """
        if not any(item is annotation for item in document.annotations):
            message = "the annotation to change is not in the document"
            raise ValueError(message)
        self._document = document
        self.annotation = annotation
        self.changed = self._checked(changed)

    def apply(self) -> None:
        """Put the changed copy in the annotation's place."""
        self._swap(self.annotation, self.changed)

    def revert(self) -> None:
        """Put the annotation back as it was."""
        self._swap(self.changed, self.annotation)

    def retouch(self, changed: Annotation) -> None:
        """Change the copy again while it is being edited (Format…); use it through OpenDocument.amend.

        Raises:
            ValueError: the copy is not a managed copy of the annotation.
        """
        current, self.changed = self.changed, self._checked(changed)
        self._swap(current, self.changed)

    def _checked(self, changed: Annotation) -> Annotation:
        if not changed.managed and not changed.moved_as_is:
            message = "a changed annotation is drawn and written by Penfold, unless it was only moved"
            raise ValueError(message)
        before = self.annotation
        if (changed.page, changed.kind, changed.origin) != (before.page, before.kind, before.origin):
            message = "a changed annotation keeps its page, kind and origin"
            raise ValueError(message)
        return changed

    def _swap(self, old: Annotation, new: Annotation) -> None:
        self._document.annotations = [new if item is old else item for item in self._document.annotations]
