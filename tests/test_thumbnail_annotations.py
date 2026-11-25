"""Thumbnails show the annotations as the pages of the document do (07-fase-12, 12)."""

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from gi.repository import Gdk, Gsk, Gtk

from penfold.document.annotations import Annotation, Kind, Style, new_annotation
from penfold.document.commands.annotations import AddAnnotations, DeleteAnnotations
from tests.gtk_helpers import process_pending_events, wait_until
from tests.sample_pdfs import make_pdf
from tests.test_renderer import make_annotated_pdf
from tests.test_sidebar import open_and_wait

if TYPE_CHECKING:
    from penfold.application import PenfoldApplication
    from penfold.ui.window import PenfoldWindow

BLUE = (0.6, 0.757, 0.945)
WHITE = (255, 255, 255)


@pytest.fixture
def window(application: "PenfoldApplication") -> Iterator["PenfoldWindow"]:
    from penfold.ui.window import PenfoldWindow

    new_window = PenfoldWindow(application)
    new_window.set_default_size(1100, 750)
    new_window.present()
    yield new_window
    new_window.destroy()
    process_pending_events()


def thumbnail_pixel(window: "PenfoldWindow", position: int, x_points: float, y_points: float) -> tuple[int, ...]:
    """The colour of a thumbnail at a point of its page, once it is drawn."""
    from penfold.ui.sidebar.pages_view import fit_page

    pages = window.pages_view
    wait_until(lambda: position in pages._cells and pages.texture(position) is not None)
    thumbnail = pages._cells[position].thumbnail

    def draw() -> "Gsk.RenderNode | None":
        snapshot = Gtk.Snapshot()
        Gtk.WidgetPaintable.new(thumbnail).snapshot(snapshot, thumbnail.get_width(), thumbnail.get_height())
        return snapshot.to_node()

    wait_until(lambda: draw() is not None)  # Once it has been drawn on the screen.
    node = draw()
    renderer = window.get_renderer()
    assert node is not None
    assert renderer is not None
    assert pages.renderer is not None
    downloader = Gdk.TextureDownloader.new(renderer.render_texture(node, None))
    downloader.set_format(Gdk.MemoryFormat.R8G8B8)
    data, stride = downloader.download_bytes()
    pixels = data.get_data()
    assert pixels is not None
    page_size = pages.renderer.page_sizes[position]
    left, top, width, _height = fit_page(page_size, thumbnail.get_width(), thumbnail.get_height())
    # The node starts where the frame around the page does, which may stick out of the thumbnail.
    bounds = node.get_bounds()
    x = round(left + x_points * width / page_size[0] - bounds.get_x())
    y = round(top + y_points * width / page_size[0] - bounds.get_y())
    return tuple(pixels[y * stride + x * 3 : y * stride + x * 3 + 3])


@pytest.mark.parametrize(
    "annotation",
    [
        new_annotation(Kind.HIGHLIGHT, 1, (100, 100, 400, 200), BLUE, "Iban", quads=((100, 100, 400, 200),)),
        new_annotation(Kind.RECTANGLE, 1, (100, 100, 400, 200), BLUE, "Iban", style=Style(filled=True)),
    ],
)
def test_a_thumbnail_shows_the_annotations_made_until_undone(
    window: "PenfoldWindow", tmp_path: Path, annotation: Annotation
) -> None:
    open_and_wait(window, make_pdf(tmp_path / "five.pdf", page_count=5))
    document = window.document
    assert document is not None
    assert thumbnail_pixel(window, 1, 250, 150) == WHITE
    document.execute(AddAnnotations(document, [annotation]))
    painted = thumbnail_pixel(window, 1, 250, 150)
    assert painted != WHITE
    assert painted[2] > painted[0]  # Blue.
    document.undo()
    assert thumbnail_pixel(window, 1, 250, 150) == WHITE
    document.redo()
    assert thumbnail_pixel(window, 1, 250, 150) == painted


def test_a_thumbnail_leaves_out_an_annotation_of_the_pdf_deleted(window: "PenfoldWindow", tmp_path: Path) -> None:
    open_and_wait(window, make_annotated_pdf(tmp_path / "annotated.pdf"))
    document = window.document
    assert document is not None
    square = next(annotation for annotation in document.annotations if annotation.kind is Kind.RECTANGLE)
    bottom_right = (490, 680)  # Inside the black square of the PDF's own annotation.

    def dark() -> bool:
        return thumbnail_pixel(window, 0, *bottom_right)[0] < 60

    assert dark()
    document.execute(DeleteAnnotations(document, [square]))
    wait_until(lambda: not dark())
    # Drawn again at its own size, not only stood in for by the drawing of the large page.
    pages = window.pages_view
    wait_until(lambda: pages.renderer is not None and pages.renderer.texture(pages._key(0)) is not None)  # type: ignore[arg-type]
    document.undo()
    wait_until(dark)


def test_the_layer_tells_which_pages_changed() -> None:
    from penfold.ui.annotation_layer import AnnotationLayer

    first = new_annotation(Kind.RECTANGLE, 0, (10, 10, 50, 50), BLUE, "Iban")
    second = new_annotation(Kind.RECTANGLE, 2, (10, 10, 50, 50), BLUE, "Iban")
    layer = AnnotationLayer()
    assert layer.update([first, second]) == {0, 2}
    assert layer.update([first, second]) == set()
    assert layer.update([first]) == {2}
    assert layer.update([first, second], left_out=first) == {0, 2}
    assert layer.painted == {2: [second]}
