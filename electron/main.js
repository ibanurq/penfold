// Penfold desktop app: Electron's main process.
// It shows index.html, unchanged, in a window and adds what a desktop app is expected to do: open PDFs from the file
// manager, the command line or by dropping them on the window; a single instance; a remembered window size; the
// document's name in the title; links in the default browser; and none of the browser's own behaviour (navigation,
// reload, developer tools, extra windows, spell-check downloads).
'use strict';
const { app, BrowserWindow, Menu, dialog, ipcMain, nativeTheme, screen, shell } = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const { fileURLToPath } = require('node:url');

const INDEX = path.join(__dirname, '..', 'index.html');

// Settings live in ~/.config/Penfold (the tests use a folder of their own, so they never touch the real one)
app.setName('Penfold');
if (process.env.PENFOLD_USER_DATA) app.setPath('userData', process.env.PENFOLD_USER_DATA);

// ---- Texts of this layer (the app itself has its own dictionary). Same rule as the app: Spanish for Spanish, Basque,
// Catalan and Galician, otherwise English.
const TEXTS = {
  en: {
    replace: 'Open “{name}”?',
    replaceDetail: 'The open document will be closed without saving its changes.',
    cancel: 'Cancel',
    open: 'Open',
    cannotRead: 'Could not open “{name}”',
  },
  es: {
    replace: '¿Abrir «{name}»?',
    replaceDetail: 'Se cerrará el documento abierto sin guardar sus cambios.',
    cancel: 'Cancelar',
    open: 'Abrir',
    cannotRead: 'No se pudo abrir «{name}»',
  },
};
function t(key, values = {}) {
  const langs = app.getPreferredSystemLanguages().map((l) => l.toLowerCase().split('-')[0]);
  const lang =
    langs.find((l) => l === 'es' || l === 'en') || (langs.some((l) => ['eu', 'ca', 'gl'].includes(l)) ? 'es' : 'en');
  return TEXTS[lang][key].replace(/\{(\w+)\}/g, (m, k) => (k in values ? values[k] : m));
}

// ---- One instance only: a second launch (e.g. “Open with Penfold” while it is open) hands its files to this one
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  let win = null;
  let pageReady = false;
  const queue = []; // files waiting to be opened
  let handoff = null; // the file being handed to the page right now
  const grants = new Map(); // files the page may overwrite with “Save” (id → path)
  let nextId = 1;

  // Files given on the command line. The menu entry (.desktop, “%U”) passes them as file:// addresses; a terminal
  // passes plain paths. Both are accepted.
  const filesFrom = (argv, cwd) =>
    argv
      .slice(1)
      .filter((a) => a && !a.startsWith('-'))
      .map((a) => (a.startsWith('file://') ? fileURLToPath(a) : path.resolve(cwd || process.cwd(), a)))
      .filter((f) => {
        try {
          return fs.statSync(f).isFile();
        } catch {
          return false;
        }
      });

  // ---- Window size and position, remembered between sessions
  const stateFile = () => path.join(app.getPath('userData'), 'window-state.json');
  function loadState() {
    try {
      const s = JSON.parse(fs.readFileSync(stateFile(), 'utf8'));
      const onScreen = screen.getAllDisplays().some(({ workArea: a }) => {
        return s.x < a.x + a.width && s.x + s.width > a.x && s.y < a.y + a.height && s.y + s.height > a.y;
      });
      return onScreen ? s : { width: s.width, height: s.height, maximized: s.maximized };
    } catch {
      return {};
    }
  }
  function saveState() {
    try {
      fs.mkdirSync(app.getPath('userData'), { recursive: true });
      fs.writeFileSync(stateFile(), JSON.stringify({ ...win.getNormalBounds(), maximized: win.isMaximized() }));
    } catch {
      // Not being able to remember the window is not worth bothering the user
    }
  }

  // ---- Opening a file: it is read here and handed to the page as if it had been chosen with “Open PDF”
  // (the page asks penfoldDesktop.take() for it; see preload.js). “Save” then writes back to the same file.
  const OPEN_IN_PAGE = `(async () => {
    const f = await window.penfoldDesktop.take();
    if (!f) return;
    const file = new File([f.bytes], f.name, { type: 'application/pdf' });
    const handle = {
      kind: 'file',
      name: f.name,
      getFile: async () => file,
      createWritable: async () => {
        const parts = [];
        return {
          write: async (d) => parts.push(d instanceof Blob ? d : new Blob([d])),
          close: async () => window.penfoldDesktop.write(f.id, new Uint8Array(await new Blob(parts).arrayBuffer())),
        };
      },
    };
    const picker = window.showOpenFilePicker;
    window.showOpenFilePicker = async () => {
      window.showOpenFilePicker = picker;
      return [handle];
    };
    document.getElementById('bOpen').click();
  })()`;

  async function openNext() {
    while (pageReady && queue.length) {
      const file = queue.shift();
      const name = path.basename(file);
      let bytes;
      try {
        bytes = await fs.promises.readFile(file);
      } catch (err) {
        await dialog.showMessageBox(win, { type: 'error', message: t('cannotRead', { name }), detail: err.message });
        continue;
      }
      if (await win.webContents.executeJavaScript('pages.length > 0')) {
        const { response } = await dialog.showMessageBox(win, {
          type: 'question',
          buttons: [t('cancel'), t('open')],
          defaultId: 1,
          cancelId: 0,
          message: t('replace', { name }),
          detail: t('replaceDetail'),
        });
        if (response !== 1) continue;
      }
      const id = nextId++;
      grants.set(id, file);
      handoff = { id, name, bytes: new Uint8Array(bytes) };
      await win.webContents.executeJavaScript(OPEN_IN_PAGE);
    }
  }
  function openFiles(files) {
    queue.push(...files);
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
    openNext();
  }

  // ---- Messages from the page (only from our window)
  const fromOurPage = (e) => win && e.sender === win.webContents;
  ipcMain.handle('penfold:take', (e) => {
    if (!fromOurPage(e)) return null;
    const h = handoff;
    handoff = null;
    return h;
  });
  ipcMain.handle('penfold:write', async (e, id, bytes) => {
    const file = fromOurPage(e) && grants.get(id);
    if (!file || !(bytes instanceof Uint8Array)) throw new Error('Not allowed');
    // Written to a temporary file first and then renamed, so a failure never leaves half a PDF
    const tmp = file + '.penfold-tmp';
    await fs.promises.writeFile(tmp, bytes);
    await fs.promises.rename(tmp, file);
  });
  ipcMain.on('penfold:open-path', (e, file) => {
    if (fromOurPage(e) && typeof file === 'string' && file) openFiles([file]);
  });

  // While a document is open the title shows its name, as in other desktop apps: “file.pdf — Penfold”
  const TITLE_WATCH = `setInterval(() => {
    try {
      const t = pages.length ? fname + ' — Penfold' : 'Penfold';
      if (document.title !== t) document.title = t;
    } catch (e) {}
  }, 300)`;

  function createWindow() {
    const s = loadState();
    win = new BrowserWindow({
      width: s.width || 1280,
      height: s.height || 860,
      x: s.x,
      y: s.y,
      minWidth: 720,
      minHeight: 480,
      show: false,
      title: 'Penfold',
      icon: path.join(__dirname, '..', 'assets', 'icons', '512x512.png'), // the installed app uses the system's icon
      backgroundColor: nativeTheme.shouldUseDarkColors ? '#242424' : '#f0f0f0',
      webPreferences: {
        preload: path.join(__dirname, 'preload.js'),
        contextIsolation: true,
        sandbox: true,
        nodeIntegration: false,
        spellcheck: false, // the spell-checker would download dictionaries from the internet
        plugins: true, // the built-in PDF viewer, used by Print
      },
    });
    if (s.maximized) win.maximize();
    win.once('ready-to-show', () => win.show());
    win.on('close', saveState);
    win.on('closed', () => (win = null));
    win.on('page-title-updated', (e, title) => {
      e.preventDefault();
      win.setTitle(/— Penfold$/.test(title) ? title : 'Penfold');
    });

    const wc = win.webContents;
    // The window never leaves Penfold: no navigation (e.g. a file dropped outside the drop zones) and no new windows,
    // except the PDF the app opens for printing when the browser refuses to print from a frame
    wc.on('will-navigate', (e) => e.preventDefault());
    wc.setWindowOpenHandler(({ url }) => {
      if (/^https?:\/\//.test(url)) {
        shell.openExternal(url);
        return { action: 'deny' };
      }
      if (url.startsWith('blob:')) {
        return {
          action: 'allow',
          overrideBrowserWindowOptions: { autoHideMenuBar: true, webPreferences: { sandbox: true, plugins: true } },
        };
      }
      return { action: 'deny' };
    });
    // Desktop shortcuts: Ctrl+Q quits, Ctrl+W closes the window. (Without a menu, the browser's reload, zoom and
    // developer-tools shortcuts do not exist.)
    wc.on('before-input-event', (e, input) => {
      if (input.type !== 'keyDown' || !(input.control || input.meta) || input.alt || input.shift) return;
      const k = input.key.toLowerCase();
      if (k === 'q') {
        e.preventDefault();
        app.quit();
      } else if (k === 'w') {
        e.preventDefault();
        win.close();
      }
    });
    wc.on('did-finish-load', async () => {
      await wc.executeJavaScript(TITLE_WATCH);
      pageReady = true;
      openNext();
    });

    win.loadFile(INDEX);
  }

  app.on('second-instance', (e, argv, cwd) => openFiles(filesFrom(argv, cwd)));
  app.whenReady().then(() => {
    Menu.setApplicationMenu(null);
    createWindow();
    openFiles(filesFrom(process.argv));
  });
  app.on('window-all-closed', () => app.quit());
}
