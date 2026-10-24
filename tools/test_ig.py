"""Instagram captions: no URLs, one bio line, hashtag caps, handle dedupe, top5 window.

Run from the repo root: python3 tools/test_ig.py
"""
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['WORK_DIR'] = tempfile.mkdtemp(prefix='ig-test-')

import share  # noqa: E402
from utm import normalize_obj  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOCIAL = os.path.join(ROOT, 'data', 'social-posts.json')
HK = timezone(timedelta(hours=8))
DUP_RE = re.compile(r'@(\w+)[：:]\s*@\1[：:]')
WIN_RE = re.compile(r'^\d\d/\d\d \d\d:\d\d – \d\d:\d\d HKT$')
BIO = share.IG_BIO
URL_RE = re.compile(r'https?://', re.I)
TICK_TAG = re.compile(r'#([A-Z]{1,6})\b')
HASH = re.compile(r'#[^\s#]+')


def _walk_ig(obj, path='', lang=None):
    if isinstance(obj, dict):
        this = obj.get('lang') if obj.get('lang') in share.LANGS else lang
        if isinstance(obj.get('instagram'), str):
            yield path + '.instagram' if path else 'instagram', obj['instagram'], this
        for key, value in obj.items():
            nxt = key if key in share.LANGS else this
            yield from _walk_ig(value, f'{path}.{key}' if path else key, nxt)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from _walk_ig(value, f'{path}[{i}]', lang)


def _assert_ig_text(text, lang, where):
    assert isinstance(text, str), where
    assert URL_RE.search(text) is None, (where, text[-200:])
    assert 'thecrowdtape.com' not in text.lower(), (where, text[-200:])
    assert '(thecrowdtape.com)' not in text
    bios = [ln.strip() for ln in text.splitlines() if ln.strip() == BIO[lang or 'en'] or ln.strip() in BIO.values()]
    assert len(bios) == 1, (where, bios, text[-250:])
    assert bios[0] == BIO[lang or share._guess_ig_lang(text)]
    tags = HASH.findall(text)
    assert share.IG_MIN_TAGS <= len(tags) <= share.IG_MAX_TAGS, (where, tags)
    tickers = TICK_TAG.findall(text)
    assert len(tickers) <= 2, (where, tickers)


def test_dedupe_handle():
    assert share.dedupe_handle('Foo', '@Foo：hello') == 'hello'
    assert share.dedupe_handle('Foo', '@Foo: hello') == 'hello'
    assert share.dedupe_handle('Foo', '@Bar：kept') == '@Bar：kept'
    assert share.dedupe_handle('Foo', '@foo：same') == 'same'
    assert share.dedupe_handle('Foo', 'plain') == 'plain'
    line = share.quote_line('Foo', '@Foo：$WMT 防守', 'zh')
    assert line == '💬 @Foo：$WMT 防守'
    en = share.quote_line('Foo', '@Foo: $WMT is defensive', 'en')
    assert en == '💬 @Foo: "$WMT is defensive"'
    assert '@Foo：@Foo：' not in line
    assert DUP_RE.search(line) is None
    assert DUP_RE.search(en) is None


def _non_hash(text):
    return share.ig_non_hashtag_lines(text)


def _preserved_in_order(orig, out):
    """Every original non-hashtag line is still present, in the same order."""
    i = 0
    for line in out:
        if i < len(orig) and line == orig[i]:
            i += 1
    return i == len(orig)


def test_sanitizer_does_not_move_body_lines():
    """A list row such as ・$RSP is not hoisted, and is not deleted."""
    raw = '\n'.join([
        '今日 X 大神共識：最看好 2 隻／最看淡 5 隻',
        '',
        '2026-10-23',
        '數據範圍: 10/23 00:00 – 09:55 HKT',
        '',
        '最看好 2 隻',
        '・$RSP 3 個帳號',
        '・$WMT 2 個帳號',
        '',
        '最看淡 5 隻',
        '・$QQQ 5 個帳號',
        '',
        '連結在個人簡介',
        '⚠️ 唔構成投資建議',
    ])
    key = '最看好 $RSP（3 個帳號）・最看淡 $QQQ（5 個帳號）'
    # Line 1 already has a digit, so a supplied key line is not prepended.
    out = share.sanitize_instagram(raw, 'zh', key_line=key)
    assert out.split('\n', 1)[0] == '今日 X 大神共識：最看好 2 隻／最看淡 5 隻'
    assert _preserved_in_order(_non_hash(raw), _non_hash(out))
    assert out.count('・$RSP 3 個帳號') == 1
    assert out.count('・$WMT 2 個帳號') == 1
    assert out.index('最看好 2 隻') < out.index('・$RSP 3 個帳號') < out.index('・$WMT 2 個帳號')
    again = share.sanitize_instagram(out, 'zh', key_line=key)
    assert again == out

    # No structured key line: a title with no ticker and no digit stays, and the list stays.
    weak = '本週最看好\n\n$AMZN 14 個帳號看好\n$RSP 4 個帳號看好\n\n⚠️ 唔構成投資建議\n#美股 #AMZN #RSP'
    kept = share.sanitize_instagram(weak, 'zh')
    assert kept.split('\n', 1)[0] == '本週最看好'
    assert _preserved_in_order(_non_hash(weak), _non_hash(kept))
    assert kept.index('$AMZN 14 個帳號看好') < kept.index('$RSP 4 個帳號看好')

    # A key line is prepended only when line 1 lacks both a $TICKER and a digit.
    bare = '今日共識\n\n最看好 2 隻\n・$RSP 3 個帳號\n・$WMT 2 個帳號\n\n⚠️ 唔構成投資建議\n#美股'
    added = share.sanitize_instagram(bare, 'zh', key_line=key)
    assert added.split('\n', 1)[0] == key
    assert _preserved_in_order(_non_hash(bare), _non_hash(added))
    assert added.index('今日共識') < added.index('・$RSP 3 個帳號') < added.index('・$WMT 2 個帳號')
    unchanged = share.sanitize_instagram(bare, 'zh')
    assert unchanged.split('\n', 1)[0] == '今日共識'
    assert _preserved_in_order(_non_hash(bare), _non_hash(unchanged))


def test_top5_ig_key_line_wording():
    bulls = [{'t': 'RSP', 'n': 3}, {'t': 'WMT', 'n': 2}]
    bears = [{'t': 'QQQ', 'n': 5}]
    assert share.top5_ig_key_line('zh', bulls, bears) == '最看好 $RSP（3 個帳號）・最看淡 $QQQ（5 個帳號）'
    assert share.top5_ig_key_line('en', bulls, bears) == 'Most bullish $RSP (3 accounts) · most bearish $QQQ (5 accounts)'
    assert share.top5_ig_key_line('ko', bulls, bears) == '가장 강세 $RSP (계정 3개) · 가장 약세 $QQQ (계정 5개)'
    assert share.top5_ig_key_line('en', bulls, []) == 'Most bullish $RSP (3 accounts)'
    assert share.top5_ig_key_line('en', [{'t': 'RSP', 'n': 1}], []) == 'Most bullish $RSP (1 account)'
    assert share.top5_ig_key_line('en', [], []) == ''


def test_sanitize_instagram():
    raw = (
        '最多人睇好 $WMT（2 個帳號）\n\n'
        '💬 @Acc：@Acc：why\n\n'
        '最新數字 👉 https://thecrowdtape.com/zh/\n'
        '☕ 鍾意就請我哋飲杯咖啡：link in bio，網站底部 PayPal 捐款 🙏\n'
        '網站約每 4 個鐘更新，最新數字 👉 link in bio (thecrowdtape.com)\n'
        'Follow @thecrowdtape 每日睇街貨點諗。\n\n'
        '⚠️ 唔構成投資建議\n\n'
        '#美股 #港人投資 #美股投資 #投資 #USStocks #StockMarket #香港投資 #WMT #QQQ #MRNA'
    )
    out = share.sanitize_instagram(raw, 'zh')
    _assert_ig_text(out, 'zh', 'sanitize')
    assert '💬 @Acc：why' in out
    assert DUP_RE.search(out) is None
    tags = HASH.findall(out)
    assert tags[:3] == ['#美股', '#美股投資', '#港人投資']
    assert tags[-2:] == ['#WMT', '#QQQ']
    again = share.sanitize_instagram(out, 'zh')
    assert again == out


def test_caption_ig():
    s = {'bull': [{'t': 'WMT'}], 'bear': [], 'split': [], 'accounts': 4, 'tickers': 1}
    items = [{'t': 'WMT', 'n': 2, 'bull': 2, 'bear': 0, 'streak': 1}]
    quote = {'acc': 'Mr_Derivatives', 'text': '@Mr_Derivatives：$WMT再度展現防守特性'}
    for lang in share.LANGS:
        cap = share.caption(lang, '2026-10-23', s, items, '10/23 00:00 – 10/23 04:58 HKT', quote)
        _assert_ig_text(cap['instagram'], lang, f'caption.{lang}')
        head = cap['instagram'].split('\n', 1)[0]
        if lang == 'zh':
            assert '最多人睇好' in head and '$WMT' in head
        elif lang == 'en':
            assert 'Most bullish' in head and '$WMT' in head
        else:
            assert '가장 강세' in head and '$WMT' in head
        assert DUP_RE.search(cap['instagram']) is None
        assert 'https://thecrowdtape.com' in cap['facebook']
        assert 'https://thecrowdtape.com' in cap['x']


def test_top5_window_and_headings():
    ms = int(datetime(2026, 10, 21, 6, 10, tzinfo=HK).timestamp() * 1000)
    daily = {
        'from': '2026-10-21T00:00',
        'to': '2026-10-21T23:59',
        'bull': [{'t': 'ZZZ', 'nb': 1, 'rows': [{'acc': 'a', 'ms': ms}]}],
        'bear': [{'t': 'AAA', 'nr': 9}],
        'split': [],
    }
    slot = share.build_top5(daily, '2026-10-21', '2026-10-21 07:05')
    assert WIN_RE.match(slot['window']), slot['window']
    assert re.search(r'\d{4}-\d{2}-\d{2}T', slot['window']) is None
    assert '23:59' not in slot['window']
    assert slot['window'] == '10/21 00:00 – 06:10 HKT'
    assert slot['bull'] == [{'t': 'ZZZ', 'n': 1}]
    assert slot['bear'] == [{'t': 'AAA', 'n': 9}]
    for lang in share.LANGS:
        labels = share.top5_labels(lang, 1, 1)
        ig = slot['posts'][lang]['instagram']
        _assert_ig_text(ig, lang, f'top5.{lang}')
        assert ig.split('\n', 1)[0] == share.top5_ig_key_line(lang, slot['bull'], slot['bear'])
        assert '・$ZZZ' in ig and '・$AAA' in ig
        assert ig.index('・$ZZZ') < ig.index('・$AAA')
        assert labels['heading'] in ig
        assert labels['bull'] in ig and labels['bear'] in ig
        assert slot['posts'][lang]['has_link']['instagram'] is False
        assert 'https://' not in ig
    # Fallback when there is no rows[].ms: social-posts.json window end.
    empty = {'from': '2026-10-21T00:00', 'to': '2026-10-21T23:59', 'bull': [], 'bear': []}
    fb = share.build_top5(empty, '2026-10-21', '2026-10-21 07:05',
                          fallback_window='10/21 00:00 – 10/21 04:58 HKT')
    assert fb['window'] == '10/21 00:00 – 04:58 HKT'
    assert re.search(r'\d{4}-\d{2}-\d{2}T', fb['window']) is None


def test_normalize_strips_ig_urls():
    data = {
        'posts': {
            'en': {'instagram': 'Most bullish: $NVDA, 8 accounts\nSee https://thecrowdtape.com/en/stock/NVDA/\n#StockMarket #USStocks #A #B #C #D'}
        },
        'top5': {
            'posts': {
                'zh': {
                    'instagram': 'https://thecrowdtape.com/zh/stock/AAA/\n#美股 #WMT #QQQ #MRNA',
                    'has_link': {'instagram': True, 'x': True},
                }
            }
        },
    }
    normalize_obj(data)
    _assert_ig_text(data['posts']['en']['instagram'], 'en', 'norm.en')
    _assert_ig_text(data['top5']['posts']['zh']['instagram'], 'zh', 'norm.zh')
    assert data['top5']['posts']['zh']['has_link']['instagram'] is False
    again = json.loads(json.dumps(data))
    normalize_obj(again)
    assert again == data


def test_real_social_posts():
    data = json.load(open(SOCIAL, encoding='utf-8'))
    blob = json.dumps(data, ensure_ascii=False)
    assert DUP_RE.search(blob) is None, DUP_RE.findall(blob)[:5]
    n = 0
    for path, text, lang in _walk_ig(data):
        n += 1
        _assert_ig_text(text, lang or share._guess_ig_lang(text), path)
    assert n >= 3, n
    top = data.get('top5') or {}
    if top:
        assert WIN_RE.match(top.get('window') or ''), top.get('window')
        assert re.search(r'\d{4}-\d{2}-\d{2}T', top.get('window') or '') is None
        for lang in share.LANGS:
            posts = (top.get('posts') or {}).get(lang) or {}
            if isinstance(posts.get('has_link'), dict) and 'instagram' in posts['has_link']:
                assert posts['has_link']['instagram'] is False
            labels = share.top5_labels(lang, len(top.get('bull') or []), len(top.get('bear') or []))
            if posts.get('instagram'):
                ig = posts['instagram']
                assert labels['heading'] in ig
                assert labels['bull'] in ig
                assert labels['bear'] in ig
                # A moved list bullet must not become line 1, and every row stays a bullet.
                assert not ig.split('\n', 1)[0].startswith('・')
                for row in (top.get('bull') or []) + (top.get('bear') or []):
                    assert f'・${row["t"]} ' in ig


def main():
    try:
        test_dedupe_handle()
        test_sanitizer_does_not_move_body_lines()
        test_top5_ig_key_line_wording()
        test_sanitize_instagram()
        test_caption_ig()
        test_top5_window_and_headings()
        test_normalize_strips_ig_urls()
        test_real_social_posts()
        print('test_ig: captions, sanitizer, hashtags, handles, top5 window ok')
    finally:
        shutil.rmtree(os.environ['WORK_DIR'], ignore_errors=True)


if __name__ == '__main__':
    main()
