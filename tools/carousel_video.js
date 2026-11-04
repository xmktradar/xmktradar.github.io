// Motion videos from the daily multi-picture posts (v6.1 Bloomberg / terminal + hookQ/parable).
// Usage: node tools/carousel_video.js work/carousel.json   (after tools/carousel.js, from the repo root)
// For each job whose slot is in VIDEO_SLOTS (default 1230) and language in VIDEO_LANGS (default en) it writes og/c/<day>-<slot>-<lang>.mp4:
// 1080x1920, H.264 limited yuv420p + AAC +faststart. Cover is merged into the open scene: frame 0 already
// shows $TICKER + the discussion count. Soft terminal cuts (open, split, m1, m2, cta) — no comic slides,
// no emoji / confetti / shake / white-flash. VO from tools/carousel_vo.py is required; skip the language
// if VO is missing or the voiced cut would exceed 29s. Sidecar og/c/<day>-<slot>-<lang>.vo.json after mix.
// Tim 2026-11-04: default VIDEO_LANGS=en (no daily *-zh.mp4). Override with VIDEO_LANGS=zh,en if needed.
// v6.1 scheme A: words() fills open.hookQ + m1 parable for en; empty → legacy #278 layout.
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const FPS = 24, BPM = 124, BEAT = 60 / BPM;
// Keep in sync with BASE_BEATS / COVER_FRAMES in tools/carousel_vo.py.
const BASE = [['open', 6], ['split', 6], ['m1', 7], ['m2', 7], ['cta', 5]];
const COVER_FRAMES = 0; // cover merged into open; frame 0 of open is also written as *-cover.jpg
const COVER = COVER_FRAMES / FPS;
const MAX_VIDEO_S = 29;
const VOICES = { zh: 'zh-CN-XiaoxiaoNeural', en: 'en-US-AndrewNeural' };
const SLOTS = (process.env.VIDEO_SLOTS || '1230').split(',').filter(Boolean);
const LANGS = (process.env.VIDEO_LANGS || 'en').split(',').filter(Boolean);
const TOOLS = __dirname;

function voiceName(lang) {
  return process.env['VO_VOICE_' + lang] || VOICES[lang] || lang;
}

function voMarkerPath(outFile) {
  return outFile.replace(/\.mp4$/i, '.vo.json');
}

function voicedTotal(vo) {
  let acc = 0;
  for (let i = 0; i < BASE.length; i++) acc += Math.max(BASE[i][1], Math.ceil((vo[i].dur + 0.4) / BEAT)) * BEAT;
  return acc + COVER;
}

function voiceoverSkip(vo, exists = p => fs.existsSync(p)) {
  if (!Array.isArray(vo) || vo.length < BASE.length) return 'no voiceover';
  for (let i = 0; i < BASE.length; i++) {
    const v = vo[i];
    if (!v || typeof v.dur !== 'number' || !v.file || !exists(v.file)) return 'voiceover audio missing';
  }
  const total = voicedTotal(vo);
  if (total > MAX_VIDEO_S) return `voiced ${total.toFixed(2)}s > ${MAX_VIDEO_S}`;
  return null;
}

function removePartial(outFile) {
  for (const p of [outFile + '.part.mp4']) {
    try { fs.unlinkSync(p); } catch (_) {}
  }
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

/** Scene copy — numbers/tickers only from job slides. Zero emoji. */
function words(lang, slides) {
  const S0 = slides[0] || {};
  const n = num(S0.sub), bull = num((S0.pills || []).find(p => p.c === 'g')?.x), bear = num((S0.pills || []).find(p => p.c === 'r')?.x);
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
    foot: zh ? '免費 · 無需登入 · 每 4 小時更新 · 不構成投資建議' : 'Free · No login · Every 4h · Not investment advice',
    date: S0.win || '',
  };
  // v6.1 scheme A (en): cold-open question + rock-valuation parable on m1. Empty → #278 rows.
  if (!zh && big) {
    open.hookQ = `${big} jumped in the tape today — where did that value go?`;
    m1.mode = 'parable';
    m1.title = 'PARABLE';
    m1.parable = [
      'Someone offers $100 for your rock.',
      'A week later: only $10.',
      "$90 of 'value' gone — rock unchanged.",
    ];
    m1.anchor = `$${big}`;
    m1.punch = 'Quotes moved on the tape — same idea.';
  }
  return { open, split: splitD, m1, m2, cta, n, bull, bear, big };
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

async function one(browser, job, vo, outFile) {
  const why = voiceoverSkip(vo);
  if (why) { refuseVideo(job, outFile, why); return; }
  const W = words(job.lang, job.slides);
  const SC = BASE.map(([name, b], i) => [name, Math.max(b, Math.ceil((vo[i].dur + 0.4) / BEAT))]);
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

  const coverJpg = `og/c/${job.date}-${job.slot}-${job.lang}-cover.jpg`;
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
  await scene(0, W.open);
  events.push({ at: 0, type: 'tick' }, { at: BEAT, type: 'tick' }, { at: 2 * BEAT, type: 'whoosh' });
  await scene(1, W.split);
  events.push({ at: starts[1], type: 'whoosh' }, { at: starts[1] + 2 * BEAT, type: 'tick' }, { at: starts[1] + 3 * BEAT, type: 'pop' });
  await scene(2, W.m1);
  events.push({ at: starts[2], type: 'whoosh' }, { at: starts[2] + BEAT, type: 'tick' }, { at: starts[2] + 3 * BEAT, type: 'tick' });
  await scene(3, W.m2);
  events.push({ at: starts[3], type: 'whoosh' }, { at: starts[3] + 2 * BEAT, type: 'tick' });
  await scene(4, W.cta);
  events.push({ at: starts[4], type: 'whoosh' }, { at: starts[4] + BEAT, type: 'ding' });

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
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

async function main() {
  const file = process.argv[2];
  const all = JSON.parse(fs.readFileSync(file, 'utf8'));
  const jobs = all.jobs.filter(j => SLOTS.includes(j.slot) && LANGS.includes(j.lang));
  if (!jobs.length) { console.log('carousel video: no slot to film'); return; }
  let vo = {};
  try {
    const voDir = path.join(path.dirname(path.resolve(file)), 'vo');
    execFileSync('python3', [path.join(TOOLS, 'carousel_vo.py'), file, voDir], { stdio: 'inherit', timeout: 240000 });
    vo = JSON.parse(fs.readFileSync(path.join(voDir, 'vo.json'), 'utf8'));
  } catch (e) { console.log('::warning::配音整唔到，今次唔出片：' + e.message); }
  fs.mkdirSync('og/c', { recursive: true });
  const ready = [];
  for (const j of jobs) {
    const clips = vo[`${j.slot}-${j.lang}`];
    const out = `og/c/${j.date}-${j.slot}-${j.lang}.mp4`;
    const why = voiceoverSkip(clips);
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
  voiceName, MAX_VIDEO_S, COVER, BEAT, BASE, VOICES, words, COVER_FRAMES,
};
