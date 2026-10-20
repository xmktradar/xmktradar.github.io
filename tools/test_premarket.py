"""Premarket X text differs from afterclose: tie, no-tie, and no x_facts.

Run from pages/: python3 tools/test_premarket.py
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['WORK_DIR'] = tempfile.mkdtemp(prefix='premarket-test-')

import share  # noqa: E402

def _url(lang):
    return f'https://thecrowdtape.com/{lang}/?utm_source=x&utm_medium=post&utm_campaign=premarket'


URLS = [_url(lang) for lang in share.LANGS]
DISC = share._disc_line()
DAY = '2026-10-20'

POSTS = {
    'zh': {'x': (
        '10/20 X 大神共識快照： $AMZN 4 個帳號一齊睇好 📊\n\n'
        '・4 個帳號： $AMZN\n'
        '・2 個帳號： $META、 $BE\n\n'
        'https://thecrowdtape.com/zh/?utm_source=x&utm_medium=post&utm_campaign=daily\n'
        '⚠️ 唔構成投資建議')},
    'en': {'x': (
        'Oct 20 · What top X accounts agree on: $AMZN, 4 accounts bullish 📊\n\n'
        '・4 accounts: $AMZN\n'
        '・2 accounts: $META, $BE\n\n'
        'https://thecrowdtape.com/en/?utm_source=x&utm_medium=post&utm_campaign=daily\n'
        '⚠️ Not investment advice')},
    'ko': {'x': (
        '10/20 X 인플루언서 컨센서스: $AMZN 계정 4개 동시 강세 📊\n\n'
        '・계정 4개: $AMZN\n'
        '・계정 2개: $META, $BE\n\n'
        'https://thecrowdtape.com/ko/?utm_source=x&utm_medium=post&utm_campaign=daily\n'
        '⚠️ 투자 조언 아님')},
}


def _pack(lines, disc=None):
    out = []
    for lang, line in zip(share.LANGS, lines):
        out.append(line)
        out.append(_url(lang))
    out.append(disc if disc is not None else share.SHORT['en']['disc'])
    return '\n'.join(out)


def _check_post(text, label):
    assert isinstance(text, str) and text.strip(), label
    assert share.xlen(text) <= 280, (label, share.xlen(text), text)
    assert 'utm_campaign=premarket' in text, label
    assert 'utm_campaign=afterclose' not in text, label
    assert 'utm_campaign=daily' not in text, label
    assert 'https://thecrowdtape.com/?' not in text, label
    lines = text.split('\n')
    assert lines[-1] == DISC or lines[-1] == share.SHORT['en']['disc'], (label, lines[-1])
    urls = [ln for ln in lines if ln.startswith('https://')]
    assert urls == URLS, (label, urls)
    assert share._minus_urls(text), label


def test_tie():
    # x_facts insertion order is AMZN then NVDA. Afterclose names NVDA first, so the tie leads with NVDA.
    sp = {
        'date': DAY,
        'posts': POSTS,
        'x_facts': {
            'AMZN': {'bull': 3, 'bear': 1, 'n': 5},
            'NVDA': {'bull': 3, 'bear': 0, 'n': 4},
            'META': {'bull': 1, 'bear': 0, 'n': 2},
        },
        'x_trilingual': {'afterclose': {'text': (
            '10/20 $NVDA 3 個帳號一齊睇好\n'
            'Oct 20 $NVDA, 3 accounts bullish\n'
            '10/20 $NVDA 계정 3개 동시 강세\n'
            'https://thecrowdtape.com/?utm_source=x&utm_medium=post&utm_campaign=afterclose\n'
            + DISC)}},
    }
    # Afterclose text only names NVDA. Joint-bull lines in posts name AMZN, META, BE.
    # NVDA is first because the stored afterclose post leads with it; AMZN is the next real bull count
    # that the posts name (the headline ticker). Both bulls are 3.
    text, form = share.premarket_text(sp)
    _check_post(text, 'tie')
    assert form == 'short'
    assert text == _pack([
        '10/20 開市前：$NVDA、$AMZN 各 3 個帳號睇好',
        'Oct 20 pre-market: $NVDA, $AMZN, 3 accounts bullish each',
        '10/20 개장 전: $NVDA·$AMZN 각각 계정 3개 강세',
    ]), text
    assert '$META' not in text and '$BE' not in text
    assert '其次' not in text
    # Bull count, not the mention count n.
    assert '各 3' in text and '各 5' not in text and '各 4' not in text
    entry = share.x_entry(sp, 'premarket')
    assert entry['image_ticker'] == 'NVDA'
    assert entry['text'].split('$')[1].startswith('NVDA')
    assert entry['counts'] == {'bull': 3, 'bear': 0, 'n': 4}
    assert entry['xlen'] == share.xlen(entry['text']) <= 280
    assert entry['post_at_hkt'] == '21:00'
    tri = share.build_x_trilingual(dict(sp))
    assert share._minus_urls(tri['premarket']['text']) != share._minus_urls(tri['afterclose']['text'])


def test_no_tie():
    # Dict order is BE, META, AMZN. Afterclose order from the posts is AMZN, META, BE.
    sp = {
        'date': DAY,
        'posts': POSTS,
        'x_facts': {
            'BE': {'bull': 2, 'bear': 0, 'n': 9},
            'META': {'bull': 2, 'bear': 1, 'n': 8},
            'AMZN': {'bull': 4, 'bear': 0, 'n': 9},
        },
    }
    text, form = share.premarket_text(sp)
    _check_post(text, 'no-tie')
    assert form == 'short'
    assert text == _pack([
        '10/20 開市前：$AMZN 4 個帳號睇好 · $META 2 個',
        'Oct 20 pre-market: $AMZN 4 accounts bullish · $META 2',
        '10/20 개장 전: $AMZN 계정 4개 강세 · $META 2개',
    ]), text
    assert '其次' not in text
    assert '各' not in text.split('\n')[0]
    assert 'each' not in text
    # Real bull counts, not n (AMZN n is 9, META n is 8).
    assert '9 個' not in text and '8 個' not in text
    entry = share.x_entry(sp, 'premarket')
    assert entry['image_ticker'] == 'AMZN'
    assert entry['counts'] == {'bull': 4, 'bear': 0, 'n': 9}
    tri = share.build_x_trilingual({'date': DAY, 'posts': POSTS, 'x_facts': sp['x_facts']})
    assert share._minus_urls(tri['premarket']['text']) != share._minus_urls(tri['afterclose']['text'])
    assert tri['afterclose']['text'] == share.trilingual_text(POSTS, 'afterclose')[0]


def test_no_data():
    cases = (
        {'date': DAY, 'posts': POSTS},
        {'date': DAY, 'posts': POSTS, 'x_facts': {}},
        {'date': DAY, 'posts': POSTS, 'x_facts': {'AMZN': {'bear': 1, 'n': 4}}},
    )
    for sp in cases:
        text, form = share.premarket_text(sp)
        _check_post(text, 'no-data')
        assert form in ('short', 'full')
        lines = [ln for ln in text.split('\n') if ln and not ln.startswith('https://') and not ln.startswith('⚠')]
        assert lines[0].startswith('10/20 開市前：'), lines[0]
        assert lines[1].startswith('Oct 20 pre-market:'), lines[1]
        assert lines[2].startswith('10/20 개장 전:'), lines[2]
        assert '$AMZN' in lines[0] and '$AMZN' in lines[1] and '$AMZN' in lines[2]
        ac = share.trilingual_text(POSTS, 'afterclose')[0]
        assert share._minus_urls(text) != share._minus_urls(ac)
        # Framing is on the headline, not a second copy of the date.
        assert '開市前：10/20' not in text
        assert 'pre-market: Oct 20' not in text
        entry = share.x_entry(sp, 'premarket')
        assert entry['image_ticker'] == 'AMZN'
        if sp.get('x_facts'):
            assert entry['counts'] == {'bear': 1, 'n': 4}
        else:
            assert 'counts' not in entry
        tri = share.build_x_trilingual({'date': DAY, 'posts': POSTS})
        assert '開市前' in tri['premarket']['text']
        assert share._minus_urls(tri['premarket']['text']) != share._minus_urls(tri['afterclose']['text'])
        assert tri['premarket']['xlen'] <= 280 and tri['afterclose']['xlen'] <= 280


def test_guard_rewrites_matching_body():
    """When premarket minus URLs equals afterclose, build_x_trilingual uses the framed fallback."""
    sp = {'date': DAY, 'posts': POSTS, 'x_facts': {
        'AMZN': {'bull': 4, 'bear': 0, 'n': 4},
        'META': {'bull': 2, 'bear': 0, 'n': 2},
    }}
    real = share.premarket_text

    def same_as_afterclose(sp, force_fallback=False):
        if force_fallback:
            return real(sp, force_fallback=True)
        return share.trilingual_text(sp.get('posts') or {}, 'premarket')

    share.premarket_text = same_as_afterclose
    try:
        tri = share.build_x_trilingual(sp)
    finally:
        share.premarket_text = real
    assert '開市前' in tri['premarket']['text']
    assert share._minus_urls(tri['premarket']['text']) != share._minus_urls(tri['afterclose']['text'])
    assert tri['premarket']['xlen'] <= 280
    assert 'utm_campaign=premarket' in tri['premarket']['text']


def main():
    try:
        test_tie()
        test_no_tie()
        test_no_data()
        test_guard_rewrites_matching_body()
        print('test_premarket: tie, no-tie, no-data, guard ok')
    finally:
        shutil.rmtree(os.environ['WORK_DIR'], ignore_errors=True)


if __name__ == '__main__':
    main()
