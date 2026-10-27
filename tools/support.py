"""Write the donation pages from tools/support.html (Chinese master).

i18n/<lang>.json["support"] maps each Chinese string to its translation.
Writes support/index.html (Chinese) and zh|en/support/index.html, and lists
the three language URLs in sitemap.xml.
"""
import json
import os
import re

from build_langs import with_root_redirect

SITE = 'https://thecrowdtape.com/'
LANGS = {'zh': 'zh-Hant', 'en': 'en'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAN = re.compile(r'[\u4e00-\u9fff]')


def table(lang):
    if lang == 'zh':
        return {}
    data = json.load(open(os.path.join(ROOT, 'i18n', lang + '.json'), encoding='utf-8'))
    got = data.get('support') or {}
    return got if isinstance(got, dict) else {}


def apply(html, tr):
    for src in sorted(tr, key=len, reverse=True):
        html = html.replace(src, tr[src])
    return html


def page(template, lang):
    cur = {k: (' aria-current="page"' if k == lang else '') for k in LANGS}
    html = template.replace('{{lang}}', LANGS[lang]).replace('{{lang_code}}', lang)
    html = html.replace('{{canon}}', f'{SITE}{lang}/support/')
    html = html.replace('{{home}}', f'/{lang}/')
    for k, mark in cur.items():
        html = html.replace('{{cur_%s}}' % k, mark)
    return apply(html, table(lang))


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


def sitemap():
    path = os.path.join(ROOT, 'sitemap.xml')
    if not os.path.exists(path):
        return
    sm = open(path, encoding='utf-8').read()
    sm = re.sub(r'\s*<url><loc>' + re.escape(SITE) + r'(?:(?:zh|en|ko)/)?support/</loc>.*?</url>', '', sm, flags=re.S)
    gen = re.search(r'<loc>' + re.escape(SITE) + r'</loc><lastmod>([^<]+)', sm)
    last = gen.group(1) if gen else ''
    alt = ''.join(f'<xhtml:link rel="alternate" hreflang="{LANGS[k]}" href="{SITE}{k}/support/"/>' for k in LANGS)
    rows = ''.join(
        f'\n  <url><loc>{SITE}{k}/support/</loc><lastmod>{last}</lastmod><changefreq>monthly</changefreq>{alt}</url>'
        for k in LANGS)
    sm = sm.replace('</urlset>', rows + '\n</urlset>')
    sm = dedupe_sitemap(sm)
    if not sm.endswith('\n'):
        sm += '\n'
    open(path, 'w', encoding='utf-8').write(sm)
    print('sitemap support')


def main():
    os.chdir(ROOT)
    template = open(os.path.join(ROOT, 'tools', 'support.html'), encoding='utf-8').read()
    zh = page(template, 'zh')
    write('support/index.html', with_root_redirect(zh, 'support'))
    write('zh/support/index.html', zh)
    for lang in ('en',):
        html = page(template, lang)
        body = re.sub(r'<nav class="lang".*?</nav>', '', html, flags=re.S)
        left = HAN.findall(body)
        if left:
            print(f'::warning::{lang} support page still has Chinese: {"".join(left[:12])}')
        write(f'{lang}/support/index.html', html)
    sitemap()


if __name__ == '__main__':
    main()
