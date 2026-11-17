// Fillable forms (fill in, save editable, flatten) and protected (encrypted) PDFs
import { test, expect } from '@playwright/test';
import { join } from 'node:path';
import {
  openApp,
  openPdf,
  openBytes,
  waitRendered,
  waitSaved,
  inspectPdf,
  FIX,
  SHOT,
  expectNoExternalRequests,
} from './helpers.mjs';

// Every test: nothing may come from the network, and no file may be missing from the project folder
test.afterEach(async ({ page }) => expectNoExternalRequests(page));

// The radio group of form.pdf (made with pdf-lib) uses /Opt: its buttons' values are "0" and "1" and their labels "small" and "large"
async function fillForm(page, { radio = false } = {}) {
  await page.fill('.fl input[data-fn="name"]', 'Ada Lovelace');
  await page.fill('.fl textarea[data-fn="notes"]', 'Line one\nLine two');
  await page.check('.fl input[data-fn="agree"]');
  if (radio) await page.check('.fl input[data-fn="size"][value="1"]');
  await page.selectOption('.fl select[data-fn="colour"]', 'Blue');
}

// Fixed in 0.5.1: in a radio group with /Opt the choice was not saved (the button's state "1" was passed to
// pdf-lib's select(), which expects the option "large")
test('radio groups with /Opt keep the choice on save, and it is shown when reopened', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'form.pdf');
  await fillForm(page, { radio: true });
  await page.click('#bSaveAs');
  await page.click('#fOk');
  const [saved] = await waitSaved(page);
  await expect(page.locator('#msg')).toHaveText('Saved ✔');
  expect((await inspectPdf(page, saved.b64)).fields).toEqual({
    name: 'Ada Lovelace',
    notes: 'Line one\nLine two',
    agree: true,
    size: 'large',
    colour: ['Blue'],
  });
  await openBytes(page, 'form.pdf', saved.b64);
  await expect(page.locator('.fl input[data-fn="size"][value="1"]')).toBeChecked();
  await expect(page.locator('.fl input[data-fn="size"][value="0"]')).not.toBeChecked();
});

test('form fields are shown, keep their values on zoom and are saved editable', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'form.pdf');
  await expect(page.locator('.fl > *')).toHaveCount(6);
  await fillForm(page);
  await expect(page.locator('#view')).toHaveScreenshot('form-filled.png', SHOT);
  await page.click('#zi');
  await waitRendered(page);
  await expect(page.locator('.fl input[data-fn="name"]')).toHaveValue('Ada Lovelace');
  await expect(page.locator('.fl input[data-fn="agree"]')).toBeChecked();
  // With another tool the fields do not take the mouse
  await page.click('#bar .ib[data-t="hl"]');
  expect(await page.locator('.fl input[data-fn="name"]').evaluate((e) => getComputedStyle(e).pointerEvents)).toBe(
    'none',
  );
  await page.click('#bar .ib[data-t="sel"]');
  await page.click('#bSaveAs');
  await expect(page.locator('#dlg #fFlat')).not.toBeChecked();
  await expect(page).toHaveScreenshot('flatten-dialog.png', SHOT);
  await page.click('#fOk');
  const [saved] = await waitSaved(page);
  const pdf = await inspectPdf(page, saved.b64);
  expect(pdf.hasAcroForm).toBe(true);
  expect(pdf.fields).toEqual({
    name: 'Ada Lovelace',
    notes: 'Line one\nLine two',
    agree: true,
    size: null,
    colour: ['Blue'],
  });
});

test('Save As can flatten the form; Cancel does not save', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'form.pdf');
  await fillForm(page, { radio: true });
  await page.click('#bSaveAs');
  await page.click('#fCancel');
  await page.waitForTimeout(300);
  expect(await page.evaluate(() => window.__pt.saved.length)).toBe(0);
  await page.click('#bSaveAs');
  await page.check('#fFlat');
  await page.click('#fOk');
  const [saved] = await waitSaved(page);
  await expect(page.locator('#msg')).toHaveText('Saved ✔ (form flattened)');
  const pdf = await inspectPdf(page, saved.b64);
  expect(pdf.hasAcroForm).toBe(false);
  expect(pdf.pages[0].annots.filter((a) => a.subtype == 'Widget')).toHaveLength(0);
  // A flattened copy is an export: the working file is still the original one
  expect(await page.evaluate(() => fileHandle && fileHandle.name)).toBe('form.pdf');
});

for (const name of ['protected.pdf', 'protected-objstm.pdf']) {
  test(`protected PDF (${name}): notice, reminder and blocked actions`, async ({ page }) => {
    await openApp(page);
    await openPdf(page, name);
    await expect(page.locator('#dlg2 h3.warn svg')).toBeVisible();
    await expect(page.locator('#dlg2')).toContainText('This PDF is protected. Any changes made to it cannot be saved.');
    if (name == 'protected.pdf') await expect(page).toHaveScreenshot('protected-notice.png', SHOT);
    await page.click('#dlg2 button.on');
    await expect(page.locator('#lockw')).toBeVisible();
    for (const s of ['#bSave', '#bSaveAs', '#bPrint']) await expect(page.locator(s)).toBeDisabled();
    await expect(page.locator('#bFind')).toBeEnabled();
    await expect(page.locator('#sbody .sbar .ib[title="Extract pages"]')).toBeDisabled();
    await page.keyboard.press('Control+p');
    await expect(page.locator('#msg')).toHaveText(
      'This PDF is protected against changes: Penfold cannot save it, print it or extract pages from it yet.',
    );
    await expect(page.locator('#dlg')).toHaveCount(0);
    if (name == 'protected.pdf') {
      await waitRendered(page);
      await expect(page).toHaveScreenshot('protected-open.png', SHOT);
    }
    // Opening an unprotected PDF removes the reminder and enables everything again
    await openPdf(page, 'text.pdf');
    await expect(page.locator('#lockw')).toBeHidden();
    for (const s of ['#bSave', '#bSaveAs', '#bPrint']) await expect(page.locator(s)).toBeEnabled();
  });
}

test('pages cannot be added from a protected PDF', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await page.click('#sbody .sbar .ib[title="Add pages"]');
  const chooser = page.waitForEvent('filechooser');
  await page.click('#dPick');
  await (await chooser).setFiles(join(FIX, 'protected.pdf'));
  await page.click('#dOk');
  await expect(page.locator('#msg')).toHaveText(
    'Error adding: “protected.pdf” is protected against changes and cannot be added yet.',
  );
  expect(await page.evaluate(() => pages.length)).toBe(3);
});
