// Security: every PDF is opened by pdf.js with isEvalSupported:false (CVE-2024-4367 in pdf.js 3.11)
import { test, expect } from '@playwright/test';
import { join } from 'node:path';
import { openApp, openPdf, dropOnMergeList, expectNoExternalRequests, FIX } from './helpers.mjs';

test.afterEach(async ({ page }) => expectNoExternalRequests(page));

test('Open, Add pages and Merge all open PDFs with isEvalSupported:false', async ({ page }) => {
  await openApp(page);
  // Records the options of every call the app makes to pdf.js to open a document
  // (pdf.js exports are read-only, so the library object is wrapped in a new one that inherits everything else)
  await page.evaluate(() => {
    const lib = window.pdfjsLib,
      g = lib.getDocument;
    window.__gd = [];
    window.pdfjsLib = Object.create(lib, {
      getDocument: {
        value: (o) => {
          window.__gd.push(o.isEvalSupported);
          return g(o);
        },
      },
    });
  });
  await openPdf(page, 'text.pdf');
  await page.click('#sbody .sbar .ib[title="Add pages"]');
  const chooser = page.waitForEvent('filechooser');
  await page.click('#dPick');
  await (await chooser).setFiles(join(FIX, 'outline.pdf'));
  await page.click('#dOk');
  await expect(page.locator('#msg')).toHaveText('PDF added: 4 pages and its bookmarks.');
  await page.click('#bMerge');
  // The pages just added are an unsaved change: Penfold asks first
  await page.click('#dlg2 button:text("Discard")');
  await dropOnMergeList(page, ['text.pdf', 'form.pdf']);
  await expect(page.locator('#mList .mrow')).toHaveCount(2);
  const calls = await page.evaluate(() => window.__gd);
  expect(calls).toEqual([false, false, false, false]);
});
