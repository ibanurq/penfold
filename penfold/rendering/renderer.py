"""Page rendering with Poppler in worker threads, with a texture cache.

The interface never waits for Poppler: it says which pieces of which pages it wants, and the renderer draws them in the
background, nearest first, and announces each one with the "tile-rendered" signal. Each worker thread opens its own
copy of the source PDFs, because a Poppler document must not be shared between threads.

A page is drawn whole while it is small enough; at high zoom it is drawn in square tiles, so that it stays sharp without
using too much memory.

The interface asks for pages by their position in the document; the layout says which source page that is (its
source index) and its turn. Drawn tiles are kept by source index and turn, so moving pages does not draw them again.

Poppler leaves out the annotations of the PDFs that Penfold draws instead (changed) or that were deleted; when they
change, the pages they are on are drawn again.
"""

import math
import threading
from collections import OrderedDict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import ClassVar

import cairo
from gi.repository import Gdk, GLib, GObject, Poppler

from penfold.document.annotations import Annotation
from penfold.document.geometry import Size, turned_size
from penfold.document.pages import Page
from penfold.document.sources import Spans
from penfold.rendering.layout import PageLayout
from penfold.rendering.poppler_sources import PopplerSources

# Every annotation but form fields, which the view shows as widgets to fill in.
SHOWN_ANNOTATIONS = Poppler.RenderAnnotsFlags.ALL ^ Poppler.RenderAnnotsFlags.WIDGET  # type: ignore[attr-defined]
# A page larger than this, in pixels, is drawn in tiles.
MAX_WHOLE_PAGE_PIXELS = 16 * 1024 * 1024
TILE_SIZE = 1024
CACHE_LIMIT_BYTES = 384 * 1024 * 1024
BYTES_PER_PIXEL = 4
SCALE_DECIMALS = 4
# Poppler draws one page at a time, even with a document per thread: drawing in parallel corrupted its memory now and
# then ("double free" in page.render with three workers drawing at once). The workers still prepare and hand over the
# tiles in parallel. Anything else that draws with Poppler (printing) takes this lock too.
POPPLER_DRAWING = threading.Lock()


@dataclass(frozen=True, order=True)
class TileKey:
    """One rendered piece of a page.

    The page is its source index (document/sources.py), drawn with a turn; the scale is in pixels per PDF point; the
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
    """Draws the pages of a document in the background and keeps the latest results."""

    __gsignals__: ClassVar = {
        # The source index of the page a tile belongs to.
        "tile-rendered": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self, sources: Spans, worker_count: int = 3) -> None:
        """Open the source PDFs for rendering, showing all their pages in order.

        Raises:
            GLib.Error: Poppler cannot open one of them.
        """
        super().__init__()
        self._spans: Spans = ()
        self._main_sources = PopplerSources(lambda: self._spans)
        self._source_sizes: list[Size] = []
        self._add_sources(sources)
        self.layout = PageLayout(self._source_sizes)
        self._cache: OrderedDict[TileKey, Gdk.Texture] = OrderedDict()
        self._cache_bytes = 0
        # Tiles of pages whose hidden annotations changed, shown until they are drawn again.
        self._stale: dict[TileKey, Gdk.Texture] = {}
        # What each part of the interface wants (the document, the thumbnails…), so they do not replace each other.
        self._wanted: dict[str, dict[TileKey, int]] = {}
        self._in_progress: set[TileKey] = set()
        # The annotations Poppler leaves out, by source index: by their subtype and drawn place, with their name; and
        # how many times those of each page changed, so that a tile drawn before a change is not kept.
        self._hidden: dict[int, Mapping[tuple[str, int], str]] = {}
        self._hidden_changes: dict[int, int] = {}
        self._condition = threading.Condition()
        self._closed = False
        self._threads = [
            threading.Thread(target=self._work, name=f"penfold-render-{number}", daemon=True)
            for number in range(worker_count)
        ]
        for thread in self._threads:
            thread.start()

    @property
    def sources(self) -> Spans:
        """The source PDFs, to open them again in other threads (the search)."""
        return self._spans

    @property
    def poppler(self) -> PopplerSources:
        """Poppler's copies of the source PDFs for the main thread (links, text), never used by the workers."""
        return self._main_sources

    @property
    def page_sizes(self) -> list[Size]:
        """The size of each page of the document as it is shown, in points."""
        return self.layout.sizes

    def set_pages(self, pages: Iterable[Page], sources: Spans) -> None:
        """Show the pages of the document in their new order and turn (after an edit), with any source added.

        Raises:
            GLib.Error: Poppler cannot open a source added.
        """
        self._add_sources(sources[len(self._spans) :])
        self.layout = PageLayout(self._source_sizes, pages)

    def _add_sources(self, added: Spans) -> None:
        """Take sources added after the known ones, reading the size of their pages."""
        self._spans = (*self._spans, *added)
        for span in added:
            if not span.page_count:
                continue  # The PDF without pages a merged document is built on.
            document, _start = self._main_sources.document(span.start)
            self._source_sizes.extend(document.get_page(index).get_size() for index in range(span.page_count))

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
            for key, texture in {**self._stale, **self._cache}.items()
            if key.source == page.source and key.rotation == page.rotation
        ]
        if not tiles:
            return []
        nearest = min({key.scale for key, _texture in tiles}, key=lambda cached: abs(math.log(cached / scale)))
        return [(key, texture) for key, texture in tiles if key.scale == nearest]

    def hide_annotations(self, annotations: Iterable[Annotation]) -> None:
        """Have Poppler leave out these annotations of the PDFs, and draw again the pages whose hidden ones changed.

        Until the new tiles are drawn, the old ones are still shown (closest_textures).
        """
        hidden: dict[int, dict[tuple[str, int], str]] = {}
        for annotation in annotations:
            if annotation.drawn_place is not None:
                hidden.setdefault(annotation.page, {})[annotation.subtype, annotation.drawn_place] = annotation.name
        changed = {source for source in {*hidden, *self._hidden} if hidden.get(source) != self._hidden.get(source)}
        if not changed:
            return
        with self._condition:
            self._hidden = dict(hidden)
            for source in changed:
                self._hidden_changes[source] = self._hidden_changes.get(source, 0) + 1
        for key in [key for key in self._cache if key.source in changed]:
            self._stale[key] = self._cache.pop(key)
        for source in changed:
            self.emit("tile-rendered", source)

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
        self._stale.clear()
        self._cache_bytes = 0

    def _next_request(self) -> tuple[TileKey, Mapping[tuple[str, int], str], int] | None:
        """Wait for a tile to draw and take it; None when the renderer is closed.

        It comes with the annotations to hide on its page, and how many times those changed.
        """
        with self._condition:
            while not self._closed:
                for channel in sorted(self._wanted, key=lambda name: (name != "view", name)):
                    wanted = self._wanted[channel]
                    pending = [key for key in wanted if key not in self._in_progress]
                    if pending:
                        key = min(pending, key=lambda candidate: (wanted[candidate], candidate))
                        self._in_progress.add(key)
                        return key, self._hidden.get(key.source, {}), self._hidden_changes.get(key.source, 0)
                self._condition.wait()
            return None

    def _work(self) -> None:
        """Body of a worker thread: draw the requested tiles one after another."""
        sources = PopplerSources(lambda: self._spans)
        while (request := self._next_request()) is not None:
            key, hidden, changes = request
            with POPPLER_DRAWING:
                sources.hide_annotations(key.source, hidden)
            texture = draw_tile(sources.page(key.source), key)
            GLib.idle_add(self._deliver, key, texture, changes)

    def _deliver(self, key: TileKey, texture: Gdk.Texture, changes: int) -> bool:
        """Store a drawn tile and announce it, in the main thread.

        One drawn before the hidden annotations of its page changed is dropped, and drawn again when it is asked for.
        """
        with self._condition:
            self._in_progress.discard(key)
            if self._closed:
                return GLib.SOURCE_REMOVE
            outdated = changes != self._hidden_changes.get(key.source, 0)
            if not outdated:
                for wanted in self._wanted.values():
                    wanted.pop(key, None)
        if outdated:
            self.emit("tile-rendered", key.source)
            return GLib.SOURCE_REMOVE
        self._cache[key] = texture
        self._stale.pop(key, None)
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
    with POPPLER_DRAWING:
        page.render_full(context, False, SHOWN_ANNOTATIONS)  # type: ignore[attr-defined]  # False: not printing
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
