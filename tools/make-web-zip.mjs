// Builds the browser version: dist/penfold_<version>-web.zip, with a folder penfold-<version>/ that holds what the
// app needs to run (index.html, css/, js/, vendor/, assets/) and the licence files. Unzipped, index.html opens with a
// double click, without a network connection.
// Run with: npm run dist:web   (npm run dist also runs it). Writes the zip itself, with Node's zlib: no extra tools.
import { readFileSync, readdirSync, statSync, mkdirSync, writeFileSync } from 'node:fs';
import { deflateRawSync, crc32 } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const { version } = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8'));
const INCLUDE = ['index.html', 'css', 'js', 'vendor', 'assets', 'LICENSE', 'THIRD-PARTY-NOTICES.md'];
const TOP = `penfold-${version}/`;

// Every file under a path, as paths relative to the project, in a fixed order
const walk = (p) =>
  statSync(join(ROOT, p)).isDirectory()
    ? readdirSync(join(ROOT, p))
        .sort()
        .flatMap((n) => walk(`${p}/${n}`))
    : [p];

// Date and time in the format zip files use (MS-DOS), from the file's modification time
function dosTime(d) {
  return {
    time: (d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1),
    date: ((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate(),
  };
}

const parts = [],
  central = [];
let offset = 0;
for (const file of INCLUDE.flatMap(walk)) {
  const data = readFileSync(join(ROOT, file)),
    packed = deflateRawSync(data, { level: 9 }),
    name = Buffer.from(TOP + file, 'utf8'),
    { time, date } = dosTime(statSync(join(ROOT, file)).mtime),
    crc = crc32(data);
  // Local header (30 bytes), then the name and the compressed data
  const local = Buffer.alloc(30);
  local.writeUInt32LE(0x04034b50, 0);
  local.writeUInt16LE(20, 4); // version needed: 2.0
  local.writeUInt16LE(0x0800, 6); // names in UTF-8
  local.writeUInt16LE(8, 8); // deflate
  local.writeUInt16LE(time, 10);
  local.writeUInt16LE(date, 12);
  local.writeUInt32LE(crc, 14);
  local.writeUInt32LE(packed.length, 18);
  local.writeUInt32LE(data.length, 22);
  local.writeUInt16LE(name.length, 26);
  parts.push(local, name, packed);
  // Entry for the central directory at the end of the file (46 bytes, then the name)
  const entry = Buffer.alloc(46);
  entry.writeUInt32LE(0x02014b50, 0);
  entry.writeUInt16LE((3 << 8) | 20, 4); // made on Unix, version 2.0
  entry.writeUInt16LE(20, 6);
  entry.writeUInt16LE(0x0800, 8);
  entry.writeUInt16LE(8, 10);
  entry.writeUInt16LE(time, 12);
  entry.writeUInt16LE(date, 14);
  entry.writeUInt32LE(crc, 16);
  entry.writeUInt32LE(packed.length, 20);
  entry.writeUInt32LE(data.length, 24);
  entry.writeUInt16LE(name.length, 28);
  entry.writeUInt32LE((0o100644 << 16) >>> 0, 38); // a normal file, readable by everyone
  entry.writeUInt32LE(offset, 42);
  central.push(entry, name);
  offset += local.length + name.length + packed.length;
}
const dir = Buffer.concat(central),
  end = Buffer.alloc(22);
end.writeUInt32LE(0x06054b50, 0);
end.writeUInt16LE(central.length / 2, 8);
end.writeUInt16LE(central.length / 2, 10);
end.writeUInt32LE(dir.length, 12);
end.writeUInt32LE(offset, 16);

mkdirSync(join(ROOT, 'dist'), { recursive: true });
const out = join(ROOT, 'dist', `penfold_${version}-web.zip`);
writeFileSync(out, Buffer.concat([...parts, dir, end]));
console.log(`${out}: ${central.length / 2} files`);
