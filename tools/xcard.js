// Draw the per-ticker X cards (1200x675) from tools/xcard.html. Usage: node tools/xcard.js work/xcards.json [outdir]
// Each job {kind, ticker, out, data} becomes <out> (og/x-premarket.png, og/x-afterclose.png).
// If a card cannot be drawn, og/social-en.png is copied to <out> so the posted link still works.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const raw = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const jobs = Array.isArray(raw) ? raw : (raw.jobs || []);
  const outdir = process.argv[3];
  const dest = j => outdir ? path.join(outdir, path.basename(j.out)) : j.out;
  let b, bad = 0;
  try {
    b = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
    const p = await b.newPage({ viewport: { width: 1200, height: 675 } });
    const errs = [];
    p.on('pageerror', e => errs.push(e.message));
    await p.goto('file://' + path.resolve(__dirname, 'xcard.html'), { waitUntil: 'networkidle' });
    for (const j of jobs) {
      const out = dest(j);
      fs.mkdirSync(path.dirname(out), { recursive: true });
      try {
        await p.evaluate(d => render(d), j.data);
        await p.evaluate(async () => {
          const want = ['900 52px "Noto Sans TC"', '700 92px "Inter"'];
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
        console.log('xcard', j.kind, j.ticker, out);
      } catch (e) {
        bad++; console.error('xcard failed', j.kind, e.message);
        if (fs.existsSync('og/social-en.png')) fs.copyFileSync('og/social-en.png', out);
      }
    }
    if (errs.length) console.error('page errors:', errs.join(' | '));
  } catch (e) {
    bad++; console.error('xcard failed', e.message);
    for (const j of jobs) if (fs.existsSync('og/social-en.png')) fs.copyFileSync('og/social-en.png', dest(j));
  } finally { if (b) await b.close(); }
  process.exit(bad ? 1 : 0);
})();
