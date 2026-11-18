"""Finding text (D13; 0.6's rules: no case, accents or line breaks)."""

from pathlib import Path

import cairo
import pytest
from gi.repository import GLib, Poppler

from penfold.rendering.text_search import MatchContext, TextSearch, find_in_page, match_context, normalize_query
from tests.gtk_helpers import wait_until
from tests.test_page_content import A4, make_text_pdf

LINES = [
    "El plazo de Garantía será de dos años",
    "desde la entrega. La garantia cubre los",
    "defectos de una garantía legal establecida en la normativa vigente del país",
]


@pytest.fixture
def document(tmp_path: Path) -> Poppler.Document:
    """One page with three lines of text, 20 points apart, from 100 points from the top."""
    path = tmp_path / "words.pdf"
    surface = cairo.PDFSurface(str(path), *A4)
    context = cairo.Context(surface)
    context.set_font_size(12)
    for index, line in enumerate(LINES):
        context.move_to(72, 100 + index * 20)
        context.show_text(line)
    surface.finish()
    return Poppler.Document.new_from_file(GLib.filename_to_uri(str(path), None), None)


def test_runs_of_spaces_count_as_one() -> None:
    assert normalize_query("  dos\n  años ") == "dos años"


def test_ignores_case_and_accents(document: Poppler.Document) -> None:
    results = find_in_page(document.get_page(0), 0, "GARANTIA")
    assert len(results) == 3
    assert [result.page for result in results] == [0, 0, 0]
    left, top, right, bottom = results[0].rectangles[0]
    assert top < 100 <= bottom  # the boxes are measured from the top of the page
    assert 72 < left < right


def test_finds_text_across_a_line_break(document: Poppler.Document) -> None:
    results = find_in_page(document.get_page(0), 0, "dos años desde la")
    assert len(results) == 1
    assert len(results[0].rectangles) == 2  # one box per line
    assert results[0].top < 100


def test_the_sentence_around_a_match(document: Poppler.Document) -> None:
    result = find_in_page(document.get_page(0), 0, "garantia legal")[0]
    context = match_context(document, result)
    assert context == MatchContext(before="defectos de una", match="garantía legal", after=context.after)
    assert context.after.startswith("establecida en la")
    assert len(context.after) <= 40
    assert context.after.split()[-1] in LINES[2].split()


def test_searches_a_pdf_in_the_background_from_a_page_on(tmp_path: Path) -> None:
    path = make_text_pdf(tmp_path / "text.pdf")
    search = TextSearch(GLib.filename_to_uri(str(path), None))
    pages: list[int] = []
    finished: list[bool] = []
    search.start(
        "LINE   2", 1, lambda results: pages.extend(item.page for item in results), lambda: finished.append(True)
    )
    wait_until(lambda: bool(finished))
    assert pages == [1, 2, 0]  # from page 2 on, wrapping around


def test_a_new_search_stops_the_previous_one(tmp_path: Path) -> None:
    path = make_text_pdf(tmp_path / "text.pdf")
    search = TextSearch(GLib.filename_to_uri(str(path), None))
    new: list[int] = []
    finished: list[bool] = []
    search.start("page", 0, lambda _results: None, lambda: None)
    search.start("page 3", 0, lambda results: new.extend(item.page for item in results), lambda: finished.append(True))
    wait_until(lambda: bool(finished))
    assert new == [2, 2]
