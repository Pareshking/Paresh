#!/usr/bin/env node
// Every row of a page's requirements list must be met by the page given:
//   node scripts/check_dashboard_requirements.mjs path/to/page.html [docs/<PAGE>_REQUIREMENTS.md]
// The list defaults to docs/DASHBOARD_REQUIREMENTS.md; its "Order:" line, when present, sets the section order.
// Renders the page in Chromium, reads its text, and checks each row's marker.
// Exit 1 when any row fails, listing them.
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const docText = readFileSync(resolve(root, process.argv[3] || 'docs/DASHBOARD_REQUIREMENTS.md'), 'utf8');
const rows = docText.split('\n')
  .filter(l => /^\| \d+ \|/.test(l)).map(l => { const c = l.split(' | '); return {n: c[0].replace('| ', ''), req: c[1], marker: c[4].replace(/ \|$/, '').trim()}; });
const page = process.argv[2];
if (!page) { console.error('usage: check_dashboard_requirements.mjs <page.html | url>'); process.exit(2); }
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
await p.goto(/^https?:/.test(page) ? page : 'file://' + resolve(page));
await p.waitForSelector('.site, .dh', { timeout: 180000 }).catch(() => {}); await p.waitForTimeout(3000);
// The page's text and every chart frame's (the Dashboard's charts are frames).
let text = '';
for (const f of p.frames()) {
  try { text += await f.evaluate(() => document.body.innerText + '\n' + [...document.querySelectorAll('summary,button,[aria-label]')].map(e => e.textContent + ' ' + (e.getAttribute('aria-label') || '')).join('\n')) + '\n'; } catch { /* a frame still loading */ }
}
await b.close();
// Kickers are upper-cased by CSS, so compare without case.
const low = text.toLowerCase();
const fails = rows.filter(r => !r.marker.split('|').some(m => low.includes(m.trim().toLowerCase())));
// The seven sections must appear in the agreed order.
const orderLine = docText.split('\n').find(l => l.startsWith('Order:'));
const order = orderLine ? orderLine.slice(6).split('→').map(x => x.trim().toLowerCase()) :
  ['1 · the book this month', '2 · what happens on', '3 · is momentum still working?', '4 · money flows', '5 · size, and where momentum works', '6 · where the book is strong and weak', '7 · where leadership is moving', 'at a glance'];
let pos = 0, inOrder = true;
for (const o of order) { const i = low.indexOf(o, pos); if (i < 0) { inOrder = false; break; } pos = i + o.length; }
if (!inOrder) fails.push({n: 'order', req: 'sections in the agreed order', marker: order.join(' → ')});
console.log(`${rows.length + 1 - fails.length} of ${rows.length + 1} checks met (${rows.length} requirements and the section order)`);
for (const f of fails) console.log(`FAIL ${f.n}: ${f.req}  (marker: ${f.marker})`);
process.exit(fails.length ? 1 : 0);
