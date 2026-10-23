"""Shared bull/bear ranking: account count, then posts, then ticker.

Run from the repo root: python3 tools/test_rank.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import share  # noqa: E402
from ranking import rank_rows  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRITEUP = os.path.join(ROOT, 'data', 'writeup-input.json')


def _tickers(rows, side):
    return [row['t'] for row in rank_rows(rows, side)]


def test_tie_break():
    # Same account count: more posts first. Same posts: ticker A to Z.
    # A higher account count beats a longer post list.
    rows = [
        {'t': 'MMM', 'nb': 2, 'nr': 2, 'n_posts': 1},
        {'t': 'CCC', 'nb': 2, 'nr': 2, 'n_posts': 5},
        {'t': 'AAA', 'nb': 2, 'nr': 2, 'n_posts': 5},
        {'t': 'ZZZ', 'nb': 4, 'nr': 4, 'n_posts': 1},
        {'t': 'BBB', 'nb': 2, 'nr': 2, 'n_posts': 5},
        {'t': 'skip'},
        {'nb': 9, 'n_posts': 9},
        'nope',
    ]
    original = [row.get('t') if isinstance(row, dict) else row for row in rows]
    assert _tickers(rows, 'bull') == ['ZZZ', 'AAA', 'BBB', 'CCC', 'MMM']
    assert _tickers(rows, 'bear') == ['ZZZ', 'AAA', 'BBB', 'CCC', 'MMM']
    assert [row.get('t') if isinstance(row, dict) else row for row in rows] == original


def test_each_side_uses_its_own_accounts():
    rows = [
        {'t': 'AAA', 'nb': 1, 'nr': 9, 'n_posts': 1},
        {'t': 'BBB', 'nb': 3, 'nr': 1, 'n_posts': 1},
    ]
    assert _tickers(rows, 'bull') == ['BBB', 'AAA']
    assert _tickers(rows, 'bear') == ['AAA', 'BBB']


def test_missing_posts_sort_as_zero():
    rows = [
        {'t': 'BBB', 'nb': 2},
        {'t': 'AAA', 'nb': 2, 'n_posts': 0},
        {'t': 'CCC', 'nb': 2, 'n_posts': 1},
    ]
    assert _tickers(rows, 'bull') == ['CCC', 'AAA', 'BBB']


def test_zero_account_is_kept_and_bool_is_not():
    assert _tickers([{'t': 'ZED', 'nb': 0, 'n_posts': 3}, {'t': 'AAA', 'nb': 1}], 'bull') == ['AAA', 'ZED']
    assert rank_rows([{'t': 'X', 'nb': True, 'n_posts': 4}], 'bull') == []
    assert rank_rows(None, 'bear') == []
    assert rank_rows([], 'bull') == []


def test_writeup_bear_top5():
    # Current daily.bear (accounts, posts):
    # QQQ 5/9, META 3/4, MRNA 3/4, SOXX 2/5, SNDK 2/3, DRAM 2/2.
    # META ties MRNA, so the ticker puts META first. SNDK has more posts than DRAM.
    daily = json.load(open(WRITEUP, encoding='utf-8'))['daily']
    ranked = _tickers(daily['bear'], 'bear')
    assert ranked[:5] == ['QQQ', 'META', 'MRNA', 'SOXX', 'SNDK'], ranked
    assert ranked[5] == 'DRAM'
    slot = share.build_top5(daily, '2026-10-23', '2026-10-23 12:37')
    assert [row['t'] for row in slot['bear']] == ranked[:5]
    assert [row['n'] for row in slot['bear']] == [5, 3, 3, 2, 2]
    assert [row['t'] for row in slot['bull']] == ['RSP', 'WMT']
    text = slot['posts']['en']['instagram']
    assert text.find('$META') < text.find('$MRNA') < text.find('$SOXX')
    assert '$SNDK' in text and '$DRAM' not in text
    assert slot['posts']['zh']['x'].find('$QQQ') < slot['posts']['zh']['x'].find('$META')


def main():
    test_tie_break()
    test_each_side_uses_its_own_accounts()
    test_missing_posts_sort_as_zero()
    test_zero_account_is_kept_and_bool_is_not()
    test_writeup_bear_top5()
    print('test_rank: tie-break, side counts, writeup bear QQQ META MRNA SOXX SNDK ok')


if __name__ == '__main__':
    main()
