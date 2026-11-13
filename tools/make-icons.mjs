// Builds the app icon in every size Linux needs (assets/icons/<size>x<size>.png) from assets/penfold.svg.
// Run with: npm run icons   (after changing the SVG). Chromium, from Playwright, paints the SVG.
import { chromium } from '@playwright/test';
import { readFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const SIZES = [16, 24, 32, 48, 64, 128, 256, 512];

// Paints an SVG (text) as a transparent PNG of size × size pixels
export async function renderSvg(page, svg, size, file) {
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(
    `<style>html,body{margin:0;background:transparent}img{display:block;width:${size}px;height:${size}px}</style>` +
      `<img src="data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}">`,
  );
  await page.waitForFunction(() => document.images[0].complete);
  return page.screenshot({ path: file, omitBackground: true });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const svg = readFileSync(join(ROOT, 'assets', 'penfold.svg'), 'utf8');
  const out = join(ROOT, 'assets', 'icons');
  mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  for (const s of SIZES) await renderSvg(page, svg, s, join(out, `${s}x${s}.png`));
  await browser.close();
  console.log('Icons written to', out, SIZES.join(', '));
}
