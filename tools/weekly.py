"""Write the ZH-only weekly brief sales page from tools/weekly.html.

Writes zh/weekly/index.html (canonical, lang=zh-Hant) and weekly/index.html
(the same Chinese page). The root file always redirects to /zh/weekly/ and
keeps the query and hash. It does not use build_langs.with_root_redirect or
root_redirect_script: those pick a language and would send visitors to
/en/weekly/, which must not exist. No EN or KO page is written.

The subscribe button links to the Stripe Payment Link for the USD 5/month
weekly brief (same tab, so Stripe can return to ?checkout=success). The
tracked-account count is len(tracked.accounts) from the Chinese master
dash-data in index.html.

Sitemap: https://thecrowdtape.com/zh/weekly/ only, monthly, lastmod from the
same bare-root stamp support.py uses. No EN sitemap row and no EN hreflang
alternate.

GitHub 管理員 should add `python3 tools/weekly.py` to Update site (after
support.py / advertise.py) so later rebuilds do not drop the page.
Website Ops does not edit .github/workflows/ (the Update-site pipeline).
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone

SITE = 'https://thecrowdtape.com/'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYMENT_LINK = 'https://buy.stripe.com/cNiaEXfyE8961qM83H2cg02'
REDIRECT = '<script>(function(){location.replace("/zh/weekly/"+location.search+location.hash)})();</script>'
DASH = re.compile(r'<script type="application/json" id="dash-data">(.*?)</script>', re.S)
# Placeholder copy and lookalikes that must not return. A billing-portal id can
# resemble a Payment Link id; only PAYMENT_LINK is allowed.
FORBIDDEN = (
    'Checkout 尚未接通',
    '唔會收費',
    '#checkout-placeholder',
    'cta-wait',
    'wait-note',
    'aria-disabled',
    'donate.stripe.com',
    'tip-usd-5',
    'billing.stripe.com',
    'invoice.stripe.com',
    'paypal.com',
    '/en/weekly/',
    'hreflang="en"',
    'application/ld+json',
    'price_',
)


def account_count():
    """Official roster size: len(tracked.accounts) in index.html dash-data.

    index.html is the Chinese master. zh/index.html can lag it, so do not read that copy.
    """
    master = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    m = DASH.search(master)
    if not m:
        raise SystemExit('index.html has no dash-data block')
    data = json.loads(m.group(1).replace('<\\/', '</'))
    accounts = (data.get('tracked') or {}).get('accounts')
    if not isinstance(accounts, list) or not accounts:
        raise SystemExit('dash-data has no tracked.accounts')
    return len(accounts)


def page(template, accounts):
    html = template.replace('{{lang}}', 'zh-Hant')
    html = html.replace('{{canon}}', SITE + 'zh/weekly/')
    html = html.replace('{{home}}', '/zh/')
    html = html.replace('{{accounts}}', str(accounts))
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


def check(html, root_html, accounts):
    if '畎' in html:
        raise SystemExit('weekly page still has 畎; use 畀')
    if html.count('<h1') != 1:
        raise SystemExit('weekly page must have one h1')
    cta = re.search(r'<a\b[^>]*\bhref="' + re.escape(PAYMENT_LINK) + r'"[^>]*>', html)
    if not cta:
        raise SystemExit('weekly CTA must use the Stripe Payment Link')
    tag = cta.group(0)
    if 'target=' in tag or 'aria-disabled' in tag or 'cta-wait' in tag:
        raise SystemExit('weekly CTA must be a same-tab subscribe link')
    if f'{accounts} 個' not in html:
        raise SystemExit('weekly page is missing the tracked account count')
    missed = re.findall(r'\{\{[a-z0-9_]+\}\}', html)
    if missed:
        raise SystemExit('weekly page has unfilled placeholders: ' + ', '.join(missed))
    for bad in FORBIDDEN:
        if bad in html:
            raise SystemExit('weekly page must not contain ' + bad)
    for url in re.findall(r'https?://[^\s"\'<>]*stripe\.com[^\s"\'<>]*', html):
        if url != PAYMENT_LINK:
            raise SystemExit('weekly page has a Stripe URL that is not the Payment Link: ' + url)
    if 'location.replace' in html or 'ct-lang' in root_html or '/en/weekly/' in root_html:
        raise SystemExit('zh page must not redirect, and the root redirect must not language-detect')
    if REDIRECT not in root_html or PAYMENT_LINK not in root_html:
        raise SystemExit('root weekly redirect or Payment Link missing')
    for banned in ('en/weekly', 'ko/weekly'):
        if os.path.isdir(os.path.join(ROOT, banned)):
            raise SystemExit('refusing to leave ' + banned)


def main():
    os.chdir(ROOT)
    accounts = account_count()
    template = open(os.path.join(ROOT, 'tools', 'weekly.html'), encoding='utf-8').read()
    html = page(template, accounts)
    root_html = with_zh_redirect(html)
    check(html, root_html, accounts)
    write('zh/weekly/index.html', html)
    write('weekly/index.html', root_html)
    sitemap()
    print('accounts', accounts)


if __name__ == '__main__':
    main()
