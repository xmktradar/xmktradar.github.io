// node --test tools/stock_follow.test.js
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { followBox } = require('./stock_pages.js');

const book = {
  from: '2026-10-06',
  as_of: '2026-11-17',
  by_ticker: {
    NVDA: {
      bull: { opened: 6, settled: 4, immature: 2, avg_ret: -0.042, avg_xs: -0.011, hit: 0.25 },
      split: { opened: 1, settled: 0, immature: 1, avg_ret: null, avg_xs: null, hit: null },
    },
  },
};

test('stock follow-through names the window and does not invent a 90-day record', () => {
  const html = followBox('zh', 'NVDA', book);
  assert.match(html, /列入之後 10 個交易日/);
  assert.match(html, /共同看好 6 次/);
  assert.match(html, /已滿 10 個交易日 4 次/);
  assert.match(html, /平均股價 -4\.2%/);
  assert.match(html, /相對 QQQ -1\.1%/);
  assert.match(html, /明顯分歧 1 次，尚未滿 10 個交易日/);
  assert.match(html, /2026-10-06/);
  assert.match(html, /不是投資建議/);
  assert.match(html, /\/zh\/weekly\//);
  assert.equal(followBox('zh', 'AAPL', book), '');
});

test('english follow-through stays in english', () => {
  const html = followBox('en', 'NVDA', book);
  assert.match(html, /10 sessions after joining/);
  assert.doesNotMatch(html, /共同看好/);
  assert.match(html, /joint bullish/);
});
