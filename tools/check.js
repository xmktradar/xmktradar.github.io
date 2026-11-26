// Step 9: open every view at desktop and phone width; fail on any JS error or sideways overflow.
// Usage: node tools/check.js index.html
// Serves the repo over http so slim pages can fetch /data/dash/ and lazy-load older posts.
// Requiring this file does not launch a browser. Only `node tools/check.js` does.
const path = require('path');

const VIEWS = ['daily', 'weekly', 'monthly', 'macro', 'tracked', 'stock/NVDA'];
const WIDTHS = [[1280, 900], [390, 844]];
const ATTEMPTS = 3;

function errText(err) {
  if (err == null) return '';
  if (typeof err === 'string') return err;
  if (err && err.message) return String(err.message);
  return String(err);
}

// Playwright tears the page down when the main thread stalls or a widget navigates.
// Only those deaths are retried. Real check failures (overflow, missing posts, missing prices) are not.
function isContextTeardown(err) {
  const s = errText(err).toLowerCase();
  if (!s) return false;
  return s.includes('execution context was destroyed')
    || s.includes('most likely because of a navigation')
    || s.includes('target closed')
    || s.includes('target crashed')
    || s.includes('page crashed')
    || s.includes('page closed')
    || s.includes('browser has been closed')
    || s.includes('context or browser has been closed')
    || s.includes('frame was detached');
}

function isTimeout(err) {
  const s = errText(err).toLowerCase();
  return s.includes('timeout') && s.includes('exceeded');
}

function joinMsg(a, b) {
  const x = errText(a), y = errText(b);
  if (x && y) return x.includes(y) ? x : y.includes(x) ? y : x + ' | ' + y;
  return x || y;
}

// Run fn up to `attempts` times. A context teardown closes nothing here — the caller closes the page
// and fn starts a fresh one. A later success is the result. Anything else fails on the first try.
async function retryOnTeardown(label, fn, opts) {
  const attempts = (opts && opts.attempts) || ATTEMPTS;
  const log = (opts && opts.log) || console.log;
  for (let i = 1; i <= attempts; i++) {
    try {
      return await fn(i);
    } catch (e) {
      if (!isContextTeardown(e) || i === attempts) throw e;
      log(`retry ${label} (${i + 1}/${attempts}) ${errText(e).split('\n')[0]}`);
    }
  }
}

async function checkViewOnce(browser, origin, url, w, h, view) {
  const p = await browser.newPage({ viewport: { width: w, height: h } });
  const errs = [];
  let crashed = null;
  p.on('pageerror', e => errs.push(e.message));
  p.on('crash', () => { crashed = new Error('page crashed'); });
  const dead = (e) => {
    if (crashed || (e && isContextTeardown(e))) throw (e && isContextTeardown(e)) ? e : crashed;
  };
  try {
    await p.route('**/*', route => {
      if (route.request().url().startsWith(origin)) route.continue();
      else route.abort();
    });
    await p.goto(url + '#' + view, { waitUntil: 'domcontentloaded' });
    dead();

    // 等開頁流程（完整資料＋分批畫面）完成先檢查；用輪詢，唔 await 頁面入面嘅 promise。
    // 超時唔當即失敗：下面仍然自己 load + render 一次。上下文被拆就重試，唔好吞掉。
    let waitErr = null;
    try {
      await p.waitForFunction(() => window.__dashReady === true && window.__viewDone !== false, null, { timeout: 60000 });
    } catch (e) {
      dead(e);
      waitErr = e;
    }
    dead();

    let evalErr = '';
    try {
      await p.evaluate(async () => {
        if (window.__loadCore) await window.__loadCore();
        if (window.__loadAllPosts) await window.__loadAllPosts();
      });
    } catch (e) {
      dead(e);
      evalErr = errText(e);
    }
    dead();

    try { await p.waitForTimeout(50); }
    catch (e) { dead(e); evalErr = joinMsg(evalErr, e); }
    dead();

    try {
      await p.evaluate(async () => {
        if (typeof paintChrome === 'function') paintChrome();
        if (typeof render === 'function') render();
        if (window.__postsFailed) throw new Error('older posts failed to load');
        if (typeof D !== 'undefined' && D._ext && D._ext.core && Object.keys(D.prices || {}).length === 0)
          throw new Error('prices did not load');
      });
    } catch (e) {
      dead(e);
      evalErr = joinMsg(evalErr, e);
    }
    dead();

    try { await p.waitForTimeout(300); }
    catch (e) { dead(e); evalErr = joinMsg(evalErr, e); }
    dead();

    let info = { ovf: false, len: 0 };
    try {
      info = await p.evaluate(() => ({ ovf: document.documentElement.scrollWidth > innerWidth + 1, len: document.body.innerText.length }));
    } catch (e) {
      dead(e);
      evalErr = joinMsg(evalErr, e);
    }
    dead();

    const contentBad = !!(errs.length || evalErr || info.ovf || !(info.len > 500));
    if (waitErr && (contentBad || !isTimeout(waitErr))) evalErr = joinMsg(waitErr, evalErr);
    const ok = !errs.length && !evalErr && !info.ovf && info.len > 500;
    console.log(`${ok ? 'ok ' : 'BAD'} ${w}px #${view}`, errs.length ? errs : '', evalErr, info.ovf ? 'overflow' : '');
    return { ok, label: `${w}px #${view}` };
  } finally {
    await p.close().catch(() => {});
  }
}

async function checkView(browser, origin, url, w, h, view) {
  const label = `${w}px #${view}`;
  try {
    return await retryOnTeardown(label, () => checkViewOnce(browser, origin, url, w, h, view));
  } catch (e) {
    console.log(`BAD ${w}px #${view}`, '', errText(e), '');
    return { ok: false, label };
  }
}

async function main() {
  const { chromium } = require('playwright');
  const { start, pageUrl } = require('./local_server');
  const root = path.resolve(__dirname, '..');
  const srv = await start(root);
  const file = process.argv[2] || 'index.html';
  const url = pageUrl(srv.origin, root, file);
  const b = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  const bad = [];
  try {
    for (const [w, h] of WIDTHS) {
      for (const v of VIEWS) {
        const r = await checkView(b, srv.origin, url, w, h, v);
        if (!r.ok) bad.push(`${w}px #${v}`);
      }
    }
  } finally {
    await b.close();
    srv.server.close();
  }
  if (bad.length) { console.log('::error::網頁檢查唔合格：' + bad.join('、')); process.exit(1); }
}

if (require.main === module) {
  main().catch(e => { console.error(e); process.exit(1); });
}

module.exports = { isContextTeardown, retryOnTeardown };
