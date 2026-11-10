// The HTML the site actually serves, per page, chart frames included.
//
//   node scripts/_launch_html.js <baseUrl> [path ...]
//
// Served markup, not visible text: a credential leaked into an attribute, a
// comment or a frame's srcdoc never shows up as text but is in the page all
// the same.
const { chromium } = require('playwright');

(async () => {
  const base = process.argv[2].replace(/\/$/, '');
  const paths = process.argv.slice(3);
  const browser = await chromium.launch();
  const out = {};

  for (const path of paths) {
    const page = await browser.newPage({ viewport: { width: 1400, height: 1200 } });
    await page.goto(path ? `${base}/${path}` : base, { timeout: 300000 });
    await page.waitForFunction(() => {
      const app = document.querySelector('[data-testid="stApp"]');
      return app && app.getAttribute('data-test-script-state') === 'notRunning';
    }, null, { timeout: 300000, polling: 400 }).catch(() => {});
    await page.waitForTimeout(3500);

    let html = await page.content();
    for (const frame of page.frames()) {
      if (frame === page.mainFrame()) continue;
      try { html += '\n' + await frame.content(); } catch (err) { /* cross-origin */ }
    }
    out[path || 'dashboard'] = html;
    await page.close();
  }

  console.log(JSON.stringify(out));
  await browser.close();
})();
