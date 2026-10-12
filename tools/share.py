"""Step 8b: share image data (one picture per language) and the daily social media posts.

Reads work/stats.json, the data in index.html and data/consensus-history.json.
Writes work/og.json for tools/og.js when a picture needs drawing, points the master page's
og:image at today's picture, and once a day (first update after 07:00 HKT) writes
data/social-posts.json and social/index.html: posts in Chinese, English and Korean for Instagram
(the @thecrowdtape format), Threads, X, Reddit and Facebook, for the Grok bot to post with og/social-<lang>.png,
plus a 1080x1920 Instagram Story picture og/story-<lang>.png. Every version asks readers to support the site (PayPal).
"""
import hashlib
import html
import json
import os
import re
from datetime import datetime

from sitedata import HK, load, notice, now_hk, read_json, work, write_json

HTML = 'index.html'
SITE = 'https://xmktradar.github.io/'
LANGS = ('zh', 'en', 'ko')
SOCIAL_HOUR = 7  # first update at or after this HKT hour writes the day's posts


def likes(p):
    v = str(p.get('likes') or '0').replace(',', '').strip().upper()
    m = re.match(r'([\d.]+)([KM]?)', v)
    return float(m.group(1)) * {'': 1, 'K': 1e3, 'M': 1e6}[m.group(2)] if m else 0


def clean(t, n):
    t = re.sub(r'https?://\S+', '', t or '')
    t = re.sub(r'\s+', ' ', t).strip()
    return t if len(t) <= n else t[:n - 1].rstrip() + '…'


def streak(days, day, t, key):
    """Days in a row, ending today, that t was in that day's list."""
    n, cur = 0, datetime.strptime(day, '%Y-%m-%d')
    while True:
        rec = days.get(cur.strftime('%Y-%m-%d'))
        if not rec or t not in rec.get(key, []):
            return n
        n += 1
        cur = datetime.fromordinal(cur.toordinal() - 1)


def hk(ms):
    return datetime.fromtimestamp(ms / 1000, HK)


def window(s):
    if s.get('first_ms') and s.get('last_ms'):
        a, b = hk(s['first_ms']), hk(s['last_ms'])
        return f"{a.month}/{a.day} {a:%H:%M} – {b.month}/{b.day} {b:%H:%M} HKT"
    return f"{s['from']} – {s['to']} HKT"


def quote(d, urls, t, lang):
    by = {p['url']: p for p in d['posts']}
    ps = [by[u] for u in urls if u in by]
    ps.sort(key=lambda p: (bool(p.get('reposted_by')), -likes(p)))
    for p in ps:
        txt = {'zh': p.get('zh_summary'), 'ko': p.get('ko_summary'),
               'en': p.get('en_summary') or p.get('text')}[lang]
        txt = re.sub(r'^\((?:Reposted|轉發|리포스트)\)\s*', '', txt or '')
        if txt:
            h = p['handle']
            a = d['accounts'].get(h, {}).get('avatar') or d.get('avmini', {}).get(h, '')
            return {'acc': h, 'text': clean(txt, 150 if lang == 'en' else 90), 'av': a, 'url': p['url']}
    return None


def build(d, s, ch, day):
    """Picture data per language, plus the facts the captions are written from."""
    days = ch.get('days', {})
    prices = d.get('prices', {})
    av = lambda h: d['accounts'].get(h, {}).get('avatar') or d.get('avmini', {}).get(h, '')

    def px(t):
        c = [r[1] for r in (prices.get(t) or {}).get('c', []) if r[1] is not None]
        return c[-22:], (round((c[-1] / c[-2] - 1) * 100, 2) if len(c) > 1 and c[-2] else None)

    bull = bool(s['bull'])
    if bull:
        groups = sorted(s['bull'], key=lambda g: -g['nb'])
        items = []
        for g in groups:
            accs = list(dict.fromkeys(r['acc'] for r in g['rows'] if r['s'] == 'bull'))
            items.append({'t': g['t'], 'n': g['nb'], 'bull': g['nb'], 'bear': g['nr'], 'accs': accs,
                          'urls': [r['url'] for r in g['rows'] if r['s'] == 'bull'],
                          'streak': streak(days, day, g['t'], 'bull')})
    else:
        items = [{'t': x['t'], 'n': x['accounts'], 'bull': x.get('bull_accounts', 0), 'bear': x.get('bear_accounts', 0),
                  'accs': x['accs'], 'urls': x.get('urls', []), 'streak': streak(days, day, x['t'], 'top')}
                 for x in s['top']]
    for x in items:
        x['spark'], x['d1'] = px(x['t'])
    top = [{k: x[k] for k in ('t', 'n', 'bull', 'bear', 'streak', 'spark', 'd1')} | {'avs': [av(h) for h in x['accs'][:4]]}
           for x in items[:4]]
    tape = [{'t': x['t'], 'd1': x['d1']} for x in items[:12] if x['d1'] is not None]
    while tape and len(tape) < 10:
        tape = tape + tape
    hero = items[0] if items else None
    win = window(s)
    out = {}
    for lang in LANGS:
        out[lang] = {'mode': 'bull' if bull else 'talk', 'date': day, 'win': win, 'acc': s['accounts'], 'posts': s['posts'],
                     'n_tk': s.get('tickers', len(s['top'])), 'bull_n': len(s['bull']), 'bear_n': len(s['bear']),
                     'top': top, 'tape': tape[:20], 'quote': quote(d, hero['urls'], hero['t'], lang) if hero else None}
    return out, items


def tags(lang, tks):
    base = {'zh': '#美股 #港人投資 #美股投資 #投資 #USStocks #StockMarket #香港投資',
            'en': '#StockMarket #USStocks #Stocks #Investing #FinTwit #WallStreet',
            'ko': '#미국주식 #미장 #해외주식 #주식 #투자 #USStocks'}[lang]
    return base + ''.join(f' #{t}' for t in tks[:5] if re.fullmatch(r'[A-Z]{1,6}', t))


def mix(x, wrap, both, bull, bear):
    """How many of the accounts were bullish or bearish, leaving out a side with none."""
    b, r = x['bull'], x['bear']
    if not b and not r:
        return ''
    return wrap.format(both.format(b, r) if b and r else (bull.format(b) if b else bear.format(r)))


def caption(lang, day, s, items, win, quote_):
    m, dd = int(day[5:7]), int(day[8:10])
    bull = bool(s['bull'])
    T = lambda t: f'${t}'
    sep = '、 ' if lang == 'zh' else (', ' if lang == 'en' else ', ')
    lines = []
    if lang == 'zh':
        acc = lambda n: f'{n} 個帳號'
        if bull:
            h = items[0]
            lines.append(f'{m}/{dd} X 大神共識快照： {T(h["t"])} {acc(h["n"])}一齊睇好 📊')
        else:
            h = items[0] if items else None
            lines.append(f'{m}/{dd} X 大神快照：今日最多人講 {T(h["t"])}（{acc(h["n"])}）💬' if h else f'{m}/{dd} X 大神快照 💬')
        lines += ['', f'數據範圍：{win}', '']
    elif lang == 'en':
        acc = lambda n: f'{n} account{"" if n == 1 else "s"}'
        mon = datetime.strptime(day, '%Y-%m-%d').strftime('%b %-d')
        if bull:
            h = items[0]
            lines.append(f'{mon} · What top X accounts agree on: {T(h["t"])}, {acc(h["n"])} bullish 📊')
        else:
            h = items[0] if items else None
            lines.append(f'{mon} · Most talked-about stock on X today: {T(h["t"])} ({acc(h["n"])}) 💬' if h else f'{mon} · X snapshot 💬')
        lines += ['', f'Data window: {win}', '']
    else:
        acc = lambda n: f'계정 {n}개'
        if bull:
            h = items[0]
            lines.append(f'{m}/{dd} X 인플루언서 컨센서스: {T(h["t"])} {acc(h["n"])} 동시 강세 📊')
        else:
            h = items[0] if items else None
            lines.append(f'{m}/{dd} X 스냅샷: 오늘 가장 많이 언급된 종목 {T(h["t"])} ({acc(h["n"])}) 💬' if h else f'{m}/{dd} X 스냅샷 💬')
        lines += ['', f'데이터 범위: {win}', '']

    L = {'zh': dict(cb=f'🔵 共同看多：{len(s["bull"])} 隻・共同看空：{len(s["bear"])} 隻', rest=lambda k, n: f'・其餘 {k} 隻各 {n} 個帳號',
                    more=lambda k: f' 等 {k} 隻', bear='🔴 共同看空：', split='⚖️ 好淡分歧：', sp=lambda b, r: f'（{b} 好 {r} 淡）',
                    stk='🔥 連續 2 日或以上都喺共同看多：', sd=lambda n: f'（{n} 日）', none='今日暫時未有共同看多（要最少 2 個帳號最新立場都睇好）。',
                    talk='💬 最多人討論：', tr=lambda x: acc(x['n']) + mix(x, '（{}）', '{} 好 {} 淡', '{} 個睇好', '{} 個睇淡'),
                    sum=f'🗣️ 今日 {s["accounts"]} 個帳號發文，講咗 {s.get("tickers", 0)} 隻股票。', q=lambda q: f'💬 @{q["acc"]}：{q["text"]}',
                    note='(共同看多＝最少 2 個帳號最新立場睇好，唔計市場快訊帳號)',
                    end=['網站約每 4 個鐘更新，最新數字 👉 link in bio (xmktradar.github.io)', '☕ 鍾意就請我哋飲杯咖啡：link in bio，網站底部 PayPal 捐款 🙏', 'Follow @thecrowdtape 每日睇街貨點諗。', '',
                         '⚠️ 只係整理公開社交媒體貼文，唔構成投資建議。網站嘅機械人頁只係紙上交易。投資有風險，請自行判斷。']),
         'en': dict(cb=f'🔵 Joint bullish: {len(s["bull"])} · Joint bearish: {len(s["bear"])}', rest=lambda k, n: f'・{k} more with {n} accounts each',
                    more=lambda k: f' +{k} more', bear='🔴 Joint bearish: ', split='⚖️ Split views: ', sp=lambda b, r: f' ({b} bull / {r} bear)',
                    stk='🔥 Joint bullish 2+ days in a row: ', sd=lambda n: f' ({n}d)', none='No joint bullish stock yet today (needs 2+ accounts whose latest view is bullish).',
                    talk='💬 Most discussed:', tr=lambda x: acc(x['n']) + mix(x, ' ({})', '{} bull / {} bear', '{} bullish', '{} bearish'),
                    sum=f'🗣️ {s["accounts"]} accounts posted today, covering {s.get("tickers", 0)} stocks.', q=lambda q: f'💬 @{q["acc"]}: "{q["text"]}"',
                    note='(Joint bullish = at least 2 accounts whose latest view is bullish; news-wire accounts not counted)',
                    end=['Updated about every 4 hours. Latest numbers 👉 link in bio (xmktradar.github.io)', '☕ Enjoy it? Buy us a coffee: link in bio, PayPal at the bottom of the site 🙏', 'Follow @thecrowdtape for the daily read on what the crowd thinks.', '',
                         '⚠️ A summary of public social media posts, not investment advice. The site\'s bot pages are paper trading only. Investing involves risk; do your own research.']),
         'ko': dict(cb=f'🔵 공동 강세: {len(s["bull"])}개・공동 약세: {len(s["bear"])}개', rest=lambda k, n: f'・나머지 {k}개 종목은 각 계정 {n}개',
                    more=lambda k: f' 외 {k}개', bear='🔴 공동 약세: ', split='⚖️ 의견 엇갈림: ', sp=lambda b, r: f' (강세 {b} / 약세 {r})',
                    stk='🔥 2일 이상 연속 공동 강세: ', sd=lambda n: f' ({n}일)', none='오늘은 아직 공동 강세 종목이 없습니다 (최신 의견이 강세인 계정이 2개 이상 필요).',
                    talk='💬 가장 많이 언급된 종목:', tr=lambda x: acc(x['n']) + mix(x, ' ({})', '강세 {} / 약세 {}', '강세 {}', '약세 {}'),
                    sum=f'🗣️ 오늘 계정 {s["accounts"]}개가 글을 올렸고, 언급된 종목은 {s.get("tickers", 0)}개입니다.', q=lambda q: f'💬 @{q["acc"]}: "{q["text"]}"',
                    note='(공동 강세 = 최신 의견이 강세인 계정 2개 이상, 뉴스 속보 계정 제외)',
                    end=['약 4시간마다 업데이트, 최신 수치 👉 프로필 링크 (xmktradar.github.io)', '☕ 도움이 되셨다면 커피 한 잔 후원해 주세요: 프로필 링크, 사이트 하단 PayPal 🙏', '@thecrowdtape 팔로우하고 매일 시장 분위기를 확인하세요.', '',
                         '⚠️ 공개 SNS 게시물을 정리한 것으로 투자 조언이 아닙니다. 사이트의 봇 페이지는 모의 거래입니다. 투자에는 위험이 따르니 스스로 판단하세요.'])}[lang]
    join = lambda ts, cap=8: sep.join(T(t) for t in ts[:cap]) + (L['more'](len(ts) - cap) if len(ts) > cap else '')
    lead = ' ' if lang == 'zh' else ''
    head, win_line = lines[0], lines[2]
    main = []
    if bull:
        main.append(L['cb'])
        by = {}
        for x in items:
            by.setdefault(x['n'], []).append(x['t'])
        for n in sorted(by, reverse=True):
            ts = by[n]
            if n >= 3 or len(ts) <= 4:
                main.append(f'・{acc(n)}：{lead}{join(ts)}' if lang == 'zh' else f'・{acc(n)}: {join(ts)}')
            else:
                main.append(L['rest'](len(ts), n))
    else:
        main += [L['none'], L['talk']]
        for x in items[:5]:
            main.append(f'・{T(x["t"])}：{L["tr"](x)}' if lang == 'zh' else f'・{T(x["t"])}: {L["tr"](x)}')
    if s['bear']:
        main.append(L['bear'] + lead + sep.join(f'{T(g["t"])}' + (f'（{acc(g["nr"])}）' if lang == 'zh' else f' ({acc(g["nr"])})') for g in s['bear'][:5]))
    extra = []  # optional blocks, most important first
    if s['split']:
        extra.append(L['split'] + lead + sep.join(T(g['t']) + L['sp'](g['nb'], g['nr']) for g in s['split'][:4]))
    if bull:
        st = sorted([x for x in items if x['streak'] >= 2], key=lambda x: -x['streak'])[:6]
        if st:
            extra.append(L['stk'] + lead + sep.join(T(x['t']) + L['sd'](x['streak']) for x in st))
    else:
        extra.append(L['sum'])
    q = L['q'](quote_) if quote_ and quote_.get('text') else None
    tg = tags(lang, [x['t'] for x in items])
    url = f'{SITE}{lang}/'
    short = SHORT[lang]

    # Instagram: the full post in Tim's format ("link in bio", since IG captions have no links).
    ig = [head, '', win_line, '', *main]
    for b in extra + ([q] if q else []):
        ig += ['', b]
    ig += ['', L['note'], '', *L['end'], '', tg]

    # Threads (500 characters) and X (280, CJK counted double): drop the least important parts until it fits.
    def fit(blocks, limit, size):
        blocks = [b for b in blocks if b]
        while len(blocks) > 3 and size('\n\n'.join(blocks)) > limit:
            blocks.pop(-3)  # keep the headline and the link + disclaimer at the end
        return '\n\n'.join(blocks)
    give = f"{short['give']}{url}#donate"
    tail = f"{short['live']}{url}\n{short['disc']}"
    threads = fit([head, win_line, '\n'.join(main[:6]), *extra, q, f"{short['live']}{url}\n{give}\n{short['disc']}", tg.split(' ')[0]], 480, len)
    xs = [head, '\n'.join([t for t in main if t != L['none']][:3]), tail]
    x = fit(xs, 270, xlen)
    while xlen(x) > 270 and len(xs[1].split('\n')) > 1:
        xs[1] = '\n'.join(xs[1].split('\n')[:-1])
        x = '\n\n'.join(xs)
    # The donation line goes in when it still fits, dropping list lines for it but keeping at least one.
    for k in range(len(xs[1].split('\n')), 0, -1):
        xd = '\n\n'.join([head, '\n'.join(xs[1].split('\n')[:k]), f"{short['live']}{url}\n{give}\n{short['disc']}"])
        if xlen(xd) <= 270:
            x = xd
            break

    # Reddit: a title plus a Markdown body; no hashtags.
    md = lambda t: re.sub(r'^・', '- ', t)
    body = [win_line, '\n'.join(md(t) for t in main)] + extra + ([f'> {q}'] if q else [])
    body += [L['note'], f"{short['live']}[{url}]({url})", f"{short['give']}[{url}#donate]({url}#donate)", short['disc_long']]

    # Facebook: the Instagram post with clickable links in place of "link in bio".
    fb = [head, '', win_line, '', *main]
    for b in extra + ([q] if q else []):
        fb += ['', b]
    fb += ['', L['note'], '', f"{short['live']}{url}", give, '', short['disc_long'], '', tg]
    return {'instagram': '\n'.join(ig), 'threads': threads, 'x': x,
            'reddit': {'title': re.sub(r'\s*[📊💬]$', '', head), 'body': '\n\n'.join(body)},
            'facebook': '\n'.join(fb)}


def xlen(t):
    """Length as X counts it: links count 23, Chinese, Japanese, Korean and emoji count 2."""
    t = re.sub(r'https?://\S+', 'x' * 23, t)
    return sum(2 if ord(c) >= 0x1100 else 1 for c in t)


SHORT = {'zh': {'live': '最新數字 👉 ', 'give': '☕ 鍾意就支持我哋 👉 ', 'disc': '⚠️ 唔構成投資建議', 'disc_long': '⚠️ 只係整理公開社交媒體貼文，唔構成投資建議。投資有風險，請自行判斷。'},
         'en': {'live': 'Live numbers 👉 ', 'give': '☕ Support the site 👉 ', 'disc': '⚠️ Not investment advice', 'disc_long': '⚠️ A summary of public social media posts, not investment advice. Investing involves risk; do your own research.'},
         'ko': {'live': '최신 수치 👉 ', 'give': '☕ 후원하기 👉 ', 'disc': '⚠️ 투자 조언 아님', 'disc_long': '⚠️ 공개 SNS 게시물을 정리한 것으로 투자 조언이 아닙니다. 투자에는 위험이 따르니 스스로 판단하세요.'}}


def social_page(sp):
    """A plain page for Tim to read the day's posts and save the pictures (not for search engines)."""
    rows = []
    for lang, name in (('zh', '中文'), ('en', 'English'), ('ko', '한국어')):
        img = sp['images'][lang]
        story = sp['stories'][lang]
        p = sp['posts'][lang]
        box = lambda title, text, n: (f'<h3>{title}</h3><textarea readonly rows="{n}">{html.escape(text)}</textarea>'
                                      '<button onclick="navigator.clipboard.writeText(this.previousElementSibling.value);this.textContent=\'已複製 ✓\'">複製</button>')
        rows.append(f'''<section><h2>{name}</h2><a href="{html.escape(img)}" download><img src="{html.escape(img)}" alt=""></a>
{box('Instagram', p['instagram'], 18)}{box('Threads', p['threads'], 10)}{box('X', p['x'], 6)}
{box('Reddit 標題', p['reddit']['title'], 2)}{box('Reddit 內文', p['reddit']['body'], 14)}{box('Facebook', p['facebook'], 18)}
<h3>IG Story（1080×1920）</h3><a href="{html.escape(story)}" download><img class="story" src="{html.escape(story)}" alt=""></a></section>''')
    return f'''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="/favicon.ico" sizes="any"><link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="robots" content="noindex"><title>每日社交媒體貼文 {sp['date']}｜The Crowd Tape</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;margin:0 auto;max-width:760px;padding:16px;background:#f7f8fb;color:#151a2c}}
section{{background:#fff;border-radius:14px;padding:16px;margin:16px 0;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
img{{width:100%;border-radius:10px}}img.story{{width:min(100%,320px);display:block;margin-top:6px}}textarea{{width:100%;box-sizing:border-box;font:inherit;margin-top:4px}}h3{{margin:18px 0 0;font-size:15px}}
button{{margin-top:8px;padding:8px 16px;border-radius:999px;border:0;background:#151a2c;color:#fff;font:inherit}}</style>
<h1>{sp['date']} 社交媒體貼文</h1><p>{html.escape(sp['window'])}｜製作時間 {sp['made_hkt']} HKT｜撳圖片可以下載。</p>
{''.join(rows)}</html>
'''


FEED_KEEP = 30  # days kept in each RSS feed
FEED_META = {'zh': ('The Crowd Tape｜X 大神每日共識', 'zh-Hant-HK', '每日整理 X 上美股大神的共同看好、看淡同分歧。唔構成投資建議。'),
             'en': ('The Crowd Tape · Daily X consensus', 'en', 'What top X stock accounts agree and disagree on, once a day. Not investment advice.'),
             'ko': ('The Crowd Tape · X 일일 컨센서스', 'ko', 'X 주식 인플루언서들의 공동 강세·약세·의견 엇갈림을 매일 정리합니다. 투자 조언 아님.')}


def write_feeds(sp):
    """/<lang>/feed.xml: one item per day (the day's snapshot), newest first, last FEED_KEEP days."""
    when = datetime.strptime(sp['made_hkt'], '%Y-%m-%d %H:%M').replace(tzinfo=HK)
    for lang in LANGS:
        path = f'{lang}/feed.xml'
        old = open(path, encoding='utf-8').read() if os.path.exists(path) else ''
        items = [i for i in re.findall(r'<item>.*?</item>', old, re.S) if f'#{sp["date"]}<' not in i]
        p = sp['posts'][lang]
        paras = []
        for block in p['reddit']['body'].split('\n\n'):
            block = html.escape(block.lstrip('> '))
            block = re.sub(r'\[(https?://[^\]]+)\]\((https?://[^)]+)\)', r'<a href="\2">\1</a>', block)
            paras.append('<p>' + block.replace('\n', '<br>') + '</p>')
        body = f'<p><img src="{html.escape(sp["images"][lang])}" alt=""></p>' + ''.join(paras)
        item = (f'<item><title>{html.escape(p["reddit"]["title"])}</title><link>{SITE}{lang}/</link>'
                f'<guid isPermaLink="false">{SITE}{lang}/#{sp["date"]}</guid>'
                f'<pubDate>{when.strftime("%a, %d %b %Y %H:%M:%S %z")}</pubDate>'
                f'<description><![CDATA[{body}]]></description></item>')
        title, code, desc = FEED_META[lang]
        xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
               f'<title>{html.escape(title)}</title><link>{SITE}{lang}/</link><description>{html.escape(desc)}</description>'
               f'<language>{code}</language><lastBuildDate>{when.strftime("%a, %d %b %Y %H:%M:%S %z")}</lastBuildDate>'
               f'<atom:link href="{SITE}{lang}/feed.xml" rel="self" type="application/rss+xml"/>'
               f'<image><url>{SITE}assets/icon-192.png</url><title>{html.escape(title)}</title><link>{SITE}{lang}/</link></image>\n'
               + '\n'.join([item] + items[:FEED_KEEP - 1]) + '\n</channel></rss>\n')
        os.makedirs(lang, exist_ok=True)
        open(path, 'w', encoding='utf-8').write(xml)


def main():
    st = read_json(work('stats.json'))
    d = load(HTML)
    ch = read_json('data/consensus-history.json', {'days': {}})
    day, s = st['today'], st['daily']
    langs, items = build(d, s, ch, day)
    # A new picture design (tools/og.html) also counts as a change.
    digest = hashlib.sha1(json.dumps(langs, sort_keys=True, ensure_ascii=False).encode() + open('tools/og.html', 'rb').read()).hexdigest()[:10]
    last = read_json('og/latest.json', {})
    draw = last.get('hash') != digest or last.get('date') != day or not os.path.exists(f'og/{day}.png')

    sp = read_json('data/social-posts.json', {})
    now = now_hk()
    old = isinstance((sp.get('posts') or {}).get('zh'), str)  # written before the per-platform versions existed
    old = old or not os.path.exists('zh/feed.xml')  # first run with RSS feeds
    old = old or ('facebook' not in ((sp.get('posts') or {}).get('zh') or {'facebook': 1})) or 'stories' not in sp  # before Facebook and Story
    social = bool(items) and (sp.get('date') != day and now.hour >= SOCIAL_HOUR or old or os.environ.get('SOCIAL_FORCE') == '1')
    if social:
        win = window(s)
        sp = {'date': day, 'made_hkt': now.strftime('%Y-%m-%d %H:%M'), 'window': win,
              'images': {l: f'{SITE}og/social-{l}.png?v={day}' for l in LANGS},
              'stories': {l: f'{SITE}og/story-{l}.png?v={day}' for l in LANGS},
              'posts': {l: caption(l, day, s, items, win, langs[l]['quote']) for l in LANGS}}
        write_json('data/social-posts.json', sp, indent=1)
        os.makedirs('social', exist_ok=True)
        open('social/index.html', 'w', encoding='utf-8').write(social_page(sp))
        write_feeds(sp)
        notice(f'今日社交媒體貼文已寫好：{SITE}social/')
    if draw or social:
        write_json(work('og.json'), {'date': day, 'hash': digest, 'social': social, 'langs': langs})

    h = open(HTML, encoding='utf-8').read()
    h = re.sub(r'(https://xmktradar\.github\.io/og/)[\w-]+\.png(\?v=[\w-]+)?', rf'\g<1>{day}.png?v={digest}', h)
    open(HTML, 'w', encoding='utf-8').write(h)
    print(f"share {day} mode {langs['zh']['mode']} hero {items[0]['t'] if items else '-'} draw {draw} social {social}")


if __name__ == '__main__':
    main()
