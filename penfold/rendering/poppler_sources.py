"""The source PDFs of a document read with Poppler: the page of each source index (document/sources.py)."""

from collections.abc import Callable, Mapping

from gi.repository import GLib, Poppler

from penfold.document.sources import Spans, locate


class PopplerSources:
    """Poppler's copies of the source PDFs, for one thread, each opened when one of its pages is first needed.

    A Poppler document must not be shared between threads, so every thread that reads pages has its own.
    """

    def __init__(self, spans: Callable[[], Spans]) -> None:
        """Read the sources that a function gives; they may grow as PDFs are added to the document."""
        self._spans = spans
        self._documents: dict[str, Poppler.Document] = {}
        # The annotations hidden on each page, by source index: their drawn place and their flags before.
        self._hidden: dict[int, dict[int, tuple[Poppler.Annot, Poppler.AnnotFlag]]] = {}

    def page(self, source_index: int) -> Poppler.Page:
        """The page with this source index.

        Raises:
            GLib.Error: Poppler cannot open its PDF.
        """
        document, start = self.document(source_index)
        return document.get_page(source_index - start)

    def document(self, source_index: int) -> tuple[Poppler.Document, int]:
        """The PDF a page comes from, and the source index of that PDF's first page.

        Raises:
            GLib.Error: Poppler cannot open the PDF.
        """
        spans = self._spans()
        span = spans[locate(spans, source_index)[0]]
        uri = GLib.filename_to_uri(str(span.path.resolve()), None)
        if uri not in self._documents:
            self._documents[uri] = Poppler.Document.new_from_file(uri, span.password or None)
        return self._documents[uri], span.start

    def hide_annotations(self, source_index: int, hidden: Mapping[int, str]) -> None:
        """Leave out these annotations of a page when it is drawn, and show again those left out before.

        They are named by their drawn place (document/annotations.py) and their subtype ("StrikeOut"); one whose type
        does not match is left as it is, rather than hide another.
        """
        before = self._hidden.get(source_index, {})
        if not hidden and not before:
            return
        for place in set(before) - set(hidden):
            annotation, flags = before.pop(place)
            annotation.set_flags(flags)
        annotations = [mapping.annot for mapping in self.page(source_index).get_annot_mapping()]
        for place, subtype in hidden.items():
            if place in before or place >= len(annotations):
                continue
            annotation = annotations[place]
            if annotation.get_annot_type().value_nick.replace("-", "") != subtype.lower():
                continue
            flags = annotation.get_flags()
            annotation.set_flags(flags | Poppler.AnnotFlag.HIDDEN)
            before[place] = (annotation, flags)
        self._hidden[source_index] = before
