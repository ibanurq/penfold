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
- **Version: 0.5.2** (tab title “Penfold 0.5.2”). Features are frozen in 0.5: the third number only goes up for
  visual polish and bug fixes.
- **Licence: GPL-3.0.** Compatible with the libraries used: pdf.js (Apache-2.0), pdf-lib (MIT) and Lucide icons (ISC).
- **Repository:** `https://github.com/ibanurq/penfold` (GitHub user `ibanurq`). Planned app ID:
  `io.github.ibanurq.Penfold`.

## Files

```
index.html          page structure: toolbar, side panel, welcome screen
css/penfold.css     all styles
js/penfold.js       the whole application (plain JavaScript, a classic script, no modules)
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
- **Dialogues (`#dlg`, `#dlg2`):** dark backdrop with `backdrop-filter: blur(2px)`, box with 24 px padding, 400 px wide.
- **Controls:** fields with 8 px corners; round search field; pure-CSS checkboxes and radio buttons; GNOME-style thin
  rounded scrollbars and focus rings.
- **Icons:** Lucide, stroke 1.8, round caps and joins, 20 px in the main toolbar and 18 px in the panel bars.
- **Single palette (`PAL`):** six colours used for everything (highlight, underline, strikethrough, comment, text box,
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

- **Bookmark palette (`BM_PAL`):** only in the bookmarks’ colour button, 8 colours in 4 columns × 2 rows: the six
  above plus **Grey** `#606971` (top right) and **Burgundy** `#ad182e` (bottom right). The annotations’ “Change
  colour” palette keeps the 6 (3 × 2).
- **Colour squares (`.sw` in the toolbar, `.sq` in palettes):** same look (24 px, 5 px corners, thin border); the
  selected one in the toolbar has a ring in the text colour.

The initial colour is Yellow (`#f9f06b`).

## Interface terms

All text in the code is British English; Spanish lives in the `ES` dictionary (see “Languages”).

| English | Spanish | Notes |
|---|---|---|
| Penfold | Penfold | App name. Tab title: “Penfold 0.5.2”. |
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
- **Right:** Find, Zoom out, Zoom in, Fit to page width, Whole page, Two pages, and Information (see “About dialogue”).

### Without a PDF

Only Open, Merge and Information are enabled; every other control (side panel, tools, colours, go to page, zoom, two
pages, Save, Save As…, Print, Find) is greyed out and disabled. `ready()` enables them when a PDF is opened or
merged (list `NEED_PDF`). A new control that needs a PDF must be added to that list. Exception: with a protected PDF,
`ready()` leaves Save, Save As… and Print disabled.

### Welcome screen

With no PDF open, the viewer shows a GNOME-style welcome screen (`#empty`, like the one in GNOME’s document viewer
Papers): a monochrome symbolic SVG icon (`currentColor`, opacity .2, about 250 px wide, roughly the width of the two
buttons) and, below it, a title (“Get started”), a line (“Open a PDF, or merge several”) and two rounded primary
buttons, **Open…** and **Merge…**, which click `#bOpen` and `#bMerge`. It disappears when pages are painted
(`renderMain` empties `#view`). The icon is a sheet with lines of text, a highlight and a marker pen, drawn with an
SVG mask for the gaps.

### Zoom on opening and when the viewer width changes

When a PDF is opened (or merged), `ready()` calls `fitOnOpen()`, which sets `cur=0` and applies “Fit to width”
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

**Bookmark destinations (`dd`):** when the outline is read, `convert()` keeps the original destination as
`dd={n:name, a:[arguments]}` (`XYZ`, `FitH`, `FitV`, `FitR`, `Fit`, `FitB`, `FitBH`, `FitBV`; `null` = no value).
`ddFrom` extracts it from pdf.js, `ddOk` validates it and `ddY` gets the height. On save, `build()` writes the
destination back **as it was** (`[page /XYZ null 700 null]`, etc.); without a valid `dd` it writes `[page /Fit]`.
Bookmarks created in Penfold have no `dd` (they go to the start of the page). “Point to the current page” (⚑) clears
`dd`, because the old height no longer belongs to the new page.

### Side panel

- Hidden by default; opens automatically when a PDF is loaded. Minimum width 265 px (`SIDE_MIN`); the maximum
  allows up to 4 thumbnail columns. Its width is remembered (`localStorage`).
- **Pages:** actions on the selection — Delete (left), Add and Extract (centre), Rotate anticlockwise / clockwise
  (right). Responsive thumbnails in 1 to 4 columns (`thCols()`), never wider than 310 px. For portrait pages the
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
- **Text box (`FreeText`):** lines are split with Helvetica metrics (`ftLines`), like `pre-wrap` on screen. The `/AP`
  draws the faint background, the border and the text in black. Characters Helvetica lacks are drawn as `?`, but
  `/Contents` keeps the full UTF-16 text.
- **Shapes (`Square`, `Circle`, `Line`):** drawn by `shapeAP(ctx, a, r)` inside the `BBox`, line width `SW=1`; circles
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
okLabel)` returns the text or `null`; `choiceDialog` offers several options. Enter confirms, Esc cancels. Short notices
use `msg()` (a toast at the bottom for 4.5 s). Callers must `await` them.

### Languages (English and Spanish)

English is the base language: every string in the code is British English (*colour*, *anticlockwise*, *grey*…).
Spanish comes from the `ES` dictionary at the top of `js/penfold.js`: the key is the English string and the value the
Spanish text.

- **Choosing the language (`LANG`):** first `?lang=en` or `?lang=es` in the address; otherwise `navigator.languages`
  in order of preference (the first `es` or `en` wins); if the browser only has Basque, Catalan or Galician, Spanish;
  otherwise English. It is also set on `<html lang>`.
- **`_t(text, values, context)`:** translates a string; `{name}` placeholders are filled from `values`. The context
  separates two uses of the same English string with different Spanish: its key is `context + "\u0004" + text` (today
  `page\u0004Delete` and `dialog\u0004Delete bookmark`).
- **`_n(n, singular, plural)`:** picks the singular or plural form; the strings contain `{n}`.
- **`i18nApply(element)`:** translates static text (text nodes and `title` / `placeholder` attributes) by looking each
  one up in the dictionary. It runs once on the whole page at start-up and on every dialogue built with `innerHTML`
  right after it is built, so static HTML and dialogue templates carry plain English.
- **With English nothing is done:** `i18nApply` returns at once and `_t` returns the string as it is.
- **Adding text:** write it in English in the code (through `_t` if JavaScript builds it) and add its pair to `ES`. A
  string missing from `ES` shows in English in the Spanish version: it breaks nothing, but it shows.
- **Not translated:** identifiers stored in the PDF, such as the author `Penfold`. A new bookmark’s default title
  (“Page 3” / “Página 3”) is translated **when it is created** and stays in the PDF in that language. Default file
  names (`document.pdf`, `merged.pdf`, `extracted_01.pdf`, `_annotated.pdf`, `_flattened.pdf`) also go through `_t`.
- **More languages:** another dictionary (`FR={…}`) and a wider `LANG` would be enough.

### About dialogue

The Information button (always enabled) opens `aboutDialog()`, a GNOME-style “About” window (`#dlg`, 470 px wide,
everything centred):

- **Icon:** the app’s colour icon, `assets/penfold.svg`, 96 px (`APP_ICON`). The welcome screen keeps its own
  monochrome symbolic version.
- **Texts, in order:** “Penfold” (22 px, bold); “Version 0.5.2”; “Read, annotate and organise your PDFs.”; the links
  “Website” (repository) and “Report an issue” (`/issues`), in the accent colour, opening in a new tab; “Created by
  ibanurq, with AI assistance”; “Uses pdf.js (Apache-2.0) · pdf-lib (MIT) · Lucide icons (ISC)”; “© 2026 ibanurq ·
  Licence GPL-3.0” (the licence links to gnu.org). The last three lines are small and dimmed.
- **Button:** Close (focused). Enter and Esc also close it.
- **Data in one place:** name, version, author, year, repository and licence are in the `APP` constant. For a new
  version change `APP.version`, the `<title>` in `index.html` and `version` in `package.json` (the tests check that
  they match).

### Adding, extracting and merging

- **Add pages** (Pages tab): from an existing PDF (its bookmarks are inserted in the right place) or a blank page in
  portrait **A4**, **Letter**, **A5** or **A3**; at the start, at the end or after a given page.
- **Extract pages:** by ranges (`1, 5, 10-12, 56-`), with help on hover. Options: extract as separate pages, delete
  the pages from the document afterwards, delete bookmarks and annotations (for sharing). With the File System Access
  API the user picks a folder (existing names: overwrite, rename or cancel); otherwise the files are downloaded.
- **Merge:** a list where PDFs are added with a button or dropped from the file manager, reordered by dragging and
  removed with ✕. Options: a bookmark for each file, and keep each file’s bookmarks. At least two mergeable files are
  needed. If a document is open, Penfold asks before closing it without saving.

### Forms (AcroForm)

- **Kept on save:** `copyPages` in pdf-lib does not copy the catalogue’s `/AcroForm`, so `build()` calls
  `carryForm(out, src, pgs)`, which rebuilds it with the fields whose widgets are on the final pages: it keeps `/DA`,
  `/DR` (copied with `PDFObjectCopier`), `/Q` and `/NeedAppearances` (not `/SigFlags`, because the document is
  rewritten); removes widgets of deleted pages from `/Kids`; fixes each annotation’s `/P`; and, when merging, renames
  repeated field names from another document (`name` → `name_2`). `build()` makes **one `copyPages` call per document**
  so fields shared between pages are copied once. If `carryForm` fails, the file is saved without the form rather than
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
- **Saved editable:** at the end of `build()`, `applyForm(out, ren)` writes `docs[di].fv` into the final PDF, **only the
  touched fields**. Text: `setText` + `defaultUpdateAppearances` (Helvetica; text outside WinAnsi, e.g. emoji, is
  written to `/V` in UTF-16 and `/NeedAppearances` is set). Checkboxes: `check()`/`uncheck()`. Radio buttons: the
  on-screen value is the button’s state name; when the group has `/Opt` it is translated to its option before
  `select()`. Lists: export values with `setValues` (with `/NeedAppearances` when options have display text different
  from their value). A field that fails does not stop the save: they are counted and reported with `msg`.
  `out.save({updateFieldAppearances:false})` keeps pdf-lib from redrawing untouched fields. Print and Extract also use
  `build()`, so they include the values.
- **Flatten:** `build({flatten:true})` runs `flattenForm(out)` after `applyForm`: each field’s `/AP` is drawn as fixed
  page content, fitting the transformed appearance box (`/BBox` by `/Matrix`) to the field’s `/Rect` (ISO 32000-1,
  12.5.5); hidden widgets or widgets without appearance are ignored; widgets, fields and `/AcroForm` are removed. It is
  Penfold’s own flattening because pdf-lib’s `form.flatten()` fails on fields without appearance and leaves the widgets.
  If it fails, saving fails with a clear error. **Interface:** only in **Save As…** and only when the document has
  fillable fields (`hasForm()`): a dialogue with the checkbox “Flatten the form” (unticked by default; Esc or Cancel do
  not save). “Save” never flattens. A flattened copy is an **export**: it does not become the working file. Without the
  File System Access API the download is called `…_flattened.pdf`.

### Saving

- **Save:** with a file handle (opened through the File System Access API), asks to overwrite and writes the file.
  Without a handle it behaves as Save As…, or downloads a copy (`…_annotated.pdf`) where the API does not exist.
- **Save As…:** the system “save” window (`showSaveFilePicker`); the new file becomes the working file.
- **`build(options)`** builds every output (save, print, extract): copies the pages, applies rotations, writes own
  annotations (all or `types`, or none with `noAnnots`), the form and the bookmarks (`/Outlines`, with `/Count`, open
  state, colour and bold/italic flags, `PageMode /UseOutlines`).

### Find and print

- **Find (Ctrl+F):** floating bar at the top right. Reads each page’s text without painting it (fast on large PDFs),
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
  `PDFDocument.load(…, {ignoreEncryption:true}).isEncrypted` from pdf-lib. Stored in `docs[di].enc`; `isLocked()`
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
- **Disabled:** Save, Save As…, Print and Extract pages (Find stays enabled). Ctrl+P shows a `msg` instead.
- **Adding pages from a protected PDF** is refused with a message; **Merge** lists protected files in red
  (`#e01b24`) with “Cannot be merged” instead of the page count and leaves them out.
- **Safety net:** `build()` throws a clear error if any source document `isEncrypted`.

## Technical details

- **Libraries:** pdf.js 3.11.174 (reading, painting, text) and pdf-lib 1.17.1 (writing), in `vendor/`.
- **Languages:** `ES`, `LANG`, `_t`, `_n` and `i18nApply`. The name `_t` is deliberate: `t` is a local variable in
  many functions.
- **Memory model:**
  - `docs`: one entry per loaded PDF (`bytes`, pdf.js `pdf`, form `fv`/`fvDirty`, `enc` if protected).
  - `pages`: the document’s pages in order; each one has `doc`, `idx` (page in its source PDF), `rot`, `thumb`,
    `loaded`, `widgets` and `annots`.
  - Annotation types: `hl`, `ul`, `so` (StrikeOut), `sq` (Square), `ci` (Circle), `ar` (Arrow / Line), `note`, `ft`,
    plus `link`. Text annotations use `quads`; others use `x`, `y` (and `x2`, `y2`, `w`). `ro: true` marks foreign ones.
  - `bms`: the bookmark tree (`title`, `page`, `dd`, `color`, `bold`, `italic`, `open`, `items`).
  - `cur`: current page index; `scale`: zoom; `tool`, `color`: current tool and colour.
- **Shapes and `/AP`:** `shapeAP`, `quadAP`, `ftAP` and `noteAP` write raw PDF drawing operators (`m`, `l`, `c`, `re`,
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
