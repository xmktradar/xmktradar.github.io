"""Write the advertise pages from tools/advertise.html (Chinese master).

i18n/<lang>.json["advertise"] maps each Chinese string to its translation.
Audience figures come from data/advertise-stats.json at build time. A metric
whose key is absent is left off the page — never a placeholder row.

JSON keys that become a row or block when present:
  monthly_users, monthly_views   one monthly-visitors row (both numbers when
                                 both keys exist; either alone otherwise)
  newsletter_subscribers
  x_followers
  x_impressions_7d               {"value", "as_of"} or a scalar value
  instagram_followers
  threads_followers
  facebook_followers
  lang_views_pct                 language-split block
  top_countries                  country line, names translated per language
  updated                        更新日期：{updated}

Writes advertise/index.html (Chinese) and zh|en|ko/advertise/index.html, and
lists the three language URLs in sitemap.xml.
"""
import html as html_mod
import json
import os
import re
from urllib.parse import quote

from build_langs import with_root_redirect

SITE = 'https://thecrowdtape.com/'
LANGS = {'zh': 'zh-Hant', 'en': 'en', 'ko': 'ko'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAN = re.compile(r'[\u4e00-\u9fff]')
MAIL = 'grokbottimli@gmail.com'
SUBJECT_ZH = '廣告合作查詢'

COUNTRY_ZH = {
    'China': '中國',
    'United States': '美國',
    'Taiwan': '台灣',
    'Hong Kong': '香港',
}
LANG_LABEL = {'zh': '中文', 'en': '英文', 'ko': '韓文'}


def warn(msg):
    print(f'::warning::{msg}')


def table(lang):
    if lang == 'zh':
        return {}
    data = json.load(open(os.path.join(ROOT, 'i18n', lang + '.json'), encoding='utf-8'))
    got = data.get('advertise') or {}
    return got if isinstance(got, dict) else {}


def apply(html, tr):
    for src in sorted(tr, key=len, reverse=True):
        if src:
            html = html.replace(src, tr[src])
    return html


def phrase(zh, lang, tr):
    if lang == 'zh' or not zh:
        return zh
    if zh not in tr:
        warn(f'{lang} advertise page has no translation for: {zh[:80]}')
        return zh
    return tr[zh]


def present(stats, key):
    return isinstance(stats, dict) and key in stats and stats[key] is not None


def num(v):
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def pct_text(v):
    s = num(v)
    return s if s.endswith('%') else s + '%'


def li(label, value):
    return f'<li><span>{label}</span><b>{value}</b></li>'


def load_template():
    return open(os.path.join(ROOT, 'tools', 'advertise.html'), encoding='utf-8').read()


def load_stats(path=None):
    path = path or os.path.join(ROOT, 'data', 'advertise-stats.json')
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise SystemExit('advertise-stats.json must be an object')
    return data


def monthly_items(stats):
    has_u = present(stats, 'monthly_users')
    has_v = present(stats, 'monthly_views')
    if has_u and has_v:
        return [li('每月訪客（近 30 日）', '{users} 人，{views} 次瀏覽')]
    if has_u:
        return [li('每月訪客（近 30 日使用者）', html_mod.escape(num(stats['monthly_users'])))]
    if has_v:
        return [li('每月瀏覽次數（近 30 日）', html_mod.escape(num(stats['monthly_views'])))]
    return []


def impression_item(stats):
    if not present(stats, 'x_impressions_7d'):
        return None
    raw = stats['x_impressions_7d']
    if isinstance(raw, dict):
        if raw.get('value') is None:
            return None
        value = html_mod.escape(num(raw.get('value')))
        if raw.get('as_of'):
            return li('X 近 7 日曝光（截至 {as_of}）', value)
        return li('X 近 7 日曝光', value)
    return li('X 近 7 日曝光', html_mod.escape(num(raw)))


def stat_items(stats):
    """Stats rows for keys that exist. Missing keys are skipped."""
    if not isinstance(stats, dict):
        return []
    rows = monthly_items(stats)
    if present(stats, 'newsletter_subscribers'):
        rows.append(li('電子報訂閱人數', html_mod.escape(num(stats['newsletter_subscribers']))))
    if present(stats, 'x_followers'):
        rows.append(li('X 追蹤人數', html_mod.escape(num(stats['x_followers']))))
    imp = impression_item(stats)
    if imp:
        rows.append(imp)
    for key, label in (
        ('instagram_followers', 'Instagram 追蹤人數'),
        ('threads_followers', 'Threads 追蹤人數'),
        ('facebook_followers', 'Facebook 追蹤人數'),
    ):
        if present(stats, key):
            rows.append(li(label, html_mod.escape(num(stats[key]))))
    return rows


def stats_block(stats):
    rows = stat_items(stats)
    if not rows:
        return ''
    body = '\n'.join('    ' + row for row in rows)
    return '  <ul class="stats">\n' + body + '\n  </ul>\n'


def updated_html(stats):
    if not present(stats, 'updated') or stats.get('updated') == '':
        return ''
    return '  <p class="asof">更新日期：{updated}</p>\n'


def lang_block(stats):
    pct = stats.get('lang_views_pct') if isinstance(stats, dict) else None
    if not isinstance(pct, dict) or not pct:
        return ''
    rows = []
    for code in ('zh', 'en', 'ko'):
        if code in pct and pct[code] is not None:
            rows.append(li(LANG_LABEL[code], html_mod.escape(pct_text(pct[code]))))
    for code, val in pct.items():
        if code in LANG_LABEL or val is None:
            continue
        rows.append(li(html_mod.escape(str(code)), html_mod.escape(pct_text(val))))
    if not rows:
        return ''
    body = '\n'.join('    ' + row for row in rows)
    return (
        '  <h3>語言分佈</h3>\n'
        '  <p class="asof">頁面瀏覽按網站語言。</p>\n'
        '  <ul class="stats">\n'
        f'{body}\n'
        '  </ul>\n'
    )


def country_block(stats, lang, tr):
    names = stats.get('top_countries') if isinstance(stats, dict) else None
    if not isinstance(names, list) or not names:
        return ''
    shown = []
    for name in names:
        if not isinstance(name, str) or not name.strip():
            continue
        zh = COUNTRY_ZH.get(name)
        if zh:
            shown.append(phrase(zh, lang, tr))
        else:
            warn(f'{lang} advertise page has no country name for: {name}')
            shown.append(name.strip())
    if not shown:
        return ''
    sep = '、' if lang == 'zh' else ', '
    text = sep.join(html_mod.escape(s) for s in shown)
    heading = html_mod.escape(phrase('主要國家同地區', lang, tr))
    return f'  <h3>{heading}</h3>\n  <p>{text}</p>\n'


def mail_href(subject):
    q = quote('The Crowd Tape: ' + subject, safe='')
    return f'mailto:{MAIL}?subject={q}'


def fill(html, stats):
    imp = stats.get('x_impressions_7d') if isinstance(stats, dict) else None
    as_of = num(imp.get('as_of')) if isinstance(imp, dict) and imp.get('as_of') else ''
    updated = num(stats.get('updated')) if present(stats, 'updated') else ''
    users = num(stats['monthly_users']) if present(stats, 'monthly_users') else ''
    views = num(stats['monthly_views']) if present(stats, 'monthly_views') else ''
    for key, val in (
        ('{updated}', updated),
        ('{users}', users),
        ('{views}', views),
        ('{as_of}', as_of),
    ):
        html = html.replace(key, html_mod.escape(val))
    return html


def page(template, lang, stats):
    tr = table(lang)
    cur = {k: (' aria-current="page"' if k == lang else '') for k in LANGS}
    html = template.replace('{{lang}}', LANGS[lang]).replace('{{canon}}', f'{SITE}{lang}/advertise/')
    html = html.replace('{{home}}', f'/{lang}/')
    for k, mark in cur.items():
        html = html.replace('{{cur_%s}}' % k, mark)
    html = html.replace('{{mailto}}', mail_href(phrase(SUBJECT_ZH, lang, tr)))
    html = html.replace('{{updated_html}}', updated_html(stats))
    html = html.replace('{{stats_block}}', stats_block(stats))
    html = html.replace('{{lang_block}}', lang_block(stats))
    html = apply(html, tr)
    html = html.replace('{{country_block}}', country_block(stats, lang, tr))
    return fill(html, stats)


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
    """Refresh advertise URLs. Replace an existing block in place."""
    path = os.path.join(ROOT, 'sitemap.xml')
    if not os.path.exists(path):
        return
    sm = open(path, encoding='utf-8').read()
    # One leading newline plus the line indent. Do not swallow the blank line
    # that separates this block from the previous section.
    pat = re.compile(
        r'\n[ \t]*<url><loc>' + re.escape(SITE) + r'(?:(?:zh|en|ko)/)?advertise/</loc>.*?</url>',
        re.S)
    found = pat.search(sm)
    sm_wo = pat.sub('', sm)
    gen = re.search(r'<loc>' + re.escape(SITE) + r'</loc><lastmod>([^<]+)', sm_wo)
    last = gen.group(1) if gen else ''
    alt = ''.join(f'<xhtml:link rel="alternate" hreflang="{LANGS[k]}" href="{SITE}{k}/advertise/"/>' for k in LANGS)
    rows = ''.join(
        f'\n  <url><loc>{SITE}{k}/advertise/</loc><lastmod>{last}</lastmod><changefreq>monthly</changefreq>{alt}</url>'
        for k in LANGS)
    if found:
        # Prefix before the first advertise URL is unchanged by the removal.
        start = found.start()
        sm = sm_wo[:start] + rows + sm_wo[start:]
    else:
        sm = sm_wo.replace('</urlset>', rows + '\n</urlset>')
    sm = dedupe_sitemap(sm)
    if not sm.endswith('\n'):
        sm += '\n'
    open(path, 'w', encoding='utf-8').write(sm)
    print('sitemap advertise')


def main():
    os.chdir(ROOT)
    template = load_template()
    stats = load_stats()
    pages = {lang: page(template, lang, stats) for lang in LANGS}
    for lang, html in pages.items():
        if lang != 'zh':
            body = re.sub(r'<nav class="lang".*?</nav>', '', html, flags=re.S)
            left = HAN.findall(body)
            if left:
                warn(f'{lang} advertise page still has Chinese: {"".join(left[:12])}')
        missed = re.findall(r'\{\{[a-z0-9_]+\}\}', html)
        if missed:
            warn(f'{lang} advertise page has unfilled placeholders: {missed}')
    write('advertise/index.html', with_root_redirect(pages['zh'], 'advertise'))
    write('zh/advertise/index.html', pages['zh'])
    write('en/advertise/index.html', pages['en'])
    write('ko/advertise/index.html', pages['ko'])
    sitemap()


if __name__ == '__main__':
    main()
