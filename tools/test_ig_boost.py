"""Instagram reach upgrades: CTA last slide, at most 3 hashtags, ig_reel.

Run from the repo root: python3 tools/test_ig_boost.py
"""
import json
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['WORK_DIR'] = tempfile.mkdtemp(prefix='ig-boost-')

import date_kst  # noqa: E402
import ig_boost  # noqa: E402
import macro_week  # noqa: E402
import share  # noqa: E402
import humanize  # noqa: E402
from humanize import BRAND, zh_written  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOCIAL = os.path.join(ROOT, 'data', 'social-posts.json')
MACRO = os.path.join(ROOT, 'data', 'macro-week.json')
HASH = re.compile(r'#[^\s#]+')
URL_RE = re.compile(r'https?://', re.I)
TICKER_RE = re.compile(r'\$[A-Z]{1,6}\b')
EMOJI_OR_HASH = re.compile(r'[\W_#]+', re.UNICODE)


def _walk_ig_captions(obj, path='', lang=None):
    """Instagram captions in obj; '' (English after tools/ig_plan.py: Instagram is Chinese only) is left out."""
    for loc, text, lg in _walk_ig_all(obj, path, lang):
        if text.strip():
            yield loc, text, lg


def _walk_ig_all(obj, path='', lang=None):
    if isinstance(obj, dict):
        this = obj.get('lang') if obj.get('lang') in share.LANGS else lang
        ig = obj.get('instagram')
        if isinstance(ig, str):
            yield (path + '.instagram' if path else 'instagram'), ig, this
        elif isinstance(ig, dict):
            for key, value in ig.items():
                lg = key if key in share.LANGS else this
                if isinstance(value, str):
                    yield f'{path}.instagram.{key}', value, lg
                elif isinstance(value, dict) and isinstance(value.get('text'), str):
                    yield f'{path}.instagram.{key}.text', value['text'], lg
        if ('video_path' in obj or 'video_expected_path' in obj) and isinstance(obj.get('caption'), dict):
            for key, value in obj['caption'].items():
                if key in share.LANGS and isinstance(value, str):
                    yield f'{path}.caption.{key}', value, key
        for key, value in obj.items():
            if key == 'instagram':
                continue
            nxt = key if key in share.LANGS else this
            if isinstance(value, (dict, list)):
                yield from _walk_ig_all(value, f'{path}.{key}' if path else key, nxt)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from _walk_ig_all(value, f'{path}[{i}]', lang)


def _first_line(text):
    for ln in (text or '').splitlines():
        if ln.strip():
            return ln.strip()
    return ''


def _assert_caption(text, lang, where):
    assert isinstance(text, str) and text.strip(), where
    assert URL_RE.search(text) is None, (where, text[-200:])
    assert 'thecrowdtape.com' not in text.lower(), (where, text[-200:])
    bios = [ln.strip() for ln in text.splitlines() if ln.strip() in BRAND['zh'] + BRAND['en']]
    assert len(bios) == 1, (where, bios)
    tags = HASH.findall(text)
    assert share.IG_MIN_TAGS <= len(tags) <= share.IG_MAX_TAGS, (where, tags)
    head = _first_line(text)
    # A title with no ticker and no digit is kept when no structured key line was built.
    # Emoji-only and hashtag-only first lines are still rejected.
    leftover = EMOJI_OR_HASH.sub('', HASH.sub('', head))
    assert leftover or TICKER_RE.search(head) or re.search(r'\d', head), (where, head)


def _assert_cta_last(urls, lang, where):
    assert isinstance(urls, list) and len(urls) >= 2, (where, urls)
    last = urls[-1]
    assert last.endswith(f'ig-cta-{lang}.jpg') or f'ig-cta-{lang}.jpg' in last, (where, last)
    assert not any(ig_boost.is_cta_url(u, lang) for u in urls[:-1]), (where, urls)
    rel = share.IG_CTA_REL.format(lang=lang)
    assert os.path.isfile(os.path.join(ROOT, rel)), rel


def test_cta_slide_last_and_files_exist():
    social = json.load(open(SOCIAL, encoding='utf-8'))
    slots = social.get('slots') or {}
    found = 0
    for key, slot in slots.items():
        if not isinstance(slot, dict):
            continue
        images = slot.get('images') or {}
        fb = slot.get('images_fb') or {}
        for lang in share.LANGS:
            urls = images.get(lang)
            if isinstance(urls, list) and len(urls) >= 2:
                _assert_cta_last(urls, lang, f'slots.{key}.images.{lang}')
                found += 1
            fb_urls = fb.get(lang)
            if isinstance(fb_urls, list):
                assert not any(ig_boost.is_cta_url(u) for u in fb_urls), (key, lang, fb_urls)
    # Early in the day only the 12:30 slot exists (one per language), so do not demand more than that.
    assert found >= min(3, len(share.LANGS) * len(slots)), found
    daily = social.get('ig_threads_daily') or {}
    for lang in share.LANGS:
        ip = ((daily.get(lang) or {}).get('image_post') or {})
        urls = ip.get('images')
        if isinstance(urls, list) and urls:
            _assert_cta_last(urls, lang, f'ig_threads_daily.{lang}')
    top_images = social.get('images') or {}
    for lang in share.LANGS:
        assert isinstance(top_images.get(lang), str), top_images.get(lang)

    macro = json.load(open(MACRO, encoding='utf-8'))
    images = macro.get('images') or {}
    ig_images = macro.get('ig_images') or {}
    for lang in share.LANGS:
        assert isinstance(images.get(lang), str), images.get(lang)
        _assert_cta_last(ig_images[lang], lang, f'macro.ig_images.{lang}')
        assert ig_images[lang][0] == images[lang] or images[lang] in ig_images[lang][0]


def test_ig_captions_rules():
    n = 0
    for path, name in ((SOCIAL, 'social'), (MACRO, 'macro')):
        data = json.load(open(path, encoding='utf-8'))
        for loc, text, lang in _walk_ig_captions(data):
            n += 1
            _assert_caption(text, lang or share._guess_ig_lang(text), f'{name}.{loc}')
    assert n >= 5, n


def test_ig_reel_structure():
    social = json.load(open(SOCIAL, encoding='utf-8'))
    reel = social['ig_reel']
    day = social.get('date_kst') or social.get('date')
    assert reel['date_kst'] == day
    assert reel['slot'] == 'daily'
    expected = f'assets/reels/{day}-daily.mp4'
    assert reel['video_expected_path'] == expected
    assert reel['video_path'] in (None, expected)
    if not os.path.isfile(os.path.join(ROOT, expected)):
        assert reel['video_path'] is None
    for lang in share.LANGS:
        if lang != 'en' or reel['caption'][lang]:  # English is '' after tools/ig_plan.py
            _assert_caption(reel['caption'][lang], lang, f'social.ig_reel.{lang}')

    macro = json.load(open(MACRO, encoding='utf-8'))
    mreel = macro['ig_reel']
    # Posting Saturday at 20:00 HKT. Window `to` can be earlier mid-week; when the
    # window ends on that Saturday, `to` equals `date` and the reel date matches both.
    mday = date_kst.macro_post_date_kst(macro.get('date'))
    assert mday and mday == macro.get('date')
    assert mreel['date_kst'] == mday
    assert mreel['date_kst'] == macro.get('date_kst')
    to = macro.get('to')
    if to and to != macro.get('date'):
        assert mreel['date_kst'] != to
    assert mreel['slot'] == 'macro-week'
    mexp = f'assets/reels/{mday}-macro-week.mp4'
    assert mreel['video_expected_path'] == mexp
    assert mreel['video_path'] in (None, mexp)
    if not os.path.isfile(os.path.join(ROOT, mexp)):
        assert mreel['video_path'] is None
    for lang in share.LANGS:
        if lang != 'en' or mreel['caption'][lang]:
            _assert_caption(mreel['caption'][lang], lang, f'macro.ig_reel.{lang}')


def test_video_path_null_and_fixture():
    tmp = tempfile.mkdtemp(prefix='ig-reel-')
    try:
        day, slot = '2026-10-26', 'daily'
        expected = ig_boost.reel_expected_path(day, slot)
        assert expected == 'assets/reels/2026-10-26-daily.mp4'
        caps = {lang: share.sanitize_instagram(f'$NVDA 8 accounts\n#StockMarket', lang) for lang in share.LANGS}
        missing = ig_boost.build_ig_reel(day, slot, captions=caps, root=tmp)
        assert missing['video_path'] is None
        assert missing['video_expected_path'] == expected
        os.makedirs(os.path.join(tmp, 'assets', 'reels'))
        open(os.path.join(tmp, expected.replace('/', os.sep)), 'wb').write(b'ftyp')
        present = ig_boost.build_ig_reel(day, slot, captions=caps, root=tmp)
        assert present['video_path'] == expected
        assert present['video_expected_path'] == expected
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_macro_week_hashtags_max_5():
    data = json.load(open(MACRO, encoding='utf-8'))
    for loc, text, lang in _walk_ig_captions(data):
        tags = HASH.findall(text)
        assert len(tags) <= 5, (loc, tags)
        # humanize.py keeps one general tag + at most 2 tickers, so a 1-ticker week has 2 tags (2026-11-01)
        assert len(tags) >= 2, (loc, tags)


def test_apply_idempotent_and_fills_tags():
    data = {
        'date': '2026-10-23',
        'date_kst': '2026-10-23',
        'posts': {
            'en': {'instagram': 'Most bullish: $WMT, 2 accounts\n#StockMarket'},
        },
        'slots': {
            '1230': {
                'images': {
                    'zh': [
                        'https://thecrowdtape.com/og/c/2026-10-23-1230-zh-1.jpg',
                        'https://thecrowdtape.com/og/c/2026-10-23-1230-zh-2.jpg',
                    ]
                },
                'images_fb': {
                    'zh': ['https://thecrowdtape.com/og/c/2026-10-23-1230-zh-1-fb.jpg']
                },
                'posts': {
                    'zh': {'instagram': '最多人睇好 $WMT（2 個帳號）\n#美股 #WMT #QQQ #MRNA #AA #BB'}
                },
            }
        },
        'images': {'zh': 'https://thecrowdtape.com/og/social-zh.png?v=1'},
    }
    ig_boost.apply_social_obj(data, root=ROOT)
    ig_boost.apply_social_obj(data, root=ROOT)
    zh_imgs = data['slots']['1230']['images']['zh']
    assert zh_imgs[-1] == share.ig_cta_url('zh')
    assert zh_imgs.count(share.ig_cta_url('zh')) == 1
    assert data['slots']['1230']['images_fb']['zh'] == ['https://thecrowdtape.com/og/c/2026-10-23-1230-zh-1-fb.jpg']
    assert data['images']['zh'] == 'https://thecrowdtape.com/og/social-zh.png?v=1'
    _assert_caption(data['posts']['en']['instagram'], 'en', 'apply.en')
    _assert_caption(data['slots']['1230']['posts']['zh']['instagram'], 'zh', 'apply.zh')
    assert data['ig_reel']['slot'] == 'daily'
    assert data['ig_reel']['video_path'] is None

    macro = {
        'date': '2026-10-31',
        'images': {'zh': 'https://thecrowdtape.com/og/macro-zh.png',
                   'en': 'https://thecrowdtape.com/og/macro-en.png'},
        'posts': {
            'zh': {'instagram': '🌐 本週宏觀｜201 個帳號\n#美股 #宏觀經濟 #聯儲局 #港人投資 #美股投資 #USStocks #Macro #StockMarket #投資'},
            'en': {'instagram': 'This week in macro · 201 accounts\n#Macro #StockMarket #USStocks #Fed #Economy #Investing #FinTwit #WallStreet'},
        },
    }
    ig_boost.apply_macro_obj(macro, root=ROOT)
    for lang in share.LANGS:
        _assert_cta_last(macro['ig_images'][lang], lang, f'apply.macro.{lang}')
        assert isinstance(macro['images'][lang], str)
        _assert_caption(macro['posts'][lang]['instagram'], lang, f'apply.macro.cap.{lang}')
        assert len(HASH.findall(macro['posts'][lang]['instagram'])) <= 5
    assert macro['ig_reel']['slot'] == 'macro-week'


def _non_hash(text):
    """Body lines as tools/humanize.py leaves them: link, bio and disclaimer lines out, written Chinese."""
    out = []
    for ln in share.ig_non_hashtag_lines(text):
        c = humanize._clean_line(ln, 'zh')
        if c:
            out.append(zh_written(c))
    return out


def _preserved(orig, out):
    i = 0
    for line in out:
        if i < len(orig) and line == orig[i]:
            i += 1
    return i == len(orig)


def test_key_line_preserves_body_and_macro_date():
    bulls = [{'t': 'RSP', 'n': 3}, {'t': 'WMT', 'n': 2}]
    bears = [{'t': 'QQQ', 'n': 5}, {'t': 'META', 'n': 3}]
    raw = '\n'.join([
        '今日 X 大神共識：最看好 2 隻／最看淡 5 隻',
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
        '',
        '#美股 #美股投資 #港人投資 #RSP #WMT',
    ])
    data = {
        'date': '2026-10-23',
        'date_kst': '2026-10-23',
        'posts': {'en': {'instagram': 'Most bullish: $WMT, 2 accounts\n#StockMarket'}},
        'top5': {
            'bull': bulls,
            'bear': bears,
            'posts': {
                'zh': {'instagram': raw},
                'en': {'instagram': 'Top 2 bullish\n\n・$RSP 3 accounts\n・$WMT 2 accounts\n\n・$QQQ 5 accounts\n#StockMarket'},
            },
        },
        'images': {'zh': 'https://thecrowdtape.com/og/social-zh.png?v=1'},
    }
    ig_boost.apply_social_obj(data, root=ROOT)
    ig_boost.apply_social_obj(data, root=ROOT)
    zh = data['top5']['posts']['zh']['instagram']
    assert zh.split('\n', 1)[0] == '最看好 $RSP（3 個帳號）・最看空 $QQQ（5 個帳號）'
    assert zh.count('最看好 $RSP（3 個帳號）・最看空 $QQQ（5 個帳號）') == 1
    assert _preserved(_non_hash(raw), _non_hash(zh))
    assert zh.index('最看好 2 檔') < zh.index('・$RSP 3 個帳號') < zh.index('・$WMT 2 個帳號')
    en = data['top5']['posts']['en']['instagram']
    assert en.split('\n', 1)[0] == 'Most bullish $RSP (3 accounts) · most bearish $QQQ (5 accounts)'
    assert '・$RSP 3 accounts' in en and '・$WMT 2 accounts' in en

    week = {
        'top': ['other'],
        'themes': [{'theme': 'other', 'bull': 10, 'bear': 11, 'neu': 19}],
    }
    assert macro_week.macro_ig_key_line('zh', week) == '本週宏觀：最多人講「其他」（利好 10・利淡 11）'
    assert macro_week.macro_ig_key_line('en', week) == 'This week in macro: most discussed "Other" (bullish 10 · bearish 11)'
    # 20:00 HKT Saturday stays that Saturday in KST. A 23:30 HKT clock would be the next day.
    assert date_kst.macro_post_date_kst('2026-10-31') == '2026-10-31'
    assert date_kst.macro_post_date_kst('2026-10-31') != '2026-10-25'

    old_zh = '🌐 本週宏觀｜201 個帳號點睇大環境（10/19–10/25）\n\n1️⃣ 其他：利好 10・利淡 11・中性 19（比上週轉好 ▲）\n\n#美股 #宏觀經濟 #聯儲局 #港人投資 #美股投資 #USStocks'
    macro = {
        'date': '2026-10-31',
        'to': '2026-10-25',
        'from': '2026-10-19',
        'frozen': False,
        'top': ['other'],
        'themes': [{'theme': 'other', 'bull': 10, 'bear': 11, 'neu': 19, 'n': 40}],
        'images': {'zh': 'https://thecrowdtape.com/og/macro-zh.png',
                   'en': 'https://thecrowdtape.com/og/macro-en.png'},
        'posts': {
            'zh': {'instagram': old_zh},
            'en': {'instagram': 'This week in macro · 201 accounts\n\n1️⃣ Other: bullish 10 · bearish 11\n#Macro #StockMarket #USStocks #Fed #Economy'},
        },
    }
    ig_boost.apply_macro_obj(macro, root=ROOT)
    ig_boost.apply_macro_obj(macro, root=ROOT)
    assert macro['date_kst'] == '2026-10-31'
    assert macro['ig_reel']['date_kst'] == '2026-10-31'
    assert macro['ig_reel']['date_kst'] != macro['to']
    assert macro['ig_reel']['video_expected_path'] == 'assets/reels/2026-10-31-macro-week.mp4'
    mzh = macro['posts']['zh']['instagram']
    assert mzh.split('\n', 1)[0] == '本週宏觀：最多人講「其他」（利好 10・利空 11）'
    assert mzh.count('本週宏觀：最多人講「其他」（利好 10・利空 11）') == 1
    assert _preserved(_non_hash(old_zh), _non_hash(mzh))
    assert '1. 其他：利好 10・利空 11・中性 19（比上週轉好 ▲）' in mzh
    assert macro['posts']['en']['instagram'].split('\n', 1)[0] == 'This week in macro: most discussed "Other" (bullish 10 · bearish 11)'
    assert '1. Other: bullish 10 · bearish 11' in macro['posts']['en']['instagram']


def test_macro_ig_bio_once_per_lang():
    """Macro IG captions have the brand line exactly once per language and no URLs."""
    week = {
        'accounts': 10,
        'top': ['rates'],
        'themes': [{'theme': 'rates', 'bull': 5, 'bear': 1, 'neu': 2, 'arrow': 'up', 'quotes': {}}],
    }
    for lang in share.LANGS:
        cap = macro_week.posts(lang, week, '10/19–10/25')['instagram']
        lines = [ln.strip() for ln in cap.splitlines() if ln.strip() in BRAND['zh'] + BRAND['en']]
        assert len(lines) == 1 and lines[0] in BRAND[lang], (lang, lines, cap)
        assert URL_RE.search(cap) is None, (lang, cap[-200:])
        assert 'thecrowdtape.com' not in cap.lower(), (lang, cap[-200:])
    data = json.load(open(MACRO, encoding='utf-8'))
    for loc, text, lang in _walk_ig_captions(data):
        brand = BRAND[lang or share._guess_ig_lang(text)]
        n = sum(1 for ln in text.splitlines() if ln.strip() in brand)
        assert n == 1, (loc, n)


def test_sanitize_tags_capped():
    out = share.sanitize_instagram('Most bullish: $WMT, 2 accounts\n#StockMarket #USStocks #Investing #MU #NVDA #AMD', 'en')
    tags = HASH.findall(out)
    assert tags == ['#StockMarket', '#MU', '#NVDA'], tags
    assert out.split('\n', 1)[0].startswith('Most bullish: $WMT')


def main():
    try:
        test_sanitize_tags_capped()
        test_key_line_preserves_body_and_macro_date()
        test_apply_idempotent_and_fills_tags()
        test_video_path_null_and_fixture()
        test_cta_slide_last_and_files_exist()
        test_ig_captions_rules()
        test_ig_reel_structure()
        test_macro_week_hashtags_max_5()
        test_macro_ig_bio_once_per_lang()
        print('test_ig_boost: CTA last slide, captions at most 3 hashtags, ig_reel, video_path ok')
    finally:
        shutil.rmtree(os.environ['WORK_DIR'], ignore_errors=True)


if __name__ == '__main__':
    main()
