"""Links and text of the pages (B7, B8, B9)."""

from pathlib import Path

import cairo
import pikepdf
import pytest
from gi.repository import GLib, Poppler

from penfold.rendering.page_content import ExternalTarget, InternalTarget, PageContent
from penfold.ui.text_selection import PagePoint, TextSelection

A4 = (595.0, 842.0)


def make_text_pdf(path: Path) -> Path:
    """Three A4 pages with two lines of text each, and links on the first page."""
    surface = cairo.PDFSurface(str(path), *A4)
    context = cairo.Context(surface)
    context.set_font_size(12)
    for page in range(3):
        for line in range(2):
            context.move_to(72, 100 + line * 20)
            context.show_text(f"Page {page + 1} line {line + 1}")
        context.show_page()
    surface.finish()
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        annotations = [
            # To page 3, showing the height 600 points from its bottom.
            pikepdf.Dictionary(
                Type=pikepdf.Name.Annot,
                Subtype=pikepdf.Name.Link,
                Rect=[72, 700, 200, 720],
                Dest=pikepdf.Array([pdf.pages[2].obj, pikepdf.Name.XYZ, None, 600, None]),
            ),
            # To page 2, without a height.
            pikepdf.Dictionary(
                Type=pikepdf.Name.Annot,
                Subtype=pikepdf.Name.Link,
                Rect=[72, 650, 200, 670],
                Dest=pikepdf.Array([pdf.pages[1].obj, pikepdf.Name.Fit]),
            ),
            pikepdf.Dictionary(
                Type=pikepdf.Name.Annot,
                Subtype=pikepdf.Name.Link,
                Rect=[300, 700, 500, 720],
                A=pikepdf.Dictionary(S=pikepdf.Name.URI, URI=pikepdf.String("https://example.org/")),
            ),
            # Launching programs is never followed.
            pikepdf.Dictionary(
                Type=pikepdf.Name.Annot,
                Subtype=pikepdf.Name.Link,
                Rect=[300, 650, 500, 670],
                A=pikepdf.Dictionary(S=pikepdf.Name.Launch, F=pikepdf.String("program")),
            ),
        ]
        pdf.pages[0].Annots = pdf.make_indirect(pikepdf.Array([pdf.make_indirect(item) for item in annotations]))
        pdf.save(path)
    return path


@pytest.fixture
def content(tmp_path: Path) -> PageContent:
    path = make_text_pdf(tmp_path / "text.pdf")
    return PageContent(Poppler.Document.new_from_file(GLib.filename_to_uri(str(path), None), None))


def test_links_are_read_from_the_top_of_the_page(content: PageContent) -> None:
    by_target = {link.target: link.area for link in content.links(0)}
    assert by_target == {
        InternalTarget(2, 842 - 600): (72, 842 - 720, 200, 842 - 700),
        InternalTarget(1, None): (72, 842 - 670, 200, 842 - 650),
        ExternalTarget("https://example.org/"): (300, 842 - 720, 500, 842 - 700),
    }


def test_link_under_a_point(content: PageContent) -> None:
    link = content.link_at(0, 100, 130)
    assert link is not None
    assert link.target == InternalTarget(2, 242)
    assert content.link_at(0, 10, 10) is None
    assert content.link_at(1, 100, 130) is None


def test_selected_text_of_one_page(content: PageContent) -> None:
    selection = TextSelection(PagePoint(0, 95, 70), PagePoint(0, 125, 300))
    assert selection.text(content, [A4] * 3) == "Page 1 line 1\nPage 1 line 2"


def test_selection_across_pages_takes_the_pages_in_between_whole(content: PageContent) -> None:
    selection = TextSelection(PagePoint(2, 125, 300), PagePoint(0, 115, 70))
    assert selection.page_selections([A4] * 3) == {
        0: (70, 115, 595.0, 842.0),
        1: (0.0, 0.0, 595.0, 842.0),
        2: (0.0, 0.0, 300, 125),
    }
    assert (
        selection.text(content, [A4] * 3) == "Page 1 line 2\nPage 2 line 1\nPage 2 line 2\nPage 3 line 1\nPage 3 line 2"
    )


def test_double_click_selects_a_word(content: PageContent) -> None:
    point = PagePoint(0, 97, 120)
    selection = TextSelection(point, point, Poppler.SelectionStyle.WORD)
    assert selection.text(content, [A4] * 3) == "line"


def test_selection_rectangles_cover_the_text(content: PageContent) -> None:
    rectangles = content.selection_rectangles(0, (70, 95, 300, 105), Poppler.SelectionStyle.GLYPH)
    assert rectangles
    left, top, right, bottom = rectangles[0]
    assert left <= 72 < right
    assert top < 100 <= bottom


def test_text_in_areas_takes_nothing_from_the_next_line(content: PageContent) -> None:
    # An area around the first line that reaches into the second one, as highlight boxes often do.
    assert content.text_in_areas(0, [(70, 88, 400, 112)]) == "Page 1 line 1"
