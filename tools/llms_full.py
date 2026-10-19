"""Write llms-full.txt from the real dash-data in index.html.

Run after the homepage data is restored and before the pages are slimmed:
  python3 tools/llms_full.py

Numbers come from the same rules as the page (consGroups, dailyWindow, stats.js top):
confirmed US stocks, latest stance per account inside the window, joint bullish only
when at least two accounts are bullish and none are bearish. Nothing here is invented.
"""
import html
import os
import re
from datetime import datetime, timedelta, timezone

from sitedata import load, notice
from slim_pages import combine, is_slim

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HK = timezone(timedelta(hours=8))
DAY = 86400000
S_OF = {'睇好': 'bull', '睇淡': 'bear', '中性': 'neu'}
US_EX = re.compile(r'^(NYSE|NASDAQ|AMEX|NYSEARCA|US)$', re.I)
OUT = os.path.join(ROOT, 'llms-full.txt')


def parse_ms(s):
    """Milliseconds since epoch, matching Date.parse for ISO strings. None if it would be NaN."""
    if s is None:
        return None
    text = str(s).strip().replace('Z', '+00:00')
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=HK)
    return int(round(dt.timestamp() * 1000))


def hk_date(ms):
    return datetime.fromtimestamp(ms / 1000, HK).strftime('%Y-%m-%d')


def hk_hm(ms):
    return datetime.fromtimestamp(ms / 1000, HK).strftime('%H:%M')


def ts_of(ms):
    return hk_date(ms) + 'T' + hk_hm(ms)


def add_days(day, n):
    base = datetime.fromisoformat(day)
    return (base + timedelta(days=n)).date().isoformat()


def plain(s):
    if not s:
        return ''
    text = re.sub(r'<[^>]+>', ' ', str(s))
    text = html.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def norm_ticker(t):
    t = str(t)
    if t.startswith('$'):
        t = t[1:]
    return t.upper()


def stance_of(p, t):
    """Per-ticker stance. An empty stance_by_ticker object does not fall back to the whole post."""
    m = p.get('stance_by_ticker')
    if not isinstance(m, dict):
        whole = p.get('stance')
        if whole in S_OF:
            return S_OF[whole], True
        return 'none', False
    for key, val in m.items():
        if norm_ticker(key) == t:
            return S_OF.get(val, 'none'), False
    return 'none', False


def raw_posts(d):
    """One row per post, including posts the page keeps out of consensus, for the window fallback."""
    rows = []
    for p in d.get('posts') or []:
        hkt = p.get('time_hkt') or ''
        if len(hkt) < 10:
            continue
        rows.append({
            'ms': parse_ms(p.get('time_utc')),
            'd': hkt[:10],
            'valid': not p.get('folded_into') and p.get('theme') != '非市場',
        })
    return rows


def expand(d):
    posts = []
    for p in d.get('posts') or []:
        if p.get('folded_into') or p.get('theme') == '非市場':
            continue
        ms = parse_ms(p.get('time_utc'))
        hkt = p.get('time_hkt') or ''
        if ms is None or len(hkt) < 10:
            continue
        tickers = []
        seen = set()
        for t in p.get('tickers') or []:
            if t not in seen:
                seen.add(t)
                tickers.append(t)
        sb = p.get('stance_by_ticker')
        if isinstance(sb, dict):
            for key in sb:
                t = norm_ticker(key)
                if t not in seen:
                    seen.add(t)
                    tickers.append(t)
        acc = p.get('reposted_by') or p.get('handle')
        for t in tickers:
            s, _star = stance_of(p, t)
            posts.append({'acc': acc, 't': t, 's': s, 'ms': ms, 'd': hkt[:10], 'url': p.get('url') or ''})
    posts.sort(key=lambda x: x['ms'])
    return posts


def in_range(row, frm, to):
    if len(frm) > 10:
        if row.get('ms') is None:
            return False
        a = parse_ms(frm + ':00+08:00')
        b = parse_ms(to + ':00+08:00')
        if a is None or b is None:
            return False
        return row['ms'] >= a and row['ms'] <= b + 59999
    return frm <= row['d'] <= to


def is_us(t, ov):
    o = ov.get(t)
    if not o:
        return True
    ex = o.get('exchange')
    sym = o.get('symbol') or ''
    bad_ex = bool(ex) and not US_EX.match(str(ex))
    dotted = bool(sym) and '.' in str(sym)
    return not (bad_ex or dotted)


def no_cons(d):
    cats = [c.get('name') for c in ((d.get('tracked') or {}).get('categories') or []) if c.get('consensus') is False]
    out = set()
    for a in (d.get('tracked') or {}).get('accounts') or []:
        if a.get('category') in cats and a.get('handle'):
            out.add(str(a['handle']).lower())
    return out


def window_of(d, raw):
    meta = d.get('meta') or {}
    cut = parse_ms(meta.get('cutoff_hkt')) if meta.get('cutoff_hkt') else None
    if cut is None:
        times = [x['ms'] for x in raw if x['ms'] is not None]
        cut = max(times) if times else 0
    today = hk_date(cut)
    summaries = (d.get('summaries') or {}).get('daily') or []
    today_rows = [x for x in summaries if x.get('date') == today]
    if today_rows:
        win = (today_rows[-1].get('win') or {})
        if win.get('from') and win.get('to'):
            return {'from': win['from'], 'to': win['to'], 'today': today, 'src': 'writer'}
    valid = [x for x in raw if x['valid']]
    slots = meta.get('scrape_slots_hkt') or []
    raw_cut = meta.get('cutoff_hkt') or ''
    scrape = parse_ms(str(raw_cut).replace(' ', 'T') + ':00+08:00') if raw_cut else None
    if slots and scrape:
        cands = []
        for k in (0, 1):
            day = add_days(hk_date(scrape), -k)
            for sl in slots:
                t = parse_ms(day + 'T' + sl + ':00+08:00')
                if t is not None and t <= scrape:
                    cands.append(t)
        last = max(cands) if cands else scrape
        frm, to = ts_of(last - DAY), ts_of(scrape)
        n = sum(1 for x in valid if in_range(x, frm, to))
        if n:
            return {'from': frm, 'to': to, 'today': today, 'src': 'cycle'}
    min_posts = meta.get('min_daily_posts') or 8
    n_today = sum(1 for x in valid if x['d'] == today)
    has_prev = any(x['d'] < today for x in raw)
    if n_today < min_posts and has_prev:
        return {'from': add_days(today, -1), 'to': today, 'today': today, 'src': 'days'}
    return {'from': today, 'to': today, 'today': today, 'src': 'days'}


def cons_groups(posts, frm, to, ov, skip):
    inside = [x for x in posts if in_range(x, frm, to)]
    tickers = sorted({x['t'] for x in inside})
    out = {'bull': [], 'bear': []}
    for t in tickers:
        if (ov.get(t) or {}).get('unconfirmed') or not is_us(t, ov):
            continue
        latest = {}
        urls = set()
        for x in inside:
            if x['t'] != t:
                continue
            urls.add(x['url'])
            if str(x['acc']).lower() in skip:
                continue
            prev = latest.get(x['acc'])
            if prev is None or x['ms'] >= prev['ms']:
                latest[x['acc']] = x
        if not latest:
            continue
        rows = list(latest.values())
        nb = sum(1 for x in rows if x['s'] == 'bull')
        nr = sum(1 for x in rows if x['s'] == 'bear')
        if nb and nr:
            continue
        kind = 'bull' if nb >= 2 else 'bear' if nr >= 2 else None
        if not kind:
            continue
        out[kind].append({'t': t, 'nb': nb, 'nr': nr, 'n_posts': len(urls)})
    for k in out:
        out[k].sort(key=lambda g: (-(g['nb'] + g['nr']), -g['n_posts'], g['t']))
    return out


def most_discussed(posts, frm, to, limit=10):
    cnt = {}
    for x in posts:
        if not in_range(x, frm, to):
            continue
        c = cnt.setdefault(x['t'], {'t': x['t'], 'n': 0, 'accs': set()})
        c['n'] += 1
        c['accs'].add(x['acc'])
    rows = sorted(cnt.values(), key=lambda c: (-len(c['accs']), -c['n'], c['t']))
    return [(c['t'], len(c['accs']), c['n']) for c in rows[:limit]]


def platforms(d):
    counts = {}
    for a in (d.get('tracked') or {}).get('accounts') or []:
        p = (a.get('platform') or 'x').lower()
        if p in ('x', 'twitter'):
            name = 'X'
        elif p == 'truthsocial':
            name = 'Truth Social'
        else:
            name = p
        counts[name] = counts.get(name, 0) + 1
    return counts


def english_daily(d, today):
    daily = ((d.get('summaries_en') or {}).get('daily') or []) if isinstance(d.get('summaries_en'), dict) else []
    if daily:
        chosen = [x for x in daily if x.get('date') == today] or [daily[-1]]
        item = chosen[-1]
        for key in ('brief', 'html', 'full'):
            text = plain(item.get(key))
            if text:
                return item.get('date') or '', 'summaries_en.daily.' + key, text
    briefs = d.get('briefings_en') if isinstance(d.get('briefings_en'), list) else []
    if briefs:
        chosen = [x for x in briefs if x.get('date') == today] or [briefs[-1]]
        item = chosen[-1]
        text = plain(item.get('html') or item.get('brief') or item.get('full'))
        if text:
            return item.get('date') or '', 'briefings_en.html', text
    return None, None, None


def lines_for(groups):
    if not groups:
        return ['- none']
    return [f"- {g['t']}: {g['nb']} bullish, {g['nr']} bearish" for g in groups]


def main():
    os.chdir(ROOT)
    d = load('index.html')
    if is_slim(d):
        d = combine(d)
    meta = d.get('meta') or {}
    accounts = (d.get('tracked') or {}).get('accounts') or []
    posts = expand(d)
    win = window_of(d, raw_posts(d))
    ov = d.get('overrides') or {}
    groups = cons_groups(posts, win['from'], win['to'], ov, no_cons(d))
    top = most_discussed(posts, win['from'], win['to'])
    date, field, text = english_daily(d, win['today'])
    plat = platforms(d)
    body = [
        '# The Crowd Tape',
        '',
        f"Generated (HKT): {meta.get('generated_hkt') or ''}",
        f"Data cutoff: {meta.get('cutoff_hkt') or ''}",
        f"Tracked accounts: {len(accounts)}",
    ]
    for name in sorted(plat, key=lambda n: (-plat[n], n)):
        body.append(f'- {name}: {plat[name]}')
    body += [
        '',
        f"Window: {win['from']} to {win['to']} HKT",
        f"Window source: {win['src']}",
        '',
        '## Joint bullish',
        'Confirmed US stocks where at least 2 tracked accounts have a latest stance of bullish in this window and none are bearish.',
    ]
    body += lines_for(groups['bull'])
    body += [
        '',
        '## Joint bearish',
        'Confirmed US stocks where at least 2 tracked accounts have a latest stance of bearish in this window and none are bullish.',
    ]
    body += lines_for(groups['bear'])
    body += [
        '',
        '## Most discussed',
        'Tickers in this window, ranked by unique accounts and then by mentions.',
    ]
    if top:
        body += [f'- {t}: {n} accounts, {m} mentions' for t, n, m in top]
    else:
        body.append('- none')
    body += ['', '## Latest English daily summary']
    if text:
        body += [f'Date: {date}', f'Field: {field}', text]
    else:
        body.append('not available')
    body += [
        '',
        '## Disclaimer',
        'Not investment advice. The content summarises public posts by third parties and is for information only.',
        '',
    ]
    open(OUT, 'w', encoding='utf-8').write('\n'.join(body))
    bulls = ', '.join(g['t'] for g in groups['bull']) or 'none'
    bears = ', '.join(g['t'] for g in groups['bear']) or 'none'
    notice(f'llms-full.txt：追蹤 {len(accounts)} 個帳號，共同看多 {bulls}，共同看空 {bears}')


if __name__ == '__main__':
    main()
