// Analysis as-of label, streak chip, and single-escape number highlighting.
const test = require('node:test'), assert = require('node:assert');
const fs = require('fs'), path = require('path');
const src = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const block = src.match(/\/\*ANALYSIS-LABEL\*\/([\s\S]*?)\/\*ANALYSIS-LABEL-END\*\//);
assert.ok(block, 'ANALYSIS-LABEL block missing from index.html');
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = d => `${+d.slice(5, 7)}/${+d.slice(8, 10)}`;

function load(lang, env) {
  const fn = new Function('PAGE_LANG', 'D', 'fmt', 'summaryOf', 'briefAsOf', 'esc', 'TODAY',
    block[1] + '\nreturn {storedPostCount,unanalyzedCount,analysisClock,analysisTag,analysisLead,streakMark,numHi};');
  return fn(lang, env.D, fmt, env.summaryOf, env.briefAsOf, esc, env.TODAY);
}

function envFor(note, brief, warnings, to) {
  const D = {
    highlights: { '2026-10-26': { stats_note: note } },
    meta: { warnings: warnings || [] },
    summaries: { daily: [{ date: '2026-10-26', brief: brief || '', win: to ? { to } : null }] },
  };
  const summaryOf = (kind, date) => {
    const arr = (D.summaries && D.summaries[kind]) || [];
    if (date) {
      const m = arr.filter(x => x.date === date);
      if (m.length) return { s: m[m.length - 1], stale: false };
    }
    return arr.length ? { s: arr[arr.length - 1], stale: !!date } : null;
  };
  return { D, summaryOf, briefAsOf: () => '', TODAY: '2026-10-26' };
}

const ZH = '這段時間213帖、62帳號，看好120對看淡20';
const EN = 'Window of 213 posts, 62 accounts, 120 bullish vs 20 bearish';
const WARN = ['未分析：106 則新帖等待 Grok 分析'];

test('stored post count is the writeup figure, not the live card total', () => {
  const api = load('en', envFor(EN));
  assert.equal(api.storedPostCount(EN, ''), 213);
  assert.equal(api.storedPostCount(ZH, ''), 213);
  assert.equal(api.storedPostCount('', '<p>這段時間213則帖文來自62個帳號</p>'), 213);
  assert.equal(api.storedPostCount('no count here', '<p>no count</p>'), null);
});

test('unanalyzed count is parsed from the stored warning', () => {
  const api = load('en', envFor(EN));
  assert.equal(api.unanalyzedCount(WARN), 106);
  assert.equal(api.unanalyzedCount(['未分析: 106 則']), 106);
  assert.equal(api.unanalyzedCount([]), 0);
  assert.equal(api.unanalyzedCount(null), 0);
  assert.match(block[1], /未分析\[\^\\d\]\{0,6\}\(\\d\+\)/);
  assert.doesNotMatch(block[1], /未分析：/);
});

test('analysis tag names the writeup clock, coverage, and gap', () => {
  const api = load('zh-Hant', envFor(ZH));
  assert.equal(api.analysisTag('10/26 06:54', 213, 106), '分析截至 10/26 06:54 HKT · 涵蓋 213 則 · 未分析 106 則');
  assert.equal(load('en', envFor(EN)).analysisTag('10/26 06:54', 213, 106), 'Analysis as of 10/26 06:54 HKT · covers 213 posts · 106 not yet analyzed');
  assert.equal(api.analysisTag('10/26 06:54', null, 0), '分析截至 10/26 06:54 HKT');
  assert.equal(api.analysisTag('', 213, 106), '');
});

test('analysis lead uses the writer window end and today gap only', () => {
  const en = load('en', envFor(EN, '<p>213 posts from 62 accounts</p>', WARN, '2026-10-26T06:54'));
  assert.equal(en.analysisLead('2026-10-26'), 'Analysis as of 10/26 06:54 HKT · covers 213 posts · 106 not yet analyzed');
  assert.equal(en.analysisLead('2026-10-25'), 'Analysis as of 10/26 06:54 HKT · covers 213 posts');
  const zh = load('zh-Hant', envFor(ZH, '', WARN, '2026-10-26T06:54'));
  assert.equal(zh.analysisLead('2026-10-26'), '分析截至 10/26 06:54 HKT · 涵蓋 213 則 · 未分析 106 則');
  const late = envFor(EN, '', [], '2026-10-26T23:59');
  late.briefAsOf = () => '';
  assert.equal(load('en', late).analysisClock('2026-10-26'), '');
});

test('streak mark keeps the day count off the ticker', () => {
  assert.equal(load('en', envFor(EN)).streakMark(2), '(2 days)');
  assert.equal(load('en', envFor(EN)).streakMark(1), '(1 day)');
  assert.equal(load('zh-Hant', envFor(ZH)).streakMark(2), '（2 日）');
  assert.match(src, /streakMark\(n\)/);
  assert.doesNotMatch(src, /\$\{n\}<\/b>/);
});

test('numHi escapes apostrophes once and still highlights numbers', () => {
  const api = load('en', envFor(EN));
  assert.equal(api.numHi("Elon's 13 GW"), 'Elon&#39;s <em>13</em> GW');
  assert.equal(api.numHi('Elon&#39;s 13 GW'), 'Elon&#39;s <em>13</em> GW');
  assert.equal(api.numHi("couldn't clear $40"), 'couldn&#39;t clear <em>$40</em>');
  const xss = api.numHi('<script>alert(1)</script> 13');
  assert.equal(xss, '&lt;script&gt;alert(<em>1</em>)&lt;/script&gt; <em>13</em>');
  assert.doesNotMatch(xss, /<script>/);
  assert.doesNotMatch(api.numHi("Elon's"), /<em>39<\/em>/);
});

test('summary and highlights are stamped with the analysis lead', () => {
  assert.match(src, /analysisLead\(w\.day,sm\)/);
  assert.match(src, /const lead=analysisLead\(date\)/);
  assert.doesNotMatch(src, /as of \$\{esc\(bx\)\} HKT/);
});

test('macro names have English translations', () => {
  const py = fs.readFileSync(path.join(__dirname, 'update_prices.py'), 'utf8');
  const body = py.match(/EVENT_ZH = \{([\s\S]*?)\n\}/);
  assert.ok(body, 'EVENT_ZH missing');
  const names = [...body[1].matchAll(/: '([^']+)'/g)].map(m => m[1]);
  assert.ok(names.length >= 30);
  const en = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'i18n', 'en.json'), 'utf8')).data;
  for (const name of names) {
    assert.equal(typeof en[name], 'string', name);
    assert.doesNotMatch(en[name], /[\u4e00-\u9fff가-힣]/, name);
  }
});
