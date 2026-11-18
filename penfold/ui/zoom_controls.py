"""Floating zoom buttons at the bottom right of the document (02-interfaz, 4)."""

from gi.repository import Gtk

from penfold import config
from penfold.ui.document_view import Fit


@Gtk.Template(resource_path=f"{config.RESOURCE_BASE_PATH}/ui/zoom_controls.ui")
class PenfoldZoomControls(Gtk.Box):
    """Fit Width, Whole Page, Zoom In and Zoom Out, as round floating buttons."""

    __gtype_name__ = "PenfoldZoomControls"

    fit_width_button: Gtk.Button = Gtk.Template.Child()
    fit_page_button: Gtk.Button = Gtk.Template.Child()

    def show_fit(self, fit: Fit) -> None:
        """Hide the fitting button that is already active; with a manual zoom both are shown."""
        self.fit_width_button.set_visible(fit is not Fit.WIDTH)
        self.fit_page_button.set_visible(fit is not Fit.PAGE)
