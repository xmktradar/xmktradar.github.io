"""Textbook TA spec v1. Offline. No Yahoo, no ffmpeg.

    python3 tools/test_textbook_ta.py
"""
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import textbook_ta  # noqa: E402
import video_signal  # noqa: E402
from test_video_signal import cited  # noqa: E402

NY = ZoneInfo('America/New_York')
BEAT = 60 / 124
FORBIDDEN = re.compile(
    r"\b(buy|sell|should|target|targets|stop|stops)\b|\bnow\b|looks like a buy",
    re.I,
)


def _rel_close(rel, n=50, prev=100.0):
    """Last close so close/SMA(n)-1 ~= rel, with n-1 copies of prev before it."""
    return (1.0 + rel) * (n - 1) * prev / (n - (1.0 + rel))


def _rel(closes, n=50):
    return closes[-1] / textbook_ta.sma(closes, n) - 1.0


def _just_lost_50(closes):
    prev_sma = sum(closes[-51:-1]) / 50.0
    now_sma = sum(closes[-50:]) / 50.0
    return closes[-2] >= prev_sma and closes[-1] < now_sma


def _lost_50_and_hot_rsi():
    """40 flats, a short rise, a long flat, then the smallest drop that crosses the 50-day.

    A large drop kills Wilder RSI. Once the 50-day has caught the rise, a few cents
    still crosses it and leaves RSI above 70, so priority (just-lost before RSI) is real.
    """
    base = [100.0] * 40
    price = 100.0
    for _ in range(14):
        price += 0.2
        base.append(round(price, 10))
    for _ in range(46):
        base.append(price)
    window = base[-50:]
    oldest = window[0]
    prev_sma = sum(window) / 50.0
    need = price - (50.0 * prev_sma - oldest) / 49.0
    return base + [price - (need + 0.01)]


def _macd_up_closes():
    """Under 50 closes so the 50-day does not exist: drift down, then rebound through MACD."""
    price = 40.0
    closes = [price] * 27
    for _ in range(8):
        price -= 0.2
        closes.append(price)
    for _ in range(5):
        price += 0.28
        closes.append(price)
    return closes


def _support_bars():
    """Swing low at 90, crossed on the last bar, with the 50-day already lost earlier."""
    closes = [120.0] * 50 + [95.0] * 20 + [91.0, 89.0]
    bars = []
    for c in closes:
        bars.append({'open': c, 'high': c + 0.5, 'low': c - 0.2, 'close': c, 'volume': 1000})
    swing = 30
    bars[swing]['low'] = 90.0
    for d in range(-5, 6):
        if d:
            bars[swing + d]['low'] = max(bars[swing + d]['low'], 96.0)
    bars[-1]['low'] = 88.0
    return bars


def _dated(end, n, close, highs=True):
    end_d = datetime.strptime(end, '%Y-%m-%d').date()
    rows = []
    for i in range(n):
        day = end_d - timedelta(days=(n - 1 - i))
        px = close if not isinstance(close, list) else close[i]
        row = {'date': day.isoformat(), 'open': px, 'close': px, 'volume': 1000}
        if highs:
            row['high'] = px + 1
            row['low'] = px - 1
        rows.append(row)
    return rows


def _decision(slot, tickers, date):
    stats_key = 'weekly' if slot in ('sat', 'week') else 'daily'
    names = [cited(t, 12, 7, 4) for t in tickers]
    return video_signal.evaluate_slot(slot, {stats_key: {'top': names}}, date=date, lang='en')


def _assert_clean(text):
    assert not FORBIDDEN.search(text or ''), text


def test_band_is_one_percent():
    """1.4% is outside the touch band (the old 1.5% band would have sat). 0.5% sits, one fact."""
    assert textbook_ta.SMA_BAND == 0.01
    assert video_signal.SMA_BAND == 0.01
    assert not hasattr(video_signal, 'SMA_CLEAR')

    wide = [100.0] * 49 + [_rel_close(0.014)]
    rel = _rel(wide)
    assert 0.01 < abs(rel) < 0.015, rel
    fact = textbook_ta.ta_fact(wide)
    assert fact is not None
    assert fact['method'] == 'sma_above', fact
    assert fact['method'] != 'sma_touch'
    assert fact['vo_en'] == "It's holding above the 50-day."
    assert 'rsi' not in fact['vo_en'].lower()
    _assert_clean(fact['vo_en'])

    near = [100.0] * 49 + [_rel_close(0.005)]
    rel = _rel(near)
    assert abs(rel) <= 0.01, rel
    fact = textbook_ta.ta_fact(near)
    assert fact['method'] == 'sma_touch', fact
    assert fact['vo_en'] == "It's sitting on the 50-day."
    assert fact['caption_en'] == 'Sitting on the 50-day'
    assert fact['on_screen']['type'] == 'ma_line'
    assert list(fact['on_screen']) == ['type', 'label', 'value']


def test_short_series_omits_without_inventing():
    closes = [432.10] * 40
    row = textbook_ta.assess_series(closes)
    assert row['emit'] is False
    assert row['omit_reason'] == 'no_clear_fact'
    assert row['vo_en'] == ''
    assert row['last_close'] == round(432.10, 2)
    assert textbook_ta.ta_fact(closes) is None
    tiny = [1.0, 2.0, 3.0]
    short = textbook_ta.assess_series(tiny)
    assert short['emit'] is False and short['omit_reason'] == 'insufficient_bars'
    assert short['vo_en'] == ''
    assert short['last_close'] == 3.0


def test_just_lost_50_beats_stretched_rsi():
    closes = _lost_50_and_hot_rsi()
    assert _just_lost_50(closes)
    rsi = textbook_ta.rsi_wilder(closes, 14)
    assert rsi >= 70, rsi
    fact = textbook_ta.ta_fact(closes, slot='1230')
    assert fact['method'] == 'sma_break_down', fact
    assert fact['vo_en'] == 'Price just lost the 50-day.'
    assert 'rsi' not in fact['vo_en'].lower()
    assert 'stretch' not in fact['vo_en'].lower()


def test_sr_omitted_without_high_low():
    bars = _support_bars()
    closes = [b['close'] for b in bars]
    bare = textbook_ta.ta_fact(closes)
    assert bare is None or not str(bare.get('method', '')).startswith('sr_'), bare
    full = textbook_ta.ta_fact(bars)
    assert full['method'] == 'sr_lost', full
    assert full['vo_en'] == 'Price just lost support near 90.00.'
    assert full['caption_en'] == 'Lost support near 90.00'
    assert full['on_screen']['type'] == 'sr_level'
    assert '90.00' in full['vo_en']
    assert full['vo_en'].count('90.00') == 1


def test_phrase_bank_verbatim():
    touch = textbook_ta.ta_fact([100.0] * 60)
    assert touch['method'] == 'sma_touch'
    assert touch['vo_en'] == textbook_ta.PHRASES['sma_touch'][0].format(n='50')
    assert touch['caption_en'] == textbook_ta.PHRASES['sma_touch'][1].format(n='50')

    lost = textbook_ta.ta_fact([100.0] * 60 + [90.0], slot='1230')
    assert lost['method'] == 'sma_break_down', lost
    assert lost['vo_en'] == 'Price just lost the 50-day.'
    assert lost['caption_en'] == 'Just lost the 50-day'

    rsi = textbook_ta.ta_fact([float(50 + i) for i in range(40)])
    assert rsi['method'] == 'rsi_high', rsi
    assert rsi['vo_en'] == 'RSI is stretched on the upside.'
    assert rsi['caption_en'] == 'RSI is stretched'
    assert rsi['on_screen']['type'] == 'rsi_reading'
    assert isinstance(rsi['on_screen']['value'], int)

    macd_closes = _macd_up_closes()
    assert len(macd_closes) < 50
    assert textbook_ta.sma(macd_closes, 50) is None
    rsi_now = textbook_ta.rsi_wilder(macd_closes, 14)
    assert 30 < rsi_now < 70, rsi_now
    assert textbook_ta.macd_cross(macd_closes, 3) == 'up'
    macd = textbook_ta.ta_fact(macd_closes)
    assert macd['method'] == 'macd_up', (macd, textbook_ta.rsi_wilder(macd_closes, 14))
    assert macd['vo_en'] == 'MACD just crossed up.'
    assert macd['caption_en'] == 'MACD crossed up'
    assert macd['on_screen']['type'] == 'macd_cross'
    for fact in (touch, lost, rsi, macd):
        _assert_clean(fact['vo_en'])
        _assert_clean(fact['caption_en'])


def test_week_tape_screen_disclaimer_weekday_may_speak():
    closes = [100.0] * 60
    week = _decision('sat', ['NVDA', 'AMD'], '2026-11-14')
    assert week['publishable'] is True and week['mode'] == 'hot-list'
    beats = video_signal.script_beats(week, closes_for=lambda _t: list(closes))
    tas = [b for b in beats if b['role'] == 'ta']
    assert len(tas) == 2, [b['role'] for b in beats]
    for b in tas:
        assert b['vo'] == "It's sitting on the 50-day.", b['vo']
        assert 'This is not a trade signal.' not in b['vo']
        assert 'Not a trade signal.' not in b['vo']
        assert b['visual']['disclaimer'] == 'Not a trade signal.'
        assert 3.0 <= b['base'] * BEAT <= 4.05, b['base'] * BEAT
        _assert_clean(b['vo'])

    one = _decision('sat', ['NVDA'], '2026-11-14')
    assert one['mode'] == 'single'
    one_beats = video_signal.script_beats(one, closes_for=lambda _t: list(closes))
    one_ta = next(b for b in one_beats if b['role'] == 'ta')
    assert 'This is not a trade signal.' not in one_ta['vo']
    assert one_ta['visual']['disclaimer'] == 'Not a trade signal.'

    day = video_signal.select_weekday([cited('QQQ', 8, 5, 3)])
    day_beats = video_signal.script_beats(day, closes_for=lambda _t: list(closes))
    day_ta = next(b for b in day_beats if b['role'] == 'ta')
    assert day_ta['vo'] == "It's sitting on the 50-day. This is not a trade signal.", day_ta['vo']
    assert 'disclaimer' not in day_ta['visual']
    assert 5.0 <= day_ta['base'] * BEAT <= 8.0
    _assert_clean(day_ta['vo'])


def test_week_tape_just_is_one_session():
    """A cross two bars back is still 'just' on a weekday and 'still' on Week Tape."""
    closes = [100.0] * 60 + [90.0, 90.0]
    day = textbook_ta.ta_fact(closes, slot='1230')
    week = textbook_ta.ta_fact(closes, slot='sat')
    assert day['method'] == 'sma_break_down', day
    assert day['vo_en'] == 'Price just lost the 50-day.'
    assert week['method'] == 'sma_below', week
    assert week['vo_en'] == "It's still trading below the 50-day."


def test_as_of_sessions_from_injected_bars():
    assert datetime(2026, 11, 11).weekday() == 2
    noon = datetime(2026, 11, 11, 12, 30, tzinfo=NY)
    after = datetime(2026, 11, 11, 16, 30, tzinfo=NY)
    early_clock = datetime(2026, 11, 11, 15, 0, tzinfo=NY)
    saturday = datetime(2026, 11, 14, 12, 0, tzinfo=NY)
    assert textbook_ta.expected_as_of('1230', noon).isoformat() == '2026-11-10'
    assert textbook_ta.expected_as_of('1630', after).isoformat() == '2026-11-11'
    assert textbook_ta.expected_as_of('1630', early_clock).isoformat() == '2026-11-10'
    assert textbook_ta.expected_as_of('sat', saturday).isoformat() == '2026-11-13'

    # Day after Thanksgiving: Thu 11-26 closed, Fri 11-27 early close (13:00 ET).
    tape = datetime(2026, 11, 27, 12, 30, tzinfo=NY)
    heat = datetime(2026, 11, 27, 16, 30, tzinfo=NY)
    assert textbook_ta.expected_as_of('1230', tape).isoformat() == '2026-11-25'
    assert textbook_ta.expected_as_of('1630', heat).isoformat() == '2026-11-27'

    bars = _dated('2026-11-11', 70, 100.0)
    bars[-2]['close'] = 100.0
    bars[-1]['close'] = 50.0  # incomplete Wednesday bar, must not be the Tape Take fact
    decision = _decision('1230', ['QQQ'], '2026-11-11')
    doc, _kept = textbook_ta.build_facts_doc(
        decision, {'QQQ': {'yahoo_symbol': 'QQQ', 'bars': bars}}, now=noon,
        fetched_hkt='2026-11-11 20:30')
    assert doc['spec'] == 'textbook-ta-v1'
    assert doc['slot'] == 'tape-take'
    assert doc['as_of'] == '2026-11-10'
    assert doc['as_of_session'] == 'regular close'
    assert doc['timezone'] == 'America/New_York'
    assert doc['source'] == 'Yahoo Finance'
    assert doc['fetched_hkt'] == '2026-11-11 20:30'
    row = doc['tickers'][0]
    assert row['emit'] is True
    assert row['last_close'] == 100.0
    assert row['last_close'] != 50.0
    assert set(doc) == {
        'spec', 'slot', 'as_of', 'as_of_session', 'timezone', 'source',
        'fetched_hkt', 'disclaimer', 'tickers',
    }
    assert set(row) == {
        'ticker', 'yahoo_symbol', 'emit', 'omit_reason', 'method', 'level_name',
        'level', 'last_close', 'vo_en', 'caption_en', 'on_screen',
    }

    heat_doc, _kept = textbook_ta.build_facts_doc(
        _decision('1630', ['QQQ'], '2026-11-11'),
        {'QQQ': {'yahoo_symbol': 'QQQ', 'bars': bars}}, now=after)
    assert heat_doc['as_of'] == '2026-11-11'
    assert heat_doc['slot'] == 'crowd-heat'
    assert heat_doc['tickers'][0]['last_close'] == 50.0

    stale_bars = _dated('2026-11-09', 70, 100.0)
    stale, _kept = textbook_ta.build_facts_doc(
        decision, {'QQQ': {'yahoo_symbol': 'QQQ', 'bars': stale_bars}}, now=noon)
    assert stale['tickers'][0]['emit'] is False
    assert stale['tickers'][0]['omit_reason'] == 'stale_bars'
    assert stale['tickers'][0]['vo_en'] == ''
    assert stale['tickers'][0]['last_close'] is None

    missing, _kept = textbook_ta.build_facts_doc(
        decision, {'QQQ': {'error': 'yahoo_unavailable'}}, now=noon)
    assert missing['tickers'][0]['omit_reason'] == 'yahoo_unavailable'
    assert missing['tickers'][0]['vo_en'] == ''
    assert missing['tickers'][0]['last_close'] is None
    assert missing['tickers'][0]['level'] is None


def test_facts_writer_injected_ohlcv_no_network():
    import update_prices
    noon = datetime(2026, 11, 11, 12, 30, tzinfo=NY)
    bars = _dated('2026-11-10', 80, 100.0)
    called = []

    def fetch(ticker):
        called.append(ticker)
        return {'yahoo_symbol': ticker, 'bars': bars}

    def _boom(*_a, **_k):
        raise AssertionError('Yahoo called')

    old = update_prices.chart_ohlcv
    update_prices.chart_ohlcv = _boom
    root = tempfile.mkdtemp(prefix='ta-facts-')
    try:
        decision = _decision('1230', ['QQQ'], '2026-11-11')
        doc = textbook_ta.publish_ta(decision, fetch=fetch, now=noon, root=root, pause=0)
    finally:
        update_prices.chart_ohlcv = old
    assert called == ['QQQ']
    assert doc['as_of'] == '2026-11-10'
    assert doc['tickers'][0]['emit'] is True
    assert doc['tickers'][0]['method'] == 'sma_touch'
    path = os.path.join(root, 'work', 'ta-facts.json')
    on_disk = json.load(open(path, encoding='utf-8'))
    assert on_disk['spec'] == 'textbook-ta-v1'
    assert on_disk['as_of'] == '2026-11-10'
    bars_doc = json.load(open(os.path.join(root, 'work', 'ta-bars.json'), encoding='utf-8'))
    stored = bars_doc['tickers']['QQQ']['bars']
    assert stored[-1]['date'] == '2026-11-10'
    assert {'date', 'open', 'high', 'low', 'close', 'volume'} <= set(stored[-1])
    assert not os.path.exists(os.path.join(root, 'px'))


def test_skip_does_not_invent_ta():
    decision = video_signal.select_weekday([cited('SPY', 12, 0, 0)])
    assert decision['publishable'] is False and decision['mode'] == 'skip'
    called = []
    root = tempfile.mkdtemp(prefix='ta-skip-')
    doc = textbook_ta.publish_ta(
        decision, fetch=lambda t: called.append(t), now=datetime(2026, 11, 11, 12, 30, tzinfo=NY),
        root=root, pause=0)
    assert doc is None
    assert called == []
    assert not os.path.exists(os.path.join(root, 'work', 'ta-facts.json'))
    juicy = [100.0] * 80
    beats = video_signal.script_beats(decision, closes_for=lambda _t: juicy)
    assert beats == []
    # A skipped show still leaves no publishable mp4 (existing gate). The juicy
    # closes above must not have been written out as a fact to save it.
    assert not any(os.path.basename(p).startswith('ta-facts') for p in os.listdir(root))


def test_resolve_symbol_matches_price_rules():
    def probe_factory(ok):
        def probe(sym):
            return sym in ok
        return probe

    assert textbook_ta.resolve_symbol(
        'VIX', probe=probe_factory({'^VIX'}), search_fn=lambda _t: (_ for _ in ()).throw(AssertionError('search'))) == '^VIX'

    searched = []

    def no_search(t):
        searched.append(t)
        return [{'symbol': 'WRONG', 'exchange': 'NYQ', 'quoteType': 'EQUITY'}]

    assert textbook_ta.resolve_symbol(
        'BRK.B', overrides={'BRK.B': {'symbol': 'BRK-B', 'confirmed': True}},
        probe=probe_factory({'BRK-B', 'BRK.B'}), search_fn=no_search) == 'BRK-B'
    assert searched == []

    assert textbook_ta.resolve_symbol(
        'FAKE', overrides={'FAKE': {'unconfirmed': True}},
        probe=probe_factory({'FAKE'}), search_fn=no_search) is None

    def search_brk(_t):
        return [
            {'symbol': 'BRK-B.SI', 'exchange': 'SES', 'quoteType': 'EQUITY'},
            {'symbol': 'BRK-B', 'exchange': 'NYQ', 'quoteType': 'EQUITY'},
        ]

    assert textbook_ta.resolve_symbol(
        'BRK', probe=probe_factory({'BRK-B'}), search_fn=search_brk) == 'BRK-B'

    assert textbook_ta.resolve_symbol(
        'SATS', probe=probe_factory(set()),
        search_fn=lambda _t: [{'symbol': 'SATS.SI', 'exchange': 'SES', 'quoteType': 'EQUITY'}]) is None

    assert textbook_ta.resolve_symbol(
        'AAPL', probe=probe_factory(set()), search_fn=lambda _t: None) is None


def test_forbidden_words_never_in_vo():
    samples = []
    samples.append(textbook_ta.ta_fact([100.0] * 60)['vo_en'])
    samples.append(textbook_ta.ta_fact([100.0] * 60 + [90.0])['vo_en'])
    samples.append(textbook_ta.ta_fact([float(50 + i) for i in range(40)])['vo_en'])
    samples.append(textbook_ta.ta_fact(_macd_up_closes())['vo_en'])
    day = video_signal.script_beats(
        video_signal.select_weekday([cited('QQQ', 8, 5, 3)]),
        closes_for=lambda _t: [100.0] * 60)
    samples.extend(b['vo'] for b in day)
    for text in samples:
        _assert_clean(text)
    for vo, cap in textbook_ta.PHRASES.values():
        _assert_clean(vo)
        _assert_clean(cap)
    _assert_clean(textbook_ta.SPOKEN_DISCLAIMER)
    _assert_clean(textbook_ta.SCREEN_DISCLAIMER)


def main():
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print('ok', name)


if __name__ == '__main__':
    main()
