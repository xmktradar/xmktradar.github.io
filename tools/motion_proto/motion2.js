// Prototype (2026-10-24) for tools/MOTION_VIDEO.md; not run by any workflow. Sample output: v2 sample shown to Tim.
// Prototype: animate one carousel job (4 slides) into frames, then mp4.
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), { execFileSync } = require('child_process');
const [,, jobFile, slot, lang, out] = process.argv;
const REPO = '/home/user/xmktradar.github.io';
const job = JSON.parse(fs.readFileSync(jobFile, 'utf8')).jobs.find(j => j.slot === slot && j.lang === lang);
const FPS = 24, SEC = 4, N = FPS * SEC;
const tmp = path.join(__dirname, 'frames'); fs.rmSync(tmp, { recursive: true, force: true }); fs.mkdirSync(tmp);
const ANIM = `
window.__tl=[];
function frame(lang,cap){
 const H=document.documentElement;
 if(!document.getElementById('band')){
  const st=document.createElement('style');st.textContent=\`html{width:1080px;height:1920px;overflow:hidden;background:linear-gradient(160deg,#5ab8ff,#8f7bff);position:relative}
  html::before{content:'';position:absolute;inset:-300px;background:repeating-conic-gradient(from var(--rot,0deg) at 50% 50%,rgba(255,255,255,.2) 0 5deg,transparent 5deg 12deg)}
  body{position:absolute!important;top:285px;left:0;border-radius:0}
  #band{position:absolute;left:0;right:0;top:40px;height:230px;display:flex;align-items:center;justify-content:center;z-index:5}
  #cap{background:#fff;border:6px solid #151a2c;border-radius:26px;box-shadow:8px 10px 0 #151a2c;padding:18px 34px;font:900 64px/1.15 "Noto Sans TC","Noto Sans KR",sans-serif;color:#151a2c;max-width:980px;text-align:center}
  #cap b{background:linear-gradient(transparent 55%,#fbe25b 55%)}
  #low{position:absolute;left:0;right:0;bottom:70px;text-align:center;z-index:5}
  #low .u{display:inline-block;background:#151a2c;color:#f8d34a;font:700 56px "IBM Plex Mono",monospace;padding:12px 34px;border-radius:20px}
  #flash{position:absolute;inset:0;background:#fff;opacity:0;z-index:9;pointer-events:none}
  .emo{position:absolute;font-size:120px;z-index:8;opacity:0}\`;
  H.appendChild(st);
  for(const [id,h] of [['band','<div id="cap"></div>'],['low','<span class="u">thecrowdtape.com</span>'],['flash','']]){const d=document.createElement('div');d.id=id;d.innerHTML=h;H.appendChild(d)}
 }
 document.getElementById('cap').innerHTML=cap;
 document.querySelectorAll('.emo').forEach(e=>e.remove());
}
function prep(){
 const tl=[],q=(s)=>[...document.querySelectorAll(s)];
 window.__slam=null;
 const add=(el,type,start,dur)=>{if(el)tl.push({el,type,start,dur:dur||350,txt:el.textContent})};
 add(document.getElementById('cap'),'wob',0,500);
 add(document.querySelector('.date'),'pop',150);
 add(document.querySelector('.pg'),'pop',250);
 let t=350;
 q('#in .talk,#in .kick,#in .win,#in .lead').forEach(e=>{add(e,'pop',t);t+=120});
 const big=document.querySelector('#in .big');
 if(big){add(big,'slam',t+50,300);window.__slam=t+350;['🔥','🚀','👀','💥'].forEach((em,i)=>{const d=document.createElement('div');d.className='emo';d.textContent=em;document.documentElement.appendChild(d);tl.push({el:d,type:'fly',start:t+350+i*60,dur:900,i})});add(big.querySelector('span'),'hl',t+350,400);t+=600}
 q('#in .sub').forEach(e=>{add(e,'count',t,600);t+=250});
 q('#in .pill').forEach(e=>{if(!e.closest('.card')){add(e,'pop',t);t+=150}});
 q('#in .bar').forEach(e=>{add(e,'grow',t,600);t+=300});
 q('#in .chart').forEach(e=>{add(e,'pop',t);add(e.querySelector('polyline'),'draw',t+150,900);t+=300});
 q('#in .stat').forEach(e=>{add(e,'count',t,500);add(e,'pop',t);t+=150});
 q('#in .cvq').forEach(e=>{add(e,'right',t,450);t+=220});
 q('#in .acc').forEach(e=>{add(e,'right',t,400);t+=250});
 q('#in .badge').forEach(e=>{add(e,'stamp',t,300);t+=300});
 q('#in .sec h2').forEach(e=>{const sec=e.closest('.sec');add(e,'pop',t);t+=200;
   if(sec)[...sec.querySelectorAll('.card')].forEach(c=>{add(c,'drop',t,400);add(c.querySelector('polyline'),'draw',t+250,700);t+=200});});
 q('#in .row').forEach(e=>{add(e,'right',t,400);t+=200});
 q('#in .box:not(.cvq)').forEach(e=>{add(e,'right',t,450);t+=250});
 q('#in .cta').forEach(e=>{add(e,'bounce',Math.max(t,2900),600)});
 q('#in .swipe').forEach(e=>{add(e,'bounce',Math.max(t,2700),600)});
 tl.forEach(x=>{if(x.type==='draw'){const L=x.el.getTotalLength();x.L=L;x.el.style.strokeDasharray=L}
   if(x.type==='hl'){x.el.style.backgroundRepeat='no-repeat'}
   if(x.type!=='draw'&&x.type!=='hl'&&x.type!=='count'){x.base=getComputedStyle(x.el).transform;if(x.base==='none')x.base=''}});
 window.__tl=tl;
}
function ev(){return window.__tl.map(x=>({type:x.type,start:x.start}))}
const cl=v=>Math.max(0,Math.min(1,v)), back=p=>{const c=1.7;return 1+(c+1)*Math.pow(p-1,3)+c*Math.pow(p-1,2)}, out=p=>1-Math.pow(1-p,3);
function seek(ms){
 const m=document.getElementById('main'), all=document.body;
 
 m.style.transform='scale('+(1+0.045*cl(ms/4000))+')';
 document.documentElement.style.setProperty('--rot',(ms/40)+'deg');
 const sl=window.__slam, fl=document.getElementById('flash');
 if(sl!=null&&ms>=sl&&ms<sl+300){const k=1-(ms-sl)/300;all.style.transform='translate('+(Math.sin(ms*.9)*22*k)+'px,'+(Math.cos(ms*1.3)*16*k)+'px)';fl.style.opacity=.55*k}else{all.style.transform='';fl.style.opacity=0}
 for(const x of window.__tl){const p=cl((ms-x.start)/x.dur),e=x.el,b=x.base||'';
  if(x.type==='draw'){e.style.strokeDashoffset=x.L*(1-out(p));continue}
  if(x.type==='hl'){e.style.backgroundSize=(out(p)*100)+'% 100%';continue}
  if(x.type==='count'){e.style.opacity=p>0?1:0;e.textContent=x.txt.replace(/\\d+/,n=>Math.round(+n*out(p)));continue}
  if(x.type==='pop'){e.style.opacity=p>0?1:0;e.style.transform=b+' scale('+(p>0?0.3+0.7*back(p):0.3)+')';continue}
  if(x.type==='slam'){e.style.opacity=p>0?1:0;e.style.transform=b+' scale('+(2.6-1.6*out(p))+')';continue}
  if(x.type==='stamp'){e.style.opacity=p>0?1:0;e.style.transform=b+' scale('+(2-1*back(p))+')';continue}
  if(x.type==='right'){e.style.opacity=p>0?1:0;e.style.transform=b+' translateX('+((1-out(p))*110)+'%)';continue}
  if(x.type==='drop'){e.style.opacity=p;e.style.transform=b+' translateY('+((1-back(p))*-60)+'px)';continue}
  if(x.type==='grow'){e.style.transformOrigin='left center';e.style.transform=b+' scaleX('+out(p)+')';continue}
  if(x.type==='wob'){e.style.opacity=p>0?1:0;e.style.transform='scale('+(0.4+0.6*back(p))+') rotate('+(Math.sin(ms/260)*2.5)+'deg)';continue}
  if(x.type==='fly'){const a=[[-1,-1],[1,-1],[-1,1],[1,1]][x.i];e.style.opacity=p>0&&p<1?1-p*p:0;e.style.left=(470+a[0]*(80+380*out(p)))+'px';e.style.top=(700+a[1]*(60+330*out(p)))+'px';e.style.transform='scale('+(0.5+out(p))+') rotate('+(a[0]*p*60)+'deg)';continue}
  if(x.type==='bounce'){e.style.opacity=p>0?1:0;e.style.transform=b+' scale('+(p>0?1+0.15*Math.sin(p*Math.PI*2)*(1-p)+(p<.2?-.5*(1-p/.2):0):0.5)+')';continue}
 }
}`;
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  await p.goto('file://' + path.join(REPO, 'tools/carousel.html'), { waitUntil: 'networkidle' });
  await p.addScriptTag({ content: ANIM });
  let f = 0; const events = [];
  const CAPS = [S => `全場最多人講 👉 <b>$${S.big}</b>`, S => '🔥 熱度 Top 4，邊隻上榜？', S => '大神一齊睇好 🟢 定睇淡 🔴？', S => '⚔️ 好淡開戰！你企邊邊？'];
  for (let i = 0; i < 4; i++) {
    await p.evaluate(([l, t, d, n, s]) => render(l, t, d, n, s), [job.lang, job.theme, job.date, i + 1, job.slides[i]]);
    await p.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map(i => i.decode().catch(() => {}))); });
    await p.evaluate(() => { const room = document.getElementById('main').clientHeight, box = document.getElementById('in'); let k = 1;
      while (box.getBoundingClientRect().height > room + 2 && k > 0.6) { k -= 0.05; box.style.zoom = k; } });
    await p.evaluate(([l,c]) => { frame(l,c); document.body.style.transform=''; document.getElementById('main').style.transform=''; prep(); }, [lang, CAPS[i](job.slides[i])]);
    events.push(...(await p.evaluate(() => ev())).map(e => ({ ...e, slide: i })));
    for (let k = 0; k < N; k++) {
      await p.evaluate(ms => seek(ms), k * 1000 / FPS);
      await p.screenshot({ path: path.join(tmp, (i + 1) + '-' + String(k).padStart(3, '0') + '.jpg'), type: 'jpeg', quality: 90 });
    }
  }
  // intro (2s) and outro (2.5s): full-screen punchy cards
  const logo = 'data:image/png;base64,' + fs.readFileSync(path.join(REPO, 'tools/logo.png')).toString('base64');
  const card = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  await card.setContent(`<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@700&family=Noto+Sans+TC:wght@900&display=block">
  <style>body{margin:0;width:1080px;height:1920px;overflow:hidden;position:relative;font-family:'Noto Sans TC',sans-serif;background:linear-gradient(160deg,#ffb020,#ff6aa8)}
  .r{position:absolute;inset:-400px;background:repeating-conic-gradient(from var(--rot,0deg) at 50% 50%,rgba(255,255,255,.25) 0 6deg,transparent 6deg 14deg)}
  .l{position:absolute;left:60px;right:60px;text-align:center;font-weight:900;color:#151a2c;opacity:0}
  .s{display:inline-block;background:#fff;border:7px solid #151a2c;border-radius:30px;box-shadow:10px 12px 0 #151a2c;padding:20px 40px}
  .y{background:#f8d34a}.k{background:#151a2c;color:#f8d34a;font-family:'IBM Plex Mono',monospace}</style>
  <div class="r"></div><div id="c"></div>`, { waitUntil: 'networkidle' });
  const scene = async (name, lines, n) => {
    await card.evaluate(L => { document.getElementById('c').innerHTML = L.map(x => `<div class="l" style="top:${x.y}px;font-size:${x.f}px"><span class="s ${x.c||''}" style="transform:rotate(${x.r||0}deg)">${x.h}</span></div>`).join(''); }, lines);
    await card.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map(i => i.decode().catch(() => {}))); });
    for (let k = 0; k < n; k++) {
      await card.evaluate(([ms, L]) => {
        document.body.style.setProperty('--rot', (ms / 25) + 'deg');
        [...document.querySelectorAll('.l')].forEach((e, i) => { const p = Math.max(0, Math.min(1, (ms - L[i].t) / 350)), c = 1.7, bk = p ? 1 + (c + 1) * Math.pow(p - 1, 3) + c * Math.pow(p - 1, 2) : 0;
          e.style.opacity = p > 0 ? 1 : 0; e.style.transform = `scale(${0.3 + 0.7 * bk}) rotate(${Math.sin(ms / 200 + i) * 2}deg)`; });
      }, [k * 1000 / FPS, lines]);
      await card.screenshot({ path: path.join(tmp, name + '-' + String(k).padStart(3, '0') + '.jpg'), type: 'jpeg', quality: 90 });
    }
  };
  const I = { zh: ['X 上面 200 個美股大神', '今日<br>最多人講邊隻？👀', '30 秒話你知 ⏱️'], en: ['200 top US-stock voices on X', 'Which stock did they<br>talk about most? 👀', 'Find out in 15s ⏱️'], ko: ['X의 미국주식 고수 200명', '오늘 가장 많이<br>얘기한 종목은? 👀', '15초 만에 확인 ⏱️'] }[lang];
  I[2] = I[2].replace('30', '20').replace('15s', '20s');
  await scene(0, [{ h: `<img src="${logo}" style="width:150px;height:150px;border-radius:30px;vertical-align:middle">`, y: 260, f: 40, t: 0 },
    { h: I[0], y: 560, f: 66, t: 150, r: -2 }, { h: I[1], y: 820, f: 100, t: 550, c: 'y', r: 2 }, { h: I[2], y: 1300, f: 60, t: 1050, c: 'k', r: -3 }], 48);
  const O = { zh: ['想睇晒全部？👇', '免費・唔使登入', '每 4 小時自動更新', 'Follow @thecrowdtape 🔔', '⚠️ 唔構成投資建議'], en: ['Want the full picture? 👇', 'Free · No login', 'Updated every 4 hours', 'Follow @thecrowdtape 🔔', '⚠️ Not investment advice'], ko: ['전체가 궁금하다면 👇', '무료 · 로그인 없음', '4시간마다 자동 업데이트', 'Follow @thecrowdtape 🔔', '⚠️ 투자 조언 아님'] }[lang];
  await scene(5, [{ h: O[0], y: 330, f: 80, t: 0, r: -2 }, { h: 'thecrowdtape.com', y: 640, f: 72, t: 300, c: 'k', r: 2 }, { h: O[1], y: 900, f: 58, t: 650 },
    { h: O[2], y: 1080, f: 58, t: 850 }, { h: O[3], y: 1330, f: 60, t: 1150, c: 'y', r: -2 }, { h: O[4], y: 1650, f: 40, t: 1400 }], 60);
  await b.close();
  fs.writeFileSync(path.join(__dirname, 'events.json'), JSON.stringify(events));
  execFileSync('python3', [path.join(__dirname, 'audio.py'), path.join(__dirname, 'events.json'), path.join(__dirname, 'audio.wav')], { stdio: 'inherit' });
  // segments: 0 intro 2s, 1-4 slides 4s, 5 outro 2.5s; 0.3s slide-left between each
  const len = [2, 4, 4, 4, 4, 2.5], X = 0.3, ins = [];
  for (let i = 0; i < 6; i++) ins.push('-framerate', String(FPS), '-i', path.join(tmp, i + '-%03d.jpg'));
  let fc = '', last = '[0:v]', off = 0;
  for (let i = 1; i < 6; i++) { off += len[i - 1] - X; const o = i === 5 ? '[v]' : `[x${i}]`; fc += `${last}[${i}:v]xfade=transition=${i === 5 ? 'zoomin' : 'slideleft'}:duration=${X}:offset=${off.toFixed(3)}${o};`; last = o; }
  fc += '[v]format=yuv420p[vo]';
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', ...ins, '-i', path.join(__dirname, 'audio.wav'), '-filter_complex', fc, '-map', '[vo]', '-map', '6:a',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-r', String(FPS), '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', out], { stdio: 'inherit' });
  console.log('wrote', out);
})();
