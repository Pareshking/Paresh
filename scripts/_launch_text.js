// Dump each page's visible text as one JSON object, for the consistency check.
//
//   node scripts/_launch_text.js <width> <baseUrl> [path ...]
//
// Visible text only: what a reader can actually read is what has to agree
// between pages. Text inside a chart's own frame is a separate document and is
// collected per frame, so a figure drawn in a chart can be compared too.
const { chromium } = require('playwright');

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

    let text = await page.evaluate(() => document.body.innerText);
    for (const frame of page.frames()) {
      if (frame === page.mainFrame()) continue;
      try {
        text += '\n' + await frame.evaluate(() => document.body.innerText);
      } catch (err) { /* a cross-origin frame has nothing for us */ }
    }
    out[path || 'dashboard'] = text;
    await page.close();
  }

  console.log(JSON.stringify(out));
  await browser.close();
})();
