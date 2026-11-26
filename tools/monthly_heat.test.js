// Tests for the monthly heatmap index. viewMonthly used to filter every post per ticker per day.
const test = require('node:test'), assert = require('node:assert');
const fs = require('fs'), path = require('path');

const ROOT = path.join(__dirname, '..');
const PAGES = ['index.html', 'zh/index.html', 'en/index.html'];

// Brace match that skips strings, template literals, and comments so ${} inside viewMonthly
// does not end the function early. Helpers have no strings; the same walker covers both.
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
const HELPERS = ['groupPostsByTicker', 'groupPostsByTickerDay', 'groupPostsByAccount'];
const F = new Function(HELPERS.map(n => extractFn(page, n)).join('\n') + '\nreturn {groupPostsByTicker, groupPostsByTickerDay, groupPostsByAccount};')();
const { groupPostsByTicker, groupPostsByTickerDay, groupPostsByAccount } = F;

const ST = ['bull', 'bear', 'neu', 'none'];

function cellOf(ps) {
  const b = ps.filter(x => x.s === 'bull').length, r = ps.filter(x => x.s === 'bear').length;
  return { n: ps.length, b, r, m: ps.filter(x => x.s === 'neu').length, u: ps.filter(x => x.s === 'none').length, net: b - r };
}

function hotNames(all, byT) {
  const tickers = [...new Set(all.map(x => x.t))];
  const use = (ps) => new Set(ps.map(x => x.acc)).size >= 3 && new Set(ps.map(x => x.d)).size >= 3;
  const naive = tickers.filter(t => use(all.filter(x => x.t === t))).sort();
  const indexed = tickers.filter(t => use(byT[t] || [])).sort();
  return { naive, indexed };
}

test('empty input indexes to empty maps', () => {
  assert.deepEqual(groupPostsByTicker([]), {});
  assert.deepEqual(groupPostsByTickerDay([]), {});
  assert.deepEqual(groupPostsByAccount([]), {});
});

test('indexed cells and hot names match a naive filter', () => {
  const all = [];
  let ms = 0;
  const add = (t, d, acc, s) => all.push({ t, d, acc, s, ms: ms++ });
  // One ticker across many days, several posts on the same day.
  for (const d of ['D1', 'D2', 'D3', 'D4']) {
    add('HOT1', d, 'A1', 'bull');
    add('HOT1', d, 'A2', 'bear');
    add('HOT1', d, 'A3', 'neu');
  }
  add('HOT1', 'D1', 'A4', 'none');
  add('HOT1', 'D1', 'A1', 'bull');
  // Exactly on the threshold: 3 accounts, 3 days.
  add('HOT2', 'D1', 'B1', 'bull');
  add('HOT2', 'D2', 'B2', 'bear');
  add('HOT2', 'D3', 'B3', 'bull');
  add('HOT2', 'D3', 'B1', 'none');
  // Two accounts over many days: not hot.
  for (const d of ['D1', 'D2', 'D3', 'D4', 'D5']) {
    add('COLDACC', d, 'C1', 'bull');
    add('COLDACC', d, 'C2', 'bear');
  }
  // Five accounts on only two days: not hot.
  for (const a of ['E1', 'E2', 'E3', 'E4', 'E5']) {
    add('COLDDAY', 'D1', a, 'bull');
    add('COLDDAY', 'D2', a, 'bear');
  }
  const days = [];
  for (let i = 0; i < 10; i++) days.push('F' + i);
  for (let i = 0; i < 172; i++) add('T' + (i % 17), days[i % 10], 'P' + (i % 9), ST[i % 4]);
  assert.ok(all.length >= 200 && all.length < 260, 'synthetic size ' + all.length);

  const byT = groupPostsByTicker(all);
  const byTD = groupPostsByTickerDay(all);
  const byA = groupPostsByAccount(all);
  const tickers = [...new Set(all.map(x => x.t))];
  const daySet = [...new Set(all.map(x => x.d))];
  const accs = [...new Set(all.map(x => x.acc))];

  for (const t of tickers) {
    const naive = all.filter(x => x.t === t);
    const idx = byT[t] || [];
    assert.equal(idx.length, naive.length, t);
    for (let i = 0; i < naive.length; i++) assert.equal(idx[i], naive[i]);
    for (const d of daySet) {
      const nCell = all.filter(x => x.t === t && x.d === d);
      const iCell = (byTD[t] && byTD[t][d]) || [];
      assert.deepEqual(cellOf(iCell), cellOf(nCell), t + ' ' + d);
    }
  }
  for (const a of accs) assert.equal((byA[a] || []).length, all.filter(x => x.acc === a).length, a);
  assert.deepEqual((byTD.NOPE && byTD.NOPE.D1) || [], all.filter(x => x.t === 'NOPE' && x.d === 'D1'));

  const hot = hotNames(all, byT);
  assert.deepEqual(hot.indexed, hot.naive);
  assert.ok(hot.indexed.includes('HOT1') && hot.indexed.includes('HOT2'));
  assert.ok(!hot.indexed.includes('COLDACC') && !hot.indexed.includes('COLDDAY'));

  const maxIndexed = Math.max(1, ...hot.indexed.flatMap(t => daySet.map(d => ((byTD[t] && byTD[t][d]) || []).length)));
  const maxNaive = Math.max(1, ...hot.naive.flatMap(t => daySet.map(d => all.filter(x => x.t === t && x.d === d).length)));
  assert.equal(maxIndexed, maxNaive);
  assert.ok(maxIndexed >= 5); // HOT1 day D1 has 5 posts
});

test('large heatmap index finishes well under a second', () => {
  const days = [];
  for (let d = 0; d < 28; d++) days.push('2026-10-' + String(d + 1).padStart(2, '0'));
  const posts = [];
  let ms = 0;
  const hotTickers = [];
  for (let t = 0; t < 300; t++) {
    const ticker = 'H' + t;
    hotTickers.push(ticker);
    for (let k = 0; k < 23; k++) {
      posts.push({
        t: ticker,
        d: days[k < 5 ? 0 : k],
        acc: 'A' + (k % 6),
        s: ST[k % 4],
        ms: ms++,
      });
    }
  }
  for (let t = 0; t < 13; t++) {
    for (let k = 0; k < 5; k++) {
      posts.push({ t: 'C' + t, d: days[k % 2], acc: 'A' + (k % 2), s: 'bull', ms: ms++ });
    }
  }
  assert.equal(posts.length, 6965);
  assert.equal(new Set(posts.map(x => x.t)).size, 313);

  const t0 = performance.now();
  const byT = groupPostsByTicker(posts);
  const byTD = groupPostsByTickerDay(posts);
  const hot = hotTickers.filter(t => {
    const ps = byT[t] || [];
    return new Set(ps.map(x => x.acc)).size >= 3 && new Set(ps.map(x => x.d)).size >= 3;
  });
  const lengths = hot.flatMap(t => days.map(d => ((byTD[t] && byTD[t][d]) || []).length));
  const maxHeat = Math.max(1, ...lengths);
  const msSpent = performance.now() - t0;

  assert.ok(msSpent < 1000, 'indexed heatmap took ' + msSpent.toFixed(1) + 'ms');
  assert.equal(hot.length, 300);
  assert.equal(maxHeat, 5);
  assert.equal(lengths.length, 300 * 28);
  assert.equal(lengths.reduce((a, b) => a + b, 0), 300 * 23);
  // Spot-check the crowded day against the naive scan. The timed section above did not do this.
  for (const t of hot) {
    assert.equal((byTD[t] && byTD[t][days[0]] || []).length, posts.filter(x => x.t === t && x.d === days[0]).length);
  }
  const cold = groupPostsByTicker(posts)['C0'] || [];
  assert.ok(new Set(cold.map(x => x.acc)).size < 3 || new Set(cold.map(x => x.d)).size < 3);
});

test('every homepage indexes the monthly heatmap and drops the nested day scan', () => {
  for (const rel of PAGES) {
    const src = fs.readFileSync(path.join(ROOT, rel), 'utf8');
    assert.match(src, /function groupPostsByTickerDay\(/);
    assert.match(src, /function groupPostsByTicker\(/);
    assert.match(src, /function groupPostsByAccount\(/);
    const vm = extractFn(src, 'viewMonthly');
    assert.match(vm, /const heatRows=/);
    assert.match(vm, /const maxHeat=/);
    assert.doesNotMatch(vm, /all\.filter\(x=>x\.t===r\.t&&x\.d===d\)/);
    assert.match(vm, /byT\[t\]\|\|\[\]/);
    assert.match(vm, /byA\[a\]\|\|\[\]/);
    assert.match(vm, /byTD\[r\.t\]&&byTD\[r\.t\]\[d\]/);
    if (rel === 'en/index.html') assert.match(vm, /posts, net bullish/);
    else assert.match(vm, /則，淨看多/);
  }
});
