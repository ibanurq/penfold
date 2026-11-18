"""A window with a PDF: header, page box, zoom, layouts and protected PDFs (fase 1)."""

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pikepdf
import pytest
from gi.repository import Adw, GLib

from tests.gtk_helpers import process_pending_events, wait_until
from tests.sample_pdfs import make_pdf

if TYPE_CHECKING:
    from penfold.application import PenfoldApplication
    from penfold.ui.window import PenfoldWindow


@pytest.fixture
def window(application: "PenfoldApplication") -> Iterator["PenfoldWindow"]:
    from penfold.ui.window import PenfoldWindow

    new_window = PenfoldWindow(application)
    new_window.set_default_size(900, 700)
    new_window.present()
    yield new_window
    dialog = new_window.get_visible_dialog()
    if dialog is not None:
        dialog.force_close()
    new_window.destroy()
    process_pending_events()


@pytest.fixture
def book(tmp_path: Path) -> Path:
    return make_pdf(
        tmp_path / "book.pdf",
        page_count=12,
        title="A Book",
        label_ranges=[(0, pikepdf.Dictionary(S=pikepdf.Name.r)), (2, pikepdf.Dictionary(S=pikepdf.Name.D))],
    )


def open_and_wait(window: "PenfoldWindow", path: Path) -> bool:
    opened = window.open_file(path)
    if opened:
        # The window grows to its size with a document (D17); wait until the view has its final width.
        wait_until(lambda: window.get_width() == window.get_default_size()[0] and bool(window.document_view._boxes))
        process_pending_events()
    return opened


def action_enabled(window: "PenfoldWindow", name: str) -> bool:
    action = window.lookup_action(name)
    assert action is not None
    return bool(action.get_enabled())


def test_without_a_document_the_document_actions_are_off(window: "PenfoldWindow") -> None:
    assert window.is_empty
    assert window.stack.get_visible_child_name() == "welcome"
    for name in ("zoom-in", "fit-width", "next-page", "layout", "focus-page-entry"):
        assert not action_enabled(window, name), name


def test_opening_shows_the_document_and_its_header(window: "PenfoldWindow", book: Path) -> None:
    assert open_and_wait(window, book)
    assert not window.is_empty
    assert window.stack.get_visible_child_name() == "document"
    assert window.get_title() == "book.pdf — Penfold"
    title = window.document_header.title_widget
    assert (title.get_title(), title.get_subtitle()) == ("A Book", "book.pdf")
    entry = window.document_header.page_entry
    assert (entry.entry.get_text(), entry.position_label.get_label()) == ("i", "(1 of 12)")
    assert not window.protected_banner.get_revealed()
    assert action_enabled(window, "next-page")


def test_without_title_or_labels_the_header_shows_the_file_name(window: "PenfoldWindow", tmp_path: Path) -> None:
    assert open_and_wait(window, make_pdf(tmp_path / "plain.pdf"))
    title = window.document_header.title_widget
    assert (title.get_title(), title.get_subtitle()) == ("plain.pdf", "")
    assert window.document_header.page_entry.position_label.get_label() == "of 3"


def test_opens_fitted_to_the_width(window: "PenfoldWindow", book: Path) -> None:
    from penfold.ui.document_view import SIDE_MARGIN, Fit

    open_and_wait(window, book)
    view = window.document_view
    assert view.fit is Fit.WIDTH
    assert view.zoom == pytest.approx((view.get_width() - 2 * SIDE_MARGIN) / 595)
    assert not window.zoom_controls.fit_width_button.get_visible()
    assert window.zoom_controls.fit_page_button.get_visible()


def test_zoom_steps_and_limits(window: "PenfoldWindow", book: Path) -> None:
    from penfold.ui.document_view import MAX_ZOOM, Fit

    open_and_wait(window, book)
    view = window.document_view
    start = view.zoom
    window.activate_action("win.zoom-in", None)
    assert view.zoom == pytest.approx(start + 0.2)
    assert view.fit is Fit.MANUAL
    assert window.zoom_controls.fit_width_button.get_visible()
    for _ in range(30):
        view.zoom_in()
    assert view.zoom == MAX_ZOOM
    assert not action_enabled(window, "zoom-in")
    window.activate_action("win.fit-width", None)
    assert view.zoom == pytest.approx(start)


def test_page_keys_and_the_page_box_move_through_the_document(window: "PenfoldWindow", book: Path) -> None:
    open_and_wait(window, book)
    view, entry = window.document_view, window.document_header.page_entry
    window.activate_action("win.next-page", None)
    assert view.current_page == 1
    assert entry.entry.get_text() == "ii"
    window.activate_action("win.last-page", None)
    assert view.current_page == 11
    assert entry.position_label.get_label() == "(12 of 12)"
    entry.entry.set_text("3")
    entry.entry.emit("activate")
    assert view.current_page == 4  # the label "3" first, before the page number
    window.activate_action("win.first-page", None)
    assert view.current_page == 0


def test_page_box_puts_back_the_current_page_after_a_wrong_text(window: "PenfoldWindow", book: Path) -> None:
    open_and_wait(window, book)
    entry = window.document_header.page_entry
    entry.entry.set_text("99")
    entry.entry.emit("activate")
    assert entry.entry.get_text() == "i"
    assert window.document_view.current_page == 0


def test_two_pages_shows_pairs_fitted_whole(window: "PenfoldWindow", book: Path) -> None:
    from penfold.ui.document_view import Fit

    open_and_wait(window, book)
    view = window.document_view
    window.activate_action("win.layout", GLib.Variant.new_string("two-pages"))
    process_pending_events()
    assert view.two_pages
    assert view.fit is Fit.PAGE
    assert [box.page for box in view._boxes] == [0, 1]
    window.activate_action("win.next-page", None)
    assert [box.page for box in view._boxes] == [2, 3]
    window.activate_action("win.layout", GLib.Variant.new_string("continuous"))
    assert not window.document_view.two_pages
    assert len(view._boxes) == 12


def test_protected_pdf_opens_with_a_notice_and_a_banner(window: "PenfoldWindow", tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "locked.pdf", passwords=("owner", ""))
    assert open_and_wait(window, path)
    assert window.protected_banner.get_revealed()
    dialog = window.get_visible_dialog()
    assert isinstance(dialog, Adw.AlertDialog)
    assert dialog.get_heading() == "Protected PDF"


def test_pdf_with_a_password_is_not_opened(window: "PenfoldWindow", tmp_path: Path) -> None:
    path = make_pdf(tmp_path / "secret.pdf", passwords=("owner", "user"))
    assert not window.open_file(path)
    assert window.is_empty
    dialog = window.get_visible_dialog()
    assert isinstance(dialog, Adw.AlertDialog)
    assert dialog.get_heading() == "Could not open “secret.pdf”"


def test_a_failed_open_keeps_the_document_shown(window: "PenfoldWindow", book: Path, tmp_path: Path) -> None:
    open_and_wait(window, book)
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"not a PDF")
    assert not window.open_file(broken)
    assert window.document is not None
    assert window.document.file_name == "book.pdf"


def test_window_grows_to_the_remembered_size_with_a_document(window: "PenfoldWindow", book: Path) -> None:
    from gi.repository import Gio

    from penfold import config

    settings = Gio.Settings(schema_id=config.APP_ID)
    settings.set_int("window-width", 1000)
    settings.set_int("window-height", 750)
    window.set_default_size(620, 600)
    open_and_wait(window, book)
    assert window.get_default_size() == (1000, 750)


def test_internal_link_puts_its_height_on_the_top_third(window: "PenfoldWindow", book: Path) -> None:
    from penfold.rendering.page_content import InternalTarget, Link

    open_and_wait(window, book)
    view = window.document_view
    view.follow_link(Link((0, 0, 10, 10), InternalTarget(6, 400)))
    assert view.current_page == 6
    box = next(box for box in view._boxes if box.page == 6)
    vadjustment = view.vadjustment
    assert vadjustment is not None
    assert box.y + 400 * view.zoom - vadjustment.get_value() == pytest.approx(view.get_height() / 3)


def test_link_without_height_goes_to_the_start_of_the_page(window: "PenfoldWindow", book: Path) -> None:
    from penfold.rendering.page_content import InternalTarget, Link
    from penfold.ui.document_view import TOP_MARGIN

    open_and_wait(window, book)
    view = window.document_view
    view.follow_link(Link((0, 0, 10, 10), InternalTarget(3)))
    box = next(box for box in view._boxes if box.page == 3)
    assert view.vadjustment is not None
    assert view.vadjustment.get_value() == pytest.approx(box.y - TOP_MARGIN)


def test_pages_are_drawn_pixel_for_pixel(window: "PenfoldWindow", tmp_path: Path) -> None:
    """Sharp text: what the screen shows is the renderer's tile unchanged, even between two pixels of scroll."""
    from gi.repository import Gdk, Gsk, Gtk

    from penfold.rendering.renderer import round_scale
    from tests.test_page_content import make_text_pdf

    open_and_wait(window, make_text_pdf(tmp_path / "text.pdf"))
    view = window.document_view
    assert view.vadjustment is not None
    assert view.hadjustment is not None
    # A zoom with more decimals than the tiles' scale keeps, and a scroll position between two pixels.
    view.zoom_around(1.2345678, None)
    view.vadjustment.set_value(43.4)
    renderer = view.renderer
    assert renderer is not None
    scale = round_scale(view.zoom * view._device_scale())
    view.queue_draw()
    wait_until(lambda: any(key.page == 0 and key.scale == scale for key in renderer._cache))
    view.queue_draw()

    def draw_view() -> "Gsk.RenderNode | None":
        snapshot = Gtk.Snapshot()
        Gtk.WidgetPaintable.new(view).snapshot(snapshot, view.get_width(), view.get_height())
        return snapshot.to_node()

    wait_until(lambda: draw_view() is not None)
    node = draw_view()
    gsk_renderer = window.get_renderer()
    assert node is not None
    assert gsk_renderer is not None
    screen = gsk_renderer.render_texture(node, None)
    tile = next(texture for key, texture in renderer._cache.items() if key.page == 0 and key.scale == scale)
    screen_bytes, screen_stride = Gdk.TextureDownloader.new(screen).download_bytes()
    tile_bytes, tile_stride = Gdk.TextureDownloader.new(tile).download_bytes()
    screen_data, tile_data = screen_bytes.get_data(), tile_bytes.get_data()
    assert screen_data is not None
    assert tile_data is not None
    box = view._boxes[0]
    left, top = round(box.x - view.hadjustment.get_value()), round(box.y - view.vadjustment.get_value())
    for tile_y in range(60, 140, 3):  # the two lines of text, about 100 and 120 points from the top
        for tile_x in range(60, 300, 3):
            screen_offset = (top + tile_y) * screen_stride + (left + tile_x) * 4
            tile_offset = tile_y * tile_stride + tile_x * 4
            assert screen_data[screen_offset : screen_offset + 3] == tile_data[tile_offset : tile_offset + 3]


def test_control_wheel_zooms_around_the_pointer(window: "PenfoldWindow", book: Path) -> None:
    from penfold.ui.document_view import Fit

    open_and_wait(window, book)
    view = window.document_view
    pointer = (300.0, 200.0)
    before = view.page_point(*pointer)
    start = view.zoom
    view.zoom_around(start * 1.1, pointer)
    assert view.zoom == pytest.approx(start * 1.1)
    assert view.fit is Fit.MANUAL
    after = view.page_point(*pointer)
    assert before is not None
    assert after is not None
    assert after.page == before.page
    assert after.x == pytest.approx(before.x, abs=0.5)
    assert after.y == pytest.approx(before.y, abs=0.5)
