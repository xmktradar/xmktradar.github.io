"""Voiceover for the carousel motion videos.

zh: Mandarin, zh-CN-XiaoxiaoNeural, rate +10%. Lines, voice, rate and the zh pass are unchanged.
en: English, en-US-AndrewNeural (override with VO_VOICE_en). Starts at +10%. If the video would
    run past 29.0s, retries +20% then +30%, then the same rates on a shorter script. Still too
    long: that video is left out of vo.json, so tools/carousel_video.js skips the language
    (no silent / music-only mp4). Never shipped over 29.0s.
ko: no script, so no voiceover.

Reads work/carousel.json (the same slides the pictures use), writes one line per video scene
(8 scenes: hook, reveal, vs, 4 pictures, outro), reads each line with edge-tts (free, no key)
and writes <out>/vo.json: {"<slot>-<lang>": [{"file": ".../vo-0.mp3", "dur": 2.31}, ...]}.
A video gets a voice only when every line of it was read; anything failing leaves that video
out of vo.json, so tools/carousel_video.js skips that language. Lines never say buy, sell,
a price target or a prediction.
Usage: python3 tools/carousel_vo.py work/carousel.json <out dir>   (VO_LANGS=zh,en  VO_VOICE_zh=... VO_VOICE_en=...)
       VO_FAKE=1 makes silent stand-in files of a plausible length (local tests, no network).
Video length uses the same beat sum as tools/carousel_video.js (scene grows to fit the line +0.4s),
plus the opening cover (~0.7s). The cover is not spoken; the 8 lines start after it.
"""
import asyncio
import json
import math
import os
import re
import subprocess
import sys

VOICES = {'zh': 'zh-CN-XiaoxiaoNeural', 'en': 'en-US-AndrewNeural', 'ko': 'ko-KR-SunHiNeural'}
RATE = '+10%'
TIMEOUT = 30
# Keep in sync with BASE / BEAT / COVER_FRAMES in tools/carousel_video.js.
BEAT = 60 / 124
BASE_BEATS = (5, 4, 6, 7, 7, 6, 6, 7)  # hook, reveal, vs, 4 pictures, outro
COVER_FRAMES = 17  # ~0.7s opening cover at 24 fps. The 29s guard includes it.
COVER_S = COVER_FRAMES / 24
MAX_VIDEO_S = 29.0
# English only. Normal script first; faster rates before the shorter script.
EN_TRIES = (
    (False, '+10%'),
    (False, '+20%'),
    (False, '+30%'),
    (True, '+10%'),
    (True, '+20%'),
    (True, '+30%'),
)


def vo_langs():
    return [x for x in os.environ.get('VO_LANGS', 'zh,en').split(',') if x]


def spell(t):
    """Tickers are read letter by letter: SPY -> 'S P Y'."""
    return ' '.join(str(t))


def num(s, d=0):
    m = re.search(r'\d+', str(s or ''))
    return int(m.group()) if m else d


def counts(cover):
    pills = cover.get('pills') or []
    bull = num(next((p['x'] for p in pills if p.get('c') == 'g'), ''))
    bear = num(next((p['x'] for p in pills if p.get('c') == 'r'), ''))
    return num(cover.get('sub')), bull, bear


def first_cards(slide, mark=None):
    out = []
    for sec in slide.get('secs') or []:
        if mark is None or str(sec.get('h', '')).startswith(mark):
            out += [c['t'] for c in sec.get('cards') or []]
    return out


def video_total(durs):
    """Seconds, matching carousel_video.js, including the opening cover.

    No durs: the 48-beat silent cut plus the cover. A voiced scene is
    max(base beats, ceil((line + 0.4s) / beat)) beats. The cover is not a line.
    """
    if not durs:
        return sum(BASE_BEATS) * BEAT + COVER_S
    total = 0.0
    for base, dur in zip(BASE_BEATS, durs):
        total += max(base, math.ceil((float(dur) + 0.4) / BEAT)) * BEAT
    return total + COVER_S


def fits(total):
    return float(total) <= MAX_VIDEO_S


def _count_en(n, one, many):
    return f'{n} {one if n == 1 else many}'


def en_lines(job, short=False):
    """8 English lines, one per scene. Tickers go through spell(). No buy, sell, target or prediction."""
    s = job['slides']
    big = s[0].get('big', '')
    n, bull, bear = counts(s[0])
    top4 = first_cards(s[1])[:4]
    up, down = first_cards(s[2], '🟢')[:1], first_cards(s[2], '🔴')[:1]
    split = first_cards(s[3])[:1]
    if bull > bear:
        verdict = 'Bulls.' if short else 'Bulls ahead!'
    elif bear > bull:
        verdict = 'Bears.' if short else 'Bears ahead!'
    else:
        verdict = 'Tie.' if short else "It's a tie!"
    if short:
        vs = f'{bull} bull, {bear} bear. {verdict}'
        bits = ([f'bull {spell(up[0])}'] if up else []) + ([f'bear {spell(down[0])}'] if down else [])
        joint = ', '.join(bits)
        return [
            'Hottest stock?',
            f'{spell(big)}, {_count_en(n, "account", "accounts")}.',
            vs,
            'What they say.',
            'Top 4 on screen.' if top4 else "Today's ranking.",
            joint if joint else 'The consensus.',
            f'{spell(split[0])}, biggest split.' if split else 'Which side?',
            'thecrowdtape dot com',
        ]
    vs = f'{_count_en(bull, "bull", "bulls")}, {_count_en(bear, "bear", "bears")}. {verdict}'
    bits = ([f'bullish {spell(up[0])}'] if up else []) + ([f'bearish {spell(down[0])}'] if down else [])
    joint = ', '.join(bits)
    return [
        "Today's hottest stock?",
        f'{spell(big)}, {_count_en(n, "account", "accounts")}.',
        vs,
        'What are they saying?',
        'Top 4, on screen.' if top4 else "Today's ranking.",
        joint if joint else 'Where they agree.',
        f'{spell(split[0])}, biggest split.' if split else 'Which side are you on?',
        'Details at thecrowdtape dot com',
    ]


def lines(job):
    """The 8 lines for one video, or None when the language has no script."""
    if job['lang'] == 'zh':
        s = job['slides']
        big = s[0].get('big', '')
        n, bull, bear = counts(s[0])
        top4 = first_cards(s[1])[:4]
        up, down = first_cards(s[2], '🟢')[:1], first_cards(s[2], '🔴')[:1]
        split = first_cards(s[3])[:1]
        # short lines so the zh video fits ~29 s at RATE +10% (2026-10-25: the longer script needed +40%)
        vs = f'{bull} 看好，{bear} 看空，' + ('多方領先！' if bull > bear else '空方領先！' if bear > bull else '打平！')
        joint = '，'.join(([f'看好 {spell(up[0])}'] if up else []) + ([f'看空 {spell(down[0])}'] if down else []))
        return [
            '今天最熱門的美股是？',
            f'{spell(big)}，{n} 個帳號在聊',
            vs,
            '大神怎麼說？',
            '熱度前四，一張圖看完' if top4 else '今天的熱度排行',  # the 4 tickers are on the picture
            joint if joint else '大神們的共識',
            f'{spell(split[0])} 分歧最大！' if split else '你站哪邊？',
            '詳情看 thecrowdtape.com',
        ]
    if job['lang'] == 'en':
        return en_lines(job)
    return None


def duration(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
                       capture_output=True, text=True, timeout=30)
    return float(r.stdout.strip())


def _pct(rate):
    m = re.fullmatch(r'([+-]?\d+)%', str(rate).strip())
    if not m:
        raise ValueError(rate)
    return int(m.group(1))


def fake_seconds(text, rate=RATE):
    """Stand-in length. RATE (+10%) stays len/6.5, the same formula zh fake audio uses."""
    secs = max(1.0, len(text) / 6.5)
    if rate != RATE:
        secs = max(1.0, secs * (1 + _pct(RATE) / 100) / (1 + _pct(rate) / 100))
    return secs


async def speak(text, voice, path, rate=RATE):
    import edge_tts
    for attempt in range(2):
        try:
            await asyncio.wait_for(edge_tts.Communicate(text, voice, rate=rate).save(path), TIMEOUT)
            if os.path.getsize(path) > 1000:
                return True
        except Exception as e:  # network, service change, timeout
            print(f'voiceover: {voice} try {attempt + 1} failed: {e}', file=sys.stderr)
    return False


def fake(text, path, rate=RATE):
    secs = fake_seconds(text, rate)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', f'sine=frequency=330:duration={secs:.2f}',
                    '-af', 'volume=0.2', path], check=True)
    return True


def render_lines(texts, voice, out_dir, key, rate):
    got = []
    for i, text in enumerate(texts):
        path = os.path.join(out_dir, f'vo-{key}-{i}.mp3')
        ok = fake(text, path, rate) if os.environ.get('VO_FAKE') == '1' else asyncio.run(speak(text, voice, path, rate))
        if not ok:
            return None
        got.append({'file': path, 'dur': round(duration(path), 3), 'text': text})
    return got


def fit_en(job, voice, out_dir, key):
    """Speak English, speeding up or shortening until the video would be <= 29.0s. None skips the language."""
    last = None
    for short, rate in EN_TRIES:
        got = render_lines(en_lines(job, short=short), voice, out_dir, key, rate)
        if not got:
            print(f'::warning::{key} 配音失敗，今次唔出呢條片')
            return None
        total = video_total([g['dur'] for g in got])
        last = total
        print(f'voiceover: {key} rate {rate}{" short" if short else ""} video {total:.2f}s')
        if fits(total):
            print(f'voiceover: {key} final {total:.2f}s')
            return got
    bare = video_total(None)
    print(f'::warning::{key} 英文旁白 {last:.2f}s 超過 {MAX_VIDEO_S:.1f} 秒，今次唔出呢條片（bare {bare:.2f}s）')
    return None


def main(job_file, out_dir):
    jobs = json.load(open(job_file, encoding='utf-8'))['jobs']
    want = vo_langs()
    slots = [x for x in os.environ.get('VIDEO_SLOTS', '1230').split(',') if x]
    os.makedirs(out_dir, exist_ok=True)
    result = {}
    for job in jobs:
        if job['lang'] not in want or job['slot'] not in slots:
            continue
        ls = lines(job)
        if not ls:
            continue
        voice = os.environ.get(f"VO_VOICE_{job['lang']}", VOICES[job['lang']])
        key = f"{job['slot']}-{job['lang']}"
        if job['lang'] == 'en':
            got = fit_en(job, voice, out_dir, key)
            if got:
                result[key] = got
            continue
        got = render_lines(ls, voice, out_dir, key, RATE)
        if got:
            result[key] = got
            print(f'voiceover: {key} {sum(g["dur"] for g in got):.1f}s')
        else:
            print(f'::warning::{key} 配音失敗，今次唔出呢條片')
    json.dump(result, open(os.path.join(out_dir, 'vo.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
