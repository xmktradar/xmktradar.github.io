// Render the 1200x630 share image from tools/og.html. Usage: node tools/og.js params.json out.png
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const [pf, out] = process.argv.slice(2);
  const q = new URLSearchParams(JSON.parse(fs.readFileSync(pf, 'utf8'))).toString();
  const b = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  const p = await b.newPage({ viewport: { width: 1200, height: 630 } });
  await p.goto('file://' + path.resolve(__dirname, 'og.html') + '?' + q, { waitUntil: 'networkidle' });
  // Ask for each font explicitly; Google Fonts only downloads a face once text needs it.
  const fonts = await p.evaluate(async () => {
    const want = ['900 54px "Noto Serif TC"', '700 46px "Noto Serif TC"', '400 24px "Noto Sans TC"', '500 26px "IBM Plex Mono"'];
    const t = new Promise(r => setTimeout(r, 20000));
    await Promise.race([Promise.all(want.map(f => document.fonts.load(f, '今日大神共同看好 SPCX 2026'))), t]);
    await document.fonts.ready;
    return [...new Set([...document.fonts].filter(f => f.status === 'loaded').map(f => f.family))];
  });
  // Text must fit on one line; shrink the picks line until it does.
  await p.evaluate(() => { const e = document.getElementById('picks'); let s = 54; while (e.scrollWidth > 1072 && s > 30) { s -= 2; e.style.fontSize = s + 'px'; } });
  await p.screenshot({ path: out });
  console.log('og', out, 'fonts', fonts.join(','));
  // A missing web font only makes the picture plainer; never block the update for it.
  if (!fonts.some(f => /Noto Serif/.test(f))) console.log('::warning::分享圖字型未載入，用咗後備字型：' + (fonts.join('、') || '冇'));
  await b.close();
})();
