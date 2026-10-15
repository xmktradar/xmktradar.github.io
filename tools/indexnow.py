"""Step 13: tell search engines which pages changed, via IndexNow (Bing, Naver, Yandex, Seznam and others share it).

The key file ccab4c5e388dc31f07a4976abba71466.txt at the site root proves the site is ours; no search-engine account is needed.
Pages changed by the commit just published are sent (deleted stock pages too, so they leave the index).
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
PAGE = re.compile(r'^(?:(zh|en|ko)/(?:stock/([^/]+)/)?)?index\.html$')


def changed():
    out = subprocess.run(['git', 'diff', '--name-only', 'HEAD~1', 'HEAD'], capture_output=True, text=True, check=True).stdout
    urls = []
    for f in out.split():
        m = PAGE.match(f)
        if m:
            lang, tk = m.groups()
            urls.append(SITE + (f'{lang}/' if lang else '') + (f'stock/{tk}/' if tk else ''))
    return urls


def everything():
    return re.findall(r'<loc>([^<]+)</loc>', open('sitemap.xml', encoding='utf-8').read())


def main():
    full = '--all' in sys.argv or os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch'
    urls = sorted(set(everything() if full else changed()))
    if not urls:
        return notice('IndexNow：今次冇網頁改動')
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
