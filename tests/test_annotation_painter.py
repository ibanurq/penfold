"""Painting the annotations Penfold manages on the screen as they look once saved."""

from pathlib import Path

import cairo
import gi
import pytest

gi.require_version("Poppler", "0.18")
gi.require_foreign("cairo")
from gi.repository import Poppler  # noqa: E402

from penfold.document.commands.annotations import AddAnnotations  # noqa: E402
from penfold.document.commands.pages import RotatePages  # noqa: E402
from penfold.document.document import OpenDocument  # noqa: E402
from penfold.document.saving import save  # noqa: E402
from penfold.rendering.annotation_painter import paint_annotations  # noqa: E402
from penfold.rendering.layout import ShownPage  # noqa: E402
from tests.sample_pdfs import make_pdf  # noqa: E402
from tests.test_appearance import A4, every_kind, restyled  # noqa: E402

SCALE = 2
# Pixels that differ more than this in a colour channel are counted as different (edges are smoothed differently).
TOLERANCE = 48


def white_surface(size: tuple[float, float]) -> tuple[cairo.ImageSurface, cairo.Context]:
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, int(size[0] * SCALE), int(size[1] * SCALE))
    context = cairo.Context(surface)
    context.set_source_rgb(1, 1, 1)
    context.paint()
    context.scale(SCALE, SCALE)
    return surface, context


def differing_pixels(first: cairo.ImageSurface, second: cairo.ImageSurface) -> tuple[int, int]:
    """How many pixels differ, and how many are painted (not white) in either."""
    one, other = bytes(first.get_data()), bytes(second.get_data())
    different = painted = 0
    for offset in range(0, len(one), 4):
        a, b = one[offset : offset + 3], other[offset : offset + 3]
        if min(a) < 250 or min(b) < 250:
            painted += 1
            different += any(abs(x - y) > TOLERANCE for x, y in zip(a, b, strict=True))
    return different, painted


@pytest.mark.parametrize(("rotation", "formatted"), [(0, False), (90, False), (180, False), (270, False), (90, True)])
def test_the_screen_shows_what_is_saved(tmp_path: Path, rotation: int, *, formatted: bool) -> None:
    document = OpenDocument.open(make_pdf(tmp_path / "one.pdf", page_count=1))
    annotations = restyled(every_kind(0)) if formatted else every_kind(0)
    for annotation in annotations:
        document.execute(AddAnnotations(document, [annotation]))
    if rotation:
        document.execute(RotatePages(document, [0], rotation))
    target = tmp_path / "saved.pdf"
    save(document.save_plan(target))
    page = ShownPage(0, A4, rotation)
    painted, context = white_surface(page.size)
    paint_annotations(context, page, annotations)
    saved, context = white_surface(page.size)
    Poppler.Document.new_from_file(target.as_uri(), None).get_page(0).render_for_printing(context)
    different, total = differing_pixels(painted, saved)
    assert total > 10_000  # Something is painted.
    assert different / total < 0.02
