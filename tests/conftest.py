"""Shared fixtures: a Meson build of the project, and the application running from it."""

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from gi.repository import Gio

from penfold import config, main

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
def settings_schemas(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Compile the settings schema and keep the settings in memory, so the tests never touch the user's ones."""
    directory = tmp_path_factory.mktemp("schemas")
    subprocess.run(
        ["glib-compile-schemas", "--strict", f"--targetdir={directory}", str(PROJECT_DIRECTORY / "data")], check=True
    )
    previous = {name: os.environ.get(name) for name in ("GSETTINGS_SCHEMA_DIR", "GSETTINGS_BACKEND")}
    os.environ.update(GSETTINGS_SCHEMA_DIR=str(directory), GSETTINGS_BACKEND="memory")
    yield directory
    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


@pytest.fixture(scope="session", autouse=True)
def reading_positions_file(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Keep the documents' reading positions in a folder of the tests', never in the user's data folder."""
    from penfold.ui import reading_positions

    path = tmp_path_factory.mktemp("data") / reading_positions.FILE_NAME
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(reading_positions, "positions_file", lambda: path)
        yield path


@pytest.fixture(scope="session")
def application(build_directory: Path, settings_schemas: Path) -> Iterator["PenfoldApplication"]:  # noqa: ARG001
    """Return Penfold's application, registered but not running, with the interface files of the build."""
    main.load_resources(str(build_directory / "data"))
    # Imported here because the window templates need the resources loaded first (see penfold.main).
    from penfold.application import PenfoldApplication

    penfold_application = PenfoldApplication()
    # Not unique, so that a Penfold already open on the desktop does not receive the tests' windows.
    penfold_application.set_flags(penfold_application.get_flags() | Gio.ApplicationFlags.NON_UNIQUE)
    penfold_application.register(None)
    # The tests' windows show many documents, and the settings are shared: no test window opens the last of them unless
    # the test asks for it.
    Gio.Settings(schema_id=config.APP_ID).set_boolean("open-last-document", False)
    # The app's own icons are installed with it; the tests run it from the source code, so tell GTK where they are.
    from gi.repository import Gdk, Gtk

    display = Gdk.Display.get_default()
    if display is not None:
        Gtk.IconTheme.get_for_display(display).add_search_path(str(PROJECT_DIRECTORY / "data" / "icons"))
    yield penfold_application
    for window in penfold_application.get_windows():
        window.destroy()
