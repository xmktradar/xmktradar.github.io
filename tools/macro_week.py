"""Saturday "this week in macro" social posts (Tim, 2026-10-13; spec weekly-macro-post-spec.md).

Same numbers as the site's 宏觀 tab (index.html viewMacro): macro posts from the last 7 days (HKT dates), grouped by
theme (SuperGrok's macro_theme, else the keyword theme macro_kw), each account's latest stance on the theme
(macro_impact), compared with the 7 days before. No AI: the captions are fixed sentences filled with these numbers
and one SuperGrok summary per theme.

On Saturday the first update from 15:00 HKT freezes the week's numbers (data/macro-week.json, frozen: true) so all
three languages, posted 20:00 / 20:30 / 21:00 HKT, tell the same story. On other days it builds a preview for the
next Saturday once a day. `date` is that Saturday (today when it is Saturday, otherwise the coming Saturday).
It is the posting day, including when the file is a preview and `date` is still in the future. `from`/`to` are
the 7-day data window and are not the posting day. ig_reel.date_kst is the Asia/Seoul date of 20:00 HKT on
`date` (21:00 KST, same calendar day). Writes data/macro-week.json, social/macro.html and work/macro_week.json for
tools/macro_week.js, which draws og/macro-<lang>.png and og/macro-story-<lang>.png.
MACRO_WEEK_FORCE=1 rebuilds now on any day (for checking).
"""
import html
import os
import re
from datetime import date, timedelta

from sitedata import load, notice, now_hk, read_json, work, write_json
from share import fit_threads, page_url, sanitize_instagram, xlen

SITE = 'https://thecrowdtape.com/'
LANGS = ('zh', 'en')
FREEZE_HOUR = 15
MIN_STANCED = 3  # a theme needs this many accounts with a stance to be one of the week's top 3
THEMES = ('rates', 'inflation', 'jobs', 'growth', 'yields', 'fx', 'energy', 'policy', 'other')
NAMES = {
    'zh': {'rates': '利率／聯儲局', 'inflation': '通脹', 'jobs': '就業', 'growth': '經濟增長／衰退', 'yields': '債息',
           'fx': '美元／匯率', 'energy': '油價／能源', 'policy': '關稅／政策／地緣政治', 'other': '其他'},
    'en': {'rates': 'Rates / Fed', 'inflation': 'Inflation', 'jobs': 'Jobs', 'growth': 'Growth / recession',
           'yields': 'Bond yields', 'fx': 'Dollar / FX', 'energy': 'Oil / energy', 'policy': 'Tariffs / policy / geopolitics',
           'other': 'Other'},
}
IMP = {'bullish': 'bull', 'bearish': 'bear', 'neutral': 'neu'}
TXT = {
    'zh': dict(head='這星期我們追蹤的 {N} 個 X 帳號，最常聊的宏觀話題是這幾個', short='這星期大家最常聊的宏觀話題', bull='利好', bear='利淡', neu='中性',
               up='比上週轉好 ▲', dn='比上週轉差 ▼', flat='同上週差唔多', none='上週未有數據',
               intro='', quiet='這星期談宏觀的人不多，各帳號的最新說法都整理在網站上。',
               more='9 個主題全部喺呢度 👉 ',
               give='☕ 鍾意就支持我哋：bio 連結，網站底部 PayPal 🙏', give_s='☕ 鍾意就支持我哋 👉 ',
               follow='Follow @thecrowdtape，逢星期六出一週宏觀總結。', disc='⚠️ 唔構成投資建議',
               disc_long='⚠️ 只係整理公開社交媒體貼文，唔構成投資建議。投資有風險，請自行判斷。',
               tags='#美股 #宏觀經濟 #聯儲局 #港人投資 #美股投資 #USStocks #Macro #StockMarket #投資'),
    'en': dict(head='The macro topics the {N} X accounts we follow talked about most this week', short='What X talked about in macro this week',
               bull='bullish', bear='bearish', neu='neutral', up='better than last week ▲', dn='worse than last week ▼',
               flat='about the same as last week', none='no data for last week yet',
               intro='',
               quiet='Not many macro views this week. Each account\'s latest take is on our site.',
               more='All 9 topics 👉 ',
               give='☕ Enjoy it? Buy us a coffee: link in bio, PayPal at the bottom of the site 🙏', give_s='☕ Support the site 👉 ',
               follow='Follow @thecrowdtape for a macro roundup every Saturday.', disc='⚠️ Not investment advice',
               disc_long='⚠️ A summary of public social media posts, not investment advice. Investing involves risk; do your own research.',
               tags='#Macro #StockMarket #USStocks #Fed #Economy #Investing #FinTwit #WallStreet'),
}
SUMKEY = {'zh': 'zh_summary', 'en': 'en_summary'}
NUM = ['1.', '2.', '3.']  # plain numbers, no emoji (Tim, 2026-10-29)


def theme_of(p):
    return p['macro_theme'] if 'macro_theme' in p else p.get('macro_kw')


def stat(posts, th, d0, d1):
    ps = [p for p in posts if d0 <= p['time_hkt'][:10] <= d1 and theme_of(p) == th]
    last, last_s = {}, {}
    for p in sorted(ps, key=lambda p: p['time_utc']):
        acc = p.get('reposted_by') or p['handle']
        last[acc] = p
        if IMP.get(p.get('macro_impact')):
            last_s[acc] = p
    c = {'bull': 0, 'bear': 0, 'neu': 0}
    for p in last_s.values():
        c[IMP[p['macro_impact']]] += 1
    return {'accounts': len(last), 'n': sum(c.values()), **c, 'stanced': sorted(last_s.items(), key=lambda kv: kv[1]['time_utc'], reverse=True)}


def arrow(s, s0):
    """Same rule as the site: bullish minus bearish share moves more than 15 points; needs 2+ stances last week."""
    if s['n'] < 1 or s0['n'] < 2:
        return 'none'
    sc = lambda x: (x['bull'] - x['bear']) / x['n']
    d = sc(s) - sc(s0)
    return 'up' if d > 0.15 else 'dn' if d < -0.15 else 'flat'


def cut(t, n):
    t = re.sub(r'\s+', ' ', str(t or '')).strip()
    return t if len(t) <= n else t[:n - 1].rstrip(' ，,。.') + '…'


TAIL = re.compile(r'\s*(沒有提及個股。|No specific stock mentioned\.|No new market view\.)\s*$')


def quote_text(t, acc):
    """A summary as a quote: without a leading '(Reposted by @x)' and the 'no stock mentioned' ending."""
    t = re.sub(r'^\s*[（(][^）)]{0,40}[）)]\s*', '', t.strip())
    while TAIL.search(t):
        t = TAIL.sub('', t)
    return t.strip()


def week(d, end):
    posts = [p for p in d['posts'] if p.get('macro') and not p.get('folded_into') and p.get('theme') != '非市場']
    d1, d0 = end.isoformat(), (end - timedelta(days=6)).isoformat()
    p1, p0 = (end - timedelta(days=7)).isoformat(), (end - timedelta(days=13)).isoformat()
    rows = []
    for th in THEMES:
        s, s0 = stat(posts, th, d0, d1), stat(posts, th, p0, p1)
        quotes = {}
        for lang in LANGS:
            q = next(((acc, p) for acc, p in s['stanced'] if (p.get(SUMKEY[lang]) or '').strip()), None)
            if q:
                quotes[lang] = {'acc': q[0], 'impact': IMP[q[1]['macro_impact']], 'text': quote_text(q[1][SUMKEY[lang]], q[0]), 'url': q[1]['url']}
        rows.append({'theme': th, 'accounts': s['accounts'], 'n': s['n'], 'bull': s['bull'], 'bear': s['bear'], 'neu': s['neu'],
                     'arrow': arrow(s, s0), 'quotes': quotes})
    top = sorted((r for r in rows if r['n'] >= MIN_STANCED), key=lambda r: (-r['n'], -r['accounts'], THEMES.index(r['theme'])))[:3]
    return {'from': d0, 'to': d1, 'themes': rows, 'top': [r['theme'] for r in top]}


def _whole(n):
    if isinstance(n, bool) or not isinstance(n, (int, float)):
        return None
    return int(n) if float(n) == int(n) else n


def macro_ig_key_line(lang, w):
    """Instagram line 1: the most-discussed theme with its bull and bear counts.

    zh '本週宏觀：最多人講「其他」（利好 10・利淡 11）'. The theme is w['top'][0]
    and the counts are that theme's bull/bear. Empty when the row is missing.
    """
    if lang not in LANGS:
        lang = 'en'
    if not isinstance(w, dict):
        return ''
    top = w.get('top') or []
    theme = top[0] if top else ''
    if not theme:
        return ''
    row = next((r for r in (w.get('themes') or []) if isinstance(r, dict) and r.get('theme') == theme), None)
    if not row:
        return ''
    bull, bear = _whole(row.get('bull')), _whole(row.get('bear'))
    if bull is None or bear is None:
        return ''
    name = NAMES.get(lang, NAMES['en']).get(theme) or str(theme)
    if lang == 'zh':
        return f'本週宏觀：最多人講「{name}」（利好 {bull}・利淡 {bear}）'
    return f'This week in macro: most discussed "{name}" (bullish {bull} · bearish {bear})'


def counts(lang, r):
    L = TXT[lang]
    return f"{L['bull']} {r['bull']}・{L['bear']} {r['bear']}・{L['neu']} {r['neu']}" if lang == 'zh' else \
        f"{L['bull']} {r['bull']} · {L['bear']} {r['bear']} · {L['neu']} {r['neu']}"


def posts(lang, w, rng):
    L, N = {k: v.replace('{N}', str(w['accounts'])) for k, v in TXT[lang].items()}, NAMES[lang]
    url = page_url(lang, '#macro')
    give = f"{L['give_s']}{page_url(lang, '#donate')}"
    by = {r['theme']: r for r in w['themes']}
    head = f"{L['head']}（{rng}）" if lang == 'zh' else f"{L['head']} ({rng})"
    blocks = []
    for i, th in enumerate(w['top']):
        r = by[th]
        line = f"{NUM[i]} {N[th]}：{counts(lang, r)}（{L[r['arrow']]}）" if lang == 'zh' else \
            f"{NUM[i]} {N[th]}: {counts(lang, r)} ({L[r['arrow']]})"
        q = r['quotes'].get(lang)
        say = ''
        if q:
            t = cut(q['text'], {'zh': 90, 'en': 150}[lang])
            # Summaries often open with the account's own @handle: then show them as they are.
            say = f"💬 {t}" if t.lower().startswith('@' + q['acc'].lower()) else \
                f"💬 @{q['acc']}：「{t}」" if lang == 'zh' else f"💬 @{q['acc']}: “{t}”"
        blocks.append((line, say))
    body = '\n\n'.join([x for x in [L['intro']] if x] + ['\n'.join(x for x in b if x) for b in blocks]) if blocks else L['quiet']
    tags = L['tags']
    # Line 1 is the top theme and its counts. The old heading and every theme block stay under it.
    key = macro_ig_key_line(lang, w)
    ig = sanitize_instagram('\n\n'.join(p for p in (key, head, body, L['give'], L['follow'], L['disc_long'], tags) if p), lang)
    fb = '\n\n'.join([head, body, L['more'] + url, give, L['follow'], L['disc_long'], tags])
    # Threads: 500 characters; drop the quotes, then the intro, if too long.
    short_body = '\n'.join(b[0] for b in blocks) if blocks else L['quiet']
    threads = None
    for b in (body, '\n\n'.join([x for x in [L['intro'], short_body] if x]) if blocks else body, short_body):
        threads = '\n\n'.join([head, b, f"{L['more']}{url}\n{give}\n{L['disc']}", tags.split(' ')[0]])
        if len(threads) <= 480:
            break
    threads = fit_threads(threads, lang)
    # X: 280 with CJK counted double.
    xtags = ' '.join(tags.split(' ')[:3])
    tiny = '\n'.join(f"{N[th]} {by[th]['bull']}/{by[th]['bear']}/{by[th]['neu']}" for th in w['top'])
    legend = {'zh': '（利好／利淡／中性）', 'en': '(bullish/bearish/neutral)'}[lang]
    x = None
    for parts in ([L['short'], short_body, f"{L['more']}{url}\n{L['disc']}", xtags],
                  [L['short'], (tiny + '\n' + legend) if blocks else L['quiet'], f"{L['more']}{url}\n{L['disc']}", xtags],
                  [L['short'], f"{L['more']}{url}\n{L['disc']}", xtags],
                  [L['short'], url, tags.split(' ')[0]]):
        x = '\n\n'.join(parts)
        if xlen(x) <= 270:
            break
    reddit = {'title': re.sub(r'^🌐\s*', '', head),
              'body': '\n\n'.join([body.replace('1️⃣ ', '1. ').replace('2️⃣ ', '2. ').replace('3️⃣ ', '3. '),
                                   f"{L['more']}[{url}]({url})", f"{L['give_s']}[{page_url(lang, '#donate')}]({page_url(lang, '#donate')})",
                                   L['disc_long'], tags])}
    return {'instagram': ig, 'threads': threads, 'x': x, 'reddit': reddit, 'facebook': fb, 'story': ' '.join(tags.split(' ')[:5])}


def page(mw):
    rows = []
    for lang, name in (('zh', '中文'), ('en', 'English')):
        img, story, p = mw['images'][lang], mw['stories'][lang], mw['posts'][lang]
        box = lambda title, text, n: (f'<h3>{title}</h3><textarea readonly rows="{n}">{html.escape(text)}</textarea>'
                                      '<button onclick="navigator.clipboard.writeText(this.previousElementSibling.value);this.textContent=\'已複製 ✓\'">複製</button>')
        rows.append(f'''<section><h2>{name}</h2><a href="{html.escape(img)}" download><img src="{html.escape(img)}" alt=""></a>
{box('Instagram', p['instagram'], 18)}{box('Threads', p['threads'], 10)}{box('X', p['x'], 7)}
{box('Reddit 標題', p['reddit']['title'], 2)}{box('Reddit 內文', p['reddit']['body'], 14)}{box('Facebook', p['facebook'], 18)}
{box('IG Story hashtag', p['story'], 2)}<h3>IG Story（1080×1920）</h3><a href="{html.escape(story)}" download><img class="story" src="{html.escape(story)}" alt=""></a></section>''')
    state = ('今日係星期六，數字已經定咗，20:00 中文、20:30 英文照貼。' if mw['frozen'] else
             f"預覽：{mw['date']}（星期六）15:00 後第一次更新先會定數字，之前每日更新一次。")
    return f'''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="/favicon.ico" sizes="any"><link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="robots" content="noindex"><title>星期六宏觀貼文 {mw['date']}｜The Crowd Tape</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;margin:0 auto;max-width:760px;padding:16px;background:#f7f8fb;color:#151a2c;overflow-wrap:anywhere}}
html{{overflow-x:clip}}
section{{background:#fff;border-radius:14px;padding:16px;margin:16px 0;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
img{{width:100%;border-radius:10px}}img.story{{width:min(100%,320px);display:block;margin-top:6px}}textarea{{width:100%;box-sizing:border-box;font:inherit;margin-top:4px}}h3{{margin:18px 0 0;font-size:15px}}
button{{margin-top:8px;padding:8px 16px;border-radius:999px;border:0;background:#151a2c;color:#fff;font:inherit}}
.money-bar,.site-nav{{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;max-width:100%;min-width:0}}
.money-bar{{margin:0 0 12px;padding:8px 10px;border:1px dashed #c9c3b8;border-radius:12px;background:#fff;font-size:14px;font-weight:700}}
.tag{{font-size:11px;font-weight:700;border:1px solid #ddd;border-radius:999px;padding:1px 8px;color:#666}}
.site-foot{{margin-top:18px;padding-top:12px;border-top:1px solid #e4e7ef;font-size:13px;color:#5c6578}}
a{{color:#8a5a22}}</style>
<nav class="site-nav" aria-label="網站"><a href="/zh/tools/">工具</a> · <a href="/zh/support/">支持我哋</a></nav>
<nav class="money-bar" aria-label="推廣"><span class="tag">推廣</span><a href="/zh/tools/">工具</a><a href="/zh/support/">支持我哋</a><a href="https://www.tradingview.com/?aff_id=1172819" rel="sponsored noopener" target="_blank" data-tool="tradingview" data-placement="money-bar">TradingView</a><a href="https://www.stockrover.com/thecrowdtape" rel="sponsored nofollow noopener" target="_blank" data-tool="stockrover" data-placement="money-bar">Stock Rover</a></nav>
<h1>{mw['date']} 星期六宏觀貼文（{mw['from']} 至 {mw['to']}）</h1>
<p>{state}製作時間 {mw['made_hkt']} HKT｜撳圖片可以下載｜<a href="/social/">平日快照貼文</a>｜<a href="/social/tutorial.html">週末教學貼文</a></p>
{''.join(rows)}
<footer class="site-foot"><p><a href="/zh/tools/">工具</a> · <a href="/zh/support/">支持我哋</a> · <a href="/zh/newsletter/">電子報</a> · <a href="https://www.tradingview.com/?aff_id=1172819" rel="sponsored noopener" target="_blank" data-tool="tradingview">TradingView <span class="tag">推廣</span></a> · <a href="https://www.stockrover.com/thecrowdtape" rel="sponsored nofollow noopener" target="_blank" data-tool="stockrover">Stock Rover <span class="tag">推廣</span></a></p></footer>
<script>document.addEventListener('click',function(e){{var a=e.target.closest&&e.target.closest('a[data-tool]');if(a&&window.gtag)gtag('event','affiliate_click',{{tool:a.dataset.tool,lang:document.documentElement.lang}});}});</script>
</html>
'''


def main():
    now = now_hk()
    today = now.date()
    old = read_json('data/macro-week.json', {})
    sat = today + timedelta(days=(5 - today.weekday()) % 7)  # this Saturday, or today when it is Saturday
    freeze = today.weekday() == 5 and now.hour >= FREEZE_HOUR
    force = os.environ.get('MACRO_WEEK_FORCE') == '1'
    if not force:
        if old.get('date') == today.isoformat() and old.get('frozen'):
            print('macro week: frozen for today')
            return
        if not freeze and old.get('date') == sat.isoformat() and str(old.get('made_hkt', ''))[:10] == today.isoformat():
            print('macro week: preview already made today')
            return
    end = today if (freeze or force) else min(today, sat)
    d = load('index.html')
    w = week(d, end)
    w['accounts'] = len(d['tracked']['accounts'])  # the tracked list grows in batches (2026-10-13), so never hard-code 100
    rng = f"{int(w['from'][5:7])}/{int(w['from'][8:])}–{int(w['to'][5:7])}/{int(w['to'][8:])}"
    v = f"{sat.isoformat()}-{now.strftime('%H%M')}"
    mw = {'date': sat.isoformat(), 'frozen': freeze, 'made_hkt': now.strftime('%Y-%m-%d %H:%M'), **w, 'range': rng,
          'images': {l: f'{SITE}og/macro-{l}.png?v={v}' for l in LANGS},
          'stories': {l: f'{SITE}og/macro-story-{l}.png?v={v}' for l in LANGS},
          'posts': {l: posts(l, w, rng) for l in LANGS}}
    write_json('data/macro-week.json', mw, indent=1)
    from ig_boost import apply_macro_file
    apply_macro_file('data/macro-week.json')
    mw = read_json('data/macro-week.json')  # apply_macro_file ends with tools/humanize.py: no links, plain wording
    os.makedirs('social', exist_ok=True)
    open('social/macro.html', 'w', encoding='utf-8').write(page(mw))
    write_json(work('macro_week.json'), {'range': rng, 'themes': w['themes'], 'top': w['top'], 'names': NAMES, 'accounts': w['accounts']})
    notice(f"星期六宏觀貼文{'（已定數）' if freeze else '（預覽）'}：{SITE}social/macro.html，頭 3 個主題 {', '.join(w['top']) or '無'}")


if __name__ == '__main__':
    main()
