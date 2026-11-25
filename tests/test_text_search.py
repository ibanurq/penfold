"""Finding text, ignoring case, accents and line breaks."""

from pathlib import Path

import cairo
import pytest

from penfold.document.pages import Page
from penfold.rendering.layout import PageLayout, ShownPage
from penfold.rendering.poppler_sources import PopplerSources
from penfold.rendering.text_search import (
    ContextReader,
    MatchContext,
    SearchResult,
    TextSearch,
    find_in_page,
    normalize_query,
)
from tests.gtk_helpers import wait_until
from tests.sample_pdfs import source_spans
from tests.test_page_content import A4, make_text_pdf

LINES = [
    "El plazo de Garantía será de dos años",
    "desde la entrega. La garantia cubre los",
    "defectos de una garantía legal establecida en la normativa vigente del país",
]


@pytest.fixture
def sources(tmp_path: Path) -> PopplerSources:
    """One page with three lines of text, 20 points apart, from 100 points from the top."""
    path = tmp_path / "words.pdf"
    surface = cairo.PDFSurface(str(path), *A4)
    context = cairo.Context(surface)
    context.set_font_size(12)
    for index, line in enumerate(LINES):
        context.move_to(72, 100 + index * 20)
        context.show_text(line)
    surface.finish()
    spans = source_spans(path)
    return PopplerSources(lambda: spans)


PAGE = ShownPage(0, A4)


def test_runs_of_spaces_count_as_one() -> None:
    assert normalize_query("  dos\n  años ") == "dos años"


def test_ignores_case_and_accents(sources: PopplerSources) -> None:
    results = find_in_page(sources.page(0), 0, PAGE, "GARANTIA")
    assert len(results) == 3
    assert [result.page for result in results] == [0, 0, 0]
    left, top, right, bottom = results[0].rectangles[0]
    assert top < 100 <= bottom  # the boxes are measured from the top of the page
    assert 72 < left < right


def test_finds_text_across_a_line_break(sources: PopplerSources) -> None:
    results = find_in_page(sources.page(0), 0, PAGE, "dos años desde la")
    assert len(results) == 1
    assert len(results[0].rectangles) == 2  # one box per line
    assert results[0].top < 100


def test_the_sentence_around_a_match(sources: PopplerSources) -> None:
    reader = ContextReader(sources)
    context = reader.context(find_in_page(sources.page(0), 0, PAGE, "garantia legal")[0])
    assert (context.before, context.match, context.more_before) == ("defectos de una", "garantía legal", False)
    assert context.after.startswith("establecida en la")
    assert len(context.after) <= 40
    assert context.more_after
    assert context.after.split()[-1] in LINES[2].split()
    # A match at the end of a line takes nothing from the next one.
    end_of_line = reader.context(find_in_page(sources.page(0), 0, PAGE, "dos años")[0])
    assert end_of_line == MatchContext("El plazo de Garantía será de", "dos años", "", False, False, True, False)


def test_a_match_inside_a_word_keeps_the_word_whole(sources: PopplerSources) -> None:
    from penfold.ui.sidebar.search_view import result_markup

    reader = ContextReader(sources)
    inside = reader.context(find_in_page(sources.page(0), 0, PAGE, "aranti")[0])
    assert (inside.before, inside.match, inside.after) == ("El plazo de G", "arantí", "a será de dos años")
    assert (inside.space_before, inside.space_after) == (False, False)
    assert result_markup(inside).startswith("El plazo de G<span")
    assert result_markup(inside).endswith("</span>a será de dos años")
    # Before a full stop there is no space either; between words, one.
    before_stop = reader.context(find_in_page(sources.page(0), 0, PAGE, "entrega")[0])
    assert (before_stop.space_before, before_stop.space_after, before_stop.after[0]) == (True, False, ".")
    assert result_markup(before_stop).startswith("desde la <span")


def test_searches_a_pdf_in_the_background_from_a_page_on(tmp_path: Path) -> None:
    path = make_text_pdf(tmp_path / "text.pdf")
    spans = source_spans(path)
    search = TextSearch(lambda: spans)
    pages: list[int] = []
    finished: list[bool] = []
    search.start(
        "LINE   2",
        1,
        PageLayout([A4] * 3),
        lambda results: pages.extend(item.page for item in results),
        lambda: finished.append(True),
    )
    wait_until(lambda: bool(finished))
    assert pages == [1, 2, 0]  # from page 2 on, wrapping around


def test_a_new_search_stops_the_previous_one(tmp_path: Path) -> None:
    path = make_text_pdf(tmp_path / "text.pdf")
    spans = source_spans(path)
    search = TextSearch(lambda: spans)
    new: list[int] = []
    finished: list[bool] = []
    layout = PageLayout([A4] * 3)
    search.start("page", 0, layout, lambda _results: None, lambda: None)
    search.start(
        "page 3", 0, layout, lambda results: new.extend(item.page for item in results), lambda: finished.append(True)
    )
    wait_until(lambda: bool(finished))
    assert new == [2, 2]


def test_searches_the_pages_in_their_order_and_turn(tmp_path: Path) -> None:
    path = make_text_pdf(tmp_path / "text.pdf")
    spans = source_spans(path)
    search = TextSearch(lambda: spans)
    found: list[SearchResult] = []
    finished: list[bool] = []
    layout = PageLayout([A4] * 3, [Page(2, rotation=180), Page(0)])
    search.start("page 3 line 1", 0, layout, found.extend, lambda: finished.append(True))
    wait_until(lambda: bool(finished))
    assert [(result.page, result.source) for result in found] == [(0, 2)]
    left, top, _right, _bottom = found[0].source_rectangles[0]
    _left, _top, shown_right, shown_bottom = found[0].rectangles[0]
    assert (shown_right, shown_bottom) == pytest.approx((A4[0] - left, A4[1] - top))


def test_the_sentence_is_read_from_the_page_of_the_pdf(sources: PopplerSources) -> None:
    turned = ShownPage(0, A4, rotation=90)
    result = find_in_page(sources.page(0), 4, turned, "dos años")[0]
    assert ContextReader(sources).context(result).match == "dos años"


def test_searches_the_pages_of_every_source(tmp_path: Path) -> None:
    spans = source_spans(make_text_pdf(tmp_path / "opened.pdf"), make_text_pdf(tmp_path / "added.pdf"))
    search = TextSearch(lambda: spans)
    found: list[SearchResult] = []
    finished: list[bool] = []
    layout = PageLayout([A4] * 6, [Page(4), Page(0)])
    search.start("page 2 line 1", 0, layout, found.extend, lambda: finished.append(True))
    wait_until(lambda: bool(finished))
    assert [(result.page, result.source) for result in found] == [(0, 4)]
    assert ContextReader(PopplerSources(lambda: spans)).context(found[0]).match == "Page 2 line 1"
