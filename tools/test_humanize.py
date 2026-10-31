"""Social captions follow the house rules (Tim, 2026-10-29: 人性化點，不要再貼網站連結，唔好搞到好似詐騙).

No URL anywhere in a caption or first comment, no donate / newsletter / link-in-bio lines, at most 2 emoji,
at most 3 hashtags, one brand line and one short disclaimer, X within 270 (CJK counted double), Threads within
500, and zh in standard written Chinese. Checks tools/humanize.py on fixtures and every post file in data/.

  python3 tools/test_humanize.py
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from humanize import (BRAND, CANTONESE, DISC, EMOJI_RE, TAG_RE, URL_RE, humanize, humanize_tree,  # noqa: E402
                      xlen, zh_written)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ('data/social-posts.json', 'data/tutorial-posts.json', 'data/earnings-posts.json', 'data/macro-week.json')
SKIP = {'url', 'urls', 'link', 'title', 'quotes', 'themes', 'slides', 'av', 'avatar', 'bull_reasons', 'bear_reasons'}

OLD_ZH = '\n'.join([
    '10/29 X 大神共識快照：最多人睇好 $MU（7 個帳號）📊',
    '',
    '🔵 共同看多：21 隻・共同看空：1 隻',
    '・7 個帳號： $MU',
    '⚖️ 好淡分歧： $TSLA（5 好 2 淡）',
    '🔥 連續 2 日或以上都喺共同看多： $BE（3 日）',
    '',
    '最新數字 👉 https://thecrowdtape.com/zh/?utm_source=x&utm_medium=social&utm_campaign=daily',
    '☕ 鍾意就支持我哋 👉 https://thecrowdtape.com/zh/?utm_source=x&utm_medium=social&utm_campaign=daily#donate',
    '📬 訂閱免費電子報 👉 https://thecrowdtape.com/zh/?utm_campaign=newsletter',
    '連結在個人簡介',
    'Follow @thecrowdtape 每日睇街貨點諗。',
    '⚠️ 只係整理公開社交媒體貼文，唔構成投資建議。投資有風險，請自行判斷。',
    '#美股 #港人投資 #美股投資 #投資 #USStocks #MU #SKHY #ORCL',
])
OLD_EN = '\n'.join([
    'Oct 29 · Most bullish: $MU (7 accounts) 📊',
    '',
    '🗣 What X accounts say (28 days): 11 bullish, 0 bearish 👉 https://thecrowdtape.com/en/stock/MSFT/?utm_source=x',
    'Full 5-chapter brief 👉 https://thecrowdtape.com/en/earnings/MSFT/',
    'Try it 👉 [https://thecrowdtape.com/en/](https://thecrowdtape.com/en/)',
    '☕ Support the site 👉 https://thecrowdtape.com/en/#donate',
    'The site is free. Link in bio 👉 thecrowdtape.com',
    '⚠️ Not investment advice',
    '#StockMarket #USStocks #Stocks #MU #NVDA #AMD',
])


def assert_rules(text, lang, where, kind='post'):
    assert not URL_RE.search(text), (where, URL_RE.findall(text))
    assert len(EMOJI_RE.findall(text)) <= 2, (where, EMOJI_RE.findall(text))
    assert not re.search('[👉☕🙏]', text), where
    tags = TAG_RE.findall(text)
    assert len(tags) <= 3, (where, tags)
    if lang == 'zh':
        assert not CANTONESE.search(text), (where, CANTONESE.findall(text)[:5], text[:200])
    if kind == 'post':
        lines = [ln.strip() for ln in text.split('\n')]
        assert sum(ln in BRAND[lang] for ln in lines) == 1, (where, text[-200:])
        assert lines.count(DISC[lang]) == 1, (where, text[-200:])
        assert not re.search(r'(?i)paypal|支持我|support the site|link in bio|連結在個人簡介|訂閱免費電子報|free newsletter', text), where


def test_old_captions():
    zh = humanize(OLD_ZH, 'zh', 'post', 'x')
    assert_rules(zh, 'zh', 'old zh')
    assert '共同看多：21 檔・共同看空：1 檔' in zh, zh
    assert '$TSLA（5 多 2 空）' in zh and '$BE（3 天）' in zh, zh
    assert zh.split('\n')[-1] == '#美股 #MU #SKHY', zh
    assert humanize(zh, 'zh', 'post', 'x') == zh  # idempotent
    en = humanize(OLD_EN, 'en', 'post', 'threads')
    assert_rules(en, 'en', 'old en')
    assert 'What X accounts say (28 days): 11 bullish, 0 bearish' in en, en
    assert 'Full 5-chapter brief' not in en and 'Try it' not in en, en
    assert en.split('\n')[-1] == '#StockMarket #MU #NVDA', en
    assert humanize(en, 'en', 'post', 'threads') == en


def test_first_comment_and_tags():
    assert humanize('$NVDA 👉 https://thecrowdtape.com/zh/stock/NVDA/', 'zh', 'comment') == ''
    assert humanize('#美股 #港人投資 #美股投資 #MU #SKHY #ORCL', 'zh', 'tags') == '#美股 #MU #SKHY'
    asset = 'https://thecrowdtape.com/og/c/2026-10-29-1230-zh-1.jpg'
    assert humanize(asset, 'zh') == asset


def test_fit():
    long = '\n'.join(['今天 X 上討論最多的是 $GOOGL。'] + [f'・{i} 個帳號： $MU、 $SKHY、 $ORCL、 $SPY、 $QQQ' for i in range(30)])
    x = humanize(long, 'zh', 'post', 'x')
    th = humanize(long * 3, 'zh', 'post', 'threads')
    assert xlen(x) <= 270 and len(th) <= 500, (xlen(x), len(th))
    assert x.startswith('今天 X 上討論最多的是 $GOOGL。')


def test_zh_written():
    assert zh_written('唔構成投資建議') == '不構成投資建議'
    assert zh_written('你點睇 $ORCL？') == '你怎麼看 $ORCL？'
    assert zh_written('有冇人睇淡') == '有沒有人看空'
    assert zh_written('關係') == '關係'


def test_tree():
    data = {'posts': {'zh': {'x': OLD_ZH, 'first_comment': {'threads': '👉 https://thecrowdtape.com/zh/'},
                             'has_link': {'x': True}, 'story': '#美股 #港人投資 #美股投資 #MU #SKHY'}},
            'three_lines': {'x': {'en': {'text': OLD_EN, 'url': 'https://thecrowdtape.com/en/?utm_source=x'}}},
            'images': {'zh': ['https://thecrowdtape.com/og/a.jpg']}}
    humanize_tree(data)
    assert data['posts']['zh']['first_comment']['threads'] == ''
    assert data['posts']['zh']['has_link'] == {'x': False}
    assert data['posts']['zh']['story'] == '#美股 #MU #SKHY'
    assert data['three_lines']['x']['en']['url'] == ''
    assert data['images']['zh'] == ['https://thecrowdtape.com/og/a.jpg']
    again = json.loads(json.dumps(data))
    humanize_tree(again)
    assert again == data


def _walk(obj, path, lang=None, key=None, parent=None):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k not in SKIP:
                yield from _walk(v, f'{path}.{k}', k if k in ('zh', 'en') else lang, k, key)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f'{path}[{i}]', lang, key, parent)
    elif isinstance(obj, str) and not re.fullmatch(r'https?://\S+', obj.strip()):
        yield path, obj, lang, key, parent


def test_real_files():
    n = 0
    for name in FILES:
        path = os.path.join(ROOT, name)
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding='utf-8'))
        for where, text, lang, key, parent in _walk(data, name):
            if URL_RE.search(text):
                raise AssertionError((where, text[:200]))
            if key in ('x', 'threads', 'instagram', 'facebook', 'facebook_cta') and '\n' in text:
                n += 1
                assert_rules(text, lang or ('zh' if re.search('[一-鿿]', text) else 'en'), where,
                             'comment' if parent == 'first_comment' else 'post')
                if key == 'x':
                    assert xlen(text) <= 280, (where, xlen(text))
                if key == 'threads':
                    assert len(text) <= 500, (where, len(text))
    assert n >= 10, n


def main():
    test_old_captions()
    test_first_comment_and_tags()
    test_fit()
    test_zh_written()
    test_tree()
    test_real_files()
    print('test_humanize: no links, brand + disclaimer once, <=2 emoji, <=3 hashtags, written Chinese ok')


def test_tree_x_en_text_capped_at_280():
    import humanize as H
    raw = ('$NVDA leads the tape as chip names rip into the open while yields slip and the dollar eases. '
           'Breadth is improving with small caps joining in, and $AMD, $AVGO and $TSM all trade higher on volume. '
           'Watch the 11:30 ET reversal window; a hold above VWAP keeps the trend intact into lunch. '
           'https://xmktradar.github.io/ #stocks #NVDA #semis #trading')
    assert len(raw) > 280
    tree = {'intraday': {'slots': {'intraday_1': {'x': {'en': {'text': raw}}, 'threads': {'zh': {'text': raw}}}}}}
    H.humanize_tree(tree)
    slot = tree['intraday']['slots']['intraday_1']
    assert H.xlen(slot['x']['en']['text']) <= 280
    assert H.xlen(slot['x']['en']['text']) <= H.X_MAX
    assert slot['x']['en']['text'] == H.humanize(raw, None, 'post', 'x')
    assert len(slot['threads']['zh']['text']) <= 500


def test_tree_x_trilingual_afterclose_capped_at_280():
    """x_trilingual.afterclose.text is X (zh+en); humanize_tree must hard-cap ≤280 weighted.

    Same failure mode as the old nested x.en.text bug (PR #253): without platform='x' on
    the x_trilingual ancestor, brand/disc/tags push a free-account post over 280.
    """
    import humanize as H
    zh = ('$GOOGL，有 19 個帳號提到，3 個看多、5 個看空；最多人看多的則是 $LITE，共 4 個帳號。')
    en = ('$GOOGL got the most attention on X today (19 accounts, 3 bullish and 5 bearish), '
          'but $LITE had the most bulls (4 accounts).')
    raw = (f'{zh}\nhttps://thecrowdtape.com/zh/?utm_source=x&utm_medium=social&utm_campaign=afterclose\n'
           f'{en}\nhttps://thecrowdtape.com/?utm_source=x&utm_medium=social&utm_campaign=afterclose\n'
           '⚠ Public X posts only · Not investment advice')
    tree = {'x_trilingual': {'afterclose': {'post_at_hkt': '08:00', 'text': raw, 'xlen': 999, 'form': 'full'}}}
    # Uncapped humanize (no platform) exceeds 280 — the bug we are locking out.
    uncapped = H.humanize(raw, None, 'post', None)
    assert H.xlen(uncapped) > 280, H.xlen(uncapped)
    H.humanize_tree(tree)
    text = tree['x_trilingual']['afterclose']['text']
    assert H.xlen(text) <= 280, (H.xlen(text), text)
    assert H.xlen(text) <= H.X_MAX, H.xlen(text)
    assert tree['x_trilingual']['afterclose']['xlen'] == H.xlen(text)
    # No mid-token ellipsis junk like "4 ac…"
    for line in text.split('\n'):
        if line.endswith('…'):
            assert not re.search(r'\b\w{1,2}…$', line), line
            assert ' ac…' not in line

if __name__ == '__main__':
    test_tree_x_en_text_capped_at_280()
    test_tree_x_trilingual_afterclose_capped_at_280()
    main()
