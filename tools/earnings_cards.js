// Draw the earnings post pictures (4 per company and language, 1080x1350 JPEG) from tools/earnings_card.html.
// Usage: node tools/earnings_cards.js work/earnings_cards.json (written by tools/earnings_posts.py).
// Writes og/e/<day>-<slot>-<TICKER>-<lang>-<n>.jpg, plus a square <n>-fb.jpg copy for Facebook (same method as
// tools/carousel.js); keeps only today's and yesterday's og/e files (pictures and videos).
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const b = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  const p = await b.newPage({ viewport: { width: 1080, height: 1350 } });
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + path.resolve(__dirname, 'earnings_card.html'), { waitUntil: 'networkidle' });
  const sq = await b.newPage({ viewport: { width: 1350, height: 1350 } });
  fs.mkdirSync('og/e', { recursive: true });
  for (const j of job.jobs) {
    for (let i = 0; i < 4; i++) {
      await p.evaluate(([l, d, n, s]) => render(l, d, n, s), [j.lang, j.date, i + 1, j.slides[i]]);
      await p.evaluate(async () => {
        const want = ['900 40px "Noto Sans TC"', '700 32px "Noto Sans TC"', '700 48px "IBM Plex Mono"'];
        const t = new Promise(r => setTimeout(r, 20000));
        await Promise.race([Promise.all(want.map(f => document.fonts.load(f, document.body.innerText))), t]);
        await document.fonts.ready;
        await Promise.all([...document.images].map(i => i.decode().catch(() => {})));
      });
      await p.evaluate(() => {  // long lists must not run into the footer
        const room = document.getElementById('main').clientHeight, box = document.getElementById('in');
        let k = 1;
        while (box.getBoundingClientRect().height > room + 2 && k > 0.6) { k -= 0.05; box.style.zoom = k; }
      });
      await p.screenshot({ path: j.files[i], type: 'jpeg', quality: 88 });
      console.log('earnings card', j.files[i]);
      if (j.fb) {
        const src = 'data:image/jpeg;base64,' + fs.readFileSync(j.files[i]).toString('base64');
        await sq.setContent(`<body style="margin:0;width:1350px;height:1350px;overflow:hidden;position:relative">
          <img src="${src}" style="position:absolute;inset:-60px;width:1470px;height:1470px;object-fit:cover;filter:blur(40px) brightness(.9)">
          <img src="${src}" style="position:absolute;left:135px;top:0;width:1080px;height:1350px"></body>`);
        await sq.evaluate(async () => Promise.all([...document.images].map(i => i.decode().catch(() => {}))));
        await sq.screenshot({ path: j.fb[i], type: 'jpeg', quality: 88 });
      }
    }
  }
  const keep = new Date(Date.parse(job.date + 'T00:00:00Z') - 864e5).toISOString().slice(0, 10);
  for (const f of fs.readdirSync('og/e')) {
    const m = f.match(/^(\d{4}-\d{2}-\d{2})-/);
    if (m && m[1] < keep) { fs.unlinkSync('og/e/' + f); console.log('earnings removed', f); }
  }
  await b.close();
  if (errs.length) { console.log('::error::財報貼文圖程式出錯：' + errs.join('；')); process.exit(1); }
})();
