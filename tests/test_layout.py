"""The layout: pages of the opened PDF shown in the document's order and turned."""

import pytest

from penfold.document.pages import Page
from penfold.rendering.layout import PageLayout, turn_point, turn_rectangle, turned_size, unturn_point

SIZE = (100.0, 200.0)


@pytest.mark.parametrize(
    ("rotation", "expected"), [(0, (10.0, 20.0)), (90, (180.0, 10.0)), (180, (90.0, 180.0)), (270, (20.0, 90.0))]
)
def test_points_turn_clockwise_with_the_page(rotation: int, expected: tuple[float, float]) -> None:
    assert turn_point(10, 20, SIZE, rotation) == expected
    assert unturn_point(*expected, SIZE, rotation) == (10, 20)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_the_corners_of_a_page_stay_on_the_turned_page(rotation: int) -> None:
    width, height = turned_size(SIZE, rotation)
    corners = [turn_point(x, y, SIZE, rotation) for x, y in ((0, 0), (100, 0), (0, 200), (100, 200))]
    assert sorted(corners) == sorted([(0, 0), (width, 0), (0, height), (width, height)])


def test_rectangles_turn_and_stay_ordered() -> None:
    assert turn_rectangle((10, 20, 30, 60), SIZE, 90) == (140, 10, 180, 30)


def test_the_layout_follows_the_document_pages() -> None:
    layout = PageLayout([(100, 200), (300, 400), (500, 600)], [Page(2, rotation=90), Page(0)])
    assert len(layout) == 2
    assert layout.sizes == [(600, 500), (100, 200)]
    assert (layout.position(2), layout.position(0), layout.position(1)) == (0, 1, None)
    assert layout[0].to_source(0, 0) == (0, 600)


def test_by_default_every_page_in_order() -> None:
    layout = PageLayout([(100, 200), (300, 400)])
    assert [page.source for page in layout.pages] == [0, 1]


@pytest.mark.parametrize(("rotation", "expected"), [(0, (1, 50.0)), (180, (1, 150.0)), (90, (1, None))])
def test_destinations_are_placed_on_the_shown_page(rotation: int, expected: tuple[int, float | None]) -> None:
    layout = PageLayout([SIZE, SIZE], [Page(1), Page(0, rotation=rotation)])
    assert layout.place(0, 50) == expected
    assert layout.place(0, None) == (1, None)


def test_destinations_on_deleted_pages_have_no_place() -> None:
    assert PageLayout([SIZE, SIZE], [Page(1)]).place(0, 10) is None
