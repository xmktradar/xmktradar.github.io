"""UTM tags on thecrowdtape.com page URLs inside social-post text.

utm_source is the platform's full name (x, threads, instagram, facebook — not ig or fb).
utm_medium is always social. utm_campaign is the slot (intraday uses the slot name, e.g. intraday_open):

  posts.*                          daily
  slots.<key>.posts.*              carousel-<key>   (carousel-1230)
  x_trilingual.<premarket|afterclose>   that key
  facebook_cta newsletter line     newsletter (kept; other links in the field use the slot)
  tutorial-posts.json              tutorial
  top5.posts.<lang>.<platform>     top5
  weekly_thread                    weekly_thread, and those posts are X (source x).
                                   langs.<lang> is a list of X posts, same campaign.
  hot_stock / discussion           that slot. threads and facebook, including first_comment.
  weekend                          weekend. posts[].langs.<lang>.{threads,facebook,first_comment}
  atomic_posts                     atomic. text and first_comment use source threads.
  three_lines.{x,threads,facebook} three_lines. Each language is {text, url}.
                                   Instagram has no URL.
  why_posts[]                      why. threads.{zh,en,ko} and optional x.en.
                                   No Instagram.
  intraday.slots.<key>             that slot (intraday_open, …). x.en is source x;
                                   threads.<lang> is source threads. No Facebook.

tag_url replaces any existing utm_source, utm_medium and utm_campaign, keeps every other
query parameter and the #fragment, and leaves asset URLs (/og/, /assets/, images) alone.
python3 tools/utm.py --apply rewrites both JSON files and refits Threads to 500 code points.
Instagram captions are passed through share.sanitize_instagram (no URLs, one bio line, 3–5 hashtags).
python3 tools/ig_boost.py --apply also sanitizes data/macro-week.json Instagram captions.
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
_NEWS_MARKERS = ('newsletter', '電子報')
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
            th = node.get('threads')
            if isinstance(th, dict):
                for lang, entry in th.items():
                    if lang not in LANGS:
                        continue
                    if isinstance(entry, dict) and isinstance(entry.get('text'), str):
                        entry['text'] = fit_threads(entry['text'], lang)
                    elif isinstance(entry, str):
                        th[lang] = fit_threads(entry, lang)
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


def _walk_intraday(node, counts):
    """intraday.slots.<key>: x.en is X (campaign = slot name); threads.<lang> is Threads."""
    slots = node.get('slots') if isinstance(node, dict) else None
    if not isinstance(slots, dict):
        return
    from share import LANGS, fit_threads
    for key, slot in slots.items():
        if not isinstance(slot, dict):
            continue
        campaign = str(key)
        x = slot.get('x')
        if isinstance(x, dict):
            for lang, entry in x.items():
                if isinstance(entry, dict):
                    _apply_field(entry, 'text', 'x', campaign, 'x', counts)
                    if isinstance(entry.get('url'), str):
                        entry['url'] = tag_url(entry['url'], 'x', campaign)
                elif isinstance(entry, str):
                    _apply_field(x, lang, 'x', campaign, 'x', counts)
        th = slot.get('threads')
        if isinstance(th, dict):
            for lang, entry in th.items():
                if isinstance(entry, dict):
                    _apply_field(entry, 'text', 'threads', campaign, 'threads', counts)
                    if isinstance(entry.get('url'), str):
                        entry['url'] = tag_url(entry['url'], 'threads', campaign)
                    if lang in LANGS and isinstance(entry.get('text'), str):
                        entry['text'] = fit_threads(entry['text'], lang)
                elif isinstance(entry, str):
                    _apply_field(th, lang, 'threads', campaign, 'threads', counts)
                    if lang in LANGS:
                        th[lang] = fit_threads(th[lang], lang)


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


def _tag_platform_block(by, campaign, counts):
    """Tag threads/facebook/x/instagram and first_comment on one language object.

    first_comment may be a string (source threads) or {threads, facebook, ...}.
    A per-platform first_comment uses that platform as utm_source.
    """
    if not isinstance(by, dict):
        return
    for field, source in PLATFORM.items():
        if isinstance(by.get(field), str):
            _apply_field(by, field, source, campaign, field, counts)
    fc = by.get('first_comment')
    if isinstance(fc, dict):
        for field, source in PLATFORM.items():
            if isinstance(fc.get(field), str):
                _apply_field(fc, field, source, campaign, field, counts)
    elif isinstance(fc, str):
        _apply_field(by, 'first_comment', 'threads', campaign, 'threads', counts)


def _walk_lang_map(posts, campaign, counts):
    """Tag {lang: {threads, facebook, first_comment, ...}}."""
    if not isinstance(posts, dict):
        return
    for by in posts.values():
        if isinstance(by, dict):
            _tag_platform_block(by, campaign, counts)


def _tag_string_list(items, counts, campaign='weekly_thread', source='x'):
    if not isinstance(items, list):
        return
    for i, item in enumerate(items):
        if isinstance(item, str):
            new, n = retag_text(item, source, campaign, field=source)
            items[i] = new
            counts[canon_source(source)] = counts.get(canon_source(source), 0) + n
        elif isinstance(item, (dict, list)):
            _walk_weekly(item, counts)


def _walk_weekly(node, counts):
    """weekly_thread posts are X: source x, campaign weekly_thread.

    The Friday thread is langs.<lang>: [str, ...]. Older files used posts.<lang>.
    Both shapes are tagged. A list of post strings is tagged in place.
    """
    if isinstance(node, list):
        _tag_string_list(node, counts)
        return
    if not isinstance(node, dict):
        return
    langs = node.get('langs')
    if isinstance(langs, dict):
        for lang, posts in langs.items():
            if isinstance(posts, str):
                _apply_field(langs, lang, 'x', 'weekly_thread', 'x', counts)
            elif isinstance(posts, list):
                _tag_string_list(posts, counts)
    posts = node.get('posts')
    if isinstance(posts, dict):
        for lang, by in posts.items():
            if isinstance(by, str):
                _apply_field(posts, lang, 'x', 'weekly_thread', 'x', counts)
            elif isinstance(by, list):
                _tag_string_list(by, counts)
            elif isinstance(by, dict):
                for field, value in by.items():
                    if isinstance(value, str) and (field in POST_FIELDS or field == 'text'):
                        used = field if field in POST_FIELDS else 'x'
                        _apply_field(by, field, 'x', 'weekly_thread', used, counts)
        return
    if isinstance(langs, dict):
        return
    if isinstance(node.get('text'), str):
        _apply_field(node, 'text', 'x', 'weekly_thread', 'x', counts)
    for key, value in node.items():
        if key in ('text', 'langs', 'posts'):
            continue
        if isinstance(value, str) and 'https://thecrowdtape.com' in value:
            _apply_field(node, key, 'x', 'weekly_thread', 'x', counts)
        elif isinstance(value, (dict, list)):
            _walk_weekly(value, counts)


def _walk_named_slot(node, campaign, counts):
    if isinstance(node, dict):
        _walk_lang_map(node.get('posts'), campaign, counts)


def _walk_weekend(node, counts):
    posts = node.get('posts') if isinstance(node, dict) else None
    if not isinstance(posts, list):
        return
    for item in posts:
        if not isinstance(item, dict):
            continue
        _walk_lang_map(item.get('langs'), 'weekend', counts)


def _walk_text_platforms(node, campaign, counts, platforms):
    """Tag {platform: {lang: {text, url}}} . Threads captions are refit to 500."""
    if not isinstance(node, dict):
        return
    from share import LANGS, fit_threads
    for plat in platforms:
        block = node.get(plat)
        if not isinstance(block, dict):
            continue
        source = PLATFORM.get(plat, plat)
        for lang, entry in list(block.items()):
            if isinstance(entry, dict):
                _apply_field(entry, 'text', source, campaign, plat, counts)
                if isinstance(entry.get('url'), str):
                    entry['url'] = tag_url(entry['url'], source, campaign)
                if plat == 'threads' and lang in LANGS and isinstance(entry.get('text'), str):
                    entry['text'] = fit_threads(entry['text'], lang)
            elif isinstance(entry, str):
                _apply_field(block, lang, source, campaign, plat, counts)
                if plat == 'threads' and lang in LANGS:
                    block[lang] = fit_threads(block[lang], lang)


def _walk_three_lines(node, counts):
    """three_lines x/threads/facebook. Instagram is sanitized elsewhere and has no URL."""
    _walk_text_platforms(node, 'three_lines', counts, ('x', 'threads', 'facebook'))


def _walk_why(items, counts):
    """why_posts: Threads-first, optional English X. Campaign is why."""
    if not isinstance(items, list):
        return
    for item in items:
        if isinstance(item, dict):
            _walk_text_platforms(item, 'why', counts, ('threads', 'x'))


def _walk_atomic(items, counts):
    """atomic_posts text and first_comment. One body, so the source is threads."""
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        for field in ('text', 'hook', 'first_comment', 'hashtags'):
            value = item.get(field)
            if isinstance(value, str) and 'https://thecrowdtape.com' in value:
                _apply_field(item, field, 'threads', 'atomic', 'threads', counts)
            elif field == 'first_comment' and isinstance(value, dict):
                for plat, source in PLATFORM.items():
                    if isinstance(value.get(plat), str):
                        _apply_field(value, plat, source, 'atomic', plat, counts)


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
            _walk_lang_map(posts, 'top5', counts)
        if 'weekly_thread' in data:
            node = data['weekly_thread']
            if isinstance(node, str):
                _apply_field(data, 'weekly_thread', 'x', 'weekly_thread', 'x', counts)
            else:
                _walk_weekly(node, counts)
        for slot, campaign in (('hot_stock', 'hot_stock'), ('discussion', 'discussion')):
            if slot in data:
                _walk_named_slot(data.get(slot), campaign, counts)
        if isinstance(data.get('weekend'), dict):
            _walk_weekend(data['weekend'], counts)
        if isinstance(data.get('atomic_posts'), list):
            _walk_atomic(data['atomic_posts'], counts)
        if isinstance(data.get('three_lines'), dict):
            _walk_three_lines(data['three_lines'], counts)
        if isinstance(data.get('why_posts'), list):
            _walk_why(data['why_posts'], counts)
        if isinstance(data.get('intraday'), dict):
            _walk_intraday(data['intraday'], counts)
    _fit_threads_tree(data)
    from share import sanitize_instagram_tree, strip_dup_handles_tree
    strip_dup_handles_tree(data)
    sanitize_instagram_tree(data)
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
