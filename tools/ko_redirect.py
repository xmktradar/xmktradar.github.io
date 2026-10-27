"""Korean (/ko/) was removed on 2026-10-27 (Tim: only Chinese and English). Old /ko/ links from search
engines and past social posts must not die, so every page that exists under /en/ gets a tiny page at the
same path under /ko/ that sends the visitor to the English page (meta refresh plus script, canonical on
the English page, noindex). Anything else under ko/ (old Korean pages, feed.xml) is deleted. 404.html
also sends any other /ko/... path to /en/... (tools/page404.py).

The sitemap loses every /ko/ URL and every hreflang="ko" alternate.
"""
import glob
import html
import os
import re

SITE = 'https://thecrowdtape.com/'
MARK = '<!-- ko-redirect -->'


def stub(target):
    url = SITE + target
    u = html.escape(url, quote=True)
    js = url.replace('\\', '\\\\').replace('"', '\\"')
    return (f'<!doctype html>{MARK}<html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="robots" content="noindex"><link rel="canonical" href="{u}">'
            f'<meta http-equiv="refresh" content="0;url={u}"><title>The Crowd Tape</title>'
            f'<script>location.replace("{js}"+location.search+location.hash)</script></head>'
            f'<body><p><a href="{u}">The Crowd Tape (English)</a></p></body></html>\n')


def target_for(rel):
    """en-relative page path -> URL path on the site (index.html maps to its folder)."""
    if rel == 'index.html':
        return 'en/'
    if rel.endswith('/index.html'):
        return 'en/' + rel[:-len('index.html')]
    return 'en/' + rel


def write_stubs():
    want = {}
    for f in glob.glob('en/**/*.html', recursive=True):
        rel = os.path.relpath(f, 'en').replace(os.sep, '/')
        want['ko/' + rel] = stub(target_for(rel))
    n = 0
    for path, body in want.items():
        old = open(path, encoding='utf-8').read() if os.path.exists(path) else None
        if old != body:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, 'w', encoding='utf-8').write(body)
            n += 1
    gone = 0
    for f in glob.glob('ko/**/*', recursive=True):
        if os.path.isfile(f) and f.replace(os.sep, '/') not in want:
            os.remove(f)
            gone += 1
    for d in sorted(glob.glob('ko/**/', recursive=True), key=len, reverse=True):
        if os.path.isdir(d) and not os.listdir(d):
            os.rmdir(d)
    return len(want), n, gone


def clean_sitemap():
    if not os.path.exists('sitemap.xml'):
        return 0
    sm = open('sitemap.xml', encoding='utf-8').read()
    out = re.sub(r'\s*<url>\s*<loc>' + re.escape(SITE) + r'ko/[^<]*</loc>.*?</url>', '', sm, flags=re.S)
    out = re.sub(r'<xhtml:link rel="alternate" hreflang="ko"[^>]*/>', '', out)
    if out != sm:
        open('sitemap.xml', 'w', encoding='utf-8').write(out)
    return sm.count('/ko/') - out.count('/ko/')


def main():
    total, changed, gone = write_stubs()
    dropped = clean_sitemap()
    print(f'::notice::韓文已刪：/ko/ 轉址頁 {total} 個（改咗 {changed} 個），刪走 {gone} 個舊韓文檔，sitemap 拎走 {dropped} 個 /ko/ 連結')


if __name__ == '__main__':
    main()
