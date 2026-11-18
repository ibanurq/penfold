"""The settings schema is valid for GSettings."""

import subprocess
from pathlib import Path

DATA_DIRECTORY = Path(__file__).parent.parent / "data"


def test_schema_compiles_strictly() -> None:
    command = ["glib-compile-schemas", "--strict", "--dry-run", str(DATA_DIRECTORY)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
