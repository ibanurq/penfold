"""Finding text (D13; 0.6's rules: no case, accents or line breaks)."""

from pathlib import Path

from gi.repository import GLib

from penfold.rendering.text_search import TextSearch, find_in_page, fold, fold_query
from tests.gtk_helpers import wait_until
from tests.test_page_content import make_text_pdf


def boxes_for(text: str) -> list[tuple[float, float, float, float]]:
    """One 10-point box per character, all on one line, as Poppler would give them."""
    return [(index * 10.0, 100.0, index * 10.0 + 10, 112.0) for index in range(len(text))]


def test_folding_ignores_case_accents_and_line_breaks() -> None:
    folded, origins = fold("Canción\n  ÚNICA")
    assert folded == "cancion unica"
    assert origins[5] == 5  # the "o" of "ción" comes from the accented letter
    assert fold_query("  GARANTÍA ") == "garantia"


def test_finds_every_match_and_its_boxes() -> None:
    text = "La garantía de la Garantia"
    results = find_in_page(3, text, boxes_for(text), fold_query("garantia"))
    assert [result.match for result in results] == ["garantía", "Garantia"]
    assert results[0].page == 3
    assert results[0].rectangles == ((30.0, 100.0, 110.0, 112.0),)


def test_a_match_across_a_line_break_has_one_box_per_line() -> None:
    text = "the plazo\nde garantía"
    boxes = (
        boxes_for("the plazo")
        + [(0.0, 0.0, 0.0, 0.0)]
        + [(index * 10.0, 120.0, index * 10.0 + 10, 132.0) for index in range(11)]
    )
    results = find_in_page(0, text, boxes, fold_query("plazo de"))
    assert len(results) == 1
    assert results[0].rectangles == ((40.0, 100.0, 90.0, 112.0), (0.0, 120.0, 20.0, 132.0))


def test_the_sentence_around_a_match_has_whole_words() -> None:
    text = "Una frase muy larga con varias palabras antes de la garantía legal establecida en la normativa vigente"
    result = find_in_page(0, text, boxes_for(text), fold_query("garantía"))[0]
    assert result.before.endswith("antes de la ")
    assert not result.before.startswith("rase")
    assert result.after.startswith(" legal")
    dotted = "la garantía. Siguiente frase"
    assert find_in_page(0, dotted, boxes_for(dotted), fold_query("garantia"))[0].after.startswith(". Siguiente")
    assert result.after.split()[-1] in text.split()


def test_searches_a_pdf_in_the_background_from_a_page_on(tmp_path: Path) -> None:
    path = make_text_pdf(tmp_path / "text.pdf")
    search = TextSearch(GLib.filename_to_uri(str(path), None))
    pages: list[int] = []
    finished: list[bool] = []
    search.start(
        "LINE 2", 1, lambda results: pages.extend(result.page for result in results), lambda: finished.append(True)
    )
    wait_until(lambda: bool(finished))
    assert pages == [1, 2, 0]  # from page 2 on, wrapping around


def test_a_new_search_stops_the_previous_one(tmp_path: Path) -> None:
    path = make_text_pdf(tmp_path / "text.pdf")
    search = TextSearch(GLib.filename_to_uri(str(path), None))
    old: list[int] = []
    new: list[int] = []
    finished: list[bool] = []
    search.start("page", 0, lambda results: old.extend(result.page for result in results), lambda: None)
    search.start(
        "page 3", 0, lambda results: new.extend(result.page for result in results), lambda: finished.append(True)
    )
    wait_until(lambda: bool(finished))
    assert new == [2, 2]
    assert not old or len(old) < 6
