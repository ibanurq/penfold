"""The About Penfold dialog."""

from gettext import gettext as _

from gi.repository import Adw, Gtk

from penfold import config

WEBSITE = "https://github.com/ibanurq/penfold"
ISSUE_URL = f"{WEBSITE}/issues"
COPYRIGHT = "© 2026 ibanurq"

# Libraries Penfold is built on, with their licenses (03-arquitectura, 2.1).
LIBRARY_LICENSES = (
    ("GTK", Gtk.License.LGPL_2_1),
    ("libadwaita", Gtk.License.LGPL_2_1),
    ("PyGObject", Gtk.License.LGPL_2_1),
    ("Poppler", Gtk.License.GPL_2_0),
    ("pikepdf", Gtk.License.MPL_2_0),
    ("qpdf", Gtk.License.APACHE_2_0),
)


def present_about_dialog(parent: Gtk.Window | None) -> None:
    """Show the About Penfold dialog over a window."""
    dialog = Adw.AboutDialog(
        application_icon=config.APP_ID,
        application_name="Penfold",
        version=config.VERSION,
        comments=_("Read, annotate and organize your PDFs"),
        developer_name=_("ibanurq, with AI assistance"),
        website=WEBSITE,
        issue_url=ISSUE_URL,
        copyright=COPYRIGHT,
        license_type=Gtk.License.GPL_3_0_ONLY,
    )
    for library, license_type in LIBRARY_LICENSES:
        dialog.add_legal_section(library, None, license_type, None)
    dialog.present(parent)
