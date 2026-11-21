"""Reading plain values of a PDF (numbers, rectangles, text) that annotations and form fields share."""

import pikepdf

# The height of a US Letter page, for a page without a usable media box.
DEFAULT_PAGE_HEIGHT = 792.0


def page_height(page: pikepdf.Page) -> float:
    """Return the height of the page's media box, in points."""
    box = page.mediabox
    numbers = [number(box[index]) for index in range(4)]
    return abs((numbers[3] or 0.0) - (numbers[1] or 0.0)) or DEFAULT_PAGE_HEIGHT


def number(value: object) -> float | None:
    """Return a PDF number as a float, or None if it is not a number."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def numbers(value: object) -> list[float] | None:
    """Return an array of numbers as floats, or None if it is not an array of numbers."""
    if not isinstance(value, pikepdf.Array):
        return None
    read = [number(value[index]) for index in range(len(value))]
    return None if None in read else [item or 0.0 for item in read]


def rectangle(value: object, height: float) -> tuple[float, float, float, float] | None:
    """Turn a PDF rectangle (from the bottom left corner, maybe inverted) into left, top, right, bottom from the top."""
    read = numbers(value)
    if read is None or len(read) != 4:  # noqa: PLR2004 (two corners)
        return None
    x1, y1, x2, y2 = read
    return min(x1, x2), height - max(y1, y2), max(x1, x2), height - min(y1, y2)


def text(value: object) -> str:
    """Return a PDF text string without the spaces around it, or "" if it is not a string."""
    return str(value).strip() if isinstance(value, pikepdf.String) else ""
