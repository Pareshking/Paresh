#!/usr/bin/env node
// The chart must not move on hover (STOCK_REQUIREMENTS row 48; owner, 22 Nov 2026: "Mock up chart is jumping so
// when you modify existing chart, ensure that mistake don't get repeated"; #589 for the other charts).
// Opens the page at each width, finds every Lightweight Charts frame, moves the pointer across the top plot at
// several x positions (and once off the chart) and fails when, between any two positions, a plot's canvas top
// moves or a readout's height changes. Also fails when no chart frame is found.
//   node scripts/chart_hover_audit.mjs <url> [widths=412,1400]     exit 1 on any movement.
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('playwright');

const url = process.argv[2] || 'http://localhost:8501/stock?stock=SANSERA';
const widths = (process.argv.find(a => /^\d+(,\d+)*$/.test(a)) || '412,1400').split(',').map(Number);
const STOPS = [0.03, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9, 0.99];

async function settled(p) {
  let quiet = 0;
  for (let i = 0; i < 240 && quiet < 2; i++) {
    const busy = await p.evaluate(() => !!document.querySelector('[data-testid="stStatusWidget"]')).catch(() => false);
    quiet = busy ? 0 : quiet + 1;
    await p.waitForTimeout(1000);
  }
}

// In the chart frame: each pane's readout height and its plot canvas's top, relative to the frame.
const measure = () => [...document.querySelectorAll('.pane')].map(p => {
  const lg = p.querySelector('.lg'), cv = p.querySelector('.plot canvas');
  return { lg: lg ? Math.round(lg.getBoundingClientRect().height * 10) / 10 : null,
           top: cv ? Math.round(cv.getBoundingClientRect().top * 10) / 10 : null,
           text: lg ? lg.innerText.replace(/\s+/g, ' ').trim() : '' };
});

const b = await chromium.launch();
let failures = 0, checked = 0;
for (const w of widths) {
  const page = await b.newPage({ viewport: { width: w, height: 900 } });
  await page.goto(url);
  await page.waitForSelector('[data-testid="stMainBlockContainer"] h1', { timeout: 240000 }).catch(() => {});
  await page.waitForTimeout(4000);
  await settled(page);
  // A modal over the page ("Page not found" when /stock?stock= is redirected to the Screener) takes the pointer.
  for (let k = 0; k < 3 && await page.$('[role="dialog"]'); k++) { await page.keyboard.press('Escape'); await page.waitForTimeout(500); }
  const frames = [];
  for (const el of await page.$$('iframe')) {
    const f = await el.contentFrame();
    if (f && await f.$('#root .pane canvas').catch(() => null)) frames.push({ el, f });
  }
  if (!frames.length) { console.log(`FAIL ${w}px: no chart frame found`); failures++; await page.close(); continue; }
  for (const [i, { el, f }] of frames.entries()) {
    await el.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);
    const box = await el.boundingBox();
    const plot = await f.evaluate(() => { const r = document.querySelector('.pane .plot').getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; });
    const base = await f.evaluate(measure);
    const readings = [];
    for (const s of STOPS) {
      await page.mouse.move(box.x + plot.x + plot.w * s * 0.92, box.y + plot.y + plot.h * 0.5);
      await page.waitForTimeout(150);
      readings.push({ at: s, m: await f.evaluate(measure) });
    }
    await page.mouse.move(2, 2);           // off the chart: the latest values again
    await page.waitForTimeout(150);
    readings.push({ at: 'off', m: await f.evaluate(measure) });
    const moved = [];
    for (const r of readings) r.m.forEach((pane, k) => {
      checked++;
      if (pane.top !== base[k].top) moved.push(`pane ${k + 1} plot top ${base[k].top} -> ${pane.top} at ${r.at} ("${pane.text}")`);
      if (pane.lg !== base[k].lg) moved.push(`pane ${k + 1} readout height ${base[k].lg} -> ${pane.lg} at ${r.at} ("${pane.text}")`);
    });
    const changed = new Set(readings.map(r => r.m[0].text)).size;
    if (changed < 2) moved.push('the readout did not change under the pointer (hover not reached)');
    if (moved.length) { failures++; console.log(`FAIL ${w}px chart ${i + 1}:\n  ` + moved.join('\n  ')); }
    else console.log(`ok ${w}px chart ${i + 1}: ${base.length} panes steady over ${readings.length} pointer positions (${changed} readings)`);
  }
  await page.close();
}
await b.close();
console.log(`${checked} pane readings checked; ${failures ? failures + ' failing' : 'no movement'}`);
process.exit(failures ? 1 : 0);
