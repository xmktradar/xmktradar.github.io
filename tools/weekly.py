"""Write the ZH-only weekly brief sales page from tools/weekly.html.

Writes zh/weekly/index.html (canonical, lang=zh-Hant) and weekly/index.html
(the same Chinese page). The root file always redirects to /zh/weekly/ and
keeps the query and hash. It does not use build_langs.with_root_redirect or
root_redirect_script: those pick a language and would send visitors to
/en/weekly/, which must not exist. No EN or KO page is written.

Sitemap: https://thecrowdtape.com/zh/weekly/ only, monthly, lastmod from the
same bare-root stamp support.py uses. No EN sitemap row and no EN hreflang
alternate.

The checkout control is a placeholder. There is no Stripe product, price, or
payment link for a USD 5/month weekly brief.

GitHub 管理員 should add `python3 tools/weekly.py` to Update site (after
support.py / advertise.py) so later rebuilds do not drop the page.
Website Ops does not edit .github/workflows/ (the Update-site pipeline).
"""
import os
import re
from datetime import datetime, timedelta, timezone

SITE = 'https://thecrowdtape.com/'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACEHOLDER = 'Checkout 尚未接通：Stripe 而家未有 Crowd Tape 週報（USD 5/month）產品或 payment link。呢個係佔位按鈕，唔會收費。'
REDIRECT = '<script>(function(){location.replace("/zh/weekly/"+location.search+location.hash)})();</script>'


def page(template):
    html = template.replace('{{lang}}', 'zh-Hant')
    html = html.replace('{{canon}}', SITE + 'zh/weekly/')
    html = html.replace('{{home}}', '/zh/')
    return html


def with_zh_redirect(html):
    """Root /weekly/ always goes to /zh/weekly/. Not the language-detect script."""
    if '</head>' not in html:
        raise SystemExit('weekly template has no </head>')
    return html.replace('</head>', REDIRECT + '</head>', 1)


def write(path, html):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w', encoding='utf-8').write(html)
    print(path)


def dedupe_sitemap(sm):
    """One <url> per <loc>; the last copy wins."""
    found = []
    for m in re.finditer(r'\s*<url>.*?</url>', sm, flags=re.S):
        loc = re.search(r'<loc>([^<]*)</loc>', m.group())
        found.append((m, loc.group(1) if loc else None))
    last = {}
    for i, (_, loc) in enumerate(found):
        if loc is not None:
            last[loc] = i
    out, pos = [], 0
    for i, (m, loc) in enumerate(found):
        if loc is not None and last[loc] != i:
            out.append(sm[pos:m.start()])
            pos = m.end()
    out.append(sm[pos:])
    return ''.join(out)


def now_hkt():
    return datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%dT%H:%M:%S+08:00')


def sitemap():
    """Add only the ZH weekly URL. lastmod matches support.py when the bare
    root row is present (publish_extras.py stamps it during Update site).
    """
    path = os.path.join(ROOT, 'sitemap.xml')
    if not os.path.exists(path):
        return
    sm = open(path, encoding='utf-8').read()
    root = re.search(r'<loc>' + re.escape(SITE) + r'</loc><lastmod>([^<]+)', sm)
    prev = re.search(r'<loc>' + re.escape(SITE) + r'zh/weekly/</loc><lastmod>([^<]+)</lastmod>', sm)
    if root:
        last = root.group(1)
    elif prev:
        last = prev.group(1)
    else:
        last = now_hkt()
    sm = re.sub(
        r'\s*<url><loc>' + re.escape(SITE) + r'(?:(?:zh|en|ko)/)?weekly/</loc>.*?</url>',
        '', sm, flags=re.S)
    alt = f'<xhtml:link rel="alternate" hreflang="zh-Hant" href="{SITE}zh/weekly/"/>'
    row = (
        f'\n  <url><loc>{SITE}zh/weekly/</loc><lastmod>{last}</lastmod>'
        f'<changefreq>monthly</changefreq>{alt}</url>'
    )
    sm = re.sub(r'\s*</urlset>\s*$', row + '\n</urlset>\n', sm, count=1)
    sm = dedupe_sitemap(sm)
    if not sm.endswith('\n'):
        sm += '\n'
    open(path, 'w', encoding='utf-8').write(sm)
    print('sitemap weekly')


def check(html, root_html):
    if '畎' in html:
        raise SystemExit('weekly page still has 畎; use 畀')
    if html.count('<h1') != 1:
        raise SystemExit('weekly page must have one h1')
    if PLACEHOLDER not in html:
        raise SystemExit('weekly page is missing the checkout placeholder')
    if 'href="#checkout-placeholder"' not in html:
        raise SystemExit('weekly CTA must point at the placeholder')
    missed = re.findall(r'\{\{[a-z0-9_]+\}\}', html)
    if missed:
        raise SystemExit('weekly page has unfilled placeholders: ' + ', '.join(missed))
    for bad in ('donate.stripe.com', 'paypal.com', '/en/weekly/', 'hreflang="en"', 'application/ld+json'):
        if bad in html:
            raise SystemExit('weekly page must not contain ' + bad)
    if 'location.replace' in html or 'ct-lang' in root_html or '/en/weekly/' in root_html:
        raise SystemExit('zh page must not redirect, and the root redirect must not language-detect')
    if REDIRECT not in root_html:
        raise SystemExit('root weekly redirect missing')
    for banned in ('en/weekly', 'ko/weekly'):
        if os.path.isdir(os.path.join(ROOT, banned)):
            raise SystemExit('refusing to leave ' + banned)


def main():
    os.chdir(ROOT)
    template = open(os.path.join(ROOT, 'tools', 'weekly.html'), encoding='utf-8').read()
    html = page(template)
    root_html = with_zh_redirect(html)
    check(html, root_html)
    write('zh/weekly/index.html', html)
    write('weekly/index.html', root_html)
    sitemap()


if __name__ == '__main__':
    main()
