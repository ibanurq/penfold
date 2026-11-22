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
        # The annotations hidden on each page, by source index: by their subtype and drawn place, with their flags
        # before.
        self._hidden: dict[int, dict[tuple[str, int], tuple[Poppler.Annot, Poppler.AnnotFlag]]] = {}

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

    def hide_annotations(self, source_index: int, hidden: Mapping[tuple[str, int], str]) -> None:
        """Leave out these annotations of a page when it is drawn, and show again those left out before.

        They are named by their subtype ("StrikeOut") and drawn place (document/annotations.py), with their unique
        name (/NM), if any, which is looked for first.
        """
        before = self._hidden.get(source_index, {})
        if not hidden and not before:
            return
        for key in set(before) - set(hidden):
            annotation, flags = before.pop(key)
            annotation.set_flags(flags)
        of_type: dict[str, list[Poppler.Annot]] = {}
        for mapping in self.page(source_index).get_annot_mapping():
            nick = mapping.annot.get_annot_type().value_nick.replace("-", "")
            of_type.setdefault(nick, []).append(mapping.annot)
        for key, name in hidden.items():
            subtype, place = key
            found = None if key in before else _find(of_type.get(subtype.lower(), []), place, name)
            if found is not None:
                flags = found.get_flags()
                found.set_flags(flags | Poppler.AnnotFlag.HIDDEN)
                before[key] = (found, flags)
        self._hidden[source_index] = before


def _find(annotations: list[Poppler.Annot], place: int, name: str) -> Poppler.Annot | None:
    """The annotation of a type with this name, or else the one at this place among them."""
    if name:
        named = [annotation for annotation in annotations if annotation.get_name() == name]
        if len(named) == 1:
            return named[0]
    return annotations[place] if place < len(annotations) else None
