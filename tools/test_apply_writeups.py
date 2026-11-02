# -*- coding: utf-8 -*-
"""Unit tests for writeup HTML cite-link sanitizer (post post / stops.post glue)."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'apply_writeups', Path(__file__).resolve().parent / 'apply_writeups.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_space_before_cite_link():
    html = 'rising to $17.25.<a href="https://x.com/a/status/1">post</a>'
    out = m.clean_html(html)
    assert out is not None
    assert '. <a href="https://x.com/a/status/1">post</a>' in out or '.&nbsp;<a' in out or out.endswith('post</a>')
    assert '25.<a' not in out


def test_adjacent_post_post_cites():
    html = ('rising to $17.25. '
            '<a href="https://x.com/a/status/1">post</a> '
            '<a href="https://x.com/b/status/2">post</a> $SKHY')
    out = m.clean_html(html)
    assert out is not None
    assert 'post post' not in out.lower()
    assert out.count('>post<') == 1
    assert '>·<' in out or '>·</' in out or '·' in out


def test_adjacent_zh_cites():
    html = ('見 <a href="https://x.com/a/status/1">原帖</a>'
            '<a href="https://x.com/b/status/2">原帖</a>')
    out = m.clean_html(html)
    assert out is not None
    assert out.count('>原帖<') == 1


def test_weekly_summary_item_runs_sanitizer():
    item = m.summary_item({
        'date': '2026-11-01',
        'brief': 'ok <a href="https://x.com/a/status/1">post</a>',
        'full': 'x <a href="https://x.com/a/status/1">post</a> <a href="https://x.com/b/status/2">post</a>',
        'html': 'rising to $17.25.<a href="https://x.com/a/status/1">post</a> <a href="https://x.com/b/status/2">post</a> $SKHY',
    })
    assert item and 'post post' not in item['html'].lower()
    assert '25.<a' not in item['html']


if __name__ == '__main__':
    test_space_before_cite_link()
    test_adjacent_post_post_cites()
    test_adjacent_zh_cites()
    test_weekly_summary_item_runs_sanitizer()
    print('ok')
