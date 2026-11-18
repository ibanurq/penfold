"""Shared fixtures: a Meson build of the project, and the application running from it."""

import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from gi.repository import Gio

from penfold import main

if TYPE_CHECKING:
    from penfold.application import PenfoldApplication

PROJECT_DIRECTORY = Path(__file__).parent.parent

# Before any test module imports GTK or libadwaita.
main.require_library_versions()


@pytest.fixture(scope="session")
def build_directory(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the project with Meson, as for installing it, and return the build folder."""
    directory = tmp_path_factory.mktemp("build")
    for command in (["meson", "setup", str(directory)], ["meson", "compile", "-C", str(directory)]):
        subprocess.run(command, cwd=PROJECT_DIRECTORY, check=True, capture_output=True)
    return directory


@pytest.fixture(scope="session")
def application(build_directory: Path) -> Iterator["PenfoldApplication"]:
    """Return Penfold's application, registered but not running, with the interface files of the build."""
    main.load_resources(str(build_directory / "data"))
    # Imported here because the window templates need the resources loaded first (see penfold.main).
    from penfold.application import PenfoldApplication

    penfold_application = PenfoldApplication()
    # Not unique, so that a Penfold already open on the desktop does not receive the tests' windows.
    penfold_application.set_flags(penfold_application.get_flags() | Gio.ApplicationFlags.NON_UNIQUE)
    penfold_application.register(None)
    yield penfold_application
    for window in penfold_application.get_windows():
        window.destroy()
