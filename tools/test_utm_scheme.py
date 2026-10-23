"""Every thecrowdtape.com page URL in social and tutorial post text uses one scheme.

utm_source is x, threads, instagram or facebook (not ig or fb). utm_medium is social.
utm_campaign is the slot: daily, carousel-<key>, premarket, afterclose, newsletter
(on the facebook_cta signup line only), tutorial, top5, weekly_thread, hot_stock,
discussion, weekend, atomic, three_lines, or why. weekly_thread langs.<lang> lists are X posts.
first_comment is tagged with the platform of that field (threads or facebook).
atomic text and first_comment use source threads and campaign atomic.
Asset URLs (/og/, /assets/, images) are left alone. Threads stays within 500
code points. X stays within 280 by xlen (each URL counts 23).

Run from the repo root after python3 tools/utm.py --apply:
  python3 tools/test_utm_scheme.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import share  # noqa: E402
from utm import (URL_RE, normalize_file, normalize_obj, tag_text, tag_url)  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOCIAL = os.path.join(ROOT, 'data', 'social-posts.json')
TUTORIAL = os.path.join(ROOT, 'data', 'tutorial-posts.json')
UTM_NAMES = ('utm_source', 'utm_medium', 'utm_campaign')
SOURCES = {'x': 'x', 'instagram': 'instagram', 'threads': 'threads', 'facebook': 'facebook', 'facebook_cta': 'facebook'}
NEWS_MARKERS = ('newsletter', '電子報', '뉴스레터')
ASSET_EXT = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.xml')


def is_asset_path(path):
    low = path.lower()
    return path.startswith('/og/') or path.startswith('/assets/') or low.endswith(ASSET_EXT)


def parsed(url):
    """(path, [(name, value), ...], fragment including the leading #) for one URL."""
    body, sep, frag = url.partition('#')
    path_and_host, _, query = body.partition('?')
    path = path_and_host.split('thecrowdtape.com', 1)[-1]
    pairs = []
    for piece in query.split('&'):
        if not piece:
            continue
        name, _, value = piece.partition('=')
        pairs.append((name, value))
    return path, pairs, ('#' + frag) if sep else ''


def assert_scheme(url, source, campaign, where):
    assert url.startswith('https://thecrowdtape.com'), (where, url)
    path, pairs, _frag = parsed(url)
    assert not is_asset_path(path), (where, url)
    names = [name for name, _ in pairs]
    for key in UTM_NAMES:
        assert names.count(key) == 1, (where, url, key, names)
    utm = [(name, value) for name, value in pairs if name in UTM_NAMES]
    assert pairs[-3:] == utm, (where, url, pairs)
    assert utm == [
        ('utm_source', source),
        ('utm_medium', 'social'),
        ('utm_campaign', campaign),
    ], (where, url, utm)
    assert source in ('x', 'threads', 'instagram', 'facebook'), (where, source)
    assert 'utm_medium=post' not in url, (where, url)
    assert 'utm_source=fb&' not in url and not url.split('#', 1)[0].endswith('utm_source=fb'), (where, url)
    assert 'utm_source=ig&' not in url and not url.split('#', 1)[0].endswith('utm_source=ig'), (where, url)


def expected_campaign(field, slot, text, start):
    """Newsletter stays on the facebook_cta signup line. Every other link uses the slot."""
    if field == 'facebook_cta':
        prefix = text[text.rfind('\n', 0, start) + 1:start]
        if any(mark in prefix for mark in NEWS_MARKERS):
            return 'newsletter'
    return slot


def iter_platform_posts(posts, campaign, where):
    if not isinstance(posts, dict):
        return
    for lang, by in posts.items():
        if not isinstance(by, dict):
            continue
        for field, source in SOURCES.items():
            if isinstance(by.get(field), str):
                yield by[field], field, source, campaign, lang, f'{where}.{lang}.{field}'
        fc = by.get('first_comment')
        if isinstance(fc, dict):
            for field, source in SOURCES.items():
                if isinstance(fc.get(field), str):
                    yield fc[field], field, source, campaign, lang, f'{where}.{lang}.first_comment.{field}'
        elif isinstance(fc, str):
            yield fc, 'threads', 'threads', campaign, lang, f'{where}.{lang}.first_comment'


def iter_weekly(node, where):
    """weekly_thread posts are X, campaign weekly_thread. langs.<lang> is a list of posts."""
    if isinstance(node, str):
        yield node, 'x', 'x', 'weekly_thread', None, where
        return
    if isinstance(node, list):
        for i, item in enumerate(node):
            if isinstance(item, str):
                yield item, 'x', 'x', 'weekly_thread', None, f'{where}[{i}]'
            else:
                yield from iter_weekly(item, f'{where}[{i}]')
        return
    if not isinstance(node, dict):
        return
    langs = node.get('langs')
    if isinstance(langs, dict):
        for lang, posts in langs.items():
            if isinstance(posts, str):
                yield posts, 'x', 'x', 'weekly_thread', lang, f'{where}.langs.{lang}'
            elif isinstance(posts, list):
                for i, item in enumerate(posts):
                    if isinstance(item, str):
                        yield item, 'x', 'x', 'weekly_thread', lang, f'{where}.langs.{lang}[{i}]'
    posts = node.get('posts')
    if isinstance(posts, dict):
        for lang, by in posts.items():
            if isinstance(by, str):
                yield by, 'x', 'x', 'weekly_thread', lang, f'{where}.posts.{lang}'
            elif isinstance(by, list):
                for i, item in enumerate(by):
                    if isinstance(item, str):
                        yield item, 'x', 'x', 'weekly_thread', lang, f'{where}.posts.{lang}[{i}]'
            elif isinstance(by, dict):
                for field, value in by.items():
                    if isinstance(value, str) and (field in SOURCES or field == 'text'):
                        yield value, field if field in SOURCES else 'x', 'x', 'weekly_thread', lang, f'{where}.posts.{lang}.{field}'
        return
    if isinstance(langs, dict):
        return
    if isinstance(node.get('text'), str):
        yield node['text'], 'x', 'x', 'weekly_thread', None, f'{where}.text'
    for key, value in node.items():
        if key in ('text', 'langs', 'posts'):
            continue
        if isinstance(value, str) and 'https://thecrowdtape.com' in value:
            yield value, 'x', 'x', 'weekly_thread', None, f'{where}.{key}'
        elif isinstance(value, (dict, list)):
            yield from iter_weekly(value, f'{where}.{key}')


def iter_atomic(items, where='atomic_posts'):
    if not isinstance(items, list):
        return
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        lang = item.get('lang')
        for field in ('text', 'hook', 'first_comment', 'hashtags'):
            value = item.get(field)
            if isinstance(value, str) and ('https://thecrowdtape.com' in value or field == 'text'):
                yield value, 'threads', 'threads', 'atomic', lang, f'{where}[{i}].{field}'
            elif field == 'first_comment' and isinstance(value, dict):
                for plat, source in SOURCES.items():
                    if isinstance(value.get(plat), str):
                        yield value[plat], plat, source, 'atomic', lang, f'{where}[{i}].first_comment.{plat}'


def iter_text_platforms(node, campaign, where, platforms):
    """{platform: {lang: {text, url}}} used by three_lines and why_posts."""
    if not isinstance(node, dict):
        return
    for plat in platforms:
        block = node.get(plat)
        if not isinstance(block, dict):
            continue
        source = SOURCES.get(plat, plat)
        for lang, entry in block.items():
            if isinstance(entry, dict):
                if isinstance(entry.get('text'), str):
                    yield entry['text'], plat, source, campaign, lang, f'{where}.{plat}.{lang}.text'
                if isinstance(entry.get('url'), str):
                    yield entry['url'], plat, source, campaign, lang, f'{where}.{plat}.{lang}.url'
            elif isinstance(entry, str):
                yield entry, plat, source, campaign, lang, f'{where}.{plat}.{lang}'


def iter_social(data):
    yield from iter_platform_posts(data.get('posts'), 'daily', 'posts')
    slots = data.get('slots')
    if isinstance(slots, dict):
        for key, slot in slots.items():
            if isinstance(slot, dict):
                yield from iter_platform_posts(slot.get('posts'), f'carousel-{key}', f'slots.{key}.posts')
    tri = data.get('x_trilingual')
    if isinstance(tri, dict):
        for kind, entry in tri.items():
            if isinstance(entry, dict) and isinstance(entry.get('text'), str):
                yield entry['text'], 'x', 'x', str(kind), None, f'x_trilingual.{kind}.text'
            elif isinstance(entry, str):
                yield entry, 'x', 'x', str(kind), None, f'x_trilingual.{kind}'
    top = data.get('top5')
    if isinstance(top, dict):
        posts = top.get('posts') if isinstance(top.get('posts'), dict) else top
        yield from iter_platform_posts(posts, 'top5', 'top5.posts')
    if 'weekly_thread' in data:
        yield from iter_weekly(data['weekly_thread'], 'weekly_thread')
    for slot, campaign in (('hot_stock', 'hot_stock'), ('discussion', 'discussion')):
        node = data.get(slot)
        if isinstance(node, dict):
            yield from iter_platform_posts(node.get('posts'), campaign, f'{slot}.posts')
    weekend = data.get('weekend')
    if isinstance(weekend, dict):
        for i, item in enumerate(weekend.get('posts') or []):
            if isinstance(item, dict):
                yield from iter_platform_posts(item.get('langs'), 'weekend', f'weekend.posts[{i}].langs')
    if isinstance(data.get('atomic_posts'), list):
        yield from iter_atomic(data['atomic_posts'])
    if isinstance(data.get('three_lines'), dict):
        yield from iter_text_platforms(
            data['three_lines'], 'three_lines', 'three_lines', ('x', 'threads', 'facebook', 'instagram'))
    if isinstance(data.get('why_posts'), list):
        for i, item in enumerate(data['why_posts']):
            if isinstance(item, dict):
                yield from iter_text_platforms(item, 'why', f'why_posts[{i}]', ('threads', 'x'))
    intra = data.get('intraday')
    if isinstance(intra, dict):
        for key, slot in (intra.get('slots') or {}).items():
            if not isinstance(slot, dict):
                continue
            xen = (slot.get('x') or {}).get('en') if isinstance(slot.get('x'), dict) else None
            if isinstance(xen, dict) and isinstance(xen.get('text'), str):
                yield xen['text'], 'x', 'x', str(key), 'en', f'intraday.slots.{key}.x.en.text'
            th = slot.get('threads') if isinstance(slot.get('threads'), dict) else {}
            for lang, entry in th.items():
                if isinstance(entry, dict) and isinstance(entry.get('text'), str):
                    yield entry['text'], 'threads', 'threads', str(key), lang, f'intraday.slots.{key}.threads.{lang}.text'
                elif isinstance(entry, str):
                    yield entry, 'threads', 'threads', str(key), lang, f'intraday.slots.{key}.threads.{lang}'


def iter_tutorial(data):
    yield from iter_platform_posts(data.get('posts'), 'tutorial', 'posts')


def walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from walk_strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk_strings(value)


def check_posts(data, iterator, label):
    """Assert scheme, Threads <= 500 and X <= 280. Returns campaigns seen."""
    seen = set()
    page_urls = 0
    for text, field, source, slot, lang, where in iterator(data):
        if field == 'threads' or (isinstance(lang, str) and where.endswith('.threads')):
            assert len(text) <= 500, (label, where, len(text))
        if source == 'x':
            assert share.xlen(text) <= 280, (label, where, share.xlen(text), text)
        for match in URL_RE.finditer(text):
            url = match.group(0)
            path, _, _ = parsed(url)
            if is_asset_path(path):
                assert 'utm_source=' not in url and 'utm_medium=' not in url, (label, where, url)
                continue
            campaign = expected_campaign(field, slot, text, match.start())
            assert_scheme(url, source, campaign, f'{label}:{where}')
            seen.add(campaign)
            page_urls += 1
    assert page_urls, label
    return seen


def check_assets_untagged(data, label):
    for text in walk_strings(data):
        for match in URL_RE.finditer(text):
            url = match.group(0)
            path, _, _ = parsed(url)
            if is_asset_path(path):
                assert 'utm_source=' not in url and 'utm_medium=' not in url and 'utm_campaign=' not in url, (label, url)


def test_real_files():
    social = json.load(open(SOCIAL, encoding='utf-8'))
    tutorial = json.load(open(TUTORIAL, encoding='utf-8'))
    seen = check_posts(social, iter_social, 'social-posts.json')
    assert 'daily' in seen, seen
    assert 'premarket' in seen and 'afterclose' in seen, seen
    assert 'newsletter' in seen, seen
    assert any(c.startswith('carousel-') and c != 'carousel' for c in seen), seen
    assert 'carousel' not in seen, seen
    tut = check_posts(tutorial, iter_tutorial, 'tutorial-posts.json')
    assert tut == {'tutorial'}, tut
    check_assets_untagged(social, 'social-posts.json')
    check_assets_untagged(tutorial, 'tutorial-posts.json')
    # Reddit is not one of the platform fields, so its page URLs stay untagged.
    for lang, by in social['posts'].items():
        body = (by.get('reddit') or {}).get('body') or ''
        for url in URL_RE.findall(body):
            assert 'utm_source=' not in url and 'utm_medium=' not in url, (lang, url)
    for lang in share.LANGS:
        assert len(social['posts'][lang]['threads']) <= 500
        assert share.xlen(social['posts'][lang]['x']) <= 280
        assert len(tutorial['posts'][lang]['threads']) <= 500
        assert share.xlen(tutorial['posts'][lang]['x']) <= 280
    for kind in ('premarket', 'afterclose'):
        text = social['x_trilingual'][kind]['text']
        assert share.xlen(text) <= 280, (kind, share.xlen(text))
    # New slots are optional on a given day. When present, their page URLs use the slot campaign.
    if social.get('hot_stock'):
        assert 'hot_stock' in seen, seen
    if social.get('discussion'):
        assert 'discussion' in seen, seen
    if isinstance(social.get('weekend'), dict) and social['weekend'].get('posts'):
        assert 'weekend' in seen, seen
    if social.get('atomic_posts'):
        assert 'atomic' in seen, seen
    if social.get('three_lines'):
        assert 'three_lines' in seen, seen
    if social.get('why_posts'):
        assert 'why' in seen, seen


def test_real_files_idempotent():
    for src, name in ((SOCIAL, 'social-posts.json'), (TUTORIAL, 'tutorial-posts.json')):
        raw = open(src, encoding='utf-8').read()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, name)
            open(path, 'w', encoding='utf-8').write(raw)
            normalize_file(path)
            assert open(path, encoding='utf-8').read() == raw, name


def test_tag_url_normalises():
    fresh = tag_url('https://thecrowdtape.com/zh/#donate', 'x', 'daily')
    assert fresh == 'https://thecrowdtape.com/zh/?utm_source=x&utm_medium=social&utm_campaign=daily#donate', fresh

    replaced = tag_url(
        'https://thecrowdtape.com/ko/?utm_campaign=newsletter&foo=1&utm_source=fb&utm_medium=post#top',
        'fb', 'newsletter')
    assert replaced == (
        'https://thecrowdtape.com/ko/?foo=1&utm_source=facebook&utm_medium=social&utm_campaign=newsletter#top'
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


def _fixture():
    live = 'https://thecrowdtape.com/en/?utm_source=threads&utm_medium=post&utm_campaign=old'
    donate = 'https://thecrowdtape.com/en/?utm_medium=post&utm_source=threads&utm_campaign=old#donate'
    threads = '\n\n'.join([
        'H' * 460,
        f"Live numbers 👉 {live}\n☕ Support the site 👉 {donate}\n⚠️ Not investment advice",
        '#StockMarket',
    ])
    return {
        'posts': {
            'en': {
                'x': 'See https://thecrowdtape.com/en/?utm_source=x&utm_medium=post&utm_campaign=daily',
                'threads': threads,
                'facebook': 'Live https://thecrowdtape.com/en/?utm_source=fb&utm_medium=post&utm_campaign=daily&ref=1',
                'facebook_cta': (
                    'Live numbers 👉 https://thecrowdtape.com/en/?utm_source=fb&utm_medium=post&utm_campaign=daily\n'
                    '☕ Support the site 👉 https://thecrowdtape.com/en/?utm_source=fb&utm_medium=post&utm_campaign=daily#donate\n'
                    '📬 Get the free newsletter 👉 https://thecrowdtape.com/en/?utm_source=fb&utm_medium=post&utm_campaign=newsletter'
                ),
                'instagram': 'link in bio (thecrowdtape.com)',
                'reddit': {'body': 'plain https://thecrowdtape.com/en/ stays bare'},
            }
        },
        'slots': {
            '1230': {
                'posts': {
                    'zh': {
                        'threads': '最新數字 👉 https://thecrowdtape.com/zh/?utm_source=threads&utm_medium=post&utm_campaign=carousel',
                        'x': '最新數字 👉 https://thecrowdtape.com/zh/?utm_source=x&utm_medium=post&utm_campaign=carousel',
                        'facebook_cta': (
                            '最新數字 👉 https://thecrowdtape.com/zh/?utm_source=fb&utm_medium=post&utm_campaign=carousel\n'
                            '📬 訂閱免費電子報 👉 https://thecrowdtape.com/zh/?utm_source=fb&utm_medium=post&utm_campaign=newsletter'
                        ),
                    }
                },
                'images': {'zh': ['https://thecrowdtape.com/og/c/x.jpg']},
            }
        },
        'x_trilingual': {
            'premarket': {
                'text': 'https://thecrowdtape.com/en/?utm_source=x&utm_medium=post&utm_campaign=daily',
                'image': 'https://thecrowdtape.com/og/x-premarket.png?v=1',
            },
            'afterclose': {
                'text': 'https://thecrowdtape.com/ko/?a=1&utm_campaign=afterclose&utm_source=x&utm_medium=post#z',
            },
        },
        'top5': {
            'posts': {
                'en': {
                    'x': 'https://thecrowdtape.com/en/',
                    'instagram': 'https://thecrowdtape.com/en/stock/NVDA/',
                }
            }
        },
        'weekly_thread': {
            'posts': {
                'en': {'x': 'https://thecrowdtape.com/en/?utm_source=ig&utm_medium=post&utm_campaign=nope'}
            }
        },
        'images': {'en': 'https://thecrowdtape.com/og/social-en.png?v=1'},
        'intraday': {
            'date': '2026-10-23',
            'slots': {
                'intraday_open': {
                    'x': {
                        'en': {
                            'text': 'See https://thecrowdtape.com/en/?utm_source=x&utm_medium=post&utm_campaign=old',
                            'url': 'https://thecrowdtape.com/en/',
                        }
                    },
                    'threads': {
                        'zh': {
                            'text': '見 https://thecrowdtape.com/zh/?utm_source=threads&utm_medium=post&utm_campaign=old',
                            'url': 'https://thecrowdtape.com/zh/',
                        },
                        'en': {'text': 'No link here', 'url': None},
                        'ko': {
                            'text': '보기 https://thecrowdtape.com/ko/?utm_source=threads&utm_medium=post&utm_campaign=old',
                            'url': 'https://thecrowdtape.com/ko/',
                        },
                    },
                }
            },
        },
    }


def test_normalize_obj_scheme():
    data = _fixture()
    normalize_obj(data)
    seen = check_posts(data, iter_social, 'fixture')
    assert 'daily' in seen and 'carousel-1230' in seen, seen
    assert 'premarket' in seen and 'afterclose' in seen, seen
    assert 'newsletter' in seen and 'top5' in seen and 'weekly_thread' in seen, seen
    assert 'intraday_open' in seen, seen
    check_assets_untagged(data, 'fixture')
    fb = data['posts']['en']['facebook']
    assert 'ref=1&utm_source=facebook&utm_medium=social&utm_campaign=daily' in fb, fb
    cta = data['posts']['en']['facebook_cta']
    assert 'utm_campaign=daily' in cta and 'utm_campaign=newsletter' in cta, cta
    assert 'utm_source=facebook' in cta and 'utm_source=fb&' not in cta
    assert data['posts']['en']['reddit']['body'] == 'plain https://thecrowdtape.com/en/ stays bare'
    assert data['slots']['1230']['images']['zh'] == ['https://thecrowdtape.com/og/c/x.jpg']
    assert data['x_trilingual']['premarket']['image'].endswith('x-premarket.png?v=1')
    after = data['x_trilingual']['afterclose']['text']
    assert after == 'https://thecrowdtape.com/ko/?a=1&utm_source=x&utm_medium=social&utm_campaign=afterclose#z', after
    ig = data['top5']['posts']['en']['instagram']
    assert 'https://' not in ig and 'thecrowdtape.com' not in ig.lower()
    assert share.IG_BIO['en'] in ig
    assert share.IG_BIO['en'] in data['posts']['en']['instagram']
    weekly = data['weekly_thread']['posts']['en']['x']
    assert 'utm_source=x&utm_medium=social&utm_campaign=weekly_thread' in weekly, weekly
    intra_x = data['intraday']['slots']['intraday_open']['x']['en']
    assert 'utm_source=x&utm_medium=social&utm_campaign=intraday_open' in intra_x['text']
    assert intra_x['url'] == 'https://thecrowdtape.com/en/?utm_source=x&utm_medium=social&utm_campaign=intraday_open'
    intra_zh = data['intraday']['slots']['intraday_open']['threads']['zh']
    assert 'utm_source=threads&utm_medium=social&utm_campaign=intraday_open' in intra_zh['text']
    assert 'utm_source=ig' not in weekly
    assert len(data['posts']['en']['threads']) <= 500
    assert 'utm_source=threads&utm_medium=social&utm_campaign=daily' in data['posts']['en']['threads']
    again = json.loads(json.dumps(data))
    normalize_obj(again)
    assert again == data


def test_normalize_file_tutorial_campaign():
    tut = {
        'posts': {
            'en': {
                'facebook': 'https://thecrowdtape.com/en/?utm_source=fb&utm_medium=post&utm_campaign=daily',
                'x': 'Try https://thecrowdtape.com/en/?utm_source=x&utm_medium=post&utm_campaign=tutorial',
                'threads': 'Try https://thecrowdtape.com/en/?utm_source=threads&utm_medium=post&utm_campaign=tutorial',
            },
            'zh': {'x': '試 https://thecrowdtape.com/zh/'},
            'ko': {'x': '보기 https://thecrowdtape.com/ko/'},
        },
        'images': {'en': 'https://thecrowdtape.com/og/tutorial-en.png?v=1'},
    }
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, 'tutorial-posts.json')
        json.dump(tut, open(path, 'w', encoding='utf-8'))
        normalize_file(path)
        got = json.load(open(path, encoding='utf-8'))
    seen = check_posts(got, iter_tutorial, 'tutorial-fixture')
    assert seen == {'tutorial'}, seen
    assert 'utm_source=facebook&utm_medium=social&utm_campaign=tutorial' in got['posts']['en']['facebook']
    assert got['images']['en'] == 'https://thecrowdtape.com/og/tutorial-en.png?v=1'
    assert share.xlen(got['posts']['zh']['x']) <= 280


def test_new_slot_shapes():
    """weekly langs lists, hot_stock, discussion, weekend and atomic_posts all get tagged.

    langs.<lang> is a list of X posts (campaign weekly_thread). first_comment uses the
    parent platform. atomic text/first_comment use source threads and campaign atomic.
    /og/*.mp4 stays untagged.
    """
    data = {
        'weekly_thread': {
            'date': '2026-10-23',
            'langs': {
                'zh': ['本週 https://thecrowdtape.com/zh/?utm_source=ig&utm_medium=post&utm_campaign=nope'],
                'en': ['Week https://thecrowdtape.com/en/'],
                'ko': ['주간 https://thecrowdtape.com/ko/'],
            },
        },
        'hot_stock': {
            'posts': {
                'zh': {
                    'threads': '專家觀點 冇連結',
                    'facebook': '專家觀點 冇連結',
                    'first_comment': {
                        'threads': '最新數字 👉 https://thecrowdtape.com/zh/stock/AAA/',
                        'facebook': '最新數字 👉 https://thecrowdtape.com/zh/stock/AAA/',
                    },
                }
            }
        },
        'discussion': {
            'posts': {
                'en': {
                    'threads': 'What do you think of $AAA?',
                    'facebook': 'What do you think of $AAA?',
                    'first_comment': {
                        'threads': 'Live numbers 👉 https://thecrowdtape.com/en/stock/AAA/',
                    },
                }
            }
        },
        'weekend': {
            'posts': [
                {
                    'langs': {
                        'ko': {
                            'threads': '이번 주',
                            'facebook': '이번 주',
                            'first_comment': {
                                'facebook': '최신 수치 👉 https://thecrowdtape.com/ko/',
                            },
                        }
                    }
                }
            ]
        },
        'atomic_posts': [
            {
                'lang': 'zh',
                'text': '今日帖文數 88',
                'hook': '88',
                'hashtags': '#美股',
                'first_comment': '最新數字 👉 https://thecrowdtape.com/zh/',
            }
        ],
        'top5': {
            'video': {'zh': 'https://thecrowdtape.com/og/top5-zh.mp4?v=2026-10-23'},
        },
    }
    normalize_obj(data)
    seen = check_posts(data, iter_social, 'new-shapes')
    assert {'weekly_thread', 'hot_stock', 'discussion', 'weekend', 'atomic'} <= seen, seen
    zh = data['weekly_thread']['langs']['zh'][0]
    assert 'utm_source=x&utm_medium=social&utm_campaign=weekly_thread' in zh, zh
    assert 'utm_source=ig' not in zh
    en = data['weekly_thread']['langs']['en'][0]
    assert en.endswith('/en/?utm_source=x&utm_medium=social&utm_campaign=weekly_thread'), en
    hot_fc = data['hot_stock']['posts']['zh']['first_comment']
    assert 'utm_source=threads&utm_medium=social&utm_campaign=hot_stock' in hot_fc['threads'], hot_fc
    assert 'utm_source=facebook&utm_medium=social&utm_campaign=hot_stock' in hot_fc['facebook'], hot_fc
    talk = data['discussion']['posts']['en']['first_comment']['threads']
    assert 'utm_source=threads&utm_medium=social&utm_campaign=discussion' in talk, talk
    week_fc = data['weekend']['posts'][0]['langs']['ko']['first_comment']['facebook']
    assert 'utm_source=facebook&utm_medium=social&utm_campaign=weekend' in week_fc, week_fc
    atom = data['atomic_posts'][0]['first_comment']
    assert 'utm_source=threads&utm_medium=social&utm_campaign=atomic' in atom, atom
    assert 'utm_' not in data['top5']['video']['zh']
    check_assets_untagged(data, 'new-shapes')
    again = json.loads(json.dumps(data))
    normalize_obj(again)
    assert again == data


def main():
    test_tag_url_normalises()
    test_normalize_obj_scheme()
    test_normalize_file_tutorial_campaign()
    test_new_slot_shapes()
    test_real_files()
    test_real_files_idempotent()
    print('test_utm_scheme: tag_url, normalize, social-posts.json, tutorial-posts.json ok')


if __name__ == '__main__':
    main()
