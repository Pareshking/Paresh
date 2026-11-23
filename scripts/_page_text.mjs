// One page read for the text audits (S205 step 2, 23 Nov 2026): number_format_audit.mjs and glossary_audit.mjs
// read the same nine pages at the same two widths. The number audit saves what it read (--save DIR) and the
// glossary audit reads it back (--cache DIR) instead of loading each page a second time.
import { mkdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { settle } from './_settle.mjs';

// The page's text in every frame, collapsed sections opened. Two copies:
//   raw       document text as shown (the number audit's input);
//   glossary  the same with the cells of a column headed "NSE index" emptied, the one place the short form of
//             an index name is allowed (glossary 3). Columns are counted on the header's last row, colspans
//             included (the Screener has a group row above it).
// emCells: table cells holding "—" alone (number rule 5).
export async function readPageText(browser, url, width) {
  const p = await browser.newPage({ viewport: { width, height: 900 } });
  await p.goto(url);
  await p.waitForSelector('.site, .dh, [data-testid="stMainBlockContainer"] h1', { timeout: 180000 }).catch(() => {});
  await settle(p);                 // Streamlit's run over, fonts in, frames still (S205)
  let raw = '', glossary = '', emCells = 0;
  for (const f of p.frames()) {
    try {
      const r = await f.evaluate(() => {
        document.querySelectorAll('details').forEach(d => { d.open = true; });
        const cells = [...document.querySelectorAll('td')].filter(td => td.innerText.trim() === '—').length;
        const before = document.body.innerText;
        const at = (tr, col) => { let i = 0; for (const c of tr.children) { i += c.colSpan || 1; if (i > col) return c; } return null; };
        for (const table of document.querySelectorAll('table')) {
          const rows = table.querySelectorAll('thead tr');
          if (!rows.length) continue;
          let col = -1, i = 0;
          for (const c of rows[rows.length - 1].children) {
            if (c.innerText.replace(/[↕↑↓]/g, '').trim() === 'NSE index') { col = i; break; }
            i += c.colSpan || 1;
          }
          if (col < 0) continue;
          for (const tr of table.querySelectorAll('tbody tr')) { const c = at(tr, col); if (c) c.textContent = ''; }
        }
        return [before, document.body.innerText, cells];
      });
      raw += r[0] + '\n'; glossary += r[1] + '\n'; emCells += r[2];
    } catch { /* a frame still loading */ }
  }
  await p.close();
  return { raw, glossary, emCells };
}

const file = (dir, url, width) => join(dir, `${encodeURIComponent(url)}@${width}.json`);

export function savePageText(dir, url, width, text) {
  mkdirSync(dir, { recursive: true });
  writeFileSync(file(dir, url, width), JSON.stringify(text));
}

// The saved read of this page at this width, or null when there is none (then the caller loads the page).
export function cachedPageText(dir, url, width) {
  if (!dir) return null;
  const f = file(dir, url, width);
  return existsSync(f) ? JSON.parse(readFileSync(f, 'utf8')) : null;
}
