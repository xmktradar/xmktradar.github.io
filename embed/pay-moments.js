/* Category reweight, watch alerts, and the weekly teaser. Official consensus stays. */
(function () {
  var KEY = 'ct_weights_off';
  var WATCH = 'ct_watch';
  var SIDE = 'ct_watch_side';
  var LABELS = {
    '大人物／企業家': 'Prominent',
    '宏觀': 'Macro',
    '股市意見': 'Market opinions',
    '基本面／主題': 'Fundamentals',
    '半導體／AI': 'Semiconductors / AI',
    '交易員': 'Traders'
  };
  var zh = (document.documentElement.lang || '').toLowerCase().indexOf('zh') === 0;

  function t(zhText, enText) { return zh ? zhText : enText; }
  function read(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) || fallback; } catch (e) { return fallback; }
  }
  function write(key, value) { localStorage.setItem(key, JSON.stringify(value)); }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&', '<': '<', '>': '>', '"': '"', "'": '&#39;' }[c];
    });
  }
  function onDaily() {
    var h = (location.hash || '#daily').replace(/^#/, '').split('/')[0];
    return h === '' || h === 'daily';
  }
  function sideName(side) {
    if (side === 'bull') return t('共同看好', 'Consensus bullish');
    if (side === 'bear') return t('共同看淡', 'Consensus bearish');
    if (side === 'split') return t('分歧', 'Split');
    return '';
  }
  function lists(allow) {
    var api = window.__ct;
    if (!api || !api.win || !api.groups) return null;
    var w = api.win();
    if (!w) return null;
    var g = api.groups(w.from, w.to, allow);
    return { bull: g.bull.map(function (x) { return x.t; }), bear: g.bear.map(function (x) { return x.t; }), split: g.split.map(function (x) { return x.t; }) };
  }
  function bucket(map, ticker) {
    if (map.bull.indexOf(ticker) >= 0) return 'bull';
    if (map.bear.indexOf(ticker) >= 0) return 'bear';
    if (map.split.indexOf(ticker) >= 0) return 'split';
    return 'none';
  }
  function cats() {
    var api = window.__ct;
    return api && api.cats ? api.cats() : [];
  }
  function offSet() { return read(KEY, []); }
  function allow() {
    var off = offSet();
    if (!off.length) return null;
    var o = {};
    cats().forEach(function (name) { if (off.indexOf(name) < 0) o[name] = true; });
    return o;
  }
  function watches() {
    return read(WATCH, []).filter(function (s) { return /^[A-Z][A-Z0-9.]{0,9}$/.test(s); });
  }
  function css() {
    if (document.getElementById('ct-pay-css')) return;
    var s = document.createElement('style');
    s.id = 'ct-pay-css';
    s.textContent = '#ct-pay{box-sizing:border-box;max-width:100%;margin:0 0 14px;padding:14px 16px;border-radius:16px;background:var(--surface,#fff);overflow-wrap:anywhere}'
      + '#ct-pay h2{margin:14px 0 6px;font-size:16px}#ct-pay h2:first-child{margin-top:0}'
      + '#ct-pay p,#ct-pay li{font-size:14px;line-height:1.55}'
      + '#ct-pay .ct-chips{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}'
      + '#ct-pay button,#ct-pay .ct-add{box-sizing:border-box;min-height:44px;border-radius:999px;border:1px solid var(--line,#e3e3e8);background:transparent;color:inherit;font:inherit;padding:6px 12px}'
      + '#ct-pay button[aria-pressed="false"]{opacity:.45}'
      + '#ct-pay input{box-sizing:border-box;min-height:44px;max-width:100%;border-radius:12px;border:1px solid var(--line,#e3e3e8);background:transparent;color:inherit;font:inherit;padding:8px 10px}'
      + '#ct-pay .ct-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}'
      + '#ct-pay .ct-bull{color:#127a3a;font-weight:700}#ct-pay .ct-bear{color:#c2410c;font-weight:700}'
      + '#ct-pay a{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}';
    document.head.appendChild(s);
  }
  function links(tickers) {
    if (!tickers.length) return t('沒有', 'none');
    return tickers.map(function (ticker) {
      return '<a href="#stock/' + encodeURIComponent(ticker) + '">' + esc(ticker) + '</a>';
    }).join(t('、', ', '));
  }
  function notify(ticker, side) {
    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    var title = t('關注股票', 'Watched stock');
    var body = ticker + ' ' + t('新列入', 'newly listed as') + sideName(side);
    try { new Notification(title, { body: body }); } catch (e) {}
  }
  function checkWatch(map) {
    var mine = watches();
    if (!mine.length || !map) return;
    var prev = read(SIDE, null);
    var next = {};
    mine.forEach(function (ticker) { next[ticker] = bucket(map, ticker); });
    if (!prev) { write(SIDE, next); return; }
    mine.forEach(function (ticker) {
      var now = next[ticker], before = prev[ticker] || 'none';
      if (now !== 'none' && now !== before) notify(ticker, now);
    });
    write(SIDE, next);
  }
  function paint() {
    css();
    var view = document.getElementById('view');
    var old = document.getElementById('ct-pay');
    if (!view || !onDaily() || !window.__ct) {
      if (old) old.remove();
      return;
    }
    var box = old;
    if (!box) {
      box = document.createElement('section');
      box.id = 'ct-pay';
      box.setAttribute('aria-label', t('週報、類別、關注', 'Weekly, categories, watchlist'));
    }
    if (view.firstChild !== box) view.insertBefore(box, view.firstChild);
    if (box.contains(document.activeElement)) { fillResults(box); return; }
    var off = offSet();
    var names = cats();
    var chips = names.map(function (name) {
      var on = off.indexOf(name) < 0;
      var label = zh ? name : (LABELS[name] || name);
      return '<button type="button" data-cat="' + esc(name) + '" aria-pressed="' + (on ? 'true' : 'false') + '">' + esc(label) + '</button>';
    }).join('');
    var mine = watches();
    var watchChips = mine.map(function (ticker) {
      return '<button type="button" data-drop="' + esc(ticker) + '">' + esc(ticker) + ' ×</button>';
    }).join('');
    box.innerHTML = '<h2>' + t('今個星期的名稱在電郵', 'This week’s names are in the email') + '</h2>'
      + '<p>' + t('首頁這張名單是現時共識，免費。已結算的 10 日成績（包括跑輸）在週報頁公開。今個星期新列入的名稱不寫在網頁，下週一寄給訂戶。',
        'The list on this page is the current consensus, and it is free. Settled 10-session results, including losses, are public on the weekly page. Names newly added this week are not on the site; subscribers get them on Monday.') + '</p>'
      + '<p><a href="/zh/weekly/">' + t('看已結算成績並訂閱（每月 USD 5）', 'Settled results and subscribe (USD 5 / month)') + '</a></p>'
      + '<h2>' + t('按類別重算', 'Recalculate by category') + '</h2>'
      + '<p>' + t('六類都計入時，與官方共識相同。關掉一類，只改下面這一欄，官方名單不變。',
        'With every category on, this matches the official consensus. Turning one off changes only the list below.') + '</p>'
      + '<div class="ct-chips">' + chips + '</div>'
      + '<div id="ct-weight"></div>'
      + '<h2>' + t('關注', 'Watchlist') + '</h2>'
      + '<p>' + t('股票新列入共同看好、共同看淡或分歧時，通知這部裝置。不會寄電郵。',
        'This device is notified when a watched stock is newly listed as bullish, bearish, or split. No email.') + '</p>'
      + '<div class="ct-row"><input id="ct-watch-in" inputmode="latin" autocapitalize="characters" maxlength="12" placeholder="' + t('代號，例如 NVDA', 'Ticker, e.g. NVDA') + '" aria-label="' + t('股票代號', 'Ticker') + '">'
      + '<button type="button" class="ct-add" id="ct-watch-add">' + t('加入', 'Add') + '</button>'
      + '<button type="button" id="ct-notify">' + t('開啟裝置通知', 'Turn on device alerts') + '</button></div>'
      + '<div class="ct-chips" id="ct-watch-list">' + watchChips + '</div>'
      + '<p id="ct-notify-note"></p>';
    box.querySelectorAll('[data-cat]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var name = btn.getAttribute('data-cat');
        var cur = offSet();
        var i = cur.indexOf(name);
        if (i >= 0) cur.splice(i, 1); else cur.push(name);
        write(KEY, cur);
        paint();
      });
    });
    box.querySelectorAll('[data-drop]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var ticker = btn.getAttribute('data-drop');
        write(WATCH, watches().filter(function (x) { return x !== ticker; }));
        paint();
      });
    });
    var add = box.querySelector('#ct-watch-add');
    var input = box.querySelector('#ct-watch-in');
    function addTicker() {
      var ticker = (input.value || '').trim().toUpperCase();
      if (!/^[A-Z][A-Z0-9.]{0,9}$/.test(ticker)) return;
      var cur = watches();
      if (cur.indexOf(ticker) < 0) cur.push(ticker);
      write(WATCH, cur);
      input.value = '';
      paint();
    }
    add.addEventListener('click', addTicker);
    input.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); addTicker(); } });
    box.querySelector('#ct-notify').addEventListener('click', function () {
      var note = box.querySelector('#ct-notify-note');
      if (!('Notification' in window)) { note.textContent = t('這部裝置不支援通知。', 'This device does not support notifications.'); return; }
      Notification.requestPermission().then(function (perm) {
        note.textContent = perm === 'granted'
          ? t('已開啟。新轉入看好、看淡或分歧時會通知。', 'On. You will be notified on a new bullish, bearish, or split listing.')
          : t('未獲允許，不會通知。', 'Permission was not granted.');
      });
    });
    fillResults(box);
  }
  function fillResults(box) {
    var slot = box.querySelector('#ct-weight');
    if (!slot) return;
    var base = lists(null);
    var custom = lists(allow());
    if (!base) { slot.textContent = ''; return; }
    checkWatch(base);
    if (!custom || offSet().length === 0) {
      slot.innerHTML = '<p>' + t('而家計入全部類別，與官方共識相同。', 'Every category is included. This matches the official consensus.') + '</p>';
      return;
    }
    slot.innerHTML = '<p>' + t('這個選法跟官方共識不同。', 'This selection differs from the official consensus.') + '</p>'
      + '<p><span class="ct-bull">' + t('共同看好', 'Bullish') + '</span>：' + links(custom.bull) + '</p>'
      + '<p><span class="ct-bear">' + t('共同看淡', 'Bearish') + '</span>：' + links(custom.bear) + '</p>'
      + '<p>' + t('分歧', 'Split') + '：' + links(custom.split) + '</p>';
  }

  window.__ctAfter = function () { try { paint(); } catch (e) { console.error(e); } };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', window.__ctAfter);
  else window.__ctAfter();
})();
