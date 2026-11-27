"""The icon and the name of each annotation type, the same in the annotation bar and in the Annotations view.

They come from Adwaita or, when it has none, from GNOME's icon collection (data/icons, prefixed "penfold-").
"""

from gettext import gettext as _

from penfold.document.annotations import Kind

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
        Kind.OTHER: _("Other Annotation"),
    }
