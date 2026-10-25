// Tests for the daily comparison window: prior end = current end minus 24h.
const test = require('node:test'), assert = require('node:assert');
const fs = require('fs'), path = require('path');
const src = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const m = src.match(/\/\*DAILY-WIN\*\/([\s\S]*?)\/\*DAILY-WIN-END\*\//);
assert.ok(m, 'DAILY-WIN block missing from index.html');
const F = new Function(m[1] + ';return {clipDailyRange,priorDailyRange};')();

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
