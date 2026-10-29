"""tools/utm.py tag_url: one UTM scheme for thecrowdtape.com page URLs.

utm_source is x, threads, instagram or facebook (not ig or fb). utm_medium is social.
Asset URLs (/og/, /assets/, images) and other hosts are left alone.
Social captions carry no links at all since 2026-10-29 (Tim); tools/test_humanize.py checks the post files.

  python3 tools/test_utm_scheme.py
"""
import os
import sys

os.environ.setdefault('UTM_PROMO', '0')  # this file checks the plain scheme

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import share  # noqa: E402
from utm import tag_text, tag_url  # noqa: E402


def test_tag_url_normalises():
    fresh = tag_url('https://thecrowdtape.com/zh/#donate', 'x', 'daily')
    assert fresh == 'https://thecrowdtape.com/zh/?utm_source=x&utm_medium=social&utm_campaign=daily#donate', fresh

    replaced = tag_url(
        'https://thecrowdtape.com/en/?utm_campaign=newsletter&foo=1&utm_source=fb&utm_medium=post#top',
        'fb', 'newsletter')
    assert replaced == (
        'https://thecrowdtape.com/en/?foo=1&utm_source=facebook&utm_medium=social&utm_campaign=newsletter#top'
    ), replaced

    middle = tag_url(
        'https://thecrowdtape.com/en/stock/NVDA/?a=1&utm_medium=post&b=2&utm_source=ig&utm_campaign=old&c=3',
        'instagram', 'tutorial')
    assert middle == (
        'https://thecrowdtape.com/en/stock/NVDA/?a=1&b=2&c=3'
        '&utm_source=instagram&utm_medium=social&utm_campaign=tutorial'
    ), middle
    assert tag_url(middle, 'ig', 'tutorial') == middle

    upper = tag_url(
        'https://thecrowdtape.com/zh/?UTM_SOURCE=fb&UTM_MEDIUM=POST&UTM_CAMPAIGN=daily&x=1',
        'threads', 'daily')
    assert upper == 'https://thecrowdtape.com/zh/?x=1&utm_source=threads&utm_medium=social&utm_campaign=daily', upper

    dup = tag_url('https://thecrowdtape.com/zh/?utm_source=x&utm_source=fb&utm_medium=email&a=1', 'x', 'daily')
    assert dup == 'https://thecrowdtape.com/zh/?a=1&utm_source=x&utm_medium=social&utm_campaign=daily', dup

    asset = 'https://thecrowdtape.com/og/social-zh.png?v=1'
    assert tag_url(asset, 'x', 'daily') == asset
    assert tag_url('https://thecrowdtape.com/og/c/a.jpg', 'facebook', 'carousel-1230') == 'https://thecrowdtape.com/og/c/a.jpg'
    assert tag_url('https://thecrowdtape.com/assets/icon-192.png', 'x', 'daily') == 'https://thecrowdtape.com/assets/icon-192.png'
    other = 'https://example.com/zh/?utm_source=x&utm_medium=post'
    assert tag_url(other, 'x', 'daily') == other
    assert tag_text('see ' + other + ' and https://thecrowdtape.com/zh/', 'x', 'daily') == (
        'see ' + other + ' and https://thecrowdtape.com/zh/?utm_source=x&utm_medium=social&utm_campaign=daily')

    long_url = tag_url('https://thecrowdtape.com/zh/?utm_source=fb&utm_medium=post&utm_campaign=daily', 'facebook', 'daily')
    bare = 'https://thecrowdtape.com/zh/?utm_source=fb&utm_medium=post&utm_campaign=daily'
    assert share.xlen(bare) == share.xlen(long_url) == 23


def main():
    test_tag_url_normalises()
    print('test_utm_scheme: tag_url ok')


if __name__ == '__main__':
    main()
