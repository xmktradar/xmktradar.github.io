// Motion videos from the daily multi-picture posts (Tim, 2026-10-24; spec tools/MOTION_VIDEO.md).
// Usage: node tools/carousel_video.js work/carousel.json   (after tools/carousel.js, from the repo root)
// For each job whose slot is in VIDEO_SLOTS (default 1230) and language in VIDEO_LANGS (default zh,en) it writes og/c/<day>-<slot>-<lang>.mp4:
// 1080x1920, a finished cover (~0.7s, also saved as og/c/<day>-<slot>-<lang>-cover.jpg) then beat-synced hard cuts
// over 8 scenes (hook, reveal, bull vs bear, the 4 pictures, outro),
// a generated beat and sound effects (tools/carousel_audio.py), and a voiceover from tools/carousel_vo.py
// (VO_LANGS, default zh,en). Tim 2026-10-26: every published daily short must have a voiceover. If a
// language has no VO entry, the VO files are missing/failed, or the voiced cut would exceed 29s
// (cover included), that language is skipped — no silent or music-only mp4. After the mixed mp4 is
// confirmed, a sidecar og/c/<day>-<slot>-<lang>.vo.json is written {voice, duration, vo:true}.
// The voice starts after the cover (same +0.15s lead-in inside each scene).
// The 4 pictures are drawn by the same tools/carousel.html as the stills and are always shown whole.
// The languages render at once.
// Old videos go with the pictures (tools/carousel.js keeps only today's and yesterday's og/c files, including markers).
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const FPS = 24, BPM = 124, BEAT = 60 / BPM;
const BASE = [['hook', 5], ['reveal', 4], ['vs', 6], ['s1', 7], ['s2', 7], ['s3', 6], ['s4', 6], ['outro', 7]];
const COVER_FRAMES = 17; // ~0.7s. Keep in sync with COVER_FRAMES in tools/carousel_vo.py.
const COVER = COVER_FRAMES / FPS;
const MAX_VIDEO_S = 29;
const VOICES = { zh: 'zh-CN-XiaoxiaoNeural', en: 'en-US-AndrewNeural' };
// Cover copy. Numbers and tickers come from the job slides, not from here. en has no Chinese.
const COVER_TEXT = {
  zh: { title: '每日精選', discussed: '最多人討論', bull: '最多人看好', foot: '⚠️ 不構成投資建議' },
  en: { title: 'Daily Picks', discussed: 'Most discussed', bull: 'Most bullish', foot: '⚠️ Not investment advice' },
};
const SLOTS = (process.env.VIDEO_SLOTS || '1230').split(',').filter(Boolean);
const LANGS = (process.env.VIDEO_LANGS || 'zh,en').split(',').filter(Boolean);  // Tim 2026-10-25: Chinese and English only
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
function words(lang, S0) {
  const n = num(S0.sub), bull = num((S0.pills || []).find(p => p.c === 'g')?.x), bear = num((S0.pills || []).find(p => p.c === 'r')?.x);
  const w = bear > bull ? 0 : bull > bear ? 1 : 2, big = S0.big;
  const T = {
    zh: { hook: ['今天', 'X 上 200 位美股大神', '討論最多的是…', '？？？'], reveal: `${n} 個帳號正在討論！`,
      vs: ['🟢 看好', '🔴 看空', ['空方大勝？😱', '多方大勝？🚀', '打平！🤝'][w]],
      caps: [`大神怎麼看 $${big}？💬`, '🔥 熱度 Top 4', '共同看好 🟢 還是看空 🔴', '⚔️ 分歧最大！你站哪邊？'],
      outro: ['想看完整內容？👇', 'thecrowdtape.com', '免費・無需登入・每 4 小時更新', 'Follow @thecrowdtape 🔔', '⚠️ 不構成投資建議'] },
    en: { hook: ['TODAY', '200 top US-stock voices on X', 'Most talked-about stock is…', '???'], reveal: `${n} accounts on it!`,
      vs: ['🟢 Bulls', '🔴 Bears', ['Bears winning? 😱', 'Bulls winning? 🚀', 'Dead even! 🤝'][w]],
      caps: [`What's said on $${big} 💬`, '🔥 Top 4 most talked', 'Bulls 🟢 or bears 🔴?', '⚔️ Pick a side!'],
      outro: ['See it all 👇', 'thecrowdtape.com', 'Free · No login · Every 4h', 'Follow @thecrowdtape 🔔', '⚠️ Not investment advice'] },
  }[lang];
  return { ...T, n, bull, bear, big };
}

function coverPack(job) {
  const S0 = job.slides[0] || {};
  const secs = (job.slides[2] && job.slides[2].secs) || [];
  const bullSec = secs.find(s => String(s.h || '').startsWith('🟢'));
  const card = bullSec && bullSec.cards && bullSec.cards[0];
  const posted = (S0.stats || []).find(x => x && x.c === 'b');
  const pill = card && (card.pills || []).find(p => p && p.c === 'g');
  const copy = COVER_TEXT[job.lang] || COVER_TEXT.en;
  return {
    title: copy.title, date: job.date || '',
    discussedL: copy.discussed, discussed: S0.big || '', discussedN: S0.sub || '',
    bullL: copy.bull, bull: (card && card.t) || '', bullN: (pill && pill.x) || '',
    posted: (posted && posted.l) || '', foot: copy.foot,
  };
}

const header = total => `
const cl=v=>Math.max(0,Math.min(1,v)), out=p=>1-Math.pow(1-p,3), back=p=>{const c=1.9;return 1+(c+1)*Math.pow(p-1,3)+c*Math.pow(p-1,2)};
const BEAT=${BEAT}, TOTAL=${total};
function chrome(gt){
 let pb=document.getElementById('pbar');
 if(!pb){pb=document.createElement('div');pb.id='pbar';pb.style.cssText='position:absolute;left:0;top:0;height:16px;background:#f8d34a;z-index:50;box-shadow:0 3px 0 #151a2c';document.documentElement.appendChild(pb)}
 pb.style.width=(gt/TOTAL*1080)+'px';
 const ph=(gt%BEAT)/BEAT; return 1+0.035*Math.exp(-ph*7);
}`;

async function one(browser, job, vo, outFile) {
  const why = voiceoverSkip(vo);
  if (why) { refuseVideo(job, outFile, why); return; }
  const W = words(job.lang, job.slides[0]);
  const C = coverPack(job);
  // scene lengths in beats; a voiced scene grows to fit its line (+0.4 s), in whole beats.
  // Same sum as carousel_vo.video_total, including the opening cover. zh and en both must stay
  // <= 29.0s; carousel_vo.py fit_en already retries +20%, +30%, then a shorter script. If this
  // total is still over, skip the language (never drop the voice and ship a silent cut).
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
  }, JSON.stringify(W) + JSON.stringify(C));
  const coverJpg = `og/c/${job.date}-${job.slot}-${job.lang}-cover.jpg`;
  await sp.evaluate(([nm, dd]) => setup(nm, dd), ['cover', C]);
  await sp.evaluate(async () => { await Promise.all([...document.images].map(im => im.decode().catch(() => {}))); });
  for (let i = 0; i < COVER_FRAMES; i++) { const t = i / FPS; await sp.evaluate(([t, gt]) => draw(t, gt), [t, t]); await shot(sp); }
  fs.copyFileSync(path.join(dir, '0000.jpg'), coverJpg);
  const scene = async (k, data) => {
    const n = Math.round(SC[k][1] * BEAT * FPS);
    await sp.evaluate(([nm, dd]) => setup(nm, dd), [SC[k][0], data]);
    for (let i = 0; i < n; i++) { const t = i / FPS; await sp.evaluate(([t, gt]) => draw(t, gt), [t, COVER + starts[k] + t]); await shot(sp); }
  };
  await scene(0, { t: W.hook });
  for (let i = 0; i < 5; i++) events.push({ at: i * BEAT, type: i < 3 ? 'hit' : 'roll' });
  await scene(1, { big: W.big, reveal: W.reveal });
  events.push({ at: starts[1], type: 'bigdrop' }, { at: starts[1] + .3, type: 'boom' }, { at: starts[1] + 2 * BEAT, type: 'pop' });
  await scene(2, { t: W.vs, bull: W.bull, bear: W.bear });
  events.push({ at: starts[2], type: 'whoosh' }, { at: starts[2] + BEAT + .2, type: 'boom' }, { at: starts[2] + 2 * BEAT + .2, type: 'stamp' },
    { at: starts[2] + 3 * BEAT + .2, type: 'stamp' }, { at: starts[2] + 4 * BEAT, type: 'rise' }, { at: starts[2] + 4.5 * BEAT, type: 'pop' });

  const p = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + path.join(TOOLS, 'carousel.html'), { waitUntil: 'networkidle' });
  await p.addScriptTag({ content: header(total) + fs.readFileSync(path.join(TOOLS, 'carousel_motion.js'), 'utf8') });
  for (let i = 0; i < 4; i++) {
    const k = 3 + i, n = Math.round(SC[k][1] * BEAT * FPS);
    await p.evaluate(([l, t, d, nn, s]) => render(l, t, d, nn, s), [job.lang, job.theme, job.date, i + 1, job.slides[i]]);
    await p.evaluate(async () => {
      const want = ['900 46px "Noto Sans TC"', '700 32px "Noto Sans TC"', '700 48px "Inter"'];
      await Promise.race([Promise.all(want.map(f => document.fonts.load(f, document.body.innerText))), new Promise(r => setTimeout(r, 20000))]);
      await document.fonts.ready;
        if (document.fonts.status !== 'loaded' || !document.fonts.check('700 28px "Noto Sans CJK TC"', '個看好')) {
          await new Promise(r => setTimeout(r, 3000)); await document.fonts.ready;
          if (document.fonts.status !== 'loaded') throw new Error('fonts not loaded (CJK) - refusing to draw tofu');
        } await Promise.all([...document.images].map(im => im.decode().catch(() => {})));
    });
    await p.evaluate(() => { const room = document.getElementById('main').clientHeight, box = document.getElementById('in'); let z = 1;
      while (box.getBoundingClientRect().height > room + 2 && z > 0.6) { z -= 0.05; box.style.zoom = z; } });
    const ev = await p.evaluate(([cap, idx]) => setupSlide(cap, idx), [W.caps[i], i]);
    ev.forEach(e => events.push({ at: starts[k] + e.start / 1000 / 1.35, type: e.type }));
    events.push({ at: starts[k], type: 'whoosh' });
    for (let f = 0; f < n; f++) { const t = f / FPS; await p.evaluate(([t, gt, dur]) => drawSlide(t, gt, dur), [t, COVER + starts[k] + t, SC[k][1] * BEAT]); await shot(p); }
  }
  await scene(7, { t: W.outro });
  events.push({ at: starts[7], type: 'whoosh' }, { at: starts[7] + .35, type: 'ding' });
  [0, 1, 2, 3, 4].forEach(i => events.push({ at: starts[7] + i * .35, type: 'pop' }));
  await sp.close(); await p.close();
  if (errs.length) throw new Error(errs.join('; '));

  const ev = path.join(dir, 'events.json'), wav = path.join(dir, 'audio.wav');
  events.forEach(e => { e.at += COVER; });
  fs.writeFileSync(ev, JSON.stringify({ total, bpm: BPM, drop: COVER + starts[1], events,
    vo: vo.map((v, i) => ({ file: v.file, at: COVER + starts[i] + 0.15 })) }));
  const tmpOut = outFile + '.part.mp4';
  try {
    execFileSync('python3', [path.join(TOOLS, 'carousel_audio.py'), ev, wav], { stdio: 'inherit' });
    // JPEG frames are full-range. scale out_range=tv writes limited-range yuv420p (not yuvj420p) for Instagram.
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
  voiceName, MAX_VIDEO_S, COVER, BEAT, BASE, VOICES,
};
