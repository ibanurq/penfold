// Penfold desktop app: the small bridge between the page and the main process.
// The page gets only two abilities: take the file the desktop has just asked to open, and write back to that same
// file (only that one) when “Save” is pressed. A PDF dropped on the window is also sent to the main process to be opened.
'use strict';
const { contextBridge, ipcRenderer, webUtils } = require('electron');

contextBridge.exposeInMainWorld('penfoldDesktop', {
  take: () => ipcRenderer.invoke('penfold:take'),
  write: (id, bytes) => ipcRenderer.invoke('penfold:write', id, bytes),
});

// Dropping a PDF anywhere on the window opens it, except where the app handles drops itself (its dialogues, such as
// Merge). Drags inside the app (thumbnails, bookmarks) carry no files and are left alone.
const hasFiles = (e) => e.dataTransfer && [...e.dataTransfer.types].includes('Files');
const appHandles = (e) => e.target instanceof Element && e.target.closest('#dlg, #dlg2');
window.addEventListener(
  'dragover',
  (e) => {
    if (!hasFiles(e) || appHandles(e)) return;
    e.preventDefault();
    e.stopPropagation(); // so the thumbnails do not react as if a page were being moved
    e.dataTransfer.dropEffect = 'copy';
  },
  true,
);
window.addEventListener(
  'drop',
  (e) => {
    if (!hasFiles(e) || appHandles(e)) return;
    e.preventDefault();
    e.stopPropagation();
    const pdf = [...e.dataTransfer.files].find((f) => /\.pdf$/i.test(f.name) || f.type === 'application/pdf');
    if (pdf) ipcRenderer.send('penfold:open-path', webUtils.getPathForFile(pdf));
  },
  true,
);
