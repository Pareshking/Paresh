// Draw every page once and report, as JSON lines: exceptions, overflow past the
// viewport, and how much visible text came back. Used by scripts/launch_gate.py.
//
//   node scripts/_launch_pages.js <width> <baseUrl> [path ...]
//
// A page that throws, a page wider than the screen and a page that renders
// almost nothing are the three failures a reader notices first; this measures
// all three rather than taking a screenshot for a human to squint at.
const { chromium } = require('playwright');

(async () => {
  const width = Number(process.argv[2]);
  const base = process.argv[3].replace(/\/$/, '');
  const paths = process.argv.slice(4);
  const browser = await chromium.launch();
  let bad = 0;

  for (const path of paths) {
    const url = path ? `${base}/${path}` : base;
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    let result;
    try {
      await page.goto(url, { timeout: 300000 });
      await page.waitForFunction(() => {
        const app = document.querySelector('[data-testid="stApp"]');
        return app && app.getAttribute('data-test-script-state') === 'notRunning';
      }, null, { timeout: 300000, polling: 400 }).catch(() => {});
      await page.waitForTimeout(4000);
      result = await page.evaluate(() => {
        const main = document.querySelector('section.main, [data-testid="stMain"]');
        const root = document.scrollingElement;
        return {
          exceptions: document.querySelectorAll('[data-testid="stException"]').length,
          overflow: Math.max(0, (main ? main.scrollWidth : 0) - root.clientWidth,
                             root.scrollWidth - root.clientWidth),
          chars: document.body.innerText.length,
        };
      });
    } catch (err) {
      result = { exceptions: 1, overflow: 0, chars: 0, error: String(err).slice(0, 120) };
    }
    result.page = path || '(dashboard)';
    result.width = width;
    if (result.exceptions || result.overflow > 0 || result.chars < 200) bad++;
    console.log(JSON.stringify(result));
    await page.close();
  }

  await browser.close();
  process.exit(bad ? 0 : 0);   // the gate decides; this reports
})();
