// ESLint: reports possible mistakes in Penfold's own code (npm run lint). It does not change anything.
import js from '@eslint/js';
import globals from 'globals';

export default [
  { ignores: ['vendor/', 'node_modules/', 'test-results/', 'playwright-report/', 'dist/', 'notas_privadas/'] },
  js.configs.recommended,
  {
    // The app: a classic browser script that uses the libraries loaded before it
    files: ['js/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'script',
      globals: { ...globals.browser, pdfjsLib: 'readonly', PDFLib: 'readonly' },
    },
    rules: {
      // The app deliberately ignores some errors with an empty catch (e.g. storage not available)
      'no-empty': ['error', { allowEmptyCatch: true }],
      'no-unused-vars': ['error', { caughtErrors: 'none' }],
    },
  },
  {
    // The desktop app (Electron): CommonJS; preload.js also sees the page's window
    files: ['electron/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'commonjs',
      globals: { ...globals.node, ...globals.browser },
    },
  },
  {
    // Tests, scripts and configuration: Node.js modules. Code inside page.evaluate() runs in the app's page.
    files: ['**/*.mjs'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: {
        ...globals.node,
        ...globals.browser,
        pdfjsLib: 'readonly',
        PDFLib: 'readonly',
        // The app's global state, read by the tests inside page.evaluate()
        docs: 'readonly',
        pages: 'readonly',
        bms: 'readonly',
        cur: 'readonly',
        handle: 'readonly',
        annBusy: 'readonly',
        prnFrame: 'readonly',
        fname: 'readonly',
        hasUnsavedChanges: 'readonly',
        _t: 'readonly',
        PENFOLD_LANGS: 'readonly',
        hasLang: 'readonly',
        LANG_FALLBACK: 'readonly',
      },
    },
  },
];
