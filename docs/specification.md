# Penfold — specification

This document describes Penfold as it is today: what it does, how it looks, how it is built and which design
decisions have been taken, in enough detail for someone else to rebuild it. It is not a change history (see
`CHANGELOG.md`). **The code is the source of truth**: if anything here disagrees with the code, the code wins.

How the app is developed with an AI assistant is described in [working-with-ai.md](working-with-ai.md).

## What it is

Penfold is a basic PDF editor for personal use that runs in the browser, with no installation and no server: open
`index.html` and it works, also offline. It can read PDFs, find text, annotate them (and edit those annotations),
reorganise their pages, edit their bookmarks, merge several PDFs, extract pages, fill in forms and print.

Annotations (highlight, underline, strikethrough, text box, comment, rectangle, circle and arrow) are always saved
with **their own appearance stream (`/AP`)**, so they look the same in Penfold and in any other viewer. Annotations
made with other programs are shown read-only. Text written into PDF dictionaries is UTF-16, so emoji and special
characters are kept. Protected (encrypted) PDFs can be read and annotated on screen but not saved, printed or
extracted: Penfold warns and blocks those actions (see “Protected PDFs”).

## Name, version and licence

- **Name: Penfold.** *Pen* + *fold* (a folded sheet of pages): the two halves of the app, annotating and organising
  pages. Always use it with a descriptive subtitle, e.g. “Penfold — PDF editor”. Penfold recognises its own
  annotations only by the author `Penfold`.
- **Version: 0.6.0** (tab title “Penfold 0.6.0”). The second number goes up when features are added (0.6: keyboard
  shortcuts and the main menu); the third one only for visual polish, translations and bug fixes.
- **Licence: GPL-3.0.** Compatible with the libraries used: pdf.js (Apache-2.0), pdf-lib (MIT) and Lucide icons (ISC).
- **Repository:** `https://github.com/ibanurq/penfold` (GitHub user `ibanurq`). Planned app ID:
  `io.github.ibanurq.Penfold`.

## Files

```
index.html          page structure: toolbar, side panel, welcome screen
css/penfold.css     all styles
js/penfold.js       the whole application (plain JavaScript, a classic script, no modules)
js/i18n/            translations, one file per language (es.js, eu.js…)
vendor/             pdf.js 3.11.174 (with worker and stylesheet) and pdf-lib 1.17.1, unchanged
tests/              Playwright tests, test PDFs and reference screenshots
```

- No build step and no framework. The scripts are classic `<script>` tags loaded in this order at the end of
  `<body>`: pdf.js, pdf-lib, `js/penfold.js`. Classic scripts (not ES modules) are deliberate: browsers do not allow
  modules from `file://`.
- **Offline:** everything the app needs is in the folder. At start-up the pdf.js worker is fetched and turned into a
  `blob:` URL; when the page is opened as a file (`file://`), where `fetch()` is not allowed, the worker is given by its
  path instead.
- **Security:** every PDF is opened with `isEvalSupported: false` (CVE-2024-4367 in pdf.js 3.11).

## Visual style

The look follows the GNOME Human Interface Guidelines and libadwaita: minimal, with automatic light and dark mode
(`prefers-color-scheme`).

- **Theme variables:** `--chrome`, `--pane`, `--bg`, `--panel`, `--ink`, `--line` and `--acc`. Accent: GNOME blue
  (`#3584e4` light, `#78aeed` dark). The canvas background (`--bg`) is a subtle grey so the sheet stands out.
- **Type:** Cantarell, then Inter and the system font. Primary buttons (`.on`) are semibold (600).
- **Top bar:** padding `8px 12px` and an inner highlight. Flat buttons with a translucent background on hover.
- **PDF pages:** soft multi-layer shadow that imitates paper.
- **Dialogues (`#dlg`, `#dlg2`), in the style of libadwaita** (values taken from its stylesheet): dialogue background
  `--dlg-bg` (#fafafb light, #36363a dark) and text `--dlg-fg`; a dimmed backdrop (`--dim`, no blur); libadwaita’s
  shadow; 11 pt text; title at 136 %, weight 800, centred. Buttons have no border, a translucent fill
  (`currentColor` at 10 %, 15 % on hover, 30 % pressed) and bold text; the main one has the accent background
  (`--acc-bg`, #3584e4) and white text; destructive ones (`.danger`) red text (`--danger`, #c30000 / #ff938c) on a
  fill of the same red. Text fields, lists and number fields are filled, borderless, 9 px corners, 34 px high, with a
  half-transparent accent focus ring. Links use `--acc-text` (#0461be / #81d0ff).
  - **Dialogues with content (`#dlg`):** 400 px wide (560 px with `.wide`), 15 px corners, 24 px padding; the answers at
    the bottom are 44 px high with 12 px corners, a common minimum width of 120 px, centred.
  - **Alerts (`#dlg2`, AdwAlertDialog):** 372 px wide, 18 px corners, padding 32 px top and 24 px elsewhere; title and
    text centred; the answers share the row’s width (and wrap if they do not fit).
- **Controls:** fields with 8 px corners; round search field; pure-CSS checkboxes and radio buttons; GNOME-style thin
  rounded scrollbars and focus rings.
- **Icons:** Lucide, stroke 1.8, round caps and joins, 20 px in the main toolbar and 18 px in the panel bars.
- **Single palette (`PALETTE`):** six colours used for everything (highlight, underline, strikethrough, comment, text box,
  shapes and bookmarks). `deep(c)` returns the same colour; it is kept only so existing calls stay untouched. Old
  annotations with other colours keep their colour.

| Name | Colour |
|---|---|
| Yellow | `#f9f06b` |
| Green | `#8ff0a4` |
| Blue | `#99c1f1` |
| Orange | `#ffbe6f` |
| Red | `#f66151` |
| Lilac | `#dc8add` |

- **Bookmark palette (`BOOKMARK_PALETTE`):** only in the bookmarks’ colour button, 8 colours in 4 columns × 2 rows: the six
  above plus **Grey** `#606971` (top right) and **Burgundy** `#ad182e` (bottom right). The annotations’ “Change
  colour” palette keeps the 6 (3 × 2).
- **Colour squares (`.sw` in the toolbar, `.sq` in palettes):** same look (24 px, 5 px corners, thin border); the
  selected one in the toolbar has a ring in the text colour.

The initial colour is Yellow (`#f9f06b`).

## Interface terms

All text in the code is British English; translations live in `js/i18n/`, one file per language (see “Languages”).

| English | Spanish | Notes |
|---|---|---|
| Penfold | Penfold | App name. Tab title: “Penfold 0.6.0”. |
| Highlight text | Resaltador | Highlight tool. In lists the item is “Highlight” / “Resaltado”. |
| Comment | Comentario | Note shown as an icon on the page (speech bubble). |
| Text box | Cuadro de texto | Text shown directly on the page. |
| Shapes | Formas geométricas | Drawing tools: Rectangle (*Cuadro*), Circle (*Círculo*) and Arrow (*Flecha*). |
| Strike through text / Strikethrough | Tachar / Tachado | StrikeOut tool and item. |
| Underline text / Underline | Subrayar / Subrayado | Tool and item. |
| Side panel | Panel lateral | Left panel with three tabs: Pages, Bookmarks and Annotations. |
| Pages | Páginas | Thumbnails tab. |
| Bookmarks | Marcadores | The PDF outline. |
| Annotations | Anotaciones | Annotation index, grouped by type and filterable. |
| Select text | Seleccionar texto | Selection tool (I-beam cursor). |
| Merge | Combinar | Join several PDFs into one. |
| Flatten | Aplanar | Turn form fields into fixed page content. |
| Rotate anticlockwise / clockwise | Girar a la izquierda / derecha | |
| Delete | Borrar / Eliminar | Spanish says “Borrar” for annotations and bookmarks and “Eliminar” for pages; English always says *Delete*, with a context in the dictionary. |

## Behaviour

### Top bar

Three groups, from left to right:

- **Left:** show / hide side panel, separator, Open PDF, Merge PDF, separator, Save, Save As…, Print.
- **Centre:** tools — Select text, Highlight, Underline, Strike through, Comment, Text box, Rectangle, Circle and Arrow
  (grouped with vertical separators); the six-colour palette (`#sws`); the “Go to page” field (“1 of 3”).
- **Right:** Find, Zoom out, Zoom in, Fit to page width, Whole page, Two pages, and the main menu ☰ (see “Main menu and keyboard shortcuts”).

### Without a PDF

Only Open, Merge and the main menu are enabled; every other control (side panel, tools, colours, go to page, zoom, two
pages, Save, Save As…, Print, Find) is greyed out and disabled. `onDocumentReady()` enables them when a PDF is opened or
merged (list `NEED_PDF`). A new control that needs a PDF must be added to that list. Exception: with a protected PDF,
`onDocumentReady()` leaves Save, Save As… and Print disabled.

### Welcome screen

With no PDF open, the viewer shows a GNOME-style welcome screen (`#empty`, like the one in GNOME’s document viewer
Papers): a monochrome symbolic SVG icon (`currentColor`, opacity .2, about 250 px wide, roughly the width of the two
buttons) and, below it, a title (“Get started”), a line (“Open a PDF, or merge several”) and two rounded primary
buttons, **Open…** and **Merge…**, which click `#bOpen` and `#bMerge`. It disappears when pages are painted
(`renderMain` empties `#view`). The icon is a sheet with lines of text, a highlight and a marker pen, drawn with an
SVG mask for the gaps.

### Zoom on opening and when the viewer width changes

When a PDF is opened (or merged), `onDocumentReady()` calls `fitOnOpen()`, which sets `currentPage=0` and applies “Fit to width”
(`setFit('w')`; in two-page mode, `setFit('p')`). If `setFit` failed, the pages are painted at the current zoom
(`renderMain`). The same happens when the side panel is resized (when the mouse is released) or shown/hidden with its
button (`reflowOnWidth`): once, not while dragging. A manual zoom is lost when the panel width changes.

### Viewer

- Pages are painted on demand with pdf.js (an `IntersectionObserver` with a 600 px margin), with a text layer and an
  annotation overlay on top. The canvas is painted at least at 2× for sharpness.
- **One page:** continuous scrolling. The current page is the one crossing the top third of the viewer.
- **Two pages:** works in pairs (1-2, 3-4…), without continuous scrolling. The wheel, the left/right arrows and
  Page Up / Page Down change pair (or scroll inside it when zoomed in).

### Going to a destination (bookmarks, annotations, links)

Clicking a bookmark, an annotation in the panel or an internal link calls `goTo(i, y)`: it goes to the page and puts
the destination height (`y`, in PDF points) in the **top third** of the viewer (`goToY`, same rule as Find). It never
scrolls above the start of the page, and without a height (thumbnails, page number, bookmarks without height) it goes
to the start of the page. In two-page mode the height is only used when the pair does not change (when it changes,
the whole page is fitted).

**Bookmark destinations (`dd`):** when the outline is read, `convertOutline()` keeps the original destination as
`dd={n:name, a:[arguments]}` (`XYZ`, `FitH`, `FitV`, `FitR`, `Fit`, `FitB`, `FitBH`, `FitBV`; `null` = no value).
`destFromPdfJs` extracts it from pdf.js, `isValidDest` validates it and `destY` gets the height. On save, `build()` writes the
destination back **as it was** (`[page /XYZ null 700 null]`, etc.); without a valid `dd` it writes `[page /Fit]`.
Bookmarks created in Penfold have no `dd` (they go to the start of the page). “Point to the current page” (⚑) clears
`dd`, because the old height no longer belongs to the new page.

### Side panel

- Hidden by default; opens automatically when a PDF is loaded. Minimum width 265 px (`SIDE_MIN`); the maximum
  allows up to 4 thumbnail columns. Its width is remembered (`localStorage`).
- **Pages:** actions on the selection — Delete (left), Add and Extract (centre), Rotate anticlockwise / clockwise
  (right). Responsive thumbnails in 1 to 4 columns (`updateThumbColumns()`), never wider than 310 px. For portrait pages the
  selection box fits the thumbnail width (class `.pt` and variable `--ar`, set when the image loads). Multiple
  selection with Ctrl/Shift; drag to reorder.
- **Bookmarks:** bar with Add, Delete (left); Bold, Italic, Colour, Clear formatting (centre); Expand/collapse
  (right). The format buttons act on the selection and are disabled without one. Drag-and-drop tree (before, after,
  inside). Hover menu on each row: edit text (✎), decrease / increase indent (←, →), point to the current page (⚑).
  A new bookmark takes the selected text as title, or asks for one (default “Page N”), and is placed in page order.
- **Annotations:** filter with toggle buttons (Highlights, Underlines, Strikethroughs, Comments, Text boxes,
  Rectangles, Circles, Arrows); Comments and Text boxes are on by default. Groups by type with a count; rows sorted by
  page and position. Click goes to the annotation. Hover buttons: Edit text (✎, comments and text boxes), Change
  colour, Delete (✕). Annotations from other programs show their author or “(External)” and have no buttons.

### Annotations on the page

- **Highlight, Underline, Strike through:** act on selected text when the mouse is released. The selection rectangles
  are merged per line into quadrilaterals. Highlight uses the pastel colour with multiply blending; underline and
  strikethrough draw a line in the chosen colour.
- **Comment:** created with a click, after typing its text. Lucide `message-square-text` icon, 33 px, black outline,
  filled with the annotation colour. Dark tooltip on hover with the text.
- **Text box:** drag to set the width; the height follows the text. Background in the colour at 14 %, 1 pt border in
  the colour, black Helvetica 11 pt.
- **Rectangle, Circle, Arrow:** drawn by dragging. Rectangle and circle use the box between the start and end points;
  the arrow goes from start to end with an open arrowhead. 1 pt line in the chosen colour, transparent inside.
- **Text dialogue** (comments and text boxes): Enter = new line, Ctrl/Cmd+Enter = save, Esc = cancel.
- **Delete:** right-click on an own annotation, after confirming.

### Saving annotations with their own appearance (`/AP`)

Every annotation gets a Form XObject in `/AP /N`, so every viewer paints the same. Free text in dictionaries (note
contents and bookmark titles) is written with `PDFHexString.fromText` (UTF-16), so special characters, backslashes,
brackets and emoji cannot break the file. Own annotations carry `T = Penfold`; when a page is saved again, the old
Penfold annotations are removed and written anew (no duplicates).

- **Highlight (`Highlight`):** polygon with `Multiply` blending in an ExtGState, opacity 0.75.
- **Underline (`Underline`) and Strikethrough (`StrikeOut`):** opaque 1 pt line, at the bottom or in the middle.
- **Text box (`FreeText`):** lines are split with Helvetica metrics (`textBoxLines`), like `pre-wrap` on screen. The `/AP`
  draws the faint background, the border and the text in black. Characters Helvetica lacks are drawn as `?`, but
  `/Contents` keeps the full UTF-16 text.
- **Shapes (`Square`, `Circle`, `Line`):** drawn by `shapeAppearance(ctx, a, bbox)` inside the `BBox`, line width `SHAPE_STROKE=1`; circles
  with four Bézier curves; the arrowhead (`/LE [/None /OpenArrow]`) computed with trigonometry.
- **Comment (`Text`):** no `/Popup`; the appearance is the same speech-bubble drawing as on screen.

### Annotations from other programs (read-only)

- **Recognised types:** Text, FreeText, Highlight, Underline, StrikeOut, Square, Circle and Line (`ro: true`). Links
  (`Link`) are handled separately: clicking them follows the URL or the internal destination.
- **Geometry:** inverted or negative rectangles are normalised with `Math.min` / `Math.max`.
- **Colour:** a foreign annotation that is white (`#ffffff`) or has no colour is shown in orange (`#c64600`), and its
  text takes that colour, so it is not invisible on white paper.
- **Integrity:** they are painted, but cannot be edited or deleted. On save, they stay in the page exactly as they
  were (properties and reply threads untouched).

### Dialogues

The app **never uses the browser’s native dialogues** (`alert`, `confirm`, `prompt`). It uses its own (`#dlg2`):
`confirmDialog(title, text, okLabel)` returns a promise with `true`/`false`; `promptDialog(title, label, initial,
okLabel)` returns the text or `null`; `choiceDialog` offers several options (each button: label, value, primary, an
extra class such as `danger`). Enter confirms, Esc cancels. Short notices
use `showMessage()` (a toast at the bottom for 4.5 s: a dark pill with white text, as libadwaita's toasts). Callers must `await` them.

### Languages

English is the base language: every string in the code is British English (*colour*, *anticlockwise*, *grey*…).
Translations live in `js/i18n/`, **one file per language** (`es.js` complete; `eu.js`, Basque, a template to fill in),
loaded with `<script>` before `js/penfold.js`. Each file adds `PENFOLD_LANGS.<code> = { 'English text': 'translation' }`.
They are `.js` files, not `.json`, because a page opened as a file (`file://`) cannot read `.json` files. The desktop
app reads the same files (`electron/i18n.js`) for its own few texts. `js/i18n/README.md` explains how to translate.

- **Choosing the language (`LANG`):** first `?lang=<code>` in the address, if that language has a file; otherwise
  `navigator.languages` in order of preference: the first one that is English or has a file wins. If none does, a
  language’s fallback is used (`LANG_FALLBACK`: Basque, Catalan and Galician → Spanish); otherwise English. It is also
  set on `<html lang>`.
- **`tKey(key)`** looks a text up in the chosen language and then in its fallback; an empty translation (`''`) counts
  as missing, so a file can be translated little by little. With nothing found, the English text is shown.
- **`_t(text, values, context)`:** translates a string; `{name}` placeholders are filled from `values`. The context
  separates two uses of the same English string with different translations: its key is `context + "\u0004" + text`
  (today `page\u0004Delete` and `dialog\u0004Delete bookmark`).
- **`_n(n, singular, plural)`:** picks the singular or plural form; the strings contain `{n}`.
- **`i18nApply(element)`:** translates static text (text nodes and `title` / `placeholder` attributes) by looking each
  one up in the dictionary. It runs once on the whole page at start-up and on every dialogue built with `innerHTML`
  right after it is built, so static HTML and dialogue templates carry plain English.
- **With English nothing is done:** `i18nApply` returns at once and `_t` returns the string as it is.
- **Adding text:** write it in English in the code (through `_t` if JavaScript builds it) and add its pair to every
  file in `js/i18n/` (translated in `es.js`, empty `''` in the others until translated). The tests check that every
  file has exactly the texts of `es.js` and that every text is still used. `npm run i18n` shows what is left to
  translate in each language.
- **Not translated:** identifiers stored in the PDF, such as the author `Penfold`. A new bookmark’s default title
  (“Page 3” / “Página 3”) is translated **when it is created** and stays in the PDF in that language. Default file
  names (`document.pdf`, `merged.pdf`, `extracted_01.pdf`, `_annotated.pdf`, `_flattened.pdf`) also go through `_t`.
- **More languages:** a new file in `js/i18n/`, loaded in `index.html`; nothing else in the code changes (the menu
  entry and the AppStream card have their own short texts per language).

### About dialogue

Main menu → About Penfold opens `aboutDialog()`, a GNOME-style “About” window (`#dlg`, 470 px wide,
everything centred):

- **Icon:** the app’s colour icon, `assets/penfold.svg`, 96 px (`APP_ICON`). The welcome screen keeps its own
  monochrome symbolic version.
- **Texts, in order:** “Penfold” (22 px, bold); “Version 0.6.0” in a pill (accent-coloured text on a pale accent
  background); “Read, annotate and organise your PDFs.”; a card (boxed list) with two rows, “Website” (repository)
  and “Report an issue” (`/issues`), each with an arrow at the end (Lucide arrow-up-right), opening in a new tab;
  “Created by ibanurq, with AI assistance”; “Uses pdf.js (Apache-2.0) · pdf-lib (MIT) · Lucide icons (ISC)”; “© 2026 ibanurq ·
  Licence GPL-3.0” (the licence links to gnu.org). The last three lines are small and dimmed.
- **Button:** Close (focused). Enter and Esc also close it.
- **Data in one place:** name, version, author, year, repository and licence are in the `APP` constant. For a new
  version change `APP.version`, the `<title>` in `index.html` and `version` in `package.json` (the tests check that
  they match).

### Main menu and keyboard shortcuts

- **Main menu (☰,** `#bMenu`, at the right end of the toolbar, always enabled): a popover in the style of libadwaita’s
  (popover colours, 12 px corners, flat rows of 32 px) with “Keyboard Shortcuts” and “About Penfold”. It closes with
  Esc, a click outside or choosing an item; the arrow keys move between the items.
- **Keyboard Shortcuts window** (`shortcutsDialog()`, also Ctrl+?): the shortcuts in groups (Annotations first, as
  they are the most used; then General, Find, View and Moving around; the annotation rows read just “Highlight” and
  “Underline”), each group a card with one row per shortcut: description on the left, keys as keycaps
  on the right. Key names are translated (Shift → “Mayús”, Page Down → “Av Pág”…). Ctrl+W and Ctrl+Q are listed only
  in the desktop app. Close, Esc or Enter close it.
- **Shortcuts:** Ctrl+O open, Ctrl+S save, Ctrl+Shift+S save as, Ctrl+P print, Ctrl+? this window; Delete
  deletes the selected pages (Pages tab) or bookmarks (Bookmarks tab), asking first, by pressing the panel's delete
  button (`data-action="delete"`); Ctrl+F find,
  Ctrl+G / Ctrl+Shift+G next / previous result (they open the find bar if it is closed), Esc closes the find bar;
  Ctrl++ (or Ctrl+=) / Ctrl+− zoom, Ctrl+0 fit to width, F9 side panel; Page Down / Page Up next / previous page,
  Ctrl+Home / Ctrl+End first / last page, Ctrl+L puts the cursor in the page box; in the desktop app, Ctrl+W closes
  the window and Ctrl+Q quits.
- **H and U:** highlight / underline. With text of a page selected they mark it (`markSelection(type)`, the same
  function the tools use when the mouse is released) and the tool stays as it was; with nothing selected they choose
  the Highlight / Underline tool. **Esc** goes back to the text selection tool (unless the find bar is open: then Esc
  closes it).
- **When they do not act:** no shortcut acts while a dialogue, the menu or the colour popover is open; the keys without
  Ctrl (H, U, Delete, Esc, Page Down / Page Up) do nothing while typing in a field (form fields, find bar, page box). The
  handler runs in the capture phase, before the other key handlers.

### Adding, extracting and merging

- **Add pages** (Pages tab): from an existing PDF (its bookmarks are inserted in the right place) or a blank page in
  portrait **A4**, **Letter**, **A5** or **A3**; at the start, at the end or after a given page.
- **Extract pages:** by ranges (`1, 5, 10-12, 56-`), explained by a dimmed line under the field. Options: extract as separate pages, delete
  the pages from the document afterwards, delete bookmarks and annotations (for sharing). With the File System Access
  API the user picks a folder (existing names: overwrite, rename or cancel); otherwise the files are downloaded.
- **Merge:** a list where PDFs are added with a button or dropped from the file manager, reordered by dragging and
  removed with ✕. Options: a bookmark for each file, and keep each file’s bookmarks. At least two mergeable files are
  needed. If a document is open, Penfold asks before closing it without saving.

### Forms (AcroForm)

- **Kept on save:** `copyPages` in pdf-lib does not copy the catalogue’s `/AcroForm`, so `build()` calls
  `rebuildForm(out, src, pageList)`, which rebuilds it with the fields whose widgets are on the final pages: it keeps `/DA`,
  `/DR` (copied with `PDFObjectCopier`), `/Q` and `/NeedAppearances` (not `/SigFlags`, because the document is
  rewritten); removes widgets of deleted pages from `/Kids`; fixes each annotation’s `/P`; and, when merging, renames
  repeated field names from another document (`name` → `name_2`). `build()` makes **one `copyPages` call per document**
  so fields shared between pages are copied once. If `rebuildForm` fails, the file is saved without the form rather than
  not at all.
- **Shown and filled on screen:** each painted page gets a layer `.fl` (`formLayer(el)`) with one HTML control per
  field — text (`input`/`textarea`, with `maxLen`, password, alignment and font size from the PDF), checkbox, radio
  buttons, dropdown and list (single or multiple). It is built from `getAnnotations()` data (not pdf.js’s
  `AnnotationLayer`, to avoid its internal API). Push buttons and signatures are left out. Values live in
  `docs[di].fv` (full field name → value) and touched fields in `docs[di].fvDirty`; they survive zoom and page changes
  and are synchronised between widgets of the same field. Checkboxes and radios have their own styles (black tick and
  dot) because the app’s global checkbox styles are cancelled inside `.fl`. Fields only take the mouse with the Select
  text tool. The canvas does not paint widgets (`AnnotationMode.DISABLE`), so fields have a faint blue background.
  Known limits: on pages rotated in Penfold the field text does not rotate; no JavaScript calculations or validation.
- **Saved editable:** at the end of `build()`, `writeFormValues(out, renamed)` writes `docs[…].fv` into the final PDF, **only the
  touched fields**. Text: `setText` + `defaultUpdateAppearances` (Helvetica; text outside WinAnsi, e.g. emoji, is
  written to `/V` in UTF-16 and `/NeedAppearances` is set). Checkboxes: `check()`/`uncheck()`. Radio buttons: the
  on-screen value is the button’s state name; when the group has `/Opt` it is translated to its option before
  `select()`. Lists: export values with `setValues` (with `/NeedAppearances` when options have display text different
  from their value). A field that fails does not stop the save: they are counted and reported with `showMessage`.
  `out.save({updateFieldAppearances:false})` keeps pdf-lib from redrawing untouched fields. Print and Extract also use
  `build()`, so they include the values.
- **Flatten:** `build({flatten:true})` runs `flattenForm(out)` after `writeFormValues`: each field’s `/AP` is drawn as fixed
  page content, fitting the transformed appearance box (`/BBox` by `/Matrix`) to the field’s `/Rect` (ISO 32000-1,
  12.5.5); hidden widgets or widgets without appearance are ignored; widgets, fields and `/AcroForm` are removed. It is
  Penfold’s own flattening because pdf-lib’s `form.flatten()` fails on fields without appearance and leaves the widgets.
  If it fails, saving fails with a clear error. **Interface:** only in **Save As…** and only when the document has
  fillable fields (`hasForm()`): a dialogue titled “Save As” (no ellipsis: GNOME keeps it for the labels of buttons and menu items that
  open a dialogue) with a card holding a switch row “Flatten the form” and its explanation (off by default; Esc or Cancel do
  not save). “Save” never flattens. A flattened copy is an **export**: it does not become the working file. Without the
  File System Access API the download is called `…_flattened.pdf`.

### Saving

- **Save:** with a file handle (opened through the File System Access API), asks to overwrite and writes the file.
  Without a handle it behaves as Save As…, or downloads a copy (`…_annotated.pdf`) where the API does not exist.
- **Save As…:** the system “save” window (`showSaveFilePicker`); the new file becomes the working file.
- **`build(options)`** builds every output (save, print, extract): copies the pages, applies rotations, writes own
  annotations (all or `types`, or none with `noAnnots`), the form and the bookmarks (`/Outlines`, with `/Count`, open
  state, colour and bold/italic flags, `PageMode /UseOutlines`).

### Unsaved changes

- **How Penfold knows:** it remembers how the document was when it was opened or last saved, and compares it with how
  it is now. `docShape()` covers page order and rotation, bookmarks (title, page, destination, colour, bold, italic;
  not whether they are expanded) and form values; each of Penfold’s own annotations keeps a snapshot of itself (`_o`)
  and each page how many there were (`_nOwn`), so new, edited, recoloured and deleted annotations all count.
  `markSaved()` runs after opening and after a successful save; annotations read from the file are marked as they load
  (`markPageSaved`). Undoing a change by hand leaves nothing to save. A merged document is unsaved until it is saved
  (`markSaved(true)`). A flattened copy is an export: the document keeps its unsaved changes. A form field set back to
  its value in the PDF counts as untouched again (it is left as it is on save).
- **`hasUnsavedChanges()`** answers the question; **`confirmUnsaved()`** asks it before the document is replaced or the
  desktop window is closed, and **first**, so no work is done twice: Open asks before the file chooser, Merge when its
  toolbar button is pressed (before its dialogue), a PDF handed over by the desktop app before it is loaded
  (`openFromDesktop`); `openFile(handle, file)` then replaces the document. The question: “Save changes to “name”?” / “If you
  don’t save, your changes will be lost.” with **Cancel**, **Discard** and **Save** (primary, focused). The text is
  centred and Discard is a destructive action (red, `button.danger`, colour `--danger`), as in GNOME. Save saves (or
  asks where, as Save As…) and then goes ahead; if saving fails or is cancelled, nothing is replaced. A protected PDF
  cannot be saved: “Discard the changes to “name”?” with Cancel and Discard. Without unsaved changes nothing is asked.
- **Browser tab:** closing it with unsaved changes makes the browser ask with its own generic message (`beforeunload`).

### Desktop app (Electron)

`electron/main.js` shows `index.html`, unchanged, in one or more windows; `electron/preload.js` is the only bridge to the
system (take the file the desktop asked to open; write back to that file only).

- **One process, several windows.** A PDF from the desktop (file manager “Open with”, command line, a second launch)
  opens in an empty window if there is one (the focused one first), otherwise in a new window. A PDF dropped on a window
  opens in that window (with the unsaved-changes question if needed). “New Window” in the dock’s menu (desktop action,
  `--new-window`) opens an empty window; launching Penfold again without files brings the open window forward.
- **Saving** a PDF opened from the desktop writes back to that file (via a temporary file and a rename).
- **Closing** a window (title bar, Ctrl+W) or quitting (Ctrl+Q, every window in turn) asks only when there are unsaved
  changes; Cancel in any window stops quitting.
- **Title:** “file.pdf — Penfold”, with “• ” in front while there are unsaved changes; “Penfold” with no document.
- **Like a desktop app, not a browser:** no menu, no navigation, no reload or developer tools, links in the default
  browser, no spell-check downloads, sandboxed page; the window size, position and maximised state are remembered;
  settings in `~/.config/Penfold`.
- **Package:** `npm run dist` builds a Debian package with the menu entry (Office, “Open with” for PDFs, English and
  Spanish texts), the icon in every size and an AppStream card. It also builds the browser version,
  `penfold_<version>-web.zip` (`npm run dist:web` on its own): a folder with `index.html`, `css/`, `js/`, `vendor/`,
  `assets/` and the licence files, which opens with a double click on `index.html` once unzipped.

### Find and print

- **Find (Ctrl+F):** floating bar at the top right, in the style of a libadwaita popover (popover colours, 15 px
  corners) with a search entry (filled, 9 px corners, a magnifier inside) and flat buttons. Reads each page’s text without painting it (fast on large PDFs),
  ignores case, accents and irregular line breaks, starts from the current page and puts the match in the top third
  of the viewer. Enter / Shift+Enter go to the next / previous match; Esc closes. It does not search inside
  annotation text.
- **Print (Ctrl+P):** dialogue with a checkbox per annotation type (Highlights, Underlines, Strikethroughs,
  Rectangles, Circles and Arrows ticked by default; Comments and Text boxes not). It builds a PDF without bookmarks in
  a hidden frame and calls the system print dialogue; if the browser does not allow it, the PDF opens in a new tab.

### Protected PDFs

pdf.js can read encrypted PDFs (for example with an owner password and no open password), but **pdf-lib cannot
decrypt them**: saving them produced broken files. Penfold detects them and blocks those actions:

- **Detection (`isProtected(pdf, bytes)`):** first `EncryptFilterName` in pdf.js’s `getMetadata().info`; if missing,
  `PDFDocument.load(…, {ignoreEncryption:true}).isEncrypted` from pdf-lib. Stored in `docs[…].enc`; `isLocked()`
  says whether any open document is protected.
- **On opening:** a notice (`protectedNotice`, built on `choiceDialog`) with the warning sign instead of a title and
  the centred text “This PDF is protected. Any changes made to it cannot be saved. It cannot be printed and pages
  cannot be extracted either.”, and an OK button.
- **Fixed reminder (`#lockw`, `lockBadge()`):** the same sign, 48 px, fixed at the top-left corner of the viewer (it
  does not move with zoom, scrolling or the side panel; a `ResizeObserver` on `#view` repositions it). On hover or
  focus it shows the notice in a dark tooltip. It disappears when an unprotected PDF is opened. It is not inside
  `#view`, because `renderMain` empties `#view` and the code uses `#view.children[i]` as pages.
- **Icon (`WARN_SVG`):** Lucide `triangle-alert` with GNOME yellow fill `#f6d32d` and black outline and exclamation
  mark (an exception to the monochrome toolbar icons). 56 px in the dialogue.
- **Disabled:** Save, Save As…, Print and Extract pages (Find stays enabled). Ctrl+P shows a message instead.
- **Adding pages from a protected PDF** is refused with a message; **Merge** lists protected files in red
  (`#e01b24`) with “Cannot be merged” instead of the page count and leaves them out.
- **Safety net:** `build()` throws a clear error if any source document `isEncrypted`.

## Technical details

- **Libraries:** pdf.js 3.11.174 (reading, painting, text) and pdf-lib 1.17.1 (writing), in `vendor/`.
- **Languages:** `js/i18n/<code>.js` (`PENFOLD_LANGS`), `LANG`, `LANG_FALLBACK`, `tKey`, `_t`, `_n` and `i18nApply`. The name `_t` is deliberate: `t` is a local variable in
  many functions.
- **Memory model:**
  - `docs`: one entry per loaded PDF (`bytes`, pdf.js `pdf`, form `fv`/`fvDirty`, `enc` if protected).
  - `pages`: the document’s pages in order; each one has `doc`, `idx` (page in its source PDF), `rot`, `thumb`,
    `loaded`, `widgets` and `annots`.
  - Annotation types: `hl`, `ul`, `so` (StrikeOut), `sq` (Square), `ci` (Circle), `ar` (Arrow / Line), `note`, `ft`,
    plus `link`. Text annotations use `quads`; others use `x`, `y` (and `x2`, `y2`, `w`). `ro: true` marks foreign ones.
  - `bookmarks`: the bookmark tree (`title`, `page`, `dd`, `color`, `bold`, `italic`, `open`, `items`).
  - `currentPage`: current page index; `scale`: zoom; `tool`, `annotColor`: current tool and colour.
- **Shapes and `/AP`:** `shapeAppearance`, `markupAppearance`, `textBoxAppearance` and `noteAppearance` write raw PDF drawing operators (`m`, `l`, `c`, `re`,
  `S`, `f`…).

## Decisions taken

- **Foreign annotations read-only:** not adopted as own, editable or deletable. Each viewer handles styles and states
  (e.g. reply threads) its own way; changing them through pdf-lib risks losing other people’s data. Showing them is
  enough for interoperability.
- **Hollow shapes:** rectangles, circles and arrows have a transparent inside, so they can surround text or images
  without hiding them.
- **UTF-16 in dictionaries:** every text `PDFString` was replaced by `PDFHexString`, the standard way to keep emoji,
  backslashes and brackets from breaking the file.
- **Own `/AP` for everything:** Penfold decides exactly how annotations look, instead of leaving it to each viewer.
- **Fixed blank page sizes:** A4, Letter, A5 and A3, portrait only, to keep the interface simple.
- **No native dialogues, no build step, no framework, no network:** the app stays a folder that opens with a
  double-click and works anywhere.

## Possible improvements

- **Text boxes:** move and resize with handles on the canvas.
- **Object clean-up:** when a file saved by Penfold is saved again, remove the orphan objects of the previous save.
