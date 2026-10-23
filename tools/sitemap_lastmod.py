"""Step 12b (runs after every generator has written sitemap.xml): give each sitemap URL its real <lastmod>.

The generators stamp every row with the build time. Here each page's HTML is hashed on its visible text plus JSON-LD (styles, scripts and markup removed) after removing the parts that
change on every build without the content changing (build ids, timestamps, view counter, cache busters). <lastmod>
only moves to this build's time when that hash changes. State lives in data/sitemap-lastmod.json.
URLs whose content changed in this build are written to data/indexnow-changed.json (used by tools/indexnow.py).

The bare root https://thecrowdtape.com/ is dropped from the final sitemap: it only redirects by language and its
canonical is /zh/ (publish_extras.py re-adds it each build because the generators read the build time from it).

--seed: build the state from git history (oldest commit of the newest run of identical content per page).
"""
import hashlib
import json
import os
import re
import subprocess
import sys

SITE = 'https://thecrowdtape.com/'
STATE = 'data/sitemap-lastmod.json'
CHANGED = 'data/indexnow-changed.json'

STRIP = [
    re.compile(r'<style\b.*?</style>', re.S),
    re.compile(r'<script\b(?![^>]*ld\+json).*?</script>', re.S),
    re.compile(r'<nav class="lang-sw".*?</nav>', re.S),
    re.compile(r'<nav id="stock-index".*?</nav>', re.S),  # site-wide list of every stock page, reordered each build
    re.compile(r'<[^>]+>'),
    re.compile(r'\s+'),
]
VOLATILE = [
    re.compile(r'<b id="viewcount">[^<]*</b>'),
    re.compile(r'<meta name="generator" content="[^"]*">'),
    re.compile(r'build-[0-9A-Za-z_-]+'),
    re.compile(r'[?&]v=[0-9A-Za-z_-]+'),
    re.compile(r'\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)?(?:Z|[+-]\d{2}:?\d{2})?'),
    re.compile(r'\b\d{1,2}:\d{2}\b'),
]


def norm_hash(b):
    s = b.decode('utf-8', 'replace')
    m = re.search(r'<main\b.*?</main>', s, re.S)
    if m:  # page content only: <main> plus structured data, not the shared header/footer chrome
        s = ''.join(re.findall(r'<script type="application/ld\+json">.*?</script>', s, re.S)) + m.group(0)
    for r in VOLATILE[:4]:
        s = r.sub('', s)
    for r in STRIP:
        s = r.sub(' ', s)
    for r in VOLATILE[4:]:
        s = r.sub('', s)
    return hashlib.sha1(s.encode()).hexdigest()[:16]


def file_of(url):
    p = url[len(SITE):]
    return (p + 'index.html') if p.endswith('/') or p == '' else p


def build_time(sm):
    m = re.search(r'<loc>' + re.escape(SITE) + r'</loc><lastmod>([^<]+)', sm) or re.search(r'<lastmod>([^<]+)', sm)
    return m.group(1) if m else None


def seed(urls):
    state = {}
    for u in urls:
        f = file_of(u)
        if not os.path.exists(f):
            continue
        cur = norm_hash(open(f, 'rb').read())
        log = subprocess.run(['git', 'log', '-n', '60', '--format=%H %cI', '--', f], capture_output=True, text=True).stdout.split('\n')
        when = None
        for line in filter(None, log):
            sha, iso = line.split(' ', 1)
            blob = subprocess.run(['git', 'show', f'{sha}:{f}'], capture_output=True).stdout
            if not blob or norm_hash(blob) != cur:
                break
            when = iso
        state[u] = [cur, when]
    return state


def iso_hkt(iso):
    # git %cI may be in any offset; keep it as-is unless it is UTC, then shift to +08:00
    from datetime import datetime, timedelta, timezone
    d = datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(timezone(timedelta(hours=8)))
    return d.strftime('%Y-%m-%dT%H:%M:%S+08:00')


def main():
    sm = open('sitemap.xml', encoding='utf-8').read()
    now = build_time(sm)
    # drop the bare root row and blank lines
    sm = re.sub(r'\n\s*<url><loc>' + re.escape(SITE) + r'</loc>.*?</url>', '', sm)
    sm = re.sub(r'\n\s*\n', '\n', sm)
    urls = re.findall(r'<loc>([^<]+)</loc>', sm)
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    if '--seed' in sys.argv:
        state = seed(urls)
    changed = []
    new_state = {}
    for u in urls:
        f = file_of(u)
        h = norm_hash(open(f, 'rb').read()) if os.path.exists(f) else None
        old = state.get(u)
        if old and old[0] == h and old[1]:
            lm = old[1]
        else:
            lm = now
            changed.append(u)
        if lm and 'T' in lm and not lm.endswith('+08:00'):
            lm = iso_hkt(lm)
        new_state[u] = [h, lm]
    def put(m):
        u = m.group(1)
        return f'<loc>{u}</loc><lastmod>{new_state[u][1]}</lastmod>' if new_state.get(u, [0, None])[1] else m.group(0)
    sm = re.sub(r'<loc>([^<]+)</loc><lastmod>[^<]*</lastmod>', put, sm)
    open('sitemap.xml', 'w', encoding='utf-8').write(sm)
    json.dump(new_state, open(STATE, 'w'), indent=0, sort_keys=True)
    json.dump(sorted(changed), open(CHANGED, 'w'), indent=0)
    print(f'sitemap lastmod: {len(urls)} URLs, {len(changed)} changed this build, {len(set(v[1] for v in new_state.values()))} distinct lastmod values')


if __name__ == '__main__':
    main()
