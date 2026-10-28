// Step 11b: static account pages /<lang>/account/<handle>/ for search engines, from the built /zh/ /en/ pages.
// Usage: node tools/account_pages.js   (runs after stock_pages.js)
//
// Spec: /mnt/project-files/dashboard/account-pages-spec.md (Tim, 2026-10-28).
// - Which accounts: tracked accounts whose current stance on MIN_STOCKS or more confirmed tickers is
//   bullish or bearish, with that stance posted in the last 28 days. Pages of accounts that drop out
//   (or leave the tracked list) are deleted and leave the sitemap.
// - Each stock row: stance, the day the current stance started, the latest reason with its post link,
//   a link to the stock page (when one exists) and the price change since the stance started.
//   Start price = last daily close before the post (a post after the 16:00 ET close uses that day's close).
//   A stance flip (bull <-> bear, or via neutral) restarts the count from the flip post.
//   A ratio over 5x or under 0.2x shows "no price" (split or bad quote). No ranking and no "accuracy" wording.
// - Stock pages: account links /<lang>/#account/<h> point to the account page when one exists.
// - Homepages (/zh/, /en/ and the root master) get an "account pages" row under the stock pages row.
// - Readable without JS. Finally opens a few pages at desktop and phone width; fails on sideways overflow.
const fs = require('fs');
const path = require('path');
const { start, pageUrl } = require('./local_server');
const { avatars, dedupeSitemap, esc, slug: tkSlug, toTop } = require('./stock_pages.js');

const SITE = 'https://thecrowdtape.com/';
const LANGS = { zh: 'zh-Hant', en: 'en' };
const MIN_STOCKS = 2;
const MARK = '<!-- account-index -->';
const STOCK_MARK = '<!-- stock-index -->';
const FOOT = '<footer class="wrap foot" id="foot">';
const hSlug = h => String(h).toLowerCase().replace(/[^a-z0-9_]/g, '');

const T = {
  zh: {
    index: '帳號頁面',
    top: '回到頂部',
    home: '首頁',
    open: '打開互動版（全部貼文）',
    profile: p => `${p} 個人頁 ↗`,
    tools: '工具',
    support: '支持我哋',
    news: '電子報',
    nav: '網站',
    stance: { bull: '看多', bear: '看空', neu: '中性' },
    since: (d, s) => `${d} 起${s}`,
    after: '之後',
    noPx: '未有股價',
    newPx: '未有新收市價',
    prev: s => `之前${s}`,
    why: '理由',
    post: '原始貼文 ↗',
    stockPage: '個股頁',
    summary: (b, r) => `過去 28 天明確看多 ${b} 隻、看空 ${r} 隻股票。`,
    note: '只計算表態後的股價變化，不代表帳號準確度，不構成投資建議。',
    pxNote: '起點為發帖前最後一個收市價，終點為最新收市價（Yahoo Finance），非即時報價。',
    advice: '不構成投資建議。本頁只整理公開貼文，供參考。',
    title: (nm, h) => `${nm}（@${h}）最近看多、看空哪些股票？｜The Crowd Tape`,
    desc: (h, b, r, ts) => `過去 28 天 @${h} 明確看多 ${b} 隻、看空 ${r} 隻股票：${ts}。查看每隻股票的立場、理由、原帖及表態後股價變化，每 4 小時更新，不構成投資建議。`,
    upd: '更新時間',
  },
  en: {
    index: 'Account pages',
    top: 'Back to top',
    home: 'Home',
    open: 'Open the interactive page (all posts)',
    profile: p => `${p} profile ↗`,
    tools: 'Tools',
    support: 'Support us',
    news: 'Newsletter',
    nav: 'Site',
    stance: { bull: 'Bullish', bear: 'Bearish', neu: 'Neutral' },
    since: (d, s) => `${s} since ${d}`,
    after: 'since then',
    noPx: 'No price yet',
    newPx: 'No new close yet',
    prev: s => `was ${s}`,
    why: 'Reason',
    post: 'Original post ↗',
    stockPage: 'Stock page',
    summary: (b, r) => `Clearly bullish on ${b} and bearish on ${r} stocks in the last 28 days.`,
    note: 'Shows only the price change since the stance. It does not measure the account\'s accuracy. Not investment advice.',
    pxNote: 'Start = last daily close before the post; end = latest daily close (Yahoo Finance). Not a live quote.',
    advice: 'Not investment advice. This page only summarises public posts.',
    title: (nm, h) => `${nm} (@${h}): which stocks are they bullish or bearish on? | The Crowd Tape`,
    desc: (h, b, r, ts) => `In the last 28 days @${h} was bullish on ${b} and bearish on ${r} stocks: ${ts}. Each stance, reason, original post and the price change since, updated every 4 hours. Not investment advice.`,
    upd: 'Updated',
  },
};

// Runs inside the built language page: accounts that qualify, with every number the page shows.
function collect(min) {
  const lim = addDays(TODAY, -27);
  const et = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
  const etOf = ms => {
    const o = {};
    et.formatToParts(new Date(ms)).forEach(x => { o[x.type] = x.value; });
    return { d: `${o.year}-${o.month}-${o.day}`, hm: +o.hour * 60 + +o.minute };
  };
  const dayGap = (a, b) => (Date.parse(b) - Date.parse(a)) / 864e5;
  function price(t, ms) {
    const pr = (D.prices || {})[t];
    const c = pr && Array.isArray(pr.c) ? pr.c.filter(x => Array.isArray(x) && typeof x[1] === 'number' && x[1] > 0) : [];
    if (!c.length) return { state: 'none' };
    const e = etOf(ms);
    const after = e.hm >= 16 * 60;
    let base = null;
    for (const x of c) if (after ? x[0] <= e.d : x[0] < e.d) base = x;
    // closes are sparse a year back; a base far from the post is not the real "last close before"
    if (!base || dayGap(base[0], e.d) > 6) return { state: 'none' };
    const last = c[c.length - 1];
    if (last[0] <= base[0]) return { state: 'new', base: base[1], baseD: base[0] };
    // a move this big inside 28 days is a split or a bad quote, not a real change (WFF 17.28 -> 0.06, 2026-10-27)
    if (last[1] / base[1] > 5 || last[1] / base[1] < 0.2) return { state: 'none' };
    return { state: 'ok', base: base[1], baseD: base[0], now: last[1], nowD: last[0], pct: (last[1] / base[1] - 1) * 100 };
  }
  const out = [];
  for (const h of HANDLES) {
    const xs = POSTS.filter(x => x.acc.toLowerCase() === String(h).toLowerCase()).sort((a, b) => a.ms - b.ms);
    if (!xs.length) continue;
    const real = xs[0].acc;
    const byT = {};
    xs.forEach(x => { (byT[x.t] = byT[x.t] || []).push(x); });
    const stocks = [];
    for (const [t, rows] of Object.entries(byT)) {
      if (UNC(t)) continue;
      const st = rows.filter(x => x.s !== 'none');
      if (!st.length) continue;
      const cur = st[st.length - 1];
      if (cur.d < lim || (cur.s !== 'bull' && cur.s !== 'bear')) continue;
      let i = st.length - 1;
      while (i > 0 && st[i - 1].s === cur.s) i--;
      const first = st[i];
      const prev = i > 0 ? st[i - 1].s : '';
      stocks.push({
        t, s: cur.s, prev,
        since: first.p.time_hkt.slice(0, 10),
        lastMs: cur.ms,
        why: String(cur.why || '').trim(),
        url: cur.url || (cur.p && cur.p.url) || '',
        px: price(t, first.ms),
      });
    }
    if (stocks.length < min) continue;
    stocks.sort((a, b) => b.lastMs - a.lastMs || a.t.localeCompare(b.t));
    const info = accInfo(real);
    out.push({
      h: real,
      name: nameOf(real),
      bio: info.bio || '',
      avatar: info.avatar && /^data:image\//.test(info.avatar) ? info.avatar : '',
      xUrl: xUrl(real),
      plat: platName(real),
      stocks,
      modified: xs[xs.length - 1].p.time_utc || '',
    });
  }
  return { accounts: out, today: TODAY, gen: (D.meta && (D.meta.cutoff_hkt || D.meta.generated_hkt)) || '' };
}

const fmtPx = v => v >= 100 ? v.toFixed(2) : v >= 1 ? v.toFixed(2) : v.toPrecision(3);
function pxLine(lang, px) {
  const L = T[lang];
  if (px.state === 'none') return `<span class="ac-px na">${esc(L.noPx)}</span>`;
  if (px.state === 'new') return `<span class="ac-px na">${esc(L.newPx)}</span>`;
  const p = Math.round(px.pct * 10) / 10 || 0;
  const cls = p > 0 ? 'up' : p < 0 ? 'down' : 'flat';
  const sign = p > 0 ? '+' : '';
  return `<span class="ac-px"><span class="ac-pct ${cls}">${esc(L.after)} ${sign}${p.toFixed(1)}%</span> <small>${fmtPx(px.base)} → ${fmtPx(px.now)}</small></span>`;
}

function stockRow(lang, x, pages) {
  const L = T[lang];
  const href = pages.has(tkSlug(x.t)) ? `/${lang}/stock/${tkSlug(x.t)}/` : `/${lang}/#stock/${encodeURIComponent(x.t)}`;
  const why = x.why ? `<p class="ac-why"><b>${esc(L.why)}${lang === 'zh' ? '：' : ': '}</b>${esc(x.why.length > 420 ? x.why.slice(0, 417) + '…' : x.why)}</p>` : '';
  const prev = x.prev && x.prev !== x.s && L.stance[x.prev] ? ` <span class="ac-prev">${esc(L.prev(L.stance[x.prev]))}</span>` : '';
  return `<li class="ac-row"><div class="ac-top"><a class="ac-tk" href="${href}">$${esc(x.t)}</a> <span class="pill ${x.s}">${esc(L.stance[x.s])}</span>${prev}</div>`
    + `<p class="ac-meta">${esc(L.since(x.since, L.stance[x.s]))} · ${pxLine(lang, x.px)}</p>${why}`
    + (x.url ? `<p class="ac-link"><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(L.post)}</a></p>` : '')
    + '</li>';
}

function body(lang, a, pages, avSrc) {
  const L = T[lang];
  const b = a.stocks.filter(x => x.s === 'bull').length, r = a.stocks.length - b;
  const av = avSrc ? `<img class="ac-av" src="${avSrc}" alt="" width="64" height="64">` : '';
  return `<div class="wrap ac-wrap"><p class="advice" role="note">${esc(L.advice)}</p><nav class="ac-crumb"><a href="/${lang}/">${esc(L.home)}</a> › <a href="/${lang}/#account-index">${esc(L.index)}</a></nav>
<div class="ac-head">${av}<div class="ac-id"><h1>${esc(a.name)}</h1><p class="ac-h">@${esc(a.h)} · <a href="${esc(a.xUrl)}" target="_blank" rel="noopener">${esc(L.profile(a.plat))}</a></p></div></div>
${a.bio ? `<p class="ac-bio">${esc(a.bio)}</p>` : ''}
<p class="ac-sum">${esc(L.summary(b, r))}</p>
<p class="ac-note" role="note">${esc(L.note)}</p>
<ul class="ac-list">${a.stocks.map(x => stockRow(lang, x, pages)).join('')}</ul>
<p class="ac-px-note">${esc(L.pxNote)}</p>
</div>`;
}

const CSS = `.ac-wrap{padding:8px 16px 8px;max-width:860px;box-sizing:border-box}
.ac-crumb{font-size:13px;margin:6px 0 12px;color:var(--muted,#87776a)}.ac-crumb a{color:inherit}
.ac-head{display:flex;align-items:center;gap:14px;min-width:0}
.ac-av{width:64px;height:64px;border-radius:50%;object-fit:cover;flex:0 0 64px;background:var(--panel2,#eee)}
.ac-id{min-width:0}.ac-id h1{margin:0;font-size:24px;line-height:1.25;overflow-wrap:anywhere}
.ac-h{margin:4px 0 0;font-size:14px;color:var(--muted,#87776a);overflow-wrap:anywhere}
.ac-bio{margin:12px 0 0;font-size:14px;line-height:1.5;color:var(--muted,#87776a);overflow-wrap:anywhere}
.ac-sum{margin:14px 0 6px;font-size:16px;font-weight:600}
.ac-note{margin:0 0 14px;padding:8px 12px;border-radius:12px;background:var(--accent-soft,#f8ecda);font-size:13px;line-height:1.45}
.ac-list{list-style:none;margin:0;padding:0;display:grid;gap:10px}
.ac-row{min-width:0;padding:12px 14px;border-radius:16px;background:var(--panel,#fff);border:1px solid var(--line,#ece1cc)}
.ac-top{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px}
.ac-tk{font:700 17px/1.2 var(--f-data,ui-monospace,monospace);text-decoration:none;color:var(--tx-strong,var(--ink,#3b2f24))}
.ac-prev{font-size:12px;color:var(--muted,#87776a)}
.ac-meta{margin:6px 0 0;font-size:13.5px;line-height:1.5;overflow-wrap:anywhere}
.ac-px small{color:var(--muted,#87776a);font-family:var(--f-data,ui-monospace,monospace)}
.ac-pct{font-weight:700;font-family:var(--f-data,ui-monospace,monospace)}
.ac-pct.up{color:var(--up,#1a7f37)}.ac-pct.down{color:var(--down,#c0392b)}.ac-px.na{color:var(--muted,#87776a)}
.ac-why{margin:6px 0 0;font-size:14px;line-height:1.5;overflow-wrap:anywhere;white-space:pre-line}
.ac-link{margin:4px 0 0;font-size:13px}
.ac-px-note{margin:12px 0 0;font-size:12px;color:var(--muted,#87776a)}
.open-live{display:flex;justify-content:center;margin:18px 0 32px}.open-live a{font:600 15px/1 var(--f-body);padding:12px 20px;border-radius:999px;background:var(--accent);color:#fff;text-decoration:none}
.brand-home{color:inherit;text-decoration:none}
.lang-sw{position:static!important;float:none!important;inset:auto!important;margin:6px 0 2px!important;justify-content:flex-start}
.brand-wrap .lang-sw{display:flex;flex-wrap:wrap}
@media(max-width:700px){header.top{position:static}}
.advice{margin:8px 0 0;padding:10px 12px;border-radius:16px;background:var(--accent-soft);font-size:14px;line-height:1.45}
.site-nav{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;max-width:100%;min-width:0}
.site-nav a{box-sizing:border-box;max-width:100%;font-size:12.5px;font-weight:700;padding:5px 10px;border-radius:999px;text-decoration:none;color:var(--ink);background:var(--panel2,var(--panel));line-height:1.3}
.site-nav a.nav-donate{background:var(--accent);color:#fff}
.foot a{font-weight:700}`;

function shell(master, lang, a, html, meta, gen) {
  const L = T[lang];
  const head = master.slice(0, master.indexOf('</head>'));
  const styles = (head.match(/<style[^>]*>[\s\S]*?<\/style>/g) || []).join('\n');
  const ga = (head.match(/<script async src="https:\/\/www\.googletagmanager\.com[^>]*><\/script>\s*<script>window\.dataLayer[\s\S]*?<\/script>/) || [''])[0];
  const fonts = (head.match(/<link rel="(?:preconnect|stylesheet)"[^>]*>/g) || []).join('');
  const apple = (master.match(/<style id="apple-home">[\s\S]*?<\/style>/) || [''])[0];
  const brand = `<a href="/${lang}/" class="brand-home"><p class="brand">${(master.match(/<h1 class="brand">([\s\S]*?)<\/h1>/) || ['', 'The Crowd Tape'])[1]}</p></a>`;
  const s = hSlug(a.h);
  const url = `${SITE}${lang}/account/${s}/`;
  const alt = Object.entries(LANGS).map(([k, h]) => `<link rel="alternate" hreflang="${h}" href="${SITE}${k}/account/${s}/">`).join('')
    + `<link rel="alternate" hreflang="x-default" href="${SITE}zh/account/${s}/">`;
  const sw = Object.keys(LANGS).map(k => `<a href="/${k}/account/${s}/"${k === lang ? ' aria-current="page"' : ''}>${{ zh: '中', en: 'EN' }[k]}</a>`).join('');
  const ld = {
    '@context': 'https://schema.org',
    '@graph': [
      { '@type': 'ProfilePage', url, name: meta.title, inLanguage: LANGS[lang], isPartOf: { '@type': 'WebSite', name: 'The Crowd Tape', url: SITE },
        ...(a.modified ? { dateModified: a.modified } : {}),
        mainEntity: { '@type': 'Person', name: a.name, alternateName: '@' + a.h, sameAs: [a.xUrl] } },
      { '@type': 'BreadcrumbList', itemListElement: [
        { '@type': 'ListItem', position: 1, name: L.home, item: `${SITE}${lang}/` },
        { '@type': 'ListItem', position: 2, name: L.index, item: `${SITE}${lang}/#account-index` },
        { '@type': 'ListItem', position: 3, name: '@' + a.h, item: url },
      ] },
    ],
  };
  const og = `${SITE}og/latest${lang === 'zh' ? '' : '-' + lang}.png`;
  return `<!DOCTYPE html>
<html lang="${LANGS[lang]}"${apple ? '' : ' data-theme="light"'}><head>
${ga}
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="192x192" href="/assets/icon-192.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest"><meta name="theme-color" content="#fbf6ec"><meta name="apple-mobile-web-app-title" content="Crowd Tape">
<meta name="robots" content="index,follow,max-image-preview:large">
<title>${esc(meta.title)}</title>
<meta name="description" content="${esc(meta.desc)}">
<meta property="og:title" content="${esc(meta.title)}">
<meta property="og:description" content="${esc(meta.desc)}">
<meta property="og:url" content="${url}">
<meta property="og:type" content="profile">
<meta property="og:image" content="${og}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="${og}">
<link rel="canonical" href="${url}">${alt}
<script type="application/ld+json">${JSON.stringify(ld).replace(/<\//g, '<\\/')}</script>
${fonts}
${styles}
${apple}
<style>${CSS}</style>
</head>
<body>
<header class="top"><div class="wrap"><div class="brand-wrap">${brand}<nav class="lang-sw" aria-label="Language">${sw}</nav><nav class="site-nav" aria-label="${esc(L.nav)}"><a href="/${lang}/tools/">${esc(L.tools)}</a><a class="nav-donate" href="/${lang}/support/">${esc(L.support)}</a></nav></div></div></header>
<main class="account-static">${html}
<div class="open-live"><a href="/${lang}/#account/${encodeURIComponent(a.h)}">${esc(L.open)}</a></div>
</main>
<footer class="wrap foot"><p><a href="/${lang}/">${esc(L.home)}</a> · <a href="/${lang}/tools/">${esc(L.tools)}</a> · <a href="/${lang}/support/">${esc(L.support)}</a> · <a href="/${lang}/newsletter/">${esc(L.news)}</a>${gen ? ` · ${esc(L.upd)} ${esc(gen)} HKT` : ''}</p></footer>
<script>document.addEventListener('click',function(e){var a=e.target&&e.target.closest&&e.target.closest('a[href]');if(!a||typeof gtag!=='function')return;var h='';try{h=new URL(a.href).hostname.toLowerCase()}catch(err){return}if(h==='x.com'||h.endsWith('.x.com')||h==='twitter.com'||h.endsWith('.twitter.com'))gtag('event','x_outbound',{link_url:a.href,page:'account',lang:document.documentElement.lang||'',transport_type:'beacon'})});</script>
${toTop(L.top)}
</body></html>
`;
}

function indexRow(lang, accs) {
  const links = accs.map(a => `<a href="/${lang}/account/${hSlug(a.h)}/">@${esc(a.h)}</a>`).join(' ');
  return `<nav id="account-index" class="wrap stock-index" aria-label="${esc(T[lang].index)}" style="font-size:12.5px;line-height:2;color:var(--muted);padding:0 16px 28px">`
    + `<details><summary><b>${esc(T[lang].index)}</b>${lang === 'zh' ? `（${accs.length}）` : ` (${accs.length})`}</summary>${links}</details></nav>`;
}

// Homepage row: right after the stock pages row, else just above the footer. Idempotent.
function withAccountIndex(html, lang, accs) {
  let s = html.replace(new RegExp(MARK + '[\\s\\S]*?' + MARK), '');
  const row = MARK + indexRow(lang, accs) + MARK;
  const i = s.lastIndexOf(STOCK_MARK);
  if (i >= 0 && s.indexOf(STOCK_MARK) < i) return s.slice(0, i + STOCK_MARK.length) + row + s.slice(i + STOCK_MARK.length);
  if (!s.includes(FOOT)) {
    console.log('::error::no footer for account index');
    process.exit(1);
  }
  return s.replace(FOOT, row + FOOT);
}

// Stock pages: account links go to the account page when it exists.
function linkStockPages(lang, have) {
  const dir = path.join(lang, 'stock');
  if (!fs.existsSync(dir)) return 0;
  let n = 0;
  const re = new RegExp(`href="/${lang}/#account/([^"]+)"`, 'g');
  for (const d of fs.readdirSync(dir)) {
    const f = path.join(dir, d, 'index.html');
    if (!fs.existsSync(f)) continue;
    const s = fs.readFileSync(f, 'utf8');
    const out = s.replace(re, (m, k) => {
      const sl = hSlug(decodeURIComponent(k));
      return have.has(sl) ? `href="/${lang}/account/${sl}/"` : m;
    });
    if (out !== s) { fs.writeFileSync(f, out); n++; }
  }
  return n;
}

if (require.main === module) {
(async () => {
  const { chromium } = require('playwright');
  const root = path.resolve(__dirname, '..');
  const srv = await start(root);
  const b = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  fs.mkdirSync('av', { recursive: true });
  const seen = new Set(fs.readdirSync('av'));
  const urls = [];
  let accs = null;
  let gen = '';
  for (const lang of Object.keys(LANGS)) {
    const file = path.resolve(lang, 'index.html');
    const p = await b.newPage();
    const errs = [];
    p.on('pageerror', e => errs.push(e.message));
    await p.route('**/*', route => {
      const u = route.request().url();
      if (u.startsWith(srv.origin) || u.startsWith('file:')) route.continue();
      else route.abort();
    });
    await p.goto(pageUrl(srv.origin, root, file) + '#daily', { waitUntil: 'domcontentloaded' });
    await p.waitForFunction(() => typeof openAccount === 'function' && typeof POSTS !== 'undefined');
    await p.evaluate(async () => {
      if (window.__loadCore) await window.__loadCore();
      if (window.__loadAllPosts) await window.__loadAllPosts();
      if (window.__postsFailed) throw new Error('older posts failed to load');
    });
    const got = await p.evaluate(collect, MIN_STOCKS);
    if (errs.length) { console.log('::error::帳號網頁生成時有錯誤：' + errs.join('；')); process.exit(1); }
    await p.close();
    // Same accounts in every language (the zh run decides; both read the same data)
    if (!accs) accs = got.accounts.map(a => a.h);
    const list = got.accounts.filter(a => accs.includes(a.h));
    gen = String(got.gen).replace('T', ' ').slice(0, 16);
    const master = fs.readFileSync(file, 'utf8');
    const dir = path.join(lang, 'account');
    fs.mkdirSync(dir, { recursive: true });
    const have = new Set(list.map(a => hSlug(a.h)));
    for (const d of fs.readdirSync(dir)) if (!have.has(d)) fs.rmSync(path.join(dir, d), { recursive: true, force: true });
    const stockPages = new Set(fs.existsSync(path.join(lang, 'stock')) ? fs.readdirSync(path.join(lang, 'stock')) : []);
    const L = T[lang];
    for (const a of list) {
      let avSrc = '';
      if (a.avatar) avSrc = (avatars(`src="${a.avatar}"`, seen).match(/src="([^"]+)"/) || [])[1] || '';
      const html = body(lang, a, stockPages, avSrc);
      const bull = a.stocks.filter(x => x.s === 'bull').length;
      const ts = a.stocks.slice(0, 6).map(x => '$' + x.t).join(lang === 'zh' ? '、' : ', ') + (a.stocks.length > 6 ? '…' : '');
      const meta = { title: L.title(a.name, a.h), desc: L.desc(a.h, bull, a.stocks.length - bull, ts) };
      fs.mkdirSync(path.join(dir, hSlug(a.h)), { recursive: true });
      fs.writeFileSync(path.join(dir, hSlug(a.h), 'index.html'), shell(master, lang, a, html, meta, gen));
      urls.push(`${lang}/account/${hSlug(a.h)}/`);
    }
    console.log(`${lang}: stock pages relinked ${linkStockPages(lang, have)}`);
    fs.writeFileSync(file, withAccountIndex(master, lang, list));
    if (lang === 'zh') {
      const rootFile = path.join(root, 'index.html');
      fs.writeFileSync(rootFile, withAccountIndex(fs.readFileSync(rootFile, 'utf8'), 'zh', list));
    }
  }

  // sitemap: drop old account rows, add the current ones
  let sm = fs.readFileSync('sitemap.xml', 'utf8').replace(/\s*<url><loc>[^<]*\/account\/[^<]*<\/loc>[\s\S]*?<\/url>/g, '');
  const stamp = new Date().toLocaleString('sv-SE', { timeZone: 'Asia/Hong_Kong' }).replace(' ', 'T') + '+08:00';
  const rows = accs.map(h => {
    const s = hSlug(h);
    const alt = Object.entries(LANGS).map(([k, hl]) => `<xhtml:link rel="alternate" hreflang="${hl}" href="${SITE}${k}/account/${s}/"/>`).join('');
    return Object.keys(LANGS).map(k => `  <url><loc>${SITE}${k}/account/${s}/</loc><lastmod>${stamp}</lastmod><changefreq>daily</changefreq>${alt}</url>`).join('\n');
  }).join('\n');
  sm = dedupeSitemap(sm.replace('</urlset>', (rows ? rows + '\n' : '') + '</urlset>'));
  fs.writeFileSync('sitemap.xml', sm);

  // check a few pages at desktop and phone width
  const bad = [];
  for (const u of [urls[0], urls[Math.floor(urls.length / 2)], urls[urls.length - 1]].filter(Boolean)) {
    for (const w of [1280, 390]) {
      const p = await b.newPage({ viewport: { width: w, height: 844 }, javaScriptEnabled: false });
      await p.route(/^https?:/, r => r.abort());
      await p.goto('file://' + path.resolve(u, 'index.html'));
      const info = await p.evaluate(() => ({
        ovf: document.documentElement.scrollWidth > innerWidth + 1,
        rows: document.querySelectorAll('.ac-row').length,
        len: document.body.innerText.length,
      }));
      const ok = !info.ovf && info.rows >= MIN_STOCKS && info.len > 300;
      console.log(`${ok ? 'ok ' : 'BAD'} ${w}px ${u}`, info.ovf ? 'overflow' : '', info.rows, info.len);
      if (!ok) bad.push(`${w}px ${u}`);
      await p.close();
    }
  }
  await b.close();
  srv.server.close();
  console.log(`帳號網頁：${accs.length} 個 × ${Object.keys(LANGS).length} 個語言`);
  if (bad.length) { console.log('::error::帳號網頁檢查唔合格：' + bad.join('、')); process.exit(1); }
})();
}

module.exports = { collect, hSlug, withAccountIndex, indexRow, pxLine, T };
