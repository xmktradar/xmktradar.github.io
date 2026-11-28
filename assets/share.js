/* Visitor share for the homepage.
   One stock per card: the picture is drawn from that consensus group's live rows,
   not from a screenshot and not from a list of other tickers.

   CT_SHARE_THEME is an engineering placeholder for the 9:16 story card.
   CT_SHARE_OG_THEME is the swappable 1200×630 painter for the same stock.
   Director will replace typography, colors, and layout.
   Every paint reads from the theme object it was given. Do not hard-code colors, type, or spacing in the painter. */
window.CT_SHARE_THEME = {
  width: 1080,
  height: 1920,
  layout: 'story',
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
  viewSize: 36,
  heroSize: 92,
  nameSize: 32,
  tickerSize: 92,
  metaSize: 32,
  badgeSize: 26,
  urlSize: 28,
  avatar: 80,
  avatarGap: 24,
  nameRowSize: 34,
  handleSize: 24,
  excerptSize: 28,
  excerptLine: 40,
  excerptLines: 3,
  maxExcerpts: 4,
  excerptGap: 28,
  headerGap: 22,
  sectionGap: 28,
  rail: 8,
  rule: 2,
  radius: 18,
  letterSize: 32,
  colW: 0,
};

window.CT_SHARE_OG_THEME = {
  width: 1200,
  height: 630,
  layout: 'wide',
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
  marginX: 56,
  safeTop: 48,
  safeBottom: 44,
  logo: 52,
  brandSize: 32,
  viewSize: 24,
  heroSize: 64,
  nameSize: 24,
  tickerSize: 64,
  metaSize: 22,
  badgeSize: 20,
  urlSize: 20,
  avatar: 56,
  avatarGap: 16,
  nameRowSize: 24,
  handleSize: 18,
  excerptSize: 22,
  excerptLine: 30,
  excerptLines: 2,
  maxExcerpts: 2,
  excerptGap: 18,
  headerGap: 14,
  sectionGap: 16,
  rail: 6,
  rule: 2,
  radius: 14,
  letterSize: 22,
  colW: 520,
};

(function () {
  /* English lines for the share card. The on-page badge keeps its own ui translation. */
  var BADGE_EN = { bull: 'Jointly bullish', bear: 'Jointly bearish', split: 'Split' };
  var cache = { key: '', canvas: null, pending: null };
  var iconP = null;
  var focus = null;

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
    nb = Number(nb) || 0;
    nr = Number(nr) || 0;
    var zh = isZh();
    if (kind === 'split') {
      var b = dict('side-bull', zh ? '看多' : 'Bullish');
      var r = dict('side-bear', zh ? '看空' : 'Bearish');
      if (!zh) { b = b.toLowerCase(); r = r.toLowerCase(); }
      return nb + ' ' + b + ' · ' + nr + ' ' + r;
    }
    if (kind === 'bear') return nr + ' ' + dict('count-bear', zh ? '個帳號看空' : 'accounts bearish');
    return nb + ' ' + dict('count-bull', zh ? '個帳號看多' : 'accounts bullish');
  }

  function stanceWord(s) {
    try {
      if (typeof STW !== 'undefined' && STW && STW[s]) return STW[s];
    } catch (e) {}
    try {
      if (typeof SLABEL !== 'undefined' && SLABEL && SLABEL[s]) return SLABEL[s];
    } catch (e2) {}
    if (s === 'bull') return dict('side-bull', isZh() ? '看多' : 'Bullish');
    if (s === 'bear') return dict('side-bear', isZh() ? '看空' : 'Bearish');
    return '';
  }

  function viewKey() {
    var h = 'daily';
    try { h = decodeURIComponent((location.hash || '#daily').slice(1)) || 'daily'; } catch (e) { h = 'daily'; }
    var m = String(h).match(/^(daily|weekly|monthly|macro|tracked)(?:\/\d+)?$/);
    if (m) return m[1];
    try {
      if (typeof current === 'string' && /^(daily|weekly|monthly|macro|tracked)$/.test(current)) return current;
    } catch (e2) {}
    return 'daily';
  }

  /* Same from/to the homepage already passes into consHtml. */
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

  function groupsFor(view) {
    if (view !== 'daily' && view !== 'weekly' && view !== 'monthly') return null;
    var range = rangeFor(view);
    if (!range || typeof consGroups !== 'function') return null;
    try { return consGroups(range.from, range.to); }
    catch (e) { return null; }
  }

  function langRoot() {
    return 'https://thecrowdtape.com/' + (isZh() ? 'zh' : 'en') + '/';
  }

  function searchOf() {
    try { return location.search || ''; } catch (e) { return ''; }
  }

  function hashOf() {
    try { return location.hash || ''; } catch (e) { return ''; }
  }

  function pageShareUrl() {
    return langRoot() + searchOf() + hashOf();
  }

  function stockShareUrl(ticker) {
    return langRoot() + searchOf() + '#stock/' + encodeURIComponent(ticker);
  }

  function displayOf(url) {
    return String(url || '').replace(/^https?:\/\//, '');
  }

  function stockText(ticker, badge) {
    var s = 'The Crowd Tape' + (isZh() ? '：' : ': ') + ticker;
    if (badge) s += ' ' + badge;
    return s;
  }

  function emptyPayload(view) {
    var url = pageShareUrl();
    return {
      view: view,
      viewLabel: viewLabel(view),
      ticker: '',
      name: '',
      kind: '',
      badge: '',
      nb: 0,
      nr: 0,
      meta: '',
      excerpts: [],
      url: url,
      displayUrl: displayOf(url),
      text: 'The Crowd Tape ' + lead(view),
    };
  }

  function findGroup(G, ticker, kind) {
    if (!G || !ticker) return null;
    var order = [];
    if (kind && G[kind]) order.push(kind);
    ['bull', 'bear', 'split'].forEach(function (k) { if (order.indexOf(k) < 0) order.push(k); });
    var loose = null;
    for (var i = 0; i < order.length; i++) {
      var list = G[order[i]] || [];
      for (var j = 0; j < list.length; j++) {
        if (list[j] && list[j].t === ticker) {
          if (order[i] === kind) return { g: list[j], kind: order[i] };
          if (!loose) loose = { g: list[j], kind: order[i] };
        }
      }
    }
    return loose;
  }

  /* Highest (nb+nr), then nPosts, then ticker ascending. Across bull, bear, and split. */
  function rankHero(G) {
    var all = [];
    if (!G) return null;
    ['bull', 'bear', 'split'].forEach(function (kind) {
      (G[kind] || []).forEach(function (g) {
        if (!g || !g.t) return;
        try { if (typeof UNC === 'function' && UNC(g.t)) return; } catch (e) {}
        all.push({ g: g, kind: kind });
      });
    });
    all.sort(function (a, b) {
      var sa = (Number(a.g.nb) || 0) + (Number(a.g.nr) || 0);
      var sb = (Number(b.g.nb) || 0) + (Number(b.g.nr) || 0);
      if (sb !== sa) return sb - sa;
      var pa = Number(a.g.nPosts) || 0;
      var pb = Number(b.g.nPosts) || 0;
      if (pb !== pa) return pb - pa;
      return String(a.g.t).localeCompare(String(b.g.t));
    });
    return all[0] || null;
  }

  function reasonFallback(x) {
    var p = (x && x.p) || {};
    var n = p.ticker_notes && p.ticker_notes[x.t];
    if (n) return { t: n, full: n };
    var z = p.zh_summary || p.summary_zh || '';
    var h = String(x && x.acc || '').replace(/[^A-Za-z0-9_]/g, '');
    var t = String(z).replace(new RegExp('^\\s*@?' + h + '\\s*(?:[:\\uFF1A]|表示|指出|認為|稱)\\s*', 'i'), '');
    return { t: t, full: z };
  }

  function excerptText(x) {
    var r = null;
    try { if (typeof reasonOf === 'function') r = reasonOf(x); } catch (e) { r = null; }
    if (!r) r = reasonFallback(x);
    var t = r && r.t != null ? String(r.t).replace(/\s+/g, ' ').trim() : '';
    var full = r && r.full != null ? String(r.full).replace(/\s+/g, ' ').trim() : '';
    return t || full;
  }

  function personName(h) {
    try {
      if (typeof nameOf === 'function') {
        var n = nameOf(h);
        if (n) return String(n);
      }
    } catch (e) {}
    return String(h || '');
  }

  function avatarSrc(h) {
    try {
      var info = (typeof accInfo === 'function') ? (accInfo(h) || {}) : {};
      if (info.avatar && /^data:image\//.test(info.avatar)) return info.avatar;
      var bag = (typeof AVMINI !== 'undefined' && AVMINI) ? AVMINI : null;
      if (!bag) return '';
      var mini = bag[h] || bag[String(h).toLowerCase()] || '';
      if (mini && /^data:image\//.test(mini)) return mini;
    } catch (e) {}
    return '';
  }

  function companyName(t) {
    try {
      if (typeof UNC === 'function' && UNC(t)) return '';
      var pr = (typeof D !== 'undefined' && D && D.prices) ? D.prices[t] : null;
      if (pr && pr.name) return String(pr.name);
      if (typeof OV !== 'undefined' && OV && OV[t] && OV[t].name) return String(OV[t].name);
    } catch (e) {}
    return '';
  }

  function themeCap(th, fallback) {
    var n = th && th.maxExcerpts;
    return n != null ? n : fallback;
  }

  /* Cap is the caller's limit: the 9:16 card passes CT_SHARE_THEME.maxExcerpts,
     the OG card passes CT_SHARE_OG_THEME.maxExcerpts. A split card with real
     text on both sides keeps one minority-side row inside that cap. Packing
     once at the larger cap and slicing the front drops that row on the OG card.
     Jointly bullish or bearish cards stay in existing row order. Neu/none is
     not a side. An empty minority side does not take a reserved slot. */
  function packExcerpts(g, cap) {
    if (cap == null) cap = themeCap(window.CT_SHARE_THEME, 4);
    cap = Number(cap);
    if (!isFinite(cap) || cap <= 0) return [];
    cap = Math.floor(cap);
    var rows = (g && g.rows) || [];
    var usable = [];
    for (var i = 0; i < rows.length; i++) {
      var x = rows[i];
      if (!x || !x.acc) continue;
      var text = excerptText(x);
      if (!text) continue;
      usable.push({ row: x, text: text });
    }
    var picked = pickWithinCap(usable, cap, g && g.kind);
    var out = [];
    for (var j = 0; j < picked.length; j++) out.push(excerptOf(picked[j]));
    return out;
  }

  function excerptOf(item) {
    var x = item.row;
    return {
      handle: x.acc,
      name: personName(x.acc),
      stance: x.s || '',
      stanceLabel: stanceWord(x.s),
      text: item.text,
      avatar: avatarSrc(x.acc),
    };
  }

  function pickWithinCap(usable, cap, kind) {
    var nBull = 0;
    var nBear = 0;
    var bullAt = -1;
    var bearAt = -1;
    for (var i = 0; i < usable.length; i++) {
      var s = usable[i].row.s;
      if (s === 'bull') {
        if (bullAt < 0) bullAt = i;
        nBull++;
      } else if (s === 'bear') {
        if (bearAt < 0) bearAt = i;
        nBear++;
      }
    }
    var both = nBull > 0 && nBear > 0;
    var reserve = both && kind !== 'bull' && kind !== 'bear';
    if (!reserve) return usable.slice(0, cap);
    var minority = nBull < nBear ? 'bull' : nBear < nBull ? 'bear' : (bearAt > bullAt ? 'bear' : 'bull');
    var firstMinor = null;
    for (var k = 0; k < usable.length; k++) {
      if (usable[k].row.s === minority) { firstMinor = usable[k]; break; }
    }
    if (!firstMinor) return usable.slice(0, cap);
    var out = [];
    var seen = false;
    for (var n = 0; n < usable.length && out.length < cap; n++) {
      var item = usable[n];
      var last = out.length === cap - 1;
      if (last && !seen && item.row.s !== minority) {
        out.push(firstMinor);
        break;
      }
      out.push(item);
      if (item.row.s === minority) seen = true;
    }
    return out;
  }

  function pack(view, hit) {
    var g = hit.g;
    var kind = hit.kind;
    var url = stockShareUrl(g.t);
    var badge = badgeText(kind);
    var rows = (g && g.rows) || [];
    return {
      view: view,
      viewLabel: viewLabel(view),
      ticker: g.t,
      name: companyName(g.t),
      kind: kind,
      badge: badge,
      nb: g.nb,
      nr: g.nr,
      meta: metaText(kind, g.nb, g.nr),
      excerpts: packExcerpts({ rows: rows, kind: kind }, themeCap(window.CT_SHARE_THEME, 4)),
      _rows: rows,
      url: url,
      displayUrl: displayOf(url),
      text: stockText(g.t, badge),
    };
  }

  function tickerOnly(view, ticker) {
    var url = stockShareUrl(ticker);
    var base = emptyPayload(view);
    base.ticker = ticker;
    base.url = url;
    base.displayUrl = displayOf(url);
    base.text = stockText(ticker, '');
    return base;
  }

  function collect() {
    var view = viewKey();
    var G = groupsFor(view);
    if (focus && focus.ticker) {
      var picked = G ? findGroup(G, focus.ticker, focus.kind) : null;
      if (picked) return pack(view, picked);
      return tickerOnly(view, focus.ticker);
    }
    var hero = rankHero(G);
    if (!hero) return emptyPayload(view);
    return pack(view, hero);
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

  function loadFace(src) {
    return new Promise(function (resolve) {
      if (!src || !/^data:image\//.test(src)) { resolve(null); return; }
      var img = new Image();
      var done = false;
      function finish(v) { if (!done) { done = true; resolve(v); } }
      img.onload = function () { finish(img.naturalWidth ? img : null); };
      img.onerror = function () { finish(null); };
      setTimeout(function () { finish(null); }, 2500);
      img.src = src;
    });
  }

  function loadFaces(rows) {
    return Promise.all((rows || []).map(function (r) { return loadFace(r && r.avatar); }));
  }

  function readyFonts(th) {
    if (!document.fonts || !document.fonts.load) return Promise.resolve();
    var jobs = [
      document.fonts.ready,
      document.fonts.load(th.weightDisplay + ' ' + th.brandSize + 'px ' + th.fontDisplay),
      document.fonts.load(th.weightDisplay + ' ' + th.viewSize + 'px ' + th.fontDisplay),
      document.fonts.load(th.weightData + ' ' + (th.heroSize || th.tickerSize) + 'px ' + th.fontData),
      document.fonts.load(th.weightBody + ' ' + th.metaSize + 'px ' + th.fontBody),
      document.fonts.load(th.weightBody + ' ' + th.nameSize + 'px ' + th.fontBody),
      document.fonts.load(th.weightBadge + ' ' + th.badgeSize + 'px ' + th.fontBody),
      document.fonts.load(th.weightBadge + ' ' + th.nameRowSize + 'px ' + th.fontBody),
      document.fonts.load(th.weightBody + ' ' + th.excerptSize + 'px ' + th.fontBody),
      document.fonts.load(th.weightBody + ' ' + th.handleSize + 'px ' + th.fontBody),
      document.fonts.load(th.weightBadge + ' ' + th.letterSize + 'px ' + th.fontBody),
      document.fonts.load(th.weightData + ' ' + th.urlSize + 'px ' + th.fontData),
    ];
    return Promise.race([
      Promise.all(jobs).then(function () {}, function () {}),
      new Promise(function (resolve) { setTimeout(resolve, 2500); }),
    ]);
  }

  function fit(g, text, maxW) {
    var chars = Array.from(String(text || ''));
    var s = chars.join('');
    if (g.measureText(s).width <= maxW) return s;
    while (chars.length > 1 && g.measureText(chars.join('') + '…').width > maxW) chars.pop();
    return chars.join('') + '…';
  }

  function wrapText(g, text, maxW, maxLines) {
    var rest = Array.from(String(text || '').replace(/\s+/g, ' ').trim());
    var lines = [];
    maxLines = maxLines || 1;
    while (rest.length && lines.length < maxLines) {
      var whole = rest.join('');
      if (g.measureText(whole).width <= maxW) { lines.push(whole); break; }
      var lo = 1;
      var hi = rest.length;
      var cut = 1;
      while (lo <= hi) {
        var mid = (lo + hi) >> 1;
        if (g.measureText(rest.slice(0, mid).join('')).width <= maxW) { cut = mid; lo = mid + 1; }
        else hi = mid - 1;
      }
      var chunk = rest.slice(0, cut).join('');
      if (cut < rest.length) {
        var sp = chunk.lastIndexOf(' ');
        if (sp > 0) {
          var word = chunk.slice(0, sp);
          if (g.measureText(word).width <= maxW) {
            chunk = word;
            cut = Array.from(word).length;
          }
        }
      }
      if (lines.length === maxLines - 1 && cut < rest.length) {
        var line = chunk.trim();
        var marked = line + '…';
        chunk = g.measureText(marked).width <= maxW ? marked : fit(g, line, maxW);
      }
      if (!chunk) break;
      lines.push(chunk.trim());
      rest = rest.slice(cut);
      while (rest.length && rest[0] === ' ') rest = rest.slice(1);
    }
    return lines;
  }

  function inkOf(th, kind) {
    if (kind === 'bear') return th.bear;
    if (kind === 'split') return th.split;
    if (kind === 'bull') return th.bull;
    return th.muted;
  }

  function stanceInk(th, s) {
    if (s === 'bear') return th.bear;
    if (s === 'bull') return th.bull;
    return th.muted;
  }

  function letterOf(handle) {
    var ch = Array.from(String(handle || ''))[0] || '?';
    return ch.toUpperCase();
  }

  function drawCover(g, img, x, y, size) {
    var iw = img.naturalWidth || img.width;
    var ih = img.naturalHeight || img.height;
    if (!iw || !ih) return false;
    var s = Math.max(size / iw, size / ih);
    var dw = iw * s;
    var dh = ih * s;
    g.save();
    g.beginPath();
    g.arc(x + size / 2, y + size / 2, size / 2, 0, Math.PI * 2);
    g.clip();
    g.drawImage(img, x + (size - dw) / 2, y + (size - dh) / 2, dw, dh);
    g.restore();
    return true;
  }

  function drawLetter(g, th, x, y, handle) {
    var size = th.avatar;
    g.fillStyle = th.pill;
    g.beginPath();
    g.arc(x + size / 2, y + size / 2, size / 2, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = th.fg;
    g.font = th.weightBadge + ' ' + th.letterSize + 'px ' + th.fontBody;
    g.textAlign = 'center';
    g.textBaseline = 'middle';
    g.fillText(letterOf(handle), x + size / 2, y + size / 2);
    g.textAlign = 'left';
    g.textBaseline = 'top';
  }

  function drawAvatar(g, th, img, x, y, handle) {
    var ok = false;
    if (img) {
      try { ok = drawCover(g, img, x, y, th.avatar); } catch (e) { ok = false; }
    }
    if (!ok) drawLetter(g, th, x, y, handle);
  }

  function drawBrand(g, th, icon, x, y, inner) {
    if (icon) {
      g.save();
      roundRect(g, x, y, th.logo, th.logo, Math.round(th.radius * 0.55));
      g.clip();
      g.drawImage(icon, x, y, th.logo, th.logo);
      g.restore();
    }
    g.fillStyle = th.fg;
    g.textBaseline = 'middle';
    g.textAlign = 'left';
    g.font = th.weightDisplay + ' ' + th.brandSize + 'px ' + th.fontDisplay;
    var brandX = icon ? x + th.logo + th.headerGap : x;
    g.fillText(fit(g, 'The Crowd Tape', x + inner - brandX), brandX, y + th.logo / 2);
    return y + Math.max(th.logo, th.brandSize) + th.headerGap;
  }

  function showHandle(row) {
    if (!row || !row.handle) return false;
    var name = String(row.name || '').replace(/^@/, '');
    return name.toLowerCase() !== String(row.handle).toLowerCase();
  }

  function excerptHeight(g, th, row, textW) {
    g.font = th.weightBody + ' ' + th.excerptSize + 'px ' + th.fontBody;
    var lines = wrapText(g, row.text, textW, th.excerptLines || 3);
    var h = th.nameRowSize + 6;
    if (showHandle(row)) h += th.handleSize + 8;
    h += lines.length * th.excerptLine;
    return { lines: lines, h: Math.max(th.avatar, h) };
  }

  function drawExcerpt(g, th, row, img, x, y, inner) {
    var textX = x + th.avatar + th.avatarGap;
    var textW = Math.max(40, inner - th.avatar - th.avatarGap);
    var measured = excerptHeight(g, th, row, textW);
    drawAvatar(g, th, img, x, y, row.handle);
    var stance = row.stanceLabel || '';
    g.font = th.weightBadge + ' ' + th.badgeSize + 'px ' + th.fontBody;
    var stanceW = stance ? g.measureText(stance).width : 0;
    var nameMax = Math.max(40, textW - (stance ? stanceW + 16 : 0));
    g.textAlign = 'left';
    g.textBaseline = 'top';
    g.font = th.weightBadge + ' ' + th.nameRowSize + 'px ' + th.fontBody;
    g.fillStyle = th.fg;
    g.fillText(fit(g, row.name || ('@' + row.handle), nameMax), textX, y);
    if (stance) {
      g.font = th.weightBadge + ' ' + th.badgeSize + 'px ' + th.fontBody;
      g.fillStyle = stanceInk(th, row.stance);
      g.fillText(fit(g, stance, stanceW + 2), textX + textW - stanceW, y + Math.max(0, (th.nameRowSize - th.badgeSize) / 2));
    }
    var ty = y + th.nameRowSize + 6;
    if (showHandle(row)) {
      g.fillStyle = th.muted;
      g.font = th.weightBody + ' ' + th.handleSize + 'px ' + th.fontBody;
      g.fillText(fit(g, '@' + row.handle, textW), textX, ty);
      ty += th.handleSize + 8;
    }
    g.fillStyle = th.fg;
    g.font = th.weightBody + ' ' + th.excerptSize + 'px ' + th.fontBody;
    measured.lines.forEach(function (line) {
      g.fillText(line, textX, ty);
      ty += th.excerptLine;
    });
    return measured.h;
  }

  function drawHero(g, th, data, x, y, inner) {
    var color = inkOf(th, data.kind);
    var rail = th.rail || 0;
    var tx = x + (rail ? rail + th.headerGap : 0);
    var top = y;
    var badge = data.badge || '';
    var bw = 0;
    var bh = th.badgeSize + 18;
    var padX = 18;
    if (badge) {
      g.font = th.weightBadge + ' ' + th.badgeSize + 'px ' + th.fontBody;
      bw = Math.min(inner * 0.56, g.measureText(badge).width + padX * 2);
    }
    var bx = x + inner - bw;
    var tickerMax = Math.max(40, (bw ? bx - 16 : x + inner) - tx);
    g.textAlign = 'left';
    g.textBaseline = 'top';
    g.fillStyle = th.fg;
    g.font = th.weightData + ' ' + th.heroSize + 'px ' + th.fontData;
    g.fillText(fit(g, data.ticker, tickerMax), tx, y);
    if (badge) {
      var by = y + (th.heroSize - bh) / 2;
      g.fillStyle = th.pill;
      roundRect(g, bx, by, bw, bh, bh / 2);
      g.fill();
      g.fillStyle = color;
      g.textBaseline = 'middle';
      g.font = th.weightBadge + ' ' + th.badgeSize + 'px ' + th.fontBody;
      g.fillText(fit(g, badge, bw - padX * 2), bx + padX, by + bh / 2);
      g.textBaseline = 'top';
    }
    y += th.heroSize + Math.round(th.headerGap * 0.55);
    if (data.name) {
      g.fillStyle = th.muted;
      g.font = th.weightBody + ' ' + th.nameSize + 'px ' + th.fontBody;
      g.fillText(fit(g, data.name, inner - (tx - x)), tx, y);
      y += th.nameSize + Math.round(th.headerGap * 0.4);
    }
    if (data.meta) {
      g.fillStyle = th.muted;
      g.font = th.weightBody + ' ' + th.metaSize + 'px ' + th.fontBody;
      g.fillText(fit(g, data.meta, inner - (tx - x)), tx, y);
      y += th.metaSize;
    }
    if (rail && data.kind) {
      g.fillStyle = color;
      var rh = Math.max(rail, y - top - 8);
      roundRect(g, x, top + 6, rail, rh, rail / 2);
      g.fill();
    }
    return y;
  }

  function drawUrl(g, th, data, x, inner) {
    var urlTop = th.height - th.safeBottom - th.urlSize;
    g.textAlign = 'left';
    g.textBaseline = 'top';
    g.fillStyle = th.muted;
    g.font = th.weightData + ' ' + th.urlSize + 'px ' + th.fontData;
    g.fillText(fit(g, data.displayUrl || '', inner), x, urlTop);
    return urlTop;
  }

  function paintStory(g, th, data, icon, faces) {
    var x = th.marginX;
    var y = th.safeTop;
    var inner = th.width - th.marginX * 2;
    g.fillStyle = th.bg;
    g.fillRect(0, 0, th.width, th.height);
    y = drawBrand(g, th, icon, x, y, inner);
    g.textBaseline = 'top';
    g.fillStyle = th.muted;
    g.font = th.weightDisplay + ' ' + th.viewSize + 'px ' + th.fontDisplay;
    g.fillText(fit(g, data.viewLabel || '', inner), x, y);
    y += th.viewSize + th.sectionGap;
    if (data.ticker) {
      y = drawHero(g, th, data, x, y, inner);
      var excerpts = (data.excerpts || []).slice(0, th.maxExcerpts != null ? th.maxExcerpts : 4);
      if (excerpts.length) {
        y += th.sectionGap;
        g.strokeStyle = th.line;
        g.lineWidth = th.rule;
        g.beginPath();
        g.moveTo(x, y + 0.5);
        g.lineTo(x + inner, y + 0.5);
        g.stroke();
        y += th.sectionGap;
        var limit = th.height - th.safeBottom - th.urlSize - th.headerGap;
        for (var i = 0; i < excerpts.length; i++) {
          var row = excerpts[i];
          var textW = Math.max(40, inner - th.avatar - th.avatarGap);
          var box = excerptHeight(g, th, row, textW);
          if (y + box.h > limit) break;
          drawExcerpt(g, th, row, faces[i], x, y, inner);
          y += box.h + th.excerptGap;
        }
      }
    }
    drawUrl(g, th, data, x, inner);
  }

  function paintWide(g, th, data, icon, faces) {
    var x = th.marginX;
    var y = th.safeTop;
    var full = th.width - th.marginX * 2;
    g.fillStyle = th.bg;
    g.fillRect(0, 0, th.width, th.height);
    var excerpts = (data.excerpts || []).slice(0, th.maxExcerpts != null ? th.maxExcerpts : 2);
    var split = !!(data.ticker && excerpts.length && th.colW);
    var leftW = split ? th.colW : full;
    y = drawBrand(g, th, icon, x, y, leftW);
    g.textBaseline = 'top';
    g.fillStyle = th.muted;
    g.font = th.weightDisplay + ' ' + th.viewSize + 'px ' + th.fontDisplay;
    g.fillText(fit(g, data.viewLabel || '', leftW), x, y);
    y += th.viewSize + th.sectionGap;
    if (data.ticker) y = drawHero(g, th, data, x, y, leftW);
    if (split) {
      var rx = x + th.colW + th.sectionGap;
      var rw = th.width - th.marginX - rx;
      g.strokeStyle = th.line;
      g.lineWidth = th.rule;
      var ruleBottom = th.height - th.safeBottom - th.urlSize - th.headerGap;
      g.beginPath();
      g.moveTo(x + th.colW + th.sectionGap / 2, th.safeTop);
      g.lineTo(x + th.colW + th.sectionGap / 2, ruleBottom);
      g.stroke();
      var ry = th.safeTop;
      var limit = th.height - th.safeBottom - th.headerGap;
      for (var i = 0; i < excerpts.length; i++) {
        var row = excerpts[i];
        var textW = Math.max(40, rw - th.avatar - th.avatarGap);
        var box = excerptHeight(g, th, row, textW);
        if (ry + box.h > limit) break;
        drawExcerpt(g, th, row, faces[i], rx, ry, rw);
        ry += box.h + th.excerptGap;
      }
    }
    drawUrl(g, th, data, x, leftW);
  }

  function paint(g, th, data, icon, faces) {
    if (th.layout === 'wide') paintWide(g, th, data, icon, faces || []);
    else paintStory(g, th, data, icon, faces || []);
  }

  function keyOf(data, th) {
    var rows = (data.excerpts || []).map(function (r) {
      return [r.handle, r.name, r.stance, r.stanceLabel, r.text].join('\u0001');
    }).join('\u0002');
    return [
      th.width, th.height, th.layout || '', data.url, data.view, data.ticker, data.name,
      data.kind, data.badge, data.meta, data.text, rows,
    ].join('~');
  }

  function withThemeExcerpts(data, th) {
    if (!data || !data._rows) return data;
    var cap = th && th.maxExcerpts != null ? th.maxExcerpts : 4;
    return Object.assign({}, data, {
      excerpts: packExcerpts({ rows: data._rows, kind: data.kind }, cap),
    });
  }

  function renderThemed(snapshot, th) {
    var data = withThemeExcerpts(snapshot || collect(), th);
    var key = keyOf(data, th);
    if (cache.canvas && cache.key === key) return Promise.resolve(cache.canvas);
    if (cache.pending && cache.key === key) return cache.pending;
    cache.key = key;
    cache.canvas = null;
    var shown = (data.excerpts || []).slice(0, th.maxExcerpts != null ? th.maxExcerpts : 4);
    cache.pending = Promise.all([readyFonts(th), loadIcon(), loadFaces(shown)]).then(function (xs) {
      var canvas = document.createElement('canvas');
      canvas.width = th.width;
      canvas.height = th.height;
      var g = canvas.getContext('2d');
      paint(g, th, data, xs[1], xs[2]);
      if (cache.key === key) { cache.canvas = canvas; cache.pending = null; }
      return canvas;
    }).catch(function (e) {
      if (cache.key === key) cache.pending = null;
      throw e;
    });
    return cache.pending;
  }

  function renderCard(snapshot) {
    return renderThemed(snapshot, window.CT_SHARE_THEME);
  }

  function renderOg(snapshot) {
    return renderThemed(snapshot, window.CT_SHARE_OG_THEME || window.CT_SHARE_THEME);
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
    } catch (e2) { return false; }
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
      applyHeading(data);
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

  function applyHeading(data) {
    var h = document.getElementById('ct-share-h');
    if (!h) return;
    if (data && data.ticker) {
      h.textContent = dict('share-one', isZh() ? '分享此股票' : 'Share this stock') + ' · ' + data.ticker;
    } else {
      h.textContent = dict('share-page', isZh() ? '分享此頁' : 'Share this page');
    }
  }

  function markExpanded(src, open) {
    var nodes = document.querySelectorAll('#ct-share-btn,[data-ct-share-ticker]');
    for (var i = 0; i < nodes.length; i++) {
      if (!nodes[i].hasAttribute('aria-expanded') && nodes[i].id !== 'ct-share-btn') continue;
      nodes[i].setAttribute('aria-expanded', open && nodes[i] === src ? 'true' : 'false');
    }
  }

  function openPanel(src) {
    var els = panelEls();
    if (!els.panel || !els.btn) return;
    closeSearch();
    say('');
    syncSystem(els.panel);
    applyHeading(collect());
    els.panel.hidden = false;
    markExpanded(src || els.btn, true);
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
    markExpanded(null, false);
    if (els.btn) {
      els.btn.setAttribute('aria-expanded', 'false');
      if (els.panel.contains(document.activeElement)) els.btn.focus();
    }
  }

  function isPhone() {
    return !!(window.matchMedia && matchMedia('(max-width:734px)').matches);
  }

  function dropCache() {
    cache.key = '';
    cache.canvas = null;
    cache.pending = null;
  }

  function bind() {
    var els = panelEls();
    if (!els.btn || !els.panel || els.btn.dataset.ctShare) return;
    els.btn.dataset.ctShare = '1';
    if (els.panel.parentNode !== document.body) document.body.appendChild(els.panel);
    els.btn.addEventListener('pointerdown', function () {
      if (!els.panel.hidden) return;
      focus = null;
      renderCard().catch(function () {});
    }, { passive: true });
    els.btn.addEventListener('click', function () {
      if (!els.panel.hidden) { closePanel(); return; }
      focus = null;
      openPanel(els.btn);
      if (isPhone() && navigator.share) shareSystem().catch(function () {});
    });
    document.addEventListener('pointerdown', function (e) {
      var hit = e.target.closest && e.target.closest('[data-ct-share-ticker]');
      if (!hit) return;
      var next = {
        ticker: hit.getAttribute('data-ct-share-ticker') || '',
        kind: hit.getAttribute('data-ct-share-kind') || '',
      };
      var same = focus && focus.ticker === next.ticker && focus.kind === next.kind;
      focus = next;
      if (!same) dropCache();
      renderCard().catch(function () {});
    }, true);
    document.addEventListener('click', function (e) {
      var hit = e.target.closest && e.target.closest('[data-ct-share-ticker]');
      if (hit) {
        e.preventDefault();
        e.stopPropagation();
        focus = {
          ticker: hit.getAttribute('data-ct-share-ticker') || '',
          kind: hit.getAttribute('data-ct-share-kind') || '',
        };
        if (els.panel.hidden) {
          openPanel(hit);
          if (isPhone() && navigator.share) shareSystem().catch(function () {});
        } else {
          say('');
          applyHeading(collect());
          markExpanded(hit, true);
        }
        return;
      }
      if (els.panel.hidden) return;
      if (e.target.closest && (e.target.closest('#ct-share-panel') || e.target.closest('#ct-share-btn'))) return;
      closePanel();
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
    window.addEventListener('hashchange', function () {
      focus = null;
      dropCache();
      if (!els.panel.hidden) applyHeading(collect());
    });
  }

  window.CTShare = {
    get theme() { return window.CT_SHARE_THEME; },
    get ogTheme() { return window.CT_SHARE_OG_THEME; },
    collect: collect,
    packExcerpts: packExcerpts,
    renderCard: renderCard,
    renderOg: renderOg,
    shareSystem: shareSystem,
    shareUrl: function () { return collect().url; },
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
