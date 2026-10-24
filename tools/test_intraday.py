"""Intraday social slots: ET/HKT times, trading-day guard, X/Threads caps, live quotes.

Offline fixtures. Quote fetches are mocked. Run from the repo root:
  python3 tools/test_intraday.py
"""
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['WORK_DIR'] = tempfile.mkdtemp(prefix='intraday-test-')
os.environ['SOCIAL_HISTORY'] = os.path.join(os.environ['WORK_DIR'], 'social-history.json')
os.environ['SOCIAL_POSTS'] = os.path.join(os.environ['WORK_DIR'], 'social-posts.json')

import share  # noqa: E402
import intraday as intra  # noqa: E402
from utm import normalize_obj  # noqa: E402

NY = intra.NY
URL = 'https://thecrowdtape.com'
URL_RE = re.compile(r'https://thecrowdtape\.com[^\s)\]"\']*')
PCT_RE = re.compile(r'[+\-]?\d+(?:\.\d+)?%')
SUMMER = '2026-10-23'
WINTER = '2026-11-03'
TS = int(datetime(2026, 10, 23, 11, 0, tzinfo=NY).timestamp())


def _row(t, nb=None, nr=None, n_posts=1, acc='acct'):
    row = {'t': t, 'n_posts': n_posts, 'rows': [{'acc': acc, 's': 'bull' if nb else 'bear'}]}
    if nb is not None:
        row['nb'] = nb
    if nr is not None:
        row['nr'] = nr
    return row


def _daily():
    return {
        'bull': [
            _row('NVDA', nb=8, nr=1, n_posts=12, acc='leadbull'),
            _row('RSP', nb=3, nr=0, n_posts=4, acc='rspacc'),
            _row('XLV', nb=2, nr=0, n_posts=3, acc='xlvacc'),
        ],
        'bear': [
            _row('QQQ', nb=0, nr=5, n_posts=10, acc='leadbear'),
            _row('MRNA', nb=0, nr=4, n_posts=8, acc='mrnaacc'),
        ],
        'split': [
            _row('SPCX', nb=4, nr=3, n_posts=11, acc='chamath'),
        ],
    }


def _chart(sym):
    px = {
        'SPY': (670.12, 668.0),
        'QQQ': (598.4, 610.0),
        'DIA': (461.2, 459.0),
        'NVDA': (182.0, 178.3),
        'RSP': (190.1, 189.0),
        'XLV': (140.0, 139.0),
        'MRNA': (24.0, 30.0),
        'SPCX': (90.0, 88.0),
    }
    price, prev = px.get(sym, (100.0, 99.0))
    return {'regularMarketPrice': price, 'previousClose': prev, 'regularMarketTime': TS}, []


def _fail_indexes(sym):
    if sym in intra.INDEXES:
        return None
    return _chart(sym)


def _quotes(chart_fn=_chart):
    tickers = list(intra.INDEXES) + ['NVDA', 'RSP', 'XLV', 'QQQ', 'MRNA', 'SPCX']
    return intra.fetch_live_quotes(tickers, chart_fn=chart_fn, sleep=0)


def _slot(name='intraday_1', date=SUMMER, chart_fn=_chart, sp=None, history=None, existing=None):
    quotes, quote_time, ok = _quotes(chart_fn)
    now = datetime(int(date[:4]), int(date[5:7]), int(date[8:10]), 10, 50, tzinfo=NY)
    return intra.build_slot(
        name, date, now, _daily(), quotes, quote_time, ok, {'days': {}}, existing or {},
        history=history or {}, sp=sp or {},
    )


def test_hkt_summer_winter():
    # 2026-10-23 is EDT (ET+12 HKT). 2026-11-03 is EST after 11/2 (ET+13 HKT).
    # KST is HKT+1, so slots from 11:00 ET land on the next Seoul date.
    expect_summer = {
        'intraday_open': '21:45',
        'intraday_1': '23:00',
        'intraday_2': '00:15',
        'intraday_3': '01:30',
        'intraday_4': '02:45',
        'intraday_close': '03:40',
    }
    expect_winter = {
        'intraday_open': '22:45',
        'intraday_1': '00:00',
        'intraday_2': '01:15',
        'intraday_3': '02:30',
        'intraday_4': '03:45',
        'intraday_close': '04:40',
    }
    expect_gen = {
        'intraday_open': (9, 40),
        'intraday_1': (10, 55),
        'intraday_2': (12, 10),
        'intraday_3': (13, 25),
        'intraday_4': (14, 40),
        'intraday_close': (15, 35),
    }
    kst_summer = {
        'intraday_open': '2026-10-23',
        'intraday_1': '2026-10-24',
        'intraday_2': '2026-10-24',
        'intraday_3': '2026-10-24',
        'intraday_4': '2026-10-24',
        'intraday_close': '2026-10-24',
    }
    kst_winter = {
        'intraday_open': '2026-11-03',
        'intraday_1': '2026-11-04',
        'intraday_2': '2026-11-04',
        'intraday_3': '2026-11-04',
        'intraday_4': '2026-11-04',
        'intraday_close': '2026-11-04',
    }
    assert intra.GEN_LEAD_MIN == 5
    for name, hour, minute in intra.SLOT_DEFS:
        assert intra.hkt_hhmm(intra.post_dt(SUMMER, hour, minute)) == expect_summer[name], name
        assert intra.hkt_hhmm(intra.post_dt(WINTER, hour, minute)) == expect_winter[name], name
        gen = intra.gen_dt(SUMMER, hour, minute)
        assert (gen.hour, gen.minute) == expect_gen[name], name
        assert (intra.gen_dt(WINTER, hour, minute).hour, intra.gen_dt(WINTER, hour, minute).minute) == expect_gen[name]
        sl = _slot(name, SUMMER)
        assert sl['post_et'] == f'{hour:02d}:{minute:02d}'
        assert sl['post_hkt'] == expect_summer[name]
        assert sl['date'] == SUMMER
        assert sl['date_kst'] == kst_summer[name], name
        winter = _slot(name, WINTER)
        assert winter['date'] == WINTER
        assert winter['date_kst'] == kst_winter[name], name
    # intraday_3 2026-10-23 13:30 ET is the next Seoul day, not the US date.
    assert intra.date_kst.et_post_date_kst('2026-10-23', '13:30') == '2026-10-24'


def test_guard_weekend_holiday_early_close():
    holidays = intra.load_holidays()
    sat = datetime(2026, 10, 24, 9, 40, tzinfo=NY)
    ok, slot, reason = intra.evaluate_guard(sat, 'auto', holidays=holidays)
    assert not ok and slot is None, reason

    thanks = datetime(2026, 11, 26, 9, 40, tzinfo=NY)
    ok, slot, reason = intra.evaluate_guard(thanks, 'auto', holidays=holidays)
    assert not ok, reason
    assert not intra.is_trading_day('2026-11-26', holidays)
    assert not intra.is_trading_day('2026-12-25', holidays)

    # Early close: skip slots after 13:00 ET (3, 4, close). 12:15 still runs.
    assert intra.is_early_close('2026-11-27', holidays)
    assert intra.slot_permitted('2026-11-27', 'intraday_2', holidays)
    assert not intra.slot_permitted('2026-11-27', 'intraday_3', holidays)
    assert not intra.slot_permitted('2026-11-27', 'intraday_close', holidays)
    early_mid = datetime(2026, 11, 27, 12, 10, tzinfo=NY)
    ok, slot, reason = intra.evaluate_guard(early_mid, 'auto', holidays=holidays)
    assert ok and slot == 'intraday_2', (ok, slot, reason)
    early_late = datetime(2026, 11, 27, 13, 25, tzinfo=NY)
    ok, slot, reason = intra.evaluate_guard(early_late, 'auto', holidays=holidays)
    assert not ok, reason

    # Friday open generation time is 09:40 ET, five minutes before the 09:45 post.
    fri = datetime(2026, 10, 23, 9, 40, tzinfo=NY)
    ok, slot, reason = intra.evaluate_guard(fri, 'auto', holidays=holidays)
    assert ok and slot == 'intraday_open', (ok, slot, reason)
    too_early = datetime(2026, 10, 23, 9, 0, tzinfo=NY)
    ok, slot, reason = intra.evaluate_guard(too_early, 'auto', holidays=holidays)
    assert not ok, reason
    # A named slot does not re-check the clock. Guard already resolved it.
    ok, slot, reason = intra.evaluate_guard(too_early, 'intraday_open', holidays=holidays)
    assert ok and slot == 'intraday_open', (ok, slot, reason)

    # force bypasses the time guard and still writes a slot.
    ok, slot, reason = intra.evaluate_guard(thanks, 'force', holidays=holidays)
    assert ok and slot in intra.SLOT_NAMES, (ok, slot, reason)


def test_x_en_only_and_length():
    sl = _slot('intraday_open')
    assert set(sl['x']) == {'en'}
    assert 'zh' not in sl['x'] and 'ko' not in sl['x'] and 'kr' not in sl['x']
    text = sl['x']['en']['text']
    assert share.xlen(text) <= 280
    assert sl['x']['en']['url']
    assert 'utm_source=x' in sl['x']['en']['url']
    assert 'utm_medium=social' in sl['x']['en']['url']
    assert 'utm_campaign=intraday_open' in sl['x']['en']['url']
    assert '/en/' in sl['x']['en']['url']
    assert share.SHORT['en']['disc'] in text
    assert 'facebook' not in sl
    assert 'facebook' not in sl.get('has_link', {})


def test_threads_caps_lang_links_utm_and_half():
    linked = 0
    total = 0
    for date in (SUMMER, WINTER):
        for name in intra.SLOT_NAMES:
            sl = _slot(name, date)
            assert set(sl['threads']) == {'zh', 'en', 'ko'}
            assert 'kr' not in sl['threads']
            take = intra.threads_take_link(date, name)
            for lang in share.LANGS:
                node = sl['threads'][lang]
                text = node['text']
                assert len(text) <= 500, (name, lang, len(text))
                assert share.SHORT[lang]['disc'] in text
                total += 1
                urls = URL_RE.findall(text)
                if take:
                    linked += 1
                    assert node['url']
                    assert urls, (name, lang, text)
                    for u in urls:
                        path = u.split('thecrowdtape.com', 1)[1]
                        assert path.startswith(f'/{lang}/'), (lang, u)
                        assert f'utm_source=threads' in u
                        assert 'utm_medium=social' in u
                        assert f'utm_campaign={name}' in u
                    assert f'/{lang}/' in node['url']
                    assert f'utm_campaign={name}' in node['url']
                else:
                    assert not node['url']
                    assert not urls, (name, lang, text)
    assert total == 36
    assert linked == total // 2 == 18, (linked, total)


def test_fallback_no_pct_and_quotes_shape():
    ok_quotes, ok_time, ok_flag = _quotes(_chart)
    assert ok_flag
    for t in intra.INDEXES:
        q = ok_quotes[t]
        assert set(q) >= {'price', 'prev_close', 'chg_pct', 'time'}
        assert isinstance(q['price'], float)
        assert isinstance(q['chg_pct'], float)
        assert isinstance(q['time'], str) and 'T' in q['time']
    assert ok_time and 'et' in ok_time and 'hkt' in ok_time

    sl = _slot('intraday_1', chart_fn=_fail_indexes)
    assert sl['quotes_ok'] is False
    assert sl['fallback'] is True
    assert sl['quote_source'] == 'Yahoo Finance'
    for blob in (sl['x']['en']['text'], *(sl['threads'][lang]['text'] for lang in share.LANGS)):
        assert PCT_RE.search(blob) is None, blob
        assert '%' not in blob
        assert 'NVDA' in blob or 'RSP' in blob or 'QQQ' in blob or 'XLV' in blob
    assert any(h['ticker'] for h in sl['hot'])

    good = _slot('intraday_1', chart_fn=_chart)
    assert good['quotes_ok'] is True
    assert good['fallback'] is False
    assert PCT_RE.search(good['x']['en']['text'])
    assert 'accounts bullish on site' in good['x']['en']['text'] or 'accounts bearish on site' in good['x']['en']['text']
    et, hkt = _quote_clocks(good['quote_time'])
    assert f'As of {et} ET ({hkt} HKT)' in good['x']['en']['text']
    nvda = next((h for h in good['hot'] if h['ticker'] == 'NVDA'), None)
    if nvda:
        assert nvda['bull'] == 8
        assert isinstance(nvda['accounts'], list)

    # Indexes missing: no quote clock. Say site data as of the writeup snapshot, not the slot time.
    stamp = intra.writeup_generated_hkt()
    assert stamp
    assert f'Site data as of {stamp}' in sl['x']['en']['text']
    assert f'網站數據截至 {stamp}' in sl['threads']['zh']['text']
    assert f'사이트 데이터 {stamp} 기준' in sl['threads']['ko']['text']
    q_et, q_hkt = _quote_clocks(sl['quote_time'])
    for blob in (sl['x']['en']['text'], *(sl['threads'][lang]['text'] for lang in share.LANGS)):
        assert f'As of {q_et}' not in blob
        assert f'{q_et} ET' not in blob
        assert f'{q_hkt} HKT' not in blob
        assert sl['post_et'] not in blob
        assert stamp in blob


def test_no_repeated_x_and_merge():
    data = {
        'date': SUMMER,
        'posts': {'en': {'x': 'keep me'}},
        'top5': {'bull': [{'t': 'RSP'}]},
    }
    history, sp, existing = {}, {'intraday': {'date': SUMMER, 'slots': {}}}, {}
    seen = set()
    for name in intra.SLOT_NAMES:
        sl = intra.build_slot(
            name, SUMMER, datetime(2026, 10, 23, 15, 30, tzinfo=NY), _daily(),
            _quotes(_chart)[0], _quotes(_chart)[1], True, {'days': {}}, existing,
            history=history, sp=sp,
        )
        text = share._norm_text(sl['x']['en']['text'])
        assert text not in seen, (name, text)
        seen.add(text)
        intra.merge_intraday(data, SUMMER, name, sl, sl['generated_at'], '2026-10-23 03:30')
        intra.remember_intraday(history, SUMMER, name, sl)
        existing = data['intraday']['slots']
        sp = data
    assert data['posts']['en']['x'] == 'keep me'
    assert data['top5']['bull'][0]['t'] == 'RSP'
    assert set(data['intraday']['slots']) == set(intra.SLOT_NAMES)

    # Date change resets slots and leaves other top-level keys.
    later = _slot('intraday_open', WINTER)
    intra.merge_intraday(data, WINTER, 'intraday_open', later, later['generated_at'], '2026-11-03 22:35')
    assert data['intraday']['date'] == WINTER
    assert list(data['intraday']['slots']) == ['intraday_open']
    assert data['posts']['en']['x'] == 'keep me'

    # Same X text is varied on a second pass via history.
    first = _slot('intraday_close', SUMMER, sp=sp, history=history, existing=existing)
    again = _slot('intraday_close', SUMMER, sp={'intraday': {'date': SUMMER, 'slots': {'intraday_close': first}}},
                  history=history, existing={'intraday_close': first})
    # Rebuild with the first text recorded: variant/ticker rotation should differ or still be valid X.
    assert share.xlen(again['x']['en']['text']) <= 280
    assert set(again['x']) == {'en'}


def test_utm_normalize_intraday():
    sl = _slot('intraday_open')
    data = {'intraday': {'date': SUMMER, 'slots': {'intraday_open': sl}}}
    normalize_obj(data)
    x = data['intraday']['slots']['intraday_open']['x']['en']
    assert 'utm_source=x&utm_medium=social&utm_campaign=intraday_open' in (x['url'] or '')
    th = data['intraday']['slots']['intraday_open']['threads']
    for lang in share.LANGS:
        if th[lang]['url']:
            assert f'utm_source=threads&utm_medium=social&utm_campaign=intraday_open' in th[lang]['url']
            assert f'/{lang}/' in th[lang]['url']
        assert len(th[lang]['text']) <= 500


def _quote_clocks(quote_time):
    """HH:MM ET and HH:MM HKT taken straight from a quote_time record."""
    et = str(quote_time['et']).split('T', 1)[1][:5]
    hkt = str(quote_time['hkt']).strip()[-5:]
    return et, hkt


def test_text_time_equals_quote_time():
    # 10:37 ET is not a slot post time (intraday_1 posts at 11:00 / 23:00).
    when = datetime(2026, 10, 23, 10, 37, tzinfo=NY)
    ts = int(when.timestamp())

    def chart(sym):
        meta, rest = _chart(sym)
        meta = dict(meta)
        meta['regularMarketTime'] = ts
        return meta, rest

    sl = _slot('intraday_1', chart_fn=chart)
    et, hkt = _quote_clocks(sl['quote_time'])
    assert et == '10:37' and hkt == intra.hkt_hhmm(when)
    assert (et, hkt) != (sl['post_et'], sl['post_hkt'])
    phrases = {
        'en': f'As of {et} ET ({hkt} HKT)',
        'zh': f'截至 {et} ET（{hkt} HKT）',
        'ko': f'{et} ET ({hkt} HKT) 기준',
    }
    blobs = {'en': [sl['x']['en']['text'], sl['threads']['en']['text']]}
    blobs['zh'] = [sl['threads']['zh']['text']]
    blobs['ko'] = [sl['threads']['ko']['text']]
    for lang, texts in blobs.items():
        for text in texts:
            assert phrases[lang] in text
            assert sl['post_et'] not in text
            assert sl['post_hkt'] not in text

    # No quotes at all: every text names the writeup snapshot, not the slot post time.
    bare = intra.build_slot(
        'intraday_open', SUMMER, datetime(2026, 10, 23, 9, 35, tzinfo=NY), _daily(),
        {}, None, False, {'days': {}}, {},
    )
    stamp = intra.writeup_generated_hkt()
    assert bare['fallback'] is True and bare['quote_time'] is None
    assert f'Site data as of {stamp}' in bare['x']['en']['text']
    assert f'Site data as of {stamp}' in bare['threads']['en']['text']
    assert f'網站數據截至 {stamp}' in bare['threads']['zh']['text']
    assert f'사이트 데이터 {stamp} 기준' in bare['threads']['ko']['text']
    for blob in (bare['x']['en']['text'], *(bare['threads'][lang]['text'] for lang in share.LANGS)):
        assert bare['post_et'] not in blob
        assert bare['post_hkt'] not in blob
        assert ' ET' not in blob


def test_merge_from_keeps_same_day_and_appends_history():
    """--merge-from applies one slot onto the latest file and does not fetch quotes."""
    open_sl = _slot('intraday_open')
    slot = _slot('intraday_1')
    later = _slot('intraday_open', WINTER)
    path = intra.write_slot_file('intraday_1', SUMMER, slot, slot['generated_at'], '2026-10-23 22:50')
    assert os.path.basename(path) == 'intraday-slot.json'
    base = {
        'date': SUMMER,
        'posts': {'en': {'x': 'keep me'}},
        'intraday': {
            'date': SUMMER,
            'generated_at': open_sl['generated_at'],
            'generated_hkt': '2026-10-23 21:35',
            'slots': {'intraday_open': open_sl},
        },
    }
    with open(intra.posts_path(), 'w', encoding='utf-8') as f:
        json.dump(base, f)
    share.save_social_history({
        SUMMER: {'hot_stock': ['SPCX'], 'intraday_x': ['already there']},
    })
    calls = []
    orig = intra.fetch_live_quotes

    def boom(*_a, **_k):
        calls.append(1)
        raise AssertionError('merge-from must not fetch quotes')

    intra.fetch_live_quotes = boom
    try:
        assert intra.main(['--merge-from', path, '--slot', 'force']) == 0
        assert calls == []
        saved = json.load(open(intra.posts_path(), encoding='utf-8'))
        assert set(saved['intraday']['slots']) == {'intraday_open', 'intraday_1'}
        assert saved['intraday']['date'] == SUMMER
        assert saved['intraday']['date_kst'] == '2026-10-23'
        assert saved['intraday']['slots']['intraday_open']['date_kst'] == '2026-10-23'
        assert saved['intraday']['slots']['intraday_1']['date'] == SUMMER
        assert saved['intraday']['slots']['intraday_1']['date_kst'] == '2026-10-24'
        assert saved['posts']['en']['x'] == 'keep me'
        hist = share.load_social_history()
        norm = share._norm_text(slot['x']['en']['text'])
        assert hist[SUMMER]['hot_stock'] == ['SPCX']
        assert 'already there' in hist[SUMMER]['intraday_x']
        assert norm in hist[SUMMER]['intraday_x']
        assert hist[SUMMER]['intraday_1']
        # A second merge appends nothing when that X body is already stored.
        assert intra.main(['--merge-from', path]) == 0
        hist = share.load_social_history()
        assert hist[SUMMER]['intraday_x'].count(norm) == 1
        # A new ET date resets slots and leaves the rest of the file.
        later_path = os.path.join(os.environ['WORK_DIR'], 'winter-slot.json')
        intra.write_slot_file(
            'intraday_open', WINTER, later, later['generated_at'], '2026-11-03 22:35', path=later_path)
        assert intra.main(['--merge-from', later_path]) == 0
        saved = json.load(open(intra.posts_path(), encoding='utf-8'))
        assert saved['intraday']['date'] == WINTER
        assert saved['intraday']['date_kst'] == '2026-11-03'
        assert saved['intraday']['slots']['intraday_open']['date_kst'] == '2026-11-03'
        assert list(saved['intraday']['slots']) == ['intraday_open']
        assert saved['posts']['en']['x'] == 'keep me'
        hist = share.load_social_history()
        assert share._norm_text(later['x']['en']['text']) in hist[WINTER]['intraday_x']
        missing = os.path.join(os.environ['WORK_DIR'], 'missing-slot.json')
        try:
            intra.merge_from_file(missing)
            raise AssertionError('missing slot file should fail')
        except SystemExit:
            pass
        bad = os.path.join(os.environ['WORK_DIR'], 'bad-slot.json')
        with open(bad, 'w', encoding='utf-8') as f:
            json.dump({'slot': 'nope', 'date': SUMMER, 'entry': {}}, f)
        try:
            intra.main(['--merge-from', bad])
            raise AssertionError('unknown slot should fail')
        except SystemExit:
            pass
        assert calls == []
    finally:
        intra.fetch_live_quotes = orig


def test_generate_writes_slot_file():
    now = datetime(2026, 10, 23, 10, 55, tzinfo=NY)
    saved = intra.generate('auto', now=now, chart_fn=_chart, sleep=0, save=True)
    assert saved and saved['post_et'] == '11:00'
    payload = json.load(open(intra.slot_file_path(), encoding='utf-8'))
    assert payload['slot'] == 'intraday_1'
    assert payload['date'] == SUMMER
    assert payload['generated_at'] == saved['generated_at']
    assert payload['entry']['post_et'] == '11:00'
    assert payload['entry']['date_kst'] == '2026-10-24'
    assert saved['date'] == SUMMER
    assert saved['date_kst'] == '2026-10-24'
    assert payload['entry']['x']['en']['text']
    on_disk = json.load(open(intra.posts_path(), encoding='utf-8'))
    assert 'intraday_1' in on_disk['intraday']['slots']
    assert on_disk['intraday']['slots']['intraday_1']['date_kst'] == '2026-10-24'


def test_auto_dispatch_around_generation():
    """External dispatch ±10 min from each generation time picks that slot.

    Checked in EDT (2026-10-23) and EST (2026-11-03), including the same instant
    expressed in UTC. Weekends, Thanksgiving, and early-close slots after 13:00 ET
    are rejected. ±20 is inside the guard; ±21 is not, and does not snap to a neighbor.
    """
    holidays = intra.load_holidays()
    offsets = (-10, -5, 0, 5, 10)
    seasons = (
        (SUMMER, timedelta(hours=-4)),
        (WINTER, timedelta(hours=-5)),
    )
    for day, offset in seasons:
        noon = datetime(int(day[:4]), int(day[5:7]), int(day[8:10]), 12, 0, tzinfo=NY)
        assert noon.utcoffset() == offset, (day, noon.utcoffset())
        for name, hour, minute in intra.SLOT_DEFS:
            gen = intra.gen_dt(day, hour, minute)
            assert gen.utcoffset() == offset, (day, name, gen.utcoffset())
            for off in offsets:
                now = gen + timedelta(minutes=off)
                ok, slot, reason = intra.evaluate_guard(now, 'auto', holidays=holidays)
                assert ok and slot == name, (day, name, off, ok, slot, reason)
                utc = now.astimezone(timezone.utc)
                ok_u, slot_u, reason_u = intra.evaluate_guard(utc, 'auto', holidays=holidays)
                assert ok_u and slot_u == name, (day, name, off, utc.isoformat(), ok_u, slot_u, reason_u)
        # Window edge. Open and close are the ends; close's −21 stays clear of slot 4.
        for post_h, post_m, slot_name in ((9, 45, 'intraday_open'), (15, 40, 'intraday_close')):
            gen = intra.gen_dt(day, post_h, post_m)
            for off in (-20, 20):
                ok, slot, reason = intra.evaluate_guard(gen + timedelta(minutes=off), 'auto', holidays=holidays)
                assert ok and slot == slot_name, (day, slot_name, off, ok, slot, reason)
            for off in (-21, 21):
                ok, slot, reason = intra.evaluate_guard(gen + timedelta(minutes=off), 'auto', holidays=holidays)
                assert not ok and slot is None, (day, slot_name, off, ok, slot, reason)

    # 10:20 ET sits between open (09:40) and intraday_1 (10:55).
    gap = datetime(2026, 10, 23, 10, 20, tzinfo=NY)
    ok, slot, reason = intra.evaluate_guard(gap, 'auto', holidays=holidays)
    assert not ok and slot is None, (ok, slot, reason)

    for y, mo, d in ((2026, 10, 24), (2026, 10, 25)):
        # Saturday and Sunday, at the open generation clock.
        for off in offsets:
            now = datetime(y, mo, d, 9, 40, tzinfo=NY) + timedelta(minutes=off)
            ok, slot, reason = intra.evaluate_guard(now, 'auto', holidays=holidays)
            assert not ok and slot is None, (y, mo, d, off, ok, slot, reason)

    for name, hour, minute in intra.SLOT_DEFS:
        gen = intra.gen_dt('2026-11-26', hour, minute)
        for off in offsets:
            ok, slot, reason = intra.evaluate_guard(gen + timedelta(minutes=off), 'auto', holidays=holidays)
            assert not ok and slot is None, ('holiday', name, off, ok, slot, reason)

    early = '2026-11-27'
    skipped = {'intraday_3', 'intraday_4', 'intraday_close'}
    for name, hour, minute in intra.SLOT_DEFS:
        gen = intra.gen_dt(early, hour, minute)
        for off in offsets:
            now = gen + timedelta(minutes=off)
            ok, slot, reason = intra.evaluate_guard(now, 'auto', holidays=holidays)
            if name in skipped:
                assert not ok and slot is None, (name, off, ok, slot, reason)
                ok_n, slot_n, reason_n = intra.evaluate_guard(now, name, holidays=holidays)
                assert not ok_n and slot_n is None, (name, off, ok_n, slot_n, reason_n)
            else:
                assert ok and slot == name, (name, off, ok, slot, reason)


def test_auto_pick():
    holidays = intra.load_holidays()
    now = datetime(2026, 10, 23, 9, 40, tzinfo=NY)
    assert intra.pick_auto_slot(now, holidays) == 'intraday_open'
    now = datetime(2026, 10, 23, 10, 55, tzinfo=NY)
    assert intra.pick_auto_slot(now, holidays) == 'intraday_1'
    now = datetime(2026, 10, 23, 15, 35, tzinfo=NY)
    assert intra.pick_auto_slot(now, holidays) == 'intraday_close'


def main():
    test_hkt_summer_winter()
    test_guard_weekend_holiday_early_close()
    test_x_en_only_and_length()
    test_threads_caps_lang_links_utm_and_half()
    test_fallback_no_pct_and_quotes_shape()
    test_text_time_equals_quote_time()
    test_no_repeated_x_and_merge()
    test_utm_normalize_intraday()
    test_merge_from_keeps_same_day_and_appends_history()
    test_generate_writes_slot_file()
    test_auto_dispatch_around_generation()
    test_auto_pick()
    print('test_intraday: schedule, guard, X/Threads, quotes, fallback, history, merge-from ok')


if __name__ == '__main__':
    main()
