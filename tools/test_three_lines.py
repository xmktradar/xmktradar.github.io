"""Today-in-3-lines social post: same lines as the homepage, three languages, four platforms.

Run from the repo root: python3 tools/test_three_lines.py
"""
import os
import re
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['WORK_DIR'] = tempfile.mkdtemp(prefix='three-lines-test-')
os.environ['SOCIAL_HISTORY'] = os.path.join(os.environ['WORK_DIR'], 'social-history.json')

import share  # noqa: E402
import three_why  # noqa: E402
from sitedata import HK  # noqa: E402

DAY = '2026-10-23'
URL_RE = re.compile(r'https?://', re.I)
HASH = re.compile(r'#[^\s#]+')
TICK_TAG = re.compile(r'#([A-Z]{1,6})\b')
WIN_RE = re.compile(r'^\d\d/\d\d \d\d:\d\d – \d\d:\d\d HKT$')


def _c(bull, bear, neu, accs, mentions):
    return {'bull': bull, 'bear': bear, 'neu': neu, 'none': 0, 'accs': accs, 'mentions': mentions}


def test_three_lines_calc_matches_page():
    rows = [
        {'t': 'A', 'c': _c(3, 0, 0, 3, 3), 'c0': _c(0, 2, 0, 2, 2), 'chg': 0},
        {'t': 'B', 'c': _c(3, 3, 1, 8, 9), 'c0': _c(3, 3, 1, 7, 7), 'chg': 1},
        {'t': 'C', 'c': _c(1, 1, 0, 2, 2), 'c0': None, 'chg': 0},
    ]
    got = share.three_lines_calc(rows, True)
    assert got['shift']['t'] == 'A' and got['shift']['kind'] == 'delta'
    assert got['most']['t'] == 'B' and got['most']['n'] == 9
    assert got['split']['t'] == 'B'
    # No previous window: no invented shift, no split when the row is one-sided.
    bare = share.three_lines_calc([{'t': 'A', 'c': _c(1, 0, 0, 1, 1), 'c0': None, 'chg': 0}], False)
    assert bare['shift'] is None and bare['split'] is None and bare['most']['t'] == 'A'
    assert share.three_lines_calc([], False) == {'shift': None, 'most': None, 'split': None}
    # Ties keep the earlier row (strict >).
    tie = share.three_lines_calc([
        {'t': 'A', 'c': _c(2, 2, 0, 4, 5), 'c0': None, 'chg': 0},
        {'t': 'B', 'c': _c(2, 2, 0, 4, 5), 'c0': None, 'chg': 0},
    ], False)
    assert tie['most']['t'] == 'A' and tie['split']['t'] == 'A'
    # JS Math.round, halves toward +infinity.
    assert three_why._pct(0.5) == '+50%'
    assert three_why._pct(-0.005) == '0%'
    assert three_why._pct(1) == '+100%'
    assert three_why._pct(-1) == '-100%'


def test_clause_for():
    assert three_why.clause_for('$AAPL 財報強。$MSFT 估值合理。', 'TSLA') == ''
    hit = three_why.clause_for('$AAPL 財報強。$MSFT 估值合理。', 'MSFT')
    assert '$MSFT' in hit and '$AAPL' not in hit
    assert three_why.clause_for('NVDA 財報勝預期，數據中心營收大增。', 'NVDA') == 'NVDA 財報勝預期，數據中心營收大增。'
    assert 'earnings' in three_why.clause_for('@x says $NVDA earnings will crush estimates, adding more.', 'NVDA')


def _ms(hm):
    return int(datetime.strptime(f'2026-10-23 {hm}', '%Y-%m-%d %H:%M').replace(tzinfo=HK).timestamp() * 1000)


def _post(day, hm, handle, tickers, stance):
    return {
        'handle': handle,
        'time_utc': f'{day}T{hm}:00+08:00',
        'time_hkt': f'{day} {hm}',
        'tickers': tickers,
        'stance': stance,
        'theme': '個股',
    }


def test_site_rows_follow_the_daily_tab():
    dash = {
        'meta': {'min_daily_posts': 1, 'cutoff_hkt': '2026-10-23T18:31:33+08:00'},
        'summaries': {'daily': [{'date': DAY, 'win': None}]},
        'tracked': {'categories': [], 'accounts': []},
        'posts': [
            _post('2026-10-22', '10:00', 'a', ['AAA'], '睇淡'),
            _post('2026-10-22', '11:00', 'b', ['AAA'], '睇淡'),
            _post(DAY, '09:00', 'a', ['AAA'], '睇好'),
            _post(DAY, '09:10', 'b', ['AAA'], '睇好'),
            _post(DAY, '09:20', 'c', ['BBB'], '睇好'),
            _post(DAY, '09:30', 'd', ['BBB'], '睇淡'),
            _post(DAY, '09:55', 'e', ['CCC'], '中性'),
        ],
    }
    rows, has_prev, sample, window = three_why.site_rows(dash, DAY)
    assert has_prev is True
    assert sample == {'posts': 5, 'accounts': 5}
    assert window == '10/23 00:00 – 09:55 HKT'
    by = {r['t']: r for r in rows}
    assert by['AAA']['c']['bull'] == 2 and by['AAA']['c']['bear'] == 0
    assert by['AAA']['c0']['bear'] == 2
    calc = share.three_lines_calc(rows, has_prev)
    assert calc['shift']['t'] == 'AAA' and calc['shift']['kind'] == 'delta'
    assert calc['most']['t'] == 'AAA'
    assert calc['split']['t'] == 'BBB'
    # An ISO cutoff already carries an offset, so the page skips the scrape cycle.
    assert three_why._js_parse_mangled_cutoff('2026-10-23T18:31:33+08:00') is None


def _daily():
    return {
        'from': '2026-10-23T00:00',
        'to': '2026-10-23T23:59',
        'posts': 12,
        'accounts': 4,
        'bull': [{
            't': 'NVDA', 'nb': 2, 'nr': 0, 'n_posts': 4,
            'rows': [{
                'acc': 'alpha', 's': 'bull', 'why': 'NVDA 財報勝預期，數據中心營收大增。',
                'ms': _ms('09:00'),
            }],
        }],
        'bear': [{
            't': 'QQQ', 'nb': 0, 'nr': 3, 'n_posts': 3,
            'rows': [{
                'acc': 'beta', 's': 'bear', 'why': 'https://example.com/x 覺得 QQQ 走勢弱',
                'ms': _ms('09:55'),
            }],
        }],
        'split': [{
            't': 'SPCX', 'nb': 2, 'nr': 2, 'n_posts': 5,
            'rows': [
                {'acc': 'gam', 's': 'bull', 'why': '$SPCX 催化。$MSFT 估值合理。', 'ms': _ms('09:20')},
                {'acc': 'dee', 's': 'bear', 'why': 'SPCX 估值太貴。', 'ms': _ms('09:40')},
                {'acc': 'nope', 'why': '$AAPL 財報強。$MSFT 估值合理。', 'ms': _ms('09:50')},
            ],
        }],
    }


def _texts(slot):
    out = []
    for plat in ('x', 'threads', 'facebook', 'instagram'):
        block = slot[plat]
        for lang in share.LANGS:
            entry = block[lang]
            text = entry['text'] if isinstance(entry, dict) else entry
            out.append((plat, lang, text, entry.get('url') if isinstance(entry, dict) else None))
    return out


def test_post_shape_limits_and_utm():
    slot = share.build_three_lines(_daily(), DAY)
    assert slot['date'] == DAY
    assert slot['date_kst'] == DAY
    assert slot['suggested_kst'] == '08:30'
    assert slot['format'] == 'text_question'
    assert slot['generated_at'].endswith('+08:00')
    assert WIN_RE.match(slot['window']), slot['window']
    assert slot['sample'] == {'posts': 12, 'accounts': 4}
    assert set(slot['x']) == set(slot['threads']) == set(slot['facebook']) == set(slot['instagram']) == set(share.LANGS)
    assert 'kr' not in slot['x']
    # Writeup fallback has no previous window, so the shift line is not invented.
    assert '共識變化最大' not in slot['threads']['zh']['text']
    assert 'Biggest consensus shift' not in slot['threads']['en']['text']
    linked = 0
    for plat, lang, text, url in _texts(slot):
        assert slot['window'] in text, (plat, lang)
        assert '12' in text and '4' in text
        assert share.SHORT[lang]['disc'] in text
        if plat == 'x':
            assert share.xlen(text) <= 280, (lang, share.xlen(text), text)
        if plat == 'threads':
            assert len(text) <= 500, (lang, len(text))
            assert URL_RE.search(text) is None
        if plat == 'instagram':
            assert 'url' not in slot['instagram'][lang]
            assert url is None
            assert URL_RE.search(text) is None
            assert 'thecrowdtape.com' not in text.lower()
            bios = [ln.strip() for ln in text.splitlines() if ln.strip() in share.IG_BIO.values()]
            assert bios == [share.IG_BIO[lang]], (lang, bios)
            tags = HASH.findall(text)
            assert share.IG_MIN_TAGS <= len(tags) <= share.IG_MAX_TAGS, tags
            assert len(TICK_TAG.findall(text)) <= 2
            assert slot['has_link']['instagram'][lang] is False
        else:
            if url:
                linked += 1 if plat in ('x', 'threads') else 0
                assert f'/{lang}/' in url
                assert f'utm_source={plat}&utm_medium=social&utm_campaign=three_lines' in url
                assert '/stock/' not in url
            if plat == 'facebook':
                assert url and url in text
                assert slot['has_link']['facebook'][lang] is True
    # X links every language. Threads still alternates: en only. 4 of the 6 copies.
    assert linked == 4, linked
    _assert_x_and_threads(slot, shift=False)
    en = slot['threads']['en']['text']
    assert 'Today in 3 lines' in en
    assert 'Most mentioned' in en and '$SPCX' in en
    assert 'Biggest disagreement' in en
    assert 'Not enough data' not in en
    zh = slot['threads']['zh']['text']
    assert '今日三句重點' in zh and '最多人討論' in zh and '分歧最大' in zh
    ko = slot['threads']['ko']['text']
    assert '오늘의 3줄 요약' in ko and '최다 언급' in ko and '의견 차이 최대' in ko
    # i18n phrase once. The page wraps cmpLab in another pair of parentheses; the post does not.
    calc = share.three_lines_calc([
        {'t': 'AAA', 'c': _c(2, 0, 0, 2, 2), 'c0': _c(0, 2, 0, 2, 2), 'chg': 0},
    ], True)
    lines, _ticks = three_why._fact_lines('en', calc)
    assert lines[0] == 'Biggest consensus shift: $AAA net bullish -100% → +100% vs the same hours yesterday'
    assert '(vs the same hours yesterday)' not in lines[0]
    assert 'vs yesterday (today so far)' not in lines[0]
    zlines, _ = three_why._fact_lines('zh', calc)
    assert zlines[0] == '共識變化最大：$AAA 淨看多比例 -100% → +100% 對比昨日同時段'
    assert '（對比昨日同時段）' not in zlines[0]
    assert '對比昨日（今日至今）' not in zlines[0]
    klines, _ = three_why._fact_lines('ko', calc)
    assert klines[0] == '합의 변화 최대: $AAA 순강세 비율 -100% → +100% 어제 같은 시간대 대비'
    assert '(어제 같은 시간대 대비)' not in klines[0]
    assert '어제 대비 (오늘 현재까지)' not in klines[0]


NEW_DELTA = {
    'zh': '對比昨日同時段',
    'en': 'vs the same hours yesterday',
    'ko': '어제 같은 시간대 대비',
}
OLD_DELTA = {
    'zh': '對比昨日（今日至今）',
    'en': 'vs yesterday (today so far)',
    'ko': '어제 대비 (오늘 현재까지)',
}


def _assert_x_and_threads(slot, shift):
    """Per language: X title, link, length, url invariant; Threads topic and wording."""
    for lang in share.LANGS:
        title = three_why.T3_COPY[lang]['title']
        topic = three_why.T3_TOPIC[lang]
        x = slot['x'][lang]
        text, url = x['text'], x['url']
        lines = text.splitlines()
        assert lines[0] == title, (lang, lines[0])
        assert title in text
        assert share.SHORT[lang]['disc'] in text
        assert share.xlen(text) <= 280, (lang, share.xlen(text), text)
        assert url, (lang, url)
        assert lines[-1] == url, (lang, lines[-1], url)
        assert (url is not None) == (url in text)
        assert text.count(url) == 1
        assert slot['has_link']['x'][lang] is True
        assert share._primary_tag(lang) == '#' + topic
        assert share._primary_tag(lang) in text

        th = slot['threads'][lang]
        body = th['text']
        assert th['topic'] == topic
        assert '#' not in th['topic']
        assert HASH.findall(body) == ['#' + topic], (lang, HASH.findall(body), body)
        assert body.splitlines()[-1] == '#' + topic
        assert URL_RE.search(body) is None
        assert 'thecrowdtape.com' not in body.lower()
        th_url = th.get('url')
        assert slot['has_link']['threads'][lang] is bool(th_url)
        if th_url:
            assert th_url not in body
        assert TICK_TAG.findall(body) == []
        # Cashtags stay. Ticker hashtags do not.
        if shift:
            assert body.count(NEW_DELTA[lang]) == 1
            assert text.count(NEW_DELTA[lang]) == 1
            assert slot['facebook'][lang]['text'].count(NEW_DELTA[lang]) == 1
            wrapped = f'（{NEW_DELTA[lang]}）' if lang == 'zh' else f'({NEW_DELTA[lang]})'
            assert wrapped not in body and wrapped not in text
            assert wrapped not in slot['facebook'][lang]['text']
        else:
            assert NEW_DELTA[lang] not in body and NEW_DELTA[lang] not in text
        assert OLD_DELTA[lang] not in body and OLD_DELTA[lang] not in text
        assert OLD_DELTA[lang] not in slot['facebook'][lang]['text']
    assert slot['threads']['zh']['url'] is None
    assert slot['threads']['ko']['url'] is None
    assert slot['threads']['en']['url']
    assert slot['has_link']['threads'] == {'zh': False, 'en': True, 'ko': False}


def _assert_x_drop_order(slot, calc):
    """Ticker tags go before the label, and the label goes before a trailing fact."""
    for lang in share.LANGS:
        text = slot['x'][lang]['text']
        facts, ticks = three_why._fact_lines(lang, calc)
        present = [f for f in facts if f in text]
        assert present == facts[:len(present)] and present, (lang, present, facts)
        ticker_tags = share._hash_tags(ticks)
        label_in = bool(slot['window'] and slot['window'] in text)
        if len(present) < len(facts):
            assert not label_in, lang
            assert not any(tag in text for tag in ticker_tags), lang
        if slot['window'] and not label_in:
            assert not any(tag in text for tag in ticker_tags), lang
        if any(tag in text for tag in ticker_tags):
            assert all(tag in text for tag in ticker_tags), lang
            assert label_in, lang


def _long_dash():
    """A morning with a shift, a most-mentioned name and a split. English X does not fit whole."""
    posts = [
        _post('2026-10-22', '10:00', 'ann', ['NVDA'], '睇淡'),
        _post('2026-10-22', '11:00', 'bob', ['NVDA'], '睇淡'),
        _post(DAY, '09:00', 'ann', ['NVDA'], '睇好'),
        _post(DAY, '09:05', 'bob', ['NVDA'], '睇好'),
    ]
    handles = ['cyd', 'dee', 'eli', 'fay', 'gus', 'hua']
    for i, handle in enumerate(handles):
        stance = '睇好' if i % 2 == 0 else '睇淡'
        posts.append(_post(DAY, f'09:{10 + i:02d}', handle, ['SPCX'], stance))
    return {
        'meta': {'min_daily_posts': 1, 'cutoff_hkt': '2026-10-23T18:31:33+08:00'},
        'summaries': {'daily': [{'date': DAY, 'win': None}]},
        'tracked': {'categories': [], 'accounts': []},
        'posts': posts,
    }


def _short_daily():
    """One name, one fact, no previous window."""
    return {
        'from': '2026-10-23T00:00',
        'to': '2026-10-23T09:00',
        'posts': 2,
        'accounts': 1,
        'bull': [{
            't': 'AAPL', 'nb': 1, 'nr': 0, 'n_posts': 2,
            'rows': [{'acc': 'alpha', 's': 'bull', 'why': 'AAPL 穩。', 'ms': _ms('09:00')}],
        }],
        'bear': [],
        'split': [],
    }


def test_long_and_short_x_threads():
    long_slot = share.build_three_lines({}, DAY, dash=_long_dash())
    assert 'homepage' in long_slot['source']
    calc = share.three_lines_calc(*three_why.site_rows(_long_dash(), DAY)[:2])
    assert calc['shift'] and calc['most'] and calc['split']
    _assert_x_and_threads(long_slot, shift=True)
    _assert_x_drop_order(long_slot, calc)
    # English does not fit with the label and ticker tags. Those go; the three facts stay.
    en = long_slot['x']['en']['text']
    en_facts, _en_ticks = three_why._fact_lines('en', calc)
    assert long_slot['window'] not in en
    assert '#NVDA' not in en and '#SPCX' not in en
    assert all(fact in en for fact in en_facts)

    short_slot = share.build_three_lines(_short_daily(), DAY)
    assert '共識變化最大' not in short_slot['threads']['zh']['text']
    _assert_x_and_threads(short_slot, shift=False)
    facts, _ticks = three_why._fact_lines('en', share.three_lines_calc(*three_why.rows_from_writeup(_short_daily())))
    assert len(facts) == 1
    for lang in share.LANGS:
        text = short_slot['x'][lang]['text']
        lang_facts, lang_ticks = three_why._fact_lines(lang, share.three_lines_calc(*three_why.rows_from_writeup(_short_daily())))
        assert short_slot['window'] in text
        for fact in lang_facts:
            assert fact in text
        for tag in share._hash_tags(lang_ticks):
            assert tag in text, (lang, tag, text)
        assert short_slot['window'] in short_slot['threads'][lang]['text']


def test_fit_x_drops_trailing_facts_last():
    """Past the label, only trailing facts go. Title, disclaimer, primary tag and link stay."""
    title = 'Today in 3 lines'
    label = '10/23 00:00 – 09:55 HKT · 120 posts / 45 accounts'
    facts = [
        'Biggest consensus shift: $AAAAAA net bullish -100% → +100% vs the same hours yesterday',
        'Most mentioned: $BBBBBB 999 views, 999 accounts',
        'Biggest disagreement: $CCCCCC Bullish 99, bearish 99 ' + ('word ' * 30),
    ]
    disc = share.SHORT['en']['disc']
    tag = '#StockMarket #AAAAAA #BBBBBB'
    url = share._camp_url('en', 'x', 'three_lines')
    text = three_why._fit_x(title, label, facts, disc, tag, url)
    assert text.splitlines()[0] == title
    assert text.splitlines()[-1] == url
    assert url in text and text.count(url) == 1
    assert share.xlen(text) <= 280
    assert disc in text and '#StockMarket' in text
    assert '#AAAAAA' not in text and '#BBBBBB' not in text
    assert label not in text
    assert facts[0] in text and facts[-1] not in text


def test_weekend_does_not_write_three_lines():
    sp = {'date': '2026-10-23', 'posts': {'zh': {'x': 'keep'}}}
    share.attach_weekend_slots(sp, '2026-10-24', {'daily': _daily(), 'weekly': {}}, {}, save=False)
    assert 'three_lines' not in sp and 'why_posts' not in sp
    assert sp['posts']['zh']['x'] == 'keep'


def main():
    test_three_lines_calc_matches_page()
    test_clause_for()
    test_site_rows_follow_the_daily_tab()
    test_post_shape_limits_and_utm()
    test_long_and_short_x_threads()
    test_fit_x_drops_trailing_facts_last()
    test_weekend_does_not_write_three_lines()
    print('test_three_lines: platforms, limits, UTM, window, X link and Threads topic ok')


if __name__ == '__main__':
    main()
