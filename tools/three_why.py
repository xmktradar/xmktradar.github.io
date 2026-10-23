"""Today-in-3-lines and per-stock why posts for the weekday social run.

three_lines copies the homepage block (index.html RUX.threeLines + the zh/en/ko
lines). why_posts quotes real writeup rows[].why for the hottest names from
ranking.rank_rows. Weekends do not build either slot.
"""
import re
from datetime import datetime, timedelta

from ranking import rank_rows
from sitedata import HK

S_OF = {'睇好': 'bull', '睇淡': 'bear', '中性': 'neu'}
_CLAUSE_SPLIT = re.compile(r'(?<=[\u3002\uff1b\uff01\uff1f!?;])\s*|(?<=\.)\s+')
_TK_RE = re.compile(r'\$[A-Za-z][A-Za-z0-9.]{0,6}')
_URL_RE = re.compile(r'https?://\S+', re.I)

T3_COPY = {
    'zh': {
        'title': '今日三句重點',
        'shift': '共識變化最大',
        'delta': '淨看多比例 {frm} → {to}（對比昨日（今日至今））',
        'chg': '{n} 次立場轉變',
        'most': '最多人討論',
        'most_rest': '{n} 個觀點、{a} 個帳號',
        'split': '分歧最大',
        'split_rest': '看多 {b}、看空 {e}',
        'sample': '{w} · {posts} 則貼文 / {accounts} 個帳號',
        'empty': '範圍內資料不足，暫時未能整理。',
        'bull_h': '看好理由',
        'bear_h': '看淡理由',
        'acc': '{n} 個帳號',
    },
    'en': {
        'title': 'Today in 3 lines',
        'shift': 'Biggest consensus shift',
        'delta': 'net bullish {frm} → {to} (vs yesterday (today so far))',
        'chg': '{n} stance changes',
        'most': 'Most mentioned',
        'most_rest': '{n} views, {a} accounts',
        'split': 'Biggest disagreement',
        'split_rest': 'Bullish {b}, bearish {e}',
        'sample': '{w} · {posts} posts / {accounts} accounts',
        'empty': 'Not enough data in this window yet.',
        'bull_h': 'Bullish reasons',
        'bear_h': 'Bearish reasons',
        'acc': '{n} accounts',
    },
    'ko': {
        'title': '오늘의 3줄 요약',
        'shift': '합의 변화 최대',
        'delta': '순강세 비율 {frm} → {to} (어제 대비 (오늘 현재까지))',
        'chg': '{n} 회 입장 변경',
        'most': '최다 언급',
        'most_rest': '{n} 개 의견, {a} 개 계정',
        'split': '의견 차이 최대',
        'split_rest': '강세 {b}, 약세 {e}',
        'sample': '{w} · 게시물 {posts} / 계정 {accounts}',
        'empty': '이 기간의 데이터가 아직 부족합니다.',
        'bull_h': '강세 이유',
        'bear_h': '약세 이유',
        'acc': '계정 {n}개',
    },
}
WHY_TITLE = {
    'zh': '今日 {t}：點解',
    'en': 'Why {t} today',
    'ko': '오늘 {t}, 왜',
}
# 07:00 HKT is 08:00 KST. The brief goes out at 08:30 KST, before the 09:00 slot.
THREE_LINES_KST = '08:30'


def _s():
    import share
    return share


def _js_round(n):
    """Math.round: halves go toward +infinity (Math.round(-0.5) is 0)."""
    import math
    return int(math.floor(n + 0.5))


def _pct(x):
    n = _js_round(x * 100)
    return f'+{n}%' if n > 0 else f'{n}%'


def _net(c):
    n = c['bull'] + c['bear'] + c['neu']
    return (c['bull'] - c['bear']) / n if n else 0.0


def three_lines_calc(rows, has_prev):
    """Port of index.html RUX.threeLines. Ties keep the earlier row."""
    shift = most = split = None
    for r in rows or []:
        c = r['c']
        c0 = r.get('c0')
        if has_prev and c0 and (c['bull'] + c['bear']) >= 2 and (c0['bull'] + c0['bear']) >= 1:
            d = _net(c) - _net(c0)
            if abs(d) >= 0.2 and (not shift or shift.get('kind') != 'delta' or abs(d) > abs(shift['d'])):
                shift = {'kind': 'delta', 't': r['t'], 'd': d, 'from': _net(c0), 'to': _net(c)}
        mentions = c.get('mentions') or 0
        if mentions > 0 and (not most or mentions > most['n'] or (mentions == most['n'] and c.get('accs', 0) > most['accs'])):
            most = {'t': r['t'], 'n': mentions, 'accs': c.get('accs') or 0}
        if c['bull'] >= 1 and c['bear'] >= 1:
            m = min(c['bull'], c['bear'])
            total = c['bull'] + c['bear']
            if not split or m > split['m'] or (m == split['m'] and total > split['b'] + split['e']):
                split = {'t': r['t'], 'b': c['bull'], 'e': c['bear'], 'm': m}
    if not shift:
        for r in rows or []:
            chg = r.get('chg') or 0
            if chg > 0 and (not shift or chg > shift['n']):
                shift = {'kind': 'chg', 't': r['t'], 'n': chg}
    return {'shift': shift, 'most': most, 'split': split}


def clause_for(text, ticker):
    """Sentences that name this ticker. A multi-ticker blurb with no such sentence is dropped."""
    text = str(text or '').strip()
    if not text:
        return ''
    parts = [p for p in _CLAUSE_SPLIT.split(text) if p]
    sym = re.sub(r'[^A-Z0-9.]', '', str(ticker or '').upper())
    if not sym:
        return text
    pat = re.compile(r'(^|[^A-Z0-9])\$?' + re.escape(sym).replace(r'\.', r'\.') + r'(?![A-Z0-9])', re.I)
    # re.escape turns '.' into '\.' already; the replace above is a no-op on that. Keep the JS form.
    pat = re.compile(r'(^|[^A-Z0-9])\$?' + sym.replace('.', r'\.') + r'(?![A-Z0-9])', re.I)
    hits = [p for p in parts if pat.search(p)]
    tks = {m.group(0).upper() for m in _TK_RE.finditer(text)}
    if hits:
        return ' '.join(hits)
    if len(tks) > 1:
        return ''
    return text


def _num(n):
    S = _s()
    return n if S._is_num(n) else None


def _as_int(n):
    return _s()._as_int(n)


def _fmt_window(start, end):
    if not start or not end:
        return ''
    if (start.year, start.month, start.day) == (end.year, end.month, end.day):
        return f'{start.month:02d}/{start.day:02d} {start:%H:%M} – {end:%H:%M} HKT'
    return (f'{start.month:02d}/{start.day:02d} {start:%H:%M} – '
            f'{end.month:02d}/{end.day:02d} {end:%H:%M} HKT')


def _parse_dt(value):
    if isinstance(value, datetime):
        return value.astimezone(HK) if value.tzinfo else value.replace(tzinfo=HK)
    s = str(value or '').strip()
    if not s:
        return None
    s = s.replace('Z', '+00:00')
    try:
        if 'T' in s:
            dt = datetime.fromisoformat(s)
        else:
            dt = datetime.strptime(s[:16], '%Y-%m-%d %H:%M')
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=HK)
    return dt.astimezone(HK)


def _ms(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    dt = _parse_dt(value)
    return dt.timestamp() * 1000 if dt else None


def _hk_day_ms(ms):
    return datetime.fromtimestamp(ms / 1000, HK).strftime('%Y-%m-%d')


def _add_days(day, n):
    return (datetime.strptime(day, '%Y-%m-%d') + timedelta(days=n)).strftime('%Y-%m-%d')


def _rk(v, end=False):
    """JS rk(): Date.parse(v + ':00+08:00') plus 59999 ms when end is set."""
    raw = str(v or '')
    if len(raw) == 10:
        raw = raw + 'T00:00'
    dt = datetime.strptime(raw[:16], '%Y-%m-%dT%H:%M').replace(tzinfo=HK)
    ms = dt.timestamp() * 1000
    return ms + (59999 if end else 0)


def _ts_of(ms):
    return datetime.fromtimestamp(ms / 1000, HK).strftime('%Y-%m-%dT%H:%M')


def _in_r(date, ms, frm, to):
    if len(str(frm)) > 10:
        return _rk(frm, False) <= ms <= _rk(to, True)
    return str(frm) <= date <= str(to)


def _site_ticker(t):
    return str(t or '').lstrip('$').upper()


def _nocons(dash):
    tracked = (dash or {}).get('tracked') or {}
    cats = set()
    for c in tracked.get('categories') or []:
        if isinstance(c, dict) and c.get('consensus') is False and c.get('name'):
            cats.add(c['name'])
    out = set()
    for a in tracked.get('accounts') or []:
        if isinstance(a, dict) and a.get('category') in cats:
            h = str(a.get('handle') or '').strip().lower()
            if h:
                out.add(h)
    return out


def _stance_of(post, ticker):
    sbt = post.get('sbt')
    if not sbt:
        return S_OF.get(post.get('stance') or '', 'none')
    for key, val in sbt.items():
        if _site_ticker(key) == ticker:
            return S_OF.get(val, 'none')
    return 'none'


def _expand_posts(posts):
    allp = []
    for p in posts or []:
        if not isinstance(p, dict):
            continue
        ms = _ms(p.get('time_utc'))
        th = str(p.get('time_hkt') or '')
        if ms is None or len(th) < 10:
            continue
        sbt = p.get('stance_by_ticker') if isinstance(p.get('stance_by_ticker'), dict) else None
        tickers = []
        for raw in list(p.get('tickers') or []) + (list(sbt) if sbt else []):
            nt = _site_ticker(raw)
            if nt and nt not in tickers:
                tickers.append(nt)
        allp.append({
            'acc': str(p.get('reposted_by') or p.get('handle') or '').strip(),
            'ms': ms,
            'date': th[:10],
            'folded': bool(p.get('folded_into')),
            'theme': p.get('theme'),
            'platform': p.get('platform') or '',
            'tickers': tickers,
            'sbt': sbt,
            'stance': p.get('stance'),
        })
    allp.sort(key=lambda x: x['ms'])
    return allp


def _views_of(allp):
    views = []
    for p in allp:
        if p['folded'] or p['theme'] == '非市場':
            continue
        for t in p['tickers']:
            views.append({'acc': p['acc'], 't': t, 's': _stance_of(p, t), 'ms': p['ms'], 'd': p['date']})
    return views


def _index_views(views):
    by_at = {}
    for v in views:
        by_at.setdefault((v['acc'], v['t']), []).append(v)
    for seq in by_at.values():
        seq.sort(key=lambda x: x['ms'])
    return by_at


def _change(prev, cur):
    if not prev or not cur or cur['s'] == 'none' or prev['s'] == cur['s']:
        return None
    if prev['s'] in ('bull', 'bear') and cur['s'] in ('bull', 'bear'):
        return 'flip'
    rank = {'bear': 0, 'neu': 1, 'bull': 2}
    if prev['s'] not in rank or cur['s'] not in rank:
        return None
    return 'up' if rank[cur['s']] > rank[prev['s']] else 'down'


def _writer_win(dash, day):
    arr = ((dash or {}).get('summaries') or {}).get('daily') or []
    if not isinstance(arr, list):
        return None
    matches = [x for x in arr if isinstance(x, dict) and x.get('date') == day]
    sm = matches[-1] if matches else None
    if not isinstance(sm, dict):
        return None
    win = sm.get('win')
    if isinstance(win, dict) and win.get('from') and win.get('to'):
        return {'from': str(win['from']), 'to': str(win['to'])}
    return None


def _js_parse_mangled_cutoff(cutoff):
    """index.html does Date.parse(cutoff.replace(' ','T') + ':00+08:00').

    An already-offset timestamp becomes invalid and the scrape window is skipped,
    which is what the page does today.
    """
    raw = str(cutoff or '')
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace(' ', 'T') + ':00+08:00')
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=HK)
    return dt.astimezone(HK)


def _cycle_window(allp, dash, day):
    """Scrape-cycle window, same shape as dailyWindow when the cutoff parse succeeds."""
    meta = (dash or {}).get('meta') or {}
    slots = meta.get('scrape_slots_hkt') or []
    cut = _js_parse_mangled_cutoff(meta.get('cutoff_hkt'))
    if not slots or cut is None:
        return None
    cut_ms = cut.timestamp() * 1000
    cands = []
    for k in (0, 1):
        base = _add_days(cut.strftime('%Y-%m-%d'), -k)
        for sl in slots:
            try:
                dt = datetime.strptime(f'{base}T{sl}', '%Y-%m-%dT%H:%M').replace(tzinfo=HK)
            except ValueError:
                continue
            ms = dt.timestamp() * 1000
            if ms <= cut_ms:
                cands.append(ms)
    last = max(cands) if cands else cut_ms
    frm = _ts_of(last - 86400000)
    to = _ts_of(cut_ms)
    n = sum(1 for p in allp if not p['folded'] and p['theme'] != '非市場' and _in_r(p['date'], p['ms'], frm, to))
    if not n:
        return None
    return {'from': frm, 'to': to, 'timed': True, 'merged': False}


def _daily_window(allp, dash, day):
    win = _writer_win(dash, day)
    if win:
        return {'from': win['from'], 'to': win['to'], 'timed': True, 'merged': False}
    cycle = _cycle_window(allp, dash, day)
    if cycle:
        return cycle
    meta = (dash or {}).get('meta') or {}
    minimum = meta.get('min_daily_posts') or 8
    n = sum(1 for p in allp if not p['folded'] and p['theme'] != '非市場' and p['date'] == day)
    has_prev = any(p['date'] < day for p in allp)
    if n < minimum and has_prev:
        return {'from': _add_days(day, -1), 'to': day, 'timed': False, 'merged': True}
    return {'from': day, 'to': day, 'timed': False, 'merged': False}


def _prev_bounds(w):
    if w['timed']:
        a = _rk(w['from'], False)
        z = _rk(w['to'], True)
        return _ts_of(a - (z - a)), _ts_of(a - 60000)
    length = 2 if w['merged'] else 1
    return _add_days(w['from'], -length), _add_days(w['from'], -1)


def site_rows(dash, day):
    """Homepage inputs for RUX.threeLines, plus the window sample the page shows.

    Returns (rows, has_prev, sample, window) or None when dash has no posts.
    sample posts = valid posts in the window. sample accounts = accounts with a
    non-folded post in the window (the page's 有動態帳號 / active accounts).
    """
    posts = (dash or {}).get('posts')
    if not isinstance(posts, list) or not posts:
        return None
    day = _s()._as_day(day)
    if not day:
        return None
    allp = _expand_posts(posts)
    if not allp:
        return None
    views = _views_of(allp)
    by_at = _index_views(views)
    w = _daily_window(allp, dash, day)
    pf, pt = _prev_bounds(w)

    def in_win(date, ms, frm, to):
        return _in_r(date, ms, frm, to)

    prev_raw = [p for p in allp if not p['folded'] and in_win(p['date'], p['ms'], pf, pt)]
    has_prev = bool(prev_raw)
    if w['timed']:
        xs = [p['ms'] for p in allp if p.get('platform') != 'truthsocial']
        x_first = min(xs) if xs else None
        has_prev = bool(prev_raw) and x_first is not None and x_first <= _rk(pf, False)

    def accs_of(frm, to):
        return {v['acc'] for v in views if v['acc'] and in_win(v['d'], v['ms'], frm, to)}

    def latest_map(frm, to):
        last = {}
        for v in views:
            if not in_win(v['d'], v['ms'], frm, to):
                continue
            key = (v['acc'], v['t'])
            prev = last.get(key)
            if prev is None or v['ms'] >= prev['ms']:
                last[key] = v
        return last

    nocons = _nocons(dash)
    last_now = latest_map(w['from'], w['to'])
    last_prev = latest_map(pf, pt) if has_prev else {}
    acc_now = accs_of(w['from'], w['to'])
    acc_prev = accs_of(pf, pt) if has_prev else set()

    def dist(ticker, last, accs):
        c = {'bull': 0, 'bear': 0, 'neu': 0, 'none': 0, 'accs': 0, 'mentions': 0}
        for acc in accs:
            if str(acc).lower() in nocons:
                continue
            x = last.get((acc, ticker))
            if not x:
                continue
            c[x['s']] = c.get(x['s'], 0) + 1
            c['accs'] += 1
        return c

    cur = [v for v in views if in_win(v['d'], v['ms'], w['from'], w['to'])]
    mentions = {}
    chg = {}
    for v in cur:
        mentions[v['t']] = mentions.get(v['t'], 0) + 1
        prev = None
        for older in by_at.get((v['acc'], v['t']), ()):
            if older['ms'] >= v['ms']:
                break
            if older['s'] != 'none':
                prev = older
        if _change(prev, v):
            chg[v['t']] = chg.get(v['t'], 0) + 1

    rows = []
    for t in sorted(set(v['t'] for v in cur)):
        c = dist(t, last_now, acc_now)
        c['mentions'] = mentions.get(t, 0)
        c0 = None
        if has_prev:
            c0 = dist(t, last_prev, acc_prev)
            c0['mentions'] = sum(1 for v in views if v['t'] == t and in_win(v['d'], v['ms'], pf, pt))
        rows.append({'t': t, 'c': c, 'c0': c0, 'chg': chg.get(t, 0)})

    cur_raw = [p for p in allp if not p['folded'] and in_win(p['date'], p['ms'], w['from'], w['to'])]
    vposts = [p for p in cur_raw if p['theme'] != '非市場']
    sample = {}
    if vposts:
        sample['posts'] = len(vposts)
    if cur_raw:
        sample['accounts'] = len({p['acc'] for p in cur_raw if p['acc']})
    window = ''
    if vposts:
        if w['timed']:
            start = _parse_dt(w['from'] if 'T' in str(w['from']) else str(w['from']) + 'T00:00')
        else:
            start = datetime.strptime(str(w['from'])[:10], '%Y-%m-%d').replace(tzinfo=HK)
        end = datetime.fromtimestamp(max(p['ms'] for p in vposts) / 1000, HK)
        window = _fmt_window(start, end)
    return rows, has_prev, sample, window


def rows_from_writeup(daily):
    """Fallback rows from writeup bull/bear/split. No previous window, so no delta shift."""
    S = _s()
    rows = []
    seen = set()
    for side_name in ('bull', 'bear', 'split'):
        for raw in (daily or {}).get(side_name) or []:
            if not isinstance(raw, dict):
                continue
            t = S._ticker_sym(raw.get('t'))
            if not t or t in seen:
                continue
            seen.add(t)
            nb = raw.get('nb') if S._is_num(raw.get('nb')) else 0
            nr = raw.get('nr') if S._is_num(raw.get('nr')) else 0
            nps = raw.get('n_posts') if S._is_num(raw.get('n_posts')) else 0
            c = {
                'bull': int(nb), 'bear': int(nr), 'neu': 0, 'none': 0,
                'accs': int(nb) + int(nr), 'mentions': int(nps),
            }
            rows.append({'t': t, 'c': c, 'c0': None, 'chg': 0})
    return rows, False


def _sample_label(lang, window, sample):
    posts = sample.get('posts') if isinstance(sample, dict) else None
    accounts = sample.get('accounts') if isinstance(sample, dict) else None
    if posts is None and accounts is None:
        return window or ''
    posts = _as_int(posts) if posts is not None else None
    accounts = _as_int(accounts) if accounts is not None else None
    if posts is None or accounts is None:
        bits = [window] if window else []
        if posts is not None:
            bits.append(str(posts))
        if accounts is not None:
            bits.append(str(accounts))
        return ' · '.join(bits)
    text = T3_COPY[lang]['sample'].format(w=window or '', posts=posts, accounts=accounts)
    return text.strip(' ·')


def _fact_lines(lang, calc):
    L = T3_COPY[lang]
    # The zh page uses a fullwidth colon. en and ko use ": ".
    sep = '：' if lang == 'zh' else ': '
    lines = []
    tickers = []
    shift = calc.get('shift')
    if shift:
        tickers.append(shift['t'])
        if shift['kind'] == 'delta':
            rest = L['delta'].format(frm=_pct(shift['from']), to=_pct(shift['to']))
        else:
            rest = L['chg'].format(n=shift['n'])
        lines.append(f"{L['shift']}{sep}${shift['t']} {rest}")
    most = calc.get('most')
    if most:
        tickers.append(most['t'])
        rest = L['most_rest'].format(n=most['n'], a=most['accs'])
        lines.append(f"{L['most']}{sep}${most['t']} {rest}")
    split = calc.get('split')
    if split:
        tickers.append(split['t'])
        rest = L['split_rest'].format(b=split['b'], e=split['e'])
        lines.append(f"{L['split']}{sep}${split['t']} {rest}")
    return lines, tickers


def _close_bits(lang, tickers):
    S = _s()
    disc = S.SHORT[lang]['disc']
    tag = ' '.join([S._primary_tag(lang), *S._hash_tags(tickers)])
    return disc, tag


def _fit_x(title, label, facts, disc, tag):
    """X body ≤ 280. The window/sample label and the disclaimer stay when they fit."""
    S = _s()

    def pack(use_title, use_facts, use_tag):
        bits = [use_title, label, *use_facts, disc, use_tag]
        return '\n\n'.join(b for b in bits if b)

    short_tag = tag.split()[0] if tag else ''
    text = pack(title, facts, tag)
    if S.xlen(text) <= 280:
        return text
    text = pack('', facts, short_tag)
    if S.xlen(text) <= 280:
        return text
    use = list(facts)
    while use and S.xlen(pack('', use, short_tag)) > 280:
        use.pop()
    text = pack('', use, short_tag)
    if S.xlen(text) <= 280:
        return text
    core = pack('', [], '')
    if S.xlen(core) <= 280:
        return core
    return S._trim_x(core)


def _maybe_x_link(text, url, take):
    """Put the link in the X body only when it still fits in 280."""
    S = _s()
    if not take or not url:
        return text, None
    trial = text + '\n' + url
    if S.xlen(trial) <= 280:
        return trial, url
    return text, url


def _platform_entry(text, url):
    return {'text': text, 'url': url}


def build_three_lines(daily, day, generated_at=None, dash=None, window_fallback=None):
    """Homepage 'today in 3 lines' as x/threads/facebook/instagram in zh, en and ko.

    Dash posts use the page's window, dist and threeLines. Without posts, the
    bull/bear/split rows in writeup daily are the inputs (no invented shift).
    """
    S = _s()
    day = S._as_day(day) or str(day or '')
    daily = daily if isinstance(daily, dict) else {}
    site = site_rows(dash, day) if dash else None
    if site:
        rows, has_prev, sample, window = site
        source = 'homepage dash-data (same window and threeLines as the daily tab)'
    else:
        rows, has_prev = rows_from_writeup(daily)
        sample = {}
        if S._is_num(daily.get('posts')):
            sample['posts'] = _as_int(daily['posts'])
        if S._is_num(daily.get('accounts')):
            sample['accounts'] = _as_int(daily['accounts'])
        window = S.top5_window(daily, window_fallback)
        source = 'data/writeup-input.json daily'
    if not rows and not sample and not window:
        return None
    calc = three_lines_calc(rows, has_prev)
    if generated_at is None:
        generated_at = datetime.now(HK).isoformat(timespec='minutes')
    texts = {}
    tickers = []
    for lang in S.LANGS:
        facts, ticks = _fact_lines(lang, calc)
        tickers = ticks or tickers
        label = _sample_label(lang, window, sample)
        title = T3_COPY[lang]['title']
        if not facts:
            facts = [T3_COPY[lang]['empty']]
        disc, tag = _close_bits(lang, ticks)
        body = '\n\n'.join(b for b in [title, label, *facts, disc, tag] if b)
        threads = S.fit_threads(body, lang)
        x = _fit_x(title, label, facts, disc, tag)
        ig = S.sanitize_instagram('\n\n'.join(b for b in [
            title, label, *facts, disc, '', S.ig_tags(lang, ticks),
        ] if b is not None), lang)
        texts[lang] = {'threads': threads, 'x': x, 'facebook': body, 'instagram': ig, 'ticks': ticks}
    # Half of x and threads, alternating by language so each platform gets some.
    # Facebook carries a link. Instagram never does.
    has_link = {p: {} for p in ('x', 'threads', 'facebook', 'instagram')}
    out_p = {p: {} for p in ('x', 'threads', 'facebook', 'instagram')}
    for i, lang in enumerate(S.LANGS):
        urls = {plat: S._camp_url(lang, plat, 'three_lines') for plat in ('x', 'threads', 'facebook')}
        x_take = (i % 2 == 0)
        th_take = (i % 2 == 1)
        x_text, x_url = _maybe_x_link(texts[lang]['x'], urls['x'] if x_take else None, x_take)
        if S.xlen(x_text) > 280:
            x_text = texts[lang]['x']
            x_url = urls['x'] if x_take else None
        has_link['x'][lang] = bool(x_url)
        out_p['x'][lang] = _platform_entry(S.strip_dup_handles(x_text), x_url)
        has_link['threads'][lang] = th_take
        out_p['threads'][lang] = _platform_entry(
            S.strip_dup_handles(texts[lang]['threads']), urls['threads'] if th_take else None)
        # Facebook may carry the link in the body. Threads stays URL-free; the link is `url`.
        fb = S.strip_dup_handles(texts[lang]['facebook'] + '\n\n' + urls['facebook'])
        has_link['facebook'][lang] = True
        out_p['facebook'][lang] = _platform_entry(fb, urls['facebook'])
        has_link['instagram'][lang] = False
        out_p['instagram'][lang] = {'text': texts[lang]['instagram']}
    return {
        'date': day,
        'generated_at': generated_at,
        'window': window,
        'sample': sample,
        'suggested_kst': THREE_LINES_KST,
        'format': 'text_question',
        'source': source,
        'x': out_p['x'],
        'threads': out_p['threads'],
        'facebook': out_p['facebook'],
        'instagram': out_p['instagram'],
        'has_link': has_link,
    }


def _clean_reason(acc, why, ticker):
    S = _s()
    text = _URL_RE.sub('', why or '')
    text = S.dedupe_handle(acc, text)
    text = clause_for(text, ticker)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _reasons(row, ticker, default_side=None):
    bull, bear = [], []
    seen = set()
    for item in (row or {}).get('rows') or []:
        if not isinstance(item, dict):
            continue
        acc = str(item.get('acc') or '').strip().lstrip('@')
        side = item.get('s') or default_side
        if side not in ('bull', 'bear') or not acc:
            continue
        text = _clean_reason(acc, item.get('why') or '', ticker)
        text = _s().strip_dup_handles(text)
        if not text:
            continue
        key = (side, acc.lower(), text)
        if key in seen:
            continue
        seen.add(key)
        (bull if side == 'bull' else bear).append({'acc': acc, 'text': text})
    return bull, bear


def hot_names(daily, limit=5):
    """Hottest names across bull, bear and split, ordered like rank_rows.

    Bull uses nb, bear uses nr, split uses the stronger of nb and nr. Then
    n_posts descending, then ticker ascending. At most `limit` names.
    """
    S = _s()
    picked = {}

    def consider(row, side_list):
        t = S._ticker_sym((row or {}).get('t'))
        if not t or not isinstance(row, dict):
            return
        nb = _num(row.get('nb'))
        nr = _num(row.get('nr'))
        nps = row.get('n_posts') if S._is_num(row.get('n_posts')) else 0
        if side_list == 'bull':
            if nb is None:
                return
            score, side = nb, 'bull'
        elif side_list == 'bear':
            if nr is None:
                return
            score, side = nr, 'bear'
        else:
            if nb is None and nr is None:
                return
            score, side = max(nb or 0, nr or 0), 'split'
        cand = (score, nps, t, row, side, nb, nr)
        prev = picked.get(t)
        if prev is None or (score, nps) > (prev[0], prev[1]):
            picked[t] = cand
        elif (score, nps) == (prev[0], prev[1]) and side == 'split' and prev[4] != 'split':
            picked[t] = cand

    for row in rank_rows((daily or {}).get('bull'), 'bull'):
        consider(row, 'bull')
    for row in rank_rows((daily or {}).get('bear'), 'bear'):
        consider(row, 'bear')
    seen_split = set()
    for side in ('bull', 'bear'):
        for row in rank_rows((daily or {}).get('split'), side):
            t = S._ticker_sym(row.get('t'))
            if not t or t in seen_split:
                continue
            seen_split.add(t)
            consider(row, 'split')
    ordered = sorted(picked.values(), key=lambda x: (-x[0], -x[1], x[2]))
    return ordered[:limit]


def _attr(lang, acc, text):
    handle = '@' + str(acc).lstrip('@')
    if lang == 'zh':
        return f'{handle}：{text}'
    return f'{handle}: {text}'


def _why_body(lang, ticker, nb, nr, accounts, label, bull_reasons, bear_reasons):
    S = _s()
    L = T3_COPY[lang]
    parts = [WHY_TITLE[lang].format(t=f'${ticker}'), label]
    bits = []
    if accounts is not None:
        bits.append(L['acc'].format(n=_as_int(accounts)))
    if nb is not None:
        bits.append(S._count_phrase(lang, 'bull', nb))
    if nr is not None:
        bits.append(S._count_phrase(lang, 'bear', nr))
    if bits:
        parts.append(' · '.join(str(b) for b in bits))
    def dump(head, reasons):
        if not reasons:
            return
        lines = [_attr(lang, r['acc'], r['text']) for r in reasons]
        parts.append(head + '\n' + '\n'.join(lines))
    dump(L['bull_h'], bull_reasons)
    dump(L['bear_h'], bear_reasons)
    disc, tag = _close_bits(lang, [ticker])
    parts.extend([disc, tag])
    body = '\n\n'.join(p for p in parts if p)
    body = S.strip_dup_handles(body)
    return S.fit_threads(body, lang), disc


def _account_total(nb, nr):
    if nb is None and nr is None:
        return None
    return _as_int((nb or 0) + (nr or 0))


def build_why_posts(daily, day, window=None, sample=None, generated_at=None, window_fallback=None):
    """One Threads-first post per hot name, at most 5. Reasons are real whys only."""
    S = _s()
    day = S._as_day(day) or str(day or '')
    daily = daily if isinstance(daily, dict) else {}
    if window is None:
        window = S.top5_window(daily, window_fallback)
    if sample is None:
        sample = {}
        if S._is_num(daily.get('posts')):
            sample['posts'] = _as_int(daily['posts'])
        if S._is_num(daily.get('accounts')):
            sample['accounts'] = _as_int(daily['accounts'])
    posts = []
    link_i = 0
    for _score, _nps, ticker, row, source_side, nb, nr in hot_names(daily, 5):
        if (nb or 0) > 0 and (nr or 0) > 0:
            side = 'split'
        elif nb is not None and (nr is None or (nb or 0) >= (nr or 0)):
            side = 'bull'
        else:
            side = 'bear'
        # A split row with no per-account side is not guessed. Bull/bear lists default to that side.
        default = None if source_side == 'split' else source_side
        bull_r, bear_r = _reasons(row, ticker, default)
        if not bull_r and not bear_r:
            continue
        accounts = _account_total(nb, nr)
        item = {
            'ticker': ticker,
            'side': side,
            'accounts': accounts,
            'window': window or '',
            'sample': sample,
            'format': 'carousel',
            'date': day,
        }
        if nb is not None:
            item['bull'] = _as_int(nb)
        if nr is not None:
            item['bear'] = _as_int(nr)
        if bull_r:
            item['bull_reasons'] = bull_r
        if bear_r:
            item['bear_reasons'] = bear_r
        threads = {}
        has_threads = {}
        for lang in S.LANGS:
            label = _sample_label(lang, window, sample)
            text, _disc = _why_body(lang, ticker, nb, nr, accounts, label, bull_r, bear_r)
            take = (link_i % 2 == 0)
            link_i += 1
            url = S._camp_url(lang, 'threads', 'why', ticker) if take else None
            threads[lang] = _platform_entry(text, url)
            has_threads[lang] = take
        item['threads'] = threads
        item['has_link'] = {'threads': has_threads}
        # English X only when the whole post fits in 280. Its link alternates by name
        # and does not shift the Threads half (Threads already walks zh, en, ko).
        en_label = _sample_label('en', window, sample)
        en_text, _disc = _why_body('en', ticker, nb, nr, accounts, en_label, bull_r, bear_r)
        if S.xlen(en_text) <= 280 and S.SHORT['en']['disc'] in en_text:
            x_take = (len(posts) % 2 == 0)
            x_url = S._camp_url('en', 'x', 'why', ticker) if x_take else None
            x_text, x_url = _maybe_x_link(en_text, x_url, x_take)
            if S.xlen(x_text) > 280:
                x_text, x_url = en_text, x_url
            item['x'] = {'en': _platform_entry(S.strip_dup_handles(x_text), x_url)}
            item['has_link']['x'] = {'en': bool(x_url)}
        posts.append(item)
    return posts


def schedule_why_atomic(why_posts, atomic):
    """Why posts take the earliest KST slots. Atomic keeps the slots that remain.

    Same ticker is not given two slots. Total stays inside the six daily times.
    """
    S = _s()
    why_posts = [p for p in (why_posts or []) if isinstance(p, dict)]
    for i, post in enumerate(why_posts):
        if i < len(S.ATOMIC_TIMES):
            post['suggested_kst'] = S.ATOMIC_TIMES[i]
    why_tickers = {p.get('ticker') for p in why_posts if p.get('ticker')}
    atomic = [a for a in (atomic or []) if isinstance(a, dict) and a.get('ticker') not in why_tickers]
    if not atomic:
        return why_posts, []
    used = {p.get('suggested_kst') for p in why_posts}
    free = [t for t in S.ATOMIC_TIMES if t not in used]
    order = []
    for item in atomic:
        slot = item.get('slot_kst')
        if slot not in order:
            order.append(slot)
    order = order[:len(free)]
    keep = set(order)
    atomic = [a for a in atomic if a.get('slot_kst') in keep]
    mapping = {old: free[i] for i, old in enumerate(order)}
    for item in atomic:
        item['slot_kst'] = mapping[item['slot_kst']]
    return why_posts, atomic


def prior_texts(history, day):
    """Normalized bodies from earlier days, so today's rebuild can skip a repeat."""
    S = _s()
    day = S._as_day(day)
    out = set()
    for key, rec in (history or {}).items():
        if not isinstance(rec, dict) or S._as_day(key) == day:
            continue
        for field in ('why_text', 'three_lines_text'):
            for text in rec.get(field) or []:
                if isinstance(text, str) and text:
                    out.add(text)
    return out


def collect_texts(node):
    """Post bodies (the `text` fields), not link URLs."""
    out = []
    if isinstance(node, dict):
        if isinstance(node.get('text'), str):
            out.append(node['text'])
        for key, value in node.items():
            if key == 'text':
                continue
            if isinstance(value, (dict, list)):
                out.extend(collect_texts(value))
    elif isinstance(node, list):
        for value in node:
            if isinstance(value, (dict, list)):
                out.extend(collect_texts(value))
    return out


def drop_repeated(posts, banned):
    """Drop a why post when any language body was already used on an earlier day."""
    S = _s()
    kept = []
    for post in posts or []:
        texts = [S._norm_text(t) for t in collect_texts(post.get('threads'))]
        if any(t and t in banned for t in texts):
            continue
        kept.append(post)
    return kept
