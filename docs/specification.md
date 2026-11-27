# Penfold — specification

This document describes Penfold as it is today: what it does, how it looks and behaves, how it is built and which
design decisions have been taken, in enough detail for someone else to understand the app without reading the code
first. It is not a change history (see `CHANGELOG.md`). **The code is the source of truth**: if anything here
disagrees with the code, the code wins, and this document should be corrected.

How the app is developed with an AI assistant is described in [working-with-ai.md](working-with-ai.md).

## What it is

Penfold is a simple PDF reader for GNOME that can also annotate PDFs and work with their pages. It is a native GTK 4
and libadwaita app, written in Python, distributed as a Flatpak. It can read PDFs and find text in them, annotate them
and edit those annotations, reorganize their pages, edit their bookmarks, merge several PDFs, extract pages, fill in
forms and print.

Two principles guide what it does:

- **Faithful to the PDF.** Everything the PDF standard (ISO 32000) defines as visible is shown correctly: annotations
  of any type and from any program, page labels, links, forms, layers in their default state. Saving changes the PDF
  that was opened instead of rebuilding it, so whatever Penfold does not edit is kept intact.
- **Annotations look the same everywhere.** Annotations made or changed in Penfold are saved with **their own
  appearance stream (`/AP`)** and every entry the standard asks for, so other viewers show them exactly as Penfold
  does. Text written into the PDF is UTF-16, so emoji and any other character are kept.

Penfold never uses the network. It does not create new annotation types beyond the ten listed below, insert images,
set passwords or permissions on a PDF, or recognize text in scanned pages.

## Name, version and license

- **Name: Penfold.** *Pen* + *fold* (a folded sheet of pages): the two halves of the app, annotating and organizing
  pages.
- **App ID:** `io.github.ibanurq.Penfold`. **Repository:** `https://github.com/ibanurq/penfold`.
- **Version:** in `meson.build` and `penfold/config.py` (a test checks that they match), following semantic
  versioning, with `-alpha.N`, `-beta.N` and `-rc.N` for pre-releases.
- **License: GPL-3.0-only.** Compatible with every library used (see “Platform and libraries”). Third-party works
  included in the app are listed in `THIRD-PARTY-NOTICES.md`.

## Platform and libraries

The minimum versions are those of **Debian 13**, so the app can run from the source code there; the Flatpak uses
newer ones. Anything only found in newer versions is used with a check and a fallback (for example the keyboard
shortcuts window, `AdwShortcutsDialog`, needs libadwaita 1.8; with 1.7, `GtkShortcutsWindow` is used).

| Component | Minimum | Debian 13 package | Use |
|---|---|---|---|
| Python | 3.13 | `python3` | The language |
| PyGObject | 3.50 | `python3-gi` | GTK, libadwaita and Poppler from Python |
| GTK | 4.18 | `gir1.2-gtk-4.0` | The interface |
| libadwaita | 1.7 | `gir1.2-adw-1` | GNOME’s widgets and style |
| Poppler (glib) | 25.03 | `gir1.2-poppler-0.18` | Reading and drawing pages, text, links, page labels |
| pikepdf (on qpdf 12) | 9.5 | `python3-pikepdf` | Reading the PDF’s objects and writing PDFs |
| PyCairo | 1.27 | `python3-cairo`, `python3-gi-cairo` | Drawing annotations |
| Meson | 1.7 | `meson` | Building and installing |
| Blueprint | 0.16 | `blueprint-compiler` | Describing the interface |

**Flatpak:** runtime `org.gnome.Platform` 51. The runtime does not include Poppler, qpdf or pikepdf, so the manifest
(`build-aux/flatpak/io.github.ibanurq.Penfold.json`) builds them from source: poppler-data, Poppler (only its glib
part), qpdf and pikepdf with its Python dependencies. Permissions: no network; access to the home folder
(`--filesystem=home`), because otherwise a PDF opened with “Open With” could only be reopened until the next restart,
and the last document and reading positions could not be remembered. Files outside the home folder arrive through
GNOME’s portals (file chooser, “Open With”, drag and drop).

## Code organization

```
penfold/
├── main.py, application.py   Start-up, the single application instance, its windows and global actions.
├── config.py, errors.py      Version and app ID (filled in by Meson); the errors explained to the user.
├── document/                 The PDF and its changes. No GTK, no Poppler: pikepdf only.
│   ├── document.py           OpenDocument: an open PDF and everything that can be edited in it, with its history.
│   ├── sources.py            The source PDFs whose pages make up the document (the opened one and those added).
│   ├── pages.py, page_labels.py, page_frame.py, geometry.py
│   ├── annotations.py, appearance.py, reshaping.py
│   ├── bookmarks.py, forms.py, form_filling.py, access_permissions.py, properties.py, pdf_values.py
│   ├── history.py, commands/ Undo and redo, and one command class per kind of change.
│   └── saving.py, extracting.py
├── rendering/                Drawing with Poppler and cairo: pages in worker threads, annotations, text boxes, search.
└── ui/                       The interface: window, headers, document view, side panel, dialogs. GTK 4 + libadwaita.
data/
├── ui/                       The interface in Blueprint (.blp), one file per piece of ui/.
├── icons/                    The app icon and the symbolic icons Adwaita does not have.
├── style.css                 The few styles libadwaita does not give.
└── *.desktop.in, *.metainfo.xml.in, *.gschema.xml, penfold.gresource.xml
po/                           Translations (gettext).
tests/                        The tests, and a real form PDF they use (fixtures/form.pdf).
build-aux/                    The Flatpak manifest and scripts to set up the tools and run from source.
```

- **Layers.** `ui` uses `rendering` and `document`; `rendering` uses `document`; **`document` uses neither** (a test,
  `tests/test_architecture.py`, checks it). So the logic of the PDF, where data can be lost, is tested without
  windows, and could be reused elsewhere.
- **Interface in Blueprint.** Windows and dialogs are described in `.blp` files, compiled to GtkBuilder when building,
  and bound to Python classes with `@Gtk.Template`.
- **Actions.** Every command (open, save, undo, turn pages, delete…) is a `Gio.SimpleAction` (`app.open`, `win.undo`),
  with its shortcut and its enabled state. Buttons, menu items and shortcuts use the same action, so they cannot
  behave differently, and graying out a control means disabling its action.
- **Source index and position.** Each page of each source PDF has a **source index** that never changes: the pages of
  the opened PDF are 0 to n−1, those of each PDF added come after them. Bookmarks, annotations, links, selected
  thumbnails and search results name their page by its source index; the interface works with **positions** in the
  document. `OpenDocument.page_position` and `rendering/layout.py` translate between them.
- **Changes.** The interface never changes the document directly: every change is a command run through the history,
  and the document tells the interface what changed (`Change.PAGES`, `ANNOTATIONS`, `BOOKMARKS`, `FORM`, `FILE`,
  `PERMISSIONS`).
- **Registration.** Each new `.py` goes into the `meson.build` of its folder; each `.blp` into `data/meson.build` and
  `data/penfold.gresource.xml`; each file with translatable text into `po/POTFILES.in`. The tests check all three.

## Interface

The interface follows the GNOME Human Interface Guidelines and uses libadwaita’s widgets as they are: sizes, colors
and type come from libadwaita, not from Penfold. Principles:

- **A clean window.** While reading, only the document and its headers are visible. Tools appear when asked for (the
  pencil, the right-click menus).
- **What cannot be used is grayed out**, never hidden or silent: every button, menu item or control that cannot act
  at that moment is shown disabled.
- **Undo rather than ask.** What can be undone is not confirmed: a toast says what was done, with “Undo”. A toast for
  an edit disappears as soon as that edit is undone, with its button or with Ctrl+Z. Only actions that cannot be
  undone ask: discarding unsaved changes and overwriting files when extracting.
- **The three list views of the side panel work alike**: a header with a title and its buttons, a list, and the
  actions on the selection in a right-click menu.
- **Menu texts are always aligned**, whether or not some row has a check mark.

### The window

- Two areas, in an `AdwOverlaySplitView`: the **side panel** on the left, with its own header, and the **document** on
  the right, with its header. In narrow windows the panel overlays the document.
- The side panel is shown or hidden with its button or F9, and opens by itself when a PDF is loaded. Its width is set
  by dragging its edge (the edge line grows from 1 to 3 pixels in the accent color on hover and while dragging) and
  remembered.
- **Size.** Without a document the window is small. When a PDF is opened it grows to the size it had the last time it
  showed a document, or is maximized if it was. The size and the maximized state are remembered (GSettings), not the
  position: on GNOME, apps do not choose where their windows go.
- **Window title** (Alt+Tab, Activities): “file.pdf — Penfold”, with “• ” in front while there are unsaved changes;
  “Penfold” without a document.

### Welcome page

An `AdwStatusPage` with a gray drawing of a sheet with a marker pen, the title “Welcome to Penfold”, the line “Drag a
PDF here to open it, or several to merge them”, and two rounded blue buttons, **Open…** and **Merge…**. The header
holds only “Penfold”, the main menu and the window buttons. There is no list of recent documents.

Dropping one PDF on a window opens it; dropping two or more opens Merge with them in the list. The same goes for “Open
With → Penfold” in the file manager, and also with a document already open.

### Headers

**Side panel header:** Find (magnifier) on the left, “Penfold” in the center, the main menu ☰ on the right.

**Document header**, from left to right:

- show or hide the side panel (F9); the pencil, which shows or hides the annotation bar (grayed out when the PDF does
  not allow annotating); Undo and Redo (grayed out when there is nothing to undo or redo);
- in the center, the document’s title and, under it, the file name; with only the file name when the PDF has no
  title. A “• ” in front of the title marks unsaved changes. For a PDF with user access permissions, a red closed
  padlock goes in front (see “Passwords and user access permissions”);
- the page box and, next to it, “of N” or “(n of N)”; the document menu ⋮; the window buttons.

There is no Save button: saving is Ctrl+S or the document menu.

**Page box.** For a PDF without page labels it shows the page number and “of 113” next to it. For a PDF with page
labels it shows the label (“ix”) and the real position next to it, “(11 of 800)”. Either the label or the number can
be typed; Enter goes to that page; Ctrl+L puts the focus in the box.

### Menus

**Document menu ⋮:** Print… (Ctrl+P) · Save (Ctrl+S), Save As… (Shift+Ctrl+S) · Continuous / Two Pages (a radio
choice) · Properties. Save, Save As… and Print are grayed out when they cannot be used, for example Print for a PDF
that does not allow printing.

**Main menu ☰:** three circles to choose the style (follow the system, light or dark) · Open… (Ctrl+O), Merge PDFs…,
New Window · Preferences (Ctrl+,), Keyboard Shortcuts (Ctrl+?), Donate (opens the Ko-fi page), About Penfold.

### Document and zoom

- Continuous scrolling by default; Two Pages shows pairs (1-2, 3-4…).
- **Floating zoom buttons** (round OSD buttons) at the bottom right, in a column: Fit Width and Whole Page (only the one
  that is not active is shown; with a manual zoom, both), Zoom In and Zoom Out.
- On opening a PDF, and whenever the width of the viewer changes, the zoom fits the width (in Two Pages, the whole
  page).
- **Going to a destination** (a bookmark, an annotation, a link, a search result) puts its height in the **top third**
  of the viewer, never above the start of the page; without a height, it goes to the start of the page.
- Internal links go to their destination; external links open in the browser.
- Text can be selected with the mouse, across pages, and copied.
- **Reading position.** With “Remember Document Position” on (see “Preferences”), each document opens at the page,
  height and zoom where it was left.

### Annotation bar

The pencil shows a bar **floating at the bottom center of the document**, to the left of the zoom buttons, without
pushing the document. In a narrow window it moves aside so as not to touch them; if both still do not fit, the zoom
buttons rise just above the bar. It looks like GNOME’s side panel: light gray (dark gray in dark style), with a thin
border and a soft shadow, so it stands out from white paper. While it is shown, toasts appear just above it.

```
[Select Text] | [Highlight] [Underline] [Squiggly Underline] [Strike Through] | [Rectangle] [Circle] [Arrow] | [Comment] [Text Box] | [Color]
```

- The separators mark the four groups of annotations (see “Annotation groups”).
- One tool at a time; Select Text is the default; the initial color is yellow. **The tool stays active** after an
  annotation is made, and the cursor shows which one it is. Each annotation made can be undone and redone.
- **Color:** a button with the current color opens upwards a row of six color circles, with a ring around the one
  chosen; choosing a color closes it. Every palette in the app looks like this.
- **H and U:** with text selected, they highlight or underline it without changing the tool; with nothing selected,
  they choose the Highlight or Underline tool.
- **Drawing and selecting are separate.** A left click never selects an annotation, so selecting highlighted text is
  easy; annotations are edited with the right click (see “Editing annotations”). Form fields only respond with Select
  Text.
- **Esc** does only the first of these that applies: close an open menu or palette → cancel the text being written →
  close the Find view → clear the selection of Pages or Bookmarks → go back to the Select Text tool.

### Side panel

A **view switcher** at the bottom of the panel with three icons: Pages, Bookmarks and Annotations. The magnifier in
the header opens a fourth view, Find.

What the three list views share:

- **Header:** the view’s title in bold on the left and its buttons on the right.
- **Selection:** click, Ctrl+click (several) and Shift+click (a range). Clicking an empty part of the list or pressing
  Esc clears the whole selection; Ctrl+click on a selected item unselects only that one. Clicking the document does not
  clear it.
- **Right-click menu:** on a selected item, it acts on the whole selection; on an unselected one, it selects only that
  one first. It opens without an arrow, to the right of the pointer; also with the Menu key or Shift+F10 on the
  selection (whatever has the focus, as long as the panel is shown), and with a long press on touch screens. What cannot
  be applied is grayed out; when the PDF does not allow the change, everything is. Delete (also the Delete key) does
  not ask: a toast offers “Undo”.
- **Counter** (Pages and Bookmarks): while something is selected, “N selected” floats at the bottom with the look of a
  toast. The lists always leave room for it after the last row, so nothing moves when selecting.

**Pages**

- Header: “Pages” · **Add** · **Extract**.
- Thumbnails of a fixed size, in as many columns as fit, centered; each page fitted into the same cell without
  distortion, with its page label underneath. Ctrl + wheel (or Ctrl++ and Ctrl+− with the focus on them) changes their
  size, which is remembered. Each thumbnail shows the page with its annotations, and is updated when an annotation is
  made, changed, moved or deleted, and on undo and redo.
- The thumbnail of the page being read is marked, and a soft frame shows the part visible in the document.
- **Drag to reorder:** pages can be dropped anywhere in the list and go next to the nearest thumbnail (before it on its
  left half, after it on its right half); a blue line shows where, and the list scrolls by itself near its edges.
- Right-click menu: Rotate Left, Rotate Right, Rotate 180°, Extract… · Delete. Not every page can be deleted: with all
  of them selected, Delete is grayed out.

**Bookmarks**

- Header: “Bookmarks” · **Add** (takes the selected text as title, or “Page N”) · **Collapse All** · **Expand All**
  (each grayed out when there is nothing to do).
- A tree with an arrow to expand each branch, the page number on the right, and bold, italic and color visible. The
  bookmark of the section being read is marked with a vertical bar in the accent color on the left of its row (not a
  background, so it is not mistaken for the selection), and kept in view.
- **Drag** before, after or inside another bookmark (top 30 % of a row: before; bottom 30 %: after; the middle:
  inside; below the list: at the end); a blue line or the row in blue shows where.
- Right-click menu: four color circles · Bold ✓, Italic ✓, Clear Formatting · Rename… (F2) · Point to the Current
  Page · Increase Indent, Decrease Indent · Delete. Rename and Point are grayed out with several selected; the indent
  items when they cannot apply.
- **Bookmark colors.** A color tints the title, so bookmarks have their own palette, readable on white: burgundy
  `#ad182e`, orange `#d54400`, green `#2c873e` and blue `#2676d5` (libadwaita’s accent colors darkened just enough to
  reach a contrast of 4.5:1 on white). That is what is saved in the PDF. In the panel, **any** bookmark color, also
  those from other programs, is darkened in light style or lightened in dark style just enough to reach 4.5:1 on the
  panel’s background, without changing the file.

**Annotations**

- Header: “Annotations” · **Filter**: a popover with one check box per group, which stays open while ticking (Esc or a
  click outside close it). All four are ticked by default.
- The list has the four sections of the groups, each with a count (“Text Elements (2)”), sorted by page and position.
  Every annotation type the PDF has falls into one of them.
- **Each row:** a small icon of the type on the left; “Page N” in bold and the author on the right in gray (or
  “(External)” without one); under it, up to about four lines of its text, with a vertical bar in the annotation’s
  color. White or colorless annotations from other programs use orange `#c64600` for the bar, so it can be seen.
  Text markups without text of their own show the marked text in quotation marks; shapes without text, “No text”.
- The annotations of the page being read are marked, and the list scrolls to the first one.
- Click goes to the annotation. Right click opens the same menu as on the page (see “Editing annotations”); it acts
  on one annotation, so there is no counter. Delete removes the selected ones, with “Undo”.

**Find**

- A search box at the top; under it, “N results” and the list: “Page N” and the sentence with the match highlighted.
  The list fills up as the search goes on, without blocking anything, also in large PDFs.
- It ignores case, accents and irregular line breaks. It does not search the text of annotations.
- A click on a result goes to it (in the top third). Enter / Shift+Enter and Ctrl+G / Shift+Ctrl+G go to the next and
  previous result. Esc goes back to the previous view and, if the panel was hidden and Find (Ctrl+F) showed it, hides
  it again; if another view is chosen meanwhile, or the panel is hidden and shown by hand, it stays.

### Dialogs and notices

| Situation | Component |
|---|---|
| Short questions (unsaved changes, overwriting) | `AdwAlertDialog`; the destructive answer in red |
| Asking for a text (a new bookmark’s title, renaming a bookmark) | `AdwAlertDialog` with a text box |
| Short messages and “Undo” | `AdwToast` at the bottom |
| Open, Save As, choosing a folder, choosing a PDF to add | The system’s file chooser (`GtkFileDialog`) |
| Merge PDFs, Extract Pages, Add Pages, Print | `AdwDialog` with Cancel at the top left and the main button at the top right |
| Preferences, Properties | `AdwPreferencesDialog`, one page, 460 pixels wide |
| Keyboard Shortcuts | The standard shortcuts window |
| About | `AdwAboutDialog` |

Enter confirms and Esc cancels.

### Icons

Adwaita’s symbolic icons; where there is no suitable one, an icon from the GNOME design team’s icon-development-kit,
included in the app; where neither has one, an icon drawn for Penfold (the squiggly underline, freehand and text box
types, Collapse All and Expand All). See `THIRD-PARTY-NOTICES.md`. Each annotation type has the same icon in the
annotation bar and in the panel. Right-click menus have text, no icons.

### Light and dark style

By default the app follows the system, like every libadwaita app. The three circles at the top of the main menu choose
System, Light or Dark; the choice is saved and applied at once to every window. PDF pages are never inverted.

## Behavior

### Opening

- A PDF opens from Open… (Ctrl+O), the welcome page, the file manager (“Open With”), the command line, or by dropping it
  on a window. Several at once open Merge with them in the list.
- **One instance, several windows.** A PDF from the desktop opens in an empty window if there is one, otherwise in a
  new window. “New Window” opens an empty one.
- **Private copy.** While a document is open, Penfold reads it from a private copy of the PDF as it was opened, in a
  temporary folder. Saving always starts from that copy, so after saving one can still undo, and another program
  changing the file meanwhile does not break the document.
- A PDF that needs a password to open asks for it (see “Passwords and user access permissions”).
- **Last document.** With “Start With Last Document” on, Penfold started without files opens the last document shown,
  at its position if it is remembered. If there is none, or it no longer exists or cannot be opened, the welcome page
  is shown, without a notice.
- **Annotation bar at start.** With “Show Annotation Bar at Start” on, each document opens with the bar shown and
  Select Text chosen, unless the PDF does not allow annotating.

### Rendering

- **Poppler draws the pages:** their content, links and the annotations Penfold does not manage. So everything in the
  PDF looks as the standard defines.
- **Penfold paints the annotations it manages** (those made or changed in Penfold) with cairo, over the page, exactly
  as they will be saved. An annotation of the PDF that is changed is hidden in Poppler’s copy, so it is not drawn
  twice. An annotation from another program that is only moved keeps the drawing its program made: Penfold records it
  once and paints it moved.
- Form fields are not drawn by Poppler: GTK widgets over each field show and edit them (see “Forms”).
- Pages are drawn **in worker threads**, only the visible ones and those nearby, and kept in a texture cache with a
  memory limit, so the interface never blocks, not even with a PDF of hundreds of pages. Each thread has its own
  Poppler document, and Poppler draws one page at a time (a lock), because drawing in parallel corrupted its memory.
  Thumbnails and search work the same way, in the background.

### Annotation types and how they are saved

Penfold makes ten types. Each is saved with its own `/AP` (a Form XObject in `/AP /N`), the entries the standard asks
for (`/NM`, dates, `/F` with the print flag, color, border style…) and the author of Preferences as `/T` (`Penfold` if
it is empty). Text in `/Contents` is UTF-16.

| Type | Subtype | Made by | Default look |
|---|---|---|---|
| Highlight | `/Highlight` | Selecting text | The color with `Multiply` blending, opacity 0.75 |
| Underline | `/Underline` | Selecting text | A 1 pt line under the text |
| Squiggly underline | `/Squiggly` | Selecting text | A 1 pt zigzag under the text, with round corners, as tall as a sixth of the line (at least 1.5 pt); each stroke goes up or down as much as along |
| Strikethrough | `/StrikeOut` | Selecting text | A 1 pt line through the middle of the text |
| Rectangle | `/Square` | Dragging | A 1 pt line, hollow |
| Circle | `/Circle` | Dragging (four Bézier curves) | A 1 pt line, hollow |
| Arrow | `/Line` | Dragging from its start to its end | A 1 pt line with an open arrowhead at the end (`/LE`) |
| Freehand | `/Ink` | Dragging; each stroke is one annotation | A 2 pt line through the points of the stroke (`/InkList`), drawn as a smooth curve (Catmull-Rom, as Bézier curves), with round ends and corners |
| Comment | `/Text` | Clicking, then writing its text | GNOME’s comment bubble, filled with the color |
| Text box | `/FreeText` | Dragging to set its width, then writing on the page | A faint background (14 %) and a 1 pt border in the color; black Liberation Sans 11 pt |

*(In progress: the annotation bar does not have the Freehand tool yet, so freehand drawings, also those of other
programs with several strokes, can be edited but not made.)*

- **Text markups** turn the selection into one quadrilateral per line (`/QuadPoints`).
- **Shapes** are drawn while dragging, so their shape is seen before releasing.
- **Comment:** a popover pointing at the place, with a multi-line box and Cancel · Apply (Enter: new line; Ctrl+Enter:
  Apply; Esc: Cancel; empty: nothing is made). On hover, its text in a tooltip (at most ten lines and about 500
  characters; longer, with “…” at the end). No `/Popup` is written.
- **Text box:** written **directly in the box, on the page**, which grows downwards as the text needs; Ctrl+Enter or a
  click outside accept, Esc cancels; empty, nothing is made. The text is laid out with Pango and saved as a drawing with
  the glyphs embedded (Liberation Sans, under the SIL Open Font License, allows it); characters it lacks are drawn, and
  embedded, with other fonts of the system. `/Contents` keeps the plain text.
- **Annotation groups.** Annotations are grouped the same way everywhere (the bar, the panel’s filter and sections,
  printing):
  - **Text Highlights:** highlights, underlines (also squiggly), strikethroughs;
  - **Shapes:** rectangles, circles, arrows and lines, polygons, polylines, freehand drawings;
  - **Text Elements:** comments, text boxes, stamps, insert-text marks;
  - **Other Types:** everything else that is listed (attachments, sounds, redactions, watermarks…). Links, form fields
    and pop-ups are not listed.

### Editing annotations

A **right click on an annotation** (on the page or on its row in the Annotations view; a long press on touch screens)
opens a menu, also while an annotation tool is active (it stays active). The annotation is outlined while the menu is
open; when several are under the pointer, a line wins over the empty inside of a shape, and otherwise the topmost wins.
A right click elsewhere does nothing. When the PDF does not allow annotating, everything in the menu is grayed out.

```
( ● ) ( ● ) ( ● ) ( ● ) ( ● ) ( ● )     the six colors; one click changes and closes
Edit Text…                              comments and text boxes
Format…                                 every type but comments
Move and Resize                         “Move” for comments; “Adjust Ends” for text markups
Delete
```

- **Edit Text…:** a comment in its popover; a text box by writing on the page, as when it was made.
- **Format…:** a popover beside the annotation, without covering it: the six colors and rows for its type. Changes
  apply at once, without an Apply button; Esc or a click outside close it; everything changed is one undo step.

  | Type | Rows |
  |---|---|
  | Highlight, underline, squiggly underline, strikethrough | Opacity |
  | Rectangle, circle | Line Width (Thin 1 pt · Medium 2 pt · Thick 4 pt) · Line (Solid · Dashed) · Fill (a soft tint of the color) · Opacity (10–100 %) |
  | Arrow | Line Width · Line · Arrowheads (At the End · At Both Ends · None) · Opacity |
  | Freehand | Line Width · Opacity |
  | Text box | Letter Size (Small 9 · Normal 11 · Large 14 · Very Large 18 pt) · Background · Border; the color is the background’s and the border’s, the text is always black |

- **Move and Resize:** handles on the annotation: corners for rectangles and circles, and for freehand drawings, whose
  strokes stretch or shrink to fill the new frame without being mirrored, while their line keeps its width; for a text box, one on each side,
  which change only its width (the height follows the text, live); the ends of an arrow; for text markups, drop-shaped
  handles at the start and the end, which follow the text letter by letter within the page (grayed out where there is
  no text under them). Dragging inside moves it. Enter or a click outside accept, Esc cancels; one undo step.
- **Delete:** no question; a toast “Annotation deleted” with “Undo”.
- **Annotations from other programs** of the ten types are edited like Penfold’s (a freehand drawing without strokes,
  `/InkList`, counts as another type). What is not touched does not
  change: a color outside the palette has no circle marked; a value outside the options appears as one more option.
  They are moved **keeping their own drawing**; resizing them draws them again, so it is only offered when Penfold can
  draw them the same way (otherwise the menu says “Move”). If Penfold cannot redraw something of theirs, it warns
  before changing it. Annotations of other types can be seen and listed, but not edited.

### Bookmarks

- Bookmarks are read as a tree with their title, destination, color, bold, italic and open state.
- **Destinations are kept as they were.** An untouched bookmark is written back with its original destination
  (`/XYZ`, `/FitH`, `/Fit`…). A new bookmark, or one pointed at the current page, leads to the start of its page.
- A new bookmark takes the selected text as title (or asks for one, “Page N” by default) and is placed in page order.
- Expanding or collapsing a branch is not a change to save.

### Pages: adding, extracting and merging

- **Add Pages** (Pages view): from a PDF or a blank page (portrait **A4**, **Letter**, **A5** or **A3**); at the start,
  at the end or after a given page. With pages selected it proposes “After page X”, the last selected; without, “At the
  End”. For a PDF with page labels the row shows the label and the position of the chosen page, “Page 2 (4 of 12)”.
  The pages of a PDF arrive with a new expanded bookmark named after the file, holding that file’s bookmarks.
- **Extract Pages:** by ranges (`1, 4, 7-10, 15, 22-`), explained under the field with that example; the selected
  pages are written in it. Options: extract as separate pages, and delete the pages afterwards (one undo step). For a
  PDF with page labels, a line warns that the numbers are positions, not labels. A folder is chosen; the files are
  called `extracted.pdf`, or `extracted_01.pdf`, `extracted_02.pdf`…; if a name is taken, Penfold asks whether to
  overwrite, rename (`extracted (2).pdf`) or cancel.
- **Merge PDFs:** a list where PDFs are added with a button or dropped from the file manager, reordered by dragging and
  removed. Options: create a bookmark for each file, and keep the files’ bookmarks. At least two files that can be
  merged are needed. Form fields brought from another PDF with a name already used are renamed (`name` → `name_2`). A
  merged document is new: it has no file until it is saved.

### Forms (AcroForm)

- **Filled in on the page:** text fields (single or multiple lines, with their maximum length, alignment and font
  size), check boxes, radio buttons, dropdowns (editable or not) and lists. Each is a GTK widget over its place on the
  page. Push buttons and signatures are not filled in. No JavaScript calculations or validation.
- The values live in the document, only those that differ from the PDF; a field set back to its value in the PDF counts
  as untouched again. Filling in a field is a change that can be undone.
- **Saved editable:** the values are written into the form, and only the touched fields are drawn again (by qpdf).
- **Flatten:** only in Save As…, and only when the document has fillable fields: a dialog with a switch “Flatten the
  Form” (off by default) before choosing the file. Each field’s appearance becomes fixed page content and the form is
  removed. A flattened copy is an **export**: the document keeps its file and its unsaved changes.

### Saving

- **Save** (Ctrl+S) writes over the file; a new (merged) document asks where, as Save As…. **Save As…** writes a new
  file, which becomes the document’s file.
- **The PDF is changed, not rebuilt.** pikepdf takes the private copy and applies the changes: pages in their new order
  and rotation, pages added from other PDFs, pages deleted (with their form fields), annotations made, changed, moved
  or deleted, bookmarks (`/Outlines`, with their color and bold and italic flags), page labels and form values.
  Everything else stays as it was. Unused objects are dropped and streams compressed, as qpdf does.
- **Page labels:** `/PageLabels` is written again for the final order: each page keeps its label, pages without one
  (blank, or from a PDF without labels) get their number, and runs are grouped so the tree stays compact.
- **Safe writing:** in a worker thread, to a temporary file next to the target; the result is opened again to check
  it, and only then put in the target’s place. If anything fails, the file that was there is untouched.
- An encrypted PDF is saved with its encryption, passwords and permissions.

### Unsaved changes and undo

- **Everything can be undone.** Every change to the document (annotations, pages, bookmarks, form values) is a command
  with `apply()` and `revert()`, kept in the history: Undo and Redo in the header, Ctrl+Z and Shift+Ctrl+Z. An action
  that does several things (extracting and deleting) is one command. Commands keep only what they need to revert, never
  copies of the PDF. The history is emptied when another document is opened.
- **Unsaved changes:** the history remembers the point where the document was saved; undoing back to it leaves nothing
  to save. A merged document is unsaved until it is saved.
- **Before the document is replaced** (opening another one, merging) **or the window is closed** (also when quitting),
  Penfold asks, first, “Save changes to “name”?” with Cancel, Discard (destructive) and Save. Save saves (or asks where)
  and then goes ahead; if saving fails or is canceled, nothing is replaced. Without unsaved changes nothing is asked.
- Quitting (Ctrl+Q) asks in every window with changes, in turn; Cancel in any of them stops quitting.

### Printing

Print… (Ctrl+P) first shows a dialog with four switches, one per annotation group, all on; Continue opens the
system’s print dialog. If the document has no annotations (counting those not yet saved), it goes straight to the
system’s dialog. The PDF printed is prepared as saving does (with the form values and the annotations chosen, without
the others), and drawn by Poppler.

### Passwords and user access permissions

The standard calls what an encrypted PDF allows its **user access permissions**: printing, filling in forms,
annotating, assembling (changing pages), copying text, modifying.

- **A PDF with permissions** (encrypted without an open password) opens without a notice. With “Respect Document
  Permissions” on (the default), whatever it allows can be used and the rest is grayed out. A **red closed padlock** in
  front of the title shows it; its tooltip says “User access permissions of this PDF:”, what is not allowed, and that
  they can be ignored from Preferences. With the option off, there is no padlock and everything is allowed.
- **A PDF with an open password:** an alert “Protected Document” asks for it (“Opening “file.pdf” requires its
  password.”), with a password box that can show the text, and Cancel · Open (grayed out while the box is empty). A
  wrong password says “Incorrect password” in red and empties the box. The password is never remembered: it lives only
  in memory, never in a log. Opened with the owner password, everything is allowed.
- **Saving and extracting** keep the encryption, the passwords and the permissions.
- **Merging and adding pages:** the pages of a PDF with a password can be used once it is typed. With permissions
  respected, a PDF that does not allow assembling cannot be merged or added; with them ignored, it can. The result
  carries no password or permissions.

### Properties

Document menu → Properties: an `AdwPreferencesDialog` **only for reading**. Each row has the name small on top and the
value under it, selectable to copy it. Groups: **Document** (title, author, subject, keywords) · **File** (name, full
folder, size in the format of the language) · **Content** (pages; page size as shown, with its paper when known, “A4,
210 × 297 mm”, or “Various”; PDF version) · **History** (created and modified, in local time; creator program;
producer) · **Security** (Password: Yes or No, the open password; Permissions: “Unrestricted” or one line per thing
not allowed). Empty rows and empty groups are not shown. The data of the PDF are those of the file as it was opened;
pages and sizes, those of the document as it is now. A merged document without saving has no File, Document data or
version.

### Preferences

Main menu → Preferences (Ctrl+,): an `AdwPreferencesDialog`, one page, no OK or Cancel (changes apply at once).

- **Annotations:** **Author**: the row is the entry itself, its title always small on top; empty, it shows “Penfold”
  as a hint, the name used when it is empty. **Show Annotation Bar at Start** (off by default).
- **Documents:** **Respect Document Permissions** (on). **Remember Document Position** (on): the page, height and zoom
  of each document are kept on the computer (`reading-positions.json` in the user’s data folder, never in the PDF), for
  the 200 most recently opened, written when the document is closed or replaced; a new unsaved document is not
  remembered. **Start With Last Document** (on).

Settings are kept with **GSettings** (`data/io.github.ibanurq.Penfold.gschema.xml`): window size and maximized state,
side panel width, thumbnail size, style, author name and the switches above.

### Keyboard shortcuts

The Keyboard Shortcuts window (Ctrl+?) lists them in groups:

- **Annotations:** H highlight, U underline, Esc back to the text selection tool.
- **General:** Ctrl+O open, Ctrl+S save, Shift+Ctrl+S save as, Ctrl+P print, Ctrl+Z undo, Shift+Ctrl+Z redo, Ctrl+,
  preferences, Ctrl+? this window, Ctrl+W close the window, Ctrl+Q quit.
- **Find:** Ctrl+F find, Ctrl+G / Shift+Ctrl+G next / previous result, Esc close the search.
- **View:** F9 side panel, Ctrl++ (or Ctrl+=) zoom in, Ctrl+− zoom out, Ctrl+0 fit to width; with the focus on the
  thumbnails, Ctrl++ and Ctrl+− change their size.
- **Moving around:** Page Down / Page Up next / previous page, Ctrl+Home / Ctrl+End first / last page, Ctrl+L go to
  page.
- **Side panel:** Delete deletes the selected pages, bookmarks or annotations; F2 renames the selected bookmark; Menu or
  Shift+F10 opens the menu of the selection; Esc clears the selection.

The keys without Ctrl (H, U, Delete, Esc, Page Down / Page Up) do nothing while typing in a field.

### About

`AdwAboutDialog` with the app’s icon, name and version, the website and issue tracker, the developer, the license,
the credits for the icons, and the libraries and font used with their licenses.

## Languages

- **gettext**, as in GNOME: strings in the code are wrapped in `_()`, with `ngettext` for plurals and `pgettext` for
  contexts (the same English word translated differently). Blueprint files mark them with `_()` too.
- **The base language is American English**, as in GNOME. Code, comments and documentation are in English.
- Translations live in `po/` (`es.po`, Spanish). The language follows the system’s.
- **Adding a language:** add its code to `po/LINGUAS` and its `.po` file, made from the template that Meson generates
  (`po/penfold.pot`). A test checks that every string is translated into Spanish.
- Identifiers written into PDFs are not translated, such as the default author `Penfold`. A new bookmark’s default
  title (“Page 3”) is translated when it is made and stays in the PDF in that language.

## Quality, tests and building

- **Style:** PEP 8, formatted with **Ruff** (`ruff format`) and checked with Ruff (`ruff check`) with a wide set of
  rules; lines of 120 characters; no warnings allowed (a rule that makes no sense somewhere is disabled on that line,
  with the reason). **Types:** annotations everywhere, checked with **mypy**, in strict mode for `document/`.
- **Names and functions:** English, complete names; short functions with one task each; no magic numbers; docstrings
  (Google style) on every module, class and public function; comments explain *why*; references to the standard cite
  their section (`ISO 32000-1, 12.4.2`).
- **Errors:** Penfold’s own exceptions (`PenfoldError` and its subclasses) for expected failures (damaged PDF, missing
  password, not allowed); errors that reach the interface are shown with a GNOME dialog or toast, never swallowed.
- **Tests:** pytest. The `document` layer is tested in depth (opening, changing, undoing, saving and opening again,
  checking the result with pikepdf), because that is where data can be lost. The interface tests run the real windows
  on a display without a screen. Test PDFs are made by the tests themselves, plus a real form
  (`tests/fixtures/form.pdf`).
- **Before every commit** (a pre-commit hook) and **on GitHub Actions** for every push: `ruff check`, `ruff format
  --check`, `mypy` and `pytest` on Debian 13, and the Flatpak build on the GNOME runtime. The Flatpak built there
  (`penfold.flatpak`) is the one attached to each release.
- **Development:** `build-aux/set-up-dev-environment.sh` creates the virtual environment with the tools and installs
  the hook; `build-aux/run-from-source.sh` builds Penfold with Meson into `_build/` and runs it, without installing
  anything in the system.
- **Meson** builds and installs everything: the Python package, the compiled interface, the icons, the `.desktop`
  file, the AppStream metainfo, the settings schema and the translations.

## Decisions taken

- **A native GNOME app**, built from GTK 4 and libadwaita widgets as they are, rather than imitating them: it looks and
  behaves like the rest of the desktop and follows its changes.
- **Change the PDF, never rebuild it**, and keep everything Penfold does not edit: a PDF reader must not lose anything
  of a file.
- **Own `/AP` for everything Penfold writes:** Penfold decides exactly how its annotations look, instead of leaving it
  to each viewer.
- **Hollow shapes by default:** rectangles, circles and arrows have a transparent inside, so they can surround text or
  images without hiding them; a fill can be chosen.
- **Annotations from other programs are edited only as far as Penfold can keep them:** what is not touched is kept,
  moving keeps their drawing, and resizing is offered only when Penfold can draw them the same way.
- **Undo instead of confirmations:** deleting asks nothing, because it can be undone.
- **Right-click menus instead of buttons that appear on hover:** the left click selects text or draws, the right click
  edits; the three list views of the panel work alike.
- **Bookmark colors readable on white**, adjusted on screen to the panel’s background without changing the file.
- **Fixed blank page sizes:** A4, Letter, A5 and A3, portrait only, to keep the dialog simple.
- **Passwords are never remembered**, and permissions can be ignored only by the user’s choice in Preferences.
- **No network, ever.**
- **Original code:** everything is written from scratch for Penfold, using libraries only through their API; the
  third-party works included are listed in `THIRD-PARTY-NOTICES.md`.
