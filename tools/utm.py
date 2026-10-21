"""UTM tags on thecrowdtape.com page URLs inside social-post text.

utm_source is the platform (x / ig / threads / fb), utm_medium is always post, utm_campaign is
daily / carousel / tutorial. Asset URLs and other domains are left alone. Idempotent: a URL that
already has utm_source is not tagged again. python3 tools/utm.py --apply rewrites the current
JSON files and prints how many URLs were tagged per platform.
"""
import re
import sys

from sitedata import read_json, write_json

SITE = 'https://thecrowdtape.com/'
PLATFORM = {'x': 'x', 'instagram': 'ig', 'threads': 'threads', 'facebook': 'fb'}
URL_RE = re.compile(r'https://thecrowdtape\.com[^\s)\]"]*')
ASSET_EXT = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.xml')


def tag_url(url, source, campaign):
    """Add utm_source, utm_medium=post, utm_campaign before any #fragment."""
    if not url.startswith('https://thecrowdtape.com'):
        return url
    body = url[len('https://thecrowdtape.com'):]
    frag = ''
    if '#' in body:
        body, frag = body.split('#', 1)
        frag = '#' + frag
    if '?' in body:
        path, query = body.split('?', 1)
    else:
        path, query = body, ''
    low = path.lower()
    if path.startswith('/og/') or path.startswith('/assets/') or low.endswith(ASSET_EXT):
        return url
    if re.search(r'(?:^|&)utm_source=', query):
        return url
    utm = f'utm_source={source}&utm_medium=post&utm_campaign={campaign}'
    query = f'{query}&{utm}' if query else utm
    return f'https://thecrowdtape.com{path}?{query}{frag}'


def tag_text(text, source, campaign):
    """Replace every thecrowdtape.com URL in text; other domains stay as they are."""
    return URL_RE.sub(lambda m: tag_url(m.group(0), source, campaign), text)


def tag_posts(posts, campaign):
    """Tag platform strings in {lang: {platform: text|dict}}. Mutates posts. Returns counts."""
    counts = {p: 0 for p in PLATFORM}
    if not isinstance(posts, dict):
        return counts
    for by in posts.values():
        if not isinstance(by, dict):
            continue
        for plat, src in PLATFORM.items():
            v = by.get(plat)
            if not isinstance(v, str):
                continue
            n = 0

            def repl(m, src=src):
                nonlocal n
                u = m.group(0)
                nu = tag_url(u, src, campaign)
                if nu != u:
                    n += 1
                return nu

            by[plat] = URL_RE.sub(repl, v)
            counts[plat] += n
    # UTM makes every URL longer. Threads counts that full length and stops at 500.
    from share import LANGS, fit_threads
    for lang, by in posts.items():
        if lang in LANGS and isinstance(by, dict) and isinstance(by.get('threads'), str):
            by['threads'] = fit_threads(by['threads'], lang)
    return counts


def tag_file(path, campaign):
    """Load JSON, tag d['posts'] and each d['slots'][k]['posts'], write back."""
    d = read_json(path)
    counts = {p: 0 for p in PLATFORM}
    if not isinstance(d, dict):
        return counts
    if isinstance(d.get('posts'), dict):
        for k, n in tag_posts(d['posts'], campaign).items():
            counts[k] += n
    for sl in (d.get('slots') or {}).values():
        if isinstance(sl, dict) and isinstance(sl.get('posts'), dict):
            for k, n in tag_posts(sl['posts'], campaign).items():
                counts[k] += n
    write_json(path, d, indent=1)
    return counts


def apply():
    """Tag data/social-posts.json (daily + carousel slots) and data/tutorial-posts.json."""
    counts = {p: 0 for p in PLATFORM}
    d = read_json('data/social-posts.json')
    if isinstance(d, dict):
        if isinstance(d.get('posts'), dict):
            for k, n in tag_posts(d['posts'], 'daily').items():
                counts[k] += n
        for sl in (d.get('slots') or {}).values():
            if isinstance(sl, dict) and isinstance(sl.get('posts'), dict):
                for k, n in tag_posts(sl['posts'], 'carousel').items():
                    counts[k] += n
        write_json('data/social-posts.json', d, indent=1)
    for k, n in tag_file('data/tutorial-posts.json', 'tutorial').items():
        counts[k] += n
    for p, n in counts.items():
        print(f'{p}: {n}')
    return counts


if __name__ == '__main__':
    if '--apply' in sys.argv:
        apply()
