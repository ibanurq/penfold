// Makes the images used by the README (docs/images/) from the real app, with the test PDFs.
// Run with: npm run screenshots   (after a visual change)
import { chromium } from '@playwright/test';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { openApp, openPdf, waitRendered } from '../tests/helpers.mjs';

const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'docs', 'images');

// Selects part of a line of text on page i and releases the mouse, as the highlight tools expect
async function selectText(page, lineText, from, to) {
  await page.evaluate(
    ([lineText, from, to]) => {
      const span = [...document.querySelectorAll('#view .page')[0].querySelectorAll('.textLayer span')].find((s) =>
        s.textContent.includes(lineText),
      );
      const start = span.textContent.indexOf(lineText);
      const r = document.createRange();
      r.setStart(span.firstChild, start + from);
      r.setEnd(span.firstChild, start + to);
      getSelection().removeAllRanges();
      getSelection().addRange(r);
      document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
    },
    [lineText, from, to],
  );
}
async function at(page, fx, fy) {
  const b = await page.locator('#view .page').first().boundingBox();
  return [b.x + b.width * fx, b.y + b.height * fy];
}
async function drag(page, a, b) {
  const [x0, y0] = await at(page, ...a),
    [x1, y1] = await at(page, ...b);
  await page.mouse.move(x0, y0);
  await page.mouse.down();
  await page.mouse.move(x1, y1, { steps: 4 });
  await page.mouse.up();
}
async function typeInDialog(page, text) {
  await page.keyboard.type(text);
  await page.keyboard.press('Control+Enter');
}
const colour = (page, c) => page.click(`.sw[data-c="${c}"]`);
const tool = (page, t) => page.click(`#bar .ib[data-t="${t}"]`);
// The mouse rests on an empty part of the page, so no button looks hovered
const rest = (page) => page.mouse.move(1180, 760);

async function annotated(page) {
  await openPdf(page, 'text.pdf');
  await tool(page, 'hl');
  await selectText(page, 'quick brown fox', 0, 15);
  await colour(page, '#8ff0a4');
  await tool(page, 'ul');
  await selectText(page, 'Penfold reads', 0, 13);
  await colour(page, '#f66151');
  await tool(page, 'so');
  await selectText(page, 'Searching ignores', 0, 17);
  await colour(page, '#99c1f1');
  await tool(page, 'note');
  await page.mouse.click(...(await at(page, 0.92, 0.08)));
  await typeInDialog(page, 'Check this paragraph');
  await colour(page, '#ffbe6f');
  await tool(page, 'ft');
  await drag(page, [0.5, 0.27], [0.85, 0.27]);
  await typeInDialog(page, 'Text box with a note\non two lines');
  await colour(page, '#dc8add');
  await tool(page, 'sq');
  await drag(page, [0.1, 0.27], [0.3, 0.33]);
  await tool(page, 'ci');
  await drag(page, [0.32, 0.27], [0.45, 0.33]);
  await colour(page, '#f66151');
  await tool(page, 'ar');
  await drag(page, [0.55, 0.45], [0.85, 0.36]);
  await tool(page, 'sel');
  await colour(page, '#f9f06b');
  await page.click('#tabs button[data-tab="an"]');
  for (const t of ['Highlights', 'Underlines', 'Strikethroughs', 'Rectangles', 'Circles', 'Arrows'])
    await page.click(`#sbody .sbar .ib[title="${t}"]`);
}

const SCENES = {
  'annotations-light.png': { lang: 'en', scheme: 'light', setup: annotated },
  'welcome.png': { lang: 'en', scheme: 'light', setup: async () => {} },
  'spanish-dark.png': { lang: 'es', scheme: 'dark', setup: (page) => openPdf(page, 'outline.pdf') },
};

const browser = await chromium.launch();
for (const [file, s] of Object.entries(SCENES)) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1 });
  await openApp(page, { lang: s.lang, scheme: s.scheme });
  await s.setup(page);
  if (await page.locator('#view .page').count()) await waitRendered(page);
  await rest(page);
  await page.waitForTimeout(400);
  await page.addStyleTag({ content: '#msg{visibility:hidden!important}' });
  await page.screenshot({ path: join(OUT, file) });
  await page.close();
  console.log('Written', file);
}
await browser.close();
