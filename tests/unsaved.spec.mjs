// Unsaved changes: what counts as a change, and the question asked before the document is replaced or closed
import { test, expect } from '@playwright/test';
import {
  openApp,
  openPdf,
  openBytes,
  fixtureB64,
  waitRendered,
  waitSaved,
  inspectPdf,
  dropOnMergeList,
  expectNoExternalRequests,
  tool,
  SHOT,
} from './helpers.mjs';

test.afterEach(async ({ page }) => expectNoExternalRequests(page));

const dirty = (page) => page.evaluate(() => hasUnsavedChanges());
async function drawRect(page) {
  await tool(page, 'sq');
  const b = await page.locator('#view .page').first().boundingBox();
  await page.mouse.move(b.x + 100, b.y + 300);
  await page.mouse.down();
  await page.mouse.move(b.x + 250, b.y + 380);
  await page.mouse.up();
  await tool(page, 'sel');
}
// Starts opening another fixture with “Open PDF” without waiting for it (the question may appear first)
async function startOpening(page, name) {
  await page.evaluate(([n, b]) => window.__pt.queue(n, b), [name, fixtureB64(name)]);
  await page.click('#bOpen');
}

test('a document just opened has nothing to save; a new annotation does, and saving clears it', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  expect(await dirty(page)).toBe(false);
  await drawRect(page);
  expect(await dirty(page)).toBe(true);
  await page.click('#bSave');
  await page.click('#dlg2 button.on'); // Overwrite
  await waitSaved(page);
  expect(await dirty(page)).toBe(false);
});

test('page, bookmark and form changes count; undoing them by hand leaves nothing to save', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'outline.pdf');
  // Rotate a page, then rotate it back
  await page.click('#tabs button[data-tab="th"]');
  await page.locator('#sbody .th').first().click();
  await page.click('#sbody .sbar .ib[title="Rotate 90° clockwise"]');
  expect(await dirty(page)).toBe(true);
  await page.click('#sbody .sbar .ib[title="Rotate 90° anticlockwise"]');
  expect(await dirty(page)).toBe(false);
  // Bookmarks: bold on, then off
  await page.click('#tabs button[data-tab="bm"]');
  await page.locator('#sbody .bm', { hasText: 'Appendix' }).click();
  await page.click('#sbody .sbar .ib[title="Bold"]');
  expect(await dirty(page)).toBe(true);
  await page.click('#sbody .sbar .ib[title="Bold"]');
  expect(await dirty(page)).toBe(false);
  // Expanding or collapsing the bookmarks is only a way of looking at them
  await page.click('#sbody .sbar .ib[title="Expand / collapse bookmarks"]');
  expect(await dirty(page)).toBe(false);
  // Deleting a page
  await page.click('#tabs button[data-tab="th"]');
  await page.locator('#sbody .th').nth(3).click();
  await page.click('#sbody .sbar .ib[title="Delete page"]');
  await page.click('#dlg2 button.on');
  expect(await dirty(page)).toBe(true);
});

test('form values count as changes', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'form.pdf');
  await page.fill('.fl input[data-fn="name"]', 'Ada');
  expect(await dirty(page)).toBe(true);
  await page.fill('.fl input[data-fn="name"]', '');
  expect(await dirty(page)).toBe(false);
});

test('changes to annotations saved earlier count: colour, text, deleting', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await tool(page, 'note');
  {
    const b = await page.locator('#view .page').first().boundingBox();
    await page.mouse.click(b.x + b.width * 0.9, b.y + 80);
  }
  await page.keyboard.type('Saved note');
  await page.keyboard.press('Control+Enter');
  await tool(page, 'sel');
  await page.click('#bSaveAs');
  const [saved] = await waitSaved(page);
  await openBytes(page, 'text.pdf', saved.b64);
  expect(await dirty(page)).toBe(false);
  await page.click('#tabs button[data-tab="an"]');
  const row = page.locator('#sbody .bm').first();
  await row.hover();
  await row.locator('button[title="Change colour"]').click();
  await page.click('#pal .sq[title="Lilac"]');
  expect(await dirty(page)).toBe(true);
  await row.hover();
  await row.locator('button[title="Change colour"]').click();
  await page.click('#pal .sq[title="Yellow"]');
  expect(await dirty(page)).toBe(false);
  await row.hover();
  await row.locator('button[title="Delete"]').click();
  await page.click('#dlg2 button.on');
  expect(await dirty(page)).toBe(true);
});

test('Open with unsaved changes asks: Cancel keeps the document, Discard opens the other one', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await drawRect(page);
  await startOpening(page, 'outline.pdf');
  await expect(page.locator('#dlg2 h3')).toHaveText('Save changes to “text.pdf”?');
  await expect(page.locator('#dlg2 button')).toHaveText(['Cancel', 'Discard', 'Save']);
  await expect(page.locator('#dlg2 button.on')).toBeFocused();
  await expect(page).toHaveScreenshot('unsaved-dialog.png', SHOT);
  await page.click('#dlg2 button:text("Cancel")');
  expect(await page.evaluate(() => [fname, pages.length, pages[0].annots.length])).toEqual(['text.pdf', 3, 1]);
  await startOpening(page, 'outline.pdf');
  await page.click('#dlg2 button:text("Discard")');
  await page.waitForFunction(() => fname == 'outline.pdf' && pages.length == 4);
  expect(await dirty(page)).toBe(false);
});

test('Open with unsaved changes: Save writes the file first, then opens the other one', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await drawRect(page);
  await startOpening(page, 'outline.pdf');
  await page.click('#dlg2 button:text("Save")');
  const [saved] = await waitSaved(page);
  expect(saved.name).toBe('text.pdf');
  expect((await inspectPdf(page, saved.b64)).pages[0].annots.map((a) => a.subtype)).toEqual(['Square']);
  await page.waitForFunction(() => fname == 'outline.pdf' && pages.length == 4);
});

test('Open without changes does not ask', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await startOpening(page, 'outline.pdf');
  await page.waitForFunction(() => fname == 'outline.pdf');
  await expect(page.locator('#dlg2')).toHaveCount(0);
});

test('Merge asks only with unsaved changes, and a merged document is unsaved until saved', async ({ page }) => {
  await openApp(page, { lang: 'es' });
  await openPdf(page, 'text.pdf');
  await drawRect(page);
  await page.click('#bMerge');
  await dropOnMergeList(page, ['text.pdf', 'outline.pdf']);
  await expect(page.locator('#mList .mrow')).toHaveCount(2);
  await page.click('#mOk');
  await expect(page.locator('#dlg2 h3')).toHaveText('¿Guardar los cambios de «text.pdf»?');
  await expect(page.locator('#dlg2 button')).toHaveText(['Cancelar', 'Descartar', 'Guardar']);
  await page.click('#dlg2 button:text("Descartar")');
  await page.waitForFunction(() => pages.length == 7);
  await waitRendered(page);
  expect(await dirty(page)).toBe(true);
  await page.click('#bSaveAs');
  await waitSaved(page);
  expect(await dirty(page)).toBe(false);
});

test('a protected PDF cannot be saved: the question offers only Discard and Cancel', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'protected.pdf');
  await page.click('#dlg2 button.on'); // the protected-PDF notice
  await drawRect(page);
  await startOpening(page, 'text.pdf');
  await expect(page.locator('#dlg2 h3')).toHaveText('Discard the changes to “protected.pdf”?');
  await expect(page.locator('#dlg2 button')).toHaveText(['Cancel', 'Discard']);
  await page.click('#dlg2 button:text("Discard")');
  await page.waitForFunction(() => fname == 'text.pdf');
});

test('closing the browser tab asks only when there are unsaved changes', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  const asked = [];
  page.on('dialog', (d) => {
    asked.push(d.type());
    d.dismiss();
  });
  const closed = page.waitForEvent('close');
  await page.close({ runBeforeUnload: true });
  await closed; // it closes straight away, without a question
  expect(asked).toEqual([]);
});

test('closing the browser tab with unsaved changes asks', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await drawRect(page);
  const dialog = page.waitForEvent('dialog');
  await page.close({ runBeforeUnload: true });
  const d = await dialog;
  expect(d.type()).toBe('beforeunload');
  await d.accept();
});
