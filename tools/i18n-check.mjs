// Shows how far each translation in js/i18n/ has got, compared with the complete Spanish one (es.js).
// Run with: npm run i18n          (every language)
//           npm run i18n -- eu    (only Basque)
// It lists the texts still to translate. It fails (exit code 1) if a file has texts that Spanish does not have, or
// lacks some of them altogether: then the file should be brought in line with es.js.
import { createRequire } from 'node:module';

const { loadLangs } = createRequire(import.meta.url)('../electron/i18n.js');
const langs = loadLangs(),
  ref = langs.es,
  refKeys = Object.keys(ref),
  show = (k) => k.split('\u0004').pop();
const wanted = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(langs).filter((l) => l !== 'es');
let bad = false;
for (const code of wanted) {
  const d = langs[code];
  if (!d) {
    console.log(`${code}: there is no file js/i18n/${code}.js`);
    bad = true;
    continue;
  }
  const missing = refKeys.filter((k) => !Object.prototype.hasOwnProperty.call(d, k)),
    extra = Object.keys(d).filter((k) => !Object.prototype.hasOwnProperty.call(ref, k)),
    empty = refKeys.filter((k) => d[k] === ''),
    done = refKeys.length - missing.length - empty.length;
  console.log(`${code}: ${done} of ${refKeys.length} texts translated`);
  if (empty.length)
    console.log(`  still to translate (${empty.length}):\n` + empty.map((k) => '    ' + show(k)).join('\n'));
  if (missing.length) {
    bad = true;
    console.log(`  missing from the file (${missing.length}):\n` + missing.map((k) => '    ' + show(k)).join('\n'));
  }
  if (extra.length) {
    bad = true;
    console.log(`  not used by Penfold (${extra.length}):\n` + extra.map((k) => '    ' + show(k)).join('\n'));
  }
}
process.exit(bad ? 1 : 0);
