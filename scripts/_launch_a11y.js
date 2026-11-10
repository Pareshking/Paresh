// Accessibility measurements for the launch gate: contrast, heading order,
// accessible names, alt text, document language, focus visibility.
//
//   node scripts/_launch_a11y.js <width> <baseUrl> [path ...]
//
// It measures what a reader meets, not what the stylesheet claims: the
// computed colour of each visible text run against the first ancestor that
// actually paints a background, and the accessible name a screen reader would
// announce. Chart frames are separate documents and are measured too.
//
// Output: one JSON object per page on the last line, read by launch_a11y.py.
const { chromium } = require('playwright');

const PROBE = () => {
  // `checked` is the number of text runs actually measured. A contrast check
  // that reports nothing because it matched nothing would pass every page
  // silently, so the count is printed alongside the failures.
  const out = { contrast: [], checked: 0, headings: [], noName: [], noAlt: [],
                named: 0, lang: document.documentElement.lang || '' };

  const parse = (c) => {
    const m = String(c).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(',').map((x) => parseFloat(x));
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };
  const over = (fg, bg) => ({
    r: fg.r * fg.a + bg.r * (1 - fg.a),
    g: fg.g * fg.a + bg.g * (1 - fg.a),
    b: fg.b * fg.a + bg.b * (1 - fg.a),
    a: 1,
  });
  const lum = (c) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const ratio = (a, b) => {
    const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
    return (x + 0.05) / (y + 0.05);
  };
  // What is painted behind this text. An ancestor's background only counts if
  // its own box actually contains the text's box: Streamlit floats a slider's
  // value label above the thumb, so the nearest painted ancestor is the dark
  // filled track, eight pixels tall and nowhere near the label. Walking
  // ancestors blindly called that label 1.51:1 when a screenshot shows dark
  // grey on white.
  const backdrop = (el) => {
    const t = el.getBoundingClientRect();
    const holds = (r) => r.left <= t.left + 0.5 && r.right >= t.right - 0.5
                      && r.top <= t.top + 0.5 && r.bottom >= t.bottom - 0.5;
    let stack = [];
    for (let n = el; n; n = n.parentElement) {
      if (n !== el && !holds(n.getBoundingClientRect())) continue;
      const bg = parse(getComputedStyle(n).backgroundColor);
      if (bg && bg.a > 0) { stack.push(bg); if (bg.a >= 1) break; }
    }
    let base = { r: 255, g: 255, b: 255, a: 1 };
    for (let i = stack.length - 1; i >= 0; i--) base = over(stack[i], base);
    return base;
  };
  const shown = (el) => {
    const s = getComputedStyle(el);
    if (s.visibility === 'hidden' || s.display === 'none' || parseFloat(s.opacity) < 0.1) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;
    // A control clipped to a sliver by an ancestor is the screen-reader-only
    // copy of a widget (react-aria puts the real radio inside a 1px span).
    // It has its own 13px box and is not on the page at all. Only the clip
    // itself is tested: an early version also called an element hidden when
    // any ancestor was 0px with overflow hidden, and <html> is 1400x0 on
    // every page, so it reported two pages as having no headings.
    for (let n = el; n; n = n.parentElement) {
      const p = getComputedStyle(n);
      if (/inset\(50%\)/.test(p.clipPath) || /rect\(0px, 0px, 0px, 0px\)/.test(p.clip)) return false;
    }
    return true;
  };
  // The accessible name, via textContent rather than innerText. innerText is
  // layout dependent and came back empty for every control below the fold,
  // which reported nine perfectly well labelled buttons as unnamed.
  const name = (el) => (
    el.getAttribute('aria-label') ||
    (el.getAttribute('aria-labelledby') &&
      (document.getElementById(el.getAttribute('aria-labelledby')) || {}).textContent) ||
    el.getAttribute('title') ||
    el.getAttribute('alt') ||
    el.textContent ||
    (el.querySelector('img') && el.querySelector('img').alt) ||
    (el.querySelector('svg title') && el.querySelector('svg title').textContent) ||
    (el.labels && el.labels[0] && el.labels[0].textContent) ||
    ''
  ).trim();

  // Text runs: an element with its own text, so the colour belongs to it.
  const seen = new Map();
  for (const el of document.querySelectorAll('body *')) {
    if (!shown(el)) continue;
    const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 1);
    if (!own) continue;
    // innerText is what is actually laid out and painted. An element whose
    // text node is there but whose innerText is empty has not been rendered
    // yet, and its computed colour is not what a reader will meet: the first
    // run of this check reported the header nav at 1.51:1 on a near-black
    // backdrop, and a screenshot showed dark-on-white, plainly legible.
    if (!el.innerText.trim()) continue;
    const s = getComputedStyle(el);
    const fg = parse(s.color);
    if (!fg) continue;
    const bg = backdrop(el);
    const r = ratio(over(fg, bg), bg);
    const px = parseFloat(s.fontSize);
    const bold = parseInt(s.fontWeight, 10) >= 700;
    const large = px >= 24 || (px >= 18.66 && bold);
    const need = large ? 3.0 : 4.5;
    out.checked++;
    if (r + 0.005 >= need) continue;
    const key = `${s.color}|${Math.round(bg.r)},${Math.round(bg.g)},${Math.round(bg.b)}|${px}|${bold}`;
    if (seen.has(key)) { seen.get(key).count++; continue; }
    const row = {
      ratio: Math.round(r * 100) / 100, need, px, bold, count: 1,
      color: s.color, bg: `rgb(${Math.round(bg.r)}, ${Math.round(bg.g)}, ${Math.round(bg.b)})`,
      sample: el.innerText.trim().slice(0, 48), where: el.className ? String(el.className).slice(0, 60) : el.tagName,
    };
    seen.set(key, row);
    out.contrast.push(row);
  }

  for (const h of document.querySelectorAll('h1,h2,h3,h4,h5,h6')) {
    if (shown(h)) out.headings.push({ level: Number(h.tagName[1]), text: h.innerText.trim().slice(0, 60) });
  }
  for (const el of document.querySelectorAll('button,a[href],[role="button"],summary,input,select,textarea')) {
    if (!shown(el)) continue;
    out.named++;
    if (!name(el)) {
      out.noName.push({ tag: el.tagName.toLowerCase(), cls: String(el.className || '').slice(0, 60),
                        test: el.getAttribute('data-testid') || '' });
    }
  }
  for (const img of document.querySelectorAll('img')) {
    if (shown(img) && img.getAttribute('alt') === null) {
      out.noAlt.push({ src: (img.getAttribute('src') || '').slice(0, 60) });
    }
  }
  return out;
};

const FOCUS = () => {
  // Does the focused element show a ring? Streamlit's reset removes outlines
  // in places, and a keyboard-only reader then has no idea where they are.
  //
  // Tabbing into an iframe leaves the parent's activeElement pointing at the
  // IFRAME while focus is really inside the frame's own document, so follow
  // it. The frames are same-origin (Streamlit serves them), and reading the
  // iframe's own computed style instead reported every chart and every row of
  // the screener table as an unringed stop.
  let el = document.activeElement;
  while (el && el.tagName === 'IFRAME') {
    const doc = el.contentDocument;
    const inner = doc && doc.activeElement;
    if (!inner || inner === doc.body || inner === doc.documentElement) {
      // Nothing inside took focus: the browser focused the frame itself. It
      // is a stop with nothing to ring, which only matters if there is
      // something in there to reach.
      return { tag: 'iframe', cls: String(el.className || '').slice(0, 50), text: '',
               ring: true, frameStop: true, outline: '', shadow: '',
               reachable: doc ? doc.querySelectorAll('a[href],button,[tabindex]:not([tabindex="-1"])').length : -1 };
    }
    el = inner;
  }
  if (!el || el === document.body) return null;
  const s = getComputedStyle(el);
  const ring = (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0)
    || /inset|rgb/.test(s.boxShadow) && s.boxShadow !== 'none';
  return {
    tag: el.tagName.toLowerCase(), cls: String(el.className || '').slice(0, 50),
    text: (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 40),
    ring, outline: s.outline, shadow: s.boxShadow === 'none' ? '' : s.boxShadow.slice(0, 50),
  };
};

(async () => {
  const width = Number(process.argv[2]);
  const base = process.argv[3].replace(/\/$/, '');
  const paths = process.argv.slice(4);
  const browser = await chromium.launch();
  const out = {};

  for (const path of paths) {
    const page = await browser.newPage({ viewport: { width, height: 1200 } });
    await page.goto(path ? `${base}/${path}` : base, { timeout: 300000 });
    await page.waitForFunction(() => {
      const app = document.querySelector('[data-testid="stApp"]');
      return app && app.getAttribute('data-test-script-state') === 'notRunning';
    }, null, { timeout: 300000, polling: 400 }).catch(() => {});
    await page.waitForTimeout(4500);

    if (process.env.A11Y_SELFTEST) {
      // A negative control: plant one text run that must fail, so a run that
      // reports nothing is known to be a clean page rather than a check that
      // quietly matched nothing. launch_a11y.py asserts it is caught.
      await page.evaluate(() => {
        const el = document.createElement('p');
        el.id = 'a11y-selftest';
        el.textContent = 'contrast self test';
        // !important, because the site's own `p { color: ... !important }`
        // wins over a plain inline style and the plant came out legible.
        el.setAttribute('style',
          'color:#c9c9c9!important;background:#fff!important;font-size:14px!important;'
          + 'padding:4px;position:relative;z-index:9');
        // Into the app's own main block: <body> is 1400x0 on every page
        // (Streamlit scrolls an inner container), so a child appended there
        // is never laid out and the planted run was not even measured.
        (document.querySelector('.stMainBlockContainer')
          || document.querySelector('[data-testid="stMain"]')
          || document.body).appendChild(el);
      });
      await page.waitForTimeout(200);
    }

    const res = await page.evaluate(PROBE);
    res.frames = [];
    for (const frame of page.frames()) {
      if (frame === page.mainFrame()) continue;
      try { res.frames.push(await frame.evaluate(PROBE)); } catch (err) { /* cross-origin */ }
    }

    // Keyboard: tab through the first 25 stops and record focus visibility.
    res.focus = [];
    await page.keyboard.press('Tab');
    for (let i = 0; i < 25; i++) {
      const f = await page.evaluate(FOCUS);
      if (f) res.focus.push(f);
      await page.keyboard.press('Tab');
      await page.waitForTimeout(60);
    }

    out[path || 'dashboard'] = res;
    await page.close();
  }

  console.log(JSON.stringify(out));
  await browser.close();
})();
