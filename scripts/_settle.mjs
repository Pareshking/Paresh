// One "the page has finished drawing" rule for every page audit (S205, 23 Nov 2026).
// The audits waited fixed times (layout 8 s after load, 4 s after a resize, 2.5 s per section opened,
// requirements 4 s + 5 s per tap, the others 3 s after a once-a-second idle check): 15 min 37 s of the
// validation run's 18 min 51 s (run 45107993629). These wait for the things the sleeps stood in for:
//   1. Streamlit's run is over: the app element's data-test-script-state reads "notRunning" for 1 s in a row
//      (4 reads 250 ms apart). The audits used to look for the "Running..." status widget, which this app
//      never shows (probed 23 Nov 2026 on /backtest: absent for the whole 6 s run while the state read
//      "running"), so their idle checks passed at once and only the fixed sleeps made them work;
//   2. every frame's web fonts have loaded (a frame drawn in the fallback font is sized wrong, then shrinks);
//   3. the page's height and every frame's size have stopped changing (Streamlit sizes a component frame
//      after it draws, and adds sections below as the run goes on).
// Each wait has a ceiling, so a page that never settles is measured as it is and reported, as before.

const poll = (p, ms) => p.waitForTimeout(ms);

export async function runFinished(p, { quiet = 4, every = 250, maxMs = 240000 } = {}) {
  let q = 0;
  for (const t0 = Date.now(); q < quiet && Date.now() - t0 < maxMs;) {
    const busy = await p.evaluate(() => {
      const app = document.querySelector('[data-testid="stApp"]');
      return !app || app.getAttribute('data-test-script-state') !== 'notRunning'
        || !!document.querySelector('[data-testid="stStatusWidget"]');
    }).catch(() => true);
    q = busy ? 0 : q + 1;
    await poll(p, every);
  }
}

async function frameSizes(p) {
  return p.evaluate(() => {
    const main = document.querySelector('[data-testid="stMain"]') || document.scrollingElement;
    return [main.scrollHeight, ...[...document.querySelectorAll('iframe')]
      .map(f => { const r = f.getBoundingClientRect(); return `${Math.round(r.width)}x${Math.round(r.height)}`; })].join(',');
  }).catch(() => '');
}

export async function framesStill(p, { every = 300, same = 3, maxMs = 15000 } = {}) {
  for (const f of p.frames()) await f.evaluate(() => document.fonts && document.fonts.ready).catch(() => {});
  let last = await frameSizes(p), n = 0;
  for (const t0 = Date.now(); n < same && Date.now() - t0 < maxMs;) {
    await poll(p, every);
    const now = await frameSizes(p);
    n = now === last ? n + 1 : 0; last = now;
  }
}

// After load, a tap, a resize or a section opened: the run is over and every frame is still.
export async function settle(p, opts = {}) {
  await runFinished(p, opts);
  await framesStill(p, opts);
}
