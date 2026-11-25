"""Prices, thumbs and avatars must leave the core file without changing the data."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from slim_pages import assemble, split_data  # noqa: E402


def test_round_trip_splits_prices_off_the_phone_path():
    data = {
        'meta': {'generated_hkt': '2026-11-25 13:56'},
        'accounts': {
            'Ann': {'type': 'opinion', 'name': 'Ann', 'avatar': 'data:image/jpeg;base64,AAAA', 'bio': 'x'},
            'Bee': {'bio': 'y', 'type': 'news', 'name': 'Bee', 'avatar': 'data:image/png;base64,BBBB'},
            'Cee': {'type': 'opinion', 'name': 'Cee'},
            'Dee': {'avatar': 'data:image/gif;base64,DD'},
            'Eve': {'type': 'avatar', 'name': 'Eve', 'avatar': 'https://example.test/a.jpg'},
        },
        'tracked': {'accounts': [{'handle': 'Ann'}]},
        'posts': [{'id': '1', 'time_hkt': '2026-11-25 10:00', 'time_utc': '2026-11-25T02:00:00Z'}],
        'prices': {'NVDA': {'source': 'Yahoo Finance', 'c': [['2026-11-24', 155.38]], 'lite': 1, 'as_of': '2026-11-24'}},
        'avmini': {'ann': 'data:image/jpeg;base64,QQ'},
        'quotes': {'NVDA': {'mcap': 1, 'date': '2026-11-25'}},
    }
    slim, core, pages, hist, prices, avmini, avatars = split_data(data, 'zh', 1000)
    assert 'prices' not in core and 'avmini' not in core
    assert 'data:image' not in str(core['accounts'])
    assert core['accounts']['Ann'] == {'type': 'opinion', 'name': 'Ann', 'bio': 'x'}
    assert avatars['Ann'] == [2, 'data:image/jpeg;base64,AAAA']
    assert avatars['Bee'][0] == 3
    assert 'Eve' not in avatars  # remote URL stays on the small account record
    assert slim['_ext']['prices'] == '/data/dash/zh-prices.json'
    assert slim['_ext']['avmini'].endswith('/zh-avmini.json')
    assert slim['_ext']['avatars'].endswith('/zh-avatars.json')
    assert prices['NVDA']['c'][-1] == ['2026-11-24', 155.38]
    rebuilt = assemble(slim, core, pages, hist, prices, avmini, avatars)
    assert rebuilt == data, rebuilt


if __name__ == '__main__':
    test_round_trip_splits_prices_off_the_phone_path()
    print('ok slim split')
