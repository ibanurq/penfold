"""The page list of the document: where each page comes from, its turn and its label."""

import pytest

from penfold.document.pages import Page, initial_pages


def test_initial_pages_keep_the_order_of_the_pdf() -> None:
    assert initial_pages(3, None) == [Page(0), Page(1), Page(2)]


def test_initial_pages_carry_their_labels() -> None:
    pages = initial_pages(3, ["i", "ii", "1"])
    assert [page.label for page in pages] == ["i", "ii", "1"]
    assert [page.source_index for page in pages] == [0, 1, 2]


@pytest.mark.parametrize(
    ("start", "degrees", "expected"),
    [(0, 90, 90), (0, -90, 270), (270, 90, 0), (90, 180, 270), (180, -360, 180), (0, 450, 90)],
)
def test_rotated_turns_in_quarter_turns(start: int, degrees: int, expected: int) -> None:
    page = Page(4, rotation=start, label="x")
    assert page.rotated(degrees) == Page(4, rotation=expected, label="x")


@pytest.mark.parametrize("degrees", [1, 45, -100])
def test_rotated_refuses_other_angles(degrees: int) -> None:
    with pytest.raises(ValueError, match="quarter turns"):
        Page(0).rotated(degrees)
