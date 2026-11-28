"""The icon and the name of each annotation type, the same in the annotation bar and in the Annotations view.

They come from Adwaita or, when it has none, from GNOME's icon collection or drawn for Penfold (data/icons, prefixed
"penfold-"). Stamps also have the name of the stamp each is, as the Annotations view shows it, and Penfold's are
chosen in a menu of their names.
"""

from gettext import gettext as _

from gi.repository import Gio, GLib

from penfold.document.annotations import Kind
from penfold.document.stamps import STAMP_GROUPS

SELECT_TEXT_ICON = "font-select-symbolic"
KIND_ICONS = {
    Kind.HIGHLIGHT: "penfold-type-highlight-symbolic",
    Kind.UNDERLINE: "format-text-underline-symbolic",
    Kind.SQUIGGLY: "penfold-type-squiggly-symbolic",
    Kind.STRIKE_OUT: "format-text-strikethrough-symbolic",
    Kind.COMMENT: "penfold-type-comment-symbolic",
    Kind.TEXT_BOX: "penfold-type-text-box-symbolic",
    Kind.RECTANGLE: "penfold-type-rectangle-symbolic",
    Kind.CIRCLE: "penfold-type-circle-symbolic",
    Kind.ARROW: "penfold-type-arrow-symbolic",
    Kind.FREEHAND: "penfold-type-freehand-symbolic",
    Kind.IMAGE: "image-x-generic-symbolic",
    Kind.STAMP: "penfold-type-stamp-symbolic",
    Kind.OTHER: "penfold-type-other-symbolic",
}


def kind_names() -> dict[Kind, str]:
    """The name of each annotation type, for tooltips and screen readers (translated when called)."""
    return {
        Kind.HIGHLIGHT: _("Highlight"),
        Kind.UNDERLINE: _("Underline"),
        Kind.SQUIGGLY: _("Squiggly Underline"),
        Kind.STRIKE_OUT: _("Strike Through"),
        Kind.COMMENT: _("Comment"),
        Kind.TEXT_BOX: _("Text Box"),
        Kind.RECTANGLE: _("Rectangle"),
        Kind.CIRCLE: _("Circle"),
        Kind.ARROW: _("Arrow"),
        Kind.FREEHAND: _("Freehand"),
        Kind.IMAGE: _("Image"),
        Kind.STAMP: _("Stamp"),
        Kind.OTHER: _("Other Annotation"),
    }


def stamp_name(stamp: str) -> str:
    """The name of a stamp (its /Name) to show: translated for those of the standard and Penfold's, else as it is."""
    names = {
        # Translators: the names of stamps, which say what state a document is in, as the annotation list shows them.
        "Approved": _("Approved"),
        "AsIs": _("As Is"),
        "Confidential": _("Confidential"),
        "Departmental": _("Departmental"),
        "Draft": _("Draft"),
        "Experimental": _("Experimental"),
        "Expired": _("Expired"),
        "Final": _("Final"),
        "ForComment": _("For Comment"),
        "ForPublicRelease": _("For Public Release"),
        "NotApproved": _("Not Approved"),
        "NotForPublicRelease": _("Not For Public Release"),
        "Paid": _("Paid"),
        "Received": _("Received"),
        "Sold": _("Sold"),
        "TopSecret": _("Top Secret"),
    }
    return names.get(stamp, stamp)


def stamp_menu(action_name: str, separators: tuple[str, ...] = ()) -> Gio.Menu:
    """A menu of Penfold's stamps, by their names, a section for each group of colour; each item is a text action.

    The action is given the stamp's name; with a state, the item of the stamp it names is marked. Inside a menu with
    widgets of its own, which GTK measures too short with several sections, the groups are one section instead,
    parted by the custom items named by separators (one fewer than the groups).
    """
    menu = Gio.Menu()
    flat = Gio.Menu() if separators else None
    for index, group in enumerate(STAMP_GROUPS):
        section = flat if flat is not None else Gio.Menu()
        if flat is not None and index:
            custom = Gio.MenuItem()
            custom.set_attribute_value("custom", GLib.Variant.new_string(separators[index - 1]))
            flat.append_item(custom)
        for stamp in group:
            item = Gio.MenuItem.new(stamp_name(stamp.name), None)
            item.set_action_and_target_value(action_name, GLib.Variant.new_string(stamp.name))
            section.append_item(item)
        if flat is None:
            menu.append_section(None, section)
    if flat is not None:
        menu.append_section(None, flat)
    return menu
