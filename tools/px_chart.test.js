// Tests for the build-time inline SVG price chart used on static stock pages.
const test = require('node:test'), assert = require('node:assert');
const fs = require('fs'), path = require('path');
const { buildPxChart, buildPxChartFromFile, lastSixMonths } = require('./px_chart.js');

const ROOT = path.join(__dirname, '..');

test('buildPxChart emits svg.px-chart with min/max/last and dates', () => {
  const closes = [];
  const start = Date.parse('2026-04-01');
  for (let i = 0; i < 90; i++) {
    const d = new Date(start + i * 864e5).toISOString().slice(0, 10);
    closes.push([d, 100 + i]);
  }
  const html = buildPxChart(closes, 'NVDA', 'Daily close, last ~6 months.', '$NVDA closing price');
  assert.match(html, /<svg class="px-chart"/);
  assert.match(html, /viewBox="0 0 640 200"/);
  assert.match(html, /width="100%"/);
  assert.match(html, />189</); // last close 100+89
  assert.match(html, /class="note px-cap"/);
  assert.ok(!html.includes('http://') && !html.includes('https://'));
});

test('lastSixMonths keeps about 6 months', () => {
  const closes = [
    ['2025-01-02', 10],
    ['2026-05-01', 50],
    ['2026-10-01', 80],
    ['2026-10-23', 90],
  ];
  const pts = lastSixMonths(closes);
  assert.equal(pts[0][0], '2026-05-01');
  assert.equal(pts[pts.length - 1][1], 90);
});

test('missing or short series omitted', () => {
  assert.equal(buildPxChart([], 'X', 'cap', 'aria'), '');
  assert.equal(buildPxChart([['2026-10-01', 1]], 'X', 'cap', 'aria'), '');
  assert.equal(buildPxChartFromFile(ROOT, '__no_such_ticker__', 'cap', 'aria'), '');
});

test('NVDA px file yields a chart; generated page has svg.px-chart when present', () => {
  const html = buildPxChartFromFile(ROOT, 'NVDA', 'cap', '$NVDA');
  assert.match(html, /<svg class="px-chart"/);
  const page = path.join(ROOT, 'en', 'stock', 'NVDA', 'index.html');
  if (fs.existsSync(page) && html) {
    const body = fs.readFileSync(page, 'utf8');
    if (body.includes('class="px-chart"') || body.includes('<!--px-chart:')) {
      assert.match(body, /<svg class="px-chart"/);
    }
  }
});
