"""Instagram reach upgrades: CTA last slide, 3–5 hashtags, ig_reel.

Apply in place without rebuilding other content:

  python3 tools/ig_boost.py --apply

Renders og/cta/ig-cta-{zh,en,ko}.jpg (1080×1350) if missing or --render, then
sanitizes every Instagram caption, appends the CTA JPEG as the last IG image
on carousels, and writes top-level `ig_reel` on data/social-posts.json and
data/macro-week.json.

Top5 and macro-week Instagram captions get the generator key-point line
prepended when it is not already line 1. Existing lines stay, in order.
The sanitizer never moves a body line. It prepends a supplied key line only
when line 1 has neither a $TICKER nor a digit.

Macro-week ig_reel.date_kst is the Asia/Seoul date of the Saturday post
(20:00 HKT on `date`, which is 21:00 KST, same calendar day). `date` is that
Saturday even on a preview, when it is still in the future. `to` is the data
window end and is not the posting day.

video_path is the convention relative path only when that file exists in the
repo at apply time; otherwise null. Never invented. video_expected_path is
always the convention string.
"""
import os
import subprocess
import sys

import date_kst
from sitedata import read_json, write_json
from share import (LANGS, SITE, IG_CTA_COPY, IG_CTA_REL, IG_BIO, ig_cta_url,
                   install_ig_headline, sanitize_instagram, sanitize_instagram_tree,
                   top5_ig_key_line)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOCIAL = 'data/social-posts.json'
MACRO = 'data/macro-week.json'
CTA_STEM = 'ig-cta-'
REEL_DIR = 'assets/reels'


def cta_rel(lang):
    lang = lang if lang in LANGS else 'en'
    return IG_CTA_REL.format(lang=lang)


def is_cta_url(url, lang=None):
    if not isinstance(url, str):
        return False
    low = url.replace('\\', '/')
    if lang:
        return f'{CTA_STEM}{lang}.jpg' in low
    return any(f'{CTA_STEM}{lg}.jpg' in low for lg in LANGS)


def with_cta(urls, lang):
    """Copy of an IG image URL list with the language CTA JPEG last. Idempotent."""
    if not isinstance(urls, list):
        return urls
    keep = [u for u in urls if isinstance(u, str) and not is_cta_url(u, lang)]
    if not keep:
        return list(urls)
    return keep + [ig_cta_url(lang)]


def _lang_from_urls(urls):
    blob = ' '.join(u for u in urls if isinstance(u, str))
    for lang in LANGS:
        if f'-{lang}-' in blob or f'-{lang}.' in blob or f'/{lang}/' in blob:
            return lang
    return None


def _looks_fb(urls):
    return any(isinstance(u, str) and '-fb.' in u for u in urls)


def append_cta_lists(obj, lang=None, parent=None):
    """Append the CTA JPEG to IG multi-image lists. Leaves images_fb and single-share images alone."""
    if isinstance(obj, dict):
        this_lang = obj.get('lang') if obj.get('lang') in LANGS else lang
        if 'images_fb' in obj:
            pass
        for key, value in list(obj.items()):
            next_lang = key if key in LANGS else this_lang
            if key == 'images_fb':
                continue
            if key in ('images', 'ig_images') and isinstance(value, list):
                if value and all(isinstance(x, str) for x in value) and not _looks_fb(value):
                    lg = next_lang or _lang_from_urls(value) or 'en'
                    obj[key] = with_cta(value, lg)
                continue
            if key == 'images' and isinstance(value, dict):
                # Per-language lists (slots) vs {portrait, square} (top5) vs string map (macro).
                if any(k in value for k in ('portrait', 'square')):
                    continue
                if any(isinstance(value.get(lg), list) for lg in LANGS):
                    for lg in LANGS:
                        if isinstance(value.get(lg), list) and not _looks_fb(value[lg]):
                            value[lg] = with_cta(value[lg], lg)
                    continue
            if isinstance(value, (dict, list)):
                append_cta_lists(value, next_lang, key)
    elif isinstance(obj, list):
        for value in obj:
            if isinstance(value, (dict, list)):
                append_cta_lists(value, lang, parent)
    return obj


def ensure_macro_ig_images(data):
    """Macro-week `images` stay single URLs for Facebook; `ig_images` is the IG carousel."""
    images = data.get('images') if isinstance(data, dict) else None
    if not isinstance(images, dict):
        return data
    ig = data.get('ig_images')
    if not isinstance(ig, dict):
        ig = {}
        data['ig_images'] = ig
    for lang in LANGS:
        src = images.get(lang)
        if isinstance(src, list):
            ig[lang] = with_cta(src, lang)
        elif isinstance(src, str) and src:
            ig[lang] = with_cta([src], lang)
    return data


def reel_expected_path(date_kst, slot):
    """Convention relative path: assets/reels/<date_kst>-<slot>.mp4"""
    day = str(date_kst or '').strip()
    name = str(slot or '').strip() or 'daily'
    if not day:
        return ''
    return f'{REEL_DIR}/{day}-{name}.mp4'


def video_path_if_exists(expected, root=None):
    """Return expected if that file exists under root, else None. Never invents a path."""
    if not expected:
        return None
    base = root or ROOT
    full = os.path.join(base, expected.replace('/', os.sep))
    return expected if os.path.isfile(full) else None


def captions_from_posts(posts):
    """{zh,en,ko} Instagram captions from a posts map. Missing langs get the CTA copy."""
    out = {}
    for lang in LANGS:
        text = None
        by = (posts or {}).get(lang) if isinstance(posts, dict) else None
        if isinstance(by, dict):
            text = by.get('instagram')
            if isinstance(text, dict):
                text = text.get('text')
        elif isinstance(by, str):
            text = by
        if not isinstance(text, str) or not text.strip():
            text = IG_CTA_COPY[lang]
        out[lang] = sanitize_instagram(text, lang)
    return out


def build_ig_reel(date_kst, slot, captions=None, root=None, posts=None):
    """Build the ig_reel object. video_path is set only when the mp4 exists on disk."""
    expected = reel_expected_path(date_kst, slot)
    cap = captions if isinstance(captions, dict) else captions_from_posts(posts)
    cleaned = {}
    for lang in LANGS:
        raw = cap.get(lang) if isinstance(cap, dict) else None
        if not isinstance(raw, str) or not raw.strip():
            raw = IG_CTA_COPY[lang]
        cleaned[lang] = sanitize_instagram(raw, lang)
    return {
        'date_kst': str(date_kst or ''),
        'slot': str(slot or ''),
        'video_path': video_path_if_exists(expected, root=root),
        'video_expected_path': expected,
        'caption': cleaned,
    }


def refresh_top5_ig_headlines(data):
    """Prepend the top5 key-point line. List rows stay where they are."""
    top5 = data.get('top5') if isinstance(data, dict) else None
    if not isinstance(top5, dict):
        return data
    posts = top5.get('posts')
    if not isinstance(posts, dict):
        return data
    bulls, bears = top5.get('bull') or [], top5.get('bear') or []
    for lang in LANGS:
        entry = posts.get(lang)
        if not isinstance(entry, dict) or not isinstance(entry.get('instagram'), str):
            continue
        key = top5_ig_key_line(lang, bulls, bears)
        entry['instagram'] = install_ig_headline(entry['instagram'], key)
    return data


def refresh_macro_ig_headlines(data):
    """Prepend the macro key-point line built from themes/top. Body stays."""
    if not isinstance(data, dict):
        return data
    from macro_week import macro_ig_key_line
    posts = data.get('posts')
    if not isinstance(posts, dict):
        return data
    for lang in LANGS:
        entry = posts.get(lang)
        if not isinstance(entry, dict) or not isinstance(entry.get('instagram'), str):
            continue
        entry['instagram'] = install_ig_headline(entry['instagram'], macro_ig_key_line(lang, data))
    return data


def macro_reel_date_kst(data):
    """KST date the Saturday macro post is intended to go out.

    Uses `date` (the posting Saturday, including a preview's next Saturday)
    at 20:00 HKT. Does not copy `to`, which can be an earlier window end.
    """
    if not isinstance(data, dict):
        return ''
    day = date_kst.as_day(data.get('date'))
    if day:
        return date_kst.macro_post_date_kst(day)
    return date_kst.as_day(data.get('date_kst'))


def _social_reel_captions(data):
    posts = data.get('posts') if isinstance(data, dict) else None
    cap = captions_from_posts(posts)
    # Prefer a caption that already names a ticker/number: daily posts do.
    return cap


def _macro_reel_captions(data):
    posts = data.get('posts') if isinstance(data, dict) else None
    return captions_from_posts(posts)


def ensure_weekend_ig(data):
    weekend = data.get('weekend') if isinstance(data, dict) else None
    posts = weekend.get('posts') if isinstance(weekend, dict) else None
    if not isinstance(posts, list):
        return
    for item in posts:
        langs = item.get('langs') if isinstance(item, dict) else None
        if not isinstance(langs, dict):
            continue
        for lang, entry in langs.items():
            if lang not in LANGS or not isinstance(entry, dict):
                continue
            if not isinstance(entry.get('instagram'), str):
                src = entry.get('threads') or entry.get('facebook') or ''
                if isinstance(src, str) and src.strip():
                    entry['instagram'] = sanitize_instagram(src, lang)
            else:
                entry['instagram'] = sanitize_instagram(entry['instagram'], lang)
            hl = entry.get('has_link')
            if isinstance(hl, dict):
                hl['instagram'] = False
            elif hl is None:
                entry['has_link'] = {'instagram': False}


def apply_social_obj(data, root=None):
    """Mutate a social-posts object: sanitize IG, CTA last on IG lists, ig_reel."""
    if not isinstance(data, dict):
        return data
    refresh_top5_ig_headlines(data)
    sanitize_instagram_tree(data)
    ensure_weekend_ig(data)
    append_cta_lists(data)
    # ig_threads_daily copies 1230 images; re-copy after CTA so they stay in sync.
    slot = (data.get('slots') or {}).get('1230') if isinstance(data.get('slots'), dict) else None
    daily = data.get('ig_threads_daily')
    if isinstance(slot, dict) and isinstance(daily, dict):
        imgs = slot.get('images') or {}
        for lang in LANGS:
            row = daily.get(lang)
            if not isinstance(row, dict):
                continue
            ip = row.get('image_post')
            if isinstance(ip, dict) and isinstance(imgs.get(lang), list):
                ip['images'] = list(imgs[lang])
    reel_day = data.get('date_kst') or data.get('date') or ''
    data['ig_reel'] = build_ig_reel(reel_day, 'daily', captions=_social_reel_captions(data), root=root)
    sanitize_instagram_tree(data.get('ig_reel'))
    return data


def apply_macro_obj(data, root=None):
    """Mutate a macro-week object: sanitize IG, ig_images carousel, ig_reel."""
    if not isinstance(data, dict):
        return data
    refresh_macro_ig_headlines(data)
    sanitize_instagram_tree(data)
    ensure_macro_ig_images(data)
    day = macro_reel_date_kst(data)
    if day:
        date_kst._place(data, 'date_kst', day, after='date' if 'date' in data else None)
    data['ig_reel'] = build_ig_reel(day, 'macro-week', captions=_macro_reel_captions(data), root=root)
    sanitize_instagram_tree(data.get('ig_reel'))
    return data


def apply_social_file(path, root=None):
    data = read_json(path, {})
    if not isinstance(data, dict):
        return data
    apply_social_obj(data, root=root)
    write_json(path, data, indent=1)
    return data


def apply_macro_file(path, root=None):
    data = read_json(path, {})
    if not isinstance(data, dict):
        return data
    apply_macro_obj(data, root=root)
    write_json(path, data, indent=1)
    return data


def cta_files_exist(root=None):
    base = root or ROOT
    return all(os.path.isfile(os.path.join(base, cta_rel(lang))) for lang in LANGS)


def render_cta(root=None):
    """Draw og/cta/ig-cta-{zh,en,ko}.jpg via Playwright. Returns the three relative paths."""
    base = root or ROOT
    env = os.environ.copy()
    env.setdefault('NODE_PATH', '/tmp/pw/node_modules')
    env.setdefault('CHROME_PATH', '/usr/bin/google-chrome')
    script = os.path.join(base, 'tools', 'ig_cta.js')
    subprocess.run(['node', script], cwd=base, env=env, check=True)
    missing = [cta_rel(lang) for lang in LANGS if not os.path.isfile(os.path.join(base, cta_rel(lang)))]
    if missing:
        raise FileNotFoundError('CTA render did not write ' + ', '.join(missing))
    return [cta_rel(lang) for lang in LANGS]


def apply(root=None, render=True):
    """Render CTA JPEGs, then upgrade both JSON files in place."""
    base = root or ROOT
    social = os.path.join(base, SOCIAL)
    macro = os.path.join(base, MACRO)
    if render or not cta_files_exist(base):
        render_cta(base)
    if os.path.isfile(social):
        apply_social_file(social, root=base)
    if os.path.isfile(macro):
        apply_macro_file(macro, root=base)
    return {'cta': [f'{SITE}{cta_rel(lang)}' for lang in LANGS],
            'social': social, 'macro': macro}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--apply' not in argv and '--render' not in argv:
        print('usage: python3 tools/ig_boost.py --apply [--render]')
        return 2
    os.chdir(ROOT)
    if '--apply' in argv:
        apply(ROOT, render=True)
        print('ig_boost: CTA slides, IG captions, ig_reel applied')
        return 0
    render_cta(ROOT)
    print('ig_boost: CTA images rendered')
    return 0


if __name__ == '__main__':
    sys.exit(main())
