// Tests for the RUX helpers (why-lines + today-in-3-lines) embedded in index.html.
const test=require('node:test'),assert=require('node:assert');
const fs=require('fs'),path=require('path');
const src=fs.readFileSync(path.join(__dirname,'..','index.html'),'utf8');
const m=src.match(/\/\*RUX\*\/([\s\S]*?)\/\*RUX-END\*\//);
assert.ok(m,'RUX block missing from index.html');
const RUX=new Function(m[1]+';return {reasonOf:ruxReasonOf,threeLines:ruxThreeLines,clauseFor:ruxClause};')();
test('reason extracted only from real summary text',()=>{
 const r=RUX.reasonOf([{s:'bull',why:'NVDA 財報勝預期，數據中心營收大增。'},{s:'bull',why:'$NVDA 指引強勁'},{s:'bear',why:'覺得 NVDA 走勢弱'}],'NVDA');
 assert.equal(r.bull.k,'earn');assert.equal(r.bull.n,2);
 assert.ok('NVDA 財報勝預期，數據中心營收大增。'.includes(r.bull.ex.replace(/…/g,'')));
 assert.equal(r.bear,null);
});
test('no clear reason -> omitted, never fabricated',()=>{
 const r=RUX.reasonOf([{s:'bull',why:'好鍾意呢隻'},{s:'bear',why:''},{s:'neu',why:'估值高'}],'TSLA');
 assert.equal(r.bull,null);assert.equal(r.bear,null);
});
test('multi-ticker summary not attributed to unmentioned ticker',()=>{
 const r=RUX.reasonOf([{s:'bull',why:'$AAPL 財報強。$MSFT 估值合理。'}],'TSLA');
 assert.equal(r.bull,null);
 const r2=RUX.reasonOf([{s:'bull',why:'$AAPL 財報強。$MSFT 估值合理。'}],'MSFT');
 assert.equal(r2.bull.k,'val');
});
test('english and korean keywords',()=>{
 assert.equal(RUX.reasonOf([{s:'bear',why:'AMD looks overvalued here.'}],'AMD').bear.k,'val');
 assert.equal(RUX.reasonOf([{s:'bull',why:'삼성 실적 개선 기대'}],'005930').bull.k,'earn');
});
const C=(bull,bear,neu,accs,mentions)=>({bull,bear,neu,none:0,accs,mentions});
test('three lines computed from data',()=>{
 const T=RUX.threeLines([
  {t:'A',c:C(3,0,0,3,3),c0:C(0,2,0,2,2),chg:0},
  {t:'B',c:C(3,3,1,8,9),c0:C(3,3,1,7,7),chg:1},
  {t:'C',c:C(1,1,0,2,2),c0:null,chg:0}],true);
 assert.equal(T.shift.t,'A');assert.equal(T.shift.kind,'delta');
 assert.equal(T.most.t,'B');assert.equal(T.most.n,9);
 assert.equal(T.split.t,'B');
});
test('lines omitted when no data',()=>{
 const T=RUX.threeLines([{t:'A',c:C(1,0,0,1,1),c0:null,chg:0}],false);
 assert.equal(T.shift,null);assert.equal(T.split,null);assert.equal(T.most.t,'A');
 const E=RUX.threeLines([],false);assert.deepEqual(E,{shift:null,most:null,split:null});
});
test('english multi-sentence summary keeps full clause',()=>{
 const r=RUX.reasonOf([{s:'bull',why:'@x says $VIX is going higher with more panic coming. No buying dips under his guidance.'}],'VIX');
 assert.equal(r.bull,null);
 const r2=RUX.reasonOf([{s:'bull',why:'@x says $NVDA earnings will crush estimates, adding more.'}],'NVDA');
 assert.equal(r2.bull.k,'earn');assert.ok(r2.bull.ex.includes('earnings'));
});
test('build-safe: no full-width punctuation inside RUX regexes',()=>{
 assert.ok(!/[。；！？]/.test(m[1].match(/split\(([^)]*)\)/)[1]));
});
test('RUX helpers are top-level functions, no IIFE',()=>{
 assert.ok(!/\(function\s*\(/.test(m[1]));assert.ok(/^function ruxReasonOf\(/m.test(m[1]));assert.ok(/^function ruxThreeLines\(/m.test(m[1]));
});
