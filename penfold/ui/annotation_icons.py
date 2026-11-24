"""The icon of each annotation type, the same in the annotation bar and in the Annotations view (D75).

They come from Adwaita or, when it has none, from GNOME's icon collection (data/icons, prefixed "penfold-").
"""

from penfold.document.annotations import Kind

SELECT_TEXT_ICON = "font-select-symbolic"
KIND_ICONS = {
    Kind.HIGHLIGHT: "penfold-type-highlight-symbolic",
    Kind.UNDERLINE: "format-text-underline-symbolic",
    Kind.STRIKE_OUT: "format-text-strikethrough-symbolic",
    Kind.COMMENT: "penfold-type-comment-symbolic",
    Kind.TEXT_BOX: "penfold-type-text-box-symbolic",
    Kind.RECTANGLE: "penfold-type-rectangle-symbolic",
    Kind.CIRCLE: "penfold-type-circle-symbolic",
    Kind.ARROW: "penfold-type-arrow-symbolic",
    Kind.OTHER: "penfold-type-other-symbolic",
}
