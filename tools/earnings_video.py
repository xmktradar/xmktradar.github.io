"""Earnings briefs, step 4: the day's earnings short (Tim, 2026-10-27: one per language a day, made by GitHub, no AI).

Usage: python3 tools/earnings_video.py work/earnings_video.json work/earnings-posts.json
Input from tools/earnings_posts.py: the 4 pictures already drawn by tools/earnings_cards.js and 5 voiceover lines per
language (numbers from the brief only). For each language it writes og/e/<day>-video-<lang>.mp4 (1080x1920, H.264
High yuv420p tv range, AAC 128k 44.1 kHz, +faststart) and og/e/<day>-video-<lang>-cover.jpg:
each picture whole on a blurred copy of itself with a slow push-in, hard cuts on the beat, the generated beat and
sound effects of tools/carousel_audio.py and an edge-tts voiceover (same voices as the daily shorts).
Same rules as the daily shorts: no voiceover, no video; longer than 29.0s after speeding the voice up, no video.
A language that was not made is removed from the "video" entry of the posts file; none made removes the entry.
"""
import json
import math
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import carousel_vo as vo  # noqa: E402

FPS = 24
BEAT = 60 / 124
MIN_BEATS = 5
MAX_S = 29.0
RATES = ('+10%', '+20%', '+30%')
TOOLS = os.path.dirname(os.path.abspath(__file__))


def plan(durs):
    """Scene lengths (whole beats) for the 4 pictures; the 4th picture also carries the outro line."""
    speak = [durs[0], durs[1], durs[2], durs[3] + 0.3 + durs[4]]
    return [max(MIN_BEATS, math.ceil((d + 0.5) / BEAT)) * BEAT for d in speak]


def voice(lines, lang, tmp):
    for rate in RATES:
        got = vo.render_lines(lines, os.environ.get('VO_VOICE_' + lang) or vo.VOICES[lang], tmp, f'earn-{lang}', rate)
        if not got:
            print(f'::warning::財報短片 {lang} 配音失敗，今次唔出')
            return None, None
        scenes = plan([g['dur'] for g in got])
        if sum(scenes) <= MAX_S:
            return got, scenes
        print(f'earnings video {lang}: {sum(scenes):.1f}s at {rate}, trying faster')
    print(f'::warning::財報短片 {lang} 配音後超過 {MAX_S} 秒，今次唔出')
    return None, None


def make(lang, job, tmp):
    imgs = job['images'][lang]
    if not all(os.path.exists(p) for p in imgs):
        print(f'::warning::財報短片 {lang} 冇圖，今次唔出')
        return False
    got, scenes = voice(job['lines'][lang], lang, tmp)
    if not got:
        return False
    total = sum(scenes)
    starts = [sum(scenes[:i]) for i in range(4)]
    events = []
    for s in starts:
        events += [{'at': s + 0.15, 'type': 'whoosh'}, {'at': s + 0.2, 'type': 'pop'}]  # whoosh starts 0.15s early
    events.append({'at': total - 1.6, 'type': 'ding'})
    vos = [{'file': got[i]['file'], 'at': starts[i] + 0.15} for i in range(4)]
    vos.append({'file': got[4]['file'], 'at': starts[3] + 0.15 + got[3]['dur'] + 0.3})
    ev = os.path.join(tmp, f'ev-{lang}.json')
    wav = os.path.join(tmp, f'audio-{lang}.wav')
    json.dump({'total': total, 'bpm': 124, 'drop': 0.0, 'events': events, 'vo': vos}, open(ev, 'w'))
    subprocess.run(['python3', os.path.join(TOOLS, 'carousel_audio.py'), ev, wav], check=True)
    args, parts = ['ffmpeg', '-y', '-loglevel', 'error'], []
    for i, (img, d) in enumerate(zip(imgs, scenes)):
        n = round(d * FPS)
        args += ['-loop', '1', '-framerate', str(FPS), '-t', f'{n / FPS:.4f}', '-i', img]
        parts.append(
            f'[{i}:v]scale=1080:1350,setsar=1,split[a{i}][b{i}];'
            f'[a{i}]scale=1536:1920,crop=1080:1920,boxblur=28:2,eq=brightness=-0.08[bg{i}];'
            f"[b{i}]zoompan=z='1+0.035*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1350:fps={FPS}[fg{i}];"
            f'[bg{i}][fg{i}]overlay=0:285:shortest=1,trim=end_frame={n},setpts=PTS-STARTPTS[v{i}]')
    fc = ';'.join(parts) + ';' + ''.join(f'[v{i}]' for i in range(4)) + 'concat=n=4:v=1:a=0,scale=1080:1920:in_range=pc:out_range=tv,format=yuv420p[v]'
    out = job['out'][lang]
    part = out + '.part.mp4'
    os.makedirs(os.path.dirname(out), exist_ok=True)
    try:
        subprocess.run(args + ['-i', wav, '-filter_complex', fc, '-map', '[v]', '-map', '4:a',
                               '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '24', '-profile:v', 'high', '-level:v', '4.0',
                               '-pix_fmt', 'yuv420p', '-color_range', 'tv', '-colorspace', 'bt709', '-color_primaries', 'bt709',
                               '-color_trc', 'bt709', '-r', str(FPS), '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-shortest',
                               '-movflags', '+faststart', part], check=True, timeout=600)
        os.replace(part, out)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', out, '-frames:v', '1', '-q:v', '3', job['cover'][lang]], check=True)
    except Exception as e:
        for p in (part, out):
            if os.path.exists(p):
                os.remove(p)
        print(f'::warning::財報短片 {lang} 整唔到：{e}')
        return False
    print(f'earnings video {out} {total:.1f}s')
    return True


def main(job_file, posts_file):
    job = json.load(open(job_file, encoding='utf-8'))
    ok = []
    with tempfile.TemporaryDirectory() as tmp:
        for lang in job['out']:
            try:
                if make(lang, job, tmp):
                    ok.append(lang)
            except Exception as e:  # one language failing must not stop the other
                print(f'::warning::財報短片 {lang} 出錯：{e}')
    ep = json.load(open(posts_file, encoding='utf-8'))
    v = ep.get('video')
    if v and v.get('day') == job['date']:
        for k in ('video', 'video_cover'):
            v[k] = {l: u for l, u in (v.get(k) or {}).items() if l in ok}
        if not ok:
            ep.pop('video', None)
        json.dump(ep, open(posts_file, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'earnings video: made {ok or "none"}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
