"""The pages of the open document: which page of the PDF each one is, how it is turned and what it is called.

Penfold does not change the PDF while it is open. Its pages are a list that the edits reorder, turn and shorten; the
PDF is rewritten from that list only when it is saved (03-arquitectura, 6).
"""

from dataclasses import dataclass, replace
from typing import Self

from penfold.document.page_labels import PageLabel

QUARTER_TURN = 90
FULL_TURN = 360


@dataclass(frozen=True)
class Page:
    """One page of the document as it is now.

    Attributes:
        source_index: index of the page in the opened PDF.
        rotation: clockwise turn that Penfold adds to the page's own, in degrees: 0, 90, 180 or 270.
        label: the page's own label (D14), which it keeps wherever it goes; None if it has none, and then it is named
            by its position.
    """

    source_index: int
    rotation: int = 0
    label: PageLabel | None = None

    def rotated(self, degrees: int) -> Self:
        """Return the page turned clockwise by some degrees, a multiple of 90 (negative degrees turn it left).

        Raises:
            ValueError: the turn is not a multiple of 90 degrees.
        """
        if degrees % QUARTER_TURN:
            message = f"pages turn in quarter turns, not by {degrees} degrees"
            raise ValueError(message)
        return replace(self, rotation=(self.rotation + degrees) % FULL_TURN)


def initial_pages(page_count: int, labels: list[PageLabel] | None) -> list[Page]:
    """Return the pages of a PDF as it was opened: in order, not turned, with their labels if it has any."""
    if labels is None:
        return [Page(index) for index in range(page_count)]
    return [Page(index, label=label) for index, label in enumerate(labels)]
