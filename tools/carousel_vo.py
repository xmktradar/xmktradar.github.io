"""Voiceover for the carousel motion videos (v6 Bloomberg / terminal).

zh: Mandarin, zh-CN-XiaoxiaoNeural, rate +10%. Lines, voice, rate and the zh pass are unchanged.
en: English, en-US-AndrewNeural (override with VO_VOICE_en). Three beats per name
    (heat, one TA fact, tracked-account lean) plus hook and CTA. Starts at +10%. If the
    cut would run past the cap (40s weekday / Saturday single, 75s Week Tape hot-list),
    retries +20% then +30%, then a shorter script. Still too long: that video is left out
    of vo.json (no silent / music-only mp4). Weekday target 30–40s. No site-URL closer.

Reads work/carousel.json (the same slides the pictures use), writes one line per video scene
(5 scenes: open, split, m1, m2, cta), reads each line with edge-tts (free, no key)
and writes <out>/vo.json: {"<slot>-<lang>": [{"file": ".../vo-0.mp3", "dur": 2.31}, ...]}.
A video gets a voice only when every line of it was read; anything failing leaves that video
out of vo.json, so tools/carousel_video.js skips that language. Lines never say buy, sell,
a price target or a prediction.
Usage: python3 tools/carousel_vo.py work/carousel.json <out dir>   (VO_LANGS=en  VO_VOICE_en=...; override VO_LANGS=zh,en)
       VO_FAKE=1 makes silent stand-in files of a plausible length (local tests, no network).
Tim 2026-11-04: default VO_LANGS=en (daily Shorts en-only). EN lines come from tools/video_signal.py.
Video length uses the same beat sum as tools/carousel_video.js (scene grows to fit the line +0.4s).
Cover is merged into open (COVER_FRAMES = 0); the 5 lines start at each scene's +0.15s lead-in.
"""
import asyncio
import json
import math
import os
import re
import subprocess
import sys

import video_signal

VOICES = {'zh': 'zh-CN-XiaoxiaoNeural', 'en': 'en-US-AndrewNeural'}
BACKUP_VOICES = {'zh': ['zh-CN-XiaoyiNeural'], 'en': ['en-US-BrianNeural', 'en-US-ChristopherNeural']}
RATE = '+10%'
TIMEOUT = 30
# Keep in sync with BASE / BEAT / COVER_FRAMES in tools/carousel_video.js.
BEAT = 60 / 124
BASE_BEATS = (6, 20, 13, 20, 14)  # open, split, m1, m2, cta — weekday-with-TA floor ~35s @124bpm
COVER_FRAMES = 0  # cover merged into open; 40s guard still uses COVER_S for parity
COVER_S = COVER_FRAMES / 24
MIN_VIDEO_S = 30.0
MAX_VIDEO_S = 40.0
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
    return [x for x in os.environ.get('VO_LANGS', 'en').split(',') if x]


def spell(t):
    """Tickers are read letter by letter: SPY -> 'S P Y'."""
    return ' '.join(str(t))


def num(s, d=0):
    m = re.search(r'\d+', str(s or ''))
    return int(m.group()) if m else d


def counts(cover):
    """Accounts, bull, bear. Pills, or duel `bar` / `nb`/`nr` / a versus subtitle."""
    return video_signal.counts(cover or {})


def first_cards(slide, mark=None):
    out = []
    for sec in slide.get('secs') or []:
        if mark is None or str(sec.get('h', '')).startswith(mark):
            out += [c['t'] for c in sec.get('cards') or []]
    return out


def video_total(durs, bases=None):
    """Seconds, matching carousel_video.js.

    No durs: the silent cut (sum of bases, default BASE_BEATS) plus COVER_S (0 in v6).
    A voiced scene is max(base beats, ceil((line + 0.4s) / beat)) beats.
    Five durations and no bases use BASE_BEATS. Four use the weekday no-TA floor.
    """
    if not durs:
        beats = bases if bases is not None else BASE_BEATS
        return sum(beats) * BEAT + COVER_S
    if bases is None:
        if len(durs) == len(BASE_BEATS):
            bases = BASE_BEATS
        elif len(durs) == 4:
            bases = (video_signal.WEEKDAY_NOTA['hook'], video_signal.WEEKDAY_NOTA['heat'],
                     video_signal.WEEKDAY_NOTA['views'], video_signal.WEEKDAY_NOTA['cta'])
        else:
            bases = tuple(8 for _ in durs)
    total = 0.0
    for i, dur in enumerate(durs):
        base = bases[i] if i < len(bases) else 8
        total += max(base, math.ceil((float(dur) + 0.4) / BEAT)) * BEAT
    return total + COVER_S


def fits(total):
    return float(total) <= MAX_VIDEO_S


def _count_en(n, one, many):
    return f'{n} {one if n == 1 else many}'


def _read_json(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def load_hero_quote(big=''):
    """Real EN highlight quote for VO. Never invent; None → generic tape line (no rock)."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data = None
    for rel in ('data/super-grok-writeups.json', 'work/writeups.json'):
        data = _read_json(os.path.join(root, rel))
        if data:
            break
    if not data:
        return None
    en = data.get('en') or data
    cards = ((en.get('highlights') or {}).get('cards')) or []
    want = str(big or '').upper()
    ordered = [c for c in cards if want and want in [str(t).upper() for t in (c.get('tickers') or [])]] + list(cards)

    def parse_point(pt):
        m = re.match(r'^@([\w.]+)\s*[:：]\s*([\s\S]+)$', str(pt or '').strip())
        if not m:
            return None
        return {'handle': '@' + m.group(1), 'text': m.group(2).strip()}

    def ok(card, parsed, tick):
        body = re.sub(r'\s+', ' ', parsed['text']).strip()
        if not body:
            return None
        # VO must not trip advice filter: rewrite common "buy-and-hold" phrasing.
        vo_text = re.sub(r'\bbuy-and-hold\b', 'hold', body, flags=re.I)
        vo_text = re.sub(r'\b(buy|sell|target|prediction|forecast)s?\b', '', vo_text, flags=re.I)
        vo_text = re.sub(r'\s{2,}', ' ', vo_text).strip(' ,;.-')
        if not vo_text:
            vo_text = 'their read is on the tape today'
        tickers = card.get('tickers') or ['']
        return {
            'handle': parsed['handle'],
            'text': vo_text,
            'ticker': tick or want or tickers[0],
            'stance': 'bear' if re.search(r'bear|看空|淡', str(card.get('tone') or ''), re.I) else (
                'bull' if re.search(r'bull|看好|多', str(card.get('tone') or ''), re.I) else ''),
        }

    if want:
        for card in ordered:
            for pt in (card.get('points') or []):
                if not re.search(r'\b' + re.escape(want) + r'\b', str(pt), re.I):
                    continue
                parsed = parse_point(pt)
                if not parsed:
                    continue
                got = ok(card, parsed, want)
                if got:
                    return got
    if want:
        for card in ordered:
            tags = [str(x).upper() for x in (card.get('tickers') or [])]
            if want not in tags:
                continue
            for pt in (card.get('points') or []):
                parsed = parse_point(pt)
                if not parsed:
                    continue
                got = ok(card, parsed, want)
                if got:
                    return got
        return None  # never invent; don't steal another ticker's quote
    for card in cards:
        for pt in (card.get('points') or []):
            parsed = parse_point(pt)
            if not parsed:
                continue
            tickers = card.get('tickers') or ['']
            got = ok(card, parsed, tickers[0])
            if got:
                return got
    return None


def en_lines(job, short=False):
    """English lines for one cut. Hook, heat, optional TA, tracked lean, CTA.

    Tickers go through spell(). Counts come from the cover (`pills` or `bar`) or
    from `job['beats']` when the selector already built them. No buy, sell, target,
    prediction, or site-URL closer. Does not read `px/` by itself.
    """
    return video_signal.en_lines(job, short=short)


def lines(job):
    """The 5 lines for one video, or None when the language has no script."""
    if job['lang'] == 'zh':
        s = job['slides']
        big = s[0].get('big', '')
        n, bull, bear = counts(s[0])
        top4 = first_cards(s[1])[:4]
        up, down = first_cards(s[2], '🟢')[:1], first_cards(s[2], '🔴')[:1]
        split = first_cards(s[3])[:1]
        vs = f'{bull} 看好，{bear} 看空，' + ('多方領先。' if bull > bear else '空方領先。' if bear > bull else '打平。')
        joint = '，'.join(([f'看好 {spell(up[0])}'] if up else []) + ([f'看空 {spell(down[0])}'] if down else []))
        m2 = joint if joint else (f'{spell(split[0])} 分歧最大。' if split else '你站哪邊？')
        top = '、'.join(spell(t) for t in top4)
        return [
            f'{spell(big)}，{n} 個帳號在聊',
            vs,
            f'熱度前四：{top}' if top4 else '今天的熱度排行',
            m2,
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
    for attempt in range(4):
        if attempt:
            await asyncio.sleep(2 ** attempt)
        try:
            await asyncio.wait_for(edge_tts.Communicate(text, voice, rate=rate).save(path), TIMEOUT)
            if os.path.getsize(path) > 1000:
                return True
        except Exception as e:
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
    """Speak English until the cut is inside the slot cap. None skips the language.

    Weekday and a Saturday single stay at 40s. A Week Tape hot-list may run to 75s.
    The short pass shrinks middle beats; hook and CTA bases stay.
    """
    cap = video_signal.video_cap(job)
    last = None
    for short, rate in EN_TRIES:
        texts = en_lines(job, short=short)
        if not texts:
            print(f'::warning::{key} 無旁白腳本，今次唔出呢條片')
            return None
        got = render_lines(texts, voice, out_dir, key, rate)
        if not got:
            print(f'::warning::{key} 配音失敗，今次唔出呢條片')
            return None
        bases = video_signal.bases_for(job, short=short)
        for clip, base in zip(got, bases):
            clip['base'] = base
        total = video_total([g['dur'] for g in got], bases)
        last = total
        print(f'voiceover: {key} rate {rate}{" short" if short else ""} video {total:.2f}s')
        if total <= cap:
            print(f'voiceover: {key} final {total:.2f}s')
            return got
    bare = video_total(None, video_signal.bases_for(job, short=False))
    print(f'::warning::{key} 英文旁白 {last:.2f}s 超過 {cap:.1f} 秒，今次唔出呢條片（bare {bare:.2f}s）')
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
        signal = job.get('signal') if isinstance(job.get('signal'), dict) else {}
        if job.get('video_skip') or job.get('skip') or job.get('publishable') is False or signal.get('publishable') is False:
            print(f"::notice::{job.get('slot')} {job.get('lang')} skipped before voiceover")
            continue
        key = f"{job['slot']}-{job['lang']}"
        texts = lines(job)
        if not texts:
            print(f'::warning::{key} 無旁白腳本，今次唔出呢條片')
            continue
        voice = os.environ.get(f"VO_VOICE_{job['lang']}") or VOICES.get(job['lang'])
        if not voice:
            print(f'::warning::{key} 無聲線，今次唔出呢條片')
            continue
        if job['lang'] == 'en':
            got = fit_en(job, voice, out_dir, key)
        else:
            got = render_lines(texts, voice, out_dir, key, RATE)
            if got:
                total = video_total([g['dur'] for g in got])
                print(f'voiceover: {key} rate {RATE} video {total:.2f}s')
                # zh is emitted once at +10%; carousel_video.js skips if voiced total > 40s.
        if got:
            result[key] = got
            print(f'voiceover: {key} {len(got)} lines')
        else:
            print(f'::warning::{key} 配音失敗，今次唔出呢條片')
    path = os.path.join(out_dir, 'vo.json')
    json.dump(result, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'voiceover wrote {path} ({len(result)} videos)')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
