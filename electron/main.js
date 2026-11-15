// Penfold desktop app: Electron's main process.
// It shows index.html, unchanged, in one or more windows and adds what a desktop app is expected to do: open PDFs from
// the file manager or the command line (in an empty window, or a new one), or dropped on a window (in that window);
// one process for all windows; “New Window” from the dock; a question before a window with unsaved changes is
// closed; a remembered window size; the document's name in the title; links in the default browser; and none of the
// browser's own behaviour (navigation, reload, developer tools, extra windows, spell-check downloads).
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
  en: { cannotRead: 'Could not open “{name}”' },
  es: { cannotRead: 'No se pudo abrir «{name}»' },
};
function t(key, values = {}) {
  const langs = app.getPreferredSystemLanguages().map((l) => l.toLowerCase().split('-')[0]);
  const lang =
    langs.find((l) => l === 'es' || l === 'en') || (langs.some((l) => ['eu', 'ca', 'gl'].includes(l)) ? 'es' : 'en');
  return TEXTS[lang][key].replace(/\{(\w+)\}/g, (m, k) => (k in values ? values[k] : m));
}

// ---- One process for every window: a second launch (“Open with Penfold”, “New Window”) hands its request to this one
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  const windows = new Map(); // webContents id → this window's state (see createWindow)
  const grants = new Map(); // files a window may overwrite with “Save” (id → { file, owner: webContents id })
  let nextId = 1;
  let firstWindow = true;

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

  // ---- Window size and position, remembered between sessions (the last window closed is the one remembered)
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
  function saveState(win) {
    try {
      fs.mkdirSync(app.getPath('userData'), { recursive: true });
      fs.writeFileSync(stateFile(), JSON.stringify({ ...win.getNormalBounds(), maximized: win.isMaximized() }));
    } catch {
      // Not being able to remember the window is not worth bothering the user
    }
  }

  // ---- Opening a file in a window: it is read here and handed to the page as if it had been chosen with “Open PDF”
  // (the page asks penfoldDesktop.take() for it; see preload.js). The page asks first if its document has unsaved
  // changes. “Save” then writes back to the same file.
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

  async function openNext(w) {
    if (w.busy) return;
    w.busy = true;
    while (w.ready && w.queue.length && !w.win.isDestroyed()) {
      const file = w.queue.shift(),
        name = path.basename(file);
      let bytes;
      try {
        bytes = await fs.promises.readFile(file);
      } catch (err) {
        await dialog.showMessageBox(w.win, { type: 'error', message: t('cannotRead', { name }), detail: err.message });
        continue;
      }
      const id = nextId++;
      grants.set(id, { file, owner: w.id });
      w.handoff = { id, name, bytes: new Uint8Array(bytes) };
      await w.win.webContents.executeJavaScript(OPEN_IN_PAGE);
    }
    w.busy = false;
  }
  function openIn(w, file) {
    w.claimed = true;
    w.queue.push(file);
    if (w.win.isMinimized()) w.win.restore();
    w.win.focus();
    openNext(w);
  }
  // Is this window free for a PDF from the desktop? (no document open and none on its way)
  async function isEmpty(w) {
    if (w.claimed || w.win.isDestroyed()) return false;
    if (!w.ready) return true;
    try {
      return (await w.win.webContents.executeJavaScript('pages.length')) === 0;
    } catch {
      return false;
    }
  }
  // A PDF from the desktop opens in an empty window (the focused one first) or, if there is none, in a new window
  async function openFromDesktop(files) {
    for (const file of files) {
      const focused = BrowserWindow.getFocusedWindow(),
        list = [...windows.values()].sort((a, b) => (b.win === focused) - (a.win === focused));
      let target = null;
      for (const w of list)
        if (await isEmpty(w)) {
          target = w;
          break;
        }
      openIn(target || createWindow(), file);
    }
  }

  // ---- Closing: a window with unsaved changes asks first, with Penfold's own question (Save, Discard, Cancel)
  async function confirmClose(w) {
    if (!w.ready || w.win.isDestroyed()) return true;
    w.win.focus();
    try {
      return await w.win.webContents.executeJavaScript('confirmUnsaved()', true);
    } catch {
      return true; // a page that cannot answer has nothing it could save
    }
  }
  async function closeWindow(w) {
    if (w.asking) return;
    w.asking = true;
    const ok = await confirmClose(w);
    w.asking = false;
    if (ok && !w.win.isDestroyed()) {
      w.allowClose = true;
      w.win.close();
    }
  }
  // Quitting (Ctrl+Q) asks each window in turn; Cancel in any of them stops it
  async function quitAll() {
    for (const w of [...windows.values()]) {
      if (!(await confirmClose(w))) return;
      w.allowClose = true;
    }
    app.quit();
  }

  // ---- Messages from the pages (each window only gets its own files)
  const from = (e) => windows.get(e.sender.id);
  ipcMain.handle('penfold:take', (e) => {
    const w = from(e);
    if (!w) return null;
    const h = w.handoff;
    w.handoff = null;
    return h;
  });
  ipcMain.handle('penfold:write', async (e, id, bytes) => {
    const g = grants.get(id);
    if (!g || g.owner !== e.sender.id || !(bytes instanceof Uint8Array)) throw new Error('Not allowed');
    // Written to a temporary file first and then renamed, so a failure never leaves half a PDF
    const tmp = g.file + '.penfold-tmp';
    await fs.promises.writeFile(tmp, bytes);
    await fs.promises.rename(tmp, g.file);
  });
  // A PDF dropped on a window opens in that window
  ipcMain.on('penfold:open-path', (e, file) => {
    const w = from(e);
    if (w && typeof file === 'string' && file) openIn(w, file);
  });

  // While a document is open the title shows its name, as in other desktop apps: “file.pdf — Penfold”, with “• ” in
  // front while it has unsaved changes
  const TITLE_WATCH = `setInterval(() => {
    try {
      const t = pages.length ? (hasUnsavedChanges() ? '• ' : '') + fname + ' — Penfold' : 'Penfold';
      if (document.title !== t) document.title = t;
    } catch (e) {}
  }, 300)`;

  function createWindow() {
    const s = loadState(),
      // The first window goes where the last one was; the others are placed by the desktop
      place = firstWindow ? { x: s.x, y: s.y } : {};
    firstWindow = false;
    const win = new BrowserWindow({
      width: s.width || 1280,
      height: s.height || 860,
      ...place,
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
    const wc = win.webContents,
      w = { id: wc.id, win, ready: false, queue: [], handoff: null, claimed: false, busy: false, asking: false };
    windows.set(w.id, w);
    if (s.maximized) win.maximize();
    win.once('ready-to-show', () => win.show());
    win.on('close', (e) => {
      if (w.allowClose) return saveState(win);
      e.preventDefault();
      closeWindow(w);
    });
    win.on('closed', () => windows.delete(w.id));
    win.on('page-title-updated', (e, title) => {
      e.preventDefault();
      win.setTitle(/— Penfold$/.test(title) ? title : 'Penfold');
    });

    // The window never leaves Penfold: no navigation (e.g. a file dropped outside the drop zones) and no new windows,
    // except the PDF the app opens for printing when the browser refuses to print from a frame
    wc.on('will-navigate', (e) => e.preventDefault());
    // Penfold has already asked about unsaved changes when a window closes: the page's own browser warning is not shown
    wc.on('will-prevent-unload', (e) => e.preventDefault());
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
        quitAll();
      } else if (k === 'w') {
        e.preventDefault();
        win.close();
      }
    });
    wc.on('did-finish-load', async () => {
      await wc.executeJavaScript(TITLE_WATCH);
      w.ready = true;
      openNext(w);
    });

    win.loadFile(INDEX);
    return w;
  }

  // A second launch: its PDFs, a new window (“New Window” in the dock), or else the existing window comes forward
  app.on('second-instance', (e, argv, cwd) => {
    const files = filesFrom(argv, cwd);
    if (files.length) return openFromDesktop(files);
    if (argv.includes('--new-window') || !windows.size) return createWindow();
    const w = BrowserWindow.getFocusedWindow() || [...windows.values()].pop().win;
    if (w.isMinimized()) w.restore();
    w.focus();
  });
  app.whenReady().then(() => {
    Menu.setApplicationMenu(null);
    createWindow();
    openFromDesktop(filesFrom(process.argv));
  });
  app.on('window-all-closed', () => app.quit());
}
