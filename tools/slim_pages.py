"""Split the inline dash-data blob out of the homepages, and put it back.

The update pipeline reads the full blob inside index.html (sitedata.load / update_prices).
Served pages stay under 1MB: the first screen is inline, everything else is in data/dash/.

  python3 tools/slim_pages.py --restore [files...]   # external -> inline full blob
  python3 tools/slim_pages.py --slim [files...]      # inline full blob -> external files

--slim on an already slim page restores first, so it is safe to run twice.
restore(slim(x)) equals x as parsed JSON (key order included).
Default files: index.html, zh/index.html, en/index.html, ko/index.html.
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOCK = re.compile(r'(<script type="application/json" id="dash-data">)(.*?)(</script>)', re.S)
# Whole values kept inline so the first screen can render before the fetch.
# posts is split separately (newest prefix inline, older pages external).
# Other languages' copies (summaries_en, ...) stay in the core file.
INLINE = {
    'meta', 'overrides', 'tracked', 'highlights', 'macro', 'days', 'quotes',
    'summaries', 'briefings', 'cons_hist', 'vs_copy', 'tv_symbols',
}
# Newest N stay inline (lists are oldest-first); the rest go to lang-hist.json.
HIST_KEEP = {'daily': 2, 'weekly': 2, 'monthly': 2}
BRIEF_KEEP = 3
PAGES = [
    ('index.html', 'master'),
    ('zh/index.html', 'zh'),
    ('en/index.html', 'en'),
    ('ko/index.html', 'ko'),
]
MAX_HTML = 990_000  # served homepage must be < 1MB
INLINE_TARGET = 600_000  # soft budget for the served homepage; inline posts are trimmed to stay under it, MAX_HTML stays the hard limit
POST_CHUNK = 400_000


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


def html_escape(blob):
    return blob.replace('</', '<\\/')


def read_html(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def parse_blob(html, rel='page'):
    m = BLOCK.search(html)
    if not m:
        raise SystemExit(rel + ': no inline <script type="application/json" id="dash-data"> block; '
                         'the build needs the data inline (see tools/check_contract.py)')
    data = json.loads(m.group(2).replace('<\\/', '</'))
    return m, data


def write_blob(path, html, match, data):
    blob = html_escape(dumps(data))
    out = html[:match.start(2)] + blob + html[match.end(2):]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(out)
    return len(out.encode()), len(blob.encode())


def url_to_path(url):
    rel = url.split('?', 1)[0]
    if not rel.startswith('/'):
        raise SystemExit('external path must start with /: ' + url)
    rel = rel.lstrip('/')
    full = os.path.normpath(os.path.join(ROOT, rel))
    if full != ROOT and not full.startswith(ROOT + os.sep):
        raise SystemExit('external path escapes the repo: ' + url)
    return full


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')
    os.replace(tmp, path)


def is_slim(data):
    return isinstance(data, dict) and isinstance(data.get('_ext'), dict)


def merge_hist(obj, hist):
    """Copy of obj with older summaries/briefings from hist prepended. Key order of obj is kept."""
    out = dict(obj)
    hist = hist or {}
    hist_summ = hist.get('summaries') or {}
    if hist_summ:
        src = out['summaries'] if isinstance(out.get('summaries'), dict) else {}
        summaries = {}
        for kind, val in src.items():
            if kind in hist_summ:
                summaries[kind] = list(hist_summ[kind] or []) + list(val or [])
            else:
                summaries[kind] = val
        for kind, val in hist_summ.items():
            if kind not in summaries:
                summaries[kind] = list(val or []) + list(src.get(kind) or [])
        out['summaries'] = summaries
    if 'briefings' in hist:
        out['briefings'] = list(hist['briefings'] or []) + list(out.get('briefings') or [])
    return out


def combine(slim):
    """Rebuild the full dash object from a slim blob plus the files it points at."""
    ext = slim['_ext']
    core = load_json(url_to_path(ext['core'])) if ext.get('core') else {}
    if not isinstance(core, dict):
        raise SystemExit('core file is not an object: ' + str(ext.get('core')))
    values = slim
    if ext.get('hist'):
        hist = load_json(url_to_path(ext['hist']))
        if not isinstance(hist, dict):
            raise SystemExit('hist file is not an object: ' + str(ext.get('hist')))
        values = merge_hist(slim, hist)
    posts = list(values.get('posts') or [])
    for url in ext.get('posts') or []:
        page = load_json(url_to_path(url))
        if not isinstance(page, list):
            raise SystemExit('posts file is not a list: ' + url)
        posts.extend(page)
    order = ext.get('order')
    out = {}
    if order:
        for key in order:
            if key == 'posts':
                out['posts'] = posts
            elif key in values and key not in ('_ext', 'posts'):
                out[key] = values[key]
            elif key in core:
                out[key] = core[key]
    for key, val in core.items():
        if key not in out and key != 'posts':
            out[key] = val
    for key, val in values.items():
        if key not in out and key not in ('_ext', 'posts'):
            out[key] = val
    if 'posts' not in out and ('posts' in values or ext.get('posts')):
        out['posts'] = posts
    return out


def full_data(html):
    _, data = parse_blob(html)
    if is_slim(data):
        return combine(data)
    return data


def post_day(post):
    return (post.get('time_hkt') or post.get('time_utc') or '')[:10]


def prefix_for_days(posts, ndays):
    """Newest-first list: index where the next day group after `ndays` starts."""
    days = []
    for i, post in enumerate(posts):
        day = post_day(post)
        if not days or days[-1] != day:
            if len(days) == ndays:
                return i
            days.append(day)
    return len(posts)


def escaped_size(obj):
    return len(html_escape(dumps(obj)).encode())


def choose_inline_count(posts, base, order, lang, shell_len):
    """Newest posts that fit: 2 days, else 1 day, else as many newest as fit."""
    def ext_for(n_pages):
        ext = {
            'posts': ['/data/dash/%s-posts-%d.json' % (lang, i) for i in range(n_pages)],
            'order': order,
        }
        # core path is present whenever we call this (prices/accounts are external)
        ext['core'] = '/data/dash/%s-core.json' % lang
        return ext

    def fits(n, n_pages):
        obj = dict(base)
        obj['posts'] = posts[:n]
        obj['_ext'] = ext_for(n_pages)
        return shell_len + escaped_size(obj) <= INLINE_TARGET

    # Page count barely changes the blob; reserve a few slots, then recheck.
    guess_pages = max(1, (len(posts) // 200) + 1)
    two = prefix_for_days(posts, 2)
    one = prefix_for_days(posts, 1)
    if two and fits(two, guess_pages):
        n = two
    elif one and fits(one, guess_pages):
        n = one
    else:
        lo, hi, n = 0, len(posts), 0
        while lo <= hi:
            mid = (lo + hi) // 2
            if fits(mid, guess_pages):
                n = mid
                lo = mid + 1
            else:
                hi = mid - 1
    # Exact page count, then shrink if the real _ext is larger than the guess.
    while True:
        pages = chunk_posts(posts[n:])
        if fits(n, len(pages)) or n == 0:
            return n
        n -= 1


def chunk_posts(posts):
    pages, cur, size = [], [], 2
    for post in posts:
        raw = len(dumps(post).encode()) + 1
        if cur and size + raw > POST_CHUNK:
            pages.append(cur)
            cur, size = [], 2
        cur.append(post)
        size += raw
    if cur:
        pages.append(cur)
    return pages


def split_data(data, lang, shell_len):
    posts = list(data.get('posts') or [])
    order = list(data.keys())
    base = {k: data[k] for k in order if k in INLINE}
    core = {k: data[k] for k in order if k not in INLINE and k != 'posts'}
    hist = {}
    if isinstance(base.get('summaries'), dict):
        summaries = {}
        hist_summ = {}
        for kind, val in base['summaries'].items():
            keep = HIST_KEEP.get(kind)
            if keep is not None and isinstance(val, list) and len(val) > keep:
                hist_summ[kind] = val[:-keep]
                summaries[kind] = val[-keep:]
            else:
                summaries[kind] = val
        base['summaries'] = summaries
        if hist_summ:
            hist['summaries'] = hist_summ
    if isinstance(base.get('briefings'), list) and len(base['briefings']) > BRIEF_KEEP:
        hist['briefings'] = base['briefings'][:-BRIEF_KEEP]
        base['briefings'] = base['briefings'][-BRIEF_KEEP:]
    n = choose_inline_count(posts, base, order, lang, shell_len) if posts else 0
    older = chunk_posts(posts[n:])
    ext = {'order': order, 'posts': ['/data/dash/%s-posts-%d.json' % (lang, i) for i in range(len(older))]}
    if core:
        ext['core'] = '/data/dash/%s-core.json' % lang
    if hist:
        ext['hist'] = '/data/dash/%s-hist.json' % lang
    slim = dict(base)
    if 'posts' in data:
        # Keep posts in its original position when it was an inline-eligible neighbour.
        built = {}
        placed = False
        for key in order:
            if key == 'posts':
                built['posts'] = posts[:n]
                placed = True
            elif key in slim:
                built[key] = slim[key]
        if not placed and 'posts' in data:
            built['posts'] = posts[:n]
        slim = built
    elif 'posts' in data:
        slim['posts'] = posts[:n]
    slim['_ext'] = ext
    return slim, core, older, hist


def shell_len(html, match):
    return len(html[:match.start(2)].encode()) + len(html[match.end(2):].encode())


def clean_stale(lang, keep):
    folder = os.path.join(ROOT, 'data', 'dash')
    if not os.path.isdir(folder):
        return
    for path in glob.glob(os.path.join(folder, lang + '-*')):
        if os.path.abspath(path) not in keep:
            os.remove(path)


def restore_file(rel):
    path = os.path.join(ROOT, rel)
    html = read_html(path)
    match, data = parse_blob(html, rel)
    if not is_slim(data):
        print(rel + ': already full')
        return
    full = combine(data)
    nbytes, _ = write_blob(path, html, match, full)
    print('%s: restored inline (%d bytes)' % (rel, nbytes))


def slim_file(rel, lang):
    path = os.path.join(ROOT, rel)
    html = read_html(path)
    match, raw = parse_blob(html, rel)
    original = combine(raw) if is_slim(raw) else raw
    # Re-parse the original through dumps/loads so the compare matches what we write.
    original = json.loads(dumps(original))
    slim, core, pages, hist = split_data(original, lang, shell_len(html, match))
    # Round-trip in memory before touching disk: rebuild from the same pieces.
    trial = dict(slim)
    # combine() reads files; check the pieces directly here.
    posts = list(slim.get('posts') or [])
    for page in pages:
        posts.extend(page)
    ext = slim['_ext']
    values = merge_hist(slim, hist)
    rebuilt = {}
    for key in ext['order']:
        if key == 'posts':
            rebuilt['posts'] = posts
        elif key in values and key not in ('_ext', 'posts'):
            rebuilt[key] = values[key]
        elif key in core:
            rebuilt[key] = core[key]
    for key, val in core.items():
        if key not in rebuilt:
            rebuilt[key] = val
    for key, val in values.items():
        if key not in rebuilt and key not in ('_ext', 'posts'):
            rebuilt[key] = val
    if rebuilt != original:
        raise SystemExit(rel + ': restore(slim(x)) != x before write')

    folder = os.path.join(ROOT, 'data', 'dash')
    os.makedirs(folder, exist_ok=True)
    keep = set()
    if core:
        core_path = os.path.join(folder, lang + '-core.json')
        write_json(core_path, core)
        keep.add(os.path.abspath(core_path))
    for i, page in enumerate(pages):
        page_path = os.path.join(folder, '%s-posts-%d.json' % (lang, i))
        write_json(page_path, page)
        keep.add(os.path.abspath(page_path))
    hist_bytes = 0
    if hist:
        hist_path = os.path.join(folder, lang + '-hist.json')
        write_json(hist_path, hist)
        keep.add(os.path.abspath(hist_path))
        hist_bytes = os.path.getsize(hist_path)
    clean_stale(lang, keep)

    # The on-disk blob must match `slim` after a read, including key order.
    html = read_html(path)
    match, _ = parse_blob(html)
    nbytes, blob_bytes = write_blob(path, html, match, slim)
    html2 = read_html(path)
    _, slim2 = parse_blob(html2)
    back = combine(slim2)
    if back != original:
        raise SystemExit(rel + ': restore(slim(x)) != x after write')
    if nbytes >= 1_000_000:
        raise SystemExit('%s is still %d bytes (limit 1MB)' % (rel, nbytes))
    n_posts = len(original.get('posts') or [])
    n_inline = len(slim.get('posts') or [])
    print('%s: %d bytes (blob %d), posts inline %d/%d, core %s, post pages %d, hist %s' % (
        rel, nbytes, blob_bytes, n_inline, n_posts,
        'yes' if core else 'no', len(pages),
        str(hist_bytes) if hist else 'no'))
    return nbytes


def targets(args):
    wanted = args or [rel for rel, _ in PAGES]
    by_rel = dict(PAGES)
    out = []
    for rel in wanted:
        rel = rel.replace('\\', '/').lstrip('./')
        lang = by_rel.get(rel)
        if not lang:
            base = os.path.basename(os.path.dirname(rel)) if rel.endswith('index.html') and os.path.dirname(rel) else 'master'
            lang = base or 'master'
        out.append((rel, lang))
    return out


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ('--slim', '--restore'):
        raise SystemExit('usage: python3 tools/slim_pages.py --slim|--restore [index.html ...]')
    mode, files = args[0], targets(args[1:])
    os.chdir(ROOT)
    if mode == '--restore':
        for rel, _ in files:
            restore_file(rel)
        return
    sizes = []
    for rel, lang in files:
        sizes.append((rel, slim_file(rel, lang)))
    print('round-trip OK')
    for rel, n in sizes:
        print('  %s %d' % (rel, n))


if __name__ == '__main__':
    main()
