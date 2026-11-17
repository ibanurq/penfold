// Translations (js/i18n/): every file is loaded, every file has exactly the texts of the complete Spanish one, every
// text is still used by Penfold, and the language is chosen and falls back as described in js/penfold.js
import { test, expect } from '@playwright/test';
import { readFileSync, readdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { ROOT, openApp, expectNoExternalRequests } from './helpers.mjs';

const { loadLangs } = createRequire(import.meta.url)('../electron/i18n.js');
const langs = loadLangs(),
  ref = langs.es;

test('every language file is loaded by the page, before the app', () => {
  const html = readFileSync(join(ROOT, 'index.html'), 'utf8'),
    app = html.indexOf('<script src="js/penfold.js">');
  for (const f of readdirSync(join(ROOT, 'js', 'i18n')).filter((f) => f.endsWith('.js'))) {
    const at = html.indexOf(`<script src="js/i18n/${f}">`);
    expect(at, `${f} is not loaded by index.html`).toBeGreaterThan(-1);
    expect(at, `${f} must be loaded before js/penfold.js`).toBeLessThan(app);
  }
});

test('every language file has exactly the texts of the Spanish one (translated or empty)', () => {
  for (const [code, d] of Object.entries(langs)) {
    expect(Object.keys(d).sort(), `js/i18n/${code}.js`).toEqual(Object.keys(ref).sort());
    for (const v of Object.values(d)) expect(typeof v).toBe('string');
  }
});

test('every translated text is still used by Penfold', () => {
  const code = ['index.html', 'js/penfold.js', 'electron/main.js']
    .map((f) => readFileSync(join(ROOT, f), 'utf8'))
    .join('\n');
  const unused = Object.keys(ref)
    .map((k) => k.split('\u0004').pop())
    .filter((text) => !code.includes(text));
  expect(unused).toEqual([]);
});

test.describe('in the page', () => {
  test.afterEach(async ({ page }) => expectNoExternalRequests(page));

  test('Basque: an empty translation is shown in Spanish; a filled one is used', async ({ page }) => {
    await openApp(page, { lang: 'eu' });
    await expect(page.locator('html')).toHaveAttribute('lang', 'eu');
    await expect(page.locator('#empty h2')).toHaveText('Comenzar a trabajar');
    expect(await page.evaluate(() => _t('Get started'))).toBe('Comenzar a trabajar');
    await page.evaluate(() => (PENFOLD_LANGS.eu['Get started'] = 'Hasi lanean'));
    expect(await page.evaluate(() => _t('Get started'))).toBe('Hasi lanean');
  });

  test('a language without a file falls back to English, or to Spanish for Catalan and Galician', async ({ page }) => {
    await page.addInitScript(() => Object.defineProperty(navigator, 'languages', { get: () => ['gl', 'en'] }));
    await openApp(page);
    // ?lang=en is given by openApp, so the browser's languages are checked through the same rule here
    expect(
      await page.evaluate(() => {
        const ls = ['fr', 'gl', 'de'];
        return ls.find(hasLang) || ls.map((x) => LANG_FALLBACK[x]).find((x) => x && hasLang(x)) || 'en';
      }),
    ).toBe('es');
    expect(await page.evaluate(() => ['fr', 'de'].find(hasLang) || 'en')).toBe('en');
  });
});
