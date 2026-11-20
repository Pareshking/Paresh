#!/usr/bin/env node
// Every row of a page's requirements list must be met by the page given:
//   node scripts/check_dashboard_requirements.mjs path/to/page.html [docs/<PAGE>_REQUIREMENTS.md]
// The list defaults to docs/DASHBOARD_REQUIREMENTS.md; its "Order:" line, when present, sets the section order.
// Renders the page in Chromium, reads its text, and checks each row's marker.
// Exit 1 when any row fails, listing them.
// A marker may name what must be done first, read after the page's own text:
//   [click Kite basket] Download basket CSV   -- tap the button or tab with that text, then read
//   [phone] On a wider screen                  -- read the page at 412 px wide
// A row whose condition the page cannot show today (e.g. an unranked holding) names the test that covers it.
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const docText = readFileSync(resolve(root, process.argv[3] || 'docs/DASHBOARD_REQUIREMENTS.md'), 'utf8');
const rows = docText.split('\n')
  .filter(l => /^\| \d+ \|/.test(l)).map(l => { const c = l.split(' | '); return {n: c[0].replace('| ', ''), req: c[1], marker: c[4].replace(/ \|$/, '').replace(/\\\|/g, '|').trim()}; });
const page = process.argv[2];
if (!page) { console.error('usage: check_dashboard_requirements.mjs <page.html | url>'); process.exit(2); }
const b = await chromium.launch();
const target = /^https?:/.test(page) ? page : 'file://' + resolve(page);
async function read(p) {
  let t = '';
  for (const f of p.frames()) {
    // Collapsed sections count: what a reader can open is on the page.
    try { t += await f.evaluate(() => { document.querySelectorAll('details').forEach(d => { d.open = true; }); return ''; }) + await f.evaluate(() => document.body.innerText + '\n' + [...document.querySelectorAll('summary,button,[aria-label]')].map(e => e.textContent + ' ' + (e.getAttribute('aria-label') || '')).join('\n')) + '\n'; } catch { /* a frame still loading */ }
  }
  return t;
}
async function open(width) {
  const p = await b.newPage({ viewport: { width, height: 900 } });
  await p.goto(target);
  await p.waitForSelector('.site, .dh, [data-testid="stMainBlockContainer"] h1', { timeout: 180000 }).catch(() => {}); await p.waitForTimeout(4000);
  return p;
}
const p = await open(1280);
// The page's text and every chart frame's (the Dashboard's charts are frames).
let text = await read(p), extra = {};
for (const r of rows) for (const m of r.marker.matchAll(/\[click ([^\]]+)\]/g)) extra[m[1]] = '';
for (const label of Object.keys(extra)) {
  try {
    const esc = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const btn = p.getByRole('button', { name: new RegExp(esc) }).or(p.getByRole('tab', { name: new RegExp(esc) })).or(p.getByText(label, { exact: true }));
    await btn.first().click({ timeout: 8000 }); await p.waitForTimeout(5000); extra[label] = await read(p); }
  catch { extra[label] = ''; }
}
let phone = '';
if (rows.some(r => r.marker.includes('[phone]'))) { const q = await open(412); phone = await read(q); }
await b.close();
// Kickers are upper-cased by CSS, so compare without case.
const low = text.toLowerCase();
// ' + ' joins texts that must all appear; '|' separates alternatives within each.
const seen = (m, where) => where.toLowerCase().includes(m.trim().toLowerCase());
const has = part => {
  const c = part.match(/^\s*\[click ([^\]]+)\]\s*(.*)$/), ph = part.match(/^\s*\[phone\]\s*(.*)$/);
  if (c) return c[2].split('|').some(m => seen(m, extra[c[1]] || ''));
  if (ph) return ph[1].split('|').some(m => seen(m, phone));
  return part.split('|').some(m => low.includes(m.trim().toLowerCase()));
};
const fails = rows.filter(r => !r.marker.split(' + ').every(has));
// The seven sections must appear in the agreed order.
const orderLine = docText.split('\n').find(l => l.startsWith('Order:'));
const isDashboard = !process.argv[3] || /DASHBOARD_REQUIREMENTS/.test(process.argv[3]);
// A page whose order is not yet agreed has no Order line: nothing to check (the Dashboard keeps its built-in order).
const order = orderLine ? orderLine.slice(6).split('→').map(x => x.trim().toLowerCase()) : !isDashboard ? [] :
  ['1 · the book this month', '2 · what happens on', '3 · is momentum still working?', '4 · money flows', '5 · size, and where momentum works', '6 · where the book is strong and weak', '7 · where leadership is moving', 'at a glance'];
let pos = 0, inOrder = true;
for (const o of order) { const i = low.indexOf(o, pos); if (i < 0) { inOrder = false; break; } pos = i + o.length; }
if (!inOrder) fails.push({n: 'order', req: 'sections in the agreed order', marker: order.join(' → ')});
console.log(`${rows.length + 1 - fails.length} of ${rows.length + 1} checks met (${rows.length} requirements and the section order)`);
for (const f of fails) console.log(`FAIL ${f.n}: ${f.req}  (marker: ${f.marker})`);
process.exit(fails.length ? 1 : 0);
