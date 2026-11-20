"""Give every mentioned X account a photo.

The page draws a letter when a handle has no data-URI avatar. Tracked accounts
already have one. This fills avmini for the rest, from the public fxtwitter
profile. A handle with no photo is remembered for seven days. Never fails the
site update: a miss stays a letter and the next run continues the rest.
"""
import base64
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

from sitedata import load, notice, save

MISS = 'data/avatar-miss.json'
UA = 'TheCrowdTape/1.0 (+https://thecrowdtape.com/)'
HANDLE = re.compile(r'@([A-Za-z0-9_]{1,15})')
RETRY_DAYS = 7
WORKERS = 6


def mentioned(d):
    """Handles that can show on the page: post authors and @names in the text."""
    out = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ('handle', 'reposted_by', 'screen_name') and isinstance(v, str) and v.strip():
                    out.add(v.lstrip('@'))
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str):
            out.update(HANDLE.findall(o))

    for key in ('posts', 'summaries', 'briefings', 'highlights'):
        walk(d.get(key))
    return {h for h in out if re.fullmatch(r'[A-Za-z0-9_]{1,15}', h)}


def have_photo(d):
    got = set()
    for h, v in (d.get('accounts') or {}).items():
        if isinstance(v, dict) and str(v.get('avatar') or '').startswith('data:image/'):
            got.add(h.lower())
    for h, v in (d.get('avmini') or {}).items():
        if str(v or '').startswith('data:image/'):
            got.add(h.lower())
    return got


def load_miss():
    try:
        raw = json.load(open(MISS, encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def fresh_miss(miss):
    cut = (date.today() - timedelta(days=RETRY_DAYS)).isoformat()
    return {h for h, day in miss.items() if isinstance(day, str) and day >= cut}


def get(url, timeout=20, accept='application/json'):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': accept})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.headers.get('Content-Type', ''), r.read()


def photo_of(handle):
    """Return a data URI, or None when this account has no usable photo."""
    body = None
    for attempt in range(3):
        try:
            status, _, body = get('https://api.fxtwitter.com/' + urllib.parse.quote(handle))
            if status == 200:
                break
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < 2:
                time.sleep(1)
                continue
            raise
    if not body:
        return None
    user = json.loads(body).get('user') or {}
    url = user.get('avatar_url') or ''
    if not url.startswith('https://'):
        return None
    status, ctype, img = get(url, accept='image/*')
    if status != 200 or len(img) < 80 or len(img) > 80_000:
        return None
    if 'png' in ctype or url.lower().split('?', 1)[0].endswith('.png'):
        kind = 'png'
    elif img[:3] == b'\xff\xd8\xff':
        kind = 'jpeg'
    elif img[:8] == b'\x89PNG\r\n\x1a\n':
        kind = 'png'
    else:
        return None
    return 'data:image/%s;base64,%s' % (kind, base64.b64encode(img).decode())


def one(handle):
    try:
        return handle, photo_of(handle), None
    except urllib.error.HTTPError as e:
        if e.code in (429, 503):
            time.sleep(2)
        return handle, None, e.code
    except Exception as e:
        return handle, None, type(e).__name__


def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    d = load()
    got = have_photo(d)
    miss = load_miss()
    skip = fresh_miss(miss)
    todo = sorted({h for h in mentioned(d) if h.lower() not in got and h.lower() not in skip}, key=str.lower)
    budget = float(os.environ.get('FILL_AVATAR_SECONDS', '480'))
    start = time.monotonic()
    filled = missed = retried = 0
    av = d.setdefault('avmini', {})
    notice('X photos to fetch: %d (already have %d, skipping %d recent misses)' % (len(todo), len(got), len(skip)))
    if not todo:
        return
    pool = ThreadPoolExecutor(max_workers=WORKERS)
    futs = [pool.submit(one, h) for h in todo]
    try:
        for n, fut in enumerate(as_completed(futs), 1):
            if time.monotonic() - start > budget:
                for f in futs:
                    f.cancel()
                notice('X photo budget reached; the rest wait for the next update', 'warning')
                break
            if fut.cancelled():
                continue
            handle, uri, err = fut.result()
            key = handle.lower()
            if uri:
                av[key] = uri
                miss.pop(key, None)
                filled += 1
            elif err in (429, 503):
                retried += 1  # do not remember a rate limit as "no photo"
            else:
                miss[key] = date.today().isoformat()
                missed += 1
            if n % 40 == 0:
                save(d)
                json.dump(miss, open(MISS, 'w', encoding='utf-8'), ensure_ascii=False)
                notice('X photos %d/%d, filled %d' % (n, len(todo), filled))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    save(d)
    os.makedirs('data', exist_ok=True)
    json.dump(miss, open(MISS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    notice('X photos filled %d, no photo %d, try again later %d' % (filled, missed, retried))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        notice('X photos skipped: %s' % e, 'warning')
