"""date_kst is the Asia/Seoul posting day. Existing `date` fields stay put.

Run from the repo root: python3 tools/test_date_kst.py
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['WORK_DIR'] = tempfile.mkdtemp(prefix='date-kst-test-')
os.environ['SOCIAL_HISTORY'] = os.path.join(os.environ['WORK_DIR'], 'social-history.json')
os.environ['SOCIAL_POSTS'] = os.path.join(os.environ['WORK_DIR'], 'social-posts.json')

import date_kst  # noqa: E402
import intraday as intra  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NY = ZoneInfo('America/New_York')
FRIDAY = '2026-10-23'
SATURDAY = '2026-10-24'
WINTER = '2026-11-03'


def _strip(obj):
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if k not in ('date_kst', 'why_posts_date_kst')}
    if isinstance(obj, list):
        return [_strip(v) for v in obj]
    return obj


def _collect_dates(obj, path=''):
    rows = []
    if isinstance(obj, dict):
        if 'date' in obj:
            rows.append((path or 'date', obj['date']))
        for key, value in obj.items():
            rows.extend(_collect_dates(value, f'{path}.{key}' if path else key))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            rows.extend(_collect_dates(value, f'{path}[{i}]'))
    return rows


def _mixed():
    """Friday file whose weekend run replaced atomic posts. Intraday has no open slot."""
    return {
        'date': FRIDAY,
        'why_posts': [
            {'ticker': 'QQQ', 'date': FRIDAY, 'suggested_kst': '09:00', 'threads': {'en': {'text': 'keep why'}}},
            {'ticker': 'SPCX', 'date': FRIDAY, 'suggested_kst': '11:30', 'threads': {'en': {'text': 'mid why'}}},
            {'ticker': 'RSP', 'date': FRIDAY, 'suggested_kst': '14:00', 'threads': {'en': {'text': 'late why'}}},
        ],
        'note': 'keep-note',
        'three_lines': {
            'date': FRIDAY,
            'suggested_kst': '08:30',
            'threads': {'en': {'text': 'keep three'}},
        },
        'posts': {'en': {'x': 'keep headline'}},
        'weekend': {'date': SATURDAY, 'posts': [{'id': 'weekend-sat-bulls', 'ticker': 'AMZN'}]},
        'atomic_posts': [
            {'ticker': 'AAA', 'slot_kst': '09:00', 'text': 'keep atomic'},
            {'ticker': 'BBB', 'slot_kst': '20:00', 'text': 'keep late'},
        ],
        'intraday': {
            'date': FRIDAY,
            'slots': {
                'intraday_1': {
                    'post_et': '11:00', 'post_hkt': '23:00', 'date': FRIDAY,
                    'x': {'en': {'text': 'keep x', 'url': None}},
                },
                'intraday_3': {
                    'post_et': '13:30', 'post_hkt': '01:30', 'date': FRIDAY,
                    'x': {'en': {'text': 'afternoon', 'url': None}},
                },
                'intraday_close': {'post_et': '15:40', 'date': FRIDAY},
            },
        },
    }


def test_et_clocks_cross_midnight_kst():
    # 2026-10-23 is EDT (UTC-4). 2026-11-03 is EST (UTC-5), after the November fallback.
    assert datetime(2026, 10, 23, 13, 30, tzinfo=NY).utcoffset().total_seconds() == -4 * 3600
    assert datetime(2026, 11, 3, 11, 0, tzinfo=NY).utcoffset().total_seconds() == -5 * 3600
    summer = {
        '09:45': FRIDAY,
        '11:00': SATURDAY,
        '12:15': SATURDAY,
        '13:30': SATURDAY,
        '14:45': SATURDAY,
        '15:40': SATURDAY,
    }
    winter = {
        '09:45': WINTER,
        '11:00': '2026-11-04',
        '12:15': '2026-11-04',
        '13:30': '2026-11-04',
        '14:45': '2026-11-04',
        '15:40': '2026-11-04',
    }
    for hhmm, day in summer.items():
        assert date_kst.et_post_date_kst(FRIDAY, hhmm) == day, hhmm
    for hhmm, day in winter.items():
        assert date_kst.et_post_date_kst(WINTER, hhmm) == day, hhmm
    # The US trade date is not copied. 13:30 ET is the next Seoul morning.
    assert date_kst.et_post_date_kst(FRIDAY, '13:30') == SATURDAY
    assert date_kst.kst_date(FRIDAY, '08:30') == FRIDAY
    assert date_kst.kst_date(SATURDAY, '08:00') == SATURDAY


def test_saturday_atomic_and_weekday_override():
    inferred = _mixed()
    before = _collect_dates(inferred)
    date_kst.apply_date_kst(inferred)
    assert _collect_dates(inferred) == before
    assert inferred['date'] == FRIDAY
    assert inferred['date_kst'] == FRIDAY
    assert inferred['why_posts_date_kst'] == FRIDAY
    assert isinstance(inferred['why_posts'], list)
    assert [p['date_kst'] for p in inferred['why_posts']] == [FRIDAY, FRIDAY, FRIDAY]
    assert [p['date'] for p in inferred['why_posts']] == [FRIDAY, FRIDAY, FRIDAY]
    assert inferred['three_lines']['date'] == FRIDAY
    assert inferred['three_lines']['date_kst'] == FRIDAY
    assert inferred['three_lines']['threads']['en']['text'] == 'keep three'
    assert inferred['weekend']['date'] == SATURDAY
    assert inferred['weekend']['date_kst'] == SATURDAY
    assert isinstance(inferred['atomic_posts'], list)
    assert [a['date_kst'] for a in inferred['atomic_posts']] == [SATURDAY, SATURDAY]
    assert inferred['atomic_posts'][0]['text'] == 'keep atomic'
    assert inferred['intraday']['date'] == FRIDAY
    assert inferred['intraday']['date_kst'] == SATURDAY
    slots = inferred['intraday']['slots']
    assert slots['intraday_1']['date'] == FRIDAY and slots['intraday_1']['date_kst'] == SATURDAY
    assert slots['intraday_3']['date'] == FRIDAY and slots['intraday_3']['date_kst'] == SATURDAY
    assert slots['intraday_close']['date_kst'] == SATURDAY
    assert slots['intraday_1']['x']['en']['text'] == 'keep x'
    assert inferred['posts']['en']['x'] == 'keep headline'
    # A weekday merge names the atomic day, so a leftover weekend date does not win.
    forced = _mixed()
    date_kst.apply_date_kst(forced, atomic_day=FRIDAY)
    assert [a['date_kst'] for a in forced['atomic_posts']] == [FRIDAY, FRIDAY]
    assert forced['weekend']['date_kst'] == SATURDAY
    assert forced['date'] == FRIDAY
    # No weekend object: atomic clocks use the file date.
    weekday = {
        'date': FRIDAY,
        'atomic_posts': [{'slot_kst': '17:00', 'text': 'daytime'}],
    }
    date_kst.apply_date_kst(weekday)
    assert weekday['atomic_posts'][0]['date_kst'] == FRIDAY
    assert 'why_posts_date_kst' not in weekday
    # A dict why_posts stays a dict and does not grow a list-only top-level key.
    as_dict = {'date': FRIDAY, 'why_posts': {'date': FRIDAY, 'suggested_kst': '09:00'}}
    date_kst.apply_date_kst(as_dict)
    assert isinstance(as_dict['why_posts'], dict)
    assert as_dict['why_posts']['date'] == FRIDAY
    assert as_dict['why_posts']['date_kst'] == FRIDAY
    assert 'why_posts_date_kst' not in as_dict


def test_backfill_only_adds_keys_and_is_idempotent():
    original = _mixed()
    path = os.path.join(os.environ['WORK_DIR'], 'backfill.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(original, f, ensure_ascii=False, indent=1)
        f.write('\n')
    date_kst.backfill_file(path)
    loaded = json.load(open(path, encoding='utf-8'))
    assert _strip(loaded) == original
    assert list(loaded)[:4] == ['date', 'date_kst', 'why_posts_date_kst', 'why_posts']
    assert loaded['date_kst'] == FRIDAY
    assert loaded['weekend']['date_kst'] == SATURDAY
    assert loaded['intraday']['slots']['intraday_3']['date_kst'] == SATURDAY
    assert isinstance(loaded['why_posts'], list) and isinstance(loaded['atomic_posts'], list)
    first = open(path, encoding='utf-8').read()
    date_kst.backfill_file(path)
    assert open(path, encoding='utf-8').read() == first
    proc = subprocess.run(
        [sys.executable, os.path.join(ROOT, 'tools', 'share.py'), '--backfill-date-kst', path],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    assert open(path, encoding='utf-8').read() == first
    assert 'date_kst=2026-10-23' in proc.stdout
    assert 'weekend.date_kst=2026-10-24' in proc.stdout
    assert 'intraday.slots.intraday_3.date_kst=2026-10-24' in proc.stdout
    assert 'atomic_posts[0].date_kst=2026-10-24' in proc.stdout
    assert 'three_lines.date_kst=2026-10-23' in proc.stdout
    assert 'why_posts[0].date_kst=2026-10-23' in proc.stdout


def test_intraday_parent_uses_earliest_slot_present():
    both = {
        'date': FRIDAY,
        'slots': {
            'intraday_3': {'post_et': '13:30', 'date': FRIDAY},
            'intraday_open': {'post_et': '09:45'},
        },
    }
    date_kst.stamp_intraday(both)
    assert both['date'] == FRIDAY
    assert both['slots']['intraday_open']['date_kst'] == FRIDAY
    assert both['slots']['intraday_3']['date'] == FRIDAY
    assert both['slots']['intraday_3']['date_kst'] == SATURDAY
    # Open is the earlier post, so the object is still Friday in Seoul.
    assert both['date_kst'] == FRIDAY
    # A file that never wrote open takes the first slot that is actually there.
    afternoon = {
        'date': FRIDAY,
        'slots': {'intraday_1': {'post_et': '11:00', 'date': FRIDAY}},
    }
    date_kst.stamp_intraday(afternoon)
    assert afternoon['date'] == FRIDAY
    assert afternoon['date_kst'] == SATURDAY
    assert afternoon['slots']['intraday_1']['date_kst'] == SATURDAY
    winter = {
        'date': WINTER,
        'slots': {
            'intraday_open': {'post_et': '09:45', 'date': WINTER},
            'intraday_1': {'post_et': '11:00', 'date': WINTER},
        },
    }
    date_kst.stamp_intraday(winter)
    assert winter['slots']['intraday_open']['date'] == WINTER
    assert winter['slots']['intraday_open']['date_kst'] == WINTER
    assert winter['slots']['intraday_1']['date_kst'] == '2026-11-04'
    assert winter['date_kst'] == WINTER


def test_merge_from_sets_date_kst_without_touching_other_keys():
    slot = {
        'post_et': '13:30',
        'post_hkt': '01:30',
        'date': FRIDAY,
        'x': {'en': {'text': 'leave this', 'url': None}},
        'threads': {
            'zh': {'text': '午后', 'url': None},
            'en': {'text': 'afternoon', 'url': None},
            'ko': {'text': '오후', 'url': None},
        },
        'hot': [],
    }
    assert 'date_kst' not in slot
    path = os.path.join(os.environ['WORK_DIR'], 'slot.json')
    intra.write_slot_file(
        'intraday_3', FRIDAY, slot, '2026-10-23T13:25:00-04:00', '2026-10-24 01:25', path=path)
    base = {'date': FRIDAY, 'posts': {'en': {'x': 'keep me'}}, 'note': 'untouched'}
    with open(intra.posts_path(), 'w', encoding='utf-8') as f:
        json.dump(base, f)
    intra.merge_from_file(path, save=True)
    saved = json.load(open(intra.posts_path(), encoding='utf-8'))
    assert saved['posts']['en']['x'] == 'keep me'
    assert saved['note'] == 'untouched'
    assert saved['date'] == FRIDAY
    assert 'date_kst' not in saved
    sl = saved['intraday']['slots']['intraday_3']
    assert sl['date'] == FRIDAY
    assert sl['date_kst'] == SATURDAY
    assert sl['x']['en']['text'] == 'leave this'
    assert saved['intraday']['date'] == FRIDAY
    assert saved['intraday']['date_kst'] == SATURDAY
    assert list(saved) == ['date', 'posts', 'note', 'intraday']


def main():
    test_et_clocks_cross_midnight_kst()
    test_saturday_atomic_and_weekday_override()
    test_backfill_only_adds_keys_and_is_idempotent()
    test_intraday_parent_uses_earliest_slot_present()
    test_merge_from_sets_date_kst_without_touching_other_keys()
    print('test_date_kst: saturday atomic, midnight slots, three_lines/why, backfill ok')


if __name__ == '__main__':
    main()
