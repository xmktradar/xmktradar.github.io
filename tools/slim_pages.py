"""Split the inline dash-data blob out of the homepages, and put it back.

The update pipeline reads the full blob inside index.html (sitedata.load / update_prices).
Served pages stay under 1MB. Prices, account thumbs and full avatars are separate
files so a phone can paint prices without parsing the avatar blob. If that
parse used to fail, every ticker showed 無股價資料.

  python3 tools/slim_pages.py --restore [files...]   # external -> inline full blob
  python3 tools/slim_pages.py --slim [files...]      # inline full blob -> external files

--slim on an already slim page restores first, so it is safe to run twice.
restore(slim(x)) equals x as parsed JSON (key order included).
Default files: index.html, zh/index.html, en/index.html.
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


def peel_avatars(accounts):
    """Pull data-URL avatars out of accounts. Returns (lite accounts, avatars or None).

    avatars[handle] = [key_index, data_url] so the avatar key can be put back
    in its original place. Round-trip must keep dict key order.
    """
    if not isinstance(accounts, dict):
        return accounts, None
    lite, avatars = {}, {}
    for handle, row in accounts.items():
        if (isinstance(row, dict) and isinstance(row.get('avatar'), str)
                and row['avatar'].startswith('data:')):
            keys = list(row)
            index = keys.index('avatar')
            avatars[handle] = [index, row['avatar']]
            lite[handle] = {k: row[k] for k in keys if k != 'avatar'}
        else:
            lite[handle] = row
    return lite, (avatars or None)


def graft_avatars(accounts, avatars):
    if not avatars or not isinstance(accounts, dict):
        return accounts
    out = {}
    for handle, row in accounts.items():
        rec = avatars.get(handle)
        if not rec or not isinstance(row, dict) or 'avatar' in row:
            out[handle] = row
            continue
        index, url = rec
        items = list(row.items())
        items.insert(min(int(index), len(items)), ('avatar', url))
        out[handle] = dict(items)
    return out


def assemble(slim, core, pages, hist, prices=None, avmini=None, avatars=None):
    """Rebuild the full dash object from the pieces split_data() returns.

    prices / avmini / avatars are None when that piece was not split out.
    """
    ext = slim.get('_ext') or {}
    posts = list(slim.get('posts') or [])
    for page in pages or []:
        posts.extend(page)
    values = merge_hist(slim, hist)
    core = core if isinstance(core, dict) else {}
    accounts = graft_avatars(core.get('accounts'), avatars) if 'accounts' in core else None
    rebuilt = {}
    for key in ext.get('order') or []:
        if key == 'posts':
            rebuilt['posts'] = posts
        elif key in values and key not in ('_ext', 'posts'):
            rebuilt[key] = values[key]
        elif key == 'prices' and prices is not None:
            rebuilt['prices'] = prices
        elif key == 'avmini' and avmini is not None:
            rebuilt['avmini'] = avmini
        elif key == 'accounts' and accounts is not None:
            rebuilt['accounts'] = accounts
        elif key in core and key != 'accounts':
            rebuilt[key] = core[key]
    for key, val in core.items():
        if key == 'accounts':
            if 'accounts' not in rebuilt and accounts is not None:
                rebuilt['accounts'] = accounts
        elif key not in rebuilt and key != 'posts':
            rebuilt[key] = val
    if prices is not None and 'prices' not in rebuilt:
        rebuilt['prices'] = prices
    if avmini is not None and 'avmini' not in rebuilt:
        rebuilt['avmini'] = avmini
    for key, val in values.items():
        if key not in rebuilt and key not in ('_ext', 'posts'):
            rebuilt[key] = val
    if 'posts' not in rebuilt and ('posts' in values or ext.get('posts') or pages):
        rebuilt['posts'] = posts
    return rebuilt


def combine(slim):
    """Rebuild the full dash object from a slim blob plus the files it points at."""
    ext = slim['_ext']
    core = {}
    if ext.get('core'):
        core = load_json(url_to_path(ext['core']))
        if not isinstance(core, dict):
            raise SystemExit('core file is not an object: ' + str(ext.get('core')))
    prices = avmini = avatars = None
    if ext.get('prices'):
        prices = load_json(url_to_path(ext['prices']))
        if not isinstance(prices, dict):
            raise SystemExit('prices file is not an object: ' + str(ext.get('prices')))
    if ext.get('avmini'):
        avmini = load_json(url_to_path(ext['avmini']))
        if not isinstance(avmini, dict):
            raise SystemExit('avmini file is not an object: ' + str(ext.get('avmini')))
    if ext.get('avatars'):
        avatars = load_json(url_to_path(ext['avatars']))
        if not isinstance(avatars, dict):
            raise SystemExit('avatars file is not an object: ' + str(ext.get('avatars')))
    hist = None
    values_hist = None
    if ext.get('hist'):
        hist = load_json(url_to_path(ext['hist']))
        if not isinstance(hist, dict):
            raise SystemExit('hist file is not an object: ' + str(ext.get('hist')))
        values_hist = hist
    pages = []
    for url in ext.get('posts') or []:
        page = load_json(url_to_path(url))
        if not isinstance(page, list):
            raise SystemExit('posts file is not a list: ' + url)
        pages.append(page)
    return assemble(slim, core, pages, values_hist, prices, avmini, avatars)


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
    # Prices, thumbs and full avatars used to share one multi-megabyte core file.
    # A phone that failed to parse it showed "無股價資料" for every ticker and often froze.
    # They are separate files so the price series can load on its own.
    prices = data['prices'] if isinstance(data.get('prices'), dict) else None
    avmini = data['avmini'] if isinstance(data.get('avmini'), dict) else None
    accounts_lite, avatars = (None, None)
    if isinstance(data.get('accounts'), dict):
        accounts_lite, avatars = peel_avatars(data['accounts'])
    skip = set()
    if prices is not None:
        skip.add('prices')
    if avmini is not None:
        skip.add('avmini')
    if accounts_lite is not None:
        skip.add('accounts')
    core = {}
    for key in order:
        if key == 'accounts' and accounts_lite is not None:
            core['accounts'] = accounts_lite
        elif key not in INLINE and key != 'posts' and key not in skip:
            core[key] = data[key]
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
    if prices is not None:
        ext['prices'] = '/data/dash/%s-prices.json' % lang
    if avmini is not None:
        ext['avmini'] = '/data/dash/%s-avmini.json' % lang
    if avatars:
        ext['avatars'] = '/data/dash/%s-avatars.json' % lang
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
    return slim, core, older, hist, prices, avmini, avatars


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
    slim, core, pages, hist, prices, avmini, avatars = split_data(original, lang, shell_len(html, match))
    rebuilt = assemble(slim, core, pages, hist, prices, avmini, avatars)
    if rebuilt != original:
        raise SystemExit(rel + ': restore(slim(x)) != x before write')

    folder = os.path.join(ROOT, 'data', 'dash')
    os.makedirs(folder, exist_ok=True)
    keep = set()

    def keep_json(name, obj):
        path_json = os.path.join(folder, name)
        write_json(path_json, obj)
        keep.add(os.path.abspath(path_json))
        return os.path.getsize(path_json)

    core_bytes = keep_json(lang + '-core.json', core) if core else 0
    price_bytes = keep_json(lang + '-prices.json', prices) if prices is not None else 0
    avmini_bytes = keep_json(lang + '-avmini.json', avmini) if avmini is not None else 0
    avatar_bytes = keep_json(lang + '-avatars.json', avatars) if avatars else 0
    for i, page in enumerate(pages):
        keep_json('%s-posts-%d.json' % (lang, i), page)
    hist_bytes = keep_json(lang + '-hist.json', hist) if hist else 0
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
    print('%s: %d bytes (blob %d), posts inline %d/%d, core %d, prices %d, avmini %d, avatars %d, post pages %d, hist %s' % (
        rel, nbytes, blob_bytes, n_inline, n_posts,
        core_bytes, price_bytes, avmini_bytes, avatar_bytes, len(pages),
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
