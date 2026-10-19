// Dev helper: render native 1080×1350 Instagram text-post pictures (tools/ig.html) only.
// Not used by the update-site workflow (that path is tools/og.js when job.social).
//
// Usage:
//   node tools/ig_sample.js [outdir]
//
// Builds work/og.json the same way the pipeline does, then screenshots zh/en/ko:
//   1. Write work/index-full.html with the full dash-data blob (slim pages split it out)
//   2. node tools/stats.js work/index-full.html work/windows.json work/stats.json
//   3. python3 tools/share.py --og-only     (writes work/og.json; no social posts, no index.html rewrite)
//   4. screenshot tools/ig.html → {outdir}/ig-{zh,en,ko}.png
//
// outdir defaults to work/ig. Example:
//   NODE_PATH=/tmp/pw/node_modules CHROME_PATH=/usr/bin/google-chrome \
//     node tools/ig_sample.js /workspace/ig-samples
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
process.chdir(ROOT);
const WORK = process.env.WORK_DIR || 'work';
const outdir = path.resolve(process.argv[2] || path.join(WORK, 'ig'));

function run(cmd, args) {
  console.log('+', cmd, args.join(' '));
  execFileSync(cmd, args, { stdio: 'inherit', env: process.env, cwd: ROOT });
}

(async () => {
  fs.mkdirSync(WORK, { recursive: true });
  fs.mkdirSync(outdir, { recursive: true });
  fs.writeFileSync(path.join(WORK, 'windows.json'), '{"daily": null}\n');

  // stats.js needs the full dash-data blob (slim homepages fetch /data/dash/ over http).
  const statsHtml = path.join(WORK, 'index-full.html');
  run('python3', ['-c',
    'import sys; sys.path.insert(0, "tools")\n'
    + 'from slim_pages import full_data, BLOCK, html_escape, dumps\n'
    + 'html = open("index.html", encoding="utf-8").read()\n'
    + 'd = full_data(html)\n'
    + 'm = BLOCK.search(html)\n'
    + 'open(' + JSON.stringify(statsHtml) + ', "w", encoding="utf-8").write('
    + 'html[:m.start(2)] + html_escape(dumps(d)) + html[m.end(2):])\n']);
  run('node', ['tools/stats.js', statsHtml, path.join(WORK, 'windows.json'), path.join(WORK, 'stats.json')]);
  run('python3', ['tools/share.py', '--og-only']);

  const job = JSON.parse(fs.readFileSync(path.join(WORK, 'og.json'), 'utf8'));
  const b = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  const p = await b.newPage({ viewport: { width: 1080, height: 1350 } });
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + path.resolve(__dirname, 'ig.html'), { waitUntil: 'networkidle' });
  for (const lang of ['zh', 'en', 'ko']) {
    await p.evaluate(([l, d]) => ig(l, d), [lang, job.langs[lang]]);
    await p.evaluate(async () => {
      const want = ['900 84px "Noto Sans TC"', '700 32px "Noto Sans TC"', '900 84px "Noto Sans KR"', '700 52px "IBM Plex Mono"'];
      const t = new Promise(r => setTimeout(r, 20000));
      await Promise.race([Promise.all(want.map(f => document.fonts.load(f, document.body.innerText))), t]);
      await document.fonts.ready;
      await Promise.all([...document.images].map(i => i.decode().catch(() => {})));
    });
    await p.evaluate(() => { if (typeof fit === 'function') fit(); });
    const out = path.join(outdir, `ig-${lang}.png`);
    await p.screenshot({ path: out });
    console.log('ig', out);
  }
  await b.close();
  if (errs.length) { console.log('ig_sample errors: ' + errs.join('; ')); process.exit(1); }
})().catch(e => { console.error(e); process.exit(1); });
