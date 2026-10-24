// Static Instagram follow/save CTA cards (1080×1350 JPEG), one per language.
// Reuses tools/carousel.html render(kind: 'igcta'). No characters, no personal names, no URLs.
//
// Usage (from repo root):
//   NODE_PATH=/tmp/pw/node_modules CHROME_PATH=/usr/bin/google-chrome node tools/ig_cta.js
//
// Writes og/cta/ig-cta-{zh,en,ko}.jpg
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const CTA = {
  zh: {
    kicker: '收藏＋追蹤',
    lead: '覺得有用？',
    sub: '收藏＋追蹤 @thecrowdtape，每日睇大神共識',
    save: '收藏＋追蹤',
  },
  en: {
    kicker: 'Save + follow',
    lead: 'Found this useful?',
    sub: 'Save + follow @thecrowdtape for daily consensus',
    save: 'Save + follow',
  },
  ko: {
    kicker: '저장 + 팔로우',
    lead: '유용했다면',
    sub: '저장 + 팔로우 @thecrowdtape',
    save: '저장 + 팔로우',
  },
};

(async () => {
  const b = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  const p = await b.newPage({ viewport: { width: 1080, height: 1350 } });
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + path.resolve(__dirname, 'carousel.html'), { waitUntil: 'networkidle' });
  fs.mkdirSync('og/cta', { recursive: true });
  for (const lang of ['zh', 'en', 'ko']) {
    const slide = { kind: 'igcta', ...CTA[lang] };
    await p.evaluate(([l, t, d, n, s]) => render(l, t, d, n, s), [lang, 'snap', '', 0, slide]);
    await p.evaluate(async () => {
      const want = ['900 46px "Noto Sans TC"', '700 32px "Noto Sans TC"', '900 46px "Noto Sans KR"', '700 48px "IBM Plex Mono"'];
      const t = new Promise(r => setTimeout(r, 20000));
      await Promise.race([Promise.all(want.map(f => document.fonts.load(f, document.body.innerText))), t]);
      await document.fonts.ready;
      await Promise.all([...document.images].map(i => i.decode().catch(() => {})));
    });
    const out = `og/cta/ig-cta-${lang}.jpg`;
    await p.screenshot({ path: out, type: 'jpeg', quality: 88 });
    console.log('ig cta', out);
  }
  await b.close();
  if (errs.length) { console.log('::error::IG CTA 圖程式出錯：' + errs.join('；')); process.exit(1); }
})();
