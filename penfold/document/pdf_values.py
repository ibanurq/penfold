"""Reading plain values of a PDF (numbers, text) that annotations and form fields share."""

import pikepdf


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


def text(value: object) -> str:
    """Return a PDF text string without the spaces around it, or "" if it is not a string."""
    return str(value).strip() if isinstance(value, pikepdf.String) else ""
