# Changelog

All notable changes to Penfold are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Version numbers: the second number goes up when features are added (0.5 → 0.6); the third one (0.6.1, 0.6.2…) only
for visual polish, translations and bug fixes.

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
