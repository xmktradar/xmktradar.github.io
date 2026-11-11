// Motion videos from the daily multi-picture posts (v6.1 Tape Cats pose-only: cream BG + PNG cats + real X quote).
// Usage: node tools/carousel_video.js work/carousel.json   (after tools/carousel.js, from the repo root)
// For each job whose slot is in VIDEO_SLOTS (default 1230) and language in VIDEO_LANGS (default en) it writes og/c/<day>-<slot>-<lang>.mp4:
// 1080x1920, H.264 limited yuv420p + AAC +faststart. Cover is merged into the open scene: frame 0 already
// shows $TICKER + the discussion count. Soft cuts (open, split, m1, m2, cta) — cream + cat poses; mouth stub reserved;
// no emoji / confetti / shake / white-flash / comic. VO from tools/carousel_vo.py is required; skip the language
// if VO is missing or the voiced cut exceeds the cap (40s weekday / Saturday single; 75s Week Tape hot-list).
// Sidecar og/c/<day>-<slot>-<lang>.vo.json after mix.
// Optional caption sidecars (not a YouTube upload): og/c/<day>-<show>-en-yt-title.txt + …-yt-desc.txt.
// New videos are X-native. YouTube upload is blocked; the channel is not deleted.
// Tim 2026-11-04: default VIDEO_LANGS=en (no daily *-zh.mp4). Override with VIDEO_LANGS=zh,en if needed.
// v3: words() fills hookQ + m1 quote (handle/lines) from writeups/highlights; empty → legacy #278 rows.
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const FPS = 24, BPM = 124, BEAT = 60 / BPM;
// Keep in sync with BASE_BEATS / COVER_FRAMES in tools/carousel_vo.py.
const BASE = [['open', 6], ['split', 20], ['m1', 13], ['m2', 20], ['cta', 14]];
const COVER_FRAMES = 0; // cover merged into open; frame 0 of open is also written as *-cover.jpg
const COVER = COVER_FRAMES / FPS;
const MIN_VIDEO_S = 30;
const MAX_VIDEO_S = 40;
const WEEK_MAX_VIDEO_S = 75; // Saturday hot-list ~60s; a little over is ok. Not the 40s fail.
const VOICES = { zh: 'zh-CN-XiaoxiaoNeural', en: 'en-US-AndrewNeural' };
const SLOTS = (process.env.VIDEO_SLOTS || '1230,1630').split(',').filter(Boolean);
const LANGS = (process.env.VIDEO_LANGS || 'en').split(',').filter(Boolean);
const TOOLS = __dirname;
const { writeYtSidecars } = require('./yt_sidecars');
// Stable stems for the X-native short (same mp4). Docs: MOTION_VIDEO.md § Tape Cats paths.
// Slot codes → show id. Override with VIDEO_SHOW_MAP=1230:tape-take,1630:crowd-heat,sat:week-tape
const DEFAULT_SHOW = { '1230': 'tape-take', '1630': 'crowd-heat', 'sat': 'week-tape', 'week': 'week-tape' };
function showMap() {
  const m = { ...DEFAULT_SHOW };
  for (const pair of String(process.env.VIDEO_SHOW_MAP || '').split(',').filter(Boolean)) {
    const [k, v] = pair.split(':');
    if (k && v) m[k.trim()] = v.trim();
  }
  return m;
}
/** og/c/<day>-<show>-<lang>.mp4 — stable for bots. */
function videoStem(job) {
  const show = (job && job.show) || showMap()[job && job.slot] || (job && job.slot) || 'tape-take';
  return `${job.date}-${show}-${job.lang}`;
}
function videoOut(job) { return `og/c/${videoStem(job)}.mp4`; }
function coverOut(job) { return `og/c/${videoStem(job)}-cover.jpg`; }


function voiceName(lang) {
  return process.env['VO_VOICE_' + lang] || VOICES[lang] || lang;
}

function voMarkerPath(outFile) {
  return outFile.replace(/\.mp4$/i, '.vo.json');
}

function videoCap(job) {
  if (!job) return MAX_VIDEO_S;
  if (job.mode === 'hot-list') return WEEK_MAX_VIDEO_S;
  const beats = job.beats || [];
  if (beats.filter(b => b && b.role === 'heat').length > 1) return WEEK_MAX_VIDEO_S;
  return MAX_VIDEO_S;
}

function sceneBases(vo, job) {
  const beats = (job && job.beats) || [];
  const n = Math.max(beats.length, (vo && vo.length) || 0, beats.length ? 0 : BASE.length);
  const out = [];
  for (let i = 0; i < n; i++) {
    const fromVo = vo && vo[i] && typeof vo[i].base === 'number' ? vo[i].base : null;
    const fromBeat = beats[i] && typeof beats[i].base === 'number' ? beats[i].base : null;
    const fromBase = BASE[i] ? BASE[i][1] : 8;
    out.push(fromVo != null ? fromVo : (fromBeat != null ? fromBeat : fromBase));
  }
  return out;
}

function voicedTotal(vo, job) {
  const bases = sceneBases(vo, job);
  const n = Math.min(bases.length, vo ? vo.length : 0);
  let acc = 0;
  for (let i = 0; i < n; i++) acc += Math.max(bases[i], Math.ceil((vo[i].dur + 0.4) / BEAT)) * BEAT;
  return acc + COVER;
}

function voiceoverSkip(vo, exists, job) {
  // voiceoverSkip(vo) and voiceoverSkip(vo, existsFn) stay valid. A non-function
  // second arg is the job (older call sites pass nothing).
  if (typeof exists !== 'function') {
    job = exists;
    exists = p => fs.existsSync(p);
  }
  const need = (job && job.beats && job.beats.length) ? job.beats.length : BASE.length;
  if (!Array.isArray(vo) || vo.length < need) return 'no voiceover';
  for (let i = 0; i < need; i++) {
    const v = vo[i];
    if (!v || typeof v.dur !== 'number' || !v.file || !exists(v.file)) return 'voiceover audio missing';
  }
  const total = voicedTotal(vo, job);
  const cap = videoCap(job);
  if (total > cap) return `voiced ${total.toFixed(2)}s > ${cap}`;
  return null;
}

function removePartial(outFile) {
  for (const p of [outFile + '.part.mp4']) {
    try { fs.unlinkSync(p); } catch (_) {}
  }
}

function writeSkip(job) {
  const stem = videoStem(job || {});
  const og = path.join('og', 'c');
  fs.mkdirSync(og, { recursive: true });
  const signal = (job && job.signal) || {};
  const payload = {
    publishable: false,
    reason: signal.reason || (job && job.reason) || 'no_heat',
    detail: signal.detail || (job && job.detail) || '',
    slot: job && job.slot,
    show: (job && job.show) || showMap()[job && job.slot] || (job && job.slot) || 'tape-take',
    date: job && job.date,
    lang: (job && job.lang) || 'en',
  };
  const skipPath = path.join(og, `${stem}.skip.json`);
  if (!fs.existsSync(skipPath)) fs.writeFileSync(skipPath, JSON.stringify(payload, null, 2) + '\n');
  for (const extra of ['.mp4', '.part.mp4', '-cover.jpg', '.vo.json', '-yt-title.txt', '-yt-desc.txt']) {
    try { fs.unlinkSync(path.join(og, stem + extra)); } catch (_) {}
  }
  const msg = `${payload.show} ${payload.date} skipped: ${payload.reason} — ${payload.detail}`;
  console.log(`::notice::${msg}`);
  console.log(`::warning::${msg}`);
  return skipPath;
}

function isVideoSkip(job) {
  if (!job) return false;
  const signal = job.signal || {};
  return !!(job.video_skip || job.skip || job.publishable === false || signal.publishable === false);
}

function refuseVideo(job, outFile, why) {
  removePartial(outFile);
  const who = job && job.slot ? `${job.slot} ${job.lang}` : outFile;
  console.log(`::warning::${who} 動態片唔出：${why}`);
  return why;
}

function writeVoMarker(outFile, job, total) {
  fs.writeFileSync(voMarkerPath(outFile), JSON.stringify({
    voice: voiceName(job.lang), duration: Math.round(total * 1000) / 1000, vo: true,
  }));
}

const num = (s, d = 0) => { const m = String(s || '').match(/\d+/); return m ? +m[0] : d; };

/** Bull/bear from pills, or duel `bar: [nb, nr]`, or `nb`/`nr`, or a versus subtitle. */
function stanceFrom(S0) {
  const cover = S0 || {};
  const pills = cover.pills || [];
  const g = pills.find(p => p && p.c === 'g');
  const r = pills.find(p => p && p.c === 'r');
  let bull = g ? num(g.x) : 0;
  let bear = r ? num(r.x) : 0;
  const bar = cover.bar;
  if (Array.isArray(bar) && bar.length >= 2) {
    if (!g) bull = +bar[0] || 0;
    if (!r) bear = +bar[1] || 0;
  } else if (!g && !r) {
    if (cover.nb != null || cover.nr != null) {
      bull = +cover.nb || 0;
      bear = +cover.nr || 0;
    } else {
      const sub = String(cover.sub || '');
      let m = sub.match(/(\d+)\s*(?:bull\w*|好).*?(\d+)\s*(?:bear\w*|淡|空)/i);
      if (!m) m = sub.match(/(\d+)\s*vs\s*(\d+)/i);
      if (m) { bull = +m[1]; bear = +m[2]; }
    }
  }
  return { n: num(cover.sub), bull, bear };
}

function firstCards(slide, mark) {
  const out = [];
  for (const sec of (slide && slide.secs) || []) {
    if (mark == null || String(sec.h || '').startsWith(mark)) {
      for (const c of sec.cards || []) if (c && c.t) out.push(c);
    }
  }
  return out;
}

function pillCount(card, color) {
  const p = (card.pills || []).find(x => x && x.c === color);
  return p ? num(p.x) : 0;
}

/** Load today's real X hero quote from writeups/highlights (never invent). */
function readJson(p) {
  try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch (_) { return null; }
}

function splitQuoteLines(text, max = 3) {
  let t = String(text || '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
  if (!t) return [];
  t = t.replace(/^@[\w.]+\s*[:：]\s*/, '');
  let parts = t.split(/\s*[;；]\s*/).map(x => x.trim()).filter(Boolean);
  if (parts.length < 2) parts = t.split(/(?<=[.!?])\s+/).map(x => x.trim()).filter(Boolean);
  if (parts.length < 2) parts = [t];
  return parts.slice(0, max).map(x => (x.length > 96 ? x.slice(0, 93) + '…' : x));
}

function parsePoint(point) {
  const s = String(point || '').trim();
  const m = s.match(/^@([\w.]+)\s*[:：]\s*([\s\S]+)$/);
  if (m) return { handle: '@' + m[1], text: m[2].trim() };
  return null;
}

/** Prefer highlight point matching ticker; else first usable EN point. */
function loadHeroQuote(big) {
  const root = path.join(TOOLS, '..');
  const files = [
    path.join(root, 'data/super-grok-writeups.json'),
    path.join(root, 'work/writeups.json'),
  ];
  let data = null;
  for (const f of files) { data = readJson(f); if (data) break; }
  if (!data) return null;
  const en = data.en || data;
  const cards = (((en.highlights || {}).cards) || []);
  const want = String(big || '').toUpperCase();
  const ordered = [
    ...cards.filter(c => (c.tickers || []).map(t => String(t).toUpperCase()).includes(want)),
    ...cards,
  ];
  function pack(card, parsed, tick) {
    const lines = splitQuoteLines(parsed.text, 3);
    if (!lines.length) return null;
    const stance = /bear|看空|淡/i.test(String(card.tone || '')) ? 'bear'
      : /bull|看好|多/i.test(String(card.tone || '')) ? 'bull' : '';
    const postsNote = (card.big && card.big.value) ? `${card.big.value} ${card.big.label || ''}`.trim() : '';
    const use = tick || want || ((card.tickers || [])[0] || '');
    return {
      hook_q: use
        ? `${use} is the most discussed name on the tape today.`
        : `The most discussed name on the tape today.`,
      quote_handle: parsed.handle,
      quote_text: lines.join(' '),
      lines,
      stance,
      ticker: use,
      punch: postsNote
        ? `One voice. ${postsNote}.`
        : 'One voice. Full quotes on the tape today.',
      source: 'data/super-grok-writeups.json en.highlights',
    };
  }
  // 1) point that names the hero ticker
  if (want) {
    for (const card of ordered) {
      for (const pt of (card.points || [])) {
        if (!new RegExp('\\b' + want + '\\b', 'i').test(pt)) continue;
        const parsed = parsePoint(pt);
        if (!parsed) continue;
        const got = pack(card, parsed, want);
        if (got) return got;
      }
    }
  }
  // 2) card tagged with hero ticker — first point
  if (want) {
    for (const card of ordered) {
      const tags = (card.tickers || []).map(t => String(t).toUpperCase());
      if (!tags.includes(want)) continue;
      for (const pt of (card.points || [])) {
        const parsed = parsePoint(pt);
        if (!parsed) continue;
        const got = pack(card, parsed, want);
        if (got) return got;
      }
    }
    return null; // never invent; don't steal another ticker's quote
  }
  // 3) no hero ticker asked — first usable point of the day
  for (const card of cards) {
    for (const pt of (card.points || [])) {
      const parsed = parsePoint(pt);
      if (!parsed) continue;
      const got = pack(card, parsed, ((card.tickers || [])[0] || ''));
      if (got) return got;
    }
  }
  // Fallback: writeup-input bull/bear rows (zh why → skip unless we only need handle; prefer highlights)
  const wi = readJson(path.join(root, 'data/writeup-input.json'));
  const daily = wi && wi.daily;
  if (daily) {
    for (const bucket of ['bull', 'bear', 'split']) {
      for (const block of (daily[bucket] || [])) {
        if (want && String(block.t || '').toUpperCase() !== want) continue;
        const row = (block.rows || [])[0];
        if (!row || !row.acc) continue;
        // EN highlights missing — do not invent English from zh why
        return null;
      }
    }
  }
  return null;
}

const SHOW_LABELS = {
  'tape-take': 'Tape Take',
  'crowd-heat': 'Crowd Heat',
  'week-tape': 'Week Tape',
};

/** Scene copy — numbers/tickers from job slides; EN quote from day writeups. Zero emoji. */
function words(lang, slides, job) {
  const showId = (job && job.show) || showMap()[(job && job.slot)] || (job && job.slot) || 'tape-take';
  const showLabel = SHOW_LABELS[showId] || SHOW_LABELS[String(showId).toLowerCase()] || 'Tape Take';
  const S0 = slides[0] || {};
  const stance = stanceFrom(S0);
  const n = stance.n, bull = stance.bull, bear = stance.bear;
  const big = S0.big || '';
  const top = firstCards(slides[1]).slice(0, 4);
  const up = firstCards(slides[2], '🟢').slice(0, 3);
  const down = firstCards(slides[2], '🔴').slice(0, 3);
  const split = firstCards(slides[3]).slice(0, 3);
  const zh = lang === 'zh';
  const verdict = bull > bear ? (zh ? '多方領先' : 'Bulls ahead')
    : bear > bull ? (zh ? '空方領先' : 'Bears ahead')
    : (zh ? '打平' : "It's a tie");
  const open = {
    lead: zh ? '最多人討論' : 'Most discussed',
    big,
    metric: zh ? `${n} 個帳號` : `${n} accounts`,
    ctx: zh
      ? `${bull} 個看好 · ${bear} 個看空`
      : `${bull} bullish · ${bear} bearish`,
    date: S0.win || '',
  };
  const splitD = {
    bull, bear, verdict,
    bullL: zh ? '看好' : 'Bulls',
    bearL: zh ? '看空' : 'Bears',
    bullSub: zh ? '個帳號' : 'accounts',
    bearSub: zh ? '個帳號' : 'accounts',
    date: S0.win || '',
  };
  const m1 = {
    title: zh ? '熱度 Top 4' : 'Top 4 discussed',
    date: S0.win || '',
    rows: top.map(c => ({
      t: c.t,
      v: zh
        ? `${pillCount(c, 'g')} 看好 · ${pillCount(c, 'r')} 看空`
        : `${pillCount(c, 'g')} up · ${pillCount(c, 'r')} down`,
      tone: pillCount(c, 'g') >= pillCount(c, 'r') ? 'up' : 'down',
    })),
  };
  const jointRows = [
    ...up.map(c => ({ t: c.t, v: zh ? `${pillCount(c, 'g')} 共同看好` : `${pillCount(c, 'g')} joint bull`, tone: 'up' })),
    ...down.map(c => ({ t: c.t, v: zh ? `${pillCount(c, 'r')} 共同看空` : `${pillCount(c, 'r')} joint bear`, tone: 'down' })),
  ];
  const splitRows = split.map(c => ({
    t: c.t,
    v: zh
      ? `${pillCount(c, 'g')} 看好 · ${pillCount(c, 'r')} 看空`
      : `${pillCount(c, 'g')} up · ${pillCount(c, 'r')} down`,
    tone: 'amber',
  }));
  const m2 = jointRows.length
    ? { title: zh ? '共同看好／看空' : 'Where they agree', date: S0.win || '', rows: jointRows.slice(0, 4) }
    : { title: zh ? '好淡分歧' : 'Biggest split', date: S0.win || '', rows: splitRows.slice(0, 4) };
  const cta = {
    foot: zh ? '免費 · 無需登入 · 每 8 小時更新 · 不構成投資建議' : 'Free · No login · Every 8h · Not investment advice',
    date: S0.win || '',
    t: zh ? ['詳情看 thecrowdtape.com', '@thecrowdtape'] : ['Full tape, free.', 'thecrowdtape.com', '@thecrowdtape'],
  };
  // EN: hook + discussion CTA from the three-beat script. No site URL, no invented quote.
  if (!zh) {
    const beats = (job && job.beats) || [];
    const hookBeat = beats.find(b => b && b.role === 'hook') || null;
    const ctaBeat = [...beats].reverse().find(b => b && b.role === 'cta') || null;
    const tick = String((hookBeat && hookBeat.visual && hookBeat.visual.big) || big || '').replace(/^\$/, '');
    if (tick) open.big = tick;
    open.hideChrome = true;
    open.hookQ = (hookBeat && hookBeat.vo) || (tick
      ? `${tick} is the most discussed name on the tape today.`
      : 'The most discussed name on the tape today.');
    open.caption = (hookBeat && hookBeat.caption) || 'Most discussed name';
    cta.discussion = true;
    cta.line = (ctaBeat && ctaBeat.vo) || (tick ? `Bull or bear on ${tick}?` : 'Bull or bear?');
    cta.caption = 'Bull or bear?';
    cta.t = [cta.caption];
    cta.foot = cta.line;
    const viewsBeat = [...beats].reverse().find(b => b && b.role === 'views');
    if (viewsBeat && viewsBeat.visual) {
      splitD.bull = viewsBeat.visual.bull != null ? viewsBeat.visual.bull : bull;
      splitD.bear = viewsBeat.visual.bear != null ? viewsBeat.visual.bear : bear;
      splitD.angle = viewsBeat.visual.angle || '';
      splitD.verdict = viewsBeat.caption || splitD.verdict;
    }
  }
  open.showLabel = showLabel; open.showId = showId;
  open.subline1 = open.subline1 || 'One crowd quote.';
  open.subline2 = open.subline2 || 'One punch.';
  splitD.showLabel = showLabel; splitD.showId = showId;
  m1.showLabel = showLabel; m1.showId = showId;
  m2.showLabel = showLabel; m2.showId = showId;
  cta.showLabel = showLabel; cta.showId = showId;
  return { open, split: splitD, m1, m2, cta, n, bull, bear, big: open.big || big, showLabel, showId };
}

const header = total => `
const cl=v=>Math.max(0,Math.min(1,v)), out=p=>1-Math.pow(1-p,3), back=p=>{const c=1.9;return 1+(c+1)*Math.pow(p-1,3)+c*Math.pow(p-1,2)};
const BEAT=${BEAT}, TOTAL=${total};
function chrome(gt){
 let pb=document.getElementById('pbar');
 if(!pb){pb=document.createElement('div');pb.id='pbar';pb.style.cssText='position:absolute;left:0;top:0;height:8px;background:#f5a623;z-index:50;opacity:.85';document.documentElement.appendChild(pb)}
 pb.style.width=(gt/TOTAL*1080)+'px';
 return 1;
}`;

function scenePlan(job, vo, W) {
  if (job && job.beats && job.beats.length) {
    return job.beats.map((b, i) => {
      const dur = vo[i] ? vo[i].dur : 0;
      const base = (vo[i] && typeof vo[i].base === 'number') ? vo[i].base : (b.base || 8);
      const visual = Object.assign({}, b.visual || {}, {
        caption: (b.visual && b.visual.caption) || b.caption,
        showLabel: W.showLabel,
        showId: W.showId,
      });
      return { name: b.scene || b.role || 'heat', beats: Math.max(base, Math.ceil((dur + 0.4) / BEAT)), data: visual };
    });
  }
  return BASE.map(([name, b], i) => ({
    name,
    beats: Math.max(b, Math.ceil((vo[i].dur + 0.4) / BEAT)),
    data: W[name] || {},
  }));
}

async function one(browser, job, vo, outFile) {
  const why = voiceoverSkip(vo, p => fs.existsSync(p), job);
  if (why) { refuseVideo(job, outFile, why); return; }
  const W = words(job.lang, job.slides, job);
  const plan = scenePlan(job, vo, W);
  const SC = plan.map(s => [s.name, s.beats]);
  const starts = []; let acc = 0; for (const [, b] of SC) { starts.push(acc); acc += b * BEAT; }
  const total = acc + COVER;
  const events = [];
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), `cv-${job.lang}-`));
  try {
  let frame = 0;
  const shot = pg => pg.screenshot({ path: path.join(dir, String(frame++).padStart(4, '0') + '.jpg'), type: 'jpeg', quality: 88 });

  const sp = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await sp.goto('file://' + path.join(TOOLS, 'carousel_scene.html'), { waitUntil: 'networkidle' });
  await sp.evaluate(l => { document.documentElement.lang = l; }, job.lang);
  await sp.addScriptTag({ content: header(total) + fs.readFileSync(path.join(TOOLS, 'carousel_scenes.js'), 'utf8') });
  await sp.evaluate(async txt => {
    await Promise.race([Promise.all(['900 80px "Noto Sans TC"', '700 80px "Inter"'].map(f => document.fonts.load(f, txt))), new Promise(r => setTimeout(r, 20000))]);
    await document.fonts.ready;
    if (document.fonts.status !== 'loaded' || !document.fonts.check('700 28px "Noto Sans CJK TC"', '個看好')) {
      await new Promise(r => setTimeout(r, 3000)); await document.fonts.ready;
      if (document.fonts.status !== 'loaded') throw new Error('fonts not loaded (CJK) - refusing to draw tofu');
    }
  }, JSON.stringify(W));

  const coverJpg = coverOut(job);
  const scene = async (k, data) => {
    const n = Math.round(SC[k][1] * BEAT * FPS);
    await sp.evaluate(([nm, dd]) => setup(nm, dd), [SC[k][0], data]);
    await sp.evaluate(async () => { await Promise.all([...document.images].map(im => im.decode().catch(() => {}))); });
    for (let i = 0; i < n; i++) {
      const t = i / FPS;
      await sp.evaluate(([t, gt]) => draw(t, gt), [t, COVER + starts[k] + t]);
      await shot(sp);
    }
  };

  // Soft FX only — ticks / whoosh / soft pop. No boom / slam / stamp spam.
  // One name at a time when the job carries beats (Week Tape hot-list or weekday single).
  for (let k = 0; k < plan.length; k++) {
    await scene(k, plan[k].data);
    events.push({ at: starts[k], type: k === plan.length - 1 ? 'ding' : (k === 0 ? 'tick' : 'whoosh') });
  }

  await sp.close();
  // Frame 0 of open doubles as the IG cover still (already shows $TICKER + count).
  fs.copyFileSync(path.join(dir, '0000.jpg'), coverJpg);

  const ev = path.join(dir, 'events.json'), wav = path.join(dir, 'audio.wav');
  events.forEach(e => { e.at += COVER; });
  fs.writeFileSync(ev, JSON.stringify({ total, bpm: BPM, drop: COVER + starts[1], events,
    vo: vo.map((v, i) => ({ file: v.file, at: COVER + starts[i] + 0.15 })) }));
  const tmpOut = outFile + '.part.mp4';
  try {
    execFileSync('python3', [path.join(TOOLS, 'carousel_audio.py'), ev, wav], { stdio: 'inherit' });
    execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-i', path.join(dir, '%04d.jpg'), '-i', wav,
      '-vf', 'scale=1080:1920:in_range=pc:out_range=tv,format=yuv420p',
      '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26', '-profile:v', 'high', '-level:v', '4.0',
      '-pix_fmt', 'yuv420p', '-color_range', 'tv', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
      '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-shortest',
      '-movflags', '+faststart', tmpOut], { stdio: 'inherit' });
    fs.renameSync(tmpOut, outFile);
  } catch (e) {
    removePartial(outFile);
    try { fs.unlinkSync(outFile); } catch (_) {}
    throw e;
  }
  try {
    writeVoMarker(outFile, job, total);
  } catch (e) {
    try { fs.unlinkSync(outFile); } catch (_) {}
    try { fs.unlinkSync(voMarkerPath(outFile)); } catch (_) {}
    throw e;
  }
  console.log(`carousel cover ${coverJpg}`);
  console.log(`carousel video ${outFile} ${total.toFixed(1)}s (voiceover)`);
  try {
    writeYtSidecars(job, W, { videoStem, alsoSamples: process.env.YT_SAMPLES === '1' });
  } catch (e) {
    console.log('::warning::YT sidecar 寫唔到：' + (e && e.message));
  }
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

async function main() {
  const file = process.argv[2];
  const all = JSON.parse(fs.readFileSync(file, 'utf8'));
  const jobs = all.jobs.filter(j => SLOTS.includes(j.slot) && LANGS.includes(j.lang));
  if (!jobs.length) { console.log('carousel video: no slot to film'); return; }
  fs.mkdirSync('og/c', { recursive: true });
  const live = [];
  for (const j of jobs) {
    if (isVideoSkip(j)) {
      writeSkip(j);
      continue;
    }
    live.push(j);
  }
  if (!live.length) {
    console.log('::notice::carousel video: nothing publishable');
    return;
  }
  let vo = {};
  try {
    const voDir = path.join(path.dirname(path.resolve(file)), 'vo');
    execFileSync('python3', [path.join(TOOLS, 'carousel_vo.py'), file, voDir], { stdio: 'inherit', timeout: 240000 });
    vo = JSON.parse(fs.readFileSync(path.join(voDir, 'vo.json'), 'utf8'));
  } catch (e) { console.log('::warning::配音整唔到，今次唔出片：' + e.message); }
  const ready = [];
  for (const j of live) {
    const clips = vo[`${j.slot}-${j.lang}`];
    const out = videoOut(j);
    const why = voiceoverSkip(clips, p => fs.existsSync(p), j);
    if (why) { refuseVideo(j, out, why); continue; }
    ready.push([j, clips, out]);
  }
  if (!ready.length) { console.log('carousel video: no voiced slot to film'); return; }
  const { chromium } = require('playwright');
  const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  const res = await Promise.allSettled(ready.map(([j, clips, out]) => one(browser, j, clips, out)));
  await browser.close();
  res.forEach((r, i) => {
    if (r.status === 'rejected') {
      const [j, , out] = ready[i];
      removePartial(out);
      try { fs.unlinkSync(out); } catch (_) {}
      try { fs.unlinkSync(voMarkerPath(out)); } catch (_) {}
      console.log(`::warning::${j.slot} ${j.lang} 動態片整唔到：${r.reason && r.reason.message}`);
    }
  });
}

if (require.main === module) main();

module.exports = {
  voicedTotal, voiceoverSkip, refuseVideo, removePartial, writeVoMarker, voMarkerPath,
  voiceName, MIN_VIDEO_S, MAX_VIDEO_S, WEEK_MAX_VIDEO_S, COVER, BEAT, BASE, VOICES, words, COVER_FRAMES,
  loadHeroQuote, splitQuoteLines, parsePoint, one, videoStem, videoOut, coverOut, showMap, DEFAULT_SHOW, SHOW_LABELS,
  writeYtSidecars, writeSkip, videoCap, stanceFrom, isVideoSkip,
};
