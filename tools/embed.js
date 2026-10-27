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
a.c{box-sizing:border-box;display:flex;flex-direction:column;justify-content:space-between;width:320px;height:120px;padding:10px 14px;border:1px solid #d2d2d7;border-radius:18px;background:#fff;color:#1d1d1f;text-decoration:none;font:14px/1.3 -apple-system,BlinkMacSystemFont,"SF Pro Text",var(--f-body);-webkit-font-smoothing:antialiased;overflow:hidden}
.r1{display:flex;align-items:baseline;gap:8px;white-space:nowrap;overflow:hidden}
.tk{font-weight:700;font-size:20px;letter-spacing:-.02em}.nm{color:#6e6e73;font-size:12px;overflow:hidden;text-overflow:ellipsis}
.n{display:flex;justify-content:space-between;font-weight:600;font-variant-numeric:tabular-nums}.g{color:#248a3d}.b{color:#d70015}
.bar{height:8px;border-radius:8px;background:#ff3b30;overflow:hidden}.bar i{display:block;height:100%;background:#34c759}
.f{display:flex;justify-content:space-between;color:#6e6e73;font-size:11px}.f b{color:#1d1d1f}
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
:root{--bg:#f5f5f7;--surface:#fff;--ink:#1d1d1f;--muted:#6e6e73;--line:#e3e3e8;--link:#0066cc;color-scheme:light dark}
@media (prefers-color-scheme: dark){:root{--bg:#000;--surface:#1c1c1e;--ink:#f5f5f7;--muted:#a1a1a6;--line:#38383a;--link:#2997ff}}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.6 -apple-system,BlinkMacSystemFont,"SF Pro Text",var(--f-body);-webkit-font-smoothing:antialiased}a{color:var(--link)}
.wrap{max-width:720px;margin:0 auto;padding:24px 16px 48px}header{display:flex;justify-content:space-between;align-items:center;gap:12px}
.brand{font-weight:600;font-size:19px;color:var(--ink);text-decoration:none;letter-spacing:-.02em}h1{font-size:clamp(30px,5vw,44px);line-height:1.12;letter-spacing:-.02em}
nav a{margin-left:6px;padding:4px 12px;border-radius:980px;background:var(--surface);color:var(--ink);text-decoration:none;font-size:13px;font-weight:600}nav a[aria-current]{background:#0071e3;color:#fff}
pre{white-space:pre-wrap;word-break:break-all;background:var(--surface);border:0;border-radius:18px;padding:12px;font-family:var(--f-data);font-size:13px}
.note{color:var(--muted);font-size:13px}</style>
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
