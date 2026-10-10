// Step 9: open every view at desktop and phone width; fail on any JS error or sideways overflow.
// Usage: node tools/check.js index.html
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const file = 'file://' + path.resolve(process.argv[2] || 'index.html');
  const b = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  const bad = [];
  for (const [w, h] of [[1280, 900], [390, 844]]) {
    for (const v of ['daily', 'weekly', 'monthly', 'tracked', 'stock/NVDA']) {
      const p = await b.newPage({ viewport: { width: w, height: h } });
      const errs = [];
      p.on('pageerror', e => errs.push(e.message));
      await p.route(/^https?:/, r => r.abort());
      await p.goto(file + '#' + v);
      await p.waitForTimeout(1500);
      const info = await p.evaluate(() => ({ ovf: document.documentElement.scrollWidth > innerWidth + 1, len: document.body.innerText.length }));
      const ok = !errs.length && !info.ovf && info.len > 500;
      console.log(`${ok ? 'ok ' : 'BAD'} ${w}px #${v}`, errs.length ? errs : '', info.ovf ? 'overflow' : '');
      if (!ok) bad.push(`${w}px #${v}`);
      await p.close();
    }
  }
  await b.close();
  if (bad.length) { console.log('::error::網頁檢查唔合格：' + bad.join('、')); process.exit(1); }
})();
