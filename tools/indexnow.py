"""Step 13: tell search engines which pages changed, via IndexNow (Bing, Naver, Yandex, Seznam and others share it).

The key file ccab4c5e388dc31f07a4976abba71466.txt at the site root proves the site is ours; no search-engine account is needed.
Only pages whose content really changed this build are sent (data/indexnow-changed.json from tools/sitemap_lastmod.py; deleted pages fall back to the commit diff) (deleted stock pages too, so they leave the index).
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

from sitedata import notice

SITE = 'https://thecrowdtape.com/'
KEY = 'ccab4c5e388dc31f07a4976abba71466'
CHANGED = 'data/indexnow-changed.json'
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


def everything():
    return re.findall(r'<loc>([^<]+)</loc>', open('sitemap.xml', encoding='utf-8').read())


def main():
    full = '--all' in sys.argv or os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch'
    urls = sorted(set(everything() if full else changed()))
    if not urls:
        return notice('IndexNow：今次冇網頁改動')
    if not key_hosted():
        return notice(f'IndexNow：{SITE}{KEY}.txt 未能讀取或內容不符，今次唔提交', 'warning')
    body = json.dumps({'host': 'thecrowdtape.com', 'key': KEY, 'keyLocation': f'{SITE}{KEY}.txt',
                       'urlList': urls[:10000]}).encode()
    req = urllib.request.Request('https://api.indexnow.org/indexnow', data=body, method='POST',
                                 headers={'Content-Type': 'application/json; charset=utf-8'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            notice(f'IndexNow：已通知 {len(urls)} 個網頁（{"全部" if full else "今次改動"}），回應 {r.status}')
    except urllib.error.HTTPError as e:
        notice(f'IndexNow 拒絕：HTTP {e.code} {e.read().decode("utf-8", "replace")[:200]}', 'warning')
    except (urllib.error.URLError, TimeoutError) as e:
        notice(f'IndexNow 連唔到：{e}', 'warning')


if __name__ == '__main__':
    main()
