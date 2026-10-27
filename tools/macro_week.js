// Draw the Saturday macro roundup pictures. Usage: node tools/macro_week.js work/macro_week.json
// For each language draws og/macro-<lang>.png (1080x1350) and og/macro-story-<lang>.png (1080x1920) from tools/macro_week.html.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const b = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  const errs = [];
  const art = await b.newPage({ viewport: { width: 1080, height: 1350 } });
  art.on('pageerror', e => errs.push(e.message));
  await art.goto('file://' + path.resolve(__dirname, 'macro_week.html'), { waitUntil: 'networkidle' });
  fs.mkdirSync('og', { recursive: true });
  for (const lang of ['zh', 'en']) {
    for (const [size, h, out] of [['feed', 1350, `og/macro-${lang}.png`], ['story', 1920, `og/macro-story-${lang}.png`]]) {
      await art.setViewportSize({ width: 1080, height: h });
      await art.evaluate(([l, d, s]) => render(l, d, s), [lang, job, size]);
      await art.evaluate(async () => {
        const want = ['900 60px "Noto Sans TC"', '700 30px "Inter"'];
        const t = new Promise(r => setTimeout(r, 20000));
        await Promise.race([Promise.all(want.map(f => document.fonts.load(f, document.body.innerText))), t]);
        await document.fonts.ready;
        await Promise.all([...document.images].map(i => i.decode().catch(() => {})));
      });
      await art.screenshot({ path: out });
      console.log('macro week', out);
    }
  }
  await b.close();
  if (errs.length) { console.log('::error::宏觀貼文圖程式出錯：' + errs.join('；')); process.exit(1); }
})();
