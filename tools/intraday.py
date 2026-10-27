"""Intraday social slots for data/social-posts.json.

US/Eastern post times: open 09:45, 1 11:00, 2 12:15, 3 13:30, 4 14:45, close 15:40.
Generation is 5 minutes before each post: 09:40, 10:55, 12:10, 13:25, 14:40, 15:35 ET.
HKT is ET+12 in summer (EDT) and ET+13 in winter (EST, from the first Sunday in November).
One English X post per slot; Threads in zh/en. No Facebook.

python3 tools/intraday.py --slot <name|auto|force>
python3 tools/intraday.py --merge-from <file>
"""
import argparse
import os
import re
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import date_kst
from ranking import rank_rows
from sitedata import read_json, work, write_json
from utm import normalize_file, tag_url
import share

NY = ZoneInfo('America/New_York')
HK = ZoneInfo('Asia/Hong_Kong')
INDEXES = ('SPY', 'QQQ', 'DIA')
SLOT_DEFS = (
    ('intraday_open', 9, 45),
    ('intraday_1', 11, 0),
    ('intraday_2', 12, 15),
    ('intraday_3', 13, 30),
    ('intraday_4', 14, 45),
    ('intraday_close', 15, 40),
)
SLOT_NAMES = tuple(name for name, _h, _m in SLOT_DEFS)
SLOT_HM = {name: (h, m) for name, h, m in SLOT_DEFS}
# 09:40, 10:55, 12:10, 13:25, 14:40, 15:35 ET. auto matches the nearest of these.
GEN_LEAD_MIN = 5
GUARD_WINDOW_MIN = 20
AUTO_AHEAD_MIN = 30
AUTO_BEHIND_MIN = 20
EARLY_CLOSE_AFTER = (13, 0)
HOLIDAYS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'market_holidays.json')
PCT_RE = re.compile(r'[+\-]?\d+(?:\.\d+)?%')
URL_RE = re.compile(r'https?://\S+', re.I)

HEAD = {
    'intraday_open': {
        'en': ('US open', 'Open tape', 'At the open'),
        'zh': ('美股開市', '開市快報', '開市時點'),
    },
    'intraday_1': {
        'en': ('Late morning', 'Morning tape', 'Late-morning check'),
        'zh': ('早盤觀察', '早盤快報', '午前觀察'),
    },
    'intraday_2': {
        'en': ('Midday', 'Lunch-hour tape', 'Midday check'),
        'zh': ('午市觀察', '午市快報', '午間觀察'),
    },
    'intraday_3': {
        'en': ('Early afternoon', 'Afternoon check', 'Post-lunch tape'),
        'zh': ('午后觀察', '午后快報', '午後時點'),
    },
    'intraday_4': {
        'en': ('Afternoon tape', 'Late-day check', 'Toward the close'),
        'zh': ('尾盤前', '尾盤觀察', '收市前快報'),
    },
    'intraday_close': {
        'en': ('Into the close', 'Before the bell', 'Close recap'),
        'zh': ('收市前回顧', '收市前快報', '尾盤回顧'),
    },
}


def posts_path():
    return os.environ.get('SOCIAL_POSTS') or 'data/social-posts.json'


def writeup_path():
    return os.environ.get('WRITEUP_INPUT') or 'data/writeup-input.json'


def consensus_path():
    return os.environ.get('CONSENSUS_HISTORY') or 'data/consensus-history.json'


def holidays_path():
    return os.environ.get('MARKET_HOLIDAYS') or HOLIDAYS_PATH


def load_holidays(path=None):
    data = read_json(path or holidays_path(), {}) or {}
    closures = {str(x) for x in (data.get('closures') or [])}
    early = {str(x) for x in (data.get('early_close') or [])}
    return closures, early


def as_day(value):
    return share._as_day(value)


def ticker_sym(value):
    return share._ticker_sym(value)


def is_num(value):
    return share._is_num(value)


def as_int(value):
    return share._as_int(value)


def now_et(now=None):
    if now is None:
        return datetime.now(NY)
    if now.tzinfo is None:
        return now.replace(tzinfo=NY)
    return now.astimezone(NY)


def et_date(now=None):
    return now_et(now).date().isoformat()


def post_dt(date, hour, minute):
    day = as_day(date)
    y, m, d = (int(p) for p in day.split('-'))
    return datetime(y, m, d, hour, minute, tzinfo=NY)


def gen_dt(date, hour, minute):
    return post_dt(date, hour, minute) - timedelta(minutes=GEN_LEAD_MIN)


def hkt_hhmm(dt):
    return dt.astimezone(HK).strftime('%H:%M')


def iso_offset(dt):
    return dt.isoformat(timespec='seconds')


def hkt_stamp(dt):
    return dt.astimezone(HK).strftime('%Y-%m-%d %H:%M')


def is_weekend(date):
    day = as_day(date)
    return bool(day) and datetime.strptime(day, '%Y-%m-%d').weekday() >= 5


def is_trading_day(date, holidays=None):
    day = as_day(date)
    if not day or is_weekend(day):
        return False
    closures, _early = holidays if holidays is not None else load_holidays()
    return day not in closures


def is_early_close(date, holidays=None):
    day = as_day(date)
    _closures, early = holidays if holidays is not None else load_holidays()
    return day in early


def slot_after_early_close(name):
    hour, minute = SLOT_HM[name]
    return (hour, minute) > EARLY_CLOSE_AFTER


def slot_permitted(date, name, holidays=None):
    if name not in SLOT_HM:
        return False
    if not is_trading_day(date, holidays):
        return False
    if is_early_close(date, holidays) and slot_after_early_close(name):
        return False
    return True


def generation_times(date, holidays=None):
    out = []
    for name, hour, minute in SLOT_DEFS:
        if slot_permitted(date, name, holidays):
            out.append((name, gen_dt(date, hour, minute)))
    return out


def within_minutes(delta_min, window):
    return abs(delta_min) <= window


def pick_auto_slot(now, holidays=None, force=False):
    """Next post within 30 min, or the previous one within 20. Used by `force`.

    `--slot auto` does not use this. It uses near_generation so a dispatch a few
    minutes early or late still lands on the slot being generated.
    `force` ignores the trading-day filter and, if nothing is close, returns the
    next remaining slot today, or the last one.
    """
    now = now_et(now)
    date = now.date().isoformat()
    holidays = holidays if holidays is not None else load_holidays()
    future, past = [], []
    for name, hour, minute in SLOT_DEFS:
        if not force and not slot_permitted(date, name, holidays):
            continue
        post = post_dt(date, hour, minute)
        delta = (post - now).total_seconds() / 60.0
        if 0 <= delta <= AUTO_AHEAD_MIN:
            future.append((delta, name))
        elif -AUTO_BEHIND_MIN <= delta < 0:
            past.append((delta, name))
    if future:
        return min(future)[1]
    if past:
        return max(past)[1]
    if not force:
        return None
    for name, hour, minute in SLOT_DEFS:
        if force or slot_permitted(date, name, holidays):
            if post_dt(date, hour, minute) >= now:
                return name
    for name, hour, minute in reversed(SLOT_DEFS):
        if force or slot_permitted(date, name, holidays):
            return name
    return SLOT_NAMES[-1]


def near_generation(now, holidays=None):
    """Slot whose generation time is nearest, when that distance is within ±20 min.

    Generation times are 55–75 minutes apart, so the ±20 windows do not overlap.
    A dispatch 10 minutes early or late still resolves to that one slot.
    """
    now = now_et(now)
    date = now.date().isoformat()
    best = None
    best_abs = None
    for name, when in generation_times(date, holidays):
        delta = abs((now - when).total_seconds()) / 60.0
        if delta <= GUARD_WINDOW_MIN and (best_abs is None or delta < best_abs):
            best, best_abs = name, delta
    return best


def evaluate_guard(now, slot='auto', force=False, holidays=None):
    """Return (ok, resolved_slot, reason).

    `auto` is the permitted slot whose ET generation time is nearest within
    ±GUARD_WINDOW_MIN. Weekends, NYSE holidays, and early-close slots after
    13:00 ET are not generation times, so they do not match. A named slot skips
    the clock (the workflow resolves auto in Guard, then writes that name after
    the fetch) and still rejects a closed or early-close day. `force` bypasses
    both checks.
    """
    now = now_et(now)
    date = now.date().isoformat()
    holidays = holidays if holidays is not None else load_holidays()
    raw = (slot or 'auto').strip().lower()
    if raw == 'force':
        force = True
        raw = 'auto'
    if raw not in ('auto', *SLOT_NAMES):
        return False, None, f'unknown slot {slot}'
    if not force and not is_trading_day(date, holidays):
        return False, None, f'{date} is not a NYSE trading day'
    if raw == 'auto':
        if force:
            picked = pick_auto_slot(now, holidays, force=True)
            if not picked:
                return False, None, f'no slot within {AUTO_AHEAD_MIN} min of {now.strftime("%H:%M")} ET'
            return True, picked, f'ok {picked}'
        picked = near_generation(now, holidays)
        if not picked:
            return False, None, f'{now.strftime("%H:%M")} ET is not within {GUARD_WINDOW_MIN} min of a generation time'
        return True, picked, f'ok {picked}'
    if not force and not slot_permitted(date, raw, holidays):
        if is_early_close(date, holidays) and slot_after_early_close(raw):
            return False, None, f'{raw} skipped on early-close {date}'
        return False, None, f'{raw} not permitted on {date}'
    return True, raw, f'ok {raw}'


def threads_take_link(date, slot):
    """About half of Threads copies include a link: alternate by slot index, flip by date parity."""
    idx = SLOT_NAMES.index(slot)
    day = datetime.strptime(as_day(date), '%Y-%m-%d')
    return ((idx + day.toordinal()) % 2) == 0


def home_url(lang, platform, campaign):
    return tag_url(share.page_url(lang), platform, campaign)


def fmt_pct(value):
    n = float(value)
    return f'{n:+.1f}%'


def format_quote_time(ts):
    if ts is None:
        return None
    dt = datetime.fromtimestamp(int(ts), NY)
    return {'et': iso_offset(dt), 'hkt': hkt_stamp(dt)}


def yahoo_chart(sym):
    from update_prices import chart
    return chart(sym, '1d', '5m')


def fetch_live_quotes(tickers, chart_fn=None, sleep=0.3):
    """Yahoo chart API via update_prices.chart. Missing tickers are omitted, never guessed."""
    chart_fn = chart_fn or yahoo_chart
    out = {}
    latest_ts = None
    for raw in tickers:
        t = ticker_sym(raw)
        if not t:
            continue
        try:
            result = chart_fn(t)
        except Exception:
            result = None
        meta = result[0] if isinstance(result, tuple) and result else result
        if not isinstance(meta, dict):
            continue
        price = meta.get('regularMarketPrice')
        prev = meta.get('previousClose') or meta.get('chartPreviousClose')
        ts = meta.get('regularMarketTime')
        if price is None:
            continue
        chg = None
        if prev not in (None, 0, 0.0):
            try:
                chg = round((float(price) / float(prev) - 1) * 100, 2)
            except (TypeError, ValueError, ZeroDivisionError):
                chg = None
        try:
            price_n = round(float(price), 4)
        except (TypeError, ValueError):
            continue
        try:
            prev_n = round(float(prev), 4) if prev is not None else None
        except (TypeError, ValueError):
            prev_n = None
        rec = {'price': price_n, 'prev_close': prev_n, 'chg_pct': chg, 'time': None}
        if ts is not None:
            rec['time'] = iso_offset(datetime.fromtimestamp(int(ts), NY))
            if latest_ts is None or int(ts) > latest_ts:
                latest_ts = int(ts)
        out[t] = rec
        if sleep:
            time.sleep(sleep)
    quote_time = format_quote_time(latest_ts) if latest_ts is not None else None
    ok = all(idx in out for idx in INDEXES)
    return out, quote_time, ok


def row_accounts(row, limit=8):
    out = []
    for item in (row or {}).get('rows') or []:
        if not isinstance(item, dict):
            continue
        acc = str(item.get('acc') or '').strip().lstrip('@')
        if acc and acc not in out:
            out.append(acc)
        if len(out) >= limit:
            break
    return out


def hot_from_row(row, quotes):
    t = ticker_sym((row or {}).get('t'))
    if not t:
        return None
    q = (quotes or {}).get(t) or {}
    chg = q.get('chg_pct') if isinstance(q.get('chg_pct'), (int, float)) else None
    bull = as_int(row['nb']) if is_num(row.get('nb')) else None
    bear = as_int(row['nr']) if is_num(row.get('nr')) else None
    return {
        'ticker': t,
        'chg_pct': chg,
        'bull': bull,
        'bear': bear,
        'accounts': row_accounts(row),
    }


def rows_by_ticker(daily):
    out = {}
    for side in ('bull', 'bear', 'split'):
        for row in (daily or {}).get(side) or []:
            if not isinstance(row, dict):
                continue
            t = ticker_sym(row.get('t'))
            if t and t not in out:
                out[t] = row
    return out


def ranked_tickers(daily, side):
    key = 'bull' if side == 'bull' else 'bear'
    return [ticker_sym(r.get('t')) for r in rank_rows((daily or {}).get(key) or [], key) if ticker_sym(r.get('t'))]


def previous_snapshot(history_days, date, existing_slots):
    for name in reversed(SLOT_NAMES):
        sl = (existing_slots or {}).get(name)
        if isinstance(sl, dict) and isinstance(sl.get('snapshot'), dict):
            snap = sl['snapshot']
            bull = [ticker_sym(t) for t in (snap.get('bull') or []) if ticker_sym(t)]
            bear = [ticker_sym(t) for t in (snap.get('bear') or []) if ticker_sym(t)]
            if bull or bear:
                return bull, bear
    days = (history_days or {}).get('days') if isinstance(history_days, dict) else history_days
    days = days if isinstance(days, dict) else {}
    start = datetime.strptime(as_day(date), '%Y-%m-%d')
    for i in range(0, 10):
        key = (start - timedelta(days=i)).strftime('%Y-%m-%d')
        rec = days.get(key)
        if not isinstance(rec, dict):
            continue
        bull = [ticker_sym(t) for t in (rec.get('bull') or []) if ticker_sym(t)]
        bear = [ticker_sym(t) for t in (rec.get('bear') or []) if ticker_sym(t)]
        if bull or bear:
            return bull, bear
    return [], []


def consensus_changes(curr_bull, curr_bear, prev_bull, prev_bear):
    pb, pr = set(prev_bull), set(prev_bear)
    cb, cr = set(curr_bull), set(curr_bear)
    return {
        'joined_bull': [t for t in curr_bull if t not in pb],
        'left_bull': [t for t in prev_bull if t not in cb],
        'joined_bear': [t for t in curr_bear if t not in pr],
        'left_bear': [t for t in prev_bear if t not in cr],
    }


def pick_hot(daily, quotes, slot, used, limit=4):
    """Hot names from real daily bull/bear/split rows. Angle varies by slot."""
    by = rows_by_ticker(daily)
    bulls = ranked_tickers(daily, 'bull')
    bears = ranked_tickers(daily, 'bear')
    split = [ticker_sym(r.get('t')) for r in rank_rows((daily or {}).get('split') or [], 'bull') if ticker_sym(r.get('t'))]
    if slot == 'intraday_open':
        order = bulls + [t for t in bears if t not in bulls]
    elif slot == 'intraday_1':
        order = bulls + split + bears
    elif slot == 'intraday_2':
        order = bears + split + bulls
    elif slot == 'intraday_3':
        order = split + bulls + bears
    elif slot == 'intraday_4':
        order = bulls[1:] + bears + split + bulls[:1]
    else:
        order = bulls[:3] + bears[:3] + split
    seen, picked = set(), []
    for pool in ([t for t in order if t not in used], order):
        for t in pool:
            if t in seen or t not in by:
                continue
            item = hot_from_row(by[t], quotes)
            if not item:
                continue
            seen.add(t)
            picked.append(item)
            if len(picked) >= limit:
                return picked
    return picked


def load_daily():
    st = read_json(work('stats.json'), {}) or {}
    daily = st.get('daily') if isinstance(st, dict) else None
    today = st.get('today') if isinstance(st, dict) else None
    if isinstance(daily, dict) and (daily.get('bull') or daily.get('bear') or daily.get('split')):
        return daily, today
    w = read_json(writeup_path(), {}) or {}
    return (w.get('daily') if isinstance(w.get('daily'), dict) else {}), w.get('today')


def quote_hhmm(quote_time):
    """ET and HKT clocks (HH:MM) from the latest regularMarketTime, or (None, None)."""
    if not isinstance(quote_time, dict):
        return None, None
    et_raw = str(quote_time.get('et') or '')
    hkt_raw = str(quote_time.get('hkt') or '').strip()
    et_m = re.search(r'T(\d{2}:\d{2})', et_raw)
    hkt_m = re.search(r'(\d{2}:\d{2})\s*$', hkt_raw)
    if not et_m or not hkt_m:
        return None, None
    return et_m.group(1), hkt_m.group(1)


def writeup_generated_hkt():
    """Site snapshot clock from data/writeup-input.json, 'YYYY-MM-DD HH:MM' in HKT."""
    data = read_json(writeup_path(), {}) or {}
    if isinstance(data, dict):
        gen = data.get('generated_hkt')
        if isinstance(gen, str) and gen.strip():
            return gen.strip()
    return ''


def asof_line(lang, et_hhmm, hkt_hhmm):
    if lang == 'zh':
        return f'截至 {et_hhmm} ET（{hkt_hhmm} HKT）'
    return f'As of {et_hhmm} ET ({hkt_hhmm} HKT)'


def site_asof_line(lang, generated_hkt):
    """Fallback when no live quote clock: site data as of the writeup snapshot."""
    stamp = str(generated_hkt or '').strip()
    if lang == 'zh':
        return f'網站數據截至 {stamp}' if stamp else '網站數據'
    return f'Site data as of {stamp}' if stamp else 'Site data'


def asof_map(quotes_ok, quote_time, generated_hkt):
    """Quote clock when quotes landed. Otherwise the site snapshot, never the slot post time."""
    if quotes_ok:
        et_hhmm, hkt_hhmm = quote_hhmm(quote_time)
        if et_hhmm and hkt_hhmm:
            return {lang: asof_line(lang, et_hhmm, hkt_hhmm) for lang in share.LANGS}
    return {lang: site_asof_line(lang, generated_hkt) for lang in share.LANGS}


def index_line(quotes, show_pct):
    if not show_pct:
        return ''
    parts = []
    for t in INDEXES:
        q = (quotes or {}).get(t) or {}
        chg = q.get('chg_pct')
        if not isinstance(chg, (int, float)):
            continue
        parts.append(f'${t} {fmt_pct(chg)}')
    return ' · '.join(parts)


def site_phrase(lang, item):
    bull = item.get('bull') if is_num(item.get('bull')) else None
    bear = item.get('bear') if is_num(item.get('bear')) else None
    if bull is None and bear is None:
        return ''
    side, n = 'bull', bull
    if bear is not None and (bull is None or bear > bull):
        side, n = 'bear', bear
    if n is None:
        return ''
    if lang == 'en':
        word = 'account' if n == 1 else 'accounts'
        adj = 'bullish' if side == 'bull' else 'bearish'
        return f'{n} {word} {adj} on site'
    adj = '看好' if side == 'bull' else '看淡'
    return f'網站 {n} 個帳號{adj}'


def hot_line(lang, item, show_pct):
    t = item['ticker']
    pct = item.get('chg_pct') if show_pct else None
    bit = f' {fmt_pct(pct)}' if isinstance(pct, (int, float)) else ''
    site = site_phrase(lang, item)
    if lang == 'zh':
        extra = f'，{site}' if site else ''
        return f'${t}{bit}{extra}'
    extra = f', {site}' if site else ''
    return f'${t}{bit}{extra}'


def change_line(lang, kind, tickers):
    if not tickers:
        return ''
    names = ', '.join(f'${t}' for t in tickers[:4])
    labels = {
        'joined_bull': {
            'en': f'Newly bullish on site: {names}',
            'zh': f'網站新入看好：{names}',
        },
        'joined_bear': {
            'en': f'Newly bearish on site: {names}',
            'zh': f'網站新入看淡：{names}',
        },
        'left_bull': {
            'en': f'Left the bullish list: {names}',
            'zh': f'退出看好：{names}',
        },
        'left_bear': {
            'en': f'Left the bearish list: {names}',
            'zh': f'退出看淡：{names}',
        },
    }
    return labels[kind][lang]


def change_kinds(slot):
    if slot == 'intraday_open':
        return ()
    if slot == 'intraday_1':
        return ('joined_bull',)
    if slot == 'intraday_2':
        return ('joined_bear',)
    if slot == 'intraday_3':
        return ('joined_bull', 'joined_bear')
    if slot == 'intraday_4':
        return ('left_bull', 'joined_bear')
    return ('joined_bull', 'joined_bear', 'left_bull', 'left_bear')


def tag_line(lang, tickers):
    tags = [share._primary_tag(lang)] + share._hash_tags(tickers[:2])
    return ' '.join(tags)


def assemble(parts):
    return '\n\n'.join(p.strip('\n') for p in parts if p and str(p).strip())


def strip_urls_and_names(text):
    """Drop non-site URLs. Posts never quote personal names."""
    if not isinstance(text, str):
        return text
    text = share.strip_dup_handles(text)
    for token in URL_RE.findall(text):
        if not token.startswith('https://thecrowdtape.com'):
            text = text.replace(token, '')
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


def fit_x(text):
    text = strip_urls_and_names(text)
    if share.xlen(text) <= 280:
        return text
    blocks = [b for b in text.split('\n\n') if b.strip()]
    while len(blocks) > 3 and share.xlen('\n\n'.join(blocks)) > 280:
        blocks.pop(-3)
    out = '\n\n'.join(blocks)
    if share.xlen(out) <= 280:
        return out
    lines = out.split('\n')
    while lines and share.xlen('\n'.join(lines)) > 280:
        if len(lines) <= 2:
            break
        lines.pop(-2)
    return '\n'.join(lines).strip()


def fit_th(text, lang):
    return share.fit_threads(strip_urls_and_names(text), lang)


def existing_x_texts(sp, history, date):
    out = set()
    intra = (sp or {}).get('intraday') if isinstance(sp, dict) else None
    slots = (intra or {}).get('slots') if isinstance(intra, dict) else {}
    for sl in (slots or {}).values():
        if not isinstance(sl, dict):
            continue
        xen = (sl.get('x') or {}).get('en') if isinstance(sl.get('x'), dict) else None
        text = xen.get('text') if isinstance(xen, dict) else xen
        if isinstance(text, str) and text.strip():
            out.add(share._norm_text(text))
    if isinstance(history, dict):
        rec = history.get(as_day(date)) or {}
        for raw in rec.get('intraday_x') or []:
            if isinstance(raw, str) and raw.strip():
                out.add(share._norm_text(raw))
        for key, rec in history.items():
            if not isinstance(rec, dict):
                continue
            for raw in rec.get('intraday_x') or []:
                if isinstance(raw, str) and raw.strip():
                    out.add(share._norm_text(raw))
    return out


def used_tickers(sp, history, date):
    out = []
    intra = (sp or {}).get('intraday') if isinstance(sp, dict) else None
    slots = (intra or {}).get('slots') if isinstance(intra, dict) else {}
    for sl in (slots or {}).values():
        if not isinstance(sl, dict):
            continue
        for item in sl.get('hot') or []:
            t = ticker_sym((item or {}).get('ticker'))
            if t and t not in out:
                out.append(t)
    rec = (history or {}).get(as_day(date)) if isinstance(history, dict) else None
    if isinstance(rec, dict):
        for t in rec.get('intraday') or []:
            s = ticker_sym(t)
            if s and s not in out:
                out.append(s)
    return out


def body_for(lang, slot, asof, indexes, hots, changes, show_pct, variant):
    heads = HEAD[slot][lang]
    head = heads[variant % len(heads)]
    title = f'{head} · {asof}'
    hot_lines = [hot_line(lang, item, show_pct) for item in hots]
    if variant % 2 and hot_lines:
        hot_lines = list(reversed(hot_lines))
    change_lines = [change_line(lang, kind, changes.get(kind) or []) for kind in change_kinds(slot)]
    change_lines = [ln for ln in change_lines if ln]
    if variant >= 2 and change_lines:
        change_lines = list(reversed(change_lines))
    parts = [title, indexes, '\n'.join(hot_lines), '\n'.join(change_lines)]
    return parts


def _x_try(head, indexes, hot_lines, change_lines, url, disc, tags, n_hot, with_idx, with_chg, with_url):
    parts = [head]
    if with_idx and indexes:
        parts.append(indexes)
    if n_hot and hot_lines:
        parts.append('\n'.join(hot_lines[:n_hot]))
    if with_chg and change_lines:
        parts.append(change_lines[0])
    if with_url and url:
        parts.append(url)
    parts.append(disc + '\n' + tags)
    return assemble(parts)


def compact_x(slot, asof, indexes, hots, changes, show_pct, variant, url, used_x):
    """English X body. Keep indexes + 1–2 hot names so xlen stays ≤ 280."""
    heads = HEAD[slot]['en']
    head = f'{heads[variant % len(heads)]} · {asof}'
    order = list(reversed(hots)) if variant % 2 else list(hots)
    hot_lines = [hot_line('en', item, show_pct) for item in order]
    change_lines = [change_line('en', kind, changes.get(kind) or []) for kind in change_kinds(slot)]
    change_lines = [ln for ln in change_lines if ln]
    if variant >= 2 and change_lines:
        change_lines = list(reversed(change_lines))
    disc = share.SHORT['en']['disc']
    tags = tag_line('en', [h['ticker'] for h in order[:2]])
    plans = (
        (2, True, True, True),
        (2, True, False, True),
        (1, True, False, True),
        (1, False, False, True),
        (1, False, False, False),
    )
    last = None
    for n_hot, with_idx, with_chg, with_url in plans:
        text = fit_x(_x_try(head, indexes, hot_lines, change_lines, url, disc, tags,
                            n_hot, with_idx, with_chg, with_url))
        last = (text, url if with_url and url in text else (url if with_url else None))
        if share.xlen(text) > 280:
            continue
        if share._norm_text(text) in used_x:
            continue
        return last
    return last


def build_texts(slot, date, asof, quotes, hots, changes, show_pct, take_threads_link, used_x):
    indexes = index_line(quotes, show_pct)
    tickers = [h['ticker'] for h in hots]
    campaign = slot
    x_url = home_url('en', 'x', campaign)
    th_urls = {lang: home_url(lang, 'threads', campaign) for lang in share.LANGS}

    x_entry, th_entries = None, None
    for variant in range(6):
        order = hots if variant < 3 else list(reversed(hots))
        x_text, x_kept_url = compact_x(
            slot, asof['en'], indexes, order, changes, show_pct, variant, x_url, used_x,
        )
        if not x_text or share.xlen(x_text) > 280:
            continue
        if share._norm_text(x_text) in used_x:
            continue
        th_out = {}
        ok_th = True
        for lang in share.LANGS:
            parts = body_for(lang, slot, asof[lang], indexes, order, changes, show_pct, variant)
            url = th_urls[lang] if take_threads_link else None
            tail = [url] if url else []
            tail += [share.SHORT[lang]['disc'] + '\n' + tag_line(lang, tickers)]
            text = fit_th(assemble(list(parts) + tail), lang)
            if len(text) > share.THREADS_MAX:
                ok_th = False
                break
            kept = url if url and url in text else None
            th_out[lang] = {'text': text, 'url': kept}
        if not ok_th:
            continue
        x_entry = {'text': x_text, 'url': x_kept_url if x_kept_url else (x_url if x_url in x_text else x_url)}
        if x_entry['url'] and x_entry['url'] not in x_entry['text']:
            # Still record the campaign URL even if the body dropped it to fit.
            pass
        th_entries = th_out
        break
    if x_entry is None:
        x_text, x_kept_url = compact_x(
            slot, asof['en'], indexes, hots, changes, show_pct, 0, x_url, set(),
        )
        x_entry = {'text': x_text, 'url': x_kept_url or x_url}
        th_entries = {}
        for lang in share.LANGS:
            parts = body_for(lang, slot, asof[lang], indexes, hots, changes, show_pct, 0)
            url = th_urls[lang] if take_threads_link else None
            tail = ([url] if url else []) + [share.SHORT[lang]['disc'] + '\n' + tag_line(lang, tickers)]
            text = fit_th(assemble(list(parts) + tail), lang)
            th_entries[lang] = {'text': text, 'url': url if url and url in text else None}
    if not show_pct:
        x_entry['text'] = re.sub(r' +', ' ', PCT_RE.sub('', x_entry['text'] or ''))
        for lang in share.LANGS:
            th_entries[lang]['text'] = re.sub(r' +', ' ', PCT_RE.sub('', th_entries[lang]['text'] or ''))
    return x_entry, th_entries


def build_slot(slot, date, now, daily, quotes, quote_time, quotes_ok, history_days, existing_slots,
               history=None, sp=None, site_asof=None):
    hour, minute = SLOT_HM[slot]
    post = post_dt(date, hour, minute)
    post_et = f'{hour:02d}:{minute:02d}'
    post_hkt = hkt_hhmm(post)
    show_pct = bool(quotes_ok)
    used = used_tickers(sp, history, date)
    hots = pick_hot(daily, quotes, slot, used, limit=4)
    curr_bull = ranked_tickers(daily, 'bull')
    curr_bear = ranked_tickers(daily, 'bear')
    prev_bull, prev_bear = previous_snapshot(history_days, date, existing_slots)
    changes = consensus_changes(curr_bull, curr_bear, prev_bull, prev_bear)
    take_link = threads_take_link(date, slot)
    used_x = existing_x_texts(sp, history, date)
    # Slot post_et/post_hkt stay on the record. The text clock is the quote, or the site snapshot.
    stamp = writeup_generated_hkt() if site_asof is None else str(site_asof).strip()
    asof = asof_map(show_pct, quote_time, stamp)
    x_entry, th_entries = build_texts(
        slot, date, asof, quotes if show_pct else {}, hots, changes,
        show_pct, take_link, used_x,
    )
    has_link = {
        'x': bool(x_entry.get('url')),
        'threads': {lang: bool((th_entries.get(lang) or {}).get('url')) for lang in share.LANGS},
    }
    generated = now_et(now)
    quote_source = 'Yahoo Finance'
    trade_day = as_day(date)
    return {
        'post_et': post_et,
        'post_hkt': post_hkt,
        'generated_at': iso_offset(generated),
        'date': trade_day,
        'date_kst': date_kst.et_post_date_kst(trade_day, post_et),
        'quotes': quotes or {},
        'quote_time': quote_time,
        'quote_source': quote_source,
        'quotes_ok': bool(quotes_ok),
        'fallback': not bool(quotes_ok),
        'hot': hots,
        'x': {'en': x_entry},
        'threads': th_entries,
        'has_link': has_link,
        'snapshot': {'bull': curr_bull, 'bear': curr_bear},
    }


def merge_intraday(data, date, slot_name, slot_obj, generated_at, generated_hkt):
    """Write data['intraday'] only. Keep other slots of the same ET date; reset when the date changes."""
    if not isinstance(data, dict):
        data = {}
    intra = data.get('intraday')
    if not isinstance(intra, dict) or as_day(intra.get('date')) != as_day(date):
        intra = {'date': as_day(date), 'slots': {}}
    slots = intra.get('slots') if isinstance(intra.get('slots'), dict) else {}
    slots[slot_name] = slot_obj
    intra['date'] = as_day(date)
    intra['generated_at'] = generated_at
    intra['generated_hkt'] = generated_hkt
    intra['slots'] = slots
    data['intraday'] = intra
    date_kst.stamp_intraday(intra)
    return data


def slot_file_path():
    """Generated slot, outside the checkout, so publish can reapply it after a hard reset."""
    return work('intraday-slot.json')


def write_slot_file(slot_name, date, slot_obj, generated_at, generated_hkt, path=None):
    path = path or slot_file_path()
    write_json(path, {
        'slot': slot_name,
        'date': as_day(date),
        'generated_at': generated_at,
        'generated_hkt': generated_hkt,
        'entry': slot_obj,
    }, indent=1)
    return path


def merge_from_file(path, save=True):
    """Merge one already-built slot into social posts and history. Does not fetch quotes."""
    payload = read_json(path, None)
    if not isinstance(payload, dict):
        raise SystemExit(f'merge-from: {path} is missing or not a slot file')
    slot_name = str(payload.get('slot') or '').strip()
    entry = payload.get('entry')
    date = as_day(payload.get('date') or (entry.get('date') if isinstance(entry, dict) else ''))
    if slot_name not in SLOT_NAMES or not isinstance(entry, dict) or not date:
        raise SystemExit(f'merge-from: {path} must contain slot, date, and entry')
    generated_at = payload.get('generated_at') or entry.get('generated_at')
    generated_hkt = payload.get('generated_hkt') or ''
    sp = read_json(posts_path(), {}) or {}
    if not isinstance(sp, dict):
        sp = {}
    merge_intraday(sp, date, slot_name, entry, generated_at, generated_hkt)
    history = share.load_social_history()
    remember_intraday(history, date, slot_name, entry)
    if save:
        write_json(posts_path(), sp, indent=1)
        normalize_file(posts_path())
        share.save_social_history(history)
    print(f'merge-from {slot_name} {date}')
    return sp.get('intraday', {}).get('slots', {}).get(slot_name)


def remember_intraday(history, date, slot_name, slot_obj):
    tickers = []
    for item in slot_obj.get('hot') or []:
        t = ticker_sym((item or {}).get('ticker'))
        if t and t not in tickers:
            tickers.append(t)
    share.remember_slots(history, date, {
        'intraday': tickers,
        slot_name: tickers,
    })
    rec = history.get(as_day(date))
    if not isinstance(rec, dict):
        rec = {}
        history[as_day(date)] = rec
    texts = rec.get('intraday_x')
    if not isinstance(texts, list):
        texts = []
    xen = ((slot_obj.get('x') or {}).get('en') or {}).get('text')
    norm = share._norm_text(xen or '')
    if norm and norm not in texts:
        texts.append(norm)
    rec['intraday_x'] = texts[-60:]
    return history


def emit_github(ok, slot, reason, force=False):
    path = os.environ.get('GITHUB_OUTPUT')
    if not path:
        return
    with open(path, 'a', encoding='utf-8') as f:
        f.write(f'run={"true" if ok else "false"}\n')
        f.write(f'slot={slot or ""}\n')
        f.write(f'force={"true" if force else "false"}\n')
        f.write(f'reason={reason}\n')


def generate(slot, now=None, force=False, chart_fn=None, sleep=0.3, save=True):
    now = now_et(now)
    holidays = load_holidays()
    ok, resolved, reason = evaluate_guard(now, slot, force=force, holidays=holidays)
    if not ok:
        print(reason)
        return None
    date = et_date(now)
    daily, _today = load_daily()
    sp = read_json(posts_path(), {}) or {}
    if not isinstance(sp, dict):
        sp = {}
    intra = sp.get('intraday') if isinstance(sp.get('intraday'), dict) else {}
    existing = intra.get('slots') if as_day(intra.get('date')) == date and isinstance(intra.get('slots'), dict) else {}
    history = share.load_social_history()
    hist = read_json(consensus_path(), {'days': {}}) or {'days': {}}
    used = used_tickers(sp, history, date)
    preview_hot = pick_hot(daily, {}, resolved, used, limit=4)
    tickers = list(INDEXES) + [h['ticker'] for h in preview_hot if h['ticker'] not in INDEXES]
    quotes, quote_time, quotes_ok = fetch_live_quotes(tickers, chart_fn=chart_fn, sleep=sleep)
    slot_obj = build_slot(
        resolved, date, now, daily, quotes, quote_time, quotes_ok, hist, existing,
        history=history, sp=sp,
    )
    generated_at = slot_obj['generated_at']
    generated_hkt = hkt_stamp(now)
    merge_intraday(sp, date, resolved, slot_obj, generated_at, generated_hkt)
    remember_intraday(history, date, resolved, slot_obj)
    if save:
        write_slot_file(resolved, date, slot_obj, generated_at, generated_hkt)
        write_json(posts_path(), sp, indent=1)
        normalize_file(posts_path())
        sp = read_json(posts_path(), sp)
        share.save_social_history(history)
    print(f'intraday {resolved} {date} quotes_ok={slot_obj["quotes_ok"]} fallback={slot_obj["fallback"]}')
    return sp.get('intraday', {}).get('slots', {}).get(resolved)


def parse_now(value):
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=NY)
    return dt.astimezone(NY)


def main(argv=None):
    p = argparse.ArgumentParser(description='Write one intraday social slot.')
    p.add_argument('--slot', default='auto', help='slot name, auto, or force')
    p.add_argument('--force', action='store_true', help='bypass time and trading-day guard')
    p.add_argument('--guard', action='store_true', help='only evaluate the time/trading-day guard')
    p.add_argument('--merge-from', default=None, metavar='FILE',
                   help='merge this slot file into social posts and history; do not fetch')
    p.add_argument('--now', default=None, help='ISO timestamp in America/New_York (tests)')
    p.add_argument('--no-sleep', action='store_true')
    args = p.parse_args(argv)
    if args.merge_from:
        merge_from_file(args.merge_from)
        return 0
    now = parse_now(args.now)
    force = bool(args.force or (args.slot or '').strip().lower() == 'force')
    if args.guard:
        ok, resolved, reason = evaluate_guard(now_et(now), args.slot, force=force)
        print(reason)
        emit_github(ok, resolved, reason, force=force)
        return 0
    slot = generate(args.slot, now=now, force=force, sleep=0 if args.no_sleep else 0.3)
    if slot is None:
        return 0
    return 0


if __name__ == '__main__':
    sys.exit(main())
