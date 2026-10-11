// Step 11: static stock pages /<lang>/stock/<TICKER>/ for search engines, from the built /zh/ /en/ /ko/ pages.
// Usage: node tools/stock_pages.js
//
// - Which stocks: mentioned by MIN_ACCOUNTS or more tracked accounts in the last 28 days (the page's own POSTS),
//   ticker confirmed. Pages of stocks that drop out are deleted and leave the sitemap.
// - Content: the page's own stock view (openDive) rendered in each language, without the TradingView card and the
//   price chart, so the text and numbers match the interactive page. A button at the bottom opens the interactive
//   page (/<lang>/#stock/<TICKER>). No page script needed to read it.
// - Avatars are written once to av/<hash>.<ext> and shared by every page.
// - Each language page gets a "stock pages" link row just above the footer; sitemap.xml lists every stock page.
// - Finally opens a few pages at desktop and phone width; fails on sideways overflow or missing text.
const { chromium } = require('playwright');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const SITE = 'https://xmktradar.github.io/';
const LANGS = { zh: 'zh-Hant', en: 'en', ko: 'ko' };
const MIN_ACCOUNTS = 2;
const AV_DIR = 'av';
const MARK = '<!-- stock-index -->';
const T = {
  zh: {
    index: '個股頁面',
    open: '打開互動版（含走勢圖）',
    title: (t, nm, c) => `${t}${nm ? `（${nm}）` : ''} X 大神觀點：看多 ${c.bull}・看空 ${c.bear}・中性 ${c.neu}｜The Crowd Tape`,
    desc: (t, n, c) => `過去 28 天有 ${n} 個追蹤帳號提及 $${t}：看多 ${c.bull}、中性 ${c.neu}、看空 ${c.bear}、未表態 ${c.none}。查看每個帳號的最新觀點、理由與原帖，每 4 小時更新，不構成投資建議。`,
  },
  en: {
    index: 'Stock pages',
    open: 'Open the interactive page (with chart)',
    title: (t, nm, c) => `${t}${nm ? ` (${nm})` : ''} on X: ${c.bull} bullish, ${c.bear} bearish, ${c.neu} neutral | The Crowd Tape`,
    desc: (t, n, c) => `${n} tracked X accounts mentioned $${t} in the last 28 days: ${c.bull} bullish, ${c.neu} neutral, ${c.bear} bearish, ${c.none} no stance. Each account's latest view, reasons and original post, updated every 4 hours. Not investment advice.`,
  },
  ko: {
    index: '종목 페이지',
    open: '인터랙티브 페이지 열기(차트 포함)',
    title: (t, nm, c) => `${t}${nm ? ` (${nm})` : ''} X 고수 관점: 강세 ${c.bull}・약세 ${c.bear}・중립 ${c.neu} | The Crowd Tape`,
    desc: (t, n, c) => `최근 28일 동안 추적 계정 ${n}개가 $${t}를 언급했다: 강세 ${c.bull}, 중립 ${c.neu}, 약세 ${c.bear}, 입장 없음 ${c.none}. 계정별 최신 관점, 근거와 원문을 4시간마다 업데이트한다. 투자 조언이 아닙니다.`,
  },
};

const slug = t => t.replace(/[^A-Za-z0-9.\-]/g, '_');  // same as px/ file names
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

function shell(master, lang, t, list, body, meta) {
  const head = master.slice(0, master.indexOf('</head>'));
  const styles = (head.match(/<style[^>]*>[\s\S]*?<\/style>/g) || []).join('\n');
  const ga = (head.match(/<script async src="https:\/\/www\.googletagmanager\.com[^>]*><\/script>\s*<script>window\.dataLayer[\s\S]*?<\/script>/) || [''])[0];
  const fonts = (head.match(/<link rel="(?:preconnect|stylesheet)"[^>]*>/g) || []).join('');
  const brand = (master.match(/<div class="brand-wrap">([\s\S]*?)<nav class="lang-sw"/) || ['', ''])[1]
    .replace(/<h1 class="brand">([\s\S]*?)<\/h1>/, `<a href="/${lang}/" class="brand-home"><p class="brand">$1</p></a>`);
  const url = `${SITE}${lang}/stock/${slug(t)}/`;
  const alt = Object.entries(LANGS).map(([k, h]) => `<link rel="alternate" hreflang="${h}" href="${SITE}${k}/stock/${slug(t)}/">`).join('')
    + `<link rel="alternate" hreflang="x-default" href="${SITE}zh/stock/${slug(t)}/">`;
  const sw = Object.keys(LANGS).map(k => `<a href="/${k}/stock/${slug(t)}/"${k === lang ? ' aria-current="page"' : ''}>${{ zh: '中', en: 'EN', ko: '한' }[k]}</a>`).join('');
  return `<!DOCTYPE html>
<html lang="${LANGS[lang]}" data-theme="light"><head>
${ga}
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="192x192" href="/assets/icon-192.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="robots" content="index,follow">
<title>${esc(meta.title)}</title>
<meta name="description" content="${esc(meta.desc)}">
<meta property="og:title" content="${esc(meta.title)}">
<meta property="og:description" content="${esc(meta.desc)}">
<meta property="og:url" content="${url}">
<meta property="og:type" content="article">
<meta property="og:image" content="${SITE}og/latest${lang === 'zh' ? '' : '-' + lang}.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="${SITE}og/latest${lang === 'zh' ? '' : '-' + lang}.png">
<link rel="canonical" href="${url}">${alt}
${fonts}
${styles}
<style>.brand-home{color:inherit;text-decoration:none}.stock-static{padding-top:8px}.stock-static .back{text-decoration:none;display:inline-block}
.open-live{display:flex;justify-content:center;margin:8px 0 40px}.open-live a{font:600 15px/1 var(--f-body);padding:12px 20px;border-radius:999px;
background:var(--accent);color:#fff;text-decoration:none}</style>
</head>
<body>
<header class="top"><div class="wrap"><div class="brand-wrap">${brand}<nav class="lang-sw" aria-label="Language">${sw}</nav></div></div></header>
<main class="stock-static">${body}
<div class="open-live"><a href="/${lang}/#stock/${encodeURIComponent(t)}">${esc(T[lang].open)}</a></div>
${indexRow(lang, list)}</main>
</body></html>
`;
}

function indexRow(lang, list) {
  const links = list.map(t => `<a href="/${lang}/stock/${slug(t)}/">${esc(t)}</a>`).join(' ');
  return `<nav class="wrap stock-index" aria-label="${esc(T[lang].index)}" style="font-size:12.5px;line-height:2;color:var(--muted);padding:12px 16px 28px">`
    + `<b>${esc(T[lang].index)}</b>：${links}</nav>`;
}

function avatars(html, seen) {
  return html.replace(/src="(data:image\/(png|jpe?g|webp|gif);base64,([^"]+))"/g, (m, uri, ext, b64) => {
    const h = crypto.createHash('sha1').update(b64).digest('hex').slice(0, 12);
    const f = `${h}.${ext === 'jpeg' ? 'jpg' : ext}`;
    if (!seen.has(f)) {
      seen.add(f);
      fs.writeFileSync(path.join(AV_DIR, f), Buffer.from(b64, 'base64'));
    }
    return `src="/${AV_DIR}/${f}" loading="lazy"`;
  });
}

(async () => {
  const b = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  fs.mkdirSync(AV_DIR, { recursive: true });
  const seen = new Set();
  let list = null;
  const urls = [];
  for (const lang of Object.keys(LANGS)) {
    const file = path.resolve(lang, 'index.html');
    const p = await b.newPage();
    const errs = [];
    p.on('pageerror', e => errs.push(e.message));
    await p.route(/^https?:/, r => r.abort());
    await p.goto('file://' + file + '#daily');
    await p.waitForFunction(() => typeof openDive === 'function' && typeof POSTS !== 'undefined');
    if (!list) {
      list = await p.evaluate((min) => {
        const lim = addDays(TODAY, -27), m = {};
        POSTS.forEach(x => { if (x.d >= lim) (m[x.t] = m[x.t] || new Set()).add(x.acc) });
        return Object.entries(m).filter(([t, s]) => s.size >= min && !UNC(t)).map(([t, s]) => [t, s.size])
          .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
      }, MIN_ACCOUNTS);
    }
    const names = list.map(x => x[0]);
    const pages = await p.evaluate(({ names, lang }) => names.map(t => {
      openDive(t);
      const el = document.getElementById('dive').cloneNode(true);
      el.querySelectorAll('.tv-card,.lang-sw,script').forEach(x => x.remove());
      const ch = el.querySelector('#chart');
      if (ch) {
        const sec = ch.closest('section');
        const dim = sec.previousElementSibling;
        if (dim && dim.classList.contains('dim')) dim.remove();
        sec.remove();
      }
      const back = el.querySelector('button.back');
      if (back) back.outerHTML = `<a class="back" href="/${lang}/">${back.innerHTML}</a>`;
      el.querySelectorAll('button.tk[data-tk]').forEach(x => { x.outerHTML = `<a class="${x.className}" href="#stock/${encodeURIComponent(x.dataset.tk)}">${x.innerHTML}</a>` });
      el.querySelectorAll('[id]').forEach(x => x.removeAttribute('id'));
      const v = [...el.querySelectorAll('.kpis .kpi .v')].map(x => parseInt(x.textContent, 10) || 0);
      const pr = (D.prices || {})[t];
      const name = pr && pr.name ? pr.name : ((D.overrides || {})[t] || {}).name || '';
      return { t, name, c: { bull: v[0] || 0, neu: v[1] || 0, none: v[2] || 0, bear: v[3] || 0 }, html: el.innerHTML };
    }), { names, lang });
    if (errs.length) { console.log('::error::股票網頁生成時有錯誤：' + errs.join('；')); process.exit(1); }
    const master = fs.readFileSync(file, 'utf8');
    const have = new Set(names.map(slug));
    const dir = path.join(lang, 'stock');
    fs.mkdirSync(dir, { recursive: true });
    for (const d of fs.readdirSync(dir)) if (!have.has(d)) fs.rmSync(path.join(dir, d), { recursive: true, force: true });
    const n = Object.fromEntries(list);
    for (const pg of pages) {
      let body = pg.html.replace(/href="#stock\/([^"]+)"/g, (m, k) => {
        const tk = decodeURIComponent(k);
        return names.includes(tk) ? `href="/${lang}/stock/${slug(tk)}/"` : `href="/${lang}/#stock/${k}"`;
      }).replace(/href="#(account\/[^"]+)"/g, `href="/${lang}/#$1"`);
      body = avatars(body, seen);
      const meta = { title: T[lang].title(pg.t, pg.name, pg.c), desc: T[lang].desc(pg.t, n[pg.t], pg.c) };
      fs.mkdirSync(path.join(dir, slug(pg.t)), { recursive: true });
      fs.writeFileSync(path.join(dir, slug(pg.t), 'index.html'), shell(master, lang, pg.t, names, body, meta));
      urls.push(`${lang}/stock/${slug(pg.t)}/`);
    }
    // link row above the footer of the language page
    let s = master.replace(new RegExp(MARK + '[\\s\\S]*?' + MARK), '');
    s = s.replace('<footer class="wrap foot" id="foot">', MARK + indexRow(lang, names) + MARK + '<footer class="wrap foot" id="foot">');
    fs.writeFileSync(file, s);
    await p.close();
  }
  for (const f of fs.readdirSync(AV_DIR)) if (!seen.has(f)) fs.rmSync(path.join(AV_DIR, f));

  // sitemap: drop old stock rows, add the current ones
  let sm = fs.readFileSync('sitemap.xml', 'utf8').replace(/\s*<url><loc>[^<]*\/stock\/[^<]*<\/loc>[\s\S]*?<\/url>/g, '');
  const gen = (sm.match(/<loc>https:\/\/xmktradar\.github\.io\/<\/loc><lastmod>([^<]+)/) || [])[1] || '';
  const rows = list.map(([t]) => {
    const alt = Object.entries(LANGS).map(([k, h]) => `<xhtml:link rel="alternate" hreflang="${h}" href="${SITE}${k}/stock/${slug(t)}/"/>`).join('');
    return Object.keys(LANGS).map(k => `  <url><loc>${SITE}${k}/stock/${slug(t)}/</loc><lastmod>${gen}</lastmod><changefreq>daily</changefreq>${alt}</url>`).join('\n');
  }).join('\n');
  sm = sm.replace('</urlset>', rows + '\n</urlset>');
  fs.writeFileSync('sitemap.xml', sm);

  // check a few pages at desktop and phone width
  const bad = [];
  for (const u of [urls[0], urls[Math.floor(urls.length / 2)], urls[urls.length - 1]].filter(Boolean)) {
    for (const w of [1280, 390]) {
      const p = await b.newPage({ viewport: { width: w, height: 844 }, javaScriptEnabled: false });
      await p.route(/^https?:/, r => r.abort());
      await p.goto('file://' + path.resolve(u, 'index.html'));
      const info = await p.evaluate(() => ({ ovf: document.documentElement.scrollWidth > innerWidth + 1, len: document.body.innerText.length }));
      const ok = !info.ovf && info.len > 500;
      console.log(`${ok ? 'ok ' : 'BAD'} ${w}px ${u}`, info.ovf ? 'overflow' : '', info.len);
      if (!ok) bad.push(`${w}px ${u}`);
      await p.close();
    }
  }
  await b.close();
  console.log(`股票網頁：${list.length} 隻 × ${Object.keys(LANGS).length} 個語言，頭像 ${seen.size} 個`);
  if (bad.length) { console.log('::error::股票網頁檢查唔合格：' + bad.join('、')); process.exit(1); }
})();
