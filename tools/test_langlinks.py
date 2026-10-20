"""Language-matched links in auto social posts.

Every thecrowdtape.com link in a post uses that post's language
(/zh/, /en/, /ko/, including /<lang>/stock/<T>/). UTM tags stay.
Trilingual X posts put one link on each language line and stay within
280 (X counts each URL as 23).

Run from pages/: python3 tools/test_langlinks.py
"""
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['WORK_DIR'] = tempfile.mkdtemp(prefix='langlinks-test-')

import share  # noqa: E402
import carousel  # noqa: E402
import macro_week  # noqa: E402
import tutorial  # noqa: E402
from utm import tag_posts, tag_url  # noqa: E402

URL_RE = re.compile(r'https://thecrowdtape\.com[^\s)\]"\']*')
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


def assert_lang_urls(text, lang, campaign=None, source=None, required=True):
    urls = URL_RE.findall(text or '')
    if required:
        assert urls, text
    for u in urls:
        path = u.split('thecrowdtape.com', 1)[1]
        assert path.startswith(f'/{lang}/'), (lang, u)
        assert not path.startswith('/stock/'), u
        assert 'thecrowdtape.com/?' not in u and not path.startswith('/?'), u
        if campaign:
            assert f'utm_campaign={campaign}' in u, u
            assert 'utm_medium=post' in u, u
        if source:
            assert f'utm_source={source}' in u, u
    return urls


def assert_tri(text, campaign):
    assert share.xlen(text) <= 280, (share.xlen(text), text)
    assert 'https://thecrowdtape.com/?' not in text
    assert re.search(r'https://thecrowdtape\.com/stock/', text) is None
    lines = text.split('\n')
    seen = []
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s or s.startswith(('⚠', '#', '・')):
            i += 1
            continue
        m = re.search(r'https://\S+', s)
        if m and m.start() == 0:
            i += 1
            continue
        if m:
            head, url, i = s[:m.start()].strip(), m.group(0), i + 1
        else:
            assert i + 1 < len(lines), text
            head, url, i = s, lines[i + 1].strip(), i + 2
        assert url.startswith('https://'), (head, url)
        if re.search(r'[\uac00-\ud7af]', head):
            lang = 'ko'
        elif re.search(r'[\u4e00-\u9fff]', head):
            lang = 'zh'
        else:
            lang = 'en'
        assert f'https://thecrowdtape.com/{lang}/' in url, (lang, head, url)
        assert 'utm_source=x' in url and 'utm_medium=post' in url, url
        assert f'utm_campaign={campaign}' in url, url
        seen.append(lang)
    assert seen == ['zh', 'en', 'ko'], seen
    found = []
    for u in URL_RE.findall(text):
        for lang in share.LANGS:
            if f'/{lang}/' in u.split('thecrowdtape.com', 1)[1]:
                found.append(lang)
                break
        else:
            raise AssertionError(u)
    assert found == ['zh', 'en', 'ko'], found
    # Each URL counts 23, not its real length.
    bare = URL_RE.sub('', text)
    assert share.xlen(text) == share.xlen(bare) + 23 * len(found), (share.xlen(text), share.xlen(bare), found)


def test_xlen_url_is_23():
    url = 'https://thecrowdtape.com/zh/?utm_source=x&utm_medium=post&utm_campaign=afterclose'
    assert len(url) > 23
    assert share.xlen(url) == 23
    assert share.xlen('開' + url + '好') == 27
    assert share.xlen(url + '\n' + url) == 47


def test_single_language():
    s = {'bull': [{'t': 'NVDA'}], 'bear': [], 'split': [], 'accounts': 4, 'tickers': 1}
    items = [{'t': 'NVDA', 'n': 2, 'bull': 2, 'bear': 0, 'streak': 1}]
    win = '10/20 00:04 – 10/20 05:02 HKT'
    bundle = {}
    for lang in share.LANGS:
        cap = share.caption(lang, DAY, s, items, win, None)
        for key in ('x', 'threads', 'facebook'):
            assert_lang_urls(cap[key], lang)
            assert share.xlen(cap['x']) <= 280
        assert_lang_urls(cap['reddit']['body'], lang)
        assert_lang_urls(cap['instagram'], lang, required=False)
        cta = share.facebook_cta(cap['facebook'], lang)
        needle = f'https://thecrowdtape.com/{lang}/?utm_source=fb&utm_medium=post&utm_campaign=newsletter'
        assert needle in cta, cta[-180:]
        assert_lang_urls(cta, lang)
        bundle[lang] = {'x': cap['x'], 'threads': cap['threads'], 'facebook': cap['facebook'],
                        'instagram': cap['instagram']}
    tag_posts(bundle, 'daily')
    for lang, by in bundle.items():
        assert_lang_urls(by['x'], lang, campaign='daily', source='x')
        assert_lang_urls(by['facebook'], lang, campaign='daily', source='fb')
        assert_lang_urls(by['threads'], lang, campaign='daily', source='threads')


def test_trilingual_afterclose_and_premarket():
    text, form = share.trilingual_text(POSTS, 'afterclose')
    assert form == 'short', form
    assert_tri(text, 'afterclose')
    heads = share._x_headlines(text)
    assert set(heads) == {'zh', 'en', 'ko'}
    assert '$AMZN' in heads['zh'] and '$AMZN' in heads['en'] and '$AMZN' in heads['ko']

    sp = {
        'date': DAY,
        'posts': POSTS,
        'x_facts': {
            'AMZN': {'bull': 3, 'bear': 1, 'n': 5},
            'NVDA': {'bull': 3, 'bear': 0, 'n': 4},
        },
    }
    pm, pm_form = share.premarket_text(sp)
    assert pm_form == 'short'
    assert_tri(pm, 'premarket')
    assert '開市前' in pm and 'pre-market' in pm and '개장 전' in pm
    assert '各 3' in pm and 'each' in pm and '각각' in pm
    assert share._minus_urls(pm) != share._minus_urls(text)

    # No x_facts: framed headlines, still one link per language.
    bare, _ = share.premarket_text({'date': DAY, 'posts': POSTS})
    assert_tri(bare, 'premarket')
    assert bare.split('\n')[0].startswith('10/20 開市前：')


def test_long_headlines_keep_three_links():
    # Script sits next to the ticker so shortening the tail still leaves a language marker.
    fat = {
        'zh': {'x': '10/20 $NVDA 看好' + '甲' * 200},
        'en': {'x': 'Oct 20 $NVDA bullish ' + 'word ' * 80},
        'ko': {'x': '10/20 $NVDA 강세' + '가' * 200},
    }
    text, _ = share.trilingual_text(fat, 'afterclose')
    assert_tri(text, 'afterclose')


def test_stock_page_links():
    for lang, ticker in (('zh', 'NVDA'), ('en', 'AAPL'), ('ko', 'TSLA')):
        raw = share.stock_url(lang, '$' + ticker.lower())
        assert raw == f'https://thecrowdtape.com/{lang}/stock/{ticker}/', raw
        tagged = tag_url(raw, 'x', 'tutorial')
        assert tagged.startswith(f'https://thecrowdtape.com/{lang}/stock/{ticker}/?')
        assert 'utm_source=x' in tagged and 'utm_medium=post' in tagged
        assert 'utm_campaign=tutorial' in tagged
        assert 'thecrowdtape.com/stock/' not in tagged
    # A root or wrong-language stock path is rewritten under the post's language.
    assert share.page_url('zh', '/stock/AMD/') == 'https://thecrowdtape.com/zh/stock/AMD/'
    assert share.page_url('en', 'ko/stock/AMD/') == 'https://thecrowdtape.com/en/stock/AMD/'
    assert share.page_url('ko', 'stock/QQQ') == 'https://thecrowdtape.com/ko/stock/QQQ/'
    assert 'thecrowdtape.com/stock/' not in share.page_url('zh', 'stock/NVDA/')

    for lang in share.LANGS:
        url = tag_url(share.page_url(lang, 'stock/NVDA/'), 'x', 'tutorial')
        post = tutorial.posts(lang, 21, 27, {'t': 'stock page', 'b': 'A stock page.', 'how': 'Open it.'}, url)
        for key in ('x', 'threads', 'facebook'):
            assert_lang_urls(post[key], lang)
            assert f'/{lang}/stock/NVDA/' in post[key]
        assert_lang_urls(post['reddit']['body'], lang)
        assert f'/{lang}/stock/NVDA/' in post['reddit']['body']
        assert 'utm_source=x' in post['x'] and 'utm_campaign=tutorial' in post['x']


def test_other_generators():
    for lang in share.LANGS:
        post = carousel.versions(lang, '10/20 headline', ['・$NVDA 2 accounts'], ['NVDA'])
        for key in ('x', 'threads', 'facebook'):
            assert_lang_urls(post[key], lang)
            assert share.xlen(post['x']) <= 280
        week = {'accounts': 4, 'themes': [], 'top': []}
        macro = macro_week.posts(lang, week, '10/13–10/19')
        for key in ('x', 'threads', 'facebook'):
            assert_lang_urls(macro[key], lang)
        assert_lang_urls(macro['reddit']['body'], lang)
        assert f'https://thecrowdtape.com/{lang}/#macro' in macro['x']
        assert f'https://thecrowdtape.com/{lang}/#donate' in macro['facebook']


def main():
    try:
        test_xlen_url_is_23()
        test_single_language()
        test_trilingual_afterclose_and_premarket()
        test_long_headlines_keep_three_links()
        test_stock_page_links()
        test_other_generators()
        print('test_langlinks: single-language, trilingual, stock, carousel, macro, tutorial ok')
    finally:
        shutil.rmtree(os.environ['WORK_DIR'], ignore_errors=True)


if __name__ == '__main__':
    main()
