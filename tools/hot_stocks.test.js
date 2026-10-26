// node --test tools/hot_stocks.test.js
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { rankHot, sitemapTickers, DAY_MS } = require('./hot_stocks.js');

const CUT = Date.parse('2026-10-26T06:54:02+08:00');

test('window is closed 7*24h ending at the cutoff, not calendar dates', () => {
  const span = 7 * DAY_MS;
  assert.equal(CUT - span, Date.parse('2026-10-19T06:54:02+08:00'));
  const rows = [
    { t: 'EDGE', ms: CUT - span, id: 'on-far' },
    { t: 'EARLY', ms: CUT - span - 1, id: 'past-far' },
    { t: 'MIDNIGHT', ms: Date.parse('2026-10-19T00:00:00+08:00'), id: 'midnight' },
    { t: 'AT', ms: CUT, id: 'at-cut' },
    { t: 'AFTER', ms: CUT + 1, id: 'after' },
    { t: 'IN', ms: CUT - 60e3, id: 'inside' },
  ];
  const by = Object.fromEntries(rankHot(rows, CUT, 7, 30).map(x => [x.t, x.n]));
  assert.equal(by.EDGE, 1);
  assert.equal(by.AT, 1);
  assert.equal(by.IN, 1);
  assert.equal(by.EARLY, undefined);
  assert.equal(by.MIDNIGHT, undefined);
  assert.equal(by.AFTER, undefined);
});

test('the same post counts once per ticker', () => {
  const rows = [
    { t: 'NVDA', ms: CUT, id: 'p1' },
    { t: 'NVDA', ms: CUT, id: 'p1' },
    { t: 'NVDA', ms: CUT - 1000, id: 'p2' },
    { t: 'AAPL', ms: CUT, id: 'p1' },
  ];
  const got = rankHot(rows, CUT, 7, 30);
  assert.deepEqual(got, [{ t: 'NVDA', n: 2 }, { t: 'AAPL', n: 1 }]);
});

test('ties: higher count first, then ticker A–Z', () => {
  const rows = [
    { t: 'NVDA', ms: CUT, id: 'a' },
    { t: 'NVDA', ms: CUT, id: 'b' },
    { t: 'AAPL', ms: CUT, id: 'c' },
    { t: 'AAPL', ms: CUT, id: 'd' },
    { t: 'MSFT', ms: CUT, id: 'e' },
    { t: 'MSFT', ms: CUT, id: 'f' },
    { t: 'MSFT', ms: CUT, id: 'g' },
  ];
  assert.deepEqual(rankHot(rows, CUT, 7, 30).map(x => x.t), ['MSFT', 'AAPL', 'NVDA']);
});

test('top 30 cap keeps the highest counts and breaks the boundary A–Z', () => {
  const rows = [];
  for (let i = 0; i < 40; i++) {
    const t = 'T' + String(i).padStart(2, '0');
    rows.push({ t, ms: CUT, id: t });
  }
  rows.push({ t: 'T39', ms: CUT - 1, id: 'extra' });
  const got = rankHot(rows, CUT, 7, 30);
  assert.equal(got.length, 30);
  assert.deepEqual(got[0], { t: 'T39', n: 2 });
  assert.deepEqual(got.slice(1).map(x => x.t), Array.from({ length: 29 }, (_, i) => 'T' + String(i).padStart(2, '0')));
  assert.ok(!got.some(x => x.t === 'T29'));
  assert.equal(rankHot(rows, CUT, 7, 0).length, 0);
  assert.deepEqual(rankHot([], CUT, 7, 30), []);
});

test('only tickers with a stock page', () => {
  const rows = [];
  for (let i = 0; i < 8; i++) rows.push({ t: 'GONE', ms: CUT, id: 'g' + i, page: false });
  rows.push({ t: 'LIVE', ms: CUT, id: 'live', page: true });
  rows.push({ t: 'ALSO', ms: CUT, id: 'also' });
  assert.deepEqual(rankHot(rows, CUT, 7, 30).map(x => x.t), ['ALSO', 'LIVE']);
});

test('sitemapTickers keeps count >= 2 by default, A–Z', () => {
  assert.deepEqual(sitemapTickers({ AAA: 2, BBB: 1, CCC: 0, DDD: 5, EEE: 2 }), ['AAA', 'DDD', 'EEE']);
  assert.deepEqual(sitemapTickers({ AAA: 1 }), []);
  assert.deepEqual(sitemapTickers({}), []);
  assert.deepEqual(sitemapTickers(null), []);
  assert.deepEqual(sitemapTickers([['MSFT', 9], ['AAPL', 1], ['NVDA', 2]]), ['MSFT', 'NVDA']);
  assert.deepEqual(sitemapTickers(new Map([['SPY', 3], ['QQQ', 2], ['X', 1]])), ['QQQ', 'SPY']);
  assert.deepEqual(sitemapTickers([{ t: 'ZZ', n: 2 }, { t: 'AA', n: 4 }, { t: 'BB', n: 1 }]), ['AA', 'ZZ']);
  assert.deepEqual(sitemapTickers({ AAA: 3, BBB: 4 }, 4), ['BBB']);
  assert.deepEqual(sitemapTickers({ AAA: 2, BBB: 2 }, null), ['AAA', 'BBB']);
});

test('30-day sitemap filter uses the same window and page rule', () => {
  const span = 30 * DAY_MS;
  const rows = [
    { t: 'KEEP', ms: CUT - span, id: 'a', page: true },
    { t: 'KEEP', ms: CUT, id: 'b', page: true },
    { t: 'DROP', ms: CUT - span, id: 'c', page: true },
    { t: 'DROP', ms: CUT - span - 1, id: 'd', page: true },
    { t: 'OLD', ms: CUT - span - 1, id: 'e', page: true },
    { t: 'OLD', ms: CUT - span - 2, id: 'f', page: true },
    { t: 'NOPAGE', ms: CUT, id: 'g', page: false },
    { t: 'NOPAGE', ms: CUT - 1, id: 'h', page: false },
  ];
  const counts = {};
  for (const t of ['KEEP', 'DROP', 'OLD', 'NOPAGE']) counts[t] = 0;
  for (const x of rankHot(rows, CUT, 30, 100)) counts[x.t] = x.n;
  assert.equal(counts.KEEP, 2);
  assert.equal(counts.DROP, 1);
  assert.equal(counts.OLD, 0);
  assert.equal(counts.NOPAGE, 0);
  const kept = sitemapTickers(counts);
  assert.deepEqual(kept, ['KEEP']);
  const pages = ['KEEP', 'DROP', 'OLD', 'NOPAGE'];
  const left = pages.filter(t => !kept.includes(t));
  assert.equal(kept.length, 1);
  assert.equal(left.length, 3);
});
