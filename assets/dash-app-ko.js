'use strict';
(async function(){
const parseJSON=function(raw){return new Promise(function(resolve){try{if(typeof Worker==='undefined'){resolve(JSON.parse(raw));return}var u=URL.createObjectURL(new Blob(['onmessage=function(e){try{postMessage({ok:1,d:JSON.parse(e.data)})}catch(err){postMessage({ok:0})}}'],{type:'text/javascript'}));var w=new Worker(u);var done=false;var fin=function(d){if(done)return;done=true;try{w.terminate()}catch(e){}try{URL.revokeObjectURL(u)}catch(e){}resolve(d)};w.onmessage=function(e){fin(e.data&&e.data.ok?e.data.d:JSON.parse(raw))};w.onerror=function(){fin(JSON.parse(raw))};w.postMessage(raw);setTimeout(function(){fin(JSON.parse(raw))},2500)}catch(e){resolve(JSON.parse(raw))}})};
const y=function(){return new Promise(function(r){if(typeof scheduler!=='undefined'&&typeof scheduler.yield==='function'){scheduler.yield().then(r,r);return}if(typeof MessageChannel==='function'){var c=new MessageChannel();c.port1.onmessage=function(){r()};c.port2.postMessage(0)}else setTimeout(r,0)})};
await y();

// 儀表板｜結構與計算依照設計稿（奶油風格）；資料全部來自內嵌資料
const D=await parseJSON((document.getElementById('dash-data')||{textContent:'{}'}).textContent);
await y();
if(!D.prices)D.prices={};if(!D.accounts)D.accounts={};if(!D.posts)D.posts=[];if(!D.intraday)D.intraday={};if(!D.avmini)D.avmini={};if(!D.quotes)D.quotes={};
const DAY=864e5, MIN_POSTS=D.meta.min_daily_posts||8, HANDLES=D.meta.handles||[];
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const S_OF={'睇好':'bull','睇淡':'bear','中性':'neu'};
const SLABEL={bull:'강세',bear:'약세',neu:'중립',none:'입장 없음'};
const SCHAR={bull:'강',bear:'약',neu:'중',none:'?'};
const TRADE_RE=/買進|買入|賣出|加倉|減倉|持倉|持有|建倉|平倉|清倉|資金|流入|流出|部位|倉位|增發/;
const OV=D.overrides||{};const UNC=t=>!!(OV[t]&&OV[t].unconfirmed);
let ACCINFO=D.accounts||{};
function accInfo(h){if(ACCINFO[h])return ACCINFO[h];const k=Object.keys(ACCINFO).find(k=>k.toLowerCase()===h.toLowerCase());return k?ACCINFO[k]:{}}
let NAMES={};D.posts.forEach(p=>{if(p.name&&!p.reposted_by)NAMES[p.handle]=p.name});
const nameOf=h=>accInfo(h).name||NAMES[h]||h;

// ---------- 日期（全部以 HKT 計） ----------
const hkDate=ms=>new Date(ms+8*36e5).toISOString().slice(0,10);
const hkMs=d=>Date.parse(d+'T00:00:00+08:00');
const addDays=(d,n)=>hkDate(hkMs(d)+n*DAY+12*36e5);
const fmt=d=>`${+d.slice(5,7)}/${+d.slice(8,10)}`;
const fmtFull=d=>d;
const hm=ms=>new Date(ms+8*36e5).toISOString().slice(11,16);
let CUT=D.meta.cutoff_hkt?Date.parse(D.meta.cutoff_hkt):Math.max(0,...D.posts.map(p=>Date.parse(p.time_utc)));
let TODAY=hkDate(CUT);

// ---------- 把貼文展開成「帖 × 股票」觀點（等同設計稿的 POSTS，一帖一股） ----------
// 股票＝貼文標出的代號 ∪ 分析師逐股立場（stance_by_ticker）裡的代號
// 一律中文：只用寫手 zh_summary／中文 summary_zh，永不顯示英文原文（讀者撳「原始貼文」睇原文）
// /en/ and /ko/ put the English original or the Korean summary in zh_summary: any text counts there
const PAGE_LANG=document.documentElement.lang||'';
const HAS_ZH=s=>typeof s==='string'&&(/^zh/.test(PAGE_LANG)?/[\u3400-\u9fff]/:/\S/).test(s);
let ALLP=[];
{
const _ps=D.posts;
for(let _i=0;_i<_ps.length;_i++){
const p=_ps[_i];
ALLP.push({...p,text:undefined,summary_zh:HAS_ZH(p.zh_summary)?p.zh_summary:HAS_ZH(p.summary_zh)?p.summary_zh:'',tokenize:HAS_ZH(p.zh_summary)&&PAGE_LANG!=='en'?false:p.tokenize,tickers:[...new Set([...(p.tickers||[]),...Object.keys(p.stance_by_ticker&&typeof p.stance_by_ticker==='object'?p.stance_by_ticker:{})].map(t=>String(t).replace(/^\$/,'').toUpperCase()))],ms:Date.parse(p.time_utc),acc:p.reposted_by||p.handle,date:p.time_hkt.slice(0,10)});
if((_i&7)===7)await y();
}
ALLP.sort((a,b)=>a.ms-b.ms);
}
await y();
const valid=p=>!p.folded_into&&p.theme!=='非市場';
// 立場一律按個股讀 stance_by_ticker（唔用整篇帖立場）；冇標示＝未表態
function stanceOf(p,t){const m=p.stance_by_ticker&&typeof p.stance_by_ticker==='object'?p.stance_by_ticker:null;if(!m)return p.stance&&S_OF[p.stance]?{s:S_OF[p.stance],star:true}:{s:'none',star:false};const k=Object.keys(m).find(x=>String(x).replace(/^\$/,'').toUpperCase()===t);return {s:k?(S_OF[m[k]]||'none'):'none',star:false}}
let POSTS=[];
{
const _vp=ALLP.filter(valid);
for(let _i=0;_i<_vp.length;_i++){
const p=_vp[_i];
for(let _j=0;_j<p.tickers.length;_j++){
const t=p.tickers[_j];const r=stanceOf(p,t);
POSTS.push({p,t,acc:p.acc,s:r.s,star:r.star,ms:p.ms,d:p.date,kind:p.basis||null,why:p.summary_zh||'',url:p.url})
}
if((_i&7)===7)await y();
}
}
await y();
let TICKERS=[...new Set(POSTS.map(x=>x.t))].sort();
await y();
const explicit=s=>s==='bull'||s==='bear';
const stanced=s=>s!=='none';

// ---------- 計算（對應設計稿 postsIn / latest / prevStance / change / dist / agreeLabel / dailyWindow） ----------
// 範圍可以係日期（YYYY-MM-DD）或時間點（YYYY-MM-DDTHH:MM，HKT，包頭包尾）
const RK=new Map();const rk=(v,end)=>{let t=RK.get(v);if(t===undefined){t=Date.parse(v+':00+08:00');RK.set(v,t)}return t+(end?59999:0)};// 快取：每個帖文都會比較時間窗，Date.parse 太慢
const inR=(d,ms,from,to)=>from.length>10?(ms>=rk(from)&&ms<=rk(to,true)):(d>=from&&d<=to);
const tsOf=ms=>hkDate(ms)+'T'+hm(ms);
const fmtR=v=>v.length>10?`${fmt(v)} ${v.slice(11,16)}`:fmt(v);
// 快取：同一個時間窗會被問好多次（每個帳號 × 每隻股票），每次重新篩全部帖文令開頁好慢；POSTS 一變（rebuildDerived）就清空
let WIN=new Map();const winOf=(from,to)=>{const k=from+'|'+to;let w=WIN.get(k);if(!w){w={xs:POSTS.filter(x=>inR(x.d,x.ms,from,to)),last:null,accs:null};WIN.set(k,w)}return w};
const postsIn=(from,to)=>winOf(from,to).xs.slice();
const rawIn=(from,to)=>ALLP.filter(p=>inR(p.date,p.ms,from,to));
function latest(acc,t,from,to){const w=winOf(from,to);if(!w.last){w.last=new Map();for(const x of w.xs){const k=x.acc+'\n'+x.t,r=w.last.get(k);if(!r||x.ms>=r.ms)w.last.set(k,x)}}return w.last.get(acc+'\n'+t)||null}
function prevStance(acc,t,beforeMs){let r=null;for(const x of POSTS)if(x.acc===acc&&x.t===t&&x.ms<beforeMs&&stanced(x.s)&&(!r||x.ms>r.ms))r=x;return r}
function change(prev,cur){if(!prev||!cur||!stanced(cur.s)||prev.s===cur.s)return null;if(explicit(prev.s)&&explicit(cur.s))return '반전';const rank={bear:0,neu:1,bull:2};return rank[cur.s]>rank[prev.s]?'강화':'약화'}
const chgOf=x=>change(prevStance(x.acc,x.t,x.ms),x);
function accsOf(from,to){const w=winOf(from,to);if(!w.accs)w.accs=[...new Set(w.xs.map(x=>x.acc))];return w.accs.slice()}
// 共識計算（一致程度、共同看多／看空、好淡分歧）計所有追蹤帳號
function dist(t,from,to,all){const c={bull:0,bear:0,neu:0,none:0,accs:0,mentions:0};accsOf(from,to).filter(a=>all||inCons(a)).forEach(a=>{const x=latest(a,t,from,to);if(x){c[x.s]++;c.accs++}});c.mentions=postsIn(from,to).filter(x=>x.t===t).length;return c}
function agreeLabel(c){const tot=c.bull+c.bear+c.neu+c.none;if(tot<2)return {l:'표본 부족',k:'neu'};if(c.bull>=1&&c.bear>=1&&Math.min(c.bull,c.bear)/(c.bull+c.bear)>=.25)return {l:'뚜렷한 엇갈림',k:'chg'};const r=Math.abs(c.bull-c.bear)/tot;if(r>=.6)return {l:c.bull>c.bear?'강한 일치 강세':'강한 일치 약세',k:c.bull>c.bear?'bull':'bear'};return {l:'부분 일치',k:'neu'}}
// 每日窗：優先用寫手分析第一行嘅時間範圍（同今日市場分析一致，包括 Truth Social）；
// 冇得讀就用同一個抓帖周期：最近一次抓帖時段之前 24 小時至資料截止
const SCRAPE_SLOTS=D.meta.scrape_slots_hkt||[];
function dailyWindow(){const sm=summaryOf('daily',TODAY);const win=sm&&!sm.stale&&sm.s.win;
 if(win&&win.from&&win.to){const n=rawIn(win.from,win.to).filter(valid).length;return {from:win.from,to:win.to,day:TODAY,timed:true,src:'writer',merged:false,n}}
 if(SCRAPE_SLOTS.length&&D.meta.cutoff_hkt){const cut=Date.parse(D.meta.cutoff_hkt.replace(' ','T')+':00+08:00');if(cut){
  const cands=[];[0,1].forEach(k=>SCRAPE_SLOTS.forEach(sl=>{const t=Date.parse(addDays(hkDate(cut),-k)+'T'+sl+':00+08:00');if(t<=cut)cands.push(t)}));
  const last=cands.length?Math.max(...cands):cut;const from=tsOf(last-DAY),to=tsOf(cut);const n=rawIn(from,to).filter(valid).length;
  if(n)return {from,to,day:TODAY,timed:true,src:'cycle',merged:false,n}}}
 return dailyWindowByDay()}
function dailyWindowByDay(){const n=rawIn(TODAY,TODAY).filter(valid).length;const y=addDays(TODAY,-1);const hasPrev=ALLP.some(p=>p.date<TODAY);return n<MIN_POSTS&&hasPrev?{from:y,to:TODAY,day:TODAY,merged:true,n}:{from:TODAY,to:TODAY,day:TODAY,merged:false,n}}
let DATES=[...new Set(ALLP.map(p=>p.date))].sort();
await y();

// ---------- 股價 ----------
function closes(t){if(UNC(t))return null;const p=D.prices[t];return p&&p.c&&p.c.length?p.c:null}
function pchg(t,days){const c=closes(t);if(!c)return null;const last=c[c.length-1];if(days==null)return (last[1]/c[0][1]-1)*100;const lim=new Date(Date.parse(last[0])-days*DAY).toISOString().slice(0,10);let base=null;for(const r of c){if(r[0]<=lim)base=r;else break}return base?(last[1]/base[1]-1)*100:null}
// 股價分檔：語言版本頁只帶最近 45 日收市價（prices[t].lite），撳入個股先載入 /px/<代號>.json 嘅完整股價同日內價
const PXFAIL={},PXBUSY={};
const pxWait=t=>!!(D.prices[t]&&D.prices[t].lite);
function loadPx(t){if(PXFAIL[t]||PXBUSY[t])return;PXBUSY[t]=1;
 fetch('/px/'+t.replace(/[^A-Za-z0-9.\-]/g,'_')+'.json?v='+encodeURIComponent((D.meta&&D.meta.build_id)||''))
  .then(r=>{if(!r.ok)throw new Error(r.status);return r.json()})
  .then(j=>{const p=D.prices[t];if(j.c&&j.c.length)p.c=j.c;delete p.lite;if(j.intra)INTRA[t]=j.intra})
  .catch(()=>{PXFAIL[t]=1})
  .finally(()=>{PXBUSY[t]=0;const m=decodeURIComponent(location.hash.slice(1)).match(/^stock[\/-](.+)$/);if(m&&m[1].toUpperCase()===t){const el=document.getElementById('dive'),y=el.scrollTop;openDive(t);el.scrollTop=y}})}
function closeOn(t,d){const c=closes(t);if(!c)return null;let r=null;for(const x of c){if(x[0]<=d)r=x;else break}return r}
const money=v=>v==null?'—':(v>=1000?v.toLocaleString('en-US',{maximumFractionDigits:2}):v.toFixed(2));
// 非美元報價（例如澳交所）：清楚標示貨幣與交易日
const CURNAME={USD:'미국 달러',AUD:'호주 달러',HKD:'홍콩 달러',CAD:'캐나다 달러',GBP:'영국 파운드',EUR:'유로',JPY:'일본 엔'};
const curOf=t=>((D.prices[t]&&D.prices[t].currency)||(OV[t]&&OV[t].currency)||'USD').toUpperCase();
const isUS=t=>!(OV[t]&&(OV[t].exchange&&!/^(NYSE|NASDAQ|AMEX|NYSEARCA|US)$/i.test(OV[t].exchange)||OV[t].symbol&&OV[t].symbol.includes('.')));
const tradeDay=t=>isUS(t)?'미국 동부 거래일':((OV[t]&&OV[t].exchange)||'현지')+'  거래일';
const moneyT=(t,v)=>{const c=curOf(t);return c==='USD'?money(v):`${money(v)} ${CURNAME[c]||c}`};
// 市值／類別標籤（中性色）：美股市值 < $50B →「細價股（市值 < $50B）」；ETF →「ETF」；沒有資料就不顯示
const QT=t=>(D.quotes||{})[t]||null;
const capKind=t=>{if(UNC(t)||!isUS(t))return null;const q=QT(t);if(!q)return null;if(q.type==='ETF')return 'etf';if(q.type==='MUTUALFUND')return 'fund';if(q.type==='EQUITY'&&typeof q.mcap==='number'&&q.mcap<50e9)return 'small';return null};
const CAPTXT={small:'소형주(시가총액 < $50B)',etf:'ETF',fund:'펀드'},CAPSHORT={small:'소형주',etf:'ETF',fund:'펀드'};
const capTag=t=>{const k=capKind(t);return k?`<span class="flag small-cap" title="${k==='small'?'시가총액 약 $'+(QT(t).mcap/1e9).toFixed(1)+'B (Yahoo Finance, '+esc(QT(t).date||'')+')':''}">${CAPTXT[k]}</span>`:''};
const OVN=t=>{const o=OV[t];if(!o||o.unconfirmed)return '';const tags=[];if(o.note)tags.push(`<span class="pill unc">${esc(o.note)}</span>`);else if(!isUS(t))tags.push('<span class="pill unc">비미국</span>');return tags.join(' ')};
const UNC_TXT='<span class="pill unc" title="티커가 모호할 수 있어 어느 종목인지 확인하지 못했다">티커 미확인</span>';
const pctCell=(t,days)=>{if(UNC(t))return UNC_TXT;const v=pchg(t,days);return v==null?'<span class="note">주가 데이터 없음</span>':signed(+v.toFixed(1))+'%'};

// ---------- 小元件 ----------
const tkBtn=t=>{const o=OV[t];const tip=o&&!o.unconfirmed&&o.note?` title="${esc(o.note)}"`:'';const ck=capKind(t);const x=o&&!o.unconfirmed&&!isUS(t)?`<small class="xch">${esc(o.exchange||'비미국')}</small>`:(ck?` <span class="flag small-cap" title="${CAPTXT[ck]}">${CAPSHORT[ck]}</span>`:'');const fl=(FLAGS[t]||[]).map(flagSpan).join('');return `<button class="tk" data-tk="${esc(t)}"${tip}>${esc(t)}${x}${fl}</button>`};
const accLink=h=>`<a class="handle" href="${xUrl(h)}" target="_blank" rel="noopener">@${esc(h)}</a>${platTag(h)}`;
const accIn=h=>`<a class="accin" href="#account/${encodeURIComponent(h)}" title="보기: @${esc(h)}  (이 페이지 관점)" aria-label="보기: @${esc(h)}  (이 페이지 관점)">관점 ›</a>`;
const pill=(s,star)=>`<span class="pill ${s}"${star?' title="다종목 게시물: 분석가가 게시물 전체 입장만 표시해 게시물 내 모든 종목에 적용했다"':''}>${SLABEL[s]}${star?'＊':''}</span>`;
const distBar=c=>{const tot=c.bull+c.neu+(c.none||0)+c.bear||1;return `<div class="bar" title="강세 ${c.bull} · 중립 ${c.neu} · 입장 없음 ${c.none||0} · 약세 ${c.bear}"><span class="b" style="width:${c.bull/tot*100}%"></span><span class="m" style="width:${c.neu/tot*100}%"></span><span class="u" style="width:${(c.none||0)/tot*100}%"></span><span class="r" style="width:${c.bear/tot*100}%"></span></div>`};
const signed=v=>`<span class="${v>0?'up':v<0?'dn':''}">${v>0?'+':''}${typeof v==='number'&&!Number.isInteger(v)?v.toFixed(1):v}</span>`;
const legend=`<div class="legend"><span><i class="sw b"></i>강세</span><span><i class="sw m"></i>중립</span><span><i class="sw u"></i>입장 없음</span><span><i class="sw r"></i>약세</span></div>`;
const empty=t=>`<div class="empty">${t}</div>`;
const vsPrev=(a,b,has,lab)=>{if(!has)return '';const d=a-b,n=Math.abs(d),base=lab||' (이전 대비)';
 const L=PAGE_LANG;
 if(d===0)return L==='en'?`unchanged (${base})`:L==='ko'?`변동 없음 (${base})`:`與${base}相同`;
 if(L==='en')return d>0?`${n} more (${base})`:`${n} fewer (${base})`;
 if(L==='ko')return d>0?`${n} 증가 (${base})`:`${n} 감소 (${base})`;
 return d>0?`${base}: 多 ${n}`:`${base}: 少 ${n}`;};// 冇前期資料就留空：頁頂「昨日重疊 vs 今日」負責比較
function whyLine(p){const k=[p.basis,p.horizon].filter(Boolean).map(esc);const extra=[];if(p.specific===true)extra.push('<span class="chip spec">구체적</span>');if(TRADE_RE.test(p.summary_zh||''))extra.push('<span class="chip claim" title="게시물에 언급된 거래 및 자금 기록은 검증되지 않았다">게시물 주장 기준</span>');
 return `<p class="why">근거: ${k.length?`<b>${k[0]}</b>${k.slice(1).map(x=>' · '+x).join('')}`:'<span class="note">분석가 미표시</span>'} ${extra.join(' ')}</p>`}
let FOLD={};ALLP.forEach(p=>{if(p.folded_into)(FOLD[p.folded_into]=FOLD[p.folded_into]||[]).push(p)});
// 一帖可提及多隻股票：每隻股票各自顯示立場與變化
function postHtml(p,focusT){const xs=POSTS.filter(x=>x.p===p&&(!focusT||x.t===focusT));
 const tags=xs.length?xs.map(x=>{const ch=chgOf(x);return `${tkBtn(x.t)} ${pill(x.s,x.star)}${ch?` <span class="pill chg">${ch}</span>`:''}`}).join(' '):pill(p.stance?S_OF[p.stance]:'none');
 const fold=(FOLD[p.url]||[]).map(f=>`<a href="${esc(f.url)}" target="_blank" rel="noopener">이미지 게시물 ↗</a>`).join(' ');
 const pap=p.price_at_post?Object.entries(p.price_at_post).filter(([t])=>!focusT||t===focusT).map(([t,v])=>`$${esc(t)} ${esc(v)}`).join(', '):'';
 const xu=xUrl(p.acc);
 return `<div class="post"><div><a class="post-who" href="${xu}" target="_blank" rel="noopener">${avImg(p.acc,'post-av')}<span><b>${esc(nameOf(p.acc))}</b><small>@${esc(p.acc)} ${platTag(p.acc)}</small></span></a></div><div class="hd">${tags}${p.reposted_by?`<span class="note">↻ 리포스트: @${esc(p.handle)}</span>`:''}<span>${p.time_hkt.slice(0,10)} ${p.time_hkt.slice(11,16)} HKT</span><a href="${esc(p.url)}" target="_blank" rel="noopener">원문 게시물 ↗</a>${fold}</div>
<p class="tx">${p.summary_zh?esc(p.summary_zh):p.media_only?'<span class="note">(원문 게시물은 이미지 또는 영상만 있고 텍스트가 없다)</span>':'<span class="note">아직 요약이 없다. 원문 게시물을 확인하세요</span>'}</p>${p.orig?`<details class="orig"><summary>원문 보기</summary><p>${esc(p.orig)}</p></details>`:''}${(p.links||[]).length||(p.media||[]).length?`<p class="ref">${(p.media||[]).map((u,i)=>`<a href="${esc(u)}" target="_blank" rel="noopener">이미지 ${i+1} ↗</a>`).concat((p.links||[]).slice(0,3).map(u=>`<a href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace(/^https?:\/\/(www\.)?/,'').slice(0,40))} ↗</a>`)).join(' ')}</p>`:''}${p.truncated?'<p class="trunc">원문이 길다. 열어서 전체를 확인하세요</p>':''}${whyLine(p)}${pap?`<p class="ref">게시 당시 주가(기록 기준): ${pap}</p>`:''}</div>`}
function spark(vals,w=110,h=26){const mx=Math.max(...vals,1);const pts=vals.map((v,i)=>`${(i/(vals.length-1||1)*w).toFixed(1)},${(h-2-v/mx*(h-4)).toFixed(1)}`);const last=pts[pts.length-1].split(',');return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true"><polygon class="sa" points="0,${h} ${pts.join(' ')} ${w},${h}"/><polyline class="sl" points="${pts.join(' ')}"/><circle class="sd" cx="${last[0]}" cy="${last[1]}" r="2.5"/></svg>`}
function summaryOf(kind,date){const arr=(D.summaries&&D.summaries[kind])||[];if(date){const m=arr.filter(x=>x.date===date);if(m.length)return {s:m[m.length-1],stale:false}}return arr.length?{s:arr[arr.length-1],stale:!!date}:null}
function daysNote(from,to){const ds=DATES.filter(d=>d>=from&&d<=to);return ds.length<3?`<div class="notice">현재 ${ds.length} 일 분량의 게시물 데이터만 있다(${ds.map(fmt).join(', ')||'없음'}). 아래는 현재 데이터로 계산했으며, 추세와 변화는 더 많은 날짜가 쌓여야 의미가 있다.</div>`:''}

// ---------- 帳號今日動態卡（指定樣式；資料：帳號資料＋當期貼文） ----------
const ATYPE={opinion:'관점 계정',news:'시장 뉴스',disclosure:'거래 공시'};
// 追蹤名單的分類優先作為帳號類型標籤
const CAT={};((D.tracked&&D.tracked.accounts)||[]).forEach(a=>{if(a.category)CAT[a.handle.toLowerCase()]=a.category});
// 帳號平台：預設 X；Truth Social 帳號個人頁連去 truthsocial.com，並加細標籤
const PLAT={};((D.tracked&&D.tracked.accounts)||[]).forEach(a=>{if(a.platform)PLAT[a.handle.toLowerCase()]={p:a.platform,url:a.url}});
const isTS=h=>(PLAT[String(h).toLowerCase()]||{}).p==='truthsocial';
const platTag=h=>isTS(h)?'<span class="plat">Truth Social</span>':'';
const platName=h=>isTS(h)?'Truth Social':'X';
const CATN={};((D.tracked&&D.tracked.categories)||[]).forEach((c,i)=>{CATN[c.name]=(i%7)+1});
// 類別層 consensus:false（例如市場快訊）→ 呢啲帳號唔計入任何共識／分歧／最看好統計；其他人（包括大人物）照計
const NOCONS_CATS=((D.tracked&&D.tracked.categories)||[]).filter(c=>c.consensus===false).map(c=>c.name);
const NOCONS=new Set(((D.tracked&&D.tracked.accounts)||[]).filter(a=>NOCONS_CATS.includes(a.category)).map(a=>a.handle.toLowerCase()));
const inCons=h=>!NOCONS.has(String(h).toLowerCase());
const noConsNote=NOCONS_CATS.length?` · 제외: ${NOCONS_CATS.join(', ')}`:'';
const catBadge=h=>{const c=CAT[String(h).toLowerCase()];return c&&CATN[c]?`<span class="cat c${CATN[c]}">${esc(c)}</span>`:''};
const typeLabel=(h,type)=>CAT[String(h).toLowerCase()]||ATYPE[type]||'관점 계정';
function accChips(a,c,max=3){return a.slice(0,max).map(t=>`<button class="tk ${c}" data-tk="${esc(t)}">${esc(t)}</button>`).join('')+(a.length>max?`<span class="tk more" title="${esc(a.slice(max).join(', '))}">+${a.length-max}</span>`:'')}
function cardData(h,from,to){const i=accInfo(h);const lt={};postsIn(from,to).filter(x=>x.acc===h).forEach(x=>{if(!lt[x.t]||x.ms>=lt[x.t].ms)lt[x.t]=x});const v=Object.values(lt).sort((a,b)=>a.t.localeCompare(b.t));
 return {h,name:nameOf(h),avatar:i.avatar&&/^data:image\//.test(i.avatar)?i.avatar:null,type:ATYPE[i.type]?i.type:'opinion',typeKnown:!!ATYPE[i.type],bio:i.bio||null,n:rawIn(from,to).filter(p=>!p.folded_into&&p.acc===h).length,bull:v.filter(x=>x.s==='bull').map(x=>x.t),bear:v.filter(x=>x.s==='bear').map(x=>x.t),men:v.filter(x=>x.s==='neu'||x.s==='none').map(x=>x.t)}}
function avatarHtml(c){return c.avatar?`<img class="av" src="${esc(c.avatar)}" alt="">`:`<div class="av" aria-hidden="true">${esc((Array.from(c.name.replace(/^[^\p{L}\p{N}]+/u,''))[0]||'@').toUpperCase())}</div>`}
function accCardsHtml(w,label){const hs=[...new Set(rawIn(w.from,w.to).filter(p=>!p.folded_into).map(p=>p.acc))];if(!hs.length)return '';
 const rows=hs.map(h=>cardData(h,w.from,w.to)).sort((a,b)=>((b.bull.length+b.bear.length)>0)-((a.bull.length+a.bear.length)>0)||b.n-a.n||a.h.localeCompare(b.h));
 const card=r=>{const has=r.bull.length||r.bear.length;const href='#account/'+encodeURIComponent(r.h);
  const body=has?`<div class="row"><span class="lb bull">강세</span>${r.bull.length?accChips(r.bull,'bull'):`<span class="none">${label}: 뚜렷한 강세 게시물 없음</span>`}</div><div class="row"><span class="lb bear">약세</span>${r.bear.length?accChips(r.bear,'bear'):`<span class="none">${label}: 뚜렷한 약세 게시물 없음</span>`}</div>`
   :`<div class="quiet">${label}: 뚜렷한 강세 또는 약세 종목 없음</div><div class="row"><span class="lb men">${label} 언급</span>${r.men.length?accChips(r.men,'men'):`<span class="none">${label}: 언급 없음</span>`}</div>`;
  return `<article class="acc" tabindex="0" role="link" data-href="${href}" aria-label="@${esc(r.h)} 관점"><div class="acc-top">${avatarHtml(r)}<div class="acc-id"><div class="nmrow"><span class="nm" title="${esc(r.name)}">${esc(r.name)}</span><a class="xlink" href="${xUrl(r.h)}" target="_blank" rel="noopener">${platName(r.h)} 프로필 ↗</a></div><div class="hdl">@${esc(r.h)} ${platTag(r.h)} <span class="cnt">· ${r.n} 건</span></div></div>${catBadge(r.h)||`<span class="type ${CAT[r.h.toLowerCase()]?'opinion':r.type}">${esc(typeLabel(r.h,r.type))}</span>`}</div>
${r.bio?`<p class="bio" title="${esc(r.bio)}">${esc(r.bio)}</p>`:'<div class="acc-div"></div>'}${body}<a class="go" href="${href}" aria-label="보기: @${esc(r.h)} 관점">›</a></article>`};
 return `<section class="c12" aria-label="계정 ${label} 동향"><div class="acc-head"><h2>${rows.length} 개 계정 · ${label} 동향</h2><small>카드를 눌러 계정 관점 보기</small></div><div class="acc-grid">${rows.map(card).join('')}</div></section>`}

// 分析文字：有「短摘要／完整分析」兩段就用設計稿的 .brief＋<details class="more">（不用 JS）；否則沿用收合＋展開掣
function sumBody(x,clamp){if(x.brief&&x.full)return `<div class="brief">${x.brief}</div><details class="more"><summary>전체 분석 펼치기</summary><div class="analysis summary-md">${x.full}</div></details>`;
 return clamp?`<div class="summary-md clamp" id="sumMd">${x.html}</div><button class="more-btn" type="button" aria-expanded="false" aria-controls="sumMd" onclick="const m=this.previousElementSibling;const c=m.classList.toggle('clamp');this.textContent=c?'전체 분석 펼치기':'접기';this.setAttribute('aria-expanded',String(!c))">전체 분석 펼치기</button>`:x.html}

// ---------- 共識卡（設計稿 consensus.css：.cc-sec／.cc-grid／.cc／.cc-empty） ----------
const STW={bull:'강세',bear:'약세',neu:'중립',none:'입장 없음'},STC={bull:'bull',bear:'bear',neu:'neu',none:'unk'};
const cut=(t,n)=>{t=String(t||'').replace(/\s+/g,' ').trim();const a=Array.from(t);return a.length>n?a.slice(0,n).join('')+'…':t};
// 一句理由：寫手的 ticker_notes → 中文摘要（約 25 字）→ 原本摘要
// 冇逐股摘要就用成篇摘要（唔再切 25 字，否則只剩「@帳號 表示 $XX ...」）；開頭重複嘅「@帳號 表示／：」刪走，長度交俾 CSS 三行收起，撳一下展開
function reasonOf(x){const n=x.p.ticker_notes&&x.p.ticker_notes[x.t];if(n)return {t:n,full:n};const z=x.p.zh_summary||x.p.summary_zh||'';const h=String(x.acc).replace(/[^A-Za-z0-9_]/g,'');const t=z.replace(new RegExp('^\\s*@?'+h+'\\s*(?:[:\\uFF1A]|表示|指出|認為|稱)\\s*','i'),'');return {t,full:z}}
function avImg(h,cls){const i=accInfo(h);return i.avatar&&/^data:image\//.test(i.avatar)?`<img class="${cls}" src="${esc(i.avatar)}" alt="">`:(AVMINI[h]||AVMINI[String(h).toLowerCase()])?`<img class="${cls}" src="${esc(AVMINI[h]||AVMINI[String(h).toLowerCase()])}" alt="">`:`<span class="${cls}">${esc((Array.from(String(h)))[0].toUpperCase())}</span>`}
function consGroups(from,to){const out={bull:[],bear:[],split:[]};
 TICKERS.forEach(t=>{if(UNC(t)||!isUS(t))return;const rows=accsOf(from,to).filter(inCons).map(a=>latest(a,t,from,to)).filter(Boolean);if(!rows.length)return;
  const nb=rows.filter(x=>x.s==='bull').length,nr=rows.filter(x=>x.s==='bear').length;const k=nb&&nr?'split':nb>=2?'bull':nr>=2?'bear':null;if(!k)return;
  const ord={bull:k==='bear'?1:0,bear:k==='bear'?0:1,neu:2,none:3};rows.sort((a,b)=>ord[a.s]-ord[b.s]||b.ms-a.ms);
  const nPosts=new Set(postsIn(from,to).filter(x=>x.t===t).map(x=>x.url)).size;out[k].push({t,rows,nb,nr,nPosts})});
 ['bull','bear','split'].forEach(k=>out[k].sort((a,b)=>(b.nb+b.nr)-(a.nb+a.nr)||b.nPosts-a.nPosts||a.t.localeCompare(b.t)));return out}
function consCard(g,k,days,retLab){const pr=UNC(g.t)?null:D.prices[g.t];const nm=pr&&pr.name?pr.name:(OV[g.t]&&OV[g.t].name&&!UNC(g.t)?OV[g.t].name:'');const v=pchg(g.t,days);
 const ret=UNC(g.t)?'<span class="na">티커 미확인</span>':v==null?'<span class="na">주가 데이터 없음</span>':`<span class="${v>0?'up':v<0?'dn':''}">${v>0?'+':''}${v.toFixed(1)}%</span>`;
 const head=k==='bull'?`<span class="g">${g.nb} 개 계정 강세</span>`:k==='bear'?`<span class="r">${g.nr} 개 계정 약세</span>`:`<span class="g">${g.nb} 강세</span> · <span class="r">${g.nr} 약세</span>`;
 const badge={bull:'공동 강세',bear:'공동 약세',split:'의견 엇갈림'}[k];
 const li=g.rows.map(x=>{const r=reasonOf(x);return `<li class="cc-row"><a href="${xUrl(x.acc)}" target="_blank" rel="noopener" title="@${esc(x.acc)}" aria-label="@${esc(x.acc)}">${avImg(x.acc,'av')}</a><span class="st ${STC[x.s]}">${STW[x.s]}</span><span class="why" title="@${esc(x.acc)}: ${esc(r.full)}" onclick="this.classList.toggle('open')">${esc(r.t)||'<span class="na">(요약 없음)</span>'}</span><a class="src" href="${esc(x.url)}" target="_blank" rel="noopener">원문 ↗</a></li>`}).join('');
 return `<article class="cc ${k}"><div class="cc-l"><div class="cc-tk">${esc(g.t)}</div><div class="cc-nm">${esc(nm)}</div><div class="cc-ret">${ret}</div><div class="cc-ret-l">${retLab}</div></div><div class="cc-r"><div class="cc-h"><b>${head}</b><span class="cc-badge">${badge}</span></div><ul class="cc-rows">${li}</ul><div class="cc-f"><span>${g.nPosts} 건 원문 게시물</span><a href="#stock/${encodeURIComponent(g.t)}">자세히 ↗</a></div></div></article>`}
function consHtml(from,to,lab,days,retLab){const G=consGroups(from,to);
 const sec=(k,title,note)=>`<div class="cc-sec"><h2>${title}</h2><span class="note">${note}</span></div>${G[k].length?`<div class="cc-grid">${G[k].map(g=>consCard(g,k,days,retLab)).join('')}</div>`:`<div class="cc-empty">${lab}: 뚜렷한 종목 없음 · ${title}</div>`}`;
 return `<section class="c12 cc-wrap" aria-label="컨센서스">${sec('bull','공동 강세','최소 2개 계정의 최신 입장이 강세'+noConsNote)}${sec('bear','공동 약세','최소 2개 계정의 최신 입장이 약세'+noConsNote)}${sec('split','의견 엇갈림','같은 종목에 강세 계정과 약세 계정이 공존'+noConsNote)}</section>`}

// ---------- 每月：每個帳號本月最看好的股票（.fav-grid／.fav） ----------
function favHtml(from,to){const accs=[...new Set(rawIn(from,to).filter(p=>!p.folded_into).map(p=>p.acc))].filter(inCons);if(!accs.length)return '';
 const cards=accs.map(a=>{const xs=postsIn(from,to).filter(x=>x.acc===a);const by={};xs.forEach(x=>{const o=by[x.t]=by[x.t]||{t:x.t,b:0,n:0,last:0};o.n++;if(x.s==='bull'){o.b++;o.last=Math.max(o.last,x.ms)}});
  const top=Object.values(by).filter(o=>o.b>0).sort((p,q)=>q.b-p.b||q.n-p.n||q.last-p.last)[0]||null;return {a,top}}).sort((p,q)=>(!!q.top-!!p.top)||((q.top?q.top.b:0)-(p.top?p.top.b:0))||((q.top?q.top.n:0)-(p.top?p.top.n:0))||p.a.localeCompare(q.a));
 const card=c=>{const who=`<a class="fav-who" href="${xUrl(c.a)}" target="_blank" rel="noopener">${avImg(c.a,'av')}<div style="min-width:0"><b>${esc(nameOf(c.a))}</b><span>@${esc(c.a)} ${platTag(c.a)}</span></div></a>`;
  if(!c.top)return `<div class="fav none">${who}<div class="fav-sub">이번 달 뚜렷한 강세 종목 없음</div></div>`;const v=pchg(c.top.t,null);
  return `<div class="fav">${who}<div class="fav-main"><span class="fav-tk">${esc(c.top.t)}</span><span class="fav-ret">${UNC(c.top.t)||v==null?'<span class="na">—</span>':`<span class="${v>0?'up':v<0?'dn':''}">${v>0?'+':''}${v.toFixed(1)}%</span>`}<small>1 년 수익률</small></span></div><div class="fav-sub">강세 ${c.top.b} · 총 언급 ${c.top.n}</div></div>`};
 return `<section class="c12" aria-label="계정별 이번 달 최선호 종목"><div class="cc-sec"><h2>계정별 이번 달 최선호 종목</h2><span class="note">명확한 강세 횟수, 총 언급, 최근 강세 순으로 정렬. 수익률은 최근 1년${noConsNote}</span></div><div class="fav-grid">${cards.map(card).join('')}</div></section>`}

// ---------- 每月：股票排行榜（.lb-wrap／table.lb，可按表頭排序） ----------
let LB_SORT={k:'b',dir:-1};
function lbHtml(rows){if(!rows.length)return '';
 const pc=v=>v==null?'<span class="na">—</span>':`<span class="${v>0?'up':v<0?'dn':''}">${v>0?'+':''}${v.toFixed(1)}%</span>`;
 const R=rows.map(r=>{return {...r,bp:r.n?r.b/r.n*100:0,rp:r.n?r.r/r.n*100:0,y1:UNC(r.t)?null:pchg(r.t,null),d28:UNC(r.t)?null:pchg(r.t,28),nm:D.prices[r.t]&&!UNC(r.t)?D.prices[r.t].name:(OV[r.t]&&OV[r.t].name&&!UNC(r.t)?OV[r.t].name:'')}});
 const val=(r,k)=>k==='t'?r.t:r[k]==null?-1e9:r[k];
 R.sort((a,b)=>{const x=val(a,LB_SORT.k),y=val(b,LB_SORT.k);return (typeof x==='string'?x.localeCompare(y):(x-y))*LB_SORT.dir||b.n-a.n||a.t.localeCompare(b.t)});
 const th=(k,l)=>`<th><button type="button" data-lbk="${k}" class="${LB_SORT.k===k?'on':''}">${l}${LB_SORT.k===k?(LB_SORT.dir<0?' ↓':' ↑'):''}</button></th>`;
 return `<section class="c12" aria-label="종목 순위"><div class="cc-sec"><h2>종목 순위</h2><span class="note">헤더를 눌러 정렬 · 강약 비율 = 언급 중 강세·약세 비중 · 28일간 전체 계정</span></div>
 <div class="lb-wrap" id="lbWrap"><table class="lb"><thead><tr>${th('t','종목')}${th('bp','강약 비율')}${th('y1','1년 수익률')}${th('d28','28 일 수익률')}${th('n',' 언급')}${th('b','강세')}${th('r','약세')}<th>상세</th></tr></thead><tbody>
 ${R.map(r=>`<tr><td><span class="lb-tk">${esc(r.t)}</span><span class="lb-nm">${esc(r.nm||'')}</span></td><td class="lb-split"><div class="lb-bar"><i class="b" style="width:${r.bp.toFixed(1)}%"></i><i class="n" style="width:${Math.max(0,100-r.bp-r.rp).toFixed(1)}%"></i><i class="r" style="width:${r.rp.toFixed(1)}%"></i></div><div class="lb-lab"><span class="g">● ${Math.round(r.bp)}% 강세</span><span class="rd">${Math.round(r.rp)}% 약세 ●</span></div></td><td class="num">${pc(r.y1)}</td><td class="num">${pc(r.d28)}</td><td class="cnt">${r.n}</td><td class="bc">${r.b}</td><td class="rc">${r.r}</td><td><a class="go" href="#stock/${encodeURIComponent(r.t)}" aria-label="보기: ${esc(r.t)} 상세">↗</a></td></tr>`).join('')}
 </tbody></table></div></section>`}
document.addEventListener('click',e=>{const b=e.target.closest('[data-lbk]');if(!b)return;const k=b.dataset.lbk;LB_SORT=LB_SORT.k===k?{k,dir:-LB_SORT.dir}:{k,dir:k==='t'?1:-1};render()});

// ---------- 頁頂「昨日重疊 vs 今日」（樣式 .vs-bar／.vs-tk；字稿由寫手提供；昨日同連續日數：共識歷史） ----------
// 新人睇唔明「重疊」：標題同兩個分組用白話覆蓋寫手字稿（Tim，2026-10-21）
const VS_FIX=(()=>{const L=PAGE_LANG;if(L==='en')return{label:'Consensus bullish / bearish: today so far vs all of yesterday',dropped:'Not on the list so far today: {removed}',stayed:'On the list {streak} days in a row: {kept}'};if(L==='ko')return{label:'공동 강세/약세: 오늘 현재까지 vs 어제 종일',dropped:'오늘 현재까지 목록에서 제외: {removed}',stayed:'{streak}일 연속 목록: {kept}'};return{label:'공동 강세/약세: 오늘 현재까지 vs 어제 종일',dropped:'今日至今未再上榜: {removed}',stayed:'연속 {streak} 일 목록 유지: {kept}'};})();
const VSC=D.vs_copy?{...D.vs_copy,...VS_FIX}:null,CH=D.cons_hist||null;
function vsHtml(w){if(!VSC||!CH)return '';
 const G=consGroups(w.from,w.to),T={bull:G.bull.map(g=>g.t),bear:G.bear.map(g=>g.t)};
 const yd=addDays(TODAY,-1),Y=CH[yd];
 const lab=`<span class="vs-l">${esc(VSC.label||'')}</span><span class="vs-hint">목록: 최소 2개 계정이 강세(또는 약세)이고 반대 입장의 계정이 없는 미국 주식</span>`,cta=VSC.cta?`<span class="vs-cta">${esc(VSC.cta)}</span>`:'';
 if(!Y)return `<section class="c12 vs-bar first" aria-label="${esc(VSC.label||'')}">${lab}<span class="vs-line">${esc(VSC.empty_first_day||'')}</span>${cta}</section>`;
 const txt=s=>esc(s).replace(/\s*→\s*/g,'<span class="ar">→</span>');
 const fillT=(tpl,m)=>String(tpl||'').split(/(\{\w+\})/).map(x=>{const k=(x.match(/^\{(\w+)\}$/)||[])[1];return k&&k in m?m[k]:txt(x)}).join('');
 const chip=(t,c,n)=>`<span class="vs-tk${c?' '+c:''}" data-tk="${esc(t)}">${esc(t)}${n?`<b>${n}</b>`:''}</span>`;
 const list=(a,c)=>a.length?a.map(t=>chip(t,c)).join(', '):'—';
 const streak=(t,k)=>{let n=1,d=yd;while(CH[d]&&(CH[d][k]||[]).includes(t)){n++;d=addDays(d,-1)}return n};
 const sides=['bull','bear'].filter(k=>k==='bull'||(Y[k]||[]).length||T[k].length);
 const body=sides.map((k,i)=>{const y=Y[k]||[],t=T[k];const add=t.filter(x=>!y.includes(x)),rm=y.filter(x=>!t.includes(x)),kept=t.filter(x=>y.includes(x));
  const byN={};kept.forEach(x=>{const n=streak(x,k);(byN[n]=byN[n]||[]).push(x)});
  const grp=[add.length?`<span class="vs-grp">${fillT(VSC.new,{added:add.map(x=>chip(x,'new')).join(', ')})}</span>`:'',rm.length?`<span class="vs-grp">${fillT(VSC.dropped,{removed:rm.map(x=>chip(x,'gone')).join(', ')})}</span>`:'',
   ...Object.keys(byN).sort((a,b)=>b-a).map(n=>`<span class="vs-grp">${fillT(VSC.stayed,{streak:esc(n),kept:byN[n].map(x=>chip(x,'keep',n)).join(', ')})}</span>`)].join('');
  return `${i?'<span class="vs-br" aria-hidden="true"></span>':''}${sides.length>1?`<span class="pill ${k}">${k==='bull'?'공동 강세':'공동 약세'}</span>`:''}<span class="vs-line">${fillT(VSC.line,{y_bull:list(y,''),t_bull:list(t,'')})}</span>${grp}`}).join('');
 return `<section class="c12 vs-bar" aria-label="${esc(VSC.label||'')}">${lab}${body}${cta}</section>`}

function moneyBar(){return `<nav class="money-bar" aria-label="홍보"><span class="pj-tag">홍보</span><a href="tools/">도구</a><a href="support/">후원하기</a><a href="https://www.tradingview.com/?aff_id=1172819" rel="sponsored noopener" target="_blank" data-tool="tradingview" data-placement="money-bar">TradingView</a><a href="https://www.stockrover.com/thecrowdtape" rel="sponsored nofollow noopener" target="_blank" data-tool="stockrover" data-placement="money-bar">Stock Rover</a></nav>`}
// 各帳號立場：每隻股票一行（按討論帳號數排列），頭像按立場分組，點開見每個帳號的最新理由；頭 10 隻以外收起
let _sxExpand=null,_restExpand=null,_sxBodies=null;
async function stanceList(w,tks,accs){const SHOW=6,K=['bull','bear','neu','none'];_sxBodies=new Map();
 const rows=tks.map(t=>{const g={bull:[],bear:[],neu:[],none:[]};accs.forEach(a=>{const x=latest(a,t,w.from,w.to);if(x)g[x.s].push({a,x})});return {t,g,n:K.reduce((s,k)=>s+g[k].length,0)}}).filter(r=>r.n).sort((x,y)=>y.n-x.n||(y.g.bull.length+y.g.bear.length)-(x.g.bull.length+x.g.bear.length)||x.t.localeCompare(y.t));
 const av=h=>avImg(h,'sx-av').replace('<img ',`<img loading="lazy" title="@${esc(h)}" `);
 const why=(a,x)=>esc(x.why.replace(new RegExp('^\\s*@?'+a.replace(/[^A-Za-z0-9_]/g,'')+'\\s*[:\\uFF1A]\\s*','i'),''));
 const row=(r,i)=>{const {g,n}=r,b=g.bull.length,e=g.bear.length;const cls=[i>=SHOW?'x':'',b&&e?'split':'',b>=2?'mbull':'',e>=2?'mbear':''].filter(Boolean).join(' ');
  const seg=(c,k)=>g[k].length?`<span class="${c}" style="width:${g[k].length/n*100}%"></span>`:'';
  const grp=(k,c)=>g[k].length?`<span class="g"><span class="lb ${c}">${SLABEL[k]}</span>${g[k].slice(0,8).map(y=>av(y.a)).join('')}${g[k].length>8?`<span>+${g[k].length-8}</span>`:''}</span>`:'';
  const _bk=r.t+'#'+i;_sxBodies.set(_bk,function(){return `<div class="sx-why">${K.flatMap(k=>g[k]).map(({a,x})=>{const orig=x.p&&x.p.handle,st=esc(x.url);const via=orig&&orig!==a?` <a href="${st}" target="_blank" rel="noopener"> (${'리포스트:'} @${esc(orig)})</a>`:` <a href="${st}" target="_blank" rel="noopener">원문</a>`;return `<p><span class="pill ${x.s==='none'?'neu':x.s}">${SLABEL[x.s]}${x.star?'＊':''}</span><a href="${xUrl(a)}" target="_blank" rel="noopener">@${esc(a)}</a>${via}: ${why(a,x)||'—'}</p>`}).join('')}</div>`});
  return `<details class="sx-row ${cls}" data-sx-body="${esc(_bk)}"><summary><div class="sx-head">${tkBtn(r.t)}<div class="track stk">${seg('b','bull')}${seg('m','neu')}${seg('u','none')}${seg('r','bear')}</div><span class="sx-cnt">${n} 개 계정 · <b class="up">강세 ${b}</b> <b class="dn">약세 ${e}</b></span></div><div class="sx-avs">${grp('bull','b')}${grp('bear','r')}${grp('neu','')}${grp('none','')}</div></summary></details>`};
 const cnt=c=>rows.filter(r=>{const b=r.g.bull.length,e=r.g.bear.length;return c==='split'?b&&e:c==='mbull'?b>=2:e>=2}).length;
 const tab=(f,l,n,tip)=>`<button type="button" data-f="${f}" aria-pressed="${f==='all'}"${tip?` title="${tip}"`:''}>${l} ${n}</button>`;
 const pick="const b=event.target.closest('button');if(!b)return;this.parentNode.dataset.f=b.dataset.f;this.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',String(x===b)))";
 _sxExpand=rows.length>SHOW?function(){return rows.slice(SHOW).map(function(r,i){return row(r,i+SHOW)}).join('')}:null;
 let _sxHead='';
 for(let _si=0;_si<Math.min(SHOW,rows.length);_si++){_sxHead+=row(rows[_si],_si);if((_si&1)===1)await y()}
 return `<div class="sx-list" data-f="all"><div class="sx-tabs" onclick="${pick}">${tab('all','전체',rows.length)}${tab('split','의견 엇갈림',cnt('split'),'강세 계정과 약세 계정이 모두 있음')}${tab('mbull','다수 강세',cnt('mbull'),'최소 2개 계정의 최신 입장이 강세')}${tab('mbear','다수 약세',cnt('mbear'),'최소 2개 계정의 최신 입장이 약세')}</div>
 ${_sxHead}<p class="note sx-none">조건에 맞는 종목이 없습니다</p>${rows.length>SHOW?`<button type="button" class="sx-more" data-sx-exp="1">나머지 ${rows.length-SHOW} 개 종목 ▾</button>`:''}</div>`}

// ---------- 每日 ----------
async function viewDaily(){
 if(!ALLP.length)return `<div class="grid">${moneyBar()}<section class="c12 analysis"><h2>오늘의 시장 분석</h2>${empty('아직 게시물 데이터가 없다.')}</section></div>`;
 const w=dailyWindow(),len=w.merged?2:1;let pf,pt;
 if(w.timed){const a=rk(w.from),z=rk(w.to,true);pt=tsOf(a-60000);pf=tsOf(a-(z-a))}else{pf=addDays(w.from,-len);pt=addDays(w.from,-1)}
 const cur=postsIn(w.from,w.to),prev=postsIn(pf,pt),curRaw=rawIn(w.from,w.to).filter(p=>!p.folded_into),prevRaw=rawIn(pf,pt).filter(p=>!p.folded_into),xFirst=Math.min(...ALLP.filter(p=>p.platform!=='truthsocial').map(p=>p.ms)),hasPrev=prevRaw.length>0&&(!w.timed||xFirst<=rk(pf));// 時間窗：前期要完整有 X 抓帖先比較（Truth Social 存檔可以早過首次抓帖）
 const accsNow=new Set(curRaw.map(p=>p.acc)).size,accsPrev=new Set(prevRaw.map(p=>p.acc)).size;
 const tkNow=[...new Set(cur.map(x=>x.t))].sort(),tkPrev=new Set(prev.map(x=>x.t));
 const expl=cur.filter(x=>explicit(x.s)).length,explPrev=prev.filter(x=>explicit(x.s)).length;
 const DD=tkNow.map(t=>({t,c:dist(t,w.from,w.to)}));
 const coBull=DD.filter(x=>x.c.bull>=2).sort((a,b)=>b.c.bull-a.c.bull),coBear=DD.filter(x=>x.c.bear>=2).sort((a,b)=>b.c.bear-a.c.bear);
 const split=DD.filter(x=>agreeLabel(x.c).l==='뚜렷한 엇갈림');
 const chg=cur.map(x=>({x,ch:chgOf(x)})).filter(y=>y.ch);
 const att=[...new Set([...tkNow,...tkPrev])].map(t=>({t,n:cur.filter(x=>x.t===t).length,d:cur.filter(x=>x.t===t).length-prev.filter(x=>x.t===t).length})).filter(x=>x.n||x.d).sort((a,b)=>b.n-a.n||a.t.localeCompare(b.t));
 const attGone=att.filter(x=>!x.n).map(x=>x.t);att.splice(0,att.length,...att.filter(x=>x.n));
 const mx=Math.max(...att.map(x=>x.n),1);
 const vposts=rawIn(w.from,w.to).filter(valid),prevV=rawIn(pf,pt).filter(valid).length;
 const nB=cur.filter(x=>x.s==='bull').length,nR=cur.filter(x=>x.s==='bear').length,nU=cur.filter(x=>x.s==='none').length,nM=cur.filter(x=>x.s==='neu').length;
 const rawAll=rawIn(w.from,w.to),nTS=rawAll.filter(p=>p.platform==='truthsocial').length,nFold=rawAll.filter(p=>p.folded_into).length,nOff=rawAll.filter(p=>!p.folded_into&&p.theme==='非市場').length;
 const rangeTxt=w.timed?`분석 범위: ${fmtR(w.from)} – ${fmtR(w.to)} HKT (${w.src==='writer'?'오늘의 시장 분석과 동일':'이번 수집 주기'}), 총 ${rawAll.length} 건(X ${rawAll.length-nTS} 건${nTS?`, Truth Social ${nTS} 건`:''})${nFold||nOff?`; 유효 게시물 ${vposts.length} 건(${[nFold?`${nFold} 건 스레드 후속 게시물은 이전 게시물에 병합`:'',nOff?`${nOff} 건 비시장 내용`:''].filter(Boolean).join(', ')} 제외)`:''}`
  :w.merged?`유효 데이터 부족(당일 ${w.n} 건뿐), 분석은 ${fmt(w.from)}–${fmt(w.to)} 이틀을 합산`:`분석 범위: ${w.to} 단일 일자`;
 const sm=summaryOf('daily',w.day);const br=(D.briefings||[]).filter(b=>b.date===w.day).slice(-1)[0];if(!histDone&&w.day){const _d=(D.summaries&&D.summaries.daily)||[],_b=D.briefings||[];if((_d.length&&w.day<_d[0].date)||(_b.length&&w.day<_b[0].date))loadHist()}
 const top=coBull[0],topB=coBear[0],sp=split[0],rev=chg.find(y=>y.ch==='반전')||chg[0];
 const auto=`<p>${top?`컨센서스가 가장 강한 종목은 ${tkBtn(top.t)}, ${top.c.bull} 개 계정 명확한 강세${top.c.bear?`, ${top.c.bear} 개 약세`:', 약세 계정 없음'}. `:'오늘 여러 계정이 공동 강세인 종목은 없었다.'} ${topB?`${tkBtn(topB.t)} 는 ${topB.c.bear} 개 계정이 공동 약세였다.`:''}</p><p>${sp?`의견이 가장 엇갈린 종목은 ${tkBtn(sp.t)}: 강세 ${sp.c.bull}, 약세 ${sp.c.bear}(심층 분석 참조).`:'오늘 뚜렷하게 의견이 엇갈린 종목은 없다.'} ${rev?`주목할 변화: @${esc(rev.x.acc)} 의 ${tkBtn(rev.x.t)}  입장 ${rev.ch} → ${SLABEL[rev.x.s]}. `:''}</p>`;
 const sparse=w.merged?`<div id="sparse" role="note">이 페이지 계산 범위: ${vposts.length?`${vposts[0].time_hkt.slice(5,10).replace('-','/')} ${vposts[0].time_hkt.slice(11,16)} – ${vposts[vposts.length-1].time_hkt.slice(5,10).replace('-','/')} ${vposts[vposts.length-1].time_hkt.slice(11,16)} HKT`:''}; ${fmt(TODAY)} 당일 유효 게시물은 ${w.n} 건뿐(기준 ${MIN_POSTS} 건 미만), 전날과 합산했다</div>`:'';
 const label=w.merged?'이번 기간':'오늘';
 const shownAccs=[...new Set(cur.map(x=>x.acc))].sort((a,b)=>a.localeCompare(b));
 const noTk=[...new Set(curRaw.map(p=>p.acc))].filter(a=>!shownAccs.includes(a)).sort();
 const score=p=>{const xs=POSTS.filter(x=>x.p===p);if(!xs.length)return -1;return Math.max(...xs.map(x=>{const ch=chgOf(x);return !explicit(x.s)?(ch?1:(stanced(x.s)?0.5:0)):(ch?3:2)}))};
 const keyAll=vposts.slice().sort((a,b)=>score(b)-score(a)||b.ms-a.ms);const keyPosts=keyAll.slice(0,6),rest=keyAll.slice(6);
 const coList=(arr,k)=>arr.map(x=>`<li>${tkBtn(x.t)}<span class="pill ${k}">${x.c[k]} ${SLABEL[k]}</span>${x.c[k==='bull'?'bear':'bull']?`<span class="pill ${k==='bull'?'bear':'bull'}">${x.c[k==='bull'?'bear':'bull']} ${SLABEL[k==='bull'?'bear':'bull']}</span>`:''}<span class="handle">${accsOf(w.from,w.to).filter(a=>latest(a,x.t,w.from,w.to)?.s===k).map(a=>'@'+esc(a)).join(' ')}</span></li>`).join('')||`<li class="note">조건에 맞는 종목 없음(필요 조건: 2개 이상 계정의 범위 내 최신 입장 = ${SLABEL[k]})</li>`;
 const cmpLab=current==='weekly'?'이전 7일 대비':current==='monthly'?'이전 28일 대비':'어제 대비 (오늘 현재까지)';
 const priorOpen=current==='weekly'?'이전 7일(':current==='monthly'?'이전 28일(':'어제(';
 const priorLoading=!hasPrev&&!postsReady();
 await y();
 if(priorLoading&&!allP)loadAllPosts().then(function(){render()});
 await y();
 let _html=`<div class="grid">
 ${moneyBar()}
 <section class="c12 analysis" aria-label="시장 분석">
  
  <h2>오늘의 시장 분석 ${sm?(sm.stale?`<span class="sub">(최신 분석, ${esc(w.day)}  당일 분석 아님)</span>`:''):'<span class="sub">오늘 분석이 아직 없어 아래는 데이터로 자동 정리했다</span>'}</h2>
  ${sm?'':sparse}
  ${sm?sumBody(sm.s,true):auto}
  <p class="note" style="margin:8px 0 0">${(PAGE_LANG==='en'?"Brief counts are from the writer; the stat cards below are live counts for the same window (posts so far: {n}, active accounts {a}).":PAGE_LANG==='ko'?"요약 숫자는 작성자 정리분; 아래 통계 카드는 같은 구간의 실시간 집계입니다 (유효 게시물 {n}, 활동 계정 {a}).":"摘要數字來自寫手整理; 下方統計卡按同一分析範圍即時計算 (目前有效貼文 {n}, 有動態帳號 {a}). ").replace(/\{n\}/g,String(vposts.length)).replace(/\{a\}/g,String(accsNow))}</p>
  ${br?`<details><summary>분석가 브리핑</summary>${br.html}</details>`:''}
 </section>
 <div class="c12 dayrange">${`<div class="range ${w.merged?'merged':''}">${rangeTxt}${vposts.length&&!w.timed?` (${vposts[0].time_hkt.slice(5,16).replace('-','/').replace('T',' ')} – ${vposts[vposts.length-1].time_hkt.slice(5,16).replace('-','/').replace('T',' ')} HKT, 유효 게시물 ${vposts.length} 건)`:''}</div>`}</div>
 ${macroHtml()}
 <section class="c12 kpis k6" aria-label="오늘 개요">
  <div class="kpi"><div class="l">유효 게시물</div><div class="v">${vposts.length}</div><div class="d">${vsPrev(vposts.length,prevV,hasPrev,cmpLab)}</div></div>
  <div class="kpi"><div class="l">활동 계정</div><div class="v">${accsNow}<span class="note"> / ${(D.tracked&&D.tracked.accounts&&D.tracked.accounts.length)||HANDLES.length}</span></div><div class="d">${vsPrev(accsNow,accsPrev,hasPrev,cmpLab)}</div></div>
  <div class="kpi"><div class="l">언급 종목</div><div class="v">${tkNow.length}</div><div class="d">${vsPrev(tkNow.length,tkPrev.size,hasPrev,cmpLab)}</div></div>
  <div class="kpi bull"><div class="l">강세</div><div class="v up">${nB}</div><div class="d note" title="게시물 × 종목마다 관점 1개로 계산">관점 수</div></div>
  <div class="kpi bear"><div class="l">약세</div><div class="v dn">${nR}</div><div class="d note" title="게시물 × 종목마다 관점 1개로 계산">관점 수</div></div>
  <div class="kpi"><div class="l">입장 없음</div><div class="v">${nU}</div><div class="d note">${nM?`그 외 중립 ${nM}`:'관점 수'}</div></div>
 </section>
 ${vsHtml(w)}
 ${highlightsHtml(w.day)}
`;
 await y();
 const _sxHtml=tkNow.length?await stanceList(w,tkNow,shownAccs):empty('이 범위에서 티커를 언급한 게시물이 없다.');
 _html+=`<!--DY-->
 <section class="c12 panel"><h2>시장 관심도 변화 <span class="sub">여전히 관심받는 종목만 표시${attGone.length?`, 관심이 끊긴 종목 ${attGone.length} 개 제외`:''}; 괄호는 ${cmpLab}</span></h2>
  ${att.length?`<div class="scrollbox" style="display:grid;gap:8px;align-content:start">${att.slice(0,20).map(x=>{const k={bull:0,neu:0,none:0,bear:0};cur.filter(y=>y.t===x.t).forEach(y=>k[y.s]=(k[y.s]||0)+1);const seg=(c,n,l)=>n?`<span class="${c}" style="width:${n/mx*100}%" title="${l} ${n}"></span>`:'';return `<div class="hbar">${tkBtn(x.t)}<div class="track stk">${seg('b',k.bull,'강세')}${seg('m',k.neu,'중립')}${seg('u',k.none,'입장 없음')}${seg('r',k.bear,'약세')}</div><span class="n">${x.n} ${hasPrev?`(${signed(x.d)})`:''}</span></div>`}).join('')}</div>${att.length>20?`<p class="note">`+uiText('另有 '+(att.length-20)+' 隻','+'+(att.length-20)+' more','+'+(att.length-20)+'개 더')+`</p>`:''}<div style="margin-top:10px">${legend}</div>${hasPrev?'':priorLoading?'<p class="note">비교 자료를 불러오는 중…</p>':`<p class="note">${priorOpen}${w.timed?`${fmtR(pf)} – ${fmtR(pt)}`:`${fmt(pf)}${len>1?'–'+fmt(pt):''}`})에 데이터가 없어 아직 비교할 수 없다.</p>`}`:empty('이 범위에서 언급된 종목이 없다.')}</section>
 <section class="c12 panel"><h2>계정별 입장 <span class="sub">${label} ${tkNow.length} 개 종목 · ${shownAccs.length} 개 계정 · 언급한 계정 수 순, 행을 누르면 계정별 이유를 볼 수 있습니다</span></h2>
  ${_sxHtml}
  <div style="margin-top:10px">${legend}</div>${noTk.length?`<p class="note">게시했지만 티커 언급 없음: ${noTk.map(accLink).join(' ')}</p>`:''}</section>
`;
 await y();
 window.__dashLate=async function(g){
  if(!g)return;
  await y();
  try{g.insertAdjacentHTML('beforeend',consHtml(w.from,w.to,label,len,'1 일 수익률'))}catch(e){console.error(e)}
  await y();
  try{g.insertAdjacentHTML('beforeend',`<section class="c12 panel"><h2>주요 관점 <span class="sub">입장 변화와 명확한 표명 우선, 원문 게시물 첨부</span></h2>${keyPosts.length?keyPosts.map(p=>postHtml(p)).join(''):empty('이 범위에 유효 게시물이 없다.')}${(function(){if(!rest.length)return '';_restExpand=function(){return rest.map(function(p){return postHtml(p)}).join('')};return `<details class="more" data-rest-exp="1"><summary>나머지 ${rest.length} 건</summary></details>`})()}</section>
 ${accCardsHtml(w,label)}`)}catch(e){console.error(e)}
  await y();
  try{linkHandles(g);fitTables(g);clampLists(g)}catch(e){}
 };
 _html+=`</div>`;
 return _html}

// ---------- 每週 ----------
async function viewWeekly(){
 const to=TODAY,from=addDays(TODAY,-6),pf=addDays(from,-7),pt=addDays(from,-1);const hasPrev=POSTS.some(x=>x.d>=pf&&x.d<=pt);
 const days=[...Array(7)].map((_,i)=>addDays(from,i));
 const rows=TICKERS.map(t=>{const c=dist(t,from,to),c0=dist(t,pf,pt),ca=dist(t,from,to,true);const daily=days.map(d=>postsIn(d,d).filter(x=>x.t===t).length);return {t,c,c0,ca,daily,net:c.bull-c.bear,net0:c0.bull-c0.bear}}).filter(r=>r.ca.accs>=1).sort((a,b)=>b.ca.accs-a.ca.accs||b.c.mentions-a.c.mentions||a.t.localeCompare(b.t));
 const tot=rows.reduce((s,r)=>({b:s.b+r.c.bull,m:s.m+r.c.neu,n:s.n+r.c.none,r:s.r+r.c.bear}),{b:0,m:0,n:0,r:0});
 const aligned=rows.filter(r=>agreeLabel(r.c).l.startsWith('강한')),split=rows.filter(r=>agreeLabel(r.c).l==='뚜렷한 엇갈림'),multi=rows.filter(r=>r.ca.accs>=2);
 const chgs=postsIn(from,to).map(x=>({x,ch:chgOf(x)})).filter(y=>y.ch);
 const sm=summaryOf('weekly');
 const wkAccs=[...new Set(rawIn(from,to).filter(p=>!p.folded_into).map(p=>p.acc))];
 const accCard=a=>{const ps=postsIn(from,to).filter(x=>x.acc===a);const raw=rawIn(from,to).filter(p=>!p.folded_into&&p.acc===a);const cnt={};ps.forEach(x=>cnt[x.t]=(cnt[x.t]||0)+1);const top=Object.entries(cnt).sort((x,y)=>y[1]-x[1]||x[0].localeCompare(y[0])).slice(0,3);const chs=ps.filter(x=>chgOf(x)).length;
  return {a,n:raw.length,html:`<div class="acc-card"><div><b>${esc(nameOf(a))}</b> ${accLink(a)}${accIn(a)}</div><div class="note">${raw.length} 건 게시물 · ${chs} 회 입장 변화</div><ul class="list">${top.map(([t,n])=>{const x=latest(a,t,from,to);return `<li>${tkBtn(t)}${pill(x.s,x.star)}<span class="note">${n} 회</span></li>`}).join('')||'<li class="note">이번 주 언급 종목 없음</li>'}</ul></div>`}};
 const cards=wkAccs.map(accCard).sort((x,y)=>y.n-x.n||x.a.localeCompare(y.a));
 return `<div class="grid">
 ${moneyBar()}
 <section class="c12 analysis"><div class="range">집계 ${from} ~ ${to} (7일)</div>
  <h2>이번 주 핵심 ${sm?'':'<span class="sub">주간 분석이 아직 없어 아래는 데이터로 자동 정리했다</span>'}</h2>
  ${daysNote(from,to)}
  ${sm?sumBody(sm.s,false):`<p>${rows.length?`가장 많은 계정의 관심을 받은 종목은 ${rows.slice(0,3).map(r=>tkBtn(r.t)).join(', ')}. `:'이번 주 언급된 종목이 없다.'} 강한 일치 종목: ${aligned.map(r=>tkBtn(r.t)).join(', ')||'없음'}; 뚜렷한 엇갈림: ${split.map(r=>tkBtn(r.t)).join(', ')||'없음'}. 이번 주 입장 변화 ${chgs.length} 회${chgs.length?': '+chgs.slice(0,3).map(y=>`@${esc(y.x.acc)} ${tkBtn(y.x.t)} ${y.ch}`).join('; '):''}. </p>`}</section>
 ${consHtml(from,to,'이번 주',7,'7 일 수익률')}
 <section class="c4 panel"><h2>관점 분포 <span class="sub">계정별 종목별 최신 입장</span></h2>
  ${distBar({bull:tot.b,neu:tot.m,none:tot.n,bear:tot.r})}
  <div class="kpis k4" style="margin-top:12px"><div class="kpi"><div class="l">강세</div><div class="v up">${tot.b}</div></div><div class="kpi"><div class="l">중립</div><div class="v">${tot.m}</div></div><div class="kpi"><div class="l">입장 없음</div><div class="v">${tot.n}</div></div><div class="kpi"><div class="l">약세</div><div class="v dn">${tot.r}</div></div></div></section>
 <section class="c8 panel"><h2>강한 일치와 뚜렷한 엇갈림 <span class="sub">최신 입장이 있는 계정 2개 이상 필요</span></h2>
  <div class="grid" style="gap:12px"><div class="c6"><div class="mod">강한 일치</div><ul class="list" style="margin-top:8px">${aligned.map(r=>`<li>${tkBtn(r.t)}<span class="pill ${agreeLabel(r.c).k}">${agreeLabel(r.c).l}</span><span class="note">${r.c.accs} 계정 </span></li>`).join('')||'<li class="note">없음</li>'}</ul></div>
  <div class="c6"><div class="mod">뚜렷한 엇갈림</div><ul class="list" style="margin-top:8px">${split.map(r=>`<li>${tkBtn(r.t)}<span class="pill bull">${r.c.bull} 강</span><span class="pill bear">${r.c.bear} 약</span></li>`).join('')||'<li class="note">없음</li>'}</ul></div></div></section>
 <section class="c12 panel"><h2>여러 계정이 관심을 보인 종목 <span class="sub">열기 = 일별 언급 수, 순강세 변화 = 이번 주 대비 지난주${multi.length?'':' · 이번 주 2개 이상 계정이 관심을 보인 종목이 없어 언급된 전체 종목을 표시'}</span></h2>
  ${rows.length?`<div class="tablewrap multi-scroll"><table><thead><tr><th>종목</th><th class="n">관심 계정</th><th class="n"> 언급</th><th>입장 분포</th><th>일치도</th><th>7 일 열기</th><th class="n">순강세 변화</th></tr></thead>
  <tbody>${rows.map(r=>{const a=agreeLabel(r.c);const nm=D.prices[r.t]&&!UNC(r.t)?D.prices[r.t].name:'';return `<tr><td>${tkBtn(r.t)} <span class="note">${esc(nm||'')}</span>${UNC(r.t)?' '+UNC_TXT:''}${OVN(r.t)?' '+OVN(r.t):''}${capTag(r.t)?' '+capTag(r.t):''}</td><td class="n">${r.ca.accs}</td><td class="n">${r.c.mentions}</td><td>${distBar(r.c)}</td><td><span class="pill ${a.k}">${a.l}</span></td><td>${spark(r.daily)}</td><td class="n">${hasPrev?signed(r.net-r.net0):'<span class="note">지난주 데이터 없음</span>'}</td></tr>`}).join('')}</tbody></table></div>
  <div style="margin-top:10px">${legend}</div>`:empty('이번 주 언급된 종목이 없다.')}</section>
 <section class="c12 panel"><h2>계정별 이번 주 주요 관심 <span class="sub">이번 주 게시한 ${cards.length} 개 계정${HANDLES.length>cards.length?`; 나머지 ${HANDLES.length-cards.length} 개 추적 계정은 이번 주 게시물이 없다`:''}</span></h2>
  ${cards.length?`<div class="acc-cards">${cards.map(c=>c.html).join('')}</div>`:empty('이번 주 게시한 계정이 없다.')}</section>
 </div>`}

// ---------- 每月 ----------
const HEAT_MIN={acc:3,days:3};
async function viewMonthly(){
 const to=TODAY,from=addDays(TODAY,-27),all=postsIn(from,to);const DAYS=[...Array(28)].map((_,i)=>addDays(from,i));
 const rows=TICKERS.map(t=>{const ps=all.filter(x=>x.t===t);return {t,n:ps.length,b:ps.filter(x=>x.s==='bull').length,r:ps.filter(x=>x.s==='bear').length,m:ps.filter(x=>x.s==='neu').length,u:ps.filter(x=>x.s==='none').length,c:dist(t,from,to)}}).filter(r=>r.n).sort((a,b)=>b.n-a.n||a.t.localeCompare(b.t));
 const B=all.filter(x=>x.s==='bull').length,X=all.filter(x=>x.s==='bear').length,M=all.filter(x=>x.s==='neu').length,U=all.length-B-X-M;
 const cons=accsOf(from,to).map(a=>{const ps=all.filter(x=>x.acc===a);let rev=0,flips=0,same=0;const byT={};ps.forEach(x=>(byT[x.t]=byT[x.t]||[]).push(x));Object.values(byT).forEach(list=>{list.sort((x,y)=>x.ms-y.ms);for(let i=1;i<list.length;i++){if(list[i].s===list[i-1].s)same++;else{flips++;if(explicit(list[i].s)&&explicit(list[i-1].s))rev++}}});const pairs=same+flips;return {a,n:ps.length,rev,score:pairs?same/pairs*100:null}}).sort((x,y)=>y.n-x.n||x.a.localeCompare(y.a));
 // 熱圖只留熱度夠嘅股票：28 天內至少 HEAT_MIN.acc 個帳號、HEAT_MIN.days 天有提及（改數字要同時改下面標題同 i18n 文字）
 const hot=rows.filter(r=>{const ps=all.filter(x=>x.t===r.t);return new Set(ps.map(x=>x.acc)).size>=HEAT_MIN.acc&&new Set(ps.map(x=>x.d)).size>=HEAT_MIN.days});
 const maxHeat=Math.max(1,...hot.flatMap(r=>DAYS.map(d=>all.filter(x=>x.t===r.t&&x.d===d).length)));
 const heatRows=hot.map(r=>`<div style="display:contents"><span>${tkBtn(r.t)}</span>${DAYS.map(d=>{const ps=all.filter(x=>x.t===r.t&&x.d===d);const b=ps.filter(x=>x.s==='bull').length,s=ps.filter(x=>x.s==='bear').length,net=b-s;const cls=!ps.length?'e':net>0?'b':net<0?'r':(b&&s)?'x':'m';const op=ps.length?(.35+.65*ps.length/maxHeat).toFixed(2):1;return `<i class="hc ${cls}" style="opacity:${op}" title="$${esc(r.t)} ${fmt(d)}: ${ps.length} 건, 순강세 ${net}"></i>`}).join('')}</div>`).join('');
 const sm=summaryOf('monthly');const srcs=[...new Set(Object.entries(D.prices).filter(([t])=>!UNC(t)).map(([,p])=>p.source))];const asof=Object.entries(D.prices).filter(([t])=>isUS(t)).map(([,p])=>p.as_of).sort().pop();
 return `<div class="grid">
 ${moneyBar()}
 <section class="c12 analysis"><div class="range">집계 ${from} ~ ${to} (28일)</div><h2>이번 달 추세 ${sm?'':'<span class="sub">월간 분석이 아직 없어 아래는 데이터로 자동 정리했다</span>'}</h2>
  ${daysNote(from,to)}
  ${sm?sumBody(sm.s,false):`<p>28 일간 총 ${all.length} 건 언급, 강세 관점 ${B} 건, 약세 ${X} 건${B+X?`, 강세 비율 ${(B/(B+X)*100).toFixed(0)}%`:', 강세 비율 계산 불가(강세·약세 관점 없음)'}. ${rows.length?`가장 많이 언급된 종목은 ${rows.slice(0,3).map(r=>tkBtn(r.t)).join(', ')}. `:''}</p>`}</section>
 ${consHtml(from,to,'이번 달',28,'28 일 수익률')}
 <section class="c4 panel"><h2>강세 대 약세 비율 <span class="sub">${B+X?`강세 ${(B/(B+X)*100).toFixed(0)}%(강세+약세 기준)`:'데이터 부족'}</span></h2>${distBar({bull:B,neu:M,none:U,bear:X})}
  <div class="kpis k3" style="margin-top:12px"><div class="kpi"><div class="l">총 언급</div><div class="v">${all.length}</div></div><div class="kpi"><div class="l">강세</div><div class="v up">${B}</div></div><div class="kpi"><div class="l">약세</div><div class="v dn">${X}</div></div></div>
  <p class="note" style="margin-bottom:0">그 외 중립 ${M} 건, 입장 없음 ${U} 건.</p></section>
 <section class="c8 panel"><h2>계정별 입장 일관성 <span class="sub">같은 종목에 대해 입장이 유지된 비율. 반전은 강세와 약세가 직접 뒤바뀐 경우</span></h2>
  ${cons.length?`<div class="tablewrap cons-scroll"><table><thead><tr><th>계정 </th><th class="n">관점</th><th class="n">반전 횟수</th><th class="n">일관성</th><th></th></tr></thead><tbody>${cons.map(c=>`<tr><td><b>${esc(nameOf(c.a))}</b> ${accLink(c.a)}${accIn(c.a)}</td><td class="n">${c.n}</td><td class="n">${c.rev}</td><td class="n">${c.score==null?'—':c.score.toFixed(0)+'%'}</td><td style="width:30%">${c.score==null?'<span class="note">종목당 관점 1개뿐이라 데이터 부족</span>':`<div class="bar"><span class="a" style="width:${c.score}%"></span></div>`}</td></tr>`).join('')}</tbody></table></div>`:empty('이 기간에 종목을 언급한 계정이 없다.')}</section>
 ${favHtml(from,to)}
 ${lbHtml(rows)}
 <section class="c12 panel"><h2>종목별 관심도와 관점의 시간별 변화 <span class="sub">칸 하나는 하루(HKT). 색은 당일 순입장, 농도는 언급 횟수. 3개 이상 계정이 3일 이상 언급한 종목만 표시</span></h2>
  ${hot.length?`<div class="heatwrap"><div class="heat">${heatRows}
  <span></span>${DAYS.map((d,i)=>`<span style="text-align:center${i===27?';direction:rtl':''}" class="note">${i%7===0||i===27?fmt(d):''}</span>`).join('')}</div></div>
  <div class="legend" style="margin-top:10px"><span><i class="sw b"></i>순강세</span><span><i class="sw r"></i>순약세</span><span><i class="sw x"></i>강약 상쇄</span><span><i class="sw m"></i>중립 / 입장 없음</span></div>`:empty(rows.length?'이 기간에 관심도 기준을 넘은 종목이 없다.':'이 기간에 언급된 종목이 없다.')}</section>
 </div>`}

// ---------- 價格圖（內嵌 SVG） ----------
let chartRange='28d';
// 走勢圖區間：1日／1星期用 Yahoo 日內價（建站時抓，每 4 小時），28日用日收市價（帖文只保留 28 日，所以最長 28 日）；冇日內價就唔顯示 1日 掣
const RANGES=[['1d','1일'],['1w','1주'],['28d','28일']];
let INTRA=D.intraday||{};
const fmtHK=ms=>`${hkDate(ms).slice(5).replace('-','/')} ${hm(ms)}`;
function chartSeries(t,rg){const I=INTRA[t]||{};
 if(rg==='1d')return I['1d']&&I['1d'].length>1?{pts:I['1d'],intra:true}:null;
 if(rg==='1w'&&I['5d']&&I['5d'].length>1)return {pts:I['5d'],intra:true};
 const c=closes(t);if(!c)return null;const last=Date.parse(c[c.length-1][0]);const span={'1w':7,'28d':28}[rg]||28;
 return {pts:c.filter(r=>Date.parse(r[0])>=last-span*DAY).map(r=>[Date.parse(r[0]),r[1],r[0]]),intra:false}}
const rangesFor=t=>RANGES.filter(([k])=>k!=='1d'||chartSeries(t,'1d'));
function drawChart(t){const el=document.getElementById('chart');if(!el)return;const note=document.getElementById('chnote');if(note)note.textContent='';
 if(UNC(t)){el.innerHTML=empty(`티커 미확인: $${esc(t)} 는 모호할 수 있다${OV[t].note?' ('+esc(OV[t].note)+')':''}, 따라서 주가와 차트를 표시하지 않는다.`);return}
 if(pxWait(t)){el.innerHTML=empty(PXFAIL[t]?'주가를 불러오지 못했다. 페이지를 새로고침해 주세요.':'주가 불러오는 중…');loadPx(t);return}
 const c=closes(t);if(!c){el.innerHTML=empty(`주가 데이터 없음($${esc(t)} 주가를 가져오지 못했거나 아직 가져오지 않았다).`);return}
 if(chartRange==='1d'&&!chartSeries(t,'1d'))chartRange='1w';
 const S=chartSeries(t,chartRange);const data=S?S.pts:[];if(data.length<2){el.innerHTML=empty('이 구간의 주가 데이터가 부족하다.');return}
 const pr=D.prices[t]||{};
 if(note)note.textContent=S.intra?`장중 가격(Yahoo Finance, ${fmtHK(data[data.length-1][0])} HKT 기준, 4시간마다 업데이트) · 실시간 시세는 위 TradingView 차트 참고`:`일간 종가(${pr.source||'Yahoo Finance'}${pr.symbol&&pr.symbol!==t?', '+pr.symbol:''}, ${CURNAME[curOf(t)]?curOf(t)+' '+CURNAME[curOf(t)]:curOf(t)}), 최근 종가 ${data[data.length-1][2]}${pr.fetched_hkt?`, 데이터 기준 시각 ${fmtHK(Date.parse(pr.fetched_hkt.replace(' ','T')+':00+08:00'))} HKT`:''}. 점은 게시일(미 동부) 또는 그 직전 거래일의 종가에 표시한다.`;
 const W=Math.max(300,el.clientWidth||760),H=W<500?200:250,L=W<500?40:52,R=12,T=14,B=22;const xs=data.map(r=>r[0]),ys=data.map(r=>r[1]);const x0=xs[0],x1=xs[xs.length-1];let y0=Math.min(...ys),y1=Math.max(...ys);
 // 每則提及落在發帖當日（美東）或之前最近一個交易日的收市價；日內則落在最近一個價位（休市時間發的帖貼到下一個開市價位）
 let marks;
 if(S.intra){const fAt=INTRA[t]&&INTRA[t].fetched_hkt?Date.parse(INTRA[t].fetched_hkt.replace(' ','T')+':00+08:00'):x1;
  marks=POSTS.filter(x=>x.t===t&&x.ms>=x0-30*60e3&&x.ms<=Math.max(x1,fAt)).map(x=>{let k=xs.findIndex(v=>v>=x.ms);if(k<0)k=xs.length-1;const hr=chartRange==='1d';return {x,key:hr?String(Math.floor(xs[k]/36e5)):hkDate(xs[k]),xv:xs[k],y:ys[k],lab:hr?fmtHK(Math.floor(xs[k]/36e5)*36e5):fmt(hkDate(xs[k]))}})}
 else marks=POSTS.filter(x=>x.t===t).map(x=>{const r=closeOn(t,x.p.date_et);return {x,key:r?r[0]:null,xv:r?Date.parse(r[0]):null,y:r?r[1]:null,lab:r?fmt(r[0]):''}}).filter(m=>m.key&&m.xv>=x0&&m.y!=null);
 const pad=(y1-y0)*.08||1;y0-=pad;y1+=pad;
 const sx=v=>L+(v-x0)/(x1-x0||1)*(W-L-R),sy=v=>T+(1-(v-y0)/(y1-y0))*(H-T-B);const pts=data.map(r=>sx(r[0]).toFixed(1)+','+sy(r[1]).toFixed(1)).join(' ');
 let g='';for(let i=0;i<=2;i++){const v=y0+(y1-y0)*i/2,yy=sy(v);g+=`<line class="g" x1="${L}" x2="${W-R}" y1="${yy}" y2="${yy}"/><text x="${L-6}" y="${yy+3}" text-anchor="end">${v>=1000?Math.round(v).toLocaleString('en-US'):v.toFixed(v<10?2:v<100?1:0)}</text>`}
 // 同一天（1日圖為同一小時）的提及合成一個圓點，放在最後一則的價位：每個帳號只計當天最後一則；顏色＝當天淨立場，數字＝帳號數
 const by={};marks.forEach(m=>(by[m.key]=by[m.key]||[]).push(m));
 const G=Object.keys(by).map(k=>{const ms0=by[k],a=ms0.reduce((p,m)=>m.xv>p.xv?m:p,ms0[0]);return [k,a]}).sort((p,q)=>p[1].xv-q[1].xv).map(([k,A])=>{const last={};by[k].forEach(m=>{if(!last[m.x.acc]||m.x.ms>last[m.x.acc].x.ms)last[m.x.acc]=m});const ms=Object.values(last).sort((a,b)=>b.x.ms-a.x.ms);
  const n=s=>ms.filter(m=>m.x.s===s).length;const b=n('bull'),r=n('bear');return {xv:A.xv,y:A.y,lab:A.lab,ms,cl:b>r?'bull':r>b?'bear':b?'mix':ms.some(m=>m.x.s==='neu')?'neu':'none'}});
 const first=data[0][1],lastP=data[data.length-1][1],pc=(lastP/first-1)*100;
 const all=G.flatMap(d=>d.ms),cnt=s=>all.filter(m=>m.x.s===s).length,turns=all.filter(m=>change(prevStance(m.x.acc,t,m.x.ms),m.x)).length;
 let mk='';G.forEach((d,i)=>{const xx=sx(d.xv),yy=sy(d.y),n=d.ms.length;
  mk+=`<g class="dot ${d.cl}" data-g="${i}" tabindex="0" role="button" aria-label="${esc(d.lab)}: ${n} 개 계정"><circle cx="${xx}" cy="${yy}" r="14" class="hit"/><circle cx="${xx}" cy="${yy}" r="${n>1?8.5:6}" class="mk"/>${n>1?`<text x="${xx}" y="${yy+3.5}" text-anchor="middle" class="num">${n}</text>`:''}</g>`});
 const avHref=m=>{const orig=m.x.p&&m.x.p.handle;return esc(orig&&orig!==m.x.acc?xUrl(m.x.acc):(m.x.p.url||xUrl(m.x.acc)))};
 const rowHtml=m=>{const p=prevStance(m.x.acc,t,m.x.ms);const acc=m.x.acc,orig=m.x.p&&m.x.p.handle,st=esc(m.x.p.url||xUrl(acc));const via=orig&&orig!==acc?` <a href="${st}" target="_blank" rel="noopener"> (${'리포스트:'} @${esc(orig)})</a>`:` <a href="${st}" target="_blank" rel="noopener">원문</a>`;return `<li><div class="ch-row">${avImg(acc,'post-av')}<span class="ch-who"><b>${esc(nameOf(acc))}</b><small><a href="${xUrl(acc)}" target="_blank" rel="noopener">@${esc(acc)}</a>${via}</small></span><span class="ch-st"><span class="ch-from">${p?SLABEL[p.s]:'첫 표명'} →</span>${pill(m.x.s,m.x.star)}</span></div></li>`};
 // 每日卡：轉向及首次表態逐行列出；立場不變及未表態只顯示頭像
 const dayHtml=(d,i)=>{const since=(lastP/d.y-1)*100;const isNew=m=>{const p=prevStance(m.x.acc,t,m.x.ms);return stanced(m.x.s)&&(!p||p.s!==m.x.s)};const big=d.ms.filter(isNew),rest=d.ms.filter(m=>!isNew(m));
  const same=[['bull','계속 강세'],['neu','계속 중립'],['bear','계속 약세'],['none','입장 없음']].map(([s,l])=>{const xs=rest.filter(m=>m.x.s===s);return xs.length?`<div class="ch-same"><span class="pill ${s}">${l}</span><span class="ch-avs">${xs.map(m=>`<a href="${avHref(m)}" target="_blank" rel="noopener" title="@${esc(m.x.acc)}" aria-label="@${esc(m.x.acc)}">${avImg(m.x.acc,'post-av')}</a>`).join('')}</span></div>`:''}).join('');
  return `<div class="ch-day" id="chd-${i}"><div class="ch-dh"><span class="ch-dot ${d.cl}"></span><b>${esc(d.lab)}</b><span>${S.intra?'당시 가격':'종가'} ${moneyT(t,d.y)}</span><span class="ch-since ${since>=0?'up':'dn'}">이후 ${since>=0?'+':''}${since.toFixed(1)}%</span></div>${big.length?`<ul>${big.map(rowHtml).join('')}</ul>`:''}${same}</div>`};
 const rev=G.map((d,i)=>[d,i]).reverse(),SHOW=4;
 el.innerHTML=`<div class="ch-sum"><span class="ch-pc ${pc>=0?'up':'dn'}">${pc>=0?'▲':'▼'} ${Math.abs(pc).toFixed(1)}%</span><span>${moneyT(t,first)} → ${moneyT(t,lastP)}</span></div>
 <div class="chwrap"><svg class="chart" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="$${esc(t)} 주가와 관점">${g}<polygon class="ar" points="${sx(x0)},${H-B} ${pts} ${sx(x1)},${H-B}"/><polyline class="ln" points="${pts}"/>${mk}<text x="${L}" y="${H-5}">${S.intra?fmtHK(x0):data[0][2]}</text><text x="${W-R}" y="${H-5}" text-anchor="end">${S.intra?fmtHK(x1)+' HKT':data[data.length-1][2]}</text></svg></div>
 <div class="ch-key"><span><i class="ch-dot bull"></i>강세 우세</span><span><i class="ch-dot bear"></i>약세 우세</span><span><i class="ch-dot mix"></i>강세·약세 반반</span><span><i class="ch-dot neu"></i>중립 / 입장 없음</span><span class="ch-tap">점 안의 숫자 = 계정 수. 점을 누르면 어떤 계정인지 볼 수 있다.</span></div>
 ${G.length?`<div class="ch-tlh"><b>기간 내 관점</b><span>강세 ${cnt('bull')} · 중립 ${cnt('neu')} · 약세 ${cnt('bear')} · 입장 없음 ${cnt('none')}${turns?` · <b class="chg-t">입장 변경 ${turns}</b>`:''}</span></div><div class="ch-list"><div class="ch-cols">${rev.slice(0,SHOW).map(([d,i])=>dayHtml(d,i)).join('')}</div>${rev.length>SHOW?`<details class="more"><summary>이전 ${rev.length-SHOW} ${chartRange==='1d'?'시점':'일'}</summary><div class="ch-cols">${rev.slice(SHOW).map(([d,i])=>dayHtml(d,i)).join('')}</div></details>`:''}</div>`:'<p class="note">이 구간에 표시할 관점이 없다.</p>'}`;
 // 點圓點：跳到下方當天的卡並高亮（手機沒有滑鼠懸停）
 el.querySelectorAll('g.dot').forEach(o=>{const go=()=>{const d=el.querySelector('#chd-'+o.dataset.g);if(!d)return;const dt=d.closest('details');if(dt)dt.open=true;el.querySelectorAll('.ch-day.on,g.dot.on').forEach(x=>x.classList.remove('on'));d.classList.add('on');o.classList.add('on');d.scrollIntoView({behavior:'smooth',block:'nearest'})};o.addEventListener('click',go);o.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go()}})})}

// ---------- 個股深入分析 ----------
// ---------- 個股頁 TradingView 免費走勢圖（設計稿 .tv-card）：只用寫手提供嘅代號對照，唔估 ----------
// 延遲（分鐘）按交易所，2026-10-06 由 TradingView 小工具本身顯示嘅「報價延遲 N 分鐘」核實；其他交易所標「可能有延遲」
const TV=D.tv_symbols||{};const TV_DELAY={NASDAQ:15,NYSE:15,AMEX:15,ASX:20};
function tvCard(t){const sym=TV[t];if(!sym)return '';const [ex,code]=sym.split(':');const slug=encodeURIComponent(ex)+'-'+encodeURIComponent(code.replace(/-/g,'.'));const d=TV_DELAY[ex];
 return `<div class="tv-card" data-tv="${esc(sym)}"><div class="tv-h"><b>TradingView 차트</b>${d?`<span class="tv-delay">약 ${d} 분 지연</span>`:'<span class="tv-delay unk">지연될 수 있음</span>'}<a class="tv-go" href="https://www.tradingview.com/symbols/${slug}/?aff_id=1172819&aff_sub=stock" target="_blank" rel="sponsored nofollow noopener" data-aff="tradingview" data-aff-page="stock">TradingView에서 보기 ↗</a></div><div class="tv-box"></div><a class="tv-full" href="https://www.tradingview.com/symbols/${slug}/?aff_id=1172819&aff_sub=stock" target="_blank" rel="sponsored noopener" data-aff="tradingview" data-aff-page="stock" data-ticker="${esc(t)}" data-placement="widget_below"><span class="pj-tag">홍보</span> TradingView에서 전체 차트 열기 ↗</a><div class="tv-f">무료 시세, 데이터 출처 TradingView, 투자 조언이 아닙니다.<span class="tradingview-widget-copyright"><a href="https://www.tradingview.com/" rel="noopener" target="_blank">TradingView에서 모든 시장 추적</a></span></div></div>`}
function mountTV(root){const card=root.querySelector('.tv-card[data-tv]');if(!card)return;const box=card.querySelector('.tv-box');
 const c=document.createElement('div');c.className='tradingview-widget-container';c.innerHTML='<div class="tradingview-widget-container__widget"></div>';
 const sc=document.createElement('script');sc.type='text/javascript';sc.async=true;sc.src='https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js';
 sc.textContent=JSON.stringify({symbols:[[card.dataset.tv]],chartOnly:false,width:'100%',height:'100%',autosize:true,locale:(PAGE_LANG==='en'?'en':PAGE_LANG==='ko'?'kr':'zh_TW'),colorTheme:'light',isTransparent:true,showVolume:false,showMA:false,hideDateRanges:false,hideMarketStatus:false,hideSymbolLogo:true,scalePosition:'right',scaleMode:'Normal',fontFamily:'-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif',fontSize:'10',noTimeScale:false,valuesTracking:'1',changeMode:'price-and-percent',chartType:'area',dateRanges:['1d|1','1m|30','3m|60','12m|1D','60m|1W','all|1M']});
 const gone=()=>card.remove();sc.onerror=gone;c.appendChild(sc);box.appendChild(c);
 let n=0;const tm=setInterval(()=>{if(!card.isConnected){clearInterval(tm);return}if(c.querySelector('iframe')){clearInterval(tm)}else if(++n>40){clearInterval(tm);gone()}},250)}
// 個股頁「當前觀點」先顯示幾多個帳號，其餘收埋
const SV_SHOW=8;
// 摘要開頭再寫一次「@帳號：」就刪走（卡上已經有帳號名）
const noSelf=(a,w)=>String(w||'').replace(new RegExp('^\\s*@?'+a.replace(/[^A-Za-z0-9_]/g,'')+'\\s*[:\\uFF1A]\\s*','i'),'');
function openDive(t){
 const el=document.getElementById('dive');const pr=UNC(t)?null:D.prices[t];const c=closes(t);
 const all=POSTS.filter(x=>x.t===t).sort((a,b)=>a.ms-b.ms);
 if(!all.length&&!pr){el.innerHTML=`<div class="wrap" style="padding-block:0 60px"><div class="divehead"><button class="back" id="back">← 대시보드로 돌아가기</button><div><h1>${esc(t)}</h1></div></div>${empty(`검색 결과 없음: $${esc(t)} 에 대한 데이터가 없다.`)}</div>`;showDive(el);return}
 const first=all.length?all[0].d:TODAY;
 const cards=[...new Set(all.map(x=>x.acc))].map(a=>({a,x:latest(a,t,first,TODAY)})).filter(y=>y.x);
 const cnt={bull:0,bear:0,neu:0,none:0};cards.forEach(y=>cnt[y.x.s]++);
 const w7=addDays(TODAY,-6);
 const recent=cards.map(y=>{const lastSt=all.filter(x=>x.acc===y.a&&stanced(x.s)).pop()||y.x;const inWk=all.some(x=>x.acc===y.a&&x.d>=w7);const before=all.filter(x=>x.acc===y.a&&x.d<w7&&stanced(x.s)).pop();const prevAny=prevStance(y.a,t,lastSt.ms);return {...y,cur:lastSt,ch:inWk?change(before,lastSt):null,chAll:change(prevAny,lastSt)}}).sort((a,b)=>b.cur.ms-a.cur.ms);
 const m28=all.filter(x=>x.d>=addDays(TODAY,-27)).length;
 const d14=addDays(TODAY,-13);const why=s=>all.filter(x=>x.s===s&&x.d>=d14);
 const whyList=s=>{const xs=why(s);if(!xs.length)return '<li class="note">없음</li>';const bk={};xs.forEach(x=>{const k=(x.kind&&String(x.kind).trim())?String(x.kind).trim():'기타/미분류';bk[k]=(bk[k]||0)+1});const rows=Object.entries(bk).filter(([,n])=>n>0).sort((a,b)=>b[1]-a[1]);const sum=rows.reduce((a,[,n])=>a+n,0);return rows.map(([k,n])=>`<li><span class="pill ${s}">${n}</span>${esc(k)}</li>`).join('')+`<li class="note">共 ${sum} / ${xs.length} 건</li>`;};
 const cntC={bull:0,bear:0,neu:0,none:0};cards.filter(y=>inCons(y.a)).forEach(y=>cntC[y.x.s]++);const ag=agreeLabel(cntC);
 const weeks=[0,1,2,3].map(k=>{const f=addDays(TODAY,-27+k*7),e=addDays(f,6);const ps=all.filter(x=>x.d>=f&&x.d<=e);const b=ps.filter(x=>x.s==='bull').length,r=ps.filter(x=>x.s==='bear').length;const key=ps.filter(x=>stanced(x.s)&&chgOf(x)).pop()||ps.filter(x=>explicit(x.s)).pop()||ps.filter(x=>stanced(x.s)).pop()||ps[ps.length-1];return {f,e,ps,b,r,key}});
 const evo=all.filter(x=>stanced(x.s)).slice(-6).reverse();
 const stars=all.some(x=>x.star);
 el.innerHTML=`<div class="wrap" style="padding-block:0 60px">
 <div class="divehead"><button class="back" id="back">← 대시보드로 돌아가기</button><div><h1>${esc(t)}</h1><div class="nm">${pr&&pr.name?esc(pr.name):(OV[t]&&OV[t].name&&!UNC(t)?esc(OV[t].name):'')}${UNC(t)?UNC_TXT:''}${OVN(t)}${capTag(t)}${(FLAGS[t]||[]).map(flagLink).join('')}<span class="pill ${ag.k}">${ag.l}</span></div></div>
  <div class="meta">${UNC(t)?'<span>주가 <b>표시 안 함(티커 미확인)</b></span>':c?`<span>종가 <b>${moneyT(t,c[c.length-1][1])}</b> (${esc(c[c.length-1][0])}${pr&&pr.symbol&&pr.symbol!==t?', '+esc(pr.symbol):''})</span><span>28일 변동 <b>${pctCell(t,28)}</b></span><span>1년 <b>${pctCell(t,null)}</b></span>`:'<span>주가 <b>주가 데이터 없음</b></span>'}<span>28 일 언급 <b>${m28}</b></span></div></div>
 ${tvCard(t)}
 <div class="grid">
  <section class="c4 panel"><h2>추적 계정 관점 분포 <span class="sub">${cards.length} 개 계정 언급 · 최신 게시물 기준</span></h2>${distBar(cnt)}<div style="margin-top:10px">${legend}</div>
   <div class="kpis k4" style="margin-top:12px"><div class="kpi"><div class="l">강세</div><div class="v up">${cnt.bull}</div></div><div class="kpi"><div class="l">중립</div><div class="v">${cnt.neu}</div></div><div class="kpi"><div class="l">입장 없음</div><div class="v">${cnt.none}</div></div><div class="kpi"><div class="l">약세</div><div class="v dn">${cnt.bear}</div></div></div>
   ${cards.length?`<div class="sx-avs sd-avs">${['bull','bear','neu','none'].map(k=>{const g=recent.filter(y=>y.x.s===k);return g.length?`<span class="g"><span class="lb ${k==='bull'?'b':k==='bear'?'r':''}">${SLABEL[k]} ${g.length}</span>${g.map(y=>`<a href="#sv-${esc(y.a)}" onclick="var c=document.getElementById('sv-${esc(y.a)}');if(c){var d=c.closest('details');if(d)d.open=true}">${avImg(y.a,'sx-av').replace('<img ',`<img loading="lazy" title="@${esc(y.a)}" `)}</a>`).join('')}</span>`:''}).join('')}</div><p class="note" style="margin-bottom:0">아바타를 누르면 해당 계정의 최신 의견을 볼 수 있습니다</p>`:''}</section>
  <section class="c8 panel"><h2>컨센서스와 의견 엇갈림 <span class="sub">최근 14일 근거(분석가 표시)와 관점</span></h2><div class="grid" style="gap:12px">
   <div class="c6"><div class="mod">강세 근거</div><ul class="list" style="margin-top:8px">${whyList('bull')}</ul></div>
   <div class="c6"><div class="mod">약세 근거</div><ul class="list" style="margin-top:8px">${whyList('bear')}</ul></div></div>
   <p class="note" style="margin-bottom:0">${ag.l}. ${cnt.bull&&cnt.bear?'강세와 약세 양쪽에 계정이 있다. 쟁점은 위 두 칸 참조.':cards.length<2?'현재 1개 계정만 언급해 컨센서스나 의견 엇갈림을 판단할 수 없다.':'현재 뚜렷하게 대립하는 의견은 없다.'}</p>
   ${stars?'<p class="ref">* 다종목 게시물: 분석가가 게시물 전체 입장만 표시해 여기서는 게시물 내 모든 종목에 적용했다. 원문을 확인하세요.</p>':''}</section>
  <div class="c12 dim">현재 관점 <small>계정별 최신 입장과 근거. 변화는 해당 계정의 직전 표명 대비</small></div>
  <section class="c12">${recent.length?`<div class="acc-cards sd-cards">${recent.map((y,i)=>`${i===SV_SHOW?`</div><details class="more sd-more"><summary>나머지 ${recent.length-SV_SHOW} 개 계정</summary><div class="acc-cards sd-cards">`:''}<div class="acc-card ${y.cur.s==='none'?'':y.cur.s}" id="sv-${esc(y.a)}"><div><b>${esc(nameOf(y.a))}</b> ${accLink(y.a)}${accIn(y.a)}</div><div>${pill(y.cur.s,y.cur.star)} ${y.chAll?`<span class="pill chg">${y.chAll}(이전 ${SLABEL[prevStance(y.a,t,y.cur.ms).s]})</span>`:stanced(y.cur.s)?'<span class="note">첫 표명</span>':''} ${y.ch?`<span class="pill info">최근 7일 ${y.ch}</span>`:''}</div><div class="note">${esc([y.cur.p.basis,y.cur.p.horizon].filter(Boolean).join(' · ')||'未標示依據')} · ${esc(noSelf(y.a,y.cur.why))}</div><div class="handle">${y.cur.p.time_hkt.slice(0,10)} ${y.cur.p.time_hkt.slice(11,16)} HKT <a href="${esc(y.cur.url)}" target="_blank" rel="noopener">원문 게시물 ↗</a></div></div>`).join('')}</div>${recent.length>SV_SHOW?'</details>':''}`:empty('이 종목을 언급한 계정이 없다.')}</section>
  <div class="c12 dim">최근 변화 <small>주가 추이와 어느 계정이 언제 입장을 밝히거나 바꿨는지</small></div>
  <section class="c12 panel"><div style="display:flex;justify-content:flex-end;margin-bottom:6px"><span class="rbtn" id="rbtn">${rangesFor(t).map(([k2,l])=>`<button type="button" data-r="${k2}" aria-pressed="${chartRange===k2}">${l}</button>`).join('')}</span></div><div id="chart"></div><p class="note" id="chnote" style="margin-bottom:0"></p></section>
  <div class="c12 dim">과거 흐름 <small>서사가 시간에 따라 어떻게 변했는지 보여 주며 현재 관점 이해에 도움</small></div>
  <section class="c6 panel"><h2>주별 정리 <span class="sub">최근 4주</span></h2><ul class="tl">${weeks.slice().reverse().map(wk=>`<li class="${wk.b>wk.r?'bull':wk.r>wk.b?'bear':wk.ps.length?'':'none'}"><div class="wk">${fmt(wk.f)}–${fmt(wk.e)} · ${wk.ps.length} 건 · 강 ${wk.b} / 약 ${wk.r}</div>${wk.key?`<div>@${esc(wk.key.acc)}: ${esc(noSelf(wk.key.acc,wk.key.why))} (${SLABEL[wk.key.s]})</div>`:'<div class="note">논의 없음</div>'}</li>`).join('')}</ul></section>
  <section class="c6 panel"><h2>주요 관점과 변화 <span class="sub">최신순</span></h2>${evo.length?`<details class="more"><summary>게시물별로 보기 (${evo.length} 건)</summary>${evo.map(x=>postHtml(x.p,t)).join('')}</details>`:empty('입장이 표시된 관점이 없다.')}${all.filter(x=>!stanced(x.s)).length?`<details class="more"><summary>입장 없는 언급(${all.filter(x=>!stanced(x.s)).length})</summary>${all.filter(x=>!stanced(x.s)).reverse().map(x=>postHtml(x.p,t)).join('')}</details>`:''}<p class="ref">게시물에 언급된 “자금 흐름 / 거래 기록”은 계정 자체 주장일 뿐이며 “게시물 주장 기준”으로 표시되고 검증되지 않았다.</p></section>
 </div></div>`;
 showDive(el);drawChart(t);try{mountTV(el)}catch(e){}
 const rb=document.getElementById('rbtn');if(rb)rb.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;chartRange=b.dataset.r;rb.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',x===b));drawChart(t)});
}
// ---------- 帳號頁（同樣以全頁覆蓋顯示） ----------
function openAccount(h){const el=document.getElementById('dive');const real=[...new Set(ALLP.map(p=>p.acc))].find(a=>a.toLowerCase()===h.toLowerCase())||h;const ps=ALLP.filter(p=>p.acc===real&&!p.folded_into).slice().reverse();const c=cardData(real,'0000-00-00','9999-99-99');
 const byT={};POSTS.filter(x=>x.acc===real).forEach(x=>(byT[x.t]=byT[x.t]||[]).push(x));
 const trows=Object.entries(byT).sort((a,b)=>b[1].length-a[1].length).map(([t,xs])=>{const st=xs.filter(x=>stanced(x.s));const cur=st[st.length-1];const ch=cur?change(prevStance(real,t,cur.ms),cur):null;return `<tr><td>${tkBtn(t)}</td><td class="n">${xs.length}</td><td>${cur?pill(cur.s,cur.star):pill('none')}</td><td>${ch?`<span class="pill chg">${ch}</span>`:cur?'<span class="note">첫 표명</span>':'—'}</td><td>${st.map(x=>pill(x.s,x.star)).join(' ')||'<span class="note">입장 없음</span>'}</td><td class="n">${xs[xs.length-1].p.time_hkt.slice(5,16).replace('T',' ')}</td></tr>`}).join('');
 const tracked=HANDLES.some(x=>x.toLowerCase()===h.toLowerCase());
 el.innerHTML=`<div class="wrap" style="padding-block:0 60px"><div class="divehead"><button class="back" id="back">← 대시보드로 돌아가기</button>${avatarHtml(c)}<div><h1 class="acct">${esc(c.name)}</h1><div class="nm">@${esc(real)} ${catBadge(real)||`<span class="type-pill pill info">${esc(typeLabel(real,c.type))}</span>`}<a href="${xUrl(real)}" target="_blank" rel="noopener">${platName(real)} 프로필 ↗</a>${platTag(real)}</div></div>
  <div class="meta"><span>게시물 <b>${ps.length}</b></span><span>언급 종목 <b>${Object.keys(byT).length}</b></span></div></div>
  ${c.bio?`<p class="note" style="margin-top:-6px">${esc(c.bio)}</p>`:''}
  ${ps.length?`<div class="grid"><section class="c7 panel"><h2>게시물 <span class="sub">최신순</span></h2>${ps.map(p=>postHtml(p)).join('')}</section>
  <section class="c5 panel"><h2>종목 및 입장 이력</h2>${trows?`<div class="tablewrap"><table><thead><tr><th>종목</th><th class="n"> 언급</th><th>현재</th><th>변화</th><th>과거 표명(이전 → 최신)</th><th class="n">최근</th></tr></thead><tbody>${trows}</tbody></table></div>`:empty('이 계정은 현재 데이터에서 티커를 언급하지 않았다.')}</section></div>`:empty(tracked?'이 계정은 현재 데이터 범위에 게시물이 없다.':'계정을 찾을 수 없다.')}</div>`;
 showDive(el)}
function showDive(el){linkHandles(el);el.hidden=false;fitTables(el);el.scrollTop=0;document.body.style.overflow='hidden';const b=document.getElementById('back');if(b)b.onclick=()=>{location.hash=current}}
function closeDive(){const el=document.getElementById('dive');el.hidden=true;el.innerHTML='';document.body.style.overflow=''}

// ---------- 路由 ----------
let current='daily';
// ---------- 大市背景（design/macro-strip）：指數期貨升綠跌紅；VIX／債息／油價只用箭咀不用紅綠 ----------
const MAC=D.macro||null;
const FLAGS={};(MAC&&MAC.flags||[]).forEach(f=>{(FLAGS[f.t]=FLAGS[f.t]||[]).push(f)});
const flagEst=f=>/估計|未正式|未確認|預計|estimate|expected|unconfirmed|예상|추정|미확정/i.test(f.note||'');
// 事件標籤顯示名（資料入面保留中文類別，語言版本翻譯顯示名）
const FLAGNAME={'負面新聞':'부정적 뉴스'};
const flagText=f=>`${esc(FLAGNAME[f.type]||f.type||'')}${f.date?' '+f.date.slice(5,7)+'/'+f.date.slice(8,10):''}${flagEst(f)?'(추정)':''}`;
const flagCls=f=>'flag'+(flagEst(f)?' est':'')+(f.type==='負面新聞'?' neg':'');
const flagSpan=f=>`<span class="${flagCls(f)}" title="${esc(f.note||'')}">${flagText(f)}</span>`;
const flagLink=f=>f.url?`<a class="${flagCls(f)}" href="${esc(f.url)}" target="_blank" rel="noopener" title="${esc(f.note||'')}">${flagText(f)}</a>`:flagSpan(f);
const MK_NAME={'VIX':'VIX 변동성 지수','US10Y':'미국채 10년물 금리','10 년물 국채 금리':'미국채 10년물 금리','WTI 원유':'WTI 원유 선물','WTI':'WTI 원유 선물'};
// TradingView 免費 Ticker Tape（實時，可能延遲）：載入成功先顯示，失敗就收起，唔留空位
const TAPE_SYMS=[{proName:'FOREXCOM:SPXUSD',title:'S&P 500'},{proName:'FOREXCOM:NSXUSD',title:'나스닥 100'},{proName:'FOREXCOM:DJI',title:'다우'},{proName:'PEPPERSTONE:VIX',title:'VIX 변동성 지수(CFD)'},{proName:'TVC:USOIL',title:'WTI 유가'}];
const tapeHtml=()=>`<div class="mk-live is-pending"><span class="mk-live-l"><i></i>TradingView 即時報價 (可能延遲)</span><div class="mk-live-w"></div></div>`;
function scheduleTape(root){var run=function(){try{mountTape(root)}catch(e){}};if('requestIdleCallback' in window)requestIdleCallback(run,{timeout:2000});else setTimeout(run,1)}function mountTape(root){const box=root&&root.querySelector('.mk-live');if(!box||box.dataset.on)return;box.dataset.on='1';const w=box.querySelector('.mk-live-w');
 const c=document.createElement('div');c.className='tradingview-widget-container';c.innerHTML='<div class="tradingview-widget-container__widget"></div>';
 const sc=document.createElement('script');sc.type='text/javascript';sc.async=true;sc.src='https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js';
 sc.textContent=JSON.stringify({symbols:TAPE_SYMS,showSymbolLogo:false,isTransparent:true,displayMode:'compact',colorTheme:'light',locale:(PAGE_LANG==='en'?'en':PAGE_LANG==='ko'?'kr':'zh_TW')});
 const ready=()=>{box.classList.remove('is-pending');box.classList.add('is-ready')};const gone=()=>{box.classList.remove('is-pending');box.classList.add('is-failed');if(w)w.innerHTML=''};sc.onerror=gone;c.appendChild(sc);w.appendChild(c);let n=0;const t=setInterval(()=>{if(c.querySelector('iframe')){ready();clearInterval(t)}else if(++n>40){clearInterval(t);gone()}},250)}
function macroHtml(){if(!MAC)return `<section class="c12 mk live-only" aria-label="시장 배경"><div class="mk-top"><b>시장 배경</b></div>${tapeHtml()}</section>`;
 const asMs=MAC.as_of?Date.parse(MAC.as_of.replace(' ','T')+':00+08:00'):null;
 const fmtV=r=>r.bp!=null?r.value.toFixed(3)+'%':r.value.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
 const cell=r=>{const idx=/期貨|futures|선물/i.test(r.name||'')&&!/油|oil|유가/i.test(r.name||'');const v=r.bp!=null?r.bp:r.pct;const arrow=v==null?'':v>0?'▲':v<0?'▼':'■';
  const cls=v==null?'flat':idx?(v>0?'up':v<0?'dn':'flat'):'flat';
  const txt=v==null?'—':`${arrow}${Math.abs(v).toFixed(2)}${r.bp!=null?' bp':'%'}`;
  const tMs=r.time?Date.parse(r.time.replace(' ','T')+':00+08:00'):null;const stale=asMs&&tMs&&asMs-tMs>6*36e5;
  return `<div class="mk-t"><div class="n">${esc(MK_NAME[r.name]||r.name||'')}</div><span class="v">${fmtV(r)}</span><span class="c ${cls}">${txt}</span>${stale?`<span class="stale">전 거래일 종가(${esc(r.time.slice(5,10).replace('-','/'))} ${esc(r.time.slice(11,16))} HKT)</span>`:''}</div>`};
 const srcs=[...new Set(MAC.rows.map(r=>(r.src||'').replace(/（.*?）|\(.*?\)/g,'').trim()).filter(Boolean))];
 const ev=MAC.events.map(e=>{const c=e.imp==='高'?'hi':e.imp==='中'?'mid':'';const inner=`<i></i>${e.time?`<time>${esc(e.time.slice(5,10).replace('-','/'))} ${esc(e.time.slice(11,16))}</time>`:''}${esc(e.title)}`;return e.url?`<a class="${c}" href="${esc(e.url)}" target="_blank" rel="noopener" title="중요도: ${esc(e.imp||'—')}">${inner}</a>`:`<a class="${c}" title="중요도: ${esc(e.imp||'—')}">${inner}</a>`}).join('');
 // live-only：只顯示 TradingView 實時報價條＋事件；數字格保留喺 markup（CSS 隱藏），截至／來源字眼屬數字格，一齊收起
 return `<section class="c12 mk live-only" aria-label="시장 배경"><div class="mk-top"><b>시장 배경</b></div>${MAC.rows.length?`<div class="mk-row">${MAC.rows.map(cell).join('')}</div>`:''}${tapeHtml()}${ev?`<div class="mk-ev">${ev}</div>`:''}</section>`}

// ---------- 今日重點卡（design/highlights-cards 結構）：文字逐字照錄，數字自動加粗 ----------
const toneCls=t=>{t=t||'';const k=/^(看好|睇好|看多|偏多|Bullish|강세)/i.test(t)?'bull':/^(看淡|睇淡|看空|偏空|Bearish|약세)/i.test(t)?'bear':'neu';return k+(k!=='neu'&&/條件|conditional|조건/i.test(t)?' cond':'')};
const numHi=s=>esc(s).replace(/([$＄]?\d[\d,]*(?:\.\d+)?(?:\s?(?:%|倍|億美元|億|萬|美元))?)/g,'<em>$1</em>');
function hlTicker(t){const c=UNC(t)?null:closes(t);const loading=!coreDone&&!(D.prices&&D.prices[t]);let svg='<svg class="empty" viewBox="0 0 120 28" aria-hidden="true"></svg>',chg=`<span class="nopx">${UNC(t)?'티커 미확인':loading?'로딩 중…':'주가 데이터 없음'}</span>`;
 if(c){const lim=new Date(Date.parse(c[c.length-1][0])-28*DAY).toISOString().slice(0,10);const r=c.filter(x=>x[0]>=lim);const v=r.map(x=>x[1]);
  if(v.length>=2){const mn=Math.min(...v),mx=Math.max(...v),sp=(mx-mn)||1;const up=v[v.length-1]>=v[0];
   svg=`<svg viewBox="0 0 120 28" preserveAspectRatio="none" aria-hidden="true"><polyline points="${v.map((y,i)=>`${(i/(v.length-1)*120).toFixed(1)},${(26-(y-mn)/sp*24).toFixed(1)}`).join(' ')}" style="fill:none;stroke:var(--${up?'bull':'bear'});stroke-width:1.8;stroke-linejoin:round"/></svg>`}
  const ch=pchg(t,28),last=c[c.length-1][1],cur=curOf(t);
  chg=`<span class="chg ${ch==null?'':ch>=0?'up':'dn'}">${ch==null?'—':(ch>=0?'+':'')+ch.toFixed(1)+'%'}<small>28 일 · ${cur==='USD'?'USD':(CURNAME[cur]||cur)} ${money(last)}${capKind(t)?' · '+CAPSHORT[capKind(t)]:''}${(FLAGS[t]||[]).map(f=>' · '+flagText(f)).join('')}</small></span>`}
 return `<a class="hl-tk" href="#stock/${encodeURIComponent(t)}" title="${OV[t]&&OV[t].note&&!UNC(t)?esc(OV[t].note):'$'+esc(t)+' 종목 심층 분석'}"><b>$${esc(t)}</b>${svg}${chg}</a>`}
function hlAvatar(h){const i=infoOf(h);const name=i.name||h;return `<a href="${xUrl(h)}" target="_blank" rel="noopener" title="@${esc(h)}" aria-label="@${esc(h)} X 프로필">${i.avatar?`<img src="${esc(i.avatar)}" alt="">`:esc((Array.from(name.replace(/^[^\p{L}\p{N}]+/u,''))[0]||'@').toUpperCase())}</a>`}
// 寫手嘅 tone（看好／看淡／分歧／中性）用返全站同一套字眼顯示，en／ko 亦會翻譯（原本直接顯示資料入面嘅中文）
const TONE_TXT={'看好':'강세','看淡':'약세','分歧':'의견 엇갈림','中性':'중립'};
function highlightsHtml(date){const H=D.highlights&&D.highlights[date];if(!H||!H.cards||!H.cards.length)return '';
 const card=c=>`<article class="hl ${toneCls(c.tone)}"><div class="hl-body"><div class="hl-tags">${c.theme?`<span class="hl-theme">${esc(c.theme)}</span>`:''}${c.tone?`<span class="hl-tone">${esc(TONE_TXT[c.tone]||c.tone)}</span>`:''}</div><h3>${esc(c.headline)}</h3>${c.big?`<div class="hl-big${c.tickers.length?' inline':''}"><div class="v">${esc(c.big.value)}</div>${c.big.label?`<div class="l">${esc(c.big.label)}</div>`:''}</div>`:''}${c.tickers.length?`<div class="hl-tks">${c.tickers.map(hlTicker).join('')}</div>`:''}${c.points.length?`<ol>${c.points.slice(0,3).map(x=>`<li><span>${numHi(x)}</span></li>`).join('')}</ol>`:''}</div>${c.handles.length||c.source_note?`<div class="hl-foot">${c.handles.length?`<div class="hl-avs">${c.handles.map(hlAvatar).join('')}</div>`:''}<div class="hl-who">${c.handles.map(h=>`<a href="${xUrl(h)}" target="_blank" rel="noopener">@${esc(h)}</a>`).join(', ')}${c.handles.length&&c.source_note?'<br>':''}${c.source_note?esc(c.source_note):''}</div></div>`:''}</article>`;
 return `<section class="c12 hl-sec" aria-label="오늘의 핵심"><div class="hl-head"><h2>오늘의 핵심</h2>${H.range?`<span class="rg">${esc(H.range)}</span>`:''}</div><div class="hl-grid">${H.cards.slice(0,3).map(card).join('')}</div>${H.stats_note?`<p class="note" style="margin:10px 0 0">${esc(H.stats_note)}</p>`:''}</section>`}

// ---------- 追蹤名單（設計稿 viewTracked；資料來自追蹤名單＋帳號資料） ----------
const xUrl=h=>{const m=PLAT[String(h).toLowerCase()];return m&&m.p==='truthsocial'?(m.url||'https://truthsocial.com/@'+encodeURIComponent(h)):'https://x.com/'+encodeURIComponent(h)};
const infoOf=h=>ACCINFO[h]||(Object.entries(ACCINFO).find(([k])=>k.toLowerCase()===h.toLowerCase())||[])[1]||{};
function viewTracked(){const T=D.tracked;
 if(!T||!T.accounts||!T.accounts.length)return `<div class="grid"><section class="c12">${empty('추적 명단 데이터가 아직 없다.')}</section></div>`;
 const L=T.accounts.map(a=>{const i=infoOf(a.handle);return {h:a.handle,n:a.name||i.name||a.handle,av:i.avatar||null,bio:a.role||i.bio||'',role:!!a.role,real:!!a.name,cat:a.category||null}});
 const inData=h=>HANDLES.some(x=>x.toLowerCase()===h.toLowerCase());
 const item=a=>`<div class="trk">${avatarHtml({avatar:a.av,name:a.n})}<div class="who"><div class="nm2${a.real?' acc-name':''}" title="${esc(a.n)}">${inData(a.h)?`<a href="#account/${encodeURIComponent(a.h)}">${esc(a.n)}</a>`:esc(a.n)}</div><div class="hd2"><a href="${xUrl(a.h)}" target="_blank" rel="noopener">@${esc(a.h)}</a> ${platTag(a.h)}</div>${a.role?`<div class="acc-role">${esc(a.bio)}</div>`:(a.bio?`<div class="bio2" title="${esc(a.bio)}">${esc(a.bio)}</div>`:'')}</div><div class="side"><a class="xlink" href="${xUrl(a.h)}" target="_blank" rel="noopener">${platName(a.h)} ↗</a></div></div>`;
 const cats=(T.categories||[]).map(c=>c.name);const groups=(T.categories||[]).map(c=>({...c,list:L.filter(a=>a.cat===c.name)}));
 const rest=L.filter(a=>!a.cat||!cats.includes(a.cat));if(rest.length)groups.push({name:groups.length?'기타':'전체 계정',desc:null,list:rest});
 return `<div class="grid">${groups.filter(g=>g.list.length).map(g=>`<section class="c12"><div class="trk-group"><h3>${esc(g.name)}</h3><span class="cnt">${g.list.length} 개</span>${g.consensus===false?`<span class="nocon">헤드라인만 리포스트, 컨센서스에 미포함</span>`:''}${g.desc?`<p>${esc(g.desc)}</p>`:''}</div><div class="trk-grid">${g.list.map(item).join('')}</div></section>`).join('')}</div>`}

// ---------- @帳號前的細頭像（設計稿 a.xh / .xh-av；CSS 在 cream-skin.css） ----------
let AVMINI=D.avmini||{};
const miniAv=h=>{const i=infoOf(h);const src=(i.avatar&&/^data:image\//.test(i.avatar))?i.avatar:AVMINI[h.toLowerCase()];
 if(src){const im=document.createElement('img');im.className='xh-av';im.src=src;im.alt='';return im}
 const sp=document.createElement('span');sp.className='xh-av ini';sp.setAttribute('aria-hidden','true');sp.textContent=(h.replace(/^_+/,'')[0]||'@').toUpperCase();return sp};
function addMiniAvatars(root){if(!root)return;root.querySelectorAll('a[href^="https://x.com/"],a[href^="https://truthsocial.com/@"]').forEach(a=>{if(a.closest('svg,.acc,.trk,.post-who,.ch-avs,.ch-row'))return;const m=a.textContent.trim().match(/^@([A-Za-z0-9_]{1,15})$/);if(!m||a.querySelector('.xh-av'))return;a.classList.add('xh');a.prepend(miniAv(m[1]))})}

// ---------- 所有 @handle 都連到 X 個人頁（掃描畫面上未連結的文字） ----------
const HANDLE_RE=/(^|[^A-Za-z0-9_\/.@])@([A-Za-z0-9_]{1,15})(?![A-Za-z0-9_])/g;
// 窄螢幕放唔落的表格（每週、每月等）改為逐行卡片：第一欄（股票）可換行，其餘欄位附欄名，
// 確保「一年股價」「淨看多變化」等右邊欄位唔使橫向捲動都見到；矩陣表維持原樣；
// 欄名用 textContent：innerText 喺未畫出嘅區（content-visibility）係空字串，手機卡片會冇欄名
function fitTables(root){if(!root)return;root.querySelectorAll('.tablewrap,.lb-wrap').forEach(w=>{if(w.querySelector('table.matrix'))return;const t=w.querySelector('table');if(!t)return;
 const hs=[...t.querySelectorAll('thead th')].map(th=>th.textContent.replace(/[↓↑]/g,'').replace(/\s+/g,' ').trim());t.querySelectorAll('tbody tr').forEach(tr=>[...tr.children].forEach((td,i)=>{if(hs[i]&&!td.dataset.l)td.dataset.l=hs[i]}));
 w.classList.remove('stack');if(w.scrollWidth>w.clientWidth+1)w.classList.add('stack')})}
// 長列表唔再喺框入面捲（手機手指會卡住、框喺半行切斷）：先出頭幾項，其餘按「再顯示 N 項」先開（Tim，2026-10-21）
const CLAMP=[['.cc-grid',4],['.fav-grid',6],['.acc-grid',6],['.acc-cards',6],['.trk-grid',8],['.multi-scroll tbody',10],['.cons-scroll tbody',10],['.lb-wrap tbody',10]];
function clampLists(root){if(!root)return;CLAMP.forEach(([sel,n])=>root.querySelectorAll(sel).forEach(box=>{if(box.closest('.sd-cards')||box.dataset.cl)return;const items=[...box.children];if(items.length<=n+2)return;box.dataset.cl='1';items.slice(n).forEach(x=>x.classList.add('cl-h'));
 const b=document.createElement('button');b.type='button';b.className='more-btn cl-more';b.textContent=`더 보기: ${items.length-n} 개`;b.onclick=()=>{items.forEach(x=>x.classList.remove('cl-h'));b.remove()};(box.tagName==='TBODY'?box.closest('.tablewrap,.lb-wrap'):box).after(b)}))}
addEventListener('resize',()=>{fitTables(document.getElementById('view'));const d=document.getElementById('dive');if(d&&!d.hidden)fitTables(d)});
function linkHandles(root){if(!root)return;const w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode:n=>{const p=n.parentElement;if(!p||p.closest('a,button,script,style,textarea,title,option,svg'))return NodeFilter.FILTER_REJECT;return /@[A-Za-z0-9_]/.test(n.nodeValue)?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_REJECT}});
 const nodes=[];while(w.nextNode())nodes.push(w.currentNode);
 for(const n of nodes){const t=n.nodeValue;HANDLE_RE.lastIndex=0;if(!HANDLE_RE.test(t))continue;HANDLE_RE.lastIndex=0;
  const frag=document.createDocumentFragment();let last=0,m;
  while((m=HANDLE_RE.exec(t))){const at=m.index+m[1].length;frag.append(t.slice(last,at));const a=document.createElement('a');a.className='handle';a.href=xUrl(m[2]);a.target='_blank';a.rel='noopener';a.textContent='@'+m[2];frag.append(a);last=at+1+m[2].length}
  frag.append(t.slice(last));n.replaceWith(frag)}
 addMiniAvatars(root)}
// ---------- 宏觀（2026-10-13）：全部追蹤帳號的宏觀貼文按 9 個固定主題分組；立場＝對美股的影響 ----------
// 主題：SuperGrok 的 macro_theme；舊貼文用 GitHub 關鍵字分類（macro_kw，沒有立場，不計入人數）
const MTH=[['rates','금리 / 연준'],['inflation','인플레이션'],['jobs','고용'],['growth','경제성장 / 경기침체'],['yields','채권 금리'],['fx','달러 / 환율'],['energy','유가 / 에너지'],['policy','관세 / 정책 / 지정학'],['other','기타']];
const MIMP={bullish:'bull',bearish:'bear',neutral:'neu'},MIMPW={bull:'호재',bear:'악재',neu:'중립',none:'입장 없음'};
const mThemeOf=p=>p.macro_theme!==undefined?p.macro_theme:(p.macro_kw||null);
const mImpOf=p=>MIMP[p.macro_impact]||'none';
function mStat(th,from,to){const ps=rawIn(from,to).filter(p=>valid(p)&&p.macro&&mThemeOf(p)===th);const last={},lastS={};
 ps.forEach(p=>{if(!last[p.acc]||p.ms>=last[p.acc].ms)last[p.acc]=p;if(mImpOf(p)!=='none'&&(!lastS[p.acc]||p.ms>=lastS[p.acc].ms))lastS[p.acc]=p});
 const c={bull:0,bear:0,neu:0};Object.values(lastS).forEach(p=>c[mImpOf(p)]++);
 return {rows:Object.values(last).sort((a,b)=>(mImpOf(b)!=='none')-(mImpOf(a)!=='none')||b.ms-a.ms),c,n:c.bull+c.bear+c.neu,posts:ps.length}}
function mArrow(c,c0){if(c.n<1||c0.n<2)return '';const sc=x=>(x.c.bull-x.c.bear)/x.n,dlt=sc(c)-sc(c0);
 return dlt>0.15?'<span class="m-arr up" title="직전 7일과 비교">▲ 개선</span>':dlt<-0.15?'<span class="m-arr dn" title="직전 7일과 비교">▼ 악화</span>':'<span class="m-arr" title="직전 7일과 비교">= 변화 없음</span>'}
function viewMacro(){const to=TODAY,from=addDays(TODAY,-6),pt=addDays(from,-1),pf=addDays(from,-7);
 const all=MTH.map(([k,l])=>({k,l,s:mStat(k,from,to),s0:mStat(k,pf,pt)}));
 const row=p=>{const s=mImpOf(p);return `<li class="m-row"><a class="post-who" href="${xUrl(p.acc)}" target="_blank" rel="noopener">${avImg(p.acc,'post-av')}<span><b>${esc(nameOf(p.acc))}</b><small>@${esc(p.acc)}</small></span></a><div class="m-body"><div class="hd"><span class="pill ${s}">${MIMPW[s]}</span><span>${p.time_hkt.slice(5,10).replace('-','/')} ${p.time_hkt.slice(11,16)} HKT</span><a href="${esc(p.url)}" target="_blank" rel="noopener">원문 게시물 ↗</a></div><p class="tx">${p.summary_zh?esc(p.summary_zh):'<span class="note">아직 요약이 없다. 원문 게시물을 확인하세요</span>'}</p></div></li>`};
 const card=t=>{const s=t.s,c=s.c;const accs=s.rows.length;
  const head=accs?`<span class="m-cnt"><span class="pill bull">호재 ${c.bull}</span><span class="pill bear">악재 ${c.bear}</span><span class="pill neu">중립 ${c.neu}</span>${mArrow(s,t.s0)}</span>`:'<span class="note">최근 7일간 언급 없음</span>';
  return `<details class="m-th${accs?'':' m-none'}"><summary><span class="m-nm">${esc(t.l)}</span>${accs?`<span class="note">${accs} 개 계정</span>`:''}${head}</summary>${accs?`${s.n?distBar({bull:c.bull,neu:c.neu,none:0,bear:c.bear}):''}${accs>s.n?`<p class="note">${accs-s.n} 개 계정의 게시물은 입장이 표시되지 않아(이전 게시물은 키워드로만 분류) 집계에서 제외됩니다.</p>`:''}<ul class="list m-list">${s.rows.slice(0,8).map(row).join('')}</ul>${accs>8?`<details class="m-more"><summary>나머지 ${accs-8} 개 계정</summary><ul class="list m-list">${s.rows.slice(8).map(row).join('')}</ul></details>`:''}`:''}</details>`};
 const nAcc=new Set(rawIn(from,to).filter(p=>valid(p)&&p.macro&&mThemeOf(p)).map(p=>p.acc)).size;
 return `<div class="grid">${macroHtml()}
 <section class="c12 panel m-sec"><div class="range">집계 ${from} ~ ${to} (7일)</div>
  <h2>매크로 관점 <span class="sub">${nAcc} 개 계정 · 입장 = 미국 주식에 대한 영향 · 계정별 최신 의견만</span></h2>
  <p class="note">▲▼ 직전 7일과 비교: 호재 비율에서 악재 비율을 뺀 값이 15%p 넘게 변할 때만 표시하며, 직전 7일에 입장을 밝힌 계정이 2개 미만이면 비교하지 않습니다. 매크로 주제 없이 지수 등락만 다룬 게시물은 여기에 넣지 않습니다.</p>
  <div class="m-grid">${all.map(card).join('')}</div></section></div>`}
const VIEWS={daily:viewDaily,weekly:viewWeekly,monthly:viewMonthly,macro:viewMacro,tracked:viewTracked};
async function rebuildDerived(){
 D.prices=D.prices||{};D.accounts=D.accounts||{};D.posts=D.posts||[];D.intraday=D.intraday||{};D.avmini=D.avmini||{};D.quotes=D.quotes||{};
 ACCINFO=D.accounts||{};
 NAMES={};D.posts.forEach(p=>{if(p.name&&!p.reposted_by)NAMES[p.handle]=p.name});
 CUT=D.meta.cutoff_hkt?Date.parse(D.meta.cutoff_hkt):Math.max(0,...D.posts.map(p=>Date.parse(p.time_utc)));
 TODAY=hkDate(CUT);
 await y();
 ALLP=[];
 {const _ps=D.posts;for(let _i=0;_i<_ps.length;_i++){const p=_ps[_i];ALLP.push({...p,text:undefined,summary_zh:HAS_ZH(p.zh_summary)?p.zh_summary:HAS_ZH(p.summary_zh)?p.summary_zh:'',tokenize:HAS_ZH(p.zh_summary)&&PAGE_LANG!=='en'?false:p.tokenize,tickers:[...new Set([...(p.tickers||[]),...Object.keys(p.stance_by_ticker&&typeof p.stance_by_ticker==='object'?p.stance_by_ticker:{})].map(t=>String(t).replace(/^\$/,'').toUpperCase()))],ms:Date.parse(p.time_utc),acc:p.reposted_by||p.handle,date:p.time_hkt.slice(0,10)});if((_i&7)===7)await y()}ALLP.sort((a,b)=>a.ms-b.ms)}
 await y();
 POSTS=[];
 {const _vp=ALLP.filter(valid);for(let _i=0;_i<_vp.length;_i++){const p=_vp[_i];for(let _j=0;_j<p.tickers.length;_j++){const t=p.tickers[_j];const r=stanceOf(p,t);POSTS.push({p,t,acc:p.acc,s:r.s,star:r.star,ms:p.ms,d:p.date,kind:p.basis||null,why:p.summary_zh||'',url:p.url})}if((_i&7)===7)await y()}}
 WIN=new Map();
 TICKERS=[...new Set(POSTS.map(x=>x.t))].sort();
 DATES=[...new Set(ALLP.map(p=>p.date))].sort();
 FOLD={};ALLP.forEach(p=>{if(p.folded_into)(FOLD[p.folded_into]=FOLD[p.folded_into]||[]).push(p)});
 INTRA=D.intraday||{};
 AVMINI=D.avmini||{};
}
let coreDone=!(D._ext&&D._ext.core),coreP=null,postCursor=0,pageP=null,postsFailed=false,allP=null;
let histDone=!(D._ext&&D._ext.hist),histP=null;
function loadHist(){if(histDone)return Promise.resolve();if(histP)return histP;histP=fetch(extUrl(D._ext.hist)).then(function(r){if(!r.ok)throw new Error('hist '+r.status);return r.json()}).then(function(j){var s=j.summaries||{};D.summaries=D.summaries||{};Object.keys(s).forEach(function(k){D.summaries[k]=(s[k]||[]).concat(D.summaries[k]||[])});if(j.briefings)D.briefings=j.briefings.concat(D.briefings||[]);histDone=true;return rebuildDerived().then(function(){document.dispatchEvent(new Event('dash-data'));return render()})}).catch(function(e){histDone=true;console.error(e)});return histP}
function extUrl(p){var v=(D.meta&&D.meta.build_id)||'';return p+(p.indexOf('?')<0?'?v=':'&v=')+encodeURIComponent(v)}
function uiText(zh,en,ko){var l=document.documentElement.lang||'';return /^ko/i.test(l)?ko:/^en/i.test(l)?en:zh}
function postsReady(){if(postsFailed)return true;var pages=D._ext&&D._ext.posts;return !pages||postCursor>=pages.length}
function loadCore(){if(coreDone)return Promise.resolve();if(coreP)return coreP;
 coreP=fetch(extUrl(D._ext.core)).then(function(r){if(!r.ok)throw new Error('core '+r.status);return r.text()}).then(function(raw){return parseJSON(raw)}).then(function(j){
  Object.keys(j).forEach(function(k){if(k!=='posts'&&k!=='_ext')D[k]=j[k]});
  coreDone=true;ACCINFO=D.accounts||{};INTRA=D.intraday||{};AVMINI=D.avmini||{};
  NAMES={};D.posts.forEach(function(p){if(p.name&&!p.reposted_by)NAMES[p.handle]=p.name});
  document.dispatchEvent(new Event('dash-data'))});return coreP}
function loadNextPosts(){if(postsReady())return Promise.resolve();if(pageP)return pageP;var url=D._ext.posts[postCursor];
 pageP=fetch(extUrl(url)).then(function(r){if(!r.ok)throw new Error('posts '+r.status);return r.text()}).then(function(raw){return parseJSON(raw)}).then(function(arr){
  postCursor++;D.posts=D.posts.concat(arr);return rebuildDerived().then(function(){document.dispatchEvent(new Event('dash-data'))});
 }).catch(function(e){postsFailed=true;window.__postsFailed=true;console.error(e)}).finally(function(){pageP=null});return pageP}
function loadAllPosts(){if(postsReady()){window.__postsReady=true;return Promise.resolve()}if(allP)return allP;
 function step(){if(postsReady()){window.__postsReady=true;allP=null;return Promise.resolve()}return loadNextPosts().then(step)}
 allP=step();return allP}
function refreshPriceChips(){var view=document.getElementById('view');if(!view)return;view.querySelectorAll('a.hl-tk[href]').forEach(function(a){var m=(a.getAttribute('href')||'').match(/#stock\/([^/?#]+)/);if(!m)return;var t=decodeURIComponent(m[1]).toUpperCase();var tmp=document.createElement('div');tmp.innerHTML=hlTicker(t);var neu=tmp.firstChild;if(neu)a.replaceWith(neu)});view.querySelectorAll('.dayrange').forEach(function(el){el.style.minHeight=el.style.minHeight||'40px'});var ld=view.querySelector('#dash-load');if(ld&&coreDone)ld.remove()}
function mountStatus(){if(coreDone)return;var v=document.getElementById('view');if(!v||document.getElementById('dash-load'))return;
 var p=document.createElement('p');p.id='dash-load';p.className='note';p.style.margin='0 0 8px';
 p.textContent=uiText('나머지 자료를 불러오는 중','Loading the rest','나머지 자료를 불러오는 중');v.insertBefore(p,v.firstChild)}
function mountMore(){if(postsReady())return;var h=decodeURIComponent((location.hash||'#daily').slice(1));
 if(h==='weekly'||h==='monthly'||h==='macro'||/^stock/.test(h)||/^account/.test(h))return;
 var v=document.getElementById('view');if(!v||document.getElementById('load-more'))return;
 var p=document.createElement('p');p.style.cssText='text-align:center;margin:16px 0';
 var b=document.createElement('button');b.type='button';b.className='more-btn';b.id='load-more';
 b.textContent=uiText('더 보기','Load more','더 보기');
 b.addEventListener('click',function(){b.disabled=true;loadNextPosts().then(function(){render()})});
 p.appendChild(b);v.appendChild(p)}
window.__loadCore=loadCore;window.__loadAllPosts=loadAllPosts;window.__postsReady=postsReady();window.__dashReady=coreDone;
async function render(){const h=decodeURIComponent((location.hash||'#daily').slice(1));
 const ms=h.match(/^stock[\/-](.+)$/),ma=h.match(/^account\/(.+)$/);
 if((ms||ma||h==='weekly'||h==='monthly'||h==='macro')&&(!postsReady()||!coreDone)){var v=document.getElementById('view');if(v&&!v.querySelector('#dash-wait'))v.insertAdjacentHTML('afterbegin','<p id="dash-wait" class="note">'+esc(uiText('나머지 자료를 불러오는 중','Loading the rest','나머지 자료를 불러오는 중'))+'</p>');Promise.all([loadAllPosts(),loadCore()]).then(function(){render()}).catch(function(e){console.error(e);coreDone=true;postsFailed=true;render()});return}
 if(ms||ma){if(!document.getElementById('view').innerHTML)await drawView();try{ms?openDive(ms[1].toUpperCase()):openAccount(ma[1])}catch(e){console.error(e);document.getElementById('dive').innerHTML='<div class="wrap">'+empty('화면 표시 오류: '+esc(e.message))+'</div>';showDive(document.getElementById('dive'))}return}
 closeDive();current=VIEWS[h]?h:'daily';await drawView();
 if(h==='donate')setTimeout(()=>{const f=document.querySelector('[data-jump="donate"]');if(f)f.click()},50)}
let lastViewKey=null,lastViewHtml=null;
async function drawView(){document.querySelectorAll('nav.tabs button[data-v]').forEach(b=>b.setAttribute('aria-selected',b.dataset.v===current));
 try{const html=await Promise.resolve(VIEWS[current]());const view=document.getElementById('view');
  await y();
  if(view.querySelector('.mk-live[data-on]')&&lastViewKey===current&&lastViewHtml===html){if(coreDone){const ld=view.querySelector('#dash-load');if(ld)ld.remove()}mountStatus();mountMore()}
  else{const oldTape=view.querySelector('.mk-live[data-on]');var parts=html.split('<!--DY-->');if(parts.length<2||html.length<100000){view.innerHTML=html;await y()}else{view.innerHTML=parts[0];await y();var g=view.querySelector('.grid')||view;for(var _i=1;_i<parts.length;_i++){var chunk=parts[_i];if(_i===parts.length-1)chunk=chunk.replace(/\s*<\/div>\s*$/,'');g.insertAdjacentHTML('beforeend',chunk);await y()}}if(oldTape){const nw=view.querySelector('.mk-live');if(nw)nw.replaceWith(oldTape)}mountStatus();mountMore();lastViewKey=current;lastViewHtml=html;if(typeof window.__dashLate==='function'){var _late=window.__dashLate,_g=view.querySelector('.grid');window.__dashLate=null;var _run=function(){Promise.resolve(_late(_g)).catch(function(e){console.error(e)})};if('requestIdleCallback'in window)requestIdleCallback(_run,{timeout:1500});else setTimeout(_run,0);}var _v=view;var _fin=function(){try{linkHandles(_v);fitTables(_v);clampLists(_v);scheduleTape(_v)}catch(e){}};if('requestIdleCallback' in window)requestIdleCallback(_fin,{timeout:1500});else setTimeout(_fin,1)}}catch(e){console.error(e);document.getElementById('view').innerHTML=empty('화면 표시 오류: '+esc(e.message))}}
document.addEventListener('click',e=>{const sx=e.target.closest('[data-sx-exp]');if(sx&&_sxExpand){e.preventDefault();var html=_sxExpand();_sxExpand=null;if(html)sx.insertAdjacentHTML('beforebegin',html);var list=sx.closest('.sx-list');if(list)list.classList.add('all');sx.remove();return}const rd=e.target.closest('details[data-rest-exp]');if(rd&&_restExpand&&!rd.dataset.restDone){/* filled on toggle */} const b=e.target.closest('[data-tk]');if(b){e.preventDefault();location.hash='stock/'+b.dataset.tk;return}
 const v=e.target.closest('nav.tabs button[data-v]');if(v){location.hash=v.dataset.v;return}
 const card=e.target.closest('.acc[data-href]');if(card&&!e.target.closest('a,button')){location.hash=card.dataset.href}});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!document.getElementById('dive').hidden){location.hash=current;return}const card=e.target.closest&&e.target.closest('.acc[data-href]');if(card&&e.key==='Enter'&&e.target===card)location.hash=card.dataset.href});
window.addEventListener('hashchange',render);
document.addEventListener('toggle',function(e){var d=e.target;if(!d||!d.matches)return;if(d.matches('details[data-sx-body]')&&d.open&&_sxBodies&&_sxBodies.has(d.dataset.sxBody)){var bh=_sxBodies.get(d.dataset.sxBody);_sxBodies.delete(d.dataset.sxBody);try{var h=bh();if(h)d.insertAdjacentHTML('beforeend',h)}catch(err){console.error(err)}return}if(d.matches('details[data-rest-exp]')&&!d.dataset.restDone&&_restExpand){d.dataset.restDone='1';var html=_restExpand();_restExpand=null;if(html)d.insertAdjacentHTML('beforeend',html)}},true);
let rT=null;window.addEventListener('resize',()=>{clearTimeout(rT);rT=setTimeout(()=>{const m=decodeURIComponent(location.hash.slice(1)).match(/^stock[\/-](.+)$/);if(m)drawChart(m[1].toUpperCase())},150)});
// 頁首
function paintChrome(){const m=D.meta;const cut=document.getElementById('cutoff');cut.textContent=m.cutoff_hkt?m.cutoff_hkt.slice(0,10)+' '+m.cutoff_hkt.slice(11,16)+' (HKT)':'데이터 부족';if(m.generated_hkt)cut.title='本頁重建於 '+m.generated_hkt+' HKT';
 const slots=m.update_slots_hkt||[];const now=Date.now(),base=Math.max(now,Date.parse((m.generated_hkt||'').replace(' ','T')+':00+08:00')||0);let next=null;
 for(let k=0;k<3&&!next;k++){const d=hkDate(base+k*DAY);for(const s of slots){const t=Date.parse(`${d}T${s}:00+08:00`);if(t>base){next=t;break}}}
 document.getElementById('nextup').textContent=next?`${hkDate(next)} ${hm(next)}(예정)`:'—';
 document.getElementById('acccount').textContent=(D.tracked&&D.tracked.accounts&&D.tracked.accounts.length)||HANDLES.length;
 const srcs={};Object.entries(D.prices).filter(([t])=>!UNC(t)&&isUS(t)).forEach(([t,p])=>(srcs[p.source]=srcs[p.source]||[]).push('$'+t));const asof=Object.entries(D.prices).filter(([t])=>isUS(t)).map(([,p])=>p.as_of).sort().pop();
 const nonUS=Object.entries(D.prices).filter(([t])=>!UNC(t)&&!isUS(t)).map(([t,p])=>`$${esc(t)} 는 ${esc(p.symbol||t)} (${esc((OV[t]&&OV[t].exchange)||p.exchange||'')}, ${CURNAME[curOf(t)]||curOf(t)}, ${esc(p.source)}, 기준일 ${esc(p.as_of)} ${tradeDay(t)}) 시세 사용, 비미국 종목`);const fet=Object.values(D.prices).map(p=>p.fetched_hkt).sort().pop();const unc=Object.keys(OV).filter(UNC);
 document.getElementById('foot').innerHTML=`<p><b>면책 조항: </b>모든 내용은 추적 계정의 공개 게시물을 정리한 것으로 해당 계정의 주장만 반영한다. 모든 “자금 흐름” 또는 “거래 기록”은 “게시물 주장 기준”이며 검증되지 않았다. 이 페이지는 투자 조언이 아닙니다.</p>
<p>입장 데이터: ${m.stance.files.length?`분석가가 게시물별로 표시( ${m.stance.matched} 건 표시). 입장이 표시되지 않은 게시물은 모두 “입장 없음”으로 분류한다.`:'아직 분석가 입장 데이터가 없어 모든 게시물을 임시로 “입장 없음”으로 분류한다.'}</p>
<p>${Object.keys(srcs).length?`가격 기준 ${esc(asof)} (미국 동부 거래일): ${Object.keys(srcs).map(esc).join(', ')} 일간 종가, 수집 시각 ${esc(fet)} HKT`:'주가 데이터 없음'}${(()=>{const pm=m.price_missing.filter(t=>!UNC(t));const wn=pm.filter(t=>OV[t]&&OV[t].price_note),wo=pm.filter(t=>!(OV[t]&&OV[t].price_note));return (wn.length?'; '+wn.map(t=>'$'+esc(t)+'  → '+esc(OV[t].price_note)).join('; '):'')+(wo.length?`; 아직 주가 데이터 없음: ${wo.map(t=>'$'+esc(t)).join(' ')}`:'')})()}${nonUS.length?'; 비미국 종목은 현지 거래소와 통화로 표시(종목 페이지에 표기)':''}. </p>
${MAC&&MAC.rows.length?`<p>시장 데이터: ${[...new Set(MAC.rows.map(r=>(r.src||'').replace(/（.*?）|\(.*?\)/g,'').trim()).filter(Boolean))].map(esc).join(', ')||'—'}${MAC.as_of?`, 기준일 ${esc(MAC.as_of)} HKT`:''}. </p>`:''}<p>모든 시간은 홍콩 시간(HKT, UTC+8)이다. 계정 아바타와 소개는 각 계정의 X 프로필에서 가져왔다.</p>
<p>일부 링크는 제휴 링크이며, 이를 통해 가입·구매 시 추가 비용 없이 수수료를 받을 수 있습니다. 이는 집계 및 <a href="/robot.html">로봇 픽</a>. 本站內容不構成投資建議. </p>
<p><a href="tools/">도구</a> · <a href="support/">후원하기</a> · <a href="newsletter/">뉴스레터</a> · <a href="https://www.tradingview.com/?aff_id=1172819" rel="sponsored noopener" target="_blank">TradingView <span class="pj-tag">홍보</span></a> · <a href="https://www.stockrover.com/thecrowdtape" rel="sponsored nofollow noopener" target="_blank" data-tool="stockrover">Stock Rover <span class="pj-tag">홍보</span></a> · <a href="advertise/">광고 제휴</a> · <a href="about/">소개 및 방법론</a></p>`;linkHandles(document.getElementById('foot'))}
(async function bootPaint(){
await y();
try{paintChrome();await render()}catch(e){console.error(e)}
if(!coreDone){
  var _bootCore=function(){loadCore().then(function(){window.__dashReady=true;paintChrome();var v=document.getElementById('view');if(v&&v.querySelector('.grid')&&(lastViewKey===current||lastViewKey==='daily')){if(typeof refreshPriceChips==='function')refreshPriceChips();mountStatus();mountMore();return}return render()}).catch(function(e){console.error(e);coreDone=true;window.__dashReady=true;paintChrome();return render()})};
  await y();
  if('requestIdleCallback'in window)requestIdleCallback(_bootCore,{timeout:3500});else setTimeout(_bootCore,1200);
}else window.__dashReady=true;
})();
document.addEventListener('click',function(e){var a=e.target&&e.target.closest&&e.target.closest('a[href]');if(!a||typeof gtag!=='function')return;var u=a.href,h='';try{h=new URL(u).hostname.toLowerCase()}catch(err){return}if(h==='x.com'||h.endsWith('.x.com')||h==='twitter.com'||h.endsWith('.twitter.com')){gtag('event','social_click',{platform:'x',link_url:u,transport_type:'beacon'});gtag('event','x_outbound',{link_url:u,page:'home',lang:document.documentElement.lang||'',transport_type:'beacon'});}else if(h==='instagram.com'||h.endsWith('.instagram.com'))gtag('event','social_click',{platform:'instagram',link_url:u,transport_type:'beacon'});else if(h==='threads.net'||h.endsWith('.threads.net')||h==='threads.com'||h.endsWith('.threads.com'))gtag('event','social_click',{platform:'threads',link_url:u,transport_type:'beacon'});else if(h==='paypal.com'||h.endsWith('.paypal.com')||h==='paypal.me'||h.endsWith('.paypal.me'))gtag('event','donate_click',{method:'paypal',page:'home',lang:document.documentElement.lang})});


})().catch(function(e){console.error(e)});
