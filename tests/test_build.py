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


def test_every_own_icon_is_bundled_and_used() -> None:
    icons = {path.stem for path in (PROJECT_DIRECTORY / "data" / "icons" / "scalable" / "actions").glob("*.svg")}
    resources = (PROJECT_DIRECTORY / "data" / "penfold.gresource.xml").read_text(encoding="utf-8")
    sources = [*PACKAGE_DIRECTORY.rglob("*.py"), *(PROJECT_DIRECTORY / "data" / "ui").rglob("*.blp")]
    named = {name for path in sources for name in re.findall(r"penfold-[a-z-]+-symbolic", path.read_text("utf-8"))}
    assert not [icon for icon in icons if f"icons/scalable/actions/{icon}.svg" not in resources]
    assert named == icons  # None missing and none left over.
