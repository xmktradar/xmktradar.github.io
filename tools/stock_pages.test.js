// Iframe src for the static stock-page TradingView chart.
// node --test tools/stock_pages.test.js
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const { tvWidgetSrc, tvMappedSymbol, tvChartLink, tvChartBlock, ensureTvFrameSrc } = require('./stock_pages.js');

const SYMBOLS = {
  NVDA: 'NASDAQ:NVDA',
  'BRK.B': 'NYSE:BRK-B',
  PSKY: 'NASDAQ:PSKY',
  SPY: 'AMEX:SPY',
};

test('symbol mapping: exchange prefix, dot share class, 404 list and unknown ticker', () => {
  assert.deepEqual(tvMappedSymbol('NVDA', SYMBOLS), { symbol: 'NASDAQ:NVDA', fallback: false });
  assert.deepEqual(tvMappedSymbol('BRK.B', SYMBOLS), { symbol: 'NYSE:BRK.B', fallback: false });
  // PSKY is mapped, but the symbol page 404s, so the widget gets the plain ticker.
  assert.deepEqual(tvMappedSymbol('PSKY', SYMBOLS), { symbol: 'PSKY', fallback: true });
  assert.deepEqual(tvMappedSymbol('SPX', SYMBOLS), { symbol: 'SPX', fallback: true });
  assert.deepEqual(tvMappedSymbol('NOPE', { NOPE: 'not a symbol' }), { symbol: 'NOPE', fallback: true });
  assert.deepEqual(tvMappedSymbol('ZZ', { ZZ: 'ONLYONE' }), { symbol: 'ZZ', fallback: true });
});

test('iframe src: locales, widget params, no aff_id', () => {
  const locales = { zh: 'zh_TW', en: 'en' };
  for (const [lang, locale] of Object.entries(locales)) {
    const src = tvWidgetSrc('NVDA', SYMBOLS, lang);
    const u = new URL(src);
    assert.equal(u.origin + u.pathname, 'https://s.tradingview.com/widgetembed/');
    assert.equal(u.searchParams.get('symbol'), 'NASDAQ:NVDA');
    assert.equal(u.searchParams.get('interval'), 'D');
    assert.equal(u.searchParams.get('theme'), 'light');
    assert.equal(u.searchParams.get('style'), '1');
    assert.equal(u.searchParams.get('timezone'), 'Asia/Hong_Kong');
    assert.equal(u.searchParams.get('hide_side_toolbar'), '1');
    assert.equal(u.searchParams.get('allow_symbol_change'), '0');
    assert.equal(u.searchParams.get('locale'), locale);
    assert.equal(u.searchParams.get('aff_id'), null);
    assert.equal(src.includes('aff_id'), false);
  }
  assert.equal(new URL(tvWidgetSrc('BRK.B', SYMBOLS, 'en')).searchParams.get('symbol'), 'NYSE:BRK.B');
  const psky = new URL(tvWidgetSrc('PSKY', SYMBOLS, 'zh'));
  assert.equal(psky.searchParams.get('symbol'), 'PSKY');
  assert.equal(psky.searchParams.get('locale'), 'zh_TW');
  assert.equal(new URL(tvWidgetSrc('SPX', SYMBOLS, 'en')).searchParams.get('symbol'), 'SPX');
});

test('other TradingView links keep aff_id=1172819', () => {
  const mapped = tvChartLink('BRK.B', SYMBOLS);
  assert.equal(mapped.fallback, false);
  assert.equal(mapped.href, 'https://www.tradingview.com/symbols/NYSE-BRK.B/?aff_id=1172819');
  const fb = tvChartLink('PSKY', SYMBOLS);
  assert.equal(fb.fallback, true);
  assert.equal(fb.href, 'https://www.tradingview.com/chart/?symbol=PSKY&aff_id=1172819');
  const unknown = tvChartLink('SPX', SYMBOLS);
  assert.equal(unknown.fallback, true);
  assert.ok(unknown.href.includes('aff_id=1172819'));
  assert.ok(!tvWidgetSrc('NVDA', SYMBOLS, 'en').includes('aff_id'));
});

test('chart block is a plain iframe above the svg', () => {
  const svg = '<section class="c12 panel px-sec"><svg class="px-chart"></svg></section>';
  const html = tvChartBlock('en', 'NVDA', SYMBOLS, svg);
  assert.match(html, /<iframe class="tv-frame"[^>]*loading="lazy"/);
  assert.equal(/<script/i.test(html), false);
  assert.ok(html.indexOf('class="tv-frame"') < html.indexOf('class="px-chart"'));
  assert.equal(html.includes('aff_id'), false);
  const src = html.match(/src="([^"]+)"/)[1].replace(/&amp;/g, '&');
  assert.equal(new URL(src).searchParams.get('symbol'), 'NASDAQ:NVDA');
  const bare = tvChartBlock('en', 'PSKY', SYMBOLS, '');
  assert.match(bare, /title="\$PSKY TradingView chart"/);
  assert.match(bare, /locale=en/);
  assert.equal(bare.includes('px-chart'), false);
  assert.match(tvChartBlock('zh', 'NVDA', SYMBOLS, ''), /title="\$NVDA TradingView 走勢圖"/);
});

test('CSP meta gains TradingView frame-src; pages without one are unchanged', () => {
  assert.equal(ensureTvFrameSrc('<meta charset="utf-8">'), '<meta charset="utf-8">');
  const meta = '<meta http-equiv="Content-Security-Policy" content="default-src \'self\'">';
  const once = ensureTvFrameSrc(meta);
  assert.match(once, /frame-src https:\/\/s\.tradingview\.com https:\/\/www\.tradingview\.com/);
  assert.equal(ensureTvFrameSrc(once), once);
  const partial = '<meta http-equiv="Content-Security-Policy" content="frame-src \'self\' https://s.tradingview.com">';
  const filled = ensureTvFrameSrc(partial);
  assert.match(filled, /frame-src 'self' https:\/\/s\.tradingview\.com https:\/\/www\.tradingview\.com/);
  assert.equal(filled.includes('https://s.tradingview.com https://s.tradingview.com'), false);
});

function iframeSrc(html) {
  const visible = html.replace(/<noscript\b[^>]*>[\s\S]*?<\/noscript>/gi, '');
  const m = visible.match(/<iframe\b[^>]*class="tv-frame"[^>]*>/i);
  assert.ok(m, 'missing visible tv-frame iframe');
  const src = m[0].match(/\bsrc="([^"]*)"/);
  assert.ok(src, 'iframe has no src');
  return { tag: m[0], src: src[1].replace(/&amp;/g, '&').replace(/&#38;/g, '&'), visible };
}

test('generated stock pages embed the iframe and keep the svg', () => {
  const root = path.join(__dirname, '..');
  const titles = {
    zh: 'title="$NVDA TradingView 走勢圖"',
    en: 'title="$NVDA TradingView chart"',
  };
  const locales = { zh: 'zh_TW', en: 'en' };
  for (const lang of ['zh', 'en']) {
    const page = path.join(root, lang, 'stock', 'NVDA', 'index.html');
    assert.ok(fs.existsSync(page), 'missing ' + page);
    const html = fs.readFileSync(page, 'utf8');
    const { tag, src, visible } = iframeSrc(html);
    const u = new URL(src);
    assert.equal(u.origin + u.pathname, 'https://s.tradingview.com/widgetembed/');
    assert.equal(u.searchParams.get('symbol'), 'NASDAQ:NVDA');
    assert.equal(u.searchParams.get('locale'), locales[lang]);
    assert.equal(u.searchParams.get('hide_side_toolbar'), '1');
    assert.equal(u.searchParams.get('allow_symbol_change'), '0');
    assert.equal(u.searchParams.get('timezone'), 'Asia/Hong_Kong');
    assert.equal(u.searchParams.get('aff_id'), null);
    assert.equal(tag.includes('aff_id'), false);
    assert.equal(/<script\b[^>]*src=["'][^"']*tradingview\.com/i.test(html), false);
    assert.ok(visible.indexOf('class="tv-frame"') < visible.indexOf('class="px-chart"'));
    assert.ok(tag.includes(titles[lang]));
    assert.match(html, /\.tv-frame\{[^}]*width:100%[^}]*height:420px[^}]*border:0/);
    assert.match(html, /@media\(max-width:480px\)\{\.tv-frame\{height:320px\}\}/);
    assert.ok(html.includes('aff_id=1172819'));
    const line = html.match(/<p class="tv-line">[\s\S]*?<\/p>/);
    assert.ok(line && line[0].includes('aff_id=1172819'));
    assert.equal(line[0].includes('widgetembed'), false);
  }
  const samples = [
    ['BRK.B', 'NYSE:BRK.B'],
    ['PSKY', 'PSKY'],
    ['SPX', 'SPX'],
  ];
  for (const [ticker, symbol] of samples) {
    const page = path.join(root, 'en', 'stock', ticker, 'index.html');
    if (!fs.existsSync(page)) continue;
    const { src } = iframeSrc(fs.readFileSync(page, 'utf8'));
    assert.equal(new URL(src).searchParams.get('symbol'), symbol, ticker);
    assert.equal(new URL(src).searchParams.has('aff_id'), false, ticker);
  }
});
