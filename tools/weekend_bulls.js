// Draw the weekend bulls cards from tools/weekend_bulls.html.
// Usage: node tools/weekend_bulls.js work/weekend-bulls-cards.json [outdir]
// Each job {lang, size, out, data} becomes <out>:
//   portrait og/weekend-bulls-<lang>.png     1080x1350 (X / Instagram / Threads)
//   square   og/weekend-bulls-<lang>-sq.png  1080x1080 (Facebook)
// CHROME_PATH, when set, is the browser executable (same as tools/top5card.js).
// Fail-closed on missing CJK fonts (PR #252): refuse to screenshot tofu.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const SIZE = { portrait: [1080, 1350], square: [1080, 1080] };
(async () => {
  const raw = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const jobs = Array.isArray(raw) ? raw : (raw.jobs || []);
  const outdir = process.argv[3];
  const dest = j => outdir ? path.join(outdir, path.basename(j.out)) : j.out;
  let b, bad = 0;
  try {
    b = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
    const p = await b.newPage({ viewport: { width: 1080, height: 1350 }, deviceScaleFactor: 1 });
    const errs = [];
    p.on('pageerror', e => errs.push(e.message));
    await p.goto('file://' + path.resolve(__dirname, 'weekend_bulls.html'), { waitUntil: 'networkidle' });
    for (const j of jobs) {
      const out = dest(j);
      const [w, h] = SIZE[j.size] || SIZE.portrait;
      fs.mkdirSync(path.dirname(out), { recursive: true });
      try {
        await p.setViewportSize({ width: w, height: h });
        await p.evaluate(d => render(d), Object.assign({}, j.data, { lang: j.lang, size: j.size }));
        await p.evaluate(async () => {
          const want = ['900 40px "Noto Sans TC"', '700 36px "Inter"', '700 28px "Noto Sans CJK TC"'];
          const t = new Promise(r => setTimeout(r, 20000));
          await Promise.race([Promise.all(want.map(f => document.fonts.load(f, document.body.innerText))), t]);
          await document.fonts.ready;
        if (document.fonts.status !== 'loaded' || !document.fonts.check('700 28px "Noto Sans CJK TC"', '個看好')) {
          await new Promise(r => setTimeout(r, 3000)); await document.fonts.ready;
          if (document.fonts.status !== 'loaded') throw new Error('fonts not loaded (CJK) - refusing to draw tofu');
        }
          await Promise.all([...document.images].map(i => i.decode().catch(() => {})));
        });
        await p.evaluate(() => { if (typeof fit === 'function') fit(); });
        await p.screenshot({ path: out });
        console.log('weekend-bulls', j.lang, j.size, out);
      } catch (e) {
        bad++; console.error('weekend-bulls failed', j.lang, j.size, e.message);
        // Do NOT fall back to og/social-*.png — that was the whole bug (daily snapshot ≠ weekly bulls).
      }
    }
    if (errs.length) console.error('page errors:', errs.join(' | '));
  } catch (e) {
    bad++; console.error('weekend-bulls failed', e.message);
  } finally { if (b) await b.close(); }
  process.exit(bad ? 1 : 0);
})();
