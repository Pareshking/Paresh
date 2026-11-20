// Layout audit for a page of the terminal (owner, 20 Nov 2026: "Why doesn't your audit catch such issues?").
// The requirements check reads text; this one reads geometry, in the main page and in every chart frame:
//   1. a table column whose heading does not line up with its values (right-aligned numbers under a
//      left-aligned heading, or the reverse), measured from where the text is drawn;
//   2. a row label that wraps to three lines or more (the column is too narrow for its words);
//   3. a chart whose drawing leaves more than a fifth of its width empty, or whose readout takes
//      more than a quarter of the frame's height;
//   4. a bar track wider than 520 px (a bar across a whole desktop screen is hard to compare);
//   5. a frame taller than what it draws, an empty band of 48 px or more between blocks, and anything
//      wider than the screen.
// Usage: node scripts/layout_audit.mjs <url> [widths=412,1400] [--open]   exit 1 when anything is found.
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('playwright');

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
      const cells = body.map(r => r.cells[j]).filter(c => txt(c) && txt(c) !== '—');
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

const b = await chromium.launch(); let bad = 0;
for (const w of widths) {
  const p = await b.newPage({ viewport: { width: w, height: 900 } });
  await p.goto(url); await p.waitForSelector('.dh', { timeout: 240000 }); await p.waitForTimeout(8000);
  if (process.argv.includes('--open')) for (const s of await p.locator('[data-testid="stExpander"] summary').all()) { await s.click(); await p.waitForTimeout(2500); }
  const H = await p.evaluate(() => (document.querySelector('[data-testid="stMain"]') || document.scrollingElement).scrollHeight);
  await p.setViewportSize({ width: w, height: Math.min(H + 50, 16000) }); await p.waitForTimeout(4000);
  const found = [];
  for (const f of p.frames()) {
    const where = f === p.mainFrame() ? 'page' : (((await f.content().catch(() => '')).match(/render\("(\w+)"/) || [])[1] || null);
    if (!where) continue;
    for (const [k, d] of await f.evaluate(probe).catch(() => [])) found.push([where, k, d]);
    if (f !== p.mainFrame()) { const fe = await f.frameElement(); const fb = await fe.boundingBox();
      const inner = await f.evaluate(() => Math.round(document.getElementById('c').getBoundingClientRect().bottom));
      if (fb && fb.height - inner > 24) found.push([where, 'frame taller than its drawing', `${Math.round(fb.height - inner)} px spare`]); }
  }
  const gaps = await p.evaluate(() => {
    const main = document.querySelector('[data-testid="stMainBlockContainer"]') || document.querySelector('[data-testid="stMain"]');
    const els = [...main.querySelectorAll('.dh *, iframe, [data-testid="stExpander"], [data-testid="stButtonGroup"], [data-testid="stDownloadButton"]')]
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
