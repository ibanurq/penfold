"""Page rendering with Poppler in worker threads, with a texture cache (03-arquitectura, 4.2).

The interface never waits for Poppler: it says which pieces of which pages it wants, and the renderer draws them in the
background, nearest first, and announces each one with the "tile-rendered" signal. Each worker thread opens its own
copy of the document, because a Poppler document must not be shared between threads.

A page is drawn whole while it is small enough; at high zoom it is drawn in square tiles, so that it stays sharp
without using too much memory (B10).

The interface asks for pages by their position in the document; the layout says which page of the opened PDF that is,
and its turn. Drawn tiles are kept by page of the PDF and turn, so moving pages does not draw them again.
"""

import math
import threading
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import cairo
from gi.repository import Gdk, GLib, GObject, Poppler

from penfold.document.pages import Page
from penfold.rendering.layout import PageLayout, Size, turned_size

# A page larger than this, in pixels, is drawn in tiles.
MAX_WHOLE_PAGE_PIXELS = 16 * 1024 * 1024
TILE_SIZE = 1024
CACHE_LIMIT_BYTES = 384 * 1024 * 1024
BYTES_PER_PIXEL = 4
SCALE_DECIMALS = 4


@dataclass(frozen=True, order=True)
class TileKey:
    """One rendered piece of a page.

    The page is its index in the opened PDF (its source), drawn with a turn; the scale is in pixels per PDF point; the
    column and row place the tile in the page. A page drawn whole is the single tile (0, 0).
    """

    source: int
    rotation: int
    scale: float
    column: int = 0
    row: int = 0


@dataclass(frozen=True)
class TileGrid:
    """How a page is cut into tiles at one scale, in pixels."""

    width: int
    height: int
    tile_size: int

    @property
    def columns(self) -> int:
        """Number of tile columns."""
        return math.ceil(self.width / self.tile_size)

    @property
    def rows(self) -> int:
        """Number of tile rows."""
        return math.ceil(self.height / self.tile_size)

    def tile_rectangle(self, column: int, row: int) -> tuple[int, int, int, int]:
        """Return the x, y, width and height of a tile, in pixels of the page."""
        x, y = column * self.tile_size, row * self.tile_size
        return x, y, min(self.tile_size, self.width - x), min(self.tile_size, self.height - y)


def round_scale(scale: float) -> float:
    """Round a scale so that tiles asked for at almost the same zoom share their cache entry."""
    return round(scale, SCALE_DECIMALS)


class Renderer(GObject.Object):
    """Draws the pages of one PDF in the background and keeps the latest results."""

    __gsignals__: ClassVar = {
        # The index, in the opened PDF, of the page a tile belongs to.
        "tile-rendered": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self, path: Path, worker_count: int = 3) -> None:
        """Open the PDF for rendering; it raises GLib.Error if Poppler cannot open it."""
        super().__init__()
        self._uri = GLib.filename_to_uri(str(path.resolve()), None)
        document = Poppler.Document.new_from_file(self._uri, None)
        self._source_sizes: list[Size] = [
            document.get_page(index).get_size() for index in range(document.get_n_pages())
        ]
        self.layout = PageLayout(self._source_sizes)
        self._main_document = document
        self._cache: OrderedDict[TileKey, Gdk.Texture] = OrderedDict()
        self._cache_bytes = 0
        # What each part of the interface wants (the document, the thumbnails…), so they do not replace each other.
        self._wanted: dict[str, dict[TileKey, int]] = {}
        self._in_progress: set[TileKey] = set()
        self._condition = threading.Condition()
        self._closed = False
        self._threads = [
            threading.Thread(target=self._work, name=f"penfold-render-{number}", daemon=True)
            for number in range(worker_count)
        ]
        for thread in self._threads:
            thread.start()

    @property
    def uri(self) -> str:
        """Address of the PDF, to open it again in other threads (the search)."""
        return self._uri

    @property
    def document(self) -> Poppler.Document:
        """Poppler's copy of the document for the main thread (links, text), never used by the workers."""
        return self._main_document

    @property
    def page_sizes(self) -> list[Size]:
        """The size of each page of the document as it is shown, in points."""
        return self.layout.sizes

    def set_pages(self, pages: Iterable[Page]) -> None:
        """Show the pages of the document in their new order and turn (after an edit)."""
        self.layout = PageLayout(self._source_sizes, pages)

    def tile_key(self, position: int, scale: float, column: int = 0, row: int = 0) -> TileKey:
        """The key of a tile of the page shown at a position of the document."""
        page = self.layout[position]
        return TileKey(page.source, page.rotation, scale, column, row)

    def key_grid(self, key: TileKey) -> TileGrid:
        """How the page of a tile is cut into tiles at the tile's scale."""
        return grid(turned_size(self._source_sizes[key.source], key.rotation), key.scale)

    def texture(self, key: TileKey) -> Gdk.Texture | None:
        """Return a tile if it has already been drawn."""
        texture = self._cache.get(key)
        if texture is not None:
            self._cache.move_to_end(key)
        return texture

    def closest_textures(self, position: int, scale: float) -> list[tuple[TileKey, Gdk.Texture]]:
        """Return the drawn tiles of the page at a position, at the cached scale nearest to the one wanted.

        They are shown, stretched, while the tiles at the right scale are being drawn, so a page is never blank after
        zooming.
        """
        page = self.layout[position]
        tiles = [
            (key, texture)
            for key, texture in self._cache.items()
            if key.source == page.source and key.rotation == page.rotation
        ]
        if not tiles:
            return []
        nearest = min({key.scale for key, _texture in tiles}, key=lambda cached: abs(math.log(cached / scale)))
        return [(key, texture) for key, texture in tiles if key.scale == nearest]

    def request(self, wanted: dict[TileKey, int], channel: str = "view") -> None:
        """Ask for these tiles, with their priority (lower first), for one part of the interface.

        Tiles that part asked for earlier and that are not drawn yet are dropped. The document view goes first, then
        the other parts in alphabetical order (thumbnails).
        """
        with self._condition:
            self._wanted[channel] = {key: priority for key, priority in wanted.items() if key not in self._cache}
            self._condition.notify_all()

    def close(self) -> None:
        """Stop the worker threads and forget the drawn pages."""
        with self._condition:
            self._closed = True
            self._wanted.clear()
            self._condition.notify_all()
        self._cache.clear()
        self._cache_bytes = 0

    def _next_request(self) -> TileKey | None:
        """Wait for a tile to draw and take it; None when the renderer is closed."""
        with self._condition:
            while not self._closed:
                for channel in sorted(self._wanted, key=lambda name: (name != "view", name)):
                    wanted = self._wanted[channel]
                    pending = [key for key in wanted if key not in self._in_progress]
                    if pending:
                        key = min(pending, key=lambda candidate: (wanted[candidate], candidate))
                        self._in_progress.add(key)
                        return key
                self._condition.wait()
            return None

    def _work(self) -> None:
        """Body of a worker thread: draw the requested tiles one after another."""
        document = Poppler.Document.new_from_file(self._uri, None)
        while (key := self._next_request()) is not None:
            texture = draw_tile(document.get_page(key.source), key)
            GLib.idle_add(self._deliver, key, texture)

    def _deliver(self, key: TileKey, texture: Gdk.Texture) -> bool:
        """Store a drawn tile and announce it, in the main thread."""
        with self._condition:
            self._in_progress.discard(key)
            for wanted in self._wanted.values():
                wanted.pop(key, None)
            if self._closed:
                return GLib.SOURCE_REMOVE
        self._cache[key] = texture
        self._cache_bytes += texture.get_width() * texture.get_height() * BYTES_PER_PIXEL
        self._trim_cache()
        self.emit("tile-rendered", key.source)
        return GLib.SOURCE_REMOVE

    def _trim_cache(self) -> None:
        """Forget the tiles used longest ago until the cache fits in its limit."""
        while self._cache_bytes > CACHE_LIMIT_BYTES and len(self._cache) > 1:
            _key, texture = self._cache.popitem(last=False)
            self._cache_bytes -= texture.get_width() * texture.get_height() * BYTES_PER_PIXEL


def grid(page_size: Size, scale: float) -> TileGrid:
    """Return how a page of this size, in points, is cut into tiles at a scale."""
    width = max(1, math.ceil(page_size[0] * scale))
    height = max(1, math.ceil(page_size[1] * scale))
    tile_size = max(width, height) if width * height <= MAX_WHOLE_PAGE_PIXELS else TILE_SIZE
    return TileGrid(width, height, tile_size)


def draw_tile(page: Poppler.Page, key: TileKey) -> Gdk.Texture:
    """Draw one tile of a page, turned, on a white background and return it as a texture (in any thread)."""
    source_size = page.get_size()
    tile_grid = grid(turned_size(source_size, key.rotation), key.scale)
    x, y, width, height = tile_grid.tile_rectangle(key.column, key.row)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    context = cairo.Context(surface)
    context.set_source_rgb(1, 1, 1)
    context.paint()
    context.translate(-x, -y)
    context.scale(key.scale, key.scale)
    _turn(context, source_size, key.rotation)
    page.render(context)
    surface.flush()
    return Gdk.MemoryTexture.new(
        width,
        height,
        Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED,
        GLib.Bytes.new(bytes(surface.get_data())),
        surface.get_stride(),
    )


def _turn(context: cairo.Context, source_size: Size, rotation: int) -> None:
    """Turn the drawing clockwise, keeping the turned page at the top left corner (as layout.turn_point does)."""
    width, height = source_size
    origin = {90: (height, 0.0), 180: (width, height), 270: (0.0, width)}.get(rotation)
    if origin is not None:
        context.translate(*origin)
        context.rotate(math.radians(rotation))
