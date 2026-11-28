/* Visitor share for the homepage.
   The picture is drawn from the current view's data (not a screenshot of the page).

   CT_SHARE_THEME is an engineering placeholder.
   Director will replace typography, colors, and layout.
   Every paint reads from this object. Do not hard-code colors, type, or spacing in the painter. */
window.CT_SHARE_THEME = {
  width: 1080,
  height: 1920,
  bg: '#161a21',
  fg: '#F5F5F7',
  muted: '#9aa2b0',
  bull: '#11845a',
  bear: '#c3343a',
  split: '#d7b15e',
  line: 'rgba(245,245,247,0.16)',
  pill: 'rgba(245,245,247,0.08)',
  fontDisplay: '"Noto Serif TC","Source Han Serif TC","Songti TC","PMingLiU",Georgia,serif',
  fontBody: '"Noto Sans TC","PingFang TC","Noto Sans CJK TC","Microsoft JhengHei",system-ui,sans-serif',
  fontData: '"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace',
  weightDisplay: 700,
  weightBody: 500,
  weightData: 600,
  weightBadge: 700,
  marginX: 88,
  safeTop: 250,
  safeBottom: 250,
  logo: 64,
  brandSize: 46,
  viewSize: 68,
  tickerSize: 52,
  metaSize: 30,
  badgeSize: 26,
  urlSize: 28,
  rowGap: 26,
  headerGap: 22,
  rail: 8,
  rule: 2,
  radius: 18,
};

(function () {
  var THEME = window.CT_SHARE_THEME;
  var BADGE_EN = { bull: 'Jointly bullish', bear: 'Jointly bearish', split: 'Split' };
  var cache = { key: '', canvas: null, pending: null };
  var iconP = null;

  function isZh() {
    return /^zh/i.test((document.documentElement.lang || ''));
  }

  function dict(key, fallback) {
    var el = document.querySelector('#ct-share-dict [data-k="' + key + '"]');
    var t = el && (el.textContent || '').trim();
    return t || fallback || '';
  }

  function viewLabel(view) {
    var fb = isZh()
      ? { daily: '每日', weekly: '每週', monthly: '每月', macro: '宏觀', tracked: '追蹤名單' }
      : { daily: 'Daily', weekly: 'Weekly', monthly: 'Monthly', macro: 'Macro', tracked: 'Tracked list' };
    return dict('view-' + view, fb[view] || view);
  }

  function lead(view) {
    var fb = isZh()
      ? { daily: '今日共識', weekly: '本週共識', monthly: '本月共識', macro: '宏觀', tracked: '追蹤名單' }
      : { daily: 'consensus today', weekly: 'consensus this week', monthly: 'consensus this month', macro: 'Macro', tracked: 'Tracked list' };
    return dict('lead-' + view, fb[view] || viewLabel(view));
  }

  function badgeText(kind) {
    if (!isZh()) return BADGE_EN[kind] || '';
    var fb = { bull: '共同看多', bear: '共同看空', split: '好淡分歧' };
    return dict('badge-' + kind, fb[kind] || '');
  }

  function metaText(kind, nb, nr) {
    var zh = isZh();
    if (kind === 'split') {
      var b = dict('side-bull', zh ? '看多' : 'Bullish');
      var r = dict('side-bear', zh ? '看空' : 'Bearish');
      if (!zh) { b = b.toLowerCase(); r = r.toLowerCase(); }
      return nb + ' ' + b + ' · ' + nr + ' ' + r;
    }
    if (kind === 'bear') {
      var tb = dict('count-bear', zh ? '個帳號看空' : 'accounts bearish');
      return zh ? (nr + ' ' + tb) : (nr + ' ' + tb);
    }
    var t = dict('count-bull', zh ? '個帳號看多' : 'accounts bullish');
    return nb + ' ' + t;
  }

  function viewKey() {
    var h = 'daily';
    try { h = decodeURIComponent((location.hash || '#daily').slice(1)) || 'daily'; } catch (e) { h = 'daily'; }
    var m = String(h).match(/^(daily|weekly|monthly|macro|tracked)(?:\/\d+)?$/);
    if (m) return m[1];
    try {
      if (typeof current === 'string' && /^(daily|weekly|monthly|macro|tracked)$/.test(current)) return current;
    } catch (e) {}
    return 'daily';
  }

  /* Same from/to the homepage already passes into consHtml. Ranking stays inside consGroups. */
  function rangeFor(view) {
    try {
      if (view === 'daily' && typeof dailyWindow === 'function') {
        var w = dailyWindow();
        if (w && w.from && w.to) return { from: w.from, to: w.to };
      }
      if (view === 'weekly' && typeof weeklyCtx === 'function') {
        var c = weeklyCtx();
        if (c && c.from && c.to) return { from: c.from, to: c.to };
      }
      if (view === 'monthly' && typeof monthlyCtx === 'function') {
        var mo = monthlyCtx();
        if (mo && mo.from && mo.to) return { from: mo.from, to: mo.to };
      }
    } catch (e) {}
    return null;
  }

  function shareUrl() {
    var hash = '';
    var search = '';
    try { hash = location.hash || ''; search = location.search || ''; } catch (e) {}
    return 'https://thecrowdtape.com/' + (isZh() ? 'zh' : 'en') + '/' + search + hash;
  }

  function shareText(view, rows) {
    var names = rows.map(function (r) { return r.ticker; });
    var s = 'The Crowd Tape ' + lead(view);
    if (names.length) s += (isZh() ? '：' : ': ') + names.join(isZh() ? '、' : ', ');
    return s;
  }

  function collect() {
    var view = viewKey();
    var rows = [];
    var range = rangeFor(view);
    if (range && (view === 'daily' || view === 'weekly' || view === 'monthly') && typeof consGroups === 'function') {
      try {
        var G = consGroups(range.from, range.to);
        ['bull', 'bear', 'split'].forEach(function (kind) {
          (G[kind] || []).forEach(function (g) {
            if (!g || !g.t) return;
            if (typeof UNC === 'function' && UNC(g.t)) return;
            rows.push({
              ticker: g.t,
              kind: kind,
              nb: g.nb,
              nr: g.nr,
              badge: badgeText(kind),
              meta: metaText(kind, g.nb, g.nr),
            });
          });
        });
      } catch (e) { rows = []; }
    }
    rows = rows.slice(0, 5);
    var url = shareUrl();
    return {
      view: view,
      viewLabel: viewLabel(view),
      rows: rows,
      url: url,
      displayUrl: url.replace(/^https?:\/\//, ''),
      text: shareText(view, rows),
    };
  }

  function roundRect(g, x, y, w, h, r) {
    r = Math.max(0, Math.min(r, w / 2, h / 2));
    g.beginPath();
    g.moveTo(x + r, y);
    g.arcTo(x + w, y, x + w, y + h, r);
    g.arcTo(x + w, y + h, x, y + h, r);
    g.arcTo(x, y + h, x, y, r);
    g.arcTo(x, y, x + w, y, r);
    g.closePath();
  }

  function loadIcon() {
    if (iconP) return iconP;
    iconP = new Promise(function (resolve) {
      var img = new Image();
      var done = false;
      function finish(v) { if (!done) { done = true; resolve(v); } }
      img.onload = function () { finish(img.naturalWidth ? img : null); };
      img.onerror = function () { finish(null); };
      setTimeout(function () { finish(null); }, 2500);
      img.src = '/apple-touch-icon.png';
    });
    return iconP;
  }

  function readyFonts(th) {
    if (!document.fonts || !document.fonts.load) return Promise.resolve();
    var jobs = [
      document.fonts.ready,
      document.fonts.load(th.weightDisplay + ' ' + th.brandSize + 'px ' + th.fontDisplay),
      document.fonts.load(th.weightDisplay + ' ' + th.viewSize + 'px ' + th.fontDisplay),
      document.fonts.load(th.weightData + ' ' + th.tickerSize + 'px ' + th.fontData),
      document.fonts.load(th.weightBody + ' ' + th.metaSize + 'px ' + th.fontBody),
      document.fonts.load(th.weightBadge + ' ' + th.badgeSize + 'px ' + th.fontBody),
      document.fonts.load(th.weightData + ' ' + th.urlSize + 'px ' + th.fontData),
    ];
    return Promise.race([
      Promise.all(jobs).then(function () {}, function () {}),
      new Promise(function (resolve) { setTimeout(resolve, 2500); }),
    ]);
  }

  function fit(g, text, maxW) {
    text = String(text || '');
    if (g.measureText(text).width <= maxW) return text;
    var t = text;
    while (t.length > 1 && g.measureText(t + '…').width > maxW) t = t.slice(0, -1);
    return t + '…';
  }

  function inkOf(th, kind) {
    if (kind === 'bear') return th.bear;
    if (kind === 'split') return th.split;
    return th.bull;
  }

  function paint(g, th, data, icon) {
    var x = th.marginX;
    var y = th.safeTop;
    var inner = th.width - th.marginX * 2;
    g.fillStyle = th.bg;
    g.fillRect(0, 0, th.width, th.height);

    if (icon) {
      g.save();
      roundRect(g, x, y, th.logo, th.logo, Math.round(th.radius * 0.55));
      g.clip();
      g.drawImage(icon, x, y, th.logo, th.logo);
      g.restore();
    }
    g.fillStyle = th.fg;
    g.textBaseline = 'middle';
    g.font = th.weightDisplay + ' ' + th.brandSize + 'px ' + th.fontDisplay;
    var brandX = icon ? x + th.logo + th.headerGap : x;
    g.fillText(fit(g, 'The Crowd Tape', x + inner - brandX), brandX, y + th.logo / 2);
    y += Math.max(th.logo, th.brandSize) + th.headerGap * 1.6;

    g.textBaseline = 'top';
    g.font = th.weightDisplay + ' ' + th.viewSize + 'px ' + th.fontDisplay;
    g.fillStyle = th.fg;
    g.fillText(fit(g, data.viewLabel, inner), x, y);
    y += th.viewSize + th.headerGap;

    g.strokeStyle = th.line;
    g.lineWidth = th.rule;
    g.beginPath();
    g.moveTo(x, y + 0.5);
    g.lineTo(x + inner, y + 0.5);
    g.stroke();
    y += th.headerGap;

    var urlTop = th.height - th.safeBottom - th.urlSize;
    var limit = urlTop - th.headerGap;
    (data.rows || []).forEach(function (row) {
      var block = th.tickerSize + 10 + th.metaSize;
      if (y + block > limit) return;
      var color = inkOf(th, row.kind);
      if (th.rail) {
        g.fillStyle = color;
        roundRect(g, x, y + 6, th.rail, block - 8, th.rail / 2);
        g.fill();
      }
      var tx = x + (th.rail ? th.rail + 20 : 0);
      g.font = th.weightBadge + ' ' + th.badgeSize + 'px ' + th.fontBody;
      var badge = row.badge || '';
      var padX = 18;
      var bw = Math.min(inner * 0.62, g.measureText(badge).width + padX * 2);
      var bh = th.badgeSize + 20;
      var bx = x + inner - bw;
      var by = y + (th.tickerSize - bh) / 2;
      g.fillStyle = th.pill;
      roundRect(g, bx, by, bw, bh, bh / 2);
      g.fill();
      g.fillStyle = color;
      g.textBaseline = 'middle';
      g.fillText(fit(g, badge, bw - padX * 2), bx + padX, by + bh / 2);

      g.textBaseline = 'top';
      g.fillStyle = th.fg;
      g.font = th.weightData + ' ' + th.tickerSize + 'px ' + th.fontData;
      var tickerMax = Math.max(40, bx - tx - 16);
      g.fillText(fit(g, row.ticker, tickerMax), tx, y);
      y += th.tickerSize + 10;
      g.fillStyle = th.muted;
      g.font = th.weightBody + ' ' + th.metaSize + 'px ' + th.fontBody;
      g.fillText(fit(g, row.meta, inner - (th.rail ? th.rail + 20 : 0)), tx, y);
      y += th.metaSize + th.rowGap;
    });

    g.textBaseline = 'top';
    g.fillStyle = th.muted;
    g.font = th.weightData + ' ' + th.urlSize + 'px ' + th.fontData;
    g.fillText(fit(g, data.displayUrl || '', inner), x, urlTop);
  }

  function keyOf(data) {
    return [data.url, data.view, data.viewLabel, data.text, (data.rows || []).map(function (r) {
      return r.ticker + r.kind + r.nb + '/' + r.nr + r.badge + r.meta;
    }).join('|')].join('~');
  }

  function renderCard(snapshot) {
    var data = snapshot || collect();
    var key = keyOf(data);
    if (cache.canvas && cache.key === key) return Promise.resolve(cache.canvas);
    if (cache.pending && cache.key === key) return cache.pending;
    cache.key = key;
    cache.canvas = null;
    var th = THEME;
    cache.pending = Promise.all([readyFonts(th), loadIcon()]).then(function (xs) {
      var canvas = document.createElement('canvas');
      canvas.width = th.width;
      canvas.height = th.height;
      var g = canvas.getContext('2d');
      paint(g, th, data, xs[1]);
      if (cache.key === key) { cache.canvas = canvas; cache.pending = null; }
      return canvas;
    }).catch(function (e) {
      if (cache.key === key) cache.pending = null;
      throw e;
    });
    return cache.pending;
  }

  function blobOf(canvas) {
    return new Promise(function (resolve) {
      canvas.toBlob(function (b) { resolve(b); }, 'image/png');
    });
  }

  async function fileOf(data) {
    var canvas = await renderCard(data);
    var blob = await blobOf(canvas);
    if (!blob) return null;
    try { return new File([blob], 'the-crowd-tape.png', { type: 'image/png' }); }
    catch (e) { return blob; }
  }

  function downloadBlob(blob) {
    var a = document.createElement('a');
    var url = URL.createObjectURL(blob);
    a.href = url;
    a.download = 'the-crowd-tape.png';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 2500);
  }

  async function copyText(text) {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (e) {}
    try {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.cssText = 'position:fixed;left:-9999px;top:0';
      document.body.appendChild(ta);
      ta.select();
      var ok = document.execCommand('copy');
      ta.remove();
      return !!ok;
    } catch (e) { return false; }
  }

  function say(msg) {
    var n = document.querySelector('#ct-share-panel .ct-share-msg');
    if (!n) return;
    n.textContent = msg || '';
    n.hidden = !msg;
  }

  function copiedMsg() {
    return dict('copied', isZh() ? '已複製連結' : 'Link copied');
  }
  function copyFailMsg() {
    return dict('copy-fail', isZh() ? '無法複製連結' : 'Could not copy the link');
  }
  function igMsg() {
    return dict('ig-fallback', isZh()
      ? '已下載圖片並複製連結，可以加到限時動態'
      : 'Image downloaded and link copied. You can add the image to your Story.');
  }

  function popup(url) {
    window.open(url, '_blank', 'noopener,noreferrer');
  }

  async function sharePayload(data, file) {
    var title = 'The Crowd Tape';
    var attempts = [];
    var filesOk = file && typeof File !== 'undefined' && file instanceof File
      && navigator.canShare && navigator.canShare({ files: [file] });
    if (filesOk) {
      attempts.push({ files: [file], title: title, text: data.text, url: data.url });
      attempts.push({ files: [file], title: title, text: data.text + '\n' + data.url });
    }
    attempts.push({ title: title, text: data.text, url: data.url });
    attempts.push({ title: title, text: data.text + '\n' + data.url });
    var last = null;
    for (var i = 0; i < attempts.length; i++) {
      var item = attempts[i];
      if (navigator.canShare) {
        try { if (!navigator.canShare(item)) continue; } catch (e) { continue; }
      }
      try {
        await navigator.share(item);
        return item.files ? 'files' : 'url';
      } catch (e) {
        if (e && e.name === 'AbortError') return 'abort';
        last = e;
      }
    }
    if (last) return 'fail';
    return 'unsupported';
  }

  async function shareSystem() {
    var data = collect();
    if (!navigator.share) return 'unsupported';
    var file = null;
    try { file = await fileOf(data); } catch (e) { file = null; }
    return sharePayload(data, file);
  }

  async function shareIG() {
    var data = collect();
    var file = null;
    try { file = await fileOf(data); } catch (e) { file = null; }
    if (file && navigator.share && navigator.canShare && file instanceof File && navigator.canShare({ files: [file] })) {
      var r = await sharePayload(data, file);
      if (r === 'files' || r === 'url' || r === 'abort') return r;
    }
    if (file) downloadBlob(file);
    var ok = await copyText(data.url);
    say(ok ? igMsg() : (igMsg() + ' ' + copyFailMsg()));
    return 'download';
  }

  function openLink(kind, data) {
    var text = data.text + '\n' + data.url;
    if (kind === 'wa') popup('https://wa.me/?text=' + encodeURIComponent(text));
    else if (kind === 'x') popup('https://twitter.com/intent/tweet?text=' + encodeURIComponent(text));
    else if (kind === 'fb') popup('https://www.facebook.com/sharer/sharer.php?u=' + encodeURIComponent(data.url));
  }

  var busy = false;
  async function run(act) {
    if (busy) return;
    busy = true;
    try {
      var data = collect();
      if (act === 'ig') await shareIG();
      else if (act === 'system') await shareSystem();
      else if (act === 'wa' || act === 'x' || act === 'fb') openLink(act, data);
      else if (act === 'copy') {
        say((await copyText(data.url)) ? copiedMsg() : copyFailMsg());
      } else if (act === 'dl') {
        var file = await fileOf(data);
        if (file) downloadBlob(file);
      }
    } finally { busy = false; }
  }

  function panelEls() {
    return {
      btn: document.getElementById('ct-share-btn'),
      panel: document.getElementById('ct-share-panel'),
    };
  }

  function closeSearch() {
    var box = document.getElementById('srch');
    var b = document.getElementById('srch-btn');
    if (box) box.hidden = true;
    if (b) b.setAttribute('aria-expanded', 'false');
  }

  function syncSystem(panel) {
    var b = panel.querySelector('[data-act="system"]');
    if (b) b.hidden = !navigator.share;
  }

  function openPanel() {
    var els = panelEls();
    if (!els.panel || !els.btn) return;
    closeSearch();
    say('');
    syncSystem(els.panel);
    els.panel.hidden = false;
    els.btn.setAttribute('aria-expanded', 'true');
    var card = els.panel.querySelector('.ct-share-card');
    if (card) {
      if (!card.hasAttribute('tabindex')) card.setAttribute('tabindex', '-1');
      card.focus();
    }
  }

  function closePanel() {
    var els = panelEls();
    if (!els.panel || els.panel.hidden) return;
    els.panel.hidden = true;
    if (els.btn) {
      els.btn.setAttribute('aria-expanded', 'false');
      if (els.panel.contains(document.activeElement)) els.btn.focus();
    }
  }

  function isPhone() {
    return !!(window.matchMedia && matchMedia('(max-width:734px)').matches);
  }

  function bind() {
    var els = panelEls();
    if (!els.btn || !els.panel || els.btn.dataset.ctShare) return;
    els.btn.dataset.ctShare = '1';
    if (els.panel.parentNode !== document.body) document.body.appendChild(els.panel);
    els.btn.addEventListener('pointerdown', function () { renderCard().catch(function () {}); }, { passive: true });
    els.btn.addEventListener('click', function () {
      if (!els.panel.hidden) { closePanel(); return; }
      openPanel();
      if (isPhone() && navigator.share) shareSystem().catch(function () {});
    });
    els.panel.addEventListener('click', function (e) {
      var b = e.target.closest && e.target.closest('[data-act]');
      if (b) {
        if (b.getAttribute('data-act') === 'close') closePanel();
        else run(b.getAttribute('data-act'));
        return;
      }
      if (e.target === els.panel) closePanel();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape' || els.panel.hidden) return;
      closePanel();
    });
    document.addEventListener('click', function (e) {
      if (els.panel.hidden) return;
      if (e.target.closest && (e.target.closest('#ct-share-panel') || e.target.closest('#ct-share-btn'))) return;
      closePanel();
    });
    window.addEventListener('hashchange', function () {
      cache.key = '';
      cache.canvas = null;
      cache.pending = null;
    });
  }

  window.CTShare = {
    theme: THEME,
    collect: collect,
    renderCard: renderCard,
    shareSystem: shareSystem,
    shareUrl: shareUrl,
    open: openPanel,
    close: closePanel,
    download: async function () {
      var file = await fileOf(collect());
      if (file) downloadBlob(file);
      return file;
    },
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind);
  else bind();
})();
