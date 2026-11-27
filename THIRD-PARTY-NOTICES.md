# Third-party notices

Penfold is licensed under the GNU General Public License v3.0 (see `LICENSE`). It includes or derives from the
following third-party works, each under its own license, which is compatible with the GPL-3.0.

## GNOME icon-development-kit

- Project: https://gitlab.gnome.org/Teams/Design/icon-development-kit — the icon collection of the GNOME design team.
- License: CC0 1.0 Universal (public domain dedication); no attribution is required, it is given here anyway.
- Used in the interface, unchanged, in `data/icons/scalable/actions/`:
  - `arrows-horizontal` (Fit Width), as `penfold-fit-width-symbolic.svg`;
  - `notebook` (the Annotations view of the side panel), as `penfold-annotations-symbolic.svg`;
  - `filter` (Filter, in the Annotations view), as `penfold-filter-symbolic.svg`;
  - for the annotation types, in the annotation bar and the Annotations view, as `penfold-type-*-symbolic.svg`:
    `pencil` (highlights), `draw-rectangle` (rectangles), `draw-circle` (circles), `top-right-arrow` (arrows),
    `comment` (comments) and `drawing` (other types).
  All by Jakub Steiner. The other icons in that folder (the squiggly underline, freehand and text box types,
  Collapse All and Expand All) and the app icon are Penfold’s own.
- Also: the outline of `comment`, by Jakub Steiner, is the speech bubble drawn on the page for a comment
  annotation, and written into the PDFs saved, in `penfold/document/appearance.py` (`BUBBLE`).

## Liberation Sans

- Project: https://github.com/liberationfonts/liberation-fonts — Copyright Red Hat, Inc.
- License: SIL Open Font License 1.1, which allows embedding the font in documents.
- Not included in Penfold: it comes with the system (Debian's `fonts-liberation`) or with the GNOME runtime of the
  Flatpak. Text boxes are drawn with it, and the characters they use are embedded in the PDFs saved; characters
  it lacks are drawn, and embedded, with other fonts of the system.
