"""Rendering pages in the background (03-arquitectura, 4.2; B10)."""

from collections.abc import Iterator
from pathlib import Path

import cairo
import pytest
from gi.repository import Gdk

from penfold.rendering import renderer as renderer_module
from penfold.rendering.renderer import MAX_WHOLE_PAGE_PIXELS, TILE_SIZE, Renderer, TileGrid, TileKey, round_scale
from tests.gtk_helpers import wait_until

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
    page_renderer = Renderer(make_black_square_pdf(tmp_path / "square.pdf"), worker_count=2)
    yield page_renderer
    page_renderer.close()


def test_small_pages_are_one_tile() -> None:
    grid = Renderer.grid(A4, 1.0)
    assert (grid.width, grid.height, grid.columns, grid.rows) == (595, 842, 1, 1)


def test_large_pages_are_cut_in_tiles() -> None:
    grid = Renderer.grid(A4, 8.0)
    assert grid.width * grid.height > MAX_WHOLE_PAGE_PIXELS
    assert grid.tile_size == TILE_SIZE
    assert (grid.columns, grid.rows) == (5, 7)
    assert grid.tile_rectangle(4, 6) == (4096, 6144, 4760 - 4096, 6736 - 6144)


def test_tile_rectangles_cover_the_page_without_overlapping() -> None:
    grid = TileGrid(2500, 1100, 1024)
    area = sum(
        width * height
        for column in range(grid.columns)
        for row in range(grid.rows)
        for _x, _y, width, height in [grid.tile_rectangle(column, row)]
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
    key = TileKey(0, 0.5)
    rendered: list[int] = []
    renderer.connect("tile-rendered", lambda _renderer, page: rendered.append(page))
    assert renderer.texture(key) is None
    renderer.request({key: 0})
    wait_until(lambda: renderer.texture(key) is not None)
    texture = renderer.texture(key)
    assert texture is not None
    assert (texture.get_width(), texture.get_height()) == (298, 421)
    assert rendered == [0]


def test_draws_the_page_content(renderer: Renderer) -> None:
    key = TileKey(0, 0.25)
    renderer.request({key: 0})
    wait_until(lambda: renderer.texture(key) is not None)
    texture = renderer.texture(key)
    assert texture is not None
    width, height = texture.get_width(), texture.get_height()
    pixels, stride = Gdk.TextureDownloader.new(texture).download_bytes()
    data = pixels.get_data()
    assert data is not None

    def brightness(x: int, y: int) -> int:
        return data[y * stride + x * 4]

    assert brightness(10, 10) < 20  # inside the black square
    assert brightness(width - 10, height - 10) > 235  # white page


def test_closest_textures_stand_in_while_drawing(renderer: Renderer) -> None:
    renderer.request({TileKey(0, 0.5): 0})
    wait_until(lambda: renderer.texture(TileKey(0, 0.5)) is not None)
    stand_ins = renderer.closest_textures(0, 0.75)
    assert [key for key, _texture in stand_ins] == [TileKey(0, 0.5)]


def test_cache_forgets_the_oldest_tiles(renderer: Renderer, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(renderer_module, "CACHE_LIMIT_BYTES", 300 * 430 * 4)
    first, second = TileKey(0, 0.5), TileKey(0, 0.49)
    for key in (first, second):
        draw(renderer, key)
    assert renderer.texture(first) is None
    assert renderer.texture(second) is not None
