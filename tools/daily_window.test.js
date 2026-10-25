// Tests for the daily comparison window: prior end = current end minus 24h.
const test = require('node:test'), assert = require('node:assert');
const fs = require('fs'), path = require('path');
const src = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const m = src.match(/\/\*DAILY-WIN\*\/([\s\S]*?)\/\*DAILY-WIN-END\*\//);
assert.ok(m, 'DAILY-WIN block missing from index.html');
const F = new Function(m[1] + ';return {clipDailyRange,priorDailyRange,rangeSrcNote};')();

test('prior window end is current end minus 24h (timed)', () => {
  const p = F.priorDailyRange('2026-10-25T00:00', '2026-10-25T09:15');
  assert.equal(p.pf, '2026-10-24T00:00');
  assert.equal(p.pt, '2026-10-24T09:15');
});

test('writer 23:59 clips to cutoff, prior is same hours yesterday', () => {
  const c = F.clipDailyRange('2026-10-25T00:00', '2026-10-25T23:59', Date.parse('2026-10-25T09:15:41+08:00'));
  assert.equal(c.from, '2026-10-25T00:00');
  assert.equal(c.to, '2026-10-25T09:15');
  const p = F.priorDailyRange(c.from, c.to);
  assert.equal(p.pf, '2026-10-24T00:00');
  assert.equal(p.pt, '2026-10-24T09:15');
});

test('date-only window clips to cutoff then prior is minus 24h', () => {
  const c = F.clipDailyRange('2026-10-25', '2026-10-25', Date.parse('2026-10-25T11:05:00+08:00'));
  assert.equal(c.from, '2026-10-25T00:00');
  assert.equal(c.to, '2026-10-25T11:05');
  const p = F.priorDailyRange(c.from, c.to);
  assert.equal(p.pt, '2026-10-24T11:05');
});

test('viewDaily uses priorDailyRange (same hours yesterday)', () => {
  assert.match(src, /priorDailyRange\(w\.from,w\.to\)/);
  assert.doesNotMatch(src, /pt=addDays\(w\.from,-1\)/);
});

test('range label says the windows match only when the brief end equals the window end', () => {
  assert.equal(F.rangeSrcNote('writer', '09:15', '09:15'), '與今日市場分析相同');
  assert.equal(F.rangeSrcNote('writer', '09:15', '11:00'), '今日市場分析截至 09:15 HKT，本頁統計至 11:00 HKT');
  assert.equal(F.rangeSrcNote('cycle', '09:15', '11:00'), '今個抓帖周期');
  assert.equal(F.rangeSrcNote('writer', '', '11:00'), '與今日市場分析相同');
  assert.equal(F.rangeSrcNote('writer', '09:15', ''), '與今日市場分析相同');
  assert.match(src, /rangeSrcNote\(w\.src,briefAsOf\(w,sm\),w\.to&&w\.to\.length>10\?w\.to\.slice\(11,16\):''\)/);
  assert.doesNotMatch(src, /w\.src==='writer'\?'與今日市場分析相同'/);
});

test('briefAsOf end feeds the range label (highlights range, else writer window)', () => {
  const fn = src.match(/function briefAsOf\(w,sm\)\{[\s\S]*?return ''\}/);
  assert.ok(fn, 'briefAsOf missing');
  const briefAsOf = new Function('D', fn[0] + '\nreturn briefAsOf;');
  const early = briefAsOf({ highlights: { '2026-10-25': { range: '10/25 00:00 – 10/25 9:05 HKT' } } });
  assert.equal(early({ day: '2026-10-25' }, null), '09:05');
  assert.equal(F.rangeSrcNote('writer', early({ day: '2026-10-25' }, null), '11:00'), '今日市場分析截至 09:05 HKT，本頁統計至 11:00 HKT');
  const same = briefAsOf({ highlights: { '2026-10-25': { range: '00:00–11:00' } } });
  assert.equal(F.rangeSrcNote('writer', same({ day: '2026-10-25' }, null), '11:00'), '與今日市場分析相同');
  const fallback = briefAsOf({ highlights: {} });
  assert.equal(fallback({ day: '2026-10-25' }, { s: { win: { to: '2026-10-25T11:00' } } }), '11:00');
  assert.equal(fallback({ day: '2026-10-25' }, { s: { win: { to: '2026-10-25T23:59' } } }), '');
});
