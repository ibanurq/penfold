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


def test_appstream_card_leads_to_the_same_pages_as_about_and_donate(build_directory: Path) -> None:
    from xml.etree import ElementTree

    from penfold.ui.about import DONATION_URL, ISSUE_URL, WEBSITE

    card = ElementTree.parse(build_directory / "data" / f"{config.APP_ID}.metainfo.xml")
    urls = {url.get("type"): url.text for url in card.iter("url")}
    assert urls == {"homepage": WEBSITE, "bugtracker": ISSUE_URL, "donation": DONATION_URL}  # D81
