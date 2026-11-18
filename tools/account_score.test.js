// node --test tools/account_score.test.js
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { scoreCalls } = require('./account_score.js');

test('bullish win is a rising stock; flat is not a win', () => {
  const s = scoreCalls([
    { side: 'bull', ret: 0.02, xs: 0.01 },
    { side: 'bull', ret: -0.01, xs: -0.02 },
    { side: 'bull', ret: 0, xs: 0 },
  ]);
  assert.equal(s.n, 3);
  assert.equal(s.bull.n, 3);
  assert.equal(s.bull.wins, 1);
  assert.ok(Math.abs(s.bull.avg - (0.01 / 3)) < 1e-12);
  assert.equal(s.bear, null);
});

test('bearish win is a falling stock; excess can be missing', () => {
  const s = scoreCalls([
    { side: 'bear', ret: -0.04, xs: 0.02 },
    { side: 'bear', ret: 0.01 },
  ]);
  assert.equal(s.bear.wins, 1);
  assert.equal(s.bear.avgXs, 0.02);
  assert.equal(s.n, 2);
});
