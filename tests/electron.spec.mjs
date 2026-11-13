// The desktop app (Electron): opening PDFs given by the desktop or dropped on the window, saving back, a single
// instance, the remembered window, the language, the title, and none of the browser's behaviour or network use.
// These tests open real windows for a few seconds. Each one uses its own settings folder and copies of the test PDFs.
import { test, expect, _electron as electron } from '@playwright/test';
import { mkdtempSync, copyFileSync, readFileSync, writeFileSync, statSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { PDFDocument, PDFName, PDFArray } from 'pdf-lib';
import { ROOT, FIX, waitRendered } from './helpers.mjs';

// By default the app runs from the project folder with the development Electron. With PENFOLD_APP set to a built
// app (e.g. dist/linux-unpacked/penfold, made by npm run dist) the same tests check the packaged app instead.
const PACKAGED = process.env.PENFOLD_APP;
const ELECTRON = PACKAGED || createRequire(import.meta.url)('electron'); // path of the program to start
const APP_ARGS = PACKAGED ? [] : [ROOT];
const EN = { LANG: 'en_GB.UTF-8', LANGUAGE: 'en_GB' };

// Starts the app. `config` is its settings folder (a new one unless given, so a test can start it twice).
async function launch({ files = [], config, env = EN } = {}) {
  config = config || join(mkdtempSync(join(tmpdir(), 'penfold-test-')), 'config');
  const app = await electron.launch({
    ...(PACKAGED ? { executablePath: PACKAGED } : {}),
    args: [...APP_ARGS, ...files],
    cwd: ROOT,
    env: { ...process.env, ...env, PENFOLD_USER_DATA: config },
  });
  const win = await app.firstWindow();
  await win.waitForFunction(() => window.pdfjsLib && window.PDFLib);
  return { app, win, config };
}
const tempCopy = (name) => {
  const f = join(mkdtempSync(join(tmpdir(), 'penfold-pdf-')), name);
  copyFileSync(join(FIX, name), f);
  return f;
};
const title = (app) => app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].getTitle());
const loaded = (win, n) => win.waitForFunction((n) => pages.length === n && pages.every((p) => p.loaded), n);
// Answers the next native question (“Open …? The open document will be closed…”) with the given button
const answerDialog = (app, response) =>
  app.evaluate(({ dialog }, response) => {
    globalThis.__asked = [];
    dialog.showMessageBox = async (w, o) => (globalThis.__asked.push(o.message), { response });
  }, response);

// Drops a file from the disk on the viewer, as from the file manager. (It is picked with a hidden file input so that it
// has a real path, which is what the desktop layer needs.)
async function dropFile(win, file) {
  await win.evaluate(() => {
    if (document.getElementById('__drop')) return;
    const i = document.createElement('input');
    i.type = 'file';
    i.id = '__drop';
    i.style.display = 'none';
    document.body.appendChild(i);
  });
  await win.setInputFiles('#__drop', file);
  await win.evaluate(() => {
    const dt = new DataTransfer();
    dt.items.add(document.getElementById('__drop').files[0]);
    const v = document.getElementById('view');
    v.dispatchEvent(new DragEvent('dragover', { dataTransfer: dt, bubbles: true, cancelable: true }));
    v.dispatchEvent(new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true }));
  });
}

test('a PDF given on the command line opens, the title shows it, and Save writes back to it', async () => {
  const pdf = tempCopy('text.pdf');
  const { app, win } = await launch({ files: [pdf] });
  await loaded(win, 3);
  await waitRendered(win);
  await expect.poll(() => title(app)).toBe('text.pdf — Penfold');
  // Draw a rectangle and save over the same file
  await win.click('#bar .ib[data-t="sq"]');
  const b = await win.locator('#view .page').first().boundingBox();
  await win.mouse.move(b.x + 100, b.y + 300);
  await win.mouse.down();
  await win.mouse.move(b.x + 250, b.y + 380);
  await win.mouse.up();
  const before = statSync(pdf).size;
  await win.click('#bSave');
  await expect(win.locator('#dlg2')).toContainText('Do you want to overwrite “text.pdf”?');
  await win.click('#dlg2 button.on');
  await expect(win.locator('#msg')).toHaveText('Saved ✔');
  expect(statSync(pdf).size).not.toBe(before);
  const saved = await PDFDocument.load(readFileSync(pdf));
  const annots = saved.getPage(0).node.lookup(PDFName.of('Annots'), PDFArray).asArray();
  expect(annots.map((r) => saved.context.lookup(r).get(PDFName.of('Subtype')).toString())).toEqual(['/Square']);
  await app.close();
});

test('no menu, links go to the default browser, and browser shortcuts do nothing', async () => {
  const { app, win } = await launch();
  expect(await app.evaluate(({ Menu }) => Menu.getApplicationMenu())).toBeNull();
  await expect.poll(() => title(app)).toBe('Penfold');
  // Reload (Ctrl+R, F5) must not reload: a marker set in the page survives
  await win.evaluate(() => (window.__marker = 1));
  await win.keyboard.press('Control+r');
  await win.keyboard.press('F5');
  await win.waitForTimeout(500);
  expect(await win.evaluate(() => window.__marker)).toBe(1);
  // The Website link is handed to the system, and no new window appears
  await app.evaluate(({ shell }) => {
    globalThis.__opened = [];
    shell.openExternal = async (u) => globalThis.__opened.push(u);
  });
  await win.click('#bInfo');
  await win.click('#dlg a.web');
  await expect.poll(() => app.evaluate(() => globalThis.__opened)).toEqual(['https://github.com/ibanurq/penfold']);
  expect(app.windows()).toHaveLength(1);
  await app.close();
});

test('a PDF dropped on the window opens, after asking when a document is already open', async () => {
  const { app, win } = await launch({ files: [tempCopy('text.pdf')] });
  await loaded(win, 3);
  await answerDialog(app, 1); // “Open”
  await dropFile(win, tempCopy('outline.pdf'));
  await loaded(win, 4);
  expect(await app.evaluate(() => globalThis.__asked)).toEqual(['Open “outline.pdf”?']);
  await expect.poll(() => title(app)).toBe('outline.pdf — Penfold');
  // Answering Cancel keeps the open document
  await answerDialog(app, 0);
  await dropFile(win, tempCopy('form.pdf'));
  await expect.poll(() => app.evaluate(() => globalThis.__asked)).toEqual(['Open “form.pdf”?']);
  await win.waitForTimeout(500);
  expect(await win.evaluate(() => pages.length)).toBe(4);
  await app.close();
});

test('files dropped on the Merge list are added to it, not opened', async () => {
  const { app, win } = await launch();
  await win.click('#bMerge');
  await win.evaluate(() => {
    const dt = new DataTransfer();
    for (const n of ['a.pdf', 'b.pdf']) dt.items.add(new File(['%PDF-1.4'], n, { type: 'application/pdf' }));
    document
      .getElementById('mList')
      .dispatchEvent(new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true }));
  });
  // The invented files are not valid PDFs: the Merge dialogue reports them, which proves it received the drop
  await expect(win.locator('#msg')).toContainText('Could not read');
  await expect(win.locator('#dlg')).toBeVisible();
  expect(await win.evaluate(() => pages.length)).toBe(0);
  await app.close();
});

test('a second launch hands its PDF to the open window and exits', async () => {
  const { app, win, config } = await launch();
  // Given as a file:// address, as the menu entry (“%U”) does
  const second = spawn(ELECTRON, [...APP_ARGS, pathToFileURL(tempCopy('outline.pdf')).href], {
    cwd: ROOT,
    env: { ...process.env, ...EN, PENFOLD_USER_DATA: config },
  });
  const code = await new Promise((r) => second.on('exit', r));
  expect(code).toBe(0);
  await loaded(win, 4);
  expect(app.windows()).toHaveLength(1);
  await expect.poll(() => title(app)).toBe('outline.pdf — Penfold');
  await app.close();
});

test('the window size is remembered between sessions', async () => {
  // On closing, the window's size is written to the settings folder. (The size itself is not changed from the test:
  // on Wayland the desktop may ignore a program's own resize requests.)
  const first = await launch();
  const bounds = await first.app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].getNormalBounds());
  await first.app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].close());
  await first.app.waitForEvent('close');
  const stateFile = join(first.config, 'window-state.json');
  const saved = JSON.parse(readFileSync(stateFile, 'utf8'));
  expect([saved.width, saved.height, saved.maximized]).toEqual([bounds.width, bounds.height, false]);
  // On opening, the window takes the size that was written
  writeFileSync(stateFile, JSON.stringify({ width: 1000, height: 640, maximized: false }));
  const again = await launch({ config: first.config });
  const size = await again.app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].getSize());
  expect(size).toEqual([1000, 640]);
  await again.app.close();
});

test('follows the system language (Spanish)', async () => {
  const { app, win } = await launch({ env: { LANG: 'es_ES.UTF-8', LANGUAGE: 'es_ES' } });
  await expect(win.locator('#empty h2')).toHaveText('Comenzar a trabajar');
  await app.close();
});

test('opening and painting a PDF makes no network request and leaves no console errors', async () => {
  const { app, win } = await launch();
  const logs = [];
  win.on('console', (m) => ['error', 'warning'].includes(m.type()) && logs.push(m.text()));
  win.on('pageerror', (e) => logs.push(e.message));
  // Every request that would leave the computer is recorded and cancelled from now on, and the page is loaded again
  await app.evaluate(({ session }) => {
    globalThis.__requests = [];
    session.defaultSession.webRequest.onBeforeRequest((d, cb) => {
      const external = !/^(file|blob|data|devtools|chrome-extension|chrome):/.test(d.url);
      if (external) globalThis.__requests.push(d.url);
      cb({ cancel: external });
    });
  });
  await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].webContents.reload());
  await win.waitForFunction(() => window.pdfjsLib && window.PDFLib && document.getElementById('empty'));
  await answerDialog(app, 1);
  await dropFile(win, tempCopy('form.pdf'));
  await loaded(win, 1);
  await waitRendered(win);
  expect(await app.evaluate(() => globalThis.__requests)).toEqual([]);
  expect(logs).toEqual([]);
  // Self-check: a deliberate request is seen by the recorder (and cancelled), so the empty list above means something
  await win.evaluate(() => fetch('https://penfold.invalid/check').catch(() => {}));
  expect(await app.evaluate(() => globalThis.__requests)).toEqual(['https://penfold.invalid/check']);
  await app.close();
});
