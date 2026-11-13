# Tests

Automatic tests that drive the real app in a headless Chromium with [Playwright](https://playwright.dev/).
They check what the app does (opening, annotating, saving, pages, bookmarks, merge, extract, find, print, forms,
protected PDFs) and how it looks: every screenshot must match the reference images in `screenshots/` pixel for pixel.

## Running them

```bash
npm install                      # once: Playwright and the libraries (exact versions)
npx playwright install chromium  # once: the browser used by the tests
npm test                         # run every test
npx playwright show-report       # see the results, with images of any difference
```

## How they work

- `helpers.mjs` serves the app from a fake address (`https://penfold.test/`) straight from the project folder.
  Any other request (internet, or a file missing from the folder) is blocked and makes the test fail, so the app
  must work offline with its own files (`vendor/`).
- `offline.spec.mjs` also opens the HTML file directly (`file://`, as with a double click) with the network cut off.
- `electron.spec.mjs` starts the desktop app (Electron) and opens real windows for a few seconds; each test uses its
  own settings folder (`PENFOLD_USER_DATA`) and copies of the test PDFs.
- The system file pickers are replaced by in-memory fakes: opened files come from `fixtures/`, saved files are kept
  so the test can read them back with pdf.js and pdf-lib.
- `fixtures/` holds invented PDFs, built by `make-fixtures.mjs` (`npm run fixtures`, needs `qpdf`).
- `PENFOLD_PAGE` chooses the page under test (default: `index.html`).

## When a screenshot changes on purpose

Only after checking the new look by hand: `npm run test:update` rewrites the reference images.

Screenshots depend on the fonts installed (Cantarell) and on the browser version, so the reference images are
only valid on the machine where they were made.
