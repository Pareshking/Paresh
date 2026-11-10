// Tap targets under 44px on a touch screen, per page, grouped by what they are.
//
//   node scripts/_launch_taps.js <baseUrl> [path ...]
//
// Measured with hasTouch, so the coarse-pointer rules in src/ui/theme.py are
// the ones in force. A label that a finger cannot hit is a page a phone reader
// cannot use, and no unit test sees it.
const { chromium } = require('playwright');

// Not real targets: a visually-hidden skip link, screen-reader-only text, and
// the slider track (its label and thumb are what a finger uses).
const IGNORE = /skip-link|sr-only|\bsr\b/;

(async () => {
  const base = process.argv[2].replace(/\/$/, '');
  const paths = process.argv.slice(3);
  const browser = await chromium.launch();

  for (const path of paths) {
    const page = await browser.newPage({
      viewport: { width: 390, height: 900 }, hasTouch: true, isMobile: true,
    });
    await page.goto(path ? `${base}/${path}` : base, { timeout: 300000 });
    await page.waitForFunction(() => {
      const app = document.querySelector('[data-testid="stApp"]');
      return app && app.getAttribute('data-test-script-state') === 'notRunning';
    }, null, { timeout: 300000, polling: 400 }).catch(() => {});
    await page.waitForTimeout(3500);

    const small = await page.evaluate((ignoreSrc) => {
      const ignore = new RegExp(ignoreSrc);
      const out = [];
      const sel = 'button, a, input, summary, [role="button"], [role="tab"]';
      for (const el of document.querySelectorAll(sel)) {
        const r = el.getBoundingClientRect();
        if (r.width < 1 || r.height < 1 || r.height >= 44) continue;
        const cls = (el.className || '').toString();
        if (ignore.test(cls)) continue;
        // Not a target a finger aims at: an element clipped to a sliver (the
        // skip link, a checkbox hidden behind its own label). Counting those
        // makes the number meaningless.
        if (r.height <= 2 || r.width <= 2) continue;
        const cs = getComputedStyle(el);
        if (cs.opacity === '0' || cs.visibility === 'hidden') continue;
        const kind = el.getAttribute('type') === 'range' ? 'slider track'
          : el.getAttribute('type') === 'radio' ? 'radio dot (its label is the target)'
          : `${el.tagName.toLowerCase()}${cls ? '.' + cls.split(' ')[0] : ''}`;
        out.push({ kind, h: Math.round(r.height), text: (el.innerText || '').trim().slice(0, 24) });
      }
      return out;
    }, IGNORE.source);

    const byKind = {};
    for (const s of small) {
      const k = `${s.kind} @${s.h}px`;
      byKind[k] = (byKind[k] || 0) + 1;
    }
    console.log(JSON.stringify({ page: path || '(dashboard)', under44: small.length, kinds: byKind }));
    await page.close();
  }

  await browser.close();
})();
