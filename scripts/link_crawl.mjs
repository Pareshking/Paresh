#!/usr/bin/env node
// Link crawler (S193 item K; owner, 23 Nov 2026, "Approved"): every page on each system, every link.
// Runs in v1-full-validation after the layout audit (S193 K2); report: docs/archive/S193_ITEM_K_2026-11-23.md.
//   node scripts/link_crawl.mjs [BASE_URL] [--out DIR] [--systems 750,1000,nano] [--pages dashboard,actions]
//        [--stocks RELIANCE,X1000,XNANO] [--cap 25] [--jobs 3] [--no-external]
// For each source page x system it records every link (main page, chart/table frames incl. srcdoc,
// Streamlit page links in the header and menu, clickable table rows) and checks:
//   a) the link opens: no "Page not found", no exception or error box, not an empty page;
//   b) ?sys= is kept when the source had it, and none is added on the 750 (the default);
//   c) a #section link's id exists on the target page, on that system;
//   d) Back returns to the source page (not the target, not a redirect loop); scroll kept is informational.
// Links are deduped by (source page, system, href pattern: symbol, industry and list values masked),
// and capped per page. Trimmed for CI (about 5 min, S193 K2): the header and menu links are the same on every
// page and carry the system in the session, so they are clicked once in all (the first system's Dashboard)
// and only read elsewhere; a link to a stock page is clicked once per system, not once per page (a page's
// own table row is still clicked on each page: F1's Back loop was page by page). External links are listed
// and checked with curl unless --no-external.
// Writes DIR/links.json (every link seen) and DIR/results.json (every check); exit 1 on a failure: a dead link,
// a lost ?sys=, a missing #section, or Back that does not return.
import { createRequire } from 'node:module';
import { writeFileSync, mkdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const here = dirname(fileURLToPath(import.meta.url));
const { settle } = await import(resolve(here, '_settle.mjs'));

const args = process.argv.slice(2);
const opt = (name, dflt) => { const i = args.indexOf(`--${name}`); return i >= 0 ? args[i + 1] : dflt; };
const flag = name => args.includes(`--${name}`);
const BASE = (args.find(a => /^https?:/.test(a)) || 'http://localhost:8501/').replace(/\/?$/, '/');
const OUT = opt('out', '.');
const SYSTEMS = opt('systems', '750,1000,nano').split(',');
const CAP = Number(opt('cap', 25));
const JOBS = Number(opt('jobs', 3));
const PAGES = [
  ['Dashboard', ''], ['Actions', 'actions'], ['Portfolio', 'portfolio'], ['Screener', 'screener'],
  ['Market', 'market'], ['Sectors', 'sectors'], ['Indices', 'indices'], ['Backtest', 'backtest'],
  ['Guide', 'guide'], ['Watchlist', 'watchlist?wl=TCS,RELIANCE'], ['Configuration', 'configuration'],
];
const pageFilter = opt('pages', '');
const NAV_IDS = new Set(['stPageLink-NavLink']);
mkdirSync(OUT, { recursive: true });

const sysQuery = s => (s === '750' ? '' : `sys=${encodeURIComponent(s)}`);
function withSys(path, s) {
  const q = sysQuery(s); if (!q) return BASE + path;
  return BASE + path + (path.includes('?') ? '&' : '?') + q;
}
const rel = u => { try { const x = new URL(u); return x.pathname.replace(/^\//, '') + x.search + x.hash; } catch { return u; } };
const sysOf = u => { try { return new URL(u).searchParams.get('sys'); } catch { return null; } };
const sameDoc = (a, b) => { try { const x = new URL(a), y = new URL(b); return x.pathname === y.pathname && x.search === y.search; } catch { return a === b; } };

// "See it in the Nifty 1000 →" switches system on purpose: its ?sys= is the named system's (none for the 750).
const SYS_NAMES = [['Nifty 750', null], ['Nifty 1000', '1000'], ['> ₹2,000 Cr', 'nano'], ['Combined', 'combined']];
function crossSystem(text) {
  if (!/^See it in /.test(text || '')) return undefined;
  const hit = SYS_NAMES.find(([n]) => text.includes(n));
  return hit ? hit[1] : undefined;
}

function pattern(href) {
  if (!href) return '(empty)';
  if (/^(https?:)?\/\//.test(href) && !href.startsWith(BASE)) { try { return 'ext:' + new URL(href, BASE).host; } catch { return 'ext:' + href; } }
  const [pathq, hash = ''] = href.split('#');
  const [path, q = ''] = pathq.split('?');
  const ps = new URLSearchParams(q);
  const keys = [...ps.keys()].sort().map(k => `${k}=${['stock', 'ind', 'wl'].includes(k) ? '{' + k + '}' : ps.get(k)}`);
  return path + (keys.length ? '?' + keys.join('&') : '') + (hash ? '#' + hash : '');
}

async function load(p, url) {
  await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 180000 });
  await p.waitForSelector('[data-testid="stMainBlockContainer"]', { timeout: 180000 }).catch(() => {});
  await p.waitForTimeout(600);
  await settle(p);
}

// What a page shows: "Page not found", exceptions, error boxes, how much text, which ids.
async function state(p) {
  const main = await p.evaluate(() => {
    const m = document.querySelector('[data-testid="stMainBlockContainer"]');
    const sc = document.querySelector('[data-testid="stMain"]');
    return {
      url: location.href,
      notFound: /Page not found/i.test(document.body.innerText),
      exceptions: [...document.querySelectorAll('[data-testid="stException"]')].map(e => e.innerText.slice(0, 200)),
      errors: [...document.querySelectorAll('[data-testid="stAlertContentError"]')].map(e => e.innerText.slice(0, 200)),
      textLen: m ? m.innerText.trim().length : 0,
      frames: document.querySelectorAll('iframe').length,
      ids: [...document.querySelectorAll('[id]')].map(e => e.id),
      scroll: Math.max(window.scrollY, sc ? sc.scrollTop : 0),
      h1: (document.querySelector('h1') || {}).innerText || '',
    };
  }).catch(e => ({ url: p.url(), err: String(e) }));
  main.frameIds = [];
  for (const f of p.frames()) if (f !== p.mainFrame()) {
    main.frameIds.push(...await f.evaluate(() => [...document.querySelectorAll('[id]')].map(e => e.id)).catch(() => []));
  }
  return main;
}
const opens = s => !s.err && !s.notFound && !s.exceptions?.length && !s.errors?.length && (s.textLen > 150 || s.frames > 0);
const whyNot = s => s.err ? 'page error ' + s.err : s.notFound ? '"Page not found"' : s.exceptions?.length ? 'exception: ' + s.exceptions[0]
  : s.errors?.length ? 'error box: ' + s.errors[0] : 'empty page';

async function collect(p) {
  const out = [];
  const frames = p.frames();
  for (let fi = 0; fi < frames.length; fi++) {
    const f = frames[fi];
    const items = await f.evaluate(() => {
      const r = [];
      for (const a of document.querySelectorAll('a[href]')) {
        const box = a.getBoundingClientRect();
        r.push({ kind: 'a', href: a.getAttribute('href'), abs: a.href, target: a.getAttribute('target') || '',
          text: (a.innerText || a.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 60),
          testid: a.getAttribute('data-testid') || '', visible: box.width > 0 && box.height > 0,
          menu: !!a.closest('[data-testid="stPopoverBody"]') });
      }
      const rows = [...document.querySelectorAll('tr[data-stock]')];
      if (rows.length) r.push({ kind: 'row', href: '(row click) ' + rows[0].getAttribute('data-stock'), abs: '',
        text: `table row ${rows[0].getAttribute('data-stock')} (${rows.length} rows)`, sym: rows[0].getAttribute('data-stock'),
        testid: '', visible: true, symbols: rows.map(x => x.getAttribute('data-stock')) });
      return r;
    }).catch(() => []);
    const furl = f.url();
    for (const it of items) out.push({ ...it, frame: fi === 0 ? 'main' : (furl.startsWith('about:srcdoc') ? 'srcdoc' : 'iframe'), fi });
  }
  return out;
}

// Click one recorded link on the open page, by href + text, in whichever frame holds it now.
async function clickLink(p, l) {
  for (const f of p.frames()) {
    const isMain = f === p.mainFrame();
    if ((l.frame === 'main') !== isMain) continue;
    const h = l.kind === 'row'
      ? await f.$(`tr[data-stock="${l.sym}"]`)
      : await f.evaluateHandle(({ href, text }) => [...document.querySelectorAll('a[href]')].find(a => a.getAttribute('href') === href
          && (a.innerText || a.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 60) === text) || null, l).then(x => x.asElement());
    if (!h) continue;
    await h.scrollIntoViewIfNeeded({ timeout: 3000 }).catch(() => {});
    l.scrollAtClick = await p.evaluate(() => { const sc = document.querySelector('[data-testid="stMain"]');
      return Math.max(window.scrollY, sc ? sc.scrollTop : 0); }).catch(() => 0);
    try { await h.click({ timeout: 5000 }); }
    catch { await h.evaluate(e => e.click()); }   // a menu link while the menu is shut: Streamlit's own handler
    return true;
  }
  return false;
}

async function checkClick(p, src, l) {
  const r = { source: src.name, system: src.system, text: l.text, href: l.href, frame: l.frame, kind: l.kind, checks: {} };
  if (!sameDoc(p.url(), src.url)) await load(p, src.url);
  const before = await state(p);
  const framesBefore = p.frames().map(f => f.url());
  const t0 = Date.now();
  if (!(await clickLink(p, l))) {
    await load(p, src.url);
    if (!(await clickLink(p, l))) { r.checks.a = { ok: false, why: 'link not found on the page to click (after a reload)' }; return r; }
  }
  await p.waitForURL(u => !sameDoc(u.toString(), src.url) || (l.href.includes('#') && u.toString().includes('#')), { timeout: 4000 }).catch(() => {});
  await p.waitForTimeout(500);
  await settle(p);
  const after = await state(p);
  r.landed = rel(after.url); r.ms = Date.now() - t0;
  const framed = p.frames().filter(f => f !== p.mainFrame()).map(f => f.url()).filter(u => u.startsWith('http') && !framesBefore.includes(u));
  if (sameDoc(after.url, src.url) && !l.href.startsWith('#') && framed.length) {
    r.checks.a = { ok: false, why: `opened inside its frame (${rel(framed[0])}); the page stayed` };
  } else if (sameDoc(after.url, src.url) && !l.href.startsWith('#') && !(l.kind === 'a' && sameDoc(new URL(l.href, src.url).toString(), src.url))) {
    r.checks.a = { ok: false, why: 'nothing happened: the page stayed where it was' };
  } else r.checks.a = opens(after) ? { ok: true } : { ok: false, why: whyNot(after) };
  const cross = crossSystem(l.text);
  const want = cross !== undefined ? cross : (src.system === '750' ? null : src.system);
  const got = sysOf(after.url);
  if (cross !== undefined) r.crossSystem = true;
  r.checks.b = { ok: got === want, why: got === want ? '' : (want ? `?sys=${want} lost (landed ${r.landed})` : `?sys=${got} added on the 750`) };
  const hash = (l.href.split('#')[1] || '');
  if (hash) {
    const there = after.ids.includes(hash) || after.frameIds.includes(hash);
    r.hashKept = after.url.includes('#' + hash);
    const reached = r.hashKept || after.scroll > 0;
    r.checks.c = { ok: there && reached, why: !there ? `#${hash} not on ${r.landed}${r.hashKept ? '' : ' (and the # was dropped from the address)'}`
      : reached ? '' : `#${hash} is on ${r.landed || '/'}, but the # was dropped on the way, so the page opens at the top` };
  }
  if (!sameDoc(after.url, src.url)) {
    await p.goBack({ timeout: 15000 }).catch(() => {});
    await p.waitForTimeout(500);
    await settle(p);
    const back = await state(p);
    r.back = rel(back.url);
    const ok = sameDoc(back.url, src.url);
    r.checks.d = { ok, why: ok ? '' : `Back went to ${r.back}, not ${rel(src.url)}` };
    const at = l.scrollAtClick || 0;
    r.scrollKept = at < 40 ? null : Math.abs(back.scroll - at) < 40;   // informational only
    r.scrollBefore = at; r.scrollAfterBack = back.scroll;
  }
  return r;
}

function externalStatus(url) {
  for (const extra of [['-I'], []]) {
    try {
      const code = execFileSync('curl', ['-s', '-o', '/dev/null', '-w', '%{http_code}', '-L', '--max-time', '20', ...extra, url], { encoding: 'utf8' }).trim();
      if (code && code !== '000' && code !== '405') return code;
    } catch { /* blocked or no network */ }
  }
  return 'blocked';
}

const t0 = Date.now();
const browser = await chromium.launch();
const allLinks = [], results = [], external = new Map(), sourceLog = [];
const stockClicked = new Set();   // `${system}|${pattern}`: a stock link is clicked once per system

async function newPage() { const c = await browser.newContext({ viewport: { width: 1400, height: 900 } }); return c.newPage(); }

// The three stocks: RELIANCE, then one only the 1000 ranks and one only the > ₹2,000 Cr list ranks,
// read from each system's Screener table (every row is sent).
async function pickStocks() {
  const given = opt('stocks', '');
  if (given) return given.split(',');
  const syms = {};
  await Promise.all(SYSTEMS.map(async s => {
    const p = await newPage(); await load(p, withSys('screener', s));
    syms[s] = new Set((await collect(p)).filter(l => l.kind === 'row').flatMap(l => l.symbols));
    await p.context().close();
  }));
  const only = (s, others) => [...(syms[s] || [])].find(x => others.every(o => !(syms[o] || new Set()).has(x)));
  return ['RELIANCE', only('1000', ['750', 'nano']), only('nano', ['750', '1000'])].filter(Boolean);
}
const stocks = await pickStocks();
const pages = PAGES.filter(([n, p]) => !pageFilter || pageFilter.split(',').includes(p.split('?')[0] || 'dashboard'));
if (!pageFilter || pageFilter.includes('stock')) for (const s of stocks) pages.push([`Stock ${s}`, `screener?stock=${s}`]);

const jobs = [];
for (const s of SYSTEMS) for (const [name, path] of pages) jobs.push({ name, path, system: s });

async function worker() {
  const p = await newPage();
  for (let job; (job = jobs.shift());) {
    const ts = Date.now();
    const src = { name: job.name, system: job.system, url: withSys(job.path, job.system) };
    try {
      await load(p, src.url);
      src.url = p.url();    // what the page settled on (the app may write ?sys= or a filter)
      const st0 = await state(p);
      const links = await collect(p);
      const srcRes = { source: src.name, system: src.system, text: '(the page itself)', href: rel(src.url), checks: { a: opens(st0) ? { ok: true } : { ok: false, why: whyNot(st0) } } };
      results.push(srcRes);
      const seen = new Map();
      for (const l of links) {
        const pat = l.kind === 'row' ? `row:${l.frame}` : pattern(l.href);
        allLinks.push({ source: src.name, system: src.system, frame: l.frame, kind: l.kind, text: l.text, href: l.href, target: l.target, testid: l.testid, pattern: pat });
        if (pat.startsWith('ext:')) { external.set(l.abs || l.href, { text: l.text, source: src.name }); continue; }
        // b) on the link itself: a hand-built href must carry the source's ?sys= (page links rely on the session).
        if (!seen.has(pat)) seen.set(pat, l);
      }
      let clicks = 0;
      for (const [pat, l] of seen) {
        if (l.href.startsWith('#') && l.kind === 'a') {           // c) a section link on this page
          const id = l.href.slice(1);
          const ok = st0.ids.includes(id) || st0.frameIds.includes(id);
          results.push({ source: src.name, system: src.system, text: l.text, href: l.href, frame: l.frame, kind: 'a',
            checks: { c: { ok, why: ok ? '' : `#${id} is not on this page` } } });
          continue;
        }
        const nav = NAV_IDS.has(l.testid);
        if (nav && !(src.name === 'Dashboard' && src.system === SYSTEMS[0])) continue;   // the header: once in all
        if (l.kind === 'a') {
          const hs = sysOf(new URL(l.href || '', src.url).toString());
          const cross = crossSystem(l.text);
          const want = cross !== undefined ? cross : (src.system === '750' ? null : src.system);
          if (!nav && hs !== want) results.push({ source: src.name, system: src.system, text: l.text, href: l.href, frame: l.frame, kind: 'href',
            checks: { b: { ok: false, why: want ? `href has no ?sys=${want}` : `href adds ?sys=${hs}` } } });
        }
        if (l.kind === 'a' && /[?&]stock=\{stock\}/.test(pat)) {   // a stock page: once per system
          if (stockClicked.has(`${src.system}|${pat}`)) continue;
          stockClicked.add(`${src.system}|${pat}`);
        }
        if (clicks++ >= CAP) continue;
        results.push(await checkClick(p, src, l).catch(e => ({ source: src.name, system: src.system, text: l.text, href: l.href, checks: { a: { ok: false, why: 'crawler: ' + String(e).slice(0, 160) } } })));
      }
      sourceLog.push({ ...src, links: links.length, patterns: seen.size, clicks: Math.min(clicks, CAP), s: Math.round((Date.now() - ts) / 1000) });
      console.error(`${src.name} [${src.system}] ${links.length} links, ${seen.size} patterns, ${Math.round((Date.now() - ts) / 1000)} s`);
    } catch (e) {
      results.push({ source: src.name, system: src.system, text: '(the page itself)', href: rel(src.url), checks: { a: { ok: false, why: 'crawler: ' + String(e).slice(0, 160) } } });
    }
  }
  await p.context().close();
}
await Promise.all(Array.from({ length: JOBS }, worker));
await browser.close();

const ext = [...external].map(([url, v]) => ({ url, ...v, status: flag('no-external') ? 'not checked' : externalStatus(url) }));
const fails = results.flatMap(r => Object.entries(r.checks).filter(([, c]) => !c.ok).map(([k, c]) => ({ check: k, ...r, why: c.why })));
const counts = {};
for (const r of results) for (const [k, c] of Object.entries(r.checks)) { counts[k] ??= { ok: 0, fail: 0 }; counts[k][c.ok ? 'ok' : 'fail']++; }
const seconds = Math.round((Date.now() - t0) / 1000);
writeFileSync(resolve(OUT, 'links.json'), JSON.stringify({ base: BASE, stocks, links: allLinks, external: ext }, null, 1));
writeFileSync(resolve(OUT, 'results.json'), JSON.stringify({ base: BASE, stocks, seconds, counts, sources: sourceLog, fails, results }, null, 1));
console.log(JSON.stringify({ seconds, stocks, counts, links: allLinks.length, external: ext.length, failures: fails.length }));
for (const f of fails) console.log(`FAIL ${f.check} ${f.source} [${f.system}] "${f.text}" ${f.href} -> ${f.why}`);
process.exit(fails.length ? 1 : 0);
