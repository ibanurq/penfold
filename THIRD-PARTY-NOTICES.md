# Third-party notices

Penfold is licensed under the GNU General Public Licence v3.0 (see `LICENSE`). It includes or derives from the
following third-party works, each under its own licence, which is compatible with the GPL-3.0.

## pdf.js 3.11.174

- Project: https://github.com/mozilla/pdf.js — Copyright Mozilla Foundation and contributors.
- Licence: Apache License 2.0. Full text: `vendor/pdf.js-3.11.174/LICENSE`.
- Included unchanged in `vendor/pdf.js-3.11.174/` (`pdf.min.js`, `pdf.worker.min.js`, `pdf_viewer.min.css`).

## pdf-lib 1.17.1

- Project: https://github.com/Hopding/pdf-lib — Copyright (c) 2019 Andrew Dillon.
- Licence: MIT. Full text: `vendor/pdf-lib-1.17.1/LICENSE.md`.
- Included unchanged in `vendor/pdf-lib-1.17.1/pdf-lib.min.js`.

## Lucide icons

- Project: https://lucide.dev/ — the toolbar and panel icons are Lucide drawings written inline as SVG in
  `index.html` and `js/penfold.js` (some slightly adapted, for example the comment icon filled with the annotation’s
  colour and the yellow warning sign). The app icon (`assets/penfold.svg`) and the welcome-screen icon are Penfold’s own.
- Licence text, as published by Lucide:

```
ISC License

Copyright (c) 2026 Lucide Icons and Contributors

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
```

Some Lucide icons are derived from the Feather project (Lucide lists them in its licence; among those used here:
circle, square, search, italic, info, sidebar, trash-2, download, x), under this licence:

```
The MIT License (MIT) (for the icons listed above)

Copyright (c) 2013-present Cole Bemis

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Development tools (not distributed with the app)

The tests use Playwright (Apache-2.0) and the npm packages `pdfjs-dist` and `pdf-lib`, installed with `npm install`
into `node_modules/`, which is not part of the repository.
