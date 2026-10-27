"""Weekend "how to use the site" social posts (Tim, 2026-10-12).

One episode every Saturday and Sunday (HKT), 26 episodes from data/tutorial-episodes.json, looping from episode 1
after the last. Episode 1 is the first Saturday in the file's "start". The captions are fixed text written once
(no Grok); this script fills in the stock and account used as examples, builds the per-platform versions in the same
shape as data/social-posts.json and writes data/tutorial-posts.json, social/tutorial.html, and work/tutorial.json
for tools/tutorial.js, which screenshots the feature on the built site and draws og/tutorial-<lang>.png and
og/tutorial-story-<lang>.png. The Grok bot posts them verbatim at the same times as the weekday posts.

Runs after the language versions and stock pages are built. TUTORIAL_EPISODE=<n> rebuilds today's posts with
episode n (for checking a single episode); TUTORIAL_FORCE=1 rebuilds today's episode on any day.
"""
import html
import os
import re
from collections import Counter
from datetime import date, timedelta

from sitedata import load, notice, now_hk, read_json, work, write_json
from share import fit_threads, fit_threads_posts, page_url, xlen
from utm import normalize_file, tag_posts

SITE = 'https://thecrowdtape.com/'
LANGS = ('zh', 'en')
SOCIAL_HOUR = 7
NOT_STOCKS = {'SPY', 'QQQ', 'IWM', 'DIA', 'VOO', 'VTI', 'GLD', 'SLV', 'TLT', 'BTC', 'ETH', 'SOL', 'DXY', 'VIX', 'TQQQ', 'SQQQ'}

TXT = {
    'zh': dict(series='📘 The Crowd Tape 教學', how='👉 點用：', bio='網站免費，連結喺 bio 👉 thecrowdtape.com',
               give='☕ 鍾意就支持我哋：bio 連結，網站底部 PayPal 🙏', follow='Follow @thecrowdtape，逢星期六日教你用一個功能。',
               live='試吓 👉 ', give_s='☕ 鍾意就支持我哋 👉 ', disc='⚠️ 唔構成投資建議',
               disc_long='⚠️ 只係整理公開社交媒體貼文，唔構成投資建議。投資有風險，請自行判斷。',
               tags='#美股 #港人投資 #美股投資 #投資 #USStocks #StockMarket #香港投資 #投資教學 #美股新手'),
    'en': dict(series='📘 The Crowd Tape guide', how='👉 How: ', bio='The site is free. Link in bio 👉 thecrowdtape.com',
               give='☕ Enjoy it? Buy us a coffee: link in bio, PayPal at the bottom of the site 🙏',
               follow='Follow @thecrowdtape: one feature every Saturday and Sunday.',
               live='Try it 👉 ', give_s='☕ Support the site 👉 ', disc='⚠️ Not investment advice',
               disc_long='⚠️ A summary of public social media posts, not investment advice. Investing involves risk; do your own research.',
               tags='#StockMarket #USStocks #Stocks #Investing #FinTwit #WallStreet #InvestingTips #StocksForBeginners'),
}


def episode_for(day, start, total):
    """Episode number (1-based) for a HKT date, or None on weekdays and before the start."""
    if day.weekday() not in (5, 6) or day < start:
        return None
    weekends = (day - start).days // 7
    return (weekends * 2 + (day.weekday() == 6)) % total + 1


def pick_examples(d):
    """The most-discussed stock with its own page, and the busiest account, over the last 7 days."""
    days = sorted({p.get('day') for p in d['posts'] if p.get('day')})[-7:]
    recent = [p for p in d['posts'] if p.get('day') in days]
    accs = Counter(t for t, _ in {(t, p['handle']) for p in recent for t in p.get('tickers') or [] if isinstance(t, str)})
    tk = next((t for t, _ in accs.most_common() if t not in NOT_STOCKS and os.path.isdir(f'zh/stock/{t}')), None)
    tk = tk or next((t for t, _ in accs.most_common() if os.path.isdir(f'zh/stock/{t}')), 'NVDA')
    acc = Counter(p['handle'] for p in recent if p.get('tickers')).most_common(1)
    return tk, acc[0][0] if acc else 'elonmusk'


def fill(s, ex):
    for k, v in ex.items():
        s = s.replace('{' + k + '}', v)
    return s


def posts(lang, n, total, e, url):
    L = TXT[lang]
    head = f"{L['series']} {n}/{total}｜{e['t']}" if lang == 'zh' else f"{L['series']} {n}/{total} · {e['t']}"
    how = L['how'] + e['how']
    tags = L['tags']
    give_url = page_url(lang, '#donate')
    give = f"{L['give_s']}{give_url}"
    ig = '\n\n'.join([head, e['b'], how, L['bio'], L['give'], L['follow'], L['disc_long'], tags])
    fb = '\n\n'.join([head, e['b'], how, f"{L['live']}{url}", give, L['follow'], L['disc_long'], tags])
    # Threads: 500 characters, one topic tag. Drop the second paragraph of the body if it is too long.
    body = e['b']
    while True:
        threads = '\n\n'.join([head, body, how, f"{L['live']}{url}\n{give}\n{L['disc']}", tags.split(' ')[0]])
        if len(threads) <= 480 or '\n' not in body:
            break
        body = body.rsplit('\n', 1)[0]
    threads = fit_threads(threads, lang)
    # X: 280 with CJK counted double. Headline, link, hashtags; then the first body line, the how line and the
    # donation line while they still fit.
    xtags = ' '.join(tags.split(' ')[:3])
    first = e['b'].split('\n')[0]
    x = None
    for parts in ([head, first, f"{L['live']}{url}\n{give}\n{L['disc']}", xtags],
                  [head, first, f"{L['live']}{url}\n{L['disc']}", xtags],
                  [head, how, f"{L['live']}{url}\n{L['disc']}", xtags],
                  [head, f"{L['live']}{url}\n{L['disc']}", xtags],
                  [head, f"{L['live']}{url}", tags.split(' ')[0]]):
        x = '\n\n'.join(parts)
        if xlen(x) <= 270:
            break
    reddit = {'title': re.sub(r'^📘\s*', '', head),
              'body': '\n\n'.join([e['b'], how, f"{L['live']}[{url}]({url})", f"{L['give_s']}[{give_url}]({give_url})",
                                   L['disc_long'], tags])}
    return {'instagram': ig, 'threads': threads, 'x': x, 'reddit': reddit, 'facebook': fb,
            'story': ' '.join(tags.split(' ')[:5])}


def page(tp):
    rows = []
    for lang, name in (('zh', '中文'), ('en', 'English')):
        img, story, p = tp['images'][lang], tp['stories'][lang], tp['posts'][lang]
        box = lambda title, text, n: (f'<h3>{title}</h3><textarea readonly rows="{n}">{html.escape(text)}</textarea>'
                                      '<button onclick="navigator.clipboard.writeText(this.previousElementSibling.value);this.textContent=\'已複製 ✓\'">複製</button>')
        rows.append(f'''<section><h2>{name}</h2><a href="{html.escape(img)}" download><img src="{html.escape(img)}" alt=""></a>
{box('Instagram', p['instagram'], 16)}{box('Threads', p['threads'], 10)}{box('X', p['x'], 6)}
{box('Reddit 標題', p['reddit']['title'], 2)}{box('Reddit 內文', p['reddit']['body'], 12)}{box('Facebook', p['facebook'], 16)}
{box('IG Story hashtag', p['story'], 2)}<h3>IG Story（1080×1920）</h3><a href="{html.escape(story)}" download><img class="story" src="{html.escape(story)}" alt=""></a></section>''')
    return f'''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="/favicon.ico" sizes="any"><link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="robots" content="noindex"><title>週末教學貼文 {tp['date']}｜The Crowd Tape</title>
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
<h1>{tp['date']} 週末教學貼文：第 {tp['episode']}/{tp['total']} 集</h1>
<p>{'今日係星期六／日，要發呢集。' if tp['post_today'] else '今日唔係發佈日；下個星期六日先發新一集。'}製作時間 {tp['made_hkt']} HKT｜撳圖片可以下載｜<a href="/social/">平日快照貼文</a></p>
{''.join(rows)}
<footer class="site-foot"><p><a href="/zh/tools/">工具</a> · <a href="/zh/support/">支持我哋</a> · <a href="/zh/newsletter/">電子報</a> · <a href="https://www.tradingview.com/?aff_id=1172819" rel="sponsored noopener" target="_blank" data-tool="tradingview">TradingView <span class="tag">推廣</span></a> · <a href="https://www.stockrover.com/thecrowdtape" rel="sponsored nofollow noopener" target="_blank" data-tool="stockrover">Stock Rover <span class="tag">推廣</span></a></p></footer>
<script>document.addEventListener('click',function(e){{var a=e.target.closest&&e.target.closest('a[data-tool]');if(a&&window.gtag)gtag('event','affiliate_click',{{tool:a.dataset.tool,lang:document.documentElement.lang}});}});</script>
</html>
'''


def main():
    cfg = read_json('data/tutorial-episodes.json')
    eps, start = cfg['episodes'], date.fromisoformat(cfg['start'])
    now = now_hk()
    today = now.date()
    n = episode_for(today, start, len(eps))
    forced = os.environ.get('TUTORIAL_EPISODE')
    old = read_json('data/tutorial-posts.json', {})
    due = n and old.get('date') != today.isoformat() and now.hour >= SOCIAL_HOUR
    if forced:
        n = int(forced)
    elif (os.environ.get('TUTORIAL_FORCE') == '1' or not old) and not n:
        # Any day (and the first run ever): build the next weekend's episode so it can be checked ahead of time.
        nxt = next(today + timedelta(days=k) for k in range(1, 400) if episode_for(today + timedelta(days=k), start, len(eps)))
        n = episode_for(nxt, start, len(eps))
    elif not due and os.environ.get('TUTORIAL_FORCE') != '1':
        print('tutorial: nothing to do', today, n)
        return
    e = eps[n - 1]
    d = load('index.html')
    tk, acc = pick_examples(d)
    n_acc = str(len(d['tracked']['accounts']))  # captions say {N} accounts; the list grows in batches (2026-10-13)
    tp = {'date': today.isoformat(), 'made_hkt': now.strftime('%Y-%m-%d %H:%M'), 'episode': n, 'total': len(eps),
          'post_today': bool(episode_for(today, start, len(eps))), 'example': {'ticker': tk, 'account': acc},
          'images': {l: f'{SITE}og/tutorial-{l}.png?v={today}-{n}' for l in LANGS},
          'stories': {l: f'{SITE}og/tutorial-story-{l}.png?v={today}-{n}' for l in LANGS}, 'posts': {}}
    job = {'episode': n, 'total': len(eps), 'langs': {}}
    for lang in LANGS:
        ex = {'TK': tk, 'TKL': tk.lower()[:3], 'ACC': acc, 'LANG': lang, 'N': n_acc}
        txt = {k: fill(v, ex) for k, v in e[lang].items()}
        shot = {k: fill(v, ex) if isinstance(v, str) else v for k, v in e['shot'].items()}
        go = shot.get('go', '')
        url = page_url(lang, go)
        tp['posts'][lang] = posts(lang, n, len(eps), txt, url)
        job['langs'][lang] = {'title': txt['t'], 'how': txt['how'], 'shot': shot}
    tag_posts(tp['posts'], 'tutorial')
    fit_threads_posts(tp['posts'])
    write_json('data/tutorial-posts.json', tp, indent=1)
    normalize_file('data/tutorial-posts.json')
    tp = read_json('data/tutorial-posts.json')
    os.makedirs('social', exist_ok=True)
    open('social/tutorial.html', 'w', encoding='utf-8').write(page(tp))
    write_json(work('tutorial.json'), job)
    notice(f'週末教學貼文第 {n} 集已寫好：{SITE}social/tutorial.html')


if __name__ == '__main__':
    main()
