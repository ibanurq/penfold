// Reads Penfold's translations (js/i18n/<code>.js, the same files the page loads) outside the page: for the desktop
// app's own few texts, and for the tools and tests that check the translations.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const DIR = path.join(__dirname, '..', 'js', 'i18n');
// Languages without a translation of a text show it in another language before English (same rule as js/penfold.js)
const FALLBACK = { eu: 'es', ca: 'es', gl: 'es' };

// { code: { 'English text': 'translation' } } for every file in js/i18n/
function loadLangs() {
  const ctx = vm.createContext({ window: {} });
  for (const f of fs
    .readdirSync(DIR)
    .filter((f) => f.endsWith('.js'))
    .sort())
    vm.runInContext(fs.readFileSync(path.join(DIR, f), 'utf8'), ctx, { filename: f });
  return ctx.window.PENFOLD_LANGS || {};
}

module.exports = { DIR, FALLBACK, loadLangs };
