// Full-screen scenes of the carousel motion videos (hook, reveal, bull-vs-bear, outro), loaded by
// tools/carousel_video.js into a blank 1080x1920 page together with tools/carousel_scene.html.
// setup(name, data) builds a scene, draw(t, globalT) draws one frame. Needs cl/out/back/BEAT/chrome
// from the shared header that carousel_video.js injects first.
const esc=v=>String(v==null?'':v).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function coverHTML(D){
 const block=(label,ticker,extra)=>{
  if(!ticker)return '';
  const sz=String(ticker).length>5?128:168;
  return `<div class="cv-block"><div class="cv-l">${esc(label)}</div><div class="cv-tk" style="font-size:${sz}px">$<span>${esc(ticker)}</span></div>${extra?`<div class="cv-n">${esc(extra)}</div>`:''}</div>`;
 };
 const px=[...String(D.title||'')].length<=4?128:104;
 return `<div id="cover"><div class="cv-dots"></div>
  <div class="cv-top"><span class="cv-brand"><img src="logo.png" alt="">The Crowd Tape</span>${D.date?`<span class="cv-date">📅 ${esc(D.date)}</span>`:''}</div>
  <div class="cv-panel"><div class="cv-title" style="font-size:${px}px"><span>${esc(D.title)}</span></div>
   ${block(D.discussedL,D.discussed,D.discussedN)}${block(D.bullL,D.bull,D.bullN)}
   ${D.posted?`<div class="cv-stat">${esc(D.posted)}</div>`:''}</div>
  <div class="cv-foot"><span><b>@thecrowdtape</b> · thecrowdtape.com</span><span>${esc(D.foot||'')}</span></div></div>`;
}
function setup(name,D){
 window.D_=D;
 const c=document.getElementById('c'); c.innerHTML=''; c.style.transform='';
 const add=(h,y,size,cls,rot)=>{const d=document.createElement('div');d.className='t';d.style.top=y+'px';d.style.fontSize=size+'px';d.innerHTML='<span class="'+(cls||'')+'" style="display:inline-block;transform:rotate('+(rot||0)+'deg)">'+h+'</span>';c.appendChild(d);return d};
 window.S={name,D,els:[]};
 if(name==='cover'){document.getElementById('bg').style.background='linear-gradient(160deg,#5ab8ff 0%,#8f7bff 100%)';c.innerHTML=coverHTML(D);return;}
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
   for(let i=0;i<60;i++){const d=document.createElement('div');d.className='cf';d.style.background=['#f8d34a','#5ee08f','#ff8a8a','#5ab8ff','#fff'][i%5];d.dataset.x=Math.random()*1080;d.dataset.v=0.6+Math.random();d.dataset.r=Math.random()*360;c.insertBefore(d,c.firstChild);S.els.push(d)}}
}
const HOOKBG=['#151a2c','#8f7bff','#ff4f6d','#ffd84d','#5ab8ff'];
function draw(t,gt){
 const pulse=chrome(gt), beat=Math.floor(t/BEAT), bt=(t%BEAT)/BEAT, E=S.els, bg=document.getElementById('bg'), fl=document.getElementById('flash'), c=document.getElementById('c');
 document.body.style.setProperty('--rot',(gt*40)+'deg'); fl.style.opacity=0; let shake=0;
 if(S.name==='cover'){bg.style.background='linear-gradient(160deg,#5ab8ff 0%,#8f7bff 100%)';c.style.transform='none';return;}
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
}
