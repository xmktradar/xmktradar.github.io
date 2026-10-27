"""Advertise pages use data/advertise-stats.json and hide missing metrics.

Offline: no network. Renders zh/en from the Chinese master and checks the
pages written by tools/advertise.py.

Run from pages/: python3 tools/test_advertise.py
"""
import os
import re
import sys
from urllib.parse import unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import advertise  # noqa: E402

ROOT = advertise.ROOT
HAN = advertise.HAN
HIDDEN = (
    '待更新',
    '數字待更新',
    'to be updated',
    'Figures to be updated',
    'Stripe',
    'stripe',
    '電子報訂閱人數',
    'Newsletter subscribers',
    'Instagram 追蹤人數',
    'Instagram followers',
    'Threads 追蹤人數',
    'Threads followers',
    'Facebook 追蹤人數',
    'Facebook followers',
)
ROW = {
    'zh': {
        'updated': '更新日期：2026-10-21',
        'monthly': '<span>每月訪客（近 30 日）</span><b>761 人，1349 次瀏覽</b>',
        'followers': '<span>X 追蹤人數</span><b>50</b>',
        'impress': '<span>X 近 7 日曝光（截至 2026-10-20）</span><b>~5.6K</b>',
        'countries': '中國、美國、台灣、香港',
        'daily': '每日以中英雙語喺 X、Instagram、Threads 同 Facebook 發佈（每種語言各自翻譯）',
        'pay': '付款用 PayPal 發票。',
        'note': '頁面瀏覽按網站語言。',
        'zh': '<span>中文</span><b>81%</b>',
        'en': '<span>英文</span><b>15%</b>',
        'subject': '廣告合作查詢',
    },
    'en': {
        'updated': 'Last updated: 2026-10-21',
        'monthly': '<span>Monthly visitors (last 30 days)</span><b>761 users, 1349 page views</b>',
        'followers': '<span>X followers</span><b>50</b>',
        'impress': '<span>X impressions, past 7 days (as of 2026-10-20)</span><b>~5.6K</b>',
        'countries': 'China, United States, Taiwan, Hong Kong',
        'daily': 'Published daily in Chinese and English on X, Instagram, Threads and Facebook (each language translated separately).',
        'pay': 'Payment is by PayPal invoice.',
        'note': 'Page views by site language.',
        'zh': '<span>Chinese</span><b>81%</b>',
        'en': '<span>English</span><b>15%</b>',
        'subject': 'Advertising enquiry',
    },
}


def body_without_langnav(html):
    return re.sub(r'<nav class="lang".*?</nav>', '', html, flags=re.S)


def assert_page(lang, html):
    want = ROW[lang]
    for bad in HIDDEN:
        assert bad not in html, (lang, bad)
    assert want['updated'] in html
    assert want['monthly'] in html
    assert want['followers'] in html
    assert want['impress'] in html
    assert want['countries'] in html
    assert want['daily'] in html
    assert want['pay'] in html
    assert want['note'] in html
    assert want['zh'] in html and want['en'] in html
    assert '761' in html and '1349' in html and '~5.6K' in html
    assert '2026-10-21' in html and '2026-10-20' in html
    assert '81%' in html and '15%' in html
    blocks = re.findall(r'<ul class="stats">(.*?)</ul>', html, flags=re.S)
    assert len(blocks) == 2, (lang, len(blocks))
    assert blocks[0].count('<li>') == 3, (lang, blocks[0])
    assert blocks[1].count('<li>') == 2, (lang, blocks[1])
    assert 'href="#contact"' not in html
    hrefs = re.findall(r'href="(mailto:[^"]+)"', html)
    assert len(hrefs) >= 2, (lang, hrefs)
    for href in hrefs:
        assert href.startswith('mailto:grokbottimli@gmail.com?subject='), href
        subject = unquote(href.split('subject=', 1)[1])
        assert subject == 'The Crowd Tape: ' + want['subject'], (lang, subject)
    assert html.count('data-u="grokbottimli"') == 2
    assert html.count('data-d="gmail.com"') == 2
    assert 'id="contact-mail"' in html
    assert "querySelectorAll('a.contact-mail, a#contact-mail')" in html
    assert html.count('G-42CSNJ8DF9') == 2
    assert 'G-' not in html.replace('G-42CSNJ8DF9', '')
    assert '557682506' not in html
    assert '{{' not in html
    assert '{updated}' not in html and '{users}' not in html and '{as_of}' not in html
    assert f'lang="{advertise.LANGS[lang]}"' in html
    assert f'https://thecrowdtape.com/{lang}/advertise/' in html
    if lang != 'zh':
        left = HAN.findall(body_without_langnav(html))
        assert not left, (lang, ''.join(left[:24]))


def test_real_pages():
    stats = advertise.load_stats()
    assert stats['updated'] == '2026-10-21'
    assert stats['monthly_users'] == 761
    assert stats['monthly_views'] == 1349
    assert stats['x_followers'] == 50
    assert stats['x_impressions_7d'] == {'value': '~5.6K', 'as_of': '2026-10-20'}
    assert stats['lang_views_pct'] == {'zh': 81, 'en': 15}
    assert stats['top_countries'] == ['China', 'United States', 'Taiwan', 'Hong Kong']
    for key in ('newsletter_subscribers', 'instagram_followers', 'threads_followers', 'facebook_followers'):
        assert key not in stats
    template = advertise.load_template()
    rendered = {}
    for lang in ('zh', 'en'):
        rendered[lang] = advertise.page(template, lang, stats)
        assert_page(lang, rendered[lang])
        disk = open(os.path.join(ROOT, lang, 'advertise', 'index.html'), encoding='utf-8').read()
        assert disk == rendered[lang], lang + ' advertise/index.html is stale; run python3 tools/advertise.py'
    root = open(os.path.join(ROOT, 'advertise', 'index.html'), encoding='utf-8').read()
    assert root == rendered['zh']
    assert '待更新' not in advertise.load_template()
    assert 'Stripe' not in advertise.load_template()


def test_missing_keys_render_nothing():
    template = advertise.load_template()
    stats = {'updated': '2026-10-21', 'x_followers': 50}
    html = advertise.page(template, 'en', stats)
    assert 'Last updated: 2026-10-21' in html
    assert '<span>X followers</span><b>50</b>' in html
    for bad in HIDDEN:
        assert bad not in html, bad
    # The publishing line still names the channels. Follower rows stay hidden.
    assert 'Instagram, Threads and Facebook' in html
    assert 'Language split' not in html
    assert 'Top countries' not in html
    assert '81%' not in html
    blocks = re.findall(r'<ul class="stats">(.*?)</ul>', html, flags=re.S)
    assert len(blocks) == 1 and blocks[0].count('<li>') == 1
    assert 'Instagram' not in blocks[0] and 'Threads' not in blocks[0] and 'Facebook' not in blocks[0]
    assert 'Newsletter' not in blocks[0]
    bare = advertise.stat_items({})
    assert bare == []
    only = advertise.stat_items({'monthly_users': 9})
    assert len(only) == 1 and '>9<' in only[0] and '次瀏覽' not in only[0]
    views = advertise.stat_items({'monthly_views': 8})
    assert len(views) == 1 and '>8<' in views[0] and '人，' not in views[0]
    nodate = advertise.stat_items({'x_impressions_7d': {'value': '100'}})
    assert len(nodate) == 1 and '100' in nodate[0] and '{as_of}' not in nodate[0]
    assert '截至' not in nodate[0]


def test_present_keys_render_rows():
    template = advertise.load_template()
    stats = {
        'updated': '2026-10-21',
        'monthly_users': 761,
        'monthly_views': 1349,
        'newsletter_subscribers': 12,
        'x_followers': 50,
        'x_impressions_7d': {'value': '~5.6K', 'as_of': '2026-10-20'},
        'instagram_followers': 3,
        'threads_followers': 4,
        'facebook_followers': 5,
        'lang_views_pct': {'zh': 81, 'en': 15},
        'top_countries': ['China', 'United States', 'Taiwan', 'Hong Kong'],
    }
    rows = advertise.stat_items(stats)
    labels = '\n'.join(rows)
    assert '電子報訂閱人數' in labels
    assert 'Instagram 追蹤人數' in labels
    assert 'Threads 追蹤人數' in labels
    assert 'Facebook 追蹤人數' in labels
    assert labels.count('<li>') == 7
    for lang, marker in (('en', 'Newsletter subscribers'),):
        html = advertise.page(template, lang, stats)
        assert marker in html
        assert '<b>12</b>' in html and '<b>3</b>' in html and '<b>4</b>' in html and '<b>5</b>' in html
        assert 'Stripe' not in html and '待更新' not in html
        left = HAN.findall(body_without_langnav(html))
        assert not left, (lang, ''.join(left[:24]))
        assert 'mailto:grokbottimli@gmail.com?subject=' in html


def main():
    test_real_pages()
    test_missing_keys_render_nothing()
    test_present_keys_render_rows()
    print('test_advertise: zh/en numbers, hidden rows, mailto ok')


if __name__ == '__main__':
    main()
