// Layout check that replaces the Grok bot's daily 11:05 layout check (Tim, 2026-10-12).
// Opens /zh/, /en/, /ko/ on the daily tab at desktop and iPhone width and writes what it finds
// into data/site-status.json as layout_warnings (empty = all fine). Never fails the build.
// Usage: node tools/layout_check.js
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { start, pageUrl } = require('./local_server');

const STATUS = 'data/site-status.json';
const HAN = /[一-鿿]/;

async function ready(p) {
  try {
    await p.evaluate(async () => {
      if (window.__loadCore) await window.__loadCore();
      if (window.__loadAllPosts) await window.__loadAllPosts();
      if (typeof paintChrome === 'function') paintChrome();
      if (typeof render === 'function') render();
    });
  } catch (e) {
    return (e && e.message) || String(e);
  }
  if (await p.evaluate(() => !!window.__postsFailed)) return 'older posts failed to load';
  return '';
}

(async () => {
  const root = path.resolve(__dirname, '..');
  const srv = await start(root);
  const b = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  const warn = [];
  try {
  for (const lang of ['zh', 'en', 'ko']) {
    const file = pageUrl(srv.origin, root, path.join(lang, 'index.html'));
    for (const [w, h] of [[1280, 900], [390, 844]]) {
      const where = `${lang} ${w}px`;
      const p = await b.newPage({ viewport: { width: w, height: h } });
      await p.route('**/*', route => {
        if (route.request().url().startsWith(srv.origin)) route.continue();
        else route.abort();
      });
      await p.goto(file + '#daily', { waitUntil: 'domcontentloaded' });
      const loadErr = await ready(p);
      if (loadErr) warn.push(`${where}：${loadErr}`);
      await p.waitForTimeout(300);
      const r = await p.evaluate(({ lang, han }) => {
        const HAN = new RegExp(han);
        const vis = el => el.offsetParent !== null;
        const text = document.body.innerText;
        const bad = (text.match(/\b(undefined|NaN)\b|\bnull\b(?=[\s,，。:：)]|$)/g) || []);
        // Untranslated interface text: headings, buttons, tabs and table headers only (post text may quote Chinese).
        const ui = lang === 'zh' ? [] : [...document.querySelectorAll('h1,h2,h3,h4,h5,button,th,nav a,[role=tab]')]
          .filter(e => vis(e) && !e.closest('.lang-sw')).map(e => e.innerText.trim()).filter(t => t && HAN.test(t)).slice(0, 5);
        const cards = document.querySelectorAll('.hl-sec article.hl').length;
        const srch = document.getElementById('srch-btn');
        const bg = getComputedStyle(document.body).backgroundColor.match(/\d+/g).slice(0, 3).map(Number);
        const lum = (0.2126 * bg[0] + 0.7152 * bg[1] + 0.0722 * bg[2]) / 255;
        return { bad: [...new Set(bad)], ui, cards, srch: !!(srch && vis(srch)), lum,
                 ovf: document.documentElement.scrollWidth > innerWidth + 1 };
      }, { lang, han: HAN.source });
      if (r.bad.length) warn.push(`${where}：頁面出現 ${r.bad.join('、')}`);
      if (r.ui.length) warn.push(`${where}：介面有未翻譯中文：${r.ui.join(' / ')}`);
      if (r.cards !== 3) warn.push(`${where}：今日重點卡有 ${r.cards} 張（應該 3 張）`);
      if (!r.srch) warn.push(`${where}：🔍 搵股票掣唔見咗`);
      if (r.lum < 0.75) warn.push(`${where}：背景唔係淺色`);
      if (r.ovf) warn.push(`${where}：頁面闊過畫面（打橫撐闊）`);
      if (r.srch && w === 390) {
        await p.click('#srch-btn');
        await p.fill('#srch-q', 'nvda');
        await p.waitForTimeout(400);
        const hit = await p.$$eval('#srch-r li[data-t]', l => l.map(e => e.dataset.t));
        if (!hit.includes('NVDA')) warn.push(`${where}：搜尋 nvda 搵唔到 NVDA`);
      }
      // 宏觀分頁（2026-10-13）
      await p.goto(file + '#macro', { waitUntil: 'domcontentloaded' });
      const macroErr = await ready(p);
      if (macroErr) warn.push(`${where}：宏觀分頁 ${macroErr}`);
      await p.waitForTimeout(300);
      const m = await p.evaluate(({ lang, han }) => {
        const HAN = new RegExp(han);
        const sec = document.querySelector('.m-sec');
        const text = sec ? sec.innerText : '';
        const ui = lang === 'zh' || !sec ? [] : [...sec.querySelectorAll('h2,.m-nm,summary .note')]
          .map(e => e.innerText.trim()).filter(t => t && HAN.test(t)).slice(0, 5);
        return { themes: document.querySelectorAll('.m-th').length, ui,
                 bad: [...new Set(text.match(/\b(undefined|NaN)\b/g) || [])],
                 ovf: document.documentElement.scrollWidth > innerWidth + 1 };
      }, { lang, han: HAN.source });
      if (m.themes !== 9) warn.push(`${where}：宏觀分頁有 ${m.themes} 個主題（應該 9 個）`);
      if (m.bad.length) warn.push(`${where}：宏觀分頁出現 ${m.bad.join('、')}`);
      if (m.ui.length) warn.push(`${where}：宏觀分頁有未翻譯中文：${m.ui.join(' / ')}`);
      if (m.ovf) warn.push(`${where}：宏觀分頁闊過畫面`);
      await p.close();
    }
  }
  } finally {
    await b.close();
    srv.server.close();
  }
  const st = JSON.parse(fs.readFileSync(STATUS, 'utf8'));
  st.layout_warnings = warn;
  st.layout_checked_hkt = new Date(Date.now() + 8 * 3600e3).toISOString().slice(0, 16).replace('T', ' ');
  fs.writeFileSync(STATUS, JSON.stringify(st, null, 1) + '\n');
  console.log(warn.length ? warn.join('\n') : '版面正常');
})();
