// Checks that two versions of a JavaScript file are the same program: it compares their syntax trees (what the engine
// understands), ignoring spaces, line breaks, positions and comments. Used to prove that formatting changed only the look.
// Usage: node tests/same-code.mjs <old.js> <new.js> [script|module]
import { parse } from 'espree';
import { readFileSync } from 'node:fs';
import { isDeepStrictEqual } from 'node:util';

const [a, b, sourceType = 'script'] = process.argv.slice(2);
const tree = (f) => {
  const ast = parse(readFileSync(f, 'utf8'), { ecmaVersion: 'latest', sourceType });
  // Drop positions and raw text: keep only the meaning
  return JSON.parse(
    JSON.stringify(ast, (k, v) => (['start', 'end', 'loc', 'range', 'raw'].includes(k) ? undefined : v)),
  );
};
const same = isDeepStrictEqual(tree(a), tree(b));
console.log(same ? `SAME PROGRAM: ${b}` : `DIFFERENT: ${a} vs ${b}`);
process.exit(same ? 0 : 1);
