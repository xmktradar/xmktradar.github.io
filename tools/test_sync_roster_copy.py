#!/usr/bin/env python3
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'sync_roster_copy', Path(__file__).resolve().parent / 'sync_roster_copy.py'
)
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def main():
    src = (
        '目前追蹤 208 個帳號，其中 207 個在 X、1 個在 Truth Social，分成 6 類。\n'
        'The Crowd Tape｜201 個美股帳號，今日共同看好／看淡邊隻？\n'
        '201 帳號｜6 類｜每 8 小時更新\n'
        'It currently tracks 201 accounts (200 on X and 1 on Truth Social).\n'
        '這星期我們追蹤的 201 個 X 帳號，最常聊的宏觀話題是這幾個\n'
        'Tracked accounts: 201\n- X: 200\n- Truth Social: 1\n'
        '市值 200 億美元以上美股\n'
    )
    out = s.apply_frames(src, 454, 453, 1)
    assert '目前追蹤 454 個帳號，其中 453 個在 X、1 個在 Truth Social' in out
    assert '454 個美股帳號' in out
    assert '454 帳號｜6 類｜每 8 小時更新' in out
    assert 'tracks 454 accounts (453 on X and 1 on Truth Social)' in out
    assert '這星期我們追蹤的 453 個 X 帳號' in out
    assert 'Tracked accounts: 454\n- X: 453\n- Truth Social: 1' in out
    assert '市值 200 億美元以上美股' in out
    html = (
        '<title>201 個美股帳號</title>'
        '<script type="application/json" id="dash-data">'
        '{"tracked":{"accounts":['
        + ','.join('{"handle":"h%s","category":"宏觀"}' % i for i in range(3))
        + ',{"handle":"realDonaldTrump","platform":"truthsocial","category":"大人物／企業家"}'
        + ']}}</script>'
        '<p>201 帳號｜6 類｜每 8 小時更新</p>'
    )
    n, nx, nt = s.official_counts(html)
    assert (n, nx, nt) == (4, 3, 1)
    print('test_sync_roster_copy: ok')


if __name__ == '__main__':
    main()
