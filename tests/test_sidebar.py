"""The side panel with a PDF: showing it, its views, thumbnails, bookmarks, annotations and Find (fase 2)."""

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
import pytest
from gi.repository import Gdk, Gio, Graphene, Gtk

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


@pytest.mark.parametrize(
    ("available", "thumbnail", "columns"), [(100, 160, 1), (200, 160, 1), (360, 160, 2), (560, 160, 3), (540, 90, 4)]
)
def test_columns_are_those_that_fit(available: int, thumbnail: int, columns: int) -> None:
    assert column_count(available, thumbnail) == columns


def test_every_page_fits_in_the_same_cell_without_distortion() -> None:
    from penfold.ui.sidebar.pages_view import fit_page

    a4, a3, landscape = (595.0, 842.0), (842.0, 1191.0), (842.0, 595.0)
    box = (160.0, 160.0 * 2**0.5)
    assert fit_page(a4, *box) == pytest.approx((0.0, 0.0, 160.0, 226.4), abs=0.2)
    assert fit_page(a3, *box) == pytest.approx(fit_page(a4, *box), abs=0.3)  # an A3 looks like an A4
    x, y, width, height = fit_page(landscape, *box)
    assert (x, width) == pytest.approx((0.0, 160.0))
    assert y == pytest.approx((box[1] - height) / 2)  # centred vertically
    assert width / height == pytest.approx(842 / 595)


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
    from penfold.document.annotations import AnnotationGroup, Kind

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
            pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Ink, Rect=[50, 150, 90, 190]),
            pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.FileAttachment, Rect=[50, 250, 60, 260]),
        ]
        pdf.pages[1].Annots = pdf.make_indirect(pikepdf.Array([pdf.make_indirect(note) for note in notes]))
        pdf.save(path)
    open_and_wait(window, path)
    view = window.annotations_view

    assert [annotation.kind for annotation in view.shown_annotations()] == [
        Kind.COMMENT
    ]  # shapes and other types are hidden by default
    popover = view.filter_button.get_popover()
    assert popover is not None
    column = popover.get_child()
    assert column is not None
    boxes = [box for box in column if isinstance(box, Gtk.CheckButton)]
    assert [box.get_label() for box in boxes] == ["Text Highlights", "Shapes", "Text Elements", "Other Types"]
    assert [box.get_active() for box in boxes] == [False, False, True, False]
    view.activate_action("annotations-filter.shapes", None)
    view.activate_action("annotations-filter.others", None)
    assert view.shown_groups == {AnnotationGroup.SHAPES, AnnotationGroup.TEXT_ELEMENTS, AnnotationGroup.OTHERS}
    assert [box.get_active() for box in boxes] == [False, True, True, True]
    # Shapes come first, from the top of the page down; a freehand drawing is a shape too (D64).
    assert [annotation.subtype for annotation in view.shown_annotations()] == [
        "Ink",
        "Square",
        "Text",
        "FileAttachment",
    ]
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


def test_thumbnails_keep_their_size_and_the_columns_follow_the_panel(window: "PenfoldWindow", tmp_path: Path) -> None:
    from penfold.ui.sidebar.pages_view import widest_thumbnail

    open_and_wait(window, make_pdf(tmp_path / "plain.pdf", page_count=12))
    window.set_default_size(1800, 800)
    pages = window.pages_view
    pages.set_thumbnail_width(120)
    seen = []
    for width in (700, 300, 450, 700):
        window.sidebar.emit("resized", width)
        wait_until_stable(lambda: (pages.get_width(), pages.grid.get_min_columns(), pages.thumbnail_width))
        available = pages.available_width
        expected_width = min(120, widest_thumbnail(available))
        assert pages.thumbnail_width == expected_width
        assert pages.grid.get_min_columns() == column_count(available, expected_width)
        seen.append(pages.grid.get_min_columns())
    assert seen[1] < seen[0]  # a narrower panel shows fewer columns of the same thumbnails
    assert seen[3] == seen[0]


def test_zooming_the_thumbnails_changes_the_columns_and_is_remembered(window: "PenfoldWindow", tmp_path: Path) -> None:

    from penfold import config
    from penfold.ui.sidebar.pages_view import MIN_THUMBNAIL_WIDTH

    open_and_wait(window, make_pdf(tmp_path / "plain.pdf", page_count=12))
    pages = window.pages_view
    window.sidebar.emit("resized", 400)
    wait_until_stable(lambda: (pages.get_width(), pages.grid.get_min_columns()))
    pages.set_thumbnail_width(MIN_THUMBNAIL_WIDTH)
    wait_until_stable(pages.grid.get_min_columns)
    many = pages.grid.get_min_columns()
    for _ in range(20):
        pages.zoom_in()
    wait_until_stable(pages.grid.get_min_columns)
    assert pages.grid.get_min_columns() == 1 < many  # at most one column filling the panel
    assert Gio.Settings(schema_id=config.APP_ID).get_int("thumbnail-size") == pages.chosen_width
    pages.zoom_out()
    assert pages.chosen_width < pages.thumbnail_width * 1.0 + 1


def test_control_plus_zooms_what_has_the_focus(window: "PenfoldWindow", tmp_path: Path) -> None:
    open_and_wait(window, make_pdf(tmp_path / "plain.pdf", page_count=4))
    pages, view = window.pages_view, window.document_view
    zoom, size = view.zoom, pages.chosen_width
    pages.grid.grab_focus()
    window.activate_action("win.zoom-out", None)
    assert view.zoom == zoom
    assert pages.chosen_width < size
    view.grab_focus()
    window.activate_action("win.zoom-out", None)
    assert view.zoom < zoom


def test_the_part_shown_is_marked_on_the_thumbnails(window: "PenfoldWindow", tmp_path: Path) -> None:
    open_and_wait(window, make_pdf(tmp_path / "plain.pdf", page_count=4))
    areas = window.pages_view.visible_areas
    assert 0 in areas
    left, top, right, bottom = areas[0]
    assert (left, top) == pytest.approx((0.0, 0.0), abs=1)
    assert right == pytest.approx(595, abs=1)  # fitted to the width: the whole width is shown
    assert 0 < bottom <= 842


def test_a_narrow_panel_shows_one_column_from_the_start(window: "PenfoldWindow", tmp_path: Path) -> None:
    window.sidebar.emit("resized", 300)
    open_and_wait(window, make_pdf(tmp_path / "plain.pdf", page_count=8))
    pages = window.pages_view
    wait_until_stable(lambda: (pages.get_width(), pages.grid.get_max_columns()))
    assert pages.grid.get_min_columns() == pages.grid.get_max_columns() == 1


def test_bookmarks_follow_the_reading(window: "PenfoldWindow", tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "outline.pdf", page_count=5)
    add_outline(path)
    open_and_wait(window, path)
    bookmarks, view = window.bookmarks_view, window.document_view
    assert bookmarks.marked_bookmark is not None
    assert bookmarks.marked_bookmark.title == "Cover"
    view.go_to(2)
    process_pending_events()
    assert bookmarks.marked_bookmark.title == "1.1 Scope"
    bookmarks.toggle_all()  # fold "1. Intro": its row shows the section being read
    process_pending_events()
    assert bookmarks.marked_bookmark.title == "1. Intro"


def test_annotations_of_the_page_being_read_are_marked(window: "PenfoldWindow", tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "notes.pdf", page_count=3)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        for page in (0, 2):
            note = pikepdf.Dictionary(
                Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Text, Rect=[10, 10, 30, 30], Contents=pikepdf.String("n")
            )
            pdf.pages[page].Annots = pdf.make_indirect(pikepdf.Array([pdf.make_indirect(note)]))
        pdf.save(path)
    open_and_wait(window, path)
    view = window.annotations_view

    def marked() -> list[int]:
        rows = view.bound_rows()
        return [row.annotation.page for row in rows if row.annotation and row.has_css_class("reading-position")]

    assert marked() == [0]
    window.document_view.go_to(2)
    process_pending_events()
    assert marked() == [2]


def test_the_row_of_the_section_being_read_is_marked(window: "PenfoldWindow", tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "outline.pdf", page_count=5)
    add_outline(path)
    open_and_wait(window, path)
    window.sidebar.show_view("bookmarks")
    window.document_view.go_to(2)
    wait_until_stable(lambda: tuple(window.bookmarks_view._rows))
    marked = [
        row.title.get_text() for row in window.bookmarks_view._rows.values() if row.has_css_class("reading-position")
    ]
    assert marked == ["1.1 Scope"]


def bookmark_pages(window: "PenfoldWindow") -> dict[str, str]:
    """The page label each bookmark row shows, by title."""
    process_pending_events()
    return {
        row.bookmark.title: row.page.get_label()
        for row in window.bookmarks_view._rows.values()
        if row.bookmark is not None
    }


def test_the_panel_follows_the_edited_pages(window: "PenfoldWindow", tmp_path: Path) -> None:
    from penfold.document.commands.pages import DeletePages, MovePages

    path = make_pdf(tmp_path / "outline.pdf", page_count=5)
    add_outline(path)
    open_and_wait(window, path)
    document = window.document
    assert document is not None
    document.execute(MovePages(document, [4], 0))
    assert bookmark_pages(window)["Cover"] == "2"
    assert bookmark_pages(window)["Action"] == "1"
    document.execute(DeletePages(document, [1]))
    assert "Cover" not in bookmark_pages(window)
    assert bookmark_pages(window)["1. Intro"] == "2"
    document.undo()
    assert bookmark_pages(window)["Cover"] == "2"


def test_annotations_and_matches_follow_the_edited_pages(window: "PenfoldWindow", tmp_path: Path) -> None:
    from penfold.document.commands.pages import DeletePages, MovePages, RotatePages

    path = make_text_pdf(tmp_path / "text.pdf")
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        note = pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Text, Rect=[10, 10, 30, 30])
        pdf.pages[1].Annots = pdf.make_indirect(pikepdf.Array([pdf.make_indirect(note)]))
        pdf.save(path)
    open_and_wait(window, path)
    document = window.document
    assert document is not None
    window.activate_action("win.find", None)
    search = window.search_view
    search.entry.set_text("LINE 1")
    wait_until(lambda: search.results.get_n_items() == 3 and not search._searching)
    document.execute(RotatePages(document, [2], 180))
    document.execute(MovePages(document, [2], 0))
    wait_until(lambda: search.results.get_n_items() == 3 and not search._searching)
    assert [(result.page, result.source) for result in search.result_list] == [(0, 2), (1, 0), (2, 1)]
    annotations = window.annotations_view
    assert [annotations.position(annotation) for annotation in annotations.shown_annotations()] == [2]
    document.execute(DeletePages(document, [2]))
    assert annotations.shown_annotations() == []
    assert annotations.empty.get_label() == "This PDF has no annotations"


def test_a_click_clears_the_selection_only_away_from_the_rows(window: "PenfoldWindow", tmp_path: Path) -> None:
    from penfold.ui.sidebar.view_header import is_away_from_rows

    path = make_pdf(tmp_path / "outline.pdf", page_count=5)
    add_outline(path)
    open_and_wait(window, path)
    pages = window.pages_view
    wait_until(lambda: 0 in pages._cells)
    wait_until_stable(lambda: sorted(pages._cells))
    boxes = [_bounds(pages._cells[page].get_parent(), pages.scrolled) for page in sorted(pages._cells)]
    first = boxes[0]
    # The first thumbnail of the next row, however many columns fit (another test may have made them smaller).
    below = next(box for box in boxes if box.get_y() >= first.get_y() + first.get_height())
    beside_thumbnail = (first.get_x() + 2, first.get_y() + first.get_height() / 2)
    between_rows = (first.get_x() + first.get_width() / 2, (first.get_y() + first.get_height() + below.get_y()) / 2)
    assert not is_away_from_rows(pages.scrolled, *beside_thumbnail)  # its selection box covers it
    assert is_away_from_rows(pages.scrolled, *between_rows)
    window.sidebar.show_view("bookmarks")
    bookmarks = window.bookmarks_view.list
    scrolled = bookmarks.get_parent()
    assert isinstance(scrolled, Gtk.ScrolledWindow)
    wait_until(lambda: bookmarks.get_height() > 0)
    assert not is_away_from_rows(scrolled, 40, 10)
    assert is_away_from_rows(scrolled, 40, scrolled.get_height() - 10)


def _bounds(widget: Gtk.Widget | None, target: Gtk.Widget) -> Graphene.Rect:
    assert widget is not None
    found, bounds = widget.compute_bounds(target)
    assert found
    return bounds


def test_escape_clears_the_selection_of_the_panel_view(window: "PenfoldWindow", tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "outline.pdf", page_count=5)
    add_outline(path)
    open_and_wait(window, path)
    pages, bookmarks = window.pages_view, window.bookmarks_view
    pages.selection.select_range(1, 2, True)
    window.activate_action("win.find", None)
    assert press_escape(window)  # it closes Find first
    assert pages.selected_pages() == [1, 2]
    window.split_view.set_show_sidebar(False)
    assert not press_escape(window)  # a hidden selection is left alone
    window.split_view.set_show_sidebar(True)
    assert press_escape(window)
    assert pages.selected_pages() == []
    assert not press_escape(window)  # nothing left to do
    window.sidebar.show_view("bookmarks")
    bookmarks.selection.select_item(0, True)
    assert press_escape(window)
    assert bookmarks.selection.get_selection().is_empty()


def press_escape(window: "PenfoldWindow") -> bool:
    """Send Esc to the window as nothing inside it used the key; return whether it did something."""
    return window._on_key_pressed(Gtk.EventControllerKey(), Gdk.KEY_Escape, 0, Gdk.ModifierType(0))


def test_added_pages_show_in_every_view(window: "PenfoldWindow", tmp_path: Path) -> None:
    from penfold.document.commands.pages import AddPages

    open_and_wait(window, make_pdf(tmp_path / "plain.pdf", page_count=2))
    document, renderer = window.document, window.renderer
    assert document is not None
    assert renderer is not None
    path = make_text_pdf(tmp_path / "text.pdf")
    add_outline_to_text_pdf(path)
    document.execute(AddPages(document, document.add_source(path), 1))
    assert window.pages_view.pages.get_n_items() == 5
    assert renderer.layout[1].source == 2
    window.sidebar.show_view("bookmarks")
    wait_until(lambda: bool(window.bookmarks_view._rows))
    assert bookmark_pages(window) == {"text": "2", "Added": "2"}  # named after the file, holding its own (D50)
    document.undo()
    assert window.pages_view.pages.get_n_items() == 2
    assert bookmark_pages(window) == {}


def add_outline_to_text_pdf(path: Path) -> None:
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        with pdf.open_outline() as outline:
            outline.root.append(pikepdf.OutlineItem("Added", 0))
        pdf.save(path)
