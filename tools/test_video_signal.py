"""Skip gate and Week Tape hot-list (tools/video_signal.py).

Offline. No ffmpeg render, no network. Run from the repo root:
    python3 tools/test_video_signal.py
"""
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import carousel_vo  # noqa: E402
import video_signal  # noqa: E402
from carousel_video_post import max_for_slot, prune  # noqa: E402

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
BEAT = 60 / 124
WEEK_HOOK = "This week's most discussed stocks."
WEEK_CTA = 'Which of these are you on — bull or bear?'


def cited(t, accounts, bull, bear, **extra):
    row = {
        't': t,
        'accounts': accounts,
        'bull_accounts': bull,
        'bear_accounts': bear,
        'urls': [f'https://x.com/{t}/status/1'],
    }
    row.update(extra)
    return row


def _lines(decision, closes_for=None):
    beats = video_signal.script_beats(decision, closes_for=closes_for or (lambda _t: []))
    return [b['vo'] for b in beats], beats


def _seconds(beats):
    return sum(b['base'] for b in beats) * BEAT


def _no_site(lines):
    blob = '\n'.join(lines)
    low = blob.lower()
    assert 'thecrowdtape' not in low, blob
    assert 'thecrowdtape dot com' not in low, blob
    assert 'follow' not in low, blob
    assert 'subscribe' not in low, blob


def test_weekday_skip_zero_no_heat():
    """Weekday 0/0 stance, and a day with no heat, both skip."""
    zero = video_signal.select_weekday([cited('SPY', 12, 0, 0)])
    assert zero['publishable'] is False and zero['mode'] == 'skip', zero
    assert zero['reason'] == 'zero_stance', zero
    assert zero['names'] == []

    cold = video_signal.select_weekday([cited('SPY', 0, 0, 0)])
    assert cold['publishable'] is False and cold['mode'] == 'skip', cold
    assert cold['reason'] == 'no_heat', cold

    empty = video_signal.evaluate_slot(
        '1230', {'daily': {'top': []}}, date='2026-11-11', lang='en')
    assert empty['publishable'] is False and empty['mode'] == 'skip', empty
    assert empty['show'] == 'tape-take'


def test_weekday_skip_mild_pile():
    """A pile of weak names, none a clear leader and none a real split, skips."""
    names = [
        cited('AAA', 4, 3, 1),
        cited('BBB', 4, 3, 1),
        cited('CCC', 5, 4, 1),
    ]
    for n in names:
        ok, why = video_signal.qualify_name(n)
        assert ok, (n['t'], why)
        assert not video_signal.is_split(n['bull_accounts'], n['bear_accounts'])
    got = video_signal.select_weekday(names)
    assert got['publishable'] is False and got['mode'] == 'skip', got
    assert got['reason'] == 'no_contrast', got
    assert got['names'] == []

    decided = video_signal.evaluate_slot(
        '1630', {'daily': {'top': names}}, date='2026-11-11', lang='en')
    assert decided['publishable'] is False and decided['show'] == 'crowd-heat'


def test_week_tape_zero_qualifying():
    """Empty Week Tape, or a week that is all 0–0, skips. Nothing is padded in."""
    empty = video_signal.select_week_tape([])
    assert empty['publishable'] is False and empty['mode'] == 'skip' and empty['names'] == []

    via_slot = video_signal.evaluate_slot(
        'sat', {'weekly': {'top': []}}, date='2026-11-14', lang='en')
    assert via_slot['publishable'] is False and via_slot['show'] == 'week-tape', via_slot

    zeros = video_signal.select_week_tape([
        cited('SPY', 0, 0, 0),
        cited('QQQ', 0, 0, 0),
    ])
    assert zeros['publishable'] is False and zeros['mode'] == 'skip', zeros
    assert zeros['names'] == []

    stance = video_signal.select_week_tape([
        cited('SPY', 9, 0, 0),
        cited('IWM', 4, 0, 0),
    ])
    assert stance['publishable'] is False and stance['reason'] == 'zero_stance', stance


def test_week_tape_two_not_padded():
    names = [
        cited('NVDA', 11, 8, 3),
        cited('AMD', 7, 5, 2),
        cited('WEAK', 1, 1, 0),
        cited('FLAT', 8, 0, 0),
    ]
    got = video_signal.evaluate_slot(
        'sat', {'weekly': {'top': names}}, date='2026-11-14', lang='en')
    assert got['publishable'] is True and got['mode'] == 'hot-list', got
    assert [n['t'] for n in got['names']] == ['NVDA', 'AMD'], [n['t'] for n in got['names']]
    assert len(got['names']) == 2
    lines, beats = _lines(got)
    assert lines[0] == WEEK_HOOK, lines[0]
    assert lines[-1] == WEEK_CTA, lines[-1]
    assert sum(1 for b in beats if b['role'] == 'heat') == 2
    assert video_signal.video_cap({'mode': 'hot-list', 'beats': beats}) == video_signal.WEEK_MAX_VIDEO_S
    _no_site(lines)


def test_week_tape_one_is_single():
    """Exactly one qualifying name uses the 30–40s single path, not a padded list."""
    names = [
        cited('QQQ', 9, 6, 3),
        cited('SPY', 0, 0, 0),
        cited('IWM', 1, 1, 0),
    ]
    got = video_signal.evaluate_slot(
        'sat', {'weekly': {'top': names}}, date='2026-11-14', lang='en')
    assert got['publishable'] is True and got['mode'] == 'single', got
    assert [n['t'] for n in got['names']] == ['QQQ']
    lines, beats = _lines(got)
    assert sum(1 for b in beats if b['role'] == 'heat') == 1
    assert lines[0] != WEEK_HOOK
    assert lines[-1] != WEEK_CTA
    assert lines[-1] == 'Bull or bear on Q Q Q?', lines[-1]
    assert video_signal.video_cap({'mode': got['mode'], 'slot': 'sat', 'beats': beats}) == 40.0
    assert 30.0 <= _seconds(beats) <= 40.0, _seconds(beats)
    roles = [b['role'] for b in beats]
    assert roles[0] == 'hook' and roles[-1] == 'cta'
    assert 'ta' not in roles  # no closes, so beat ② is omitted rather than invented
    _no_site(lines)


def test_week_tape_five_hot():
    """Five names that clear the gate. A hotter 0/0 and a sub-gate name stay out."""
    names = [
        cited('MOST', 40, 0, 0),
        cited('A', 30, 18, 12),
        cited('B', 22, 8, 0),
        cited('C', 16, 9, 7),
        cited('D', 12, 7, 5),
        cited('E', 9, 6, 3),
        cited('WEAK', 2, 2, 0),
    ]
    got = video_signal.select_week_tape(names)
    assert got['publishable'] is True and got['mode'] == 'hot-list', got
    tickers = [n['t'] for n in got['names']]
    assert tickers == ['A', 'B', 'C', 'D', 'E'], tickers
    assert 'MOST' not in tickers and 'WEAK' not in tickers
    assert len(got['names']) == 5
    for n in got['names']:
        ok, why = video_signal.qualify_name(n)
        assert ok, (n['t'], why)
        assert n['accounts'] >= video_signal.MIN_HEAT_ACCOUNTS
    assert got['names'][1]['angle'] == 'one_sided_bull'
    assert got['names'][1]['angle'] != 'split'
    lines, beats = _lines({'mode': 'hot-list', 'slot': 'sat', 'names': got['names']})
    assert lines[0] == WEEK_HOOK
    assert lines[-1] == WEEK_CTA
    assert sum(1 for b in beats if b['role'] == 'heat') == 5
    _no_site(lines)


def test_one_sided_hot_not_called_split():
    name = cited('NVDA', 8, 8, 0)
    assert video_signal.qualify_name(name)[0] is True
    assert video_signal.is_split(8, 0) is False
    assert video_signal.angle_of(8, 0) == 'one_sided_bull'
    got = video_signal.select_weekday([name])
    assert got['publishable'] is True and got['mode'] == 'single', got
    assert got['names'][0]['t'] == 'NVDA'
    assert got['names'][0]['angle'] == 'one_sided_bull'
    lines, beats = _lines(got)
    assert lines[0] == 'N V D A is the most discussed name on the tape today.', lines[0]
    assert 'fight' not in lines[0].lower()
    views = next(b for b in beats if b['role'] == 'views')
    assert views['visual']['angle'] == 'one_sided_bull'
    assert 'split' not in views['vo'].lower()
    assert 'fight' not in views['vo'].lower()
    assert 'lean bullish' in views['vo'].lower()
    assert 'almost no bear case' in views['vo'].lower()
    assert lines[-1] == 'Bull or bear on N V D A?'
    _no_site(lines)


def test_split_ratio():
    assert video_signal.is_split(5, 4) is True
    assert video_signal.is_split(68, 51) is True
    assert video_signal.is_split(99, 1) is False
    assert video_signal.is_split(8, 0) is False
    assert video_signal.angle_of(5, 4) == 'split'
    assert video_signal.angle_of(68, 51) == 'split'
    assert video_signal.angle_of(99, 1) == 'one_sided_bull'
    fight = video_signal._hook_vo('QQQ', 6, 5)
    lean = video_signal._hook_vo('QQQ', 99, 1)
    assert fight == 'The fight today is Q Q Q.', fight
    assert lean == 'Q Q Q is the most discussed name on the tape today.', lean
    assert 'fight' not in lean.lower()


def test_weekday_skips_zero_hero_for_qqq():
    """Most-mentioned 0/0 stays off the open. A real QQQ 6/5 split is the cut."""
    window = {
        'top': [cited('SPY', 24, 0, 0)],
        'split': [{'t': 'QQQ', 'nb': 6, 'nr': 5, 'rows': [{'acc': 'tracked', 'url': 'https://x.com/tracked/status/9'}]}],
    }
    got = video_signal.evaluate_slot('1230', {'daily': window}, date='2026-11-11', lang='en')
    assert got['publishable'] is True and got['mode'] == 'single', got
    assert [n['t'] for n in got['names']] == ['QQQ'], got['names']
    assert got['names'][0]['angle'] == 'split'
    assert got['names'][0]['bull_accounts'] == 6 and got['names'][0]['bear_accounts'] == 5
    lines, _beats = _lines(got)
    assert lines[0] == 'The fight today is Q Q Q.', lines[0]
    assert 'S P Y' not in lines[0]
    assert lines[-1] == 'Bull or bear on Q Q Q?'
    _no_site(lines)


def test_ta_short_series_omits_beat():
    """Fewer than 50 closes and a mid RSI: beat ② is omitted. No invented price."""
    closes = [432.10] * 40
    assert len(closes) < 50
    rsi = video_signal.rsi_wilder(closes, 14)
    assert rsi is not None and 30 < rsi < 70, rsi
    assert video_signal.sma(closes, 50) is None
    assert video_signal.ta_fact(closes) is None
    name = cited('QQQ', 8, 6, 2)
    got = video_signal.select_weekday([name])
    lines, beats = _lines(got, closes_for=lambda _t: closes)
    assert not any(b['role'] == 'ta' for b in beats), [b['role'] for b in beats]
    blob = '\n'.join(lines)
    assert '432' not in blob, blob
    assert 'rsi' not in blob.lower()
    assert '50-day' not in blob.lower()
    assert 'support' not in blob.lower()
    _no_site(lines)


def test_ta_on_sma50_is_one_fact():
    """Close within 1.5% of the 50-day: exactly one fact, no second indicator."""
    closes = [100.0] * 49 + [101.0]
    assert len(closes) >= 50
    sma50 = video_signal.sma(closes, 50)
    rel = closes[-1] / sma50 - 1.0
    assert abs(rel) <= video_signal.SMA_BAND, rel
    fact = video_signal.ta_fact(closes)
    assert fact is not None
    assert fact['id'] == 'sma50_on', fact
    assert fact['line'] == "It's sitting on the 50-day."
    assert 'rsi' not in fact['line'].lower()
    assert 'support' not in fact['line'].lower()
    assert fact['note'] == 'This is not a trade signal.'
    name = cited('QQQ', 8, 5, 3)
    _lines_out, beats = _lines(
        video_signal.select_weekday([name]), closes_for=lambda _t: list(closes))
    ta = [b for b in beats if b['role'] == 'ta']
    assert len(ta) == 1, [b['role'] for b in beats]
    vo = ta[0]['vo']
    assert "It's sitting on the 50-day." in vo
    assert 'This is not a trade signal.' in vo
    assert 'rsi' not in vo.lower()
    assert 'lost support' not in vo.lower()
    assert 'above the 50-day' not in vo.lower()
    assert '101' not in vo and '100' not in vo
    assert [b['role'] for b in beats].count('ta') == 1


def test_counts_bar_without_pills():
    cover = {'big': 'QQQ', 'bar': [5, 3]}
    n, bull, bear = video_signal.counts(cover)
    assert (bull, bear) == (5, 3), (n, bull, bear)
    assert carousel_vo.counts(cover)[1:] == (5, 3)
    script = r'''
const { stanceFrom, words } = require('./tools/carousel_video.js');
const s = stanceFrom({ big: 'QQQ', bar: [5, 3] });
if (s.bull !== 5 || s.bear !== 3) process.exit(2);
const w = words('en', [{ big: 'QQQ', bar: [5, 3] }], { slot: '1630', show: 'crowd-heat' });
if (w.bull !== 5 || w.bear !== 3) process.exit(3);
console.log(JSON.stringify({ bull: w.bull, bear: w.bear }));
'''
    proc = subprocess.run(['node', '-e', script], cwd=ROOT, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    got = json.loads(proc.stdout.strip().splitlines()[-1])
    assert got == {'bull': 5, 'bear': 3}, got


def test_en_hooks_and_cta():
    week = video_signal.evaluate_slot('sat', {'weekly': {'top': [
        cited('NVDA', 12, 8, 4),
        cited('AMD', 9, 5, 4),
    ]}}, date='2026-11-14')
    lines, _beats = _lines(week)
    assert lines[0] == WEEK_HOOK
    assert lines[-1] == WEEK_CTA
    _no_site(lines)

    split = video_signal.select_weekday([cited('SPY', 15, 6, 5)])
    split_lines, _ = _lines(split)
    assert split_lines[0] == 'The fight today is S P Y.', split_lines[0]
    assert split_lines[-1] == 'Bull or bear on S P Y?'
    _no_site(split_lines)

    lean = video_signal.select_weekday([cited('TSLA', 8, 8, 0)])
    lean_lines, _ = _lines(lean)
    assert lean_lines[0] == 'T S L A is the most discussed name on the tape today.', lean_lines[0]
    assert 'fight' not in lean_lines[0].lower()
    assert lean_lines[-1] == 'Bull or bear on T S L A?'
    _no_site(lean_lines)

    assert video_signal._cta_vo('SPY', week_list=False) == 'Bull or bear on S P Y?'
    assert 'thecrowdtape dot com' not in '\n'.join(split_lines + lean_lines + lines).lower()


def test_duration_caps():
    """Weekday single stays inside 30–40s. A ~60s Week Tape hot-list is not a 40s fail."""
    single = video_signal.select_weekday([cited('QQQ', 8, 5, 3)])
    _lines_out, beats = _lines(single, closes_for=lambda _t: [100.0] * 60)
    assert any(b['role'] == 'ta' for b in beats)
    assert 30.0 <= _seconds(beats) <= 40.0, _seconds(beats)
    assert video_signal.video_cap({'mode': 'single', 'beats': beats}) == 40.0

    five = video_signal.select_week_tape([
        cited(t, 20 - i, 6, 4) for i, t in enumerate(['A', 'B', 'C', 'D', 'E'])
    ])
    assert five['mode'] == 'hot-list' and len(five['names']) == 5
    hot_beats = video_signal.build_beats(
        five['names'], mode='hot-list',
        facts={n['t']: {
            'id': 'sma50_on', 'line': "It's sitting on the 50-day.",
            'caption': 'On the 50-day', 'note': 'This is not a trade signal.',
        } for n in five['names']},
    )
    hot_s = _seconds(hot_beats)
    assert hot_s > 40.0, hot_s
    assert hot_s <= 75.0, hot_s
    job = {'mode': 'hot-list', 'beats': hot_beats}
    assert video_signal.video_cap(job) == 75.0
    assert max_for_slot('sat', {'show': 'week-tape', 'mode': 'hot-list'}) == 75.0
    assert max_for_slot('sat', {'show': 'week-tape', 'mode': 'single'}) == 40.0
    assert max_for_slot('1230', {'show': 'tape-take', 'mode': 'single'}) == 40.0

    # Node uses the same cap: a ~60s hot-list is voiced; the same length fails a weekday single.
    payload = json.dumps({
        'bases': [b['base'] for b in hot_beats],
        'n': len(hot_beats),
    })
    script = r'''
const fs = require('fs');
const os = require('os');
const path = require('path');
const { videoCap, voiceoverSkip, WEEK_MAX_VIDEO_S, MAX_VIDEO_S } = require('./tools/carousel_video.js');
const spec = JSON.parse(process.argv[1]);
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'vs-cap-'));
const clips = spec.bases.map((base, i) => {
  const file = path.join(dir, i + '.mp3');
  fs.writeFileSync(file, 'x');
  return { file, dur: 0.5, base };
});
const beats = spec.bases.map(base => ({ role: 'heat', base }));
const hot = { mode: 'hot-list', beats };
const day = { mode: 'single', beats: [{ role: 'heat', base: 6 }] };
if (videoCap(hot) !== WEEK_MAX_VIDEO_S) process.exit(2);
if (videoCap(day) !== MAX_VIDEO_S) process.exit(3);
const whyHot = voiceoverSkip(clips, hot);
if (whyHot) { console.error(whyHot); process.exit(4); }
const long = clips.map(c => Object.assign({}, c, { dur: 9 }));
const whyDay = voiceoverSkip(long.slice(0, 5), { mode: 'single' });
if (!whyDay || whyDay.indexOf('> 40') < 0) { console.error(whyDay); process.exit(5); }
console.log('ok');
'''
    proc = subprocess.run(['node', '-e', script, payload], cwd=ROOT, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr + proc.stdout


def test_week_list_60s_kept_by_prune():
    d = tempfile.mkdtemp(prefix='vs-prune-')
    cwd = os.getcwd()
    try:
        os.chdir(d)
        os.makedirs('og/c')
        stem = '2026-11-14-week-tape-en'
        open(f'og/c/{stem}.mp4', 'wb').write(b'x')
        json.dump({'voice': 'en-US-AndrewNeural', 'duration': 60.0, 'vo': True},
                  open(f'og/c/{stem}.vo.json', 'w', encoding='utf-8'))
        url = f'https://thecrowdtape.com/og/c/{stem}.mp4'
        sp = {'slots': {'sat': {
            'show': 'week-tape', 'mode': 'hot-list', 'video': {'en': url},
        }}}
        assert prune(sp, probe=lambda _p: {'audio': True, 'duration': 60.0}) is False
        assert sp['slots']['sat']['video']['en'] == url
        day_stem = '2026-11-11-tape-take-en'
        open(f'og/c/{day_stem}.mp4', 'wb').write(b'x')
        json.dump({'voice': 'en-US-AndrewNeural', 'duration': 60.0, 'vo': True},
                  open(f'og/c/{day_stem}.vo.json', 'w', encoding='utf-8'))
        day_url = f'https://thecrowdtape.com/og/c/{day_stem}.mp4'
        day = {'slots': {'1230': {
            'show': 'tape-take', 'mode': 'single', 'video': {'en': day_url},
        }}}
        assert prune(day, probe=lambda _p: {'audio': True, 'duration': 60.0}) is True
        assert 'video' not in day['slots']['1230']
    finally:
        os.chdir(cwd)


def test_skip_path_no_ffmpeg():
    """Skip writes publishable:false, no mp4 / vo:true, and the entrypoint exits 0 without ffmpeg."""
    tmp = tempfile.mkdtemp(prefix='vs-skip-')
    day = '2026-11-14'
    show = 'week-tape'
    stem = os.path.join(tmp, 'og', 'c', f'{day}-{show}-en')
    os.makedirs(os.path.dirname(stem), exist_ok=True)
    open(stem + '.mp4', 'wb').write(b'not a video')
    json.dump({'vo': True, 'voice': 'en-US-AndrewNeural', 'duration': 33},
              open(stem + '.vo.json', 'w', encoding='utf-8'))
    open(stem + '-cover.jpg', 'wb').write(b'jpg')
    open(stem + '-yt-title.txt', 'w', encoding='utf-8').write('title\n')
    old_work = os.environ.get('WORK_DIR')
    os.environ['WORK_DIR'] = os.path.join(tmp, 'work')
    try:
        path = video_signal.write_skip({
            'date': day, 'show': show, 'slot': 'sat', 'lang': 'en',
            'reason': 'no_names', 'detail': 'No qualifying name for Week Tape.',
        }, root=tmp)
    finally:
        if old_work is None:
            os.environ.pop('WORK_DIR', None)
        else:
            os.environ['WORK_DIR'] = old_work
    payload = json.load(open(path, encoding='utf-8'))
    assert payload['publishable'] is False
    assert payload['reason'] == 'no_names'
    status = json.load(open(os.path.join(tmp, 'work', 'video-status.json'), encoding='utf-8'))
    assert status['publishable'] is False
    assert not os.path.exists(stem + '.mp4')
    assert not os.path.exists(stem + '.vo.json')
    assert not os.path.exists(stem + '-cover.jpg')
    assert not os.path.exists(stem + '-yt-title.txt')

    # Voiceover entrypoint: a skip job returns without calling ffmpeg.
    called = []

    def _boom(*args, **kwargs):
        called.append(args)
        raise AssertionError('ffmpeg invoked on a skip')

    old_run = carousel_vo.subprocess.run
    old_slots = os.environ.get('VIDEO_SLOTS')
    old_langs = os.environ.get('VO_LANGS')
    old_fake = os.environ.get('VO_FAKE')
    os.environ['VIDEO_SLOTS'] = '1230'
    os.environ['VO_LANGS'] = 'en'
    os.environ['VO_FAKE'] = '1'
    carousel_vo.subprocess.run = _boom
    vo_dir = os.path.join(tmp, 'vo')
    job_path = os.path.join(tmp, 'carousel.json')
    json.dump({'jobs': [{
        'slot': '1230', 'lang': 'en', 'date': '2026-11-11', 'show': 'tape-take',
        'video_skip': True, 'publishable': False,
        'signal': {'publishable': False, 'reason': 'no_heat', 'detail': 'no heat'},
        'slides': [{'kind': 'cover', 'big': 'SPY', 'sub': '0', 'bar': [0, 0]}],
    }]}, open(job_path, 'w', encoding='utf-8'))
    try:
        carousel_vo.main(job_path, vo_dir)
    finally:
        carousel_vo.subprocess.run = old_run
        for key, prev in (('VIDEO_SLOTS', old_slots), ('VO_LANGS', old_langs), ('VO_FAKE', old_fake)):
            if prev is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev
    assert called == []
    vo = json.load(open(os.path.join(vo_dir, 'vo.json'), encoding='utf-8'))
    assert '1230-en' not in vo
    assert not any(isinstance(v, dict) and v.get('vo') is True for v in vo.values())

    # Render entrypoint: node tools/carousel_video.js exits 0 and never execs ffmpeg.
    render_dir = tempfile.mkdtemp(prefix='vs-node-skip-')
    bin_dir = os.path.join(render_dir, 'bin')
    os.makedirs(bin_dir)
    marker = os.path.join(render_dir, 'ffmpeg-called')
    ffmpeg = os.path.join(bin_dir, 'ffmpeg')
    open(ffmpeg, 'w', encoding='utf-8').write(
        '#!/bin/sh\necho called >> "$FFMPEG_CALLED"\nexit 99\n')
    os.chmod(ffmpeg, 0o755)
    os.makedirs(os.path.join(render_dir, 'og', 'c'))
    planted = os.path.join(render_dir, 'og', 'c', '2026-11-11-tape-take-en')
    open(planted + '.mp4', 'wb').write(b'x')
    json.dump({'vo': True}, open(planted + '.vo.json', 'w', encoding='utf-8'))
    open(planted + '-cover.jpg', 'wb').write(b'x')
    open(planted + '-yt-title.txt', 'w', encoding='utf-8').write('t\n')
    render_job = os.path.join(render_dir, 'carousel.json')
    json.dump({'date': '2026-11-11', 'jobs': [{
        'slot': '1230', 'lang': 'en', 'date': '2026-11-11', 'show': 'tape-take',
        'video_skip': True, 'publishable': False,
        'signal': {'publishable': False, 'reason': 'no_heat', 'detail': 'no heat'},
        'slides': [],
    }]}, open(render_job, 'w', encoding='utf-8'))
    env = os.environ.copy()
    env['PATH'] = bin_dir + os.pathsep + env.get('PATH', '')
    env['FFMPEG_CALLED'] = marker
    env['VIDEO_SLOTS'] = '1230'
    env['VIDEO_LANGS'] = 'en'
    env.pop('YT_SAMPLES', None)
    proc = subprocess.run(
        ['node', os.path.join(ROOT, 'tools', 'carousel_video.js'), render_job],
        cwd=render_dir, env=env, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert not os.path.exists(marker), proc.stdout + proc.stderr
    skip = json.load(open(planted + '.skip.json', encoding='utf-8'))
    assert skip['publishable'] is False
    assert not os.path.exists(planted + '.mp4')
    assert not os.path.exists(planted + '.vo.json')
    assert not os.path.exists(planted + '-cover.jpg')
    assert not os.path.exists(planted + '-yt-title.txt')
    assert 'nothing publishable' in (proc.stdout + proc.stderr)


def main():
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print('ok', name)


if __name__ == '__main__':
    main()
