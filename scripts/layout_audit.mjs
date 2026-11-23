// Layout audit for a page of the terminal (owner, 20 Nov 2026: "Why doesn't your audit catch such issues?").
// The requirements check reads text; this one reads geometry, in the main page and in every chart frame:
//   1. a table column whose heading does not line up with its values (right-aligned numbers under a
//      left-aligned heading, or the reverse), measured from where the text is drawn;
//   2. a row label that wraps to three lines or more (the column is too narrow for its words);
//   3. a chart whose drawing leaves more than a fifth of its width empty, or whose readout takes
//      more than a quarter of the frame's height;
//   4. a bar track wider than 520 px (a bar across a whole desktop screen is hard to compare);
//   5. a frame taller than what it draws, an empty band of 48 px or more between blocks, and anything
//      wider than the screen;
//   6. (S193 H5) a time-range chart that opens off the range its spec states (the pressed chip, or the first
//      date drawn), a chart with no readout at rest, and a Streamlit period picker (3M / 12M / 3Y / All
//      buttons on the page: one period picker, and it is in the chart).
// Usage: node scripts/layout_audit.mjs <url> [widths=412,1400] [--open]   exit 1 when anything is found.
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('playwright');
import { settle, framesStill } from './_settle.mjs';

const url = process.argv[2] || 'http://localhost:8501/portfolio';
const widths = (process.argv.find(a => /^\d+(,\d+)*$/.test(a)) || '412,1400').split(',').map(Number);

function probe() {
  const out = [];
  const txt = el => (el.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 40);
  const box = el => { const rs = []; const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);   // text hidden for screen readers is skipped
    for (let n = w.nextNode(); n; n = w.nextNode()) { if (!n.textContent.trim() || n.parentElement.closest('.vh')) continue;
      const r = document.createRange(); r.selectNodeContents(n); rs.push(...[...r.getClientRects()].filter(q => q.width > 0)); }
    if (!rs.length) return null; return { l: Math.min(...rs.map(q => q.left)), r: Math.max(...rs.map(q => q.right)) }; };
  const visible = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'; };
  // 1, 2: tables
  for (const t of document.querySelectorAll('table')) {
    if (!visible(t)) continue;
    const head = t.tHead && t.tHead.rows[t.tHead.rows.length - 1]; if (!head) continue;
    const body = [...(t.tBodies[0]?.rows || [])].filter(r => r.cells.length === head.cells.length);
    [...head.cells].forEach((th, j) => {
      if (!txt(th) || th.colSpan > 1) return;
      const cells = body.map(r => r.cells[j]).filter(c => txt(c) && txt(c) !== '—' && txt(c) !== '–');
      if (cells.length < 2) return;
      const hb = box(th), cb = cells.map(box).filter(Boolean); if (!hb || !cb.length) return;
      const al = c => { const a = getComputedStyle(c).textAlign; return a === 'right' || a === 'end' ? 'right' : a === 'center' ? 'center' : 'left'; };
      const kinds = cells.map(al), side = kinds.filter(k => k === 'right').length * 2 > kinds.length ? 'right' : kinds.filter(k => k === 'center').length * 2 > kinds.length ? 'center' : 'left';
      const rs = cb.map(b => b.r), ls = cb.map(b => b.l);
      if (side === 'right' && Math.abs(hb.r - Math.max(...rs)) > 3) out.push(['heading not over its numbers', `${txt(th)}: heading ends ${Math.round(hb.r)}, values end ${Math.round(Math.max(...rs))}`]);
      if (side === 'left' && Math.abs(hb.l - Math.min(...ls)) > 3) out.push(['heading not over its column', `${txt(th)}: heading starts ${Math.round(hb.l)}, values start ${Math.round(Math.min(...ls))}`]);
      if (side === 'center' && Math.abs((hb.l + hb.r) / 2 - (Math.min(...ls) + Math.max(...rs)) / 2) > 4) out.push(['heading not centred on its column', txt(th)]);
      if (side === 'left' && cells.length >= 3 && cells.filter(c => /^[−+\-#\d₹.,% ]+%?$/.test(txt(c))).length * 2 > cells.length)
        out.push(['numbers set left', `${txt(th)}: figures should line up on the right`]);
    });
    for (const r of body) { const c = r.cells[0]; if (!c) continue; const lh = parseFloat(getComputedStyle(c).lineHeight) || 18;
      const b = document.createRange(); b.selectNodeContents(c.firstChild || c); const lines = new Set([...b.getClientRects()].map(q => Math.round(q.top))).size;
      if (lines >= 3) out.push(['row label wraps', `${txt(c)} takes ${lines} lines`]); }
  }
  // 3: charts in this document
  for (const svg of document.querySelectorAll('.chart svg')) {
    if (!visible(svg)) continue; const sb = svg.getBoundingClientRect();
    const marks = [...svg.querySelectorAll('path,rect')].map(e => e.getBoundingClientRect()).filter(q => q.width > 0);
    if (!marks.length) continue;
    const used = Math.max(...marks.map(q => q.right)) - Math.min(...marks.map(q => q.left));
    if (used / sb.width < 0.8) out.push(['chart leaves width empty', `drawing uses ${Math.round(used)} of ${Math.round(sb.width)} px`]);
  }
  const ro = document.querySelector('.readout'), card = document.getElementById('c');
  if (ro && card && visible(ro) && document.querySelector('.chart svg') && ro.getBoundingClientRect().height > 0.25 * card.getBoundingClientRect().height)
    out.push(['readout crowds the chart', `${Math.round(ro.getBoundingClientRect().height)} of ${Math.round(card.getBoundingClientRect().height)} px`]);
  // 4: bar tracks
  for (const el of document.querySelectorAll('.pf-ibar, .dh-ibar, .tt')) if (visible(el) && el.getBoundingClientRect().width > 520)
    out.push(['bar track too wide', `${Math.round(el.getBoundingClientRect().width)} px`]);
  // 5: wider than the screen
  const sw = document.documentElement.scrollWidth; if (sw > innerWidth + 1) out.push(['wider than the screen', `${sw} > ${innerWidth}`]);
  return out;
}

// 6. In a chart frame, before any pointer or key: the range it opened on, and its readout.
function chartProbe(kind) {
  const out = [];
  const el = document.getElementById('c') || document.getElementById('root'); if (!el) return out;
  const d = el.dataset;
  if (d.rangeDefault) {
    const want = String(d.rangeDefault).toLowerCase();
    const pressed = [...document.querySelectorAll('[aria-label="Period"] .chip[aria-pressed="true"], .rg button[aria-pressed="true"]')].map(b => b.textContent.trim().toLowerCase());
    if (pressed.length && !pressed.includes(want)) out.push(['chart opens off its stated range', `${kind}: the pressed chip is ${pressed.join(',')}, the spec says ${d.rangeDefault}`]);
    const m = /^(\d+)([MY])$/i.exec(d.rangeDefault), n = m ? (+m[1]) * (m[2].toUpperCase() === 'Y' ? 12 : 1) : 0;
    let ok = true, why = '';
    if (!n) { ok = d.rangeFrom === d.rangeFirst; why = `draws from ${d.rangeFrom}, its data from ${d.rangeFirst}`; }
    else { const [y, mo, dd] = d.rangeTo.split('-').map(Number); let k = (mo - 1) - n, yy = y + Math.floor(k / 12); k = ((k % 12) + 12) % 12;
      const target = Date.UTC(yy, k, Math.min(dd, new Date(Date.UTC(yy, k + 1, 0)).getUTCDate()));
      const from = Date.parse(d.rangeFrom + 'T00:00:00Z'), first = Date.parse(d.rangeFirst + 'T00:00:00Z');
      ok = Math.abs(from - target) <= 7 * 864e5 || (first > target && d.rangeFrom === d.rangeFirst);
      why = `draws from ${d.rangeFrom}, ${d.rangeDefault} before ${d.rangeTo} is ${new Date(target).toISOString().slice(0, 10)}`; }
    if (!ok) out.push(['chart opens off its stated range', `${kind}: ${why}`]);
  }
  if (['holdings', 'history', 'stable'].includes(kind)) return out;
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && !e.closest('[hidden]'); };
  const reads = kind === 'lw' ? [...document.querySelectorAll('.lg')].slice(0, 1) : [...el.querySelectorAll('.readout, .ph')].filter(vis);
  for (const r of reads) { const t = (r.innerText || '').trim();
    if (!/\d/.test(t) || (kind === 'lw' && !/(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)/.test(t)))
      out.push(['chart has no readout at rest', `${kind}: "${t.slice(0, 40)}"`]); }
  return out;
}
const pickers = () => [...document.querySelectorAll('[data-testid="stButtonGroup"]')].map(g => [...g.querySelectorAll('button')].map(b => b.innerText.trim()))
  .filter(t => t.length > 1 && t.every(x => /^(\d+[MY]|All)$/.test(x))).map(t => ['period picker outside the chart', t.join(' · ')]);

const b = await chromium.launch(); let bad = 0;
for (const w of widths) {
  const p = await b.newPage({ viewport: { width: w, height: 900 } });
  await p.goto(url); await p.waitForSelector('.dh, .qp-head, .scr-head', { timeout: 240000 }); await settle(p);
  if (process.argv.includes('--open')) { for (const s of await p.locator('[data-testid="stExpander"] summary').all()) await s.click(); await settle(p); }
  const H = await p.evaluate(() => (document.querySelector('[data-testid="stMain"]') || document.scrollingElement).scrollHeight);
  await p.setViewportSize({ width: w, height: Math.min(H + 50, 16000) }); await framesStill(p);
  const found = [];
  for (const f of p.frames()) {
    const html = f === p.mainFrame() ? '' : await f.content().catch(() => '');
    const where = f === p.mainFrame() ? 'page' : ((html.match(/render\("(\w+)"/) || [])[1] || (/const ONE_LINE=/.test(html) ? 'lw' : null));
    if (!where) continue;
    if (where !== 'lw') for (const [k, d] of await f.evaluate(probe).catch(() => [])) found.push([where, k, d]);
    for (const [k, d] of await f.evaluate(where === 'page' ? pickers : chartProbe, where).catch(() => [])) found.push([where, k, d]);
    if (where === 'lw') continue;
    if (f !== p.mainFrame()) { const fe = await f.frameElement();
      // A frame is sized by Streamlit from its first drawing, which can be in the fallback font; it shrinks
      // once the web font has loaded. Measure again after a pause before calling it too tall.
      const spare = async () => { const fb = await fe.boundingBox();
        const inner = await f.evaluate(() => Math.round(document.getElementById('c').getBoundingClientRect().bottom));
        return fb ? Math.round(fb.height - inner) : 0; };
      let sp = await spare();
      if (sp > 24) { await framesStill(p, { same: 3 }); sp = await spare(); }
      if (sp > 24) found.push([where, 'frame taller than its drawing', `${sp} px spare`]); }
  }
  const gaps = await p.evaluate(() => {
    const main = document.querySelector('[data-testid="stMainBlockContainer"]') || document.querySelector('[data-testid="stMain"]');
    const els = [...main.querySelectorAll('.dh *, iframe, [data-testid="stExpander"], [data-testid="stButtonGroup"], [data-testid="stDownloadButton"], [data-testid="stHtml"] > * > *, [data-testid="stElementContainer"], [data-testid="stPopover"]')]
      .filter(e => !e.checkVisibility || e.checkVisibility())   // a closed expander's contents are measured but not seen
      .map(e => e.getBoundingClientRect()).filter(r => r.height > 0 && r.width > 0).map(r => [r.top + scrollY, r.bottom + scrollY]);
    const top = Math.min(...els.map(e => e[0])), bot = Math.max(...els.map(e => e[1]));
    const cover = new Uint8Array(Math.ceil(bot) + 2); for (const [t, b] of els) for (let y = Math.floor(t); y < Math.ceil(b); y++) cover[y] = 1;
    const out = []; let s = -1;
    for (let y = Math.floor(top); y <= bot; y++) { if (!cover[y] && s < 0) s = y; if (cover[y] && s >= 0) { if (y - s >= 48) out.push(`${y - s} px empty at y=${s}`); s = -1; } }
    const end = main.getBoundingClientRect().bottom + scrollY - bot; if (end > 80) out.push(`${Math.round(end)} px empty after the last block`);
    return out; });
  for (const g of gaps) found.push(['page', 'empty band', g]);
  const seen = new Set();
  for (const f of found) { const k = f.join('|'); if (seen.has(k)) continue; seen.add(k); console.log(w, ...f); bad++; }
  console.log(w, found.length ? `${seen.size} layout findings` : 'clean');
  await p.close();
}
await b.close(); process.exit(bad ? 1 : 0);
