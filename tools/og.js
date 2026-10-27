// Draw the 1200x630 share pictures from tools/og.html, one per language. Usage: node tools/og.js work/og.json
// Writes og/<day>.png (Chinese), og/<day>-en.png, og/<day>-ko.png, og/latest*.png and og/latest.json,
// plus a 1080x1350 IG/Threads portrait from tools/portrait.html: og/portrait-<lang>.png and og/latest-portrait*.png.
// When og.json says social, also og/social-<lang>.png for the day's social media posts, og/ig-<lang>.png
// (native 1080x1350 Instagram text-post picture, from tools/ig.html), and og/story-<lang>.png
// (1080x1920 Instagram Story, from tools/story.html).
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
  for (const lang of ['zh', 'en']) {
    await p.evaluate(([l, d]) => render(l, d), [lang, job.langs[lang]]);
    // Ask for each font explicitly; Google Fonts only downloads a face once text needs it.
    fonts = await p.evaluate(async () => {
      const want = ['900 52px "Noto Sans TC"', '700 21px "Noto Sans TC"', '700 34px "Inter"'];
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
  // Native 1080x1350 Instagram text-post pictures, only with the day's social posts.
  if (job.social) {
    const ip = await b.newPage({ viewport: { width: 1080, height: 1350 } });
    ip.on('pageerror', e => errs.push(e.message));
    await ip.goto('file://' + path.resolve(__dirname, 'ig.html'), { waitUntil: 'networkidle' });
    for (const lang of ['zh', 'en']) {
      await ip.evaluate(([l, d]) => ig(l, d), [lang, job.langs[lang]]);
      await ip.evaluate(async () => {
        const want = ['900 84px "Noto Sans TC"', '700 32px "Noto Sans TC"', '700 52px "Inter"'];
        const t = new Promise(r => setTimeout(r, 20000));
        await Promise.race([Promise.all(want.map(f => document.fonts.load(f, document.body.innerText))), t]);
        await document.fonts.ready;
        await Promise.all([...document.images].map(i => i.decode().catch(() => {})));
      });
      await ip.evaluate(() => { if (typeof fit === 'function') fit(); });
      await ip.screenshot({ path: `og/ig-${lang}.png` });
      console.log('ig', `og/ig-${lang}.png`);
    }
  }
  // IG/Threads portrait (1080x1350), every run: the landscape picture plus headline and brand.
  const pp = await b.newPage({ viewport: { width: 1080, height: 1350 } });
  pp.on('pageerror', e => errs.push(e.message));
  await pp.goto('file://' + path.resolve(__dirname, 'portrait.html'), { waitUntil: 'networkidle' });
  for (const lang of ['zh', 'en']) {
    const sfx = lang === 'zh' ? '' : '-' + lang;
    const pic = 'data:image/png;base64,' + fs.readFileSync(`og/${job.date}${sfx}.png`).toString('base64');
    await pp.evaluate(([l, d, pc]) => portrait(l, d, pc), [lang, job.langs[lang], pic]);
    await pp.evaluate(async () => {
      const want = ['900 62px "Noto Sans TC"', '700 48px "Inter"'];
      const t = new Promise(r => setTimeout(r, 20000));
      await Promise.race([Promise.all(want.map(f => document.fonts.load(f, document.body.innerText))), t]);
      await document.fonts.ready;
      await Promise.all([...document.images].map(i => i.decode().catch(() => {})));
    });
    const pout = `og/portrait-${lang}.png`;
    await pp.screenshot({ path: pout });
    fs.copyFileSync(pout, `og/latest-portrait${sfx}.png`);
    console.log('portrait', pout);
  }
  // Instagram Story pictures (1080x1920), only with the day's social posts.
  if (job.social) {
    const sp = await b.newPage({ viewport: { width: 1080, height: 1920 } });
    sp.on('pageerror', e => errs.push(e.message));
    await sp.goto('file://' + path.resolve(__dirname, 'story.html'), { waitUntil: 'networkidle' });
    for (const lang of ['zh', 'en']) {
      const pic = 'data:image/png;base64,' + fs.readFileSync(`og/social-${lang}.png`).toString('base64');
      await sp.evaluate(([l, d, pc]) => story(l, d, pc), [lang, job.langs[lang], pic]);
      await sp.evaluate(async () => {
        const want = ['900 62px "Noto Sans TC"', '700 90px "Inter"'];
        const t = new Promise(r => setTimeout(r, 20000));
        await Promise.race([Promise.all(want.map(f => document.fonts.load(f, document.body.innerText))), t]);
        await document.fonts.ready;
        await Promise.all([...document.images].map(i => i.decode().catch(() => {})));
      });
      await sp.screenshot({ path: `og/story-${lang}.png` });
      console.log('story', `og/story-${lang}.png`);
    }
  }
  // Keep only today's and yesterday's dated pictures (Tim, 2026-10-11); latest*.png and social-*.png stay.
  const keep = new Date(Date.parse(job.date + 'T00:00:00Z') - 864e5).toISOString().slice(0, 10);
  for (const f of fs.readdirSync('og')) {
    const m = f.match(/^(\d{4}-\d{2}-\d{2})(-[a-z]+)?\.png$/);
    if (m && m[1] < keep) { fs.unlinkSync('og/' + f); console.log('og removed', f); }
  }
  fs.writeFileSync('og/latest.json', JSON.stringify({ date: job.date, hash: job.hash }) + '\n');
  console.log('fonts', fonts.join(','));
  // A missing web font only makes the picture plainer; never block the update for it.
  if (!fonts.some(f => /Noto Sans/.test(f))) console.log('::warning::分享圖字型未載入，用咗後備字型：' + (fonts.join('、') || '冇'));
  await b.close();
  if (errs.length) { console.log('::error::分享圖程式出錯：' + errs.join('；')); process.exit(1); }
})();
