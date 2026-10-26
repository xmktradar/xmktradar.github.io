"""After tools/carousel_video.js: keep only voiced motion videos and their cover posters.

tools/carousel.py writes slots.<slot>.video = {lang: url} and slots.<slot>.video_cover = {lang: url}
up front. A language is kept only when the mp4 exists, a sidecar og/c/<day>-<slot>-<lang>.vo.json
exists with vo:true, and (when ffprobe is available) the file has an audio stream and duration
<= 29.0s. Silent / music-only / over-long / missing-marker files are dropped so Grok bot never
gets a dead or voiceless link. Drop the whole key when none is left. Rewrites social/index.html
when something changed.
Usage: python3 tools/carousel_video_post.py   (from the repo root)
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sitedata import notice, read_json  # noqa: E402

POSTS = 'data/social-posts.json'
MAX_VIDEO_S = 29.0

# field, warning when a language is dropped. Drop the whole key when none is left.
MEDIA = (
    ('video', '{} 時段冇動態片：{}'),
    ('video_cover', '{} 時段冇封面：{}'),
)


def local_path(url):
    i = url.find('og/c/')
    return url[i:].split('?')[0] if i >= 0 else None


def marker_path(mp4):
    return mp4[:-4] + '.vo.json' if mp4.endswith('.mp4') else mp4 + '.vo.json'


def ffprobe_media(path):
    """Audio stream and duration, or None if ffprobe is not installed.

    A probe that ran and failed (bad file) returns audio=False so the language is dropped.
    Tests inject a replacement via prune(..., probe=...).
    """
    try:
        r = subprocess.run(
            ['ffprobe', '-v', 'error', '-print_format', 'json', '-show_streams', '-show_format', path],
            capture_output=True, text=True, timeout=30,
        )
    except FileNotFoundError:
        return None
    except (OSError, subprocess.TimeoutExpired):
        return {'audio': False, 'duration': None}
    if r.returncode != 0:
        return {'audio': False, 'duration': None}
    try:
        data = json.loads(r.stdout or '{}')
    except json.JSONDecodeError:
        return {'audio': False, 'duration': None}
    audio = any(s.get('codec_type') == 'audio' for s in (data.get('streams') or []))
    try:
        duration = float((data.get('format') or {}).get('duration'))
    except (TypeError, ValueError):
        duration = None
    return {'audio': audio, 'duration': duration}


def load_marker(mp4, exists=os.path.isfile):
    path = marker_path(mp4)
    if not exists(path):
        return None
    try:
        data = json.load(open(path, encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def voiced_ok(mp4, exists=os.path.isfile, probe=None):
    """True when mp4 exists, sidecar says vo:true, and ffprobe (if any) agrees."""
    if not mp4 or not exists(mp4):
        return False
    mark = load_marker(mp4, exists)
    if not mark or mark.get('vo') is not True:
        return False
    info = (ffprobe_media if probe is None else probe)(mp4)
    if info is None:
        return True
    if not info.get('audio'):
        return False
    try:
        dur = float(info['duration'])
    except (TypeError, ValueError, KeyError):
        return False
    return dur <= MAX_VIDEO_S


def prune(sp, exists=os.path.isfile, probe=None):
    """Drop video and video_cover languages that are not a voiced <=29s mp4. Returns True if changed.

    probe(path) -> {'audio': bool, 'duration': float|None} | None
    Injected in tests. Default is ffprobe_media. None from the probe means ffprobe is
    unavailable: trust the VO marker.
    """
    changed = False
    for key, sl in (sp.get('slots') or {}).items():
        if not isinstance(sl, dict):
            continue
        vid = sl.get('video')
        keep_video = {}
        if isinstance(vid, dict):
            for lang, url in vid.items():
                path = local_path(url) if isinstance(url, str) else None
                if path and voiced_ok(path, exists, probe):
                    keep_video[lang] = url
            if keep_video != vid:
                changed = True
                gone = sorted(set(vid) - set(keep_video))
                if gone:
                    notice(MEDIA[0][1].format(key, ', '.join(gone)), 'warning')
                if keep_video:
                    sl['video'] = keep_video
                else:
                    sl.pop('video')
        cov = sl.get('video_cover')
        if isinstance(cov, dict):
            keep_cov = {}
            for lang, url in cov.items():
                path = local_path(url) if isinstance(url, str) else None
                if lang in keep_video and isinstance(url, str) and path and exists(path):
                    keep_cov[lang] = url
            if keep_cov != cov:
                changed = True
                gone = sorted(set(cov) - set(keep_cov))
                if gone:
                    notice(MEDIA[1][1].format(key, ', '.join(gone)), 'warning')
                if keep_cov:
                    sl['video_cover'] = keep_cov
                else:
                    sl.pop('video_cover')
    return changed


def main():
    if os.path.isdir('og/c'):  # half-written files from a run that was cut off
        for f in os.listdir('og/c'):
            if f.endswith('.part.mp4'):
                os.remove(os.path.join('og/c', f))
    sp = read_json(POSTS)
    if not sp or not prune(sp):
        return
    from utm import normalize_file
    from sitedata import write_json
    write_json(POSTS, sp, indent=1)
    normalize_file(POSTS)
    from carousel import write_page
    os.makedirs('social', exist_ok=True)
    write_page(read_json(POSTS), 'social/index.html')


if __name__ == '__main__':
    main()
