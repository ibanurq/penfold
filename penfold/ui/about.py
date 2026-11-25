"""The About Penfold dialog."""

from gettext import gettext as _

from gi.repository import Adw, Gtk

from penfold import config

WEBSITE = "https://github.com/ibanurq/penfold"
ISSUE_URL = f"{WEBSITE}/issues"
COPYRIGHT = "© 2026 ibanurq"


def library_licenses() -> tuple[tuple[str, Gtk.License, str | None], ...]:
    """The libraries Penfold uses (03-arquitectura, 2.1), and those the Flatpak brings along with them (L5).

    Each with its license, and the name of those GTK has no name for. GTK's "or later" licenses also stand for "or
    later" ones of an earlier version (Pango is LGPL-2.0 or later), and the first of two to choose from (cairo:
    LGPL-2.1 or MPL-1.1).
    """
    return (
        ("GTK", Gtk.License.LGPL_2_1, None),
        ("libadwaita", Gtk.License.LGPL_2_1, None),
        ("PyGObject", Gtk.License.LGPL_2_1, None),
        ("Pango", Gtk.License.LGPL_2_1, None),
        ("cairo · pycairo", Gtk.License.LGPL_2_1, None),
        ("Poppler", Gtk.License.GPL_2_0, None),
        ("poppler-data", Gtk.License.CUSTOM, _("Adobe’s BSD-style license and GPL-2.0 or later.")),
        ("pikepdf", Gtk.License.MPL_2_0, None),
        ("qpdf", Gtk.License.APACHE_2_0, None),
        ("pybind11", Gtk.License.BSD_3, None),
        ("Pillow", Gtk.License.CUSTOM, _("MIT-CMU license (Historical Permission Notice and Disclaimer).")),
        ("Deprecated", Gtk.License.MIT_X11, None),
        ("wrapt", Gtk.License.BSD, None),
        ("Liberation Sans", Gtk.License.CUSTOM, _("SIL Open Font License 1.1.")),
    )


# The icons of GNOME's design team that Penfold uses (D75; THIRD-PARTY-NOTICES.md).
ICON_AUTHORS = ("Jakub Steiner https://gitlab.gnome.org/Teams/Design/icon-development-kit",)


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
    dialog.add_acknowledgement_section(_("Icons"), ICON_AUTHORS)
    for library, license_type, license_text in library_licenses():
        dialog.add_legal_section(library, None, license_type, license_text)
    dialog.present(parent)
