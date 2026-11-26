// Tests for weekly mention indexes and slice yielding.
// viewWeekly used to filter every window of posts per ticker (and once per day).
const test = require('node:test'), assert = require('node:assert');
const fs = require('fs'), path = require('path');

const ROOT = path.join(__dirname, '..');
const PAGES = ['index.html', 'zh/index.html', 'en/index.html'];

function extractFn(src, name) {
  const key = 'function ' + name + '(';
  const start = src.indexOf(key);
  if (start < 0) throw new Error('missing ' + name);
  const open = src.indexOf('{', start);
  if (open < 0) throw new Error('missing body ' + name);
  let depth = 0, state = 'code';
  const interp = [];
  for (let i = open; i < src.length; i++) {
    const c = src[i], n = src[i + 1];
    if (state === 'line') { if (c === '\n') state = 'code'; continue; }
    if (state === 'block') { if (c === '*' && n === '/') { state = 'code'; i++; } continue; }
    if (state === 'sq' || state === 'dq') {
      if (c === '\\') { i++; continue; }
      if ((state === 'sq' && c === "'") || (state === 'dq' && c === '"')) state = 'code';
      continue;
    }
    if (state === 'tpl') {
      if (c === '\\') { i++; continue; }
      if (c === '`') { state = 'code'; continue; }
      if (c === '$' && n === '{') { interp.push(depth); depth++; state = 'code'; i++; }
      continue;
    }
    if (c === '/' && n === '/') { state = 'line'; i++; continue; }
    if (c === '/' && n === '*') { state = 'block'; i++; continue; }
    if (c === "'") { state = 'sq'; continue; }
    if (c === '"') { state = 'dq'; continue; }
    if (c === '`') { state = 'tpl'; continue; }
    if (c === '{') { depth++; continue; }
    if (c === '}') {
      depth--;
      if (interp.length && depth === interp[interp.length - 1]) { interp.pop(); state = 'tpl'; continue; }
      if (depth === 0) return src.slice(start, i + 1);
    }
  }
  throw new Error('unclosed ' + name);
}

const page = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const HELPERS = ['countByTicker', 'countByTickerDay', 'countUrlsByTicker', 'runSlices'];
const F = new Function(
  HELPERS.map(n => extractFn(page, n)).join('\n') +
  '\nreturn {countByTicker, countByTickerDay, countUrlsByTicker, runSlices};'
)();
const { countByTicker, countByTickerDay, countUrlsByTicker, runSlices } = F;

test('empty input counts to empty maps', () => {
  assert.deepEqual(countByTicker([]), {});
  assert.deepEqual(countByTickerDay([]), {});
  assert.deepEqual(countUrlsByTicker([]), {});
});

test('ticker and day counts match a naive filter', () => {
  const all = [];
  let ms = 0;
  const add = (t, d, acc, url) => all.push({ t, d, acc, url, ms: ms++ });
  add('AAA', 'D1', 'A1', 'u1');
  add('AAA', 'D1', 'A2', 'u2');
  add('AAA', 'D2', 'A1', 'u3');
  add('BBB', 'D1', 'A1', 'u4');
  add('BBB', 'D1', 'A1', 'u4'); // same url twice
  add('BBB', 'D3', 'A3', 'u5');
  const byT = countByTicker(all);
  const byTD = countByTickerDay(all);
  const byU = countUrlsByTicker(all);
  const tickers = [...new Set(all.map(x => x.t))];
  const days = [...new Set(all.map(x => x.d))];
  for (const t of tickers) {
    assert.equal(byT[t] || 0, all.filter(x => x.t === t).length, t);
    assert.equal(byU[t] || 0, new Set(all.filter(x => x.t === t).map(x => x.url)).size, 'urls ' + t);
    for (const d of days) {
      assert.equal((byTD[t] && byTD[t][d]) || 0, all.filter(x => x.t === t && x.d === d).length, t + ' ' + d);
    }
  }
  assert.equal(byT.NOPE || 0, 0);
  assert.equal((byTD.AAA && byTD.AAA.D9) || 0, 0);
  assert.equal(byU.BBB, 2);
});

test('large weekly mention index finishes well under a second', () => {
  const days = [];
  for (let d = 0; d < 7; d++) days.push('2026-11-0' + (d + 1));
  const posts = [];
  let ms = 0;
  for (let t = 0; t < 400; t++) {
    const ticker = 'W' + t;
    for (let k = 0; k < 18; k++) {
      posts.push({
        t: ticker,
        d: days[k % 7],
        acc: 'A' + (k % 11),
        url: 'u-' + t + '-' + k,
        ms: ms++,
      });
    }
  }
  assert.equal(posts.length, 7200);
  assert.equal(new Set(posts.map(x => x.t)).size, 400);

  const t0 = performance.now();
  const byT = countByTicker(posts);
  const byTD = countByTickerDay(posts);
  const byU = countUrlsByTicker(posts);
  const msSpent = performance.now() - t0;
  assert.ok(msSpent < 1000, 'indexed week took ' + msSpent.toFixed(1) + 'ms');

  const tickers = [...new Set(posts.map(x => x.t))];
  for (const t of tickers) {
    assert.equal(byT[t], posts.filter(x => x.t === t).length, t);
    assert.equal(byU[t], 18, 'urls ' + t);
    const daySum = days.reduce((s, d) => s + ((byTD[t] && byTD[t][d]) || 0), 0);
    assert.equal(daySum, byT[t], 'day sum ' + t);
  }
  assert.equal(byTD.W0['2026-11-01'], posts.filter(x => x.t === 'W0' && x.d === '2026-11-01').length);
});

test('runSlices yields so a queued timeout can run before the last item', async () => {
  const items = [];
  for (let i = 0; i < 20; i++) items.push(i);
  let i = 0, flipped = false, midFlip = false;
  const seen = [];
  setTimeout(() => { flipped = true; }, 0);
  await new Promise(resolve => {
    runSlices(function () {
      if (i >= items.length) return false;
      if (flipped) midFlip = true;
      seen.push(items[i++]);
      return true;
    }, resolve, { ms: 0, maxItems: 1 });
  });
  assert.deepEqual(seen, items);
  assert.equal(flipped, true);
  assert.equal(midFlip, true);
});

test('every homepage weekly view uses the mention index and keeps the USD 5 line', () => {
  for (const rel of PAGES) {
    const src = fs.readFileSync(path.join(ROOT, rel), 'utf8');
    assert.match(src, /function countByTicker\(/);
    assert.match(src, /function countByTickerDay\(/);
    assert.match(src, /function countUrlsByTicker\(/);
    assert.match(src, /function runSlices\(/);
    assert.match(src, /function buildWeeklySliced\(/);
    assert.match(src, /function buildMonthlySliced\(/);
    assert.match(src, /c\.mentions=mentionsOf\(t,from,to\)/);
    const weekly = ['weeklyCtx', 'weeklyRow', 'weeklyHtml', 'viewWeekly', 'buildWeeklySliced'].map(n => extractFn(src, n)).join('\n');
    assert.doesNotMatch(weekly, /postsIn\(d,d\)\.filter\(x=>x\.t===t\)/);
    assert.doesNotMatch(weekly, /postsIn\(from,to\)\.filter\(x=>x\.t===t\)/);
    assert.match(weekly, /countByTickerDay/);
    const dist = extractFn(src, 'dist');
    assert.doesNotMatch(dist, /postsIn\(from,to\)\.filter\(x=>x\.t===t\)/);
    assert.match(dist, /mentionsOf\(t,from,to\)/);
    if (rel === 'en/index.html') {
      assert.match(src, /This page only shows how many accounts\. Names newly listed last week, whose last bullish call beat QQQ and SPY, are only in the Monday email\.<a href=\"\/en\/weekly\/\">Get the Monday brief, USD 5 a month \(cancel any time\)<\/a>/);
      assert.match(src, /28 days only show mention counts and how many accounts are bullish or bearish\. To compare with what you hold, read the Monday email\. Names are not on this page\.<a href=\"\/en\/weekly\/\">Get the Monday brief, USD 5 a month \(cancel any time\)<\/a>/);
    } else {
      assert.match(src, /這一頁只列人數。上週新列入、上一次做多又跑贏 QQQ 和 SPY 的名稱，只寫在星期一電郵。<a href="\/zh\/weekly\/">訂週報・潛力觀察（每月 USD 5）<\/a>/);
      assert.match(src, /28 日只列提及次數與多空人數。若要對照自己的持倉，請看星期一電郵，名稱不在這一頁。<a href="\/zh\/weekly\/">訂週報・潛力觀察（每月 USD 5）<\/a>/);
    }
  }
});
