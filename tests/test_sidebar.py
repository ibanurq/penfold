"""The side panel with a PDF: showing it, its views, thumbnails, bookmarks, annotations and Find (fase 2)."""

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
import pytest

from penfold.ui.sidebar.pages_view import column_count
from tests.gtk_helpers import process_pending_events, wait_until, wait_until_stable
from tests.sample_pdfs import make_pdf
from tests.test_bookmarks import add_outline
from tests.test_page_content import make_text_pdf

if TYPE_CHECKING:
    from penfold.application import PenfoldApplication
    from penfold.ui.window import PenfoldWindow


@pytest.fixture
def window(application: "PenfoldApplication") -> Iterator["PenfoldWindow"]:
    from penfold.ui.window import PenfoldWindow

    new_window = PenfoldWindow(application)
    new_window.set_default_size(1100, 750)
    new_window.present()
    yield new_window
    dialog = new_window.get_visible_dialog()
    if dialog is not None:
        dialog.force_close()
    new_window.destroy()
    process_pending_events()


def open_and_wait(window: "PenfoldWindow", path: Path) -> None:
    assert window.open_file(path)
    view = window.document_view
    wait_until(lambda: view.get_width() > 0 and bool(view._boxes))
    wait_until_stable(lambda: (window.get_width(), view.get_width(), view.zoom))


@pytest.mark.parametrize(("width", "columns"), [(249, 1), (310, 1), (321, 2), (700, 3), (2000, 4)])
def test_thumbnail_columns_follow_the_width_as_in_06(width: int, columns: int) -> None:
    assert column_count(width) == columns


def test_panel_width_limits(application: "PenfoldApplication") -> None:  # noqa: ARG001 (loads the interface files)
    from penfold.ui.sidebar.sidebar import MAX_WIDTH, MIN_WIDTH, clamp_width

    assert clamp_width(10) == MIN_WIDTH
    assert clamp_width(5000) == MAX_WIDTH
    assert clamp_width(400.4) == 400


def test_panel_opens_with_a_pdf_and_f9_hides_it(window: "PenfoldWindow", tmp_path: Path) -> None:
    open_and_wait(window, make_pdf(tmp_path / "plain.pdf"))
    assert window.split_view.get_show_sidebar()
    assert not window.document_header.main_menu_button.get_visible()  # the main menu is in the panel (D36)
    window.activate_action("win.show-sidebar", None)
    assert not window.split_view.get_show_sidebar()
    assert window.document_header.main_menu_button.get_visible()


def test_views_switch_and_find_goes_back_to_the_previous_one(window: "PenfoldWindow", tmp_path: Path) -> None:
    from penfold.ui.sidebar import sidebar

    open_and_wait(window, make_pdf(tmp_path / "plain.pdf"))
    panel = window.sidebar
    assert panel.visible_view == sidebar.PAGES
    panel.bookmarks_button.set_active(True)
    assert panel.visible_view == sidebar.BOOKMARKS
    window.activate_action("win.find", None)
    assert panel.visible_view == sidebar.SEARCH
    assert panel.search_button.get_active()
    window.close_find()
    assert panel.visible_view == sidebar.BOOKMARKS
    assert panel.bookmarks_button.get_active()


def test_thumbnails_list_every_page_with_its_label(window: "PenfoldWindow", tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "book.pdf", page_count=4, label_ranges=[(0, pikepdf.Dictionary(S=pikepdf.Name.r))])
    open_and_wait(window, path)
    pages = window.pages_view
    items = [pages.pages.get_item(index) for index in range(pages.pages.get_n_items())]
    assert [item.label for item in items if item is not None] == ["i", "ii", "iii", "iv"]
    pages.emit("page-activated", 2)
    assert window.document_view.current_page == 2
    assert pages.current_page == 2


def test_bookmarks_show_the_tree_and_go_to_their_destination(window: "PenfoldWindow", tmp_path: Path) -> None:
    from penfold.ui.sidebar.bookmarks_view import BookmarkItem

    path = make_pdf(tmp_path / "outline.pdf", page_count=5)
    add_outline(path)
    open_and_wait(window, path)
    bookmarks = window.bookmarks_view
    titles = []
    for index in range(bookmarks.tree.get_n_items()):
        row = bookmarks.tree.get_row(index)
        item = row.get_item() if row is not None else None
        assert isinstance(item, BookmarkItem)
        titles.append(item.bookmark.title)
    assert titles == ["Cover", "1. Intro", "1.1 Scope", "Broken", "Action"]  # "1. Intro" is stored open
    bookmarks.toggle_all()
    assert bookmarks.tree.get_n_items() == 4
    bookmarks.emit("destination-activated", 4, 342.0)
    assert window.document_view.current_page == 4


def test_annotations_are_grouped_and_filtered(window: "PenfoldWindow", tmp_path: Path) -> None:
    from penfold.document.annotations import Kind
    from penfold.ui.sidebar.annotations_view import AnnotationRow

    path = make_pdf(tmp_path / "notes.pdf", page_count=2)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        notes = [
            pikepdf.Dictionary(
                Type=pikepdf.Name.Annot,
                Subtype=pikepdf.Name.Text,
                Rect=[10, 10, 30, 30],
                Contents=pikepdf.String("A note"),
            ),
            pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Square, Rect=[50, 50, 90, 90]),
        ]
        pdf.pages[1].Annots = pdf.make_indirect(pikepdf.Array([pdf.make_indirect(note) for note in notes]))
        pdf.save(path)
    open_and_wait(window, path)
    view = window.annotations_view

    def rows() -> list[AnnotationRow]:
        found = []
        child = view.list.get_first_child()
        while child is not None:
            if isinstance(child, AnnotationRow):
                found.append(child)
            child = child.get_next_sibling()
        return found

    assert [row.annotation.kind for row in rows()] == [Kind.COMMENT]  # rectangles are hidden by default, as in 0.6
    view.shown_kinds.add(Kind.RECTANGLE)
    view.refresh()
    assert [row.annotation.kind for row in rows()] == [Kind.COMMENT, Kind.RECTANGLE]
    view.emit("annotation-activated", 1, 700.0)
    assert window.document_view.current_page == 1


def test_find_lists_matches_and_goes_to_them(window: "PenfoldWindow", tmp_path: Path) -> None:
    open_and_wait(window, make_text_pdf(tmp_path / "text.pdf"))
    window.activate_action("win.find", None)
    search = window.search_view
    search.entry.set_text("LINE 1")
    wait_until(lambda: search.results.get_n_items() == 3 and not search._searching)
    assert [result.page for result in search.result_list] == [0, 1, 2]
    assert search.current == 0
    assert search.count_label.get_label() == "3 results"
    window.activate_action("win.find-next", None)
    assert search.current == 1
    assert window.document_view.current_page == 1
    window.activate_action("win.find-previous", None)
    assert search.current == 0
    assert window.document_view.has_matches  # highlighted on the pages while Find is open
    window.close_find()
    assert not window.document_view.has_matches


def test_dragging_the_panel_edge_fits_the_zoom_once_released(window: "PenfoldWindow", tmp_path: Path) -> None:
    open_and_wait(window, make_pdf(tmp_path / "plain.pdf"))
    window.set_default_size(1400, 800)  # wide enough for a 500-pixel panel
    view = window.document_view
    wait_until_stable(lambda: (window.get_width(), view.get_width(), view.zoom))
    zoom = view.zoom
    window.sidebar.emit("resize-started")
    window.sidebar.emit("resized", 500)
    wait_until_stable(view.get_width)
    assert view.zoom == zoom  # not while dragging (B4)
    window.sidebar.emit("resize-finished")
    wait_until_stable(lambda: (view.get_width(), view.zoom))
    assert view.zoom < zoom
    from gi.repository import Gio

    from penfold import config

    assert Gio.Settings(schema_id=config.APP_ID).get_int("sidebar-width") == 500


def test_the_panel_leaves_room_for_the_document(window: "PenfoldWindow", tmp_path: Path) -> None:
    open_and_wait(window, make_pdf(tmp_path / "plain.pdf"))
    window.set_default_size(1400, 800)
    window.sidebar.emit("resize-started")
    window.sidebar.emit("resized", 1300)
    window.sidebar.emit("resize-finished")
    widest = window.split_view.get_max_sidebar_width()
    assert widest < 1300  # never wider than the window minus the document's room, as in 0.6
    window.set_default_size(900, 800)
    assert window.split_view.get_max_sidebar_width() < widest
    window.set_default_size(1400, 800)
    assert window.split_view.get_max_sidebar_width() == widest  # the chosen width comes back


def test_thumbnails_grow_with_the_panel_and_then_add_columns(window: "PenfoldWindow", tmp_path: Path) -> None:
    from penfold.ui.sidebar.pages_view import LIST_MARGIN, SCROLLBAR_WIDTH

    open_and_wait(window, make_pdf(tmp_path / "plain.pdf", page_count=6))
    window.set_default_size(1800, 800)
    pages = window.pages_view
    sizes = []
    # Wide first, then narrow: the thumbnails must shrink back to one column, and grow again.
    for width in (700, 300, 330, 450, 700):
        window.sidebar.emit("resized", width)
        wait_until_stable(lambda: (pages.grid.get_min_columns(), pages.thumbnail_width))
        available = pages.get_width() - SCROLLBAR_WIDTH - 2 * LIST_MARGIN
        assert pages.grid.get_min_columns() == column_count(available)  # the panel may be narrower than asked
        sizes.append((pages.grid.get_min_columns(), pages.thumbnail_width))
    assert sizes[1][0] == 1
    assert sizes[2][1] > sizes[1][1]  # a wider panel, bigger thumbnails, until a new column fits
    assert sizes[-1][0] >= 2
