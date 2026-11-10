// Page weight and time to content, per page, for the launch baseline.
//
//   node scripts/_launch_perf.js <width> <baseUrl> [path ...]
//
// Two numbers per page, because a reader pays each once:
//   cold  - its own browser context, nothing in the cache: a first visit
//   warm  - the same context after every other page: a click from the nav
//
// Bytes come from the Resource Timing API, not from response events. A
// response served out of the browser's cache still fires a `response` event
// and still hands over a body, so counting those bytes reported a warm visit
// to the dashboard as 3,473 KB downloaded when the true figure was 1 KB.
// `transferSize === 0` with a non-zero decoded body is a cache hit.
const { chromium } = require('playwright');

const SETTLE = async (page) => {
  await page.waitForFunction(() => {
    const app = document.querySelector('[data-testid="stApp"]');
    return app && app.getAttribute('data-test-script-state') === 'notRunning';
  }, null, { timeout: 300000, polling: 200 }).catch(() => {});
  await page.waitForTimeout(3000);
};

const WEIGH = () => {
  let over = 0, cached = 0, n = 0, c = 0;
  const byType = {};
  for (const r of performance.getEntriesByType('resource')) {
    n++;
    if (r.transferSize === 0 && r.decodedBodySize > 0) { cached += r.decodedBodySize; c++; continue; }
    over += r.transferSize;
    const kind = r.initiatorType || 'other';
    byType[kind] = (byType[kind] || 0) + r.transferSize;
  }
  return {
    over, cached, requests: n, cachedRequests: c, byType,
    nodes: document.querySelectorAll('*').length,
    frames: document.querySelectorAll('iframe').length,
    heap: (performance.memory && performance.memory.usedJSHeapSize) || 0,
    html: document.documentElement.outerHTML.length,
  };
};

(async () => {
  const width = Number(process.argv[2]);
  const base = process.argv[3].replace(/\/$/, '');
  const paths = process.argv.slice(4);
  const browser = await chromium.launch();
  const out = {};
  const url = (p) => (p ? `${base}/${p}` : base);

  for (const path of paths) {
    const context = await browser.newContext({ viewport: { width, height: 1200 } });
    const page = await context.newPage();
    const t0 = Date.now();
    await page.goto(url(path), { timeout: 300000 });
    await SETTLE(page);
    const cold = await page.evaluate(WEIGH);
    cold.ms = Date.now() - t0;
    // Every frame is its own document: a chart's markup and its copy of the
    // shared helper are part of what the page weighs.
    cold.frameBytes = 0;
    for (const frame of page.frames()) {
      if (frame === page.mainFrame()) continue;
      try { cold.frameBytes += await frame.evaluate(() => document.documentElement.outerHTML.length); }
      catch (err) { /* cross-origin */ }
    }
    out[path || 'dashboard'] = { cold };
    await context.close();
  }

  // Warm: one reader, one browser, walking the whole site in order.
  const context = await browser.newContext({ viewport: { width, height: 1200 } });
  const page = await context.newPage();
  for (const path of paths) {
    const t0 = Date.now();
    await page.goto(url(path), { timeout: 300000 });
    await SETTLE(page);
    const warm = await page.evaluate(WEIGH);
    warm.ms = Date.now() - t0;
    out[path || 'dashboard'].warm = warm;
  }
  await context.close();

  console.log(JSON.stringify(out));
  await browser.close();
})();
