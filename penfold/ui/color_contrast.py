"""How well text in a colour can be read on a background, and the colour adjusted until it can (07-fase-12, 6).

Contrast as WCAG 2 measures it; the colour is made darker or lighter in OKLab, where lightness changes without changing
the hue.
"""

Color = tuple[float, float, float]

WHITE: Color = (1.0, 1.0, 1.0)
# The contrast that text needs to be read with ease (WCAG 2, level AA).
READABLE_CONTRAST = 4.5
# The luminance at which black and white have the same contrast on it: above it, darker text reads best.
EVEN_LUMINANCE = 0.179
# Where the sRGB curve stops being a straight line, before and after gamma.
SRGB_KNEE = 0.04045
LINEAR_KNEE = 0.0031308
BYTE = 255
SEARCH_STEPS = 24


def relative_luminance(color: Color) -> float:
    """How light a colour looks, from 0 (black) to 1 (white), as WCAG 2 measures it."""
    red, green, blue = (_linear(component) for component in color)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(first: Color, second: Color) -> float:
    """The contrast between two colours, from 1 (the same) to 21 (black and white), as WCAG 2 measures it."""
    lighter, darker = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def readable_on(color: Color, background: Color) -> Color:
    """The colour, darkened or lightened just enough for text in it to be read on the background.

    Only its lightness changes: darker on a light background, lighter on a dark one. A colour that can already be read
    is left as it is; the result can be written as #rrggbb without losing contrast.
    """
    if contrast(color, background) >= READABLE_CONTRAST:
        return color
    lightness, a, b = _to_oklab(color)
    readable = 0.0 if relative_luminance(background) > EVEN_LUMINANCE else 1.0
    unreadable = lightness
    for _step in range(SEARCH_STEPS):
        middle = (readable + unreadable) / 2
        if contrast(_from_oklab(middle, a, b), background) >= READABLE_CONTRAST:
            readable = middle
        else:
            unreadable = middle
    return _from_oklab(readable, a, b)


def _linear(component: float) -> float:
    """An sRGB component as light, without gamma."""
    return component / 12.92 if component <= SRGB_KNEE else ((component + 0.055) / 1.055) ** 2.4


def _gamma(component: float) -> float:
    """Light as an sRGB component, rounded to what #rrggbb can write; outside what a screen shows, the nearest."""
    component = min(1.0, max(0.0, component))
    value = component * 12.92 if component <= LINEAR_KNEE else 1.055 * component ** (1 / 2.4) - 0.055
    return round(value * BYTE) / BYTE


def _to_oklab(color: Color) -> Color:
    red, green, blue = (_linear(component) for component in color)
    long = (0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue) ** (1 / 3)
    medium = (0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue) ** (1 / 3)
    short = (0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue) ** (1 / 3)
    return (
        0.2104542553 * long + 0.7936177850 * medium - 0.0040720468 * short,
        1.9779984951 * long - 2.4285922050 * medium + 0.4505937099 * short,
        0.0259040371 * long + 0.7827717662 * medium - 0.8086757660 * short,
    )


def _from_oklab(lightness: float, a: float, b: float) -> Color:
    long = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    medium = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    short = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (
        _gamma(4.0767416621 * long - 3.3077115913 * medium + 0.2309699292 * short),
        _gamma(-1.2684380046 * long + 2.6097574011 * medium - 0.3413193965 * short),
        _gamma(-0.0041960863 * long - 0.7034186147 * medium + 1.7076147010 * short),
    )
