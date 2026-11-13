// Automatic tests: Playwright drives a headless Chromium through the real app.
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: 'tests',
  timeout: 60_000,
  expect: { timeout: 10_000, toHaveScreenshot: { maxDiffPixels: 0, animations: 'disabled', caret: 'hide' } },
  fullyParallel: true,
  reporter: [['list'], ['html', { open: 'never' }]],
  snapshotPathTemplate: '{testDir}/screenshots/{testFilePath}/{arg}{ext}',
  use: {
    browserName: 'chromium',
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: 1,
    colorScheme: 'light',
    locale: 'en-GB',
    timezoneId: 'Europe/Madrid',
  },
});
