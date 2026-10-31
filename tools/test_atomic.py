"""Atomic posts and weekend slots: 4–6 per language, unique facts, Saturday and Sunday.

Counts and names come from the writeup fixture. A number, ticker or full body used by
another slot is not reused. Run from the repo root: python3 tools/test_atomic.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['WORK_DIR'] = tempfile.mkdtemp(prefix='atomic-test-')
os.environ['SOCIAL_HISTORY'] = os.path.join(os.environ['WORK_DIR'], 'social-history.json')

import share  # noqa: E402

URL = 'https://thecrowdtape.com'
TAG = {'zh': '#美股', 'en': '#StockMarket'}


def _writeup():
    return {
        'daily': {
            'posts': 88, 'accounts': 34, 'originals': 77, 'reposts': 11,
            'bull_views': 36, 'bear_views': 41, 'clear_accounts': 28,
            'bull_total': 2, 'bear_total': 5, 'split_total': 7,
            'bull': [{
                't': 'AAA', 'nb': 5,
                'rows': [{'acc': 'alpha', 'why': '這句有 999 所以股票帖唔用'}],
            }],
            'bear': [{
                't': 'BBB', 'nr': 6,
                'rows': [
                    {'acc': 'dirty', 'why': '壞 999'},
                    {'acc': 'clean', 'why': '只談看法'},
                ],
            }],
            'split': [],
        },
        'weekly': {
            'from': '2026-10-17', 'to': '2026-10-23',
            'bull_total': 34, 'bear_total': 4, 'split_total': 64,
            'posts': 1864, 'accounts': 128,
            'bull': [
                {'t': 'AMZN', 'nb': 12, 'rows': [{'acc': 'a', 'why': '週看好'}]},
                {'t': 'GOOG', 'nb': 8, 'rows': [{'acc': 'b', 'why': '雲'}]},
            ],
            'bear': [
                {'t': 'MRNA', 'nr': 9, 'rows': [{'acc': 'c', 'why': '週看淡'}]},
            ],
            'split': [
                {'t': 'SPCX', 'nb': 4, 'nr': 3, 'n_posts': 10, 'rows': [{'acc': 'd', 'why': '分歧'}]},
            ],
        },
    }


def _by_lang(items):
    out = {lang: [] for lang in share.LANGS}
    for item in items:
        out[item['lang']].append(item)
    return out


def _assert_atomic(items):
    assert items, 'atomic posts missing'
    by = _by_lang(items)
    assert [p['lang'] for p in items] == (
        ['zh'] * len(by['zh']) + ['en'] * len(by['en']))
    n = len(by['zh'])
    assert all(4 <= len(rows) <= 6 for rows in by.values())
    assert len(by['en']) == n
    assert [p['slot_kst'] for p in by['zh']] == list(share.ATOMIC_TIMES[:n])
    assert len(set(share.ATOMIC_TIMES[:n])) == n
    texts = []
    seen_n, seen_t = set(), set()
    linked = 0
    for i, item in enumerate(items):
        assert item['format'] in ('image_card', 'carousel', 'text_question', 'poll')
        assert item['point_type'] in ('stock', 'expert_view', 'number')
        assert item['slot_kst'] == share.ATOMIC_TIMES[i % n]
        text = item['text']
        texts.append(share._norm_text(text))
        assert URL not in text
        assert share.SHORT[item['lang']]['disc'] in text
        assert TAG[item['lang']] in text
        assert item['hashtags'].startswith('#')
        assert len(text) <= 500
        assert '999' not in text
        if item['has_link']:
            linked += 1
            fc = item['first_comment']
            assert isinstance(fc, str)
            assert fc.startswith(share.SHORT[item['lang']]['live'])
            assert f"utm_source=threads&utm_medium=social&utm_campaign=atomic" in fc
            assert f"/{item['lang']}/" in fc
            if item.get('ticker'):
                assert f"/stock/{item['ticker']}/" in fc
            else:
                assert '/stock/' not in fc
        else:
            assert 'first_comment' not in item
        if item['point_type'] == 'number':
            assert item['format'] == 'text_question'
            assert 'ticker' not in item
        elif item['point_type'] == 'stock':
            assert item['format'] == 'image_card'
        else:
            assert item['format'] == 'carousel'
    assert len(texts) == len(set(texts))
    # About half the flat list carries a first_comment link.
    assert abs(linked - (len(items) - linked)) <= 1
    assert linked and linked < len(items)
    # One fact per point. Languages of the same point share it. Points do not.
    groups = {}
    for item in items:
        groups.setdefault(item['id'].split('-', 1)[1], []).append(item)
    for gid, rows in groups.items():
        assert {r['lang'] for r in rows} == set(share.LANGS)
        assert len({r['slot_kst'] for r in rows}) == 1
        nums = [share.content_numbers(r['text']) for r in rows]
        ticks = [share.content_tickers(r['text']) for r in rows]
        assert all(s == nums[0] for s in nums), gid
        assert all(s == ticks[0] for s in ticks), gid
        assert len(nums[0]) <= 1
        assert not (nums[0] & seen_n), (gid, nums[0], seen_n)
        assert not (ticks[0] & seen_t), (gid, ticks[0], seen_t)
        seen_n |= nums[0]
        seen_t |= ticks[0]
    zh = by['zh']
    assert [p['point_type'] for p in zh[:3]] == ['number', 'stock', 'expert_view']
    assert zh[1]['ticker'] == 'AAA' and share.content_numbers(zh[1]['text']) == {5}
    assert zh[2]['ticker'] == 'BBB' and share.content_numbers(zh[2]['text']) == {6}
    assert '只談看法' in zh[2]['text'] and '@clean' in zh[2]['text']
    assert '只談看法' not in by['en'][2]['text']
    assert '@clean' in by['en'][2]['text']
    return seen_n


def _assert_weekend(weekend, day, id_prefix):
    assert weekend['date'] == day
    # 08:00 KST is the Saturday/Sunday social hour, so date_kst is that same day.
    assert weekend['date_kst'] == day
    posts = weekend['posts']
    assert len(posts) >= 2
    assert all(p['id'].startswith(id_prefix) for p in posts)
    linked = 0
    total = 0
    for item in posts:
        assert item['format'] in ('image_card', 'carousel', 'text_question', 'poll')
        if item['format'] == 'poll':
            for lang in share.LANGS:
                poll = item['poll'][lang]
                assert 2 <= len(poll['options']) <= 4
                assert poll['question']
                assert item['langs'][lang]['poll'] == poll
        for lang in share.LANGS:
            entry = item['langs'][lang]
            for plat in ('threads', 'facebook'):
                total += 1
                text = entry[plat]
                assert URL not in text
                assert share.SHORT[lang]['disc'] in text
                assert TAG[lang] in text
                assert len(text) <= 500, (item['id'], lang, len(text))
                if entry['has_link'][plat]:
                    linked += 1
                    fc = entry['first_comment'][plat]
                    assert fc.startswith(share.SHORT[lang]['live'])
                    assert f'utm_source={plat}&utm_medium=social&utm_campaign=weekend' in fc
                    assert f'/{lang}/' in fc
                else:
                    assert plat not in (entry.get('first_comment') or {})
    assert linked == total // 2


def test_atomic_posts():
    items = share.build_atomic_posts(_writeup(), set(), set(), set())
    _assert_atomic(items)
    sp = {'atomic_posts': items}
    assert share.guard_slots(sp) == []
    # A copied body, or a reused number, is a guard failure.
    dirty = {
        'atomic_posts': items,
        'posts': {'zh': {'x': items[0]['text']}},
    }
    problems = share.guard_slots(dirty)
    assert any('duplicate text' in p for p in problems)
    assert any('reuses numbers' in p for p in problems)
    # Not enough free facts: omit the whole array.
    blocked = set(range(0, 5000))
    assert share.build_atomic_posts(_writeup(), blocked, {'AAA', 'BBB'}, set()) == []


def test_weekend_two_angles():
    weekly = _writeup()['weekly']
    assert share.build_weekend(weekly, '2026-10-23') is None  # Friday
    sat = share.build_weekend(weekly, '2026-10-24')
    sun = share.build_weekend(weekly, '2026-10-25')
    _assert_weekend(sat, '2026-10-24', 'weekend-sat')
    _assert_weekend(sun, '2026-10-25', 'weekend-sun')
    sat_ids = [p['id'] for p in sat['posts']]
    sun_ids = [p['id'] for p in sun['posts']]
    assert sat_ids == ['weekend-sat-bulls', 'weekend-sat-totals']
    assert sun_ids == ['weekend-sun-bears', 'weekend-sun-split_poll']
    assert set(sat_ids).isdisjoint(sun_ids)
    assert sat['posts'][0]['format'] == 'image_card'
    assert sat['posts'][1]['format'] == 'text_question'
    assert sun['posts'][0]['format'] == 'carousel'
    assert sun['posts'][1]['format'] == 'poll'
    assert sat['posts'][0]['ticker'] == 'AMZN'
    # Dedicated weekend bulls card — never og/social-*.png (daily snapshot).
    bulls = sat['posts'][0]
    assert bulls['bull'] == [{'t': 'AMZN', 'n': 12}, {'t': 'GOOG', 'n': 8}]
    assert bulls['images']['zh']['portrait'].endswith('og/weekend-bulls-zh.png?v=2026-10-24')
    assert bulls['images']['zh']['square'].endswith('og/weekend-bulls-zh-sq.png?v=2026-10-24')
    assert bulls['images']['en']['portrait'].endswith('og/weekend-bulls-en.png?v=2026-10-24')
    assert 'social-zh.png' not in bulls['images']['zh']['portrait']
    assert os.path.isfile(os.path.join(os.environ['WORK_DIR'], 'weekend-bulls-cards.json'))
    assert sun['posts'][0]['ticker'] == 'MRNA'
    assert sun['posts'][1]['ticker'] == 'SPCX'
    assert sun['posts'][1]['poll']['en']['options'] == ['Bullish', 'Bearish', 'Neutral']
    # Weekday keys stay. Atomic still lands, 4–6 per language, and the guard is clean.
    sp = {
        'date': '2026-10-23',
        'posts': {'zh': {'x': 'keep-weekday-post'}},
        'top5': {'bull': [{'t': 'RSP', 'n': 2}], 'bear': [{'t': 'QQQ', 'n': 4}]},
    }
    share.attach_weekend_slots(sp, '2026-10-24', _writeup(), {}, save=False)
    assert sp['date'] == '2026-10-23'
    # No weekday clocks on this file, so the top-level stamp stays Friday 08:30 KST.
    assert sp['date_kst'] == '2026-10-23'
    assert sp['posts']['zh']['x'] == 'keep-weekday-post'
    assert sp['top5']['bull'][0]['t'] == 'RSP'
    assert sp['weekend']['date'] == '2026-10-24'
    assert sp['weekend']['date_kst'] == '2026-10-24'
    assert len(sp['weekend']['posts']) >= 2
    assert sp['atomic_posts'] and all(a.get('date_kst') == '2026-10-24' for a in sp['atomic_posts'])
    by = _by_lang(sp['atomic_posts'])
    assert all(4 <= len(rows) <= 6 for rows in by.values())
    assert share.guard_slots(sp) == []
    assert os.path.exists(os.environ['SOCIAL_HISTORY']) is False


def main():
    test_atomic_posts()
    test_weekend_two_angles()
    print('test_atomic: atomic posts, weekend angles, unique facts ok')


if __name__ == '__main__':
    main()
