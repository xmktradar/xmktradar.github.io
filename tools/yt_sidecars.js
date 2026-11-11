// YouTube Shorts title/desc sidecars for Tape Cats EN stems.
// Writes og/c/<day>-<show>-en-yt-title.txt and …-yt-desc.txt after a successful voiced mp4.
// Style mirrors tools/samples/2026-11-04-*-yt-*.txt (Tim 2026-11-05: never ship MP4-only).
'use strict';
const fs = require('fs');
const path = require('path');

const SHOW_LABELS = {
  'tape-take': 'Tape Take',
  'crowd-heat': 'Crowd Heat',
  'week-tape': 'Week Tape',
};

const UTM_HOME = 'https://thecrowdtape.com/en/?utm_source=youtube&utm_medium=social&utm_campaign=yt_shorts';
const UTM_CHECK = 'https://thecrowdtape.com/en/checklist/earnings/?utm_source=youtube&utm_medium=shorts&utm_campaign=yt_shorts_checklist';
const UTM_TOOLS = 'https://thecrowdtape.com/en/tools/?utm_source=youtube&utm_medium=shorts&utm_campaign=yt_shorts_tools';

function showIdOf(job, showMapFn) {
  if (job && job.show) return job.show;
  if (typeof showMapFn === 'function') {
    const m = showMapFn();
    if (job && m[job.slot]) return m[job.slot];
  }
  const def = { '1230': 'tape-take', '1630': 'crowd-heat', sat: 'week-tape', week: 'week-tape' };
  return (job && def[job.slot]) || 'tape-take';
}

function shortWindow(win) {
  const s = String(win || '').trim();
  if (!s) return '';
  // "11/3 21:10 – 11/5 01:19 HKT" → "11/3–11/5 HKT"
  const m = s.match(/(\d{1,2}\/\d{1,2}).*?[–-].*?(\d{1,2}\/\d{1,2}).*?(HKT|ET|EDT|EST)?/i);
  if (m) return `${m[1]}–${m[2]} ${m[3] || 'HKT'}`.trim();
  return s.length > 40 ? s.slice(0, 37) + '…' : s;
}

function cleanQuote(text) {
  let t = String(text || '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
  t = t.replace(/^["“]|["”]$/g, '').trim();
  // drop trailing ellipsis truncation markers from social captions
  t = t.replace(/\s*D…["”]?\s*$/i, '').replace(/\s*[….]{2,}\s*$/, '').trim();
  if (t.length > 220) t = t.slice(0, 217) + '…';
  return t;
}

function tagTicker(t) {
  const x = String(t || '').replace(/^\$/, '').toUpperCase();
  return x ? `$${x}` : '';
}

/** Build title + desc strings from a rendered job + words() payload (EN only). */
function buildYtCopy(job, W) {
  const showId = (W && W.showId) || showIdOf(job);
  const showLabel = (W && W.showLabel) || SHOW_LABELS[showId] || 'Tape Take';
  const open = (W && W.open) || {};
  const m1 = (W && W.m1) || {};
  const big = String(open.big || (W && W.big) || '').replace(/^\$/, '').toUpperCase();
  const tick = tagTicker(big);
  const handle = String(m1.handle || '').trim() || '@thecrowdtape';
  const quote = cleanQuote((m1.lines || []).join(' ') || m1.quote_text || '');
  const hook = String(open.hookQ || (tick
    ? `${tick} is the most discussed name on the tape today.`
    : `The most discussed name on the tape today.`)).trim();
  const n = Number(W && W.n) || 0;
  const bull = Number(W && W.bull) || 0;
  const bear = Number(W && W.bear) || 0;
  const win = shortWindow(open.date || (W && W.date) || '');
  const metrics = tick
    ? (n
      ? `${tick} · ${n} accounts · ${bull} bullish · ${bear} bearish`
      : `${tick} · ${bull} bullish · ${bear} bearish`)
    : `${bull} bullish · ${bear} bearish`;

  const titleBit = handle && handle !== '@thecrowdtape'
    ? `${handle} on the tape`
    : (showId === 'crowd-heat' ? 'bulls vs bears on the tape' : 'on the tape');
  const title = tick
    ? `${showLabel} · ${tick} — ${titleBit} 📊 #Shorts`
    : `${showLabel} — ${titleBit} 📊 #Shorts`;

  const hashTick = big ? `#${big}` : '';
  const lines = [
    hook,
    '',
    quote
      ? `On X, ${handle}: ${quote}`
      : `On X today — full quote on the tape.`,
    '',
    metrics,
    win ? `Data window: ${win}` : null,
    '',
    `Tape Cats · ${showLabel} (EN Short) — The Crowd Tape`,
    '(Based on public info, not investment advice)',
    '',
    ['#StockMarket', hashTick, '#Shorts', '#XTrading'].filter(Boolean).join(' '),
    '',
    `Live numbers 👉 ${UTM_HOME}`,
    '',
    `Free earnings checklist → ${UTM_CHECK}`,
    `Tools (affiliate / OptionStrat): ${UTM_TOOLS}`,
  ].filter(x => x !== null);

  return { title, desc: lines.join('\n') + '\n', showId, stemHint: null };
}

function pathsFor(job, videoStemFn) {
  const stem = typeof videoStemFn === 'function' ? videoStemFn(job) : `${job.date}-${showIdOf(job)}-${job.lang}`;
  return {
    stem,
    titlePath: path.join('og', 'c', `${stem}-yt-title.txt`),
    descPath: path.join('og', 'c', `${stem}-yt-desc.txt`),
  };
}

/** Write sidecars next to the mp4. Returns {titlePath, descPath} or null if skipped. */
function writeYtSidecars(job, W, opts = {}) {
  if (!job || job.lang !== 'en') return null;
  const { title, desc } = buildYtCopy(job, W);
  const { titlePath, descPath, stem } = pathsFor(job, opts.videoStem);
  fs.mkdirSync(path.dirname(titlePath), { recursive: true });
  fs.writeFileSync(titlePath, title.endsWith('\n') ? title : title + '\n', 'utf8');
  fs.writeFileSync(descPath, desc.endsWith('\n') ? desc : desc + '\n', 'utf8');
  if (opts.alsoSamples) {
    const sampleDir = path.join('tools', 'samples');
    fs.mkdirSync(sampleDir, { recursive: true });
    fs.writeFileSync(path.join(sampleDir, path.basename(titlePath)), title.endsWith('\n') ? title : title + '\n', 'utf8');
    fs.writeFileSync(path.join(sampleDir, path.basename(descPath)), desc.endsWith('\n') ? desc : desc + '\n', 'utf8');
  }
  console.log(`carousel yt ${titlePath}`);
  console.log(`carousel yt ${descPath}`);
  return { titlePath, descPath, stem, title, desc };
}

module.exports = {
  SHOW_LABELS, UTM_HOME, UTM_CHECK, UTM_TOOLS,
  showIdOf, shortWindow, cleanQuote, tagTicker,
  buildYtCopy, pathsFor, writeYtSidecars,
};
