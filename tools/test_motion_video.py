"""Motion videos (tools/MOTION_VIDEO.md): which slots and languages get one, the voiceover lines,
dropping videos that were not made, and the /social/ page. Offline, no browser, no network.
Run from the repo root: python3 tools/test_motion_video.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['WORK_DIR'] = tempfile.mkdtemp(prefix='motion-test-')
os.environ.pop('VIDEO_SLOTS', None)
os.environ.pop('VIDEO_LANGS', None)

import carousel  # noqa: E402
import carousel_vo  # noqa: E402
from carousel_video_post import prune  # noqa: E402

URL = 'https://thecrowdtape.com/og/c/2026-10-23-1230-{}.mp4'


def job(lang='zh'):
    return {'slot': '1230', 'lang': lang, 'slides': [
        {'kind': 'cover', 'big': 'SPY', 'sub': '15 個帳號', 'pills': [{'c': 'g', 'x': '3 個睇好'}, {'c': 'r', 'x': '6 個睇淡'}]},
        {'kind': 'cards', 'secs': [{'h': '🔥 最多人討論 Top 4', 'cards': [{'t': t} for t in ('SPY', 'SPCX', 'AMZN', 'META', 'QQQ')]}]},
        {'kind': 'cards', 'secs': [{'h': '🟢 共同看多', 'cards': [{'t': 'META'}]}, {'h': '🔴 共同看空', 'cards': [{'t': 'QQQ'}]}]},
        {'kind': 'cards', 'secs': [{'h': '⚖️ 好淡分歧', 'cards': [{'t': 'GLD'}]}]}]}


def test_defaults():
    assert carousel.VIDEO_SLOTS == ('1230',), carousel.VIDEO_SLOTS
    assert carousel.VIDEO_LANGS == ('zh', 'en'), carousel.VIDEO_LANGS  # Tim: no Korean video


def test_vo_lines():
    ls = carousel_vo.lines(job())
    assert len(ls) == 8, ls
    text = ''.join(ls)
    assert 'S P Y' in ls[1] and '15' in ls[1], ls[1]
    assert '空方' in ls[2], ls[2]
    assert ls[4].count('、') == 3 and 'Q Q Q' not in ls[4], ls[4]  # top 4 only
    assert 'M E T A' in ls[5] and 'Q Q Q' in ls[5], ls[5]
    assert 'G L D' in ls[6], ls[6]
    for bad in ('買', '賣', '目標價', '會升', '會跌', '必升'):
        assert bad not in text, bad
    assert carousel_vo.lines(job('en')) is None  # only Mandarin for now


def test_vo_missing_sections():
    j = job()
    j['slides'][2]['secs'] = [{'h': '🟢 共同看多', 'cards': [{'t': 'META'}]}]
    j['slides'][3]['secs'] = []
    ls = carousel_vo.lines(j)
    assert '看空' not in ls[5] and 'M E T A' in ls[5], ls[5]
    assert ls[6] == '你站哪邊？', ls[6]


def test_prune():
    sp = {'slots': {'1230': {'video': {'zh': URL.format('zh'), 'en': URL.format('en')}}, '1630': {'images': {}}}}
    have = {'og/c/2026-10-23-1230-zh.mp4'}
    assert prune(sp, exists=lambda p: p in have)
    assert sp['slots']['1230']['video'] == {'zh': URL.format('zh')}
    assert not prune(sp, exists=lambda p: p in have)  # nothing more to drop
    assert prune(sp, exists=lambda p: False)
    assert 'video' not in sp['slots']['1230']


def test_social_page():
    posts = {k: 'text' for k in ('x', 'threads', 'instagram', 'facebook')}
    sl = {'day': '2026-10-23', 'made_hkt': '2026-10-23 07:20', 'images': {l: [] for l in ('zh', 'en', 'ko')},
          'posts': {l: dict(posts) for l in ('zh', 'en', 'ko')}, 'video': {'zh': URL.format('zh')}}
    page = carousel.slot_page({'slots': {'1230': sl}})
    assert page.count('<video') == 1 and URL.format('zh') in page
    sl.pop('video')
    assert '<video' not in carousel.slot_page({'slots': {'1230': sl}})


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print('ok', name)
