"""The stamps Penfold puts on pages: what each is called in the PDF (/Name) and its colour, in the order of its menu.

Six are of the standard (ISO 32000-1, table 181); Received and Paid are not, so other programs do not know them by their
name, but every viewer shows them as Penfold does: Penfold writes their drawing (rendering/stamp_look.py). They come in
three groups, by what their colour says, from GNOME's palette: green, what is right or done; blue, what is under way;
red, what warns.
"""

from dataclasses import dataclass

GREEN = (0.149, 0.635, 0.412)  # #26a269
BLUE = (0.110, 0.443, 0.847)  # #1c71d8
RED = (0.753, 0.110, 0.157)  # #c01c28


@dataclass(frozen=True)
class Stamp:
    """One of Penfold's stamps: its name in the PDF (/Name) and its colour."""

    name: str
    color: tuple[float, float, float]


STAMP_GROUPS: tuple[tuple[Stamp, ...], ...] = (
    (Stamp("Approved", GREEN), Stamp("Final", GREEN), Stamp("Received", GREEN), Stamp("Paid", GREEN)),
    (Stamp("Draft", BLUE), Stamp("ForComment", BLUE)),
    (Stamp("NotApproved", RED), Stamp("Confidential", RED)),
)
STAMPS = {stamp.name: stamp for group in STAMP_GROUPS for stamp in group}
