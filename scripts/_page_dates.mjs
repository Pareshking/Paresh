// S164 (owner, 21 Nov 2026: "market breadth page must be having live data till yesterday atleast ... must be strict
// audit"): every chart, table and sentence ends on the page's session, or says why, by rule.
//
// Read off a page as the reader sees it (number_format_audit.mjs and page_dates_audit.mjs pass the read of
// _page_text.mjs): the main document's text, and each chart frame's text and the last date of its spec.
//
//   1. The page's session: the header pill "Prices · closes of D Mon", the year from the footer "Data to D Mon YYYY"
//      (or the footer alone). A page with data and neither is a finding.
//   2. Every end a reader can see: a chart readout at rest ("Latest · 30 Oct 2026", "Latest · Oct 2026"), the footer,
//      "to D Mon [YYYY]", "to Mon YYYY", "until / through", "2–19 Nov", "as of D Mon", and each chart spec's last
//      date ("dates", lightweight-charts "time"). A month-only date ends on its last day.
//   3. An end before the session passes only when the element states its rule: one of RULES below in the same
//      sentence (for a chart, anywhere in its frame), or an ALLOW entry, each with its reason and TODO id.
//   Text ranges that end more than a year before the session are history ("its deepest fall, December 2024 to
//   September 2025"), not a figure that stops early, and are left alone. A future end ("board meetings to 5 Dec")
//   passes.
// Not checkable from the text and so not checked: the owner's stricter half, that a rule's figure also shows today's
// reading beside it (tests/test_staleness_verdicts_2026_11_21.py checks the two verdicts it applies to); dates in
// a figure's hover readouts away from rest; an element with no date at all (S193 E: it ends on the session).

const MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
const MON = '(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*';
const DAY = `(\\d{1,2}) (${MON})(?: (20\\d\\d))?`;          // 20 Nov, 20 Nov 2026
const MONTH = `(${MON}) (20\\d\\d)`;                           // Oct 2026, October 2026
const DATE = `(?:${DAY}|${MONTH})`;

// The words that state a rule for an end before the session. Each is a reason a reader can check.
export const RULES = {
  month_end: /\bmonth-ends?\b|\b(?:finished|completed) months?\b|\blast (?:finished|completed) month\b/i,
  source_lag: /\bnot in yet\b|\bprovisional\b|\blatest day published\b|\bpublishes? .{0,40}\blate\b/i,
  weekly: /\bweekly\b|\bweek to\b|\beach week\b/i,
};

// Ends before the session that the page explains elsewhere than in the sentence, or a fault still open. Each entry:
// where (a URL pattern, or null for every page), re (matched on the element's text), todo, why. A fault is listed
// with its TODO id and comes out when it is fixed; never add one silently.
export const ALLOW = [
  { where: null, re: /Domestic institutions, \d{1,2} to \d{1,2} \w+, on NSE/, todo: 'S164',
    why: 'open: NSE posts its category workbook about two sessions late (scripts/collect_nse_dii.py); the tile ' +
      'names its end, but the provisional all-exchange figures to the session (data/fii_dii_flows.csv) are not shown' },
  { where: null, re: /domestic, \d{1,2}–\d{1,2} \w+/, todo: 'S164',
    why: 'open: the same DII figure in the flows chart readout (see the tile)' },
  { where: null, re: /pts, momentum’s lead/, todo: 'S164',
    why: 'rule shown: the bars are finished months of the system’s own record ("Each finished month" in the ' +
      'chart’s note) and the "Month so far" tile beside them reads to the session; the chart itself does not say it' },
  { where: null, re: /What heavy foreign buying has meant · \w+ 20\d\d to \w+ 20\d\d/, todo: 'S164',
    why: 'rule shown: a study of finished months (audit: RULE, SHOWN); the month so far is in the tiles above it' },
  { where: /\/portfolio/, re: /were worked out from the rules on \d{1,2} \w+ 20\d\d/, todo: 'S164',
    why: 'not a figure: which months of the record were replayed and which recorded live' },
];

const monthIndex = m => MONTHS.indexOf(m.slice(0, 3).toLowerCase());

// A date token's end: a day, or a month's last day. The year, when not written, is the session's (a later month
// than the session's, with no year, is ahead: "to 5 Dec").
function endOf(day, mon, year, monOnly, monYear, sessionYear) {
  if (monOnly) {
    const m = monthIndex(monOnly);
    return new Date(Date.UTC(Number(monYear), m + 1, 0));
  }
  return new Date(Date.UTC(year ? Number(year) : sessionYear, monthIndex(mon), Number(day)));
}

const iso = d => d.toISOString().slice(0, 10);
const words = d => `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()][0].toUpperCase()}${MONTHS[d.getUTCMonth()].slice(1, 3)} ${d.getUTCFullYear()}`;

// The page's session from its header pill and footer, and any disagreement left to the end check.
export function pageSession(text) {
  const chip = new RegExp(`closes of (\\d{1,2}) (${MON})`).exec(text);
  const foots = [...text.matchAll(new RegExp(`Data to (\\d{1,2}) (${MON}) (20\\d\\d)`, 'g'))];
  const foot = foots.length ? foots[foots.length - 1] : null;
  if (chip) {
    let year = foot ? Number(foot[3]) : new Date().getUTCFullYear();
    if (foot && monthIndex(chip[2]) < monthIndex(foot[2]) - 6) year += 1;      // a December footer, a January pill
    return new Date(Date.UTC(year, monthIndex(chip[2]), Number(chip[1])));
  }
  return foot ? new Date(Date.UTC(Number(foot[3]), monthIndex(foot[2]), Number(foot[1]))) : null;
}

// The sentence of `text` around position i: its line, cut at sentence ends.
function sentenceAt(text, i) {
  const ls = text.lastIndexOf('\n', i) + 1;
  const le = text.indexOf('\n', i);
  const line = text.slice(ls, le < 0 ? text.length : le);
  let at = i - ls, start = 0;
  for (const m of line.matchAll(/[.!?](?=\s)/g)) {
    if (m.index < at) start = m.index + 1;
    else return line.slice(start, m.index + 1).trim();
  }
  return line.slice(start).trim();
}

// Every visible end in a text: [{end: Date, shown: string, at: index, kind}].
function endsIn(text, sessionYear) {
  const out = [];
  const add = (m, kind, groupAt = 1) => {
    const g = m.slice(groupAt, groupAt + 5);
    if (!g[0] && !g[3]) return;
    out.push({ end: endOf(g[0], g[1], g[2], g[3], g[4], sessionYear), shown: m[0], at: m.index, kind });
  };
  for (const m of text.matchAll(new RegExp(`\\b(?:to|until|through|till|as of|closes of) ${DATE}`, 'g'))) add(m, 'to');
  for (const m of text.matchAll(new RegExp(`\\b\\d{1,2} ?– ?${DAY}`, 'g'))) {
    out.push({ end: endOf(m[1], m[2], m[3], null, null, sessionYear), shown: m[0], at: m.index, kind: 'to' });
  }
  for (const m of text.matchAll(/Latest · ([^\n]{0,48})/g)) {
    let last = null;
    for (const d of m[1].matchAll(new RegExp(DATE, 'g'))) {
      const e = endOf(d[1], d[2], d[3], d[4], d[5], sessionYear);
      if (!last || e > last) last = e;
    }
    if (last) out.push({ end: last, shown: m[0].trim(), at: m.index, kind: 'readout' });
  }
  return out;
}

function allowed(url, context) {
  return ALLOW.find(a => (!a.where || a.where.test(url)) && a.re.test(context)) || null;
}

function ruleIn(context) {
  return Object.entries(RULES).find(([, re]) => re.test(context))?.[0] || null;
}

// The findings on one page. `read` is _page_text.mjs's read: {raw, frames?: [{text, specEnd}]} (frames[0] is the
// main document). Returns {session, findings: [{shown, end, context}], ruled: [{shown, rule}], allowed: [...]}.
export function pageDateFindings(url, read) {
  const frames = read.frames && read.frames.length ? read.frames : [{ text: read.raw || '', specEnd: null }];
  const all = frames.map(f => f.text).join('\n');
  const session = pageSession(all);
  const res = { session: session && iso(session), findings: [], ruled: [], allowed: [] };
  if (!session) {
    if (!/\/guide\b/.test(url)) res.findings.push({ shown: 'no session', end: null, context: 'no "closes of D Mon" pill and no "Data to D Mon YYYY" footer' });
    return res;
  }
  const yearAgo = new Date(session.getTime() - 366 * 864e5);
  // A footer that ends before the session and states its rule ("Data to 30 Oct 2026 · NSE’s long price file, the
  // last completed month") rules the whole page: every end in that month, up to the footer's date, follows it.
  const foot = [...all.matchAll(new RegExp(`Data to ${DAY}[^\\n]*`, 'g'))].pop();
  let pageRule = null;
  if (foot) {
    const fend = endOf(foot[1], foot[2], foot[3], null, null, session.getUTCFullYear());
    const rule = fend < session ? ruleIn(sentenceAt(foot[0], 0)) : null;
    if (rule) pageRule = { rule: `${rule} (the footer)`, from: new Date(Date.UTC(fend.getUTCFullYear(), fend.getUTCMonth(), 1)),
      to: new Date(Date.UTC(fend.getUTCFullYear(), fend.getUTCMonth() + 1, 0)) };
  }
  const seen = new Set();
  frames.forEach((f, k) => {
    const chart = k > 0;
    const judge = (shown, end, context) => {
      const key = `${shown}|${context.slice(0, 80)}`;
      if (seen.has(key)) return;
      seen.add(key);
      const rule = ruleIn(chart ? f.text : context)
        || (pageRule && end >= pageRule.from && end <= pageRule.to ? pageRule.rule : null);
      if (rule) { res.ruled.push({ shown, rule }); return; }
      const a = allowed(url, chart ? f.text.slice(0, 400) + '\n' + context : context);
      if (a) { res.allowed.push({ shown, todo: a.todo, why: a.why }); return; }
      res.findings.push({ shown, end: iso(end), context: context.slice(0, 160) });
    };
    for (const e of endsIn(f.text, session.getUTCFullYear())) {
      if (e.end >= session) continue;
      if (e.kind === 'to' && e.end < yearAgo) continue;                // history, not a figure that stops early
      judge(e.shown, e.end, sentenceAt(f.text, e.at));
    }
    if (chart && f.specEnd) {
      const end = new Date(`${f.specEnd}T00:00:00Z`);
      if (end < session) judge(`chart data to ${words(end)}`, end, f.text.split('\n').find(s => s.trim()) || '');
    }
  });
  return res;
}

// The report lines for one page, and the number of findings.
export function reportPageDates(name, read, verbose = false) {
  const r = pageDateFindings(name, read);
  const lines = [`${name}: session ${r.session || '–'}; ${r.findings.length ? r.findings.length + ' ending early without a rule' : 'every end on the session or ruled'}`
    + (r.ruled.length || r.allowed.length ? ` (${r.ruled.length} by a stated rule, ${r.allowed.length} allowed)` : '')];
  for (const x of r.findings) lines.push(`  S164 ends ${x.end || '?'} with no rule: "${x.shown}" in "${x.context}"`);
  if (verbose) {
    for (const x of r.ruled) lines.push(`  by rule (${x.rule}): "${x.shown}"`);
    for (const x of r.allowed) lines.push(`  allowed (${x.todo}): "${x.shown}": ${x.why}`);
  }
  return { lines, n: r.findings.length, result: r };
}
