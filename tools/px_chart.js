// Build-time inline SVG price chart for static stock pages (no JS, no external requests).
// Usage: const { buildPxChart, buildPxChartFromFile } = require('./px_chart.js');
'use strict';
const fs = require('fs');
const path = require('path');

const slug = t => String(t).replace(/[^A-Za-z0-9.\-]/g, '_');
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

function lastSixMonths(closes) {
  if (!Array.isArray(closes) || closes.length < 2) return [];
  const last = closes[closes.length - 1];
  const lastT = Date.parse(last && last[0]);
  if (!lastT) return [];
  const cut = lastT - 183 * 864e5;
  const out = closes.filter(r => Array.isArray(r) && r.length >= 2 && typeof r[1] === 'number' && Date.parse(r[0]) >= cut);
  return out.length >= 2 ? out : [];
}

function fmtPx(v) {
  if (v >= 1000) return v.toLocaleString('en-US', { maximumFractionDigits: 2 });
  if (Number.isInteger(v)) return String(v);
  return (Math.round(v * 100) / 100).toFixed(2).replace(/\.?0+$/, '') || String(v);
}

function md(d) {
  const m = String(d).match(/(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${+m[2]}/${+m[3]}` : String(d);
}

function buildPxChart(closes, ticker, caption, aria) {
  const pts = lastSixMonths(closes);
  if (pts.length < 2) return '';
  const W = 640, H = 200, L = 52, R = 56, T = 18, B = 28;
  const ys = pts.map(p => p[1]);
  const min = Math.min(...ys), max = Math.max(...ys);
  const last = pts[pts.length - 1][1];
  const span = (max - min) || 1;
  const sx = i => L + i / (pts.length - 1) * (W - L - R);
  const sy = v => T + (1 - (v - min) / span) * (H - T - B);
  const line = pts.map((p, i) => `${sx(i).toFixed(1)},${sy(p[1]).toFixed(1)}`).join(' ');
  const lastX = sx(pts.length - 1), lastY = sy(last);
  const minY = sy(min), maxY = sy(max);
  const up = last >= pts[0][1];
  const col = up ? 'var(--bull,#1a7f37)' : 'var(--bear,#b42318)';
  const d0 = pts[0][0], d1 = pts[pts.length - 1][0];
  const maxLabY = Math.max(12, maxY + 4);
  const minLabY = Math.min(H - B - 2, minY + 4);
  return `<section class="c12 panel px-sec"><svg class="px-chart" viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc(aria || ticker)}" preserveAspectRatio="xMidYMid meet" overflow="hidden">`
    + `<polygon points="${sx(0).toFixed(1)},${(H - B).toFixed(1)} ${line} ${lastX.toFixed(1)},${(H - B).toFixed(1)}" fill="${col}" opacity="0.1"/>`
    + `<polyline points="${line}" fill="none" stroke="${col}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`
    + `<text x="4" y="${maxLabY.toFixed(1)}">${esc(fmtPx(max))}</text>`
    + `<text x="4" y="${minLabY.toFixed(1)}">${esc(fmtPx(min))}</text>`
    + `<text x="${(Math.min(lastX + 4, W - R)).toFixed(1)}" y="${(lastY + 4).toFixed(1)}">${esc(fmtPx(last))}</text>`
    + `<text x="${L}" y="${H - 6}">${esc(md(d0))}</text>`
    + `<text x="${W - 8}" y="${H - 6}" text-anchor="end">${esc(md(d1))}</text>`
    + `</svg>${caption ? `<p class="note px-cap">${esc(caption)}</p>` : ''}</section>`;
}

function buildPxChartFromFile(root, ticker, caption, aria) {
  const file = path.join(root, 'px', slug(ticker) + '.json');
  if (!fs.existsSync(file)) return '';
  let data;
  try { data = JSON.parse(fs.readFileSync(file, 'utf8')); } catch (e) { return ''; }
  return buildPxChart(data && data.c, ticker, caption, aria);
}

module.exports = { buildPxChart, buildPxChartFromFile, lastSixMonths, slug, fmtPx };
