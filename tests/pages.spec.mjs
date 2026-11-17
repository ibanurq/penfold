// Pages panel (rotate, delete, reorder, add), bookmarks, merge, extract, find and print
import { test, expect } from '@playwright/test';
import { join } from 'node:path';
import {
  openApp,
  openPdf,
  waitRendered,
  waitSaved,
  inspectPdf,
  dropOnMergeList,
  FIX,
  SHOT,
  expectNoExternalRequests,
} from './helpers.mjs';

// Every test: nothing may come from the network, and no file may be missing from the project folder
test.afterEach(async ({ page }) => expectNoExternalRequests(page));

const pagesBtn = (page, title) => page.click(`#sbody .sbar .ib[title="${title}"]`);
const idxs = (page) => page.evaluate(() => pages.map((p) => p.doc + ':' + p.idx));

test('rotate, delete and reorder pages, then save', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await expect(page.locator('#sbody .sbar .ib[title="Delete page"]')).toBeDisabled();
  await page.locator('#sbody .th').nth(0).click();
  await pagesBtn(page, 'Rotate 90° clockwise');
  expect(await page.evaluate(() => pages[0].rot)).toBe(90);
  await page.locator('#sbody .th').nth(2).click();
  await pagesBtn(page, 'Delete page');
  await expect(page.locator('#dlg2')).toContainText('Delete page 3?');
  await page.click('#dlg2 button.on');
  expect(await idxs(page)).toEqual(['0:0', '0:1']);
  // Drag the second thumbnail onto the first
  await page.locator('#sbody .th').nth(1).dragTo(page.locator('#sbody .th').nth(0));
  expect(await idxs(page)).toEqual(['0:1', '0:0']);
  await waitRendered(page);
  await page.click('#bSaveAs');
  const [saved] = await waitSaved(page);
  const pdf = await inspectPdf(page, saved.b64);
  expect(pdf.pages.map((p) => [p.width, p.height, p.rotate])).toEqual([
    [842, 595, 0],
    [842, 595, 90],
  ]);
});

test('you cannot delete every page', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await page.locator('#sbody .th').nth(0).click();
  await page
    .locator('#sbody .th')
    .nth(2)
    .click({ modifiers: ['Shift'] });
  await pagesBtn(page, 'Delete page');
  await expect(page.locator('#msg')).toHaveText('You can’t delete all the pages.');
  expect(await page.evaluate(() => pages.length)).toBe(3);
});

test('add a blank A5 page and a PDF with its bookmarks', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await pagesBtn(page, 'Add pages');
  await expect(page.locator('#dOk')).toBeDisabled();
  await page.selectOption('#dSize', 'a5');
  await expect(page.locator('#dOk')).toBeEnabled();
  await page.click('#dOk');
  await expect(page.locator('#msg')).toHaveText('Blank page added.');
  expect(await page.evaluate(() => pages.length)).toBe(4);
  // From a PDF, at the start
  await pagesBtn(page, 'Add pages');
  const chooser = page.waitForEvent('filechooser');
  await page.click('#dPick');
  await (await chooser).setFiles(join(FIX, 'outline.pdf'));
  await expect(page.locator('#dName')).toHaveText('outline.pdf');
  await page.check('input[name=dw][value=start]');
  await page.click('#dOk');
  await expect(page.locator('#msg')).toHaveText('PDF added: 4 pages and its bookmarks.');
  expect(await page.evaluate(() => pages.length)).toBe(8);
  await page.waitForFunction(() => pages.every((p) => p.loaded));
  await page.click('#bSaveAs');
  const [saved] = await waitSaved(page);
  const pdf = await inspectPdf(page, saved.b64);
  expect(pdf.pages.map((p) => [p.width, p.height])).toEqual([
    [595, 842],
    [595, 842],
    [595, 842],
    [595, 842],
    [595, 842],
    [842, 595],
    [595, 842],
    [420, 595],
  ]);
  expect(pdf.outline.map((o) => o.title)).toEqual(['Introduction', 'Chapter one', 'Appendix']);
});

test('bookmarks: list, go to, add, bold, save', async ({ page }) => {
  await openApp(page, { lang: 'es' });
  await openPdf(page, 'outline.pdf');
  await expect(page.locator('#tabs button.on')).toHaveAttribute('data-tab', 'bm');
  await expect(page.locator('#sbody .bm > span:nth-child(2)')).toHaveText([
    'Introduction',
    'Chapter one',
    'Section 1.1',
    'Section 1.2 — café',
    'Appendix',
  ]);
  await expect(page).toHaveScreenshot('bookmarks-es.png', SHOT);
  await page.locator('#sbody .bm > span:nth-child(2)', { hasText: 'Section 1.1' }).click();
  await expect(page.locator('#pg')).toHaveValue('2');
  // New bookmark for the current page, with the default title
  await page.click('#addbm');
  await expect(page.locator('#dlg2 input')).toHaveValue('Página 2');
  await page.keyboard.press('Enter');
  const row = page.locator('#sbody .bm', { hasText: 'Página 2' });
  await row.click();
  await page.click('#sbody .sbar .ib[title="Negrita"]');
  const state = await page.evaluate(() => {
    const m = (l) => l.map((i) => ({ title: i.title, bold: !!i.bold, italic: !!i.italic, items: m(i.items) }));
    return m(bookmarks);
  });
  expect(JSON.stringify(state)).toContain('"title":"Página 2","bold":true');
  await page.click('#bSaveAs');
  const [saved] = await waitSaved(page);
  expect((await inspectPdf(page, saved.b64)).outline).toEqual(state);
});

test('merge PDFs: protected files are listed in red and left out', async ({ page }) => {
  await openApp(page);
  await page.click('#eMerge');
  await expect(page.locator('#mOk')).toBeDisabled();
  await dropOnMergeList(page, ['text.pdf', 'outline.pdf', 'protected.pdf']);
  await expect(page.locator('#mList .mrow')).toHaveCount(3);
  await expect(page.locator('#mList .mrow.enc .bad')).toHaveText('Cannot be merged');
  await expect(page.locator('#mTot')).toHaveText('2 files · 7 pages in total');
  await expect(page).toHaveScreenshot('merge-dialog.png', SHOT);
  await page.click('#mOk');
  await expect(page.locator('#msg')).toHaveText('PDF merged: 7 pages. Use “Save As…” to save it.');
  expect(await page.evaluate(() => pages.length)).toBe(7);
  await waitRendered(page);
  await page.click('#bSaveAs');
  const [saved] = await waitSaved(page);
  expect(saved.name).toBe('merged.pdf');
  const pdf = await inspectPdf(page, saved.b64);
  expect(pdf.pages).toHaveLength(7);
  expect(pdf.outline.map((o) => [o.title, o.items.length])).toEqual([
    ['text', 0],
    ['outline', 3],
  ]);
});

test('extract pages into one file', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await pagesBtn(page, 'Extract pages');
  await page.fill('#xPg', 'abc');
  await page.click('#xOk');
  await expect(page.locator('#xErr')).toHaveText('Invalid format: “abc”.');
  await page.fill('#xPg', '5');
  await page.click('#xOk');
  await expect(page.locator('#xErr')).toHaveText('Page 5 does not exist (the document has 3).');
  await page.fill('#xPg', '1, 3');
  await page.click('#xOk');
  const [f] = await waitSaved(page);
  expect(f.name).toBe('extracted.pdf');
  expect((await inspectPdf(page, f.b64)).pages.map((p) => p.width)).toEqual([595, 595]);
  await expect(page.locator('#msg')).toHaveText('2 pages extracted into 1 file ✔');
  expect(await page.evaluate(() => pages.length)).toBe(3);
});

test('extract as separate pages and delete them from the document', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await pagesBtn(page, 'Extract pages');
  await page.fill('#xPg', '2-');
  await page.check('#xSep');
  await page.check('#xDel');
  await page.click('#xOk');
  const files = await waitSaved(page, 2);
  expect(files.map((f) => f.name)).toEqual(['extracted_01.pdf', 'extracted_02.pdf']);
  await expect(page.locator('#msg')).toHaveText('2 pages extracted into 2 files and removed from the document ✔');
  expect(await page.evaluate(() => pages.length)).toBe(1);
});

test('find text, ignoring accents', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await page.keyboard.press('Control+f');
  await expect(page.locator('#sb')).toBeVisible();
  await page.keyboard.type('cancion');
  await expect(page.locator('#sc')).toHaveText('1 of 6');
  await page.keyboard.press('Enter');
  await expect(page.locator('#sc')).toHaveText('2 of 6');
  await page.keyboard.press('Shift+Enter');
  await expect(page.locator('#sc')).toHaveText('1 of 6');
  await waitRendered(page);
  await expect(page).toHaveScreenshot('find-results.png', SHOT);
  await page.fill('#sq', 'LIGHTHOUSE3');
  await expect(page.locator('#sc')).toHaveText('1 of 1');
  await expect(page.locator('#pg')).toHaveValue('3');
  await page.fill('#sq', 'zzzz');
  await expect(page.locator('#sc')).toHaveText('No results');
  await page.keyboard.press('Escape');
  await expect(page.locator('#sb')).toBeHidden();
});

test('print dialog: default choices, then a PDF is prepared for printing', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await page.keyboard.press('Control+p');
  await expect(page.locator('#dlg h3')).toHaveText('Print');
  const checked = await page
    .locator('#dlg input[type=checkbox]')
    .evaluateAll((es) => Object.fromEntries(es.map((e) => [e.dataset.t, e.checked])));
  expect(checked).toEqual({ note: false, ft: false, hl: true, ul: true, so: true, sq: true, ci: true, ar: true });
  await expect(page).toHaveScreenshot('print-dialog.png', SHOT);
  await page.click('#pOk');
  await page.waitForFunction(() => printFrame && printFrame.src.startsWith('blob:'));
});
