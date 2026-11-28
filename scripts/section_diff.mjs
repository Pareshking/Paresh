// What a page shows, as a list, and what a redesign takes out of it (S238, owner 28 Nov 2026: "I am talking about silent
// drops by you"). Reads every heading, kicker, chart (each chart frame's aria-label), table column, tile label, expander,
// button and download of one page, and with two addresses lists what the second lacks.
//
//   node scripts/section_diff.mjs <url>                     # the page's parts, one per line
//   node scripts/section_diff.mjs <before-url> <after-url>  # parts the after page lacks, then the ones it adds
//
// The before page is the live or main-branch app; the after page the preview. Exit 1 when the after page lacks any part,
// so a redesign cannot pass with a drop the before/after table does not name (.claude/skills/page-redesign, step 4).
// Figures are left out (they change every day); words that carry numbers are kept with the digits masked as "#".
import { createRequire } from 'module';
import { settle, appFrame } from './_settle.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

async function parts(browser, url) {
  const p = await browser.newPage({ viewport: { width: 1400, height: 1200 } });
  await p.goto(url, { timeout: 240000 });
  await settle(p);
  const f = await appFrame(p);
  const own = await f.evaluate(() => {
    const t = s => (s || '').replace(/\s+/g, ' ').trim();
    const out = [];
    const add = (kind, el, text) => { const x = t(text ?? el.innerText); if (x) out.push(`${kind}: ${x.slice(0, 120)}`); };
    document.querySelectorAll('h1,h2,h3,h4').forEach(el => add('heading', el));
    document.querySelectorAll('.dh-kick,.qp-kick,.kicker,.dh-date,.qp-date').forEach(el => add('kicker', el));
    document.querySelectorAll('th[scope=col], thead th').forEach(el => add('column', el));
    document.querySelectorAll('summary, [data-testid="stExpander"] summary').forEach(el => add('expander', el));
    document.querySelectorAll('[data-testid="stDownloadButton"] button').forEach(el => add('download', el));
    document.querySelectorAll('[data-testid="stButton"] button, [data-testid="stPopover"] button').forEach(el => add('button', el));
    document.querySelectorAll('[data-testid="stMetricLabel"], .dh-tile-l, .tile-l, .ix-card-n, .qp-g-n').forEach(el => add('tile', el));
    document.querySelectorAll('img[alt]').forEach(el => add('image', el, el.getAttribute('alt')));
    return out;
  });
  // Charts are frames of their own: each one's aria-label names it.
  const charts = [];
  for (const fr of p.frames()) {
    if (fr === f || fr === p.mainFrame()) continue;
    const labels = await fr.evaluate(() => [...document.querySelectorAll('[aria-label]')]
      .map(e => e.getAttribute('aria-label')).filter(Boolean)).catch(() => []);
    for (const l of labels) charts.push(`chart: ${l.replace(/\s+/g, ' ').trim().slice(0, 120)}`);
    // The words a chart prints (its column heads, readout names, key): a figure dropped from a chart shows here.
    const words = await fr.evaluate(() => (document.body?.innerText || '').split('\n')).catch(() => []);
    for (const w of words) {
      const x = w.replace(/\s+/g, ' ').trim();
      if (x && /[A-Za-z]{2}/.test(x) && x.length <= 80) charts.push(`chart text: ${x}`);
    }
  }
  await p.close();
  const mask = s => s.replace(/[−+-]?\d[\d,.]*/g, '#');
  return [...new Set([...own, ...charts].map(mask))];
}

const [a, b] = process.argv.slice(2);
if (!a) { console.error('usage: node scripts/section_diff.mjs <url> [<after-url>]'); process.exit(2); }
const browser = await chromium.launch();
try {
  const before = await parts(browser, a);
  if (!b) { console.log(before.join('\n')); process.exit(0); }
  const after = await parts(browser, b);
  const gone = before.filter(x => !after.includes(x)), added = after.filter(x => !before.includes(x));
  console.log(`== in ${a}, not in ${b} (${gone.length}): name each in the before/after table`);
  gone.forEach(x => console.log('- ' + x));
  console.log(`== new in ${b} (${added.length})`);
  added.forEach(x => console.log('+ ' + x));
  process.exitCode = gone.length ? 1 : 0;
} finally {
  await browser.close();
}
