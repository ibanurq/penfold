"""Bookmark colours that can be read on the panel, light or dark, and on white (07-fase-12, 6)."""

import pytest

from penfold.ui.color_contrast import READABLE_CONTRAST, WHITE, contrast, readable_on, relative_luminance
from penfold.ui.palette import BOOKMARK_COLORS, hex_to_color
from penfold.ui.sidebar.bookmarks_view import panel_background

BLACK = (0.0, 0.0, 0.0)
OLD_COLORS = ("#f9f06b", "#8ff0a4", "#99c1f1", "#ffbe6f", "#f66151", "#dc8add", "#606971", "#ad182e")


def test_contrast_goes_from_one_to_twenty_one() -> None:
    assert contrast(BLACK, WHITE) == pytest.approx(21)
    assert contrast(WHITE, BLACK) == pytest.approx(21)
    assert contrast(WHITE, WHITE) == pytest.approx(1)


def test_the_bookmark_colours_are_the_accent_colours_darkened_just_enough_for_white() -> None:
    accents = ("#ad182e", "#ed5b00", "#3a944a", "#3584e4")
    assert [readable_on(hex_to_color(value), WHITE) for value in accents] == [
        hex_to_color(value) for value in BOOKMARK_COLORS
    ]
    for value in BOOKMARK_COLORS:
        assert READABLE_CONTRAST <= contrast(hex_to_color(value), WHITE) < 4.6 or value == "#ad182e"


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("value", BOOKMARK_COLORS + OLD_COLORS)
def test_any_bookmark_colour_is_read_on_the_panel(value: str, dark: bool) -> None:
    background = panel_background(dark=dark)
    color = hex_to_color(value)
    adjusted = readable_on(color, background)
    assert contrast(adjusted, background) >= READABLE_CONTRAST
    if contrast(color, background) >= READABLE_CONTRAST:
        assert adjusted == color  # Already readable: left as it is.
    elif dark:
        assert relative_luminance(adjusted) > relative_luminance(color)
    else:
        assert relative_luminance(adjusted) < relative_luminance(color)


def test_the_colour_changes_only_just_enough() -> None:
    adjusted = readable_on(hex_to_color("#3584e4"), WHITE)
    assert contrast(adjusted, WHITE) < READABLE_CONTRAST + 0.1
