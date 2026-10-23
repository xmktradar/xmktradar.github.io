"""Top-5 consensus cards: real counts only, length caps, language links.

Offline fixtures. At most five names a side, a shorter list stays short, n equals the
input nb/nr, Threads stays within 500, X within 280, each language links to its own
stock page with utm_campaign=top5, and the disclaimer, hashtags and image paths are set.

Run from the repo root: python3 tools/test_top5.py
"""
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['WORK_DIR'] = tempfile.mkdtemp(prefix='top5-test-')

import share  # noqa: E402

URL_RE = re.compile(r'https://thecrowdtape\.com[^\s)\]"\']*')
TICK_RE = re.compile(r'\$([A-Z0-9.\-]+)')
SRC = {'x': 'x', 'instagram': 'instagram', 'threads': 'threads', 'facebook': 'facebook'}
NONE = {'zh': '今日暫無', 'en': 'None today', 'ko': '오늘 없음'}
TAG = {'zh': '#美股', 'en': '#StockMarket', 'ko': '#미국주식'}
DAY = '2026-10-21'
MADE = '2026-10-21 07:05'
FRM, TO = '2026-10-21T00:00', '2026-10-21T23:59'
HK = timezone(timedelta(hours=8))
MS = int(datetime(2026, 10, 21, 6, 10, tzinfo=HK).timestamp() * 1000)
WINDOW = '10/21 00:00 – 06:10 HKT'
WIN_RE = re.compile(r'^\d\d/\d\d \d\d:\d\d – \d\d:\d\d HKT$')


def _head(lang, n_bull, n_bear):
    return share.top5_labels(lang, n_bull, n_bear)['heading']


def _daily(bull, bear):
    return {
        'from': FRM, 'to': TO, 'bull': bull, 'bear': bear,
        'split': [{'t': 'CUT', 'nb': 1, 'nr': 1, 'rows': [{'acc': 'clock', 'ms': MS}]}],
    }


def _acc(lang, n):
    if lang == 'zh':
        return f'{n} 個帳號'
    if lang == 'ko':
        return f'계정 {n}개'
    return f'{n} account' if n == 1 else f'{n} accounts'


def _urls(text):
    return URL_RE.findall(text or '')


def _assert_post(text, lang, platform, bulls, bears):
    assert _head(lang, len(bulls), len(bears)) in text, (lang, platform, text[:180])
    assert DAY in text
    assert WINDOW in text
    assert share.SHORT[lang]['disc'] in text
    assert TAG[lang] in text
    assert share.xlen(text) <= 280 or platform != 'x'
    if platform == 'threads':
        assert len(text) <= 500, (lang, len(text))
    urls = _urls(text)
    src = SRC[platform]
    for u in urls:
        path = u.split('thecrowdtape.com', 1)[1]
        assert path.startswith(f'/{lang}/'), (lang, u)
        assert f'utm_source={src}' in u and 'utm_medium=social' in u and 'utm_campaign=top5' in u, u
        assert 'utm_campaign=daily' not in u
    if platform == 'x':
        assert share.xlen(text) <= 280, (lang, share.xlen(text), text)
        assert len(urls) == 1, (lang, urls)
    if platform == 'threads':
        assert urls == [], (lang, urls)
    if platform == 'facebook':
        assert urls == [], (lang, urls)
        for row in bulls + bears:
            assert f'${row["t"]} {_acc(lang, row["n"])}' in text
        if not bulls:
            assert NONE[lang] in text
        if not bears:
            assert NONE[lang] in text
    lead = bulls[0]['t'] if bulls else None
    if platform == 'x':
        if lead:
            assert f'/{lang}/stock/{lead}/' in urls[0], (platform, urls[0])
        else:
            assert '/stock/' not in urls[0], urls[0]
            assert urls[0].startswith(f'https://thecrowdtape.com/{lang}/?'), urls[0]
    if platform == 'instagram':
        assert urls == [], (lang, urls)
        assert 'thecrowdtape.com' not in text.lower()
        assert share.IG_BIO[lang] in text
        assert text.count(share.IG_BIO[lang]) == 1
        tags = re.findall(r'#[^\s#]+', text)
        assert len(tags) <= 5, (lang, tags)
        assert len(re.findall(r'#([A-Z]{1,6})\b', text)) <= 2
        for row in bulls + bears:
            assert f'${row["t"]} {_acc(lang, row["n"])}' in text
        if not bulls:
            assert NONE[lang] in text
        if not bears:
            assert NONE[lang] in text
    names = {r['t'] for r in bulls + bears}
    for t in TICK_RE.findall(text):
        assert t in names, (lang, platform, t, names)


def _assert_slot(slot, bulls, bears):
    assert slot['date'] == DAY
    assert slot['made_hkt'] == MADE
    assert slot['source'] == 'data/writeup-input.json daily'
    assert WIN_RE.match(slot['window']), slot['window']
    assert slot['window'] == WINDOW
    assert re.search(r'\d{4}-\d{2}-\d{2}T', slot['window']) is None
    assert '23:59' not in slot['window']
    assert slot['bull'] == [{'t': r['t'], 'n': r['n']} for r in bulls]
    assert slot['bear'] == [{'t': r['t'], 'n': r['n']} for r in bears]
    assert len(slot['bull']) <= 5 and len(slot['bear']) <= 5
    assert slot['format'] == 'image_card'
    for lang in share.LANGS:
        assert slot['video'][lang] == f'https://thecrowdtape.com/og/top5-{lang}.mp4?v={DAY}'
        fc = slot['posts'][lang]['first_comment']
        th = fc['threads']
        assert f'utm_source=threads' in th and 'utm_medium=social' in th and 'utm_campaign=top5' in th
        assert f'/{lang}/' in th
        lead = bulls[0]['t'] if bulls else None
        if lead:
            assert f'/{lang}/stock/{lead}/' in th
        else:
            assert '/stock/' not in th
        if bulls or bears:
            fb = fc['facebook']
            assert 'utm_source=facebook' in fb and 'utm_campaign=top5' in fb
            for row in bulls + bears:
                assert f'/{lang}/stock/{row["t"]}/' in fb
        else:
            assert 'facebook' not in fc
            assert slot['posts'][lang]['has_link']['facebook'] is False
        assert slot['posts'][lang]['has_link']['threads'] is True
        assert slot['posts'][lang]['has_link']['x'] is True
        assert slot['posts'][lang]['has_link']['instagram'] is False
        assert slot['images'][lang]['portrait'] == f'https://thecrowdtape.com/og/top5-{lang}.png?v={DAY}'
        assert slot['images'][lang]['square'] == f'https://thecrowdtape.com/og/top5-{lang}-sq.png?v={DAY}'
        for platform in ('x', 'instagram', 'threads', 'facebook'):
            _assert_post(slot['posts'][lang][platform], lang, platform, bulls, bears)


def test_five_cap_and_order():
    # Seven valid names plus a row with no count. Ranked by account count, not input order.
    bull = [{'t': 'SKIP', 'nr': 5}]
    bull += [{'t': t, 'nb': n, 'nr': 99} for t, n in zip(
        ['AAA', 'BBB', 'CCC', 'DDD', 'EEE', 'FFF', 'GGG'], [2, 9, 4, 8, 3, 42, 43])]
    bear = [{'t': 'NOPE'}]
    bear += [{'t': t, 'nb': 77, 'nr': n} for t, n in zip(
        ['HHH', 'III', 'JJJ', 'KKK', 'LLL', 'MMM', 'NNN'], [4, 2, 6, 1, 3, 15, 16])]
    slot = share.build_top5(_daily(bull, bear), DAY, MADE)
    want_b = [{'t': t, 'n': n} for t, n in zip(['GGG', 'FFF', 'BBB', 'DDD', 'CCC'], [43, 42, 9, 8, 4])]
    want_r = [{'t': t, 'n': n} for t, n in zip(['NNN', 'MMM', 'JJJ', 'HHH', 'LLL'], [16, 15, 6, 4, 3])]
    _assert_slot(slot, want_b, want_r)
    blob = json.dumps(slot['posts'], ensure_ascii=False)
    for banned in ('SKIP', 'NOPE', 'AAA', 'EEE', 'III', 'KKK', '99', '77'):
        assert banned not in blob, banned
    # Lead bull is GGG (43 accounts). The X link stays on that name.
    assert '/stock/GGG/' in slot['posts']['en']['x']
    assert '/stock/FFF/' not in slot['posts']['en']['x']
    # X keeps the lead and does not invent a sixth name. Listed counts match.
    xs = TICK_RE.findall(slot['posts']['zh']['x'])
    assert xs[0] == 'GGG'
    assert 'AAA' not in xs and 'EEE' not in xs
    for t, n in zip(['GGG', 'FFF', 'BBB', 'DDD', 'CCC'], [43, 42, 9, 8, 4]):
        if t in xs:
            assert f'${t} {n}' in slot['posts']['zh']['x']


def test_fewer_and_empty():
    bull = [{'t': 'ZZZ', 'nb': 1, 'nr': 8}, {'t': 'AAA', 'nb': 9, 'nr': 0}]
    slot = share.build_top5(_daily(bull, []), DAY, MADE)
    _assert_slot(slot, [{'t': 'AAA', 'n': 9}, {'t': 'ZZZ', 'n': 1}], [])
    assert TICK_RE.findall(slot['posts']['en']['instagram']) == ['AAA', 'ZZZ']
    assert '・$ZZZ 1 account' in slot['posts']['en']['facebook']
    assert '・$ZZZ 1 accounts' not in slot['posts']['en']['facebook']
    assert '8' not in slot['posts']['en']['x']
    for lang in share.LANGS:
        assert NONE[lang] in slot['posts'][lang]['x']
        assert NONE[lang] in slot['posts'][lang]['threads']
    empty = share.build_top5(_daily([], []), DAY, MADE)
    _assert_slot(empty, [], [])
    for lang in share.LANGS:
        assert '$' not in empty['posts'][lang]['x']
        assert '$' not in empty['posts'][lang]['threads']
        assert empty['posts'][lang]['x'].count(NONE[lang]) >= 1


def test_zero_is_kept():
    slot = share.build_top5(_daily([{'t': 'ZED', 'nb': 0}], []), DAY, MADE)
    assert slot['bull'] == [{'t': 'ZED', 'n': 0}]
    assert slot['bear'] == []
    assert '$ZED 0' in slot['posts']['en']['x']
    assert NONE['en'] in slot['posts']['en']['x']


def test_job_file():
    slot = share.build_top5(_daily([{'t': 'AAA', 'nb': 2}], [{'t': 'QQQ', 'nr': 4}]), DAY, MADE)
    share.write_top5_jobs(slot)
    path = os.path.join(os.environ['WORK_DIR'], 'top5cards.json')
    raw = json.load(open(path, encoding='utf-8'))
    outs = [(j['lang'], j['size'], j['out']) for j in raw['jobs']]
    assert outs == [
        ('zh', 'portrait', 'og/top5-zh.png'), ('zh', 'square', 'og/top5-zh-sq.png'),
        ('en', 'portrait', 'og/top5-en.png'), ('en', 'square', 'og/top5-en-sq.png'),
        ('ko', 'portrait', 'og/top5-ko.png'), ('ko', 'square', 'og/top5-ko-sq.png'),
    ]
    assert raw['jobs'][0]['data']['bull'] == [{'t': 'AAA', 'n': 2}]
    assert raw['jobs'][0]['data']['bear'] == [{'t': 'QQQ', 'n': 4}]
    assert raw['jobs'][0]['data']['heading'] == _head('zh', 1, 1)
    assert raw['jobs'][0]['data']['window'] == WINDOW
    assert raw['jobs'][0]['data']['bull_label'] == share.top5_labels('zh', 1, 1)['bull']
    sp = {'kept': {'zh': 'stay'}}
    share.attach_top5_and_weekly(sp, DAY, MADE, {'days': {}}, {'daily': _daily([{'t': 'AAA', 'nb': 2}], []), 'weekly': {}})
    assert sp['kept']['zh'] == 'stay'
    assert sp['top5']['bull'] == [{'t': 'AAA', 'n': 2}]
    assert 'weekly_thread' not in sp  # 2026-10-21 is a Wednesday


def main():
    try:
        test_five_cap_and_order()
        test_fewer_and_empty()
        test_zero_is_kept()
        test_job_file()
        print('test_top5: cap, fewer, empty, zero, links, images ok')
    finally:
        shutil.rmtree(os.environ['WORK_DIR'], ignore_errors=True)


if __name__ == '__main__':
    main()
