"""Weekend bulls dedicated card: images align to weekly.bull, not og/social-*.png."""
import os
import sys
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['WORK_DIR'] = tempfile.mkdtemp(prefix='weekend-bulls-test-')
os.environ['SOCIAL_HISTORY'] = os.path.join(os.environ['WORK_DIR'], 'social-history.json')

import share  # noqa: E402


def _weekly():
    return {
        'from': '2026-10-25', 'to': '2026-10-31',
        'bull_total': 33, 'bear_total': 13,
        'bull': [
            {'t': 'SOFI', 'nb': 7},
            {'t': 'SKHY', 'nb': 5},
            {'t': 'SMH', 'nb': 5},
            {'t': 'LLY', 'nb': 4},
            {'t': 'MA', 'nb': 4},
            {'t': 'EXTRA', 'nb': 3},
        ],
        'bear': [{'t': 'INTC', 'nr': 2}],
        'split': [],
    }


def test_rows_and_range():
    rows = share._weekend_bulls_rows(_weekly())
    assert rows == [
        {'t': 'SOFI', 'n': 7}, {'t': 'SKHY', 'n': 5}, {'t': 'SMH', 'n': 5},
        {'t': 'LLY', 'n': 4}, {'t': 'MA', 'n': 4},
    ]
    assert share._weekend_range_label(_weekly()) == '10/25 – 10/31'


def test_build_weekend_attaches_images():
    sat = share.build_weekend(_weekly(), '2026-10-31')
    bulls = sat['posts'][0]
    assert bulls['id'] == 'weekend-sat-bulls'
    assert bulls['format'] == 'image_card'
    assert bulls['ticker'] == 'SOFI'
    assert bulls['bull'][0] == {'t': 'SOFI', 'n': 7}
    for lang in ('zh', 'en'):
        assert 'weekend-bulls-' + lang in bulls['images'][lang]['portrait']
        assert 'weekend-bulls-' + lang + '-sq' in bulls['images'][lang]['square']
        assert 'social-' not in bulls['images'][lang]['portrait']
    jobs = json.load(open(os.path.join(os.environ['WORK_DIR'], 'weekend-bulls-cards.json')))
    assert len(jobs['jobs']) == 4
    zh = next(j for j in jobs['jobs'] if j['lang'] == 'zh' and j['size'] == 'portrait')
    assert zh['data']['bull'][0]['t'] == 'SOFI'
    assert zh['data']['heading'] == '本週最看好'
    assert zh['out'] == 'og/weekend-bulls-zh.png'


def test_ensure_refreshes_existing_weekend():
    # Simulate captions already posted with no images (the bug state).
    sp = {
        'weekend': {
            'date': '2026-10-31',
            'posts': [{
                'id': 'weekend-sat-bulls',
                'format': 'image_card',
                'ticker': 'SOFI',
                'langs': {'zh': {}, 'en': {}},
            }, {
                'id': 'weekend-sat-totals',
                'format': 'text_question',
                'langs': {'zh': {}, 'en': {}},
            }],
        }
    }
    assert share.ensure_weekend_bulls_images(sp, _weekly(), '2026-10-31')
    bulls = sp['weekend']['posts'][0]
    assert bulls['images']['zh']['portrait'].endswith('og/weekend-bulls-zh.png?v=2026-10-31')
    assert bulls['bull'][0]['t'] == 'SOFI'
    assert 'images' not in sp['weekend']['posts'][1]


if __name__ == '__main__':
    test_rows_and_range()
    test_build_weekend_attaches_images()
    test_ensure_refreshes_existing_weekend()
    print('test_weekend_bulls: ok')
