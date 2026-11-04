// Bloomberg / terminal scenes for carousel motion videos (v6.1).
// setup(name, data) builds a scene; draw(t, globalT) paints one frame.
// Shared helpers cl/out/back/BEAT/chrome come from the header injected by carousel_video.js.
// v6.1: optional hookQ on open + parable layout on m1 (scheme A). Empty → #278 behavior.
const esc = v => String(v == null ? '' : v).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function brandBar(D) {
  return `<div class="brand"><img src="logo.png" alt=""><span class="name">The Crowd Tape</span>` +
    (D.date ? `<span class="date mono">${esc(D.date)}</span>` : '') + `</div>`;
}

function setup(name, D) {
  window.D_ = D;
  const c = document.getElementById('c');
  c.innerHTML = '';
  c.style.transform = '';
  document.getElementById('bg').style.background = '#0e1116';
  window.S = { name, D, els: [] };
  if (name === 'open') {
    const head = D.hookQ
      ? `<div class="hookQ" id="hookQ">${esc(D.hookQ)}</div>`
      : `<div class="label">${esc(D.lead || '')}</div>`;
    c.innerHTML = brandBar(D) + `
      <div class="panel" style="top:180px;bottom:220px;padding:64px 48px;display:flex;flex-direction:column;justify-content:center;gap:36px">
        ${head}
        <div class="row"><div class="tk mono amber" style="font-size:${String(D.big || '').length > 4 ? 160 : 200}px">$${esc(D.big || '')}</div></div>
        <div class="num mono" style="font-size:72px">${esc(D.metric || '')}</div>
        <div class="muted" style="font-size:36px;font-weight:600;line-height:1.35">${esc(D.ctx || '')}</div>
      </div>
      <div class="muted" style="position:absolute;left:56px;right:56px;bottom:72px;font-size:26px;font-weight:600">thecrowdtape.com</div>`;
    return;
  }
  if (name === 'split') {
    const bull = D.bull | 0, bear = D.bear | 0;
    c.innerHTML = brandBar(D) + `
      <div style="position:absolute;left:56px;right:56px;top:200px;bottom:160px;display:flex;gap:28px">
        <div class="card" style="flex:1;display:flex;flex-direction:column;justify-content:center;gap:28px;border-color:#234033">
          <div class="label up">${esc(D.bullL || 'Bulls')}</div>
          <div class="num mono up" id="bullN" style="font-size:160px">${bull}</div>
          <div class="muted" style="font-size:32px">${esc(D.bullSub || '')}</div>
        </div>
        <div class="card" style="flex:1;display:flex;flex-direction:column;justify-content:center;gap:28px;border-color:#3a2430">
          <div class="label down">${esc(D.bearL || 'Bears')}</div>
          <div class="num mono down" id="bearN" style="font-size:160px">${bear}</div>
          <div class="muted" style="font-size:32px">${esc(D.bearSub || '')}</div>
        </div>
      </div>
      <div class="muted" style="position:absolute;left:56px;right:56px;bottom:72px;text-align:center;font-size:32px;font-weight:600">${esc(D.verdict || '')}</div>`;
    return;
  }
  if (name === 'm1' && (D.mode === 'parable' || (D.parable && D.parable.length))) {
    const lines = (D.parable || []).slice(0, 4).map((line, i) =>
      `<div class="parable-line muted" id="p${i}" style="opacity:0;transform:translateY(24px)">${esc(line)}</div>`).join('');
    c.innerHTML = brandBar(D) + `
      <div class="panel" style="top:180px;bottom:140px;padding:48px 44px;display:flex;flex-direction:column;gap:8px">
        <div class="label" style="margin-bottom:20px">${esc(D.title || 'PARABLE')}</div>
        ${lines}
        ${D.anchor ? `<div class="tk mono amber" style="margin-top:28px;font-size:48px">${esc(D.anchor)}</div>` : ''}
        ${D.punch ? `<div class="muted" style="margin-top:20px;font-size:28px;line-height:1.4">${esc(D.punch)}</div>` : ''}
      </div>`;
    return;
  }
  if (name === 'm1' || name === 'm2') {
    const rows = (D.rows || []).slice(0, 4).map(r => `
      <div class="row" style="padding:22px 0;border-bottom:1px solid #1e2a3a">
        <div class="tk mono" style="font-size:56px">$${esc(r.t)}</div>
        <div class="num mono" style="font-size:44px;color:${r.tone === 'down' ? '#ff5c7a' : r.tone === 'up' ? '#3dd68c' : '#e8eef7'}">${esc(r.v)}</div>
      </div>`).join('');
    c.innerHTML = brandBar(D) + `
      <div class="panel" style="top:180px;bottom:140px;padding:48px 44px">
        <div class="label" style="margin-bottom:28px">${esc(D.title || '')}</div>
        ${rows || `<div class="muted" style="font-size:36px">${esc(D.empty || '')}</div>`}
        ${D.note ? `<div class="muted" style="margin-top:36px;font-size:28px;line-height:1.4">${esc(D.note)}</div>` : ''}
      </div>`;
    return;
  }
  if (name === 'cta') {
    c.innerHTML = brandBar(D) + `
      <div class="panel" style="top:420px;bottom:420px;padding:64px 48px;display:flex;flex-direction:column;justify-content:center;gap:40px;text-align:center">
        <div class="mono amber" style="font-size:56px;font-weight:800">thecrowdtape.com</div>
        <div style="font-size:44px;font-weight:700">Follow @thecrowdtape</div>
        <div class="muted" style="font-size:30px;line-height:1.45">${esc(D.foot || '')}</div>
      </div>`;
  }
}

function lerpRgb(a, b, e) {
  return `rgb(${Math.round(a[0] + (b[0] - a[0]) * e)},${Math.round(a[1] + (b[1] - a[1]) * e)},${Math.round(a[2] + (b[2] - a[2]) * e)})`;
}

function draw(t, gt) {
  chrome(gt);
  const c = document.getElementById('c');
  c.style.transform = 'none';
  // Soft fade-in of the whole scene; ticker/numbers are already in the DOM at t=0 (open).
  const p = Math.min(1, t / 0.18);
  c.style.opacity = String(0.55 + 0.45 * p);
  if (S.name === 'open' && D_ && D_.hookQ) {
    const hq = document.getElementById('hookQ');
    if (hq) {
      const e = out(cl(t / 0.45));
      hq.style.opacity = String(0.35 + 0.65 * e);
      hq.style.color = lerpRgb([139, 155, 180], [232, 238, 247], e);
    }
  }
  if (S.name === 'split' && D_) {
    const e = out(cl(t / 0.55));
    const bn = document.getElementById('bullN'), rn = document.getElementById('bearN');
    if (bn) bn.textContent = String(Math.round((D_.bull || 0) * e));
    if (rn) rn.textContent = String(Math.round((D_.bear || 0) * e));
  }
  if (S.name === 'm1' && D_ && (D_.mode === 'parable' || (D_.parable && D_.parable.length))) {
    const n = (D_.parable || []).length;
    for (let i = 0; i < n; i++) {
      const el = document.getElementById('p' + i);
      if (!el) continue;
      const e = out(cl(Math.max(0, t - 0.25 * i) / 0.35));
      el.style.opacity = String(e);
      el.style.transform = `translateY(${(1 - e) * 24}px)`;
      el.style.color = e > 0.92 ? '#e8eef7' : '#8b9bb4';
    }
  }
}

if (typeof module !== 'undefined') module.exports = { setup, draw, esc };
