"""After tools/carousel_video.js: keep only the motion videos that really exist.

tools/carousel.py writes slots.<slot>.video = {lang: url} up front; a video that failed or has
been cleaned away (og/c keeps today and yesterday) is removed here, so Grok bot never gets a
dead link and simply skips Reels. Rewrites social/index.html when something changed.
Usage: python3 tools/carousel_video_post.py   (from the repo root)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sitedata import notice, read_json  # noqa: E402

POSTS = 'data/social-posts.json'


def local_path(url):
    i = url.find('og/c/')
    return url[i:].split('?')[0] if i >= 0 else None


def prune(sp, exists=os.path.isfile):
    """Drop video languages whose file is missing; drop the whole key when none is left. Returns True if changed."""
    changed = False
    for key, sl in (sp.get('slots') or {}).items():
        vid = sl.get('video') if isinstance(sl, dict) else None
        if vid is None:
            continue
        keep = {l: u for l, u in vid.items() if isinstance(u, str) and local_path(u) and exists(local_path(u))}
        if keep != vid:
            changed = True
            gone = sorted(set(vid) - set(keep))
            notice(f'{key} 時段冇動態片：{", ".join(gone)}', 'warning')
            if keep:
                sl['video'] = keep
            else:
                sl.pop('video')
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
