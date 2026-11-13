// Opening the app by double-clicking the HTML file (file://) with no network at all
import { test, expect } from '@playwright/test';
import { openAppFile, openPdf, waitSaved, inspectPdf, expectNoExternalRequests, SHOT } from './helpers.mjs';

test.afterEach(async ({ page }) => expectNoExternalRequests(page));

test('file:// without network: open, annotate, save', async ({ page }) => {
  const logs = [];
  page.on('console', (m) => logs.push(m.type() + ': ' + m.text()));
  page.on('pageerror', (e) => logs.push('pageerror: ' + e.message));
  await openAppFile(page);
  await expect(page.locator('#empty h2')).toHaveText('Get started');
  await expect(page).toHaveScreenshot('welcome-file-url.png', SHOT);
  await openPdf(page, 'text.pdf');
  await expect(page.locator('#pgN')).toHaveText('3');
  await expect(page.locator('#view .page').first().locator('.textLayer span').first()).toBeAttached();
  await page.click('#bar .ib[data-t="sq"]');
  const b = await page.locator('#view .page').first().boundingBox();
  await page.mouse.move(b.x + 100, b.y + 400);
  await page.mouse.down();
  await page.mouse.move(b.x + 250, b.y + 480);
  await page.mouse.up();
  await page.click('#bSaveAs');
  const [saved] = await waitSaved(page);
  expect((await inspectPdf(page, saved.b64)).pages[0].annots.map((a) => a.subtype)).toEqual(['Square']);
  // No errors in the console (since 0.5.1 the worker is not fetched with file://)
  expect(logs.filter((l) => /^(error|pageerror|warning)/.test(l))).toEqual([]);
});
