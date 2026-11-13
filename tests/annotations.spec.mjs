// Annotations: creating each type with the real tools, the Annotations panel, saving with /AP, reopening, and annotations from other programs
import { test, expect } from '@playwright/test';
import {
  openApp,
  openPdf,
  openBytes,
  waitSaved,
  inspectPdf,
  tool,
  SHOT,
  expectNoExternalRequests,
} from './helpers.mjs';

// Every test: nothing may come from the network, and no file may be missing from the project folder
test.afterEach(async ({ page }) => expectNoExternalRequests(page));

// Selects part of a line of text on page i (as if dragged with the mouse) and releases the mouse, which is when the app reacts
async function selectText(page, i, lineText, from, to) {
  await page.evaluate(
    ([i, lineText, from, to]) => {
      const span = [...document.querySelectorAll('#view .page')[i].querySelectorAll('.textLayer span')].find((s) =>
        s.textContent.includes(lineText),
      );
      const node = span.firstChild,
        start = span.textContent.indexOf(lineText);
      const r = document.createRange();
      r.setStart(node, start + from);
      r.setEnd(node, start + to);
      const s = getSelection();
      s.removeAllRanges();
      s.addRange(r);
      document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
    },
    [i, lineText, from, to],
  );
}
// Page-relative point (fractions of the page size) → screen coordinates. At “fit width” only the top ~55 % of page 1 is in view.
async function at(page, i, fx, fy) {
  const b = await page.locator('#view .page').nth(i).boundingBox();
  return [b.x + b.width * fx, b.y + b.height * fy];
}
async function drag(page, i, a, b) {
  const [x0, y0] = await at(page, i, ...a),
    [x1, y1] = await at(page, i, ...b);
  await page.mouse.move(x0, y0);
  await page.mouse.down();
  await page.mouse.move((x0 + x1) / 2, (y0 + y1) / 2);
  await page.mouse.move(x1, y1);
  await page.mouse.up();
}
async function typeInDialog(page, text) {
  await expect(page.locator('#dlg textarea')).toBeFocused();
  await page.keyboard.type(text);
  await page.keyboard.press('Control+Enter');
  await expect(page.locator('#dlg')).toHaveCount(0);
}

// Creates one annotation of every type on page 1 of text.pdf
async function annotateAll(page) {
  await tool(page, 'hl');
  await selectText(page, 0, 'quick brown fox', 0, 15);
  await page.click('.sw[data-c="#8ff0a4"]');
  await tool(page, 'ul');
  await selectText(page, 0, 'Penfold reads', 0, 13);
  await page.click('.sw[data-c="#f66151"]');
  await tool(page, 'so');
  await selectText(page, 0, 'Searching ignores', 0, 17);
  await page.click('.sw[data-c="#99c1f1"]');
  await tool(page, 'note');
  {
    const [x, y] = await at(page, 0, 0.92, 0.08);
    await page.mouse.click(x, y);
  }
  await typeInDialog(page, 'A comment with ñ, € and 😀');
  await page.click('.sw[data-c="#ffbe6f"]');
  await tool(page, 'ft');
  await drag(page, 0, [0.5, 0.27], [0.85, 0.27]);
  await typeInDialog(page, 'Text box line one\nSecond line');
  await page.click('.sw[data-c="#dc8add"]');
  await tool(page, 'sq');
  await drag(page, 0, [0.1, 0.27], [0.3, 0.33]);
  await tool(page, 'ci');
  await drag(page, 0, [0.32, 0.27], [0.45, 0.33]);
  await page.click('.sw[data-c="#f9f06b"]');
  await tool(page, 'ar');
  await drag(page, 0, [0.55, 0.45], [0.85, 0.36]);
  await tool(page, 'sel');
}
const ALL = ['hl', 'ul', 'so', 'note', 'ft', 'sq', 'ci', 'ar'];

test('create every annotation type, see them on the page and in the panel', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await annotateAll(page);
  expect(await page.evaluate(() => pages[0].annots.map((a) => a.type))).toEqual(ALL);
  const ov = page.locator('#view .page').first().locator('.ov');
  for (const c of ALL) await expect(ov.locator('.an.' + c).first()).toBeAttached();
  await expect(ov.locator('.an.note')).toHaveAttribute('data-text', 'A comment with ñ, € and 😀');
  await expect(page.locator('#view')).toHaveScreenshot('page-all-annotations.png', SHOT);
  // Annotations panel: comments and text boxes by default; turning on the other types lists them all
  await page.click('#tabs button[data-tab="an"]');
  await expect(page.locator('#sbody .bm')).toHaveCount(2);
  for (const t of ['Highlights', 'Underlines', 'Strikethroughs', 'Rectangles', 'Circles', 'Arrows'])
    await page.click(`#sbody .sbar .ib[title="${t}"]`);
  await expect(page.locator('#sbody .bm')).toHaveCount(8);
  await expect(page).toHaveScreenshot('annotations-panel.png', SHOT);
});

test('edit, recolour and delete annotations from the panel', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await tool(page, 'note');
  {
    const [x, y] = await at(page, 0, 0.92, 0.08);
    await page.mouse.click(x, y);
  }
  await typeInDialog(page, 'First text');
  await tool(page, 'sel');
  await page.click('#tabs button[data-tab="an"]');
  const row = page.locator('#sbody .bm').first();
  await row.hover();
  await row.locator('button[title="Edit text"]').click();
  await page.keyboard.press('Control+a');
  await page.keyboard.type('Edited text');
  await page.keyboard.press('Control+Enter');
  expect(await page.evaluate(() => pages[0].annots[0].text)).toBe('Edited text');
  await row.hover();
  await row.locator('button[title="Change colour"]').click();
  await page.click('#pal .sq[title="Lilac"]');
  expect(await page.evaluate(() => pages[0].annots[0].color)).toBe('#dc8add');
  await row.hover();
  await row.locator('button[title="Delete"]').click();
  await expect(page.locator('#dlg2 h3')).toHaveText('Delete annotation');
  await page.click('#dlg2 button.on');
  expect(await page.evaluate(() => pages[0].annots.length)).toBe(0);
  await expect(page.locator('#sbody')).toContainText('No annotations');
});

test('right-click deletes an annotation after confirming', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await tool(page, 'note');
  {
    const [x, y] = await at(page, 0, 0.92, 0.08);
    await page.mouse.click(x, y);
  }
  await typeInDialog(page, 'To delete');
  await tool(page, 'sel');
  await page.locator('.an.note').click({ button: 'right' });
  await page.click('#dlg2 button:not(.on)'); // Cancel
  expect(await page.evaluate(() => pages[0].annots.length)).toBe(1);
  await page.locator('.an.note').click({ button: 'right' });
  await page.click('#dlg2 button.on');
  expect(await page.evaluate(() => pages[0].annots.length)).toBe(0);
});

test('Save As writes every annotation with its own drawing, and reopening keeps them as Penfold’s own', async ({
  page,
}) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await annotateAll(page);
  await page.click('#bSaveAs');
  const [saved] = await waitSaved(page);
  expect(saved.name).toBe('text.pdf');
  await expect(page.locator('#msg')).toHaveText('Saved ✔');
  const pdf = await inspectPdf(page, saved.b64);
  expect(pdf.pages).toHaveLength(3);
  const an = pdf.pages[0].annots;
  expect(an.map((a) => a.subtype).sort()).toEqual([
    'Circle',
    'FreeText',
    'Highlight',
    'Line',
    'Square',
    'StrikeOut',
    'Text',
    'Underline',
  ]);
  expect(an.every((a) => a.author === 'Penfold')).toBe(true);
  expect(pdf.penfoldWithoutAP).toBe(0);
  expect(an.find((a) => a.subtype == 'Text').contents).toBe('A comment with ñ, € and 😀');
  expect(an.find((a) => a.subtype == 'FreeText').contents).toBe('Text box line one\nSecond line');
  // Reopen the saved file: the annotations are recognised as editable (not read-only) and nothing is duplicated
  await openBytes(page, 'text.pdf', saved.b64);
  const back = await page.evaluate(() => pages[0].annots.map((a) => ({ type: a.type, ro: a.ro, color: a.color })));
  expect(back.map((a) => a.type).sort()).toEqual([...ALL].sort());
  expect(back.every((a) => a.ro === false)).toBe(true);
  expect(back.find((a) => a.type == 'hl').color).toBe('#f9f06b');
  // Saving again does not duplicate them
  await page.click('#bSaveAs');
  const files = await waitSaved(page, 2);
  expect((await inspectPdf(page, files[1].b64)).pages[0].annots).toHaveLength(8);
});

test('Save overwrites the opened file after confirming', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'text.pdf');
  await tool(page, 'sq');
  await drag(page, 0, [0.1, 0.27], [0.3, 0.33]);
  await tool(page, 'sel');
  await page.click('#bSave');
  await expect(page.locator('#dlg2 h3')).toHaveText('Overwrite file');
  await expect(page.locator('#dlg2')).toContainText('Do you want to overwrite “text.pdf”?');
  await page.click('#dlg2 button.on');
  const [saved] = await waitSaved(page);
  expect(saved.name).toBe('text.pdf');
  expect((await inspectPdf(page, saved.b64)).pages[0].annots.map((a) => a.subtype)).toEqual(['Square']);
});

test('annotations from other programs are shown read-only and kept on save', async ({ page }) => {
  await openApp(page);
  await openPdf(page, 'foreign.pdf');
  const an = await page.evaluate(() =>
    pages[0].annots.map((a) => ({ type: a.type, ro: a.ro, author: a.author, color: a.color })),
  );
  expect(an).toEqual([
    { type: 'hl', ro: true, author: 'Alice', color: '#00ff00' },
    { type: 'note', ro: true, author: 'Bob', color: '#ffff00' },
    { type: 'ft', ro: true, author: '', color: '#c64600' },
    { type: 'sq', ro: true, author: 'Alice', color: '#0000ff' },
  ]);
  await page.click('#tabs button[data-tab="an"]');
  for (const t of ['Highlights', 'Rectangles']) await page.click(`#sbody .sbar .ib[title="${t}"]`);
  await expect(page.locator('#sbody .bm')).toHaveCount(4);
  await expect(page.locator('#sbody .bm').first()).toContainText('(Alice)');
  await expect(page.locator('#sbody .bm .ctl button')).toHaveCount(0);
  await expect(page).toHaveScreenshot('foreign-annotations.png', SHOT);
  await page.click('#bSaveAs');
  const [saved] = await waitSaved(page);
  const out = (await inspectPdf(page, saved.b64)).pages[0].annots;
  expect(out.map((a) => [a.subtype, a.author, a.contents])).toEqual([
    ['Highlight', 'Alice', 'Foreign highlight'],
    ['Text', 'Bob', 'Foreign comment'],
    ['FreeText', '', 'Foreign text box'],
    ['Square', 'Alice', ''],
  ]);
});
