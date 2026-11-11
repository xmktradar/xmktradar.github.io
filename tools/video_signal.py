"""Tape Take / Crowd Heat / Week Tape selection and three-beat script.

Official tracked-account counts only (the same `top` / `split` rows `stats.js` already
writes). Never invent a handle, a quote, or a price.

A name qualifies only when all of these hold:
  * heat is real (`accounts >= MIN_HEAT_ACCOUNTS`, ranked by `top[].accounts`,
    `heat.now` as a tie-break)
  * at least one citable tracked post (`urls` / `accs` / `rows` / an explicit quote)
  * not 零看好、零看淡 (`bull_accounts + bear_accounts == 0`)
  * not empty talk

Split (both sides have weight): each side >= MIN_SIDE, bull+bear >= 5, and
min/max >= 0.35. 5 vs 4 and 68 vs 51 are splits. 99 vs 1 is a one-sided lean.
A hot one-sided name (8 bull / 0 bear) may still be selected; the script must
not call it a split or a fight.

Week Tape (`sat`): hottest qualifying names, cap 5. Two names stay a list of
two. Exactly one name uses the weekday single structure. Zero names skip.
Weekday Tape Take / Crowd Heat: one name, and only when the day has a clear
heat leader or a real split. A pile of mild names skips.

TA runs only after that gate, and only for selected names. One textbook fact
(spec v1) from a separate 2-year Yahoo OHLCV pull — never from `px/` price
cards, and never invented to rescue a skip. If nothing qualifies, beat ② is
omitted and the job log gets `ta_omit`.
"""
import json
import os
import re
from datetime import date as date_cls

import textbook_ta

MIN_HEAT_ACCOUNTS = 3
MIN_SIDE = 2
SPLIT_SUM = 5
SPLIT_RATIO = 0.35
CLEAR_HEAT = 6          # standout discussion count for a weekday heat leader
CLEAR_GAP = 2           # accounts ahead of #2, or 1.5x, counts as a clear leader
LEADER_OVER_SPLIT = 3   # a one-sided name this far ahead of a split wins on heat
SMA_BAND = textbook_ta.SMA_BAND  # |close/SMA - 1| <= 1% → sitting on that line
WEEK_CAP = 5
MAX_VIDEO_S = 40.0
WEEK_MAX_VIDEO_S = 75.0  # Saturday hot-list ~60s; a little over is ok. Not the 40s fail.

SHOWS = {'1230': 'tape-take', '1630': 'crowd-heat', 'sat': 'week-tape', 'week': 'week-tape'}

# Weekday single, 124 BPM. Seconds ≈ beats * 60/124.
# hook 6 ≈ 2.9s, heat 20 ≈ 9.7s, ta 13 ≈ 6.3s, views 20 ≈ 9.7s, cta 14 ≈ 6.8s → ~35s.
WEEKDAY_TA = {'hook': 6, 'heat': 20, 'ta': 13, 'views': 20, 'cta': 14}
# No TA: fold that time into heat / views / cta so the cut stays inside 30–40s.
WEEKDAY_NOTA = {'hook': 6, 'heat': 24, 'views': 24, 'cta': 16}
WEEKDAY_TA_SHORT = {'hook': 6, 'heat': 16, 'ta': 11, 'views': 16, 'cta': 12}
WEEKDAY_NOTA_SHORT = {'hook': 6, 'heat': 18, 'views': 18, 'cta': 14}


def spell(t):
    """Tickers are read letter by letter: SPY -> 'S P Y'."""
    return ' '.join(str(t or ''))


def num(s, d=0):
    m = re.search(r'\d+', str(s or ''))
    return int(m.group()) if m else d


def count_en(n, one, many):
    n = int(n or 0)
    return f'{n} {one if n == 1 else many}'


def _int(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def is_split(bull, bear):
    """Both sides have weight. 5/4 and 68/51 yes. 99/1 and 8/0 no."""
    b, r = _int(bull), _int(bear)
    if b < MIN_SIDE or r < MIN_SIDE:
        return False
    if b + r < SPLIT_SUM:
        return False
    hi = max(b, r)
    if hi <= 0:
        return False
    return (min(b, r) / hi) >= SPLIT_RATIO


def angle_of(bull, bear):
    if is_split(bull, bear):
        return 'split'
    if _int(bull) > _int(bear):
        return 'one_sided_bull'
    if _int(bear) > _int(bull):
        return 'one_sided_bear'
    return 'flat'


def stance_from(cover):
    """Bull/bear from pills, or `bar: [nb, nr]`, or `nb`/`nr`, or a vs subtitle.

    Duel covers often have `bar` and `sub` and no pills. Reading only pills
    turned 5 vs 3 into 0 vs 0.
    """
    if not isinstance(cover, dict):
        return 0, 0
    pills = [p for p in (cover.get('pills') or []) if isinstance(p, dict)]
    g = next((p for p in pills if p.get('c') == 'g'), None)
    r = next((p for p in pills if p.get('c') == 'r'), None)
    bull = num(g.get('x')) if g else 0
    bear = num(r.get('x')) if r else 0
    bar = cover.get('bar')
    if isinstance(bar, (list, tuple)) and len(bar) >= 2:
        if g is None:
            bull = _int(bar[0])
        if r is None:
            bear = _int(bar[1])
    if g is None and r is None and not (isinstance(bar, (list, tuple)) and len(bar) >= 2):
        if cover.get('nb') is not None or cover.get('nr') is not None:
            bull, bear = _int(cover.get('nb')), _int(cover.get('nr'))
        else:
            sub = str(cover.get('sub') or '')
            m = re.search(r'(\d+)\s*(?:bull\w*|好).*?(\d+)\s*(?:bear\w*|淡|空)', sub, re.I)
            if not m:
                m = re.search(r'(\d+)\s*vs\s*(\d+)', sub, re.I)
            if m:
                bull, bear = int(m.group(1)), int(m.group(2))
    return bull, bear


def counts(cover):
    """`(accounts, bull, bear)` from a cover slide."""
    bull, bear = stance_from(cover if isinstance(cover, dict) else {})
    sub = str((cover or {}).get('sub') or '') if isinstance(cover, dict) else ''
    n = num(sub)
    if (bull or bear) and re.search(r'\bvs\b|\bbull', sub, re.I) and not re.search(r'account|帳號|个|個', sub, re.I):
        n = bull + bear
    return n, bull, bear


def norm(raw):
    if not isinstance(raw, dict):
        raw = {}
    bull = raw.get('bull_accounts')
    bear = raw.get('bear_accounts')
    if bull is None:
        bull = raw.get('nb') if raw.get('nb') is not None else 0
    if bear is None:
        bear = raw.get('nr') if raw.get('nr') is not None else 0
    accounts = raw.get('accounts')
    if accounts is None:
        accounts = raw.get('now')
    if accounts is None:
        accounts = _int(bull) + _int(bear)
    return {
        't': str(raw.get('t') or '').upper(),
        'accounts': _int(accounts),
        'bull_accounts': _int(bull),
        'bear_accounts': _int(bear),
        'urls': [u for u in (raw.get('urls') or []) if u],
        'accs': [a for a in (raw.get('accs') or []) if a],
        'rows': [r for r in (raw.get('rows') or []) if r],
        'now': raw.get('now'),
        'citable': raw.get('citable'),
        'quote': raw.get('quote'),
        'quotes': raw.get('quotes'),
        'empty': bool(raw.get('empty')),
    }


def _citable(n):
    if n.get('citable') is True:
        return True
    if n.get('urls') or n.get('accs') or n.get('rows'):
        return True
    if n.get('quote') or n.get('quotes'):
        return True
    return False


def qualify_name(name, **_ignored):
    """Return `(ok, reason)`. `reason` is empty when the name may air."""
    n = norm(name)
    if not n['t']:
        return False, 'no_names'
    if n.get('empty'):
        return False, 'weak_signal'
    if n['accounts'] < MIN_HEAT_ACCOUNTS:
        return False, 'no_heat'
    if n['bull_accounts'] + n['bear_accounts'] <= 0:
        return False, 'zero_stance'
    if not _citable(n):
        return False, 'no_cite'
    return True, ''


def heat_key(n):
    now = n.get('now')
    try:
        now_n = int(now) if now is not None else 0
    except (TypeError, ValueError):
        now_n = 0
    return (int(n.get('accounts') or 0), now_n, int(n.get('bull_accounts') or 0) + int(n.get('bear_accounts') or 0))


def _as_names(names):
    if isinstance(names, dict) and any(k in names for k in ('top', 'split', 'bull', 'bear')):
        return candidates(names)
    if isinstance(names, dict):
        return [norm(names)]
    return [norm(n) for n in (names or [])]


def candidates(window):
    """Merge `top` / `split` / `bull` / `bear` into one row per ticker.

    `top` is authoritative for accounts and stance when those keys are present,
    so a 0/0 hero is not rewritten into a fake split. A name that exists only
    on `split` still enters the pool (weekday must be able to pick it).
    """
    if not isinstance(window, dict):
        return []
    order, by = [], {}

    def slot(t):
        t = str(t or '').strip().upper()
        if not t:
            return None
        if t not in by:
            by[t] = norm({'t': t})
            by[t]['_stance'] = False
            by[t]['_accounts'] = False
            order.append(t)
        return by[t]

    for x in window.get('top') or []:
        if not isinstance(x, dict):
            continue
        row = slot(x.get('t'))
        if not row:
            continue
        if x.get('accounts') is not None:
            row['accounts'] = _int(x.get('accounts'))
            row['_accounts'] = True
        if 'bull_accounts' in x or 'bear_accounts' in x:
            row['bull_accounts'] = _int(x.get('bull_accounts'))
            row['bear_accounts'] = _int(x.get('bear_accounts'))
            row['_stance'] = True
        if x.get('urls'):
            row['urls'] = [u for u in x['urls'] if u]
        if x.get('accs'):
            row['accs'] = [a for a in x['accs'] if a]
        if x.get('now') is not None:
            row['now'] = x.get('now')
        if x.get('citable') is True:
            row['citable'] = True
        if x.get('empty'):
            row['empty'] = True
    for g in window.get('split') or []:
        if not isinstance(g, dict):
            continue
        row = slot(g.get('t'))
        if not row:
            continue
        nb, nr = _int(g.get('nb')), _int(g.get('nr'))
        if not row['_stance']:
            row['bull_accounts'], row['bear_accounts'] = nb, nr
            row['_stance'] = True
        if not row['_accounts']:
            row['accounts'] = nb + nr
            row['_accounts'] = True
        if g.get('rows'):
            row['rows'] = [r for r in g['rows'] if r]
        if g.get('urls'):
            row['urls'] = [u for u in g['urls'] if u]
    for key, side in (('bull', 'bull'), ('bear', 'bear')):
        for g in window.get(key) or []:
            if not isinstance(g, dict):
                continue
            row = slot(g.get('t'))
            if not row:
                continue
            if g.get('rows') and not row['rows']:
                row['rows'] = [r for r in g['rows'] if r]
            n = _int(g.get('nb') if side == 'bull' else g.get('nr'))
            if not row['_accounts'] and n:
                row['accounts'] = max(row['accounts'], n)
                row['_accounts'] = True
            if not row['_stance'] and n:
                if side == 'bull':
                    row['bull_accounts'] = n
                else:
                    row['bear_accounts'] = n
                row['_stance'] = True
    for h in window.get('heat') or []:
        if not isinstance(h, dict):
            continue
        row = by.get(str(h.get('t') or '').upper())
        if row and h.get('now') is not None and row.get('now') is None:
            row['now'] = h.get('now')
    out = []
    for t in order:
        row = by[t]
        row.pop('_stance', None)
        row.pop('_accounts', None)
        out.append(row)
    return out


def _clear_leader(ranked):
    if not ranked:
        return False
    lead = ranked[0]['accounts']
    if lead < CLEAR_HEAT:
        return False
    if len(ranked) == 1:
        return True
    second = ranked[1]['accounts']
    if second <= 0:
        return True
    return (lead - second) >= CLEAR_GAP or lead >= second * 1.5


def _decision(publishable, reason, detail, mode, names):
    return {
        'publishable': bool(publishable),
        'reason': reason,
        'detail': detail,
        'mode': mode,
        'names': names,
    }


def _weekday_reason(raw, fails):
    if not raw or all(n['accounts'] < MIN_HEAT_ACCOUNTS for n in raw):
        return 'no_heat'
    heated = [n for n in raw if n['accounts'] >= MIN_HEAT_ACCOUNTS]
    if heated and all(n['bull_accounts'] + n['bear_accounts'] <= 0 for n in heated):
        return 'zero_stance'
    if fails and set(fails) <= {'no_heat'}:
        return 'no_heat'
    return 'weak_signal'


def _week_reason(raw, fails):
    if not raw:
        return 'no_names'
    if all(n['accounts'] <= 0 for n in raw):
        return 'zero_discussion'
    heated = [n for n in raw if n['accounts'] >= MIN_HEAT_ACCOUNTS]
    if heated and all(n['bull_accounts'] + n['bear_accounts'] <= 0 for n in heated):
        return 'zero_stance'
    if not heated:
        return 'zero_discussion' if all(n['accounts'] <= 0 for n in raw) else 'no_names'
    if fails and set(fails) <= {'zero_stance'}:
        return 'zero_stance'
    return 'no_names'


def _stamp(names):
    out = []
    for n in names:
        row = dict(n)
        row['angle'] = angle_of(row['bull_accounts'], row['bear_accounts'])
        out.append(row)
    return out


def select_weekday(names):
    """One ticker, or skip. Hottest clear leader, else the hottest real split."""
    raw = _as_names(names)
    qualified, fails = [], []
    for n in raw:
        ok, why = qualify_name(n)
        if ok:
            qualified.append(n)
        else:
            fails.append(why)
    qualified.sort(key=heat_key, reverse=True)
    if not qualified:
        return _decision(False, _weekday_reason(raw, fails), 'No clear heat or contrast on the day.', 'skip', [])
    splits = [n for n in qualified if is_split(n['bull_accounts'], n['bear_accounts'])]
    leader = qualified[0]
    if is_split(leader['bull_accounts'], leader['bear_accounts']):
        chosen = leader
    elif splits:
        best_split = max(splits, key=heat_key)
        if _clear_leader(qualified) and leader['accounts'] >= best_split['accounts'] + LEADER_OVER_SPLIT:
            chosen = leader
        else:
            chosen = best_split
    elif _clear_leader(qualified):
        chosen = leader
    else:
        reason = 'no_contrast' if len(qualified) > 1 else 'weak_signal'
        return _decision(False, reason, 'No clear heat leader and no big contrast.', 'skip', [])
    return _decision(True, None, '', 'single', _stamp([chosen]))


def select_week_tape(names):
    """3–5 hottest qualifiers. 2 stays 2. 1 becomes a single. 0 skips. Never pad."""
    raw = _as_names(names)
    qualified, fails = [], []
    for n in raw:
        ok, why = qualify_name(n)
        if ok:
            qualified.append(n)
        else:
            fails.append(why)
    qualified.sort(key=heat_key, reverse=True)
    if not qualified:
        return _decision(False, _week_reason(raw, fails), 'No qualifying name for Week Tape.', 'skip', [])
    if len(qualified) == 1:
        return _decision(True, None, '', 'single', _stamp(qualified))
    return _decision(True, None, '', 'hot-list', _stamp(qualified[:WEEK_CAP]))


def _wd(date):
    if date is None:
        return None
    if isinstance(date, date_cls):
        return date.weekday()
    text = str(date)[:10]
    try:
        y, m, d = (int(x) for x in text.split('-'))
        return date_cls(y, m, d).weekday()
    except (TypeError, ValueError):
        return None


def _window(stats, slot):
    if not isinstance(stats, dict):
        return stats
    if slot in ('sat', 'week'):
        weekly = stats.get('weekly')
        if isinstance(weekly, dict):
            return weekly
        return stats
    daily = stats.get('daily')
    if isinstance(daily, dict):
        return daily
    return stats


def evaluate_slot(slot, stats, date=None, lang='en', weekday=None):
    """Full gate for one show. Sunday and an empty pool skip with `publishable` false."""
    slot = str(slot or '')
    show = SHOWS.get(slot, slot)
    wd = weekday if weekday is not None else _wd(date)
    base = {'slot': slot, 'show': show, 'date': (str(date)[:10] if date else None), 'lang': lang or 'en'}
    if wd == 6:
        out = _decision(False, 'sunday', 'Sunday is off.', 'skip', [])
        out.update(base)
        return out
    window = _window(stats, slot)
    if isinstance(window, dict) and any(k in window for k in ('top', 'split', 'bull', 'bear')):
        names = candidates(window)
    elif isinstance(window, list):
        names = [norm(n) for n in window]
    elif isinstance(stats, list):
        names = [norm(n) for n in stats]
    else:
        names = []
    picked = select_week_tape(names) if slot in ('sat', 'week') else select_weekday(names)
    picked = dict(picked)
    picked.update(base)
    return picked


# ---------- technical fact (one, or none) ----------

sma = textbook_ta.sma
rsi_wilder = textbook_ta.rsi_wilder


def ta_fact(series, slot='1230', just_bars=None):
    """Exactly one textbook fact, or None. Never a second indicator. Never a made-up price."""
    return textbook_ta.ta_fact(series, slot=slot, just_bars=just_bars)


def load_closes(ticker, root=None):
    """Daily closes from `px/<TICKER>.json`. Missing file → []. No live quote."""
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, 'px', f'{ticker}.json')
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    out = []
    for row in data.get('c') or []:
        if isinstance(row, (list, tuple)) and len(row) >= 2 and row[1] is not None:
            out.append(float(row[1]))
        elif isinstance(row, (int, float)):
            out.append(float(row))
    return out


# ---------- three-beat script ----------

def _views_copy(bull, bear, short=False):
    counts = f'{count_en(bull, "bull", "bulls")} versus {count_en(bear, "bear", "bears")}'
    ang = angle_of(bull, bear)
    if ang == 'split':
        return f'Split: {counts}.' if short else f'Tracked accounts are split: {counts}.'
    if ang == 'one_sided_bull':
        if _int(bear) == 0:
            return f'Lean bullish. {counts}.' if short else f'Tracked accounts lean bullish — almost no bear case. {counts}.'
        return f'Lean bullish. {counts}.' if short else f'Tracked accounts lean bullish. {counts}.'
    if ang == 'one_sided_bear':
        if _int(bull) == 0:
            return f'Lean bearish. {counts}.' if short else f'Tracked accounts lean bearish — almost no bull case. {counts}.'
        return f'Lean bearish. {counts}.' if short else f'Tracked accounts lean bearish. {counts}.'
    return 'On the tape.' if short else 'Tracked accounts are on the tape.'


def _views_caption(bull, bear):
    ang = angle_of(bull, bear)
    if ang == 'split':
        return 'Bulls versus bears'
    if ang == 'one_sided_bear':
        return 'Accounts lean bearish'
    if ang == 'one_sided_bull':
        return 'Accounts lean bullish'
    return 'On the tape today'


def _hook_vo(ticker, bull, bear, week_list=False, weekly_single=False):
    if week_list:
        return "This week's most discussed stocks."
    sp = spell(ticker)
    if is_split(bull, bear):
        return f'The fight this week is {sp}.' if weekly_single else f'The fight today is {sp}.'
    when = 'this week' if weekly_single else 'today'
    return f'{sp} is the most discussed name on the tape {when}.'


def _hook_caption(week_list, bull, bear, weekly_single=False):
    if week_list:
        return "This week's most discussed"
    if is_split(bull, bear):
        return 'The fight this week' if weekly_single else 'The fight today'
    return 'Most discussed name'


def _heat_vo(ticker, n, first=True, week=False, short=False):
    sp = spell(ticker)
    when = 'this week' if week else 'today'
    if short:
        return f'{sp} — {n} tracked accounts.'
    if first:
        return f'{sp} is the most talked-about name {when} — {n} tracked accounts are on it.'
    return f'Next, {sp} — {n} tracked accounts are on it.'


def _cta_vo(ticker, week_list=False):
    if week_list:
        return 'Which of these are you on — bull or bear?'
    return f'Bull or bear on {spell(ticker)}?'


def _week_name_budget(n_names, has_ta):
    """Beats for one Week Tape name. ~10s at 5 names, up to ~15s at 2–3. TA time folds in when omitted."""
    if n_names >= 5:
        heat, ta, views = 7, 7, 8
    elif n_names == 4:
        heat, ta, views = 8, 8, 10
    elif n_names == 3:
        heat, ta, views = 10, 8, 12
    else:
        heat, ta, views = 10, 8, 13
    if has_ta:
        return heat, ta, views
    return heat + ta // 2, 0, views + (ta - ta // 2)


def _beat(role, scene, base, base_short, vo, vo_short, caption, visual):
    return {
        'role': role,
        'scene': scene,
        'base': base,
        'base_short': base_short,
        'vo': vo,
        'vo_short': vo_short or vo,
        'caption': caption,
        'visual': visual,
    }


def _ta_voice(fact, speak):
    """Week Tape keeps the short line. A weekday single may add the spoken disclaimer."""
    line = (fact.get('line') or fact.get('vo_en') or '').strip()
    if speak and line and textbook_ta.disclaimer_fits(line):
        note = (fact.get('note') or textbook_ta.SPOKEN_DISCLAIMER).strip()
        if note:
            return f'{line} {note}'.strip(), line
    return line, line


def _ta_visual(ticker, fact, line, speak):
    visual = {
        'ticker': ticker,
        'big': ticker,
        'caption': fact.get('caption') or fact.get('caption_en') or '',
        'fact': line,
        'factId': fact.get('id') or fact.get('method'),
    }
    if fact.get('on_screen'):
        visual['on_screen'] = fact['on_screen']
    if not speak:
        visual['disclaimer'] = textbook_ta.SCREEN_DISCLAIMER
    return visual


def _single_beats(name, fact, weekly_single=False, speak_disclaimer=True):
    bull, bear = name['bull_accounts'], name['bear_accounts']
    n = name['accounts']
    ticker = name['t']
    table = WEEKDAY_TA if fact else WEEKDAY_NOTA
    short = WEEKDAY_TA_SHORT if fact else WEEKDAY_NOTA_SHORT
    week = bool(weekly_single)
    hook = _hook_vo(ticker, bull, bear, weekly_single=week)
    heat = _heat_vo(ticker, n, first=True, week=week, short=False)
    heat_s = _heat_vo(ticker, n, first=True, week=week, short=True)
    views = _views_copy(bull, bear, short=False)
    views_s = _views_copy(bull, bear, short=True)
    cta = _cta_vo(ticker, week_list=False)
    ang = angle_of(bull, bear)
    beats = [
        _beat('hook', 'hook', table['hook'], short['hook'], hook, hook,
              _hook_caption(False, bull, bear, weekly_single=week),
              {'hideChrome': True, 'hookQ': hook, 'caption': _hook_caption(False, bull, bear, weekly_single=week),
               'big': ticker, 'flash': False, 'tickers': []}),
        _beat('heat', 'heat', table['heat'], short['heat'], heat, heat_s,
              f'{n} accounts on it',
              {'ticker': ticker, 'big': ticker, 'accounts': n, 'caption': f'{n} accounts on it'}),
    ]
    if fact:
        ta_vo, ta_line = _ta_voice(fact, speak_disclaimer)
        caption = fact.get('caption') or fact.get('caption_en') or ''
        beats.append(_beat('ta', 'ta', table['ta'], short['ta'], ta_vo, ta_line, caption,
                           _ta_visual(ticker, fact, ta_line, speak_disclaimer)))
    beats.append(_beat('views', 'views', table['views'], short['views'], views, views_s, _views_caption(bull, bear),
                       {'ticker': ticker, 'big': ticker, 'bull': bull, 'bear': bear, 'angle': ang,
                        'caption': _views_caption(bull, bear)}))
    beats.append(_beat('cta', 'cta', table['cta'], short['cta'], cta, cta, 'Bull or bear?',
                       {'discussion': True, 'line': cta, 'caption': 'Bull or bear?', 'ticker': ticker, 'big': ticker}))
    return beats


def _list_beats(names, facts):
    n_names = len(names)
    hook = _hook_vo('', 0, 0, week_list=True)
    cta = _cta_vo('', week_list=True)
    tickers = [n['t'] for n in names]
    # Ending 4–6s. Hook stays inside 3s. Short pass trims name beats, never hook or CTA.
    hook_b, cta_b = 6, 12 if n_names <= 3 else 11
    beats = [_beat('hook', 'hook', hook_b, hook_b, hook, hook, "This week's most discussed",
                   {'hideChrome': True, 'hookQ': hook, 'caption': "This week's most discussed",
                    'flash': True, 'tickers': tickers, 'big': tickers[0] if tickers else ''})]
    for i, name in enumerate(names):
        fact = (facts or {}).get(name['t'])
        heat_b, ta_b, views_b = _week_name_budget(n_names, bool(fact))
        bull, bear = name['bull_accounts'], name['bear_accounts']
        heat = _heat_vo(name['t'], name['accounts'], first=(i == 0), week=True, short=False)
        heat_s = _heat_vo(name['t'], name['accounts'], first=(i == 0), week=True, short=True)
        views = _views_copy(bull, bear, short=False)
        views_s = _views_copy(bull, bear, short=True)
        beats.append(_beat('heat', 'heat', heat_b, max(4, int(round(heat_b * 0.75))), heat, heat_s,
                           f'{name["accounts"]} accounts on it',
                           {'ticker': name['t'], 'big': name['t'], 'accounts': name['accounts'],
                            'caption': f'{name["accounts"]} accounts on it'}))
        if fact and ta_b:
            ta_vo, ta_line = _ta_voice(fact, speak=False)
            caption = fact.get('caption') or fact.get('caption_en') or ''
            beats.append(_beat('ta', 'ta', ta_b, max(4, int(round(ta_b * 0.75))),
                               ta_vo, ta_line, caption,
                               _ta_visual(name['t'], fact, ta_line, speak=False)))
        beats.append(_beat('views', 'views', views_b, max(4, int(round(views_b * 0.75))), views, views_s,
                           _views_caption(bull, bear),
                           {'ticker': name['t'], 'big': name['t'], 'bull': bull, 'bear': bear,
                            'angle': angle_of(bull, bear), 'caption': _views_caption(bull, bear)}))
    beats.append(_beat('cta', 'cta', cta_b, cta_b, cta, cta, 'Bull or bear?',
                       {'discussion': True, 'line': cta, 'caption': 'Bull or bear?', 'tickers': tickers}))
    return beats


def build_beats(names, mode='single', weekly_single=False, facts=None, speak_disclaimer=None):
    """Beats for a decision. One qualifying name always uses the 30–40s single."""
    names = [norm(n) if 'angle' not in n else n for n in names]
    facts = facts or {}
    if speak_disclaimer is None:
        speak_disclaimer = mode != 'hot-list'
    if mode != 'hot-list' or len(names) <= 1:
        if not names:
            return []
        return _single_beats(
            names[0], facts.get(names[0]['t']),
            weekly_single=weekly_single or (mode == 'single' and weekly_single),
            speak_disclaimer=speak_disclaimer,
        )
    return _list_beats(names, facts)


def _fact_map_from_doc(doc):
    out = {}
    for row in (doc or {}).get('tickers') or []:
        ticker = row.get('ticker')
        out[ticker] = row if row.get('emit') else None
    return out


def script_beats(decision, closes_for=None, bars_for=None, facts=None):
    """Beats for a decision that already passed the gate.

    A skip returns no beats and does not read prices. `facts` is a ta-facts
    document or a `{ticker: fact}` map. Otherwise one fact is assessed from
    injected bars or closes — not from `px/` unless the caller passes `load_closes`.
    """
    if not isinstance(decision, dict) or decision.get('publishable') is False or decision.get('mode') == 'skip':
        return []
    names = decision.get('names') or []
    slot = decision.get('slot') or '1230'
    if facts is None and closes_for is None and bars_for is None:
        facts = textbook_ta.publish_ta(decision)
    if isinstance(facts, dict) and 'tickers' in facts:
        fact_map = _fact_map_from_doc(facts)
    elif facts is not None:
        fact_map = facts
    else:
        fact_map = {}
        for n in names:
            ticker = n.get('t')
            try:
                if bars_for is not None:
                    series = bars_for(ticker) if ticker else []
                else:
                    series = closes_for(ticker) if ticker else []
            except Exception:
                series = []
            row = textbook_ta.assess_series(series or [], slot=slot)
            if row.get('emit'):
                fact_map[ticker] = row
            else:
                fact_map[ticker] = None
                textbook_ta.log_ta_omit(ticker, row.get('omit_reason') or 'no_clear_fact')
    weekly_single = decision.get('mode') == 'single' and slot in ('sat', 'week')
    speak = textbook_ta.speak_disclaimer(decision.get('mode'), decision.get('slot'), decision.get('show'))
    return build_beats(names, mode=decision.get('mode') or 'single', weekly_single=weekly_single,
                       facts=fact_map, speak_disclaimer=speak)


def derive_beats(job):
    """Beats from a carousel job. Does not read `px/` (tests stay stable).

    A stored `job['beats']` wins. Otherwise one name is taken from the cover.
    Pass `job['closes']` or `job['ta']` to force a TA beat in tests.
    """
    if not isinstance(job, dict):
        return []
    if job.get('beats'):
        return job['beats']
    if job.get('names'):
        names = [norm(n) for n in job['names']]
    else:
        slides = job.get('slides') or []
        cover = slides[0] if slides else {}
        n, bull, bear = counts(cover if isinstance(cover, dict) else {})
        names = [norm({
            't': (cover or {}).get('big') if isinstance(cover, dict) else '',
            'accounts': n, 'bull_accounts': bull, 'bear_accounts': bear,
            'citable': True, 'urls': ['slide'],
        })]
    facts = {}
    if job.get('ta') and names:
        facts[names[0]['t']] = job['ta']
    elif job.get('closes') and names:
        facts[names[0]['t']] = ta_fact(job['closes'])
    mode = job.get('mode') or ('hot-list' if len(names) > 1 else 'single')
    weekly_single = mode == 'single' and str(job.get('slot') or '') in ('sat', 'week')
    speak = textbook_ta.speak_disclaimer(mode, job.get('slot'), job.get('show'))
    return build_beats(names, mode=mode, weekly_single=weekly_single, facts=facts, speak_disclaimer=speak)


def en_lines(job, short=False):
    beats = derive_beats(job)
    key = 'vo_short' if short else 'vo'
    return [b.get(key) or b.get('vo') or '' for b in beats]


def bases_for(job, short=False):
    beats = derive_beats(job)
    if short:
        return [b.get('base_short') or b.get('base') or 8 for b in beats]
    return [b.get('base') or 8 for b in beats]


def video_cap(job):
    """40s weekday / Saturday single. Hot-list may run ~60s (cap 75s)."""
    if not isinstance(job, dict):
        return MAX_VIDEO_S
    if job.get('mode') == 'hot-list':
        return WEEK_MAX_VIDEO_S
    beats = job.get('beats') or []
    if sum(1 for b in beats if b.get('role') == 'heat') > 1:
        return WEEK_MAX_VIDEO_S
    return MAX_VIDEO_S


def write_skip(body, root='.'):
    """Skip artifact. No mp4, no cover, no vo:true, no yt sidecar.

    Writes `og/c/<day>-<show>-<lang>.skip.json` and `work/video-status.json`.
    """
    day = body.get('date') or 'day'
    show = body.get('show') or 'tape-take'
    lang = body.get('lang') or 'en'
    payload = {
        'publishable': False,
        'reason': body.get('reason') or 'no_heat',
        'detail': body.get('detail') or '',
        'slot': body.get('slot'),
        'show': show,
        'date': day,
        'lang': lang,
    }
    og = os.path.join(root, 'og', 'c')
    os.makedirs(og, exist_ok=True)
    skip_path = os.path.join(og, f'{day}-{show}-{lang}.skip.json')
    with open(skip_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write('\n')
    # Drop a half-written publish for this stem. Never touch another day.
    stem = os.path.join(og, f'{day}-{show}-{lang}')
    for extra in ('.mp4', '.part.mp4', '-cover.jpg', '.vo.json', '-yt-title.txt', '-yt-desc.txt'):
        try:
            os.remove(stem + extra)
        except OSError:
            pass
    work = os.environ.get('WORK_DIR') or os.path.join(root, 'work')
    os.makedirs(work, exist_ok=True)
    status_path = os.path.join(work, 'video-status.json')
    prev = {}
    if os.path.isfile(status_path):
        try:
            with open(status_path, encoding='utf-8') as f:
                prev = json.load(f)
        except (OSError, json.JSONDecodeError):
            prev = {}
    skips = prev.get('skips') if isinstance(prev, dict) else None
    if not isinstance(skips, list):
        skips = []
    skips.append(payload)
    status = dict(payload)
    status['skips'] = skips
    with open(status_path, 'w', encoding='utf-8') as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
        f.write('\n')
    msg = f"{show} {day} skipped: {payload['reason']} — {payload['detail']}"
    print(f'::notice::{msg}', flush=True)
    print(f'::warning::{msg}', flush=True)
    return skip_path
