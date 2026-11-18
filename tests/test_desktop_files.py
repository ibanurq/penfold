"""The desktop entry and the AppStream card built by Meson pass their official validators."""

import subprocess
from pathlib import Path

from penfold import config


def validate(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_desktop_entry_is_valid(build_directory: Path) -> None:
    validate(["desktop-file-validate", str(build_directory / "data" / f"{config.APP_ID}.desktop")])


def test_appstream_card_is_valid(build_directory: Path) -> None:
    validate(["appstreamcli", "validate", "--no-net", str(build_directory / "data" / f"{config.APP_ID}.metainfo.xml")])
