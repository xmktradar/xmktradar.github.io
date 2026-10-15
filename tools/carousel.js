// Draw the daily multi-picture posts (4 pictures, 1080x1350 JPEG) from tools/carousel.html.
// Usage: node tools/carousel.js work/carousel.json (written by tools/carousel.py).
// Writes og/c/<day>-<slot>-<lang>-<n>.jpg; keeps only today's and yesterday's.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const b = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  const p = await b.newPage({ viewport: { width: 1080, height: 1350 } });
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + path.resolve(__dirname, 'carousel.html'), { waitUntil: 'networkidle' });
  fs.mkdirSync('og/c', { recursive: true });
  for (const j of job.jobs) {
    for (let i = 0; i < 4; i++) {
      await p.evaluate(([l, t, d, n, s]) => render(l, t, d, n, s), [j.lang, j.theme, j.date, i + 1, j.slides[i]]);
      await p.evaluate(async () => {
        const want = ['900 46px "Noto Sans TC"', '700 32px "Noto Sans TC"', '900 46px "Noto Sans KR"', '700 48px "IBM Plex Mono"'];
        const t = new Promise(r => setTimeout(r, 20000));
        await Promise.race([Promise.all(want.map(f => document.fonts.load(f, document.body.innerText))), t]);
        await document.fonts.ready;
        await Promise.all([...document.images].map(i => i.decode().catch(() => {})));
      });
      // Long text must not run into the footer: shrink the main text until it fits.
      await p.evaluate(() => {
        const room = document.getElementById('main').clientHeight, box = document.getElementById('in');
        let k = 1;
        while (box.getBoundingClientRect().height > room + 2 && k > 0.6) { k -= 0.05; box.style.zoom = k; }
      });
      await p.screenshot({ path: j.files[i], type: 'jpeg', quality: 88 });
      console.log('carousel', j.files[i]);
    }
  }
  const keep = new Date(Date.parse(job.date + 'T00:00:00Z') - 864e5).toISOString().slice(0, 10);
  for (const f of fs.readdirSync('og/c')) {
    const m = f.match(/^(\d{4}-\d{2}-\d{2})-/);
    if (m && m[1] < keep) { fs.unlinkSync('og/c/' + f); console.log('carousel removed', f); }
  }
  await b.close();
  if (errs.length) { console.log('::error::多圖帖程式出錯：' + errs.join('；')); process.exit(1); }
})();
