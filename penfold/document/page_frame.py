"""Where things are on a page as Poppler shows it: from the top left corner of its crop box, after its own turn.

Annotations and form fields are placed in this frame, the one of the text Poppler finds and of the pages it draws.
The turns Penfold gives pages (Page.rotation) come on top, when the pages are laid out.
"""

from dataclasses import dataclass

import pikepdf

from penfold.document.geometry import Rectangle, turn_point, turn_rectangle, unturn_point
from penfold.document.pages import FULL_TURN, QUARTER_TURN
from penfold.document.pdf_values import number, numbers

# How deep the page tree is followed to find a turn a page inherits.
MAX_DEPTH = 32
# The crop box of a page without a usable one: US Letter.
LETTER = (0.0, 0.0, 612.0, 792.0)


@dataclass(frozen=True)
class PageFrame:
    """The crop box of a page (left, bottom, right, top, in PDF units) and its own turn (/Rotate)."""

    crop_box: tuple[float, float, float, float]
    rotation: int = 0

    @classmethod
    def of(cls, page: pikepdf.Page) -> "PageFrame":
        """The frame of a page of a PDF."""
        return cls(_crop_box(page), _rotation(page.obj))

    @property
    def size(self) -> tuple[float, float]:
        """The width and height of the crop box, before the turn."""
        left, bottom, right, top = self.crop_box
        return right - left, top - bottom

    def place(self, value: object) -> Rectangle | None:
        """Turn a PDF rectangle (/Rect, maybe inverted) into left, top, right, bottom of the page as shown."""
        corners = numbers(value)
        if corners is None or len(corners) != 4:  # noqa: PLR2004 (two corners)
            return None
        left, _bottom, _right, top = self.crop_box
        x1, y1, x2, y2 = corners
        unturned = (min(x1, x2) - left, top - max(y1, y2), max(x1, x2) - left, top - min(y1, y2))
        return turn_rectangle(unturned, self.size, self.rotation)

    def point(self, x: float, y: float) -> tuple[float, float]:
        """Where a point of the PDF (from the bottom left corner) is on the page as shown."""
        left, _bottom, _right, top = self.crop_box
        return turn_point(x - left, top - y, self.size, self.rotation)

    def pdf_point(self, x: float, y: float) -> tuple[float, float]:
        """Where a point of the page as shown is in the PDF (from the bottom left corner)."""
        left, _bottom, _right, top = self.crop_box
        unturned_x, unturned_y = unturn_point(x, y, self.size, self.rotation)
        return left + unturned_x, top - unturned_y


def _crop_box(page: pikepdf.Page) -> tuple[float, float, float, float]:
    corners = numbers(page.cropbox) or []
    if len(corners) != 4:  # noqa: PLR2004 (two corners)
        return LETTER
    x1, y1, x2, y2 = corners
    box = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
    return box if box[2] > box[0] and box[3] > box[1] else LETTER


def _rotation(page: pikepdf.Object) -> int:
    """Return the page's own turn in degrees (0, 90, 180 or 270), which it may inherit from the page tree (7.7.3.4)."""
    node: pikepdf.Object | None = page
    for _ in range(MAX_DEPTH):
        if not isinstance(node, pikepdf.Dictionary):
            break
        if "/Rotate" in node:
            degrees = int(number(node.get("/Rotate")) or 0)
            return degrees % FULL_TURN if degrees % QUARTER_TURN == 0 else 0
        node = node.get("/Parent")
    return 0
