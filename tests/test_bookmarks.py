"""Reading the bookmarks of a PDF (ISO 32000-1, 12.3.3)."""

from pathlib import Path

import pikepdf
import pytest

from penfold.document.bookmarks import Bookmark, read_bookmarks
from tests.sample_pdfs import make_pdf


def outline_item(pdf: pikepdf.Pdf, parent: pikepdf.Dictionary, title: str, **entries: object) -> pikepdf.Dictionary:
    """Add an outline item (not yet linked to its siblings)."""
    item = pikepdf.Dictionary({"/Title": pikepdf.String(title), "/Parent": parent})
    for key, value in entries.items():
        item[f"/{key}"] = value
    return pdf.make_indirect(item)


def add_outline(path: Path) -> None:
    """Give a 5-page PDF an outline with styles, nesting, a named destination, a broken one and an action.

    Cover (page 1, bold, red); 1. Intro (page 2, italic, open, height 700) with 1.1 Scope (named: page 3); Broken (a
    page outside the document); Action (GoTo: page 5, /FitH 500).
    """
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pages = pdf.pages
        scope_destination = pikepdf.Array([pages[2].obj, pikepdf.Name.Fit])
        names = pikepdf.Dictionary(Names=pikepdf.Array([pikepdf.String("scope"), scope_destination]))
        pdf.Root.Names = pdf.make_indirect(pikepdf.Dictionary(Dests=names))
        outlines = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Outlines))
        cover = outline_item(
            pdf,
            outlines,
            "Cover",
            Dest=pikepdf.Array([pages[0].obj, pikepdf.Name.Fit]),
            F=2,
            C=pikepdf.Array([1, 0, 0]),
        )
        intro_destination = pikepdf.Array([pages[1].obj, pikepdf.Name.XYZ, None, 700, None])
        intro = outline_item(pdf, outlines, "1. Intro", Dest=intro_destination, F=1, Count=1)
        scope = outline_item(pdf, intro, "1.1 Scope", Dest=pikepdf.String("scope"))
        other = pikepdf.new()
        other.add_blank_page()
        foreign_page = pdf.copy_foreign(other.pages[0].obj)
        broken = outline_item(pdf, outlines, "Broken", Dest=pikepdf.Array([foreign_page, pikepdf.Name.Fit]))
        goto = pikepdf.Dictionary(S=pikepdf.Name.GoTo, D=pikepdf.Array([pages[4].obj, pikepdf.Name.FitH, 500]))
        action = outline_item(pdf, outlines, "Action", A=goto)
        intro.First = intro.Last = scope
        for previous, following in ((cover, intro), (intro, broken), (broken, action)):
            previous.Next, following.Prev = following, previous
        outlines.First, outlines.Last, outlines.Count = cover, action, 4
        pdf.Root.Outlines = outlines
        pdf.save(path)


@pytest.fixture
def bookmarks(tmp_path: Path) -> list[Bookmark]:
    path = make_pdf(tmp_path / "outline.pdf", page_count=5)
    add_outline(path)
    with pikepdf.open(path) as pdf:
        return read_bookmarks(pdf)


def test_tree_and_titles(bookmarks: list[Bookmark]) -> None:
    assert [bookmark.title for bookmark in bookmarks] == ["Cover", "1. Intro", "Broken", "Action"]
    assert [child.title for child in bookmarks[1].children] == ["1.1 Scope"]


def test_style(bookmarks: list[Bookmark]) -> None:
    cover, intro = bookmarks[0], bookmarks[1]
    assert (cover.bold, cover.italic, cover.color) == (True, False, (1.0, 0.0, 0.0))
    assert (intro.bold, intro.italic, intro.color) == (False, True, None)
    assert intro.is_open
    assert not cover.is_open


def test_destinations(bookmarks: list[Bookmark]) -> None:
    cover, intro, broken, action = bookmarks
    assert (cover.page, cover.top) == (0, None)
    assert (intro.page, intro.top) == (1, 842 - 700)
    assert (intro.children[0].page, intro.children[0].top) == (2, None)
    assert (broken.page, broken.top) == (None, None)
    assert (action.page, action.top) == (4, 842 - 500)


def test_pdf_without_outline(tmp_path: Path) -> None:
    with pikepdf.open(make_pdf(tmp_path / "plain.pdf")) as pdf:
        assert read_bookmarks(pdf) == []


def test_a_looping_outline_ends(tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "loop.pdf", page_count=1)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        outlines = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Outlines))
        first = pdf.make_indirect(pikepdf.Dictionary(Title=pikepdf.String("A"), Parent=outlines))
        second = pdf.make_indirect(pikepdf.Dictionary(Title=pikepdf.String("B"), Parent=outlines, Next=first))
        first.Next = second
        outlines.First = first
        pdf.Root.Outlines = outlines
        pdf.save(path)
    with pikepdf.open(path) as pdf:
        assert [bookmark.title for bookmark in read_bookmarks(pdf)] == ["A", "B"]


def test_the_bookmark_of_the_section_being_read(bookmarks: list[Bookmark]) -> None:
    from penfold.document.bookmarks import ReadingIndex

    index = ReadingIndex(bookmarks)
    cover, intro, _broken, action = bookmarks
    scope = intro.children[0]
    assert index.at(0, 0) is cover
    assert index.at(1, 100) is cover  # page 2 before the height where "1. Intro" starts (142)
    assert index.at(1, 200) is intro
    assert index.at(2, 0) is scope
    assert index.at(3, 500) is scope  # page 4 has no bookmark of its own
    assert index.at(4, 400) is action
    assert index.ancestors(scope) == [intro]
    assert index.ancestors(cover) == []


def test_no_bookmark_before_the_first_one() -> None:
    from penfold.document.bookmarks import ReadingIndex

    index = ReadingIndex([Bookmark("Late", page=3)])
    assert index.at(1, 0) is None
    assert index.at(3, 0) is not None


def test_the_colour_of_a_title_is_adjusted_to_the_style() -> None:
    from penfold.document.bookmarks import Bookmark
    from penfold.ui.palette import hex_to_color
    from penfold.ui.sidebar.bookmarks_view import title_markup

    bookmark = Bookmark(title="Burgundy", color=hex_to_color("#ad182e"))
    assert '<span foreground="#ad182e">' in title_markup(bookmark, dark=False)
    assert '<span foreground="#f7656a">' in title_markup(bookmark, dark=True)
