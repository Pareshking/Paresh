// Page style audit: the 8-rule sheet in docs/PAGE_DESIGN.md "Numbers and words" (S173; owner, 22 Nov 2026).
//
//   node scripts/number_format_audit.mjs [--report] http://localhost:8501/ [more URLs]
//
// Reads each page's text at 412 and 1400 px, chart frames included and collapsed sections opened, and checks
// what can be read off a page:
//   1/2/8  a ₹ figure with decimals (prices and ₹ Cr are whole rupees), a % with two or more decimals
//   3      a date written otherwise than "20 Nov 2026" / "20 Nov" (ISO, slashes, "Nov 20, 2026")
//   4      a hyphen-minus used as a minus sign ("-3.2%" for "−3.2%")
//   5      a missing value written "nan", "None", "NaN", or "—" alone in a table cell (the rule is "–")
//   6      a second word for one thing (see SYNONYMS)
//   7      no footer "Data to <date> · <source>"
// Not checkable from the text and so not checked: the explicit + on a change (rule 4), that a missing value's
// reason is in a footnote (rule 5), ranks and counts being whole (rule 8).
// Allowed, with the reason: a chart's scale note ("Each line is 0.25%"), statutory rates as the law writes them
// (stamp duty 0.015%). Ratios (beta 1.02, P/B 3.17), correlations and index levels (196.4) are not ₹ or %.
// Exit 1 on any finding, unless --report.
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('playwright');
import { settle } from './_settle.mjs';

const args = process.argv.slice(2);
const report = args.includes('--report');
const urls = args.filter(a => a !== '--report');
if (!urls.length) { console.error('usage: number_format_audit.mjs [--report] URL [URL ...]'); process.exit(2); }

// "pts = percentage points: …" is the glossary's own explainer (glossary 4), the one place the long form is right.
const ALLOWED = [/Each line is [\d.]+%/g, /stamp duty \(?[\d.]+%/gi, /pts = percentage points/g];
const MON = '(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)';
const RULES = {
  '1 ₹ with decimals': t => t.match(/₹\s?[\d,]*\d\.\d+(?!\d|\s?(?:lakh|crore))/g),   // ₹1.22 lakh Cr, ₹34.1 lakh are units, not paise
  '1 % with 2+ decimals': t => t.match(/[+−-]?\d+\.\d{2,}\s?%/g),
  '3 date format': t => t.match(new RegExp(`\\b20\\d\\d-\\d\\d-\\d\\d\\b|\\b\\d{1,2}/\\d{1,2}/20\\d\\d\\b|\\b${MON}[a-z]* \\d{1,2}, 20\\d\\d\\b`, 'g')),
  '4 hyphen as minus': t => t.match(/(?<![\w\d.])-(?=₹?\d)[₹\d][\d,.]*\s?(?:%|pts)?/g),
  '5 missing as nan/None': t => t.match(/(?:^|\t)(?:nan|NaN|None|null)(?=\t|$)|\bnan%/gm),   // a bare value, not the English word
  '6 synonym': t => t.match(/\b\d+ ?DMA\b|\bDMA\b|\bppts?\b|\bpercentage points\b|(?<!Nifty )\bTotal Market\b|\b(?:50|200)[- ]day (?:EMA|moving average)\b/g),
};
const SIZES = [412, 1400];

const b = await chromium.launch();
let bad = 0;
for (const url of urls) {
  for (const width of SIZES) {
    const p = await b.newPage({ viewport: { width, height: 900 } });
    await p.goto(url);
    await p.waitForSelector('.site, .dh, [data-testid="stMainBlockContainer"] h1', { timeout: 180000 }).catch(() => {});
    await settle(p);                 // Streamlit's run over, fonts in, frames still (S205)
    let t = '', emCells = 0;
    for (const f of p.frames()) {
      try {
        const r = await f.evaluate(() => {
          document.querySelectorAll('details').forEach(d => { d.open = true; });
          const cells = [...document.querySelectorAll('td')].filter(td => td.innerText.trim() === '—').length;
          return [document.body.innerText, cells];
        });
        t += r[0] + '\n'; emCells += r[1];
      } catch { /* a frame still loading */ }
    }
    for (const re of ALLOWED) t = t.replace(re, '');
    const found = {};
    for (const [rule, fn] of Object.entries(RULES)) {
      const m = [...new Set(fn(t) || [])];
      if (m.length) found[rule] = m;
    }
    if (emCells) found['5 "—" in a table cell'] = [`${emCells} cell(s)`];
    // The Guide holds no data, so it has no data date (rule 7 is for pages that show data).
    if (!/\/guide\b/.test(url) && !new RegExp(`Data to \\d{1,2} ${MON} 20\\d\\d · \\S`).test(t)) found['7 footer'] = ['no "Data to <date> · <source>"'];
    if (/Screener and NSE|Data from: |Ranked from: /.test(t)) found['7 source named'] = ['a vendor or internal source named (owner, 20-21 Nov: no source names)'];
    const n = Object.values(found).reduce((a, m) => a + m.length, 0);
    bad += n;
    console.log(`${url} @${width}: ${n ? n + ' found' : 'clean'}`);
    for (const [rule, m] of Object.entries(found)) console.log(`  rule ${rule}: ${m.slice(0, 10).join(' | ')}${m.length > 10 ? ` (+${m.length - 10})` : ''}`);
    await p.close();
  }
}
await b.close();
process.exit(bad && !report ? 1 : 0);
