// Font stacks use only --f-display / --f-body / --f-data, and the families are actually loaded.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const SKIP = new Set(['node_modules', '__pycache__', '.git', 'data', 'px', 'av', 'og', 'docs']);
const OLD = /var\(\s*--(?:serif|mono|sans)\s*\)|(?:^|[^\w-])--(?:serif|mono|sans)\s*:/;
const SHEET = 'https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=Noto+Serif+TC:wght@700&family=Noto+Sans+KR:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap';
const KO = /html\[lang=ko\][^{]*\{[^}]*--f-body:"Noto Sans KR"[^}]*--f-display:"Noto Sans KR"/;

function walk(dir, out) {
  for (const name of fs.readdirSync(dir)) {
    if (SKIP.has(name)) continue;
    const p = path.join(dir, name);
    if (fs.statSync(p).isDirectory()) walk(p, out);
    else if (/\.(html|js|py)$/.test(name) && !name.endsWith('.test.js')) out.push(p);
  }
  return out;
}

test('no legacy --serif, --mono or --sans, and no Georgia or Times in the new stacks', () => {
  const bad = [];
  for (const p of walk(ROOT, [])) {
    const s = fs.readFileSync(p, 'utf8');
    const rel = path.relative(ROOT, p);
    const hit = s.match(OLD);
    if (hit) bad.push(rel + ': ' + hit[0].trim());
    for (const line of s.match(/--f-(?:display|body):[^;]+/g) || []) {
      if (/Georgia|Times New Roman/.test(line)) bad.push(rel + ': ' + line);
    }
  }
  assert.deepEqual(bad, []);
});

function assertFonts(file) {
  const p = path.join(ROOT, file);
  assert.ok(fs.existsSync(p), 'missing ' + file);
  const s = fs.readFileSync(p, 'utf8');
  assert.ok(s.includes('<link rel="preconnect" href="https://fonts.googleapis.com">'), file + ' missing fonts preconnect');
  assert.ok(s.includes('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'), file + ' missing gstatic preconnect');
  assert.ok(s.includes(SHEET), file + ' missing font stylesheet');
  assert.ok(s.includes('--f-data:'), file + ' missing --f-data');
  assert.ok(s.includes('"IBM Plex Mono"'), file + ' data stack does not name IBM Plex Mono');
  assert.ok(KO.test(s), file + ' missing html[lang=ko] Noto Sans KR for body and display');
  assert.ok(!/Noto Serif KR/.test(s), file + ' names Noto Serif KR');
  const csp = s.match(/Content-Security-Policy[^>]*>/i);
  if (csp) {
    assert.ok(/fonts\.googleapis\.com/.test(csp[0]) && /fonts\.gstatic\.com/.test(csp[0]), file + ' CSP would block Google Fonts');
  }
  assert.ok(/--f-display:"[^"]+"(?:,"[^"]+")*,serif/.test(s), file + ' --f-display does not end with serif');
  assert.ok(/--f-body:"[^"]+"(?:,"[^"]+")*,system-ui,sans-serif/.test(s), file + ' --f-body does not end with system-ui,sans-serif');
}

test('homepage, about, support, tools, stock and embed pages load the fonts', () => {
  const pages = [
    'index.html', 'robot.html', '404.html',
    'zh/index.html', 'en/index.html', 'ko/index.html',
    'about/index.html', 'zh/about/index.html', 'en/about/index.html', 'ko/about/index.html',
    'support/index.html', 'zh/support/index.html', 'en/support/index.html', 'ko/support/index.html',
    'tools/index.html', 'zh/tools/index.html', 'en/tools/index.html', 'ko/tools/index.html',
    'newsletter/index.html', 'zh/newsletter/index.html', 'en/newsletter/index.html', 'ko/newsletter/index.html',
    'newsletter/issue-1/index.html',
    'advertise/index.html', 'zh/advertise/index.html', 'en/advertise/index.html', 'ko/advertise/index.html',
    'zh/embed/index.html', 'en/embed/index.html', 'ko/embed/index.html',
    'tools/about.html', 'tools/support.html', 'tools/toolspage.html', 'tools/newsletter.html', 'tools/advertise.html',
    'tools/embed.js', 'tools/newsletter.py', 'tools/page404.py',
  ];
  for (const lang of ['zh', 'en', 'ko']) {
    const dir = path.join(ROOT, lang, 'stock');
    const name = fs.existsSync(path.join(dir, 'NVDA', 'index.html'))
      ? 'NVDA'
      : fs.readdirSync(dir).find(d => fs.existsSync(path.join(dir, d, 'index.html')));
    assert.ok(name, 'no stock page under ' + lang);
    pages.push(`${lang}/stock/${name}/index.html`);
  }
  const card = fs.readdirSync(path.join(ROOT, 'embed')).find(f => f.endsWith('.html'));
  assert.ok(card, 'no embed card');
  pages.push('embed/' + card);
  for (const file of pages) assertFonts(file);
});

test('about, support and tools numbers use --f-data', () => {
  for (const file of ['tools/about.html', 'about/index.html', 'en/about/index.html', 'tools/support.html', 'support/index.html', 'tools/toolspage.html', 'tools/index.html', 'en/tools/index.html']) {
    const s = fs.readFileSync(path.join(ROOT, file), 'utf8');
    assert.match(s, /\.n,\.count b\{[^}]*font-family:var\(--f-data\)/, file);
  }
  assert.match(fs.readFileSync(path.join(ROOT, 'advertise/index.html'), 'utf8'), /\.stats b\{[^}]*font-family:var\(--f-data\)/);
  assert.match(fs.readFileSync(path.join(ROOT, 'newsletter/index.html'), 'utf8'), /\.issues \.dates\{[^}]*font-family:var\(--f-data\)/);
});
