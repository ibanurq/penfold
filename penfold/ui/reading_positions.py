"""Where each document was left, to show it there when it is opened again.

The positions are kept on the user's computer, in a small file of Penfold's own (never in the PDFs), for the
documents opened most recently. Each change reads the file again before writing it, so that several windows do not
undo each other's positions. A file that cannot be read or written is only logged: remembering is a convenience.
"""

import json
import logging
import tempfile
from pathlib import Path

from gi.repository import GLib

from penfold.ui.document_view import Fit, ReadingPosition

logger = logging.getLogger(__name__)

REMEMBERED_DOCUMENTS = 200
FILE_NAME = "reading-positions.json"


def positions_file() -> Path:
    """The file with the positions, in the user's data folder (in the Flatpak, the app's own one)."""
    return Path(GLib.get_user_data_dir()) / "penfold" / FILE_NAME


class ReadingPositions:
    """The positions of the documents opened most recently, by their path."""

    def __init__(self, path: Path | None = None) -> None:
        """Keep the positions in path; by default, in positions_file()."""
        self._path = path

    @property
    def path(self) -> Path:
        """The file with the positions."""
        return self._path or positions_file()

    def get(self, document: Path) -> ReadingPosition | None:
        """Where the document was left, if it is remembered."""
        return self._read().get(_key(document))

    def remember(self, document: Path, position: ReadingPosition) -> None:
        """Keep where the document was left, forgetting the oldest documents beyond the limit."""
        positions = self._read()
        key = _key(document)
        positions.pop(key, None)  # The most recent go last.
        positions[key] = position
        self._write(dict(list(positions.items())[-REMEMBERED_DOCUMENTS:]))

    def _read(self) -> dict[str, ReadingPosition]:
        try:
            content = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            logger.warning("Could not read the reading positions in %s", self.path, exc_info=True)
            return {}
        documents = content.get("documents") if isinstance(content, dict) else None
        if not isinstance(documents, dict):
            return {}
        positions = {}
        for key, value in documents.items():
            position = _position(value)
            if position is not None:
                positions[key] = position
        return positions

    def _write(self, positions: dict[str, ReadingPosition]) -> None:
        content = {
            "documents": {
                key: {"page": position.page, "depth": position.depth, "fit": position.fit.value, "zoom": position.zoom}
                for key, position in positions.items()
            }
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Written aside and then put in place, so that a file cut halfway never replaces the good one.
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.path.parent, prefix=".positions-", delete=False
            ) as written:
                json.dump(content, written)
            Path(written.name).replace(self.path)
        except OSError:
            logger.warning("Could not keep the reading positions in %s", self.path, exc_info=True)


def _key(document: Path) -> str:
    return str(document.absolute())


def _position(value: object) -> ReadingPosition | None:
    """The position written in the file, or None if it is not a valid one."""
    if not isinstance(value, dict):
        return None
    page, depth, fit, zoom = (value.get(name) for name in ("page", "depth", "fit", "zoom"))
    if (
        not isinstance(page, int)
        or isinstance(page, bool)
        or page < 0
        or not isinstance(depth, int | float)
        or not isinstance(zoom, int | float)
        or zoom <= 0
        or fit not in {item.value for item in Fit}
    ):
        return None
    return ReadingPosition(page, float(depth), Fit(fit), float(zoom))
