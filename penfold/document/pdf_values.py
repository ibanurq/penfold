"""Reading plain values of a PDF (numbers, text, dates) that annotations and form fields share."""

import re
from datetime import UTC, datetime, timedelta, timezone

import pikepdf

# A PDF date (7.9.4): D:YYYYMMDDHHmmSS, then Z or the offset from UTC (+HH'mm'); all but the year may be left out.
DATE = re.compile(r"(?:D:)?(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?(?:(Z)|([+-])(\d{2})'?(\d{2})?'?)?")


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


def date(value: object) -> datetime | None:
    """Return a PDF date (7.9.4), or None if it is not one; without an offset from UTC, it is taken as UTC."""
    found = DATE.match(text(value))
    if found is None:
        return None
    year, month, day, hour, minute, second, _z, sign, offset_hours, offset_minutes = found.groups()
    offset = timedelta(hours=int(offset_hours or 0), minutes=int(offset_minutes or 0))
    zone = timezone(-offset if sign == "-" else offset) if sign else UTC
    try:
        return datetime(
            int(year), int(month or 1), int(day or 1), int(hour or 0), int(minute or 0), int(second or 0), tzinfo=zone
        )
    except ValueError:
        return None


def name(value: object) -> str:
    """Return a PDF name without its slash ("OpenArrow"), or "" if it is not a name."""
    return str(value)[1:] if isinstance(value, pikepdf.Name) else ""
