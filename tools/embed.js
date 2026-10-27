// Embeddable sentiment badge (growth plan 2026-10-25 A). Written by tools/stock_pages.js:
//  - /embed/<TICKER>.html: 320x120 card, no JavaScript, noindex; English (one file per stock).
//    Type comes from the Google Fonts stylesheet (the same families as the site).
//    Counts = the stock page's stance mix (each account's latest view in the 28-day window, same rule as the site).
//  - /<lang>/embed/: how-to page with the copy-paste <iframe> code, fully in that language.
// Every link out of the badge carries utm_source=embed&utm_medium=widget&utm_campaign=badge.
const SITE = 'https://thecrowdtape.com/';
const UTM = 'utm_source=embed&utm_medium=widget&utm_campaign=badge';
const FONTS = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=Noto+Serif+TC:wght@700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">';
const FONT_VARS = ':root{--f-display:"Noto Serif TC","Source Han Serif TC","Songti TC","PMingLiU",serif;--f-body:"Noto Sans TC","PingFang TC","Noto Sans CJK TC","Microsoft JhengHei",system-ui,sans-serif;--f-data:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}';
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

function card(t, slug, name, c, day) {
  const href = `${SITE}en/stock/${slug}/?${UTM}`;
  const tot = (c.bull || 0) + (c.bear || 0);
  const pb = tot ? Math.round(c.bull / tot * 100) : 50;
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex,follow">
<meta name="viewport" content="width=320">
<title>$${esc(t)} crowd sentiment · The Crowd Tape</title>
<link rel="canonical" href="${SITE}en/stock/${esc(slug)}/">
${FONTS}
<style>
${FONT_VARS}
html,body{margin:0;padding:0;background:transparent}
a.c{box-sizing:border-box;display:flex;flex-direction:column;justify-content:space-between;width:320px;height:120px;padding:10px 14px;border:1px solid #d9cfc2;border-radius:12px;background:#fffaf2;color:#3b2f25;text-decoration:none;font:14px/1.3 var(--f-body);overflow:hidden}
.r1{display:flex;align-items:baseline;gap:8px;white-space:nowrap;overflow:hidden}
.tk{font-family:var(--f-data);font-weight:800;font-size:20px}.nm{color:#7a6a5a;font-size:12px;overflow:hidden;text-overflow:ellipsis}
.n{display:flex;justify-content:space-between;font-family:var(--f-data);font-weight:700;font-variant-numeric:tabular-nums}.g{color:#1f7a4a}.b{color:#b23a2e}
.bar{height:8px;border-radius:4px;background:#e7b2ac;overflow:hidden}.bar i{display:block;height:100%;background:#7cc49b}
.f{display:flex;justify-content:space-between;color:#7a6a5a;font-size:11px}.f b{color:#3b2f25}
</style></head>
<body><a class="c" href="${esc(href)}" target="_blank" rel="noopener">
<div class="r1"><span class="tk">$${esc(t)}</span><span class="nm">${esc(name)}</span></div>
<div class="n"><span class="g">${c.bull || 0} bullish</span><span class="b">${c.bear || 0} bearish</span></div>
<div class="bar" role="img" aria-label="${c.bull || 0} bullish vs ${c.bear || 0} bearish accounts"><i style="width:${pb}%"></i></div>
<div class="f"><span>Tracked X accounts, latest view · ${esc(day)}</span><span>via <b>The Crowd Tape</b></span></div>
</a></body></html>
`;
}

const COPY = {
  zh: { lang: 'zh-Hant', title: '把好淡卡片嵌入你的網站', desc: '免費把任何美股的 X 大神好淡統計卡片嵌入你的網站或部落格：複製一行 iframe 代碼即可，每 4 小時自動更新。',
    h: '嵌入好淡卡片', p1: '把下面一行代碼貼到你的網站、部落格或論壇文章，就會顯示該股票最新的看多／看空帳號數（每個帳號只計最近一則觀點，每 4 小時更新）。',
    p2: '把網址中的 NVDA 換成你想要的股票代號（大寫），例如 TSLA、AAPL。卡片大小 320×120，不含任何 JavaScript。', ex: '預覽', back: '返回首頁', note: '卡片內容只整理公開貼文，不構成投資建議。' },
  en: { lang: 'en', title: 'Embed a crowd sentiment card on your site', desc: 'Free embeddable card showing how tracked X accounts lean on any US stock. Copy one line of iframe code; it updates every 4 hours.',
    h: 'Embed a sentiment card', p1: 'Paste this one line into your site, blog or forum post to show the latest count of bullish and bearish accounts on a stock (each account counted once, by its latest view; updated every 4 hours).',
    p2: 'Replace NVDA in the URL with any ticker (upper case), e.g. TSLA or AAPL. The card is 320×120 and contains no JavaScript.', ex: 'Preview', back: 'Back to the dashboard', note: 'The card summarises public posts only. Not investment advice.' },
};

function howto(lang, ga, sample) {
  const L = COPY[lang];
  const code = `<iframe src="${SITE}embed/${sample}.html" width="320" height="120" loading="lazy"></iframe>`;
  const alt = Object.entries(COPY).map(([k, v]) => `<link rel="alternate" hreflang="${v.lang}" href="${SITE}${k}/embed/">`).join('');
  const sw = Object.entries({ zh: '中', en: 'EN' }).map(([k, n]) => `<a href="/${k}/embed/" hreflang="${COPY[k].lang}"${k === lang ? ' aria-current="page"' : ''}>${n}</a>`).join(' ');
  return `<!doctype html>
<html lang="${L.lang}"><head>
${ga}
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="index,follow">
<title>${esc(L.title)} · The Crowd Tape</title>
<meta name="description" content="${esc(L.desc)}">
<link rel="canonical" href="${SITE}${lang}/embed/">${alt}<link rel="alternate" hreflang="x-default" href="${SITE}en/embed/">
${FONTS}
<style>${FONT_VARS}
body{margin:0;background:#f6efe4;color:#3b2f25;font:16px/1.6 var(--f-body)}
.wrap{max-width:720px;margin:0 auto;padding:24px 16px 48px}header{display:flex;justify-content:space-between;align-items:center;gap:12px}
.brand{font-family:var(--f-display);font-weight:800;color:#3b2f25;text-decoration:none}h1{font-family:var(--f-display)}nav a{margin-left:6px;color:#3b2f25}
pre{white-space:pre-wrap;word-break:break-all;background:#fffaf2;border:1px solid #d9cfc2;border-radius:10px;padding:12px;font-family:var(--f-data);font-size:13px}
.note{color:#7a6a5a;font-size:13px}</style>
</head><body><div class="wrap">
<header><a class="brand" href="/${lang}/">The Crowd Tape</a><nav class="lang-sw" aria-label="Language">${sw}</nav></header>
<h1>${esc(L.h)}</h1>
<p>${esc(L.p1)}</p>
<pre><code>${esc(code)}</code></pre>
<p>${esc(L.p2)}</p>
<h2>${esc(L.ex)}</h2>
${code}
<p class="note">${esc(L.note)}</p>
<p><a href="/${lang}/">${esc(L.back)}</a></p>
</div></body></html>
`;
}

module.exports = { card, howto, UTM };
