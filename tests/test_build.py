"""The Meson build installs every module and carries the same version as the code."""

import re
from pathlib import Path

from penfold import config

PROJECT_DIRECTORY = Path(__file__).parent.parent
PACKAGE_DIRECTORY = PROJECT_DIRECTORY / "penfold"


def test_version_matches_meson_build() -> None:
    meson_build = (PROJECT_DIRECTORY / "meson.build").read_text(encoding="utf-8")
    match = re.search(r"^\s*version: '([^']+)'", meson_build, flags=re.MULTILINE)
    assert match, "meson.build has no version"
    assert match.group(1) == config.VERSION


def test_every_module_is_installed() -> None:
    missing = [
        str(module.relative_to(PROJECT_DIRECTORY))
        for module in sorted(PACKAGE_DIRECTORY.rglob("*.py"))
        if f"'{module.name}'" not in (module.parent / "meson.build").read_text(encoding="utf-8")
    ]
    assert not missing, "Add these modules to the meson.build of their folder: " + ", ".join(missing)
