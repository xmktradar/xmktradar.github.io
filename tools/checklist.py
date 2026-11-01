"""Write the earnings checklist lead-magnet pages (ZH+EN).

Chinese master lives in tools/checklist.html with {{placeholders}}.
Writes checklist/earnings/ (root → zh redirect), zh|en/checklist/earnings/,
and lists the language URLs in sitemap.xml.
"""
import os
import re

from build_langs import lang_pick_js

SITE = 'https://thecrowdtape.com/'
LANGS = {'zh': 'zh-Hant', 'en': 'en'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAN = re.compile(r'[\u4e00-\u9fff]')

def with_nested_root_redirect(html, path):
    """Like with_root_redirect but allows nested paths (e.g. checklist/earnings)."""
    seg = path.strip('/')
    if not re.fullmatch(r'[a-z]+(?:/[a-z]+)*', seg):
        raise ValueError(path)
    script = ('<script>(function(){if(!/(github\\.io|thecrowdtape\\.com)$/.test(location.hostname))return;'
              + lang_pick_js('localStorage.getItem("ct-lang")')
              + f'location.replace("/"+l+"/{seg}/"+location.search+location.hash)'
              + '})();</script>')
    if '</head>' not in html:
        raise ValueError('no </head> in ' + path)
    return html.replace('</head>', script + '</head>', 1)



COPY = {
    'zh': dict(
        title='財報解讀清單（免費）｜The Crowd Tape',
        desc='公布前、公布中、公布後要睇咩：收入／EPS／指引／語氣，再對照 Crowd Tape 好淡。免費電郵領取完整清單。',
        h1='免費財報解讀清單',
        lead='一頁實用 checklist：開市前點準備、聽會時記咩、收市後點對照群眾好淡。留低電郵即睇完整版（歡迎電郵亦會附連結）。',
        preview_label='預覽',
        preview_h2='裡面有什麼（預覽）',
        preview_items=[
            '公布前：共識收入／EPS、指引預期、選擇權隱含波動',
            '公布中：實際 vs 預期、guidance 方向、管理層語氣',
            '公布後：股價反應 vs Crowd Tape 好淡，有冇「預期差」',
        ],
        full_h2='完整財報解讀清單',
        full_items=[
            '公布前：寫低共識收入、EPS、YoY；有冇「必須 beat」的 implicit bar',
            '公布前：睇下一次指引共識；市場最怕邊句 guidance',
            '公布前：查選擇權 IV／straddle，估吓股價「應該」震幾多',
            '公布前：開 Crowd Tape 睇呢隻股近幾日好淡同重點帳號說法',
            '公布中：收入／EPS 實際 vs 預期；beat／miss 幅度',
            '公布中：guidance（收入／EPS／毛利率）上調、持平定下調',
            '公布中：管理層語氣——防守、進取、定避談需求',
            '公布中：業務線／地區有冇結構性變化（唔好只睇 headline）',
            '公布後：盤後／翌日股價同成交，係咪「好數壞走」定「差數好走」',
            '公布後：對照 Crowd Tape——群眾提早睇啱定一窩蜂追價',
            '公布後：更新你自己的 thesis：加倉、減倉定觀望條件',
            '公布後：如有期權結構，用 OptionStrat 核對損益圖（見／tools）',
        ],
        form_title='免費領取財報解讀清單',
        form_btn='電郵領取',
        form_note='唔會濫發，隨時取消。',
        welcome_note='提示：請把本頁加入書籤；歡迎電郵（Resend）應附上同一連結：https://thecrowdtape.com/zh/checklist/earnings/ — 若未設定自動 welcome，CEO 可於 Resend 手動加。',
        back_earnings='返回最新財報簡報',
        to_tools='我們用的工具',
        nav_label='網站',
        lang_nav='語言',
        earnings_nav='財報簡報',
        tools_nav='工具',
        support_nav='支持我們',
        home_nav='首頁',
        news_nav='電子報',
    ),
    'en': dict(
        title='Free earnings checklist | The Crowd Tape',
        desc='What to check before, during and after the print: revenue, EPS, guidance, tone — then compare with Crowd Tape. Email for the full list.',
        h1='Free earnings print checklist',
        lead='One practical page: prepare before the open, note the call, then compare the tape with the crowd. Leave your email to unlock the full list (welcome email will include the same link).',
        preview_label='Preview',
        preview_h2='What’s inside (preview)',
        preview_items=[
            'Before: consensus revenue/EPS, guidance bar, options-implied move',
            'During: actual vs estimate, guidance direction, management tone',
            'After: price reaction vs Crowd Tape bull/bear — any expectation gap?',
        ],
        full_h2='Full earnings checklist',
        full_items=[
            'Before: write down consensus revenue, EPS, YoY; any “must-beat” bar',
            'Before: next-quarter guidance consensus; which line the market fears',
            'Before: check options IV / straddle for the “expected” move size',
            'Before: open Crowd Tape for this ticker’s recent bull/bear and key voices',
            'During: revenue/EPS actual vs estimate; size of beat/miss',
            'During: guidance (revenue/EPS/margins) raised, flat, or cut',
            'During: management tone — defensive, assertive, or dodging demand',
            'During: segment/region mix shifts (don’t stop at the headline)',
            'After: after-hours / next-day price & volume — “good number, bad tape”?',
            'After: compare with Crowd Tape — did the crowd call it early or chase?',
            'After: update your thesis: add, trim, or wait — with conditions',
            'After: if you use options, sanity-check the payoff on OptionStrat (/tools)',
        ],
        form_title='Get the free earnings checklist',
        form_btn='Email me the list',
        form_note='No spam. Unsubscribe anytime.',
        welcome_note='Tip: bookmark this page. Welcome email (Resend) should include: https://thecrowdtape.com/en/checklist/earnings/ — if auto-welcome is not set, CEO can add it in Resend.',
        back_earnings='Back to latest earnings briefs',
        to_tools='Tools we use',
        nav_label='Site',
        lang_nav='Language',
        earnings_nav='Earnings',
        tools_nav='Tools',
        support_nav='Support us',
        home_nav='Home',
        news_nav='Newsletter',
    ),
}


def lis(items, tag='li'):
    return '\n      '.join(f'<{tag}>{item}</{tag}>' for item in items)


def page(template, lang):
    c = COPY[lang]
    cur = {k: (' aria-current="page"' if k == lang else '') for k in LANGS}
    html = template
    repl = {
        '{{lang}}': LANGS[lang],
        '{{lang_code}}': lang,
        '{{canon}}': f'{SITE}{lang}/checklist/earnings/',
        '{{home}}': f'/{lang}/',
        '{{title}}': c['title'],
        '{{desc}}': c['desc'],
        '{{h1}}': c['h1'],
        '{{lead}}': c['lead'],
        '{{preview_label}}': c['preview_label'],
        '{{preview_h2}}': c['preview_h2'],
        '{{preview_items}}': lis(c['preview_items']),
        '{{full_h2}}': c['full_h2'],
        '{{full_items}}': lis(c['full_items']),
        '{{form_title}}': c['form_title'],
        '{{form_btn}}': c['form_btn'],
        '{{form_note}}': c['form_note'],
        '{{welcome_note}}': c['welcome_note'],
        '{{back_earnings}}': c['back_earnings'],
        '{{to_tools}}': c['to_tools'],
        '{{nav_label}}': c['nav_label'],
        '{{lang_nav}}': c['lang_nav'],
        '{{earnings_nav}}': c['earnings_nav'],
        '{{tools_nav}}': c['tools_nav'],
        '{{support_nav}}': c['support_nav'],
        '{{home_nav}}': c['home_nav'],
        '{{news_nav}}': c['news_nav'],
        '{{cur_zh}}': cur['zh'],
        '{{cur_en}}': cur['en'],
    }
    for k, v in repl.items():
        html = html.replace(k, v)
    if '{{' in html:
        print(f'::warning::{lang} checklist still has a placeholder')
    return html


def write(path, html):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w', encoding='utf-8').write(html)
    print(path)


def dedupe_sitemap(sm):
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
    sm = re.sub(
        r'\s*<url><loc>' + re.escape(SITE) + r'(?:(?:zh|en)/)?checklist/earnings/</loc>.*?</url>',
        '', sm, flags=re.S)
    gen = re.search(r'<loc>' + re.escape(SITE) + r'</loc><lastmod>([^<]+)', sm)
    last = gen.group(1) if gen else ''
    alt = ''.join(
        f'<xhtml:link rel="alternate" hreflang="{LANGS[k]}" href="{SITE}{k}/checklist/earnings/"/>'
        for k in LANGS)
    alt += f'<xhtml:link rel="alternate" hreflang="x-default" href="{SITE}zh/checklist/earnings/"/>'
    rows = ''.join(
        f'\n  <url><loc>{SITE}{k}/checklist/earnings/</loc><lastmod>{last}</lastmod>'
        f'<changefreq>monthly</changefreq>{alt}</url>'
        for k in LANGS)
    sm = sm.replace('</urlset>', rows + '\n</urlset>')
    sm = dedupe_sitemap(sm)
    if not sm.endswith('\n'):
        sm += '\n'
    open(path, 'w', encoding='utf-8').write(sm)
    print('sitemap checklist')


def main():
    os.chdir(ROOT)
    template = open(os.path.join(ROOT, 'tools', 'checklist.html'), encoding='utf-8').read()
    zh = page(template, 'zh')
    write('checklist/earnings/index.html', with_nested_root_redirect(zh, 'checklist/earnings'))
    write('zh/checklist/earnings/index.html', zh)
    en = page(template, 'en')
    body = re.sub(r'<nav class="lang".*?</nav>', '', en, flags=re.S)
    left = HAN.findall(body)
    if left:
        print(f'::warning::en checklist still has Chinese: {"".join(left[:12])}')
    write('en/checklist/earnings/index.html', en)
    sitemap()


if __name__ == '__main__':
    main()
