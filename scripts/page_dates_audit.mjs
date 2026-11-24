// Page dates audit (S164): every chart, table and sentence ends on the page's session, or says why, by rule.
//
//   node scripts/page_dates_audit.mjs [--report] [--verbose] [--cache DIR] URL ...   pages at 1400 px (dates do not change with
//                                     the width); a page number_format_audit.mjs --save DIR already read is not loaded
//   node scripts/page_dates_audit.mjs [--report] --files a.json ...      reads saved before ({url?, raw, frames}), the
//                                     test's fixtures (tests/test_page_dates.py)
//
// The rules, the stated-rule words and the allowed ends (each with its reason and TODO id) are in _page_dates.mjs.
// CI runs the same check inside number_format_audit.mjs (rule 9) on the pages it reads; this script is for the live
// site and for a page that audit does not read:
//   node scripts/page_dates_audit.mjs https://<the live site>/ https://<the live site>/market ...
// Exit 1 on any finding, unless --report.
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { readPageText, cachedPageText } from './_page_text.mjs';
import { reportPageDates } from './_page_dates.mjs';

const args = process.argv.slice(2);
const report = args.includes('--report');
const verbose = args.includes('--verbose');      // also list the ends passed by a rule or ALLOW
const fromFiles = args.includes('--files');
const cacheAt = args.indexOf('--cache');
const cacheDir = cacheAt >= 0 ? args[cacheAt + 1] : null;
const targets = args.filter((a, i) => !a.startsWith('--') && !(cacheAt >= 0 && i === cacheAt + 1));
if (!targets.length) { console.error('usage: page_dates_audit.mjs [--report] [--cache DIR] URL ... | --files FILE ...'); process.exit(2); }

let bad = 0;
const audit = (name, read) => { const r = reportPageDates(name, read, verbose); r.lines.forEach(l => console.log(l)); bad += r.n; };
if (fromFiles) {
  for (const f of targets) { const read = JSON.parse(readFileSync(f, 'utf8')); audit(read.url || f, read); }
} else {
  const { chromium } = createRequire(import.meta.url)('playwright');
  const b = await chromium.launch();
  for (const url of targets) audit(url, cachedPageText(cacheDir, url, 1400) || await readPageText(b, url, 1400));
  await b.close();
}
process.exit(bad && !report ? 1 : 0);
