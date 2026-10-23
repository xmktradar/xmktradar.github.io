"""Write the newsletter archive from tools/newsletter.html (Chinese master).

i18n/<lang>.json["newsletter"] maps each Chinese UI string to its translation.
Issues come from data/newsletter-issues.json. Each issue page is one
language-neutral HTML file (lang="en") rendered from data/newsletter/<slug>.txt.
The unsubscribe line and any {{...}} placeholders are dropped. The rest of the
issue text is kept verbatim. $TICKER links to /en/stock/<T>/ only when that
page exists. @handle links to https://x.com/<handle>.

Writes newsletter/index.html (Chinese), zh|en|ko/newsletter/index.html, and
newsletter/<slug>/index.html. Sitemap: three language archive URLs plus each issue.
"""
import html
import os
import re
from urllib.parse import urlparse

from build_langs import with_root_redirect
from sitedata import BLOCK, read_json

SITE = 'https://thecrowdtape.com/'
LANGS = {'zh': 'zh-Hant', 'en': 'en', 'ko': 'ko'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAN = re.compile(r'[\u4e00-\u9fff]')
FAQ_LD = re.compile(r'(<script type="application/ld\+json" id="faq-ld">)(.*?)(</script>)', re.S)
DISCLAIM_Q = '這是投資建議嗎？'
TOKEN = re.compile(r'https?://[^\s]+|(?<![\w.])@[A-Za-z0-9_]{1,30}|\$[A-Za-z][A-Za-z0-9]{0,9}')
ISSUES = os.path.join(ROOT, 'data', 'newsletter-issues.json')


def table(lang, key):
    if lang == 'zh':
        return {}
    data = read_json(os.path.join(ROOT, 'i18n', lang + '.json'), {})
    got = data.get(key) or {}
    return got if isinstance(got, dict) else {}


def apply(html_s, tr):
    for src in sorted(tr, key=len, reverse=True):
        if src:
            html_s = html_s.replace(src, tr[src])
    return html_s


def esc(s):
    return html.escape(s if s is not None else '', quote=True)


def warn(msg):
    print(f'::warning::{msg}')


def disclaimer_zh():
    master = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    m = FAQ_LD.search(master)
    if not m:
        raise SystemExit('index.html has no faq-ld block')
    d = json_loads(m.group(2))
    for q in d.get('mainEntity') or []:
        if q.get('name') == DISCLAIM_Q:
            return (q.get('acceptedAnswer') or {}).get('text') or ''
    raise SystemExit('faq-ld has no disclaimer answer')


def json_loads(s):
    import json
    return json.loads(s)


def disclaimer_for(lang, zh):
    if lang == 'zh':
        return zh
    data = table(lang, 'data')
    if zh not in data:
        warn(f'{lang} has no data translation for the disclaimer')
        return zh
    return data[zh]


def load_issues():
    import json
    if not os.path.isfile(ISSUES):
        raise SystemExit('missing ' + ISSUES)
    rows = json.load(open(ISSUES, encoding='utf-8'))
    if not isinstance(rows, list):
        raise SystemExit('newsletter-issues.json must be a list')
    out = []
    for row in rows:
        slug = str(row.get('slug') or '')
        if not re.fullmatch(r'[a-z0-9-]+', slug):
            raise SystemExit('bad newsletter slug: ' + slug)
        if not row.get('title') or not row.get('dates'):
            raise SystemExit('newsletter issue needs title and dates: ' + slug)
        out.append(row)
    return out


def clean_issue(raw):
    """Drop {{...}} placeholders and the unsubscribe line. Leave every other line."""
    text = re.sub(r'\{\{.*?\}\}+', '', raw)
    kept = []
    for line in text.splitlines():
        if '{{' in line or '}}' in line:
            continue
        if re.match(r'\s*Unsubscribe\s*:', line, re.I):
            continue
        kept.append(line)
    return '\n'.join(kept).strip('\n')


def stock_set():
    root = os.path.join(ROOT, 'en', 'stock')
    if not os.path.isdir(root):
        return set()
    return {name for name in os.listdir(root)
            if os.path.isfile(os.path.join(root, name, 'index.html'))}


def same_site(url):
    host = (urlparse(url).hostname or '').lower()
    return host in ('thecrowdtape.com', 'www.thecrowdtape.com')


def linkify(text, stocks):
    out, pos = [], 0
    for m in TOKEN.finditer(text):
        out.append(esc(text[pos:m.start()]))
        g = m.group(0)
        if g.startswith('http'):
            url = g.rstrip('.,);')
            extra = g[len(url):]
            attrs = '' if same_site(url) else ' target="_blank" rel="noopener"'
            out.append(f'<a href="{esc(url)}"{attrs}>{esc(url)}</a>')
            out.append(esc(extra))
        elif g.startswith('@'):
            handle = g[1:]
            out.append(
                f'<a href="https://x.com/{esc(handle)}" target="_blank" rel="noopener">{esc(g)}</a>')
        else:
            ticker = g[1:].upper()
            if ticker in stocks:
                out.append(f'<a href="/en/stock/{esc(ticker)}/">{esc(g)}</a>')
            else:
                out.append(esc(g))
        pos = m.end()
    out.append(esc(text[pos:]))
    return ''.join(out)


def is_heading(line):
    if '://' in line or len(line) > 80:
        return False
    return not line.endswith(('.', '。', '!', '?', '！', '？'))


def body_html(text, stocks):
    blocks = re.split(r'\n\s*\n', text.strip())
    parts = []
    for i, block in enumerate(blocks):
        lines = [ln for ln in block.split('\n') if ln.strip()]
        if not lines:
            continue
        if i == 0:
            parts.append(f'<h1>{linkify(lines[0], stocks)}</h1>')
            for ln in lines[1:]:
                parts.append(f'<p class="lead">{linkify(ln, stocks)}</p>')
            continue
        if len(lines) > 1 and is_heading(lines[0]):
            parts.append(f'<h2>{linkify(lines[0], stocks)}</h2>')
            lines = lines[1:]
        for ln in lines:
            parts.append(f'<p>{linkify(ln, stocks)}</p>')
    return '\n'.join(parts)


ISSUE_SHELL = '''<!DOCTYPE html>
<html lang="en">
<head>
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-42CSNJ8DF9"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-42CSNJ8DF9');</script>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="index,follow">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canon}">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="192x192" href="/assets/icon-192.png">
<style>
:root{{
  --bg:#fbf6ec; --surface:#fffaf2; --ink:#3b2f24; --muted:#87776a; --line:#ece1cc;
  --accent:#a5672c; --accent-soft:#f8ecda;
  --f-body:"Noto Sans TC","PingFang TC","Microsoft JhengHei",system-ui,sans-serif;
  --f-display:"Noto Serif TC","Songti TC",serif;
  color-scheme:light;
}}
*{{box-sizing:border-box}}
html{{overflow-x:clip}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--f-body);font-size:16px;line-height:1.6;overflow-wrap:anywhere}}
a{{color:var(--accent)}}
.wrap{{max-width:760px;margin:0 auto;padding:20px 16px 48px}}
header{{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px 16px;margin-bottom:14px;min-width:0}}
.brand{{font-family:var(--f-display);font-weight:700;font-size:20px;color:var(--ink);text-decoration:none}}
.site-nav{{display:flex;flex-wrap:wrap;gap:6px;align-items:center;max-width:100%;min-width:0}}
.site-nav a{{box-sizing:border-box;max-width:100%;font-size:13px;font-weight:700;padding:5px 10px;border:1px solid var(--line);border-radius:999px;color:var(--ink);text-decoration:none;background:var(--surface);line-height:1.3}}
.site-nav a.nav-donate{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.money-bar{{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;box-sizing:border-box;max-width:100%;min-width:0;margin:0 0 14px;padding:8px 10px;border:1px dashed var(--line);border-radius:12px;background:var(--surface);font-size:13.5px;font-weight:700}}
.aff-tag{{display:inline-block;margin-left:4px;padding:1px 8px;border:1px solid var(--line);border-radius:999px;background:var(--bg);color:var(--muted);font-size:11px;font-weight:700;vertical-align:middle}}
.site-foot{{margin-top:22px;padding-top:14px;border-top:1px solid var(--line);color:var(--muted);font-size:13px;line-height:1.7}}
.site-foot p{{margin:0}}
.site-foot a{{font-weight:700}}
h1{{font-family:var(--f-display);font-size:28px;line-height:1.3;margin:0 0 8px;overflow-wrap:anywhere}}
.issue h2{{font-family:var(--f-display);font-size:22px;line-height:1.35;margin:22px 0 8px;overflow-wrap:anywhere}}
.issue p{{margin:0 0 12px}}
.issue .lead{{margin:0 0 16px;color:var(--muted)}}
.note{{margin:16px 0 0;padding:14px 16px;border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:0 12px 12px 0;background:var(--accent-soft)}}
.note b{{display:block;margin-bottom:4px}}
.note p{{margin:0;font-size:14px}}
.back{{display:inline-block;margin-top:18px;font-weight:700;text-decoration:none}}
.ct-news{{position:relative;overflow-x:clip;box-sizing:border-box;width:100%;max-width:100%;margin:18px 0 0;padding:14px 16px;background:var(--surface);border:1px solid var(--line);border-radius:16px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}}
.ct-news-t{{flex:1 0 100%;margin:0;font-weight:700;font-size:15px;line-height:1.45;overflow-wrap:anywhere}}
.ct-news input[type=email]{{flex:1 1 140px;min-width:0;max-width:100%;box-sizing:border-box;margin:0;padding:8px 12px;border:1px solid var(--line);border-radius:999px;background:#fff;color:var(--ink);font:inherit;font-size:16px}}
.ct-news button[type=submit]{{flex:0 1 auto;max-width:100%;box-sizing:border-box;margin:0;padding:8px 16px;border:0;border-radius:999px;background:var(--accent);color:#fff;font:inherit;font-weight:700;font-size:14px;cursor:pointer}}
.ct-news small{{flex:1 0 100%;margin:0;color:var(--muted);font-size:12.5px;line-height:1.4}}
.ct-news-msg{{flex:1 0 100%;margin:0;font-size:14px;line-height:1.45;overflow-wrap:anywhere}}
.ct-news input[name=website]{{position:absolute!important;left:0!important;top:0!important;width:1px!important;height:1px!important;margin:-1px!important;padding:0!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;border:0!important;white-space:nowrap}}
@media(max-width:420px){{h1{{font-size:24px}}.wrap{{padding:16px 14px 40px}}.issue h2{{font-size:20px}}}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <a class="brand" href="/en/">The Crowd Tape</a>
  <nav class="site-nav" aria-label="Site">
    <a href="/en/tools/">Tools</a>
    <a class="nav-donate" href="/en/support/">Support us</a>
  </nav>
</header>
<main class="issue">
  <nav class="money-bar" aria-label="Promotion"><span class="aff-tag">Promotion</span><a href="/en/tools/">Tools</a><a href="/en/support/">Support us</a><a href="https://www.tradingview.com/?aff_id=1172819" rel="sponsored noopener" target="_blank" data-tool="tradingview" data-placement="money-bar">TradingView</a><a href="https://www.stockrover.com/thecrowdtape" rel="sponsored nofollow noopener" target="_blank" data-tool="stockrover" data-placement="money-bar">Stock Rover</a></nav>
  {body}
  <aside class="note">
    <b>Not investment advice</b>
    <p>{disclaimer}</p>
  </aside>
  <form class="ct-news" id="ct-news-issue" data-lang="en" action="https://crowdtape-newsletter.vercel.app/api/subscribe" method="POST">
    <label for="ct-email-issue" class="ct-news-t">{form_label}</label>
    <input id="ct-email-issue" type="email" name="email" required autocomplete="email" placeholder="you@example.com">
    <input type="hidden" name="lang" value="en">
    <input type="text" name="website" tabindex="-1" autocomplete="off" style="position:absolute;left:-9999px" aria-hidden="true">
    <button type="submit">{form_btn}</button>
    <small>{form_note}</small>
    <p class="ct-news-msg" role="status" hidden></p>
  </form>
  <script>
  (function(){{
    var M={{en:["Thanks! You're subscribed.","Please check the email address and try again."],
           zh:["Thanks! You're subscribed.","Please check the email address and try again."],
           ko:["감사합니다! 구독되었습니다.","이메일 주소를 확인 후 다시 시도해 주세요."]}};
    document.querySelectorAll('form.ct-news').forEach(function(f){{
      f.addEventListener('submit',function(e){{
        e.preventDefault();
        var l=f.dataset.lang||'en',m=f.querySelector('.ct-news-msg'),d=Object.fromEntries(new FormData(f));
        fetch(f.action,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(d)}})
          .then(function(r){{return r.json()}}).then(function(j){{
            m.hidden=false;m.textContent=M[l][j.ok?0:1];
            if(j.ok){{f.reset();if(window.gtag)gtag('event','newsletter_signup',{{lang:l}});}}
          }}).catch(function(){{m.hidden=false;m.textContent=M[l][1];}});
      }});
    }});
    var sub=new URLSearchParams(location.search).get('subscribed');
    if(sub==='1'||sub==='0') document.querySelectorAll('form.ct-news').forEach(function(f){{
      var l=f.dataset.lang||'en',m=f.querySelector('.ct-news-msg');
      m.hidden=false;m.textContent=M[l][sub==='1'?0:1];
    }});
  }})();
  </script>
  <p><a class="back" href="/en/newsletter/">{back}</a></p>
</main>
<footer class="site-foot">
  <p><a href="/en/tools/">Tools</a> · <a href="/en/support/">Support us</a> · <a href="/en/newsletter/">Newsletter</a> · <a href="https://www.tradingview.com/?aff_id=1172819" rel="sponsored noopener" target="_blank" data-tool="tradingview">TradingView <span class="aff-tag">Promotion</span></a> · <a href="https://www.stockrover.com/thecrowdtape" rel="sponsored nofollow noopener" target="_blank" data-tool="stockrover">Stock Rover <span class="aff-tag">Promotion</span></a></p>
</footer>
</div>
<script>
document.addEventListener("click",function(e){{
  var a=e.target&&e.target.closest&&e.target.closest("a[href]");
  if(!a||!window.gtag)return;
  var u=a.href,h="";
  try{{h=new URL(u).hostname.toLowerCase()}}catch(err){{return}}
  if(a.getAttribute("data-tool")||h==="tradingview.com"||h.endsWith(".tradingview.com"))gtag("event","affiliate_click",{{tool:(a.getAttribute("data-tool")||"tradingview").toLowerCase(),lang:document.documentElement.lang||""}});
  if(h==="x.com"||h.endsWith(".x.com")||h==="twitter.com"||h.endsWith(".twitter.com"))gtag("event","x_outbound",{{link_url:u,page:"newsletter-issue",lang:document.documentElement.lang||"",transport_type:"beacon"}});
}});
</script>
</body>
</html>
'''


def issue_page(issue, text, stocks, disclaimer, ui):
    lines = [ln for ln in text.split('\n') if ln.strip()]
    title = (issue.get('title') or lines[0]) + ' — The Crowd Tape'
    desc = lines[1] if len(lines) > 1 else issue.get('title') or ''
    canon = f'{SITE}newsletter/{issue["slug"]}/'
    body = body_html(text, stocks)
    return ISSUE_SHELL.format(
        title=esc(title),
        desc=esc(desc),
        canon=esc(canon),
        body=body,
        disclaimer=esc(disclaimer),
        form_label=esc(ui.get('每週好淡統計，直送你嘅電郵', 'Get the weekly crowd tally by email')),
        form_btn=esc(ui.get('訂閱', 'Subscribe')),
        form_note=esc(ui.get('免費・每週一封・隨時取消', 'Free · weekly · unsubscribe anytime.')),
        back=esc(ui.get('電子報', 'Newsletter')),
    )


def issues_html(rows):
    items = []
    for row in rows:
        href = f'/newsletter/{row["slug"]}/'
        items.append(
            '<li><a href="{href}"><span class="t">{title}</span>'
            '<span class="dates">{dates}</span></a></li>'.format(
                href=esc(href), title=esc(row['title']), dates=esc(row['dates'])))
    return '<ul class="issues">' + ''.join(items) + '</ul>'


def page(template, lang, issues, disc):
    cur = {k: (' aria-current="page"' if k == lang else '') for k in LANGS}
    html_s = template.replace('{{lang}}', LANGS[lang]).replace('{{lang_code}}', lang)
    html_s = html_s.replace('{{canon}}', f'{SITE}{lang}/newsletter/')
    html_s = html_s.replace('{{home}}', f'/{lang}/')
    for k, mark in cur.items():
        html_s = html_s.replace('{{cur_%s}}' % k, mark)
    html_s = apply(html_s, table(lang, 'newsletter'))
    html_s = html_s.replace('{{issues}}', issues)
    html_s = html_s.replace('{{disclaimer}}', esc(disc))
    if '{{' in html_s:
        warn(f'{lang} newsletter page still has a placeholder')
    return html_s


def write(path, html_s):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w', encoding='utf-8').write(html_s)
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


def sitemap(slugs):
    path = os.path.join(ROOT, 'sitemap.xml')
    if not os.path.exists(path):
        return
    sm = open(path, encoding='utf-8').read()
    sm = re.sub(
        r'\s*<url><loc>' + re.escape(SITE) + r'(?:(?:zh|en|ko)/)?newsletter/</loc>.*?</url>',
        '', sm, flags=re.S)
    sm = re.sub(
        r'\s*<url><loc>' + re.escape(SITE) + r'(?:(?:zh|en|ko)/)?newsletter/[^<]+/</loc>.*?</url>',
        '', sm, flags=re.S)
    gen = re.search(r'<loc>' + re.escape(SITE) + r'</loc><lastmod>([^<]+)', sm)
    last = gen.group(1) if gen else ''
    alt = ''.join(
        f'<xhtml:link rel="alternate" hreflang="{LANGS[k]}" href="{SITE}{k}/newsletter/"/>' for k in LANGS)
    rows = ''.join(
        f'\n  <url><loc>{SITE}{k}/newsletter/</loc><lastmod>{last}</lastmod><changefreq>monthly</changefreq>{alt}</url>'
        for k in LANGS)
    rows += ''.join(
        f'\n  <url><loc>{SITE}newsletter/{slug}/</loc><lastmod>{last}</lastmod><changefreq>monthly</changefreq></url>'
        for slug in slugs)
    sm = sm.replace('</urlset>', rows + '\n</urlset>')
    sm = dedupe_sitemap(sm)
    if not sm.endswith('\n'):
        sm += '\n'
    open(path, 'w', encoding='utf-8').write(sm)
    print('sitemap newsletter')


def main():
    os.chdir(ROOT)
    rows = load_issues()
    zh_disc = disclaimer_zh()
    stocks = stock_set()
    en_ui = table('en', 'newsletter')
    built = []
    for row in rows:
        src = os.path.join(ROOT, 'data', 'newsletter', row['slug'] + '.txt')
        if not os.path.isfile(src):
            raise SystemExit('missing issue text: ' + src)
        raw = open(src, encoding='utf-8').read()
        text = clean_issue(raw)
        if '{{' in text or '}}' in text:
            raise SystemExit('placeholder left in ' + row['slug'])
        page_html = issue_page(row, text, stocks, disclaimer_for('en', zh_disc), en_ui)
        if 'Unsubscribe' in page_html or '{{' in page_html:
            raise SystemExit('issue page still has an unsubscribe line or placeholder: ' + row['slug'])
        write(f'newsletter/{row["slug"]}/index.html', page_html)
        linked = sorted(set(re.findall(r'/en/stock/([A-Z0-9]+)/', page_html)))
        plain = sorted(set(re.findall(r'\$([A-Za-z][A-Za-z0-9]{0,9})', text)))
        missed = [t for t in plain if t.upper() not in stocks]
        print(f'{row["slug"]}: linked {", ".join(linked) or "—"}; no stock page for {", ".join(missed) or "—"}')
        built.append(row['slug'])
    template = open(os.path.join(ROOT, 'tools', 'newsletter.html'), encoding='utf-8').read()
    listing = issues_html(rows)
    zh = page(template, 'zh', listing, zh_disc)
    write('newsletter/index.html', with_root_redirect(zh, 'newsletter'))
    write('zh/newsletter/index.html', zh)
    for lang in ('en', 'ko'):
        html_s = page(template, lang, listing, disclaimer_for(lang, zh_disc))
        body = re.sub(r'<nav class="lang".*?</nav>', '', html_s, flags=re.S)
        left = HAN.findall(body)
        if left:
            warn(f'{lang} newsletter page still has Chinese: {"".join(left[:12])}')
        write(f'{lang}/newsletter/index.html', html_s)
    sitemap(built)


if __name__ == '__main__':
    main()
