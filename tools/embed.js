// Embeddable sentiment badge (growth plan 2026-10-25 A). Written by tools/stock_pages.js:
//  - /embed/<TICKER>.html: 320x120 card, inline CSS only, no JavaScript at all, noindex; English (one file per stock).
//    Counts = the stock page's stance mix (each account's latest view in the 28-day window, same rule as the site).
//  - /<lang>/embed/: how-to page with the copy-paste <iframe> code, fully in that language.
// Every link out of the badge carries utm_source=embed&utm_medium=widget&utm_campaign=badge.
const SITE = 'https://thecrowdtape.com/';
const UTM = 'utm_source=embed&utm_medium=widget&utm_campaign=badge';
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
<style>
html,body{margin:0;padding:0;background:transparent}
a.c{box-sizing:border-box;display:flex;flex-direction:column;justify-content:space-between;width:320px;height:120px;padding:10px 14px;border:1px solid #d9cfc2;border-radius:12px;background:#fffaf2;color:#3b2f25;text-decoration:none;font:14px/1.3 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;overflow:hidden}
.r1{display:flex;align-items:baseline;gap:8px;white-space:nowrap;overflow:hidden}
.tk{font-weight:800;font-size:20px}.nm{color:#7a6a5a;font-size:12px;overflow:hidden;text-overflow:ellipsis}
.n{display:flex;justify-content:space-between;font-weight:700}.g{color:#1f7a4a}.b{color:#b23a2e}
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
  ko: { lang: 'ko', title: '내 사이트에 강세/약세 카드 넣기', desc: 'X 추적 계정들의 미국 주식 강세/약세 집계 카드를 무료로 내 사이트에 넣으세요. iframe 코드 한 줄이면 되고 4시간마다 업데이트됩니다.',
    h: '강세/약세 카드 퍼가기', p1: '아래 코드 한 줄을 사이트, 블로그, 커뮤니티 글에 붙여 넣으면 해당 종목의 최신 강세·약세 계정 수가 표시됩니다 (계정마다 최신 의견 하나만 집계, 4시간마다 업데이트).',
    p2: 'URL의 NVDA를 원하는 티커(대문자)로 바꾸세요. 예: TSLA, AAPL. 카드 크기는 320×120이며 JavaScript가 없습니다.', ex: '미리보기', back: '대시보드로 돌아가기', note: '카드는 공개 게시물만 정리하며 투자 조언이 아닙니다.' },
};

function howto(lang, ga, sample) {
  const L = COPY[lang];
  const code = `<iframe src="${SITE}embed/${sample}.html" width="320" height="120" loading="lazy"></iframe>`;
  const alt = Object.entries(COPY).map(([k, v]) => `<link rel="alternate" hreflang="${v.lang}" href="${SITE}${k}/embed/">`).join('');
  const sw = Object.entries({ zh: '中', en: 'EN', ko: '한' }).map(([k, n]) => `<a href="/${k}/embed/" hreflang="${COPY[k].lang}"${k === lang ? ' aria-current="page"' : ''}>${n}</a>`).join(' ');
  return `<!doctype html>
<html lang="${L.lang}"><head>
${ga}
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="index,follow">
<title>${esc(L.title)} · The Crowd Tape</title>
<meta name="description" content="${esc(L.desc)}">
<link rel="canonical" href="${SITE}${lang}/embed/">${alt}<link rel="alternate" hreflang="x-default" href="${SITE}en/embed/">
<style>body{margin:0;background:#f6efe4;color:#3b2f25;font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans TC","Noto Sans KR",sans-serif}
.wrap{max-width:720px;margin:0 auto;padding:24px 16px 48px}header{display:flex;justify-content:space-between;align-items:center;gap:12px}
.brand{font-weight:800;color:#3b2f25;text-decoration:none}nav a{margin-left:6px;color:#3b2f25}
pre{white-space:pre-wrap;word-break:break-all;background:#fffaf2;border:1px solid #d9cfc2;border-radius:10px;padding:12px;font-size:13px}
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
