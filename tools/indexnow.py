"""Step 13: tell search engines which pages changed, via IndexNow (Bing, Naver, Yandex, Seznam and others share it).

The key file ccab4c5e388dc31f07a4976abba71466.txt at the site root proves the site is ours; no search-engine account is needed.
Each run sends pages whose content really changed this build (data/indexnow-changed.json from tools/sitemap_lastmod.py; deleted pages fall back to the commit diff). Deleted stock pages are included so they leave the index.
The first Update site run of an HKT day (hour < 4, the 03:05 slot; INDEXNOW_BACKFILL=1 forces it) also sends up to BACKFILL sitemap URLs. Those are a deterministic rotating slice of the priority order (/zh/ /en/ /ko/, then other non-stock pages, then stock pages, sitemap order inside each group). The slice starts at (day_number * BACKFILL) mod N and wraps, so each URL is resubmitted about once per ceil(N/BACKFILL) days (8 days at the current sitemap size) and at most once a day. URLs already in the changed list are left out of the slice. No submission ledger is stored.
Manual runs (workflow_dispatch) or --all send every page in sitemap.xml.
Google does not use IndexNow; it reads sitemap.xml, which robots.txt points to.
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

from sitedata import notice, now_hk

SITE = 'https://thecrowdtape.com/'
KEY = 'ccab4c5e388dc31f07a4976abba71466'
CHANGED = 'data/indexnow-changed.json'
BACKFILL = 150
MAX = 10000
HOMES = (SITE + 'zh/', SITE + 'en/', SITE + 'ko/')
PAGE = re.compile(r'^(?:(zh|en|ko)/(?:stock/([^/]+)/)?)?index\.html$')


def changed():
    """URLs whose content really changed this build (tools/sitemap_lastmod.py writes the list).
    Falls back to the files changed by the last commit when that list is missing."""
    if os.path.exists(CHANGED):
        urls = [u for u in json.load(open(CHANGED)) if u.startswith(SITE)]
        gone = subprocess.run(['git', 'diff', '--name-only', '--diff-filter=D', 'HEAD~1', 'HEAD'], capture_output=True, text=True).stdout
        for f in gone.split():  # deleted pages, so they leave the index
            m = PAGE.match(f)
            if m:
                lang, tk = m.groups()
                urls.append(SITE + (f'{lang}/' if lang else '') + (f'stock/{tk}/' if tk else ''))
        return urls
    out = subprocess.run(['git', 'diff', '--name-only', 'HEAD~1', 'HEAD'], capture_output=True, text=True, check=True).stdout
    urls = []
    for f in out.split():
        m = PAGE.match(f)
        if m:
            lang, tk = m.groups()
            urls.append(SITE + (f'{lang}/' if lang else '') + (f'stock/{tk}/' if tk else ''))
    return urls


def key_hosted():
    try:
        with urllib.request.urlopen(f'{SITE}{KEY}.txt', timeout=20) as r:
            return r.read().decode().strip() == KEY
    except Exception:
        return False


def everything(path='sitemap.xml'):
    return re.findall(r'<loc>([^<]+)</loc>', open(path, encoding='utf-8').read())


def day_number(today):
    """One integer per civil date. It increases by 1 each HKT day, so the slice steps by BACKFILL."""
    return today.toordinal()


def want_backfill(now=None):
    """True on the first Update site slot of the HKT day (03:05, hour < 4). INDEXNOW_BACKFILL=1 forces it."""
    if os.environ.get('INDEXNOW_BACKFILL') == '1':
        return True
    if now is None:
        now = now_hk()
    return now.hour < 4


def order_urls(sitemap):
    """/zh/ /en/ /ko/, then other non-stock pages, then stock pages. Sitemap order within each group."""
    seen = set()
    other, stock = [], []
    for url in sitemap:
        if url in seen:
            continue
        seen.add(url)
        if url in HOMES:
            continue
        if '/stock/' in url:
            stock.append(url)
        else:
            other.append(url)
    homes = [u for u in HOMES if u in seen]
    return homes + other + stock


def rotating_slice(ordered, day_num, cap=BACKFILL):
    """Window of at most cap URLs (never more than BACKFILL or N) starting at (day_num * BACKFILL) mod N, wrapping."""
    n = len(ordered)
    if n == 0:
        return []
    count = min(cap, BACKFILL, n)
    if count <= 0:
        return []
    start = (day_num * BACKFILL) % n
    return [ordered[(start + i) % n] for i in range(count)]


def pick_backfill(sitemap, skip, today, cap=BACKFILL):
    """Today's rotating slice, without URLs already in skip. The window does not grow to replace them."""
    skip = set(skip)
    return [u for u in rotating_slice(order_urls(sitemap), day_number(today), cap) if u not in skip]


def unique(seq):
    seen = set()
    out = []
    for u in seq:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def post(urls):
    body = json.dumps({'host': 'thecrowdtape.com', 'key': KEY, 'keyLocation': f'{SITE}{KEY}.txt',
                       'urlList': urls}).encode()
    req = urllib.request.Request('https://api.indexnow.org/indexnow', data=body, method='POST',
                                 headers={'Content-Type': 'application/json; charset=utf-8'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def main():
    full = '--all' in sys.argv or os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch'
    sitemap = everything()
    if full:
        batch = unique(sitemap)[:MAX]
        label = '全部'
    else:
        now = now_hk()
        changed_urls = unique(changed())[:MAX]
        if want_backfill(now):
            fill = pick_backfill(sitemap, changed_urls, now.date(), min(BACKFILL, MAX - len(changed_urls)))
        else:
            fill = []
        batch = changed_urls + fill
        label = f'{len(changed_urls)} 今次改動 + {len(fill)} 補交'
    if not batch:
        return notice('IndexNow：今次冇網頁改動')
    if not key_hosted():
        return notice(f'IndexNow：{SITE}{KEY}.txt 未能讀取或內容不符，今次唔提交', 'warning')
    try:
        status = post(batch)
        notice(f'IndexNow：已通知 {len(batch)} 個網頁（{label}），回應 {status}')
    except urllib.error.HTTPError as e:
        notice(f'IndexNow 拒絕：HTTP {e.code} {e.read().decode("utf-8", "replace")[:200]}', 'warning')
    except (urllib.error.URLError, TimeoutError) as e:
        notice(f'IndexNow 連唔到：{e}', 'warning')


if __name__ == '__main__':
    main()
