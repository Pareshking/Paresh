// Glossary audit: the "Not" column of docs/GLOSSARY.md in every page's rendered text (S193 item D; owner, 23 Nov 2026).
//
//   node scripts/glossary_audit.mjs [--report] URL [URL ...]        pages at 412 and 1400 px, chart frames included
//   node scripts/glossary_audit.mjs [--report] --files a.txt b.txt   text already read off pages (a negative control)
//
// A page's text is read as number_format_audit.mjs reads it (every frame, collapsed sections opened). Cells of a table
// column headed "NSE index" are left out first: that is the one place the short form of an index name is allowed
// (glossary 3). Then each rule below is a finding; ALLOW removes text first, each entry with its reason. Never add to
// ALLOW silently: say why in the entry, and in the pull request.
// Not checkable from text and so not checked here: rounding (glossary 12; tests/test_rounding_parity.py), whether a
// "sector" really is one of NSE's 22 groups, and whether "points" sits in a sentence rather than a figure.
// Exit 1 on any finding, unless --report.
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';

const args = process.argv.slice(2);
const report = args.includes('--report');
const fromFiles = args.includes('--files');
const targets = args.filter(a => !a.startsWith('--'));
if (!targets.length) { console.error('usage: glossary_audit.mjs [--report] URL ... | --files FILE ...'); process.exit(2); }

// Text taken out before the rules run. Each entry: what, where (a URL or file-name pattern, or null for every page), why.
const ALLOW = [
  { re: /\bProcess Industries\b/g, where: null,
    why: "a TradingView sector's proper name, shown where NSE gives a stock no sector (the mix of taxonomies is an S193 item A/B question, not a wording one)" },
  { re: /\b[A-Z][\w&.'-]* Industries\b/g, where: null,
    why: "a company's name (Reliance Industries, Supreme Industries), not a word for a group of stocks" },
  { re: /[^.\n\t]*TradingView[^.\n\t]*/g, where: /sectors|guide/,
    why: "glossary 2: \"industry\" stays for TradingView's finer split on the Sectors page (and the Guide's note of it)" },
  { re: /\b20-day average\b/g, where: null,
    why: "a stock's average daily volume over 20 sessions, not a price moving average (glossary 11 is about price averages); wording left for the owner" },
  { re: /pts = percentage points/g, where: null,
    why: "glossary 4's own explainer line" },
  { re: /\bexponential moving average\b|\bsimple moving average\b/gi, where: /guide/,
    why: "glossary 11: the Guide explains EMA (and SMA) once, in words" },
  { re: /\bone year in (?:three|four|five|ten)\b/g, where: null,
    why: "a frequency (\"one year in three\"), not a 12-month window" },
];

const INDEX_NAMED = /Nifty (?:Total Market|\d+|[A-Z][a-z]+)/;   // "Nifty Total Market", "Nifty 500", "Nifty Smallcap 250"
const RULES = {
  '1 "the market" with no index named earlier in the sentence': t => {
    const out = [];
    for (const seg of t.split(/(?<=[.!?])\s+|\n|\t/)) {
      const m = /\bthe market(?:'s|’s)?\b/i.exec(seg);
      if (m && !INDEX_NAMED.test(seg.slice(0, m.index))) out.push(seg.trim().slice(0, 90));
    }
    return out;
  },
  '1 "Market" alone as a column head': t => t.match(/\t(?:The )?[Mm]arket(?=\t|$)|^(?:The )?[Mm]arket(?=\t)/gm),   // the menu's "Market" stands on a line of its own
  '1 "Total Market" without Nifty, "NTM", "Nifty Nifty"': t => t.match(/(?<!Nifty )\bTotal Market\b|\bNTM\b|\bNifty Nifty\b/g),
  '2 "Industry" as a column head': t => t.match(/(?:^|\t)Industr(?:y|ies)\b[^\t\n]{0,12}/gm),
  '2 "industry" for NSE\'s groups': t => t.match(/[^.\n\t]{0,40}\bindustr(?:y|ies)\b[^.\n\t]{0,30}/gi),
  '3 an NSE index without "Nifty" outside an "NSE index" column': t => t.match(/(?<!Nifty )\b(?:Smallcap|Midcap|Microcap|Largecap|LargeMidcap)\s?\d+\b/g),
  '3 a stock\'s size without "Cap"': t => t.match(/(?:^|\t|· )(?:Large|Mid|Small|Micro)(?=\t|$| \d+%| ·)/gm),
  // bps is for costs; a gap between returns is pts. A sentence with bps and a gap word, and no cost word, is a finding.
  '4 "bps" for a gap between returns': t => t.split(/(?<=[.!?])\s+|\n/).filter(s => /\bbps\b/.test(s)
    && /\b(?:lead|ahead|behind|gap|beat|lag|outperform|underperform)/i.test(s)
    && !/cost|brokerage|slippage|charge|impact|fee|spread|stamp|STT|round trip|basis points/i.test(s)).map(s => s.slice(0, 90)),
  '5 "crore" spelled out, or a lakh crore in thousands': t => t.match(/\bcrores?\b|₹\s?\d{1,2},\d\d,\d{3}(?:,\d{3})* ?Cr\b/gi),
  '6 "1Y", "1-year", "12-month", "one year"': t => t.match(/(?<![\w.])1Y\b|\b1-year\b|\b12-month\b|\bone year\b/gi),
  '7 "since inception", "since start", "since the record began"': t => t.match(/\bsince (?:inception|start|the record began)\b/gi),
  '8 "Max DD", "largest fall", "maximum drawdown"': t => t.match(/\bMax DD\b|\blargest fall\b|\bmaximum drawdown\b/gi),
  '9 "this month", "MTD", "month to date"': t => t.match(/\bthis month\b|\bMTD\b|\bmonth[- ]to[- ]date\b/gi),
  '10 "exit rule", "a hold" as a noun': t => t.match(/\bexit rules?\b|\ba hold\b/gi),
  '11 "200-day average", "50-day", "moving average" as a label': t => t.match(/\b\d+-day (?:average|EMA|SMA|moving average)\b|\b(?:50|200)-day\b|\bmoving average\b/gi),
  'S173 "None" as wording': t => t.match(/\bNone (?:announced|found|due)\b/g),
};
// A page that shows "pts" says once what it means (glossary 4): read on the text before ALLOW takes the explainer out.
const EXPLAINER = /pts = percentage points: 12% − 8% = 4 pts/g;
const needsExplainer = raw => /\bpts\b/.test(raw.replace(EXPLAINER, '')) && !raw.match(EXPLAINER);

function audit(name, text) {
  let t = text;
  for (const a of ALLOW) if (!a.where || a.where.test(name)) t = t.replace(a.re, '');
  const found = {};
  for (const [rule, fn] of Object.entries(RULES)) {
    const m = [...new Set(fn(t) || [])];
    if (m.length) found[rule] = m;
  }
  if (needsExplainer(text)) found['4 "pts" with no "pts = percentage points" on the page'] = ['no explainer'];
  const n = Object.values(found).reduce((a, m) => a + m.length, 0);
  console.log(`${name}: ${n ? n + ' found' : 'clean'}`);
  for (const [rule, m] of Object.entries(found)) console.log(`  ${rule}: ${m.slice(0, 8).join(' | ')}${m.length > 8 ? ` (+${m.length - 8})` : ''}`);
  return n;
}

let bad = 0;
if (fromFiles) {
  for (const f of targets) bad += audit(f, readFileSync(f, 'utf8'));
} else {
  const { chromium } = createRequire(import.meta.url)('playwright');
  const b = await chromium.launch();
  for (const url of targets) {
    for (const width of [412, 1400]) {
      const p = await b.newPage({ viewport: { width, height: 900 } });
      await p.goto(url);
      await p.waitForSelector('.site, .dh, [data-testid="stMainBlockContainer"] h1', { timeout: 180000 }).catch(() => {});
      for (let i = 0, quiet = 0; i < 240 && quiet < 3; i++) {       // until Streamlit finishes the run
        const busy = await p.evaluate(() => !!document.querySelector('[data-testid="stStatusWidget"]')).catch(() => false);
        quiet = busy ? 0 : quiet + 1; await p.waitForTimeout(1000);
      }
      await p.waitForTimeout(3000);
      let t = '';
      for (const f of p.frames()) {
        try {
          t += await f.evaluate(() => {
            document.querySelectorAll('details').forEach(d => { d.open = true; });
            // Glossary 3: the short form of an NSE index is allowed in a column headed "NSE index".
            // Columns are counted on the header's last row, colspans included (the Screener has a group row above it).
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
            return document.body.innerText;
          }) + '\n';
        } catch { /* a frame still loading */ }
      }
      bad += audit(`${url} @${width}`, t);
      await p.close();
    }
  }
  await b.close();
}
process.exit(bad && !report ? 1 : 0);
