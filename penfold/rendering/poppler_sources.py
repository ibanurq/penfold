"""The source PDFs of a document read with Poppler: the page of each source index (document/sources.py)."""

from collections.abc import Callable

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
