// Hot-stock rank and sitemap mention filter. Pure functions, no page DOM.
// A mention is one distinct post (same id) that names the ticker.
// The window is closed at both ends: cutoffMs - days*24h <= post time <= cutoffMs.
// That is 7*24h (or 30*24h) before D.meta.cutoff_hkt / CUT, not a calendar-date span.
'use strict';

const DAY_MS = 864e5;
// 2026-11-01 patrol: $JOJO ranked #11 on 64 posts, nearly all @leadlagreport fund promo and disclosure
// boilerplate. Promo/disclosure posts do not count, and one account adds at most PER_ACC_CAP posts per ticker.
const PER_ACC_CAP = 5;
const PROMO_RE = new RegExp([
  'not investment advice\\.?\\s*$', 'past performance (?:does not|is no) guarantee', 'cannot be invested in directly',
  'backtested and hypothetical', 'is not an? affiliate of', 'learn more about the .{0,60}\\betf\\b',
  'carefully consider the (?:fund|investment)', 'read (?:it|the prospectus) carefully', 'sponsored\\b', '#ad\\b',
  'paid (?:promotion|partnership)', 'distributed by .{0,40}(?:foreside|distributors)',
].join('|'), 'i');

/** True for fund promo / disclosure boilerplate that should not count as a mention. */
function isPromo(text) {
  return typeof text === 'string' && PROMO_RE.test(text);
}

/**
 * Top tickers by distinct in-window posts.
 * @param {Array<{t:string, ms:number, id?:*, page?:boolean}>} rows
 *   One row per post × ticker. Rows with page === false have no stock page and are ignored.
 *   The same id on the same ticker counts once. Omit id to treat each row as its own post.
 * @param {number} cutoffMs
 * @param {number} days
 * @param {number} n  cap, e.g. 30
 * @returns {Array<{t:string, n:number}>} higher count first, then ticker A–Z
 */
function rankHot(rows, cutoffMs, days, n) {
  const cap = Number(n);
  if (!(cap > 0)) return [];
  const span = Number(days) * DAY_MS;
  const open = Number.isFinite(cutoffMs) && Number.isFinite(span) && span >= 0;
  const ids = new Map();
  const perAcc = new Map();
  const list = Array.isArray(rows) ? rows : [];
  for (let i = 0; i < list.length; i++) {
    const row = list[i];
    if (!row || row.page === false || row.promo || row.t == null || row.t === '') continue;
    const ms = row.ms;
    if (!open || typeof ms !== 'number' || !Number.isFinite(ms)) continue;
    if (ms < cutoffMs - span || ms > cutoffMs) continue;
    const t = String(row.t);
    const id = row.id != null ? row.id : '\0' + i;
    let set = ids.get(t);
    if (!set) ids.set(t, set = new Set());
    if (set.has(id)) continue;
    if (row.acc != null && row.acc !== '') {
      const k = t + '\0' + String(row.acc).toLowerCase();
      const c = perAcc.get(k) || 0;
      if (c >= PER_ACC_CAP) continue;
      perAcc.set(k, c + 1);
    }
    set.add(id);
  }
  const ranked = [];
  for (const [t, set] of ids) ranked.push({ t, n: set.size });
  ranked.sort((a, b) => b.n - a.n || (a.t < b.t ? -1 : a.t > b.t ? 1 : 0));
  return ranked.length > cap ? ranked.slice(0, cap) : ranked;
}

function addCount(best, t, c) {
  if (t == null || t === '') return;
  const num = typeof c === 'number' ? c : Number(c);
  if (!Number.isFinite(num)) return;
  const key = String(t);
  const prev = best.get(key);
  if (prev == null || num > prev) best.set(key, num);
}

/**
 * Tickers to keep in sitemap.xml. Fewer than `min` mentions (default 2) are left out.
 * @param {Record<string, number>|Map<string, number>|Array} counts30
 *   ticker → distinct posts in the 30-day window. Array items may be [ticker, count] or {t, n}.
 * @param {number} [min=2]
 * @returns {string[]} A–Z
 */
function sitemapTickers(counts30, min = 2) {
  const floor = min == null ? 2 : Number(min);
  const best = new Map();
  if (counts30 instanceof Map) {
    for (const [t, c] of counts30) addCount(best, t, c);
  } else if (Array.isArray(counts30)) {
    for (const item of counts30) {
      if (Array.isArray(item)) addCount(best, item[0], item[1]);
      else if (item && typeof item === 'object') addCount(best, item.t, item.n);
    }
  } else if (counts30 && typeof counts30 === 'object') {
    for (const t of Object.keys(counts30)) addCount(best, t, counts30[t]);
  }
  const out = [];
  for (const [t, c] of best) if (c >= floor) out.push(t);
  out.sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
  return out;
}

module.exports = { rankHot, sitemapTickers, isPromo, PROMO_SRC: PROMO_RE.source, PER_ACC_CAP, DAY_MS };
