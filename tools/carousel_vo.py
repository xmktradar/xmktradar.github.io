"""Voiceover for the carousel motion videos (Tim, 2026-10-24: Mandarin on the zh video).

Reads work/carousel.json (the same slides the pictures use), writes one line per video scene
(8 scenes: hook, reveal, vs, 4 pictures, outro), reads each line with edge-tts (free, no key)
and writes <out>/vo.json: {"<slot>-<lang>": [{"file": ".../vo-0.mp3", "dur": 2.31}, ...]}.
A video gets a voice only when every line of it was read; anything failing leaves that video
out of vo.json, so tools/carousel_video.js makes it without a voice. Lines never say buy, sell,
a price target or a prediction.
Usage: python3 tools/carousel_vo.py work/carousel.json <out dir>   (VO_LANGS=zh, VO_VOICE_zh=...)
       VO_FAKE=1 makes silent stand-in files of a plausible length (local tests, no network).
"""
import asyncio
import json
import os
import re
import subprocess
import sys

VOICES = {'zh': 'zh-CN-XiaoxiaoNeural', 'en': 'en-US-AvaNeural', 'ko': 'ko-KR-SunHiNeural'}
RATE = '+10%'
TIMEOUT = 30


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


def lines(job):
    """The 8 lines for one video, or None when the language has no script."""
    if job['lang'] != 'zh':
        return None
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


def duration(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
                       capture_output=True, text=True, timeout=30)
    return float(r.stdout.strip())


async def speak(text, voice, path):
    import edge_tts
    for attempt in range(2):
        try:
            await asyncio.wait_for(edge_tts.Communicate(text, voice, rate=RATE).save(path), TIMEOUT)
            if os.path.getsize(path) > 1000:
                return True
        except Exception as e:  # network, service change, timeout
            print(f'voiceover: {voice} try {attempt + 1} failed: {e}', file=sys.stderr)
    return False


def fake(text, path):
    secs = max(1.0, len(text) / 6.5)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', f'sine=frequency=330:duration={secs:.2f}',
                    '-af', 'volume=0.2', path], check=True)
    return True


def main(job_file, out_dir):
    jobs = json.load(open(job_file, encoding='utf-8'))['jobs']
    want = [x for x in os.environ.get('VO_LANGS', 'zh').split(',') if x]
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
        got = []
        for i, text in enumerate(ls):
            path = os.path.join(out_dir, f'vo-{key}-{i}.mp3')
            ok = fake(text, path) if os.environ.get('VO_FAKE') == '1' else asyncio.run(speak(text, voice, path))
            if not ok:
                got = None
                break
            got.append({'file': path, 'dur': round(duration(path), 3), 'text': text})
        if got:
            result[key] = got
            print(f'voiceover: {key} {sum(g["dur"] for g in got):.1f}s')
        else:
            print(f'::warning::{key} 配音失敗，今次出冇配音版')
    json.dump(result, open(os.path.join(out_dir, 'vo.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
