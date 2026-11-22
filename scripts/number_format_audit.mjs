// Number format audit (S173; owner, 22 Nov 2026: "price etc, Moving averages etc should be in round numbers,
// return only with Max one decimal values like 11.1% not 11.11%").
//
//   node scripts/number_format_audit.mjs http://localhost:8501/ [more URLs]
//
// Reads each page's text, chart frames included and collapsed sections opened, and fails on
//  - a rupee figure of ₹100 or more with paise (whole rupees above ₹100; below, two decimals are the rule), and
//  - a percentage with two or more decimals.
// Allowed, with the reason: a chart's scale note ("Each line is 0.25%"), and statutory rates written as the law
// writes them (stamp duty 0.015%). Ratios (beta 1.02, P/B 3.17), correlations, ranks and counts are not checked.
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('playwright');

const urls = process.argv.slice(2);
if (!urls.length) { console.error('usage: number_format_audit.mjs URL [URL ...]'); process.exit(2); }
const ALLOWED = [/Each line is [\d.]+%/g, /stamp duty \(?[\d.]+%/gi, /stamp duty [\d.]+%/gi];
const b = await chromium.launch();
let bad = 0;
for (const url of urls) {
  const p = await b.newPage({ viewport: { width: 1400, height: 900 } });
  await p.goto(url);
  await p.waitForSelector('.site, .dh, [data-testid="stMainBlockContainer"] h1', { timeout: 180000 }).catch(() => {});
  // Until Streamlit finishes the run (Backtest draws its long calculation after the title).
  for (let i = 0, quiet = 0; i < 240 && quiet < 3; i++) {
    const busy = await p.evaluate(() => !!document.querySelector('[data-testid="stStatusWidget"]')).catch(() => false);
    quiet = busy ? 0 : quiet + 1; await p.waitForTimeout(1000);
  }
  await p.waitForTimeout(3000);
  let t = '';
  for (const f of p.frames()) {
    try { t += await f.evaluate(() => { document.querySelectorAll('details').forEach(d => { d.open = true; }); return document.body.innerText; }) + '\n'; }
    catch { /* a frame still loading */ }
  }
  for (const re of ALLOWED) t = t.replace(re, '');
  const rupee = [...new Set((t.match(/₹\s?[\d,]+\.\d+/g) || []).filter(s => parseFloat(s.replace(/[₹,\s]/g, '')) >= 100))];
  const pct = [...new Set(t.match(/[+−-]?\d+\.\d{2,}\s?%/g) || [])];
  const n = rupee.length + pct.length;
  bad += n;
  console.log(`${url}: ${n ? n + ' found' : 'clean'}`);
  if (rupee.length) console.log('  ₹100+ with paise: ' + rupee.slice(0, 12).join(' | '));
  if (pct.length) console.log('  % with 2+ decimals: ' + pct.slice(0, 12).join(' | '));
  await p.close();
}
await b.close();
process.exit(bad ? 1 : 0);
