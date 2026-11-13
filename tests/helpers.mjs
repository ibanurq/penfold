// Shared helpers for the tests.
// The app is served from a fake address (https://penfold.test/) straight from the project folder, so it runs in a
// "secure context" like a real site. Any other request (internet, or a file missing from the project) is blocked and
// recorded, and expectNoExternalRequests() fails: the app must work offline with what is in the project folder.
import { expect } from '@playwright/test';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, join, normalize, extname } from 'node:path';

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
export const FIX = join(ROOT, 'tests', 'fixtures');
// The app's version, from package.json (it must match the tab title and the About dialog)
export const VERSION = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8')).version;
// Page under test (relative to the project folder)
export const APP_PAGE = process.env.PENFOLD_PAGE || 'index.html';
const ORIGIN = 'https://penfold.test/';
const TYPES = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.mjs': 'text/javascript',
  '.css': 'text/css',
  '.pdf': 'application/pdf',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.json': 'application/json',
  '.gif': 'image/gif',
};

// Fake file pickers (the real ones open system windows). Opened files come from a queue; saved files are kept in memory.
function initStubs() {
  const fromB64 = (b) => Uint8Array.from(atob(b), (c) => c.charCodeAt(0));
  const toB64 = (u) => {
    let s = '';
    for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000));
    return btoa(s);
  };
  const T = (window.__pt = { open: [], saved: [], files: {} });
  const bytesOf = async (d) =>
    d instanceof Blob
      ? new Uint8Array(await d.arrayBuffer())
      : d instanceof ArrayBuffer
        ? new Uint8Array(d)
        : new Uint8Array(d.buffer || d);
  const fileHandle = (name, file) => ({
    kind: 'file',
    name,
    getFile: async () =>
      file || new File([T.files[name] ? fromB64(T.files[name]) : new Uint8Array()], name, { type: 'application/pdf' }),
    createWritable: async () => {
      const parts = [];
      return {
        write: async (d) => {
          parts.push(await bytesOf(d));
        },
        close: async () => {
          const all = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
          let o = 0;
          parts.forEach((p) => {
            all.set(p, o);
            o += p.length;
          });
          T.files[name] = toB64(all);
          T.saved.push({ name, b64: T.files[name] });
        },
      };
    },
  });
  T.queue = (name, b64) => {
    T.open.push(new File([fromB64(b64)], name, { type: 'application/pdf' }));
  };
  T.toB64 = toB64;
  T.fromB64 = fromB64;
  window.showOpenFilePicker = async () => {
    const f = T.open.shift();
    if (!f) throw Object.assign(new Error('no file'), { name: 'AbortError' });
    return [fileHandle(f.name, f)];
  };
  window.showSaveFilePicker = async (o) => [fileHandle((o && o.suggestedName) || 'saved.pdf')][0];
  window.showDirectoryPicker = async () => ({
    kind: 'directory',
    name: 'out',
    getFileHandle: async (name, o) => {
      if (!(o && o.create) && !(name in T.files))
        throw Object.assign(new Error('not found'), { name: 'NotFoundError' });
      return fileHandle(name);
    },
  });
}

export async function openApp(page, { lang = 'en', scheme = 'light' } = {}) {
  const blocked = [];
  page.__blocked = blocked;
  await page.emulateMedia({ colorScheme: scheme });
  await page.route('**/*', async (route) => {
    const url = route.request().url();
    if (url.startsWith(ORIGIN)) {
      const rel = decodeURIComponent(new URL(url).pathname).replace(/^\/+/, ''),
        file = normalize(join(ROOT, rel));
      if (file.startsWith(ROOT) && existsSync(file))
        return route.fulfill({
          path: file,
          headers: { 'Content-Type': TYPES[extname(file)] || 'application/octet-stream' },
        });
      blocked.push('missing: ' + rel);
      return route.fulfill({ status: 404, body: 'not found' });
    }
    if (url.startsWith('blob:') || url.startsWith('data:')) return route.continue();
    blocked.push(url);
    return route.abort();
  });
  await page.addInitScript(initStubs);
  await page.goto(ORIGIN + APP_PAGE + '?lang=' + lang);
  await page.waitForFunction(() => window.pdfjsLib && window.PDFLib);
  return page;
}

// The same app opened by double-clicking the file (file://), with the network cut off completely
export async function openAppFile(page, { lang = 'en', scheme = 'light' } = {}) {
  const blocked = [];
  page.__blocked = blocked;
  await page.emulateMedia({ colorScheme: scheme });
  await page.context().route('**/*', (route) => {
    const url = route.request().url();
    if (/^(blob|data|file):/.test(url)) return route.continue();
    blocked.push(url);
    return route.abort();
  });
  await page.addInitScript(initStubs);
  await page.goto(pathToFileURL(join(ROOT, APP_PAGE)).href + '?lang=' + lang);
  await page.waitForFunction(() => window.pdfjsLib && window.PDFLib);
  return page;
}

// No request left the app, and no file was missing from the project folder
export const expectNoExternalRequests = (page) => expect(page.__blocked, 'unexpected network requests').toEqual([]);

export const fixtureB64 = (name) => readFileSync(join(FIX, name)).toString('base64');

// Waits until the visible pages are painted (canvas, text layer, annotations) and the visible thumbnails are loaded
export async function waitRendered(page) {
  await page.waitForFunction(() => {
    const v = document.querySelector('#view'),
      vr = v.getBoundingClientRect();
    const shown = [...v.querySelectorAll('.page')].filter(
      (e) => e.style.display != 'none' && ((r) => r.bottom > vr.top && r.top < vr.bottom)(e.getBoundingClientRect()),
    );
    if (!shown.length) return false;
    if (!shown.every((e) => e._ov && e.querySelector('canvas') && e.querySelector('.textLayer span'))) return false;
    const sb = document.querySelector('#sbody'),
      sr = sb.getBoundingClientRect();
    const ths = [...sb.querySelectorAll('.th img')].filter((i) =>
      ((r) => r.bottom > sr.top && r.top < sr.bottom)(i.getBoundingClientRect()),
    );
    if (!ths.every((i) => i.complete && i.naturalWidth > 0)) return false;
    return annBusy === 0;
  });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
}

// Opens a fixture with “Open PDF” (the file picker is replaced by the queue)
export async function openPdf(page, name) {
  await openBytes(page, name, fixtureB64(name));
}
// Same, with any PDF given as base64 (e.g. one the app has just saved). Waits for the new document (Open replaces the docs array)
export async function openBytes(page, name, b64) {
  await page.evaluate(
    ([n, b]) => {
      window.__pt.queue(n, b);
      window.__pt.oldDocs = docs;
    },
    [name, b64],
  );
  await page.click('#bOpen');
  await page.waitForFunction(() => docs !== window.__pt.oldDocs && pages.length && pages.every((p) => p.loaded));
  await expect(page.locator('#view .page').first()).toBeVisible();
  await waitRendered(page);
}

// Drops fixture files on the Merge dialog's list (like dragging them from the file manager)
export async function dropOnMergeList(page, names) {
  await page.evaluate(
    (files) => {
      const dt = new DataTransfer();
      files.forEach(([n, b]) => dt.items.add(new File([window.__pt.fromB64(b)], n, { type: 'application/pdf' })));
      document
        .querySelector('#mList')
        .dispatchEvent(new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true }));
    },
    names.map((n) => [n, fixtureB64(n)]),
  );
}

// Files written by the app (Save, Save As, Extract), in order
export const savedFiles = (page) => page.evaluate(() => window.__pt.saved.map((s) => ({ name: s.name, b64: s.b64 })));
export async function waitSaved(page, n = 1) {
  await page.waitForFunction((k) => window.__pt.saved.length >= k, n);
  return savedFiles(page);
}

// Reads a PDF (base64) with the app's own pdf.js and pdf-lib: pages, annotations, outline and form fields
export function inspectPdf(page, b64) {
  return page.evaluate(async (b64) => {
    const bytes = window.__pt.fromB64(b64),
      pdf = await pdfjsLib.getDocument({ data: bytes.slice() }).promise,
      out = { pages: [], outline: [] };
    for (let i = 1; i <= pdf.numPages; i++) {
      const pg = await pdf.getPage(i),
        vp = pg.getViewport({ scale: 1 });
      const an = (await pg.getAnnotations()).map((a) => ({
        subtype: a.subtype,
        author: a.titleObj ? a.titleObj.str : '',
        contents: a.contentsObj ? a.contentsObj.str : '',
        hasAppearance: !!a.hasAppearance,
        fieldName: a.fieldName || null,
        fieldValue: a.fieldValue ?? null,
      }));
      out.pages.push({ width: Math.round(vp.width), height: Math.round(vp.height), rotate: pg.rotate, annots: an });
    }
    const walk = async (l) =>
      Promise.all(
        (l || []).map(async (it) => ({
          title: it.title,
          bold: !!it.bold,
          italic: !!it.italic,
          items: await walk(it.items),
        })),
      );
    out.outline = await walk(await pdf.getOutline());
    const doc = await PDFLib.PDFDocument.load(bytes, { ignoreEncryption: true });
    out.hasAcroForm = doc.catalog.has(PDFLib.PDFName.of('AcroForm'));
    out.fields = {};
    if (out.hasAcroForm)
      doc
        .getForm()
        .getFields()
        .forEach((f) => {
          const n = f.getName();
          out.fields[n] =
            f instanceof PDFLib.PDFTextField
              ? (f.getText() ?? '')
              : f instanceof PDFLib.PDFCheckBox
                ? f.isChecked()
                : f instanceof PDFLib.PDFRadioGroup
                  ? (f.getSelected() ?? null)
                  : f instanceof PDFLib.PDFDropdown
                    ? f.getSelected()
                    : null;
        });
    // Every annotation written by Penfold must carry its own drawing (/AP /N)
    out.penfoldWithoutAP = 0;
    doc.getPages().forEach((p) => {
      const a = p.node.lookupMaybe(PDFLib.PDFName.of('Annots'), PDFLib.PDFArray);
      if (!a) return;
      for (let i = 0; i < a.size(); i++) {
        const d = a.lookup(i);
        const t = d.get(PDFLib.PDFName.of('T'));
        if (t && t.decodeText && t.decodeText() === 'Penfold') {
          const ap = d.lookupMaybe(PDFLib.PDFName.of('AP'), PDFLib.PDFDict);
          if (!ap || !ap.get(PDFLib.PDFName.of('N'))) out.penfoldWithoutAP++;
        }
      }
    });
    return out;
  }, b64);
}

// Clicks a toolbar button found by its (English) tooltip
export const tool = (page, t) => page.click(`#bar .ib[data-t="${t}"]`);

// Screenshot options: the brief messages at the bottom (#msg) depend on timing, so they are hidden in the images
export const SHOT = { stylePath: join(ROOT, 'tests', 'screenshot.css') };
