const $ = (s) => document.querySelector(s),
  W = 'vendor/pdf.js-3.11.174/pdf.worker.min.js';
// Opened as a file (file://) the browser refuses fetch(), so the worker is given by its path straight away
if (location.protocol == 'file:') pdfjsLib.GlobalWorkerOptions.workerSrc = W;
else
  fetch(W)
    .then((r) => r.blob())
    .then((b) => (pdfjsLib.GlobalWorkerOptions.workerSrc = URL.createObjectURL(b)))
    .catch(() => (pdfjsLib.GlobalWorkerOptions.workerSrc = W));
// ---- Language ----
// English is the source language: every string in this file is English, and the Spanish text lives in the ES dictionary below
// (key = the English string; a key may carry a context prefix, "ctx\u0004text", when two uses need different Spanish).
// The language comes from ?lang=en|es, otherwise from the browser's preferred languages (Basque, Catalan and Galician fall back to Spanish).
const ES = {
  // Toolbar, side panel and welcome screen
  'Show / hide side panel': 'Mostrar / ocultar panel lateral',
  'Open PDF': 'Abrir PDF',
  'Merge PDF': 'Combinar PDF',
  'Save': 'Guardar',
  'Save As…': 'Guardar como…',
  'Print (Ctrl+P)': 'Imprimir (Ctrl+P)',
  'Select text': 'Seleccionar texto',
  'Highlight text': 'Resaltador',
  'Underline text': 'Subrayar',
  'Strike through text': 'Tachar',
  'Comment': 'Comentario',
  'Text box': 'Cuadro de texto',
  'Rectangle': 'Cuadro',
  'Circle': 'Círculo',
  'Arrow': 'Flecha',
  'Go to page': 'Ir a la página',
  'of': 'de',
  'Find (Ctrl+F)': 'Buscar (Ctrl+F)',
  'Zoom out': 'Alejar',
  'Zoom in': 'Acercar',
  'Fit to page width': 'Ajustar al ancho de página',
  'Whole page': 'Página entera',
  'Two pages': 'Dos páginas',
  'Information': 'Información',
  'Find in document': 'Buscar en el documento',
  'Previous (Shift+Enter)': 'Anterior (Mayús+Intro)',
  'Next (Enter)': 'Siguiente (Intro)',
  'Close (Esc)': 'Cerrar (Esc)',
  'Pages': 'Páginas',
  'Bookmarks': 'Marcadores',
  'Annotations': 'Anotaciones',
  'Drag to change the width': 'Arrastra para cambiar la anchura',
  'Get started': 'Comenzar a trabajar',
  'Open a PDF, or merge several': 'Abra un PDF, o combine varios',
  'Open…': 'Abrir…',
  'Merge…': 'Combinar…',
  // Colours
  'Yellow': 'Amarillo',
  'Green': 'Verde',
  'Blue': 'Azul',
  'Orange': 'Naranja',
  'Red': 'Rojo',
  'Lilac': 'Lila',
  'Grey': 'Gris',
  'Burgundy': 'Granate',
  // Annotations panel
  'Highlights': 'Resaltados',
  'Underlines': 'Subrayados',
  'Strikethroughs': 'Tachados',
  'Comments': 'Comentarios',
  'Text boxes': 'Cuadros de texto',
  'Rectangles': 'Cuadros',
  'Circles': 'Círculos',
  'Arrows': 'Flechas',
  'Highlight': 'Resaltado',
  'Underline': 'Subrayado',
  'Strikethrough': 'Tachado',
  'External': 'Externo',
  'Delete': 'Borrar',
  'page\u0004Delete': 'Eliminar',
  'Delete annotation': 'Borrar anotación',
  'Delete this annotation?': '¿Borrar esta anotación?',
  'Edit text': 'Editar texto',
  'Change colour': 'Cambiar color',
  'Turn on at least one annotation type.': 'Activa algún tipo de anotación.',
  'Loading annotations…': 'Cargando anotaciones…',
  'No annotations': 'Sin anotaciones',
  // Bookmarks panel
  'Add bookmark': 'Añadir marcador',
  'Bookmark title:': 'Título del marcador:',
  'Page {n}': 'Página {n}',
  'Add': 'Añadir',
  'Delete bookmark': 'Eliminar marcador',
  'dialog\u0004Delete bookmark': 'Borrar marcador',
  'Delete bookmarks': 'Borrar marcadores',
  'Delete {n} bookmarks?': '¿Borrar {n} marcadores?',
  'Delete the bookmark “{title}”?': '¿Borrar el marcador «{title}»?',
  'Bold': 'Negrita',
  'Italic': 'Cursiva',
  'Clear formatting (bold, italic and colour)': 'Quitar formato (negrita, cursiva y color)',
  'Expand / collapse bookmarks': 'Expandir / colapsar marcadores',
  'No bookmarks': 'Sin marcadores',
  'Edit bookmark': 'Editar marcador',
  'Title:': 'Título:',
  'Decrease indent (move up a level)': 'Disminuir sangría (subir de nivel)',
  'Increase indent (make a sub-item of the previous one)': 'Aumentar sangría (hacer subapartado del anterior)',
  'Point to the current page': 'Apuntar a la página actual',
  // Pages panel
  'Delete page': 'Eliminar página',
  'Delete pages': 'Eliminar páginas',
  'You can’t delete all the pages.': 'No puedes borrar todas las páginas.',
  'Delete {n} pages?': '¿Eliminar {n} páginas?',
  'Delete page {n}?': '¿Eliminar la página {n}?',
  'Add pages': 'Añadir páginas',
  'Extract pages': 'Extraer páginas',
  'Rotate 90° anticlockwise': 'Girar 90° a la izquierda',
  'Rotate 90° clockwise': 'Girar 90° a la derecha',
  // Saving
  'Flatten the form': 'Aplanar el formulario',
  'The data becomes part of the page and the fields can no longer be edited in the saved file.':
    'Los datos pasan a ser parte de la página y los campos dejan de ser editables en el archivo guardado.',
  '{n} form field(s) could not be saved.': 'No se han podido guardar {n} campo(s) del formulario.',
  'Could not flatten the form: {m}': 'No se pudo aplanar el formulario: {m}',
  'The form data could not be saved.': 'No se han podido guardar los datos del formulario.',
  'Saved ✔': 'Guardado ✔',
  'Saved ✔ (form flattened)': 'Guardado ✔ (formulario aplanado)',
  'Overwrite file': 'Sobrescribir archivo',
  'Do you want to overwrite “{name}”?': '¿Desea sobrescribir «{name}»?',
  'Overwrite': 'Sobrescribir',
  'This browser cannot overwrite files: a copy is being downloaded.':
    'Este navegador no puede sobrescribir: se descarga una copia.',
  'document.pdf': 'documento.pdf',
  'merged.pdf': 'combinado.pdf',
  '_flattened.pdf': '_aplanado.pdf',
  '_annotated.pdf': '_anotado.pdf',
  // Adding pages
  '{n} page': '{n} página',
  '{n} pages': '{n} páginas',
  'Blank page added.': 'Página en blanco añadida.',
  'PDF added: {pn} and its bookmarks.': 'PDF añadido: {pn} y sus marcadores.',
  'PDF added: {pn}.': 'PDF añadido: {pn}.',
  'From a PDF': 'Desde un PDF',
  'Choose PDF…': 'Elegir PDF…',
  'No file chosen': 'Ningún archivo elegido',
  'Blank page': 'Página en blanco',
  'Size:': 'Tamaño:',
  'Letter': 'Carta (Letter)',
  'Where should they be added?': '¿Dónde se añade?',
  'At the start': 'Al principio',
  'At the end': 'Al final',
  'After page': 'Después de la página',
  'The page must be between 1 and {n}.': 'La página debe estar entre 1 y {n}.',
  'Adding…': 'Añadiendo…',
  'Error adding: {m}': 'Error al añadir: {m}',
  // Find
  'Searching…': 'Buscando…',
  'No results': 'Sin resultados',
  '{n} result': '{n} resultado',
  '{n} results': '{n} resultados',
  '{i} of {n}': '{i} de {n}',
  // Print
  'Print': 'Imprimir',
  'Annotations to print:': 'Anotaciones que se imprimirán:',
  'Preparing to print…': 'Preparando la impresión…',
  'This browser does not allow printing from here: the PDF has been opened in another tab; print it from there.':
    'Este navegador no permite imprimir desde aquí: se ha abierto el PDF en otra pestaña; imprímelo desde ella.',
  // Generic dialogs
  'Cancel': 'Cancelar',
  'OK': 'Aceptar',
  // Unsaved changes
  'Save changes to “{name}”?': '¿Guardar los cambios de «{name}»?',
  'If you don’t save, your changes will be lost.': 'Si no los guardas, se perderán.',
  'Discard the changes to “{name}”?': '¿Descartar los cambios de «{name}»?',
  'This PDF is protected: its changes cannot be saved and will be lost.':
    'Este PDF está protegido: sus cambios no se pueden guardar y se perderán.',
  'Discard': 'Descartar',
  // Merge
  'Add PDFs…': 'Añadir PDFs…',
  'Create a bookmark for each file': 'Generar marcador asociado a cada archivo',
  'Keep the files’ bookmarks': 'Conservar marcadores de los archivos',
  'Merge': 'Combinar',
  'Drag PDFs here or click “Add PDFs…”': 'Arrastra aquí los PDF o pulsa «Añadir PDFs…»',
  '{n} p.': '{n} pág.',
  '{n} pp.': '{n} págs.',
  'Remove from list': 'Quitar de la lista',
  '{n} file': '{n} archivo',
  '{n} files': '{n} archivos',
  '{n} page in total': '{n} página en total',
  '{n} pages in total': '{n} páginas en total',
  'Could not read “{name}”: {m}': 'No se pudo leer «{name}»: {m}',
  'Merging…': 'Combinando…',
  'PDF merged: {n} pages. Use “Save As…” to save it.':
    'PDF combinado: {n} páginas. Usa «Guardar como…» para guardarlo.',
  'Error merging: {m}': 'Error al combinar: {m}',
  // Zoom, pages and extraction
  'Enter at least one page.': 'Indica al menos una página.',
  'Invalid format: “{t}”.': 'Formato no válido: «{t}».',
  'Page {p} does not exist (the document has {n}).': 'La página {p} no existe (el documento tiene {n}).',
  'Invalid range: “{t}”.': 'Rango no válido: «{t}».',
  'Open a PDF first.': 'Abre un PDF primero.',
  'Pages to extract:': 'Páginas a extraer:',
  'Examples:': 'Ejemplos:',
  '→ page 5 only': '→ solo la página 5',
  '→ pages 5 and 9': '→ páginas 5 y 9',
  '→ pages 5 to 10': '→ de la 5 a la 10',
  '→ page 5 to the end': '→ de la 5 hasta el final',
  '→ pages 1 and 5, 10 to 12, and 56 to the end': '→ las páginas 1 y 5, de la 10 a la 12 y de la 56 hasta el final',
  'Extract as separate pages': 'Extraer como páginas independientes',
  'Delete pages after extraction': 'Eliminar páginas tras extracción',
  'Delete bookmarks and annotations': 'Eliminar marcadores y anotaciones',
  'You can’t delete all the pages: untick “Delete pages after extraction”.':
    'No puedes eliminar todas las páginas: desmarca «Eliminar páginas tras extracción».',
  'extracted': 'extraidas',
  'Existing files': 'Archivos existentes',
  'Already in the folder:': 'Ya existe en la carpeta:',
  '…and {n} more': '…y {n} más',
  'Do you want to overwrite them or rename the new ones?': '¿Quieres sobrescribir o renombrar los nuevos?',
  'Rename': 'Renombrar',
  'This browser does not allow choosing a folder: the files will be downloaded.':
    'Este navegador no permite elegir carpeta: se descargarán los archivos.',
  '{x} into {f}': '{x} en {f}',
  '{n} page extracted': '{n} página extraída',
  '{n} pages extracted': '{n} páginas extraídas',
  ' and removed from the document': ' y eliminadas del documento',
  // Protected PDFs
  'Protected PDF': 'PDF protegido',
  'This PDF is protected. Any changes made to it cannot be saved. It cannot be printed and pages cannot be extracted either.':
    'Este PDF está protegido. Cualquier cambio que se haga sobre él no podrá ser guardado. Tampoco se podrá imprimir ni extraer páginas.',
  'This PDF is protected against changes: Penfold cannot save it, print it or extract pages from it yet.':
    'Este PDF está protegido contra cambios: Penfold todavía no puede guardarlo, imprimirlo ni extraer páginas.',
  '“{name}” is protected against changes and cannot be added yet.':
    '«{name}» está protegido contra cambios y todavía no se puede añadir.',
  'Cannot be merged': 'No combinable',
  // About dialog (Information button)
  'Version {v}': 'Versión {v}',
  'Read, annotate and organise your PDFs.': 'Lee, anota y organiza tus PDF.',
  'Website': 'Sitio web',
  'Report an issue': 'Informar de un error',
  'Created by {a}, with AI assistance': 'Creado por {a}, con ayuda de IA',
  'Uses pdf.js (Apache-2.0) · pdf-lib (MIT) · Lucide icons (ISC)':
    'Usa pdf.js (Apache-2.0) · pdf-lib (MIT) · iconos Lucide (ISC)',
  'Licence {l}': 'Licencia {l}',
  'Close': 'Cerrar',
};
const LANG = (() => {
  try {
    const q = new URLSearchParams(location.search).get('lang');
    if (q === 'es' || q === 'en') return q;
  } catch (e) {}
  const ls = (
    navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || 'en']
  ).map((x) => String(x).toLowerCase().split('-')[0]);
  return (
    ls.find((x) => x === 'es' || x === 'en') || (ls.some((x) => x === 'eu' || x === 'ca' || x === 'gl') ? 'es' : 'en')
  );
})();
document.documentElement.lang = LANG;
// _t translates a string ({name} placeholders are filled from v; c is the optional context). _n picks the singular or plural form for n.
const _t = (s, v, c) => {
  const r = LANG == 'es' && ES[c ? c + '\u0004' + s : s] !== undefined ? ES[c ? c + '\u0004' + s : s] : s;
  return v ? r.replace(/\{(\w+)\}/g, (m, k) => (k in v ? v[k] : m)) : r;
};
const _n = (n, one, many) => _t(n == 1 ? one : many, { n });
// Translates the static text (text nodes and title / placeholder attributes) of an element: the page itself and every dialog built from HTML.
function i18nApply(root) {
  if (LANG == 'en') return;
  const tr = (x) => {
    const m = x.match(/^(\s*)([\s\S]*?)(\s*)$/);
    return m[2] && ES[m[2]] !== undefined ? m[1] + ES[m[2]] + m[3] : x;
  };
  [root, ...root.querySelectorAll('*')].forEach((el) => {
    if (/^(SCRIPT|STYLE)$/.test(el.tagName)) return;
    ['title', 'placeholder'].forEach((a) => {
      const v = el.getAttribute(a);
      if (v !== null && ES[v] !== undefined) el.setAttribute(a, ES[v]);
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
let docs = [],
  pages = [],
  handle = null,
  fname = _t('document.pdf'),
  tool = 'sel',
  color = '#f9f06b',
  scale = 1.3,
  tab = 'th',
  lastTab = 'th',
  bms = [],
  cur = 0;
let dragBms = [],
  dragPgs = [],
  flashBm = null,
  twoUp = false;
const selPages = new Set(),
  selBms = new Set();
let anchor = -1,
  anchorBm = null;

const PAL = [
  { n: 'Yellow', p: '#f9f06b' },
  { n: 'Green', p: '#8ff0a4' },
  { n: 'Blue', p: '#99c1f1' },
  { n: 'Orange', p: '#ffbe6f' },
  { n: 'Red', p: '#f66151' },
  { n: 'Lilac', p: '#dc8add' },
];
// Palette for bookmarks: the 6 colours plus 2 more (4 columns × 2 rows, the extra one on the right of each row)
const BM_PAL = [
  PAL[0],
  PAL[1],
  PAL[2],
  { n: 'Grey', p: '#606971' },
  PAL[3],
  PAL[4],
  PAL[5],
  { n: 'Burgundy', p: '#ad182e' },
];
// Single palette: there is no separate deep tone any more. The function is kept so existing uses stay untouched.
const deep = (c) => c;
// Text box: measurements in PDF units (fs = font size, pad = inner padding, bw = border width, w = default width)
const FT = { fs: 11, pad: 6, bw: 1, lh: 1.2, w: 200 };
const SW = 1;
// Comment icon (Lucide message-square-text): black outline, filled with the annotation's colour. Same drawing on screen and in the PDF.
const NOTE_SW = 1.5;
const noteSvg = (c) =>
  '<svg viewBox="2 2 20 20"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" fill="' +
  c +
  '" stroke="#000" stroke-width="' +
  NOTE_SW +
  '" stroke-linecap="round" stroke-linejoin="round"/><path d="M13 8H7M17 12H7" fill="none" stroke="#000" stroke-width="' +
  NOTE_SW +
  '" stroke-linecap="round"/></svg>';
const tint = (c, t) =>
  '#' +
  [1, 3, 5]
    .map((i) =>
      Math.round(255 * (1 - t) + parseInt(c.substr(i, 2), 16) * t)
        .toString(16)
        .padStart(2, '0'),
    )
    .join('');
function ftH(a) {
  const m = document.createElement('div');
  m.style.cssText =
    'position:absolute;left:-9999px;top:0;visibility:hidden;box-sizing:border-box;white-space:pre-wrap;overflow-wrap:break-word;width:' +
    (a.w || FT.w) +
    'px;font:' +
    FT.fs +
    'px/' +
    FT.lh +
    ' Helvetica,Arial,sans-serif;padding:' +
    FT.pad +
    'px;border:' +
    FT.bw +
    'px solid';
  m.textContent = a.text;
  document.body.appendChild(m);
  const h = m.offsetHeight;
  m.remove();
  return h;
}
$('#sws').innerHTML = PAL.map(
  (x) =>
    `<button class="sw${x.p == color ? ' on' : ''}" data-c="${x.p}" title="${_t(x.n)}" style="background:${x.p}"></button>`,
).join('');
let mt;
const msg = (t) => {
  const m = $('#msg');
  m.textContent = t;
  m.style.display = 'block';
  clearTimeout(mt);
  mt = setTimeout(() => (m.style.display = 'none'), 4500);
};
document.querySelectorAll('[data-t]').forEach(
  (b) =>
    (b.onclick = () => {
      tool = b.dataset.t;
      document.querySelectorAll('[data-t]').forEach((x) => x.classList.toggle('on', x == b));
      document.body.className = 'tool-' + tool;
    }),
);
document.querySelectorAll('.sw').forEach(
  (b) =>
    (b.onclick = () => {
      color = b.dataset.c;
      document.querySelectorAll('.sw').forEach((x) => x.classList.toggle('on', x == b));
    }),
);
$('#zi').onclick = () =>
  zoomTo(() => {
    scale = Math.min(4, scale + 0.2);
  });
$('#zo').onclick = () =>
  zoomTo(() => {
    scale = Math.max(0.3, scale - 0.2);
  });
document.querySelectorAll('#tabs button').forEach(
  (b) =>
    (b.onclick = () => {
      tab = b.dataset.tab;
      renderSide();
      followThumb(true);
    }),
);

function rotatePages(list, dir) {
  list.forEach((p) => {
    p.rot = ((p.rot || 0) + dir + 360) % 360;
    p.thumb = null;
  });
  renderSide();
  zoomTo(() => {});
}
const pathTo = (l, t) => {
  for (const x of l) {
    if (x === t) return [x];
    const r = pathTo(x.items, t);
    if (r) return [x, ...r];
  }
  return null;
};
const openAnc = (t) => (pathTo(bms, t) || []).slice(0, -1).forEach((x) => (x.open = true));
async function addBookmark() {
  let title = null,
    pi = cur;
  const sel = getSelection();
  if (sel && sel.rangeCount && !sel.isCollapsed) {
    const n = sel.getRangeAt(0).startContainer,
      el = (n.nodeType == 1 ? n : n.parentElement).closest('.page');
    if (el) {
      const t = sel.toString().replace(/\s+/g, ' ').trim();
      if (t) {
        title = t.length > 150 ? t.slice(0, 150) + '…' : t;
        pi = +el.dataset.i;
      }
    }
  }
  if (!title) {
    title = await promptDialog(_t('Add bookmark'), _t('Bookmark title:'), _t('Page {n}', { n: pi + 1 }), _t('Add'));
    if (!title) return;
  }
  const nb = { title, page: pages[pi], items: [] },
    flat = [];
  const fl = (l) =>
    l.forEach((x) => {
      flat.push(x);
      fl(x.items);
    });
  fl(bms);
  let ref = null;
  flat.forEach((x) => {
    if (pages.indexOf(x.page) <= pi) ref = x;
  });
  if (!ref) bms.unshift(nb);
  else if (ref.items.length) {
    ref.items.unshift(nb);
    ref.open = true;
    openAnc(ref);
  } else {
    const f = locate(bms, ref);
    f.list.splice(f.i + 1, 0, nb);
    openAnc(ref);
  }
  flashBm = nb;
  renderSide();
}
const inTree = (a, b) => a === b || a.items.some((c) => inTree(c, b));
const dragSet = (it) => {
  if (!(selBms.has(it) && selBms.size > 1)) return [it];
  const flat = [];
  const fl = (l) =>
    l.forEach((x) => {
      flat.push(x);
      fl(x.items);
    });
  fl(bms);
  return flat.filter((n) => selBms.has(n) && !(pathTo(bms, n) || []).slice(0, -1).some((a) => selBms.has(a)));
};
const detach = (l, n) => {
  const i = l.indexOf(n);
  if (i >= 0) {
    l.splice(i, 1);
    return true;
  }
  return l.some((x) => detach(x.items, n));
};
const locate = (l, t) => {
  const i = l.indexOf(t);
  if (i >= 0) return { list: l, i };
  for (const x of l) {
    const r = locate(x.items, t);
    if (r) return r;
  }
};
// PDF destinations (/XYZ, /FitH…): name + numeric arguments (null = no value). Kept when the outline is read and written back unchanged on save.
const DD_N = { XYZ: 3, Fit: 0, FitH: 1, FitV: 1, FitR: 4, FitB: 0, FitBH: 1, FitBV: 1 };
const ddOk = (dd) =>
  !!dd &&
  Object.prototype.hasOwnProperty.call(DD_N, dd.n) &&
  Array.isArray(dd.a) &&
  dd.a.length == DD_N[dd.n] &&
  dd.a.every((v) => v === null || (typeof v == 'number' && isFinite(v)));
const ddFrom = (d) => {
  const n = d && d[1] && d[1].name;
  if (typeof n != 'string' || !Object.prototype.hasOwnProperty.call(DD_N, n)) return null;
  const a = d.slice(2, 2 + DD_N[n]).map((v) => (typeof v == 'number' && isFinite(v) ? v : null));
  while (a.length < DD_N[n]) a.push(null);
  return { n, a };
};
// Height (in PDF points) a destination points to; null if it only names the page
const ddY = (dd) =>
  !ddOk(dd)
    ? null
    : dd.n == 'XYZ'
      ? dd.a[1]
      : dd.n == 'FitH' || dd.n == 'FitBH'
        ? dd.a[0]
        : dd.n == 'FitR'
          ? dd.a[3]
          : null;
const prune = (l, ps = pages) =>
  l.flatMap((i) => (i.page && ps.includes(i.page) ? [{ ...i, items: prune(i.items, ps) }] : prune(i.items, ps)));
const toHex = (c) =>
  c && (c[0] || c[1] || c[2]) ? '#' + [c[0], c[1], c[2]].map((v) => v.toString(16).padStart(2, '0')).join('') : null;
async function convert(items, di) {
  const r = [];
  for (const it of items) {
    let pg = null,
      dd = null;
    try {
      let d = it.dest;
      if (typeof d == 'string') d = await docs[di].pdf.getDestination(d);
      const n = await docs[di].pdf.getPageIndex(d[0]);
      pg = pages.find((p) => p.doc == di && p.idx == n) || null;
      dd = ddFrom(d);
    } catch (e) {}
    r.push({
      title: it.title,
      page: pg,
      dd,
      color: toHex(it.color),
      bold: !!it.bold,
      italic: !!it.italic,
      items: await convert(it.items || [], di),
    });
  }
  return r;
}
async function pickFile() {
  if (window.showOpenFilePicker) {
    const [h] = await showOpenFilePicker({ types: [{ accept: { 'application/pdf': ['.pdf'] } }] });
    return { h, f: await h.getFile() };
  }
  return new Promise((res) => {
    const i = document.createElement('input');
    i.type = 'file';
    i.accept = '.pdf';
    i.onchange = () => res({ h: null, f: i.files[0] });
    i.click();
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
const LOCK_TXT = () =>
  _t(
    'This PDF is protected. Any changes made to it cannot be saved. It cannot be printed and pages cannot be extracted either.',
  );
function protectedNotice() {
  choiceDialog('', LOCK_TXT(), [[_t('OK'), 'ok', true]]);
  const h = document.querySelector('#dlg2 h3');
  if (h) {
    h.innerHTML = WARN_SVG;
    h.className = 'warn';
  }
  const t = document.querySelector('#dlg2 .box>div');
  if (t) t.style.textAlign = 'center';
  const b = document.querySelector('#dlg2 button.on');
  if (b) b.focus();
}
// Reminder while a protected PDF is open: the warning sign stays fixed at the top-left corner of the viewer; hovering it shows the notice
function lockBadge() {
  const w = $('#lockw'),
    on = isLocked();
  w.style.display = on ? '' : 'none';
  if (!on) return;
  if (!w.firstChild) w.innerHTML = WARN_SVG;
  w.dataset.text = LOCK_TXT();
  const r = $('#view').getBoundingClientRect();
  w.style.left = r.left + 10 + 'px';
  w.style.top = r.top + 10 + 'px';
}
// Every PDF is opened with isEvalSupported:false (here, in insertPdf and in the Merge dialogue): pdf.js 3.11 could
// otherwise run JavaScript hidden in a crafted font (CVE-2024-4367). Glyphs are then drawn without compiled code; same result.
async function load(f) {
  const bytes = await f.arrayBuffer(),
    pdf = await pdfjsLib.getDocument({ data: bytes.slice(0), isEvalSupported: false }).promise;
  const di = docs.push({ bytes, pdf, enc: await isProtected(pdf, bytes) }) - 1;
  for (let i = 0; i < pdf.numPages; i++)
    pages.push({ doc: di, idx: i, annots: [], thumb: null, rot: 0, loaded: false });
  return di;
}
$('#bOpen').onclick = async () => {
  try {
    const { h, f } = await pickFile();
    if (!(await confirmUnsaved())) return;
    docs = [];
    pages = [];
    selPages.clear();
    selBms.clear();
    anchor = -1;
    anchorBm = null;
    handle = h;
    fname = f.name;
    const di = await load(f);
    bms = prune(await convert((await docs[di].pdf.getOutline()) || [], di));
    markSaved();
    tab = bms.length ? 'bm' : 'th';
    ready();
    if (docs[di].enc) protectedNotice();
  } catch (e) {
    if (e.name != 'AbortError') msg('Error: ' + e.message);
  }
};
function setPanel(v) {
  $('#side').style.display = $('#rs').style.display = v ? '' : 'none';
  $('#bPanel').classList.toggle('on', v);
  if (v) followThumb(true);
}
$('#bPanel').onclick = () => {
  const w0 = $('#view').clientWidth;
  setPanel($('#side').style.display == 'none');
  reflowOnWidth(w0);
};
setPanel(false);
// Toolbar controls that are no use until a PDF is open (Open, Merge and Information are always enabled)
const NEED_PDF = '#bPanel,.ib[data-t],.sw,#pg,#zo,#zi,#fw,#fp,#two';
document.querySelectorAll(NEED_PDF).forEach((b) => (b.disabled = true));
function ready() {
  ['#bSave', '#bSaveAs', '#bPrint', '#bFind'].forEach((s) => ($(s).disabled = s != '#bFind' && isLocked()));
  document.querySelectorAll(NEED_PDF).forEach((b) => (b.disabled = false));
  setPanel(true);
  lockBadge();
  renderSide();
  fitOnOpen();
  loadAllAnnots();
  if ($('#sb').style.display == 'flex') runFind();
}

async function thumb(p) {
  if (p.thumb) return p.thumb;
  const pg = await docs[p.doc].pdf.getPage(p.idx + 1),
    vp = pg.getViewport({ scale: 0.3, rotation: (pg.rotate + (p.rot || 0)) % 360 }),
    c = document.createElement('canvas');
  c.width = vp.width;
  c.height = vp.height;
  await pg.render({ canvasContext: c.getContext('2d'), viewport: vp }).promise;
  return (p.thumb = c.toDataURL());
}

const io = new IntersectionObserver(
  (es) =>
    es.forEach((e) => {
      if (e.isIntersecting && !e.target._done) {
        e.target._done = 1;
        paint(e.target);
      }
    }),
  { root: null, rootMargin: '600px' },
);
const thIo = new IntersectionObserver(
  (es) =>
    es.forEach((e) => {
      if (e.isIntersecting && !e.target._done) {
        e.target._done = 1;
        thumb(e.target._p).then((u) => {
          const el = e.target,
            im = el.querySelector('img');
          im.onload = () => {
            const ar = im.naturalWidth / im.naturalHeight;
            if (ar > 0 && ar < 0.999) {
              el.style.setProperty('--ar', ar.toFixed(4));
              el.classList.add('pt');
            }
          };
          im.src = u;
        });
      }
    }),
  { root: null, rootMargin: '600px' },
);

// Thumbnails: a cell never exceeds TH_W px in width (the same maximum zoom with 1, 2, 3 or 4 columns).
// Just enough columns are used to satisfy that, up to TH_C at most; the panel's maximum width follows from that cap.
const TH_W = 310,
  TH_G = 10,
  TH_C = 4,
  TH_SB = 14;
// Minimum width of the side panel: so the Bookmarks tab bar (left 54 + centre 120 + right 54, symmetrical, + 6) always fits on one row
const SIDE_MIN = 2 * 54 + 120 + 6 + 16 + 1 + TH_SB;
const thMaxPanel = () => Math.min(TH_C * TH_W + (TH_C - 1) * TH_G + 16 + TH_SB + 1, innerWidth - 160);
function thCols() {
  const sb = $('#sbody'),
    a = sb.clientWidth - 16;
  if (a <= 0) return;
  const n = Math.max(1, Math.min(TH_C, Math.ceil((a + TH_G) / (TH_W + TH_G))));
  if (sb.dataset.cols != n) {
    sb.dataset.cols = n;
    sb.style.setProperty('--cols', n);
  }
}
// Top bar shared by the panels (Bookmarks, Pages and Annotations): grey background and three zones (left, centre, right)
function sbar() {
  const row = document.createElement('div');
  row.className = 'sbw';
  row.style.cssText =
    'position:sticky;top:-8px;margin-top:-8px;margin-bottom:8px;padding-top:8px;background:var(--pane);z-index:10';
  const bar = document.createElement('div');
  bar.className = 'sbar';
  row.appendChild(bar);
  const mkb = (ico, tip, fn) => {
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
  const grp = (cls, ...bs) => {
    const g = document.createElement('div');
    g.className = 'g' + (cls ? ' ' + cls : '');
    g.append(...bs);
    bar.appendChild(g);
  };
  return { row, mkb, grp };
}
// Annotations: which types are listed (comments and text boxes by default)
const anOn = { note: true, ft: true, hl: false, ul: false, so: false, sq: false, ci: false, ar: false };
// Pages: updates the state of the bar buttons when the selection changes, without redrawing the panel
let thBar = null;
function renderSide() {
  const sb = $('#sbody');
  const isSameTab = lastTab === tab;
  const prevScroll = isSameTab ? sb.scrollTop : 0;
  lastTab = tab;
  document.querySelectorAll('#tabs button').forEach((b) => b.classList.toggle('on', b.dataset.tab == tab));
  sb.innerHTML = '';
  sb.style.scrollbarGutter = tab == 'th' ? 'stable' : '';
  thCols();
  if (tab == 'an') {
    const T = [
        ['hl', _t('Highlights')],
        ['ul', _t('Underlines')],
        ['so', _t('Strikethroughs')],
        ['note', _t('Comments')],
        ['ft', _t('Text boxes')],
        ['sq', _t('Rectangles')],
        ['ci', _t('Circles')],
        ['ar', _t('Arrows')],
      ],
      G = { note: [], ft: [], hl: [], ul: [], so: [], sq: [], ci: [], ar: [] };
    const IC = {
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
    const B = sbar();
    const mBtns = [];
    T.forEach(([t, title], i) => {
      if (i == 3 || i == 5) {
        const s = document.createElement('span');
        s.className = 'sep';
        s.style.margin = '0';
        mBtns.push(s);
      }
      const b = B.mkb(IC[t], title, () => {
        anOn[t] = !anOn[t];
        renderSide();
      });
      b.classList.toggle('on', anOn[t]);
      mBtns.push(b);
    });
    B.grp('m', ...mBtns);
    B.row.querySelector('.g.m').style.gap = '4px';
    sb.appendChild(B.row);
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
      p.annots.forEach((a, k) => (G[a.type] ? G[a.type].push({ a, p, i, k, x: xOf(a), y: yOf(a) }) : null)),
    );
    let n = 0;
    T.forEach(([t, title]) => {
      const L = G[t];
      if (!anOn[t] || !L.length) return;
      n += L.length;
      L.sort((u, v) => u.i - v.i || v.y - u.y || u.x - v.x);
      const h = document.createElement('div');
      h.style.cssText = 'padding:8px 4px 4px';
      const ti = document.createElement('span');
      ti.style.fontWeight = '600';
      ti.textContent = title;
      const ct = document.createElement('span');
      ct.style.opacity = '.6';
      ct.textContent = ' (' + L.length + ')';
      h.append(ti, ct);
      sb.appendChild(h);
      L.forEach(({ a, p, i, k, y }) => {
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
        const tx = document.createElement('div');
        tx.style.cssText =
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
        tx.textContent = baseTx;
        if (!str && !a.ro) tx.style.opacity = '.7';
        if (a.ro && str) tx.title = str;
        const pg = document.createElement('span');
        pg.style.opacity = '.6';
        pg.textContent = i + 1;
        const ctl = document.createElement('span');
        ctl.className = 'ctl';
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
            const ed = document.createElement('button');
            ed.textContent = '✎';
            ed.title = _t('Edit text');
            ed.onclick = (ev) => {
              ev.stopPropagation();
              textDialog(_t('Edit text'), a.text, (n) => {
                a.text = n;
                redraw();
              });
            };
            ctl.append(ed);
          }
          {
            const ci = document.createElement('button');
            ci.title = _t('Change colour');
            ci.style.cssText =
              'width:20px;height:20px;padding:0;border-radius:4px;margin:2px 3px;border:1px solid var(--line);background:' +
              (t == 'ft' || t == 'sq' || t == 'ci' || t == 'ar' ? deep(a.color) : a.color);
            ci.onclick = (ev) => {
              ev.stopPropagation();
              openPal(ci, (pc) => {
                a.color = t == 'hl' || t == 'note' ? pc : deep(pc);
                redraw();
              });
            };
            ctl.append(ci);
          }
          ctl.append(x);
        }
        e.onclick = () => goTo(i, y);
        e.append(tx, pg, ctl);
        sb.appendChild(e);
      });
    });
    if (!n) {
      const z = document.createElement('div');
      z.style.opacity = '.6';
      z.textContent = !T.some(([t]) => anOn[t])
        ? _t('Turn on at least one annotation type.')
        : annBusy
          ? _t('Loading annotations…')
          : _t('No annotations');
      sb.appendChild(z);
    }
    if (isSameTab) sb.scrollTop = prevScroll;
    return;
  }
  if (tab == 'bm') {
    // Top bar: left (add / delete), centre (format) and right (expand / collapse). Acts on the selected bookmarks that are visible.
    const { row, mkb, grp } = sbar();
    const sel = () => flatBms.filter((x) => selBms.has(x));
    const add = mkb('<path d="M5 12h14"/><path d="M12 5v14"/>', _t('Add bookmark'), addBookmark);
    add.id = 'addbm';
    const del = mkb(
      '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/>',
      _t('Delete bookmark'),
      async () => {
        const ts = sel();
        if (!ts.length) return;
        if (
          await confirmDialog(
            ts.length > 1 ? _t('Delete bookmarks') : _t('Delete bookmark', null, 'dialog'),
            ts.length > 1
              ? _t('Delete {n} bookmarks?', { n: ts.length })
              : _t('Delete the bookmark “{title}”?', { title: ts[0].title }),
            _t('Delete'),
          )
        ) {
          ts.forEach((x) => detach(bms, x));
          selBms.clear();
          renderSide();
        }
      },
    );
    const bold = mkb(
      '<path d="M6 12h9a4 4 0 0 1 0 8H7a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h7a4 4 0 0 1 0 8"/>',
      _t('Bold'),
      () => {
        const ts = sel(),
          v = !ts.every((x) => x.bold);
        ts.forEach((x) => (x.bold = v));
        renderSide();
      },
    );
    const ita = mkb(
      '<line x1="19" x2="10" y1="4" y2="4"/><line x1="14" x2="5" y1="20" y2="20"/><line x1="15" x2="9" y1="4" y2="20"/>',
      _t('Italic'),
      () => {
        const ts = sel(),
          v = !ts.every((x) => x.italic);
        ts.forEach((x) => (x.italic = v));
        renderSide();
      },
    );
    const pal = mkb(
      '<circle cx="13.5" cy="6.5" r=".5"/><circle cx="17.5" cy="10.5" r=".5"/><circle cx="8.5" cy="7.5" r=".5"/><circle cx="6.5" cy="12.5" r=".5"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/>',
      _t('Change colour'),
      () =>
        openPal(
          pal,
          (pc) => {
            sel().forEach((x) => (x.color = deep(pc)));
            renderSide();
          },
          BM_PAL,
        ),
    );
    const rf = mkb(
      '<path d="M4 7V4h16v3"/><path d="M5 20h6"/><path d="M13 4 8 20"/><path d="m15 15 5 5"/><path d="m20 15-5 5"/>',
      _t('Clear formatting (bold, italic and colour)'),
      () => {
        sel().forEach((x) => {
          x.bold = false;
          x.italic = false;
          x.color = null;
        });
        renderSide();
      },
    );
    const all = mkb('<path d="m7 15 5 5 5-5"/><path d="m7 9 5-5 5 5"/>', _t('Expand / collapse bookmarks'), () => {
      const anyOpen = (l) => l.some((x) => x.items.length && (x.open !== false || anyOpen(x.items)));
      const v = !anyOpen(bms);
      const set = (l) =>
        l.forEach((x) => {
          x.open = v;
          set(x.items);
        });
      set(bms);
      renderSide();
    });
    all.textContent = '⇕';
    all.style.fontSize = '16px';
    grp('l', add, del);
    grp('c', bold, ita, pal, rf);
    grp('r', all);
    // Button states follow the selection: with nothing selected there is nothing to delete or format; bold and italic show as active
    const upd = () => {
      const ts = sel(),
        no = !ts.length;
      [del, bold, ita, pal, rf].forEach((b) => (b.disabled = no));
      bold.classList.toggle('on', !no && ts.every((x) => x.bold));
      ita.classList.toggle('on', !no && ts.every((x) => x.italic));
    };
    sb.appendChild(row);
    if (!bms.length) {
      const n = document.createElement('div');
      n.style.opacity = '.6';
      n.textContent = _t('No bookmarks');
      sb.appendChild(n);
    }
    const flatBms = [];
    const flatten = (l) =>
      l.forEach((x) => {
        flatBms.push(x);
        if (x.open !== false) flatten(x.items);
      });
    flatten(bms);
    upd();
    const walk = (list, d, up) =>
      list.forEach((it, i) => {
        const e = document.createElement('div');
        e.className = 'bm' + (selBms.has(it) ? ' sel' : '');
        e.draggable = true;
        e.style.paddingLeft = 4 + d * 14 + 'px';
        const tg = document.createElement('span');
        tg.style.cssText = 'width:16px;flex-shrink:0;text-align:center;opacity:.7';
        if (it.items.length) {
          tg.textContent = it.open === false ? '▸' : '▾';
          tg.onclick = (ev) => {
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
            if (k >= 0) goTo(k, ddY(it.dd));
          }
        };
        e.onclick = (ev) => {
          ev.stopPropagation();
          if (ev.shiftKey && anchorBm) {
            const a = flatBms.indexOf(anchorBm),
              b = flatBms.indexOf(it);
            if (a >= 0 && b >= 0) {
              if (!(ev.ctrlKey || ev.metaKey)) selBms.clear();
              for (let k = Math.min(a, b); k <= Math.max(a, b); k++) selBms.add(flatBms[k]);
            }
          } else if (ev.ctrlKey || ev.metaKey) {
            selBms.has(it) ? selBms.delete(it) : selBms.add(it);
            anchorBm = it;
          } else {
            selBms.clear();
            selBms.add(it);
            anchorBm = it;
          }
          renderSide();
        };
        const mv = (txt, tip, fn) => {
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
        const ctl = document.createElement('span');
        ctl.className = 'ctl';
        const bTg = () => (selBms.has(it) && selBms.size > 1 ? Array.from(selBms) : [it]);
        ctl.append(
          mv('✎', _t('Edit bookmark'), () => {
            promptDialog(_t('Edit bookmark'), _t('Title:'), it.title, _t('Save')).then((n) => {
              if (n) {
                it.title = n;
                renderSide();
              }
            });
          }),
          mv('←', _t('Decrease indent (move up a level)'), () => {
            if (up) {
              list.splice(i, 1);
              up.list.splice(up.i + 1, 0, it);
            }
          }),
          mv('→', _t('Increase indent (make a sub-item of the previous one)'), () => {
            if (i > 0) {
              list.splice(i, 1);
              list[i - 1].items.push(it);
              list[i - 1].open = true;
            }
          }),
          mv('⚑', _t('Point to the current page'), () => {
            bTg().forEach((x) => {
              x.page = pages[cur];
              x.dd = null;
            });
          }),
        );
        const clr = () => e.classList.remove('before', 'after', 'inside');
        const zone = (ev) => {
          const r = e.getBoundingClientRect(),
            y = (ev.clientY - r.top) / r.height;
          return y < 0.3 ? 'before' : y > 0.7 ? 'after' : 'inside';
        };
        e.ondragstart = (ev) => {
          dragBms = dragSet(it);
          ev.dataTransfer.setData('text/plain', 'bm');
          ev.dataTransfer.effectAllowed = 'move';
        };
        e.ondragend = () => {
          dragBms = [];
          renderSide();
        };
        e.ondragover = (ev) => {
          if (!dragBms.length || dragBms.some((n) => inTree(n, it))) return;
          ev.preventDefault();
          clr();
          e.classList.add(zone(ev));
        };
        e.ondragleave = clr;
        e.ondrop = (ev) => {
          if (!dragBms.length || dragBms.some((n) => inTree(n, it))) return;
          ev.preventDefault();
          const z = zone(ev),
            ns = dragBms;
          ns.forEach((n) => detach(bms, n));
          if (z == 'inside') {
            it.items.push(...ns);
            it.open = true;
          } else {
            const f = locate(bms, it);
            f.list.splice(f.i + (z == 'after' ? 1 : 0), 0, ...ns);
          }
          dragBms = [];
          renderSide();
        };
        e.append(tg, t, ctl);
        sb.appendChild(e);
        if (it === flashBm) {
          e.style.background = 'color-mix(in srgb,var(--acc) 30%,transparent)';
          requestAnimationFrame(() => e.scrollIntoView({ block: 'nearest' }));
        }
        if (it.open !== false) walk(it.items, d + 1, { list, i });
      });
    walk(bms, 0);
    const hadFlash = !!flashBm;
    flashBm = null;
    const end = document.createElement('div');
    end.style.minHeight = '80px';
    end.ondragover = (ev) => {
      if (dragBms.length) ev.preventDefault();
    };
    end.ondrop = (ev) => {
      if (!dragBms.length) return;
      ev.preventDefault();
      const ns = dragBms;
      ns.forEach((n) => detach(bms, n));
      bms.push(...ns);
      dragBms = [];
      renderSide();
    };
    sb.appendChild(end);
    if (isSameTab && !hadFlash) sb.scrollTop = prevScroll;
    return;
  }
  // Top bar: delete (left), extract (centre) and rotate (right). Delete and rotate act on the selected pages.
  {
    const T = sbar(),
      sel = () => pages.filter((x) => selPages.has(x));
    const del = T.mkb(
      '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/>',
      _t('Delete page'),
      async () => {
        const tgs = sel();
        if (!tgs.length) return;
        if (pages.length <= tgs.length) {
          msg(_t('You can’t delete all the pages.'));
          return;
        }
        if (
          await confirmDialog(
            tgs.length > 1 ? _t('Delete pages') : _t('Delete page'),
            tgs.length > 1
              ? _t('Delete {n} pages?', { n: tgs.length })
              : _t('Delete page {n}?', { n: pages.indexOf(tgs[0]) + 1 }),
            _t('Delete', null, 'page'),
          )
        ) {
          tgs.forEach((x) => {
            const idx = pages.indexOf(x);
            if (idx >= 0) pages.splice(idx, 1);
          });
          selPages.clear();
          bms = prune(bms);
          renderSide();
          renderMain();
        }
      },
    );
    const ad = T.mkb(
      '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M12 11v6M9 14h6"/>',
      _t('Add pages'),
      addDialog,
    );
    ad.disabled = !pages.length;
    const ex = T.mkb(
      '<path d="M16 3h5v5"/><path d="M8 3H3v5"/><path d="M12 22v-8.3a4 4 0 0 0-1.172-2.872L3 3"/><path d="m15 9 6-6"/>',
      _t('Extract pages'),
      () => extractDialog(),
    );
    ex.disabled = isLocked();
    const rl = T.mkb(
      '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
      _t('Rotate 90° anticlockwise'),
      () => rotatePages(sel(), -90),
    );
    const rr = T.mkb(
      '<path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>',
      _t('Rotate 90° clockwise'),
      () => rotatePages(sel(), 90),
    );
    T.grp('l', del);
    T.grp('c', ad, ex);
    T.grp('r', rl, rr);
    thBar = () => {
      const no = !sel().length;
      [del, rl, rr].forEach((b) => (b.disabled = no));
    };
    thBar();
    sb.appendChild(T.row);
  }
  const grid = document.createElement('div');
  grid.className = 'grid';
  sb.appendChild(grid);
  thIo.disconnect();
  pages.forEach((p, i) => {
    const d = document.createElement('div');
    d.className = 'th' + (i == cur ? ' cur' : '') + (selPages.has(p) ? ' sel' : '');
    d.draggable = true;
    d.innerHTML = `<img alt=""><div class="n">${i + 1}</div>`;
    d._p = p;
    thIo.observe(d);
    d.onclick = (e) => {
      if (e.shiftKey && anchor >= 0) {
        const a = Math.min(anchor, i),
          b = Math.max(anchor, i);
        if (!(e.ctrlKey || e.metaKey)) selPages.clear();
        for (let k = a; k <= b; k++) selPages.add(pages[k]);
      } else if (e.ctrlKey || e.metaKey) {
        if (selPages.has(p)) selPages.delete(p);
        else selPages.add(p);
        anchor = i;
      } else {
        selPages.clear();
        selPages.add(p);
        anchor = i;
      }
      goTo(i);
      document.querySelectorAll('.th').forEach((x, k) => x.classList.toggle('sel', selPages.has(pages[k])));
      if (thBar) thBar();
    };
    d.ondragstart = (e) => {
      e.dataTransfer.setData('text/plain', i);
      dragPgs = selPages.has(p) && selPages.size > 1 ? pages.filter((x) => selPages.has(x)) : [p];
    };
    d.ondragover = (e) => {
      e.preventDefault();
      d.classList.add('over');
    };
    d.ondragleave = () => d.classList.remove('over');
    d.ondrop = (e) => {
      e.preventDefault();
      const f = +e.dataTransfer.getData('text/plain');
      if (f == i || dragPgs.includes(p)) {
        d.classList.remove('over');
        return;
      }
      const ms = dragPgs;
      pages = pages.filter((x) => !ms.includes(x));
      pages.splice(pages.indexOf(p) + (f < i ? 1 : 0), 0, ...ms);
      dragPgs = [];
      renderSide();
      renderMain();
    };
    grid.appendChild(d);
  });
  if (isSameTab) sb.scrollTop = prevScroll;
  followThumb(false);
}
// Pages panel: follows the current page. It only scrolls if the page's thumbnail is out of view (center=true: leaves it centred)
function followThumb(center) {
  if (tab != 'th') return;
  const sb = $('#sbody'),
    t = sb.querySelectorAll('.th')[cur];
  if (!t) return;
  const sr = sb.getBoundingClientRect(),
    tr = t.getBoundingClientRect();
  if (!sr.height) return;
  const w = sb.querySelector('.sbw'),
    top = sr.top + (w ? w.offsetHeight - 8 : 0);
  if (center) sb.scrollTop += tr.top + tr.height / 2 - (top + (sr.bottom - top) / 2);
  else if (tr.top < top) sb.scrollTop -= top - tr.top + 6;
  else if (tr.bottom > sr.bottom) sb.scrollTop += tr.bottom - sr.bottom + 6;
}
// “Two pages”: only one pair (1-2, 3-4…) is visible at a time; the other pages are hidden
let shownPair = -1;
function showPair() {
  if (!pages.length) return;
  const v = $('#view'),
    s = cur - (cur % 2);
  shownPair = twoUp ? s : -1;
  v.querySelectorAll('.ph').forEach((x) => x.remove());
  [...v.children].forEach((c, i) => {
    c.style.display = twoUp && i != s && i != s + 1 ? 'none' : '';
  });
  if (twoUp) {
    v.scrollTop = 0;
    const c = v.children[s];
    if (s + 1 >= pages.length && c) {
      const h = document.createElement('div');
      h.className = 'ph';
      h.style.width = c.style.width;
      v.appendChild(h);
    }
  }
}
// Puts height y (in PDF points) of page i in the first third of the viewer; never scrolls back up from where the page already is
function goToY(i, y) {
  const v = $('#view'),
    e = v.children[i];
  if (!e || !e._vp || e.style.display == 'none') return;
  const py = e._vp.convertToViewportPoint(0, y)[1],
    d = e.getBoundingClientRect().top + py - (v.getBoundingClientRect().top + v.clientHeight / 3);
  if (d > 0) v.scrollTop += d;
}
function goTo(i, y) {
  cur = i;
  updPg();
  const nf = twoUp && cur - (cur % 2) != shownPair;
  if (twoUp) {
    if (nf) setFit('p');
    $('#view').scrollTop = 0;
  } else {
    const e = $('#view').children[i];
    if (e) e.scrollIntoView();
  }
  if (typeof y == 'number' && isFinite(y) && !nf) goToY(i, y);
  document.querySelectorAll('.th').forEach((t, k) => t.classList.toggle('cur', k == i));
  followThumb(false);
}

$('#view').addEventListener('scroll', () => {
  if (twoUp) return;
  const v = $('#view'),
    t = v.getBoundingClientRect().top + v.clientHeight / 3;
  let k = 0;
  [...v.children].forEach((c, i) => {
    if (c.getBoundingClientRect().top <= t) k = i;
  });
  if (twoUp) {
    k -= k % 2;
    if (cur === k + 1) k = cur;
  }
  if (k != cur) {
    cur = k;
    updPg();
    document.querySelectorAll('.th').forEach((x, j) => x.classList.toggle('cur', j == k));
    followThumb(false);
    const a = $('#addbm');
    if (a) a.title = _t('Add bookmark');
  }
});

async function renderMain() {
  updPg();
  const v = $('#view'),
    s = cur - (cur % 2);
  io.disconnect();
  v.innerHTML = '';
  for (let i = 0; i < pages.length; i++) {
    const p = pages[i],
      pg = await docs[p.doc].pdf.getPage(p.idx + 1),
      vp = pg.getViewport({ scale, rotation: (pg.rotate + (p.rot || 0)) % 360 });
    const el = document.createElement('div');
    el.className = 'page';
    el.style.width = vp.width + 'px';
    el.style.height = vp.height + 'px';
    el._p = p;
    el._pg = pg;
    el._vp = vp;
    el.dataset.i = i;
    if (twoUp && (i < s || i > s + 1)) el.style.display = 'none';
    v.appendChild(el);
    io.observe(el);
  }
  showPair();
}
// Reads a page's annotations from the PDF (once per page)
function loadAnnots(p) {
  if (p.loaded) return Promise.resolve();
  return (
    p.annP ||
    (p.annP = (async () => {
      const pdf = docs[p.doc].pdf,
        pg = await pdf.getPage(p.idx + 1),
        raw = await pg.getAnnotations();
      p.widgets = raw.filter(
        (a) => a.subtype === 'Widget' && a.rect && a.fieldType && !((a.annotationFlags || 0) & 34),
      );
      raw.forEach((a) => {
        const author = a.titleObj ? a.titleObj.str : a.title || '';
        const isM = author === 'Penfold';
        if (
          isM ||
          ['Text', 'FreeText', 'Highlight', 'Underline', 'StrikeOut', 'Square', 'Circle', 'Line'].includes(a.subtype)
        ) {
          let col =
            a.color && a.color.length === 3
              ? '#' +
                Array.from(a.color)
                  .map((v) => v.toString(16).padStart(2, '0'))
                  .join('')
              : null;
          if (!isM) {
            if (!col || col === '#ffffff') col = '#c64600';
          } else {
            col = col || '#f9f06b';
          }
          const txt = (a.contentsObj ? a.contentsObj.str : a.contents) || '';
          const ro = !isM;
          if (a.subtype === 'Text')
            p.annots.push({
              type: 'note',
              color: col,
              text: txt,
              x: (a.rect[0] + a.rect[2]) / 2,
              y: (a.rect[1] + a.rect[3]) / 2,
              ro,
              author,
            });
          else if (a.subtype === 'FreeText')
            p.annots.push({
              type: 'ft',
              color: col,
              text: txt,
              x: Math.min(a.rect[0], a.rect[2]),
              y: Math.max(a.rect[1], a.rect[3]),
              w: Math.abs(a.rect[2] - a.rect[0]),
              ro,
              author,
            });
          else if (a.subtype === 'Highlight' || a.subtype === 'Underline' || a.subtype === 'StrikeOut') {
            const quads = [];
            if (a.quadPoints) {
              const qp = a.quadPoints;
              if (typeof qp[0] === 'number') {
                for (let i = 0; i < qp.length; i += 8) quads.push(Array.from(qp.slice(i, i + 8)));
              } else
                qp.forEach((q) => {
                  if (Array.isArray(q) && q.length === 8) quads.push(q);
                  else if (q.length === 4) quads.push([q[0].x, q[0].y, q[1].x, q[1].y, q[2].x, q[2].y, q[3].x, q[3].y]);
                });
            } else if (a.rect) {
              quads.push([a.rect[0], a.rect[3], a.rect[2], a.rect[3], a.rect[0], a.rect[1], a.rect[2], a.rect[1]]);
            }
            if (quads.length)
              p.annots.push({
                type: a.subtype === 'Highlight' ? 'hl' : a.subtype === 'Underline' ? 'ul' : 'so',
                color: col,
                quads,
                txt,
                ro,
                author,
              });
          } else if (a.subtype === 'Square' || a.subtype === 'Circle') {
            p.annots.push({
              type: a.subtype === 'Square' ? 'sq' : 'ci',
              color: col,
              x: Math.min(a.rect[0], a.rect[2]),
              y: Math.max(a.rect[1], a.rect[3]),
              x2: Math.max(a.rect[0], a.rect[2]),
              y2: Math.min(a.rect[1], a.rect[3]),
              ro,
              author,
            });
          } else if (a.subtype === 'Line') {
            const lc = a.lineCoordinates || [a.rect[0], a.rect[1], a.rect[2], a.rect[3]];
            p.annots.push({ type: 'ar', color: col, x: lc[0], y: lc[1], x2: lc[2], y2: lc[3], ro, author });
          }
        } else if (a.subtype === 'Link') {
          const dest = a.dest || (a.action && a.action.dest);
          if (dest || a.url) {
            p.annots.push({
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
      markPageSaved(p);
      p.loaded = true;
    })().catch((e) => {
      p.annP = null;
      throw e;
    }))
  );
}
// Loads the annotations of every page when a PDF is opened or added, so the index is complete from the start
let annBusy = 0;
async function loadAllAnnots() {
  annBusy++;
  if (tab == 'an') renderSide();
  try {
    for (const p of pages.slice()) {
      if (pages.includes(p)) await loadAnnots(p);
    }
  } catch (e) {}
  annBusy--;
  if (tab == 'an') renderSide();
}
// ---- Forms: layer of fillable fields over the page (phase 2). Values are kept in docs[di].fv (full field name → value); they are written to the PDF on save (applyForm).
function fvInit(a) {
  const t = a.fieldType,
    v = a.fieldValue;
  if (t == 'Btn') return a.radioButton ? (v == null || v === 'Off' ? '' : String(v)) : !!(v && v !== 'Off' && v !== '');
  if (t == 'Ch') return Array.isArray(v) ? v.map(String) : v == null || v === '' ? [] : [String(v)];
  return v == null ? '' : Array.isArray(v) ? v.join('\n') : String(v);
}
function formLayer(el) {
  const p = el._p,
    vp = el._vp,
    ws = p.widgets;
  if (!ws || !ws.length) return;
  const doc = docs[p.doc];
  if (!doc) return;
  const fv = doc.fv || (doc.fv = {});
  const lay = document.createElement('div');
  lay.className = 'fl';
  const sync = (name, val, src) => {
    lay.parentNode &&
      $('#view')
        .querySelectorAll('.fl [data-fn]')
        .forEach((x) => {
          if (x === src || x.dataset.fn !== name || x._doc !== p.doc) return;
          if (x.type == 'checkbox') x.checked = !!val;
          else if (x.type == 'radio') x.checked = x.value === val;
          else if (x.tagName == 'SELECT') [...x.options].forEach((o) => (o.selected = val.includes(o.value)));
          else x.value = val;
        });
  };
  const set = (a, val, src) => {
    if (!doc.fvDirty) doc.fvDirty = new Set();
    // Back to the value it has in the PDF: the field counts as untouched again (and is left as it is on save)
    if (JSON.stringify(val) === JSON.stringify(fvInit(a))) {
      delete fv[a.fieldName];
      doc.fvDirty.delete(a.fieldName);
    } else {
      fv[a.fieldName] = val;
      doc.fvDirty.add(a.fieldName);
    }
    sync(a.fieldName, val, src);
  };
  ws.forEach((a) => {
    const t = a.fieldType;
    if (t != 'Tx' && t != 'Btn' && t != 'Ch') return;
    if (t == 'Btn' && a.pushButton) return;
    const r = vp.convertToViewportRectangle(a.rect),
      l = Math.min(r[0], r[2]),
      tp = Math.min(r[1], r[3]),
      w = Math.abs(r[2] - r[0]),
      h = Math.abs(r[3] - r[1]);
    if (w < 2 || h < 2) return;
    const name = a.fieldName || '',
      has = Object.prototype.hasOwnProperty.call(fv, name),
      cur = has ? fv[name] : fvInit(a);
    let e;
    if (t == 'Tx') {
      const ml = !!a.multiLine,
        pw = ((a.fieldFlags || 0) & 0x2000) != 0;
      e = document.createElement(ml ? 'textarea' : 'input');
      if (!ml) e.type = pw ? 'password' : 'text';
      e.value = Array.isArray(cur) ? cur.join('\n') : String(cur);
      if (a.maxLen) e.maxLength = a.maxLen;
      const da = a.defaultAppearanceData,
        fs =
          da && da.fontSize > 0
            ? da.fontSize * vp.scale
            : ml
              ? 12 * vp.scale
              : Math.max(8, Math.min(h * 0.66, 16 * vp.scale));
      e.style.fontSize = fs + 'px';
      e.style.textAlign = ['left', 'center', 'right'][a.textAlignment || 0] || 'left';
      e.oninput = () => set(a, e.value, e);
    } else if (t == 'Btn' && a.checkBox) {
      e = document.createElement('input');
      e.type = 'checkbox';
      e.checked = !!cur;
      e.onchange = () => set(a, e.checked, e);
    } else if (t == 'Btn') {
      e = document.createElement('input');
      e.type = 'radio';
      e.name = p.doc + '|' + name;
      e.value = String(a.buttonValue);
      e.checked = cur === e.value;
      e.onchange = () => {
        if (e.checked) set(a, e.value, e);
      };
    } else {
      e = document.createElement('select');
      const multi = !!a.multiSelect;
      if (multi) e.multiple = true;
      else if (!a.combo) e.size = Math.max(2, Math.min(8, (a.options || []).length));
      const sel = Array.isArray(cur) ? cur : [];
      if (a.combo && !sel.length) {
        const o = document.createElement('option');
        o.value = '';
        o.textContent = '';
        e.appendChild(o);
      }
      (a.options || []).forEach((op) => {
        const o = document.createElement('option');
        o.value = String(op.exportValue);
        o.textContent = op.displayValue != null ? op.displayValue : op.exportValue;
        o.selected = sel.includes(o.value);
        e.appendChild(o);
      });
      e.style.fontSize = Math.max(8, Math.min(h * 0.66, 14 * vp.scale)) + 'px';
      e.onchange = () => set(a, [...e.selectedOptions].map((o) => o.value).filter(Boolean), e);
    }
    if (a.readOnly) {
      e.disabled = true;
    }
    e.dataset.fn = name;
    e._doc = p.doc;
    e.title = a.alternativeText || '';
    e.style.left = l + 'px';
    e.style.top = tp + 'px';
    e.style.width = w + 'px';
    e.style.height = h + 'px';
    lay.appendChild(e);
  });
  if (lay.children.length) el.appendChild(lay);
}
async function paint(el) {
  const { _pg: pg, _vp: vp } = el,
    c = document.createElement('canvas'),
    r = Math.max(2, devicePixelRatio || 1);
  c.width = vp.width * r;
  c.height = vp.height * r;
  c.style.width = vp.width + 'px';
  c.style.height = vp.height + 'px';
  el.appendChild(c);
  await pg.render({
    canvasContext: c.getContext('2d'),
    viewport: vp,
    transform: [r, 0, 0, r, 0, 0],
    annotationMode: pdfjsLib.AnnotationMode.DISABLE,
  }).promise;
  const tl = document.createElement('div');
  tl.className = 'textLayer';
  tl.style.setProperty('--scale-factor', vp.scale);
  el.appendChild(tl);
  pdfjsLib.renderTextLayer({ textContentSource: pg.streamTextContent(), container: tl, viewport: vp, textDivs: [] });
  const ov = document.createElement('div');
  ov.className = 'ov';
  el.appendChild(ov);
  el._ov = ov;
  if (!el._p.loaded) {
    await loadAnnots(el._p);
    if (tab == 'an') renderSide();
  }
  draw(el);
  markHits(el);
  formLayer(el);
  el.onclick = (e) => {
    if (e.target.closest('.an') || tool != 'note') return;
    const b = el.getBoundingClientRect(),
      x = e.clientX - b.left,
      y = e.clientY - b.top;
    textDialog(_t('Comment'), '', (t) => {
      const [px, py] = vp.convertToPdfPoint(x, y);
      el._p.annots.push({ type: 'note', color, text: t, x: px, y: py });
      draw(el);
      if (tab == 'an') renderSide();
    });
  };
  el.onmousedown = (e) => {
    if (!['ft', 'sq', 'ci', 'ar'].includes(tool) || e.button !== 0 || e.target.closest('.an')) return;
    e.preventDefault();
    const b = el.getBoundingClientRect(),
      x0 = e.clientX - b.left,
      y0 = e.clientY - b.top,
      g = document.createElement('div');
    let x1 = x0,
      y1 = y0;
    if (tool == 'ft') {
      g.style.cssText =
        'position:absolute;pointer-events:none;z-index:6;height:26px;display:none;border:1.5px dashed ' + deep(color);
    } else if (tool == 'sq' || tool == 'ci') {
      g.style.cssText =
        'position:absolute;pointer-events:none;z-index:6;display:none;border:' +
        SW +
        'px solid ' +
        deep(color) +
        (tool == 'ci' ? ';border-radius:50%' : '');
    } else if (tool == 'ar') {
      g.style.cssText = 'position:absolute;pointer-events:none;z-index:6;display:none;overflow:visible';
      g.innerHTML = `<svg style="position:absolute;inset:0;width:100%;height:100%;overflow:visible" stroke="${deep(color)}" stroke-width="${SW}" fill="none" stroke-linecap="round" stroke-linejoin="round"><path class="P" d=""/></svg>`;
    }
    el.appendChild(g);
    const mm = (ev) => {
      x1 = Math.max(0, Math.min(b.width, ev.clientX - b.left));
      y1 = Math.max(0, Math.min(b.height, ev.clientY - b.top));
      const w = Math.abs(x1 - x0),
        h = Math.abs(y1 - y0);
      if (tool == 'ft') {
        g.style.display = w > 8 ? 'block' : 'none';
        g.style.left = Math.min(x0, x1) + 'px';
        g.style.top = y0 + 'px';
        g.style.width = w + 'px';
      } else if (tool == 'sq' || tool == 'ci') {
        g.style.display = w > 4 || h > 4 ? 'block' : 'none';
        g.style.left = Math.min(x0, x1) + 'px';
        g.style.top = Math.min(y0, y1) + 'px';
        g.style.width = w + 'px';
        g.style.height = h + 'px';
      } else if (tool == 'ar') {
        g.style.display = w > 4 || h > 4 ? 'block' : 'none';
        g.style.left = Math.min(x0, x1) + 'px';
        g.style.top = Math.min(y0, y1) + 'px';
        g.style.width = Math.max(1, w) + 'px';
        g.style.height = Math.max(1, h) + 'px';
        if (g.querySelector('.P')) {
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
          g.querySelector('.P').setAttribute(
            'd',
            `M${px1} ${py1} L${px2} ${py2} M${p1x} ${p1y} L${px2} ${py2} L${p2x} ${p2y}`,
          );
        }
      }
    };
    const mu = () => {
      document.removeEventListener('mousemove', mm);
      document.removeEventListener('mouseup', mu);
      g.remove();
      const w = Math.abs(x1 - x0),
        h = Math.abs(y1 - y0);
      if (tool == 'ft') {
        const wp = w > 8 ? Math.max(40, w / vp.scale) : FT.w;
        let l = w > 8 ? Math.min(x0, x1) : x0;
        l = Math.max(0, Math.min(l, b.width - wp * vp.scale));
        textDialog(_t('Text box'), '', (t) => {
          const [px, py] = vp.convertToPdfPoint(l, y0);
          el._p.annots.push({ type: 'ft', color: deep(color), text: t, x: px, y: py, w: wp });
          draw(el);
          if (tab == 'an') renderSide();
        });
      } else if (tool == 'sq' || tool == 'ci' || tool == 'ar') {
        if (w > 4 || h > 4) {
          const [px1, py1] = vp.convertToPdfPoint(x0, y0);
          const [px2, py2] = vp.convertToPdfPoint(x1, y1);
          el._p.annots.push({ type: tool, color: deep(color), x: px1, y: py1, x2: px2, y2: py2 });
          draw(el);
          if (tab == 'an') renderSide();
        }
      }
    };
    document.addEventListener('mousemove', mm);
    document.addEventListener('mouseup', mu);
  };
}
function draw(el) {
  const ov = el._ov,
    vp = el._vp;
  ov.innerHTML = '';
  el._p.annots.forEach((a, k) => {
    const mk = (css, cls) => {
      const d = document.createElement('div');
      d.className = 'an ' + cls;
      Object.assign(d.style, css);
      if (cls !== 'link' && !a.ro)
        d.oncontextmenu = async (e) => {
          e.preventDefault();
          if (await confirmDialog(_t('Delete annotation'), _t('Delete this annotation?'), _t('Delete'))) {
            el._p.annots.splice(k, 1);
            draw(el);
            if (tab == 'an') renderSide();
          }
        };
      ov.appendChild(d);
      return d;
    };
    if (a.quads)
      a.quads.forEach((q) => {
        const xs = [],
          ys = [];
        for (let i = 0; i < 8; i += 2) {
          const [x, y] = vp.convertToViewportPoint(q[i], q[i + 1]);
          xs.push(x);
          ys.push(y);
        }
        const l = Math.min(...xs),
          t = Math.min(...ys),
          w = Math.max(...xs) - l,
          h = Math.max(...ys) - t;
        mk(
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
        ov.lastChild.style.pointerEvents = 'auto';
      });
    else if (a.type == 'link') {
      const [x, y] = vp.convertToViewportPoint(a.x, a.y),
        [x2, y2] = vp.convertToViewportPoint(a.x + a.w, a.y - a.h);
      const d = mk(
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
              const ti = pages.findIndex((p) => p.doc == el._p.doc && p.idx == n);
              if (ti >= 0) goTo(ti, ddY(ddFrom(d)));
            }
          } catch (e) {}
        }
      };
    } else if (a.type == 'sq' || a.type == 'ci' || a.type == 'ar') {
      const [vx1, vy1] = vp.convertToViewportPoint(a.x, a.y);
      const [vx2, vy2] = vp.convertToViewportPoint(a.x2, a.y2);
      const vl = Math.min(vx1, vx2),
        vt = Math.min(vy1, vy2);
      const vw = Math.max(1, Math.abs(vx2 - vx1)),
        vh = Math.max(1, Math.abs(vy2 - vy1));
      const sSW = SW * vp.scale;
      const d = mk(
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
        const L = 12 * vp.scale;
        const p1x = px2 - L * Math.cos(angle - Math.PI / 6),
          p1y = py2 - L * Math.sin(angle - Math.PI / 6);
        const p2x = px2 - L * Math.cos(angle + Math.PI / 6),
          p2y = py2 - L * Math.sin(angle + Math.PI / 6);
        inner = `<path d="M${px1} ${py1} L${px2} ${py2} M${p1x} ${p1y} L${px2} ${py2} L${p2x} ${p2y}" style="pointer-events:visibleStroke"/>`;
      } else if (a.type == 'sq') {
        inner = `<rect x="${sSW / 2}" y="${sSW / 2}" width="${Math.max(0, vw - sSW)}" height="${Math.max(0, vh - sSW)}" style="pointer-events:visibleStroke"/>`;
      } else if (a.type == 'ci') {
        inner = `<ellipse cx="${vw / 2}" cy="${vh / 2}" rx="${Math.max(0, (vw - sSW) / 2)}" ry="${Math.max(0, (vh - sSW) / 2)}" style="pointer-events:visibleStroke"/>`;
      }
      d.innerHTML = `<svg style="position:absolute;inset:0;width:100%;height:100%;overflow:visible" stroke="${a.color}" stroke-width="${sSW}" fill="none" stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`;
    } else {
      const [x, y] = vp.convertToViewportPoint(a.x, a.y);
      const d = mk({ left: x + 'px', top: y + 'px' }, a.type == 'note' ? 'note' : 'ft');
      if (a.type == 'note') {
        d.dataset.text = a.text;
        d.innerHTML = noteSvg(a.color);
      } else {
        const s = vp.scale,
          c = deep(a.color);
        d.title = a.text;
        d.textContent = a.text;
        Object.assign(d.style, {
          width: (a.w || FT.w) * s + 'px',
          boxSizing: 'border-box',
          font: FT.fs * s + 'px/' + FT.lh + ' Helvetica,Arial,sans-serif',
          padding: FT.pad * s + 'px',
          border: Math.max(1, FT.bw * s) + 'px solid ' + c,
          background: tint(c, 0.14),
          color: a.ro ? c : 'var(--ink)',
        });
      }
    }
  });
  ov.style.pointerEvents = 'none';
  ov.querySelectorAll('.an.note,.an.ft,.an.link').forEach((n) => (n.style.pointerEvents = 'auto'));
}
document.addEventListener('mouseup', () => {
  if (tool != 'hl' && tool != 'ul' && tool != 'so') return;
  const s = getSelection();
  if (!s.rangeCount || s.isCollapsed) return;
  const r = s.getRangeAt(0),
    n = r.commonAncestorContainer,
    el = (n.nodeType == 1 ? n : n.parentElement).closest('.page');
  if (!el) return;
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
      type: tool,
      color: tool == 'ul' || tool == 'so' ? deep(color) : color,
      quads,
      txt: s.toString().replace(/\s+/g, ' ').trim(),
    });
    draw(el);
    if (tab == 'an') renderSide();
  }
  s.removeAllRanges();
});

// ---- Saving ----
const hex = (h) => [1, 3, 5].map((i) => parseInt(h.substr(i, 2), 16) / 255);
// Own drawing (appearance stream) for highlights, underlines and strikethroughs: that way every viewer paints the same as Penfold.
// Highlight: fill with Multiply blending and HL_A opacity (as on screen). Underline / strikethrough: a line SW points wide.
const HL_A = 0.75;
function quadAP(ctx, a, r) {
  const n = (v) => +v.toFixed(3),
    hl = a.type == 'hl',
    c = hex(a.color).map(n).join(' ');
  let s = hl ? '/GS0 gs ' + c + ' rg\n' : c + ' RG ' + SW + ' w\n';
  a.quads.forEach((q) => {
    if (hl)
      s +=
        n(q[0]) +
        ' ' +
        n(q[1]) +
        ' m ' +
        n(q[2]) +
        ' ' +
        n(q[3]) +
        ' l ' +
        n(q[6]) +
        ' ' +
        n(q[7]) +
        ' l ' +
        n(q[4]) +
        ' ' +
        n(q[5]) +
        ' l h f\n';
    else if (a.type == 'ul') {
      const dx = q[0] - q[4],
        dy = q[1] - q[5],
        L = Math.hypot(dx, dy) || 1,
        ox = ((dx / L) * SW) / 2,
        oy = ((dy / L) * SW) / 2;
      s += n(q[4] + ox) + ' ' + n(q[5] + oy) + ' m ' + n(q[6] + ox) + ' ' + n(q[7] + oy) + ' l S\n';
    } else {
      const mx0 = (q[0] + q[4]) / 2,
        my0 = (q[1] + q[5]) / 2,
        mx1 = (q[2] + q[6]) / 2,
        my1 = (q[3] + q[7]) / 2;
      s += n(mx0) + ' ' + n(my0) + ' m ' + n(mx1) + ' ' + n(my1) + ' l S\n';
    }
  });
  const res = hl ? { ExtGState: { GS0: { Type: 'ExtGState', BM: 'Multiply', ca: HL_A, CA: HL_A } } } : {};
  return ctx.register(ctx.stream(s, { Type: 'XObject', Subtype: 'Form', FormType: 1, BBox: r, Resources: res }));
}
// Text box: splits the text into lines using Helvetica metrics (like pre-wrap + overflow-wrap on screen).
// Characters Helvetica does not have (emoji, arrows…) come out as “?” in the drawing; the /Contents text is stored in full.
function ftLines(font, text, w) {
  const ok = new Set(font.getCharacterSet()),
    max = w - 2 * (FT.bw + FT.pad),
    W = (t) => font.widthOfTextAtSize(t, FT.fs),
    lines = [];
  text
    .replace(/\r\n?/g, '\n')
    .replace(/\t/g, ' ')
    .replace(/\n$/, '')
    .split('\n')
    .forEach((par) => {
      let cur = '';
      for (const t of par.match(/ +|[^ ]+/g) || []) {
        const tt = Array.from(t, (ch) => (ok.has(ch.codePointAt(0)) ? ch : '?')).join('');
        if (tt[0] == ' ' || W(cur + tt) <= max) {
          cur += tt;
          continue;
        }
        if (cur.trim()) {
          lines.push(cur.replace(/ +$/, ''));
          cur = '';
        }
        let part = '';
        for (const ch of tt) {
          if (part && W(part + ch) > max) {
            lines.push(part);
            part = '';
          }
          part += ch;
        }
        cur = part;
      }
      lines.push(cur);
    });
  return lines;
}
// Own drawing of the text box: background, border and text already split into lines, with the same measurements as on screen.
function ftAP(ctx, font, lines, w, h, c) {
  const { bw, pad, fs, lh } = FT,
    n = (v) => +v.toFixed(3),
    lineH = fs * lh,
    base = (lineH - fs * 1.117) / 2 + fs * 0.905;
  let s =
    hex(tint(c, 0.14)).map(n).join(' ') +
    ' rg\n0 0 ' +
    n(w) +
    ' ' +
    n(h) +
    ' re f\n' +
    hex(c).map(n).join(' ') +
    ' RG ' +
    bw +
    ' w\n' +
    n(bw / 2) +
    ' ' +
    n(bw / 2) +
    ' ' +
    n(w - bw) +
    ' ' +
    n(h - bw) +
    ' re S\nBT /Helv ' +
    fs +
    ' Tf 0 g\n';
  lines.forEach((ln, i) => {
    if (ln.trim())
      s +=
        '1 0 0 1 ' +
        n(bw + pad) +
        ' ' +
        n(h - bw - pad - base - i * lineH) +
        ' Tm ' +
        font.encodeText(ln).toString() +
        ' Tj\n';
  });
  s += 'ET';
  return ctx.register(
    ctx.stream(s, {
      Type: 'XObject',
      Subtype: 'Form',
      FormType: 1,
      BBox: [0, 0, w, h],
      Resources: { Font: { Helv: font.ref } },
    }),
  );
}
// Own drawing of rectangles, circles and arrows, stroked SW points wide.
function shapeAP(ctx, a, r) {
  const n = (v) => +v.toFixed(3),
    c = hex(a.color).map(n).join(' ');
  let s = c + ' RG ' + SW + ' w\n';
  const [minX, minY, maxX, maxY] = r;
  const w = Math.max(1, maxX - minX),
    h = Math.max(1, maxY - minY);
  if (a.type == 'sq') {
    s += n(SW / 2) + ' ' + n(SW / 2) + ' ' + n(w - SW) + ' ' + n(h - SW) + ' re S\n';
  } else if (a.type == 'ci') {
    const kappa = 0.5522848;
    const rx = (w - SW) / 2,
      ry = (h - SW) / 2;
    const cx = w / 2,
      cy = h / 2;
    s += n(cx) + ' ' + n(cy + ry) + ' m\n';
    s +=
      n(cx + rx * kappa) +
      ' ' +
      n(cy + ry) +
      ' ' +
      n(cx + rx) +
      ' ' +
      n(cy + ry * kappa) +
      ' ' +
      n(cx + rx) +
      ' ' +
      n(cy) +
      ' c\n';
    s +=
      n(cx + rx) +
      ' ' +
      n(cy - ry * kappa) +
      ' ' +
      n(cx + rx * kappa) +
      ' ' +
      n(cy - ry) +
      ' ' +
      n(cx) +
      ' ' +
      n(cy - ry) +
      ' c\n';
    s +=
      n(cx - rx * kappa) +
      ' ' +
      n(cy - ry) +
      ' ' +
      n(cx - rx) +
      ' ' +
      n(cy - ry * kappa) +
      ' ' +
      n(cx - rx) +
      ' ' +
      n(cy) +
      ' c\n';
    s +=
      n(cx - rx) +
      ' ' +
      n(cy + ry * kappa) +
      ' ' +
      n(cx - rx * kappa) +
      ' ' +
      n(cy + ry) +
      ' ' +
      n(cx) +
      ' ' +
      n(cy + ry) +
      ' c S\n';
  } else if (a.type == 'ar') {
    const x1 = a.x - minX,
      y1 = a.y - minY;
    const x2 = a.x2 - minX,
      y2 = a.y2 - minY;
    s += n(x1) + ' ' + n(y1) + ' m ' + n(x2) + ' ' + n(y2) + ' l S\n';
    const dx = x2 - x1,
      dy = y2 - y1;
    const angle = Math.atan2(dy, dx);
    const L = 10;
    const p1x = x2 - L * Math.cos(angle - Math.PI / 6),
      p1y = y2 - L * Math.sin(angle - Math.PI / 6);
    const p2x = x2 - L * Math.cos(angle + Math.PI / 6),
      p2y = y2 - L * Math.sin(angle + Math.PI / 6);
    s += '1 J 1 j\n';
    s += n(p1x) + ' ' + n(p1y) + ' m ' + n(x2) + ' ' + n(y2) + ' l ' + n(p2x) + ' ' + n(p2y) + ' l S\n';
  }
  return ctx.register(
    ctx.stream(s, { Type: 'XObject', Subtype: 'Form', FormType: 1, BBox: [0, 0, w, h], Resources: {} }),
  );
}
// Comment icon: the same drawing as on screen (Lucide message-square-text, black outline and fill in the annotation's colour), in a 20 × 20 point box.
function noteAP(ctx, a) {
  const n = (v) => +v.toFixed(3),
    k = 1.1046,
    s =
      'q 1 0 0 -1 -2 22 cm\n' +
      hex(a.color).map(n).join(' ') +
      ' rg 0 0 0 RG ' +
      NOTE_SW +
      ' w 1 J 1 j\n' +
      '21 15 m 21 ' +
      n(15 + k) +
      ' ' +
      n(19 + k) +
      ' 17 19 17 c 7 17 l 3 21 l 3 5 l 3 ' +
      n(5 - k) +
      ' ' +
      n(5 - k) +
      ' 3 5 3 c 19 3 l ' +
      n(19 + k) +
      ' 3 21 ' +
      n(5 - k) +
      ' 21 5 c h B\n' +
      '13 8 m 7 8 l S 17 12 m 7 12 l S\nQ';
  return ctx.register(
    ctx.stream(s, { Type: 'XObject', Subtype: 'Form', FormType: 1, BBox: [0, 0, 20, 20], Resources: {} }),
  );
}
// Forms (AcroForm): copyPages does not copy the catalogue's /AcroForm, so the fields were left loose. It is rebuilt with the fields
// whose widgets are on the final pages (removes the widgets of deleted pages, fixes /P and avoids duplicate names when merging).
function carryForm(out, src, pgs) {
  const { PDFName, PDFDict, PDFArray, PDFRef, PDFBool, PDFHexString, PDFObjectCopier } = PDFLib,
    ctx = out.context,
    N = (n) => PDFName.of(n);
  const pagesOut = out.getPages(),
    pageTags = new Set(pagesOut.map((q) => q.ref.tag)),
    roots = new Map(),
    onPage = new Set(),
    orphans = new Map(),
    dead = [];
  pagesOut.forEach((pg, pi) => {
    const arr = pg.node.lookupMaybe(N('Annots'), PDFArray);
    if (!arr) return;
    for (let i = 0; i < arr.size(); i++) {
      const ref = arr.get(i);
      if (!(ref instanceof PDFRef)) continue;
      const d = ctx.lookupMaybe(ref, PDFDict);
      if (!d) continue;
      const op = d.get(N('P'));
      if (op instanceof PDFRef && op.tag !== pg.ref.tag) {
        if (!pageTags.has(op.tag)) orphans.set(op.tag, op);
        d.set(N('P'), pg.ref);
      }
      if (d.get(N('Subtype')) !== N('Widget')) continue;
      onPage.add(ref.tag);
      let r = ref,
        f = d;
      for (let g = 0; g < 50; g++) {
        const pr = f.get(N('Parent'));
        if (!(pr instanceof PDFRef)) break;
        const pd = ctx.lookupMaybe(pr, PDFDict);
        if (!pd) break;
        r = pr;
        f = pd;
      }
      if (!roots.has(r.tag)) roots.set(r.tag, { ref: r, doc: pgs[pi] ? pgs[pi].doc : 0 });
    }
  });
  // A field is kept if any of its widgets is on the final pages; widgets of deleted pages are removed from /Kids
  const keep = (ref, dep) => {
    const d = ctx.lookupMaybe(ref, PDFDict);
    if (!d || dep > 40) return false;
    const kids = d.lookupMaybe(N('Kids'), PDFArray);
    if (!kids) return onPage.has(ref.tag);
    const ok = [],
      bad = [];
    for (let i = 0; i < kids.size(); i++) {
      const k = kids.get(i);
      if (!(k instanceof PDFRef)) return true;
      if (keep(k, dep + 1)) ok.push(k);
      else bad.push(k);
    }
    if (bad.length) {
      d.set(N('Kids'), ctx.obj(ok));
      bad.forEach((b) => dead.push(b));
    }
    return ok.length > 0;
  };
  const fields = [],
    fdocs = [],
    names = new Map(),
    ren = new Map();
  roots.forEach(({ ref, doc }) => {
    if (!keep(ref, 0)) return;
    const d = ctx.lookupMaybe(ref, PDFDict),
      t = d.get(N('T'));
    if (t && t.decodeText) {
      let nm = t.decodeText();
      const own = names.get(nm),
        orig = nm;
      if (own !== undefined && own !== doc) {
        let k = 2;
        while (names.has(nm + '_' + k)) k++;
        nm = nm + '_' + k;
        d.set(N('T'), PDFHexString.fromText(nm));
        ren.set(doc + '|' + orig, nm);
      }
      names.set(nm, doc);
    }
    fields.push(ref);
    fdocs.push(doc);
  });
  if (!fields.length) return null;
  const af = ctx.obj({ Fields: fields });
  for (const di of [...new Set(fdocs)]) {
    const sa = src[di] && src[di].catalog.lookupMaybe(N('AcroForm'), PDFDict);
    if (!sa) continue;
    if (!af.has(N('DA'))) {
      const v = sa.lookup(N('DA'));
      if (v) af.set(N('DA'), v);
    }
    if (!af.has(N('Q'))) {
      const v = sa.lookup(N('Q'));
      if (v) af.set(N('Q'), v);
    }
    if (sa.lookup(N('NeedAppearances')) === PDFBool.True) af.set(N('NeedAppearances'), PDFBool.True);
    const dr = sa.get(N('DR'));
    if (!dr) continue;
    const cp = PDFObjectCopier.for(src[di].context, ctx).copy(dr);
    if (!af.has(N('DR'))) {
      af.set(N('DR'), cp);
      continue;
    }
    const cur = ctx.lookupMaybe(af.get(N('DR')), PDFDict),
      cd = ctx.lookupMaybe(cp, PDFDict);
    if (cur && cd)
      cd.entries().forEach(([k, v]) => {
        if (!cur.has(k)) {
          cur.set(k, v);
          return;
        }
        const a = ctx.lookupMaybe(cur.get(k), PDFDict),
          b = ctx.lookupMaybe(v, PDFDict);
        if (a && b)
          b.entries().forEach(([kk, vv]) => {
            if (!a.has(kk)) a.set(kk, vv);
          });
      });
  }
  out.catalog.set(N('AcroForm'), ctx.register(af));
  // Clean-up: page copies that are no longer used (they used to be pointed at by /P) and widgets of deleted pages
  orphans.forEach((r) => {
    const o = ctx.lookupMaybe(r, PDFDict);
    if (o && o.get(N('Type')) === N('Page') && !pageTags.has(r.tag)) ctx.delete(r);
  });
  dead.forEach((r) => ctx.delete(r));
  return ren;
}
// Phase 3: writes the values filled in on screen (docs[di].fv) into the final PDF's fields, only the fields that were touched (fvDirty).
// It is still an editable form. Returns how many fields could not be written.
async function applyForm(out, ren, flat) {
  const { PDFTextField, PDFCheckBox, PDFRadioGroup, PDFDropdown, PDFOptionList, PDFHexString, PDFName, PDFBool } =
    PDFLib;
  if (!docs.some((d) => d && d.fvDirty && d.fvDirty.size) || !out.catalog.has(PDFName.of('AcroForm'))) return 0;
  const form = out.getForm(),
    font = await out.embedFont(PDFLib.StandardFonts.Helvetica);
  let bad = 0,
    needApp = false;
  const enc = (t) =>
    t.split(/\r\n|\r|\n/).every((l) => {
      try {
        font.encodeText(l);
        return true;
      } catch (e) {
        return false;
      }
    });
  const safe = (t) =>
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
          fin = (ren.get(di + '|' + root) || root) + name.slice(root.length),
          f = form.getFieldMaybe(fin);
        if (!f) return;
        const v = d.fv[name];
        if (f instanceof PDFTextField) {
          const tx = Array.isArray(v) ? v.join('\n') : String(v == null ? '' : v);
          if (enc(tx)) {
            f.setText(tx === '' ? undefined : tx);
            f.defaultUpdateAppearances(font);
          } else if (flat) {
            const sf = safe(tx);
            f.setText(sf === '' ? undefined : sf);
            f.defaultUpdateAppearances(font);
          } else {
            f.acroField.setValue(PDFHexString.fromText(tx));
            needApp = true;
          }
        } else if (f instanceof PDFCheckBox) {
          v ? f.check() : f.uncheck();
        }
        // Radio buttons: the value on screen is the button's state name; select() wants the option, which differs when the
        // group has /Opt (states "0", "1"… and options "small", "large"…), so the state is translated to its option
        else if (f instanceof PDFRadioGroup) {
          if (!v) f.clear();
          else {
            const s = String(v),
              op = f.getOptions(),
              k = f.acroField.getOnValues().findIndex((n) => n.decodeText() === s);
            f.select(k >= 0 && op[k] !== undefined ? op[k] : s);
          }
        } else if (f instanceof PDFDropdown || f instanceof PDFOptionList) {
          const vals = (Array.isArray(v) ? v : v ? [String(v)] : []).map((x) => PDFHexString.fromText(String(x)));
          if (flat) {
            const op = f.acroField.getOptions(),
              dp = (x) => {
                const o = op.find((q) => q.value.decodeText() === x);
                return o && o.display ? o.display.decodeText() : x;
              };
            f.acroField.setValues(vals.map((x) => PDFHexString.fromText(safe(dp(x.decodeText())))));
            f.markAsDirty();
            f.defaultUpdateAppearances(font);
          } else {
            f.acroField.setValues(vals);
            f.markAsDirty();
            if (
              f.acroField.getOptions().some((o) => o.display && o.display.decodeText() !== o.value.decodeText()) ||
              !vals.every((x) => enc(x.decodeText()))
            )
              needApp = true;
            else f.defaultUpdateAppearances(font);
          }
        }
      } catch (e) {
        bad++;
        console.warn('Form field not saved:', name, e);
      }
    });
  });
  if (needApp && !flat) form.acroForm.dict.set(PDFName.of('NeedAppearances'), PDFBool.True);
  return bad;
}
// Phase 4: flatten. Draws each field's appearance (its /AP) as fixed page content, following the standard's algorithm
// (ISO 32000-1, 12.5.5: the transformed appearance box is fitted to the field's /Rect), and removes the widgets and the /AcroForm.
function flattenForm(out) {
  const L = PDFLib,
    N = (n) => L.PDFName.of(n),
    ctx = out.context,
    form = out.getForm(),
    num = (a) => (a ? a.asArray().map((x) => x.asNumber()) : null);
  const pageOf = new Map();
  out.getPages().forEach((pg) => {
    const a = pg.node.lookupMaybe(N('Annots'), L.PDFArray);
    if (a)
      for (let i = 0; i < a.size(); i++) {
        const r = a.get(i);
        if (r instanceof L.PDFRef) pageOf.set(r.tag, pg);
      }
  });
  const apOf = (w) => {
    const apd = w.dict.lookupMaybe(N('AP'), L.PDFDict);
    if (!apd) return null;
    const n = apd.get(N('N')),
      o = n instanceof L.PDFRef ? ctx.lookup(n) : n;
    if (o instanceof L.PDFStream) return n instanceof L.PDFRef ? n : null;
    if (o instanceof L.PDFDict) {
      const as = w.dict.lookupMaybe(N('AS'), L.PDFName),
        r = as && o.get(as);
      if (r instanceof L.PDFRef && ctx.lookup(r) instanceof L.PDFStream) return r;
    }
    return null;
  };
  form
    .getFields()
    .slice()
    .forEach((f) => {
      f.acroField.getWidgets().forEach((w) => {
        const wr = ctx.getObjectRef(w.dict),
          pg = wr && pageOf.get(wr.tag);
        if (!pg) return;
        try {
          const fl = w.dict.lookupMaybe(N('F'), L.PDFNumber),
            ap = apOf(w);
          if (ap && !(fl && fl.asNumber() & 34)) {
            const st = ctx.lookup(ap),
              bb = num(st.dict.lookupMaybe(N('BBox'), L.PDFArray)),
              m = num(st.dict.lookupMaybe(N('Matrix'), L.PDFArray)) || [1, 0, 0, 1, 0, 0],
              rc = num(w.dict.lookupMaybe(N('Rect'), L.PDFArray));
            if (bb && rc && bb.length == 4 && rc.length == 4) {
              const xs = [],
                ys = [];
              [
                [bb[0], bb[1]],
                [bb[2], bb[1]],
                [bb[0], bb[3]],
                [bb[2], bb[3]],
              ].forEach(([x, y]) => {
                xs.push(m[0] * x + m[2] * y + m[4]);
                ys.push(m[1] * x + m[3] * y + m[5]);
              });
              const x0 = Math.min(...xs),
                x1 = Math.max(...xs),
                y0 = Math.min(...ys),
                y1 = Math.max(...ys),
                rx = Math.min(rc[0], rc[2]),
                ry = Math.min(rc[1], rc[3]),
                rw = Math.abs(rc[2] - rc[0]),
                rh = Math.abs(rc[3] - rc[1]);
              if (x1 > x0 && y1 > y0 && rw > 0 && rh > 0) {
                const sx = rw / (x1 - x0),
                  sy = rh / (y1 - y0),
                  key = pg.node.newXObject('FlatWidget', ap);
                pg.pushOperators(
                  L.pushGraphicsState(),
                  L.concatTransformationMatrix(sx, 0, 0, sy, rx - x0 * sx, ry - y0 * sy),
                  L.drawObject(key),
                  L.popGraphicsState(),
                );
              }
            }
          }
        } catch (e) {
          console.warn('Field not flattened:', e);
        }
        pg.node.removeAnnot(wr);
        ctx.delete(wr);
      });
      let par = f.acroField.dict.get(N('Parent')),
        g = 0;
      while (par instanceof L.PDFRef && g++ < 50) {
        const nx = ctx.lookupMaybe(par, L.PDFDict);
        ctx.delete(par);
        par = nx && nx.get(N('Parent'));
      }
      ctx.delete(f.ref);
    });
  out.catalog.delete(N('AcroForm'));
}
async function build(o = {}) {
  const { PDFDocument, PDFName, PDFString, PDFHexString, degrees } = PDFLib,
    out = await PDFDocument.create(),
    refs = new Map();
  const src = o.src || (await Promise.all(docs.map((d) => PDFDocument.load(d.bytes, { ignoreEncryption: true }))));
  // Safety net: pdf-lib cannot decrypt, so a protected PDF would come out broken (or not at all)
  if (src.some((s) => s && s.isEncrypted))
    throw new Error(
      _t('This PDF is protected against changes: Penfold cannot save it, print it or extract pages from it yet.'),
    );
  const pgs = o.pages || pages,
    noA = !!o.noAnnots;
  let hf = null;
  // One copyPages call per document: form fields shared between pages are copied only once
  const cps = new Map(),
    usedCp = new Set();
  for (let di = 0; di < src.length; di++) {
    const ix = [...new Set(pgs.filter((q) => q.doc == di).map((q) => q.idx))];
    if (!ix.length) continue;
    const arr = await out.copyPages(src[di], ix);
    ix.forEach((x, k) => cps.set(di + ':' + x, arr[k]));
  }
  for (const p of pgs) {
    const ck = p.doc + ':' + p.idx;
    let cp = cps.get(ck);
    if (!cp || usedCp.has(ck)) cp = (await out.copyPages(src[p.doc], [p.idx]))[0];
    usedCp.add(ck);
    out.addPage(cp);
    refs.set(p, cp.ref);
    if (p.rot) cp.setRotation(degrees((src[p.doc].getPage(p.idx).getRotation().angle + p.rot) % 360));
    const ctx = out.context;
    if (p.loaded || noA) {
      const aRef = cp.node.get(PDFName.of('Annots'));
      if (aRef) {
        const aObj = ctx.lookup(aRef);
        if (aObj && aObj.array) {
          const fil = aObj.array.filter((ref) => {
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
          cp.node.set(PDFName.of('Annots'), ctx.obj(fil));
        }
      }
    }
    for (const a of noA ? [] : o.types ? p.annots.filter((a) => o.types.has(a.type)) : p.annots) {
      if (a.type == 'link' || a.ro) continue;
      let d;
      const base = { Type: 'Annot', F: 4, C: hex(a.color), T: PDFString.of('Penfold') };
      if (a.type == 'note' || a.type == 'ft') base.Contents = PDFHexString.fromText(a.text || '');
      if (a.quads) {
        const all = a.quads.flat(),
          xs = all.filter((_, i) => i % 2 == 0),
          ys = all.filter((_, i) => i % 2);
        const rc = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
        d = ctx.obj({
          ...base,
          Subtype: a.type == 'hl' ? 'Highlight' : a.type == 'ul' ? 'Underline' : 'StrikeOut',
          Rect: rc,
          QuadPoints: all,
          CA: a.type == 'hl' ? HL_A : 1,
          AP: { N: quadAP(ctx, a, rc) },
        });
      } else if (a.type == 'sq' || a.type == 'ci' || a.type == 'ar') {
        let rc;
        if (a.type == 'ar') {
          rc = [Math.min(a.x, a.x2) - 15, Math.min(a.y, a.y2) - 15, Math.max(a.x, a.x2) + 15, Math.max(a.y, a.y2) + 15];
        } else {
          rc = [Math.min(a.x, a.x2), Math.min(a.y, a.y2), Math.max(a.x, a.x2), Math.max(a.y, a.y2)];
        }
        d = ctx.obj({
          ...base,
          Subtype: a.type == 'sq' ? 'Square' : a.type == 'ci' ? 'Circle' : 'Line',
          Rect: rc,
          C: hex(a.color),
          BS: { W: SW, S: 'S' },
          AP: { N: shapeAP(ctx, a, rc) },
        });
        if (a.type == 'ar') {
          d.set(PDFName.of('L'), ctx.obj([a.x, a.y, a.x2, a.y2]));
          d.set(PDFName.of('LE'), ctx.obj([PDFName.of('None'), PDFName.of('OpenArrow')]));
        }
      } else if (a.type == 'note')
        d = ctx.obj({
          ...base,
          Subtype: 'Text',
          Rect: [a.x - 10, a.y - 10, a.x + 10, a.y + 10],
          Name: 'Note',
          AP: { N: noteAP(ctx, a) },
        });
      else {
        const w = a.w || FT.w,
          c = deep(a.color),
          font = hf || (hf = await out.embedFont(PDFLib.StandardFonts.Helvetica)),
          ls = ftLines(font, a.text, w),
          h = 2 * (FT.bw + FT.pad) + ls.length * FT.fs * FT.lh,
          z = (x) => String(x).padStart(2, '0'),
          t = new Date();
        d = ctx.obj({
          ...base,
          C: hex(c),
          IC: hex(tint(c, 0.14)),
          BS: { W: FT.bw, S: 'S' },
          Subtype: 'FreeText',
          Rect: [a.x, a.y - h, a.x + w, a.y],
          DA: PDFString.of('/Helv 11 Tf 0 0 0 rg'),
          Q: 0,
          M: PDFString.of(
            'D:' +
              t.getUTCFullYear() +
              z(t.getUTCMonth() + 1) +
              z(t.getUTCDate()) +
              z(t.getUTCHours()) +
              z(t.getUTCMinutes()) +
              z(t.getUTCSeconds()) +
              'Z',
          ),
          AP: { N: ftAP(ctx, font, ls, w, h, c) },
        });
      }
      Object.keys(d.dict ? d.dict : {});
      cp && out.getPage(out.getPageCount() - 1).node.addAnnot(ctx.register(d));
    }
  }
  let frm = null;
  try {
    frm = carryForm(out, src, pgs);
  } catch (e) {
    console.warn('Form not preserved:', e);
  }
  if (frm) {
    try {
      const bad = await applyForm(out, frm, !!o.flatten);
      if (bad) msg(_t('{n} form field(s) could not be saved.', { n: bad }));
    } catch (e) {
      console.warn('Form data not saved:', e);
      if (o.flatten) throw new Error(_t('Could not flatten the form: {m}', { m: e.message }));
      msg(_t('The form data could not be saved.'));
    }
    if (o.flatten) {
      try {
        flattenForm(out);
      } catch (e) {
        throw new Error(_t('Could not flatten the form: {m}', { m: e.message }));
      }
    }
  }
  const items = noA || o.noBms ? [] : prune(bms, pgs);
  if (items.length) {
    const ctx = out.context,
      root = ctx.nextRef(),
      cnt = (l) => l.reduce((n, i) => n + 1 + cnt(i.items), 0),
      vis = (l) => l.reduce((n, i) => n + 1 + (i.open === false ? 0 : vis(i.items)), 0);
    const wr = (list, par) => {
      const rs = list.map(() => ctx.nextRef());
      list.forEach((it, i) => {
        const o = {
          Title: PDFHexString.fromText(it.title),
          Parent: par,
          Dest: [refs.get(it.page), ...(ddOk(it.dd) ? [it.dd.n, ...it.dd.a] : ['Fit'])],
        };
        if (it.color) o.C = hex(it.color);
        const ff = (it.italic ? 1 : 0) | (it.bold ? 2 : 0);
        if (ff) o.F = ff;
        if (i > 0) o.Prev = rs[i - 1];
        if (i < list.length - 1) o.Next = rs[i + 1];
        if (it.items.length) {
          const k = wr(it.items, rs[i]);
          o.First = k[0];
          o.Last = k[k.length - 1];
          o.Count = it.open === false ? -cnt(it.items) : vis(it.items);
        }
        ctx.assign(rs[i], ctx.obj(o));
      });
      return rs;
    };
    const top = wr(items, root);
    ctx.assign(root, ctx.obj({ Type: 'Outlines', First: top[0], Last: top[top.length - 1], Count: vis(items) }));
    out.catalog.set(PDFName.of('Outlines'), root);
    out.catalog.set(PDFName.of('PageMode'), PDFName.of('UseOutlines'));
  }
  return out.save({ updateFieldAppearances: false });
}
async function save(h, flat) {
  const bytes = await build(flat ? { flatten: true } : {}),
    w = await h.createWritable();
  await w.write(bytes);
  await w.close();
  // A flattened copy is an export: the working document still has its changes unsaved
  if (!flat) markSaved();
  msg(flat ? _t('Saved ✔ (form flattened)') : _t('Saved ✔'));
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
  return new Promise((res) => {
    if (document.getElementById('dlg')) return res(null);
    const ov = document.createElement('div');
    ov.id = 'dlg';
    ov.innerHTML =
      '<div class="box"><h3>Save As…</h3><label><input type="checkbox" id="fFlat"> Flatten the form</label><div class="hint" style="margin-top:-6px;padding-left:26px">The data becomes part of the page and the fields can no longer be edited in the saved file.</div><div class="row r"><button id="fCancel">Cancel</button><button id="fOk" class="on">Save</button></div></div>';
    i18nApply(ov);
    const fin = (v) => {
        ov.remove();
        document.removeEventListener('keydown', key);
        res(v);
      },
      key = (e) => {
        if (e.key == 'Escape') fin(null);
        else if (e.key == 'Enter' && !document.getElementById('dlg2')) {
          e.preventDefault();
          fin(ov.querySelector('#fFlat').checked);
        }
      };
    ov.querySelector('#fCancel').onclick = () => fin(null);
    ov.querySelector('#fOk').onclick = () => fin(ov.querySelector('#fFlat').checked);
    document.addEventListener('keydown', key);
    document.body.appendChild(ov);
    ov.querySelector('#fOk').focus();
  });
}
$('#bSave').onclick = async () => {
  try {
    if (handle) {
      if (
        !(await confirmDialog(
          _t('Overwrite file'),
          _t('Do you want to overwrite “{name}”?', { name: fname }),
          _t('Overwrite'),
        ))
      )
        return;
      await save(handle);
    } else if (window.showSaveFilePicker) $('#bSaveAs').click();
    else {
      msg(_t('This browser cannot overwrite files: a copy is being downloaded.'));
      download();
    }
  } catch (e) {
    if (e.name != 'AbortError') msg('Error: ' + e.message);
  }
};
// “Save As…”: returns true if a file was written (false if cancelled)
async function saveAs() {
  let flat = false;
  if (hasForm()) {
    flat = await flattenDialog();
    if (flat === null) return false;
  }
  if (!window.showSaveFilePicker) {
    await download(flat);
    return true;
  }
  const h = await showSaveFilePicker({ suggestedName: fname, types: [{ accept: { 'application/pdf': ['.pdf'] } }] });
  await save(h, flat);
  // A flattened copy is an export: it does not become the working file (so that “Save” never overwrites it with the editable version)
  if (!flat) {
    handle = h;
    fname = h.name;
  }
  return true;
}
$('#bSaveAs').onclick = async () => {
  try {
    await saveAs();
  } catch (e) {
    if (e.name != 'AbortError') msg('Error: ' + e.message);
  }
};
async function download(flat) {
  const b = new Blob([await build(flat ? { flatten: true } : {})], { type: 'application/pdf' }),
    a = document.createElement('a');
  a.href = URL.createObjectURL(b);
  a.download = fname.replace(/\.pdf$/i, '') + (flat ? _t('_flattened.pdf') : _t('_annotated.pdf'));
  a.click();
  if (!flat) markSaved();
}
// ---- Unsaved changes. Penfold remembers how the document was when it was opened or last saved, and compares it with
// how it is now: page order and rotation, bookmarks and form values (docShape), and each of Penfold's own annotations
// (a snapshot in a._o, and how many there were per page in p._nOwn). Undoing a change by hand leaves nothing to save.
// A merged document has never been saved (savedShape = null).
let savedShape = '';
const annSnap = (a) => JSON.stringify(a, (k, v) => (k == '_o' ? undefined : v));
const ownAnnots = (p) => p.annots.filter((a) => !a.ro && a.type != 'link');
function docShape() {
  const bm = (l) =>
    l.map((b) => [b.title, pages.indexOf(b.page), b.dd || null, b.color || null, !!b.bold, !!b.italic, bm(b.items)]);
  return JSON.stringify([pages.map((p) => [p.doc, p.idx, p.rot || 0]), bm(bms), docs.map((d) => (d && d.fv) || {})]);
}
function markPageSaved(p) {
  const own = ownAnnots(p);
  own.forEach((a) => (a._o = annSnap(a)));
  p._nOwn = own.length;
}
// After opening or saving, the current state becomes the saved one (never = a document that has not been saved yet)
function markSaved(never) {
  savedShape = never ? null : docShape();
  pages.forEach(markPageSaved);
}
function hasUnsavedChanges() {
  if (!pages.length) return false;
  if (savedShape === null || docShape() !== savedShape) return true;
  return pages.some((p) => {
    const own = ownAnnots(p);
    return own.some((a) => a._o !== annSnap(a)) || own.filter((a) => a._o).length !== (p._nOwn || 0);
  });
}
// What to do with unsaved changes: 'save', 'discard' or 'cancel'. A protected PDF cannot be saved: Discard or Cancel.
// As in GNOME, the text is centred and Discard, which loses the changes, is shown in red.
function unsavedDialog() {
  const locked = isLocked(),
    pr = locked
      ? choiceDialog(
          _t('Discard the changes to “{name}”?', { name: fname }),
          _t('This PDF is protected: its changes cannot be saved and will be lost.'),
          [
            [_t('Cancel'), 'cancel'],
            [_t('Discard'), 'discard', false, 'danger'],
          ],
        )
      : choiceDialog(
          _t('Save changes to “{name}”?', { name: fname }),
          _t('If you don’t save, your changes will be lost.'),
          [
            [_t('Cancel'), 'cancel'],
            [_t('Discard'), 'discard', false, 'danger'],
            [_t('Save'), 'save', true],
          ],
        );
  document.querySelector('#dlg2 .box>div').style.textAlign = 'center';
  const b = document.querySelector('#dlg2 button.on') || document.querySelector('#dlg2 button.danger');
  if (b) b.focus();
  return pr;
}
// Before the document is replaced (Open, Merge, a PDF from the desktop) or the window is closed.
// true = go ahead (nothing to save, discarded or saved); false = stop.
async function confirmUnsaved() {
  if (!hasUnsavedChanges()) return true;
  const v = await unsavedDialog();
  if (v == 'discard') return true;
  if (v != 'save') return false;
  try {
    if (handle) {
      await save(handle);
      return true;
    }
    return await saveAs();
  } catch (e) {
    if (e.name != 'AbortError') msg('Error: ' + e.message);
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
function placeBms(list, at, nodes) {
  let x = null,
    xi = -1;
  list.forEach((it, i) => {
    if (pages.indexOf(it.page) < at) {
      x = it;
      xi = i;
    }
  });
  if (!x) {
    list.unshift(...nodes);
    return;
  }
  const later = (l) => l.some((c) => pages.indexOf(c.page) >= at || later(c.items));
  if (x.items.length && later(x.items)) {
    x.open = true;
    placeBms(x.items, at, nodes);
  } else list.splice(xi + 1, 0, ...nodes);
}
async function insertPdf(f, mode, afterN, blank) {
  const bytes = await f.arrayBuffer(),
    pdf = await pdfjsLib.getDocument({ data: bytes.slice(0), isEvalSupported: false }).promise;
  if (await isProtected(pdf, bytes))
    throw new Error(_t('“{name}” is protected against changes and cannot be added yet.', { name: f.name }));
  const di = docs.push({ bytes, pdf }) - 1,
    np = [];
  for (let i = 0; i < pdf.numPages; i++) np.push({ doc: di, idx: i, annots: [], thumb: null, rot: 0, loaded: false });
  const at = mode == 'start' ? 0 : mode == 'end' ? pages.length : afterN;
  pages.splice(at, 0, ...np);
  const nodes = prune(await convert((await pdf.getOutline()) || [], di));
  if (nodes.length) {
    placeBms(bms, at, nodes);
    flashBm = nodes[0];
  }
  renderSide();
  await renderMain();
  goTo(at);
  loadAllAnnots();
  {
    const pn = _n(np.length, '{n} page', '{n} pages');
    msg(
      blank
        ? _t('Blank page added.')
        : nodes.length
          ? _t('PDF added: {pn} and its bookmarks.', { pn })
          : _t('PDF added: {pn}.', { pn }),
    );
  }
}
// Blank page: a single-page PDF created on the spot, which goes in just like an added PDF
async function insertBlank(size, mode, afterN) {
  const dim = { a4: [595.28, 841.89], letter: [612, 792], a5: [419.53, 595.28], a3: [841.89, 1190.55] };
  const [w, h] = dim[size] || dim.a4;
  const d = await PDFLib.PDFDocument.create();
  d.addPage([w, h]);
  await insertPdf(new Blob([await d.save()], { type: 'application/pdf' }), mode, afterN, true);
}
function addDialog() {
  if (!pages.length) return;
  let file = null;
  const ov = document.createElement('div');
  ov.id = 'dlg';
  ov.innerHTML = `<div class="box"><h3>Add pages</h3>
  <label><input type="radio" name="ds" value="pdf" checked> From a PDF</label>
  <div class="row"><button id="dPick">Choose PDF…</button><span id="dName">No file chosen</span></div>
  <label><input type="radio" name="ds" value="blank"> Blank page</label>
  <div class="row">Size: <select id="dSize"><option value="a4">A4</option><option value="letter">Letter</option><option value="a5">A5</option><option value="a3">A3</option></select></div>
  <b>Where should they be added?</b>
  <label><input type="radio" name="dw" value="start"> At the start</label>
  <label><input type="radio" name="dw" value="end" checked> At the end</label>
  <label><input type="radio" name="dw" value="after"> After page <input id="dN" type="number" min="1" max="${pages.length}" value="${cur + 1}"></label>
  <div class="row r"><button id="dCancel">Cancel</button><button id="dOk" class="on" disabled>Add</button></div></div>`;
  i18nApply(ov);
  document.body.appendChild(ov);
  const close = () => {
      ov.remove();
      document.removeEventListener('keydown', esc);
    },
    esc = (e) => {
      if (e.key == 'Escape') close();
    };
  document.addEventListener('keydown', esc);
  const inp = document.createElement('input');
  inp.type = 'file';
  inp.accept = '.pdf,application/pdf';
  const src = () => ov.querySelector('input[name=ds]:checked').value,
    okState = () => {
      ov.querySelector('#dOk').disabled = src() == 'pdf' && !file;
    };
  inp.onchange = () => {
    file = inp.files[0];
    if (file) {
      ov.querySelector('#dName').textContent = file.name;
      ov.querySelector('input[name=ds][value=pdf]').checked = true;
      okState();
    }
  };
  ov.querySelector('#dPick').onclick = () => inp.click();
  ov.querySelectorAll('input[name=ds]').forEach((r) => (r.onchange = okState));
  ov.querySelector('#dSize').onchange = () => {
    ov.querySelector('input[name=ds][value=blank]').checked = true;
    okState();
  };
  ov.querySelector('#dSize').onfocus = ov.querySelector('#dSize').onchange;
  ov.querySelector('#dN').oninput = () => (ov.querySelector('input[value=after]').checked = true);
  ov.querySelector('#dCancel').onclick = close;
  ov.querySelector('#dOk').onclick = async () => {
    const mode = ov.querySelector('input[name=dw]:checked').value,
      n = parseInt(ov.querySelector('#dN').value);
    if (mode == 'after' && !(n >= 1 && n <= pages.length)) {
      msg(_t('The page must be between 1 and {n}.', { n: pages.length }));
      return;
    }
    const kind = src(),
      size = ov.querySelector('#dSize').value;
    close();
    msg(_t('Adding…'));
    try {
      if (kind == 'blank') await insertBlank(size, mode, n);
      else await insertPdf(file, mode, n);
    } catch (e) {
      msg(_t('Error adding: {m}', { m: e.message }));
    }
  };
}
// ---- Find: the text of each page is read without painting it; ignores case and accents
const S = { q: '', hits: [], i: -1, tok: 0, busy: false, by: null, ref: [] };
const nch = (c) =>
  c
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
const nq = (s) => {
  let n = '';
  for (let o = 0; o < s.length; o++) {
    const c = nch(s[o]);
    for (let k = 0; k < c.length; k++) {
      const w = /\s/.test(c[k]) ? ' ' : c[k];
      if (w == ' ' && (n === '' || n.endsWith(' '))) continue;
      n += w;
    }
  }
  return n.trim();
};
// Normalised page text, with the mapping of each character to its fragment (mi) and its position within it (mo)
function mkTx(items) {
  let n = '',
    prev = null;
  const mi = [],
    mo = [];
  items.forEach((it, k) => {
    if (prev && n && !n.endsWith(' ')) {
      const h = it.height || prev.height || 10,
        dy = Math.abs(it.transform[5] - prev.transform[5]),
        gap = it.transform[4] - (prev.transform[4] + prev.width);
      if (prev.hasEOL || dy > h * 0.5 || gap > h * 0.15) {
        n += ' ';
        mi.push(-1);
        mo.push(0);
      }
    }
    const t = it.str;
    for (let o = 0; o < t.length; o++) {
      const c = nch(t[o]);
      for (let q = 0; q < c.length; q++) {
        const w = /\s/.test(c[q]) ? ' ' : c[q];
        if (w == ' ' && (n === '' || n.endsWith(' '))) continue;
        n += w;
        mi.push(k);
        mo.push(o);
      }
    }
    prev = it;
  });
  return { items, n, mi, mo };
}
async function getTx(p) {
  if (p._tx) return p._tx;
  const pg = await docs[p.doc].pdf.getPage(p.idx + 1),
    tc = await pg.getTextContent();
  return (p._tx = mkTx(tc.items.filter((i) => typeof i.str == 'string')));
}
// Rectangles (in page pixels) of a match: one for each text fragment it crosses
function hitRects(h, vp) {
  const tx = h.p._tx,
    seg = {},
    out = [];
  for (let k = h.s; k < h.e; k++) {
    const i = tx.mi[k];
    if (i < 0) continue;
    const o = tx.mo[k],
      g = seg[i] || (seg[i] = [o, o + 1]);
    if (o < g[0]) g[0] = o;
    if (o + 1 > g[1]) g[1] = o + 1;
  }
  for (const i in seg) {
    const it = tx.items[i],
      [a, b, c, d, e, f] = it.transform,
      L = it.str.length || 1,
      [o1, o2] = seg[i],
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
      ].map((q) => vp.convertToViewportPoint(q[0], q[1])),
      xs = P.map((q) => q[0]),
      ys = P.map((q) => q[1]),
      l = Math.min(...xs),
      t = Math.min(...ys);
    out.push({ l, t, w: Math.max(...xs) - l, h: Math.max(...ys) - t });
  }
  return out;
}
function markHits(el) {
  const o = el.querySelector('.sr');
  if (o) o.remove();
  if (!S.by || !S.q || !el._vp) return;
  const arr = S.by.get(el._p);
  if (!arr) return;
  const box = document.createElement('div');
  box.className = 'sr';
  arr.forEach((h) => {
    const c = h === S.hits[S.i];
    hitRects(h, el._vp).forEach((r) => {
      const d = document.createElement('div');
      if (c) d.className = 'cur';
      d.style.cssText = 'left:' + r.l + 'px;top:' + r.t + 'px;width:' + r.w + 'px;height:' + r.h + 'px';
      box.appendChild(d);
    });
  });
  el.appendChild(box);
}
const refreshMarks = () =>
  [...$('#view').children].forEach((el) => {
    if (el._ov) markHits(el);
  });
function fcount() {
  const c = $('#sc');
  c.textContent = !S.q
    ? ''
    : !S.hits.length
      ? S.busy
        ? _t('Searching…')
        : _t('No results')
      : S.i < 0
        ? _n(S.hits.length, '{n} result', '{n} results')
        : _t('{i} of {n}', { i: S.i + 1, n: S.hits.length });
}
function fshow() {
  const h = S.hits[S.i];
  if (!h) return;
  const pi = pages.indexOf(h.p);
  if (pi < 0) return;
  const v = $('#view'),
    el = v.children[pi],
    same = !twoUp || pi - (pi % 2) == shownPair,
    r = el && el._vp && hitRects(h, el._vp)[0];
  let vis = false;
  if (r && same) {
    const er = el.getBoundingClientRect(),
      vr = v.getBoundingClientRect(),
      t = er.top + r.t,
      l = er.left + r.l;
    vis =
      el.style.display != 'none' &&
      t >= vr.top + 20 &&
      t + r.h <= vr.bottom - 20 &&
      l >= vr.left &&
      l + r.w <= vr.right - 16;
  }
  if (!vis && !(twoUp && same)) goTo(pi);
  refreshMarks();
  if (!vis && r && same) {
    const er = el.getBoundingClientRect(),
      vr = v.getBoundingClientRect(),
      cx = er.left + r.l + r.w / 2;
    v.scrollTop += er.top + r.t - (vr.top + v.clientHeight / 3);
    if (cx < vr.left || cx > vr.right) v.scrollLeft += cx - (vr.left + v.clientWidth / 2);
  }
  fcount();
}
async function runFind() {
  const q = nq($('#sq').value),
    tok = ++S.tok;
  S.q = q;
  S.hits = [];
  S.i = -1;
  S.by = new Map();
  S.ref = pages.slice();
  S.busy = false;
  $('#view')
    .querySelectorAll('.sr')
    .forEach((x) => x.remove());
  if (!q) {
    fcount();
    return;
  }
  S.busy = true;
  fcount();
  const start = cur;
  let placed = false;
  for (let k = 0; k < pages.length; k++) {
    const p = pages[k];
    let tx;
    try {
      tx = await getTx(p);
    } catch (e) {
      continue;
    }
    if (tok != S.tok) return;
    const arr = [];
    let i = 0;
    while ((i = tx.n.indexOf(q, i)) >= 0) {
      const h = { p, s: i, e: i + q.length };
      S.hits.push(h);
      arr.push(h);
      i += q.length;
    }
    if (arr.length) {
      S.by.set(p, arr);
      if (!placed && k >= start) {
        placed = true;
        S.i = S.hits.length - arr.length;
        fshow();
      } else {
        const el = $('#view').children[k];
        if (el && el._ov) markHits(el);
      }
    }
    fcount();
  }
  S.busy = false;
  if (!placed && S.hits.length) {
    S.i = 0;
    fshow();
  }
  fcount();
}
function fstep(d) {
  if (!S.q || !pages.length) return;
  if (pages.length != S.ref.length || pages.some((p, i) => p !== S.ref[i])) {
    runFind();
    return;
  }
  const n = S.hits.length;
  if (!n) return;
  S.i = S.i < 0 ? (d > 0 ? 0 : n - 1) : (S.i + d + n) % n;
  fshow();
}
const findOpen = () => $('#sb').style.display == 'flex';
function openFind() {
  if (!pages.length) return;
  const b = $('#sb'),
    was = findOpen();
  b.style.top = $('#bar').offsetHeight + 8 + 'px';
  b.style.display = 'flex';
  $('#bFind').classList.add('on');
  const i = $('#sq');
  i.focus();
  i.select();
  if (!was && nq(i.value)) runFind();
}
function closeFind() {
  S.tok++;
  S.hits = [];
  S.by = null;
  S.i = -1;
  S.busy = false;
  S.q = '';
  $('#sb').style.display = 'none';
  $('#bFind').classList.remove('on');
  $('#sc').textContent = '';
  $('#view')
    .querySelectorAll('.sr')
    .forEach((x) => x.remove());
}
let ftm;
$('#sq').oninput = () => {
  clearTimeout(ftm);
  ftm = setTimeout(runFind, 250);
};
$('#sq').onkeydown = (e) => {
  if (e.key != 'Enter') return;
  e.preventDefault();
  if (nq(e.target.value) !== S.q) {
    clearTimeout(ftm);
    runFind();
  } else fstep(e.shiftKey ? -1 : 1);
};
$('#sPrev').onclick = () => fstep(-1);
$('#sNext').onclick = () => fstep(1);
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
let prnBusy = false,
  prnFrame = null,
  prnUrl = null;
function printDialog() {
  if (!pages.length || document.getElementById('dlg')) return;
  if (isLocked()) {
    msg(_t('This PDF is protected against changes: Penfold cannot save it, print it or extract pages from it yet.'));
    return;
  }
  const ov = document.createElement('div');
  ov.id = 'dlg';
  ov.innerHTML = `<div class="box"><h3>Print</h3><div class="hint">Annotations to print:</div>
  <label><input type="checkbox" data-t="note"> Comments</label>
  <label><input type="checkbox" data-t="ft"> Text boxes</label>
  <label><input type="checkbox" data-t="hl" checked> Highlights</label>
  <label><input type="checkbox" data-t="ul" checked> Underlines</label>
  <label><input type="checkbox" data-t="so" checked> Strikethroughs</label>
  <label><input type="checkbox" data-t="sq" checked> Rectangles</label>
  <label><input type="checkbox" data-t="ci" checked> Circles</label>
  <label><input type="checkbox" data-t="ar" checked> Arrows</label>
  <div class="row r"><button id="pCancel">Cancel</button><button id="pOk" class="on">Print</button></div></div>`;
  i18nApply(ov);
  document.body.appendChild(ov);
  const close = () => {
    ov.remove();
    document.removeEventListener('keydown', key);
  };
  const ok = () => {
    const types = new Set([...ov.querySelectorAll('input:checked')].map((x) => x.dataset.t));
    close();
    doPrint(types);
  };
  const key = (e) => {
    if (e.key == 'Escape') close();
    else if (e.key == 'Enter' && e.target.tagName != 'BUTTON') {
      e.preventDefault();
      ok();
    }
  };
  document.addEventListener('keydown', key);
  ov.querySelector('#pCancel').onclick = close;
  ov.querySelector('#pOk').onclick = ok;
  ov.querySelector('#pOk').focus();
}
async function doPrint(types) {
  if (prnBusy) return;
  prnBusy = true;
  try {
    msg(_t('Preparing to print…'));
    await Promise.all(pages.map(loadAnnots));
    const bytes = await build({ types, noBms: true });
    if (prnFrame) {
      prnFrame.remove();
      prnFrame = null;
    }
    if (prnUrl) {
      URL.revokeObjectURL(prnUrl);
      prnUrl = null;
    }
    const url = URL.createObjectURL(new Blob([bytes], { type: 'application/pdf' })),
      f = document.createElement('iframe');
    f.style.cssText = 'position:fixed;left:-9999px;top:0;width:800px;height:600px;border:0';
    f.onload = () =>
      setTimeout(() => {
        try {
          f.contentWindow.focus();
          f.contentWindow.print();
          $('#msg').style.display = 'none';
        } catch (e) {
          window.open(url, '_blank');
          msg(
            _t(
              'This browser does not allow printing from here: the PDF has been opened in another tab; print it from there.',
            ),
          );
        }
      }, 400);
    f.src = url;
    document.body.appendChild(f);
    prnFrame = f;
    prnUrl = url;
  } catch (e) {
    msg('Error: ' + e.message);
  }
  prnBusy = false;
}
$('#bPrint').onclick = printDialog;
// ---- About dialog (Information button): name, version, links, credits and licence. Change these values here only.
const APP = {
  name: 'Penfold',
  version: '0.5.3',
  author: 'ibanurq',
  year: 2026,
  repo: 'https://github.com/ibanurq/penfold',
  licence: 'GPL-3.0',
  licenceUrl: 'https://www.gnu.org/licenses/gpl-3.0.html',
};
// The About dialogue shows the app's colour icon (the welcome screen keeps its monochrome symbolic version)
const APP_ICON = '<img class="ico" src="assets/penfold.svg" alt="">';
function aboutDialog() {
  if (document.getElementById('dlg')) return;
  const ov = document.createElement('div');
  ov.id = 'dlg';
  ov.innerHTML =
    '<div class="box about">' +
    APP_ICON +
    '<h3></h3><div class="ver"></div><div class="tag"></div>' +
    '<div class="links"><a class="web" target="_blank" rel="noopener"></a><a class="bug" target="_blank" rel="noopener"></a></div>' +
    '<div class="small cred"></div><div class="small libs"></div><div class="small copy"><span></span> · <a class="lic" target="_blank" rel="noopener"></a></div>' +
    '<div class="row r"><button class="on ok"></button></div></div>';
  const q = (s) => ov.querySelector(s);
  q('h3').textContent = APP.name;
  q('.ver').textContent = _t('Version {v}', { v: APP.version });
  q('.tag').textContent = _t('Read, annotate and organise your PDFs.');
  q('.web').textContent = _t('Website');
  q('.web').href = APP.repo;
  q('.bug').textContent = _t('Report an issue');
  q('.bug').href = APP.repo + '/issues';
  q('.cred').textContent = _t('Created by {a}, with AI assistance', { a: APP.author });
  q('.libs').textContent = _t('Uses pdf.js (Apache-2.0) · pdf-lib (MIT) · Lucide icons (ISC)');
  q('.copy span').textContent = '© ' + APP.year + ' ' + APP.author;
  q('.lic').textContent = _t('Licence {l}', { l: APP.licence });
  q('.lic').href = APP.licenceUrl;
  q('.ok').textContent = _t('Close');
  const close = () => {
      ov.remove();
      document.removeEventListener('keydown', key);
    },
    key = (e) => {
      if (e.key == 'Escape' || (e.key == 'Enter' && e.target.tagName != 'A')) {
        e.preventDefault();
        close();
      }
    };
  q('.ok').onclick = close;
  document.addEventListener('keydown', key);
  document.body.appendChild(ov);
  q('.ok').focus();
}
$('#bInfo').onclick = aboutDialog;
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
function textDialog(title, init, cb) {
  if (document.getElementById('dlg')) return;
  const ov = document.createElement('div');
  ov.id = 'dlg';
  ov.innerHTML =
    '<div class="box wide"><h3></h3><textarea rows="6"></textarea><div class="row r"><button id="tCancel">Cancel</button><button id="tOk" class="on">Save</button></div></div>';
  i18nApply(ov);
  ov.querySelector('h3').textContent = title;
  const ta = ov.querySelector('textarea');
  ta.value = init || '';
  document.body.appendChild(ov);
  const close = () => {
    ov.remove();
    document.removeEventListener('keydown', key);
  };
  const ok = () => {
    const v = ta.value;
    close();
    if (v.trim()) cb(v);
  };
  const key = (e) => {
    if (e.key == 'Escape') close();
    else if (e.key == 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      ok();
    }
  };
  document.addEventListener('keydown', key);
  ov.querySelector('#tCancel').onclick = close;
  ov.querySelector('#tOk').onclick = ok;
  ta.focus();
  ta.setSelectionRange(ta.value.length, ta.value.length);
}
// ---- Merge PDF: list of files -> a single document open in the application
async function mergeInto(items, genBm, keepBm) {
  docs = [];
  pages = [];
  selPages.clear();
  selBms.clear();
  anchor = -1;
  anchorBm = null;
  cur = 0;
  handle = null;
  fname = _t('merged.pdf');
  const firsts = [];
  items.forEach((it) => {
    const di = docs.push({ bytes: it.bytes, pdf: it.pdf }) - 1;
    firsts.push(pages.length);
    for (let i = 0; i < it.n; i++) pages.push({ doc: di, idx: i, annots: [], thumb: null, rot: 0, loaded: false });
  });
  bms = [];
  for (let k = 0; k < items.length; k++) {
    const sub = keepBm ? prune(await convert((await items[k].pdf.getOutline()) || [], k)) : [];
    if (genBm) {
      bms.push({
        title: items[k].file.name.replace(/\.[^.\/\\]+$/, ''),
        page: pages[firsts[k]],
        color: null,
        bold: false,
        italic: false,
        items: sub,
      });
    } else {
      bms.push(...sub);
    }
  }
  // The merged document exists only on screen until it is saved
  markSaved(true);
  tab = 'bm';
  ready();
}
function mergeDialog() {
  if (document.getElementById('dlg')) return;
  const items = [];
  let dragIdx = -1;
  const ov = document.createElement('div');
  ov.id = 'dlg';
  ov.innerHTML = `<div class="box wide"><h3>Merge PDF</h3>
  <div id="mList" class="mlist"></div>
  <div class="row"><button id="mAdd">Add PDFs…</button><span id="mTot" style="opacity:.7"></span></div>
  <label><input type="checkbox" id="mGen" checked> Create a bookmark for each file</label>
  <label><input type="checkbox" id="mKeep" checked> Keep the files’ bookmarks</label>
  <div class="row r"><button id="mCancel">Cancel</button><button id="mOk" class="on" disabled>Merge</button></div></div>`;
  i18nApply(ov);
  document.body.appendChild(ov);
  const q = (sel) => ov.querySelector(sel),
    list = q('#mList');
  const close = () => {
      ov.remove();
      document.removeEventListener('keydown', esc);
    },
    esc = (e) => {
      if (e.key == 'Escape') close();
    };
  document.addEventListener('keydown', esc);
  ov.ondragover = (e) => e.preventDefault();
  ov.ondrop = (e) => e.preventDefault();
  const draw = () => {
    list.innerHTML = '';
    if (!items.length) {
      const e = document.createElement('div');
      e.style.cssText = 'opacity:.55;text-align:center;padding:100px 10px';
      e.textContent = _t('Drag PDFs here or click “Add PDFs…”');
      list.appendChild(e);
    }
    items.forEach((it, i) => {
      const r = document.createElement('div');
      r.className = 'mrow' + (it.enc ? ' enc' : '');
      r.draggable = true;
      const nm = document.createElement('span');
      nm.className = 'nm';
      nm.textContent = it.file.name;
      nm.title = it.file.name;
      // Protected PDFs stay in the list (in red) so it is clear which ones will not be merged
      const pg = document.createElement('span');
      if (it.enc) {
        pg.className = 'bad';
        pg.textContent = _t('Cannot be merged');
      } else {
        pg.className = 'pg';
        pg.textContent = _n(it.n, '{n} p.', '{n} pp.');
      }
      const x = document.createElement('button');
      x.textContent = '✕';
      x.title = _t('Remove from list');
      x.onclick = () => {
        items.splice(i, 1);
        draw();
      };
      const zone = (ev) => {
        const b = r.getBoundingClientRect();
        return ev.clientY < b.top + b.height / 2 ? 'before' : 'after';
      };
      r.ondragstart = (ev) => {
        dragIdx = i;
        ev.dataTransfer.setData('text/plain', 'row');
        ev.dataTransfer.effectAllowed = 'move';
      };
      r.ondragend = () => {
        dragIdx = -1;
        draw();
      };
      r.ondragover = (ev) => {
        if (dragIdx < 0) return;
        ev.preventDefault();
        ev.stopPropagation();
        r.classList.remove('before', 'after');
        r.classList.add(zone(ev));
      };
      r.ondragleave = () => r.classList.remove('before', 'after');
      r.ondrop = (ev) => {
        if (dragIdx < 0) return;
        ev.preventDefault();
        ev.stopPropagation();
        const z = zone(ev),
          [m] = items.splice(dragIdx, 1);
        let t = i;
        if (dragIdx < i) t--;
        items.splice(z == 'after' ? t + 1 : t, 0, m);
        dragIdx = -1;
        draw();
      };
      r.append(nm, pg, x);
      list.appendChild(r);
    });
    const ok = items.filter((it) => !it.enc),
      tot = ok.reduce((n, it) => n + it.n, 0);
    q('#mTot').textContent = ok.length
      ? _n(ok.length, '{n} file', '{n} files') + ' · ' + _n(tot, '{n} page in total', '{n} pages in total')
      : '';
    q('#mOk').disabled = ok.length < 2;
  };
  const addFiles = async (fs) => {
    for (const f of fs) {
      if (!/\.pdf$/i.test(f.name) && f.type != 'application/pdf') continue;
      try {
        const bytes = await f.arrayBuffer(),
          pdf = await pdfjsLib.getDocument({ data: bytes.slice(0), isEvalSupported: false }).promise;
        items.push({ file: f, bytes, pdf, n: pdf.numPages, enc: await isProtected(pdf, bytes) });
      } catch (e) {
        msg(_t('Could not read “{name}”: {m}', { name: f.name, m: e.message }));
      }
    }
    draw();
  };
  const inp = document.createElement('input');
  inp.type = 'file';
  inp.accept = '.pdf,application/pdf';
  inp.multiple = true;
  inp.onchange = () => addFiles([...inp.files]);
  q('#mAdd').onclick = () => inp.click();
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
  q('#mCancel').onclick = close;
  q('#mOk').onclick = async () => {
    if (!(await confirmUnsaved())) return;
    const genBm = q('#mGen').checked;
    const keepBm = q('#mKeep').checked;
    close();
    msg(_t('Merging…'));
    try {
      await mergeInto(
        items.filter((it) => !it.enc),
        genBm,
        keepBm,
      );
      msg(_t('PDF merged: {n} pages. Use “Save As…” to save it.', { n: pages.length }));
    } catch (e) {
      msg(_t('Error merging: {m}', { m: e.message }));
    }
  };
  draw();
}
function closePal() {
  const d = document.getElementById('pal');
  if (d) d.remove();
}
function openPal(anchor, pick, list) {
  closePal();
  const d = document.createElement('div');
  d.id = 'pal';
  list = list || PAL;
  if (list.length > 6) d.style.gridTemplateColumns = 'repeat(4,24px)';
  list.forEach((x) => {
    const b = document.createElement('button');
    b.className = 'sq';
    b.title = _t(x.n);
    b.style.background = x.p;
    b.onclick = (ev) => {
      ev.stopPropagation();
      closePal();
      pick(x.p);
    };
    d.appendChild(b);
  });
  document.body.appendChild(d);
  const r = anchor.getBoundingClientRect();
  d.style.left = Math.max(8, Math.min(r.left, innerWidth - d.offsetWidth - 8)) + 'px';
  d.style.top = r.bottom + 6 + 'px';
  setTimeout(() => document.addEventListener('click', closePal, { once: true }), 0);
}
function updPg() {
  cur = Math.max(0, Math.min(cur, pages.length - 1));
  $('#pg').value = pages.length ? cur + 1 : '';
  $('#pgN').textContent = pages.length;
}
async function zoomTo(fn) {
  const keep = cur;
  fn();
  await renderMain();
  goTo(keep);
}
// When the viewer's width changes (side panel) the zoom is re-fitted (fit width; in “Two pages”, whole page). Called once, when the change has finished.
function reflowOnWidth(w0) {
  const w = $('#view').clientWidth;
  if (!pages.length || w0 <= 60 || w <= 60 || Math.abs(w - w0) < 2) return;
  setFit(twoUp ? 'p' : 'w');
}
// When a PDF is opened it is fitted to the width (if that fails, it is painted at the current zoom)
function fitOnOpen() {
  cur = 0;
  Promise.resolve(setFit(twoUp ? 'p' : 'w')).catch(() => renderMain());
}
async function setFit(mode) {
  const p = pages[cur];
  if (!p) return;
  const v = $('#view'),
    s = cur - (cur % 2),
    ix = twoUp ? [s, s + 1].filter((k) => k < pages.length) : [cur],
    vs = [];
  for (const k of ix) {
    const q = pages[k],
      g = await docs[q.doc].pdf.getPage(q.idx + 1);
    vs.push(g.getViewport({ scale: 1, rotation: (g.rotate + (q.rot || 0)) % 360 }));
  }
  const tw = vs.reduce((a, x) => a + x.width, 0) + (twoUp && vs.length == 1 ? vs[0].width : 0),
    th = Math.max(...vs.map((x) => x.height)),
    w = (v.clientWidth - 40 - (twoUp ? 14 : 0)) / tw,
    h = v.clientHeight - (twoUp ? 48 : 30);
  const ns = Math.max(0.3, Math.min(4, mode == 'w' ? w : Math.min(w, h / th)));
  if (twoUp && Math.abs(ns - scale) < 1e-6) {
    showPair();
    return;
  }
  zoomTo(() => {
    scale = ns;
  });
}
$('#two').onclick = () => {
  twoUp = !twoUp;
  $('#view').classList.toggle('two', twoUp);
  $('#two').classList.toggle('on', twoUp);
  showPair();
  setFit(twoUp ? 'p' : 'w');
};
// In “Two pages” the wheel, the left/right arrows and Page Up / Page Down change pair
const flip = (d) => {
  const t = cur - (cur % 2) + 2 * d;
  if (t >= 0 && t < pages.length) goTo(t);
};
let wLock = 0;
$('#view').addEventListener(
  'wheel',
  (e) => {
    if (!twoUp || e.ctrlKey || !e.deltaY || Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;
    const v = e.currentTarget,
      now = Date.now(),
      down = e.deltaY > 0;
    if (down ? v.scrollTop + v.clientHeight < v.scrollHeight - 2 : v.scrollTop > 0) {
      wLock = Math.max(wLock, now + 250);
      return;
    }
    e.preventDefault();
    if (now < wLock) {
      wLock = Math.max(wLock, now + 150);
      return;
    }
    wLock = now + 450;
    flip(down ? 1 : -1);
  },
  { passive: false },
);
document.addEventListener('keydown', (e) => {
  if (
    !twoUp ||
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
    flip(d);
  }
});
$('#fw').onclick = () => setFit('w');
$('#fp').onclick = () => setFit('p');
$('#pg').onfocus = (e) => e.target.select();
$('#pg').onkeydown = (e) => {
  if (e.key != 'Enter') return;
  const n = parseInt(e.target.value);
  if (n >= 1 && n <= pages.length) goTo(n - 1);
  else updPg();
  e.target.blur();
};
$('#bMerge').onclick = mergeDialog;
$('#eOpen').onclick = () => $('#bOpen').click();
$('#eMerge').onclick = () => $('#bMerge').click();
// ---- Extract pages ----
function parsePages(str, n) {
  const out = new Set(),
    parts = str
      .split(/[,;]/)
      .map((t) => t.trim())
      .filter(Boolean);
  if (!parts.length) return { err: _t('Enter at least one page.') };
  for (const t of parts) {
    const m = t.match(/^(\d+)\s*(-)?\s*(\d+)?$/);
    if (!m || (m[3] && !m[2])) return { err: _t('Invalid format: “{t}”.', { t }) };
    const a = +m[1],
      b = m[2] ? (m[3] ? +m[3] : n) : a;
    if (a < 1 || a > n) return { err: _t('Page {p} does not exist (the document has {n}).', { p: a, n }) };
    if (b < a) return { err: _t('Invalid range: “{t}”.', { t }) };
    if (b > n) return { err: _t('Page {p} does not exist (the document has {n}).', { p: b, n }) };
    for (let k = a; k <= b; k++) out.add(k);
  }
  return { list: [...out].sort((x, y) => x - y) };
}
function fmtPages(l) {
  const r = [];
  for (let i = 0; i < l.length;) {
    let j = i;
    while (j + 1 < l.length && l[j + 1] == l[j] + 1) j++;
    r.push(j > i ? l[i] + '-' + l[j] : '' + l[i]);
    i = j + 1;
  }
  return r.join(', ');
}
function choiceDialog(title, text, btns) {
  return new Promise((res) => {
    const o = document.createElement('div');
    o.id = 'dlg2';
    o.innerHTML = '<div class="box"><h3></h3><div style="white-space:pre-wrap"></div><div class="row"></div></div>';
    o.querySelector('h3').textContent = title;
    o.querySelector('.box>div').textContent = text;
    const fin = (v) => {
        o.remove();
        document.removeEventListener('keydown', esc);
        res(v);
      },
      esc = (e) => {
        if (e.key == 'Escape') fin('cancel');
      };
    btns.forEach(([l, v, on, cls]) => {
      const b = document.createElement('button');
      b.textContent = l;
      if (on) b.className = 'on';
      if (cls) b.classList.add(cls);
      b.onclick = () => fin(v);
      o.querySelector('.row').appendChild(b);
    });
    document.addEventListener('keydown', esc);
    document.body.appendChild(o);
  });
}
function confirmDialog(title, text, okLabel) {
  const pr = choiceDialog(title, text, [
    [_t('Cancel'), 'cancel'],
    [okLabel || _t('OK'), 'ok', true],
  ]);
  const b = document.querySelector('#dlg2 button.on');
  if (b) b.focus();
  return pr.then((v) => v == 'ok');
}
function promptDialog(title, label, init, okLabel) {
  return new Promise((res) => {
    const o = document.createElement('div');
    o.id = 'dlg2';
    o.innerHTML =
      '<div class="box"><h3></h3><div></div><input type="text" autocomplete="off"><div class="row"><button class="c"></button><button class="on ok"></button></div></div>';
    o.querySelector('.c').textContent = _t('Cancel');
    o.querySelector('h3').textContent = title;
    o.querySelector('.box>div').textContent = label;
    const inp = o.querySelector('input');
    inp.value = init || '';
    o.querySelector('.ok').textContent = okLabel || _t('OK');
    const fin = (v) => {
      o.remove();
      document.removeEventListener('keydown', key);
      res(v);
    };
    const key = (e) => {
      if (e.key == 'Escape') fin(null);
      else if (e.key == 'Enter' && e.target === inp) {
        e.preventDefault();
        fin(inp.value || null);
      }
    };
    o.querySelector('.c').onclick = () => fin(null);
    o.querySelector('.ok').onclick = () => fin(inp.value || null);
    document.addEventListener('keydown', key);
    document.body.appendChild(o);
    inp.focus();
    inp.select();
  });
}
function extractDialog(init) {
  if (!pages.length) {
    msg(_t('Open a PDF first.'));
    return;
  }
  if (document.getElementById('dlg')) return;
  if (init === undefined) init = fmtPages(pages.map((p, k) => (selPages.has(p) ? k + 1 : 0)).filter(Boolean));
  const ov = document.createElement('div');
  ov.id = 'dlg';
  ov.innerHTML = `<div class="box"><h3>Extract pages</h3>
  <div style="position:relative"><div class="row"><b>Pages to extract:</b><span class="help" tabindex="0">?<span class="tip">Examples:<br><code>5</code> → page 5 only<br><code>5, 9</code> → pages 5 and 9<br><code>5-10</code> → pages 5 to 10<br><code>5-</code> → page 5 to the end<br><code>1, 5, 10-12, 56-</code> → pages 1 and 5, 10 to 12, and 56 to the end</span></span></div>
  <input id="xPg" type="text" autocomplete="off" placeholder="1, 5, 10-12, 56-" style="width:100%;box-sizing:border-box;margin-top:6px">
  <div id="xErr" class="err"></div></div>
  <label><input type="checkbox" id="xSep"> Extract as separate pages</label>
  <label><input type="checkbox" id="xDel"> Delete pages after extraction</label>
  <label><input type="checkbox" id="xClean"> Delete bookmarks and annotations</label>
  <div class="row r"><button id="xCancel">Cancel</button><button id="xOk" class="on">OK</button></div></div>`;
  i18nApply(ov);
  document.body.appendChild(ov);
  const q = (s) => ov.querySelector(s),
    inp = q('#xPg'),
    err = q('#xErr');
  inp.value = init;
  const close = () => {
      ov.remove();
      document.removeEventListener('keydown', esc);
    },
    esc = (e) => {
      if (e.key == 'Escape' && !document.getElementById('dlg2')) close();
    };
  document.addEventListener('keydown', esc);
  q('#xCancel').onclick = close;
  inp.oninput = () => (err.textContent = '');
  const run = async () => {
    const r = parsePages(inp.value, pages.length);
    if (r.err) {
      err.textContent = r.err;
      return;
    }
    const sel = r.list.map((k) => pages[k - 1]),
      o = { sep: q('#xSep').checked, del: q('#xDel').checked, clean: q('#xClean').checked };
    if (o.del && sel.length >= pages.length) {
      err.textContent = _t('You can’t delete all the pages: untick “Delete pages after extraction”.');
      return;
    }
    q('#xOk').disabled = true;
    try {
      await extractPages(sel, o, ov);
      close();
    } catch (e) {
      q('#xOk').disabled = false;
      if (e.name != 'AbortError') msg('Error: ' + e.message);
    }
  };
  q('#xOk').onclick = run;
  inp.onkeydown = (e) => {
    if (e.key == 'Enter') run();
  };
  inp.focus();
  inp.select();
}
async function extractPages(sel, o, ov) {
  const groups = o.sep ? sel.map((p) => [p]) : [sel],
    w = Math.max(2, String(groups.length).length);
  const names = o.sep
    ? groups.map((_, i) => _t('extracted') + '_' + String(i + 1).padStart(w, '0') + '.pdf')
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
    const ex = [];
    for (const n of names) if (await exists(n)) ex.push(n);
    if (ex.length) {
      ov.style.display = 'none';
      let ch;
      try {
        ch = await choiceDialog(
          _t('Existing files'),
          _t('Already in the folder:') +
            '\n' +
            ex
              .slice(0, 6)
              .map((n) => '- ' + n)
              .join('\n') +
            (ex.length > 6 ? '\n' + _t('…and {n} more', { n: ex.length - 6 }) : '') +
            '\n\n' +
            _t('Do you want to overwrite them or rename the new ones?'),
          [
            [_t('Cancel'), 'cancel'],
            [_t('Rename'), 'rename'],
            [_t('Overwrite'), 'over', 1],
          ],
        );
      } finally {
        ov.style.display = '';
      }
      if (ch == 'cancel') throw Object.assign(new Error('cancel'), { name: 'AbortError' });
      if (ch == 'rename') {
        final = [];
        for (const n of names) {
          let m = n,
            k = 2;
          while (await exists(m)) m = n.replace(/\.pdf$/, '') + ' (' + k++ + ').pdf';
          final.push(m);
        }
      }
    }
  } else msg(_t('This browser does not allow choosing a folder: the files will be downloaded.'));
  const src = await Promise.all(docs.map((d) => PDFLib.PDFDocument.load(d.bytes, { ignoreEncryption: true })));
  for (let i = 0; i < groups.length; i++) {
    const bytes = await build({ pages: groups[i], noAnnots: o.clean, src });
    if (dir) {
      const fh = await dir.getFileHandle(final[i], { create: true }),
        wr = await fh.createWritable();
      await wr.write(bytes);
      await wr.close();
    } else {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([bytes], { type: 'application/pdf' }));
      a.download = final[i];
      a.click();
      await new Promise((r) => setTimeout(r, 300));
    }
  }
  if (o.del) {
    sel.forEach((x) => {
      const idx = pages.indexOf(x);
      if (idx >= 0) pages.splice(idx, 1);
    });
    selPages.clear();
    bms = prune(bms);
    renderSide();
    renderMain();
  }
  msg(
    _t('{x} into {f}', {
      x: _n(sel.length, '{n} page extracted', '{n} pages extracted'),
      f: _n(groups.length, '{n} file', '{n} files'),
    }) +
      (o.del ? _t(' and removed from the document') : '') +
      ' ✔',
  );
}
(() => {
  const sd = $('#side'),
    r = $('#rs');
  sd.style.minWidth = SIDE_MIN + 'px';
  try {
    const w = localStorage.getItem('sw');
    if (w) sd.style.width = w + 'px';
  } catch (e) {}
  r.onmousedown = (e) => {
    e.preventDefault();
    const w0 = $('#view').clientWidth;
    const mm = (ev) => {
      sd.style.width = Math.max(SIDE_MIN, Math.min(thMaxPanel(), ev.clientX)) + 'px';
    };
    const mu = () => {
      document.removeEventListener('mousemove', mm);
      document.removeEventListener('mouseup', mu);
      document.body.style.userSelect = '';
      try {
        localStorage.setItem('sw', parseInt(sd.style.width));
      } catch (e) {}
      reflowOnWidth(w0);
    };
    document.body.style.userSelect = 'none';
    document.addEventListener('mousemove', mm);
    document.addEventListener('mouseup', mu);
  };
})();
new ResizeObserver(thCols).observe($('#sbody'));
new ResizeObserver(lockBadge).observe($('#view'));
