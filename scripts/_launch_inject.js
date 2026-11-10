// Query-parameter fuzzing: does a hostile ?stock= / ?sys= / ?wl= / ?owner=
// reach the page as markup, break the app, or open a control it should not?
//
//   node scripts/_launch_inject.js <baseUrl> <path> <param> <value-file>
//
// The value file holds one payload per line, so a shell never has to quote
// them. For each payload the page is loaded and three things are read back:
// whether Streamlit threw, whether the payload survived into the DOM as an
// element rather than as text, and whether the two owner-only controls became
// visible. Output is one JSON object per payload on its own line.
const fs = require('fs');
const { chromium } = require('playwright');

(async () => {
  const base = process.argv[2].replace(/\/$/, '');
  const path = process.argv[3];
  const param = process.argv[4];
  const payloads = fs.readFileSync(process.argv[5], 'utf8').split('\n').filter((s) => s.length);
  const browser = await chromium.launch();

  for (const payload of payloads) {
    const page = await browser.newPage({ viewport: { width: 1400, height: 1200 } });
    let dialogs = 0;
    page.on('dialog', async (d) => { dialogs++; await d.dismiss(); });
    const url = `${base}${path ? '/' + path : ''}?${param}=${encodeURIComponent(payload)}`;
    let nav = 'ok';
    try {
      await page.goto(url, { timeout: 120000 });
      await page.waitForFunction(() => {
        const app = document.querySelector('[data-testid="stApp"]');
        return app && app.getAttribute('data-test-script-state') === 'notRunning';
      }, null, { timeout: 120000, polling: 300 }).catch(() => {});
      await page.waitForTimeout(2500);
    } catch (err) { nav = String(err).slice(0, 120); }

    const seen = await page.evaluate(() => {
      const text = document.body.innerText;
      const owner = ['Sync from niftyindices.com', 'Clear cached files']
        .filter((label) => text.includes(label));
      return {
        threw: document.querySelectorAll('[data-testid="stException"]').length,
        // An injected <img onerror> or <script> would be an ELEMENT; the same
        // characters printed as text are harmless and expected.
        // iframe[srcdoc] is Streamlit's own chart frame and matched on a
        // perfectly ordinary page, so it is not in this list: a check that
        // reports two injections for the payload "RELIANCE" reports nothing.
        injected: document.querySelectorAll(
          'img[onerror], script[data-x], svg[onload], [data-pwned]').length,
        marker: text.includes('PWNED'),
        owner,
      };
    }).catch(() => ({ threw: -1, injected: -1, marker: false, owner: [] }));

    console.log(JSON.stringify({ param, payload, nav, dialogs, ...seen }));
    await page.close();
  }
  await browser.close();
})();
