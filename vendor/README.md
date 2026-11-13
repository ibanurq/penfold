# Third-party libraries

Penfold works offline: the libraries it needs are included here unchanged, exactly as published.
Each folder name carries the version, so an upgrade is always a visible, deliberate change.

| Library | Version | Licence | Used for |
|---|---|---|---|
| [pdf.js](https://github.com/mozilla/pdf.js) | 3.11.174 | Apache-2.0 (`pdf.js-3.11.174/LICENSE`) | Reading and painting PDFs, text layer |
| [pdf-lib](https://github.com/Hopding/pdf-lib) | 1.17.1 | MIT (`pdf-lib-1.17.1/LICENSE.md`) | Writing PDFs (save, merge, extract, forms) |

The icons are [Lucide](https://lucide.dev/) drawings (ISC licence) written inline in the HTML; they are not files here.

## Origin and checksums

The files were downloaded from cdnjs, the same addresses the app used before it worked offline
(`https://cdnjs.cloudflare.com/ajax/libs/<library>/<version>/<file>`). The JavaScript files are byte-for-byte
identical to the ones in the npm packages `pdfjs-dist@3.11.174` and `pdf-lib@1.17.1`. The licence files come from
those npm packages.

```
5b5799e6f8c680663207ac5b42ee14eed2a406fa7af48f50c154f0c0b1566946  pdf.js-3.11.174/pdf.min.js
feabdf309770ed24bba31a5467836cdc8cf639c705af27d52b585b041bb8527b  pdf.js-3.11.174/pdf.worker.min.js
0f2f7750328ec786c9588f83f1227c4e8862d1fe9b650f2bb0ca46d8c30f577c  pdf.js-3.11.174/pdf_viewer.min.css
0f9a5cad07941f0826586c94e089d89b918c46e5c17cf2d5a3c6f666e3bc694f  pdf-lib-1.17.1/pdf-lib.min.js
```

To check them: `cd vendor && sha256sum -c` with the lines above.

## Notes

- `pdf_viewer.min.css` mentions three images (`images/…`) used only by parts of pdf.js's viewer that Penfold does
  not use (alt-text editor, loading spinner). They are never requested, so they are not included.
- pdf.js 3.11.174 is affected by CVE-2024-4367 (arbitrary JavaScript in a crafted PDF when `isEvalSupported` is on).
  The known mitigation, without upgrading, is to open documents with `isEvalSupported: false`.
