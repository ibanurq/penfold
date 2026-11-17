// Keyboard shortcuts, the main menu (☰) and the Keyboard Shortcuts window
import { test, expect } from '@playwright/test';
import { openApp, openPdf, fixtureB64, waitSaved, expectNoExternalRequests, SHOT } from './helpers.mjs';

test.afterEach(async ({ page }) => expectNoExternalRequests(page));

// Selects part of a line of text on page i, without releasing the mouse (so no tool reacts to it)
async function selectText(page, i, lineText, from, to) {
  await page.evaluate(
    ([i, lineText, from, to]) => {
      const span = [...document.querySelectorAll('#view .page')[i].querySelectorAll('.textLayer span')].find((s) =>
        s.textContent.includes(lineText),
      );
      const start = span.textContent.indexOf(lineText),
        r = document.createRange();
      r.setStart(span.firstChild, start + from);
      r.setEnd(span.firstChild, start + to);
      getSelection().removeAllRanges();
      getSelection().addRange(r);
    },
    [i, lineText, from, to],
  );
}
const annots = (page) => page.evaluate(() => pages[0].annots.map((a) => [a.type, a.txt]));

test('main menu: Keyboard Shortcuts and About Penfold; Esc or a click outside closes it', async ({ page }) => {
  await openApp(page);
  await page.click('#bMenu');
  await expect(page.locator('#menu button')).toHaveText(['Keyboard Shortcuts', 'About Penfold']);
  await expect(page.locator('#menu button').first()).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.locator('#menu')).toHaveCount(0);
  await page.click('#bMenu');
  await page.mouse.click(400, 400);
  await expect(page.locator('#menu')).toHaveCount(0);
  await page.click('#bMenu');
  await page.click('#menu button:text("Keyboard Shortcuts")');
  await expect(page.locator('#menu')).toHaveCount(0);
  await expect(page.locator('#dlg .shortcuts h3')).toHaveText('Keyboard Shortcuts');
});

test('Keyboard Shortcuts window: opened with Ctrl+?, grouped, in Spanish with Spanish key names', async ({ page }) => {
  await openApp(page, { lang: 'es' });
  await page.keyboard.press('Control+?');
  const box = page.locator('#dlg .shortcuts');
  await expect(box.locator('h3')).toHaveText('Atajos de teclado');
  await expect(box.locator('h4')).toHaveText(['Anotaciones', 'General', 'Buscar', 'Ver', 'Desplazarse']);
  // Ctrl+W and Ctrl+Q exist only in the desktop app
  await expect(box.locator('.krow', { hasText: 'Cerrar la ventana' })).toHaveCount(0);
  await expect(box.locator('.krow', { hasText: 'Guardar como' }).locator('kbd')).toHaveText(['Ctrl', 'Mayús', 'S']);
  await expect(box.locator('.krow', { hasText: 'Página siguiente' }).locator('kbd')).toHaveText(['Av Pág']);
  await expect(box.locator('.krow').first()).toHaveText('ResaltarH');
  await expect(page).toHaveScreenshot('shortcuts-es.png', SHOT);
  await page.keyboard.press('Escape');
  await expect(page.locator('#dlg')).toHaveCount(0);
});

test('H and U: mark the selected text, or choose the tool; Esc goes back to text selection', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  // With text selected: it is marked, and the tool stays as it was
  await selectText(page, 0, 'quick brown fox', 0, 15);
  await page.keyboard.press('h');
  expect(await annots(page)).toEqual([['hl', 'quick brown fox']]);
  expect(await page.evaluate(() => tool)).toBe('sel');
  await selectText(page, 0, 'Penfold reads', 0, 13);
  await page.keyboard.press('u');
  expect(await annots(page)).toEqual([
    ['hl', 'quick brown fox'],
    ['ul', 'Penfold reads'],
  ]);
  // With nothing selected: the tool is chosen
  await page.keyboard.press('u');
  expect(await page.evaluate(() => tool)).toBe('ul');
  await expect(page.locator('#bar .ib[data-t="ul"]')).toHaveClass(/on/);
  await page.keyboard.press('h');
  expect(await page.evaluate(() => tool)).toBe('hl');
  await page.keyboard.press('Escape');
  expect(await page.evaluate(() => tool)).toBe('sel');
  await expect(page.locator('#bar .ib[data-t="sel"]')).toHaveClass(/on/);
  // Typing in a field does not trigger them
  await page.keyboard.press('Control+f');
  await page.keyboard.type('hu');
  await expect(page.locator('#sq')).toHaveValue('hu');
  expect(await page.evaluate(() => tool)).toBe('sel');
  // With the find bar open, Esc closes it and leaves the tool alone
  await page.keyboard.press('h');
  expect(await page.evaluate(() => tool)).toBe('sel');
  await page.click('#bar .ib[data-t="hl"]');
  await page.click('#sq');
  await page.keyboard.press('Escape');
  await expect(page.locator('#sb')).toBeHidden();
  expect(await page.evaluate(() => tool)).toBe('hl');
});

test('Ctrl+O, Ctrl+S and Ctrl+Shift+S', async ({ page }) => {
  await openApp(page);
  await page.evaluate((b) => window.__pt.queue('text.pdf', b), fixtureB64('text.pdf'));
  await page.keyboard.press('Control+o');
  await page.waitForFunction(() => fileName == 'text.pdf' && pages.length == 3);
  await page.keyboard.press('Control+s');
  await expect(page.locator('#dlg2 h3')).toHaveText('Overwrite file');
  await page.click('#dlg2 button:text("Overwrite")');
  await waitSaved(page, 1);
  await page.keyboard.press('Control+Shift+S');
  await waitSaved(page, 2);
});

test('zoom, panel, pages and find from the keyboard', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  const scale = () => page.evaluate(() => scale);
  const fit = await scale();
  await page.keyboard.press('Control+=');
  await expect.poll(scale).toBeCloseTo(fit + 0.2);
  await page.keyboard.press('Control+-');
  await page.keyboard.press('Control+-');
  await expect.poll(scale).toBeCloseTo(fit - 0.2);
  await page.keyboard.press('Control+0');
  await expect.poll(scale).toBeCloseTo(fit);
  // F9 hides and shows the side panel
  await page.keyboard.press('F9');
  await expect(page.locator('#side')).toBeHidden();
  await page.keyboard.press('F9');
  await expect(page.locator('#side')).toBeVisible();
  // Pages
  const current = () => page.evaluate(() => currentPage);
  await page.keyboard.press('PageDown');
  await expect.poll(current).toBe(1);
  await page.keyboard.press('Control+End');
  await expect.poll(current).toBe(2);
  await page.keyboard.press('PageUp');
  await expect.poll(current).toBe(1);
  await page.keyboard.press('Control+Home');
  await expect.poll(current).toBe(0);
  await page.keyboard.press('Control+l');
  await expect(page.locator('#pg')).toBeFocused();
  await page.keyboard.press('Escape');
  // Find: Ctrl+G opens the bar, then goes to the next result
  await page.keyboard.press('Control+g');
  await expect(page.locator('#sb')).toBeVisible();
  await page.keyboard.type('heading');
  await expect(page.locator('#sc')).toHaveText('1 of 3');
  await page.locator('#sq').blur();
  await page.keyboard.press('Control+g');
  await expect(page.locator('#sc')).toHaveText('2 of 3');
  await page.keyboard.press('Control+Shift+G');
  await expect(page.locator('#sc')).toHaveText('1 of 3');
});

test('Delete: deletes the selected pages or bookmarks, asking first', async ({ page }) => {
  await openApp(page);
  // outline.pdf (4 pages) opens on the Bookmarks tab
  await openPdf(page, 'outline.pdf');
  // Nothing selected: nothing happens
  await page.keyboard.press('Delete');
  await expect(page.locator('#dlg2')).toHaveCount(0);
  // A selected bookmark: Penfold asks; Cancel keeps it
  const before = await page.evaluate(() => bookmarks.length);
  await page.click('#sbody .bm >> nth=0');
  await page.keyboard.press('Delete');
  await expect(page.locator('#dlg2 h3')).toHaveText('Delete bookmark');
  await page.click('#dlg2 button:text("Cancel")');
  expect(await page.evaluate(() => bookmarks.length)).toBe(before);
  // A selected page (Pages tab): Penfold asks; Delete deletes it
  await page.click('#tabs button[data-tab="th"]');
  await page.click('#sbody .th >> nth=1');
  await page.keyboard.press('Delete');
  await expect(page.locator('#dlg2 .box > div').first()).toHaveText('Delete page 2?');
  await page.click('#dlg2 button:text("Delete")');
  await expect.poll(() => page.evaluate(() => pages.length)).toBe(3);
});
