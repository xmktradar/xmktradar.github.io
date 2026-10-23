"""UTM tags on thecrowdtape.com page URLs inside social-post text.

utm_source is the platform's full name (x, threads, instagram, facebook — not ig or fb).
utm_medium is always social. utm_campaign is the slot:

  posts.*                          daily
  slots.<key>.posts.*              carousel-<key>   (carousel-1230)
  x_trilingual.<premarket|afterclose>   that key
  facebook_cta newsletter line     newsletter (kept; other links in the field use the slot)
  tutorial-posts.json              tutorial
  top5.posts.<lang>.<platform>     top5
  weekly_thread                    weekly_thread, and those posts are X (source x)

tag_url replaces any existing utm_source, utm_medium and utm_campaign, keeps every other
query parameter and the #fragment, and leaves asset URLs (/og/, /assets/, images) alone.
python3 tools/utm.py --apply rewrites both JSON files and refits Threads to 500 code points.
"""
import os
import re
import sys

from sitedata import read_json, write_json

MEDIUM = 'social'
PLATFORM = {'x': 'x', 'instagram': 'instagram', 'threads': 'threads', 'facebook': 'facebook'}
SOURCE_ALIAS = {'ig': 'instagram', 'fb': 'facebook'}
POST_FIELDS = ('x', 'instagram', 'threads', 'facebook', 'facebook_cta')
UTM_KEYS = ('utm_source', 'utm_medium', 'utm_campaign')
URL_RE = re.compile(r'https://thecrowdtape\.com[^\s)\]"]*')
ASSET_EXT = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.xml')
_NEWS_MARKERS = ('newsletter', '電子報', '뉴스레터')
DATA_FILES = ('data/social-posts.json', 'data/tutorial-posts.json')


def canon_source(source):
    """Full platform name. ig and fb become instagram and facebook."""
    source = SOURCE_ALIAS.get(source, source)
    return PLATFORM.get(source, source)


def is_asset_path(path):
    low = (path or '').lower()
    return path.startswith('/og/') or path.startswith('/assets/') or low.endswith(ASSET_EXT)


def split_url(url):
    """Return (path, query, fragment-with-hash) for a thecrowdtape.com URL."""
    rest = url[len('https://thecrowdtape.com'):] if url.startswith('https://thecrowdtape.com') else url
    frag = ''
    if '#' in rest:
        rest, frag = rest.split('#', 1)
        frag = '#' + frag
    if '?' in rest:
        path, query = rest.split('?', 1)
    else:
        path, query = rest, ''
    return path, query, frag


def existing_campaign(url):
    """Current utm_campaign value, or None."""
    _, query, _ = split_url(url)
    for piece in query.split('&'):
        name, _, value = piece.partition('=')
        if name.lower() == 'utm_campaign' and value:
            return value
    return None


def tag_url(url, source, campaign):
    """Set utm_source, utm_medium=social and utm_campaign, replacing any previous trio.

    Other query parameters stay in their original order. The #fragment stays.
    Asset URLs and other hosts are returned unchanged. ig/fb is stored as
    instagram/facebook.
    """
    if not isinstance(url, str) or not url.startswith('https://thecrowdtape.com'):
        return url
    path, query, frag = split_url(url)
    if is_asset_path(path):
        return url
    source = canon_source(source)
    kept = []
    for piece in query.split('&'):
        if not piece:
            continue
        if piece.split('=', 1)[0].lower() in UTM_KEYS:
            continue
        kept.append(piece)
    utm = [
        f'utm_source={source}',
        f'utm_medium={MEDIUM}',
        f'utm_campaign={campaign}',
    ]
    return f'https://thecrowdtape.com{path}?{"&".join(kept + utm)}{frag}'


def _line_prefix(text, start):
    return text[text.rfind('\n', 0, start) + 1:start]


def campaign_for(url, text, start, field, slot_campaign):
    """Slot campaign, except a facebook_cta newsletter line keeps newsletter."""
    if field == 'facebook_cta':
        prefix = _line_prefix(text, start)
        if any(mark in prefix for mark in _NEWS_MARKERS) or existing_campaign(url) == 'newsletter':
            return 'newsletter'
    return slot_campaign


def retag_text(text, source, campaign, field=None):
    """Rewrite page URLs in one post string. Returns (text, number changed)."""
    if not isinstance(text, str) or 'https://thecrowdtape.com' not in text:
        return text, 0
    changed = 0

    def repl(m):
        nonlocal changed
        camp = campaign_for(m.group(0), text, m.start(), field, campaign) if field == 'facebook_cta' else campaign
        new = tag_url(m.group(0), source, camp)
        if new != m.group(0):
            changed += 1
        return new

    return URL_RE.sub(repl, text), changed


def tag_text(text, source, campaign):
    """Replace every thecrowdtape.com page URL in text; other domains stay as they are."""
    return retag_text(text, source, campaign)[0]


def _fit_lang_posts(posts):
    from share import LANGS, fit_threads
    if not isinstance(posts, dict):
        return posts
    for lang, by in posts.items():
        if lang in LANGS and isinstance(by, dict) and isinstance(by.get('threads'), str):
            by['threads'] = fit_threads(by['threads'], lang)
    return posts


def _fit_threads_tree(obj):
    """Refit every threads string under a language key so len() <= 500."""
    from share import LANGS, fit_threads

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in LANGS and isinstance(value, dict) and isinstance(value.get('threads'), str):
                    value['threads'] = fit_threads(value['threads'], key)
                if isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                if isinstance(value, (dict, list)):
                    walk(value)

    walk(obj)


def tag_posts(posts, campaign):
    """Tag platform strings in {lang: {platform: text}}. Mutates posts. Returns counts.

    facebook_cta is not tagged here: its newsletter line is added separately and
    normalize_obj keeps that campaign. Threads captions are refit to 500.
    """
    counts = {p: 0 for p in PLATFORM}
    if not isinstance(posts, dict):
        return counts
    for by in posts.values():
        if not isinstance(by, dict):
            continue
        for plat, src in PLATFORM.items():
            value = by.get(plat)
            if not isinstance(value, str):
                continue
            new, n = retag_text(value, src, campaign, field=plat)
            by[plat] = new
            counts[plat] += n
    _fit_lang_posts(posts)
    return counts


def _empty_counts():
    return {p: 0 for p in PLATFORM}


def _apply_field(container, key, source, campaign, field, counts):
    value = container.get(key) if isinstance(container, dict) else None
    if not isinstance(value, str):
        return
    new, n = retag_text(value, source, campaign, field=field)
    container[key] = new
    counts[canon_source(source)] = counts.get(canon_source(source), 0) + n


def _walk_posts(posts, campaign, counts, force_source=None):
    """Tag x/instagram/threads/facebook/facebook_cta strings. force_source overrides the field."""
    if not isinstance(posts, dict):
        return
    for by in posts.values():
        if not isinstance(by, dict):
            continue
        for field in POST_FIELDS:
            if not isinstance(by.get(field), str):
                continue
            source = force_source or ('facebook' if field == 'facebook_cta' else PLATFORM[field])
            _apply_field(by, field, source, campaign, field, counts)


def _walk_weekly(node, counts):
    """weekly_thread posts are X: source x, campaign weekly_thread."""
    if isinstance(node, list):
        for item in node:
            _walk_weekly(item, counts)
        return
    if not isinstance(node, dict):
        return
    posts = node.get('posts')
    if isinstance(posts, dict):
        for lang, by in posts.items():
            if isinstance(by, str):
                _apply_field(posts, lang, 'x', 'weekly_thread', 'x', counts)
            elif isinstance(by, dict):
                for field, value in by.items():
                    if isinstance(value, str) and (field in POST_FIELDS or field == 'text'):
                        used = field if field in POST_FIELDS else 'x'
                        _apply_field(by, field, 'x', 'weekly_thread', used, counts)
        return
    if isinstance(node.get('text'), str):
        _apply_field(node, 'text', 'x', 'weekly_thread', 'x', counts)
    for key, value in node.items():
        if key == 'text':
            continue
        if isinstance(value, str) and 'https://thecrowdtape.com' in value:
            _apply_field(node, key, 'x', 'weekly_thread', 'x', counts)
        elif isinstance(value, (dict, list)):
            _walk_weekly(value, counts)


def normalize_obj(data, tutorial=False):
    """Rewrite page URLs in a social or tutorial posts object. Mutates data. Returns counts.

    Threads strings are refit afterwards so each one is at most 500 code points.
    """
    counts = _empty_counts()
    if not isinstance(data, dict):
        return counts
    if tutorial:
        _walk_posts(data.get('posts'), 'tutorial', counts)
    else:
        _walk_posts(data.get('posts'), 'daily', counts)
        slots = data.get('slots')
        if isinstance(slots, dict):
            for key, slot in slots.items():
                if isinstance(slot, dict):
                    _walk_posts(slot.get('posts'), f'carousel-{key}', counts)
        tri = data.get('x_trilingual')
        if isinstance(tri, dict):
            for kind, entry in tri.items():
                if isinstance(entry, dict):
                    _apply_field(entry, 'text', 'x', str(kind), 'x', counts)
                elif isinstance(entry, str):
                    _apply_field(tri, kind, 'x', str(kind), 'x', counts)
        top = data.get('top5')
        if isinstance(top, dict):
            posts = top.get('posts') if isinstance(top.get('posts'), dict) else top
            _walk_posts(posts, 'top5', counts)
        if 'weekly_thread' in data:
            node = data['weekly_thread']
            if isinstance(node, str):
                _apply_field(data, 'weekly_thread', 'x', 'weekly_thread', 'x', counts)
            else:
                _walk_weekly(node, counts)
    _fit_threads_tree(data)
    return counts


def normalize_file(path):
    """Load JSON at path, normalize page URLs, write it back. Returns per-platform counts.

    A file whose name contains 'tutorial' uses the tutorial campaign. Anything else
    is a social-posts file (daily, carousel-<key>, premarket, afterclose, …).
    """
    data = read_json(path)
    counts = normalize_obj(data, tutorial='tutorial' in os.path.basename(str(path)))
    if isinstance(data, dict):
        write_json(path, data, indent=1)
    return counts


def normalize_all(paths=None):
    """Normalize data/social-posts.json and data/tutorial-posts.json. Returns summed counts."""
    counts = _empty_counts()
    for path in paths or DATA_FILES:
        for key, n in normalize_file(path).items():
            counts[key] = counts.get(key, 0) + n
    return counts


def tag_file(path, campaign):
    """Load JSON, tag d['posts'] and each slot's posts with one campaign, write back.

    Structural campaigns (carousel-<key>, newsletter, premarket, …) are applied by
    normalize_file. This helper remains for a single campaign on posts and slots.
    """
    data = read_json(path)
    counts = _empty_counts()
    if not isinstance(data, dict):
        return counts
    if isinstance(data.get('posts'), dict):
        for key, n in tag_posts(data['posts'], campaign).items():
            counts[key] += n
    for slot in (data.get('slots') or {}).values():
        if isinstance(slot, dict) and isinstance(slot.get('posts'), dict):
            for key, n in tag_posts(slot['posts'], campaign).items():
                counts[key] += n
    write_json(path, data, indent=1)
    return counts


def apply():
    """Rewrite both post JSON files onto the social UTM scheme and print counts."""
    counts = normalize_all()
    for name in ('x', 'instagram', 'threads', 'facebook'):
        print(f'{name}: {counts.get(name, 0)}')
    return counts


if __name__ == '__main__':
    if '--apply' in sys.argv:
        apply()
