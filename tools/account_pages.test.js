// EN account title/meta length. Run: node --test tools/account_pages.test.js
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { T } = require('./account_pages.js');

test('EN account title and meta stay within SERP length', () => {
  const cases = [
    { nm: 'Stephanie Link', h: 'stephanie_link', b: 12, r: 8, ts: 'AAPL, NVDA, MSFT, TSLA, AMZN, META, GOOGL' },
    { nm: 'Elon Musk', h: 'elonmusk', b: 3, r: 1, ts: 'TSLA' },
    { nm: 'A Very Long Display Name Here', h: 'fifteenccharsxx', b: 120, r: 80, ts: 'AAA, BBB, CCC' },
  ];
  for (const x of cases) {
    const title = T.en.title(x.nm, x.h);
    const desc = T.en.desc(x.h, x.b, x.r, x.ts);
    assert.ok(title.startsWith('@' + x.h), title);
    assert.ok(title.endsWith('| The Crowd Tape'), title);
    assert.ok(title.length <= 70, `${title} (${title.length})`);
    assert.ok(!title.includes(x.ts), title);
    assert.ok(desc.length >= 120 && desc.length <= 160, `${desc} (${desc.length})`);
    assert.ok(!desc.includes(x.ts), desc);
  }
});
