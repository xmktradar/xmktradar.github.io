"""Friday consensus thread: real weekly counts, xlen <= 280, link on the last post.

Run from the repo root: python3 tools/test_weekly_thread.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import share  # noqa: E402

TICK_RE = re.compile(r'\$([A-Z0-9.\-]+)')
FRIDAY = '2026-10-23'
OTHERS = ('2026-10-19', '2026-10-22', '2026-10-24', '2026-10-25')
WEEKLY = {
    'from': '2026-10-17',
    'to': '2026-10-23',
    'bull_total': 32,
    'bear_total': 4,
    'bull': [
        {'t': 'AMZN', 'nb': 13, 'nr': 1},
        {'t': 'PLTR', 'nb': 6, 'nr': 8},
    ],
    'bear': [
        {'t': 'MRNA', 'nb': 9, 'nr': 3},
    ],
}
HISTORY = {'days': {
    '2026-10-16': {'bull': ['OUTSIDE'], 'bear': ['NOPE']},
    '2026-10-17': {'bull': ['AMD', 'AMZN', 'OLD1'], 'bear': ['QQQ', 'GONE']},
    '2026-10-20': {'bull': ['MID'], 'bear': ['MIDB']},
    '2026-10-23': {'bull': ['AMZN', 'RSP', 'WMT'], 'bear': ['QQQ', 'MRNA']},
    '2026-10-24': {'bull': ['NEXT'], 'bear': ['NEXTB']},
}}
BANNED = ('OUTSIDE', 'NOPE', 'MID', 'MIDB', 'NEXT', 'NEXTB', 'QQQ')


def _posts(out, lang):
    posts = out['langs'][lang]
    assert 1 <= len(posts) <= 5, (lang, len(posts))
    for i, text in enumerate(posts):
        assert share.xlen(text) <= 280, (lang, i, share.xlen(text), text)
    return posts


def _last(out, lang):
    last = _posts(out, lang)[-1]
    url = f'https://thecrowdtape.com/{lang}/?utm_source=x&utm_medium=post&utm_campaign=weekly_thread'
    assert url in last, (lang, last)
    assert f'/{lang}/stock/' not in last
    assert share.SHORT[lang]['disc'] in last
    for text in _posts(out, lang)[:-1]:
        assert 'utm_campaign=weekly_thread' not in text
    return last


def test_friday_only():
    for day in OTHERS:
        assert share.build_weekly_thread(WEEKLY, HISTORY, day) is None, day
    out = share.build_weekly_thread(WEEKLY, HISTORY, FRIDAY)
    assert out['date'] == FRIDAY
    assert out['range'] == {'from': '2026-10-17', 'to': '2026-10-23'}
    assert set(out['langs']) == {'en', 'zh', 'ko'}
    assert 'writeup-input.json' in out['note'] and 'consensus-history.json' in out['note']
    heads = {
        'zh': '本週共識變化',
        'en': "This week's consensus changes",
        'ko': '이번 주 컨센서스 변화',
    }
    for lang in ('en', 'zh', 'ko'):
        posts = _posts(out, lang)
        _last(out, lang)
        assert posts[0].startswith(heads[lang])
        assert '2026-10-17' in posts[0] and '2026-10-23' in posts[0]
        assert '32' in posts[0] and '4' in posts[0]
        blob = '\n'.join(posts)
        for banned in BANNED:
            assert f'${banned}' not in blob, (lang, banned)
        # nb / nr, not the other side's count.
        assert f'$AMZN {share._acc(lang, 13)}' in blob
        assert f'$PLTR {share._acc(lang, 6)}' in blob
        assert f'$MRNA {share._acc(lang, 3)}' in blob
        assert f'$PLTR {share._acc(lang, 8)}' not in blob
        assert f'$MRNA {share._acc(lang, 9)}' not in blob
        assert f'$AMZN {share._acc(lang, 1)}' not in blob
        # First day vs last day: RSP then WMT joined; AMD then OLD1 left; MRNA joined bear; GONE left.
        changes = next(p for p in posts if '$RSP' in p)
        assert changes.index('$RSP') < changes.index('$WMT')
        assert changes.index('$AMD') < changes.index('$OLD1')
        assert '$MRNA' in changes and '$GONE' in changes
        assert '$AMZN' not in changes  # on both bull lists, so not a join or a drop


def test_long_list_and_empty_changes():
    rows = [{'t': f'B{i:02d}', 'nb': i + 1, 'nr': 50} for i in range(40)]
    weekly = {'from': '2026-10-19', 'to': '2026-10-23', 'bull_total': 40, 'bear_total': 0, 'bull': rows, 'bear': []}
    # Same names on the first and last day: no joins or drops.
    names = [r['t'] for r in rows]
    history = {'days': {
        '2026-10-19': {'bull': names, 'bear': []},
        '2026-10-23': {'bull': list(names), 'bear': []},
    }}
    out = share.build_weekly_thread(weekly, history, FRIDAY)
    for lang in share.LANGS:
        posts = _posts(out, lang)
        _last(out, lang)
        bull = next(p for p in posts if p.startswith(share.WEEK_COPY[lang]['bulls']))
        shown = TICK_RE.findall(bull)
        assert shown == names[:len(shown)]
        assert shown, bull
        more = re.search(r'\+(\d+)', bull)
        if more:
            assert int(more.group(1)) == len(names) - len(shown)
        else:
            assert len(shown) == len(names)
        for t in shown:
            n = names.index(t) + 1
            assert f'${t} {share._acc(lang, n)}' in bull
            assert '50' not in bull.split(f'${t} ', 1)[1].split('\n', 1)[0]
        changes = next(p for p in posts if share.WEEK_COPY[lang]['no_change'] in p)
        assert '$' not in changes
    # History without ticker lists: no invented join/drop names.
    bad = {'days': {
        '2026-10-19': {'bull': {'AMZN': 2}, 'bear': []},
        '2026-10-23': {'bull': ['GHOST'], 'bear': ['GHOST']},
    }}
    out = share.build_weekly_thread(weekly, bad, FRIDAY)
    assert 'no join/drop' in out['note']
    blob = '\n'.join(out['langs']['en'])
    assert '$GHOST' not in blob
    assert '$B00' in blob


def main():
    test_friday_only()
    test_long_list_and_empty_changes()
    print('test_weekly_thread: friday-only, xlen, last link ok')


if __name__ == '__main__':
    main()
