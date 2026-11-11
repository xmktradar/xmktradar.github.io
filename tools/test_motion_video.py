"""Motion videos (tools/MOTION_VIDEO.md): which slots and languages get one, the voiceover lines,
dropping videos that were not made, and the /social/ page. Offline, no browser, no network.
The 40s guard is exercised on the VO_FAKE=1 path (durations are supplied; no edge-tts).
Tim 2026-10-26: no silent/music-only mp4; a language without VO is skipped.
Run from the repo root: python3 tools/test_motion_video.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['WORK_DIR'] = tempfile.mkdtemp(prefix='motion-test-')
os.environ.pop('VIDEO_SLOTS', None)
os.environ.pop('VIDEO_LANGS', None)
os.environ.pop('VO_LANGS', None)
os.environ.pop('VO_FAKE', None)
os.environ.pop('VO_VOICE_en', None)
os.environ.pop('VO_VOICE_zh', None)

import carousel  # noqa: E402
import carousel_vo  # noqa: E402
from carousel_video_post import prune  # noqa: E402

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)

URL = 'https://thecrowdtape.com/og/c/2026-10-23-1230-{}.mp4'
# Snapshot of lines(job('zh')) before the English voiceover change. Do not edit to match a new zh script.
ZH_LINES = [
    'S P Y，15 個帳號在聊',
    '3 看好，6 看空，空方領先。',
    '熱度前四：S P Y、S P C X、A M Z N、M E T A',
    '看好 M E T A，看空 Q Q Q',
    '詳情看 thecrowdtape.com',
]
EN_LINES = [
    'The fight today is S P Y.',
    'S P Y is the most talked-about name today — 15 tracked accounts are on it.',
    'Tracked accounts are split: 3 bulls versus 6 bears.',
    'Bull or bear on S P Y?',
]
EN_SHORT = [
    'The fight today is S P Y.',
    'S P Y — 15 tracked accounts.',
    'Split: 3 bulls versus 6 bears.',
    'Bull or bear on S P Y?',
]
BAD_EN = re.compile(r'\b(buy|sell|buys|sells|buying|selling|target|targets|prediction|predictions|forecast|forecasts)\b', re.I)


@contextmanager
def no_hero_quote():
    """Snapshot EN_LINES assumes no writeup hit for SPY fixture; isolate from live data."""
    old = carousel_vo.load_hero_quote
    carousel_vo.load_hero_quote = lambda big='': None
    try:
        yield
    finally:
        carousel_vo.load_hero_quote = old


def job(lang='zh'):
    return {'slot': '1230', 'lang': lang, 'slides': [
        {'kind': 'cover', 'big': 'SPY', 'sub': '15 個帳號', 'pills': [{'c': 'g', 'x': '3 個睇好'}, {'c': 'r', 'x': '6 個睇淡'}]},
        {'kind': 'cards', 'secs': [{'h': '🔥 最多人討論 Top 4', 'cards': [{'t': t} for t in ('SPY', 'SPCX', 'AMZN', 'META', 'QQQ')]}]},
        {'kind': 'cards', 'secs': [{'h': '🟢 共同看多', 'cards': [{'t': 'META'}]}, {'h': '🔴 共同看空', 'cards': [{'t': 'QQQ'}]}]},
        {'kind': 'cards', 'secs': [{'h': '⚖️ 好淡分歧', 'cards': [{'t': 'GLD'}]}]}]}


def test_defaults():
    assert carousel.VIDEO_SLOTS == ('1230', '1630'), carousel.VIDEO_SLOTS
    assert carousel.VIDEO_LANGS == ('en',), carousel.VIDEO_LANGS  # Tim 2026-11-04: daily Shorts en-only


def _assert_no_advice(lines):
    text = '\n'.join(lines)
    assert BAD_EN.search(text) is None, text
    for bad in ('買', '賣', '目標價', '會升', '會跌', '必升', 'buy', 'sell', 'target', 'prediction'):
        assert bad not in text.lower(), bad


def test_vo_lines():
    ls = carousel_vo.lines(job())
    assert ls == ZH_LINES, ls
    assert len(ls) == 5, ls
    text = ''.join(ls)
    assert 'S P Y' in ls[0] and '15' in ls[0], ls[0]
    assert '空方' in ls[1], ls[1]
    assert '前四' in ls[2] and 'S P Y' in ls[2], ls[2]
    assert 'M E T A' in ls[3] and 'Q Q Q' in ls[3], ls[3]
    assert ls[4] == '詳情看 thecrowdtape.com', ls[4]
    for bad in ('買', '賣', '目標價', '會升', '會跌', '必升'):
        assert bad not in text, bad
    assert carousel_vo.VOICES['zh'] == 'zh-CN-XiaoxiaoNeural'
    assert carousel_vo.RATE == '+10%'
    assert carousel_vo.fake_seconds(ls[0]) == max(1.0, len(ls[0]) / 6.5)  # zh fake length is unchanged at +10%



def test_en_lines():
    with no_hero_quote():
        assert carousel_vo.VOICES['en'] == 'en-US-AndrewNeural'
        assert os.environ.get('VO_VOICE_en', carousel_vo.VOICES['en']) == 'en-US-AndrewNeural'
        ls = carousel_vo.lines(job('en'))
        assert ls == EN_LINES, ls
        assert len(ls) == 4, ls
        _assert_no_advice(ls)
        assert ls[0] == 'The fight today is S P Y.', ls[0]
        assert 'tracked accounts' in ls[1] and '15' in ls[1], ls[1]
        assert 'split' in ls[2] and '3 bulls' in ls[2] and '6 bears' in ls[2], ls[2]
        assert ls[3] == 'Bull or bear on S P Y?', ls[3]
        assert 'thecrowdtape' not in '\n'.join(ls).lower()
        assert "everyone's screaming" not in '\n'.join(ls).lower()
        assert carousel_vo.vo_langs() == ['en']
        short = carousel_vo.en_lines(job('en'), short=True)
        assert short == EN_SHORT, short
        _assert_no_advice(short)
        assert 'thecrowdtape' not in '\n'.join(short).lower()
        assert short != ls
        one = job('en')
        one['slides'][0]['sub'] = '1 account'
        one['slides'][0]['pills'] = [{'c': 'g', 'x': '1 bullish'}]
        lone = '\n'.join(carousel_vo.lines(one))
        assert 'most discussed name' in lone and 'fight' not in lone.lower(), lone
        assert 'lean bullish' in lone and 'almost no bear case' in lone and '1 bull versus 0 bears' in lone
        assert 'split' not in lone.lower()
        tie = job('en')
        tie['slides'][0]['pills'] = [{'c': 'g', 'x': '4 bullish'}, {'c': 'r', 'x': '4 bearish'}]
        tied = '\n'.join(carousel_vo.lines(tie))
        assert 'split' in tied.lower() and "it's a tie" not in tied.lower(), tied
        bulls = job('en')
        bulls['slides'][0]['pills'] = [{'c': 'g', 'x': '8 bullish'}, {'c': 'r', 'x': '2 bearish'}]
        leaned = '\n'.join(carousel_vo.lines(bulls))
        assert '8 bulls versus 2 bears' in leaned and 'lean bullish' in leaned, leaned
        assert 'split' not in leaned.lower() and 'fight' not in leaned.lower() and 'almost no' not in leaned.lower()
        missing = job('en')
        missing['slides'][1]['secs'] = []
        missing['slides'][2]['secs'] = []
        missing['slides'][3]['secs'] = []
        assert carousel_vo.lines(missing) == EN_LINES



def test_en_quote_from_highlights():
    """EN VO does not invent an expert from writeups. Counts stay on the cover."""
    j = job('en')
    j['slides'][0]['big'] = 'TSLA'
    j['slides'][0]['sub'] = '6 accounts'
    j['slides'][0]['pills'] = [{'c': 'g', 'x': '6 bullish'}, {'c': 'r', 'x': '0 bearish'}]
    ls = carousel_vo.lines(j)
    text = '\n'.join(ls)
    assert "everyone's screaming" not in text.lower()
    assert 'thecrowdtape' not in text.lower()
    assert ls[0] == 'T S L A is the most discussed name on the tape today.', ls[0]
    assert 'lean bullish' in ls[2] and 'split' not in ls[2].lower() and 'fight' not in ls[0].lower()
    hero = carousel_vo.load_hero_quote('TSLA')
    if hero and hero.get('handle'):
        assert hero['handle'] not in text
    _assert_no_advice(ls)




def _run_vo(jobs, dur, langs):
    """Run carousel_vo.main on the VO_FAKE=1 path. dur(rate, text) supplies each clip length."""
    calls = []
    old_fake, old_duration = carousel_vo.fake, carousel_vo.duration
    old_fake_env, old_langs = os.environ.get('VO_FAKE'), os.environ.get('VO_LANGS')
    os.environ['VO_FAKE'] = '1'
    os.environ['VO_LANGS'] = langs

    def fake(text, path, rate=carousel_vo.RATE):
        assert os.environ.get('VO_FAKE') == '1'
        calls.append((rate, text))
        return True

    def duration(path):
        rate, text = calls[-1]
        return dur(rate, text)

    carousel_vo.fake = fake
    carousel_vo.duration = duration
    try:
        d = tempfile.mkdtemp()
        path = os.path.join(d, 'carousel.json')
        json.dump({'jobs': jobs}, open(path, 'w', encoding='utf-8'))
        out = os.path.join(d, 'vo')
        carousel_vo.main(path, out)
        vo = json.load(open(os.path.join(out, 'vo.json'), encoding='utf-8'))
        return vo, calls
    finally:
        carousel_vo.fake, carousel_vo.duration = old_fake, old_duration
        if old_fake_env is None:
            os.environ.pop('VO_FAKE', None)
        else:
            os.environ['VO_FAKE'] = old_fake_env
        if old_langs is None:
            os.environ.pop('VO_LANGS', None)
        else:
            os.environ['VO_LANGS'] = old_langs


def test_duration_guard():
    """English over 40s retries faster rates, then shorter lines, then drops the voice. zh does not."""
    assert carousel_vo.fits(40.0) and not carousel_vo.fits(40.03)
    assert carousel_vo.fits(carousel_vo.video_total(None))
    assert carousel_vo.COVER_FRAMES == 0 and carousel_vo.COVER_S == 0
    assert abs(carousel_vo.video_total(None) - (sum(carousel_vo.BASE_BEATS) * carousel_vo.BEAT)) < 1e-9
    long = [9.0] * 5
    assert carousel_vo.video_total(long) > 40.0
    assert carousel_vo.video_total([1.2] * 5) <= 40.0
    assert [r for _, r in carousel_vo.EN_TRIES] == ['+10%', '+20%', '+30%', '+10%', '+20%', '+30%']

    with no_hero_quote():
        vo, calls = _run_vo([job('en')], lambda rate, text: 1.2, langs='en')
        assert len(calls) == 4 and {r for r, _ in calls} == {'+10%'}
        assert [x['text'] for x in vo['1230-en']] == EN_LINES
        assert carousel_vo.video_total([x['dur'] for x in vo['1230-en']]) <= 40.0

        vo, calls = _run_vo([job('en')], lambda rate, text: 1.2 if rate == '+30%' else 12.0, langs='en')
        assert [x['text'] for x in vo['1230-en']] == EN_LINES  # fitted on the normal script, not the short one
        assert calls[0][0] == '+10%' and calls[-1][0] == '+30%'
        assert all(t != 'Hottest stock?' for _, t in calls)
        assert carousel_vo.video_total([x['dur'] for x in vo['1230-en']]) <= 40.0

        vo, calls = _run_vo([job('en')], lambda rate, text: 12.0, langs='en')
        assert '1230-en' not in vo  # still over 40s after every try: no voice, rather than a long video
        assert any('tracked accounts' in t or 'Bull or bear' in t for _, t in calls)
        assert calls[-1] == ('+30%', 'Bull or bear on S P Y?')

    # A zh read that would be over 40s is still emitted once, at +10%, with the snapshot lines.
    vo, calls = _run_vo([job('zh')], lambda rate, text: 9.0, langs='zh')
    assert [x['text'] for x in vo['1230-zh']] == ZH_LINES
    assert len(calls) == 5 and {r for r, _ in calls} == {'+10%'}
    assert carousel_vo.video_total([x['dur'] for x in vo['1230-zh']]) > 40.0

    j = job('en')
    j['slides'][0]['big'] = 'GOOGL'
    vo, calls = _run_vo([j], lambda rate, text: carousel_vo.fake_seconds(text, rate), langs='en')
    if '1230-en' in vo:
        assert carousel_vo.video_total([x['dur'] for x in vo['1230-en']]) <= 40.0
        assert any('G O O G L' in x['text'] for x in vo['1230-en'])
    else:
        assert calls and calls[-1][0] == '+30%'



def test_video_total_matches_js():
    import random
    rng = random.Random(1230)
    n = len(carousel_vo.BASE_BEATS)
    cases = [[round(rng.uniform(0.8, 6.5), 3) for _ in range(n)] for _ in range(80)]
    cases.append([round(7 * 60 / 124 - 0.4, 3)] * n)  # ceil boundary
    script = r'''
const fs = require("fs");
const { voicedTotal } = require("./tools/carousel_video.js");
const cases = JSON.parse(fs.readFileSync(0, "utf8"));
for (const durs of cases) {
  console.log(voicedTotal(durs.map(dur => ({ dur, file: "x" }))));
}
'''
    env = os.environ.copy()
    env.pop('FORCE_COLOR', None)
    env['NO_COLOR'] = '1'
    proc = subprocess.run(['node', '-e', script], input=json.dumps(cases), text=True, capture_output=True, check=True, env=env, cwd=ROOT)
    nums = re.findall(r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?', proc.stdout)
    got = [float(x) for x in nums]
    assert len(got) == len(cases)
    for durs, js in zip(cases, got):
        assert abs(carousel_vo.video_total(durs) - js) < 1e-6, (durs, carousel_vo.video_total(durs), js)



def test_vo_missing_sections():
    j = job()
    j['slides'][2]['secs'] = [{'h': '🟢 共同看多', 'cards': [{'t': 'META'}]}]
    j['slides'][3]['secs'] = []
    ls = carousel_vo.lines(j)
    assert '看空' not in ls[3] and 'M E T A' in ls[3], ls[3]



COVER_URL = 'https://thecrowdtape.com/og/c/2026-10-23-1230-{}-cover.jpg'
HAN = __import__('re').compile(r'[\u3400-\u9fff]')
MARK_ZH = {'voice': 'zh-CN-XiaoxiaoNeural', 'duration': 27.0, 'vo': True}
MARK_EN = {'voice': 'en-US-AndrewNeural', 'duration': 26.5, 'vo': True}


@contextmanager
def _ogc(files):
    """Write og/c files in a temp dir and chdir there so prune sees relative paths."""
    d = tempfile.mkdtemp(prefix='ogc-')
    cwd = os.getcwd()
    try:
        os.chdir(d)
        os.makedirs('og/c', exist_ok=True)
        for name, body in files.items():
            path = os.path.join('og/c', name)
            if isinstance(body, dict):
                json.dump(body, open(path, 'w', encoding='utf-8'))
            else:
                open(path, 'wb').write(b'x' if body is True else body)
        yield d
    finally:
        os.chdir(cwd)


def _slot(langs=('zh', 'en'), cover=False):
    sl = {'video': {l: URL.format(l) for l in langs}}
    if cover:
        sl['video_cover'] = {l: COVER_URL.format(l) for l in langs}
    return {'slots': {'1230': sl, '1630': {'images': {}}}}


def _node(script, args=None):
    env = os.environ.copy()
    env.pop('FORCE_COLOR', None)
    env['NO_COLOR'] = '1'
    proc = subprocess.run(['node', '-e', script, '--', *(args or [])], text=True, capture_output=True, cwd=ROOT, env=env)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return proc.stdout


def test_no_vo_no_mp4():
    """No VO entry (zh or en): skip the language, delete .part.mp4, write neither mp4 nor marker."""
    d = tempfile.mkdtemp()
    out = os.path.join(d, '2026-10-23-1230-zh.mp4')
    open(out + '.part.mp4', 'w').write('part')
    script = r'''
const { voiceoverSkip, refuseVideo } = require('./tools/carousel_video.js');
const fs = require('fs');
const out = process.argv[1];
const why = voiceoverSkip(null);
if (!why) process.exit(2);
refuseVideo({slot:'1230', lang:'zh'}, out, why);
if (fs.existsSync(out + '.part.mp4')) process.exit(3);
if (fs.existsSync(out)) process.exit(4);
if (fs.existsSync(out.replace(/\.mp4$/, '.vo.json'))) process.exit(5);
const en = voiceoverSkip(undefined);
if (!en) process.exit(6);
const empty = voiceoverSkip([]);
if (!empty) process.exit(7);
console.log(why);
'''
    text = _node(script, [out])
    assert 'no voiceover' in text
    assert not os.path.exists(out)
    assert not os.path.exists(out + '.part.mp4')
    src = open(os.path.join(TOOLS, 'carousel_video.js'), encoding='utf-8').read()
    assert 'dropping voice' not in src
    assert '出冇配音版' not in src


def test_over_40_no_mp4():
    """Voiced cut > 40s (zh and en): skip, no mp4. Same rule for both languages."""
    d = tempfile.mkdtemp()
    clips = []
    for i in range(len(carousel_vo.BASE_BEATS)):
        p = os.path.join(d, f'vo-{i}.mp3')
        open(p, 'wb').write(b'x')
        clips.append({'file': p, 'dur': 9.0})
    out = os.path.join(d, '2026-10-23-1230-en.mp4')
    open(out + '.part.mp4', 'w').write('part')
    script = r'''
const { voiceoverSkip, refuseVideo, voicedTotal, MAX_VIDEO_S } = require('./tools/carousel_video.js');
const fs = require('fs');
const clips = JSON.parse(process.argv[1]);
const out = process.argv[2];
if (!(voicedTotal(clips) > MAX_VIDEO_S)) process.exit(2);
for (const lang of ['en', 'zh']) {
  const why = voiceoverSkip(clips);
  if (!why || !why.includes('> 40')) process.exit(3);
  refuseVideo({slot:'1230', lang}, out, why);
}
if (fs.existsSync(out + '.part.mp4')) process.exit(4);
if (fs.existsSync(out)) process.exit(5);
if (fs.existsSync(out.replace(/\.mp4$/, '.vo.json'))) process.exit(6);
const short = clips.map(c => Object.assign({}, c, {dur: 1.2}));
if (voiceoverSkip(short)) process.exit(7);
console.log('ok');
'''
    _node(script, [json.dumps(clips), out])
    assert not os.path.exists(out)
    src = open(os.path.join(TOOLS, 'carousel_video.js'), encoding='utf-8').read()
    assert "job.lang === 'en' && total > 40" not in src


def test_missing_vo_audio_no_mp4():
    d = tempfile.mkdtemp()
    clips = [{'file': os.path.join(d, 'missing.mp3'), 'dur': 1.2} for _ in range(len(carousel_vo.BASE_BEATS))]
    script = r'''
const { voiceoverSkip } = require('./tools/carousel_video.js');
const why = voiceoverSkip(JSON.parse(process.argv[1]));
if (why !== 'voiceover audio missing') process.exit(2);
console.log(why);
'''
    assert 'voiceover audio missing' in _node(script, [json.dumps(clips)])


def test_vo_marker_after_mp4():
    """Sidecar is written only as {voice, duration, vo:true}, and in source after renameSync."""
    d = tempfile.mkdtemp()
    out = os.path.join(d, '2026-10-23-1230-zh.mp4')
    open(out, 'wb').write(b'x')
    script = r'''
const { writeVoMarker, voMarkerPath } = require('./tools/carousel_video.js');
const fs = require('fs');
const out = process.argv[1];
writeVoMarker(out, {lang: 'zh'}, 27.125);
const mark = JSON.parse(fs.readFileSync(voMarkerPath(out), 'utf8'));
if (mark.vo !== true) process.exit(2);
if (mark.voice !== 'zh-CN-XiaoxiaoNeural') process.exit(3);
if (mark.duration !== 27.125) process.exit(4);
console.log(JSON.stringify(mark));
'''
    mark = json.loads(_node(script, [out]).strip())
    assert mark == {'voice': 'zh-CN-XiaoxiaoNeural', 'duration': 27.125, 'vo': True}
    src = open(os.path.join(TOOLS, 'carousel_video.js'), encoding='utf-8').read()
    assert src.index('fs.renameSync(tmpOut, outFile)') < src.index('writeVoMarker(outFile, job, total);')


def test_prune():
    """Missing en file (and its marker) drops en; missing everything drops the key."""
    with _ogc({
        '2026-10-23-1230-zh.mp4': True,
        '2026-10-23-1230-zh.vo.json': MARK_ZH,
    }):
        sp = _slot()
        assert prune(sp, probe=lambda p: None)
        assert sp['slots']['1230']['video'] == {'zh': URL.format('zh')}
        assert not prune(sp, probe=lambda p: None)
    with _ogc({}):
        sp = _slot()
        assert prune(sp, probe=lambda p: None)
        assert 'video' not in sp['slots']['1230']


def test_prune_cover():
    """video_cover drops a language whose poster is missing, and the key when none is left. video stays."""
    with _ogc({
        '2026-10-23-1230-zh.mp4': True,
        '2026-10-23-1230-en.mp4': True,
        '2026-10-23-1230-zh.vo.json': MARK_ZH,
        '2026-10-23-1230-en.vo.json': MARK_EN,
        '2026-10-23-1230-zh-cover.jpg': True,
    }):
        sp = _slot(cover=True)
        assert prune(sp, probe=lambda p: None)
        assert sp['slots']['1230']['video'] == {'zh': URL.format('zh'), 'en': URL.format('en')}
        assert sp['slots']['1230']['video_cover'] == {'zh': COVER_URL.format('zh')}
        assert not prune(sp, probe=lambda p: None)
    with _ogc({
        '2026-10-23-1230-zh.mp4': True,
        '2026-10-23-1230-en.mp4': True,
        '2026-10-23-1230-zh.vo.json': MARK_ZH,
        '2026-10-23-1230-en.vo.json': MARK_EN,
    }):
        sp = _slot(cover=True)
        assert prune(sp, probe=lambda p: None)
        assert 'video_cover' not in sp['slots']['1230']
        assert set(sp['slots']['1230']['video']) == {'zh', 'en'}


def test_prune_without_marker():
    with _ogc({'2026-10-23-1230-zh.mp4': True}):
        sp = _slot(langs=('zh',), cover=True)
        assert prune(sp, probe=lambda p: {'audio': True, 'duration': 20})
        assert 'video' not in sp['slots']['1230']
        assert 'video_cover' not in sp['slots']['1230']


def test_prune_without_audio():
    with _ogc({
        '2026-10-23-1230-zh.mp4': True,
        '2026-10-23-1230-zh.vo.json': MARK_ZH,
        '2026-10-23-1230-zh-cover.jpg': True,
    }):
        sp = _slot(langs=('zh',), cover=True)
        assert prune(sp, probe=lambda p: {'audio': False, 'duration': 20})
        assert 'video' not in sp['slots']['1230']
        assert 'video_cover' not in sp['slots']['1230']


def test_prune_too_long():
    with _ogc({
        '2026-10-23-1230-zh.mp4': True,
        '2026-10-23-1230-zh.vo.json': MARK_ZH,
    }):
        sp = _slot(langs=('zh',))
        assert prune(sp, probe=lambda p: {'audio': True, 'duration': 40.01})
        assert 'video' not in sp['slots']['1230']


def test_prune_happy_path():
    with _ogc({
        '2026-10-23-1230-zh.mp4': True,
        '2026-10-23-1230-en.mp4': True,
        '2026-10-23-1230-zh.vo.json': MARK_ZH,
        '2026-10-23-1230-en.vo.json': MARK_EN,
        '2026-10-23-1230-zh-cover.jpg': True,
        '2026-10-23-1230-en-cover.jpg': True,
    }):
        sp = _slot(cover=True)
        assert not prune(sp, probe=lambda p: {'audio': True, 'duration': 40.0})
        assert set(sp['slots']['1230']['video']) == {'zh', 'en'}
        assert set(sp['slots']['1230']['video_cover']) == {'zh', 'en'}
        # no ffprobe: marker is enough
        assert not prune(sp, probe=lambda p: None)


def test_prune_vo_false_and_cover_follows_video():
    with _ogc({
        '2026-10-23-1230-zh.mp4': True,
        '2026-10-23-1230-zh.vo.json': {'voice': 'x', 'duration': 20, 'vo': False},
        '2026-10-23-1230-en.mp4': True,
        '2026-10-23-1230-en.vo.json': MARK_EN,
        '2026-10-23-1230-zh-cover.jpg': True,
        '2026-10-23-1230-en-cover.jpg': True,
    }):
        sp = _slot(cover=True)
        assert prune(sp, probe=lambda p: None)
        assert sp['slots']['1230']['video'] == {'en': URL.format('en')}
        assert sp['slots']['1230']['video_cover'] == {'en': COVER_URL.format('en')}


def test_og_c_cleanup_includes_markers():
    src = open(os.path.join(TOOLS, 'carousel.js'), encoding='utf-8').read()
    assert "fs.readdirSync('og/c')" in src
    assert 'm[1] < keep' in src
    pat = re.compile(r'^(\d{4}-\d{2}-\d{2})-')
    assert pat.match('2026-10-23-1230-zh.vo.json').group(1) == '2026-10-23'
    yml = open(os.path.join(ROOT, '.github/workflows/update-site.yml'), encoding='utf-8').read()
    assert 'git add -A' in yml and ' og/' in yml
    assert '.vo.json' in yml or 'voiceover markers' in yml


def test_cover_text_and_encode():
    """IG encode flags; v6 merges cover into open (COVER_FRAMES=0) with $TICKER on frame 0."""
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'carousel_video.js'), encoding='utf-8').read()
    assert 'format=yuv420p' in src and 'yuv420p' in src
    assert 'out_range=tv' in src and "'-color_range', 'tv'" in src
    assert '+faststart' in src
    assert "'-profile:v', 'high'" in src and 'libx264' in src
    assert re.search(r'const COVER_FRAMES = 0', src)
    assert "['open'" in src and "['cta'" in src
    assert 'carousel_motion.js' not in src  # comic slides no longer filmed
    assert '🚀' not in src and '😱' not in src
    scenes = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'carousel_scenes.js'), encoding='utf-8').read()
    html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'carousel_scene.html'), encoding='utf-8').read()
    # Canva lock 2026-11-05 cream (#FFF9EE); legacy #FFF6EC still accepted as close.
    assert ('#FFF9EE' in html or '#FFF6EC' in html) and 'frame-bg' in html and 'cat-host' in html
    assert '#E8940A' in html or '--ticker' in html  # cream-world ticker
    assert '#07080c' not in html and 'bg-flare' not in html  # no dark energy crush
    assert 'show-badge' in html and 'speech-bubble' in html and 'lightning' in html
    assert '#F06A4D' in html and '#BAE6FD' in html
    assert 'setup' in scenes and 'open' in scenes and 'cta' in scenes
    assert "mode === 'quote'" in scenes or 'isQuote' in scenes
    assert 'energyBg' in scenes or 'brightBg' in scenes
    assert 'showBadge' in scenes and 'accentHookHtml' in scenes
    assert 'setCat' in scenes and 'catMouthOpen' in scenes and 'setMouth' in scenes
    py = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'carousel.py'), encoding='utf-8').read()
    assert "['video_cover']" in py and '-cover.jpg' in py



def test_social_page():
    posts = {k: 'text' for k in ('x', 'threads', 'instagram', 'facebook')}
    sl = {'day': '2026-10-23', 'made_hkt': '2026-10-23 07:20', 'images': {l: [] for l in ('zh', 'en')},
          'posts': {l: dict(posts) for l in ('zh', 'en')}, 'video': {'zh': URL.format('zh')}}
    page = carousel.slot_page({'slots': {'1230': sl}})
    assert page.count('<video') == 1 and URL.format('zh') in page
    sl.pop('video')
    assert '<video' not in carousel.slot_page({'slots': {'1230': sl}})



def test_video_missing_redo():
    from datetime import datetime
    at = lambda h, m: datetime(2026, 10, 27, h, m)
    full = {'video': {'zh': URL.format('zh'), 'en': URL.format('en')}}
    assert not carousel.video_missing(full, '1230', at(11, 30))
    assert carousel.video_missing({'video': {'zh': URL.format('zh')}}, '1230', at(11, 30))
    assert carousel.video_missing({}, '1230', at(7, 40))
    assert not carousel.video_missing({}, '1230', at(12, 10))  # too close to the 12:30 post
    assert carousel.video_missing({}, '1630', at(11, 0))  # Crowd Heat also gets video
    assert not carousel.video_missing({}, '2030', at(11, 0))  # 2030 still no video

def test_zh_video_text_is_written_chinese():
    """Tim 2026-10-28: Chinese text in the videos (and the pictures they show) is standard written Chinese, not Cantonese."""
    import carousel
    import carousel_vo
    import earnings_posts
    canto = re.compile('[嘅唔冇睇哋咗喺嗰啲仲企晒咁乜嚟俾]|撐得|講緊|點講|點睇|好過|差過|打和|今日')
    bad = []

    def check(where, v):
        if callable(v):
            v = v(3) if v.__code__.co_argcount == 1 else v(3, 2)
        if isinstance(v, (list, tuple)):
            for x in v:
                check(where, x)
        elif isinstance(v, str) and canto.search(v):
            bad.append(f'{where}: {v}')
    for k, v in carousel.PIC['zh'].items():
        check(f'carousel.PIC.{k}', v)
    check('carousel.TALK', carousel.TALK['zh'])
    for k, v in earnings_posts.CARD['zh'].items():
        check(f'earnings CARD.{k}', v)
    co = {'kind': 'cover', 'big': 'SPY', 'sub': '15', 'pills': [{'c': 'g', 'x': '3'}, {'c': 'r', 'x': '6'}]}
    job = {'lang': 'zh', 'slides': [co, {'secs': []}, {'secs': []}, {'secs': []}]}
    check('carousel_vo.lines', carousel_vo.lines(job))
    js = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'carousel_video.js'), encoding='utf-8').read()
    for line in js.splitlines():
        if line.strip().startswith(('zh:', 'vs:', 'caps:', 'outro:')) and not line.strip().startswith('console'):
            if canto.search(line.replace('::warning::', '')):
                bad.append('carousel_video.js: ' + line.strip())
    for name in ('carousel.html', 'earnings_card.html'):
        txt = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name), encoding='utf-8').read()
        m = re.search(r"const FL=\{zh:'([^']*)'", txt)
        check(name, m.group(1) if m else '')
    assert not bad, '\n'.join(bad)



def test_yt_sidecars_js():
    """EN YT title/desc sidecar helper (tools/yt_sidecars.js) — Tim 2026-11-05 complete sets."""
    script = r"""
const { buildYtCopy, shortWindow } = require('./tools/yt_sidecars');
const assert = require('assert');
assert.strictEqual(shortWindow('11/3 21:10 – 11/5 01:19 HKT'), '11/3–11/5 HKT');
const job = { date: '2026-11-05', slot: '1630', lang: 'en', show: 'crowd-heat' };
const W = {
  showId: 'crowd-heat', showLabel: 'Crowd Heat', big: 'PLTR', n: 4, bull: 3, bear: 1,
  open: { big: 'PLTR', hookQ: "Everyone's screaming about $PLTR — who's actually making sense?", date: '11/3–11/4 HKT' },
  m1: { handle: '@amitisinvesting', lines: ['PLTR revenue +96%, US commercial +148% YoY.'] },
};
const { title, desc } = buildYtCopy(job, W);
assert.ok(title.includes('Crowd Heat') && title.includes('$PLTR') && title.includes('#Shorts'));
assert.ok(desc.includes('On X, @amitisinvesting:'));
assert.ok(desc.includes('Tape Cats · Crowd Heat'));
console.log('ok');
"""
    r = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr or r.stdout

if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print('ok', name)
