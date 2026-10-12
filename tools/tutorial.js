// Draw the weekend guide pictures. Usage: node tools/tutorial.js work/tutorial.json
// For each language: opens the built page (served from the repo folder) at iPhone size, screenshots the feature the
// episode is about, then draws og/tutorial-<lang>.png (1080x1350) and og/tutorial-story-<lang>.png (1080x1920)
// from tools/tutorial.html. Shot fields (data/tutorial-episodes.json): go = page and hash, sel = CSS selector or
// @top for the first screen, part = [first, last] child elements to frame, search = text to type in the 🔍 box,
// image = an existing picture to show instead of a screenshot.
const { chromium } = require('playwright');
const fs = require('fs');
const http = require('http');
const path = require('path');

const ROOT = process.cwd();
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.json': 'application/json', '.css': 'text/css',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.xml': 'application/xml' };
const W = 390, SHOT_H = 693;  // a 9:16 phone screen at iPhone width

function serve() {
  const srv = http.createServer((req, res) => {
    let f = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    f = path.join(ROOT, path.normalize(f).replace(/^(\.\.[/\\])+/, ''));
    if (fs.existsSync(f) && fs.statSync(f).isDirectory()) f = path.join(f, 'index.html');
    if (!f.startsWith(ROOT) || !fs.existsSync(f)) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(f)] || 'application/octet-stream' });
    fs.createReadStream(f).pipe(res);
  });
  return new Promise(r => srv.listen(0, '127.0.0.1', () => r(srv)));
}

async function shoot(page, base, lang, shot, warn) {
  if (shot.image) {
    const f = shot.image;
    if (fs.existsSync(f)) return { wide: true, png: fs.readFileSync(f) };
    warn(`教學圖：搵唔到 ${f}，改用網站首頁截圖`);
    shot = { go: '', sel: '@top' };
  }
  await page.goto(`${base}/${lang}/${shot.go || ''}`, { waitUntil: 'networkidle' });
  await page.addStyleTag({ content: '.donate-fab{display:none!important}' });
  await page.waitForTimeout(1200);
  if (shot.search) {
    await page.click('#srch-btn');
    await page.fill('#srch-q', shot.search);
    await page.waitForTimeout(800);
  }
  let top = 0;
  if (shot.sel !== '@top') {
    top = await page.evaluate(([sel, part]) => {
      const el = document.querySelector(sel);
      if (!el || !el.getBoundingClientRect().height) return null;
      const first = part ? el.children[part[0]] || el : el;
      first.scrollIntoView({ block: 'start' });
      // Leave room for the sticky tab bar.
      const sc = first.closest('#dive') || window;
      sc.scrollBy(0, -64);
      return Math.max(0, first.getBoundingClientRect().top - 12);
    }, [shot.sel, shot.part || null]);
    if (top === null) {
      warn(`教學圖：${lang} 頁面搵唔到 ${shot.sel}，改用第一個畫面`);
      await page.evaluate(() => window.scrollTo(0, 0));
      top = 0;
    }
    await page.waitForTimeout(400);
  }
  const png = await page.screenshot({ clip: { x: 0, y: top, width: W, height: SHOT_H } });
  return { wide: false, png };
}

(async () => {
  const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const srv = await serve();
  const base = `http://127.0.0.1:${srv.address().port}`;
  const b = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  const errs = [], warns = [];
  const warn = m => { warns.push(m); console.log('::warning::' + m); };
  // Tall viewport so a section scrolled to the top always has a full phone screen below it.
  const site = await b.newPage({ viewport: { width: W, height: 1400 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const art = await b.newPage({ viewport: { width: 1080, height: 1350 } });
  art.on('pageerror', e => errs.push(e.message));
  await art.goto('file://' + path.resolve(__dirname, 'tutorial.html'), { waitUntil: 'networkidle' });
  fs.mkdirSync('og', { recursive: true });
  for (const lang of ['zh', 'en', 'ko']) {
    const L = job.langs[lang];
    const { wide, png } = await shoot(site, base, lang, L.shot, warn);
    const pic = 'data:image/png;base64,' + png.toString('base64');
    for (const [size, h, out] of [['feed', 1350, `og/tutorial-${lang}.png`], ['story', 1920, `og/tutorial-story-${lang}.png`]]) {
      await art.setViewportSize({ width: 1080, height: h });
      await art.evaluate(([l, d, p, s]) => render(l, d, p, s), [lang, { episode: job.episode, total: job.total, title: L.title, how: L.how, wide }, pic, size]);
      await art.evaluate(async () => {
        const want = ['900 60px "Noto Sans TC"', '900 60px "Noto Sans KR"', '700 30px "IBM Plex Mono"'];
        const t = new Promise(r => setTimeout(r, 20000));
        await Promise.race([Promise.all(want.map(f => document.fonts.load(f, document.body.innerText))), t]);
        await document.fonts.ready;
        await Promise.all([...document.images].map(i => i.decode().catch(() => {})));
      });
      await art.screenshot({ path: out });
      console.log('tutorial', out);
    }
  }
  await b.close();
  srv.close();
  if (errs.length) { console.log('::error::教學圖程式出錯：' + errs.join('；')); process.exit(1); }
})();
