"""Step 10: build the language versions /zh/, /en/ and /ko/ from index.html (the Chinese master).

- Fixed text: i18n/<lang>.json, {"ui": {"中文片段": "translation"}, "data": {"中文": "translation"},
  "meta": {"image_alt": "..."}}. i18n/zh.json lists the Chinese UI texts (python3 tools/build_langs.py --extract).
  "ui" replaces text in the page code (longest first); "data" replaces whole strings in the data block
  (category names, roles and the like). A missing file or entry leaves the Chinese text in place.
- Changing content: English posts show the original X text; Korean posts show ko_summary.
  summaries_<lang>, highlights_<lang>, briefings_<lang> replace the Chinese ones when present.
- Every version gets <html lang>, canonical, hreflang, the language switch and absolute asset paths.
- index.html itself gets the same switch and hreflang plus a script that sends visitors to the
  version matching their browser language (automation/README.md section 9).
"""
import copy
import json
import os
import re
import sys

from sitedata import BLOCK, notice, read_json

SITE = 'https://xmktradar.github.io/'
LANGS = {'zh': ('zh-Hant', '中'), 'en': ('en', 'EN'), 'ko': ('ko', '한')}
CONTENT = ('summaries', 'highlights', 'briefings')
MARK = '<!-- lang-head -->'

SWITCH_CSS = ('.lang-sw{display:flex;gap:4px;margin:6px 0 2px}.lang-sw a{font:600 12.5px/1 var(--f-body);'
              'padding:5px 10px;border:1px solid var(--line);border-radius:999px;color:var(--muted);'
              'text-decoration:none;background:var(--surface)}.lang-sw a[aria-current]{color:var(--accent);'
              'border-color:var(--accent);background:var(--accent-soft)}')


CJ = '\u3000-\u303f\u3400-\u9fff\uff00-\uffef'
RUN = re.compile(r'[%s](?:[^<>`\'"\n{}$\\|]*[%s）」』])?' % (CJ, CJ))


def fragments(code):
    """(start, end, text) for every run of Chinese UI text in the page code: HTML text, string pieces
    between ${...}, attribute values. Comments and regular expressions (code logic) are skipped."""
    def blank(m):
        return re.sub(r'[^\n]', ' ', m.group())
    c = re.sub(r'<!--.*?-->', blank, code, flags=re.S)
    c = re.sub(r'/\*.*?\*/', blank, c, flags=re.S)
    c = re.sub(r'(?m)(^|[\s;{}),])//[^\n]*', lambda m: m.group(1) + ' ' * (len(m.group()) - len(m.group(1))), c)
    out = []
    for m in RUN.finditer(c):
        a, b = m.start(), m.end()
        while b > a and c[b - 1] == ' ':
            b -= 1
        t = c[a:b]
        if not re.search('[\u4e00-\u9fff]', t):
            continue
        if (a and c[a - 1] in '/|(') or c[b:b + 1] in ('|', ')', '/'):
            continue  # inside a regular expression
        out.append((a, b, t))
    return out


def translate(code, ui):
    if not ui:
        return code
    parts, last = [], 0
    for a, b, t in fragments(code):
        if t in ui:
            parts += [code[last:a], ui[t]]
            last = b
    return ''.join(parts) + code[last:]


def head_tags(cur):
    alt = ''.join(f'<link rel="alternate" hreflang="{LANGS[k][0]}" href="{SITE}{k}/">' for k in LANGS)
    alt += f'<link rel="alternate" hreflang="x-default" href="{SITE}">'
    canon = f'<link rel="canonical" href="{SITE}{cur or "zh"}/">'
    js = ('<script>(function(){var k="ct-lang";document.addEventListener("click",function(e){'
          'var a=e.target.closest&&e.target.closest(".lang-sw a");if(!a)return;'
          'try{localStorage.setItem(k,a.dataset.lang)}catch(_){}'
          'e.preventDefault();location.href=a.getAttribute("href")+location.hash})')
    if cur is None:  # root: pick a version from the saved choice or the browser language (live site only)
        js += (';if(!/github\\.io$/.test(location.hostname))return;var l;try{l=localStorage.getItem(k)}catch(_){}'
               'if(!l){var n=(navigator.languages||[navigator.language||""]).join(",").toLowerCase();'
               'l=/^ko|,ko/.test(n)?"ko":/^zh|,zh/.test(n)?"zh":/^en|,en/.test(n)?"en":"zh"}'
               'location.replace("/"+l+"/"+location.hash)')
    js += '})();</script>'
    return f'{MARK}{canon}{alt}<style>{SWITCH_CSS}</style>{js}{MARK}'


def switch(cur):
    on = ' aria-current="page"'
    links = ''.join(f'<a href="/{k}/" data-lang="{k}"{on if k == (cur or "zh") else ""}>{lab}</a>'
                    for k, (_, lab) in LANGS.items())
    return f'<nav class="lang-sw" aria-label="Language">{links}</nav>'


def add_chrome(s, cur):
    """Head tags and the switch; safe to run again on a page that already has them."""
    s = re.sub(re.escape(MARK) + '.*?' + re.escape(MARK), '', s, flags=re.S)
    s = re.sub(r'<link rel="canonical"[^>]*>', '', s)
    s = s.replace('</head>', head_tags(cur) + '</head>', 1)
    s = re.sub(r'<nav class="lang-sw".*?</nav>', '', s, flags=re.S)
    s = s.replace('<div class="views">', switch(cur) + '<div class="views">', 1)
    return s


def overlay(zh, tr):
    if isinstance(zh, dict) and isinstance(tr, dict):
        if all(isinstance(v, list) for v in zh.values()):  # summaries: {daily: [...], weekly: [...]}
            return {k: overlay(v, tr.get(k)) for k, v in zh.items()}
        return {**zh, **tr}  # highlights by day
    if isinstance(zh, list) and isinstance(tr, list):  # items matched by date (and window)
        key = lambda x: (x.get('date'), json.dumps(x.get('win'), sort_keys=True)) if isinstance(x, dict) else None  # noqa: E731
        by = {key(x): x for x in tr}
        out = [by.get(key(x), x) for x in zh]
        return out
    return zh if tr is None else tr


def swap_data(d, lang, fixed):
    d = copy.deepcopy(d)
    for k in CONTENT:  # translated items replace the Chinese ones; items not yet translated stay in Chinese
        if d.get(f'{k}_{lang}'):
            d[k] = overlay(d.get(k), d[f'{k}_{lang}'])
    for p in d['posts']:
        alt = p.get('text') if lang == 'en' else p.get('ko_summary') if lang == 'ko' else None
        if alt:
            p['zh_summary'] = alt
            if 'summary_zh' in p:
                p['summary_zh'] = alt

    def walk(o):
        if isinstance(o, dict):
            return {k: walk(v) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v) for v in o]
        return fixed.get(o, o) if isinstance(o, str) else o
    if fixed:
        posts = d.pop('posts')
        d = walk(d)
        d['posts'] = posts
    for k in list(d):
        if re.match(r'^(%s)_(en|ko)$' % '|'.join(CONTENT), k):
            del d[k]  # the other languages' copies are not needed on this page
    return d


def build(lang, master):
    tr = read_json(f'i18n/{lang}.json', {}) or {}
    m = BLOCK.search(master)
    d = json.loads(m.group(2).replace('<\\/', '</'))
    blob = json.dumps(swap_data(d, lang, tr.get('data') or {}), ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    code = master[:m.start(2)], master[m.end(2):]
    out = [translate(part, tr.get('ui') or {}) for part in code]
    s = out[0] + blob + out[1]
    s = re.sub(r'<html lang="[^"]*"', f'<html lang="{LANGS[lang][0]}"', s, count=1)
    s = re.sub(r'(<meta property="og:url" content=")[^"]*', rf'\g<1>{SITE}{lang}/', s, count=1)
    alt = (tr.get('meta') or {}).get('image_alt')
    if alt:  # the Chinese alt text changes every day; other versions use a fixed description
        s = re.sub(r'(<meta (?:property="og|name="twitter):image:alt" content=")[^"]*', lambda m: m.group(1) + alt, s)
    s = re.sub(r'''(["'(])assets/''', r'\1/assets/', s)
    s = add_chrome(s, lang)
    os.makedirs(lang, exist_ok=True)
    open(f'{lang}/index.html', 'w', encoding='utf-8').write(s)
    left = len(re.findall(r'[一-鿿]', out[0] + out[1])) if lang != 'zh' else 0
    return left


def sitemap(gen):
    sm = open('sitemap.xml', encoding='utf-8').read()
    sm = re.sub(r'\s*<url><loc>https://xmktradar\.github\.io/(zh|en|ko)/</loc>.*?</url>', '', sm, flags=re.S)
    if 'xmlns:xhtml' not in sm:
        sm = sm.replace('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
                        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">')
    alt = ''.join(f'<xhtml:link rel="alternate" hreflang="{LANGS[k][0]}" href="{SITE}{k}/"/>' for k in LANGS)
    rows = ''.join(f'\n  <url><loc>{SITE}{k}/</loc><lastmod>{gen}</lastmod><changefreq>hourly</changefreq>{alt}</url>' for k in LANGS)
    sm = sm.replace('</urlset>', rows[1:] + '\n</urlset>')
    open('sitemap.xml', 'w', encoding='utf-8').write(sm)


def extract():
    """Write i18n/zh.json: every Chinese UI text in the page code, the list translators work from."""
    s = open('index.html', encoding='utf-8').read()
    m = BLOCK.search(s)
    seen = {}
    for part in (s[:m.start(2)], s[m.end(2):]):
        part = re.sub(r'<meta (?:property="og|name="twitter):image:alt"[^>]*>', '', part)
        for _, _, t in fragments(part):
            seen.setdefault(t, None)
    os.makedirs('i18n', exist_ok=True)
    json.dump(list(seen), open('i18n/zh.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(len(seen), 'texts')


def main():
    if sys.argv[1:] == ['--extract']:
        return extract()
    master = open('index.html', encoding='utf-8').read()
    master = add_chrome(master, None)
    open('index.html', 'w', encoding='utf-8').write(master)
    left = {k: build(k, master) for k in LANGS}
    gen = re.search(r'<loc>https://xmktradar\.github\.io/</loc><lastmod>([^<]+)', open('sitemap.xml', encoding='utf-8').read())
    sitemap(gen.group(1) if gen else '')
    notice('語言版本：/zh/ /en/ /ko/ 已生成' + ''.join(f'；{k} 版介面仍有 {n} 段中文未翻譯' for k, n in left.items() if n))


if __name__ == '__main__':
    main()
