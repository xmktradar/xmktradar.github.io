"""en/ and ko/ pages must not show Chinese (Han) characters in UI text.

Run after tools/build_langs.py (the Build check and Update site do).  Checks:
  1. every en/ko HTML page (home, tools, about, advertise, newsletter, support, 404, stock pages, ...):
     visible text and title/alt/aria-label/placeholder/content attributes, with <script>/<style>/comments removed;
  2. the en/ko homepage app code: no untranslated Chinese UI fragment (build_langs.fragments minus code values).
Exempt (listed with --list):
  - the language switch (<nav class="lang-sw"> or a link with hreflang="zh-Hant": "中" names the Chinese version);
  - third-party content: a post's own original text and account display names, i.e. any text that appears
    in the page data fields posts[].text / orig / name / zh_summary (en/ko: untranslated original) or accounts[].name.
"""
import glob, html, json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import build_langs as B

HAN = re.compile(r'[\u3400-\u9fff\uf900-\ufaff]')
ATTR = re.compile(r'\b(title|alt|aria-label|placeholder|content)="([^"]*)"')


def exempt_blob(lang):
    s = open(f'{lang}/index.html', encoding='utf-8').read()
    m = B.BLOCK.search(s)
    d = json.loads(m.group(2).replace('<\\/', '</'))
    out = []
    posts = list(d.get('posts') or [])
    for f in glob.glob(f'data/dash/{lang}-posts-*.json'):
        try:
            x = json.load(open(f, encoding='utf-8'))
            posts += x if isinstance(x, list) else (x.get('posts') or [])
        except Exception:
            pass
    for p in posts:
        for k in ('text', 'orig', 'name', 'zh_summary', 'summary_zh', 'quoted_text'):
            v = p.get(k) if isinstance(p, dict) else None
            if isinstance(v, str) and HAN.search(v):
                out.append(v)
    for h, a in (d.get('accounts') or {}).items():
        if isinstance(a, dict) and isinstance(a.get('name'), str):
            out.append(a['name'])
    return re.sub(r'\s+', ' ', '\n'.join(out))


def segments(page):
    s = re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>|<!--.*?-->', ' ', page, flags=re.S)
    s = re.sub(r'<nav class="lang-sw"[^>]*>.*?</nav>', ' ', s, flags=re.S)
    s = re.sub(r'<a [^>]*(?:hreflang|data-lang)="zh[^"]*"[^>]*>中</a>', ' ', s)  # link to the Chinese version
    for m in ATTR.finditer(s):
        if HAN.search(m.group(2)):
            yield html.unescape(m.group(2))
    for t in re.split(r'<[^>]*>', s):
        if HAN.search(t):
            yield html.unescape(t)


def run(show=False):
    bad, ex = [], []
    for lang in ('en', 'ko'):
        blob = exempt_blob(lang)
        for f in sorted(glob.glob(f'{lang}/**/*.html', recursive=True)):
            for seg in segments(open(f, encoding='utf-8').read()):
                seg = re.sub(r'\s+', ' ', seg).strip()
                # exempt only if every Han run in the segment comes from third-party text
                runs = re.findall(r'[^\s<>]*' + HAN.pattern + r'[^\s<>]*', seg)
                (ex if all(r in blob for r in runs) else bad).append((f, seg[:120]))
        s = open(f'{lang}/index.html', encoding='utf-8').read()
        m = B.BLOCK.search(s)
        code = s[:m.start(2)] + s[m.end(2):]
        for t in sorted({t for _, _, t in B.fragments(code)} - B.code_values(code)):
            bad.append((f'{lang}/index.html (app code)', t))
    if show:
        for f, t in ex:
            print('exempt', f, t)
    for f, t in bad:
        print('CHINESE', f, t)
    print(f'{len(bad)} Chinese UI strings, {len(ex)} exempt third-party strings')
    return not bad


if __name__ == '__main__':
    sys.exit(0 if run('--list' in sys.argv) else 1)
