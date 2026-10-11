// Draw the 1200x630 share pictures from tools/og.html, one per language. Usage: node tools/og.js work/og.json
// Writes og/<day>.png (Chinese), og/<day>-en.png, og/<day>-ko.png, og/latest*.png and og/latest.json;
// when og.json says social, also og/social-<lang>.png for the day's social media posts.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const b = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  const p = await b.newPage({ viewport: { width: 1200, height: 630 } });
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + path.resolve(__dirname, 'og.html'), { waitUntil: 'networkidle' });
  let fonts = [];
  fs.mkdirSync('og', { recursive: true });
  for (const lang of ['zh', 'en', 'ko']) {
    await p.evaluate(([l, d]) => render(l, d), [lang, job.langs[lang]]);
    // Ask for each font explicitly; Google Fonts only downloads a face once text needs it.
    fonts = await p.evaluate(async () => {
      const want = ['900 52px "Noto Sans TC"', '700 21px "Noto Sans TC"', '900 52px "Noto Sans KR"', '700 34px "IBM Plex Mono"'];
      const t = new Promise(r => setTimeout(r, 20000));
      await Promise.race([Promise.all(want.map(f => document.fonts.load(f, document.body.innerText))), t]);
      await document.fonts.ready;
      await Promise.all([...document.images].map(i => i.decode().catch(() => {})));
      return [...new Set([...document.fonts].filter(f => f.status === 'loaded').map(f => f.family))];
    });
    // The headline must stay on two lines; shrink it until it does.
    await p.evaluate(() => { const e = document.getElementById('h'); e.style.fontSize = ''; let s = 52; while (e.offsetHeight > 150 && s > 34) { s -= 2; e.style.fontSize = s + 'px'; } });
    const sfx = lang === 'zh' ? '' : '-' + lang;
    const out = `og/${job.date}${sfx}.png`;
    await p.screenshot({ path: out });
    fs.copyFileSync(out, `og/latest${sfx}.png`);
    if (job.social) fs.copyFileSync(out, `og/social-${lang}.png`);
    console.log('og', out);
  }
  fs.writeFileSync('og/latest.json', JSON.stringify({ date: job.date, hash: job.hash }) + '\n');
  console.log('fonts', fonts.join(','));
  // A missing web font only makes the picture plainer; never block the update for it.
  if (!fonts.some(f => /Noto Sans/.test(f))) console.log('::warning::分享圖字型未載入，用咗後備字型：' + (fonts.join('、') || '冇'));
  await b.close();
  if (errs.length) { console.log('::error::分享圖程式出錯：' + errs.join('；')); process.exit(1); }
})();
