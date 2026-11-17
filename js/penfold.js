// Penfold: a PDF reader and editor that runs in the browser (and, wrapped by Electron, as a desktop app).
// pdf.js (pdfjsLib) reads and draws the PDFs; pdf-lib (PDFLib) writes the saved files. No build step: this is a
// classic script loaded by index.html after the libraries and the translations.
//
// $ finds an element by CSS selector; WORKER_SRC is pdf.js's worker, which parses PDFs in the background
const $ = (s) => document.querySelector(s),
  WORKER_SRC = 'vendor/pdf.js-3.11.174/pdf.worker.min.js';
// Opened as a file (file://) the browser refuses fetch(), so the worker is given by its path straight away
if (location.protocol == 'file:') pdfjsLib.GlobalWorkerOptions.workerSrc = WORKER_SRC;
else
  fetch(WORKER_SRC)
    .then((r) => r.blob())
    .then((b) => (pdfjsLib.GlobalWorkerOptions.workerSrc = URL.createObjectURL(b)))
    .catch(() => (pdfjsLib.GlobalWorkerOptions.workerSrc = WORKER_SRC));
// ---- Language ----
// English is the source language: every string in this file is English. The translations live in js/i18n/, one file
// per language, loaded before this script: each one adds PENFOLD_LANGS.<code> = { 'English text': 'translation' } (a
// key may carry a context prefix, "ctx\u0004text", when two uses of one English text need different translations).
// The language comes from ?lang=<code>, otherwise from the browser's preferred languages: the first one that is English
// or has a file. A missing or empty translation falls back to the language's fallback (Basque, Catalan and Galician
// fall back to Spanish), and then to English.
const LANGS = window.PENFOLD_LANGS || {},
  LANG_FALLBACK = { eu: 'es', ca: 'es', gl: 'es' },
  hasLang = (x) => x === 'en' || Object.prototype.hasOwnProperty.call(LANGS, x);
const LANG = (() => {
  try {
    const q = new URLSearchParams(location.search).get('lang');
    if (q && hasLang(q)) return q;
  } catch (e) {}
  const ls = (
    navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || 'en']
  ).map((x) => String(x).toLowerCase().split('-')[0]);
  return ls.find(hasLang) || ls.map((x) => LANG_FALLBACK[x]).find((x) => x && hasLang(x)) || 'en';
})();
document.documentElement.lang = LANG;
// The translation of a key in the chosen language, or in its fallback; undefined when there is none (English is shown)
function tKey(k) {
  for (let l = LANG; l && l !== 'en'; l = LANG_FALLBACK[l]) {
    const d = LANGS[l],
      v = d && Object.prototype.hasOwnProperty.call(d, k) ? d[k] : undefined;
    if (typeof v === 'string' && v !== '') return v;
  }
}
// _t translates a string ({name} placeholders are filled from v; c is the optional context). _n picks the singular or plural form for n.
const _t = (s, v, c) => {
  const r = tKey(c ? c + '\u0004' + s : s) ?? s;
  return v ? r.replace(/\{(\w+)\}/g, (m, k) => (k in v ? v[k] : m)) : r;
};
const _n = (n, one, many) => _t(n == 1 ? one : many, { n });
// Translates the static text (text nodes and title / placeholder attributes) of an element: the page itself and every dialog built from HTML.
function i18nApply(root) {
  if (LANG == 'en') return;
  const tr = (x) => {
    const m = x.match(/^(\s*)([\s\S]*?)(\s*)$/);
    const t = m[2] && tKey(m[2]);
    return t !== undefined && t !== '' ? m[1] + t + m[3] : x;
  };
  [root, ...root.querySelectorAll('*')].forEach((el) => {
    if (/^(SCRIPT|STYLE)$/.test(el.tagName)) return;
    ['title', 'placeholder'].forEach((a) => {
      const v = el.getAttribute(a);
      const t = v !== null ? tKey(v) : undefined;
      if (t !== undefined) el.setAttribute(a, t);
    });
    el.childNodes.forEach((n) => {
      if (n.nodeType == 3) {
        const v = tr(n.nodeValue);
        if (v !== n.nodeValue) n.nodeValue = v;
      }
    });
  });
}
i18nApply(document.body);
// ---- App state ----
// docs: the open PDF files ({ bytes, pdf, enc }); pages: every page shown, in order ({ doc, idx, annots, rot… }), so
// pages from several files can be mixed and reordered. fileHandle/fileName: where “Save” writes. tool: the active
// toolbar tool (sel, hl, ul, so, note, ft, sq, ci, ar); annotColor: the chosen colour; scale: the zoom;
// panelTab: the side panel's tab (th = pages, bm = bookmarks, an = annotations); currentPage: the page in view
let docs = [],
  pages = [],
  fileHandle = null,
  fileName = _t('document.pdf'),
  tool = 'sel',
  annotColor = '#f9f06b',
  scale = 1.3,
  panelTab = 'th',
  lastPanelTab = 'th',
  bookmarks = [],
  currentPage = 0;
// Drag and drop in the side panel, the bookmark just added (shown highlighted once) and the two-page view
let draggedBookmarks = [],
  draggedPages = [],
  flashBookmark = null,
  twoPageView = false;
// Multiple selection in the side panel; the anchors are where a Shift+click range starts
const selectedPages = new Set(),
  selectedBookmarks = new Set();
let pageAnchor = -1,
  bookmarkAnchor = null;

// Annotation colours (GNOME palette): n is the name shown as tooltip, p the colour
const PALETTE = [
  { n: 'Yellow', p: '#f9f06b' },
  { n: 'Green', p: '#8ff0a4' },
  { n: 'Blue', p: '#99c1f1' },
  { n: 'Orange', p: '#ffbe6f' },
  { n: 'Red', p: '#f66151' },
  { n: 'Lilac', p: '#dc8add' },
];
// Palette for bookmarks: the 6 colours plus 2 more (4 columns × 2 rows, the extra one on the right of each row)
const BOOKMARK_PALETTE = [
  PALETTE[0],
  PALETTE[1],
  PALETTE[2],
  { n: 'Grey', p: '#606971' },
  PALETTE[3],
  PALETTE[4],
  PALETTE[5],
  { n: 'Burgundy', p: '#ad182e' },
];
// Single palette: there is no separate deep tone any more. The function is kept so existing uses stay untouched.
const deep = (c) => c;
// Text box: measurements in PDF units (fs = font size, pad = inner padding, bw = border width, w = default width)
const TEXT_BOX = { fs: 11, pad: 6, bw: 1, lh: 1.2, w: 200 };
// Line width of rectangles, circles and arrows, in PDF units
const SHAPE_STROKE = 1;
// Comment icon (Lucide message-square-text): black outline, filled with the annotation's colour. Same drawing on screen and in the PDF.
const NOTE_STROKE = 1.5;
const noteIconSvg = (c) =>
  '<svg viewBox="2 2 20 20"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" fill="' +
  c +
  '" stroke="#000" stroke-width="' +
  NOTE_STROKE +
  '" stroke-linecap="round" stroke-linejoin="round"/><path d="M13 8H7M17 12H7" fill="none" stroke="#000" stroke-width="' +
  NOTE_STROKE +
  '" stroke-linecap="round"/></svg>';
// Mixes colour c with white: t = 1 keeps the colour, t = 0 gives white
const tint = (c, t) =>
  '#' +
  [1, 3, 5]
    .map((i) =>
      Math.round(255 * (1 - t) + parseInt(c.substr(i, 2), 16) * t)
        .toString(16)
        .padStart(2, '0'),
    )
    .join('');
// The colour buttons of the toolbar
$('#sws').innerHTML = PALETTE.map(
  (x) =>
    `<button class="sw${x.p == annotColor ? ' on' : ''}" data-c="${x.p}" title="${_t(x.n)}" style="background:${x.p}"></button>`,
).join('');
// Short message at the bottom of the window, hidden after 4.5 s
let messageTimer;
const showMessage = (text) => {
  const box = $('#msg');
  box.textContent = text;
  box.style.display = 'block';
  clearTimeout(messageTimer);
  messageTimer = setTimeout(() => (box.style.display = 'none'), 4500);
};
// ---- Toolbar ----
// Tool buttons: the chosen tool is marked and set as a class on <body> (the CSS changes the cursor and what can be clicked)
document.querySelectorAll('[data-t]').forEach(
  (b) =>
    (b.onclick = () => {
      tool = b.dataset.t;
      document.querySelectorAll('[data-t]').forEach((x) => x.classList.toggle('on', x == b));
      document.body.className = 'tool-' + tool;
    }),
);
// Colour buttons: the chosen colour is used by the next annotation
document.querySelectorAll('.sw').forEach(
  (b) =>
    (b.onclick = () => {
      annotColor = b.dataset.c;
      document.querySelectorAll('.sw').forEach((x) => x.classList.toggle('on', x == b));
    }),
);
// Zoom in and out by 20 %, between 30 % and 400 %
$('#zi').onclick = () =>
  zoomTo(() => {
    scale = Math.min(4, scale + 0.2);
  });
$('#zo').onclick = () =>
  zoomTo(() => {
    scale = Math.max(0.3, scale - 0.2);
  });
// Side panel tabs (Pages, Bookmarks, Annotations)
document.querySelectorAll('#tabs button').forEach(
  (b) =>
    (b.onclick = () => {
      panelTab = b.dataset.tab;
      renderSide();
      followThumb(true);
    }),
);

// ---- Pages and bookmarks ----
// Rotates the pages in list by dir degrees (90 or -90); thumbnails are redrawn
function rotatePages(list, dir) {
  list.forEach((p) => {
    p.rot = ((p.rot || 0) + dir + 360) % 360;
    p.thumb = null;
  });
  renderSide();
  zoomTo(() => {});
}
// Bookmarks form a tree: each one is { title, page, dd, color, bold, italic, open, items: [sub-bookmarks] }.
// bookmarkPath gives the chain of bookmarks from the top level down to target (null if it is not in list)
const bookmarkPath = (list, target) => {
  for (const x of list) {
    if (x === target) return [x];
    const rest = bookmarkPath(x.items, target);
    if (rest) return [x, ...rest];
  }
  return null;
};
// Expands every bookmark above target, so it can be seen
const openAncestors = (target) => (bookmarkPath(bookmarks, target) || []).slice(0, -1).forEach((x) => (x.open = true));
// Adds a bookmark: titled with the selected text (and pointing to its page) or, with nothing selected, asked for and
// pointing to the current page. It goes after the last bookmark that points to an earlier or the same page
async function addBookmark() {
  let title = null,
    pageIndex = currentPage;
  const sel = getSelection();
  if (sel && sel.rangeCount && !sel.isCollapsed) {
    const n = sel.getRangeAt(0).startContainer,
      el = (n.nodeType == 1 ? n : n.parentElement).closest('.page');
    if (el) {
      const t = sel.toString().replace(/\s+/g, ' ').trim();
      if (t) {
        title = t.length > 150 ? t.slice(0, 150) + '…' : t;
        pageIndex = +el.dataset.i;
      }
    }
  }
  if (!title) {
    title = await promptDialog(
      _t('Add bookmark'),
      _t('Bookmark title:'),
      _t('Page {n}', { n: pageIndex + 1 }),
      _t('Add'),
    );
    if (!title) return;
  }
  const newBm = { title, page: pages[pageIndex], items: [] },
    flat = [];
  const collect = (l) =>
    l.forEach((x) => {
      flat.push(x);
      collect(x.items);
    });
  collect(bookmarks);
  let prevBm = null;
  flat.forEach((x) => {
    if (pages.indexOf(x.page) <= pageIndex) prevBm = x;
  });
  if (!prevBm) bookmarks.unshift(newBm);
  else if (prevBm.items.length) {
    prevBm.items.unshift(newBm);
    prevBm.open = true;
    openAncestors(prevBm);
  } else {
    const place = findBookmark(bookmarks, prevBm);
    place.list.splice(place.i + 1, 0, newBm);
    openAncestors(prevBm);
  }
  flashBookmark = newBm;
  renderSide();
}
// True if bookmark b is a or is under a (a bookmark cannot be dropped inside itself)
const isInSubtree = (a, b) => a === b || a.items.some((c) => isInSubtree(c, b));
// The bookmarks dragged together with bm: the selected ones if bm is selected (without those whose parent is also
// selected, as they move with it), otherwise bm alone
const bookmarksToDrag = (bm) => {
  if (!(selectedBookmarks.has(bm) && selectedBookmarks.size > 1)) return [bm];
  const flat = [];
  const collect = (l) =>
    l.forEach((x) => {
      flat.push(x);
      collect(x.items);
    });
  collect(bookmarks);
  return flat.filter(
    (n) =>
      selectedBookmarks.has(n) &&
      !(bookmarkPath(bookmarks, n) || []).slice(0, -1).some((a) => selectedBookmarks.has(a)),
  );
};
// Takes bookmark bm out of the tree; true if it was found
const removeBookmark = (list, bm) => {
  const i = list.indexOf(bm);
  if (i >= 0) {
    list.splice(i, 1);
    return true;
  }
  return list.some((x) => removeBookmark(x.items, bm));
};
// Where bookmark target is: { list, i } with list being the array that holds it
const findBookmark = (list, target) => {
  const i = list.indexOf(target);
  if (i >= 0) return { list: list, i };
  for (const x of list) {
    const r = findBookmark(x.items, target);
    if (r) return r;
  }
};
// PDF destinations (/XYZ, /FitH…): name + numeric arguments (null = no value). Kept when the outline is read and written back unchanged on save.
const DEST_ARGS = { XYZ: 3, Fit: 0, FitH: 1, FitV: 1, FitR: 4, FitB: 0, FitBH: 1, FitBV: 1 };
const isValidDest = (dest) =>
  !!dest &&
  Object.prototype.hasOwnProperty.call(DEST_ARGS, dest.n) &&
  Array.isArray(dest.a) &&
  dest.a.length == DEST_ARGS[dest.n] &&
  dest.a.every((v) => v === null || (typeof v == 'number' && isFinite(v)));
const destFromPdfJs = (pdfDest) => {
  const kind = pdfDest && pdfDest[1] && pdfDest[1].name;
  if (typeof kind != 'string' || !Object.prototype.hasOwnProperty.call(DEST_ARGS, kind)) return null;
  const args = pdfDest.slice(2, 2 + DEST_ARGS[kind]).map((v) => (typeof v == 'number' && isFinite(v) ? v : null));
  while (args.length < DEST_ARGS[kind]) args.push(null);
  return { n: kind, a: args };
};
// Height (in PDF points) a destination points to; null if it only names the page
const destY = (dest) =>
  !isValidDest(dest)
    ? null
    : dest.n == 'XYZ'
      ? dest.a[1]
      : dest.n == 'FitH' || dest.n == 'FitBH'
        ? dest.a[0]
        : dest.n == 'FitR'
          ? dest.a[3]
          : null;
// Copy of a bookmark tree with only the bookmarks that point to one of the pages in keep; the sub-bookmarks of a
// removed one move up into its place
const pruneBookmarks = (list, keep = pages) =>
  list.flatMap((bm) =>
    bm.page && keep.includes(bm.page)
      ? [{ ...bm, items: pruneBookmarks(bm.items, keep) }]
      : pruneBookmarks(bm.items, keep),
  );
// Colour of a bookmark from pdf.js ([r, g, b], 0-255) as #rrggbb; black or none gives null (the default colour)
const rgbToHex = (rgb) =>
  rgb && (rgb[0] || rgb[1] || rgb[2])
    ? '#' + [rgb[0], rgb[1], rgb[2]].map((v) => v.toString(16).padStart(2, '0')).join('')
    : null;
// Converts the outline (bookmarks) that pdf.js reads from document docIndex into Penfold's bookmark tree
async function convertOutline(items, docIndex) {
  const out = [];
  for (const it of items) {
    let page = null,
      dest = null;
    try {
      let pdfDest = it.dest;
      if (typeof pdfDest == 'string') pdfDest = await docs[docIndex].pdf.getDestination(pdfDest);
      const pageIdx = await docs[docIndex].pdf.getPageIndex(pdfDest[0]);
      page = pages.find((p) => p.doc == docIndex && p.idx == pageIdx) || null;
      dest = destFromPdfJs(pdfDest);
    } catch (e) {}
    out.push({
      title: it.title,
      page: page,
      dd: dest,
      color: rgbToHex(it.color),
      bold: !!it.bold,
      italic: !!it.italic,
      items: await convertOutline(it.items || [], docIndex),
    });
  }
  return out;
}
// ---- Opening files ----
// Asks for a PDF. Chromium-based browsers give a handle, so “Save” can write back into the same file; other browsers
// give only the file (handle = null)
async function pickFile() {
  if (window.showOpenFilePicker) {
    const [handle] = await showOpenFilePicker({ types: [{ accept: { 'application/pdf': ['.pdf'] } }] });
    return { h: handle, f: await handle.getFile() };
  }
  return new Promise((resolve) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.pdf';
    input.onchange = () => resolve({ h: null, f: input.files[0] });
    input.click();
  });
}
// Protected (encrypted) PDFs: pdf.js can read them, but pdf-lib cannot decrypt them, so anything built from them comes out broken.
// pdf.js reports the encryption in its document info; if this pdf.js did not report it, pdf-lib is asked (it detects it, though it cannot decrypt).
async function isProtected(pdf, bytes) {
  try {
    const { info } = await pdf.getMetadata();
    if (info && 'EncryptFilterName' in info) return !!info.EncryptFilterName;
  } catch (e) {}
  try {
    return (await PDFLib.PDFDocument.load(bytes, { ignoreEncryption: true, updateMetadata: false })).isEncrypted;
  } catch (e) {
    return false;
  }
}
// While a protected PDF is open, Save, Save As…, Print and Extract are disabled
const isLocked = () => docs.some((d) => d && d.enc);
// Warning sign (Lucide triangle-alert): yellow fill, black outline and exclamation mark
const WARN_SVG =
  '<svg viewBox="0 0 24 24" role="img" aria-label="' +
  _t('Protected PDF') +
  '"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" fill="#f6d32d" stroke="#000" stroke-width="1.8" stroke-linejoin="round"/><path d="M12 9v4M12 17h.01" fill="none" stroke="#000" stroke-width="2.2" stroke-linecap="round"/></svg>';
// Text of the protected-PDF notice
const lockText = () =>
  _t(
    'This PDF is protected. Any changes made to it cannot be saved. It cannot be printed and pages cannot be extracted either.',
  );
// The notice shown when a protected PDF is opened: a dialogue with the warning sign as its title
function protectedNotice() {
  choiceDialog('', lockText(), [[_t('OK'), 'ok', true]]);
  const title = document.querySelector('#dlg2 h3');
  if (title) {
    title.innerHTML = WARN_SVG;
    title.className = 'warn';
  }
  const text = document.querySelector('#dlg2 .box>div');
  if (text) text.style.textAlign = 'center';
  const okButton = document.querySelector('#dlg2 button.on');
  if (okButton) okButton.focus();
}
// Reminder while a protected PDF is open: the warning sign stays fixed at the top-left corner of the viewer; hovering it shows the notice
function lockBadge() {
  const badge = $('#lockw'),
    on = isLocked();
  badge.style.display = on ? '' : 'none';
  if (!on) return;
  if (!badge.firstChild) badge.innerHTML = WARN_SVG;
  badge.dataset.text = lockText();
  const view = $('#view').getBoundingClientRect();
  badge.style.left = view.left + 10 + 'px';
  badge.style.top = view.top + 10 + 'px';
}
// Every PDF is opened with isEvalSupported:false (here, in insertPdf and in the Merge dialogue): pdf.js 3.11 could
// otherwise run JavaScript hidden in a crafted font (CVE-2024-4367). Glyphs are then drawn without compiled code; same result.
// Reads a PDF file and adds it to docs, and its pages at the end of pages; gives its index in docs
async function loadPdf(file) {
  const bytes = await file.arrayBuffer(),
    pdf = await pdfjsLib.getDocument({ data: bytes.slice(0), isEvalSupported: false }).promise;
  const docIndex = docs.push({ bytes, pdf, enc: await isProtected(pdf, bytes) }) - 1;
  for (let i = 0; i < pdf.numPages; i++)
    pages.push({ doc: docIndex, idx: i, annots: [], thumb: null, rot: 0, loaded: false });
  return docIndex;
}
// Replaces the open document with file (handle: where “Save” writes, or null)
async function openFile(handle, file) {
  docs = [];
  pages = [];
  selectedPages.clear();
  selectedBookmarks.clear();
  pageAnchor = -1;
  bookmarkAnchor = null;
  fileHandle = handle;
  fileName = file.name;
  const docIndex = await loadPdf(file);
  bookmarks = pruneBookmarks(await convertOutline((await docs[docIndex].pdf.getOutline()) || [], docIndex));
  markSaved();
  panelTab = bookmarks.length ? 'bm' : 'th';
  onDocumentReady();
  if (docs[docIndex].enc) protectedNotice();
}
// Open PDF: the question about unsaved changes comes first, before choosing the file, so no work is done twice
$('#bOpen').onclick = async () => {
  try {
    if (!(await confirmUnsaved())) return;
    const { h: handle, f: file } = await pickFile();
    await openFile(handle, file);
  } catch (e) {
    if (e.name != 'AbortError') showMessage('Error: ' + e.message);
  }
};
// A PDF handed over by the desktop app (“Open with”, or dropped on the window): the same question, then it opens.
// Called from electron/main.js.
/* exported openFromDesktop */
async function openFromDesktop(handle) {
  try {
    if (!(await confirmUnsaved())) return;
    await openFile(handle, await handle.getFile());
  } catch (e) {
    showMessage('Error: ' + e.message);
  }
}
// Shows or hides the side panel (and the bar that resizes it)
function showPanel(visible) {
  $('#side').style.display = $('#rs').style.display = visible ? '' : 'none';
  $('#bPanel').classList.toggle('on', visible);
  if (visible) followThumb(true);
}
// Panel button: the pages keep their zoom relative to the new width of the viewer
$('#bPanel').onclick = () => {
  const w0 = $('#view').clientWidth;
  showPanel($('#side').style.display == 'none');
  reflowOnWidth(w0);
};
showPanel(false);
// Toolbar controls that are no use until a PDF is open (Open, Merge and the main menu are always enabled)
const NEED_PDF = '#bPanel,.ib[data-t],.sw,#pg,#zo,#zi,#fw,#fp,#two';
document.querySelectorAll(NEED_PDF).forEach((b) => (b.disabled = true));
// Called once a document is open: enables the toolbar, shows the panel and the pages, and loads the annotations
function onDocumentReady() {
  ['#bSave', '#bSaveAs', '#bPrint', '#bFind'].forEach((s) => ($(s).disabled = s != '#bFind' && isLocked()));
  document.querySelectorAll(NEED_PDF).forEach((b) => (b.disabled = false));
  showPanel(true);
  lockBadge();
  renderSide();
  fitOnOpen();
  loadAllAnnots();
  if ($('#sb').style.display == 'flex') runFind();
}

// ---- Pages panel (thumbnails) ----
// Draws a small image of the page (once; kept in page.thumb until the page is rotated)
async function thumbnail(page) {
  if (page.thumb) return page.thumb;
  const pdfPage = await docs[page.doc].pdf.getPage(page.idx + 1),
    viewport = pdfPage.getViewport({ scale: 0.3, rotation: (pdfPage.rotate + (page.rot || 0)) % 360 }),
    canvas = document.createElement('canvas');
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  await pdfPage.render({ canvasContext: canvas.getContext('2d'), viewport: viewport }).promise;
  return (page.thumb = canvas.toDataURL());
}

// Pages are drawn only when they come near the visible area (600 px before), so long PDFs open fast
const pageObserver = new IntersectionObserver(
  (entries) =>
    entries.forEach((e) => {
      if (e.isIntersecting && !e.target._done) {
        e.target._done = 1;
        paint(e.target);
      }
    }),
  { root: null, rootMargin: '600px' },
);
// Same for thumbnails; pages in portrait get the class pt and their aspect ratio, to keep the cells even
const thumbObserver = new IntersectionObserver(
  (entries) =>
    entries.forEach((e) => {
      if (e.isIntersecting && !e.target._done) {
        e.target._done = 1;
        thumbnail(e.target._p).then((url) => {
          const el = e.target,
            img = el.querySelector('img');
          img.onload = () => {
            const ratio = img.naturalWidth / img.naturalHeight;
            if (ratio > 0 && ratio < 0.999) {
              el.style.setProperty('--ar', ratio.toFixed(4));
              el.classList.add('pt');
            }
          };
          img.src = url;
        });
      }
    }),
  { root: null, rootMargin: '600px' },
);

// Thumbnails: a cell never exceeds THUMB_MAX_W px in width (the same maximum zoom with 1, 2, 3 or 4 columns).
// Just enough columns are used to satisfy that, up to THUMB_MAX_COLS at most; the panel's maximum width follows from that cap.
const THUMB_MAX_W = 310,
  THUMB_GAP = 10,
  THUMB_MAX_COLS = 4,
  SCROLLBAR_W = 14;
// Minimum width of the side panel: so the Bookmarks tab bar (left 54 + centre 120 + right 54, symmetrical, + 6) always fits on one row
const SIDE_MIN = 2 * 54 + 120 + 6 + 16 + 1 + SCROLLBAR_W;
const panelMaxWidth = () =>
  Math.min(THUMB_MAX_COLS * THUMB_MAX_W + (THUMB_MAX_COLS - 1) * THUMB_GAP + 16 + SCROLLBAR_W + 1, innerWidth - 160);
// Number of thumbnail columns for the current panel width
function updateThumbColumns() {
  const body = $('#sbody'),
    avail = body.clientWidth - 16;
  if (avail <= 0) return;
  const cols = Math.max(1, Math.min(THUMB_MAX_COLS, Math.ceil((avail + THUMB_GAP) / (THUMB_MAX_W + THUMB_GAP))));
  if (body.dataset.cols != cols) {
    body.dataset.cols = cols;
    body.style.setProperty('--cols', cols);
  }
}
// Top bar shared by the panels (Bookmarks, Pages and Annotations): grey background and three zones (left, centre, right)
function panelBar() {
  const row = document.createElement('div');
  row.className = 'sbw';
  row.style.cssText =
    'position:sticky;top:-8px;margin-top:-8px;margin-bottom:8px;padding-top:8px;background:var(--pane);z-index:10';
  const bar = document.createElement('div');
  bar.className = 'sbar';
  row.appendChild(bar);
  const makeButton = (ico, tip, fn) => {
    const b = document.createElement('button');
    b.className = 'ib';
    b.title = tip;
    b.innerHTML = '<svg viewBox="0 0 24 24">' + ico + '</svg>';
    b.onmousedown = (ev) => ev.preventDefault();
    b.onclick = (ev) => {
      ev.stopPropagation();
      if (!b.disabled) fn();
    };
    return b;
  };
  const addGroup = (cls, ...buttons) => {
    const g = document.createElement('div');
    g.className = 'g' + (cls ? ' ' + cls : '');
    g.append(...buttons);
    bar.appendChild(g);
  };
  return { row, makeButton, addGroup };
}
// Annotations: which types are listed (comments and text boxes by default)
const listedAnnotTypes = { note: true, ft: true, hl: false, ul: false, so: false, sq: false, ci: false, ar: false };
// Pages: updates the state of the bar buttons when the selection changes, without redrawing the panel
let updatePagesBar = null;
// ---- Side panel ----
// Redraws the side panel for the current tab: annotations (an), bookmarks (bm) or pages (th)
function renderSide() {
  const body = $('#sbody');
  const isSameTab = lastPanelTab === panelTab;
  const prevScroll = isSameTab ? body.scrollTop : 0;
  lastPanelTab = panelTab;
  document.querySelectorAll('#tabs button').forEach((b) => b.classList.toggle('on', b.dataset.tab == panelTab));
  body.innerHTML = '';
  body.style.scrollbarGutter = panelTab == 'th' ? 'stable' : '';
  updateThumbColumns();
  // Annotations tab: a list grouped by type, each item with its colour, text and page; a click goes to it
  if (panelTab == 'an') {
    const TYPES = [
        ['hl', _t('Highlights')],
        ['ul', _t('Underlines')],
        ['so', _t('Strikethroughs')],
        ['note', _t('Comments')],
        ['ft', _t('Text boxes')],
        ['sq', _t('Rectangles')],
        ['ci', _t('Circles')],
        ['ar', _t('Arrows')],
      ],
      groups = { note: [], ft: [], hl: [], ul: [], so: [], sq: [], ci: [], ar: [] };
    const ICONS = {
      note: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><path d="M13 8H7"/><path d="M17 12H7"/>',
      ft: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="m8 17 4-10 4 10"/><path d="M9.5 14h5"/>',
      hl: '<path d="m9 11-6 6v3h9l3-3"/><path d="m22 12-4.6 4.6a2 2 0 0 1-2.8 0l-5.2-5.2a2 2 0 0 1 0-2.8L14 4"/>',
      ul: '<path d="M7 4v7a5 5 0 0 0 10 0V4M5 20h14"/>',
      so: '<path d="M16 4H9a3 3 0 0 0-2.83 4"/><path d="M14 12a4 4 0 0 1 0 8H6"/><line x1="4" y1="12" x2="20" y2="12"/>',
      sq: '<rect width="18" height="18" x="3" y="3" rx="2"/>',
      ci: '<circle cx="12" cy="12" r="10"/>',
      ar: '<path d="M7 17 17 7"/><path d="M7 7h10v10"/>',
    };
    // Top bar: one button per annotation type (active = listed)
    const bar = panelBar();
    const typeButtons = [];
    TYPES.forEach(([t, title], i) => {
      if (i == 3 || i == 5) {
        const s = document.createElement('span');
        s.className = 'sep';
        s.style.margin = '0';
        typeButtons.push(s);
      }
      const b = bar.makeButton(ICONS[t], title, () => {
        listedAnnotTypes[t] = !listedAnnotTypes[t];
        renderSide();
      });
      b.classList.toggle('on', listedAnnotTypes[t]);
      typeButtons.push(b);
    });
    bar.addGroup('m', ...typeButtons);
    bar.row.querySelector('.g.m').style.gap = '4px';
    body.appendChild(bar.row);
    // Position of an annotation on its page (top and left, in PDF units), to sort each group in reading order
    const yOf = (a) =>
        a.quads
          ? Math.max(...a.quads.flatMap((q) => [q[1], q[3], q[5], q[7]]))
          : a.y2 !== undefined
            ? Math.max(a.y, a.y2)
            : a.y,
      xOf = (a) =>
        a.quads
          ? Math.min(...a.quads.flatMap((q) => [q[0], q[2], q[4], q[6]]))
          : a.x2 !== undefined
            ? Math.min(a.x, a.x2)
            : a.x;
    pages.forEach((p, i) =>
      p.annots.forEach((a, k) => (groups[a.type] ? groups[a.type].push({ a, p, i, k, x: xOf(a), y: yOf(a) }) : null)),
    );
    let n = 0;
    TYPES.forEach(([t, title]) => {
      const group = groups[t];
      if (!listedAnnotTypes[t] || !group.length) return;
      n += group.length;
      group.sort((u, v) => u.i - v.i || v.y - u.y || u.x - v.x);
      const h = document.createElement('div');
      h.style.cssText = 'padding:8px 4px 4px';
      const titleEl = document.createElement('span');
      titleEl.style.fontWeight = '600';
      titleEl.textContent = title;
      const countEl = document.createElement('span');
      countEl.style.opacity = '.6';
      countEl.textContent = ' (' + group.length + ')';
      h.append(titleEl, countEl);
      body.appendChild(h);
      group.forEach(({ a, p, i, k, y }) => {
        const e = document.createElement('div');
        e.className = 'bm';
        e.style.cssText = 'gap:8px;align-items:flex-start;padding:5px 4px 5px 20px;font-size:12.5px;line-height:1.4';
        {
          const dot = document.createElement('span');
          dot.style.cssText =
            'width:10px;height:10px;border-radius:50%;margin-top:4px;flex-shrink:0;background:' +
            (t == 'ft' || t == 'sq' || t == 'ci' || t == 'ar' ? deep(a.color) : a.color);
          e.appendChild(dot);
        }
        const textEl = document.createElement('div');
        textEl.style.cssText =
          'flex:1;min-width:0;overflow:hidden;' +
          (t == 'note' || t == 'ft'
            ? 'display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;word-break:break-word'
            : 'text-overflow:ellipsis;white-space:nowrap');
        const str = a.txt || a.text || '';
        let baseTx =
          str ||
          (t == 'hl'
            ? _t('Highlight')
            : t == 'ul'
              ? _t('Underline')
              : t == 'so'
                ? _t('Strikethrough')
                : t == 'sq'
                  ? _t('Rectangle')
                  : t == 'ci'
                    ? _t('Circle')
                    : t == 'ar'
                      ? _t('Arrow')
                      : '');
        if (a.ro) {
          baseTx += a.author ? ' (' + a.author + ')' : ' (' + _t('External') + ')';
        }
        textEl.textContent = baseTx;
        if (!str && !a.ro) textEl.style.opacity = '.7';
        if (a.ro && str) textEl.title = str;
        const pageEl = document.createElement('span');
        pageEl.style.opacity = '.6';
        pageEl.textContent = i + 1;
        const controls = document.createElement('span');
        controls.className = 'ctl';
        if (!a.ro) {
          const x = document.createElement('button');
          x.textContent = '✕';
          x.title = _t('Delete');
          x.onclick = async (ev) => {
            ev.stopPropagation();
            if (!(await confirmDialog(_t('Delete annotation'), _t('Delete this annotation?'), _t('Delete')))) return;
            p.annots.splice(k, 1);
            const el = $('#view').children[i];
            if (el && el._ov) draw(el);
            renderSide();
          };
          const redraw = () => {
            const el = $('#view').children[i];
            if (el && el._ov) draw(el);
            renderSide();
          };
          if (t == 'note' || t == 'ft') {
            const editBtn = document.createElement('button');
            editBtn.textContent = '✎';
            editBtn.title = _t('Edit text');
            editBtn.onclick = (ev) => {
              ev.stopPropagation();
              textDialog(_t('Edit text'), a.text, (n) => {
                a.text = n;
                redraw();
              });
            };
            controls.append(editBtn);
          }
          {
            const ci = document.createElement('button');
            ci.title = _t('Change colour');
            ci.style.cssText =
              'width:20px;height:20px;padding:0;border-radius:4px;margin:2px 3px;border:1px solid var(--line);background:' +
              (t == 'ft' || t == 'sq' || t == 'ci' || t == 'ar' ? deep(a.color) : a.color);
            ci.onclick = (ev) => {
              ev.stopPropagation();
              openPalette(ci, (pc) => {
                a.color = t == 'hl' || t == 'note' ? pc : deep(pc);
                redraw();
              });
            };
            controls.append(ci);
          }
          controls.append(x);
        }
        e.onclick = () => goTo(i, y);
        e.append(textEl, pageEl, controls);
        body.appendChild(e);
      });
    });
    if (!n) {
      const z = document.createElement('div');
      z.style.opacity = '.6';
      z.textContent = !TYPES.some(([t]) => listedAnnotTypes[t])
        ? _t('Turn on at least one annotation type.')
        : annotsLoading
          ? _t('Loading annotations…')
          : _t('No annotations');
      body.appendChild(z);
    }
    if (isSameTab) body.scrollTop = prevScroll;
    return;
  }
  // Bookmarks tab: the tree, with selection, buttons on each row and drag and drop
  if (panelTab == 'bm') {
    // Top bar: left (add / delete), centre (format) and right (expand / collapse). Acts on the selected bookmarks that are visible.
    const { row, makeButton, addGroup } = panelBar();
    const getSelected = () => flatBms.filter((x) => selectedBookmarks.has(x));
    const add = makeButton('<path d="M5 12h14"/><path d="M12 5v14"/>', _t('Add bookmark'), addBookmark);
    add.id = 'addbm';
    const del = makeButton(
      '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/>',
      _t('Delete bookmark'),
      async () => {
        const targets = getSelected();
        if (!targets.length) return;
        if (
          await confirmDialog(
            targets.length > 1 ? _t('Delete bookmarks') : _t('Delete bookmark', null, 'dialog'),
            targets.length > 1
              ? _t('Delete {n} bookmarks?', { n: targets.length })
              : _t('Delete the bookmark “{title}”?', { title: targets[0].title }),
            _t('Delete'),
          )
        ) {
          targets.forEach((x) => removeBookmark(bookmarks, x));
          selectedBookmarks.clear();
          renderSide();
        }
      },
    );
    del.dataset.action = 'delete'; // the Delete key presses it (see the keyboard shortcuts)
    const bold = makeButton(
      '<path d="M6 12h9a4 4 0 0 1 0 8H7a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h7a4 4 0 0 1 0 8"/>',
      _t('Bold'),
      () => {
        const targets = getSelected(),
          v = !targets.every((x) => x.bold);
        targets.forEach((x) => (x.bold = v));
        renderSide();
      },
    );
    const italic = makeButton(
      '<line x1="19" x2="10" y1="4" y2="4"/><line x1="14" x2="5" y1="20" y2="20"/><line x1="15" x2="9" y1="4" y2="20"/>',
      _t('Italic'),
      () => {
        const targets = getSelected(),
          v = !targets.every((x) => x.italic);
        targets.forEach((x) => (x.italic = v));
        renderSide();
      },
    );
    const colour = makeButton(
      '<circle cx="13.5" cy="6.5" r=".5"/><circle cx="17.5" cy="10.5" r=".5"/><circle cx="8.5" cy="7.5" r=".5"/><circle cx="6.5" cy="12.5" r=".5"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/>',
      _t('Change colour'),
      () =>
        openPalette(
          colour,
          (pc) => {
            getSelected().forEach((x) => (x.color = deep(pc)));
            renderSide();
          },
          BOOKMARK_PALETTE,
        ),
    );
    const clearFormat = makeButton(
      '<path d="M4 7V4h16v3"/><path d="M5 20h6"/><path d="M13 4 8 20"/><path d="m15 15 5 5"/><path d="m20 15-5 5"/>',
      _t('Clear formatting (bold, italic and colour)'),
      () => {
        getSelected().forEach((x) => {
          x.bold = false;
          x.italic = false;
          x.color = null;
        });
        renderSide();
      },
    );
    const all = makeButton(
      '<path d="m7 15 5 5 5-5"/><path d="m7 9 5-5 5 5"/>',
      _t('Expand / collapse bookmarks'),
      () => {
        const anyOpen = (l) => l.some((x) => x.items.length && (x.open !== false || anyOpen(x.items)));
        const v = !anyOpen(bookmarks);
        const set = (l) =>
          l.forEach((x) => {
            x.open = v;
            set(x.items);
          });
        set(bookmarks);
        renderSide();
      },
    );
    all.textContent = '⇕';
    all.style.fontSize = '16px';
    addGroup('l', add, del);
    addGroup('c', bold, italic, colour, clearFormat);
    addGroup('r', all);
    // Button states follow the selection: with nothing selected there is nothing to delete or format; bold and italic show as active
    const updateButtons = () => {
      const targets = getSelected(),
        no = !targets.length;
      [del, bold, italic, colour, clearFormat].forEach((b) => (b.disabled = no));
      bold.classList.toggle('on', !no && targets.every((x) => x.bold));
      italic.classList.toggle('on', !no && targets.every((x) => x.italic));
    };
    body.appendChild(row);
    if (!bookmarks.length) {
      const n = document.createElement('div');
      n.style.opacity = '.6';
      n.textContent = _t('No bookmarks');
      body.appendChild(n);
    }
    const flatBms = [];
    const flatten = (l) =>
      l.forEach((x) => {
        flatBms.push(x);
        if (x.open !== false) flatten(x.items);
      });
    flatten(bookmarks);
    updateButtons();
    // Draws the bookmarks of list at depth d (indented); up is where the parent is ({ list, i }), to move a level up
    const walk = (list, d, up) =>
      list.forEach((it, i) => {
        const e = document.createElement('div');
        e.className = 'bm' + (selectedBookmarks.has(it) ? ' sel' : '');
        e.draggable = true;
        e.style.paddingLeft = 4 + d * 14 + 'px';
        const toggle = document.createElement('span');
        toggle.style.cssText = 'width:16px;flex-shrink:0;text-align:center;opacity:.7';
        if (it.items.length) {
          toggle.textContent = it.open === false ? '▸' : '▾';
          toggle.onclick = (ev) => {
            ev.stopPropagation();
            it.open = it.open === false;
            renderSide();
          };
        }
        const t = document.createElement('span');
        t.textContent = it.title;
        t.style.flex = '1';
        if (it.color) t.style.color = it.color;
        if (it.bold) t.style.fontWeight = '700';
        if (it.italic) t.style.fontStyle = 'italic';
        t.onclick = (ev) => {
          if (!ev.ctrlKey && !ev.metaKey && !ev.shiftKey) {
            const k = pages.indexOf(it.page);
            if (k >= 0) goTo(k, destY(it.dd));
          }
        };
        e.onclick = (ev) => {
          ev.stopPropagation();
          if (ev.shiftKey && bookmarkAnchor) {
            const a = flatBms.indexOf(bookmarkAnchor),
              b = flatBms.indexOf(it);
            if (a >= 0 && b >= 0) {
              if (!(ev.ctrlKey || ev.metaKey)) selectedBookmarks.clear();
              for (let k = Math.min(a, b); k <= Math.max(a, b); k++) selectedBookmarks.add(flatBms[k]);
            }
          } else if (ev.ctrlKey || ev.metaKey) {
            selectedBookmarks.has(it) ? selectedBookmarks.delete(it) : selectedBookmarks.add(it);
            bookmarkAnchor = it;
          } else {
            selectedBookmarks.clear();
            selectedBookmarks.add(it);
            bookmarkAnchor = it;
          }
          renderSide();
        };
        const rowButton = (txt, tip, fn) => {
          const b = document.createElement('button');
          b.textContent = txt;
          b.title = tip;
          b.onclick = (ev) => {
            ev.stopPropagation();
            fn();
            renderSide();
          };
          return b;
        };
        const controls = document.createElement('span');
        controls.className = 'ctl';
        const rowTargets = () =>
          selectedBookmarks.has(it) && selectedBookmarks.size > 1 ? Array.from(selectedBookmarks) : [it];
        controls.append(
          rowButton('✎', _t('Edit bookmark'), () => {
            promptDialog(_t('Edit bookmark'), _t('Title:'), it.title, _t('Save')).then((n) => {
              if (n) {
                it.title = n;
                renderSide();
              }
            });
          }),
          rowButton('←', _t('Decrease indent (move up a level)'), () => {
            if (up) {
              list.splice(i, 1);
              up.list.splice(up.i + 1, 0, it);
            }
          }),
          rowButton('→', _t('Increase indent (make a sub-item of the previous one)'), () => {
            if (i > 0) {
              list.splice(i, 1);
              list[i - 1].items.push(it);
              list[i - 1].open = true;
            }
          }),
          rowButton('⚑', _t('Point to the current page'), () => {
            rowTargets().forEach((x) => {
              x.page = pages[currentPage];
              x.dd = null;
            });
          }),
        );
        // Drag and drop: dropping on the top 30 % of a row puts the bookmarks before it, on the bottom 30 % after it,
        // otherwise inside it
        const clearDropMark = () => e.classList.remove('before', 'after', 'inside');
        const zone = (ev) => {
          const r = e.getBoundingClientRect(),
            y = (ev.clientY - r.top) / r.height;
          return y < 0.3 ? 'before' : y > 0.7 ? 'after' : 'inside';
        };
        e.ondragstart = (ev) => {
          draggedBookmarks = bookmarksToDrag(it);
          ev.dataTransfer.setData('text/plain', 'bm');
          ev.dataTransfer.effectAllowed = 'move';
        };
        e.ondragend = () => {
          draggedBookmarks = [];
          renderSide();
        };
        e.ondragover = (ev) => {
          if (!draggedBookmarks.length || draggedBookmarks.some((n) => isInSubtree(n, it))) return;
          ev.preventDefault();
          clearDropMark();
          e.classList.add(zone(ev));
        };
        e.ondragleave = clearDropMark;
        e.ondrop = (ev) => {
          if (!draggedBookmarks.length || draggedBookmarks.some((n) => isInSubtree(n, it))) return;
          ev.preventDefault();
          const z = zone(ev),
            moved = draggedBookmarks;
          moved.forEach((n) => removeBookmark(bookmarks, n));
          if (z == 'inside') {
            it.items.push(...moved);
            it.open = true;
          } else {
            const f = findBookmark(bookmarks, it);
            f.list.splice(f.i + (z == 'after' ? 1 : 0), 0, ...moved);
          }
          draggedBookmarks = [];
          renderSide();
        };
        e.append(toggle, t, controls);
        body.appendChild(e);
        if (it === flashBookmark) {
          e.style.background = 'color-mix(in srgb,var(--acc) 30%,transparent)';
          requestAnimationFrame(() => e.scrollIntoView({ block: 'nearest' }));
        }
        if (it.open !== false) walk(it.items, d + 1, { list, i });
      });
    walk(bookmarks, 0);
    const hadFlash = !!flashBookmark;
    flashBookmark = null;
    const end = document.createElement('div');
    end.style.minHeight = '80px';
    end.ondragover = (ev) => {
      if (draggedBookmarks.length) ev.preventDefault();
    };
    end.ondrop = (ev) => {
      if (!draggedBookmarks.length) return;
      ev.preventDefault();
      const moved = draggedBookmarks;
      moved.forEach((n) => removeBookmark(bookmarks, n));
      bookmarks.push(...moved);
      draggedBookmarks = [];
      renderSide();
    };
    body.appendChild(end);
    if (isSameTab && !hadFlash) body.scrollTop = prevScroll;
    return;
  }
  // Pages tab: the thumbnails, with selection (click, Ctrl+click, Shift+click) and drag and drop to reorder
  // Top bar: delete (left), extract (centre) and rotate (right). Delete and rotate act on the selected pages.
  {
    const bar = panelBar(),
      getSelected = () => pages.filter((x) => selectedPages.has(x));
    const del = bar.makeButton(
      '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/>',
      _t('Delete page'),
      async () => {
        const targets = getSelected();
        if (!targets.length) return;
        if (pages.length <= targets.length) {
          showMessage(_t('You can’t delete all the pages.'));
          return;
        }
        if (
          await confirmDialog(
            targets.length > 1 ? _t('Delete pages') : _t('Delete page'),
            targets.length > 1
              ? _t('Delete {n} pages?', { n: targets.length })
              : _t('Delete page {n}?', { n: pages.indexOf(targets[0]) + 1 }),
            _t('Delete', null, 'page'),
          )
        ) {
          targets.forEach((x) => {
            const idx = pages.indexOf(x);
            if (idx >= 0) pages.splice(idx, 1);
          });
          selectedPages.clear();
          bookmarks = pruneBookmarks(bookmarks);
          renderSide();
          renderMain();
        }
      },
    );
    del.dataset.action = 'delete'; // the Delete key presses it (see the keyboard shortcuts)
    const addBtn = bar.makeButton(
      '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M12 11v6M9 14h6"/>',
      _t('Add pages'),
      addDialog,
    );
    addBtn.disabled = !pages.length;
    const extractBtn = bar.makeButton(
      '<path d="M16 3h5v5"/><path d="M8 3H3v5"/><path d="M12 22v-8.3a4 4 0 0 0-1.172-2.872L3 3"/><path d="m15 9 6-6"/>',
      _t('Extract pages'),
      () => extractDialog(),
    );
    extractBtn.disabled = isLocked();
    const rotLeftBtn = bar.makeButton(
      '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
      _t('Rotate 90° anticlockwise'),
      () => rotatePages(getSelected(), -90),
    );
    const rotRightBtn = bar.makeButton(
      '<path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>',
      _t('Rotate 90° clockwise'),
      () => rotatePages(getSelected(), 90),
    );
    bar.addGroup('l', del);
    bar.addGroup('c', addBtn, extractBtn);
    bar.addGroup('r', rotLeftBtn, rotRightBtn);
    // Delete and rotate are enabled only with pages selected
    updatePagesBar = () => {
      const no = !getSelected().length;
      [del, rotLeftBtn, rotRightBtn].forEach((b) => (b.disabled = no));
    };
    updatePagesBar();
    body.appendChild(bar.row);
  }
  // One cell per page; its image is drawn when it comes into view (thumbObserver)
  const grid = document.createElement('div');
  grid.className = 'grid';
  body.appendChild(grid);
  thumbObserver.disconnect();
  pages.forEach((p, i) => {
    const d = document.createElement('div');
    d.className = 'th' + (i == currentPage ? ' cur' : '') + (selectedPages.has(p) ? ' sel' : '');
    d.draggable = true;
    d.innerHTML = `<img alt=""><div class="n">${i + 1}</div>`;
    d._p = p;
    thumbObserver.observe(d);
    d.onclick = (e) => {
      if (e.shiftKey && pageAnchor >= 0) {
        const a = Math.min(pageAnchor, i),
          b = Math.max(pageAnchor, i);
        if (!(e.ctrlKey || e.metaKey)) selectedPages.clear();
        for (let k = a; k <= b; k++) selectedPages.add(pages[k]);
      } else if (e.ctrlKey || e.metaKey) {
        if (selectedPages.has(p)) selectedPages.delete(p);
        else selectedPages.add(p);
        pageAnchor = i;
      } else {
        selectedPages.clear();
        selectedPages.add(p);
        pageAnchor = i;
      }
      goTo(i);
      document.querySelectorAll('.th').forEach((x, k) => x.classList.toggle('sel', selectedPages.has(pages[k])));
      if (updatePagesBar) updatePagesBar();
    };
    // Dragging a selected page drags every selected page with it
    d.ondragstart = (e) => {
      e.dataTransfer.setData('text/plain', i);
      draggedPages = selectedPages.has(p) && selectedPages.size > 1 ? pages.filter((x) => selectedPages.has(x)) : [p];
    };
    d.ondragover = (e) => {
      e.preventDefault();
      d.classList.add('over');
    };
    d.ondragleave = () => d.classList.remove('over');
    d.ondrop = (e) => {
      e.preventDefault();
      const f = +e.dataTransfer.getData('text/plain');
      if (f == i || draggedPages.includes(p)) {
        d.classList.remove('over');
        return;
      }
      const moved = draggedPages;
      pages = pages.filter((x) => !moved.includes(x));
      pages.splice(pages.indexOf(p) + (f < i ? 1 : 0), 0, ...moved);
      draggedPages = [];
      renderSide();
      renderMain();
    };
    grid.appendChild(d);
  });
  if (isSameTab) body.scrollTop = prevScroll;
  followThumb(false);
}
// Pages panel: follows the current page. It only scrolls if the page's thumbnail is out of view (center=true: leaves it centred)
function followThumb(center) {
  if (panelTab != 'th') return;
  const body = $('#sbody'),
    thumb = body.querySelectorAll('.th')[currentPage];
  if (!thumb) return;
  const bodyRect = body.getBoundingClientRect(),
    thumbRect = thumb.getBoundingClientRect();
  if (!bodyRect.height) return;
  const bar = body.querySelector('.sbw'),
    top = bodyRect.top + (bar ? bar.offsetHeight - 8 : 0);
  if (center) body.scrollTop += thumbRect.top + thumbRect.height / 2 - (top + (bodyRect.bottom - top) / 2);
  else if (thumbRect.top < top) body.scrollTop -= top - thumbRect.top + 6;
  else if (thumbRect.bottom > bodyRect.bottom) body.scrollTop += thumbRect.bottom - bodyRect.bottom + 6;
}
// “Two pages”: only one pair (1-2, 3-4…) is visible at a time; the other pages are hidden
let shownPair = -1;
function showPair() {
  if (!pages.length) return;
  const view = $('#view'),
    first = currentPage - (currentPage % 2);
  shownPair = twoPageView ? first : -1;
  view.querySelectorAll('.ph').forEach((x) => x.remove());
  [...view.children].forEach((c, i) => {
    c.style.display = twoPageView && i != first && i != first + 1 ? 'none' : '';
  });
  if (twoPageView) {
    view.scrollTop = 0;
    const c = view.children[first];
    if (first + 1 >= pages.length && c) {
      const filler = document.createElement('div');
      filler.className = 'ph';
      filler.style.width = c.style.width;
      view.appendChild(filler);
    }
  }
}
// Puts height y (in PDF points) of page i in the first third of the viewer; never scrolls back up from where the page already is
function goToY(i, y) {
  const view = $('#view'),
    el = view.children[i];
  if (!el || !el._vp || el.style.display == 'none') return;
  const yPx = el._vp.convertToViewportPoint(0, y)[1],
    delta = el.getBoundingClientRect().top + yPx - (view.getBoundingClientRect().top + view.clientHeight / 3);
  if (delta > 0) view.scrollTop += delta;
}
// Goes to page i (and, if given, to height y on it): scrolls the viewer and marks the page in the thumbnails
function goTo(i, y) {
  currentPage = i;
  updatePageBox();
  const newPair = twoPageView && currentPage - (currentPage % 2) != shownPair;
  if (twoPageView) {
    if (newPair) setFit('p');
    $('#view').scrollTop = 0;
  } else {
    const e = $('#view').children[i];
    if (e) e.scrollIntoView();
  }
  if (typeof y == 'number' && isFinite(y) && !newPair) goToY(i, y);
  document.querySelectorAll('.th').forEach((t, k) => t.classList.toggle('cur', k == i));
  followThumb(false);
}

// While scrolling, the current page is the last one whose top has passed the first third of the viewer
$('#view').addEventListener('scroll', () => {
  if (twoPageView) return;
  const view = $('#view'),
    line = view.getBoundingClientRect().top + view.clientHeight / 3;
  let k = 0;
  [...view.children].forEach((c, i) => {
    if (c.getBoundingClientRect().top <= line) k = i;
  });
  if (twoPageView) {
    k -= k % 2;
    if (currentPage === k + 1) k = currentPage;
  }
  if (k != currentPage) {
    currentPage = k;
    updatePageBox();
    document.querySelectorAll('.th').forEach((x, j) => x.classList.toggle('cur', j == k));
    followThumb(false);
    const a = $('#addbm');
    if (a) a.title = _t('Add bookmark');
  }
});

// ---- Viewer ----
// Builds the viewer: an empty box of the right size per page; each is painted when it comes into view (pageObserver)
async function renderMain() {
  updatePageBox();
  const view = $('#view'),
    first = currentPage - (currentPage % 2);
  pageObserver.disconnect();
  view.innerHTML = '';
  for (let i = 0; i < pages.length; i++) {
    const p = pages[i],
      pdfPage = await docs[p.doc].pdf.getPage(p.idx + 1),
      viewport = pdfPage.getViewport({ scale, rotation: (pdfPage.rotate + (p.rot || 0)) % 360 });
    const el = document.createElement('div');
    el.className = 'page';
    el.style.width = viewport.width + 'px';
    el.style.height = viewport.height + 'px';
    el._p = p;
    el._pg = pdfPage;
    el._vp = viewport;
    el.dataset.i = i;
    if (twoPageView && (i < first || i > first + 1)) el.style.display = 'none';
    view.appendChild(el);
    pageObserver.observe(el);
  }
  showPair();
}
// Reads a page's annotations from the PDF (once per page)
function loadAnnots(page) {
  if (page.loaded) return Promise.resolve();
  return (
    page.annP ||
    (page.annP = (async () => {
      const pdf = docs[page.doc].pdf,
        pdfPage = await pdf.getPage(page.idx + 1),
        raw = await pdfPage.getAnnotations();
      page.widgets = raw.filter(
        (a) => a.subtype === 'Widget' && a.rect && a.fieldType && !((a.annotationFlags || 0) & 34),
      );
      raw.forEach((a) => {
        const author = a.titleObj ? a.titleObj.str : a.title || '';
        const isOwn = author === 'Penfold';
        if (
          isOwn ||
          ['Text', 'FreeText', 'Highlight', 'Underline', 'StrikeOut', 'Square', 'Circle', 'Line'].includes(a.subtype)
        ) {
          let colour =
            a.color && a.color.length === 3
              ? '#' +
                Array.from(a.color)
                  .map((v) => v.toString(16).padStart(2, '0'))
                  .join('')
              : null;
          if (!isOwn) {
            if (!colour || colour === '#ffffff') colour = '#c64600';
          } else {
            colour = colour || '#f9f06b';
          }
          const txt = (a.contentsObj ? a.contentsObj.str : a.contents) || '';
          const readOnly = !isOwn;
          if (a.subtype === 'Text')
            page.annots.push({
              type: 'note',
              color: colour,
              text: txt,
              x: (a.rect[0] + a.rect[2]) / 2,
              y: (a.rect[1] + a.rect[3]) / 2,
              ro: readOnly,
              author,
            });
          else if (a.subtype === 'FreeText')
            page.annots.push({
              type: 'ft',
              color: colour,
              text: txt,
              x: Math.min(a.rect[0], a.rect[2]),
              y: Math.max(a.rect[1], a.rect[3]),
              w: Math.abs(a.rect[2] - a.rect[0]),
              ro: readOnly,
              author,
            });
          else if (a.subtype === 'Highlight' || a.subtype === 'Underline' || a.subtype === 'StrikeOut') {
            const quads = [];
            if (a.quadPoints) {
              const qpts = a.quadPoints;
              if (typeof qpts[0] === 'number') {
                for (let i = 0; i < qpts.length; i += 8) quads.push(Array.from(qpts.slice(i, i + 8)));
              } else
                qpts.forEach((q) => {
                  if (Array.isArray(q) && q.length === 8) quads.push(q);
                  else if (q.length === 4) quads.push([q[0].x, q[0].y, q[1].x, q[1].y, q[2].x, q[2].y, q[3].x, q[3].y]);
                });
            } else if (a.rect) {
              quads.push([a.rect[0], a.rect[3], a.rect[2], a.rect[3], a.rect[0], a.rect[1], a.rect[2], a.rect[1]]);
            }
            if (quads.length)
              page.annots.push({
                type: a.subtype === 'Highlight' ? 'hl' : a.subtype === 'Underline' ? 'ul' : 'so',
                color: colour,
                quads,
                txt,
                ro: readOnly,
                author,
              });
          } else if (a.subtype === 'Square' || a.subtype === 'Circle') {
            page.annots.push({
              type: a.subtype === 'Square' ? 'sq' : 'ci',
              color: colour,
              x: Math.min(a.rect[0], a.rect[2]),
              y: Math.max(a.rect[1], a.rect[3]),
              x2: Math.max(a.rect[0], a.rect[2]),
              y2: Math.min(a.rect[1], a.rect[3]),
              ro: readOnly,
              author,
            });
          } else if (a.subtype === 'Line') {
            const line = a.lineCoordinates || [a.rect[0], a.rect[1], a.rect[2], a.rect[3]];
            page.annots.push({
              type: 'ar',
              color: colour,
              x: line[0],
              y: line[1],
              x2: line[2],
              y2: line[3],
              ro: readOnly,
              author,
            });
          }
        } else if (a.subtype === 'Link') {
          const dest = a.dest || (a.action && a.action.dest);
          if (dest || a.url) {
            page.annots.push({
              type: 'link',
              x: Math.min(a.rect[0], a.rect[2]),
              y: Math.max(a.rect[1], a.rect[3]),
              w: Math.abs(a.rect[2] - a.rect[0]),
              h: Math.abs(a.rect[3] - a.rect[1]),
              dest: dest,
              url: a.url,
            });
          }
        }
      });
      // Annotations read from the file are the saved state of this page (see “Unsaved changes”)
      markPageSaved(page);
      page.loaded = true;
    })().catch((e) => {
      page.annP = null;
      throw e;
    }))
  );
}
// Loads the annotations of every page when a PDF is opened or added, so the index is complete from the start
let annotsLoading = 0;
async function loadAllAnnots() {
  annotsLoading++;
  if (panelTab == 'an') renderSide();
  try {
    for (const p of pages.slice()) {
      if (pages.includes(p)) await loadAnnots(p);
    }
  } catch (e) {}
  annotsLoading--;
  if (panelTab == 'an') renderSide();
}
// ---- Forms: layer of fillable fields over the page (phase 2). Values are kept in docs[…].fv (full field name → value); they are written to the PDF on save (writeFormValues).
// The value a form field has in the PDF, in the form the screen uses: text, true/false (checkbox), the chosen option
// (radio) or a list of options (list box)
function fieldValueInPdf(a) {
  const type = a.fieldType,
    value = a.fieldValue;
  if (type == 'Btn')
    return a.radioButton
      ? value == null || value === 'Off'
        ? ''
        : String(value)
      : !!(value && value !== 'Off' && value !== '');
  if (type == 'Ch')
    return Array.isArray(value) ? value.map(String) : value == null || value === '' ? [] : [String(value)];
  return value == null ? '' : Array.isArray(value) ? value.join('\n') : String(value);
}
// Puts an HTML field over each form field of the page (text box, checkbox, radio button or list), at the same
// place and size. Changes go to docs[…].fv, and fields with the same name show the same value
function formLayer(el) {
  const page = el._p,
    viewport = el._vp,
    widgets = page.widgets;
  if (!widgets || !widgets.length) return;
  const doc = docs[page.doc];
  if (!doc) return;
  const values = doc.fv || (doc.fv = {});
  const layer = document.createElement('div');
  layer.className = 'fl';
  // Shows the new value in the other fields with the same name (a form can repeat a field on several pages)
  const sync = (name, val, src) => {
    layer.parentNode &&
      $('#view')
        .querySelectorAll('.fl [data-fn]')
        .forEach((x) => {
          if (x === src || x.dataset.fn !== name || x._doc !== page.doc) return;
          if (x.type == 'checkbox') x.checked = !!val;
          else if (x.type == 'radio') x.checked = x.value === val;
          else if (x.tagName == 'SELECT') [...x.options].forEach((o) => (o.selected = val.includes(o.value)));
          else x.value = val;
        });
  };
  // A field was changed: its value is stored (fvDirty lists the changed fields, for the unsaved-changes check)
  const setValue = (a, val, src) => {
    if (!doc.fvDirty) doc.fvDirty = new Set();
    // Back to the value it has in the PDF: the field counts as untouched again (and is left as it is on save)
    if (JSON.stringify(val) === JSON.stringify(fieldValueInPdf(a))) {
      delete values[a.fieldName];
      doc.fvDirty.delete(a.fieldName);
    } else {
      values[a.fieldName] = val;
      doc.fvDirty.add(a.fieldName);
    }
    sync(a.fieldName, val, src);
  };
  widgets.forEach((a) => {
    const t = a.fieldType;
    if (t != 'Tx' && t != 'Btn' && t != 'Ch') return;
    if (t == 'Btn' && a.pushButton) return;
    const r = viewport.convertToViewportRectangle(a.rect),
      l = Math.min(r[0], r[2]),
      top = Math.min(r[1], r[3]),
      w = Math.abs(r[2] - r[0]),
      h = Math.abs(r[3] - r[1]);
    if (w < 2 || h < 2) return;
    const name = a.fieldName || '',
      has = Object.prototype.hasOwnProperty.call(values, name),
      current = has ? values[name] : fieldValueInPdf(a);
    let input;
    if (t == 'Tx') {
      const multiLine = !!a.multiLine,
        password = ((a.fieldFlags || 0) & 0x2000) != 0;
      input = document.createElement(multiLine ? 'textarea' : 'input');
      if (!multiLine) input.type = password ? 'password' : 'text';
      input.value = Array.isArray(current) ? current.join('\n') : String(current);
      if (a.maxLen) input.maxLength = a.maxLen;
      const appearance = a.defaultAppearanceData,
        fontSize =
          appearance && appearance.fontSize > 0
            ? appearance.fontSize * viewport.scale
            : multiLine
              ? 12 * viewport.scale
              : Math.max(8, Math.min(h * 0.66, 16 * viewport.scale));
      input.style.fontSize = fontSize + 'px';
      input.style.textAlign = ['left', 'center', 'right'][a.textAlignment || 0] || 'left';
      input.oninput = () => setValue(a, input.value, input);
    } else if (t == 'Btn' && a.checkBox) {
      input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = !!current;
      input.onchange = () => setValue(a, input.checked, input);
    } else if (t == 'Btn') {
      input = document.createElement('input');
      input.type = 'radio';
      input.name = page.doc + '|' + name;
      input.value = String(a.buttonValue);
      input.checked = current === input.value;
      input.onchange = () => {
        if (input.checked) setValue(a, input.value, input);
      };
    } else {
      input = document.createElement('select');
      const multi = !!a.multiSelect;
      if (multi) input.multiple = true;
      else if (!a.combo) input.size = Math.max(2, Math.min(8, (a.options || []).length));
      const sel = Array.isArray(current) ? current : [];
      if (a.combo && !sel.length) {
        const o = document.createElement('option');
        o.value = '';
        o.textContent = '';
        input.appendChild(o);
      }
      (a.options || []).forEach((op) => {
        const o = document.createElement('option');
        o.value = String(op.exportValue);
        o.textContent = op.displayValue != null ? op.displayValue : op.exportValue;
        o.selected = sel.includes(o.value);
        input.appendChild(o);
      });
      input.style.fontSize = Math.max(8, Math.min(h * 0.66, 14 * viewport.scale)) + 'px';
      input.onchange = () => setValue(a, [...input.selectedOptions].map((o) => o.value).filter(Boolean), input);
    }
    if (a.readOnly) {
      input.disabled = true;
    }
    input.dataset.fn = name;
    input._doc = page.doc;
    input.title = a.alternativeText || '';
    input.style.left = l + 'px';
    input.style.top = top + 'px';
    input.style.width = w + 'px';
    input.style.height = h + 'px';
    layer.appendChild(input);
  });
  if (layer.children.length) el.appendChild(layer);
}
// Paints a page: the image (at twice the screen resolution at least, so it stays sharp), the text layer (invisible
// text over the image, so text can be selected and found), the annotations layer and the form fields.
// It also handles the clicks and drags that create comments, text boxes, rectangles, circles and arrows
async function paint(el) {
  const { _pg: pdfPage, _vp: viewport } = el,
    canvas = document.createElement('canvas'),
    ratio = Math.max(2, devicePixelRatio || 1);
  canvas.width = viewport.width * ratio;
  canvas.height = viewport.height * ratio;
  canvas.style.width = viewport.width + 'px';
  canvas.style.height = viewport.height + 'px';
  el.appendChild(canvas);
  await pdfPage.render({
    canvasContext: canvas.getContext('2d'),
    viewport: viewport,
    transform: [ratio, 0, 0, ratio, 0, 0],
    annotationMode: pdfjsLib.AnnotationMode.DISABLE,
  }).promise;
  const textLayer = document.createElement('div');
  textLayer.className = 'textLayer';
  textLayer.style.setProperty('--scale-factor', viewport.scale);
  el.appendChild(textLayer);
  pdfjsLib.renderTextLayer({
    textContentSource: pdfPage.streamTextContent(),
    container: textLayer,
    viewport: viewport,
    textDivs: [],
  });
  const overlay = document.createElement('div');
  overlay.className = 'ov';
  el.appendChild(overlay);
  el._ov = overlay;
  if (!el._p.loaded) {
    await loadAnnots(el._p);
    if (panelTab == 'an') renderSide();
  }
  draw(el);
  markHits(el);
  formLayer(el);
  // Comment tool: a click on the page asks for the text and puts the comment there
  el.onclick = (e) => {
    if (e.target.closest('.an') || tool != 'note') return;
    const b = el.getBoundingClientRect(),
      x = e.clientX - b.left,
      y = e.clientY - b.top;
    textDialog(_t('Comment'), '', (t) => {
      const [px, py] = viewport.convertToPdfPoint(x, y);
      el._p.annots.push({ type: 'note', color: annotColor, text: t, x: px, y: py });
      draw(el);
      if (panelTab == 'an') renderSide();
    });
  };
  // Text box, rectangle, circle and arrow tools: dragging draws a dashed preview (ghost) that becomes the annotation
  el.onmousedown = (e) => {
    if (!['ft', 'sq', 'ci', 'ar'].includes(tool) || e.button !== 0 || e.target.closest('.an')) return;
    e.preventDefault();
    const b = el.getBoundingClientRect(),
      x0 = e.clientX - b.left,
      y0 = e.clientY - b.top,
      ghost = document.createElement('div');
    let x1 = x0,
      y1 = y0;
    if (tool == 'ft') {
      ghost.style.cssText =
        'position:absolute;pointer-events:none;z-index:6;height:26px;display:none;border:1.5px dashed ' +
        deep(annotColor);
    } else if (tool == 'sq' || tool == 'ci') {
      ghost.style.cssText =
        'position:absolute;pointer-events:none;z-index:6;display:none;border:' +
        SHAPE_STROKE +
        'px solid ' +
        deep(annotColor) +
        (tool == 'ci' ? ';border-radius:50%' : '');
    } else if (tool == 'ar') {
      ghost.style.cssText = 'position:absolute;pointer-events:none;z-index:6;display:none;overflow:visible';
      ghost.innerHTML = `<svg style="position:absolute;inset:0;width:100%;height:100%;overflow:visible" stroke="${deep(annotColor)}" stroke-width="${SHAPE_STROKE}" fill="none" stroke-linecap="round" stroke-linejoin="round"><path class="P" d=""/></svg>`;
    }
    el.appendChild(ghost);
    const onMove = (ev) => {
      x1 = Math.max(0, Math.min(b.width, ev.clientX - b.left));
      y1 = Math.max(0, Math.min(b.height, ev.clientY - b.top));
      const w = Math.abs(x1 - x0),
        h = Math.abs(y1 - y0);
      if (tool == 'ft') {
        ghost.style.display = w > 8 ? 'block' : 'none';
        ghost.style.left = Math.min(x0, x1) + 'px';
        ghost.style.top = y0 + 'px';
        ghost.style.width = w + 'px';
      } else if (tool == 'sq' || tool == 'ci') {
        ghost.style.display = w > 4 || h > 4 ? 'block' : 'none';
        ghost.style.left = Math.min(x0, x1) + 'px';
        ghost.style.top = Math.min(y0, y1) + 'px';
        ghost.style.width = w + 'px';
        ghost.style.height = h + 'px';
      } else if (tool == 'ar') {
        ghost.style.display = w > 4 || h > 4 ? 'block' : 'none';
        ghost.style.left = Math.min(x0, x1) + 'px';
        ghost.style.top = Math.min(y0, y1) + 'px';
        ghost.style.width = Math.max(1, w) + 'px';
        ghost.style.height = Math.max(1, h) + 'px';
        if (ghost.querySelector('.P')) {
          const px1 = x0 - Math.min(x0, x1),
            py1 = y0 - Math.min(y0, y1);
          const px2 = x1 - Math.min(x0, x1),
            py2 = y1 - Math.min(y0, y1);
          const angle = Math.atan2(y1 - y0, x1 - x0);
          const L = 12;
          const p1x = px2 - L * Math.cos(angle - Math.PI / 6),
            p1y = py2 - L * Math.sin(angle - Math.PI / 6);
          const p2x = px2 - L * Math.cos(angle + Math.PI / 6),
            p2y = py2 - L * Math.sin(angle + Math.PI / 6);
          ghost
            .querySelector('.P')
            .setAttribute('d', `M${px1} ${py1} L${px2} ${py2} M${p1x} ${p1y} L${px2} ${py2} L${p2x} ${p2y}`);
        }
      }
    };
    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      ghost.remove();
      const w = Math.abs(x1 - x0),
        h = Math.abs(y1 - y0);
      if (tool == 'ft') {
        const widthPdf = w > 8 ? Math.max(40, w / viewport.scale) : TEXT_BOX.w;
        let l = w > 8 ? Math.min(x0, x1) : x0;
        l = Math.max(0, Math.min(l, b.width - widthPdf * viewport.scale));
        textDialog(_t('Text box'), '', (t) => {
          const [px, py] = viewport.convertToPdfPoint(l, y0);
          el._p.annots.push({ type: 'ft', color: deep(annotColor), text: t, x: px, y: py, w: widthPdf });
          draw(el);
          if (panelTab == 'an') renderSide();
        });
      } else if (tool == 'sq' || tool == 'ci' || tool == 'ar') {
        if (w > 4 || h > 4) {
          const [px1, py1] = viewport.convertToPdfPoint(x0, y0);
          const [px2, py2] = viewport.convertToPdfPoint(x1, y1);
          el._p.annots.push({ type: tool, color: deep(annotColor), x: px1, y: py1, x2: px2, y2: py2 });
          draw(el);
          if (panelTab == 'an') renderSide();
        }
      }
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  };
}
// Draws the annotations of a page in its overlay (HTML and SVG over the page image). Right-click deletes one of your
// own; links can be clicked
function draw(el) {
  const overlay = el._ov,
    viewport = el._vp;
  overlay.innerHTML = '';
  el._p.annots.forEach((a, k) => {
    const addMark = (css, cls) => {
      const d = document.createElement('div');
      d.className = 'an ' + cls;
      Object.assign(d.style, css);
      if (cls !== 'link' && !a.ro)
        d.oncontextmenu = async (e) => {
          e.preventDefault();
          if (await confirmDialog(_t('Delete annotation'), _t('Delete this annotation?'), _t('Delete'))) {
            el._p.annots.splice(k, 1);
            draw(el);
            if (panelTab == 'an') renderSide();
          }
        };
      overlay.appendChild(d);
      return d;
    };
    if (a.quads)
      a.quads.forEach((q) => {
        const xs = [],
          ys = [];
        for (let i = 0; i < 8; i += 2) {
          const [x, y] = viewport.convertToViewportPoint(q[i], q[i + 1]);
          xs.push(x);
          ys.push(y);
        }
        const l = Math.min(...xs),
          t = Math.min(...ys),
          w = Math.max(...xs) - l,
          h = Math.max(...ys) - t;
        addMark(
          a.type == 'hl'
            ? { left: l + 'px', top: t + 'px', width: w + 'px', height: h + 'px', background: a.color }
            : a.type == 'ul'
              ? {
                  left: l + 'px',
                  top: t + h - 2 + 'px',
                  width: w + 'px',
                  height: '2px',
                  borderColor: a.color,
                  background: a.color,
                  borderBottom: '0',
                }
              : {
                  left: l + 'px',
                  top: t + h / 2 - 1 + 'px',
                  width: w + 'px',
                  height: '2px',
                  borderColor: a.color,
                  background: a.color,
                  borderBottom: '0',
                },
          a.type,
        );
        overlay.lastChild.style.pointerEvents = 'auto';
      });
    else if (a.type == 'link') {
      const [x, y] = viewport.convertToViewportPoint(a.x, a.y),
        [x2, y2] = viewport.convertToViewportPoint(a.x + a.w, a.y - a.h);
      const d = addMark(
        {
          left: Math.min(x, x2) + 'px',
          top: Math.min(y, y2) + 'px',
          width: Math.abs(x2 - x) + 'px',
          height: Math.abs(y2 - y) + 'px',
          cursor: 'pointer',
          zIndex: 5,
        },
        'link',
      );
      d.onclick = async (ev) => {
        ev.stopPropagation();
        if (a.url) window.open(a.url, '_blank');
        else if (a.dest) {
          try {
            let d = a.dest;
            if (typeof d == 'string') d = await docs[el._p.doc].pdf.getDestination(d);
            if (d) {
              const n = await docs[el._p.doc].pdf.getPageIndex(d[0]);
              const target = pages.findIndex((p) => p.doc == el._p.doc && p.idx == n);
              if (target >= 0) goTo(target, destY(destFromPdfJs(d)));
            }
          } catch (e) {}
        }
      };
    } else if (a.type == 'sq' || a.type == 'ci' || a.type == 'ar') {
      const [vx1, vy1] = viewport.convertToViewportPoint(a.x, a.y);
      const [vx2, vy2] = viewport.convertToViewportPoint(a.x2, a.y2);
      const vl = Math.min(vx1, vx2),
        vt = Math.min(vy1, vy2);
      const vw = Math.max(1, Math.abs(vx2 - vx1)),
        vh = Math.max(1, Math.abs(vy2 - vy1));
      const strokePx = SHAPE_STROKE * viewport.scale;
      const d = addMark(
        {
          left: vl + 'px',
          top: vt + 'px',
          width: vw + 'px',
          height: vh + 'px',
          overflow: 'visible',
          pointerEvents: 'none',
        },
        a.type,
      );
      let inner = '';
      if (a.type == 'ar') {
        const px1 = vx1 - vl,
          py1 = vy1 - vt,
          px2 = vx2 - vl,
          py2 = vy2 - vt;
        const angle = Math.atan2(vy2 - vy1, vx2 - vx1);
        const L = 12 * viewport.scale;
        const p1x = px2 - L * Math.cos(angle - Math.PI / 6),
          p1y = py2 - L * Math.sin(angle - Math.PI / 6);
        const p2x = px2 - L * Math.cos(angle + Math.PI / 6),
          p2y = py2 - L * Math.sin(angle + Math.PI / 6);
        inner = `<path d="M${px1} ${py1} L${px2} ${py2} M${p1x} ${p1y} L${px2} ${py2} L${p2x} ${p2y}" style="pointer-events:visibleStroke"/>`;
      } else if (a.type == 'sq') {
        inner = `<rect x="${strokePx / 2}" y="${strokePx / 2}" width="${Math.max(0, vw - strokePx)}" height="${Math.max(0, vh - strokePx)}" style="pointer-events:visibleStroke"/>`;
      } else if (a.type == 'ci') {
        inner = `<ellipse cx="${vw / 2}" cy="${vh / 2}" rx="${Math.max(0, (vw - strokePx) / 2)}" ry="${Math.max(0, (vh - strokePx) / 2)}" style="pointer-events:visibleStroke"/>`;
      }
      d.innerHTML = `<svg style="position:absolute;inset:0;width:100%;height:100%;overflow:visible" stroke="${a.color}" stroke-width="${strokePx}" fill="none" stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`;
    } else {
      const [x, y] = viewport.convertToViewportPoint(a.x, a.y);
      const d = addMark({ left: x + 'px', top: y + 'px' }, a.type == 'note' ? 'note' : 'ft');
      if (a.type == 'note') {
        d.dataset.text = a.text;
        d.innerHTML = noteIconSvg(a.color);
      } else {
        const s = viewport.scale,
          c = deep(a.color);
        d.title = a.text;
        d.textContent = a.text;
        Object.assign(d.style, {
          width: (a.w || TEXT_BOX.w) * s + 'px',
          boxSizing: 'border-box',
          font: TEXT_BOX.fs * s + 'px/' + TEXT_BOX.lh + ' Helvetica,Arial,sans-serif',
          padding: TEXT_BOX.pad * s + 'px',
          border: Math.max(1, TEXT_BOX.bw * s) + 'px solid ' + c,
          background: tint(c, 0.14),
          color: a.ro ? c : 'var(--ink)',
        });
      }
    }
  });
  overlay.style.pointerEvents = 'none';
  overlay.querySelectorAll('.an.note,.an.ft,.an.link').forEach((n) => (n.style.pointerEvents = 'auto'));
}
// Turns the text selected on a page into a highlight, underline or strikethrough (type 'hl', 'ul' or 'so').
// Each selected line is a quadrilateral (quads, in PDF units); overlapping boxes of one line are merged.
// Returns false if no text of a page is selected (then nothing is done)
function markSelection(type) {
  const s = getSelection();
  if (!s.rangeCount || s.isCollapsed) return false;
  const r = s.getRangeAt(0),
    n = r.commonAncestorContainer,
    el = (n.nodeType == 1 ? n : n.parentElement).closest('.page');
  if (!el) return false;
  const b = el.getBoundingClientRect(),
    vp = el._vp,
    quads = [],
    rects = [];
  for (const c of r.getClientRects()) {
    if (c.width < 2 || c.height < 2) continue;
    const l = c.left - b.left,
      t = c.top - b.top,
      rr = l + c.width,
      bb = t + c.height;
    const match = rects.find((x) => {
      const ox = Math.max(0, Math.min(rr, x.rr) - Math.max(l, x.l)),
        oy = Math.max(0, Math.min(bb, x.bb) - Math.max(t, x.t));
      return ox * oy > 0.5 * Math.min((rr - l) * (bb - t), (x.rr - x.l) * (x.bb - x.t));
    });
    if (match) {
      match.l = Math.min(match.l, l);
      match.t = Math.min(match.t, t);
      match.rr = Math.max(match.rr, rr);
      match.bb = Math.max(match.bb, bb);
    } else rects.push({ l, t, rr, bb });
  }
  for (const c of rects)
    quads.push([
      ...vp.convertToPdfPoint(c.l, c.t),
      ...vp.convertToPdfPoint(c.rr, c.t),
      ...vp.convertToPdfPoint(c.l, c.bb),
      ...vp.convertToPdfPoint(c.rr, c.bb),
    ]);
  if (quads.length) {
    el._p.annots.push({
      type,
      color: type == 'ul' || type == 'so' ? deep(annotColor) : annotColor,
      quads,
      txt: s.toString().replace(/\s+/g, ' ').trim(),
    });
    draw(el);
    if (panelTab == 'an') renderSide();
  }
  s.removeAllRanges();
  return true;
}
// Highlight, underline and strikethrough tools: releasing the mouse after selecting text marks it
document.addEventListener('mouseup', () => {
  if (tool == 'hl' || tool == 'ul' || tool == 'so') markSelection(tool);
});

// ---- Saving ----
// #rrggbb as [r, g, b] from 0 to 1, as PDF drawing commands want it.
// The functions that follow write small PDF drawings (content streams): a text of commands such as “x y m” (move),
// “x y l” (line), “re” (rectangle), “S” (stroke), “f” (fill), “rg”/“RG” (fill / stroke colour)
const hexToRgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.substr(i, 2), 16) / 255);
// Own drawing (appearance stream) for highlights, underlines and strikethroughs: that way every viewer paints the same as Penfold.
// Highlight: fill with Multiply blending and HIGHLIGHT_OPACITY (as on screen). Underline / strikethrough: a line SHAPE_STROKE points wide.
const HIGHLIGHT_OPACITY = 0.75;
function markupAppearance(ctx, a, bbox) {
  const round = (v) => +v.toFixed(3),
    hl = a.type == 'hl',
    rgb = hexToRgb(a.color).map(round).join(' ');
  let ops = hl ? '/GS0 gs ' + rgb + ' rg\n' : rgb + ' RG ' + SHAPE_STROKE + ' w\n';
  a.quads.forEach((q) => {
    if (hl)
      ops +=
        round(q[0]) +
        ' ' +
        round(q[1]) +
        ' m ' +
        round(q[2]) +
        ' ' +
        round(q[3]) +
        ' l ' +
        round(q[6]) +
        ' ' +
        round(q[7]) +
        ' l ' +
        round(q[4]) +
        ' ' +
        round(q[5]) +
        ' l h f\n';
    else if (a.type == 'ul') {
      const dx = q[0] - q[4],
        dy = q[1] - q[5],
        L = Math.hypot(dx, dy) || 1,
        ox = ((dx / L) * SHAPE_STROKE) / 2,
        oy = ((dy / L) * SHAPE_STROKE) / 2;
      ops += round(q[4] + ox) + ' ' + round(q[5] + oy) + ' m ' + round(q[6] + ox) + ' ' + round(q[7] + oy) + ' l S\n';
    } else {
      const mx0 = (q[0] + q[4]) / 2,
        my0 = (q[1] + q[5]) / 2,
        mx1 = (q[2] + q[6]) / 2,
        my1 = (q[3] + q[7]) / 2;
      ops += round(mx0) + ' ' + round(my0) + ' m ' + round(mx1) + ' ' + round(my1) + ' l S\n';
    }
  });
  const resources = hl
    ? { ExtGState: { GS0: { Type: 'ExtGState', BM: 'Multiply', ca: HIGHLIGHT_OPACITY, CA: HIGHLIGHT_OPACITY } } }
    : {};
  return ctx.register(
    ctx.stream(ops, { Type: 'XObject', Subtype: 'Form', FormType: 1, BBox: bbox, Resources: resources }),
  );
}
// Text box: splits the text into lines using Helvetica metrics (like pre-wrap + overflow-wrap on screen).
// Characters Helvetica does not have (emoji, arrows…) come out as “?” in the drawing; the /Contents text is stored in full.
function textBoxLines(font, text, w) {
  const glyphs = new Set(font.getCharacterSet()),
    max = w - 2 * (TEXT_BOX.bw + TEXT_BOX.pad),
    widthOf = (word) => font.widthOfTextAtSize(word, TEXT_BOX.fs),
    lines = [];
  text
    .replace(/\r\n?/g, '\n')
    .replace(/\t/g, ' ')
    .replace(/\n$/, '')
    .split('\n')
    .forEach((par) => {
      let line = '';
      for (const word of par.match(/ +|[^ ]+/g) || []) {
        const safeWord = Array.from(word, (ch) => (glyphs.has(ch.codePointAt(0)) ? ch : '?')).join('');
        if (safeWord[0] == ' ' || widthOf(line + safeWord) <= max) {
          line += safeWord;
          continue;
        }
        // The current line is full: keep it (the word goes on the next one; line is replaced below)
        if (line.trim()) lines.push(line.replace(/ +$/, ''));
        let part = '';
        for (const ch of safeWord) {
          if (part && widthOf(part + ch) > max) {
            lines.push(part);
            part = '';
          }
          part += ch;
        }
        line = part;
      }
      lines.push(line);
    });
  return lines;
}
// Own drawing of the text box: background, border and text already split into lines, with the same measurements as on screen.
function textBoxAppearance(ctx, font, lines, w, h, colour) {
  const { bw, pad, fs, lh } = TEXT_BOX,
    round = (v) => +v.toFixed(3),
    lineH = fs * lh,
    base = (lineH - fs * 1.117) / 2 + fs * 0.905;
  let ops =
    hexToRgb(tint(colour, 0.14)).map(round).join(' ') +
    ' rg\n0 0 ' +
    round(w) +
    ' ' +
    round(h) +
    ' re f\n' +
    hexToRgb(colour).map(round).join(' ') +
    ' RG ' +
    bw +
    ' w\n' +
    round(bw / 2) +
    ' ' +
    round(bw / 2) +
    ' ' +
    round(w - bw) +
    ' ' +
    round(h - bw) +
    ' re S\nBT /Helv ' +
    fs +
    ' Tf 0 g\n';
  lines.forEach((ln, i) => {
    if (ln.trim())
      ops +=
        '1 0 0 1 ' +
        round(bw + pad) +
        ' ' +
        round(h - bw - pad - base - i * lineH) +
        ' Tm ' +
        font.encodeText(ln).toString() +
        ' Tj\n';
  });
  ops += 'ET';
  return ctx.register(
    ctx.stream(ops, {
      Type: 'XObject',
      Subtype: 'Form',
      FormType: 1,
      BBox: [0, 0, w, h],
      Resources: { Font: { Helv: font.ref } },
    }),
  );
}
// Own drawing of rectangles, circles and arrows, stroked SHAPE_STROKE points wide.
function shapeAppearance(ctx, a, bbox) {
  const round = (v) => +v.toFixed(3),
    rgb = hexToRgb(a.color).map(round).join(' ');
  let ops = rgb + ' RG ' + SHAPE_STROKE + ' w\n';
  const [minX, minY, maxX, maxY] = bbox;
  const w = Math.max(1, maxX - minX),
    h = Math.max(1, maxY - minY);
  if (a.type == 'sq') {
    ops +=
      round(SHAPE_STROKE / 2) +
      ' ' +
      round(SHAPE_STROKE / 2) +
      ' ' +
      round(w - SHAPE_STROKE) +
      ' ' +
      round(h - SHAPE_STROKE) +
      ' re S\n';
  } else if (a.type == 'ci') {
    const kappa = 0.5522848;
    const rx = (w - SHAPE_STROKE) / 2,
      ry = (h - SHAPE_STROKE) / 2;
    const cx = w / 2,
      cy = h / 2;
    ops += round(cx) + ' ' + round(cy + ry) + ' m\n';
    ops +=
      round(cx + rx * kappa) +
      ' ' +
      round(cy + ry) +
      ' ' +
      round(cx + rx) +
      ' ' +
      round(cy + ry * kappa) +
      ' ' +
      round(cx + rx) +
      ' ' +
      round(cy) +
      ' c\n';
    ops +=
      round(cx + rx) +
      ' ' +
      round(cy - ry * kappa) +
      ' ' +
      round(cx + rx * kappa) +
      ' ' +
      round(cy - ry) +
      ' ' +
      round(cx) +
      ' ' +
      round(cy - ry) +
      ' c\n';
    ops +=
      round(cx - rx * kappa) +
      ' ' +
      round(cy - ry) +
      ' ' +
      round(cx - rx) +
      ' ' +
      round(cy - ry * kappa) +
      ' ' +
      round(cx - rx) +
      ' ' +
      round(cy) +
      ' c\n';
    ops +=
      round(cx - rx) +
      ' ' +
      round(cy + ry * kappa) +
      ' ' +
      round(cx - rx * kappa) +
      ' ' +
      round(cy + ry) +
      ' ' +
      round(cx) +
      ' ' +
      round(cy + ry) +
      ' c S\n';
  } else if (a.type == 'ar') {
    const x1 = a.x - minX,
      y1 = a.y - minY;
    const x2 = a.x2 - minX,
      y2 = a.y2 - minY;
    ops += round(x1) + ' ' + round(y1) + ' m ' + round(x2) + ' ' + round(y2) + ' l S\n';
    const dx = x2 - x1,
      dy = y2 - y1;
    const angle = Math.atan2(dy, dx);
    const L = 10;
    const p1x = x2 - L * Math.cos(angle - Math.PI / 6),
      p1y = y2 - L * Math.sin(angle - Math.PI / 6);
    const p2x = x2 - L * Math.cos(angle + Math.PI / 6),
      p2y = y2 - L * Math.sin(angle + Math.PI / 6);
    ops += '1 J 1 j\n';
    ops +=
      round(p1x) +
      ' ' +
      round(p1y) +
      ' m ' +
      round(x2) +
      ' ' +
      round(y2) +
      ' l ' +
      round(p2x) +
      ' ' +
      round(p2y) +
      ' l S\n';
  }
  return ctx.register(
    ctx.stream(ops, { Type: 'XObject', Subtype: 'Form', FormType: 1, BBox: [0, 0, w, h], Resources: {} }),
  );
}
// Comment icon: the same drawing as on screen (Lucide message-square-text, black outline and fill in the annotation's colour), in a 20 × 20 point box.
function noteAppearance(ctx, a) {
  const round = (v) => +v.toFixed(3),
    k = 1.1046,
    ops =
      'q 1 0 0 -1 -2 22 cm\n' +
      hexToRgb(a.color).map(round).join(' ') +
      ' rg 0 0 0 RG ' +
      NOTE_STROKE +
      ' w 1 J 1 j\n' +
      '21 15 m 21 ' +
      round(15 + k) +
      ' ' +
      round(19 + k) +
      ' 17 19 17 c 7 17 l 3 21 l 3 5 l 3 ' +
      round(5 - k) +
      ' ' +
      round(5 - k) +
      ' 3 5 3 c 19 3 l ' +
      round(19 + k) +
      ' 3 21 ' +
      round(5 - k) +
      ' 21 5 c h B\n' +
      '13 8 m 7 8 l S 17 12 m 7 12 l S\nQ';
  return ctx.register(
    ctx.stream(ops, { Type: 'XObject', Subtype: 'Form', FormType: 1, BBox: [0, 0, 20, 20], Resources: {} }),
  );
}
// Forms (AcroForm): copyPages does not copy the catalogue's /AcroForm, so the fields were left loose. It is rebuilt with the fields
// whose widgets are on the final pages (removes the widgets of deleted pages, fixes /P and avoids duplicate names when merging).
function rebuildForm(out, src, pageList) {
  const { PDFName, PDFDict, PDFArray, PDFRef, PDFBool, PDFHexString, PDFObjectCopier } = PDFLib,
    ctx = out.context,
    name = (n) => PDFName.of(n);
  const pagesOut = out.getPages(),
    pageTags = new Set(pagesOut.map((q) => q.ref.tag)),
    roots = new Map(),
    onPage = new Set(),
    orphans = new Map(),
    dead = [];
  pagesOut.forEach((page, pageIdx) => {
    const annots = page.node.lookupMaybe(name('Annots'), PDFArray);
    if (!annots) return;
    for (let i = 0; i < annots.size(); i++) {
      const ref = annots.get(i);
      if (!(ref instanceof PDFRef)) continue;
      const d = ctx.lookupMaybe(ref, PDFDict);
      if (!d) continue;
      const pageRef = d.get(name('P'));
      if (pageRef instanceof PDFRef && pageRef.tag !== page.ref.tag) {
        if (!pageTags.has(pageRef.tag)) orphans.set(pageRef.tag, pageRef);
        d.set(name('P'), page.ref);
      }
      if (d.get(name('Subtype')) !== name('Widget')) continue;
      onPage.add(ref.tag);
      let r = ref,
        f = d;
      for (let g = 0; g < 50; g++) {
        const parentRef = f.get(name('Parent'));
        if (!(parentRef instanceof PDFRef)) break;
        const parentDict = ctx.lookupMaybe(parentRef, PDFDict);
        if (!parentDict) break;
        r = parentRef;
        f = parentDict;
      }
      if (!roots.has(r.tag)) roots.set(r.tag, { ref: r, doc: pageList[pageIdx] ? pageList[pageIdx].doc : 0 });
    }
  });
  // A field is kept if any of its widgets is on the final pages; widgets of deleted pages are removed from /Kids
  const keep = (ref, depth) => {
    const d = ctx.lookupMaybe(ref, PDFDict);
    if (!d || depth > 40) return false;
    const kids = d.lookupMaybe(name('Kids'), PDFArray);
    if (!kids) return onPage.has(ref.tag);
    const ok = [],
      bad = [];
    for (let i = 0; i < kids.size(); i++) {
      const k = kids.get(i);
      if (!(k instanceof PDFRef)) return true;
      if (keep(k, depth + 1)) ok.push(k);
      else bad.push(k);
    }
    if (bad.length) {
      d.set(name('Kids'), ctx.obj(ok));
      bad.forEach((b) => dead.push(b));
    }
    return ok.length > 0;
  };
  // The fields kept; when merging, a field name already used by another file gets a suffix (_2, _3…)
  const fields = [],
    fieldDocs = [],
    names = new Map(),
    renamed = new Map();
  roots.forEach(({ ref, doc }) => {
    if (!keep(ref, 0)) return;
    const d = ctx.lookupMaybe(ref, PDFDict),
      t = d.get(name('T'));
    if (t && t.decodeText) {
      let fieldName = t.decodeText();
      const own = names.get(fieldName),
        orig = fieldName;
      if (own !== undefined && own !== doc) {
        let k = 2;
        while (names.has(fieldName + '_' + k)) k++;
        fieldName = fieldName + '_' + k;
        d.set(name('T'), PDFHexString.fromText(fieldName));
        renamed.set(doc + '|' + orig, fieldName);
      }
      names.set(fieldName, doc);
    }
    fields.push(ref);
    fieldDocs.push(doc);
  });
  if (!fields.length) return null;
  // The new /AcroForm takes the default appearance (DA), alignment (Q) and resources (DR: fonts) of the source files
  const acroForm = ctx.obj({ Fields: fields });
  for (const docIndex of [...new Set(fieldDocs)]) {
    const srcForm = src[docIndex] && src[docIndex].catalog.lookupMaybe(name('AcroForm'), PDFDict);
    if (!srcForm) continue;
    if (!acroForm.has(name('DA'))) {
      const v = srcForm.lookup(name('DA'));
      if (v) acroForm.set(name('DA'), v);
    }
    if (!acroForm.has(name('Q'))) {
      const v = srcForm.lookup(name('Q'));
      if (v) acroForm.set(name('Q'), v);
    }
    if (srcForm.lookup(name('NeedAppearances')) === PDFBool.True) acroForm.set(name('NeedAppearances'), PDFBool.True);
    const srcResources = srcForm.get(name('DR'));
    if (!srcResources) continue;
    const copied = PDFObjectCopier.for(src[docIndex].context, ctx).copy(srcResources);
    if (!acroForm.has(name('DR'))) {
      acroForm.set(name('DR'), copied);
      continue;
    }
    const merged = ctx.lookupMaybe(acroForm.get(name('DR')), PDFDict),
      copiedDict = ctx.lookupMaybe(copied, PDFDict);
    if (merged && copiedDict)
      copiedDict.entries().forEach(([k, v]) => {
        if (!merged.has(k)) {
          merged.set(k, v);
          return;
        }
        const a = ctx.lookupMaybe(merged.get(k), PDFDict),
          b = ctx.lookupMaybe(v, PDFDict);
        if (a && b)
          b.entries().forEach(([kk, vv]) => {
            if (!a.has(kk)) a.set(kk, vv);
          });
      });
  }
  out.catalog.set(name('AcroForm'), ctx.register(acroForm));
  // Clean-up: page copies that are no longer used (they used to be pointed at by /P) and widgets of deleted pages
  orphans.forEach((r) => {
    const o = ctx.lookupMaybe(r, PDFDict);
    if (o && o.get(name('Type')) === name('Page') && !pageTags.has(r.tag)) ctx.delete(r);
  });
  dead.forEach((r) => ctx.delete(r));
  return renamed;
}
// Phase 3: writes the values filled in on screen (docs[…].fv) into the final PDF's fields, only the fields that were touched (fvDirty).
// It is still an editable form. Returns how many fields could not be written.
async function writeFormValues(out, renamed, flatten) {
  const { PDFTextField, PDFCheckBox, PDFRadioGroup, PDFDropdown, PDFOptionList, PDFHexString, PDFName, PDFBool } =
    PDFLib;
  if (!docs.some((d) => d && d.fvDirty && d.fvDirty.size) || !out.catalog.has(PDFName.of('AcroForm'))) return 0;
  const form = out.getForm(),
    font = await out.embedFont(PDFLib.StandardFonts.Helvetica);
  let bad = 0,
    needAppearances = false;
  const canEncode = (t) =>
    t.split(/\r\n|\r|\n/).every((l) => {
      try {
        font.encodeText(l);
        return true;
      } catch (e) {
        return false;
      }
    });
  const encodable = (t) =>
    [...t]
      .map((c) => {
        try {
          font.encodeText(c);
          return c;
        } catch (e) {
          return /[\r\n]/.test(c) ? c : '?';
        }
      })
      .join('');
  docs.forEach((d, di) => {
    if (!d || !d.fvDirty) return;
    d.fvDirty.forEach((name) => {
      try {
        const root = name.split('.')[0],
          fullName = (renamed.get(di + '|' + root) || root) + name.slice(root.length),
          field = form.getFieldMaybe(fullName);
        if (!field) return;
        const value = d.fv[name];
        if (field instanceof PDFTextField) {
          const text = Array.isArray(value) ? value.join('\n') : String(value == null ? '' : value);
          if (canEncode(text)) {
            field.setText(text === '' ? undefined : text);
            field.defaultUpdateAppearances(font);
          } else if (flatten) {
            const safeText = encodable(text);
            field.setText(safeText === '' ? undefined : safeText);
            field.defaultUpdateAppearances(font);
          } else {
            field.acroField.setValue(PDFHexString.fromText(text));
            needAppearances = true;
          }
        } else if (field instanceof PDFCheckBox) {
          value ? field.check() : field.uncheck();
        }
        // Radio buttons: the value on screen is the button's state name; select() wants the option, which differs when the
        // group has /Opt (states "0", "1"… and options "small", "large"…), so the state is translated to its option
        else if (field instanceof PDFRadioGroup) {
          if (!value) field.clear();
          else {
            const s = String(value),
              options = field.getOptions(),
              k = field.acroField.getOnValues().findIndex((n) => n.decodeText() === s);
            field.select(k >= 0 && options[k] !== undefined ? options[k] : s);
          }
        } else if (field instanceof PDFDropdown || field instanceof PDFOptionList) {
          const vals = (Array.isArray(value) ? value : value ? [String(value)] : []).map((x) =>
            PDFHexString.fromText(String(x)),
          );
          if (flatten) {
            const options = field.acroField.getOptions(),
              displayOf = (x) => {
                const o = options.find((q) => q.value.decodeText() === x);
                return o && o.display ? o.display.decodeText() : x;
              };
            field.acroField.setValues(vals.map((x) => PDFHexString.fromText(encodable(displayOf(x.decodeText())))));
            field.markAsDirty();
            field.defaultUpdateAppearances(font);
          } else {
            field.acroField.setValues(vals);
            field.markAsDirty();
            if (
              field.acroField.getOptions().some((o) => o.display && o.display.decodeText() !== o.value.decodeText()) ||
              !vals.every((x) => canEncode(x.decodeText()))
            )
              needAppearances = true;
            else field.defaultUpdateAppearances(font);
          }
        }
      } catch (e) {
        bad++;
        console.warn('Form field not saved:', name, e);
      }
    });
  });
  if (needAppearances && !flatten) form.acroForm.dict.set(PDFName.of('NeedAppearances'), PDFBool.True);
  return bad;
}
// Phase 4: flatten. Draws each field's appearance (its /AP) as fixed page content, following the standard's algorithm
// (ISO 32000-1, 12.5.5: the transformed appearance box is fitted to the field's /Rect), and removes the widgets and the /AcroForm.
function flattenForm(out) {
  const lib = PDFLib,
    name = (n) => lib.PDFName.of(n),
    ctx = out.context,
    form = out.getForm(),
    numbers = (a) => (a ? a.asArray().map((x) => x.asNumber()) : null);
  const pageOf = new Map();
  out.getPages().forEach((page) => {
    const a = page.node.lookupMaybe(name('Annots'), lib.PDFArray);
    if (a)
      for (let i = 0; i < a.size(); i++) {
        const r = a.get(i);
        if (r instanceof lib.PDFRef) pageOf.set(r.tag, page);
      }
  });
  const appearanceOf = (widget) => {
    const apDict = widget.dict.lookupMaybe(name('AP'), lib.PDFDict);
    if (!apDict) return null;
    const n = apDict.get(name('N')),
      o = n instanceof lib.PDFRef ? ctx.lookup(n) : n;
    if (o instanceof lib.PDFStream) return n instanceof lib.PDFRef ? n : null;
    if (o instanceof lib.PDFDict) {
      const as = widget.dict.lookupMaybe(name('AS'), lib.PDFName),
        r = as && o.get(as);
      if (r instanceof lib.PDFRef && ctx.lookup(r) instanceof lib.PDFStream) return r;
    }
    return null;
  };
  form
    .getFields()
    .slice()
    .forEach((f) => {
      f.acroField.getWidgets().forEach((widget) => {
        const widgetRef = ctx.getObjectRef(widget.dict),
          page = widgetRef && pageOf.get(widgetRef.tag);
        if (!page) return;
        try {
          const flags = widget.dict.lookupMaybe(name('F'), lib.PDFNumber),
            apRef = appearanceOf(widget);
          if (apRef && !(flags && flags.asNumber() & 34)) {
            const stream = ctx.lookup(apRef),
              bbox = numbers(stream.dict.lookupMaybe(name('BBox'), lib.PDFArray)),
              matrix = numbers(stream.dict.lookupMaybe(name('Matrix'), lib.PDFArray)) || [1, 0, 0, 1, 0, 0],
              rect = numbers(widget.dict.lookupMaybe(name('Rect'), lib.PDFArray));
            if (bbox && rect && bbox.length == 4 && rect.length == 4) {
              const xs = [],
                ys = [];
              [
                [bbox[0], bbox[1]],
                [bbox[2], bbox[1]],
                [bbox[0], bbox[3]],
                [bbox[2], bbox[3]],
              ].forEach(([x, y]) => {
                xs.push(matrix[0] * x + matrix[2] * y + matrix[4]);
                ys.push(matrix[1] * x + matrix[3] * y + matrix[5]);
              });
              const x0 = Math.min(...xs),
                x1 = Math.max(...xs),
                y0 = Math.min(...ys),
                y1 = Math.max(...ys),
                rx = Math.min(rect[0], rect[2]),
                ry = Math.min(rect[1], rect[3]),
                rw = Math.abs(rect[2] - rect[0]),
                rh = Math.abs(rect[3] - rect[1]);
              if (x1 > x0 && y1 > y0 && rw > 0 && rh > 0) {
                const scaleX = rw / (x1 - x0),
                  scaleY = rh / (y1 - y0),
                  key = page.node.newXObject('FlatWidget', apRef);
                page.pushOperators(
                  lib.pushGraphicsState(),
                  lib.concatTransformationMatrix(scaleX, 0, 0, scaleY, rx - x0 * scaleX, ry - y0 * scaleY),
                  lib.drawObject(key),
                  lib.popGraphicsState(),
                );
              }
            }
          }
        } catch (e) {
          console.warn('Field not flattened:', e);
        }
        page.node.removeAnnot(widgetRef);
        ctx.delete(widgetRef);
      });
      let parent = f.acroField.dict.get(name('Parent')),
        g = 0;
      while (parent instanceof lib.PDFRef && g++ < 50) {
        const next = ctx.lookupMaybe(parent, lib.PDFDict);
        ctx.delete(parent);
        parent = next && next.get(name('Parent'));
      }
      ctx.delete(f.ref);
    });
  out.catalog.delete(name('AcroForm'));
}
// Builds the PDF to save (bytes) with pdf-lib: copies the pages in their current order and rotation, adds Penfold's
// annotations (each with its own drawing), keeps the form and writes the bookmarks. opts can give other pages (pages),
// other source files (src), only some annotation types (types), no annotations (noAnnots), no bookmarks (noBms) or
// flatten the form (flatten)
async function build(opts = {}) {
  const { PDFDocument, PDFName, PDFString, PDFHexString, degrees } = PDFLib,
    out = await PDFDocument.create(),
    refs = new Map();
  const src = opts.src || (await Promise.all(docs.map((d) => PDFDocument.load(d.bytes, { ignoreEncryption: true }))));
  // Safety net: pdf-lib cannot decrypt, so a protected PDF would come out broken (or not at all)
  if (src.some((s) => s && s.isEncrypted))
    throw new Error(
      _t('This PDF is protected against changes: Penfold cannot save it, print it or extract pages from it yet.'),
    );
  const pageList = opts.pages || pages,
    noAnnots = !!opts.noAnnots;
  let helvetica = null;
  // One copyPages call per document: form fields shared between pages are copied only once
  const copies = new Map(),
    usedCopies = new Set();
  for (let di = 0; di < src.length; di++) {
    const indices = [...new Set(pageList.filter((q) => q.doc == di).map((q) => q.idx))];
    if (!indices.length) continue;
    const copied = await out.copyPages(src[di], indices);
    indices.forEach((x, k) => copies.set(di + ':' + x, copied[k]));
  }
  for (const p of pageList) {
    const key = p.doc + ':' + p.idx;
    let copy = copies.get(key);
    if (!copy || usedCopies.has(key)) copy = (await out.copyPages(src[p.doc], [p.idx]))[0];
    usedCopies.add(key);
    out.addPage(copy);
    refs.set(p, copy.ref);
    if (p.rot) copy.setRotation(degrees((src[p.doc].getPage(p.idx).getRotation().angle + p.rot) % 360));
    const ctx = out.context;
    // Penfold's own annotations already in the file (author “Penfold”) are taken out: they are written again from what
    // is on screen, so deleted ones disappear and edited ones are not doubled
    if (p.loaded || noAnnots) {
      const annotsRef = copy.node.get(PDFName.of('Annots'));
      if (annotsRef) {
        const annotsObj = ctx.lookup(annotsRef);
        if (annotsObj && annotsObj.array) {
          const kept = annotsObj.array.filter((ref) => {
            const obj = ctx.lookup(ref);
            if (obj && typeof obj.get === 'function') {
              const t = obj.get(PDFName.of('T'));
              if (t) {
                const tStr = t.decodeText ? t.decodeText() : t.value || '';
                if (tStr === 'Penfold') return false;
              }
            }
            return true;
          });
          copy.node.set(PDFName.of('Annots'), ctx.obj(kept));
        }
      }
    }
    for (const a of noAnnots ? [] : opts.types ? p.annots.filter((a) => opts.types.has(a.type)) : p.annots) {
      if (a.type == 'link' || a.ro) continue;
      let dict;
      const base = { Type: 'Annot', F: 4, C: hexToRgb(a.color), T: PDFString.of('Penfold') };
      if (a.type == 'note' || a.type == 'ft') base.Contents = PDFHexString.fromText(a.text || '');
      if (a.quads) {
        const all = a.quads.flat(),
          xs = all.filter((_, i) => i % 2 == 0),
          ys = all.filter((_, i) => i % 2);
        const rect = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
        dict = ctx.obj({
          ...base,
          Subtype: a.type == 'hl' ? 'Highlight' : a.type == 'ul' ? 'Underline' : 'StrikeOut',
          Rect: rect,
          QuadPoints: all,
          CA: a.type == 'hl' ? HIGHLIGHT_OPACITY : 1,
          AP: { N: markupAppearance(ctx, a, rect) },
        });
      } else if (a.type == 'sq' || a.type == 'ci' || a.type == 'ar') {
        let rect;
        if (a.type == 'ar') {
          rect = [
            Math.min(a.x, a.x2) - 15,
            Math.min(a.y, a.y2) - 15,
            Math.max(a.x, a.x2) + 15,
            Math.max(a.y, a.y2) + 15,
          ];
        } else {
          rect = [Math.min(a.x, a.x2), Math.min(a.y, a.y2), Math.max(a.x, a.x2), Math.max(a.y, a.y2)];
        }
        dict = ctx.obj({
          ...base,
          Subtype: a.type == 'sq' ? 'Square' : a.type == 'ci' ? 'Circle' : 'Line',
          Rect: rect,
          C: hexToRgb(a.color),
          BS: { W: SHAPE_STROKE, S: 'S' },
          AP: { N: shapeAppearance(ctx, a, rect) },
        });
        if (a.type == 'ar') {
          dict.set(PDFName.of('L'), ctx.obj([a.x, a.y, a.x2, a.y2]));
          dict.set(PDFName.of('LE'), ctx.obj([PDFName.of('None'), PDFName.of('OpenArrow')]));
        }
      } else if (a.type == 'note')
        dict = ctx.obj({
          ...base,
          Subtype: 'Text',
          Rect: [a.x - 10, a.y - 10, a.x + 10, a.y + 10],
          Name: 'Note',
          AP: { N: noteAppearance(ctx, a) },
        });
      else {
        const w = a.w || TEXT_BOX.w,
          c = deep(a.color),
          font = helvetica || (helvetica = await out.embedFont(PDFLib.StandardFonts.Helvetica)),
          lines = textBoxLines(font, a.text, w),
          h = 2 * (TEXT_BOX.bw + TEXT_BOX.pad) + lines.length * TEXT_BOX.fs * TEXT_BOX.lh,
          pad2 = (x) => String(x).padStart(2, '0'),
          now = new Date();
        dict = ctx.obj({
          ...base,
          C: hexToRgb(c),
          IC: hexToRgb(tint(c, 0.14)),
          BS: { W: TEXT_BOX.bw, S: 'S' },
          Subtype: 'FreeText',
          Rect: [a.x, a.y - h, a.x + w, a.y],
          DA: PDFString.of('/Helv 11 Tf 0 0 0 rg'),
          Q: 0,
          M: PDFString.of(
            'D:' +
              now.getUTCFullYear() +
              pad2(now.getUTCMonth() + 1) +
              pad2(now.getUTCDate()) +
              pad2(now.getUTCHours()) +
              pad2(now.getUTCMinutes()) +
              pad2(now.getUTCSeconds()) +
              'Z',
          ),
          AP: { N: textBoxAppearance(ctx, font, lines, w, h, c) },
        });
      }
      Object.keys(dict.dict ? dict.dict : {});
      copy && out.getPage(out.getPageCount() - 1).node.addAnnot(ctx.register(dict));
    }
  }
  let renamedFields = null;
  try {
    renamedFields = rebuildForm(out, src, pageList);
  } catch (e) {
    console.warn('Form not preserved:', e);
  }
  if (renamedFields) {
    try {
      const bad = await writeFormValues(out, renamedFields, !!opts.flatten);
      if (bad) showMessage(_t('{n} form field(s) could not be saved.', { n: bad }));
    } catch (e) {
      console.warn('Form data not saved:', e);
      if (opts.flatten) throw new Error(_t('Could not flatten the form: {m}', { m: e.message }), { cause: e });
      showMessage(_t('The form data could not be saved.'));
    }
    if (opts.flatten) {
      try {
        flattenForm(out);
      } catch (e) {
        throw new Error(_t('Could not flatten the form: {m}', { m: e.message }), { cause: e });
      }
    }
  }
  // Bookmarks (the PDF outline): a linked list per level (Prev / Next, First / Last); Count is negative for collapsed ones
  const items = noAnnots || opts.noBms ? [] : pruneBookmarks(bookmarks, pageList);
  if (items.length) {
    const ctx = out.context,
      root = ctx.nextRef(),
      countAll = (l) => l.reduce((n, i) => n + 1 + countAll(i.items), 0),
      countVisible = (l) => l.reduce((n, i) => n + 1 + (i.open === false ? 0 : countVisible(i.items)), 0);
    const writeOutline = (list, parent) => {
      const itemRefs = list.map(() => ctx.nextRef());
      list.forEach((it, i) => {
        const entry = {
          Title: PDFHexString.fromText(it.title),
          Parent: parent,
          Dest: [refs.get(it.page), ...(isValidDest(it.dd) ? [it.dd.n, ...it.dd.a] : ['Fit'])],
        };
        if (it.color) entry.C = hexToRgb(it.color);
        const flags = (it.italic ? 1 : 0) | (it.bold ? 2 : 0);
        if (flags) entry.F = flags;
        if (i > 0) entry.Prev = itemRefs[i - 1];
        if (i < list.length - 1) entry.Next = itemRefs[i + 1];
        if (it.items.length) {
          const children = writeOutline(it.items, itemRefs[i]);
          entry.First = children[0];
          entry.Last = children[children.length - 1];
          entry.Count = it.open === false ? -countAll(it.items) : countVisible(it.items);
        }
        ctx.assign(itemRefs[i], ctx.obj(entry));
      });
      return itemRefs;
    };
    const top = writeOutline(items, root);
    ctx.assign(
      root,
      ctx.obj({ Type: 'Outlines', First: top[0], Last: top[top.length - 1], Count: countVisible(items) }),
    );
    out.catalog.set(PDFName.of('Outlines'), root);
    out.catalog.set(PDFName.of('PageMode'), PDFName.of('UseOutlines'));
  }
  return out.save({ updateFieldAppearances: false });
}
// Writes the PDF into the file of handle (flatten: with the form flattened)
async function save(handle, flatten) {
  const bytes = await build(flatten ? { flatten: true } : {}),
    writable = await handle.createWritable();
  await writable.write(bytes);
  await writable.close();
  // A flattened copy is an export: the working document still has its changes unsaved
  if (!flatten) markSaved();
  showMessage(flatten ? _t('Saved ✔ (form flattened)') : _t('Saved ✔'));
}
// Does the open document have fillable form fields?
const hasForm = () =>
  pages.some(
    (p) =>
      p.widgets &&
      p.widgets.some((w) => w.fieldType == 'Tx' || w.fieldType == 'Ch' || (w.fieldType == 'Btn' && !w.pushButton)),
  );
// “Save As…” dialogue for documents with a form: returns true (flatten), false (keep editable) or null (cancel)
function flattenDialog() {
  return new Promise((resolve) => {
    if (document.getElementById('dlg')) return resolve(null);
    const overlay = document.createElement('div');
    overlay.id = 'dlg';
    overlay.innerHTML =
      '<div class="box"><h3>Save As</h3><div class="card"><label class="srow"><span class="txt"><span>Flatten the form</span><span class="sub">The data becomes part of the page and the fields can no longer be edited in the saved file.</span></span><input type="checkbox" id="fFlat" class="switch"></label></div><div class="row r"><button id="fCancel">Cancel</button><button id="fOk" class="on">Save</button></div></div>';
    i18nApply(overlay);
    const finish = (v) => {
        overlay.remove();
        document.removeEventListener('keydown', onKey);
        resolve(v);
      },
      onKey = (e) => {
        if (e.key == 'Escape') finish(null);
        else if (e.key == 'Enter' && !document.getElementById('dlg2')) {
          e.preventDefault();
          finish(overlay.querySelector('#fFlat').checked);
        }
      };
    overlay.querySelector('#fCancel').onclick = () => finish(null);
    overlay.querySelector('#fOk').onclick = () => finish(overlay.querySelector('#fFlat').checked);
    document.addEventListener('keydown', onKey);
    document.body.appendChild(overlay);
    overlay.querySelector('#fOk').focus();
  });
}
// Save: overwrites the opened file after asking; without a file handle it does “Save As…” or, if the browser cannot
// write files, downloads a copy
$('#bSave').onclick = async () => {
  try {
    if (fileHandle) {
      if (
        !(await confirmDialog(
          _t('Overwrite file'),
          _t('Do you want to overwrite “{name}”?', { name: fileName }),
          _t('Overwrite'),
        ))
      )
        return;
      await save(fileHandle);
    } else if (window.showSaveFilePicker) $('#bSaveAs').click();
    else {
      showMessage(_t('This browser cannot overwrite files: a copy is being downloaded.'));
      download();
    }
  } catch (e) {
    if (e.name != 'AbortError') showMessage('Error: ' + e.message);
  }
};
// “Save As…”: returns true if a file was written (false if cancelled)
async function saveAs() {
  let flatten = false;
  if (hasForm()) {
    flatten = await flattenDialog();
    if (flatten === null) return false;
  }
  if (!window.showSaveFilePicker) {
    await download(flatten);
    return true;
  }
  const handle = await showSaveFilePicker({
    suggestedName: fileName,
    types: [{ accept: { 'application/pdf': ['.pdf'] } }],
  });
  await save(handle, flatten);
  // A flattened copy is an export: it does not become the working file (so that “Save” never overwrites it with the editable version)
  if (!flatten) {
    fileHandle = handle;
    fileName = handle.name;
  }
  return true;
}
// Save As… button
$('#bSaveAs').onclick = async () => {
  try {
    await saveAs();
  } catch (e) {
    if (e.name != 'AbortError') showMessage('Error: ' + e.message);
  }
};
// Browsers that cannot write files: the PDF is downloaded as “name_annotated.pdf” (or “_flattened.pdf”)
async function download(flatten) {
  const blob = new Blob([await build(flatten ? { flatten: true } : {})], { type: 'application/pdf' }),
    link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = fileName.replace(/\.pdf$/i, '') + (flatten ? _t('_flattened.pdf') : _t('_annotated.pdf'));
  link.click();
  if (!flatten) markSaved();
}
// ---- Unsaved changes. Penfold remembers how the document was when it was opened or last saved, and compares it with
// how it is now: page order and rotation, bookmarks and form values (docShape), and each of Penfold's own annotations
// (a snapshot in a._o, and how many there were per page in p._nOwn). Undoing a change by hand leaves nothing to save.
// A merged document has never been saved (savedShape = null).
let savedShape = '';
// annotSnapshot: an annotation as text, to compare it with its saved copy; ownAnnots: the annotations Penfold can edit
const annotSnapshot = (a) => JSON.stringify(a, (k, v) => (k == '_o' ? undefined : v));
const ownAnnots = (p) => p.annots.filter((a) => !a.ro && a.type != 'link');
// The state of the document as text: pages (file, page, rotation), bookmarks and form values
function docShape() {
  const bookmarkShape = (l) =>
    l.map((b) => [
      b.title,
      pages.indexOf(b.page),
      b.dd || null,
      b.color || null,
      !!b.bold,
      !!b.italic,
      bookmarkShape(b.items),
    ]);
  return JSON.stringify([
    pages.map((p) => [p.doc, p.idx, p.rot || 0]),
    bookmarkShape(bookmarks),
    docs.map((d) => (d && d.fv) || {}),
  ]);
}
// Remembers the annotations of a page as saved
function markPageSaved(page) {
  const own = ownAnnots(page);
  own.forEach((a) => (a._o = annotSnapshot(a)));
  page._nOwn = own.length;
}
// After opening or saving, the current state becomes the saved one (never = a document that has not been saved yet)
function markSaved(never) {
  savedShape = never ? null : docShape();
  pages.forEach(markPageSaved);
}
// True if something differs from the saved state: the document, or an own annotation changed, added or deleted
function hasUnsavedChanges() {
  if (!pages.length) return false;
  if (savedShape === null || docShape() !== savedShape) return true;
  return pages.some((p) => {
    const own = ownAnnots(p);
    return own.some((a) => a._o !== annotSnapshot(a)) || own.filter((a) => a._o).length !== (p._nOwn || 0);
  });
}
// What to do with unsaved changes: 'save', 'discard' or 'cancel'. A protected PDF cannot be saved: Discard or Cancel.
// As in GNOME, the text is centred and Discard, which loses the changes, is shown in red.
function unsavedDialog() {
  const locked = isLocked(),
    answer = locked
      ? choiceDialog(
          _t('Discard the changes to “{name}”?', { name: fileName }),
          _t('This PDF is protected: its changes cannot be saved and will be lost.'),
          [
            [_t('Cancel'), 'cancel'],
            [_t('Discard'), 'discard', false, 'danger'],
          ],
        )
      : choiceDialog(
          _t('Save changes to “{name}”?', { name: fileName }),
          _t('If you don’t save, your changes will be lost.'),
          [
            [_t('Cancel'), 'cancel'],
            [_t('Discard'), 'discard', false, 'danger'],
            [_t('Save'), 'save', true],
          ],
        );
  document.querySelector('#dlg2 .box>div').style.textAlign = 'center';
  const focusBtn = document.querySelector('#dlg2 button.on') || document.querySelector('#dlg2 button.danger');
  if (focusBtn) focusBtn.focus();
  return answer;
}
// Before the document is replaced (Open, Merge, a PDF from the desktop) or the window is closed.
// true = go ahead (nothing to save, discarded or saved); false = stop.
async function confirmUnsaved() {
  if (!hasUnsavedChanges()) return true;
  const answer = await unsavedDialog();
  if (answer == 'discard') return true;
  if (answer != 'save') return false;
  try {
    if (fileHandle) {
      await save(fileHandle);
      return true;
    }
    return await saveAs();
  } catch (e) {
    if (e.name != 'AbortError') showMessage('Error: ' + e.message);
    return false;
  }
}
// Closing the browser tab with unsaved changes: the browser asks with its own (generic) message
window.addEventListener('beforeunload', (e) => {
  if (!hasUnsavedChanges()) return;
  e.preventDefault();
  e.returnValue = '';
});
// Places the imported bookmarks according to the insertion point (at = position of the first new page)
function placeBookmarks(list, at, nodes) {
  let prevBm = null,
    prevIdx = -1;
  list.forEach((it, i) => {
    if (pages.indexOf(it.page) < at) {
      prevBm = it;
      prevIdx = i;
    }
  });
  if (!prevBm) {
    list.unshift(...nodes);
    return;
  }
  const hasLater = (l) => l.some((c) => pages.indexOf(c.page) >= at || hasLater(c.items));
  if (prevBm.items.length && hasLater(prevBm.items)) {
    prevBm.open = true;
    placeBookmarks(prevBm.items, at, nodes);
  } else list.splice(prevIdx + 1, 0, ...nodes);
}
// Adds the pages of PDF file (and its bookmarks) at the start, at the end or after page afterN
async function insertPdf(file, mode, afterN, blank) {
  const bytes = await file.arrayBuffer(),
    pdf = await pdfjsLib.getDocument({ data: bytes.slice(0), isEvalSupported: false }).promise;
  if (await isProtected(pdf, bytes))
    throw new Error(_t('“{name}” is protected against changes and cannot be added yet.', { name: file.name }));
  const docIndex = docs.push({ bytes, pdf }) - 1,
    newPages = [];
  for (let i = 0; i < pdf.numPages; i++)
    newPages.push({ doc: docIndex, idx: i, annots: [], thumb: null, rot: 0, loaded: false });
  const at = mode == 'start' ? 0 : mode == 'end' ? pages.length : afterN;
  pages.splice(at, 0, ...newPages);
  const nodes = pruneBookmarks(await convertOutline((await pdf.getOutline()) || [], docIndex));
  if (nodes.length) {
    placeBookmarks(bookmarks, at, nodes);
    flashBookmark = nodes[0];
  }
  renderSide();
  await renderMain();
  goTo(at);
  loadAllAnnots();
  {
    const count = _n(newPages.length, '{n} page', '{n} pages');
    showMessage(
      blank
        ? _t('Blank page added.')
        : nodes.length
          ? _t('PDF added: {pn} and its bookmarks.', { pn: count })
          : _t('PDF added: {pn}.', { pn: count }),
    );
  }
}
// Blank page: a single-page PDF created on the spot, which goes in just like an added PDF
async function insertBlank(size, mode, afterN) {
  const SIZES = { a4: [595.28, 841.89], letter: [612, 792], a5: [419.53, 595.28], a3: [841.89, 1190.55] };
  const [w, h] = SIZES[size] || SIZES.a4;
  const doc = await PDFLib.PDFDocument.create();
  doc.addPage([w, h]);
  await insertPdf(new Blob([await doc.save()], { type: 'application/pdf' }), mode, afterN, true);
}
// “Add pages” dialogue: pages from a PDF or a blank page, at the start, at the end or after a page
function addDialog() {
  if (!pages.length) return;
  let file = null;
  const overlay = document.createElement('div');
  overlay.id = 'dlg';
  overlay.innerHTML = `<div class="box"><h3>Add pages</h3>
  <label><input type="radio" name="ds" value="pdf" checked> From a PDF</label>
  <div class="row"><button id="dPick">Choose PDF…</button><span id="dName">No file chosen</span></div>
  <label><input type="radio" name="ds" value="blank"> Blank page</label>
  <div class="row">Size: <select id="dSize"><option value="a4">A4</option><option value="letter">Letter</option><option value="a5">A5</option><option value="a3">A3</option></select></div>
  <b>Where should they be added?</b>
  <label><input type="radio" name="dw" value="start"> At the start</label>
  <label><input type="radio" name="dw" value="end" checked> At the end</label>
  <label><input type="radio" name="dw" value="after"> After page <input id="dN" type="number" min="1" max="${pages.length}" value="${currentPage + 1}"></label>
  <div class="row r"><button id="dCancel">Cancel</button><button id="dOk" class="on" disabled>Add</button></div></div>`;
  i18nApply(overlay);
  document.body.appendChild(overlay);
  const close = () => {
      overlay.remove();
      document.removeEventListener('keydown', onKey);
    },
    onKey = (e) => {
      if (e.key == 'Escape') close();
    };
  document.addEventListener('keydown', onKey);
  const picker = document.createElement('input');
  picker.type = 'file';
  picker.accept = '.pdf,application/pdf';
  const source = () => overlay.querySelector('input[name=ds]:checked').value,
    okState = () => {
      overlay.querySelector('#dOk').disabled = source() == 'pdf' && !file;
    };
  picker.onchange = () => {
    file = picker.files[0];
    if (file) {
      overlay.querySelector('#dName').textContent = file.name;
      overlay.querySelector('input[name=ds][value=pdf]').checked = true;
      okState();
    }
  };
  overlay.querySelector('#dPick').onclick = () => picker.click();
  overlay.querySelectorAll('input[name=ds]').forEach((r) => (r.onchange = okState));
  overlay.querySelector('#dSize').onchange = () => {
    overlay.querySelector('input[name=ds][value=blank]').checked = true;
    okState();
  };
  overlay.querySelector('#dSize').onfocus = overlay.querySelector('#dSize').onchange;
  overlay.querySelector('#dN').oninput = () => (overlay.querySelector('input[value=after]').checked = true);
  overlay.querySelector('#dCancel').onclick = close;
  overlay.querySelector('#dOk').onclick = async () => {
    const mode = overlay.querySelector('input[name=dw]:checked').value,
      n = parseInt(overlay.querySelector('#dN').value);
    if (mode == 'after' && !(n >= 1 && n <= pages.length)) {
      showMessage(_t('The page must be between 1 and {n}.', { n: pages.length }));
      return;
    }
    const kind = source(),
      size = overlay.querySelector('#dSize').value;
    close();
    showMessage(_t('Adding…'));
    try {
      if (kind == 'blank') await insertBlank(size, mode, n);
      else await insertPdf(file, mode, n);
    } catch (e) {
      showMessage(_t('Error adding: {m}', { m: e.message }));
    }
  };
}
// ---- Find: the text of each page is read without painting it; ignores case and accents
// findState: the search state. q: what is searched (normalised); hits: the matches ({ p: page, s: start, e: end });
// i: the current one; tok: increases with each search, so an older search that is still running stops; by: matches per
// page; ref: the pages when the search ran (to know if they changed)
const findState = { q: '', hits: [], i: -1, tok: 0, busy: false, by: null, ref: [] };
// foldChar / foldText: lower case and no accents (“Canción” → “cancion”); foldText also merges spaces
const foldChar = (c) =>
  c
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
const foldText = (text) => {
  let out = '';
  for (let o = 0; o < text.length; o++) {
    const folded = foldChar(text[o]);
    for (let k = 0; k < folded.length; k++) {
      const ch = /\s/.test(folded[k]) ? ' ' : folded[k];
      if (ch == ' ' && (out === '' || out.endsWith(' '))) continue;
      out += ch;
    }
  }
  return out.trim();
};
// Normalised page text, with the mapping of each character to its fragment (mi) and its position within it (mo)
function pageText(items) {
  let text = '',
    prev = null;
  const itemOf = [],
    offsetOf = [];
  items.forEach((it, k) => {
    if (prev && text && !text.endsWith(' ')) {
      const h = it.height || prev.height || 10,
        dy = Math.abs(it.transform[5] - prev.transform[5]),
        gap = it.transform[4] - (prev.transform[4] + prev.width);
      if (prev.hasEOL || dy > h * 0.5 || gap > h * 0.15) {
        text += ' ';
        itemOf.push(-1);
        offsetOf.push(0);
      }
    }
    const str = it.str;
    for (let o = 0; o < str.length; o++) {
      const folded = foldChar(str[o]);
      for (let q = 0; q < folded.length; q++) {
        const ch = /\s/.test(folded[q]) ? ' ' : folded[q];
        if (ch == ' ' && (text === '' || text.endsWith(' '))) continue;
        text += ch;
        itemOf.push(k);
        offsetOf.push(o);
      }
    }
    prev = it;
  });
  return { items, n: text, mi: itemOf, mo: offsetOf };
}
// The text of a page (read once and kept)
async function getPageText(page) {
  if (page._tx) return page._tx;
  const pdfPage = await docs[page.doc].pdf.getPage(page.idx + 1),
    content = await pdfPage.getTextContent();
  return (page._tx = pageText(content.items.filter((i) => typeof i.str == 'string')));
}
// Rectangles (in page pixels) of a match: one for each text fragment it crosses
function hitRects(hit, viewport) {
  const text = hit.p._tx,
    spans = {},
    out = [];
  for (let k = hit.s; k < hit.e; k++) {
    const i = text.mi[k];
    if (i < 0) continue;
    const o = text.mo[k],
      g = spans[i] || (spans[i] = [o, o + 1]);
    if (o < g[0]) g[0] = o;
    if (o + 1 > g[1]) g[1] = o + 1;
  }
  for (const i in spans) {
    const it = text.items[i],
      [a, b, c, d, e, f] = it.transform,
      L = it.str.length || 1,
      [o1, o2] = spans[i],
      lu = Math.hypot(a, b) || 1,
      lv = Math.hypot(c, d) || 1,
      ux = a / lu,
      uy = b / lu,
      vx = c / lv,
      vy = d / lv,
      fs = lv,
      x0 = e + (ux * it.width * o1) / L,
      y0 = f + (uy * it.width * o1) / L,
      x1 = e + (ux * it.width * o2) / L,
      y1 = f + (uy * it.width * o2) / L,
      P = [
        [x0 - vx * 0.2 * fs, y0 - vy * 0.2 * fs],
        [x1 - vx * 0.2 * fs, y1 - vy * 0.2 * fs],
        [x1 + vx * 0.85 * fs, y1 + vy * 0.85 * fs],
        [x0 + vx * 0.85 * fs, y0 + vy * 0.85 * fs],
      ].map((q) => viewport.convertToViewportPoint(q[0], q[1])),
      xs = P.map((q) => q[0]),
      ys = P.map((q) => q[1]),
      l = Math.min(...xs),
      t = Math.min(...ys);
    out.push({ l, t, w: Math.max(...xs) - l, h: Math.max(...ys) - t });
  }
  return out;
}
// Marks the matches on a page (the current one in another colour)
function markHits(el) {
  const old = el.querySelector('.sr');
  if (old) old.remove();
  if (!findState.by || !findState.q || !el._vp) return;
  const pageHits = findState.by.get(el._p);
  if (!pageHits) return;
  const box = document.createElement('div');
  box.className = 'sr';
  pageHits.forEach((h) => {
    const isCurrent = h === findState.hits[findState.i];
    hitRects(h, el._vp).forEach((r) => {
      const d = document.createElement('div');
      if (isCurrent) d.className = 'cur';
      d.style.cssText = 'left:' + r.l + 'px;top:' + r.t + 'px;width:' + r.w + 'px;height:' + r.h + 'px';
      box.appendChild(d);
    });
  });
  el.appendChild(box);
}
// Marks the matches again on every page already painted
const refreshMarks = () =>
  [...$('#view').children].forEach((el) => {
    if (el._ov) markHits(el);
  });
// The counter of the find bar: “Searching…”, “No results”, “12 results” or “3 of 12”
function showFindCount() {
  const counter = $('#sc');
  counter.textContent = !findState.q
    ? ''
    : !findState.hits.length
      ? findState.busy
        ? _t('Searching…')
        : _t('No results')
      : findState.i < 0
        ? _n(findState.hits.length, '{n} result', '{n} results')
        : _t('{i} of {n}', { i: findState.i + 1, n: findState.hits.length });
}
// Shows the current match: scrolls only if it is not already in view, and leaves it in the first third of the viewer
function showHit() {
  const hit = findState.hits[findState.i];
  if (!hit) return;
  const pageIdx = pages.indexOf(hit.p);
  if (pageIdx < 0) return;
  const view = $('#view'),
    el = view.children[pageIdx],
    same = !twoPageView || pageIdx - (pageIdx % 2) == shownPair,
    rect = el && el._vp && hitRects(hit, el._vp)[0];
  let visible = false;
  if (rect && same) {
    const elRect = el.getBoundingClientRect(),
      viewRect = view.getBoundingClientRect(),
      t = elRect.top + rect.t,
      l = elRect.left + rect.l;
    visible =
      el.style.display != 'none' &&
      t >= viewRect.top + 20 &&
      t + rect.h <= viewRect.bottom - 20 &&
      l >= viewRect.left &&
      l + rect.w <= viewRect.right - 16;
  }
  if (!visible && !(twoPageView && same)) goTo(pageIdx);
  refreshMarks();
  if (!visible && rect && same) {
    const elRect = el.getBoundingClientRect(),
      viewRect = view.getBoundingClientRect(),
      cx = elRect.left + rect.l + rect.w / 2;
    view.scrollTop += elRect.top + rect.t - (viewRect.top + view.clientHeight / 3);
    if (cx < viewRect.left || cx > viewRect.right) view.scrollLeft += cx - (viewRect.left + view.clientWidth / 2);
  }
  showFindCount();
}
// Searches every page for the text of the find bar; the first match goes to the one at or after the current page
async function runFind() {
  const query = foldText($('#sq').value),
    token = ++findState.tok;
  findState.q = query;
  findState.hits = [];
  findState.i = -1;
  findState.by = new Map();
  findState.ref = pages.slice();
  findState.busy = false;
  $('#view')
    .querySelectorAll('.sr')
    .forEach((x) => x.remove());
  if (!query) {
    showFindCount();
    return;
  }
  findState.busy = true;
  showFindCount();
  const start = currentPage;
  let placed = false;
  for (let k = 0; k < pages.length; k++) {
    const p = pages[k];
    let text;
    try {
      text = await getPageText(p);
    } catch (e) {
      continue;
    }
    if (token != findState.tok) return;
    const pageHits = [];
    let i = 0;
    while ((i = text.n.indexOf(query, i)) >= 0) {
      const h = { p, s: i, e: i + query.length };
      findState.hits.push(h);
      pageHits.push(h);
      i += query.length;
    }
    if (pageHits.length) {
      findState.by.set(p, pageHits);
      if (!placed && k >= start) {
        placed = true;
        findState.i = findState.hits.length - pageHits.length;
        showHit();
      } else {
        const el = $('#view').children[k];
        if (el && el._ov) markHits(el);
      }
    }
    showFindCount();
  }
  findState.busy = false;
  if (!placed && findState.hits.length) {
    findState.i = 0;
    showHit();
  }
  showFindCount();
}
// Next (dir = 1) or previous (dir = -1) match; if the pages changed since the search, it searches again
function stepHit(dir) {
  if (!findState.q || !pages.length) return;
  if (pages.length != findState.ref.length || pages.some((p, i) => p !== findState.ref[i])) {
    runFind();
    return;
  }
  const count = findState.hits.length;
  if (!count) return;
  findState.i = findState.i < 0 ? (dir > 0 ? 0 : count - 1) : (findState.i + dir + count) % count;
  showHit();
}
// The find bar: open or not, open (selects what was searched before) and close (removes the marks)
const findOpen = () => $('#sb').style.display == 'flex';
function openFind() {
  if (!pages.length) return;
  const bar = $('#sb'),
    wasOpen = findOpen();
  bar.style.top = $('#bar').offsetHeight + 8 + 'px';
  bar.style.display = 'flex';
  $('#bFind').classList.add('on');
  const input = $('#sq');
  input.focus();
  input.select();
  if (!wasOpen && foldText(input.value)) runFind();
}
function closeFind() {
  findState.tok++;
  findState.hits = [];
  findState.by = null;
  findState.i = -1;
  findState.busy = false;
  findState.q = '';
  $('#sb').style.display = 'none';
  $('#bFind').classList.remove('on');
  $('#sc').textContent = '';
  $('#view')
    .querySelectorAll('.sr')
    .forEach((x) => x.remove());
}
// Typing searches 250 ms after the last key; Enter goes to the next match (Shift+Enter: previous)
let findTimer;
$('#sq').oninput = () => {
  clearTimeout(findTimer);
  findTimer = setTimeout(runFind, 250);
};
$('#sq').onkeydown = (e) => {
  if (e.key != 'Enter') return;
  e.preventDefault();
  if (foldText(e.target.value) !== findState.q) {
    clearTimeout(findTimer);
    runFind();
  } else stepHit(e.shiftKey ? -1 : 1);
};
// Find bar buttons, and Ctrl+F / Esc to open and close it
$('#sPrev').onclick = () => stepHit(-1);
$('#sNext').onclick = () => stepHit(1);
$('#sClose').onclick = closeFind;
$('#bFind').onclick = () => (findOpen() ? closeFind() : openFind());
document.addEventListener('keydown', (e) => {
  if (
    (e.ctrlKey || e.metaKey) &&
    !e.altKey &&
    !e.shiftKey &&
    e.key.toLowerCase() == 'f' &&
    pages.length &&
    !$('#dlg') &&
    !$('#dlg2')
  ) {
    e.preventDefault();
    openFind();
    return;
  }
  if (e.key == 'Escape' && findOpen() && !$('#dlg') && !$('#dlg2') && !$('#pal')) closeFind();
});
// ---- Print: the PDF is built with the chosen annotations and sent to the browser's print dialogue
// The hidden frame that prints and its temporary address, kept until the next print
let printing = false,
  printFrame = null,
  printUrl = null;
// “Print” dialogue: which annotation types are printed
function printDialog() {
  if (!pages.length || document.getElementById('dlg')) return;
  if (isLocked()) {
    showMessage(
      _t('This PDF is protected against changes: Penfold cannot save it, print it or extract pages from it yet.'),
    );
    return;
  }
  const overlay = document.createElement('div');
  overlay.id = 'dlg';
  overlay.innerHTML = `<div class="box"><h3>Print</h3><div class="hint">Annotations to print:</div>
  <label><input type="checkbox" data-t="note"> Comments</label>
  <label><input type="checkbox" data-t="ft"> Text boxes</label>
  <label><input type="checkbox" data-t="hl" checked> Highlights</label>
  <label><input type="checkbox" data-t="ul" checked> Underlines</label>
  <label><input type="checkbox" data-t="so" checked> Strikethroughs</label>
  <label><input type="checkbox" data-t="sq" checked> Rectangles</label>
  <label><input type="checkbox" data-t="ci" checked> Circles</label>
  <label><input type="checkbox" data-t="ar" checked> Arrows</label>
  <div class="row r"><button id="pCancel">Cancel</button><button id="pOk" class="on">Print</button></div></div>`;
  i18nApply(overlay);
  document.body.appendChild(overlay);
  const close = () => {
    overlay.remove();
    document.removeEventListener('keydown', onKey);
  };
  const ok = () => {
    const types = new Set([...overlay.querySelectorAll('input:checked')].map((x) => x.dataset.t));
    close();
    doPrint(types);
  };
  const onKey = (e) => {
    if (e.key == 'Escape') close();
    else if (e.key == 'Enter' && e.target.tagName != 'BUTTON') {
      e.preventDefault();
      ok();
    }
  };
  document.addEventListener('keydown', onKey);
  overlay.querySelector('#pCancel').onclick = close;
  overlay.querySelector('#pOk').onclick = ok;
  overlay.querySelector('#pOk').focus();
}
// Builds the PDF with those annotations and prints it from a hidden frame (the browser's own PDF viewer prints it)
async function doPrint(types) {
  if (printing) return;
  printing = true;
  try {
    showMessage(_t('Preparing to print…'));
    await Promise.all(pages.map(loadAnnots));
    const bytes = await build({ types, noBms: true });
    if (printFrame) {
      printFrame.remove();
      printFrame = null;
    }
    if (printUrl) {
      URL.revokeObjectURL(printUrl);
      printUrl = null;
    }
    const url = URL.createObjectURL(new Blob([bytes], { type: 'application/pdf' })),
      frame = document.createElement('iframe');
    frame.style.cssText = 'position:fixed;left:-9999px;top:0;width:800px;height:600px;border:0';
    frame.onload = () =>
      setTimeout(() => {
        try {
          frame.contentWindow.focus();
          frame.contentWindow.print();
          $('#msg').style.display = 'none';
        } catch (e) {
          window.open(url, '_blank');
          showMessage(
            _t(
              'This browser does not allow printing from here: the PDF has been opened in another tab; print it from there.',
            ),
          );
        }
      }, 400);
    frame.src = url;
    document.body.appendChild(frame);
    printFrame = frame;
    printUrl = url;
  } catch (e) {
    showMessage('Error: ' + e.message);
  }
  printing = false;
}
$('#bPrint').onclick = printDialog;
// ---- About dialog (main menu → About Penfold): name, version, links, credits and licence. Change these values here only.
const APP = {
  name: 'Penfold',
  version: '0.6.0',
  author: 'ibanurq',
  year: 2026,
  repo: 'https://github.com/ibanurq/penfold',
  licence: 'GPL-3.0',
  licenceUrl: 'https://www.gnu.org/licenses/gpl-3.0.html',
};
// The About dialogue shows the app's colour icon (the welcome screen keeps its monochrome symbolic version)
const APP_ICON = '<img class="ico" src="assets/penfold.svg" alt="">';
// The arrow at the end of a link row (Lucide arrow-up-right): the link opens outside Penfold, in the browser
const LINK_ARROW = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7h10v10"/><path d="M7 17 17 7"/></svg>';
// “About Penfold” dialogue
function aboutDialog() {
  if (document.getElementById('dlg')) return;
  const overlay = document.createElement('div');
  overlay.id = 'dlg';
  overlay.innerHTML =
    '<div class="box about">' +
    APP_ICON +
    '<h3></h3><div class="ver"></div><div class="tag"></div>' +
    '<div class="card links"><a class="web" target="_blank" rel="noopener"><span></span>' +
    LINK_ARROW +
    '</a><a class="bug" target="_blank" rel="noopener"><span></span>' +
    LINK_ARROW +
    '</a></div>' +
    '<div class="small cred"></div><div class="small libs"></div><div class="small copy"><span></span> · <a class="lic" target="_blank" rel="noopener"></a></div>' +
    '<div class="row r"><button class="on ok"></button></div></div>';
  const query = (s) => overlay.querySelector(s);
  query('h3').textContent = APP.name;
  query('.ver').textContent = _t('Version {v}', { v: APP.version });
  query('.tag').textContent = _t('Read, annotate and organise your PDFs.');
  query('.web span').textContent = _t('Website');
  query('.web').href = APP.repo;
  query('.bug span').textContent = _t('Report an issue');
  query('.bug').href = APP.repo + '/issues';
  query('.cred').textContent = _t('Created by {a}, with AI assistance', { a: APP.author });
  query('.libs').textContent = _t('Uses pdf.js (Apache-2.0) · pdf-lib (MIT) · Lucide icons (ISC)');
  query('.copy span').textContent = '© ' + APP.year + ' ' + APP.author;
  query('.lic').textContent = _t('Licence {l}', { l: APP.licence });
  query('.lic').href = APP.licenceUrl;
  query('.ok').textContent = _t('Close');
  const close = () => {
      overlay.remove();
      document.removeEventListener('keydown', onKey);
    },
    onKey = (e) => {
      if (e.key == 'Escape' || (e.key == 'Enter' && e.target.tagName != 'A')) {
        e.preventDefault();
        close();
      }
    };
  query('.ok').onclick = close;
  document.addEventListener('keydown', onKey);
  document.body.appendChild(overlay);
  query('.ok').focus();
}
// ---- Main menu (☰, at the right end of the toolbar), as in GNOME apps: Keyboard Shortcuts and About Penfold.
// It is a small popover under the button; a click outside, Esc or choosing an item closes it
function closeMenu() {
  const m = $('#menu');
  if (!m) return false;
  m.remove();
  $('#bMenu').classList.remove('on');
  document.removeEventListener('pointerdown', menuOutside, true);
  return true;
}
const menuOutside = (e) => {
  if (!e.target.closest('#menu, #bMenu')) closeMenu();
};
function openMenu() {
  if (closeMenu()) return;
  const m = document.createElement('div');
  m.id = 'menu';
  m.setAttribute('role', 'menu');
  [
    [_t('Keyboard Shortcuts'), shortcutsDialog],
    [_t('About Penfold'), aboutDialog],
  ].forEach(([label, action]) => {
    const b = document.createElement('button');
    b.setAttribute('role', 'menuitem');
    b.textContent = label;
    b.onclick = () => {
      closeMenu();
      action();
    };
    m.appendChild(b);
  });
  // Esc closes the menu; the arrow keys move between its items
  m.onkeydown = (e) => {
    const items = [...m.children],
      i = items.indexOf(document.activeElement);
    if (e.key == 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      closeMenu();
      $('#bMenu').focus();
    } else if (e.key == 'ArrowDown' || e.key == 'ArrowUp') {
      e.preventDefault();
      items[(i + (e.key == 'ArrowDown' ? 1 : items.length - 1)) % items.length].focus();
    }
  };
  document.body.appendChild(m);
  const r = $('#bMenu').getBoundingClientRect();
  m.style.top = r.bottom + 6 + 'px';
  m.style.right = Math.max(8, innerWidth - r.right) + 'px';
  $('#bMenu').classList.add('on');
  document.addEventListener('pointerdown', menuOutside, true);
  m.firstChild.focus();
}
$('#bMenu').onclick = openMenu;

// ---- Keyboard shortcuts. SHORTCUTS lists them for the Keyboard Shortcuts window, in groups: each one is [keys,
// description]; the keys are drawn one by one as keycaps. Annotations come first: they are the ones used most. Ctrl+W and Ctrl+Q exist only in the desktop app (its main
// process handles them), so they are listed only there
const IN_DESKTOP_APP = !!window.penfoldDesktop;
const SHORTCUTS = [
  [
    _t('Annotations'),
    [
      [['H'], _t('Highlight', null, 'shortcuts')],
      [['U'], _t('Underline', null, 'shortcuts')],
      [['Esc'], _t('Back to the text selection tool')],
    ],
  ],
  [
    _t('General'),
    [
      [['Ctrl', 'O'], _t('Open a PDF')],
      [['Ctrl', 'S'], _t('Save')],
      [['Ctrl', 'Shift', 'S'], _t('Save As')],
      [['Ctrl', 'P'], _t('Print')],
      [['Delete'], _t('Delete the selected pages or bookmarks')],
      [['Ctrl', '?'], _t('Show the keyboard shortcuts')],
      ...(IN_DESKTOP_APP
        ? [
            [['Ctrl', 'W'], _t('Close the window')],
            [['Ctrl', 'Q'], _t('Quit')],
          ]
        : []),
    ],
  ],
  [
    _t('Find', null, 'shortcuts'),
    [
      [['Ctrl', 'F'], _t('Find in document')],
      [['Ctrl', 'G'], _t('Next result')],
      [['Ctrl', 'Shift', 'G'], _t('Previous result')],
      [['Esc'], _t('Close the find bar')],
    ],
  ],
  [
    _t('View'),
    [
      [['Ctrl', '+'], _t('Zoom in')],
      [['Ctrl', '−'], _t('Zoom out')],
      [['Ctrl', '0'], _t('Fit to page width')],
      [['F9'], _t('Show / hide side panel')],
    ],
  ],
  [
    _t('Moving around'),
    [
      [['Page Down'], _t('Next page')],
      [['Page Up'], _t('Previous page')],
      [['Ctrl', 'Home'], _t('First page')],
      [['Ctrl', 'End'], _t('Last page')],
      [['Ctrl', 'L'], _t('Go to page')],
    ],
  ],
];
// Names of keys that are written differently in other languages (Shift is “Mayús” in Spanish…)
const keyName = (k) =>
  ['Shift', 'Page Down', 'Page Up', 'Home', 'End', 'Delete'].includes(k) ? _t(k, null, 'key') : k;
// “Keyboard Shortcuts” window, as GNOME's: the groups one under another, each a card with a row per shortcut
// (description on the left, keys on the right)
function shortcutsDialog() {
  if (document.getElementById('dlg')) return;
  const overlay = document.createElement('div');
  overlay.id = 'dlg';
  overlay.innerHTML =
    '<div class="box wide shortcuts"><h3></h3><div class="groups"></div><div class="row r"><button class="on ok"></button></div></div>';
  overlay.querySelector('h3').textContent = _t('Keyboard Shortcuts');
  overlay.querySelector('.ok').textContent = _t('Close');
  const groups = overlay.querySelector('.groups');
  SHORTCUTS.forEach(([title, rows]) => {
    const h = document.createElement('h4');
    h.textContent = title;
    const card = document.createElement('div');
    card.className = 'card';
    rows.forEach(([keys, text]) => {
      const row = document.createElement('div');
      row.className = 'krow';
      const label = document.createElement('span');
      label.textContent = text;
      const caps = document.createElement('span');
      caps.className = 'keys';
      keys.forEach((k) => {
        const kbd = document.createElement('kbd');
        kbd.textContent = keyName(k);
        caps.appendChild(kbd);
      });
      row.append(label, caps);
      card.appendChild(row);
    });
    groups.append(h, card);
  });
  const close = () => {
      overlay.remove();
      document.removeEventListener('keydown', onKey);
    },
    onKey = (e) => {
      if (e.key == 'Escape' || e.key == 'Enter') {
        e.preventDefault();
        close();
      }
    };
  overlay.querySelector('.ok').onclick = close;
  document.addEventListener('keydown', onKey);
  document.body.appendChild(overlay);
  overlay.querySelector('.ok').focus();
}
// Chooses a toolbar tool, as if its button were clicked (nothing happens while no PDF is open: the buttons are disabled)
const chooseTool = (t) => $('#bar .ib[data-t="' + t + '"]').click();
// Clicks a toolbar button if it is enabled
const pressButton = (sel) => !$(sel).disabled && $(sel).click();
// The shortcuts themselves. They run in the capture phase, before the other key handlers, so that Esc can tell
// whether the find bar was open. Nothing is done while a dialogue, the menu or the colour popover is open, and the
// keys without Ctrl (H, U, Delete, Esc, Page Up / Page Down) are left alone while typing in a field
document.addEventListener(
  'keydown',
  (e) => {
    if ($('#dlg') || $('#dlg2') || $('#pal') || $('#menu')) return;
    const ctrl = e.ctrlKey || e.metaKey,
      key = e.key.length == 1 ? e.key.toLowerCase() : e.key,
      run = (action) => {
        e.preventDefault();
        action();
      };
    if (ctrl && !e.altKey) {
      // Ctrl+? (on most keyboards “?” itself needs Shift)
      if (key == '?') return run(shortcutsDialog);
      if (e.shiftKey) {
        if (key == 's') return run(() => pressButton('#bSaveAs'));
        if (key == 'g') return run(() => (findOpen() ? stepHit(-1) : openFind()));
        return;
      }
      if (key == 'o') return run(() => $('#bOpen').click());
      if (key == 's') return run(() => pressButton('#bSave'));
      if (key == 'g') return run(() => (findOpen() ? stepHit(1) : openFind()));
      if (key == '+' || key == '=') return run(() => pressButton('#zi'));
      if (key == '-') return run(() => pressButton('#zo'));
      if (key == '0') return run(() => pages.length && setFit('w'));
      if (key == 'l')
        return run(() => {
          if (!pages.length) return;
          $('#pg').focus();
          $('#pg').select();
        });
      if (key == 'Home') return run(() => pages.length && goTo(0));
      if (key == 'End') return run(() => pages.length && goTo(pages.length - 1));
      return;
    }
    if (ctrl || e.altKey) return;
    if (key == 'F9') return run(() => pressButton('#bPanel'));
    if (!pages.length || e.shiftKey || /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable)
      return;
    // Page Down / Page Up: next / previous page (in “Two pages” they already change pair)
    if ((key == 'PageDown' || key == 'PageUp') && !twoPageView)
      return run(() => goTo(Math.max(0, Math.min(pages.length - 1, currentPage + (key == 'PageDown' ? 1 : -1)))));
    // H / U: highlight / underline the selected text; with no text selected, choose that tool
    if (key == 'h' || key == 'u') {
      const type = key == 'h' ? 'hl' : 'ul';
      return run(() => markSelection(type) || chooseTool(type));
    }
    // Delete: deletes the selected pages (Pages tab) or bookmarks (Bookmarks tab), asking first, like the panel's
    // delete button (with nothing selected the button is disabled and nothing happens)
    if (key == 'Delete') {
      const del = $('#sbody [data-action="delete"]');
      return del && $('#side').style.display != 'none' && run(() => pressButton('#sbody [data-action="delete"]'));
    }
    // Esc: back to the text selection tool (if the find bar is open, Esc closes it instead)
    if (key == 'Escape' && tool != 'sel' && !findOpen()) return run(() => chooseTool('sel'));
  },
  true,
);
// Ctrl+P opens the Print dialogue
document.addEventListener('keydown', (e) => {
  if (
    (e.ctrlKey || e.metaKey) &&
    !e.altKey &&
    !e.shiftKey &&
    e.key.toLowerCase() == 'p' &&
    pages.length &&
    !$('#dlg') &&
    !$('#dlg2')
  ) {
    e.preventDefault();
    printDialog();
  }
});
// ---- Text dialogue (comments and text boxes): Enter = new line, Ctrl/Cmd+Enter = save, Esc = cancel
function textDialog(title, initial, onSave) {
  if (document.getElementById('dlg')) return;
  const overlay = document.createElement('div');
  overlay.id = 'dlg';
  overlay.innerHTML =
    '<div class="box wide"><h3></h3><textarea rows="6"></textarea><div class="row r"><button id="tCancel">Cancel</button><button id="tOk" class="on">Save</button></div></div>';
  i18nApply(overlay);
  overlay.querySelector('h3').textContent = title;
  const textarea = overlay.querySelector('textarea');
  textarea.value = initial || '';
  document.body.appendChild(overlay);
  const close = () => {
    overlay.remove();
    document.removeEventListener('keydown', onKey);
  };
  const ok = () => {
    const text = textarea.value;
    close();
    if (text.trim()) onSave(text);
  };
  const onKey = (e) => {
    if (e.key == 'Escape') close();
    else if (e.key == 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      ok();
    }
  };
  document.addEventListener('keydown', onKey);
  overlay.querySelector('#tCancel').onclick = close;
  overlay.querySelector('#tOk').onclick = ok;
  textarea.focus();
  textarea.setSelectionRange(textarea.value.length, textarea.value.length);
}
// ---- Merge PDF: list of files -> a single document open in the application
// Replaces the open document with the merged files (items, in order): optionally one bookmark per file, with the
// file's own bookmarks under it (or at the top level)
async function mergeInto(items, bookmarkPerFile, keepBookmarks) {
  docs = [];
  pages = [];
  selectedPages.clear();
  selectedBookmarks.clear();
  pageAnchor = -1;
  bookmarkAnchor = null;
  currentPage = 0;
  fileHandle = null;
  fileName = _t('merged.pdf');
  const firstPages = [];
  items.forEach((it) => {
    const docIndex = docs.push({ bytes: it.bytes, pdf: it.pdf }) - 1;
    firstPages.push(pages.length);
    for (let i = 0; i < it.n; i++)
      pages.push({ doc: docIndex, idx: i, annots: [], thumb: null, rot: 0, loaded: false });
  });
  bookmarks = [];
  for (let k = 0; k < items.length; k++) {
    const fileBookmarks = keepBookmarks
      ? pruneBookmarks(await convertOutline((await items[k].pdf.getOutline()) || [], k))
      : [];
    if (bookmarkPerFile) {
      bookmarks.push({
        title: items[k].file.name.replace(/\.[^./\\]+$/, ''),
        page: pages[firstPages[k]],
        color: null,
        bold: false,
        italic: false,
        items: fileBookmarks,
      });
    } else {
      bookmarks.push(...fileBookmarks);
    }
  }
  // The merged document exists only on screen until it is saved
  markSaved(true);
  panelTab = 'bm';
  onDocumentReady();
}
// “Merge PDF” dialogue: a list of files (added with the button or dropped on it), reordered by dragging
function mergeDialog() {
  if (document.getElementById('dlg')) return;
  const items = [];
  let dragIdx = -1;
  const overlay = document.createElement('div');
  overlay.id = 'dlg';
  overlay.innerHTML = `<div class="box wide"><h3>Merge PDF</h3>
  <div id="mList" class="mlist"></div>
  <div class="row"><button id="mAdd">Add PDFs…</button><span id="mTot" style="opacity:.7"></span></div>
  <label><input type="checkbox" id="mGen" checked> Create a bookmark for each file</label>
  <label><input type="checkbox" id="mKeep" checked> Keep the files’ bookmarks</label>
  <div class="row r"><button id="mCancel">Cancel</button><button id="mOk" class="on" disabled>Merge</button></div></div>`;
  i18nApply(overlay);
  document.body.appendChild(overlay);
  const query = (sel) => overlay.querySelector(sel),
    list = query('#mList');
  const close = () => {
      overlay.remove();
      document.removeEventListener('keydown', onKey);
    },
    onKey = (e) => {
      if (e.key == 'Escape') close();
    };
  document.addEventListener('keydown', onKey);
  overlay.ondragover = (e) => e.preventDefault();
  overlay.ondrop = (e) => e.preventDefault();
  const drawList = () => {
    list.innerHTML = '';
    if (!items.length) {
      const e = document.createElement('div');
      e.style.cssText = 'opacity:.55;text-align:center;padding:100px 10px';
      e.textContent = _t('Drag PDFs here or click “Add PDFs…”');
      list.appendChild(e);
    }
    items.forEach((it, i) => {
      const row = document.createElement('div');
      row.className = 'mrow' + (it.enc ? ' enc' : '');
      row.draggable = true;
      // Drag handle (Lucide grip-vertical), as in GNOME's reorderable lists: it shows that the rows can be moved
      const grip = document.createElement('span');
      grip.className = 'grip';
      grip.innerHTML =
        '<svg viewBox="0 0 24 24"><circle cx="9" cy="12" r="1"/><circle cx="9" cy="5" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="19" r="1"/></svg>';
      const nameEl = document.createElement('span');
      nameEl.className = 'nm';
      nameEl.textContent = it.file.name;
      nameEl.title = it.file.name;
      // Protected PDFs stay in the list (in red) so it is clear which ones will not be merged
      const pagesEl = document.createElement('span');
      if (it.enc) {
        pagesEl.className = 'bad';
        pagesEl.textContent = _t('Cannot be merged');
      } else {
        pagesEl.className = 'pg';
        pagesEl.textContent = _n(it.n, '{n} p.', '{n} pp.');
      }
      const removeBtn = document.createElement('button');
      removeBtn.textContent = '✕';
      removeBtn.title = _t('Remove from list');
      removeBtn.onclick = () => {
        items.splice(i, 1);
        drawList();
      };
      const zone = (ev) => {
        const b = row.getBoundingClientRect();
        return ev.clientY < b.top + b.height / 2 ? 'before' : 'after';
      };
      row.ondragstart = (ev) => {
        dragIdx = i;
        ev.dataTransfer.setData('text/plain', 'row');
        ev.dataTransfer.effectAllowed = 'move';
      };
      row.ondragend = () => {
        dragIdx = -1;
        drawList();
      };
      row.ondragover = (ev) => {
        if (dragIdx < 0) return;
        ev.preventDefault();
        ev.stopPropagation();
        row.classList.remove('before', 'after');
        row.classList.add(zone(ev));
      };
      row.ondragleave = () => row.classList.remove('before', 'after');
      row.ondrop = (ev) => {
        if (dragIdx < 0) return;
        ev.preventDefault();
        ev.stopPropagation();
        const where = zone(ev),
          [moved] = items.splice(dragIdx, 1);
        let to = i;
        if (dragIdx < i) to--;
        items.splice(where == 'after' ? to + 1 : to, 0, moved);
        dragIdx = -1;
        drawList();
      };
      row.append(grip, nameEl, pagesEl, removeBtn);
      list.appendChild(row);
    });
    const ok = items.filter((it) => !it.enc),
      total = ok.reduce((n, it) => n + it.n, 0);
    query('#mTot').textContent = ok.length
      ? _n(ok.length, '{n} file', '{n} files') + ' · ' + _n(total, '{n} page in total', '{n} pages in total')
      : '';
    query('#mOk').disabled = ok.length < 2;
  };
  // Reads the files and adds them to the list (only PDFs; protected ones are listed but not merged)
  const addFiles = async (files) => {
    for (const file of files) {
      if (!/\.pdf$/i.test(file.name) && file.type != 'application/pdf') continue;
      try {
        const bytes = await file.arrayBuffer(),
          pdf = await pdfjsLib.getDocument({ data: bytes.slice(0), isEvalSupported: false }).promise;
        items.push({ file: file, bytes, pdf, n: pdf.numPages, enc: await isProtected(pdf, bytes) });
      } catch (e) {
        showMessage(_t('Could not read “{name}”: {m}', { name: file.name, m: e.message }));
      }
    }
    drawList();
  };
  const picker = document.createElement('input');
  picker.type = 'file';
  picker.accept = '.pdf,application/pdf';
  picker.multiple = true;
  picker.onchange = () => addFiles([...picker.files]);
  query('#mAdd').onclick = () => picker.click();
  list.ondragover = (ev) => {
    if (ev.dataTransfer.types.includes('Files')) {
      ev.preventDefault();
      list.classList.add('drop');
    }
  };
  list.ondragleave = () => list.classList.remove('drop');
  list.ondrop = (ev) => {
    if (!ev.dataTransfer.types.includes('Files')) return;
    ev.preventDefault();
    list.classList.remove('drop');
    addFiles([...ev.dataTransfer.files]);
  };
  query('#mCancel').onclick = close;
  query('#mOk').onclick = async () => {
    const genBm = query('#mGen').checked;
    const keepBm = query('#mKeep').checked;
    close();
    showMessage(_t('Merging…'));
    try {
      await mergeInto(
        items.filter((it) => !it.enc),
        genBm,
        keepBm,
      );
      showMessage(_t('PDF merged: {n} pages. Use “Save As…” to save it.', { n: pages.length }));
    } catch (e) {
      showMessage(_t('Error merging: {m}', { m: e.message }));
    }
  };
  drawList();
}
// ---- Small helpers ----
// The colour popover (used to change the colour of an annotation or a bookmark): closes it
function closePalette() {
  const pop = document.getElementById('pal');
  if (pop) pop.remove();
}
// Opens the colour popover under button; onPick gets the chosen colour. Closes with any click
function openPalette(button, onPick, list) {
  closePalette();
  const pop = document.createElement('div');
  pop.id = 'pal';
  list = list || PALETTE;
  if (list.length > 6) pop.style.gridTemplateColumns = 'repeat(4,24px)';
  list.forEach((x) => {
    const b = document.createElement('button');
    b.className = 'sq';
    b.title = _t(x.n);
    b.style.background = x.p;
    b.onclick = (ev) => {
      ev.stopPropagation();
      closePalette();
      onPick(x.p);
    };
    pop.appendChild(b);
  });
  document.body.appendChild(pop);
  const rect = button.getBoundingClientRect();
  pop.style.left = Math.max(8, Math.min(rect.left, innerWidth - pop.offsetWidth - 8)) + 'px';
  pop.style.top = rect.bottom + 6 + 'px';
  setTimeout(() => document.addEventListener('click', closePalette, { once: true }), 0);
}
// Keeps currentPage within the document and shows it in the page box of the toolbar (“3 of 12”)
function updatePageBox() {
  currentPage = Math.max(0, Math.min(currentPage, pages.length - 1));
  $('#pg').value = pages.length ? currentPage + 1 : '';
  $('#pgN').textContent = pages.length;
}
// Changes the zoom (fn sets scale), draws the pages again and stays on the same page
async function zoomTo(fn) {
  const keep = currentPage;
  fn();
  await renderMain();
  goTo(keep);
}
// When the viewer's width changes (side panel) the zoom is re-fitted (fit width; in “Two pages”, whole page). Called once, when the change has finished.
function reflowOnWidth(w0) {
  const w = $('#view').clientWidth;
  if (!pages.length || w0 <= 60 || w <= 60 || Math.abs(w - w0) < 2) return;
  setFit(twoPageView ? 'p' : 'w');
}
// When a PDF is opened it is fitted to the width (if that fails, it is painted at the current zoom)
function fitOnOpen() {
  currentPage = 0;
  Promise.resolve(setFit(twoPageView ? 'p' : 'w')).catch(() => renderMain());
}
// Fits the zoom to the width (mode 'w') or to the whole page (mode 'p'; in “Two pages”, the whole pair)
async function setFit(mode) {
  const page = pages[currentPage];
  if (!page) return;
  const view = $('#view'),
    first = currentPage - (currentPage % 2),
    shown = twoPageView ? [first, first + 1].filter((k) => k < pages.length) : [currentPage],
    viewports = [];
  for (const k of shown) {
    const q = pages[k],
      pdfPage = await docs[q.doc].pdf.getPage(q.idx + 1);
    viewports.push(pdfPage.getViewport({ scale: 1, rotation: (pdfPage.rotate + (q.rot || 0)) % 360 }));
  }
  const totalW =
      viewports.reduce((a, x) => a + x.width, 0) + (twoPageView && viewports.length == 1 ? viewports[0].width : 0),
    maxH = Math.max(...viewports.map((x) => x.height)),
    fitW = (view.clientWidth - 40 - (twoPageView ? 14 : 0)) / totalW,
    availH = view.clientHeight - (twoPageView ? 48 : 30);
  const newScale = Math.max(0.3, Math.min(4, mode == 'w' ? fitW : Math.min(fitW, availH / maxH)));
  if (twoPageView && Math.abs(newScale - scale) < 1e-6) {
    showPair();
    return;
  }
  zoomTo(() => {
    scale = newScale;
  });
}
// “Two pages” button
$('#two').onclick = () => {
  twoPageView = !twoPageView;
  $('#view').classList.toggle('two', twoPageView);
  $('#two').classList.toggle('on', twoPageView);
  showPair();
  setFit(twoPageView ? 'p' : 'w');
};
// In “Two pages” the wheel, the left/right arrows and Page Up / Page Down change pair
const flipPair = (dir) => {
  const target = currentPage - (currentPage % 2) + 2 * dir;
  if (target >= 0 && target < pages.length) goTo(target);
};
// Mouse wheel in “Two pages”: scrolls the pair first; at its end, the next turn of the wheel changes pair.
// wheelLock is a short pause, so one swipe of a touchpad does not skip several pairs
let wheelLock = 0;
$('#view').addEventListener(
  'wheel',
  (e) => {
    if (!twoPageView || e.ctrlKey || !e.deltaY || Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;
    const view = e.currentTarget,
      now = Date.now(),
      down = e.deltaY > 0;
    if (down ? view.scrollTop + view.clientHeight < view.scrollHeight - 2 : view.scrollTop > 0) {
      wheelLock = Math.max(wheelLock, now + 250);
      return;
    }
    e.preventDefault();
    if (now < wheelLock) {
      wheelLock = Math.max(wheelLock, now + 150);
      return;
    }
    wheelLock = now + 450;
    flipPair(down ? 1 : -1);
  },
  { passive: false },
);
document.addEventListener('keydown', (e) => {
  if (
    !twoPageView ||
    !pages.length ||
    e.ctrlKey ||
    e.metaKey ||
    e.altKey ||
    /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) ||
    $('#dlg') ||
    $('#dlg2')
  )
    return;
  const d = e.key == 'ArrowRight' || e.key == 'PageDown' ? 1 : e.key == 'ArrowLeft' || e.key == 'PageUp' ? -1 : 0;
  if (d) {
    e.preventDefault();
    flipPair(d);
  }
});
// Fit width and fit page buttons; the page box (typing a number + Enter goes to that page)
$('#fw').onclick = () => setFit('w');
$('#fp').onclick = () => setFit('p');
$('#pg').onfocus = (e) => e.target.select();
$('#pg').onkeydown = (e) => {
  if (e.key != 'Enter') return;
  const n = parseInt(e.target.value);
  if (n >= 1 && n <= pages.length) goTo(n - 1);
  else updatePageBox();
  e.target.blur();
};
// Merge PDF: the question about unsaved changes comes first, before the files are chosen
$('#bMerge').onclick = async () => {
  if (await confirmUnsaved()) mergeDialog();
};
// The Open and Merge buttons of the welcome screen do the same as the toolbar ones
$('#eOpen').onclick = () => $('#bOpen').click();
$('#eMerge').onclick = () => $('#bMerge').click();
// ---- Extract pages ----
// Reads a list of pages such as “1, 5, 10-12, 56-” (56- = to the end) for a document of count pages:
// { list: [page numbers] } or { err: message }
function parsePages(text, count) {
  const out = new Set(),
    parts = text
      .split(/[,;]/)
      .map((part) => part.trim())
      .filter(Boolean);
  if (!parts.length) return { err: _t('Enter at least one page.') };
  for (const part of parts) {
    const m = part.match(/^(\d+)\s*(-)?\s*(\d+)?$/);
    if (!m || (m[3] && !m[2])) return { err: _t('Invalid format: “{t}”.', { t: part }) };
    const a = +m[1],
      b = m[2] ? (m[3] ? +m[3] : count) : a;
    if (a < 1 || a > count) return { err: _t('Page {p} does not exist (the document has {n}).', { p: a, n: count }) };
    if (b < a) return { err: _t('Invalid range: “{t}”.', { t: part }) };
    if (b > count) return { err: _t('Page {p} does not exist (the document has {n}).', { p: b, n: count }) };
    for (let k = a; k <= b; k++) out.add(k);
  }
  return { list: [...out].sort((x, y) => x - y) };
}
// The opposite: [1, 5, 10, 11, 12] → “1, 5, 10-12”
function formatPages(list) {
  const parts = [];
  for (let i = 0; i < list.length;) {
    let j = i;
    while (j + 1 < list.length && list[j + 1] == list[j] + 1) j++;
    parts.push(j > i ? list[i] + '-' + list[j] : '' + list[i]);
    i = j + 1;
  }
  return parts.join(', ');
}
// ---- Question dialogues (in the style of GNOME's alerts) ----
// A question with buttons: each is [label, value, isDefault, extra class]; resolves to the value of the button
// pressed ('cancel' with Esc)
function choiceDialog(title, text, buttons) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.id = 'dlg2';
    overlay.innerHTML =
      '<div class="box"><h3></h3><div style="white-space:pre-wrap"></div><div class="row"></div></div>';
    overlay.querySelector('h3').textContent = title;
    overlay.querySelector('.box>div').textContent = text;
    const finish = (value) => {
        overlay.remove();
        document.removeEventListener('keydown', onKey);
        resolve(value);
      },
      onKey = (e) => {
        if (e.key == 'Escape') finish('cancel');
      };
    buttons.forEach(([label, value, isDefault, cls]) => {
      const b = document.createElement('button');
      b.textContent = label;
      if (isDefault) b.className = 'on';
      if (cls) b.classList.add(cls);
      b.onclick = () => finish(value);
      overlay.querySelector('.row').appendChild(b);
    });
    document.addEventListener('keydown', onKey);
    document.body.appendChild(overlay);
  });
}
// Cancel / OK question: resolves to true or false
function confirmDialog(title, text, okLabel) {
  const answer = choiceDialog(title, text, [
    [_t('Cancel'), 'cancel'],
    [okLabel || _t('OK'), 'ok', true],
  ]);
  const okBtn = document.querySelector('#dlg2 button.on');
  if (okBtn) okBtn.focus();
  return answer.then((v) => v == 'ok');
}
// Asks for a text: resolves to the text, or null if cancelled or empty
function promptDialog(title, label, initial, okLabel) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.id = 'dlg2';
    overlay.innerHTML =
      '<div class="box"><h3></h3><div></div><input type="text" autocomplete="off"><div class="row"><button class="c"></button><button class="on ok"></button></div></div>';
    overlay.querySelector('.c').textContent = _t('Cancel');
    overlay.querySelector('h3').textContent = title;
    overlay.querySelector('.box>div').textContent = label;
    const input = overlay.querySelector('input');
    input.value = initial || '';
    overlay.querySelector('.ok').textContent = okLabel || _t('OK');
    const finish = (v) => {
      overlay.remove();
      document.removeEventListener('keydown', onKey);
      resolve(v);
    };
    const onKey = (e) => {
      if (e.key == 'Escape') finish(null);
      else if (e.key == 'Enter' && e.target === input) {
        e.preventDefault();
        finish(input.value || null);
      }
    };
    overlay.querySelector('.c').onclick = () => finish(null);
    overlay.querySelector('.ok').onclick = () => finish(input.value || null);
    document.addEventListener('keydown', onKey);
    document.body.appendChild(overlay);
    input.focus();
    input.select();
  });
}
// “Extract pages” dialogue: which pages (by default the selected ones), as one file or one per page, and whether to
// delete them from the document or leave out bookmarks and annotations
function extractDialog(initial) {
  if (!pages.length) {
    showMessage(_t('Open a PDF first.'));
    return;
  }
  if (document.getElementById('dlg')) return;
  if (initial === undefined)
    initial = formatPages(pages.map((p, k) => (selectedPages.has(p) ? k + 1 : 0)).filter(Boolean));
  const overlay = document.createElement('div');
  overlay.id = 'dlg';
  overlay.innerHTML = `<div class="box"><h3>Extract pages</h3>
  <div><b>Pages to extract:</b>
  <input id="xPg" type="text" autocomplete="off" placeholder="1, 5, 10-12, 56-" style="width:100%;box-sizing:border-box;margin-top:6px">
  <div class="hint xhint">Separate the pages with commas and use a dash for a range (10‑12). 56‑ means from page 56 to the end.</div>
  <div id="xErr" class="err"></div></div>
  <label><input type="checkbox" id="xSep"> Extract as separate pages</label>
  <label><input type="checkbox" id="xDel"> Delete pages after extraction</label>
  <label><input type="checkbox" id="xClean"> Delete bookmarks and annotations</label>
  <div class="row r"><button id="xCancel">Cancel</button><button id="xOk" class="on">OK</button></div></div>`;
  i18nApply(overlay);
  document.body.appendChild(overlay);
  const query = (s) => overlay.querySelector(s),
    input = query('#xPg'),
    error = query('#xErr');
  input.value = initial;
  const close = () => {
      overlay.remove();
      document.removeEventListener('keydown', onKey);
    },
    onKey = (e) => {
      if (e.key == 'Escape' && !document.getElementById('dlg2')) close();
    };
  document.addEventListener('keydown', onKey);
  query('#xCancel').onclick = close;
  input.oninput = () => (error.textContent = '');
  const run = async () => {
    const parsed = parsePages(input.value, pages.length);
    if (parsed.err) {
      error.textContent = parsed.err;
      return;
    }
    const chosen = parsed.list.map((k) => pages[k - 1]),
      opts = { sep: query('#xSep').checked, del: query('#xDel').checked, clean: query('#xClean').checked };
    if (opts.del && chosen.length >= pages.length) {
      error.textContent = _t('You can’t delete all the pages: untick “Delete pages after extraction”.');
      return;
    }
    query('#xOk').disabled = true;
    try {
      await extractPages(chosen, opts, overlay);
      close();
    } catch (e) {
      query('#xOk').disabled = false;
      if (e.name != 'AbortError') showMessage('Error: ' + e.message);
    }
  };
  query('#xOk').onclick = run;
  input.onkeydown = (e) => {
    if (e.key == 'Enter') run();
  };
  input.focus();
  input.select();
}
// Writes the extracted files. Chromium-based browsers write into a chosen folder (asking before overwriting files
// already there); other browsers download them
async function extractPages(chosen, opts, dialog) {
  const groups = opts.sep ? chosen.map((p) => [p]) : [chosen],
    digits = Math.max(2, String(groups.length).length);
  const names = opts.sep
    ? groups.map((_, i) => _t('extracted') + '_' + String(i + 1).padStart(digits, '0') + '.pdf')
    : [_t('extracted') + '.pdf'];
  let dir = null,
    final = names;
  if (window.showDirectoryPicker) {
    dir = await showDirectoryPicker({ mode: 'readwrite' });
    const exists = async (n) => {
      try {
        await dir.getFileHandle(n);
        return true;
      } catch (e) {
        if (e.name == 'NotFoundError') return false;
        throw e;
      }
    };
    const existing = [];
    for (const n of names) if (await exists(n)) existing.push(n);
    if (existing.length) {
      dialog.style.display = 'none';
      let answer;
      try {
        answer = await choiceDialog(
          _t('Existing files'),
          _t('Already in the folder:') +
            '\n' +
            existing
              .slice(0, 6)
              .map((n) => '- ' + n)
              .join('\n') +
            (existing.length > 6 ? '\n' + _t('…and {n} more', { n: existing.length - 6 }) : '') +
            '\n\n' +
            _t('Do you want to overwrite them or rename the new ones?'),
          [
            [_t('Cancel'), 'cancel'],
            [_t('Rename'), 'rename'],
            [_t('Overwrite'), 'over', 1],
          ],
        );
      } finally {
        dialog.style.display = '';
      }
      if (answer == 'cancel') throw Object.assign(new Error('cancel'), { name: 'AbortError' });
      if (answer == 'rename') {
        final = [];
        for (const n of names) {
          let m = n,
            k = 2;
          while (await exists(m)) m = n.replace(/\.pdf$/, '') + ' (' + k++ + ').pdf';
          final.push(m);
        }
      }
    }
  } else showMessage(_t('This browser does not allow choosing a folder: the files will be downloaded.'));
  const src = await Promise.all(docs.map((d) => PDFLib.PDFDocument.load(d.bytes, { ignoreEncryption: true })));
  for (let i = 0; i < groups.length; i++) {
    const bytes = await build({ pages: groups[i], noAnnots: opts.clean, src });
    if (dir) {
      const fileHandle = await dir.getFileHandle(final[i], { create: true }),
        writable = await fileHandle.createWritable();
      await writable.write(bytes);
      await writable.close();
    } else {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([bytes], { type: 'application/pdf' }));
      a.download = final[i];
      a.click();
      await new Promise((r) => setTimeout(r, 300));
    }
  }
  if (opts.del) {
    chosen.forEach((x) => {
      const idx = pages.indexOf(x);
      if (idx >= 0) pages.splice(idx, 1);
    });
    selectedPages.clear();
    bookmarks = pruneBookmarks(bookmarks);
    renderSide();
    renderMain();
  }
  showMessage(
    _t('{x} into {f}', {
      x: _n(chosen.length, '{n} page extracted', '{n} pages extracted'),
      f: _n(groups.length, '{n} file', '{n} files'),
    }) +
      (opts.del ? _t(' and removed from the document') : '') +
      ' ✔',
  );
}
// ---- Start-up ----
// Side panel resizer: dragging the bar changes the panel's width, which is remembered for next time
(() => {
  const side = $('#side'),
    resizer = $('#rs');
  side.style.minWidth = SIDE_MIN + 'px';
  try {
    const w = localStorage.getItem('sw');
    if (w) side.style.width = w + 'px';
  } catch (e) {}
  resizer.onmousedown = (e) => {
    e.preventDefault();
    const w0 = $('#view').clientWidth;
    const onMove = (ev) => {
      side.style.width = Math.max(SIDE_MIN, Math.min(panelMaxWidth(), ev.clientX)) + 'px';
    };
    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.body.style.userSelect = '';
      try {
        localStorage.setItem('sw', parseInt(side.style.width));
      } catch (e) {}
      reflowOnWidth(w0);
    };
    document.body.style.userSelect = 'none';
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  };
})();
// The thumbnail columns follow the panel's width; the protected-PDF sign follows the viewer
new ResizeObserver(updateThumbColumns).observe($('#sbody'));
new ResizeObserver(lockBadge).observe($('#view'));
