// Step 9: open every view at desktop and phone width; fail on any JS error or sideways overflow.
// Usage: node tools/check.js index.html
// Serves the repo over http so slim pages can fetch /data/dash/ and lazy-load older posts.
const { chromium } = require('playwright');
const path = require('path');
const { start, pageUrl } = require('./local_server');
(async () => {
  const root = path.resolve(__dirname, '..');
  const srv = await start(root);
  const url = pageUrl(srv.origin, root, process.argv[2] || 'index.html');
  const b = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  const bad = [];
  try {
    for (const [w, h] of [[1280, 900], [390, 844]]) {
      for (const v of ['daily', 'weekly', 'monthly', 'macro', 'tracked', 'stock/NVDA']) {
        const p = await b.newPage({ viewport: { width: w, height: h } });
        const errs = [];
        p.on('pageerror', e => errs.push(e.message));const DIAG=[];p.on('framenavigated',f=>DIAG.push('nav '+(f===p.mainFrame())+' '+f.url()));p.on('console',m=>DIAG.push('con '+m.text().slice(0,200)));p.on('crash',()=>DIAG.push('crash'));p.on('close',()=>DIAG.push('close'));
        await p.route('**/*', route => {
          if (route.request().url().startsWith(srv.origin)) route.continue();
          else route.abort();
        });
        await p.goto(url + '#' + v, { waitUntil: 'domcontentloaded' });
        if (process.env.CI) { const st=[]; try { st.push('t0 '+await p.evaluate(()=>performance.timeOrigin+' '+document.readyState+' '+(window.__dashReady)+' '+typeof window.__loadCore));
          st.push('core '+await p.evaluate(async()=>{await window.__loadCore();return performance.timeOrigin}));
          st.push('posts '+await p.evaluate(async()=>{const t=Date.now();await window.__loadAllPosts();return performance.timeOrigin+' '+(Date.now()-t)}));
          st.push('chrome '+await p.evaluate(()=>{paintChrome();return 1}));
          st.push('render '+await p.evaluate(()=>{render();return performance.timeOrigin}));
          } catch(e){ st.push('ERR '+e.message.slice(0,120)) } console.log('STEP', v, JSON.stringify(st), JSON.stringify(DIAG)); }
        let evalErr = '';
        try {
          await p.evaluate(async () => {
            if (window.__loadCore) await window.__loadCore();
            if (window.__loadAllPosts) await window.__loadAllPosts();
            if (typeof paintChrome === 'function') paintChrome();
            if (typeof render === 'function') render();
            if (window.__postsFailed) throw new Error('older posts failed to load');
            if (typeof D !== 'undefined' && D._ext && D._ext.core && Object.keys(D.prices || {}).length === 0)
              throw new Error('prices did not load');
          });
        } catch (e) { evalErr = e.message || String(e); console.log('DIAG', JSON.stringify(DIAG), (e.stack||'').slice(0,600)); }
        await p.waitForTimeout(300);
        const info = await p.evaluate(() => ({ ovf: document.documentElement.scrollWidth > innerWidth + 1, len: document.body.innerText.length }));
        const ok = !errs.length && !evalErr && !info.ovf && info.len > 500;
        console.log(`${ok ? 'ok ' : 'BAD'} ${w}px #${v}`, errs.length ? errs : '', evalErr, info.ovf ? 'overflow' : '');
        if (!ok) bad.push(`${w}px #${v}`);
        await p.close();
      }
    }
  } finally {
    await b.close();
    srv.server.close();
  }
  if (bad.length) { console.log('::error::網頁檢查唔合格：' + bad.join('、')); process.exit(1); }
})();
