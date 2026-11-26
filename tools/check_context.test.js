// Tests for the page-check teardown retry. No browser: check.js must load without launching one.
const test = require('node:test'), assert = require('node:assert');
const fs = require('fs'), path = require('path');
const { isContextTeardown, retryOnTeardown } = require('./check.js');

test('isContextTeardown matches a dead Playwright page', () => {
  const yes = [
    'page.evaluate: Execution context was destroyed, most likely because of a navigation.',
    'Execution context was destroyed, most likely because of a navigation.',
    'Target closed',
    'target closed',
    'Target page, context or browser has been closed',
    'page crashed',
    'Page crashed',
    'TARGET CRASHED',
    'target crashed',
    'Frame was detached',
  ];
  for (const s of yes) assert.equal(isContextTeardown(s), true, s);
  assert.equal(isContextTeardown(new Error(yes[0])), true);
  assert.equal(isContextTeardown({ message: 'page crashed' }), true);
});

test('isContextTeardown ignores real check failures', () => {
  const no = [
    'overflow',
    'older posts failed to load',
    'prices did not load',
    'page.evaluate: Error: prices did not load',
    'page.evaluate: Error: older posts failed to load',
    'AssertionError: expected true to equal false',
    'page.evaluate: ReferenceError: nope is not defined',
    'page.waitForFunction: Timeout 60000ms exceeded.',
    '',
  ];
  for (const s of no) assert.equal(isContextTeardown(s), false, JSON.stringify(s));
  assert.equal(isContextTeardown(null), false);
  assert.equal(isContextTeardown(undefined), false);
  assert.equal(isContextTeardown(new Error('overflow')), false);
});

test('retry helper retries a teardown and keeps a later success', async () => {
  let n = 0;
  const logs = [];
  const out = await retryOnTeardown('1280px #monthly', async () => {
    n++;
    if (n === 1) throw new Error('page.evaluate: Execution context was destroyed, most likely because of a navigation.');
    return { ok: true };
  }, { attempts: 3, log: line => logs.push(line) });
  assert.equal(n, 2);
  assert.equal(out.ok, true);
  assert.equal(logs.length, 1);
  assert.match(logs[0], /^retry 1280px #monthly \(2\/3\) /);
});

test('retry helper does not retry overflow, missing posts, or missing prices', async () => {
  for (const msg of ['overflow', 'older posts failed to load', 'prices did not load']) {
    let n = 0;
    const logs = [];
    await assert.rejects(() => retryOnTeardown('390px #stock/NVDA', async () => {
      n++;
      throw new Error(msg);
    }, { attempts: 3, log: line => logs.push(line) }), new RegExp(msg));
    assert.equal(n, 1, msg);
    assert.equal(logs.length, 0, msg);
  }
});

test('a finished bad view is not retried', async () => {
  let n = 0;
  const out = await retryOnTeardown('1280px #daily', async () => {
    n++;
    return { ok: false, reason: 'overflow' };
  }, { attempts: 3, log: () => { throw new Error('should not retry'); } });
  assert.equal(n, 1);
  assert.equal(out.ok, false);
});

test('retry helper stops after 3 teardown attempts', async () => {
  let n = 0;
  const logs = [];
  await assert.rejects(() => retryOnTeardown('1280px #monthly', async () => {
    n++;
    throw new Error('Target closed');
  }, { attempts: 3, log: line => logs.push(line) }), /Target closed/);
  assert.equal(n, 3);
  assert.equal(logs.length, 2);
});

test('check.js stays requireable and still checks every view', () => {
  const src = fs.readFileSync(path.join(__dirname, 'check.js'), 'utf8');
  assert.match(src, /if\s*\(\s*require\.main\s*===\s*module\s*\)/);
  assert.match(src, /module\.exports\s*=\s*\{[^}]*isContextTeardown/);
  assert.match(src, /await p\.waitForFunction\([\s\S]*?\);\s*\}\s*catch \(e\) \{\s*dead\(e\);/);
  assert.doesNotMatch(src, /waitForFunction\([\s\S]{0,500}?\)\s*\.catch\(/);
  for (const v of ['daily', 'weekly', 'monthly', 'macro', 'tracked', 'stock/NVDA']) assert.match(src, new RegExp(v.replace('/', '\\/')));
  assert.match(src, /1280,\s*900/);
  assert.match(src, /390,\s*844/);
  assert.match(src, /::error::網頁檢查唔合格：/);
  assert.match(src, /route\.abort\(\)/);
  assert.match(src, /__loadCore/);
  assert.match(src, /__loadAllPosts/);
  assert.match(src, /waitForTimeout\(50\)/);
  assert.match(src, /older posts failed to load/);
  assert.match(src, /prices did not load/);
  assert.match(src, /__viewDone === true/);
  assert.match(src, /390px and 1280px #weekly must complete/);
});
