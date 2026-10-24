// Motion videos from the daily multi-picture posts (Tim, 2026-10-24; spec tools/MOTION_VIDEO.md).
// Usage: node tools/carousel_video.js work/carousel.json   (after tools/carousel.js, from the repo root)
// For each job whose slot is in VIDEO_SLOTS (default 1230) and language in VIDEO_LANGS (default zh,en) it writes og/c/<day>-<slot>-<lang>.mp4:
// 1080x1920, beat-synced hard cuts over 8 scenes (hook, reveal, bull vs bear, the 4 pictures, outro),
// a generated beat and sound effects (tools/carousel_audio.py), and a voiceover where
// tools/carousel_vo.py could read one (VO_LANGS, default zh). The 4 pictures are drawn by the same
// tools/carousel.html as the stills and are always shown whole. The three languages render at once.
// Old videos go with the pictures (tools/carousel.js keeps only today's and yesterday's og/c files).
const { chromium } = require('playwright');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const FPS = 24, BPM = 124, BEAT = 60 / BPM;
const BASE = [['hook', 5], ['reveal', 4], ['vs', 6], ['s1', 7], ['s2', 7], ['s3', 6], ['s4', 6], ['outro', 7]];
const SLOTS = (process.env.VIDEO_SLOTS || '1230').split(',').filter(Boolean);
const LANGS = (process.env.VIDEO_LANGS || 'zh,en').split(',').filter(Boolean);  // Tim 2026-10-25: Chinese and English only
const TOOLS = __dirname;

const num = (s, d = 0) => { const m = String(s || '').match(/\d+/); return m ? +m[0] : d; };
function words(lang, S0) {
  const n = num(S0.sub), bull = num((S0.pills || []).find(p => p.c === 'g')?.x), bear = num((S0.pills || []).find(p => p.c === 'r')?.x);
  const w = bear > bull ? 0 : bull > bear ? 1 : 2, big = S0.big;
  const T = {
    zh: { hook: ['今日', 'X 上 200 個美股大神', '最多人講嘅係…', '？？？'], reveal: `${n} 個帳號講緊！`,
      vs: ['🟢 睇好', '🔴 睇淡', ['淡友大勝？😱', '好友大勝？🚀', '打和！🤝'][w]],
      caps: [`大神點講 $${big}？💬`, '🔥 熱度 Top 4', '一齊睇好 🟢 定睇淡 🔴', '⚔️ 爭拗最大！你企邊？'],
      outro: ['想睇晒全部？👇', 'thecrowdtape.com', '免費・唔使登入・每 4 小時更新', 'Follow @thecrowdtape 🔔', '⚠️ 唔構成投資建議'] },
    en: { hook: ['TODAY', '200 top US-stock voices on X', 'Most talked-about stock is…', '???'], reveal: `${n} accounts on it!`,
      vs: ['🟢 Bulls', '🔴 Bears', ['Bears winning? 😱', 'Bulls winning? 🚀', 'Dead even! 🤝'][w]],
      caps: [`What's said on $${big} 💬`, '🔥 Top 4 most talked', 'Bulls 🟢 or bears 🔴?', '⚔️ Pick a side!'],
      outro: ['See it all 👇', 'thecrowdtape.com', 'Free · No login · Every 4h', 'Follow @thecrowdtape 🔔', '⚠️ Not investment advice'] },
    ko: { hook: ['오늘', 'X 미국주식 고수 200명', '가장 많이 얘기한 종목은…', '???'], reveal: `${n}개 계정이 언급!`,
      vs: ['🟢 강세', '🔴 약세', ['약세 우세? 😱', '강세 우세? 🚀', '무승부! 🤝'][w]],
      caps: [`$${big}, 고수들 의견은? 💬`, '🔥 화제 Top 4', '같이 강세 🟢 vs 약세 🔴', '⚔️ 의견 최대 분열! 당신은?'],
      outro: ['전체가 궁금하다면 👇', 'thecrowdtape.com', '무료 · 로그인 없음 · 4시간마다 업데이트', 'Follow @thecrowdtape 🔔', '⚠️ 투자 조언 아님'] },
  }[lang];
  return { ...T, n, bull, bear, big };
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
  const W = words(job.lang, job.slides[0]);
  // scene lengths in beats; a voiced scene grows to fit its line (+0.4 s), in whole beats
  const SC = BASE.map(([name, b], i) => [name, vo ? Math.max(b, Math.ceil((vo[i].dur + 0.4) / BEAT)) : b]);
  const starts = []; let acc = 0; for (const [, b] of SC) { starts.push(acc); acc += b * BEAT; }
  const total = acc, events = [];
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), `cv-${job.lang}-`));
  let frame = 0;
  const shot = pg => pg.screenshot({ path: path.join(dir, String(frame++).padStart(4, '0') + '.jpg'), type: 'jpeg', quality: 88 });

  const sp = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await sp.goto('file://' + path.join(TOOLS, 'carousel_scene.html'), { waitUntil: 'networkidle' });
  await sp.evaluate(l => { document.documentElement.lang = l; }, job.lang);
  await sp.addScriptTag({ content: header(total) + fs.readFileSync(path.join(TOOLS, 'carousel_scenes.js'), 'utf8') });
  await sp.evaluate(async txt => {
    await Promise.race([Promise.all(['900 80px "Noto Sans TC"', '900 80px "Noto Sans KR"', '700 80px "IBM Plex Mono"'].map(f => document.fonts.load(f, txt))), new Promise(r => setTimeout(r, 20000))]);
    await document.fonts.ready;
  }, JSON.stringify(W));
  const scene = async (k, data) => {
    const n = Math.round(SC[k][1] * BEAT * FPS);
    await sp.evaluate(([nm, dd]) => setup(nm, dd), [SC[k][0], data]);
    for (let i = 0; i < n; i++) { const t = i / FPS; await sp.evaluate(([t, gt]) => draw(t, gt), [t, starts[k] + t]); await shot(sp); }
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
      const want = ['900 46px "Noto Sans TC"', '700 32px "Noto Sans TC"', '900 46px "Noto Sans KR"', '700 48px "IBM Plex Mono"'];
      await Promise.race([Promise.all(want.map(f => document.fonts.load(f, document.body.innerText))), new Promise(r => setTimeout(r, 20000))]);
      await document.fonts.ready; await Promise.all([...document.images].map(im => im.decode().catch(() => {})));
    });
    await p.evaluate(() => { const room = document.getElementById('main').clientHeight, box = document.getElementById('in'); let z = 1;
      while (box.getBoundingClientRect().height > room + 2 && z > 0.6) { z -= 0.05; box.style.zoom = z; } });
    const ev = await p.evaluate(([cap, idx]) => setupSlide(cap, idx), [W.caps[i], i]);
    ev.forEach(e => events.push({ at: starts[k] + e.start / 1000 / 1.35, type: e.type }));
    events.push({ at: starts[k], type: 'whoosh' });
    for (let f = 0; f < n; f++) { const t = f / FPS; await p.evaluate(([t, gt, dur]) => drawSlide(t, gt, dur), [t, starts[k] + t, SC[k][1] * BEAT]); await shot(p); }
  }
  await scene(7, { t: W.outro });
  events.push({ at: starts[7], type: 'whoosh' }, { at: starts[7] + .35, type: 'ding' });
  [0, 1, 2, 3, 4].forEach(i => events.push({ at: starts[7] + i * .35, type: 'pop' }));
  await sp.close(); await p.close();
  if (errs.length) throw new Error(errs.join('; '));

  const ev = path.join(dir, 'events.json'), wav = path.join(dir, 'audio.wav');
  fs.writeFileSync(ev, JSON.stringify({ total, bpm: BPM, drop: starts[1], events,
    vo: vo ? vo.map((v, i) => ({ file: v.file, at: starts[i] + 0.15 })) : [] }));
  execFileSync('python3', [path.join(TOOLS, 'carousel_audio.py'), ev, wav], { stdio: 'inherit' });
  const tmpOut = outFile + '.part.mp4';
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-i', path.join(dir, '%04d.jpg'), '-i', wav,
    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-shortest',
    '-movflags', '+faststart', tmpOut], { stdio: 'inherit' });
  fs.renameSync(tmpOut, outFile);
  fs.rmSync(dir, { recursive: true, force: true });
  console.log(`carousel video ${outFile} ${total.toFixed(1)}s${vo ? ' (voiceover)' : ''}`);
}

(async () => {
  const file = process.argv[2];
  const all = JSON.parse(fs.readFileSync(file, 'utf8'));
  const jobs = all.jobs.filter(j => SLOTS.includes(j.slot) && LANGS.includes(j.lang));
  if (!jobs.length) { console.log('carousel video: no slot to film'); return; }
  let vo = {};
  try {
    const voDir = path.join(path.dirname(path.resolve(file)), 'vo');
    execFileSync('python3', [path.join(TOOLS, 'carousel_vo.py'), file, voDir], { stdio: 'inherit', timeout: 240000 });
    vo = JSON.parse(fs.readFileSync(path.join(voDir, 'vo.json'), 'utf8'));
  } catch (e) { console.log('::warning::配音整唔到，今次出冇配音版：' + e.message); }
  const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  fs.mkdirSync('og/c', { recursive: true });
  const res = await Promise.allSettled(jobs.map(j =>
    one(browser, j, vo[`${j.slot}-${j.lang}`], `og/c/${j.date}-${j.slot}-${j.lang}.mp4`)));
  await browser.close();
  res.forEach((r, i) => { if (r.status === 'rejected') console.log(`::warning::${jobs[i].slot} ${jobs[i].lang} 動態片整唔到：${r.reason && r.reason.message}`); });
})();
