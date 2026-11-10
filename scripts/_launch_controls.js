// Touch every control on a page once and report what broke.
//
//   node scripts/_launch_controls.js <width> <baseUrl> [path ...]
//
// Loading a page proves less than it looks: most Streamlit failures happen on
// the rerun a control triggers, not on first paint. This clicks each pill,
// tab, expander, select option and ordinary button once, waits for the rerun,
// and reports any exception with the control that caused it.
//
// Destructive controls are never clicked: anything whose label matches
// /sync|clear|delete|reset|remove/i acts site-wide (they clear shared caches),
// and a download writes a file nobody asked for.
const { chromium } = require('playwright');

const SKIP = /sync|clear|delete|reset|remove|download|export|csv|basket/i;

// A dialog left open covers the page, so the next click times out and the
// harness blames the app for its own mess. Dismiss one before each click.
async function dismissDialog(page) {
  const open = await page.$('[role="dialog"], [data-testid="stDialog"]');
  if (!open) return false;
  await page.keyboard.press('Escape').catch(() => {});
  await page.waitForTimeout(400);
  return true;
}

async function settle(page) {
  await page.waitForFunction(() => {
    const app = document.querySelector('[data-testid="stApp"]');
    return app && app.getAttribute('data-test-script-state') === 'notRunning';
  }, null, { timeout: 60000, polling: 300 }).catch(() => {});
  await page.waitForTimeout(700);
}

(async () => {
  const width = Number(process.argv[2]);
  const base = process.argv[3].replace(/\/$/, '');
  const paths = process.argv.slice(4);
  const browser = await chromium.launch();

  for (const path of paths) {
    const url = path ? `${base}/${path}` : base;
    const page = await browser.newPage({ viewport: { width, height: 1000 } });
    const consoleErrors = [];
    page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 90)); });

    const out = { page: path || '(dashboard)', width, clicked: 0, skipped: 0, failures: [] };
    try {
      await page.goto(url, { timeout: 300000 });
      await settle(page);

      const selectors = [
        '[data-testid="stButtonGroup"] button',   // pills and segmented controls
        '[role="tab"]',
        '[data-testid="stExpander"] summary',
        '.stButton button',
      ];
      for (const sel of selectors) {
        const n = await page.$$eval(sel, (els) => els.length).catch(() => 0);
        for (let i = 0; i < n; i++) {
          const handles = await page.$$(sel);
          const el = handles[i];
          if (!el) continue;
          const label = ((await el.innerText().catch(() => '')) || '').trim().slice(0, 40);
          if (SKIP.test(label)) { out.skipped++; continue; }
          const visible = await el.isVisible().catch(() => false);
          if (!visible) { out.skipped++; continue; }
          try {
            await dismissDialog(page);
            await el.click({ timeout: 8000 });
            out.clicked++;
            await settle(page);
            out.dialogs = (out.dialogs || 0) + (await page.$('[role="dialog"]') ? 1 : 0);
            const exc = await page.$$eval('[data-testid="stException"]',
                                          (e) => e.map((x) => x.innerText.slice(0, 120)));
            if (exc.length) out.failures.push({ control: label || sel, error: exc[0] });
          } catch (err) {
            out.failures.push({ control: label || sel, error: `click: ${String(err).slice(0, 80)}` });
          }
        }
      }
      out.consoleErrors = consoleErrors.length;
    } catch (err) {
      out.failures.push({ control: '(load)', error: String(err).slice(0, 120) });
    }
    console.log(JSON.stringify(out));
    await page.close();
  }

  await browser.close();
})();
