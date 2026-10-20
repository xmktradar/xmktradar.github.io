// Step 11: static stock pages /<lang>/stock/<TICKER>/ for search engines, from the built /zh/ /en/ /ko/ pages.
// Usage: node tools/stock_pages.js
//
// - Which stocks: mentioned by MIN_ACCOUNTS or more tracked accounts in the last 28 days (the page's own POSTS),
//   ticker confirmed. Pages of stocks that drop out are deleted and leave the sitemap.
// - Content: the page's own stock view (openDive) rendered in each language, without the TradingView card and the
//   price chart, so the text and numbers match the interactive page. A button at the bottom opens the interactive
//   page (/<lang>/#stock/<TICKER>). Readable without JS. One inline script runs the newsletter A/B test;
//   the box stays hidden for variant A and when JS is off.
// - Avatars are written once to av/<hash>.<ext> and shared by every page.
// - Each language page gets a "stock pages" link row just above the footer; sitemap.xml lists every stock page.
// - Finally opens a few pages at desktop and phone width; fails on sideways overflow or missing text.
const { chromium } = require('playwright');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { start, pageUrl } = require('./local_server');

const SITE = 'https://thecrowdtape.com/';
const LANGS = { zh: 'zh-Hant', en: 'en', ko: 'ko' };
const MIN_ACCOUNTS = 2;
const AV_DIR = 'av';
const MARK = '<!-- stock-index -->';
const T = {
  zh: {
    index: '個股頁面',
    top: '回到頂部',
    open: '打開互動版（含走勢圖）',
    home: '首頁',
    advice: '不構成投資建議。本頁只整理公開貼文，供參考。',
    tools: '工具',
    support: '支持我哋',
    news: '電子報',
    promo: '推廣',
    tv: '用 TradingView 睇圖表',
    bullName: '看多帳號',
    bearName: '看空帳號',
    menName: '提及帳號',
    dsName: t => `X 帳號對 $${t} 的看多／看空統計`,
    dsDesc: (t, s) => `追蹤帳號對 $${t} 的最新立場，資料窗 ${s.from} 至 ${s.to}（香港時間）。看多帳號 ${s.bull}、看空帳號 ${s.bear}、提及帳號 ${s.mentions}。不構成投資建議。`,
    title: (t, nm, c) => `${t}${nm ? `（${nm}）` : ''} X 大神觀點：看多 ${c.bull}・看空 ${c.bear}・中性 ${c.neu}｜The Crowd Tape`,
    desc: (t, n, c) => `過去 28 天有 ${n} 個追蹤帳號提及 $${t}：看多 ${c.bull}、中性 ${c.neu}、看空 ${c.bear}、未表態 ${c.none}。查看每個帳號的最新觀點、理由與原帖，每 4 小時更新，不構成投資建議。`,
  },
  en: {
    index: 'Stock pages',
    top: 'Back to top',
    open: 'Open the interactive page (with chart)',
    home: 'Home',
    advice: 'Not investment advice. This page only summarises public posts.',
    tools: 'Tools',
    support: 'Support us',
    news: 'Newsletter',
    promo: 'Promotion',
    tv: 'View charts on TradingView',
    bullName: 'Bullish accounts',
    bearName: 'Bearish accounts',
    menName: 'Mentioning accounts',
    dsName: t => `X-account bull/bear stats for $${t}`,
    dsDesc: (t, s) => `Latest stance of each tracked account that mentioned $${t}. Data window ${s.from} to ${s.to} (Hong Kong time). Bullish accounts: ${s.bull}. Bearish accounts: ${s.bear}. Mentioning accounts: ${s.mentions}. Not investment advice.`,
    title: (t, nm, c) => `${t}${nm ? ` (${nm})` : ''} on X: ${c.bull} bullish, ${c.bear} bearish, ${c.neu} neutral | The Crowd Tape`,
    desc: (t, n, c) => `${n} tracked X accounts mentioned $${t} in the last 28 days: ${c.bull} bullish, ${c.neu} neutral, ${c.bear} bearish, ${c.none} no stance. Each account's latest view, reasons and original post, updated every 4 hours. Not investment advice.`,
  },
  ko: {
    index: '종목 페이지',
    top: '맨 위로',
    open: '인터랙티브 페이지 열기(차트 포함)',
    home: '홈',
    advice: '투자 조언이 아닙니다. 이 페이지는 공개 게시물을 정리한 자료입니다.',
    tools: '도구',
    support: '후원하기',
    news: '뉴스레터',
    promo: '홍보',
    tv: 'TradingView에서 차트 보기',
    bullName: '강세 계정',
    bearName: '약세 계정',
    menName: '언급 계정',
    dsName: t => `$${t} X 계정 강세/약세 통계`,
    dsDesc: (t, s) => `추적 계정이 $${t}에 대해 남긴 최신 입장. 자료 구간 ${s.from}–${s.to} (홍콩 시간). 강세 계정 ${s.bull}, 약세 계정 ${s.bear}, 언급 계정 ${s.mentions}. 투자 조언이 아닙니다.`,
    title: (t, nm, c) => `${t}${nm ? ` (${nm})` : ''} X 고수 관점: 강세 ${c.bull}・약세 ${c.bear}・중립 ${c.neu} | The Crowd Tape`,
    desc: (t, n, c) => `최근 28일 동안 추적 계정 ${n}개가 $${t}를 언급했다: 강세 ${c.bull}, 중립 ${c.neu}, 약세 ${c.bear}, 입장 없음 ${c.none}. 계정별 최신 관점, 근거와 원문을 4시간마다 업데이트한다. 투자 조언이 아닙니다.`,
  },
};

// Newsletter A/B box (nl-stock-2026-10). en/ko copy lives in i18n/<lang>.json under "nl".
// i18n/zh.json is a list of UI strings, so the Chinese block stays here.
const NL_ENDPOINT = 'https://crowdtape-newsletter.vercel.app/api/subscribe';
const NL_ZH = {
  aria: '訂閱每日電郵',
  title: '每天收到這檔股票的大神觀點變化',
  note: '免費・隨時退訂・不構成投資建議',
  label: '電郵地址',
  placeholder: '你的電郵',
  button: '訂閱',
  ok: '已收到，請查看確認信。',
};
const NL_CSS = `/* The Crowd Tape — newsletter signup box (A/B). Scoped to .ct-nl. Uses site :root vars only; no bull/bear colours. */
.ct-nl{margin-top:12px;display:flex;align-items:center;gap:6px 10px;flex-wrap:wrap;
  padding:6px 10px;border:1px solid var(--line);border-radius:10px;background:var(--accent-soft);
  font-family:var(--f-body);color:var(--ink);box-sizing:border-box}
.ct-nl[hidden]{display:none}
/* narrow column (desktop c4 panel ~280px): stack text over form */
.ct-nl{container-type:inline-size}
@container (max-width:420px){.ct-nl__txt,.ct-nl__f{flex-basis:100%}}
.ct-nl__txt{flex:1 1 220px;min-width:0;line-height:1.3}
.ct-nl__t{font-size:13px;line-height:16px;font-weight:600;margin:0}
.ct-nl__n{font-size:10.5px;line-height:13px;color:var(--muted);margin:0}
.ct-nl__f{display:flex;gap:6px;flex:0 1 330px;min-width:0;margin:0}
.ct-nl__in{flex:1 1 auto;min-width:0;height:28px;padding:0 10px;font:inherit;font-size:13px;color:var(--ink);
  background:var(--surface);border:1px solid var(--line);border-radius:8px;box-sizing:border-box}
.ct-nl__in:focus{outline:2px solid var(--accent);outline-offset:0;border-color:var(--accent)}
.ct-nl__btn{height:28px;padding:0 14px;font:inherit;font-size:13px;font-weight:600;white-space:nowrap;
  color:#fff;background:var(--accent);border:0;border-radius:8px;cursor:pointer}
.ct-nl__btn:hover{filter:brightness(1.08)}
.ct-nl__ok{font-size:12.5px;color:var(--accent);margin:0}
.ct-nl .sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
@media (max-width:600px){
  .ct-nl{gap:6px;padding:6px 8px}
  .ct-nl__txt{flex-basis:100%}
  .ct-nl__f{flex:1 1 100%}
}
`;
const NL_SNIPPET = `<aside class="ct-nl" data-ab="B" data-ab-test="nl-stock-2026-10" data-ticker="{{TICKER}}" aria-label="{{nl.aria}}" hidden>
  <div class="ct-nl__txt">
    <p class="ct-nl__t">{{nl.title}}</p>
    <p class="ct-nl__n">{{nl.note}}</p>
  </div>
  <form class="ct-nl__f" action="{{NEWSLETTER_ENDPOINT}}" method="post">
    <label class="sr" for="ct-nl-email">{{nl.label}}</label>
    <input class="ct-nl__in" id="ct-nl-email" type="email" name="email" required autocomplete="email" placeholder="{{nl.placeholder}}">
    <input type="hidden" name="lang" value="{{LANG}}"><input type="hidden" name="src" value="stock-{{TICKER}}">
    <button class="ct-nl__btn" type="submit">{{nl.button}}</button>
  </form>
</aside>`;
const NL_CACHE = { zh: NL_ZH };
function nlCopy(lang) {
  if (!NL_CACHE[lang]) {
    const data = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'i18n', lang + '.json'), 'utf8'));
    if (!data.nl) throw new Error('i18n/' + lang + '.json has no nl block');
    NL_CACHE[lang] = data.nl;
  }
  return NL_CACHE[lang];
}
function nlMarkup(lang, ticker) {
  const nl = nlCopy(lang);
  return NL_SNIPPET
    .split('{{TICKER}}').join(esc(ticker))
    .split('{{LANG}}').join(lang)
    .split('{{NEWSLETTER_ENDPOINT}}').join(NL_ENDPOINT)
    .split('{{nl.aria}}').join(esc(nl.aria))
    .split('{{nl.title}}').join(esc(nl.title))
    .split('{{nl.note}}').join(esc(nl.note))
    .split('{{nl.label}}').join(esc(nl.label))
    .split('{{nl.placeholder}}').join(esc(nl.placeholder))
    .split('{{nl.button}}').join(esc(nl.button));
}
// Right after the balanced <div class="kpis k4"> inside section.c4.panel, before .tablewrap.
function insertAfterKpis(html, box) {
  const sec = html.indexOf('<section class="c4 panel">');
  if (sec < 0) return html;
  const start = html.indexOf('<div class="kpis k4"', sec);
  if (start < 0) return html;
  const secEnd = html.indexOf('</section>', start);
  if (secEnd < 0) return html;
  let depth = 0, i = start;
  while (i < secEnd) {
    const open = html.indexOf('<div', i);
    const close = html.indexOf('</div>', i);
    if (close < 0 || close >= secEnd) return html;
    if (open !== -1 && open < close) {
      depth++;
      i = open + 4;
    } else {
      depth--;
      i = close + 6;
      if (depth === 0) {
        const out = html.slice(0, i) + '\n' + box + '\n' + html.slice(i);
        const boxAt = out.indexOf('data-ab-test="nl-stock-2026-10"', sec);
        const sectionClose = out.indexOf('</section>', boxAt);
        const table = out.indexOf('<div class="tablewrap"', boxAt);
        if (boxAt < 0 || sectionClose < 0 || boxAt > sectionClose) return html;
        if (table !== -1 && table < sectionClose && !(boxAt < table)) return html;
        return out;
      }
    }
  }
  return html;
}
function nlScript(ok) {
  const okLit = JSON.stringify(esc(ok)).replace(/</g, '\\u003c');
  return `<script>(function(){
var aside=document.querySelector('aside.ct-nl');
if(!aside)return;
var T=aside.getAttribute('data-ticker')||'';
var langIn=aside.querySelector('input[name="lang"]');
var lang=langIn?langIn.value:'';
var m=document.cookie.match(/(?:^|; )ct_ab_nl=([AB])(?:;|$)/);
var cur=m?m[1]:'';
var q='';
try{q=new URLSearchParams(location.search).get('ab')||'';}catch(e){}
var v,set=false;
if(q==='A'||q==='B'){v=q;set=true;}
else if(cur==='A'||cur==='B')v=cur;
else{v=Math.random()<0.5?'A':'B';set=true;}
if(set)document.cookie='ct_ab_nl='+v+'; Max-Age=2592000; path=/; SameSite=Lax';
aside.dataset.ab=v;
if(v==='B')aside.removeAttribute('hidden');
if(window.gtag){
  gtag('set','user_properties',{nl_ab:v});
  gtag('event','ab_exposure',{experiment:'nl-stock-2026-10',variant:v,ticker:T});
}
if(v==='B'&&window.IntersectionObserver){
  var seen=false;
  var io=new IntersectionObserver(function(ents){
    if(seen)return;
    for(var i=0;i<ents.length;i++){
      if(ents[i].isIntersecting&&ents[i].intersectionRatio>=0.5){
        seen=true;io.disconnect();
        if(window.gtag)gtag('event','newsletter_view',{variant:'B',ticker:T,lang:lang});
        return;
      }
    }
  },{threshold:0.5});
  io.observe(aside);
}
var form=aside.querySelector('form.ct-nl__f');
if(!form)return;
var OK=${okLit};
form.addEventListener('submit',function(e){
  e.preventDefault();
  if(form.getAttribute('data-sending'))return;
  form.setAttribute('data-sending','1');
  var d=new FormData(form);
  fetch(form.action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:d.get('email'),lang:d.get('lang'),src:d.get('src')})})
    .then(function(r){return r.json();})
    .then(function(j){
      if(!j||!j.ok){form.removeAttribute('data-sending');return;}
      form.outerHTML='<p class="ct-nl__ok">'+OK+'<\\/p>';
      if(window.gtag)gtag('event','newsletter_signup',{variant:'B',ticker:T,lang:d.get('lang'),src:'stock'});
    })
    .catch(function(){form.removeAttribute('data-sending');});
});
})();</script>`;
}

const slug = t => t.replace(/[^A-Za-z0-9.\-]/g, '_');  // same as px/ file names
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
// Keep "</" out of inline JSON so the closing script tag cannot be forged by a string.
const jsonLd = obj => JSON.stringify(obj).replace(/<\//g, '<\\/');
// generated_hkt is "YYYY-MM-DD HH:MM" in Hong Kong time. Other values are already ISO from the data.
const asModified = s => /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(s) ? s.replace(' ', 'T') + ':00+08:00' : s;

function graph(lang, t, url, meta, stats) {
  const home = `${SITE}${lang}/`;
  const L = T[lang];
  const dataset = {
    '@type': 'Dataset',
    name: L.dsName(t),
    description: L.dsDesc(t, stats),
    url,
    creator: { '@type': 'Organization', name: 'The Crowd Tape', url: SITE },
    license: SITE,
    isAccessibleForFree: true,
    temporalCoverage: `${stats.from}/${stats.to}`,
    variableMeasured: [
      { '@type': 'PropertyValue', name: L.bullName, value: stats.bull },
      { '@type': 'PropertyValue', name: L.bearName, value: stats.bear },
      { '@type': 'PropertyValue', name: L.menName, value: stats.mentions },
    ],
  };
  const modified = asModified(stats.modified || '');
  if (modified) dataset.dateModified = modified;
  return {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'WebPage',
        url,
        name: meta.title,
        inLanguage: LANGS[lang],
        isPartOf: { '@type': 'WebSite', name: 'The Crowd Tape', url: SITE },
      },
      {
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: L.home, item: home },
          { '@type': 'ListItem', position: 2, name: L.index, item: home + '#stock-index' },
          { '@type': 'ListItem', position: 3, name: t, item: url },
        ],
      },
      dataset,
    ],
  };
}

// 回到頂部 (Tim, 2026-10-21): same button and look as the live page; stock pages have no ☕ button, so it sits in the corner.
function toTop(label) {
  return `<button type="button" class="to-top" aria-label="${esc(label)}" title="${esc(label)}">↑</button>
<style>.to-top{position:fixed;right:24px;bottom:calc(24px + env(safe-area-inset-bottom,0px));z-index:30;width:42px;height:42px;padding:0;border-radius:999px;border:1px solid var(--line-strong);background:var(--panel);color:var(--tx-strong);font:700 19px/1 var(--f-body);cursor:pointer;box-shadow:0 3px 10px rgba(59,47,37,.15);opacity:0;pointer-events:none;transition:opacity .2s}
.to-top.on{opacity:1;pointer-events:auto}
@media(max-width:700px){.to-top{right:16px;bottom:calc(16px + env(safe-area-inset-bottom,0px))}}</style>
<script>(function(){var b=document.querySelector('.to-top');if(!b)return;var on=false,q=false;
function u(){q=false;var s=scrollY>innerHeight;if(s!==on){on=s;b.classList.toggle('on',s)}}
addEventListener('scroll',function(){if(!q){q=true;requestAnimationFrame(u)}},{passive:true});u();
b.addEventListener('click',function(){scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'})})})();</script>`;
}

function shell(master, lang, t, list, body, meta, stats) {
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
<script type="application/ld+json">${jsonLd(graph(lang, t, url, meta, stats))}</script>
${fonts}
${styles}
<style>.brand-home{color:inherit;text-decoration:none}
/* phones: the header scrolls away so the stock content gets the whole screen (Tim, 2026-10-21); ↑ button goes back up */
@media(max-width:700px){header.top{position:static}}
.stock-static{padding-top:8px}.stock-static .back{text-decoration:none;display:inline-block}
.advice{margin:8px 16px 0;padding:10px 12px;border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:0 12px 12px 0;background:var(--accent-soft);font-size:14px;line-height:1.45}
.open-live{display:flex;justify-content:center;margin:8px 0 40px}.open-live a{font:600 15px/1 var(--f-body);padding:12px 20px;border-radius:999px;
background:var(--accent);color:#fff;text-decoration:none}
.site-nav{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;max-width:100%;min-width:0}
.site-nav a{box-sizing:border-box;max-width:100%;font-size:12.5px;font-weight:700;padding:5px 10px;border:1px solid var(--line);border-radius:999px;text-decoration:none;color:var(--ink);background:var(--panel);line-height:1.3}
.site-nav a.nav-donate{background:var(--accent);color:#fff;border-color:var(--accent)}
.money-bar{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;box-sizing:border-box;max-width:100%;min-width:0;margin:8px 16px 0;padding:8px 10px;border:1px dashed var(--line-strong);border-radius:12px;background:var(--panel);font-size:13px;font-weight:700}
.money-bar a,.tv-line a{color:var(--ink);text-decoration:none}
.money-bar .pj-tag,.tv-line .pj-tag,.foot .pj-tag{display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.04em;color:var(--mut);border:1px solid var(--line-strong);border-radius:999px;padding:1px 8px;line-height:1.4}
.tv-line{margin:12px 16px 8px;font-size:14px;line-height:1.45;overflow-wrap:anywhere;max-width:100%}
.foot a{font-weight:700}
${NL_CSS}</style>
</head>
<body>
<header class="top"><div class="wrap"><div class="brand-wrap">${brand}<nav class="lang-sw" aria-label="Language">${sw}</nav><nav class="site-nav" aria-label="${esc(T[lang].promo)}"><a href="/${lang}/tools/">${esc(T[lang].tools)}</a><a class="nav-donate" href="/${lang}/support/">${esc(T[lang].support)}</a></nav></div></div></header>
<main class="stock-static"><nav class="money-bar" aria-label="${esc(T[lang].promo)}"><span class="pj-tag">${esc(T[lang].promo)}</span><a href="/${lang}/tools/">${esc(T[lang].tools)}</a><a href="/${lang}/support/">${esc(T[lang].support)}</a></nav><p class="advice" role="note">${esc(T[lang].advice)}</p>${body}
<p class="tv-line"><span class="pj-tag">${esc(T[lang].promo)}</span> <a href="https://www.tradingview.com/?aff_id=1172819" rel="sponsored noopener" target="_blank" data-tool="tradingview">${esc(T[lang].tv)}</a></p>
<div class="open-live"><a href="/${lang}/#stock/${encodeURIComponent(t)}">${esc(T[lang].open)}</a></div>
${indexRow(lang, list)}</main>
<footer class="wrap foot"><p><a href="/${lang}/tools/">${esc(T[lang].tools)}</a> · <a href="/${lang}/support/">${esc(T[lang].support)}</a> · <a href="/${lang}/newsletter/">${esc(T[lang].news)}</a> · <a href="https://www.tradingview.com/?aff_id=1172819" rel="sponsored noopener" target="_blank" data-tool="tradingview">TradingView <span class="pj-tag">${esc(T[lang].promo)}</span></a></p></footer>
<script>document.addEventListener('click',function(e){var a=e.target&&e.target.closest&&e.target.closest('a[href]');if(!a||typeof gtag!=='function')return;var u=a.href,h='';try{h=new URL(u).hostname.toLowerCase()}catch(err){return}var tool=a.getAttribute('data-tool');if(tool||h==='tradingview.com'||h.endsWith('.tradingview.com'))gtag('event','affiliate_click',{tool:(tool||'tradingview').toLowerCase(),lang:document.documentElement.lang||''});if(h==='x.com'||h.endsWith('.x.com')||h==='twitter.com'||h.endsWith('.twitter.com'))gtag('event','x_outbound',{link_url:u,page:'stock',lang:document.documentElement.lang||'',transport_type:'beacon'})});</script>
${nlScript(nlCopy(lang).ok)}
${toTop(T[lang].top)}
</body></html>
`;
}

function indexRow(lang, list) {
  const links = list.map(t => `<a href="/${lang}/stock/${slug(t)}/">${esc(t)}</a>`).join(' ');
  return `<nav id="stock-index" class="wrap stock-index" aria-label="${esc(T[lang].index)}" style="font-size:12.5px;line-height:2;color:var(--muted);padding:12px 16px 28px">`
    + `<b>${esc(T[lang].index)}</b>：${links}</nav>`;
}

// One <url> per <loc>; the last copy wins.
function dedupeSitemap(sm) {
  const found = [];
  for (const m of sm.matchAll(/\s*<url>[\s\S]*?<\/url>/g)) {
    const loc = (m[0].match(/<loc>([^<]*)<\/loc>/) || [])[1];
    found.push([m, loc]);
  }
  const last = new Map();
  found.forEach(([, loc], i) => { if (loc !== undefined) last.set(loc, i); });
  let out = '', pos = 0;
  found.forEach(([m, loc], i) => {
    if (loc !== undefined && last.get(loc) !== i) {
      out += sm.slice(pos, m.index);
      pos = m.index + m[0].length;
    }
  });
  return out + sm.slice(pos);
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
  const root = path.resolve(__dirname, '..');
  const srv = await start(root);
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
    await p.route('**/*', route => {
      const u = route.request().url();
      if (u.startsWith(srv.origin) || u.startsWith('file:')) route.continue();
      else route.abort();
    });
    await p.goto(pageUrl(srv.origin, root, file) + '#daily', { waitUntil: 'domcontentloaded' });
    await p.waitForFunction(() => typeof openDive === 'function' && typeof POSTS !== 'undefined');
    await p.evaluate(async () => {
      if (window.__loadCore) await window.__loadCore();
      if (window.__loadAllPosts) await window.__loadAllPosts();
      if (window.__postsFailed) throw new Error('older posts failed to load');
    });
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
      const c = { bull: v[0] || 0, neu: v[1] || 0, none: v[2] || 0, bear: v[3] || 0 };
      const rows = POSTS.filter(x => x.t === t).sort((a, b) => a.ms - b.ms);
      const from = rows.length ? rows[0].d : TODAY;
      const to = TODAY;
      const last = rows.length ? rows[rows.length - 1] : null;
      let modified = last && last.p && last.p.time_utc ? String(last.p.time_utc) : '';
      if (!modified && D.meta) modified = D.meta.cutoff_hkt || D.meta.generated_hkt || '';
      return { t, name, c, html: el.innerHTML, from, to, modified, mentions: c.bull + c.neu + c.none + c.bear };
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
      const boxed = insertAfterKpis(body, nlMarkup(lang, pg.t));
      if (boxed === body) {
        console.log('::error::股票網頁沒有電子報位置：' + lang + '/' + pg.t);
        process.exit(1);
      }
      body = boxed;
      const meta = { title: T[lang].title(pg.t, pg.name, pg.c), desc: T[lang].desc(pg.t, n[pg.t], pg.c) };
      const stats = { bull: pg.c.bull, bear: pg.c.bear, mentions: pg.mentions, from: pg.from, to: pg.to, modified: pg.modified };
      fs.mkdirSync(path.join(dir, slug(pg.t)), { recursive: true });
      fs.writeFileSync(path.join(dir, slug(pg.t), 'index.html'), shell(master, lang, pg.t, names, body, meta, stats));
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
  const siteEsc = SITE.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const gen = (sm.match(new RegExp('<loc>' + siteEsc + '</loc><lastmod>([^<]+)')) || [])[1] || '';
  const rows = list.map(([t]) => {
    const alt = Object.entries(LANGS).map(([k, h]) => `<xhtml:link rel="alternate" hreflang="${h}" href="${SITE}${k}/stock/${slug(t)}/"/>`).join('');
    return Object.keys(LANGS).map(k => `  <url><loc>${SITE}${k}/stock/${slug(t)}/</loc><lastmod>${gen}</lastmod><changefreq>daily</changefreq>${alt}</url>`).join('\n');
  }).join('\n');
  sm = dedupeSitemap(sm.replace('</urlset>', rows + '\n</urlset>'));
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
  srv.server.close();
  console.log(`股票網頁：${list.length} 隻 × ${Object.keys(LANGS).length} 個語言，頭像 ${seen.size} 個`);
  if (bad.length) { console.log('::error::股票網頁檢查唔合格：' + bad.join('、')); process.exit(1); }
})();
