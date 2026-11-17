# Working with an AI assistant

Penfold is developed by a person who does not write code, together with an AI coding assistant. This document
describes the working method, so that anyone can reproduce it with an AI assistant of their choice.

## Starting a session

Give the assistant this repository and ask it to read, in this order:

1. this document;
2. [specification.md](specification.md), which describes the app as it is;
3. the code (`index.html`, `css/penfold.css`, `js/penfold.js`).

Then say what you want to do. The code is the source of truth: if the specification disagrees with it, the code wins,
and the specification should be corrected.

## Rules of conversation

- **Language:** the person and the assistant talk in Spanish. **Everything inside the app is British English** (interface
  text, comments, console messages); translations live only in the language files in `js/i18n/` (see the specification, “Languages”).
  The public documentation is in English, with a Spanish README.
- **Explain first.** Before running a command or changing a file, the assistant explains in plain words what it will
  do and why. The person is not expected to know git, npm or programming terms.
- **Only what is asked, and only what is needed.** No other part of the code is touched.
- **Doubts are asked before programming, one question at a time.** When there are several options, the assistant
  explains their advantages and limits and recommends one.
- **“Don’t program”, “don’t do anything” or “let’s leave it”** mean: talk about options only, do not touch the code.
- **No half implementations.** If something asked for is not possible or does not fit the PDF format, the assistant
  says so, explains why and carries on with the rest.
- **Phases.** Big changes are split into phases: first the essentials, then see how they work in practice. After each
  phase the person checks the result in their own PDF viewers and only with their approval does the next one start.

## Safety net: automatic tests

Every change must keep the app working and looking exactly the same, except for what was asked for. That is checked
automatically, not by eye:

- `npm test` runs the Playwright tests (see [tests/README.md](../tests/README.md)): they drive the real app in a
  headless Chromium, open invented PDFs, use every feature, read back the saved PDFs with pdf.js and pdf-lib, and
  compare reference screenshots **pixel by pixel**. Every network request is blocked.
- **Before** a change the tests must pass; **after** it, too. A screenshot that changes is a failure, unless the change
  was intended: then the assistant shows the difference image, the person agrees, and only that screenshot is
  updated (`npm run test:update`, or better, only for the affected test).
- A new feature or a bug fix comes with its test. A bug found by the tests but not yet fixed can be recorded as an
  expected failure (`test.fail`) so it is not forgotten.
- Techniques that proved useful:
  - File pickers are replaced by in-memory fakes (`window.showOpenFilePicker` returns a `File`; saved files are kept
    and read back). Merge is tested by dispatching a `drop` event with a `DataTransfer` on `#mList`.
  - The app’s global state (`docs`, `pages`, `currentPage`, `bookmarks`) can be read from the test to check the result.
  - Protected test PDFs are made with `qpdf --encrypt` (with and without `--object-streams=generate`, which behave
    differently).
  - Reference screenshots depend on the installed fonts (Cantarell) and on the browser version, so they are only valid
    on the machine where they were made.

## Code conventions

- **Formatting:** all of Penfold’s own code (HTML, CSS, JavaScript, tests, configuration) is formatted with
  [Prettier](https://prettier.io/) (`.prettierrc.json`: 120 columns, single quotes, semicolons). Run `npm run format`
  after every change; `npm run format:check` says whether anything is left. Third-party code in `vendor/` is never
  formatted. After formatting JavaScript, `node tests/same-code.mjs <old> <new>` can prove that only the layout changed.
- **Lint:** `npm run lint` runs [ESLint](https://eslint.org/) to report possible mistakes. Its findings are reviewed
  with the person; nothing is changed automatically.
- Plain JavaScript in a classic script, no build step, no framework, no ES modules (they do not load from `file://`).
- The app must work offline: any library goes into `vendor/`, unchanged, in a folder named with its version, with its
  licence and its checksum in `vendor/README.md`. Only free licences compatible with the GPL-3.0.
- No native browser dialogues (`alert`, `confirm`, `prompt`): use `confirmDialog`, `promptDialog`, `choiceDialog` and
  `showMessage`.
- New text: in English in the code (through `_t` when JavaScript builds it), with its pair in every language file in
  `js/i18n/` (translated in `es.js`, empty in the others until someone translates it; see `js/i18n/README.md`).
- New toolbar controls that need a PDF go into the `NEED_PDF` list.
- Icons from Lucide, in the same style as the rest (stroke 1.8, round caps and joins, 20 px in the toolbar and 18 px
  in the panel bars).
- Annotations are always saved with their own appearance (`/AP`), and text in PDF dictionaries with
  `PDFHexString.fromText`.

## Versions and git

- Features are frozen in 0.5: the third number (0.5.1, 0.5.2…) only goes up for visual polish and bug fixes. A new
  version changes `APP.version` in `js/penfold.js`, the `<title>` in `index.html` and `version` in `package.json`, and
  gets an entry in `CHANGELOG.md`.
- Each change is a separate git commit with a clear message, so it can be reviewed and undone on its own.
- **The assistant never publishes.** It does not run `git push`; when something has to go to GitHub, it gives the
  person the folder, a command to review which commits will be sent, and the exact command with a plain explanation,
  and the person runs it.
- Private notes (internal research, ideas not yet decided) are kept outside the repository, in a folder ignored by git.
