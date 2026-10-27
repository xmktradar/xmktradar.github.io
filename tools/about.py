"""Write the methodology pages from tools/about.html (Chinese master).

i18n/<lang>.json["about"] maps each Chinese UI string to its translation.
Category names and descriptions, and the four homepage FAQ answers, are reused
from i18n/<lang>.json["data"] (the same table build_langs.py uses).
Account counts come from index.html dash-data at build time. The update clock
comes from the cron in .github/workflows/update-site.yml (GitHub cron is UTC;
Hong Kong is UTC+8). When that clock matches the FAQ answer, the FAQ wording
is used as-is.

Writes about/index.html (Chinese) and zh|en/about/index.html, and lists
the three language URLs in sitemap.xml.
"""
import html
import json
import os
import re
from collections import Counter

from build_langs import with_root_redirect
from sitedata import BLOCK, read_json

SITE = 'https://thecrowdtape.com/'
LANGS = {'zh': 'zh-Hant', 'en': 'en'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAN = re.compile(r'[\u4e00-\u9fff]')
FAQ_LD = re.compile(r'(<script type="application/ld\+json" id="faq-ld">)(.*?)(</script>)', re.S)
YML = os.path.join(ROOT, '.github', 'workflows', 'update-site.yml')
UPDATE_Q = '網站多久更新一次？'
DISCLAIM_Q = '這是投資建議嗎？'
COUNT_TMPL = '目前追蹤 <b>{n}</b> 個帳號，其中 {parts}，分成 <b>{nc}</b> 類。'
SCHED_TMPL = '由 GitHub Actions 每 4 小時自動重建一次。排程為 UTC {utc}，即香港時間 {hkt}。'
PLAT_LABEL = {'x': 'X', 'truthsocial': 'Truth Social'}


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


def fill(tmpl, **kw):
    for k, v in kw.items():
        tmpl = tmpl.replace('{' + k + '}', str(v))
    return tmpl


def esc(s):
    return html.escape(s if s is not None else '', quote=True)


def warn(msg):
    print(f'::warning::{msg}')


def load_dash():
    """Same read as build_langs.py: the dash-data block in index.html."""
    master = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    m = BLOCK.search(master)
    if not m:
        raise SystemExit('index.html has no dash-data block')
    d = json.loads(m.group(2).replace('<\\/', '</'))
    tracked = d.get('tracked') or {}
    if not isinstance(tracked.get('accounts'), list) or not isinstance(tracked.get('categories'), list):
        raise SystemExit('dash-data has no tracked.accounts / tracked.categories (restore the full page first)')
    return master, d


def load_faq(master):
    m = FAQ_LD.search(master)
    if not m:
        raise SystemExit('index.html has no faq-ld block')
    d = json.loads(m.group(2))
    rows = []
    for q in d.get('mainEntity') or []:
        ans = (q.get('acceptedAnswer') or {}).get('text') or ''
        rows.append({'name': q.get('name') or '', 'text': ans})
    if len(rows) != 4:
        warn(f'faq-ld has {len(rows)} answers, expected 4')
    return rows


def expand_field(field, lo, hi):
    vals = []
    for part in field.split(','):
        step = 1
        if '/' in part:
            part, step_s = part.split('/', 1)
            step = int(step_s)
        if part == '*':
            a, b = lo, hi
        elif '-' in part:
            a_s, b_s = part.split('-', 1)
            a, b = int(a_s), int(b_s)
        else:
            a = b = int(part)
        if step < 1:
            raise SystemExit('bad cron step in ' + field)
        vals.extend(range(a, b + 1, step))
    return vals


def cron_clocks():
    """UTC and HKT HH:MM lists from update-site.yml. GitHub Actions cron is UTC."""
    text = open(YML, encoding='utf-8').read()
    m = re.search(r"cron:\s*'([^']+)'", text) or re.search(r'cron:\s*"([^"]+)"', text)
    if not m:
        raise SystemExit('no cron in update-site.yml')
    bits = m.group(1).split()
    if len(bits) < 2:
        raise SystemExit('cron is not minute hour ...: ' + m.group(1))
    minutes = expand_field(bits[0], 0, 59)
    hours = expand_field(bits[1], 0, 23)
    utc, hkt = [], []
    for h in hours:
        for mi in minutes:
            utc.append(f'{h:02d}:{mi:02d}')
            hkt.append(f'{(h + 8) % 24:02d}:{mi:02d}')
    return utc, hkt


def zh_join(items):
    if not items:
        return ''
    if len(items) == 1:
        return items[0]
    return '、'.join(items[:-1]) + ' 和 ' + items[-1]


def en_join(items):
    if not items:
        return ''
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return items[0] + ' and ' + items[1]
    return ', '.join(items[:-1]) + ' and ' + items[-1]


def plat_of(account):
    p = (account.get('platform') or 'x').strip().lower()
    if p == 'twitter':
        return 'x'
    return p or 'x'


def plat_label(p):
    return PLAT_LABEL.get(p, p)


def account_href(account):
    handle = (account.get('handle') or '').strip()
    p = plat_of(account)
    if p == 'truthsocial':
        return account.get('url') or ('https://truthsocial.com/@' + handle)
    if p == 'x':
        return 'https://x.com/' + handle
    return account.get('url') or ('https://x.com/' + handle)


def tr_text(zh, lang, data_tr, about_tr):
    if lang == 'zh' or not zh:
        return zh
    if zh in data_tr:
        return data_tr[zh]
    if zh in about_tr:
        return about_tr[zh]
    warn(f'{lang} about page has no translation for: {zh[:80]}')
    return zh


def count_sentence(lang, n, pairs, nc, about_tr):
    """pairs: [(display label, count), ...] already ordered."""
    if lang == 'zh':
        parts = '、'.join(f'<b>{c}</b> 個在 {esc(name)}' for name, c in pairs)
        tmpl = COUNT_TMPL
    elif lang == 'en':
        bits = [f'<b>{c}</b> on {esc(name)}' for name, c in pairs]
        parts = en_join(bits)
        tmpl = about_tr.get(COUNT_TMPL) or COUNT_TMPL
        if COUNT_TMPL not in about_tr:
            warn('en about dict is missing the account-count template')
    else:
        parts = ', '.join(f'{esc(name)} <b>{c}</b>개' for name, c in pairs)
        tmpl = about_tr.get(COUNT_TMPL) or COUNT_TMPL
        if COUNT_TMPL not in about_tr:
            warn('ko about dict is missing the account-count template')
    return '<p class="count">' + fill(tmpl, n=n, parts=parts, nc=nc) + '</p>'


def accounts_html(lang, tracked, data_tr, about_tr):
    accounts = tracked.get('accounts') or []
    categories = tracked.get('categories') or []
    counts = Counter(plat_of(a) for a in accounts)
    order = [p for p in ('x', 'truthsocial') if p in counts]
    order += sorted(p for p in counts if p not in order)
    pairs = [(plat_label(p), counts[p]) for p in order]
    by = {}
    for a in accounts:
        by.setdefault(a.get('category') or '', []).append(a)
    groups = []
    seen = set()
    for cat in categories:
        name = cat.get('name') or ''
        seen.add(name)
        groups.append((cat, by.get(name, [])))
    for name, rows in by.items():
        if name not in seen:
            groups.append(({'name': name, 'desc': ''}, rows))
    parts = [count_sentence(lang, len(accounts), pairs, len(categories), about_tr)]
    for cat, rows in groups:
        name = tr_text(cat.get('name') or '', lang, data_tr, about_tr)
        desc = tr_text(cat.get('desc') or '', lang, data_tr, about_tr)
        items = []
        for a in rows:
            handle = (a.get('handle') or '').strip()
            if not handle:
                warn('tracked account with no handle')
                continue
            href = account_href(a)
            items.append(
                f'<li><a href="{esc(href)}" target="_blank" rel="noopener">@{esc(handle)}</a></li>')
        desc_html = f'<p class="desc">{esc(desc)}</p>' if desc else ''
        parts.append(
            '<section class="cat">'
            f'<h3>{esc(name)}<span class="n">{len(items)}</span></h3>'
            f'{desc_html}'
            f'<ul class="handles">{"".join(items)}</ul>'
            '</section>')
    return '\n'.join(parts)


def schedule_answer(lang, utc, hkt, faq_zh, data_tr, about_tr):
    """Prefer the FAQ sentence when it already states this cron; otherwise the cron."""
    made = fill(SCHED_TMPL, utc=zh_join(utc), hkt=zh_join(hkt))
    if made == faq_zh:
        src = faq_zh
    else:
        warn('update-site.yml cron does not match the FAQ update answer; using the cron')
        src = made
    if lang == 'zh':
        return src
    if src in data_tr:
        return data_tr[src]
    if src == made:
        tmpl = about_tr.get(SCHED_TMPL)
        if tmpl:
            utc_s = en_join(utc) if lang == 'en' else ', '.join(utc)
            hkt_s = en_join(hkt) if lang == 'en' else ', '.join(hkt)
            return fill(tmpl, utc=utc_s, hkt=hkt_s)
    warn(f'{lang} has no translation for the update-frequency answer')
    return src


def faq_html(lang, faqs, utc, hkt, data_tr, about_tr):
    blocks = []
    for q in faqs:
        name = tr_text(q['name'], lang, data_tr, about_tr)
        if q['name'] == UPDATE_Q:
            text = schedule_answer(lang, utc, hkt, q['text'], data_tr, about_tr)
        else:
            text = tr_text(q['text'], lang, data_tr, about_tr)
        if q['name'] == DISCLAIM_Q:
            label = tr_text('非投資建議', lang, data_tr, about_tr)
            body = f'<aside class="note"><b>{esc(label)}</b><p>{esc(text)}</p></aside>'
        else:
            body = f'<p>{esc(text)}</p>'
        blocks.append(f'<section class="faq"><h2>{esc(name)}</h2>{body}</section>')
    return '\n'.join(blocks)


def page(template, lang, blocks):
    cur = {k: (' aria-current="page"' if k == lang else '') for k in LANGS}
    html_s = template.replace('{{lang}}', LANGS[lang]).replace('{{lang_code}}', lang)
    html_s = html_s.replace('{{canon}}', f'{SITE}{lang}/about/')
    html_s = html_s.replace('{{home}}', f'/{lang}/')
    for k, mark in cur.items():
        html_s = html_s.replace('{{cur_%s}}' % k, mark)
    html_s = apply(html_s, table(lang, 'about'))
    html_s = html_s.replace('{{accounts}}', blocks[lang]['accounts'])
    html_s = html_s.replace('{{faq}}', blocks[lang]['faq'])
    if '{{' in html_s:
        warn(f'{lang} about page still has a placeholder')
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


def sitemap():
    path = os.path.join(ROOT, 'sitemap.xml')
    if not os.path.exists(path):
        return
    sm = open(path, encoding='utf-8').read()
    sm = re.sub(r'\s*<url><loc>' + re.escape(SITE) + r'(?:(?:zh|en|ko)/)?about/</loc>.*?</url>', '', sm, flags=re.S)
    gen = re.search(r'<loc>' + re.escape(SITE) + r'</loc><lastmod>([^<]+)', sm)
    last = gen.group(1) if gen else ''
    alt = ''.join(f'<xhtml:link rel="alternate" hreflang="{LANGS[k]}" href="{SITE}{k}/about/"/>' for k in LANGS)
    rows = ''.join(
        f'\n  <url><loc>{SITE}{k}/about/</loc><lastmod>{last}</lastmod><changefreq>monthly</changefreq>{alt}</url>'
        for k in LANGS)
    sm = sm.replace('</urlset>', rows + '\n</urlset>')
    sm = dedupe_sitemap(sm)
    if not sm.endswith('\n'):
        sm += '\n'
    open(path, 'w', encoding='utf-8').write(sm)
    print('sitemap about')


def main():
    os.chdir(ROOT)
    master, dash = load_dash()
    faqs = load_faq(master)
    utc, hkt = cron_clocks()
    tracked = dash['tracked']
    n = len(tracked['accounts'])
    print(f'about: {n} accounts, platforms {dict(Counter(plat_of(a) for a in tracked["accounts"]))}, '
          f'{len(tracked["categories"])} categories, cron UTC {", ".join(utc)} / HKT {", ".join(hkt)}')
    blocks = {}
    for lang in LANGS:
        data_tr = table(lang, 'data')
        about_tr = table(lang, 'about')
        blocks[lang] = {
            'accounts': accounts_html(lang, tracked, data_tr, about_tr),
            'faq': faq_html(lang, faqs, utc, hkt, data_tr, about_tr),
        }
    template = open(os.path.join(ROOT, 'tools', 'about.html'), encoding='utf-8').read()
    zh = page(template, 'zh', blocks)
    write('about/index.html', with_root_redirect(zh, 'about'))
    write('zh/about/index.html', zh)
    for lang in ('en',):
        html_s = page(template, lang, blocks)
        body = re.sub(r'<nav class="lang".*?</nav>', '', html_s, flags=re.S)
        left = HAN.findall(body)
        if left:
            warn(f'{lang} about page still has Chinese: {"".join(left[:12])}')
        write(f'{lang}/about/index.html', html_s)
    sitemap()


if __name__ == '__main__':
    main()
