"""Small PDFs built on the fly for the tests, so the repository needs no binary test files for these cases."""

from pathlib import Path

import pikepdf

from penfold.document.sources import SourceSpan, Spans

A4 = (595, 842)


def make_pdf(
    path: Path,
    page_count: int = 3,
    *,
    title: str | None = None,
    label_ranges: list[tuple[int, pikepdf.Dictionary]] | None = None,
    passwords: tuple[str, str] | None = None,
) -> Path:
    """Write a PDF with blank A4 pages and return its path.

    Args:
        path: where to write it.
        page_count: number of pages.
        title: the /Title of its document information, if any.
        label_ranges: /PageLabels entries as (first page index, label dictionary).
        passwords: encrypt it with these (owner, user) passwords; an empty user password opens without one.
    """
    pdf = pikepdf.new()
    for _ in range(page_count):
        pdf.add_blank_page(page_size=A4)
    if title is not None:
        pdf.docinfo["/Title"] = title
    if label_ranges is not None:
        numbers = pikepdf.Array([item for label_range in label_ranges for item in label_range])
        pdf.Root.PageLabels = pikepdf.Dictionary(Nums=numbers)
    encryption = pikepdf.Encryption(owner=passwords[0], user=passwords[1]) if passwords else False
    pdf.save(path, encryption=encryption)
    return path


def source_spans(*paths: Path) -> Spans:
    """The sources of a document made of these PDFs, numbered one after another, read from the files themselves."""
    spans: list[SourceSpan] = []
    for path in paths:
        with pikepdf.open(path) as pdf:
            start = spans[-1].start + spans[-1].page_count if spans else 0
            spans.append(SourceSpan(path, start, len(pdf.pages)))
    return tuple(spans)
