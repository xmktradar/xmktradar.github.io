// Render the 1200x630 share image from tools/og.html. Usage: node tools/og.js params.json out.png
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const [pf, out] = process.argv.slice(2);
  const q = new URLSearchParams(JSON.parse(fs.readFileSync(pf, 'utf8'))).toString();
  const b = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  const p = await b.newPage({ viewport: { width: 1200, height: 630 } });
  await p.goto('file://' + path.resolve(__dirname, 'og.html') + '?' + q);
  await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(1500);
  const fonts = await p.evaluate(() => [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family));
  // Text must fit on one line; shrink the picks line until it does.
  await p.evaluate(() => { const e = document.getElementById('picks'); let s = 54; while (e.scrollWidth > 1072 && s > 30) { s -= 2; e.style.fontSize = s + 'px'; } });
  await p.screenshot({ path: out });
  console.log('og', out, 'fonts', fonts.join(','));
  await b.close();
  if (!fonts.some(f => /Noto/.test(f))) process.exit(1);
})();
