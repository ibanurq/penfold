# Changelog

All notable changes to Penfold are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Version numbers: the second number goes up when features are added (0.5 → 0.6); the third one (0.6.1, 0.6.2…) only
for visual polish, translations and bug fixes.

## 1.0.0-alpha.12 — 2026-11-24

Twelfth preview of Penfold 1.0: pages and bookmarks are edited from a menu, a right click away, as annotations are.

### Added
- A right click on a thumbnail (or a long press, the Menu key or Shift+F10) opens the menu of the pages selected:
  Rotate Left, Rotate Right, Rotate 180° (new) and Delete. A thumbnail not selected is selected alone first.
- A right click on a bookmark opens the menu of the bookmarks selected: the eight colours (the bookmarks’ own with a
  ring), Bold and Italic (ticked when all of them have it), Clear Formatting, Rename… (F2), Point to the Current Page,
  Increase Indent, Decrease Indent and Delete. What cannot be done is greyed out; a PDF that does not allow changing
  its pages or bookmarks shows the menus greyed out.
- While pages or bookmarks are selected, a counter floats at the bottom of the list, with the look of a toast:
  “3 selected”.
- F2 renames the bookmark selected, and the Menu key opens the menu of the pages or bookmarks selected, wherever the
  focus is, while their view is shown.

### Changed
- The bars at the bottom of Pages and Bookmarks, and the Format panel of the bookmarks, are gone: their menus do what
  they did.
- The dialogue to change the text of a bookmark is called Rename.

## 1.0.0-alpha.11 — 2026-11-23

Eleventh preview of Penfold 1.0: annotations are moved and resized on the page, with handles.

### Added
- Move and Resize, in the menu of an annotation (Move for comments, whose size is fixed), also from the Annotations
  panel. The annotation shows its handles over a thin frame: dragging a handle changes its size, dragging the
  annotation moves it, inside its page. Enter or a click outside accept the change, Esc cancels it, and one undo takes
  it back.
- Rectangles and circles have a handle at each corner; arrows one at each end.
- Text boxes have a handle at each side, which changes only their width: the text is laid out again as the handle is
  dragged, and the box grows or shrinks to it.
- Highlights, underlines and strikethroughs have a handle where they start and one where they end, which cover more
  or less text, letter by letter; the item is greyed out where there is no text under them.
- Annotations made with other programs are moved keeping the drawing their program made, on the screen and when
  saving. They are resized only if Penfold can draw all of their look again; otherwise their menu has Move.

### Fixed
- Saving, printing, extracting, editing the pages or closing first accept what is being edited on the page: a move
  not accepted yet, or a text box being written, were left out of the file saved.

## 1.0.0-alpha.10 — 2026-11-23

Tenth preview of Penfold 1.0: annotations are edited from their menu, a right click away, also those made with other
programs.

### Added
- A right click on an annotation (or a long press) opens its menu, and outlines it: the six colours at the top, the
  annotation’s own with a ring, then Edit Text…, Format… and Delete, as its type has them. A left click still only
  selects text, also over a highlight. Annotations of types Penfold does not make only have Delete; a PDF that does
  not allow annotating shows the menu greyed out.
- A colour of the menu changes the annotation at once. Delete deletes it without asking, with a toast to undo it.
- Edit Text… opens a comment’s popover with its text, and writes a text box’s text on the page, with its format; the
  box keeps where its text starts and its width, and grows or shrinks to the text.
- Format… opens a panel beside the annotation, with its colours and the rows of its type: opacity for marks on text;
  line width (thin, medium, thick), solid or dashed line, a soft fill and opacity for rectangles and circles; the same
  and arrowheads (at the end, at both ends or none) for arrows; letter size, background and border for text boxes.
  Every change shows at once, and all of them are undone as one.
- Annotations made with other programs, of the types Penfold makes, are edited too: Penfold reads their look, name and
  dates, keeps what is not changed, and warns before changing one whose look it cannot draw again (a cloudy border, a
  closed arrowhead, another font or background colour). Until changed, they are drawn as their program made them.
- The Annotations panel: rows are selected and unselected as in Pages and Bookmarks; a right click on a row, the Menu
  key or Shift+F10 open the menu of its annotation, the document going to it; Delete deletes the rows selected.
- Annotations deleted or changed are taken out of their pages when saving, printing or extracting, with the pop-up
  windows of their notes.

### Fixed
- The group headings of the Annotations panel count the annotations left after an edit.

## 1.0.0-alpha.9 — 2026-11-22

Ninth preview of Penfold 1.0: annotations are made, with the pencil’s floating bar, and saved as the PDF standard asks.

### Added
- The pencil shows a floating bar at the bottom of the document, with the look of the zoom buttons: Select Text, then
  the tools by group (highlight, underline, strike through · rectangle, circle, arrow · comment, text box) and the
  colour, whose palette of six circles opens above it and closes on choosing. A tool stays chosen until another one is,
  or Esc; hiding the bar goes back to Select Text. Toasts rise above the bar.
- Highlight, underline and strike through mark the text selected when the mouse is released, one mark per line,
  fitted to the characters; a selection over several pages makes one mark on each, undone together. H and U mark the
  text selected without changing the tool, or else choose their tool. Text can be marked even in a PDF that does not
  let it be copied.
- Rectangles, circles and arrows are drawn by dragging, shown while dragging and kept inside the page.
- A comment is placed with a click: its speech bubble shows there, and its text is written in a popover below it
  (Enter, a new line; Ctrl+Enter, apply; Esc, cancel). Its text shows when the pointer is over it.
- A text box is written on the page, in a box that grows with the text: a drag sets its width, a click gives it the
  usual width; Ctrl+Enter or a click outside apply, Esc cancels. Its font, Liberation Sans 11 pt, goes inside the PDF
  with only the characters used, and characters it lacks are taken from other fonts of the system: any text shows
  everywhere, and the lines break as they did while writing.
- Every annotation made can be undone and redone; its author is the one in Preferences (empty: “Penfold”).
- Annotations are saved with their own drawing and every entry of the PDF standard (colour, opacity, border, unique
  name, dates, texts in UTF-16…), so any viewer shows them as Penfold does and any editor can change them. Comments
  stay upright on turned pages. Saving, printing and extracting write them.
- With any tool but Select Text, the mouse goes through form fields to the page.
- A PDF that does not allow annotating has the pencil greyed out.
- The Keyboard Shortcuts window lists the annotation keys first: H, U and Esc.

### Changed
- Annotations are grouped in four groups everywhere: text highlights, shapes, text elements and, new, other types.
  The Annotations panel lists them in those four sections, with the icon of each type on its row, and its filter is a
  popover with a box for each group, which stays open while choosing. The print dialogue has a fourth switch.
- Annotations of turned or cropped pages are placed as they are shown, like form fields.

## 1.0.0-alpha.8 — 2026-11-22

Eighth preview of Penfold 1.0: Preferences, the choice of a light or dark style, and PDFs with an open password.

### Added
- Preferences (in the main menu, Ctrl+,): the author name of new annotations (empty: “Penfold”) and “Respect Document
  Permissions”, on by default. Every change is kept at once.
- With “Respect Document Permissions” off, the permissions of a PDF are ignored: no lock and every tool, at once in
  every window. Files are still saved keeping their permissions, and PDFs that deny assembling can be merged or have
  their pages added to another document; the result has no permissions.
- Three circles at the top of the main menu choose the style: follow the system (the default), light or dark. The
  pages of the PDF keep their colours.
- PDFs with an open password ask for it when they are opened, however that is done; a wrong password asks again.
  Penfold does not remember it. Saving, Save As and extracting keep both passwords and the permissions.
- A PDF opened with its owner password allows everything, with no lock.
- PDFs with an open password can be merged or have their pages added to another document, asking for the password;
  the result has none.

### Changed
- “Restrictions” are now called user access permissions, as in the PDF standard. The lock’s tooltip lists them and
  says they can be ignored in Preferences.
- Only its permissions stop a PDF from being merged or having its pages added: an encrypted PDF that allows assembling
  no longer counts as protected.

## 1.0.0-alpha.7 — 2026-11-21

Seventh preview of Penfold 1.0: forms are filled in and saved, the document is printed choosing which annotations go
on paper, and PDFs with restrictions can be used as far as they allow, and saved.

### Added
- Form fields can be filled in on the pages: text (with the maximum length, password, alignment and font size of the
  PDF), checkboxes, radio buttons, dropdowns (also those that let you write) and lists of one or several options.
  Each field shows its value in every place it appears; push buttons and signatures are not filled in. Every change
  can be undone, and typing in a field is undone at once.
- Save writes only the fields that changed, and the form stays editable in other viewers; a field that cannot be
  written does not stop the save and is reported. Extracted pages keep their values.
- Save As offers to flatten the form of a PDF that has one: the data becomes part of the page in a copy named
  “…_flattened.pdf”, and the document keeps its own file and changes.
- Print (Ctrl+P) first asks which annotations go on paper — text highlights, shapes and text elements, all on — and
  then opens the system’s print dialogue. Form values are always printed.
- A PDF with restrictions shows a red lock before its title; its tooltip says what the PDF does not allow.

### Changed
- PDFs with restrictions (encrypted without an open password) are no longer read-only: every tool the PDF allows
  works, the rest is greyed out, and saving keeps the encryption and the permissions. They open without a notice and
  without a banner, and their changes are saved like any others. Ctrl+P says when a PDF does not allow printing.
- Alerts with a single button answer both Enter and Esc.

## 1.0.0-alpha.6 — 2026-11-21

Sixth preview of Penfold 1.0: bookmarks can be edited, and every change can be undone.

### Added
- Add, in the Bookmarks view: a bookmark titled with the text selected in the document, at the page where the selection
  starts; with no text selected, it asks for a title, proposing “Page N” with the label of the current page. The new
  bookmark goes in page order and is selected.
- With bookmarks selected in the Bookmarks view, a bar at the bottom formats them, points one to the current page,
  edits the text of one, decreases or increases their indent, and deletes them (also with the Delete key, with a
  notice to undo it). What cannot be done with the bookmarks selected is greyed out.
- Format opens a panel with Bold, Italic, the eight bookmark colours as a row of circles, and Clear Formatting; it
  shows the style the bookmarks selected share.
- Bookmarks can be dragged before, after or inside another, several at once if the one dragged is selected; a line or
  a highlighted row shows where they will go, and the list scrolls near its edges.

### Changed
- Unlike 0.6, bookmarks that lead nowhere do not decide where a new bookmark goes, and the hover and editing menus of
  each row are gone: everything is in the bar at the bottom.

## 1.0.0-alpha.5 — 2026-11-21

Fifth preview of Penfold 1.0: pages from other PDFs. Pages can be added, extracted and merged.

### Added
- Add, in the Pages view: the pages of another PDF, or a blank page (A4, Letter, A5 or A3), at the start, at the end or
  after a page. With pages selected it proposes the place after the last of them; in a PDF with page labels it shows
  the label of the page chosen. The pages keep their labels and annotations, and the PDF's bookmarks come under a new,
  unfolded bookmark named after the file.
- Extract, in the Pages view: the pages written as a list such as “1, 5, 10-12, 56-”, starting with the selected ones,
  into one file or one per page, in a folder chosen. A name already in the folder can be overwritten or the new file
  renamed. The pages can be deleted afterwards, with Undo. The files keep their pages as they are, with their
  annotations and the bookmarks that lead to them.
- Merge PDFs, in the main menu and on the welcome page: a list of files, added with a button or dropped on it,
  reordered by dragging and removed; protected PDFs are shown in red and left out. It can create a bookmark for each
  file and keep the files' own bookmarks. The merged document opens unsaved, and Save asks where to save it.
- Dropping several PDFs on a window, or opening several with Penfold at once, opens Merge PDFs with them.
- The form fields of added or merged pages join the document's form; a name already used gets a number (“name_2”).
- A click in an empty part of the Pages or Bookmarks list, or Esc, clears the selection.

### Changed
- Unlike 0.6, Extract no longer offers to remove bookmarks and annotations from the files: they can be removed from
  the extracted file afterwards, as wanted.

## 1.0.0-alpha.4 — 2026-11-20

Fourth preview of Penfold 1.0: the first edits. Pages can be turned, deleted and reordered, every edit can be undone,
and the PDF can be saved.

### Added
- Undo and Redo, in the document header and with Ctrl+Z and Shift+Ctrl+Z; greyed out when there is nothing to undo
  or redo.
- With pages selected in the Pages view, a bar at the bottom says how many and turns them left or right or deletes
  them (also with the Delete key). Deleting asks nothing: a notice offers to undo it. Every page cannot be deleted.
- Thumbnails can be dragged to reorder the pages, several at once if they are selected; a line shows where they will
  go, and the list scrolls while dragging near its edges.
- Save (Ctrl+S) and Save As… (Shift+Ctrl+S) in the document menu. The PDF is changed, not rebuilt: what Penfold does
  not edit is kept as it was. Page labels follow their pages, bookmarks keep their destinations, style and unfolded
  state, and the form fields of deleted pages are removed. The file is written next to the original, checked, and
  only then put in its place, so a failure never damages it.
- A “• ” in front of the title while there are unsaved changes; undoing back to the saved state removes it.
- Closing a window, quitting, opening another PDF or dropping one on the window with unsaved changes asks first: Save,
  Discard or Cancel.

### Changed
- Bookmarks, annotations, the thumbnails and Find follow the pages to their new place and turn; links and text
  selection work on turned pages.

### Fixed
- Penfold could stop now and then with a memory error while drawing pages.

## 1.0.0-alpha.3 — 2026-11-19

Third preview of Penfold 1.0: the side panel, to find your way around a PDF. Nothing can be changed or saved yet.

### Added
- Side panel, opened by itself with a PDF and shown or hidden with F9. Its edge can be dragged and its width is
  remembered; it always leaves the document room, and goes over the document in narrow windows. The main menu moves
  to the document header while the panel is hidden.
- Pages: thumbnails with their page labels and a size of their own. Ctrl and the mouse wheel over them (or Ctrl++ and
  Ctrl+− while they have the focus) make them larger or smaller, and the size is remembered; the panel shows as many
  columns as fit. Every page sits in the same cell, so an A3 looks like an A4 and landscape pages are centred. The
  page being read is marked, with a soft box over the part shown in the document.
- Bookmarks: the outline with its bold, italic and colour, unfolded as the PDF says, and Expand or Collapse All.
- Annotations: grouped by type with a count, with the page, the author (or “External”) and the text, next to a line
  in the annotation's colour; a filter chooses the types shown (Comments and Text Boxes by default, as in 0.6).
- Bookmarks and Annotations follow the reading: the section or the annotations of the page being read are marked.
- Find (Ctrl+F): a list of every match, which fills while the PDF is searched, with the sentence around each one.
  Case, accents and line breaks do not matter; Enter, Ctrl+G and Shift+Ctrl+G move between matches, highlighted on
  the pages, and Esc goes back to the previous view.
- A click on a thumbnail, a bookmark, an annotation or a match goes there.

### Changed
- The page box is narrower and selects the page when entering it, so typing replaces it.
- Large PDFs stay smooth: searching 800 pages takes a few seconds without freezing the window, and hundreds of
  annotations are listed at once.

## 1.0.0-alpha.2 — 2026-11-18

Second preview of Penfold 1.0: it works as a PDF viewer. Nothing can be changed or saved yet.

### Added
- Open a PDF with the Open button, Ctrl+O, Open With in the file manager, the command line or by dropping it on the
  window. Each PDF from the desktop opens in an empty window, or in a new one.
- Continuous scrolling and Two Pages (in pairs: 1-2, 3-4…), from the document menu (⋮).
- Zoom from 30 % to 400 % with the round floating buttons (Fit Width, Whole Page, Zoom In, Zoom Out), Ctrl++, Ctrl+−
  and Ctrl+0. It fits the width on opening and when the window gets wider or narrower. New: Ctrl and the mouse wheel
  zoom around the pointer.
- Document header with the PDF's title and file name, and the page box with the PDF's own page labels, as in
  “ix (11 of 800)”. Page Down, Page Up, Ctrl+Home, Ctrl+End, Ctrl+L and the arrow keys move around.
- Internal links go to their destination, with its height on the top third of the viewer; web links open in the
  browser.
- Select text with the mouse, also across pages (double click: a word; triple click: a line), and copy it with Ctrl+C.
- Everything in the PDF is shown as Poppler draws it, including annotations made with other programs and forms.
- Protected PDFs open with a notice and a fixed banner; PDFs that need a password are not opened, with a message.
- The window remembers its size with a document; New Window also in the dock's menu; Ctrl+W and Ctrl+Q.
- Pages are drawn in the background, only the visible ones and those near them: large PDFs scroll smoothly.

## 1.0.0-alpha.1 — 2026-11-18

First preview of Penfold 1.0, a native GNOME app (Python, GTK 4 and libadwaita) that replaces the web and Electron
version. It is incomplete on purpose: it only shows the foundations, and it cannot open PDFs yet.

### Added
- Welcome window with Open… and Merge… (both greyed out until they work), in light and dark mode.
- Main menu (☰): Keyboard Shortcuts (also Ctrl+?) and About Penfold work; Open, Merge PDFs and New Window are greyed
  out for now.
- English and Spanish.
- Entry in the applications menu, AppStream card for GNOME Software, and a Flatpak package with minimum permissions.
- Automatic checks (Ruff, mypy and pytest) and the Flatpak build on GitHub Actions.

## 0.6.0 — 2026-11-17

### Added
- Keyboard shortcuts: Ctrl+O open, Ctrl+S save, Ctrl+Shift+S save as, Ctrl+G / Ctrl+Shift+G next / previous result,
  Ctrl++ / Ctrl+− / Ctrl+0 zoom, F9 side panel, Page Down / Page Up, Ctrl+Home / Ctrl+End and Ctrl+L to move around.
  Delete deletes the selected pages or bookmarks (asking first). H and U highlight or underline the selected text (with
  nothing selected they choose the tool), and Esc goes back to the text selection tool.
- Main menu (☰) in place of the Information button, as in GNOME apps, with Keyboard Shortcuts (a window listing them,
  also opened with Ctrl+?) and About Penfold.

### Changed
- Dialogues closer to GNOME (libadwaita): Extract pages explains the page list in a line under the field instead of a
  “?” tooltip that covered it; the Save As dialogue has no “…” in its title and “Flatten the form” is a switch in a
  card; About shows the version in a pill and Website / Report an issue as rows of a card; the brief messages at the
  bottom are dark pills, like GNOME's toasts.
- The code has clearer names and a comment for every part; the code checker reports nothing.

### Fixed
- A test of the unsaved-changes question could fail now and then: it checked before the document had finished opening.

## 0.5.4 — 2026-11-17

### Fixed
- The question about unsaved changes now comes first: before choosing the file to open, and when Merge is pressed
  (before choosing the files to merge), so no work is done twice.

### Changed
- App icon in livelier colours from the GNOME palette (yellow and green sheets, blue pen), with a darker edge under
  each sheet and a thin border, so the white sheet can be seen on a white background.
- Dialogues in the style of GNOME (libadwaita), with values taken from its stylesheet: dialogue background and dimmed
  backdrop, rounded corners, 11 pt text and a larger title, borderless filled buttons, tall rounded answer buttons,
  filled text fields. Questions such as “Save changes to …?” look like GNOME’s alerts: everything centred and answers
  sharing the width. In dialogues with content, the answers keep a common width and are centred.
- The Merge list looks like a GNOME list (a card with rows), with a drag handle on each row to show that the files can
  be reordered, and an accent border while files are dragged over it.
- Checkboxes and radio buttons in the dialogues look like libadwaita’s (a thin outline; checked, the accent colour with
  a white tick or dot). The PDF form fields drawn over the page keep their own look.
- The find bar looks like a libadwaita popover with a search entry (a magnifier inside, as in GNOME’s document viewer)
  and flat buttons.
- README in English and Spanish rewritten, with new screenshots (forms and the print dialogue added) and image widths
  that adapt to the screen. The browser version is now described as a zip to download from the releases page.
- Translations are now in `js/i18n/`, one file per language (`es.js`), instead of inside the app’s code; the desktop
  app reads its few texts from the same files. Spanish looks exactly as before.

### Added
- Browser version as a zip, `penfold_<version>-web.zip`, built by `npm run dist` next to the Debian package (or alone
  with `npm run dist:web`): unzip it and open `index.html`.
- A Basque translation file to fill in (`js/i18n/eu.js`): untranslated texts are shown in Spanish, as before.
  `npm run i18n` shows what is left to translate; `js/i18n/README.md` explains how to translate or add a language.

## 0.5.3 — 2026-11-15

### Fixed
- Unsaved changes are no longer lost without warning. Penfold now knows when a document has unsaved changes (pages,
  bookmarks, forms and annotations; undoing a change by hand leaves nothing to save) and, only then, asks “Save
  changes to …?” with Cancel, Discard and Save before opening another PDF, merging, or closing the window. Closing the
  browser tab makes the browser ask.
- Desktop app: opening a PDF from the file manager no longer asks, with a system dialogue, about changes that did not
  exist.

### Changed
- Desktop app: several windows. A PDF from the file manager opens in an empty window, or in a new one, so the open
  document stays; a PDF dropped on a window opens in it. “New Window” in the dock’s menu. The title shows “•” while
  there are unsaved changes.
- The unsaved-changes question has its text centred and a red Discard button, as in GNOME apps.

## 0.5.2 — 2026-11-12

### Added
- Desktop app for Linux, built with Electron: opens PDFs from the file manager (“Open with”), from the command line or
  dropped on the window, in a single instance; “Save” writes back to the opened file; remembers the window; shows the
  document’s name in the title; no browser behaviour; no network use. Installed from a Debian package (`npm run dist`)
  with a menu entry, “Open with” for PDFs and a card for GNOME Software.
- App icon in colour (`assets/penfold.svg`, with PNG sizes from 16 to 512 px in `assets/icons/`, made by
  `npm run icons`).

### Changed
- The About dialogue shows the colour icon instead of the grey welcome-screen icon. Its credit line is now “Created by
  ibanurq, with AI assistance”, and the line “Everything happens on your computer…” is gone.
- The protected-PDF reminder in the viewer is 1.5 times bigger (48 px).

## 0.5.1 — 2026-11-12

### Security
- Every PDF is opened with `isEvalSupported: false`, the documented mitigation for CVE-2024-4367 in pdf.js 3.11
  (a crafted font could run JavaScript inside the page).

### Fixed
- Forms: in radio groups whose buttons have export values different from their options (`/Opt`), the chosen option
  is now saved. It used to be lost, with the message “1 form field(s) could not be saved”.
- Opened by double-clicking the file (`file://`), the app no longer leaves an error in the browser console when it
  loads the pdf.js worker.

### Changed
- Works offline: pdf.js 3.11.174 and pdf-lib 1.17.1 are included in `vendor/`, unchanged, instead of being loaded
  from cdnjs.
- The single HTML file is now `index.html`, `css/penfold.css` and `js/penfold.js`, cut as they were; behaviour and
  look are unchanged.

### Added
- Automatic tests with Playwright: 35 tests that drive the real app, check the saved PDFs and compare 21 reference
  screenshots pixel by pixel, with the network blocked.
- Licence file, third-party notices, README in English and Spanish, specification and working method in `docs/`.

## 0.5.0 — 2026-11-11

The starting point of this history: the whole app in a single HTML file, loading its libraries from cdnjs.

- Reading: continuous scrolling and two pages, zoom and fitting, thumbnails, find (ignores case and accents).
- Annotations: highlight, underline, strikethrough, comment, text box, rectangle, circle and arrow, all saved with
  their own appearance (`/AP`); annotations from other programs shown read-only and kept on save.
- Side panel with Pages, Bookmarks and Annotations; page reordering, rotation, deletion, blank pages and pages from
  another PDF; bookmark editing.
- Merge, extract pages, print with a choice of annotations.
- Forms (AcroForm): kept on save, filled in on screen, saved editable, optionally flattened.
- Protected PDFs detected: notice and fixed reminder; save, print and extract disabled.
- English and Spanish interface; light and dark mode; About dialogue.
