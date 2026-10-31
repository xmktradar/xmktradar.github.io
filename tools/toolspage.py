"""Write the tools pages from tools/toolspage.html (Chinese master).

i18n/<lang>.json["toolspage"] maps each Chinese string to its translation.
Writes tools/index.html (Chinese) and zh|en/tools/index.html, and lists
the three language URLs in sitemap.xml.
The IBKR card (data-region="ibkr") is omitted on the Korean page.
Cards follow data/money-links.json: a card shows only when enabled AND it
earns (affiliate/referral). Stock Rover / OptionStrat show only when their
tools.* flag is true and their *_url is a real URL; otherwise the card is removed.
"""
import html as html_lib
import json
import os
import re

from build_langs import with_root_redirect

SITE = 'https://thecrowdtape.com/'
LANGS = {'zh': 'zh-Hant', 'en': 'en'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAN = re.compile(r'[\u4e00-\u9fff]')
DEFAULT_TOOLS = {
    'tradingview': True,
    'finviz': False,
    'koyfin': False,
    'ibkr': False,
    'stockrover': False,
    'optionstrat': False,
}


def money_links():
    """Load data/money-links.json. Defaults: tradingview true, others false."""
    tools = dict(DEFAULT_TOOLS)
    sr_url = ''
    os_url = ''
    path = os.path.join(ROOT, 'data', 'money-links.json')
    try:
        data = json.load(open(path, encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return tools, sr_url, os_url
    if not isinstance(data, dict):
        return tools, sr_url, os_url
    got = data.get('tools') or {}
    if isinstance(got, dict):
        tools.update(got)
    sr_url = data.get('stockrover_url') or ''
    if not isinstance(sr_url, str):
        sr_url = ''
    os_url = data.get('optionstrat_url') or ''
    if not isinstance(os_url, str):
        os_url = ''
    return tools, sr_url, os_url


def table(lang):
    if lang == 'zh':
        return {}
    data = json.load(open(os.path.join(ROOT, 'i18n', lang + '.json'), encoding='utf-8'))
    got = data.get('toolspage') or {}
    return got if isinstance(got, dict) else {}


def apply(html, tr):
    for src in sorted(tr, key=len, reverse=True):
        html = html.replace(src, tr[src])
    return html


def stockrover(html, url):
    """Fill Stock Rover placeholders; hide the card when the URL is empty."""
    url = (url or '').strip()
    if url:
        return html.replace('{{sr_hidden}}', '').replace('{{sr_href}}', html_lib.escape(url, quote=True))
    return html.replace('{{sr_hidden}}', ' hidden').replace('{{sr_href}}', '')


def optionstrat(html, url):
    """Fill OptionStrat placeholders; hide the card when the URL is empty."""
    url = (url or '').strip()
    if url:
        return html.replace('{{os_hidden}}', '').replace('{{os_href}}', html_lib.escape(url, quote=True))
    return html.replace('{{os_hidden}}', ' hidden').replace('{{os_href}}', '')


def drop_disabled(html, tools):
    """Remove each <article> whose inner a.tool-btn has tools[data-tool] false."""
    def keep(m):
        art = m.group(0)
        btn = re.search(r'<a class="tool-btn"[^>]*\bdata-tool="([^"]+)"', art)
        if btn and tools.get(btn.group(1)) is False:
            return ''
        return art
    return re.sub(r'\s*<article\b[^>]*>.*?</article>', keep, html, flags=re.S)


def page(template, lang, tools, sr_url, os_url):
    cur = {k: (' aria-current="page"' if k == lang else '') for k in LANGS}
    html = stockrover(template, sr_url)
    html = optionstrat(html, os_url)
    html = html.replace('{{lang}}', LANGS[lang]).replace('{{lang_code}}', lang)
    html = html.replace('{{canon}}', f'{SITE}{lang}/tools/')
    html = html.replace('{{home}}', f'/{lang}/')
    for k, mark in cur.items():
        html = html.replace('{{cur_%s}}' % k, mark)
    html = apply(html, table(lang))
    enabled = dict(tools)
    if not (sr_url or '').strip():
        enabled['stockrover'] = False
    if not (os_url or '').strip():
        enabled['optionstrat'] = False
    html = drop_disabled(html, enabled)
    return html


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
    sm = re.sub(r'\s*<url><loc>' + re.escape(SITE) + r'(?:(?:zh|en|ko)/)?tools/</loc>.*?</url>', '', sm, flags=re.S)
    gen = re.search(r'<loc>' + re.escape(SITE) + r'</loc><lastmod>([^<]+)', sm)
    last = gen.group(1) if gen else ''
    alt = ''.join(f'<xhtml:link rel="alternate" hreflang="{LANGS[k]}" href="{SITE}{k}/tools/"/>' for k in LANGS)
    rows = ''.join(
        f'\n  <url><loc>{SITE}{k}/tools/</loc><lastmod>{last}</lastmod><changefreq>monthly</changefreq>{alt}</url>'
        for k in LANGS)
    sm = sm.replace('</urlset>', rows + '\n</urlset>')
    sm = dedupe_sitemap(sm)
    if not sm.endswith('\n'):
        sm += '\n'
    open(path, 'w', encoding='utf-8').write(sm)
    print('sitemap tools')


def main():
    os.chdir(ROOT)
    tools, sr_url, os_url = money_links()
    template = open(os.path.join(ROOT, 'tools', 'toolspage.html'), encoding='utf-8').read()
    zh = page(template, 'zh', tools, sr_url, os_url)
    write('tools/index.html', with_root_redirect(zh, 'tools'))
    write('zh/tools/index.html', zh)
    for lang in ('en',):
        html = page(template, lang, tools, sr_url, os_url)
        body = re.sub(r'<nav class="lang".*?</nav>', '', html, flags=re.S)
        left = HAN.findall(body)
        if left:
            print(f'::warning::{lang} tools page still has Chinese: {"".join(left[:12])}')
        write(f'{lang}/tools/index.html', html)
    sitemap()


if __name__ == '__main__':
    main()
