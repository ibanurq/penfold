# Translations

Penfold is written in English; each other language has one file here. The Spanish one, `es.js`, is complete and is the
model for the others.

| File | Language | State |
|---|---|---|
| `es.js` | Spanish (castellano) | complete |
| `eu.js` | Basque (euskara) | to be filled in |

## Translating

Each line of a file is a text in English, as it appears in the code, and its translation:

```js
'Open PDF': 'Abrir PDF',
'Page {n}': 'Página {n}',
```

- Write the translation between the second pair of quotes. Keep `{name}` placeholders exactly as they are.
- A quote inside a translation is written `\'`.
- An empty translation (`''`) is not used: the text is shown in the language’s fallback (Spanish for Basque, Catalan
  and Galician) or, failing that, in English. So a file can be translated little by little.
- A few keys start with a context, such as `'page\u0004Delete'`: the same English word with a different translation in
  that place (here, deleting pages).

To see how far a translation has got and which texts are left:

```bash
npm run i18n -- eu
```

## Adding a language

1. Copy `eu.js` (or `es.js`) to `<code>.js`, using the language’s two-letter code (`fr`, `ca`, `gl`…), change the
   code in its last line of the header (`PENFOLD_LANGS.<code>`) and translate.
2. Load it in `index.html`, next to the others, before `js/penfold.js`.
3. Penfold uses it when the system (or the browser) prefers that language; `?lang=<code>` forces it in the browser.
4. Outside these files, two places have their own short texts for each language: the menu entry (`GenericName`,
   `Comment` and `Keywords` in `electron-builder.yml`) and the software centre card (`build/penfold.metainfo.xml`).

The tests check that every file here is loaded, that each one has exactly the texts of `es.js` (translated or
empty), and that every text is still used by Penfold. When a text in the app changes, it changes in every file.
