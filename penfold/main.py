"""Entry point: prepares translations and resources, then runs the application."""

import faulthandler
import gettext
import locale
import logging
import sys
from pathlib import Path

import gi
from gi.repository import Gio

from penfold import config

logger = logging.getLogger(__name__)

REQUIRED_LIBRARY_VERSIONS = {
    "Gtk": "4.0",
    "Gdk": "4.0",
    "Gsk": "4.0",
    "Graphene": "1.0",
    "Pango": "1.0",
    "PangoCairo": "1.0",
    "Adw": "1",
    "Poppler": "0.18",
}


def require_library_versions() -> None:
    """Tell PyGObject which versions of the libraries to load; it must happen before they are first imported."""
    for namespace, version in REQUIRED_LIBRARY_VERSIONS.items():
        gi.require_version(namespace, version)
    # Poppler draws on cairo contexts made with pycairo.
    gi.require_foreign("cairo")


def set_up_translations(localedir: str) -> None:
    """Use the system language for the texts of Python code and of the interface files."""
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        logger.warning("The system locale is not available; the interface will be in English")
    # The C library (GtkBuilder) and Python's gettext keep separate catalogs.
    locale.bindtextdomain(config.GETTEXT_DOMAIN, localedir)
    locale.textdomain(config.GETTEXT_DOMAIN)
    gettext.bindtextdomain(config.GETTEXT_DOMAIN, localedir)
    gettext.textdomain(config.GETTEXT_DOMAIN)


def load_resources(pkgdatadir: str) -> None:
    """Register the compiled interface files and icons so that GTK can find them."""
    resource = Gio.Resource.load(str(Path(pkgdatadir) / config.RESOURCE_FILE_NAME))
    Gio.resources_register(resource)


def main(pkgdatadir: str, localedir: str) -> int:
    """Run Penfold and return its exit status."""
    # If Penfold ever crashes in C code (GTK, Poppler, qpdf), write where every thread was, to find the cause.
    faulthandler.enable()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # pikepdf announces at INFO level that it has started; only its warnings are of interest.
    logging.getLogger("pikepdf").setLevel(logging.WARNING)
    require_library_versions()
    set_up_translations(localedir)
    load_resources(pkgdatadir)
    # The window templates are read when their modules are imported, and the library versions must be known before:
    # this import has to come last.
    from penfold.application import PenfoldApplication  # noqa: PLC0415

    return PenfoldApplication().run(sys.argv)
