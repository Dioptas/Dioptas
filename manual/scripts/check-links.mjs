// Check generated pages, downloads, assets, and fragment links under the manual
// base path. External sites and the app itself are outside this build's scope.
import { readFile, readdir, stat } from 'node:fs/promises';
import { resolve, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(fileURLToPath(new URL('../dist/', import.meta.url)));
const base = new URL(`https://dioptas.github.io${(process.env.DIOPTAS_MANUAL_BASE || '/Dioptas/manual').replace(/\/$/, '')}/`);
const pages = new Map();
async function visit(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) await visit(path);
    else if (entry.name.endsWith('.html')) pages.set(path, await readFile(path, 'utf8'));
  }
}
await visit(root);
const failures = [];
let checked = 0;
for (const [path, html] of pages) {
  const pageUrl = new URL(relative(root, path).split(sep).join('/'), base);
  // A generated 404 page's canonical URL need not have a directory route.
  const linkedHtml = html.replace(/<link\b[^>]*\brel="canonical"[^>]*>/g, '');
  for (const match of linkedHtml.matchAll(/\b(?:href|src)="([^"]+)"/g)) {
    const url = new URL(match[1].replaceAll('&amp;', '&'), pageUrl);
    if (url.origin !== base.origin || !url.pathname.startsWith(base.pathname)) continue;
    const target = resolve(root, '.' + decodeURIComponent(url.pathname.slice(base.pathname.length - 1)));
    if (target !== root && !target.startsWith(root + sep)) throw new Error('Manual link escaped output directory');
    let file = target;
    try {
      if ((await stat(file)).isDirectory()) file = resolve(file, 'index.html');
      await stat(file);
      if (url.hash && pages.has(file)) {
        const id = decodeURIComponent(url.hash.slice(1));
        const ids = [...pages.get(file).matchAll(/\bid="([^"]+)"/g)].map(m => m[1]);
        if (!ids.includes(id)) throw new Error(`Missing anchor: ${id}`);
      }
      checked++;
    } catch (error) {
      failures.push(`${relative(root, path)} → ${match[1]} (${error.message})`);
    }
  }
}
if (!pages.size) throw new Error('No generated manual pages found');
if (failures.length) throw new Error(`Broken manual links:\n${failures.join('\n')}`);
console.log(`Checked ${checked} local links across ${pages.size} generated HTML pages.`);
