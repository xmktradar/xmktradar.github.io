function prep(){
 const tl=[],q=(s)=>[...document.querySelectorAll(s)];
 window.__slam=null;
 const add=(el,type,start,dur)=>{if(el)tl.push({el,type,start,dur:dur||350,txt:el.textContent})};
 
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

function seek(ms){
 const m=document.getElementById('main'), all=document.body;
 

 for(const x of window.__tl){const p=cl((ms-x.start)/x.dur),e=x.el,b=x.base||'';
  if(x.type==='draw'){e.style.strokeDashoffset=x.L*(1-out(p));continue}
  if(x.type==='hl'){e.style.backgroundSize=(out(p)*100)+'% 100%';continue}
  if(x.type==='count'){e.style.opacity=p>0?1:0;e.textContent=x.txt.replace(/\d+/,n=>Math.round(+n*out(p)));continue}
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
}

function setupSlide(cap,idx){
 const H=document.documentElement;
 if(!document.getElementById('band')){
  const st=document.createElement('style');st.textContent=`html{width:1080px;height:1920px;overflow:hidden;background:#151a2c;position:relative}
  html::before{content:'';position:absolute;inset:-400px;background:repeating-conic-gradient(from var(--rot,0deg) at 50% 50%,rgba(255,255,255,.12) 0 6deg,transparent 6deg 14deg)}
  body{position:absolute!important;top:285px;left:0;transform-origin:0 0}
  #band{position:absolute;left:0;right:0;top:70px;display:flex;justify-content:center;z-index:20}
  #cap{background:#f8d34a;border:8px solid #151a2c;border-radius:30px;box-shadow:10px 12px 0 #151a2c;padding:16px 36px;font:900 72px/1.15 "Noto Sans TC","Noto Sans KR",sans-serif;color:#151a2c;max-width:1000px;text-align:center}
  #low{position:absolute;left:0;right:0;bottom:60px;text-align:center;z-index:20}
  #low span{display:inline-block;background:#151a2c;color:#f8d34a;font:700 54px "IBM Plex Mono",monospace;padding:10px 30px;border-radius:18px;border:5px solid #f8d34a}
  #flash{position:absolute;inset:0;background:#fff;opacity:0;z-index:40;pointer-events:none}
  .emo{position:absolute;font-size:140px;z-index:30;opacity:0}`;
  H.appendChild(st);
  for(const [id,h] of [['band','<div id="cap"></div>'],['low','<span>thecrowdtape.com</span>'],['flash','']]){const d=document.createElement('div');d.id=id;d.innerHTML=h;H.appendChild(d)}
 }
 document.getElementById('cap').innerHTML=cap;
 document.querySelectorAll('.emo').forEach(e=>e.remove());
 document.body.style.transform='';document.getElementById('main').style.transform='';
 // spotlight targets (whole card always visible; no zoom)
 const q=sel=>typeof sel==='string'?document.querySelector('#in '+sel):sel;
 const cards=[...document.querySelectorAll('#in .card')], secs=[...document.querySelectorAll('#in .sec')];
 const K=[
  [[0,null],[.12,'.big'],[.5,'.cvr'],[.85,null]],
  [[0,null],[.15,cards[0]],[.33,cards[1]],[.51,cards[2]],[.69,cards[3]],[.87,null]],
  [[0,null],[.2,secs[0]],[.6,secs[1]],[.9,null]],
  [[0,null],[.6,'.cta'],[1,'.cta']]][idx];
 window.__spot=K.map(([f,s])=>({f,el:s?q(s):null}));
 window.__spotAll=[...new Set([...cards,...secs,...document.querySelectorAll('#in .cvr,#in .big,#in .cta,#in .cv,#in .stats,#in .kick,#in .win,#in .lead,#in .sub,#in .pills,#in .chart,#in .swipe')])];
 prep();
 return window.__tl.map(x=>({type:x.type,start:x.start}));
}
const io=p=>p<.5?4*p*p*p:1-Math.pow(-2*p+2,3)/2;
function drawSlide(t,gt,dur){
 chrome(gt); const ms=t*1000*1.35, f=t/dur;
 document.documentElement.style.setProperty('--rot',(gt*30)+'deg');
 let tx=0,ty=0;
 const sl=window.__slam, fl=document.getElementById('flash'); fl.style.opacity=0;
 if(sl!=null&&ms>=sl&&ms<sl+400){const q=1-(ms-sl)/400;tx=Math.sin(ms*.9)*18*q;ty=Math.cos(ms*1.3)*14*q;fl.style.opacity=.6*q}
 if(t<.08)fl.style.opacity=.5*(1-t/.08);
 document.body.style.transform='translate('+tx+'px,'+ty+'px)';
 const cap=document.getElementById('cap'),cp=cl(t/.25);cap.style.transform='scale('+(0.3+0.7*back(cp))+') rotate('+(Math.sin(gt*5)*2)+'deg)';
 seek(ms);
 // spotlight: current target glows yellow, the rest dims a little
 const S=window.__spot; let k=0; while(k<S.length-1&&f>=S[k+1].f)k++;
 const cur=S[k].el, since=(f-S[k].f)*dur, gl=cl(since/.2);
 for(const e of window.__spotAll){ if(e===cur||(cur&&(cur.contains(e)||e.contains(cur)))){continue} e.style.filter=cur?'brightness(.6) saturate(.7)':''; }
 if(cur){cur.style.filter='';cur.style.position=cur.style.position||'relative';cur.style.zIndex=5;
   const pulse=1+Math.sin(gt*Math.PI*2/BEAT)*.5;
   cur.style.boxShadow='0 0 0 '+(8*gl)+'px #f8d34a, 0 0 '+(30+20*pulse)*gl+'px '+(10*gl)+'px rgba(248,211,74,.85)';cur.style.borderRadius=cur.style.borderRadius||'22px';}
 for(const s of S) if(s.el&&s.el!==cur){s.el.style.boxShadow='';s.el.style.zIndex='';}
}
