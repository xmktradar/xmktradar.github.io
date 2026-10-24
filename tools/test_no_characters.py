"""Social posts no longer use the Nova / Ember / Iris characters.

From 2026-10-23 16:30 the carousel dropped character names, dialogue and
stickers. This test scans today's social-posts.json, generator output from
offline fixtures, and the tools tree so those names cannot come back.

Run from the repo root: python3 tools/test_no_characters.py
"""
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['WORK_DIR'] = tempfile.mkdtemp(prefix='nochar-test-')
os.environ['SOCIAL_HISTORY'] = os.path.join(os.environ['WORK_DIR'], 'social-history.json')

import carousel  # noqa: E402
import share  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOCIAL = os.path.join(ROOT, 'data', 'social-posts.json')
TOOLS = os.path.join(ROOT, 'tools')
WORKFLOWS = os.path.join(ROOT, '.github', 'workflows')
CHAR_DIR = os.path.join(ROOT, 'assets', 'characters')
STICKERS_PY = os.path.join(TOOLS, 'stickers.py')
THIS = os.path.basename(__file__)

ZH_KO_NAMES = ('諾娃', '安柏', '艾莉絲', '노바', '엠버', '아이리스')
EN_RE = re.compile(r'\b(?:Nova|Ember|Iris)\b')
BANNED_PATHS = ('assets/characters', 'tools/stickers.py')
GONE_FUNCS = ('Cast', 'CAST_FILE', 'STORY_CAST', 'dialogue', 'add_dialogue',
              'poses', 'situation', 'story')
DAY = '2026-10-23'
WIN = '10/23 00:00 – 10/23 04:58 HKT'


def _walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(key, str):
                yield key
            yield from _walk_strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk_strings(value)


def _assert_clean(text, where):
    assert isinstance(text, str), where
    for name in ZH_KO_NAMES:
        assert name not in text, (where, name, text[:240])
    found = EN_RE.search(text)
    assert found is None, (where, found.group(0), text[:240])


def _assert_obj_clean(obj, where):
    for i, text in enumerate(_walk_strings(obj)):
        _assert_clean(text, f'{where}[{i}]')


def _row(t, nb=None, nr=None, n_posts=1, why='觀點沒有數字', acc='someone'):
    row = {'t': t, 'n_posts': n_posts, 'rows': [{'acc': acc, 'why': why, 'url': f'https://x.com/{acc}/status/1'}]}
    if nb is not None:
        row['nb'] = nb
    if nr is not None:
        row['nr'] = nr
    return row


class _Site:
    def __init__(self):
        self.d = {'posts': [], 'accounts': {}, 'prices': {}, 'avmini': {}}
        self.by_url = {
            'u-bull': {'handle': 'leadbull', 'zh_summary': '睇好這隻',
                       'en_summary': 'bullish on this name', 'ko_summary': '이 종목 강세',
                       'text': 'bullish on this name'},
            'u-bear': {'handle': 'leadbear', 'zh_summary': '睇淡這隻',
                       'en_summary': 'bearish on this name', 'ko_summary': '이 종목 약세',
                       'text': 'bearish on this name'},
        }

    def av(self, h):
        return ''

    def name(self, h):
        return h

    def text(self, p, lang, n):
        t = {'zh': p.get('zh_summary'), 'ko': p.get('ko_summary'),
             'en': p.get('en_summary') or p.get('text')}[lang]
        return (t or '')[:n]

    def px(self, t):
        return [], None


def test_social_posts_json_has_no_character_names():
    data = json.load(open(SOCIAL, encoding='utf-8'))
    _assert_obj_clean(data, 'social-posts.json')
    assert 'pose_log' not in data
    for key, slot in (data.get('slots') or {}).items():
        assert 'poses' not in slot, key


def test_pipeline_files_are_gone():
    assert not os.path.exists(CHAR_DIR), CHAR_DIR
    assert not os.path.isdir(CHAR_DIR)
    assert not os.path.exists(STICKERS_PY), STICKERS_PY
    assert not os.path.exists(os.path.join(WORKFLOWS, 'draw-stickers.yml'))


def test_tools_do_not_reference_pipeline():
    hits = []
    for folder in (TOOLS, WORKFLOWS):
        for dirpath, _dirs, files in os.walk(folder):
            for name in files:
                if name == THIS:
                    continue
                path = os.path.join(dirpath, name)
                try:
                    text = open(path, encoding='utf-8').read()
                except (UnicodeDecodeError, OSError):
                    continue
                for needle in BANNED_PATHS:
                    if needle in text:
                        hits.append((os.path.relpath(path, ROOT), needle))
    assert hits == [], hits
    for name in GONE_FUNCS:
        assert not hasattr(carousel, name), name


def test_generator_outputs_from_fixtures():
    s = {'bull': [{'t': 'WMT'}], 'bear': [{'t': 'QQQ', 'nr': 2}], 'split': [],
         'accounts': 4, 'tickers': 2}
    items = [{'t': 'WMT', 'n': 2, 'bull': 2, 'bear': 0, 'streak': 1}]
    quote = {'acc': 'Mr_Derivatives', 'text': '@Mr_Derivatives：$WMT再度展現防守特性'}
    site = _Site()
    outputs = []
    for lang in share.LANGS:
        cap = share.caption(lang, DAY, s, items, WIN, quote)
        outputs.append(cap)
        posts = dict(cap)
        posts.pop('reddit', None)
        for field, see in (('instagram', carousel.END[lang][0]), ('facebook', carousel.FB_TAP[lang])):
            posts[field] = posts[field].replace('\n\n', f'\n\n{see}\n\n', 1)
        if isinstance(posts.get('instagram'), str):
            posts['instagram'] = share.sanitize_instagram(posts['instagram'], lang)
        posts['facebook_cta'] = share.facebook_cta(posts['facebook'], lang)
        outputs.append(posts)
        outputs.append(carousel.versions(lang, 'head $WMT', ['body line'], ['WMT']))
        pick = ('SPY', 2, 1, [
            {'acc': 'leadbull', 's': 'bull', 'url': 'u-bull'},
            {'acc': 'leadbear', 's': 'bear', 'url': 'u-bear'},
        ])
        outputs.append(carousel.cap_duel(site, s, lang, DAY, pick))
        hot = [{'t': 'NVDA', 'now': 5, 'was': 2}]
        pts = [{'t': 'NVDA', 'pt': '200', 'acc': 'leadbull', 'day': '2026-10-22', 'url': 'u-bull'}]
        outputs.append(carousel.cap_focus(site, s, lang, DAY, (hot, pts, None)))
        empty = {'top': [], 'bull': [], 'bear': [], 'split': [], 'accounts': 0, 'tickers': 0}
        slides = carousel.label_talk(carousel.snap(site, empty, lang, DAY, WIN), lang)
        for slide in slides:
            assert 'char' not in slide, slide
        outputs.append(slides)

    daily = {
        'from': '2026-10-23T00:00',
        'to': '2026-10-23T23:59',
        'posts': 88,
        'accounts': 34,
        'bull': [_row('RSP', nb=2, n_posts=7, acc='leadbull')],
        'bear': [_row('QQQ', nr=4, n_posts=6, acc='leadbear')],
        'split': [
            _row('SPCX', nb=4, nr=3, n_posts=10, why='ZQXQZX 原文開始', acc='chamath'),
            _row('SPY', nb=2, nr=1, n_posts=9, why='另一段原文', acc='other'),
        ],
    }
    outputs.append(share.build_top5(daily, DAY, '2026-10-23 07:18'))
    hot_row, talk_row = share.select_slot_rows(daily, {'RSP', 'QQQ'})
    outputs.append(share.build_hot_stock(hot_row, DAY))
    outputs.append(share.build_discussion(talk_row, DAY))
    weekly = {
        'from': '2026-10-17', 'to': '2026-10-23',
        'bull': [{'t': 'AAPL', 'nb': 3}], 'bear': [{'t': 'QQQ', 'nr': 2}],
        'bull_total': 3, 'bear_total': 2, 'split': [],
    }
    outputs.append(share.build_weekly_thread(weekly, {}, DAY))
    outputs.append(share.build_weekend(weekly, '2026-10-24'))

    for i, obj in enumerate(outputs):
        assert obj is not None, i
        _assert_obj_clean(obj, f'fixture[{i}]')


def main():
    test_social_posts_json_has_no_character_names()
    test_pipeline_files_are_gone()
    test_tools_do_not_reference_pipeline()
    test_generator_outputs_from_fixtures()
    print('test_no_characters: names gone from posts and generators, sticker pipeline deleted')


if __name__ == '__main__':
    main()
