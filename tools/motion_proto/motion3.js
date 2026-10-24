// Prototype v4 (2026-10-24, Tim OK 15:41) for tools/MOTION_VIDEO.md; not run by any workflow. Needs slideanim.js and audio3.py next to it.
// node motion3.js work/carousel.json 1230 zh out.mp4   (run from the repo root)
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), { execFileSync } = require('child_process');
const [,, jobFile, slot, lang, out] = process.argv;
const REPO = process.cwd();
const job = JSON.parse(fs.readFileSync(jobFile, 'utf8')).jobs.find(j => j.slot === slot && j.lang === lang);
const FPS = 24, BPM = 124, BEAT = 60 / BPM;
// scenes in beats: hook, reveal, vs, slide1..4, outro
const SC = [['hook', 5], ['reveal', 4], ['vs', 6], ['s1', 7], ['s2', 7], ['s3', 6], ['s4', 6], ['outro', 7]];
const starts = []; let acc = 0; for (const [, b] of SC) { starts.push(acc); acc += b * BEAT; }
const TOTAL = acc;
const tmp = path.join(__dirname, 'f3'); fs.rmSync(tmp, { recursive: true, force: true }); fs.mkdirSync(tmp);
const S0 = job.slides[0];
const num = (s, d = 0) => { const m = String(s || '').match(/\d+/); return m ? +m[0] : d; };
const bull = num((S0.pills || []).find(p => p.c === 'g')?.x), bear = num((S0.pills || []).find(p => p.c === 'r')?.x), nAcc = num(S0.sub);
const events = [];  // {at, type} absolute seconds, for the audio
const logo = 'data:image/png;base64,' + fs.readFileSync(path.join(REPO, 'tools/logo.png')).toString('base64');
const T = {
  hook: ['今日', 'X 上 200 個美股大神', '最多人講嘅係…', '？？？'],
  reveal: `${nAcc} 個帳號講緊！`,
  vs: ['🟢 睇好', '🔴 睇淡', bear > bull ? '淡友大勝？😱' : bull > bear ? '好友大勝？🚀' : '打和！🤝'],
  caps: [`大神點講 $${S0.big}？💬`, '🔥 熱度 Top 4', '一齊睇好 🟢 定睇淡 🔴', '⚔️ 爭拗最大！你企邊？'],
  outro: ['想睇晒全部？👇', 'thecrowdtape.com', '免費・唔使登入・每 4 小時更新', 'Follow @thecrowdtape 🔔', '⚠️ 唔構成投資建議'],
};
// ---------- shared page helpers (progress bar, beat pulse) ----------
const COMMON = `
const cl=v=>Math.max(0,Math.min(1,v)), out=p=>1-Math.pow(1-p,3), back=p=>{const c=1.9;return 1+(c+1)*Math.pow(p-1,3)+c*Math.pow(p-1,2)};
const BEAT=${BEAT}, TOTAL=${TOTAL};
function chrome(gt){
 let pb=document.getElementById('pbar');
 if(!pb){pb=document.createElement('div');pb.id='pbar';pb.style.cssText='position:absolute;left:0;top:0;height:16px;background:#f8d34a;z-index:50;box-shadow:0 3px 0 #151a2c';document.documentElement.appendChild(pb)}
 pb.style.width=(gt/TOTAL*1080)+'px';
 const ph=(gt%BEAT)/BEAT; return 1+0.035*Math.exp(-ph*7);   // beat pulse scale
}`;
const SCENE_CSS = `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@700&family=Noto+Sans+TC:wght@900&display=block">
<style>html,body{margin:0;width:1080px;height:1920px;overflow:hidden}body{position:relative;font-family:'Noto Sans TC',sans-serif;background:#151a2c}
#bg{position:absolute;inset:0}#rays{position:absolute;inset:-500px;background:repeating-conic-gradient(from var(--rot,0deg) at 50% 50%,rgba(255,255,255,.22) 0 6deg,transparent 6deg 14deg)}
#c{position:absolute;inset:0}.t{position:absolute;left:0;right:0;text-align:center;font-weight:900;opacity:0}
.s{display:inline-block;border:8px solid #151a2c;border-radius:34px;box-shadow:12px 14px 0 #151a2c;padding:18px 44px;background:#fff;color:#151a2c}
.mono{font-family:'IBM Plex Mono',monospace}#flash{position:absolute;inset:0;background:#fff;opacity:0;z-index:40}
.emo{position:absolute;font-size:150px;opacity:0;z-index:30}.cf{position:absolute;width:22px;height:34px;z-index:30}</style>
<body><div id="bg"></div><div id="rays"></div><div id="c"></div><div id="flash"></div></body>`;
(async () => {
  const b = await chromium.launch();
  let frame = 0;
  const shot = async (pg) => pg.screenshot({ path: path.join(tmp, String(frame++).padStart(4, '0') + '.jpg'), type: 'jpeg', quality: 90 });
  // ---------- full-screen kinetic scenes ----------
  const sp = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  await sp.setContent(SCENE_CSS, { waitUntil: 'networkidle' });
  await sp.addScriptTag({ content: COMMON + `
  function setup(name,D){
   const c=document.getElementById('c'); c.innerHTML=''; c.style.transform='';
   const add=(h,y,size,cls,rot)=>{const d=document.createElement('div');d.className='t';d.style.top=y+'px';d.style.fontSize=size+'px';d.innerHTML='<span class="'+(cls||'')+'" style="display:inline-block;transform:rotate('+(rot||0)+'deg)">'+h+'</span>';c.appendChild(d);return d};
   window.S={name,D,els:[]};
   if(name==='hook'){S.els=[add(D.t[0],520,260,'',-3),add(D.t[1],880,76,'s',2),add(D.t[2],1080,96,'s',-2),add(D.t[3],1340,200,'',0)];}
   if(name==='reveal'){S.els=[add('$'+D.big,640,D.big.length>4?230:300,'mono s',-2),add(D.reveal,1130,84,'s',2)];
     ['🔥','🚀','👀','💥','📈','🤯'].forEach((e,i)=>{const d=document.createElement('div');d.className='emo';d.textContent=e;c.appendChild(d);S.els.push(d)});}
   if(name==='vs'){c.innerHTML='<div id="L" style="position:absolute;left:0;top:0;bottom:0;width:50%;background:#2fc46b"></div><div id="R" style="position:absolute;right:0;top:0;bottom:0;width:50%;background:#ff4f6d"></div>';
     S.els=[add(D.t[0],520,70,'s',-3),add(D.t[1],520,70,'s',3),add('VS',760,260,'mono',0),add(String(D.bull),1050,300,'mono',0),add(String(D.bear),1050,300,'mono',0),add(D.t[2],1500,80,'s',-2)];
     S.els[0].style.right='50%';S.els[3].style.right='50%';S.els[1].style.left='50%';S.els[4].style.left='50%';
     S.els[2].querySelector('span').style.cssText+=';color:#f8d34a;-webkit-text-stroke:10px #151a2c;paint-order:stroke';
     [3,4].forEach(i=>S.els[i].querySelector('span').style.cssText+=';color:#fff;-webkit-text-stroke:12px #151a2c;paint-order:stroke');}
   if(name==='outro'){S.els=[add(D.t[0],330,96,'s',-2),add(D.t[1],620,80,'mono s',2),add(D.t[2],900,50,'s',0),add(D.t[3],1150,72,'s',-2),add(D.t[4],1600,44,'',0)];
     S.els[1].querySelector('span').style.cssText+=';background:#151a2c;color:#f8d34a';S.els[3].querySelector('span').style.background='#f8d34a';S.els[4].style.color='#fff';
     for(let i=0;i<60;i++){const d=document.createElement('div');d.className='cf';d.style.background=['#f8d34a','#5ee08f','#ff8a8a','#5ab8ff','#fff'][i%5];d.dataset.x=Math.random()*1080;d.dataset.v=0.6+Math.random();d.dataset.r=Math.random()*360;c.appendChild(d);S.els.push(d)}}
  }
  const HOOKBG=['#151a2c','#8f7bff','#ff4f6d','#ffd84d','#5ab8ff'];
  function draw(t,gt){
   const pulse=chrome(gt), beat=Math.floor(t/BEAT), bt=(t%BEAT)/BEAT, E=S.els, bg=document.getElementById('bg'), fl=document.getElementById('flash'), c=document.getElementById('c');
   document.body.style.setProperty('--rot',(gt*40)+'deg'); fl.style.opacity=0; let shake=0;
   const pop=(e,start,dur,mode)=>{const p=cl((t-start)/(dur||.25));e.style.opacity=p>0?1:0;const sc=mode==='slam'?2.8-1.8*out(p):0.2+0.8*back(p);e.style.transform='scale('+sc+')';return p};
   if(S.name==='hook'){bg.style.background=HOOKBG[Math.min(beat,4)];
     E[0].style.color=beat%2?'#151a2c':'#f8d34a';
     pop(E[0],0,.2,'slam');pop(E[1],BEAT,.25);pop(E[2],2*BEAT,.25);
     if(t>=3*BEAT){const p=pop(E[3],3*BEAT,.2);E[3].style.color='#fff';E[3].style.transform+=' rotate('+Math.sin(t*40)*6+'deg)';shake=8}
     if(bt<.12)fl.style.opacity=.5*(1-bt/.12);}
   if(S.name==='reveal'){bg.style.background='linear-gradient(160deg,#ffd84d,#ff6aa8)';
     const p=pop(E[0],0,.3,'slam'); if(t>.3&&t<.75){shake=30*(1-(t-.3)/.45);fl.style.opacity=.7*(1-(t-.3)/.45)}
     E[0].querySelector('span').style.background='#fff';
     pop(E[1],2*BEAT,.3);
     E.slice(2).forEach((e,i)=>{const a=i*Math.PI/3+.4,q=cl((t-.3-i*.04)/1.1);e.style.opacity=q>0&&q<1?1-q*q:0;e.style.left=(470+Math.cos(a)*(60+520*out(q)))+'px';e.style.top=(760+Math.sin(a)*(60+520*out(q)))+'px';e.style.transform='scale('+(.5+out(q))+') rotate('+(q*90)+'deg)'});}
   if(S.name==='vs'){bg.style.background='#151a2c';
     const L=document.getElementById('L'),R=document.getElementById('R'),q=out(cl(t/.3));L.style.transform='translateX('+(-(1-q)*100)+'%)';R.style.transform='translateX('+((1-q)*100)+'%)';
     pop(E[0],.15,.25);pop(E[1],.3,.25);const v=pop(E[2],BEAT,.25,'slam');if(t>BEAT+.25&&t<BEAT+.6){shake=24;fl.style.opacity=.5}
     E[2].querySelector('span').style.transform='rotate('+Math.sin(t*12)*5+'deg)';
     const n1=pop(E[3],2*BEAT,.25,'slam'),n2=pop(E[4],3*BEAT,.25,'slam');
     E[3].querySelector('span').textContent=Math.round(D_.bull*out(cl((t-2*BEAT)/.4)));E[4].querySelector('span').textContent=Math.round(D_.bear*out(cl((t-3*BEAT)/.4)));
     // winner side grows
     const w=cl((t-4*BEAT)/.5), tot=Math.max(1,D_.bull+D_.bear), lw=50+(D_.bull/tot*100-50)*out(w);L.style.width=lw+'%';R.style.width=(100-lw)+'%';
     pop(E[5],4.5*BEAT,.3);}
   if(S.name==='outro'){bg.style.background='linear-gradient(160deg,#8f7bff,#ff6aa8)';
     [0,1,2,3,4].forEach(i=>pop(E[i],i*.35,.3)); if(t>.35&&t<.45)fl.style.opacity=.4;
     E.slice(5).forEach(d=>{const y=-60+(t*700*d.dataset.v)%2100;d.style.left=(+d.dataset.x+Math.sin(t*3+ +d.dataset.r)*40)+'px';d.style.top=y+'px';d.style.opacity=t>.3?1:0;d.style.transform='rotate('+(+d.dataset.r+t*300)+'deg)'});}
   c.style.transform='scale('+pulse+') translate('+(Math.sin(gt*90)*shake)+'px,'+(Math.cos(gt*70)*shake)+'px)';
  }` });
  const D = { t: T.hook, big: S0.big, reveal: T.reveal, bull, bear };
  await sp.evaluate(d => { window.D_ = d; }, D);
  await sp.evaluate(async () => { await document.fonts.load('900 80px "Noto Sans TC"', '今日睇好'); await document.fonts.load('700 80px "IBM Plex Mono"', 'SPY'); await document.fonts.ready; });
  const scene = async (k, data) => {
    const [name, beats] = SC[k], n = Math.round(beats * BEAT * FPS);
    await sp.evaluate(([nm, dd]) => setup(nm, dd), [name, data]);
    for (let i = 0; i < n; i++) { const t = i / FPS; await sp.evaluate(([t, gt]) => draw(t, gt), [t, starts[k] + t]); await shot(sp); }
  };
  // hook
  await scene(0, { t: T.hook });
  for (let i = 0; i < 5; i++) events.push({ at: i * BEAT, type: i < 3 ? 'hit' : 'roll' });
  // reveal
  await scene(1, { big: S0.big, reveal: T.reveal });
  events.push({ at: starts[1], type: 'bigdrop' }, { at: starts[1] + .3, type: 'boom' }, { at: starts[1] + 2 * BEAT, type: 'pop' });
  // vs
  await scene(2, { t: T.vs, bull, bear });
  events.push({ at: starts[2], type: 'whoosh' }, { at: starts[2] + BEAT + .2, type: 'boom' }, { at: starts[2] + 2 * BEAT + .2, type: 'stamp' }, { at: starts[2] + 3 * BEAT + .2, type: 'stamp' }, { at: starts[2] + 4 * BEAT, type: 'rise' }, { at: starts[2] + 4.5 * BEAT, type: 'pop' });
  // ---------- carousel slides with camera ----------
  const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  await p.goto('file://' + path.join(REPO, 'tools/carousel.html'), { waitUntil: 'networkidle' });
  await p.addScriptTag({ content: COMMON + fs.readFileSync(path.join(__dirname, 'slideanim.js'), 'utf8') });
  for (let i = 0; i < 4; i++) {
    const k = 3 + i, n = Math.round(SC[k][1] * BEAT * FPS);
    await p.evaluate(([l, t, d, nn, s]) => render(l, t, d, nn, s), [job.lang, job.theme, job.date, i + 1, job.slides[i]]);
    await p.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map(i => i.decode().catch(() => {}))); });
    await p.evaluate(() => { const room = document.getElementById('main').clientHeight, box = document.getElementById('in'); let k = 1;
      while (box.getBoundingClientRect().height > room + 2 && k > 0.6) { k -= 0.05; box.style.zoom = k; } });
    const ev = await p.evaluate(([cap, idx]) => setupSlide(cap, idx), [T.caps[i], i]);
    ev.forEach(e => events.push({ at: starts[k] + e.start / 1000 / 1.35, type: e.type }));
    events.push({ at: starts[k], type: 'whoosh' });
    for (let f = 0; f < n; f++) { const t = f / FPS; await p.evaluate(([t, gt, dur]) => drawSlide(t, gt, dur), [t, starts[k] + t, SC[k][1] * BEAT]); await shot(p); }
  }
  // outro
  await scene(7, { t: T.outro });
  events.push({ at: starts[7], type: 'whoosh' }); [0, 1, 2, 3, 4].forEach(i => events.push({ at: starts[7] + i * .35, type: 'pop' })); events.push({ at: starts[7] + .35, type: 'ding' });
  await b.close();
  fs.writeFileSync(path.join(__dirname, 'events3.json'), JSON.stringify({ total: TOTAL, bpm: BPM, drop: starts[1], events }));
  execFileSync('python3', [path.join(__dirname, 'audio3.py'), path.join(__dirname, 'events3.json'), path.join(__dirname, 'audio3.wav')], { stdio: 'inherit' });
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-i', path.join(tmp, '%04d.jpg'), '-i', path.join(__dirname, 'audio3.wav'),
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '22', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', out], { stdio: 'inherit' });
  console.log('wrote', out, TOTAL.toFixed(1) + 's');
})();
