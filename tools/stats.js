// Compute consensus and counts with the page's own code, so numbers in the write-ups
// match what the site shows. Usage: node tools/stats.js index.html windows.json out.json
// windows.json: {"daily": {"from": "YYYY-MM-DDTHH:MM", "to": "..."} | null}; weekly/monthly use the page's ranges.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const [html, winFile, out] = process.argv.slice(2);
  const wins = JSON.parse(fs.readFileSync(winFile, 'utf8'));
  const b = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  const p = await b.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  await p.route(/^https?:/, r => r.abort());
  await p.goto('file://' + path.resolve(html) + '#daily');
  await p.waitForFunction(() => typeof consGroups === 'function');
  const r = await p.evaluate((wins) => {
    const stat = (from, to) => {
      const G = consGroups(from, to);
      const grp = g => ({ t: g.t, nb: g.nb, nr: g.nr, n_posts: g.nPosts,
        rows: g.rows.map(x => ({ acc: x.acc, s: x.s, why: (x.why || '').slice(0, 160), url: x.url, ms: x.ms })) });
      const raw = rawIn(from, to).filter(valid);
      const ps = postsIn(from, to);
      const cnt = {};
      ps.forEach(x => { const c = cnt[x.t] = cnt[x.t] || { t: x.t, n: 0, accs: new Set(), bull: 0, bear: 0 }; c.n++; c.accs.add(x.acc); if (x.s === 'bull') c.bull++; if (x.s === 'bear') c.bear++; });
      const top = Object.values(cnt).sort((a, b) => b.accs.size - a.accs.size || b.n - a.n || a.t.localeCompare(b.t)).slice(0, 25)
        .map(c => ({ t: c.t, mentions: c.n, accounts: c.accs.size, bull: c.bull, bear: c.bear }));
      const ms = raw.map(x => x.ms);
      return {
        from, to, posts: raw.length, accounts: new Set(raw.map(x => x.acc)).size,
        originals: raw.filter(x => !x.reposted_by && !x.replying_to).length,
        reposts: raw.filter(x => x.reposted_by).length,
        bull_views: ps.filter(x => x.s === 'bull').length, bear_views: ps.filter(x => x.s === 'bear').length,
        clear_accounts: new Set(ps.filter(x => x.s === 'bull' || x.s === 'bear').map(x => x.acc)).size,
        first_ms: ms.length ? Math.min(...ms) : null, last_ms: ms.length ? Math.max(...ms) : null,
        bull: G.bull.map(grp), bear: G.bear.map(grp), split: G.split.map(grp), top
      };
    };
    const dw = wins.daily || (({ from, to }) => ({ from, to }))(dailyWindow());
    return {
      today: TODAY,
      daily: stat(dw.from, dw.to),
      weekly: stat(addDays(TODAY, -6), TODAY),
      monthly: stat(addDays(TODAY, -27), TODAY)
    };
  }, wins);
  r.errors = errs;
  fs.writeFileSync(out, JSON.stringify(r, null, 1));
  const s = r.daily;
  console.log(`daily ${s.from}..${s.to} posts ${s.posts} bull ${s.bull.map(g => g.t).join(',')} bear ${s.bear.map(g => g.t).join(',')} split ${s.split.map(g => g.t).join(',')} errors ${errs.length}`);
  await b.close();
  if (errs.length) process.exit(1);
})();
