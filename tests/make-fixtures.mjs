// Builds the PDF files used by the tests (tests/fixtures/). They are invented documents, so no real file is ever needed.
// Run with: npm run fixtures   (needs qpdf installed for the protected PDFs)
import { PDFDocument, StandardFonts, PDFName, PDFString, PDFHexString, rgb } from 'pdf-lib';
import { writeFileSync, mkdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const OUT = join(dirname(fileURLToPath(import.meta.url)), 'fixtures');
mkdirSync(OUT, { recursive: true });
const FIXED_DATE = new Date('2026-01-01T00:00:00Z');

async function newDoc(title) {
  const d = await PDFDocument.create({ updateMetadata: false });
  d.setTitle(title);
  d.setProducer('Penfold test fixtures');
  d.setCreator('Penfold test fixtures');
  d.setCreationDate(FIXED_DATE);
  d.setModificationDate(FIXED_DATE);
  return d;
}
const save = async (d, name) => {
  writeFileSync(join(OUT, name), await d.save({ useObjectStreams: false }));
  return join(OUT, name);
};

// A page with a heading and some paragraphs of plain text (selectable and searchable)
function textPage(d, font, bold, n, size = [595.28, 841.89]) {
  const p = d.addPage(size),
    h = size[1];
  p.drawText('Page ' + n + ' heading', { x: 72, y: h - 90, size: 22, font: bold });
  const lines = [
    'The quick brown fox jumps over the lazy dog.',
    'Penfold reads, annotates and organises PDF files.',
    'Searching ignores accents: cancion and canción match.',
    'Marker word on page ' + n + ': lighthouse' + n + '.',
  ];
  lines.forEach((t, i) => p.drawText(t, { x: 72, y: h - 140 - i * 22, size: 13, font, color: rgb(0.1, 0.1, 0.1) }));
  p.drawRectangle({ x: 72, y: h - 400, width: 200, height: 120, borderColor: rgb(0.2, 0.4, 0.8), borderWidth: 2 });
  return p;
}

// Writes an outline (bookmarks) tree by hand: items = [{title, page, y?, items?}]
function addOutline(d, items) {
  const ctx = d.context,
    pages = d.getPages(),
    root = ctx.nextRef();
  const count = (l) => l.reduce((n, i) => n + 1 + count(i.items || []), 0);
  const write = (list, parent) => {
    const refs = list.map(() => ctx.nextRef());
    list.forEach((it, i) => {
      const dest =
        it.y != null
          ? [pages[it.page].ref, PDFName.of('XYZ'), null, it.y, null]
          : [pages[it.page].ref, PDFName.of('Fit')];
      const o = { Title: PDFHexString.fromText(it.title), Parent: parent, Dest: dest };
      if (i > 0) o.Prev = refs[i - 1];
      if (i < list.length - 1) o.Next = refs[i + 1];
      if (it.items && it.items.length) {
        const k = write(it.items, refs[i]);
        o.First = k[0];
        o.Last = k[k.length - 1];
        o.Count = count(it.items);
      }
      ctx.assign(refs[i], ctx.obj(o));
    });
    return refs;
  };
  const top = write(items, root);
  ctx.assign(root, ctx.obj({ Type: 'Outlines', First: top[0], Last: top[top.length - 1], Count: count(items) }));
  d.catalog.set(PDFName.of('Outlines'), root);
}

async function main() {
  // 1. text.pdf: three pages (the second one landscape)
  {
    const d = await newDoc('Text fixture'),
      f = await d.embedFont(StandardFonts.Helvetica),
      b = await d.embedFont(StandardFonts.HelveticaBold);
    textPage(d, f, b, 1);
    textPage(d, f, b, 2, [841.89, 595.28]);
    textPage(d, f, b, 3);
    await save(d, 'text.pdf');
  }
  // 2. outline.pdf: four pages and a nested outline (one item with an /XYZ destination)
  {
    const d = await newDoc('Outline fixture'),
      f = await d.embedFont(StandardFonts.Helvetica),
      b = await d.embedFont(StandardFonts.HelveticaBold);
    for (let i = 1; i <= 4; i++) textPage(d, f, b, i);
    addOutline(d, [
      { title: 'Introduction', page: 0 },
      {
        title: 'Chapter one',
        page: 1,
        items: [
          { title: 'Section 1.1', page: 1, y: 500 },
          { title: 'Section 1.2 — café', page: 2 },
        ],
      },
      { title: 'Appendix', page: 3 },
    ]);
    await save(d, 'outline.pdf');
  }
  // 3. form.pdf: text field, multi-line field, checkbox, radio group and dropdown
  {
    const d = await newDoc('Form fixture'),
      f = await d.embedFont(StandardFonts.Helvetica),
      p = d.addPage([595.28, 841.89]),
      form = d.getForm();
    const label = (t, y) => p.drawText(t, { x: 72, y, size: 12, font: f });
    label('Name:', 740);
    const name = form.createTextField('name');
    name.addToPage(p, { x: 180, y: 732, width: 250, height: 22, font: f });
    label('Notes:', 690);
    const notes = form.createTextField('notes');
    notes.enableMultiline();
    notes.addToPage(p, { x: 180, y: 620, width: 250, height: 80, font: f });
    label('Agree:', 580);
    const agree = form.createCheckBox('agree');
    agree.addToPage(p, { x: 180, y: 576, width: 16, height: 16 });
    label('Size:', 540);
    const size = form.createRadioGroup('size');
    size.addOptionToPage('small', p, { x: 180, y: 536, width: 16, height: 16 });
    size.addOptionToPage('large', p, { x: 240, y: 536, width: 16, height: 16 });
    label('Colour:', 500);
    const col = form.createDropdown('colour');
    col.addOptions(['Red', 'Green', 'Blue']);
    col.addToPage(p, { x: 180, y: 492, width: 150, height: 22, font: f });
    form.updateFieldAppearances(f);
    await save(d, 'form.pdf');
  }
  // 4. foreign.pdf: annotations made by "another program" (shown read-only by Penfold)
  {
    const d = await newDoc('Foreign annotations fixture'),
      f = await d.embedFont(StandardFonts.Helvetica),
      b = await d.embedFont(StandardFonts.HelveticaBold);
    const p = textPage(d, f, b, 1),
      ctx = d.context,
      h = 841.89;
    const annots = [
      {
        Type: 'Annot',
        Subtype: 'Highlight',
        Rect: [72, h - 145, 330, h - 128],
        QuadPoints: [72, h - 128, 330, h - 128, 72, h - 145, 330, h - 145],
        C: [0, 1, 0],
        T: PDFString.of('Alice'),
        Contents: PDFHexString.fromText('Foreign highlight'),
      },
      {
        Type: 'Annot',
        Subtype: 'Text',
        Rect: [400, h - 200, 420, h - 180],
        C: [1, 1, 0],
        T: PDFString.of('Bob'),
        Contents: PDFHexString.fromText('Foreign comment'),
      },
      {
        Type: 'Annot',
        Subtype: 'FreeText',
        Rect: [300, h - 420, 500, h - 380],
        C: [1, 1, 1],
        DA: PDFString.of('/Helv 11 Tf 0 g'),
        Contents: PDFHexString.fromText('Foreign text box'),
      },
      { Type: 'Annot', Subtype: 'Square', Rect: [380, h - 330, 300, h - 260], C: [0, 0, 1], T: PDFString.of('Alice') },
    ];
    p.node.set(PDFName.of('Annots'), ctx.obj(annots.map((a) => ctx.register(ctx.obj(a)))));
    await save(d, 'foreign.pdf');
  }
  // 5. Protected PDFs (owner password, no open password), old style and with object streams
  const text = join(OUT, 'text.pdf');
  execFileSync('qpdf', [
    '--encrypt',
    '',
    'owner-secret',
    '256',
    '--modify=none',
    '--',
    text,
    join(OUT, 'protected.pdf'),
  ]);
  execFileSync('qpdf', [
    '--object-streams=generate',
    '--encrypt',
    '',
    'owner-secret',
    '256',
    '--modify=none',
    '--',
    text,
    join(OUT, 'protected-objstm.pdf'),
  ]);
  console.log('Fixtures written to', OUT);
}
main().catch((e) => {
  console.error(e);
  process.exit(1);
});
