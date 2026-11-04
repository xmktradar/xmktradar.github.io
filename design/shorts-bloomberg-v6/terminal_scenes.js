// Terminal-style full-screen scenes for the carousel motion video.
// Loaded by tools/carousel_video.js into terminal_scene.html (replaces comic carousel_scenes.js).
// API (unchanged): setup(name, D) builds a scene; draw(t, gt) paints one frame.
// Needs cl / out / back / BEAT / chrome from the header carousel_video.js injects first.
// Motion: fade, slide (translateY), count-up only. No shake, flash, emoji, confetti, slam scale.
// Scene names: cover | hook | reveal | vs | facts | outro
//   cover/hook/reveal/vs/outro map 1:1 to the existing BASE list (s1–s4 stay on carousel.html).
//   facts is optional (preview / if BASE grows). Production vs already shows fact1/fact2 when present.

const esc = v => String(v == null ? '' : v).replace(/[&<>"]/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'
}[c]));

function T_cl(v) {
  return typeof cl === 'function' ? cl(v) : Math.max(0, Math.min(1, v));
}
function T_out(p) {
  return typeof out === 'function' ? out(p) : (1 - Math.pow(1 - p, 3));
}
function T_beat() {
  return typeof BEAT === 'number' ? BEAT : 60 / 124;
}

const EMOJI_RE = /[\u{1F300}-\u{1FAFF}\u{1F000}-\u{1F02F}\u{2600}-\u{27BF}\u{FE0F}\u{200D}\u{20E3}]/gu;

function clean(s) {
  return String(s == null ? '' : s)
    .replace(EMOJI_RE, '')
    .replace(/[?？]{2,}/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function isCount(v) {
  if (typeof v === 'number' && isFinite(v)) return true;
  if (typeof v === 'string' && /^\s*-?\d+\s*$/.test(v)) return true;
  return false;
}

function parseHero(raw) {
  const s = clean(raw);
  const m = s.match(/^([+\-−])?\s*(\d+(?:\.\d+)?)(.*)$/);
  if (!m) return { raw: s, sign: '', n: null, suffix: '', decimals: 0, tone: 'ink' };
  const sign = m[1] === '−' ? '-' : (m[1] || '');
  const decimals = (m[2].split('.')[1] || '').length;
  const tone = sign === '-' ? 'bear' : sign === '+' ? 'bull' : 'ink';
  return { raw: s, sign, n: parseFloat(m[2]), suffix: m[3] || '', decimals, tone };
}

function tickerSize(tk, base) {
  const n = String(tk || '').replace(/^\$/, '').length;
  if (n > 5) return Math.round(base * 0.68);
  if (n > 4) return Math.round(base * 0.82);
  return base;
}

function cashtag(tk) {
  const s = clean(tk).replace(/^\$/, '');
  return s ? '$' + s : '';
}

function pack(D) {
  D = D || {};
  const prev = window.TAPE || {};
  const t = Array.isArray(D.t) ? D.t.map(clean) : [];
  const ticker = clean(D.ticker || D.big || D.discussed) || prev.ticker || '';
  const hero = clean(D.hero || D.discussedN) || prev.hero || '';
  const heroLabel = clean(D.heroLabel || D.reveal) || prev.heroLabel || '';
  const bullIsN = isCount(D.bull);
  const bearIsN = isCount(D.bear);
  const bullN = bullIsN ? +D.bull : (prev.bullN != null ? prev.bullN : 0);
  const bearN = bearIsN ? +D.bear : (prev.bearN != null ? prev.bearN : 0);
  const bullTk = (!bullIsN && D.bull != null && D.bull !== '') ? clean(D.bull) : (prev.bullTk || '');
  const bearTk = (!bearIsN && D.bear != null && D.bear !== '') ? clean(D.bear) : (prev.bearTk || '');
  const bullL = clean(D.bullL) || (bullIsN ? t[0] : '') || prev.bullL || '';
  const bearL = clean(D.bearL) || (bearIsN ? t[1] : '') || prev.bearL || '';
  const verdict = t[2] || prev.verdict || '';
  const date = clean(D.date) || prev.date || '';
  const title = clean(D.title) || prev.title || '';
  const handle = clean(D.handle) || prev.handle || '@thecrowdtape';
  const ctaFromT = t.find(x => /crowdtape|\.com/i.test(x)) || '';
  const cta = clean(D.cta) || prev.cta || ctaFromT || 'thecrowdtape.com';
  const foot = clean(D.foot) || prev.foot || '';
  const posted = clean(D.posted) || prev.posted || '';
  const fact1 = clean(D.fact1) || prev.fact1 || '';
  const fact2 = clean(D.fact2) || prev.fact2 || '';
  const discussedL = clean(D.discussedL) || prev.discussedL || '';
  const discussedN = clean(D.discussedN) || prev.discussedN || '';
  const out = {
    ticker, hero, heroLabel, bullN, bearN, bullTk, bearTk, bullL, bearL, verdict,
    date, title, handle, cta, foot, posted, fact1, fact2, discussedL, discussedN, t
  };
  window.TAPE = Object.assign({}, prev, out);
  return out;
}

function $id(id) {
  const root = (window.S && S.mount) || window.__TERM_ROOT || document;
  if (root && root.querySelector) {
    const n = root.querySelector('#' + id);
    if (n) return n;
  }
  return document.getElementById(id);
}

function chromeTick(gt) {
  if (typeof chrome === 'function') {
    try { chrome(gt); } catch (e) { /* preview stubs */ }
  }
  const pb = document.getElementById('pbar');
  if (pb) {
    pb.style.height = '3px';
    pb.style.background = '#00d26a';
    pb.style.boxShadow = 'none';
    pb.style.top = '0px';
  }
  const fl = $id('flash');
  if (fl) fl.style.opacity = '0';
}

function chromeTop(P) {
  return `<header class="term-top">
    <div class="term-top-l">
      <span class="led"></span>
      <span class="caps" style="color:var(--live)">LIVE</span>
      <span class="term-sep">/</span>
      <span class="caps">TAPE</span>
      <span class="term-mark">TCT</span>
      <span class="term-brand">The Crowd Tape</span>
    </div>
    <div class="term-top-r">
      <span class="term-date tnum">${esc(P.date)}</span>
    </div>
  </header>`;
}

function chromeQuote(P, hide) {
  if (hide) return '';
  const tag = cashtag(P.ticker);
  if (!tag && !P.hero) return '';
  const h = parseHero(P.hero);
  const px = P.hero ? `<span class="q-px tnum ${h.tone}" data-el="qpx">${esc(P.hero)}</span>` : '';
  const lb = P.heroLabel ? `<span class="q-lb">${esc(P.heroLabel)}</span>` : '';
  return `<div class="term-quote">
    <span class="q-sym tnum" data-el="qsym">${esc(tag)}</span>
    ${px}${lb}
  </div>`;
}

function chromeFoot(P) {
  const left = P.handle ? `<b>${esc(P.handle)}</b>` : '';
  const mid = P.cta ? `<span>${esc(P.cta)}</span>` : '';
  const right = P.foot ? `<span>${esc(P.foot)}</span>` : '';
  return `<footer class="term-foot">
    <div class="term-foot-l">${left}${mid ? `<span class="term-sep">·</span>${mid}` : ''}</div>
    <div class="term-foot-r">${right}</div>
  </footer>`;
}

function frame(P, main, opts) {
  opts = opts || {};
  return `<div class="term-frame" data-scene="${esc(opts.scene || '')}">
    ${chromeTop(P)}
    ${chromeQuote(P, opts.noQuote)}
    <main class="term-main">${main}</main>
    ${chromeFoot(P)}
  </div>`;
}

function coverHTML(P) {
  const tag = cashtag(P.ticker);
  const h = parseHero(P.hero);
  const tkPx = tickerSize(P.ticker, 176);
  const heroPx = tickerSize(P.hero, 188);
  const title = P.title || P.discussedL || '';
  const mini = (P.bullN || P.bearN) ? `<div class="mini-bb">
      <span class="n bull tnum" data-el="miniBull">${esc(P.bullN || 0)}</span>
      <span>${esc(P.bullL || '')}</span>
      <span class="term-sep">/</span>
      <span class="n bear tnum" data-el="miniBear">${esc(P.bearN || 0)}</span>
      <span>${esc(P.bearL || '')}</span>
    </div>` : '';
  const second = P.bullTk && P.bullTk !== P.ticker ? `<div class="cta-line" style="margin-top:8px">${esc(P.bullL || '')} <span class="tnum">${esc(cashtag(P.bullTk))}</span></div>` : '';
  const main = `
    <div class="kicker" data-el="kicker">EQTY · US</div>
    <div class="h-title" data-el="title">${esc(title)}</div>
    <div class="field-lab" data-el="lab">SYM / LAST</div>
    <div class="sym-xl" data-el="sym" style="font-size:${tkPx}px">${esc(tag)}</div>
    <div class="hero-xl ${h.tone}" data-el="hero" style="font-size:${heroPx}px">${esc(P.hero)}</div>
    <div class="hero-lb" data-el="hlab">${esc(P.heroLabel || P.discussedL || '')}</div>
    ${second}${mini}`;
  return frame(P, main, { scene: 'cover', noQuote: true });
}

function hookLines(P) {
  if (P.t && P.t.length) return P.t.slice(0, 4).filter(Boolean);
  return [P.heroLabel, [cashtag(P.ticker), P.hero].filter(Boolean).join('  ')].filter(Boolean);
}

function hookHTML(P) {
  const lines = hookLines(P);
  const rows = lines.map((ln, i) => `<div class="log-row" data-el="ln${i}">
      <span class="log-idx tnum">${String(i + 1).padStart(2, '0')}</span>
      <span>${esc(ln)}</span>
    </div>`).join('');
  const main = `
    <div class="kicker" data-el="kicker">SESSION</div>
    <div class="h-title" data-el="title">${esc(P.title || '')}</div>
    <div class="rule"></div>
    <div class="log">${rows}</div>`;
  return frame(P, main, { scene: 'hook' });
}

function revealHTML(P) {
  const tag = cashtag(P.ticker);
  const h = parseHero(P.hero);
  const tkPx = tickerSize(P.ticker, 176);
  const heroPx = tickerSize(P.hero, 200);
  const sub = P.heroLabel || '';
  const main = `
    <div class="kicker" data-el="kicker">LAST</div>
    <div class="field-lab" data-el="lab">SYM</div>
    <div class="sym-xl" data-el="sym" style="font-size:${tkPx}px">${esc(tag)}</div>
    <div class="hero-xl ${h.tone}" data-el="hero" style="font-size:${heroPx}px">${esc(P.hero)}</div>
    <div class="hero-lb" data-el="hlab">${esc(sub)}</div>`;
  return frame(P, main, { scene: 'reveal' });
}

function vsHTML(P) {
  const tot = Math.max(1, (+P.bullN || 0) + (+P.bearN || 0));
  const bp = Math.round((+P.bullN || 0) / tot * 100);
  const ep = 100 - bp;
  const f1 = P.fact1, f2 = P.fact2;
  const verdict = (!f1 && !f2 && P.verdict) ? P.verdict : '';
  const facts = [f1, f2].filter(Boolean).map((tx, i) => `<div class="fact" data-el="fact${i}">
      <span class="fact-idx tnum">${String(i + 1).padStart(2, '0')}</span>
      <span>${esc(tx)}</span>
    </div>`).join('');
  const extra = facts || (verdict ? `<div class="fact" data-el="fact0">
      <span class="fact-idx tnum">01</span><span>${esc(verdict)}</span>
    </div>` : '');
  const main = `
    <div class="kicker" data-el="kicker">BULL / BEAR</div>
    <div class="bb">
      <div class="bb-col">
        <div class="bb-l" data-el="blab">${esc(P.bullL || '')}</div>
        <div class="bb-n bull tnum" data-el="bn">0</div>
        <div class="bb-pct tnum" data-el="bp">0%</div>
      </div>
      <div class="bb-col right">
        <div class="bb-l" data-el="elab">${esc(P.bearL || '')}</div>
        <div class="bb-n bear tnum" data-el="en">0</div>
        <div class="bb-pct tnum" data-el="ep">0%</div>
      </div>
    </div>
    <div class="bb-track" data-el="track">
      <div class="bb-seg bull" data-el="barB"></div>
      <div class="bb-seg bear" data-el="barE"></div>
    </div>
    <div class="facts">${extra}</div>`;
  return frame(P, main, { scene: 'vs' });
}

function factsHTML(P) {
  const items = [P.fact1, P.fact2].filter(Boolean);
  const rows = items.map((tx, i) => `<div class="fact" data-el="fact${i}">
      <span class="fact-idx tnum">${String(i + 1).padStart(2, '0')}</span>
      <span>${esc(tx)}</span>
    </div>`).join('');
  const main = `
    <div class="kicker" data-el="kicker">DATA</div>
    <div class="h-title" data-el="title">關鍵數據</div>
    <div class="facts">${rows}</div>`;
  return frame(P, main, { scene: 'facts' });
}

function outroHTML(P) {
  const lines = (P.t && P.t.length)
    ? P.t.filter(x => x && !/^thecrowdtape\.com$/i.test(x) && x !== P.handle)
    : [];
  const extra = lines.slice(0, 4).map((ln, i) =>
    `<div class="cta-line" data-el="ln${i}">${esc(ln)}</div>`).join('');
  const main = `
    <div class="kicker" data-el="kicker">FOLLOW</div>
    <div class="cta-block">
      <div class="cta-url tnum" data-el="url">${esc(P.cta)}</div>
      <div class="cta-handle tnum" data-el="handle">${esc(P.handle)}</div>
      ${extra}
    </div>`;
  return frame(P, main, { scene: 'outro' });
}

function fadeSlide(el, t, start, dur, dy) {
  if (!el) return 0;
  const p = T_out(T_cl((t - start) / (dur || 0.32)));
  el.style.opacity = p;
  el.style.transform = 'translateY(' + ((1 - p) * (dy == null ? 24 : dy)) + 'px)';
  return p;
}

function hold(el) {
  if (!el) return;
  el.style.opacity = 1;
  el.style.transform = 'translateY(0)';
}

function fmtHero(spec, p) {
  if (spec.n == null) return spec.raw;
  const n = spec.n * p;
  const shown = spec.decimals ? n.toFixed(spec.decimals) : String(Math.round(n));
  return spec.sign + shown + spec.suffix;
}

function sel(attr) {
  const c = $id('c');
  return c ? c.querySelector('[data-el="' + attr + '"]') : null;
}

function setup(name, D) {
  const mount = window.__TERM_ROOT || document;
  const P = pack(D);
  window.D_ = D;
  const c = (mount.querySelector && mount.querySelector('#c')) || document.getElementById('c');
  const bg = (mount.querySelector && mount.querySelector('#bg')) || document.getElementById('bg');
  if (c) {
    c.innerHTML = '';
    c.style.transform = 'none';
  }
  if (bg) bg.style.backgroundColor = '';
  window.S = { name, D, P, mount, els: {}, hero: parseHero(P.hero) };

  const html = {
    cover: coverHTML,
    hook: hookHTML,
    reveal: revealHTML,
    vs: vsHTML,
    facts: factsHTML,
    outro: outroHTML
  }[name];
  if (!html) return;
  if (c) c.innerHTML = html(P);

  if (name === 'cover') {
    Array.prototype.forEach.call(c.querySelectorAll('[data-el]'), hold);
  } else if (name === 'hook') {
    hold(sel('kicker'));
    const title = sel('title');
    if (title) title.style.opacity = 0;
    hookLines(P).forEach((_, i) => {
      const el = sel('ln' + i);
      if (el) el.style.opacity = 0;
    });
  } else if (name === 'reveal') {
    ['kicker', 'lab', 'sym', 'hero', 'hlab'].forEach(k => {
      const el = sel(k);
      if (el) el.style.opacity = 0;
    });
    const qsym = sel('qsym'), qpx = sel('qpx');
    hold(qsym); hold(qpx);
  } else if (name === 'vs') {
    ['kicker', 'blab', 'elab', 'bn', 'en', 'bp', 'ep', 'track', 'fact0', 'fact1'].forEach(k => {
      const el = sel(k);
      if (el) el.style.opacity = 0;
    });
    hold(sel('qsym')); hold(sel('qpx'));
  } else if (name === 'facts') {
    ['kicker', 'title', 'fact0', 'fact1'].forEach(k => {
      const el = sel(k);
      if (el) el.style.opacity = 0;
    });
    hold(sel('qsym')); hold(sel('qpx'));
  } else if (name === 'outro') {
    ['kicker', 'url', 'handle', 'ln0', 'ln1', 'ln2', 'ln3'].forEach(k => {
      const el = sel(k);
      if (el) el.style.opacity = 0;
    });
  }
}

function draw(t, gt) {
  if (!window.S) return;
  chromeTick(gt);
  const c = $id('c');
  if (c) c.style.transform = 'none';
  const fl = $id('flash');
  if (fl) fl.style.opacity = '0';

  const name = S.name;
  const P = S.P || {};
  const B = T_beat();
  const h = S.hero || parseHero(P.hero);

  if (name === 'cover') {
    ['kicker', 'title', 'lab', 'sym', 'hero', 'hlab'].forEach(k => hold(sel(k)));
    return;
  }

  if (name === 'hook') {
    fadeSlide(sel('title'), t, 0, 0.28, 18);
    const n = hookLines(P).length;
    for (let i = 0; i < n; i++) fadeSlide(sel('ln' + i), t, 0.12 + i * 0.22, 0.28, 18);
    hold(sel('qsym')); hold(sel('qpx'));
    return;
  }

  if (name === 'reveal') {
    fadeSlide(sel('kicker'), t, 0, 0.22, 12);
    fadeSlide(sel('lab'), t, 0.05, 0.22, 12);
    fadeSlide(sel('sym'), t, 0.08, 0.32, 28);
    const hp = fadeSlide(sel('hero'), t, 0.16, 0.4, 28);
    const heroEl = sel('hero');
    if (heroEl) heroEl.textContent = fmtHero(h, hp);
    fadeSlide(sel('hlab'), t, 0.36, 0.28, 16);
    hold(sel('qsym')); hold(sel('qpx'));
    return;
  }

  if (name === 'vs') {
    fadeSlide(sel('kicker'), t, 0, 0.2, 12);
    fadeSlide(sel('blab'), t, 0.08, 0.25, 16);
    fadeSlide(sel('elab'), t, 0.12, 0.25, 16);
    const np = T_out(T_cl((t - 0.18) / 0.55));
    const bn = sel('bn'), en = sel('en');
    if (bn) { bn.style.opacity = np > 0 ? 1 : 0; bn.style.transform = 'translateY(' + ((1 - np) * 20) + 'px)'; bn.textContent = String(Math.round((+P.bullN || 0) * np)); }
    if (en) { en.style.opacity = np > 0 ? 1 : 0; en.style.transform = 'translateY(' + ((1 - np) * 20) + 'px)'; en.textContent = String(Math.round((+P.bearN || 0) * np)); }
    const tot = Math.max(1, (+P.bullN || 0) + (+P.bearN || 0));
    const bp = Math.round((+P.bullN || 0) / tot * 100);
    const ep = 100 - bp;
    const bpEl = sel('bp'), epEl = sel('ep');
    if (bpEl) { bpEl.style.opacity = np; bpEl.textContent = Math.round(bp * np) + '%'; }
    if (epEl) { epEl.style.opacity = np; epEl.textContent = Math.round(ep * np) + '%'; }
    const bp2 = T_out(T_cl((t - 0.35) / 0.55));
    const barB = sel('barB'), barE = sel('barE'), track = sel('track');
    if (track) track.style.opacity = bp2 > 0 ? 1 : 0;
    if (barB) barB.style.width = (bp * bp2) + '%';
    if (barE) barE.style.width = (ep * bp2) + '%';
    fadeSlide(sel('fact0'), t, 1.15, 0.3, 18);
    fadeSlide(sel('fact1'), t, 1.15 + 0.22, 0.3, 18);
    hold(sel('qsym')); hold(sel('qpx'));
    return;
  }

  if (name === 'facts') {
    fadeSlide(sel('kicker'), t, 0, 0.2, 12);
    fadeSlide(sel('title'), t, 0.06, 0.28, 18);
    fadeSlide(sel('fact0'), t, 0.22, 0.3, 18);
    fadeSlide(sel('fact1'), t, 0.44, 0.3, 18);
    hold(sel('qsym')); hold(sel('qpx'));
    return;
  }

  if (name === 'outro') {
    fadeSlide(sel('kicker'), t, 0, 0.2, 12);
    fadeSlide(sel('url'), t, 0.08, 0.32, 24);
    fadeSlide(sel('handle'), t, 0.22, 0.28, 18);
    for (let i = 0; i < 4; i++) fadeSlide(sel('ln' + i), t, 0.4 + i * 0.18, 0.28, 16);
  }
}
