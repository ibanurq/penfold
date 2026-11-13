// Welcome screen, toolbar state, About dialog, opening a PDF, zoom and “Two pages”
import { test, expect } from '@playwright/test';
import { openApp, openPdf, waitRendered, expectNoExternalRequests, SHOT } from './helpers.mjs';
import { VERSION } from './helpers.mjs';

// Every test: nothing may come from the network, and no file may be missing from the project folder
test.afterEach(async ({ page }) => expectNoExternalRequests(page));

for (const lang of ['en', 'es'])
  for (const scheme of ['light', 'dark']) {
    test(`welcome screen (${lang}, ${scheme})`, async ({ page }) => {
      await openApp(page, { lang, scheme });
      await expect(page).toHaveTitle('Penfold ' + VERSION);
      await expect(page.locator('html')).toHaveAttribute('lang', lang);
      await expect(page.locator('#empty h2')).toHaveText(lang == 'es' ? 'Comenzar a trabajar' : 'Get started');
      await expect(page).toHaveScreenshot(`welcome-${lang}-${scheme}.png`, SHOT);
      expectNoExternalRequests(page);
    });
  }

test('without a PDF only Open, Merge and Information are enabled', async ({ page }) => {
  await openApp(page);
  for (const s of ['#bOpen', '#bMerge', '#bInfo', '#eOpen', '#eMerge']) await expect(page.locator(s)).toBeEnabled();
  for (const s of ['#bPanel', '#bSave', '#bSaveAs', '#bPrint', '#bFind', '#zo', '#zi', '#fw', '#fp', '#two', '#pg'])
    await expect(page.locator(s)).toBeDisabled();
  await expect(page.locator('#bar .ib[data-t]')).toHaveCount(9);
  for (const b of await page.locator('#bar .ib[data-t], .sw').all()) await expect(b).toBeDisabled();
  await expect(page.locator('#side')).toBeHidden();
});

for (const [lang, scheme] of [
  ['en', 'light'],
  ['es', 'dark'],
]) {
  test(`About dialog (${lang}, ${scheme})`, async ({ page }) => {
    await openApp(page, { lang, scheme });
    await page.click('#bInfo');
    const box = page.locator('#dlg .box.about');
    await expect(box.locator('h3')).toHaveText('Penfold');
    await expect(box.locator('.ver')).toHaveText((lang == 'es' ? 'Versión ' : 'Version ') + VERSION);
    await expect(box.locator('a.web')).toHaveAttribute('href', 'https://github.com/ibanurq/penfold');
    await expect(box.locator('a.bug')).toHaveAttribute('href', 'https://github.com/ibanurq/penfold/issues');
    await expect(page).toHaveScreenshot(`about-${lang}-${scheme}.png`, SHOT);
    await page.keyboard.press('Escape');
    await expect(page.locator('#dlg')).toHaveCount(0);
  });
}

test('open a PDF: pages, thumbnails, toolbar enabled', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await expect(page.locator('#pgN')).toHaveText('3');
  await expect(page.locator('#pg')).toHaveValue('1');
  await expect(page.locator('#view .page')).toHaveCount(3);
  await expect(page.locator('#side')).toBeVisible();
  await expect(page.locator('#sbody .th')).toHaveCount(3);
  await expect(page.locator('#tabs button.on')).toHaveAttribute('data-tab', 'th');
  for (const s of ['#bPanel', '#bSave', '#bSaveAs', '#bPrint', '#bFind', '#zo', '#zi', '#fw', '#fp', '#two', '#pg'])
    await expect(page.locator(s)).toBeEnabled();
  await expect(page.locator('#empty')).toHaveCount(0);
  await expect(page).toHaveScreenshot('open-text-en-light.png', SHOT);
  expectNoExternalRequests(page);
});

test('open a PDF in Spanish and dark mode', async ({ page }) => {
  await openApp(page, { lang: 'es', scheme: 'dark' });
  await openPdf(page, 'text.pdf');
  await expect(page.locator('#pgl')).toHaveText('de 3');
  await expect(page).toHaveScreenshot('open-text-es-dark.png', SHOT);
});

test('zoom in, zoom out, fit width, whole page', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  const width = () =>
    page
      .locator('#view .page')
      .first()
      .evaluate((e) => parseFloat(e.style.width));
  const fitW = await width();
  await page.click('#zi');
  await waitRendered(page);
  expect(await width()).toBeGreaterThan(fitW);
  await page.click('#zo');
  await page.click('#zo');
  await waitRendered(page);
  expect(await width()).toBeLessThan(fitW);
  await page.click('#fp');
  await waitRendered(page);
  const whole = await width();
  expect(whole).toBeLessThan(fitW);
  await page.click('#fw');
  await waitRendered(page);
  expect(Math.abs((await width()) - fitW)).toBeLessThan(1);
});

test('go to page and side panel toggle', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await page.fill('#pg', '3');
  await page.press('#pg', 'Enter');
  await expect(page.locator('#pg')).toHaveValue('3');
  await expect(page.locator('#sbody .th').nth(2)).toHaveClass(/cur/);
  await page.click('#bPanel');
  await expect(page.locator('#side')).toBeHidden();
  await page.click('#bPanel');
  await expect(page.locator('#side')).toBeVisible();
});

test('two pages mode shows one pair at a time', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await page.click('#two');
  await expect(page.locator('#view')).toHaveClass(/two/);
  await waitRendered(page);
  const visible = () => page.locator('#view .page').evaluateAll((es) => es.map((e) => e.style.display != 'none'));
  expect(await visible()).toEqual([true, true, false]);
  await page.keyboard.press('ArrowRight');
  await waitRendered(page);
  expect(await visible()).toEqual([false, false, true]);
  await expect(page.locator('#pg')).toHaveValue('3');
  await expect(page).toHaveScreenshot('two-pages-second-pair.png', SHOT);
  await page.keyboard.press('ArrowLeft');
  expect(await visible()).toEqual([true, true, false]);
});
