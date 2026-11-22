"""Rendering pages in the background (03-arquitectura, 4.2; B10)."""

from collections.abc import Iterator
from pathlib import Path

import cairo
import pikepdf
import pytest
from gi.repository import Gdk

from penfold.document.annotations import Kind
from penfold.document.commands.annotations import DeleteAnnotations
from penfold.document.document import OpenDocument
from penfold.document.pages import Page
from penfold.rendering import renderer as renderer_module
from penfold.rendering.renderer import MAX_WHOLE_PAGE_PIXELS, TILE_SIZE, Renderer, TileGrid, TileKey, grid, round_scale
from tests.gtk_helpers import wait_until
from tests.sample_pdfs import make_pdf, source_spans

A4 = (595.0, 842.0)


def make_black_square_pdf(path: Path) -> Path:
    """One A4 page, white, with a black square in its top left quarter."""
    surface = cairo.PDFSurface(str(path), *A4)
    context = cairo.Context(surface)
    context.rectangle(0, 0, A4[0] / 2, A4[1] / 2)
    context.fill()
    surface.finish()
    return path


@pytest.fixture
def renderer(tmp_path: Path) -> Iterator[Renderer]:
    page_renderer = Renderer(source_spans(make_black_square_pdf(tmp_path / "square.pdf")), worker_count=2)
    yield page_renderer
    page_renderer.close()


def test_small_pages_are_one_tile() -> None:
    page_grid = grid(A4, 1.0)
    assert (page_grid.width, page_grid.height, page_grid.columns, page_grid.rows) == (595, 842, 1, 1)


def test_large_pages_are_cut_in_tiles() -> None:
    page_grid = grid(A4, 8.0)
    assert page_grid.width * page_grid.height > MAX_WHOLE_PAGE_PIXELS
    assert page_grid.tile_size == TILE_SIZE
    assert (page_grid.columns, page_grid.rows) == (5, 7)
    assert page_grid.tile_rectangle(4, 6) == (4096, 6144, 4760 - 4096, 6736 - 6144)


def test_tile_rectangles_cover_the_page_without_overlapping() -> None:
    tiles = TileGrid(2500, 1100, 1024)
    area = sum(
        width * height
        for column in range(tiles.columns)
        for row in range(tiles.rows)
        for _x, _y, width, height in [tiles.tile_rectangle(column, row)]
    )
    assert area == 2500 * 1100


def test_almost_equal_scales_share_their_tiles() -> None:
    assert round_scale(1.234561) == round_scale(1.234559)


def draw(renderer: Renderer, key: TileKey) -> None:
    """Ask for one tile and wait until it is drawn."""
    renderer.request({key: 0})
    wait_until(lambda: renderer.texture(key) is not None)


def test_reads_the_page_sizes(renderer: Renderer) -> None:
    assert renderer.page_sizes == [A4]


def test_draws_the_requested_tile_in_the_background(renderer: Renderer) -> None:
    key = TileKey(0, 0, 0.5)
    rendered: list[int] = []
    renderer.connect("tile-rendered", lambda _renderer, page: rendered.append(page))
    assert renderer.texture(key) is None
    renderer.request({key: 0})
    wait_until(lambda: renderer.texture(key) is not None)
    texture = renderer.texture(key)
    assert texture is not None
    assert (texture.get_width(), texture.get_height()) == (298, 421)
    assert rendered == [0]


def brightness_at_corners(renderer: Renderer, key: TileKey) -> dict[str, bool]:
    """Draw a tile and tell which of its corners are dark."""
    draw(renderer, key)
    texture = renderer.texture(key)
    assert texture is not None
    width, height = texture.get_width(), texture.get_height()
    pixels, stride = Gdk.TextureDownloader.new(texture).download_bytes()
    data = pixels.get_data()
    assert data is not None
    corners = {"top left": (10, 10), "top right": (width - 10, 10), "bottom left": (10, height - 10)}
    return {name: data[y * stride + x * 4] < 20 for name, (x, y) in corners.items()}


def test_draws_the_page_content(renderer: Renderer) -> None:
    assert brightness_at_corners(renderer, TileKey(0, 0, 0.25)) == {
        "top left": True,
        "top right": False,
        "bottom left": False,
    }


def test_draws_turned_pages(renderer: Renderer) -> None:
    key = TileKey(0, 90, 0.25)
    assert renderer.key_grid(key).width == 211
    assert brightness_at_corners(renderer, key) == {"top left": False, "top right": True, "bottom left": False}
    assert brightness_at_corners(renderer, TileKey(0, 270, 0.25))["bottom left"]


def test_pages_are_asked_for_by_their_position(renderer: Renderer) -> None:
    renderer.set_pages([Page(0, rotation=90)], renderer.sources)
    assert renderer.page_sizes == [(A4[1], A4[0])]
    assert renderer.tile_key(0, 0.5) == TileKey(0, 90, 0.5)


def test_closest_textures_stand_in_while_drawing(renderer: Renderer) -> None:
    renderer.request({TileKey(0, 0, 0.5): 0})
    wait_until(lambda: renderer.texture(TileKey(0, 0, 0.5)) is not None)
    stand_ins = renderer.closest_textures(0, 0.75)
    assert [key for key, _texture in stand_ins] == [TileKey(0, 0, 0.5)]


def test_cache_forgets_the_oldest_tiles(renderer: Renderer, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(renderer_module, "CACHE_LIMIT_BYTES", 300 * 430 * 4)
    first, second = TileKey(0, 0, 0.5), TileKey(0, 0, 0.49)
    for key in (first, second):
        draw(renderer, key)
    assert renderer.texture(first) is None
    assert renderer.texture(second) is not None


def test_draws_the_pages_of_a_pdf_added_later(tmp_path: Path) -> None:
    spans = source_spans(make_pdf(tmp_path / "blank.pdf", page_count=2), make_black_square_pdf(tmp_path / "square.pdf"))
    page_renderer = Renderer(spans[:1], worker_count=1)
    try:
        assert len(page_renderer.page_sizes) == 2
        page_renderer.set_pages([Page(2), Page(0)], spans)
        assert page_renderer.sources == spans
        key = page_renderer.tile_key(0, 0.25)
        assert key == TileKey(2, 0, 0.25)
        assert brightness_at_corners(page_renderer, key)["top left"]
        assert not brightness_at_corners(page_renderer, page_renderer.tile_key(1, 0.25))["top left"]
    finally:
        page_renderer.close()


def test_draws_a_merged_document(tmp_path: Path) -> None:
    from penfold.document.document import OpenDocument, PdfToMerge

    paths = [make_black_square_pdf(tmp_path / "square.pdf"), make_pdf(tmp_path / "blank.pdf", page_count=2)]
    document = OpenDocument.merge(
        [PdfToMerge(path) for path in paths],
        tmp_path / "merged.pdf",
        bookmark_per_file=False,
        keep_bookmarks=False,
        respect_permissions=True,
    )
    page_renderer = Renderer(document.sources.spans, worker_count=1)
    try:
        assert len(page_renderer.page_sizes) == 3  # the PDF without pages it is built on adds none
        assert brightness_at_corners(page_renderer, page_renderer.tile_key(0, 0.25))["top left"]
    finally:
        page_renderer.close()
        document.close()


def make_annotated_pdf(path: Path) -> Path:
    """The black square page with annotations, the last a black square at the bottom right.

    Before it, a note and its pop-up window, and a freehand drawing Poppler cannot read (it has no strokes).
    """
    make_black_square_pdf(path)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        note = pdf.make_indirect(
            pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Text, Rect=[0, 0, 1, 1])
        )
        popup = pdf.make_indirect(
            pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Popup, Rect=[0, 0, 1, 1], Parent=note)
        )
        square = pdf.make_indirect(
            pikepdf.Dictionary(
                Type=pikepdf.Name.Annot,
                Subtype=pikepdf.Name.Square,
                Rect=[400, 50, 580, 250],
                C=pikepdf.Array([0, 0, 0]),
                IC=pikepdf.Array([0, 0, 0]),
                BS=pikepdf.Dictionary(W=1),
            )
        )
        broken = pdf.make_indirect(
            pikepdf.Dictionary(Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Ink, Rect=[0, 0, 9, 9])
        )
        pdf.pages[0].obj.Annots = pdf.make_indirect(pikepdf.Array([popup, note, broken, square]))
        pdf.save(path)
    return path


def dark_at(renderer: Renderer, key: TileKey, point: tuple[int, int]) -> bool:
    texture = renderer.texture(key)
    assert texture is not None
    pixels, stride = Gdk.TextureDownloader.new(texture).download_bytes()
    data = pixels.get_data()
    assert data is not None
    return data[point[1] * stride + point[0] * 4] < 20


def test_annotations_penfold_draws_instead_are_left_out(tmp_path: Path) -> None:
    document = OpenDocument.open(make_annotated_pdf(tmp_path / "annotated.pdf"))
    square = next(annotation for annotation in document.annotations if annotation.kind is Kind.RECTANGLE)
    assert square.drawn_place == 0  # The first square: the broken drawing, which Poppler skips, does not count.
    page_renderer = Renderer(document.sources.spans, worker_count=2)
    key, bottom_right = TileKey(0, 0, 0.5), (245, 340)
    try:
        draw(page_renderer, key)
        assert dark_at(page_renderer, key, bottom_right)
        document.execute(DeleteAnnotations(document, [square]))
        page_renderer.hide_annotations(document.replaced_annotations)
        assert page_renderer.texture(key) is None
        assert page_renderer.closest_textures(0, 0.5)  # The old drawing stands in meanwhile.
        draw(page_renderer, key)
        assert not dark_at(page_renderer, key, bottom_right)
        document.undo()
        page_renderer.hide_annotations(document.replaced_annotations)
        draw(page_renderer, key)
        assert dark_at(page_renderer, key, bottom_right)
    finally:
        page_renderer.close()
