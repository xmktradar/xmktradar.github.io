"""Textbook TA spec v1 — one fact for beat ②, or omit.

Gate first (video_signal select_*). This module never invents a price and never
runs for a skipped slot. Touch band is 1% of the line. "Still above/below" is
anything outside that band that is not a just-cross — there is no 3% clear band.

Page price cards stay on px/*.json via update_prices.chart(). TA uses a separate
2-year daily OHLCV pull (chart_ohlcv) written to work/ta-bars.json.
"""
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SMA_BAND = 0.01
RSI_PERIOD = 14
RSI_HI = 70
RSI_LO = 30
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
MACD_JUST = 3
SWING = 5
LOOKBACK = 60
MIN_BARS = RSI_PERIOD + 1  # shorter than this → insufficient_bars
MAX_GAP_DAYS = 12
PAUSE_S = 0.3
REGULAR_CLOSE = (16, 0)
EARLY_CLOSE = (13, 0)

NY = ZoneInfo('America/New_York')
HK = timezone(timedelta(hours=8))

SPEC = 'textbook-ta-v1'
SOURCE = 'Yahoo Finance'
TIMEZONE = 'America/New_York'
AS_OF_SESSION = 'regular close'
DISCLAIMER = 'Statistics and this technical fact are not a trade signal or investment advice.'
SPOKEN_DISCLAIMER = 'This is not a trade signal.'
SCREEN_DISCLAIMER = 'Not a trade signal.'

OMIT_REASONS = ('yahoo_unavailable', 'insufficient_bars', 'stale_bars', 'no_clear_fact')
ON_SCREEN_TYPES = ('ma_line', 'sr_level', 'rsi_reading', 'macd_cross', 'structure')

# Verbatim phrase bank. {n} is 50 or 200. {px} is the one price. No second number.
PHRASES = {
    'sma_touch': ("It's sitting on the {n}-day.", 'Sitting on the {n}-day'),
    'sma_break_down': ('Price just lost the {n}-day.', 'Just lost the {n}-day'),
    'sma_break_up': ('Price just reclaimed the {n}-day.', 'Just reclaimed the {n}-day'),
    'sma_below': ("It's still trading below the {n}-day.", 'Still below the {n}-day'),
    'sma_above': ("It's holding above the {n}-day.", 'Holding above the {n}-day'),
    'sr_lost': ('Price just lost support near {px}.', 'Lost support near {px}'),
    'sr_broke': ('Price just broke resistance near {px}.', 'Broke resistance near {px}'),
    'sr_test': ("It's testing support near {px}.", 'Testing support near {px}'),
    'rsi_high': ('RSI is stretched on the upside.', 'RSI is stretched'),
    'rsi_low': ('RSI is stretched on the downside.', 'RSI is stretched'),
    'macd_up': ('MACD just crossed up.', 'MACD crossed up'),
    'macd_down': ('MACD just crossed down.', 'MACD crossed down'),
    'struct_lh': ("It's still making lower highs.", 'Still making lower highs'),
    'struct_hl': ("It's still making higher lows.", 'Still making higher lows'),
    'range_break': ('Price just broke out of its recent range.', 'Broke its recent range'),
}

FORBIDDEN = re.compile(
    r"\b(buy|sell|should|target|targets|stop|stops)\b|\bnow\b|looks like a buy",
    re.I,
)

_JSON_KEYS = (
    'ticker', 'yahoo_symbol', 'emit', 'omit_reason', 'method', 'level_name',
    'level', 'last_close', 'vo_en', 'caption_en', 'on_screen',
)


def sma(closes, n=50):
    if not closes or len(closes) < n:
        return None
    window = closes[-n:]
    return sum(window) / float(n)


def rsi_wilder(closes, period=14):
    """Wilder RSI. None when the series is shorter than period+1."""
    if not closes or len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gain = sum(max(d, 0.0) for d in deltas[:period]) / period
    loss = sum(max(-d, 0.0) for d in deltas[:period]) / period
    for d in deltas[period:]:
        gain = (gain * (period - 1) + max(d, 0.0)) / period
        loss = (loss * (period - 1) + max(-d, 0.0)) / period
    if loss == 0:
        return 100.0 if gain > 0 else 50.0
    rs = gain / loss
    return 100.0 - (100.0 / (1.0 + rs))


def just_window(slot, just_bars=None):
    """Week Tape: last completed session vs the prior day. Weekday: 1–2 bars."""
    if just_bars is not None:
        return int(just_bars)
    if str(slot or '') in ('sat', 'week'):
        return 1
    return 2


def fmt_px(v):
    v = float(v)
    if abs(v) >= 10:
        return f'{v:.2f}'
    return f'{v:.3f}'


def round_px(v):
    if v is None:
        return None
    v = float(v)
    return round(v, 2 if abs(v) >= 10 else 3)


def _num(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def coerce_bars(series):
    """[close], or bar dicts with date/open/high/low/close/volume. No invented prices."""
    if not series:
        return []
    first = series[0]
    if isinstance(first, dict):
        out = []
        for b in series:
            out.append({
                'date': b.get('date'),
                'open': _num(b.get('open')),
                'high': _num(b.get('high')),
                'low': _num(b.get('low')),
                'close': _num(b.get('close')),
                'volume': _num(b.get('volume')),
            })
        return [b for b in out if b['close'] is not None]
    out = []
    for c in series:
        if c is None:
            continue
        out.append({
            'date': None, 'open': None, 'high': None, 'low': None,
            'close': float(c), 'volume': None,
        })
    return out


def _has_hl(bars):
    if not bars:
        return False
    return all(b.get('high') is not None and b.get('low') is not None for b in bars)


def _phrase(method, n=None, px=None):
    vo, cap = PHRASES[method]
    if '{n}' in vo or '{n}' in cap:
        n = str(n)
        vo, cap = vo.format(n=n), cap.format(n=n)
    if '{px}' in vo or '{px}' in cap:
        px = fmt_px(px)
        vo, cap = vo.format(px=px), cap.format(px=px)
    return vo, cap


def _screen(kind, label, value):
    if kind not in ON_SCREEN_TYPES:
        raise ValueError(kind)
    return {'type': kind, 'label': label, 'value': value}


def _blocked(text):
    return bool(text and FORBIDDEN.search(text))


def _pack(method, *, n=None, px=None, level_name, level, last_close, screen_type, screen_label, screen_value):
    vo, cap = _phrase(method, n=n, px=px)
    if _blocked(vo) or _blocked(cap):
        return None
    level_r = round_px(level) if screen_type != 'rsi_reading' else level
    if screen_type == 'rsi_reading':
        screen_value = int(screen_value)
        level_r = screen_value
    else:
        screen_value = round_px(screen_value) if screen_value is not None else None
        level_r = screen_value if level is not None else None
    row = {
        'emit': True,
        'omit_reason': None,
        'method': method,
        'id': method,
        'level_name': level_name,
        'level': level_r,
        'last_close': round_px(last_close),
        'vo_en': vo,
        'caption_en': cap,
        'line': vo,
        'caption': cap,
        'note': SPOKEN_DISCLAIMER,
        'on_screen': _screen(screen_type, screen_label, screen_value),
    }
    return row


def _blank(reason, last_close=None):
    return {
        'emit': False,
        'omit_reason': reason,
        'method': None,
        'id': None,
        'level_name': None,
        'level': None,
        'last_close': round_px(last_close) if last_close is not None else None,
        'vo_en': '',
        'caption_en': '',
        'line': '',
        'caption': '',
        'note': '',
        'on_screen': None,
    }


def _sma_at(closes, n, end):
    """SMA of the `n` closes ending at index `end` (inclusive)."""
    if end < n - 1 or end >= len(closes):
        return None
    window = closes[end - n + 1:end + 1]
    return sum(window) / float(n)


def _cross_at(closes, n, back, direction):
    """`back` 1 = last bar. Cross vs the SMA as of each bar."""
    end = len(closes) - back
    if end < 1:
        return False
    sma_now = _sma_at(closes, n, end)
    sma_prev = _sma_at(closes, n, end - 1)
    if sma_now is None or sma_prev is None:
        return False
    prev, cur = closes[end - 1], closes[end]
    if direction == 'down':
        return prev >= sma_prev and cur < sma_now
    return prev < sma_prev and cur >= sma_now


def ma_cross(closes, n, just_bars):
    """'down' / 'up' if the line was crossed inside the just window, else None."""
    for back in range(1, just_bars + 1):
        if _cross_at(closes, n, back, 'down'):
            return 'down'
        if _cross_at(closes, n, back, 'up'):
            return 'up'
    return None


def _cross_age(closes, n):
    """Bars ago of the most recent cross, or None. 1 = last bar."""
    limit = len(closes) - n
    for back in range(1, max(limit, 0) + 1):
        if _cross_at(closes, n, back, 'down') or _cross_at(closes, n, back, 'up'):
            return back
    return None


def _touch(close, line):
    if not line:
        return False
    return abs(close / line - 1.0) <= SMA_BAND + 1e-9


def _ema(values, period):
    if len(values) < period:
        return None
    k = 2.0 / (period + 1)
    ema = sum(values[:period]) / float(period)
    out = [None] * (period - 1)
    out.append(ema)
    for v in values[period:]:
        ema = (v - ema) * k + ema
        out.append(ema)
    return out


def macd_cross(closes, just_bars=MACD_JUST):
    """'up' / 'down' if MACD crossed the signal line inside the window, else None."""
    if len(closes) < MACD_SLOW + MACD_SIGNAL:
        return None
    ema_fast = _ema(closes, MACD_FAST)
    ema_slow = _ema(closes, MACD_SLOW)
    macd = []
    for a, b in zip(ema_fast, ema_slow):
        macd.append(None if a is None or b is None else a - b)
    start = next(i for i, v in enumerate(macd) if v is not None)
    tail = macd[start:]
    signal = _ema(tail, MACD_SIGNAL)
    if not signal:
        return None
    n = len(closes)
    for back in range(1, just_bars + 1):
        i = n - back
        j = i - start
        if j <= 0 or j >= len(signal):
            continue
        prev_m, prev_s = tail[j - 1], signal[j - 1]
        cur_m, cur_s = tail[j], signal[j]
        if None in (prev_m, prev_s, cur_m, cur_s):
            continue
        if prev_m <= prev_s and cur_m > cur_s:
            return 'up'
        if prev_m >= prev_s and cur_m < cur_s:
            return 'down'
    return None


def _swings(bars):
    """Confirmed swings in the last 60 bars. Last 5 bars cannot confirm."""
    n = len(bars)
    start = max(0, n - LOOKBACK)
    highs, lows = [], []
    lo = max(start, SWING)
    hi = n - SWING
    for i in range(lo, hi):
        h = bars[i]['high']
        l = bars[i]['low']
        if h is not None and all(h > bars[i + d]['high'] for d in range(-SWING, SWING + 1) if d != 0):
            highs.append((i, h))
        if l is not None and all(l < bars[i + d]['low'] for d in range(-SWING, SWING + 1) if d != 0):
            lows.append((i, l))
    return highs, lows


def _nearest_swing(bars, close):
    highs, lows = _swings(bars)
    pool = [('resistance', i, p) for i, p in highs] + [('support', i, p) for i, p in lows]
    if not pool:
        return None
    return min(pool, key=lambda row: abs(row[2] - close))


def _level_cross(closes, level, just_bars, direction):
    for back in range(1, just_bars + 1):
        i = len(closes) - back
        if i <= 0:
            continue
        prev, cur = closes[i - 1], closes[i]
        if direction == 'down' and prev >= level and cur < level:
            return True
        if direction == 'up' and prev <= level and cur > level:
            return True
    return False


def _lower_highs(bars):
    highs, _lows = _swings(bars)
    if len(highs) < 2:
        return False
    return highs[-1][1] < highs[-2][1]


def _higher_lows(bars):
    _highs, lows = _swings(bars)
    if len(lows) < 2:
        return False
    return lows[-1][1] > lows[-2][1]


def _range_break(bars, just_bars):
    if len(bars) < LOOKBACK + 1:
        return False
    closes = [b['close'] for b in bars]
    for back in range(1, just_bars + 1):
        i = len(bars) - back
        if i < LOOKBACK:
            continue
        window = bars[i - LOOKBACK:i]
        if any(b['high'] is None or b['low'] is None for b in window):
            continue
        hi = max(b['high'] for b in window)
        lo = min(b['low'] for b in window)
        if closes[i] > hi or closes[i] < lo:
            return True
    return False


def _ma_fact(closes, period, kind, last):
    line = sma(closes, period)
    if kind == 'down':
        method = 'sma_break_down'
    elif kind == 'up':
        method = 'sma_break_up'
    elif kind == 'touch':
        method = 'sma_touch'
    elif kind == 'above':
        method = 'sma_above'
    else:
        method = 'sma_below'
    return _pack(
        method, n=period, level_name=f'{period}-day SMA', level=line, last_close=last,
        screen_type='ma_line', screen_label=f'{period}-day', screen_value=line,
    )


def assess_series(series, slot='1230', just_bars=None):
    """One fact dict, or emit false. `series` is closes or OHLCV bars. No network."""
    bars = coerce_bars(series)
    closes = [b['close'] for b in bars]
    last = closes[-1] if closes else None
    if len(closes) < MIN_BARS:
        return _blank('insufficient_bars', last)
    window = just_window(slot, just_bars)
    hl = _has_hl(bars)

    # 1. Just lost / reclaimed / broke: 50-day, then 200-day, then one S/R.
    for period in (50, 200):
        kind = ma_cross(closes, period, window)
        if kind:
            fact = _ma_fact(closes, period, kind, last)
            if fact:
                return fact
    if hl:
        nearest = _nearest_swing(bars, last)
        if nearest:
            side, _i, level = nearest
            if side == 'support' and _level_cross(closes, level, window, 'down'):
                fact = _pack(
                    'sr_lost', px=level, level_name='support', level=level, last_close=last,
                    screen_type='sr_level', screen_label='support', screen_value=level,
                )
                if fact:
                    return fact
            if side == 'resistance' and _level_cross(closes, level, window, 'up'):
                fact = _pack(
                    'sr_broke', px=level, level_name='resistance', level=level, last_close=last,
                    screen_type='sr_level', screen_label='resistance', screen_value=level,
                )
                if fact:
                    return fact

    # 2. Sitting on / testing the same lines. 50-day, then 200-day, then support.
    for period in (50, 200):
        line = sma(closes, period)
        if line and _touch(last, line):
            fact = _ma_fact(closes, period, 'touch', last)
            if fact:
                return fact
    if hl:
        nearest = _nearest_swing(bars, last)
        if nearest and nearest[0] == 'support' and _touch(last, nearest[2]):
            if not _level_cross(closes, nearest[2], window, 'down'):
                fact = _pack(
                    'sr_test', px=nearest[2], level_name='support', level=nearest[2], last_close=last,
                    screen_type='sr_level', screen_label='support', screen_value=nearest[2],
                )
                if fact:
                    return fact

    # 3. Still above/below, outside the 1% band, not a just-cross.
    # Both qualify: the line whose cross is more recent; else 50-day; 200-day only when it is the clear one.
    qual = []
    for period in (50, 200):
        line = sma(closes, period)
        if not line or _touch(last, line):
            continue
        side = 'above' if last > line else 'below'
        qual.append((period, side, _cross_age(closes, period)))
    if qual:
        by_p = {p: (side, age) for p, side, age in qual}
        if 50 in by_p and 200 in by_p:
            age50, age200 = by_p[50][1], by_p[200][1]
            if age200 is not None and (age50 is None or age200 < age50):
                period = 200
            else:
                period = 50
        elif 50 in by_p:
            period = 50
        else:
            period = 200
        fact = _ma_fact(closes, period, by_p[period][0], last)
        if fact:
            return fact

    # 4. RSI(14) only at the extremes.
    rsi = rsi_wilder(closes, RSI_PERIOD)
    if rsi is not None and (rsi >= RSI_HI or rsi <= RSI_LO):
        method = 'rsi_high' if rsi >= RSI_HI else 'rsi_low'
        shown = int(round(rsi))
        fact = _pack(
            method, level_name='RSI(14)', level=shown, last_close=last,
            screen_type='rsi_reading', screen_label='RSI', screen_value=shown,
        )
        if fact:
            return fact

    # 5. MACD just crossed the signal line within 1–3 completed bars.
    macd = macd_cross(closes, MACD_JUST)
    if macd:
        method = 'macd_up' if macd == 'up' else 'macd_down'
        fact = _pack(
            method, level_name='MACD(12,26,9)', level=None, last_close=last,
            screen_type='macd_cross', screen_label='MACD', screen_value=None,
        )
        if fact:
            return fact

    # 6. Structure. No head-and-shoulders / double-top names.
    if hl:
        if _lower_highs(bars):
            fact = _pack(
                'struct_lh', level_name='lower highs', level=None, last_close=last,
                screen_type='structure', screen_label='lower highs', screen_value=None,
            )
            if fact:
                return fact
        if _higher_lows(bars):
            fact = _pack(
                'struct_hl', level_name='higher lows', level=None, last_close=last,
                screen_type='structure', screen_label='higher lows', screen_value=None,
            )
            if fact:
                return fact
        if _range_break(bars, window):
            fact = _pack(
                'range_break', level_name='60-day range', level=None, last_close=last,
                screen_type='structure', screen_label='60-day range', screen_value=None,
            )
            if fact:
                return fact

    return _blank('no_clear_fact', last)


def ta_fact(series, slot='1230', just_bars=None):
    """Emit-true fact, or None. Same priority as assess_series."""
    row = assess_series(series, slot=slot, just_bars=just_bars)
    if not row.get('emit'):
        return None
    return row


def disclaimer_fits(line, note=SPOKEN_DISCLAIMER):
    """Weekday TA beat is 5–8s (~12–20 English words). Append the disclaimer only inside that."""
    words = f'{line or ""} {note or ""}'.split()
    return 0 < len(words) <= 20


def speak_disclaimer(mode, slot=None, show=None):
    """Week Tape never speaks the disclaimer. A weekday single may."""
    if mode == 'hot-list':
        return False
    if str(slot or '') in ('sat', 'week') or show == 'week-tape':
        return False
    return True


# ---------- session clock (completed regular bars only) ----------

def load_market_days(path=None):
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'market_holidays.json')
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return set(), set()
    closures = {str(x) for x in (data.get('closures') or [])}
    early = {str(x) for x in (data.get('early_close') or [])}
    return closures, early


def _is_trading(day, closures):
    return day.weekday() < 5 and day.isoformat() not in closures


def last_completed_before(day, closures):
    """Previous NYSE session strictly before `day`. Holidays and weekends are not sessions."""
    d = day - timedelta(days=1)
    for _ in range(21):
        if _is_trading(d, closures):
            return d
        d -= timedelta(days=1)
    return d


def session_complete(now, day, early):
    close = EARLY_CLOSE if day.isoformat() in early else REGULAR_CLOSE
    return (now.hour, now.minute) >= close


def expected_as_of(slot, now, closures=None, early=None):
    """NY date of the completed bar this show may use.

    Tape Take (1230, 12:30 ET): previous completed session.
    Crowd Heat (1630, 16:30 ET): today's bar only after the regular close, else previous.
    Week Tape (sat): last completed trading day (usually Friday).
    """
    if closures is None or early is None:
        loaded_c, loaded_e = load_market_days()
        if closures is None:
            closures = loaded_c
        if early is None:
            early = loaded_e
    if now.tzinfo is None:
        now = now.replace(tzinfo=NY)
    else:
        now = now.astimezone(NY)
    day = now.date()
    slot = str(slot or '')
    if slot in ('sat', 'week'):
        if _is_trading(day, closures) and session_complete(now, day, early):
            return day
        return last_completed_before(day, closures)
    if slot == '1630':
        if _is_trading(day, closures) and session_complete(now, day, early):
            return day
        return last_completed_before(day, closures)
    return last_completed_before(day, closures)


def normalize_rows(rows):
    """Dedupe by date. None when the series is broken (unordered or a gap over 12 days)."""
    if not rows:
        return None
    cleaned = []
    for row in rows:
        close = _num(row.get('close') if isinstance(row, dict) else None)
        if close is None or close <= 0:
            continue
        date = row.get('date')
        if not date:
            continue
        high, low = _num(row.get('high')), _num(row.get('low'))
        if high is not None and low is not None and high < low:
            continue
        cleaned.append({
            'date': str(date)[:10],
            'open': _num(row.get('open')),
            'high': high,
            'low': low,
            'close': close,
            'volume': _num(row.get('volume')),
        })
    if not cleaned:
        return None
    dedup = {}
    for row in cleaned:
        dedup[row['date']] = row
    out = [dedup[k] for k in sorted(dedup)]
    prev = None
    for row in out:
        if prev is not None:
            gap = (datetime.strptime(row['date'], '%Y-%m-%d') - datetime.strptime(prev, '%Y-%m-%d')).days
            if gap <= 0 or gap > MAX_GAP_DAYS:
                return None
        prev = row['date']
    return out


def _trim_completed(bars, as_of):
    day = as_of.isoformat()
    return [b for b in bars if b.get('date') and b['date'] <= day]


def _public_row(row, ticker, yahoo_symbol):
    out = {k: row.get(k) for k in _JSON_KEYS}
    out['ticker'] = ticker
    out['yahoo_symbol'] = yahoo_symbol
    if out['emit']:
        out['omit_reason'] = None
    else:
        out['vo_en'] = ''
        out['method'] = None
        out['on_screen'] = None
    return out


def row_for_bars(ticker, yahoo_symbol, bars, *, as_of, slot):
    """Freshness + one fact. `bars` already normalized. No network."""
    trimmed = _trim_completed(bars or [], as_of)
    if not trimmed or trimmed[-1]['date'] < as_of.isoformat():
        return _public_row(_blank('stale_bars'), ticker, yahoo_symbol), None
    assessed = assess_series(trimmed, slot=slot)
    return _public_row(assessed, ticker, yahoo_symbol), trimmed


def log_ta_omit(ticker, reason):
    print(f'ta_omit {ticker} {reason}', flush=True)


def _show_of(decision):
    show = (decision or {}).get('show')
    if show:
        return show
    slot = str((decision or {}).get('slot') or '')
    return {'1230': 'tape-take', '1630': 'crowd-heat', 'sat': 'week-tape', 'week': 'week-tape'}.get(slot, slot or 'tape-take')


def _work_dir(root=None):
    if root is not None:
        return os.path.join(root, 'work')
    env = os.environ.get('WORK_DIR')
    if env:
        return env
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'work')


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')


def build_facts_doc(decision, bars_by_ticker, *, now, fetched_hkt=None, closures=None, early=None):
    """Facts document from injected OHLCV. `bars_by_ticker[ticker]` is bars or {'error': reason}."""
    slot = str((decision or {}).get('slot') or '1230')
    as_of = expected_as_of(slot, now, closures, early)
    if fetched_hkt is None:
        stamp = now if now.tzinfo else now.replace(tzinfo=NY)
        fetched_hkt = stamp.astimezone(HK).strftime('%Y-%m-%d %H:%M')
    tickers = []
    kept = {}
    for name in (decision or {}).get('names') or []:
        ticker = name.get('t')
        got = (bars_by_ticker or {}).get(ticker)
        if got is None or (isinstance(got, dict) and got.get('error')):
            reason = (got or {}).get('error') if isinstance(got, dict) else None
            row = _public_row(_blank(reason or 'yahoo_unavailable'), ticker, (got or {}).get('yahoo_symbol') if isinstance(got, dict) else None)
            tickers.append(row)
            continue
        if isinstance(got, dict) and 'bars' in got:
            yahoo_symbol = got.get('yahoo_symbol') or ticker
            raw = got.get('bars')
        else:
            yahoo_symbol = ticker
            raw = got
        norm = normalize_rows(raw) if raw and isinstance(raw[0], dict) and raw[0].get('date') else None
        if raw and isinstance(raw[0], dict) and raw[0].get('date') and norm is None:
            row = _public_row(_blank('yahoo_unavailable'), ticker, yahoo_symbol)
            tickers.append(row)
            continue
        if norm is None:
            # Injected undated closes are not a Yahoo pull; still no invented price.
            assessed = assess_series(raw, slot=slot)
            row = _public_row(assessed, ticker, yahoo_symbol)
            tickers.append(row)
            if assessed.get('emit'):
                kept[ticker] = coerce_bars(raw)
            continue
        row, used = row_for_bars(ticker, yahoo_symbol, norm, as_of=as_of, slot=slot)
        tickers.append(row)
        if used is not None:
            kept[ticker] = used
    doc = {
        'spec': SPEC,
        'slot': _show_of(decision),
        'as_of': as_of.isoformat(),
        'as_of_session': AS_OF_SESSION,
        'timezone': TIMEZONE,
        'source': SOURCE,
        'fetched_hkt': fetched_hkt,
        'disclaimer': DISCLAIMER,
        'tickers': tickers,
    }
    return doc, kept


def publish_ta(decision, *, fetch=None, now=None, root=None, closures=None, early=None, pause=None, write=True):
    """Write work/ta-facts.json and work/ta-bars.json for a publishable decision.

    Returns None when the gate skipped — no fetch, no file, no invented fact.
    `fetch(ticker)` may return {'yahoo_symbol', 'bars'} or {'error': 'yahoo_unavailable'}.
    """
    if not decision or decision.get('publishable') is False or decision.get('mode') == 'skip':
        return None
    names = decision.get('names') or []
    if not names:
        return None
    now = now or datetime.now(NY)
    if now.tzinfo is None:
        now = now.replace(tzinfo=NY)
    pause = PAUSE_S if pause is None else pause
    if fetch is None:
        def fetch(ticker, _pause=pause):
            return fetch_yahoo(ticker, pause=_pause)
    bars_by = {}
    for name in names:
        ticker = name.get('t')
        try:
            bars_by[ticker] = fetch(ticker)
        except Exception:
            bars_by[ticker] = {'error': 'yahoo_unavailable'}
    doc, kept = build_facts_doc(decision, bars_by, now=now, closures=closures, early=early)
    for row in doc['tickers']:
        if not row.get('emit'):
            log_ta_omit(row.get('ticker'), row.get('omit_reason') or 'no_clear_fact')
    if write:
        work = _work_dir(root)
        _write_json(os.path.join(work, 'ta-facts.json'), doc)
        slot = str(decision.get('slot') or 'slot')
        _write_json(os.path.join(work, f'ta-facts-{slot}.json'), doc)
        bars_doc = {
            'spec': SPEC,
            'slot': doc['slot'],
            'as_of': doc['as_of'],
            'timezone': TIMEZONE,
            'source': SOURCE,
            'fetched_hkt': doc['fetched_hkt'],
            'tickers': {
                t: {'yahoo_symbol': next((r.get('yahoo_symbol') for r in doc['tickers'] if r.get('ticker') == t), t),
                    'bars': rows}
                for t, rows in kept.items()
            },
        }
        _write_json(os.path.join(work, 'ta-bars.json'), bars_doc)
    return doc


def load_symbol_context(root=None):
    """Hand overrides and price-card symbols, same places update_prices reads. Read only."""
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, 'data', 'dash', 'overrides.json')
    if os.path.isfile(path):
        try:
            with open(path, encoding='utf-8') as f:
                ov = json.load(f)
            if isinstance(ov, dict):
                return ov, {}
        except (OSError, json.JSONDecodeError):
            pass
    try:
        from sitedata import load
        data = load(os.path.join(root, 'index.html'))
    except Exception:
        return {}, {}
    ov = data.get('overrides') if isinstance(data.get('overrides'), dict) else {}
    prices = data.get('prices') if isinstance(data.get('prices'), dict) else {}
    symbols = {}
    for t, row in prices.items():
        if isinstance(row, dict) and row.get('symbol'):
            symbols[t] = row['symbol']
    return ov, symbols


def resolve_symbol(ticker, overrides=None, price_symbols=None, probe=None, search_fn=None):
    """Yahoo symbol, or None when unresolved / unconfirmed / the probe found nothing.

    Hand overrides are not second-guessed. Otherwise: override or price-card symbol,
    INDEX_SYMBOLS, the ticker, then US-exchange exact matches from search.
    """
    from update_prices import INDEX_SYMBOLS, candidates

    t = str(ticker or '').lstrip('$').upper().strip()
    if not t:
        return None
    ov = (overrides or {}).get(t) or {}
    if ov.get('drop'):
        return None
    if ov.get('unconfirmed') and not ov.get('auto'):
        return None
    hand = bool(ov) and not ov.get('auto')
    if hand and ov.get('symbol'):
        if probe and probe(ov['symbol']):
            return ov['symbol']
        return None

    price_sym = (price_symbols or {}).get(t)
    first = []
    if ov.get('symbol'):
        first.append(ov['symbol'])
    elif price_sym:
        first.append(price_sym)
    if t in INDEX_SYMBOLS:
        first.append(INDEX_SYMBOLS[t])
    first.append(t)
    seen = []
    for sym in list(dict.fromkeys(first)):
        seen.append(sym)
        if probe and probe(sym):
            return sym
    if hand:
        return None
    if search_fn is None:
        return None
    found = search_fn(t)
    if not found:
        return None
    for sym in candidates(t, found):
        if sym in seen:
            continue
        seen.append(sym)
        if probe and probe(sym):
            return sym
    return None


def fetch_yahoo(ticker, pause=PAUSE_S, overrides=None, price_symbols=None):
    """2y daily OHLCV. Throttles about 0.3s per request. Never writes px/."""
    from update_prices import chart_ohlcv, search

    if overrides is None or price_symbols is None:
        loaded_ov, loaded_px = load_symbol_context()
        if overrides is None:
            overrides = loaded_ov
        if price_symbols is None:
            price_symbols = loaded_px
    cache = {}

    def probe(sym):
        if sym not in cache:
            try:
                got = chart_ohlcv(sym, '2y', '1d')
            except Exception:
                got = None
            if pause:
                time.sleep(pause)
            cache[sym] = got if got and got[1] else None
        return cache[sym] is not None

    def search_fn(t):
        try:
            found = search(t)
        except Exception:
            found = None
        if pause:
            time.sleep(pause)
        return found

    sym = resolve_symbol(ticker, overrides, price_symbols, probe=probe, search_fn=search_fn)
    if not sym or cache.get(sym) is None:
        return {'error': 'yahoo_unavailable', 'yahoo_symbol': sym}
    _meta, rows = cache[sym]
    norm = normalize_rows(rows)
    if not norm:
        return {'error': 'yahoo_unavailable', 'yahoo_symbol': sym}
    return {'yahoo_symbol': sym, 'bars': norm}
