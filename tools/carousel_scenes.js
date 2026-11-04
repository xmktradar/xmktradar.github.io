// Tape Cats scenes for carousel motion videos (v6.1 full: cream + pose + mouth/cue).
// setup(name, data) builds a scene; draw(t, globalT) paints one frame.
// Shared helpers cl/out/back/BEAT/chrome come from header injected by carousel_video.js.
// Bright cream BG + PNG cats; mouth follows VO cue table; blink/nod overlays.
// Real X quote on m1 (mode=quote). Empty quote → legacy rows. Never invent quotes.
const esc = v => String(v == null ? '' : v).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const CAT_ASSET = '../design/shorts-maneki/assets';

/** Pose / face stems per character. Talk frames are full-body swaps (same lock). */
const CAT_POSES = {
  specs: {
    idle: 'specs-idle', raise: 'specs-raise', 'point-R': 'specs-point-R', 'point-L': 'specs-point-R',
    nod: 'specs-nod', blink: 'specs-blink',
    'talk-closed': 'specs-talk-closed', 'talk-half': 'specs-talk-half', 'talk-open': 'specs-talk-open',
  },
  wave: {
    idle: 'wave-idle', 'point-L': 'wave-point-L', 'point-R': 'wave-point-R',
    nod: 'wave-nod', blink: 'wave-blink', surprise: 'wave-surprise',
    'talk-closed': 'wave-talk-closed', 'talk-half': 'wave-talk-half', 'talk-open': 'wave-talk-open',
  },
  boom: {
    idle: 'boom-idle', cheer: 'boom-cheer', nod: 'boom-nod', blink: 'boom-blink',
    'talk-closed': 'boom-talk-closed', 'talk-half': 'boom-talk-half', 'talk-open': 'boom-talk-open',
  },
};

const SCENE_CAT = {
  open: { id: 'specs', side: 'right' },
  split: { id: 'specs', side: 'center' },
  m1: { id: 'wave', side: 'right' },
  m2: { id: 'boom', side: 'right' },
  cta: { id: 'boom', side: 'right' },
};

/**
 * Cue table keyed by scene, times relative to scene start (sample ~28s total).
 * Scaled at runtime by window.__cueScale (duration/28). From design/shorts-maneki/CUE-TABLE.md.
 * mouth: 'closed'|'half'|'open'|'talk'  face: optional overlay pose (nod|blink|surprise)
 */
const CUES = {
  open: [
    { t: 0.0, pose: 'raise', mouth: 'closed' },
    { t: 0.4, pose: 'idle', mouth: 'talk' },
    { t: 1.2, pose: 'point-R', mouth: 'open', face: 'nod' },
    { t: 2.4, pose: 'point-R', mouth: 'talk' },
  ],
  split: [
    { t: 0.0, pose: 'idle', mouth: 'talk' },
    { t: 1.5, pose: 'point-L', mouth: 'talk', face: 'nod' },
    { t: 3.0, pose: 'point-R', mouth: 'half' },
    { t: 4.5, pose: 'nod', mouth: 'closed' },
  ],
  m1: [
    { t: 0.0, pose: 'idle', mouth: 'closed' },
    { t: 0.6, pose: 'surprise', mouth: 'open' },
    { t: 1.5, pose: 'point-L', mouth: 'talk' },
    { t: 5.0, pose: 'nod', mouth: 'closed' },
  ],
  m2: [
    { t: 0.0, pose: 'idle', mouth: 'talk' },
    { t: 1.5, pose: 'nod', mouth: 'open' },
    { t: 3.0, pose: 'idle', mouth: 'half' },
  ],
  cta: [
    { t: 0.0, pose: 'cheer', mouth: 'open' },
    { t: 2.5, pose: 'cheer', mouth: 'talk', face: 'nod' },
    { t: 4.5, pose: 'cheer', mouth: 'closed' },
  ],
};

const TALK_CYCLE = ['talk-closed', 'talk-half', 'talk-open', 'talk-half'];
const MOUTH_MS = 100;

function brandBar(D) {
  return `<div class="brand"><img src="logo.png" alt=""><span class="name">The Crowd Tape</span>` +
    (D.date ? `<span class="date mono">${esc(D.date)}</span>` : '') + `</div>`;
}

function brightBg(name) {
  const bg = document.getElementById('bg');
  document.body.className = 'scene-' + name;
  document.body.style.background = '#FFF6EC';
  let decor = '';
  if (name === 'open') {
    decor = `<div class="frame-bg"></div><div class="orb orb--hook"></div>` +
      `<div class="petal petal--apricot" style="left:-8%;top:18%;width:48%;height:32%"></div>` +
      `<div class="petal petal--coral" style="right:-6%;bottom:22%;width:40%;height:26%"></div><div class="stripe"></div>`;
  } else if (name === 'split') {
    decor = `<div class="frame-bg"></div>` +
      `<div class="orb orb--mint" style="left:-12%;top:30%;width:50%;height:40%;opacity:.35"></div>` +
      `<div class="orb orb--coral" style="right:-12%;top:30%;width:50%;height:40%;opacity:.35"></div>`;
  } else if (name === 'm1') {
    decor = `<div class="frame-bg"></div><div class="orb orb--quote"></div>` +
      `<div class="petal petal--lilac" style="left:8%;top:12%;width:36%;height:22%"></div>` +
      `<div class="petal petal--lemon" style="right:4%;bottom:18%;width:34%;height:24%"></div>`;
  } else if (name === 'm2') {
    decor = `<div class="frame-bg"></div><div class="orb orb--mint" style="right:-8%;bottom:10%;width:45%;height:32%;opacity:.32"></div>`;
  } else if (name === 'cta') {
    decor = `<div class="frame-bg"></div><div class="orb orb--mint" id="ctaOrb" style="left:20%;top:28%;width:60%;height:36%;opacity:.4"></div>`;
  } else {
    decor = `<div class="frame-bg"></div>`;
  }
  bg.innerHTML = decor;
}
const energyBg = brightBg;

function isQuote(D) {
  return D && (D.mode === 'quote' || (D.handle && D.lines && D.lines.length));
}
function isParable(D) {
  return D && (D.mode === 'parable' || (D.parable && D.parable.length));
}

function catSrc(id, pose) {
  const map = CAT_POSES[id] || {};
  const stem = map[pose] || map.idle || (id + '-idle');
  return CAT_ASSET + '/' + stem + '.png';
}

function cueScale() {
  return (typeof window !== 'undefined' && window.__cueScale) ? window.__cueScale : 1;
}

function activeCue(name, t) {
  const list = CUES[name] || [];
  const s = cueScale();
  let cur = list[0] || { t: 0, pose: 'idle', mouth: 'closed' };
  for (const c of list) {
    if (t >= c.t * s) cur = c;
    else break;
  }
  return cur;
}

function setMouth(catId, state) {
  const body = document.getElementById('catBody');
  const mouth = document.getElementById('catMouth');
  if (!body) return;
  const st = state || 'closed';
  // Full-frame talk swaps replace body when talking; overlay kept for future partial mouths.
  if (st === 'closed' || st === 'half' || st === 'open') {
    const talkPose = 'talk-' + st;
    if ((CAT_POSES[catId] || {})[talkPose]) {
      body.src = catSrc(catId, talkPose);
      body.setAttribute('data-mouth', st);
    }
  }
  if (mouth) {
    mouth.style.opacity = '0';
    mouth.setAttribute('data-mouth', st);
  }
}

/** VO amplitude proxy → mouth. Used by cue 'talk' cycle + direct open/half/closed. */
function catMouthOpen(catId, amp) {
  if (amp == null || amp <= 0) { setMouth(catId, 'closed'); return; }
  if (amp < 0.35) setMouth(catId, 'half');
  else setMouth(catId, 'open');
}

function mouthFromCue(catId, mouth, gt) {
  if (mouth === 'talk') {
    const i = Math.floor((gt * 1000) / MOUTH_MS) % TALK_CYCLE.length;
    const pose = TALK_CYCLE[i];
    const body = document.getElementById('catBody');
    if (body) {
      body.src = catSrc(catId, pose);
      body.setAttribute('data-mouth', pose.replace('talk-', ''));
    }
    return;
  }
  if (mouth === 'open' || mouth === 'half' || mouth === 'closed') {
    setMouth(catId, mouth);
  }
}

function setCat(id, pose, side) {
  const layer = document.getElementById('cat-layer');
  if (!layer) return;
  const sideCls = side === 'left' ? 'cat-host--left' : (side === 'center' ? 'cat-host--center' : '');
  const src = catSrc(id, pose);
  // No specs-point-L.png — mirror specs-point-R (design CUE / MANIFEST).
  const flip = (id === 'specs' && pose === 'point-L') ? ' style="transform:scaleX(-1)"' : '';
  layer.innerHTML =
    `<div class="cat-host bobbing ${sideCls}" id="catHost" data-cat="${esc(id)}" data-pose="${esc(pose)}">` +
    `<img class="cat-body" id="catBody" alt="" src="${src}"${flip}>` +
    `<img class="cat-mouth" id="catMouth" alt="" src="${src}"${flip}>` +
    `</div>`;
  window.__cat = { id, pose, side: side || 'right' };
}

function ensureCat(name) {
  const conf = SCENE_CAT[name];
  if (!conf) {
    const layer = document.getElementById('cat-layer');
    if (layer) layer.innerHTML = '';
    window.__cat = null;
    return;
  }
  const cue = activeCue(name, 0);
  setCat(conf.id, cue.pose || 'idle', conf.side);
}

function drawCat(t, gt) {
  const conf = SCENE_CAT[S && S.name];
  if (!conf) return;
  const cue = activeCue(S.name, t);
  let pose = cue.pose || 'idle';
  // Brief face overlays (nod / surprise / blink) take body when keyed.
  if (cue.face && (CAT_POSES[conf.id] || {})[cue.face]) {
    // nod/surprise show ~180ms at cue edge then fall back to pose
    const s = cueScale();
    const cues = CUES[S.name] || [];
    const idx = cues.indexOf(cue);
    const start = (cue.t || 0) * s;
    if (t - start < 0.18) pose = cue.face;
  }
  // Independent blink every ~2.8s for 120ms
  const blinkPhase = ((gt + (conf.id === 'wave' ? 0.9 : 0)) % 2.8);
  if (blinkPhase < 0.12 && (CAT_POSES[conf.id] || {}).blink) pose = 'blink';

  const cur = window.__cat;
  if (!cur || cur.id !== conf.id || cur.pose !== pose) {
    setCat(conf.id, pose, conf.side);
  }
  mouthFromCue(conf.id, cue.mouth || 'closed', gt);

  const host = document.getElementById('catHost');
  if (host) {
    const e = out(cl(t / 0.35));
    host.style.opacity = String(e);
  }
}

function setup(name, D) {
  window.D_ = D;
  const c = document.getElementById('c');
  c.innerHTML = '';
  c.style.transform = '';
  brightBg(name, D);
  window.S = { name, D, els: [] };
  // Scale cues: sample table is 28s; TOTAL injected by carousel_video header.
  if (typeof TOTAL === 'number' && TOTAL > 0) window.__cueScale = TOTAL / 28;
  else window.__cueScale = 1;
  ensureCat(name);
  if (name === 'open') {
    const head = D.hookQ
      ? `<div class="hookQ" id="hookQ">${esc(D.hookQ)}</div>`
      : `<div class="label">${esc(D.lead || '')}</div>`;
    c.innerHTML = brandBar(D) + `
      <div class="panel" style="top:180px;bottom:360px;padding:64px 48px;display:flex;flex-direction:column;justify-content:center;gap:36px">
        ${head}
        <div class="row"><div class="tk mono amber" style="font-size:${String(D.big || '').length > 4 ? 160 : 200}px">$${esc(D.big || '')}</div></div>
        <div class="num mono" style="font-size:72px">${esc(D.metric || '')}</div>
        <div class="muted" style="font-size:36px;font-weight:600;line-height:1.35">${esc(D.ctx || '')}</div>
      </div>
      <div class="muted" style="position:absolute;left:56px;right:56px;bottom:72px;font-size:26px;font-weight:600;z-index:4">thecrowdtape.com</div>`;
    return;
  }
  if (name === 'split') {
    const bull = D.bull | 0, bear = D.bear | 0;
    c.innerHTML = brandBar(D) + `
      <div style="position:absolute;left:56px;right:56px;top:200px;bottom:320px;display:flex;gap:28px">
        <div class="card" style="flex:1;display:flex;flex-direction:column;justify-content:center;gap:28px">
          <div class="label up">${esc(D.bullL || 'Bulls')}</div>
          <div class="num mono up" id="bullN" style="font-size:160px">${bull}</div>
          <div class="muted" style="font-size:32px">${esc(D.bullSub || '')}</div>
        </div>
        <div class="card" style="flex:1;display:flex;flex-direction:column;justify-content:center;gap:28px">
          <div class="label down">${esc(D.bearL || 'Bears')}</div>
          <div class="num mono down" id="bearN" style="font-size:160px">${bear}</div>
          <div class="muted" style="font-size:32px">${esc(D.bearSub || '')}</div>
        </div>
      </div>
      <div class="muted" style="position:absolute;left:56px;right:56px;bottom:72px;text-align:center;font-size:32px;font-weight:600;z-index:4">${esc(D.verdict || '')}</div>`;
    return;
  }
  if (name === 'm1' && isQuote(D)) {
    const handle = String(D.handle || '').startsWith('@') ? D.handle : ('@' + (D.handle || ''));
    const lines = (D.lines || []).slice(0, 3).map((line, i) =>
      `<div class="quote-line muted" id="q${i}" style="opacity:0;transform:translateY(24px)">${esc(line)}</div>`).join('');
    const stance = String(D.stance || '').toLowerCase();
    const pill = stance === 'bull' || stance === 'bear'
      ? `<span class="stance-pill ${stance === 'bull' ? 'up' : 'down'}">${stance === 'bull' ? 'BULL' : 'BEAR'}</span>`
      : '';
    c.innerHTML = brandBar(D) + `
      <div class="panel" style="top:180px;bottom:360px;padding:48px 44px;display:flex;flex-direction:column;gap:8px">
        <div class="label" style="margin-bottom:8px">${esc(D.kicker || 'ON X')}</div>
        <div class="quote-handle mono amber" id="qHandle">${esc(handle)}</div>
        ${lines}
        <div class="row" style="margin-top:auto;padding-top:28px;align-items:center">
          ${D.anchor ? `<div class="tk mono amber" style="font-size:48px">${esc(D.anchor)}</div>` : '<div></div>'}
          ${pill}
        </div>
      </div>`;
    return;
  }
  if (name === 'm1' && isParable(D)) {
    const lines = (D.parable || []).slice(0, 4).map((line, i) =>
      `<div class="parable-line muted" id="p${i}" style="opacity:0;transform:translateY(24px)">${esc(line)}</div>`).join('');
    c.innerHTML = brandBar(D) + `
      <div class="panel" style="top:180px;bottom:360px;padding:48px 44px;display:flex;flex-direction:column;gap:8px">
        <div class="label" style="margin-bottom:20px">${esc(D.title || 'PARABLE')}</div>
        ${lines}
        ${D.anchor ? `<div class="tk mono amber" style="margin-top:28px;font-size:48px">${esc(D.anchor)}</div>` : ''}
        ${D.punch ? `<div class="muted" style="margin-top:20px;font-size:28px;line-height:1.4">${esc(D.punch)}</div>` : ''}
      </div>`;
    return;
  }
  if (name === 'm1' || name === 'm2') {
    const rows = (D.rows || []).slice(0, 4).map(r => `
      <div class="row" style="padding:22px 0;border-bottom:1px solid rgba(29,29,31,.08)">
        <div class="tk mono" style="font-size:56px">$${esc(r.t)}</div>
        <div class="num mono" style="font-size:44px;color:${r.tone === 'down' ? 'var(--bear)' : r.tone === 'up' ? 'var(--bull)' : 'var(--ink)'}">${esc(r.v || r.n || '')}</div>
      </div>`).join('');
    c.innerHTML = brandBar(D) + `
      <div class="panel" style="top:180px;bottom:360px;padding:48px 44px">
        <div class="label" style="margin-bottom:28px">${esc(D.title || '')}</div>
        ${rows || `<div class="muted" style="font-size:36px">${esc(D.empty || '')}</div>`}
        ${D.note || D.punch ? `<div class="muted" style="margin-top:36px;font-size:28px;line-height:1.4">${esc(D.note || D.punch || '')}</div>` : ''}
      </div>`;
    return;
  }
  if (name === 'cta') {
    const lines = (D.t || []).filter(Boolean);
    const foot = D.foot || (lines[0] || '');
    const mid = lines[1] || 'Follow @thecrowdtape';
    c.innerHTML = brandBar(D) + `
      <div class="panel" style="top:360px;bottom:420px;padding:64px 48px;display:flex;flex-direction:column;justify-content:center;gap:40px;text-align:center">
        <div class="mono amber" style="font-size:56px;font-weight:800">thecrowdtape.com</div>
        <div style="font-size:44px;font-weight:700">${esc(mid.startsWith('Follow') ? mid : 'Follow @thecrowdtape')}</div>
        <div class="muted" style="font-size:30px;line-height:1.45">${esc(foot)}</div>
      </div>`;
  }
}

function lerpRgb(a, b, e) {
  return `rgb(${Math.round(a[0] + (b[0] - a[0]) * e)},${Math.round(a[1] + (b[1] - a[1]) * e)},${Math.round(a[2] + (b[2] - a[2]) * e)})`;
}

function drawDecor(t, gt) {
  const petals = document.querySelectorAll('#bg .petal, #bg .orb');
  petals.forEach((el, i) => {
    const y = Math.sin(gt * 0.7 + i * 1.3) * 8;
    const x = Math.cos(gt * 0.45 + i) * 6;
    if (el.id === 'ctaOrb') {
      const s = 1 + 0.03 * Math.sin(gt * 2.0);
      el.style.transform = `scale(${s}) translate(${x}px,${y}px)`;
    } else {
      el.style.transform = `translate(${x}px,${y}px)`;
    }
  });
  void t;
}

function draw(t, gt) {
  chrome(gt);
  drawDecor(t, gt);
  drawCat(t, gt);
  const c = document.getElementById('c');
  c.style.transform = 'none';
  const p = Math.min(1, t / 0.18);
  c.style.opacity = String(0.55 + 0.45 * p);
  if (S.name === 'open' && D_ && D_.hookQ) {
    const hq = document.getElementById('hookQ');
    if (hq) {
      const e = out(cl(t / 0.45));
      hq.style.opacity = String(0.45 + 0.55 * e);
      hq.style.color = lerpRgb([110, 110, 115], [29, 29, 31], e);
    }
  }
  if (S.name === 'split' && D_) {
    const e = out(cl(t / 0.55));
    const bn = document.getElementById('bullN'), rn = document.getElementById('bearN');
    if (bn) bn.textContent = String(Math.round((D_.bull || 0) * e));
    if (rn) rn.textContent = String(Math.round((D_.bear || 0) * e));
  }
  if (S.name === 'm1' && isQuote(D_)) {
    const n = (D_.lines || []).length;
    for (let i = 0; i < n; i++) {
      const el = document.getElementById('q' + i);
      if (!el) continue;
      const e = out(cl(Math.max(0, t - 0.25 * i) / 0.35));
      el.style.opacity = String(e);
      el.style.transform = `translateY(${(1 - e) * 24}px)`;
      el.style.color = e > 0.92 ? '#1d1d1f' : '#6e6e73';
    }
  }
  if (S.name === 'm1' && isParable(D_) && !isQuote(D_)) {
    const n = (D_.parable || []).length;
    for (let i = 0; i < n; i++) {
      const el = document.getElementById('p' + i);
      if (!el) continue;
      const e = out(cl(Math.max(0, t - 0.25 * i) / 0.35));
      el.style.opacity = String(e);
      el.style.transform = `translateY(${(1 - e) * 24}px)`;
      el.style.color = e > 0.92 ? '#1d1d1f' : '#6e6e73';
    }
  }
}

if (typeof module !== 'undefined') {
  module.exports = {
    setup, draw, esc, isQuote, isParable, brightBg, energyBg,
    setCat, setMouth, catMouthOpen, CAT_POSES, SCENE_CAT, CUES, activeCue, catSrc,
  };
}
