"""Step 8b: share image data (one picture per language) and the daily social media posts.

Reads work/stats.json, the data in index.html and data/consensus-history.json.
Writes work/og.json for tools/og.js when a picture needs drawing, points the master page's
og:image at today's picture, and once a day (first update after 07:00 HKT) writes
data/social-posts.json and social/index.html: posts in Chinese, English and Korean for Instagram
(the @thecrowdtape format), Threads, X, Reddit and Facebook, for the Grok bot to post with og/social-<lang>.png,
plus a 1080x1920 Instagram Story picture og/story-<lang>.png and a native 1080x1350
Instagram text-post picture og/ig-<lang>.png. Every version asks readers to support the site (PayPal).
Also writes x_trilingual (one zh+en+ko X post at 21:00 and 08:00 HKT, picture og/x-<kind>.png for the $TICKER in the text), facebook_cta and ig_threads_daily.
python3 tools/share.py --og-only writes work/og.json from dash-data + work/stats.json and stops
(no social posts, no index.html rewrite); used by tools/ig_sample.js.
"""
import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime

from sitedata import HK, load, notice, now_hk, read_json, work, write_json
from utm import tag_posts, tag_url

HTML = 'index.html'
SITE = 'https://thecrowdtape.com/'
LANGS = ('zh', 'en', 'ko')
SOCIAL_HOUR = 7  # first update at or after this HKT hour writes the day's posts


def page_url(lang, path=''):
    """Absolute page URL under /{lang}/.

    Stock pages are /{lang}/stock/<T>/ (root /stock/<T>/ is 404). A path that already
    starts with zh/, en/, ko/, or a leading slash is rewritten under `lang`.
    """
    if lang not in LANGS:
        lang = 'en'
    path = (path or '').strip()
    if path.startswith('http://') or path.startswith('https://'):
        return path
    if path.startswith('/'):
        path = path[1:]
    for pfx in ('zh/', 'en/', 'ko/'):
        if path.startswith(pfx):
            path = path[len(pfx):]
            break
    if path.startswith('#'):
        return f'{SITE}{lang}/{path}'
    if path and not path.endswith('/'):
        path += '/'
    return f'{SITE}{lang}/{path}'


def stock_url(lang, ticker):
    """/{lang}/stock/<TICKER>/ . Root /stock/<TICKER>/ is 404."""
    ticker = re.sub(r'[^A-Z0-9.\-]', '', (ticker or '').strip().lstrip('$').upper())
    return page_url(lang, f'stock/{ticker}/')
# Social posts only go out on US trading days, Monday to Friday (Tim, 2026-10-12). NYSE full-day closures:
US_HOLIDAYS = {'2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25', '2026-06-19', '2026-07-03',
               '2026-09-07', '2026-11-26', '2026-12-25',
               '2027-01-01', '2027-01-18', '2027-02-15', '2027-03-26', '2027-05-31', '2027-06-18', '2027-07-05',
               '2027-09-06', '2027-11-25', '2027-12-24'}


def trading_day(day):
    return datetime.strptime(day, '%Y-%m-%d').weekday() < 5 and day not in US_HOLIDAYS


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
        # English card only: a quote with CJK or Hangul is skipped for the next post. Korean is left as-is.
        if lang == 'en' and re.search('[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\uf900-\ufaff]', txt):
            continue
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
                    end=['網站約每 4 個鐘更新，最新數字 👉 link in bio (thecrowdtape.com)', '☕ 鍾意就請我哋飲杯咖啡：link in bio，網站底部 PayPal 捐款 🙏', 'Follow @thecrowdtape 每日睇街貨點諗。', '',
                         '⚠️ 只係整理公開社交媒體貼文，唔構成投資建議。網站嘅機械人頁只係紙上交易。投資有風險，請自行判斷。']),
         'en': dict(cb=f'🔵 Joint bullish: {len(s["bull"])} · Joint bearish: {len(s["bear"])}', rest=lambda k, n: f'・{k} more with {n} accounts each',
                    more=lambda k: f' +{k} more', bear='🔴 Joint bearish: ', split='⚖️ Split views: ', sp=lambda b, r: f' ({b} bull / {r} bear)',
                    stk='🔥 Joint bullish 2+ days in a row: ', sd=lambda n: f' ({n}d)', none='No joint bullish stock yet today (needs 2+ accounts whose latest view is bullish).',
                    talk='💬 Most discussed:', tr=lambda x: acc(x['n']) + mix(x, ' ({})', '{} bull / {} bear', '{} bullish', '{} bearish'),
                    sum=f'🗣️ {s["accounts"]} accounts posted today, covering {s.get("tickers", 0)} stocks.', q=lambda q: f'💬 @{q["acc"]}: "{q["text"]}"',
                    note='(Joint bullish = at least 2 accounts whose latest view is bullish; news-wire accounts not counted)',
                    end=['Updated about every 4 hours. Latest numbers 👉 link in bio (thecrowdtape.com)', '☕ Enjoy it? Buy us a coffee: link in bio, PayPal at the bottom of the site 🙏', 'Follow @thecrowdtape for the daily read on what the crowd thinks.', '',
                         '⚠️ A summary of public social media posts, not investment advice. The site\'s bot pages are paper trading only. Investing involves risk; do your own research.']),
         'ko': dict(cb=f'🔵 공동 강세: {len(s["bull"])}개・공동 약세: {len(s["bear"])}개', rest=lambda k, n: f'・나머지 {k}개 종목은 각 계정 {n}개',
                    more=lambda k: f' 외 {k}개', bear='🔴 공동 약세: ', split='⚖️ 의견 엇갈림: ', sp=lambda b, r: f' (강세 {b} / 약세 {r})',
                    stk='🔥 2일 이상 연속 공동 강세: ', sd=lambda n: f' ({n}일)', none='오늘은 아직 공동 강세 종목이 없습니다 (최신 의견이 강세인 계정이 2개 이상 필요).',
                    talk='💬 가장 많이 언급된 종목:', tr=lambda x: acc(x['n']) + mix(x, ' ({})', '강세 {} / 약세 {}', '강세 {}', '약세 {}'),
                    sum=f'🗣️ 오늘 계정 {s["accounts"]}개가 글을 올렸고, 언급된 종목은 {s.get("tickers", 0)}개입니다.', q=lambda q: f'💬 @{q["acc"]}: "{q["text"]}"',
                    note='(공동 강세 = 최신 의견이 강세인 계정 2개 이상, 뉴스 속보 계정 제외)',
                    end=['약 4시간마다 업데이트, 최신 수치 👉 프로필 링크 (thecrowdtape.com)', '☕ 도움이 되셨다면 커피 한 잔 후원해 주세요: 프로필 링크, 사이트 하단 PayPal 🙏', '@thecrowdtape 팔로우하고 매일 시장 분위기를 확인하세요.', '',
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
    url = page_url(lang)
    short = SHORT[lang]

    # Instagram: the full post in Tim's format ("link in bio", since IG captions have no links).
    ig = [head, '', win_line, '', *main]
    for b in extra + ([q] if q else []):
        ig += ['', b]
    ig += ['', L['note'], '', *L['end'], '', tg]

    # X (280, CJK counted double): drop the least important blocks until it fits.
    # Threads is fit afterwards by fit_threads (500 code points, URLs counted in full).
    def fit(blocks, limit, size):
        blocks = [b for b in blocks if b]
        while len(blocks) > 3 and size('\n\n'.join(blocks)) > limit:
            blocks.pop(-3)  # keep the headline and the link + disclaimer at the end
        return '\n\n'.join(blocks)
    give = f"{short['give']}{url}#donate"
    tail = f"{short['live']}{url}\n{short['disc']}"
    # Threads shows one topic tag per post, so it gets the first hashtag only.
    threads = fit_threads('\n\n'.join(b for b in [
        head, win_line, '\n'.join(main[:6]), *extra, q,
        f"{short['live']}{url}\n{give}\n{short['disc']}", tg.split(' ')[0]] if b), lang)
    xs = [head, '\n'.join([t for t in main if t != L['none']][:3]), tail]
    x = fit(xs, 270, xlen)
    while xlen(x) > 270 and len(xs[1].split('\n')) > 1:
        xs[1] = '\n'.join(xs[1].split('\n')[:-1])
        x = '\n\n'.join(xs)
    # Every post carries hashtags (Tim, 2026-10-12). X gets a short set; then the donation line when it still fits,
    # dropping list lines for them but keeping at least one.
    tks = [t for t in [x_['t'] for x_ in items] if re.fullmatch(r'[A-Z]{1,6}', t)]
    xtags = ' '.join([tg.split(' ')[0]] + [f'#{t}' for t in tks[:2]])
    lines_ = xs[1].split('\n')
    done = False
    for end in (f"{short['live']}{url}\n{give}\n{short['disc']}\n{xtags}", f"{tail}\n{xtags}", f"{tail}\n{tg.split(' ')[0]}"):
        for k in range(len(lines_), 0, -1):
            xd = '\n\n'.join([head, '\n'.join(lines_[:k]), end])
            if xlen(xd) <= 270:
                x, done = xd, True
                break
        if done:
            break

    # Reddit: a title plus a Markdown body, hashtags on the last line.
    md = lambda t: re.sub(r'^・', '- ', t)
    body = [win_line, '\n'.join(md(t) for t in main)] + extra + ([f'> {q}'] if q else [])
    body += [L['note'], f"{short['live']}[{url}]({url})", f"{short['give']}[{url}#donate]({url}#donate)", short['disc_long'], tg]

    # Facebook: the Instagram post with clickable links in place of "link in bio".
    fb = [head, '', win_line, '', *main]
    for b in extra + ([q] if q else []):
        fb += ['', b]
    fb += ['', L['note'], '', f"{short['live']}{url}", give, '', short['disc_long'], '', tg]
    return {'instagram': '\n'.join(ig), 'threads': threads, 'x': x,
            'reddit': {'title': re.sub(r'\s*[📊💬]$', '', head), 'body': '\n\n'.join(body)},
            'facebook': '\n'.join(fb),
            # Instagram Story: hashtags for a hashtag sticker or small text on the Story picture.
            'story': ' '.join(tg.split(' ')[:3] + [f'#{t}' for t in tks[:2]])}


# URL body is ASCII. CJK, Hangul and emoji after a link are weighted on their own, not swallowed into the 23.
_XURL = re.compile(r'https?://[A-Za-z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+')


def xlen(t):
    """Length as X counts it: each URL counts 23, Chinese, Japanese, Korean and emoji count 2."""
    def weight(s):
        return sum(2 if ord(c) >= 0x1100 else 1 for c in s)

    n, i = 0, 0
    for m in _XURL.finditer(t or ''):
        n += weight(t[i:m.start()]) + 23
        i = m.end()
    return n + weight((t or '')[i:])


SHORT = {'zh': {'live': '最新數字 👉 ', 'give': '☕ 鍾意就支持我哋 👉 ', 'disc': '⚠️ 唔構成投資建議', 'disc_long': '⚠️ 只係整理公開社交媒體貼文，唔構成投資建議。投資有風險，請自行判斷。'},
         'en': {'live': 'Live numbers 👉 ', 'give': '☕ Support the site 👉 ', 'disc': '⚠️ Not investment advice', 'disc_long': '⚠️ A summary of public social media posts, not investment advice. Investing involves risk; do your own research.'},
         'ko': {'live': '최신 수치 👉 ', 'give': '☕ 후원하기 👉 ', 'disc': '⚠️ 투자 조언 아님', 'disc_long': '⚠️ 공개 SNS 게시물을 정리한 것으로 투자 조언이 아닙니다. 투자에는 위험이 따르니 스스로 판단하세요.'}}

# Threads rejects a post past 500 Unicode code points. len() is that count; a URL counts in full.
THREADS_MAX = 500
_THREADS_URL = re.compile(r'https?://\S+')


def _truncate_ending(line, target):
    """Shorten `line` to at most `target` code points, ending with …. None if it would not get shorter."""
    if target >= len(line):
        return line
    if target < 1:
        return None
    raw = line[:-1].rstrip() if line.endswith('…') else line
    keep = target - 1
    cut = raw[:keep].rstrip(' \t') if keep > 0 else ''
    while cut and ord(cut[-1]) in (0xfe0f, 0x200d):
        cut = cut[:-1].rstrip(' \t')
    new = (cut + '…') if cut else '…'
    if len(new) > target:
        extra = len(new) - target
        cut = cut[:-extra] if extra < len(cut) else ''
        while cut and ord(cut[-1]) in (0xfe0f, 0x200d):
            cut = cut[:-1]
        new = (cut + '…') if cut else '…'
        if len(new) > target:
            new = new[:target]
    if len(new) >= len(line):
        return None
    return new


def _threads_join(parts):
    blocks = []
    for lines in parts:
        if any(ln.strip() for ln in lines):
            blocks.append('\n'.join(lines))
    return '\n\n'.join(blocks)


def _is_quote_line(line):
    """A 💬 quote (💬 @name：…), not a section label and not a headline that merely ends with 💬."""
    s = line.strip()
    return s.startswith('💬') and '@' in s


def _is_donate_line(line):
    s = line.strip()
    return s.startswith('☕') or '#donate' in s


def _is_live_line(line, lang):
    s = line.strip()
    if not s or _is_donate_line(s) or s.startswith('⚠') or s.startswith('#'):
        return False
    live = SHORT.get(lang, SHORT['en'])['live'].strip()
    return s.startswith(live)


def _sole_link(parts):
    """Index of the only non-donate URL line, if there is exactly one."""
    spots = []
    for i, lines in enumerate(parts):
        for j, ln in enumerate(lines):
            if _THREADS_URL.search(ln) and not _is_donate_line(ln):
                spots.append((i, j))
    return spots[0] if len(spots) == 1 else None


def _threads_fixed(i, j, line):
    """Headline, disclaimer and the hashtag line are never dropped."""
    if i == 0 and j == 0:
        return True
    s = line.strip()
    return s.startswith('#') or s.startswith('⚠')


def fit_threads(text, lang):
    """Fit a Threads caption into 500 code points.

    When len(text) > 500, trim in order: shorten the 💬 quote (ellipsis), then drop it;
    drop the ☕ donate line so at most one link remains (the language's 最新數字 / Live numbers /
    최신 수치 link); drop the 🔥 streak paragraph, then the ⚖️ split paragraph, then ticker
    lines (・) from the bottom. The headline, the disclaimer and the hashtag line stay.
    """
    if text is None:
        return ''
    if not isinstance(text, str):
        text = str(text)
    if lang not in LANGS:
        lang = 'en'
    if len(text) <= THREADS_MAX:
        return text
    parts = [p.split('\n') for p in text.split('\n\n')]

    def total():
        return len(_threads_join(parts))

    def quote_spots():
        found = []
        for i, lines in enumerate(parts):
            for j, ln in enumerate(lines):
                if _is_quote_line(ln) and not _threads_fixed(i, j, ln):
                    found.append((i, j))
        return found

    guard = 0
    while total() > THREADS_MAX and guard < 10000:
        guard += 1
        spots = quote_spots()
        if not spots:
            break
        i, j = spots[-1]
        saved = parts[i][j]
        parts[i].pop(j)
        without = total()
        parts[i].insert(j, saved)
        if without > THREADS_MAX:
            parts[i].pop(j)  # even an empty quote cannot get the post under the limit
            continue
        new = _truncate_ending(saved, len(saved) - (total() - THREADS_MAX))
        if not new or len(new) >= len(saved):
            parts[i].pop(j)
            continue
        parts[i][j] = new

    def drop_where(pred):
        for i, lines in enumerate(parts):
            parts[i] = [ln for j, ln in enumerate(lines) if _threads_fixed(i, j, ln) or not pred(ln)]

    if total() > THREADS_MAX:
        drop_where(_is_donate_line)
        # Any other extra link goes too, leaving the live-numbers link when it is there.
        while total() > THREADS_MAX and len(_THREADS_URL.findall(_threads_join(parts))) > 1 and guard < 10000:
            guard += 1
            spot = None
            for i, lines in enumerate(parts):
                for j, ln in enumerate(lines):
                    if _THREADS_URL.search(ln) and not _threads_fixed(i, j, ln) and not _is_live_line(ln, lang):
                        spot = (i, j)
            if not spot:
                break
            before = total()
            parts[spot[0]].pop(spot[1])
            if total() >= before:
                break

    if total() > THREADS_MAX:
        drop_where(lambda ln: ln.strip().startswith('🔥'))
    if total() > THREADS_MAX:
        drop_where(lambda ln: ln.strip().startswith('⚖'))
    while total() > THREADS_MAX and guard < 10000:
        guard += 1
        spot = None
        for i, lines in enumerate(parts):
            for j, ln in enumerate(lines):
                if ln.strip().startswith('・') and not _threads_fixed(i, j, ln):
                    spot = (i, j)
        if not spot:
            break
        before = total()
        parts[spot[0]].pop(spot[1])
        if total() >= before:
            break

    # Body lines that are not the ticker list (carousel duel rows, window, dialogue) go next, from the bottom.
    # The one remaining link stays, even when it is not the live-numbers line.
    while total() > THREADS_MAX and guard < 10000:
        guard += 1
        sole = _sole_link(parts)
        spot = None
        for i, lines in enumerate(parts):
            for j, ln in enumerate(lines):
                if not ln.strip() or _threads_fixed(i, j, ln) or _is_live_line(ln, lang):
                    continue
                if sole == (i, j):
                    continue
                spot = (i, j)
        if not spot:
            break
        before = total()
        parts[spot[0]].pop(spot[1])
        if total() >= before:
            break

    while total() > THREADS_MAX and parts and parts[0] and guard < 10000:
        guard += 1
        head = parts[0][0]
        new = _truncate_ending(head, max(1, len(head) - (total() - THREADS_MAX)))
        if not new or len(new) >= len(head):
            break
        parts[0][0] = new

    out = _threads_join(parts)
    if len(out) <= THREADS_MAX:
        return out
    return _threads_force(parts, lang)


def _threads_force(parts, lang):
    """Last resort: keep a headline prefix, the disclaimer and the hashtag, and stay within 500."""
    head = parts[0][0] if parts and parts[0] else ''
    disc, tag, live = '', '', ''
    for i, lines in enumerate(parts):
        for j, ln in enumerate(lines):
            s = ln.strip()
            if not s or (i == 0 and j == 0):
                continue
            if s.startswith('⚠') and not disc:
                disc = s
            elif s.startswith('#') and not tag:
                tag = s
            elif _is_live_line(s, lang) and not live:
                live = s

    def assemble(head_line, live_line):
        chunks = []
        if head_line:
            chunks.append(head_line)
        mid = [ln for ln in (live_line, disc) if ln]
        if mid:
            chunks.append('\n'.join(mid))
        if tag and tag != head_line:
            chunks.append(tag)
        return '\n\n'.join(chunks)

    out = assemble(head, live)
    guard = 0
    while len(out) > THREADS_MAX and len(head) > 1 and guard < 5000:
        guard += 1
        new = _truncate_ending(head, max(1, len(head) - (len(out) - THREADS_MAX)))
        if not new or len(new) >= len(head):
            head = head[:-1].rstrip()
            if head and not head.endswith('…'):
                head = head[:-1] + '…' if len(head) > 1 else '…'
        else:
            head = new
        out = assemble(head, live)
    if len(out) > THREADS_MAX:
        out = assemble(head, '')
    if len(out) > THREADS_MAX:
        tail = '\n'.join(ln for ln in (disc, tag) if ln)
        room = THREADS_MAX - (len(tail) + 2 if tail else 0)
        if tail and room >= 1:
            piece = _truncate_ending(head, room) or '…'
            if len(piece) > room:
                piece = piece[:room]
            out = piece + '\n\n' + tail
        elif tail and len(tail) <= THREADS_MAX:
            # Headline gets one character so it is not dropped, tag and disc fill the rest.
            room = THREADS_MAX - 1 - (2 if tail else 0)
            keep = tail[-room:] if room > 0 else ''
            out = ('…\n\n' + keep) if keep else '…'
        else:
            out = (out or '')[:THREADS_MAX]
    if len(out) > THREADS_MAX:
        out = out[:THREADS_MAX]
    return out


def fit_threads_posts(posts):
    """Fit every language's threads string. Mutates `posts` ({lang: {threads: str}}) and returns it."""
    if not isinstance(posts, dict):
        return posts
    for lang, p in posts.items():
        if lang in LANGS and isinstance(p, dict) and isinstance(p.get('threads'), str):
            p['threads'] = fit_threads(p['threads'], lang)
    return posts

# One extra line under the Facebook post. The link is that language's home, campaign newsletter.
FB_CTA = {'zh': '📬 訂閱免費電子報 👉 ', 'en': '📬 Get the free newsletter 👉 ', 'ko': '📬 무료 뉴스레터 구독 👉 '}
X_WHEN = {'premarket': '21:00', 'afterclose': '08:00'}
_XDATE = re.compile(r'^(\d{1,2}/\d{1,2}|[A-Z][a-z]{2}\s+\d{1,2})')
_XTICK = re.compile(r'\$([A-Z]{1,6})\b')
_XEMOJI = re.compile(r'\s*[📊💬🚀⚔️]+\s*$')


def facebook_cta(text, lang):
    """Facebook text plus the newsletter line. `text` is kept as it already is."""
    line = FB_CTA[lang] + tag_url(page_url(lang), 'fb', 'newsletter')
    text = (text or '').rstrip()
    return f'{text}\n\n{line}' if text else line


def add_facebook_ctas(posts):
    """Set posts[lang]['facebook_cta'] from the existing facebook text. Idempotent."""
    if not isinstance(posts, dict):
        return posts
    for lang, p in posts.items():
        if isinstance(p, dict) and isinstance(p.get('facebook'), str) and lang in FB_CTA:
            p['facebook_cta'] = facebook_cta(p['facebook'], lang)
    return posts


def _x_head_body(text):
    """Headline (first block of an X post) and the joint-bull lines under it, without the link tail."""
    paras = (text or '').strip().split('\n\n')
    head = paras[0].strip() if paras else ''
    body = []
    for p in paras[1:]:
        s = p.strip()
        if not s or re.search(r'https?://', s) or s.startswith('⚠') or s.startswith('#'):
            continue
        body.append(s)
    return head, '\n'.join(body)


def _short_headline(head):
    """Date plus the ticker clause of the X headline. Same words, without the long label."""
    bare = _XEMOJI.sub('', head).strip()
    m = _XDATE.match(bare)
    date = m.group(1) if m else ''
    sm = re.search(r'\$[A-Z]{1,6}.*$', bare)
    fact = sm.group(0).strip() if sm else bare
    if date and fact and not fact.startswith(date):
        return f'{date} {fact}'.strip()
    return fact or bare


def _ticker_block(posts):
    """Verbatim joint-bull ticker lines from the X post that kept the most tickers."""
    best, best_n = '', -1
    for lang in LANGS:
        p = posts.get(lang)
        text = p.get('x') if isinstance(p, dict) else ''
        _, body = _x_head_body(text or '')
        lines = [ln for ln in body.split('\n') if _XTICK.search(ln)]
        n = len(set(_XTICK.findall('\n'.join(lines))))
        if n > best_n:
            best, best_n = '\n'.join(lines), n
    return best


def _disc_line():
    """One line, the short disclaimer in each language (SHORT['disc'], not the long one)."""
    return ' · '.join(SHORT[lang]['disc'] for lang in LANGS)


def _x_link(lang, campaign):
    """Language home for an X post, with the same utm on every language."""
    return tag_url(page_url(lang), 'x', campaign)


def _ticker_fact(line):
    m = re.search(r'\$[A-Z]{1,6}.*$', line or '')
    return m.group(0) if m else (line or '')


def _keep_frame(line):
    """Shorten a premarket line without dropping 開市前 / pre-market / 개장 전."""
    for frame in ('開市前：', 'pre-market:', '개장 전:'):
        i = (line or '').find(frame)
        if i < 0:
            continue
        pre = line[:i + len(frame)]
        fact = _ticker_fact(line[i + len(frame):].strip())
        if not fact:
            return pre
        if pre.endswith('：'):
            return f'{pre}{fact}'
        return f'{pre} {fact}'
    return _short_headline(line)


def _shrink_headline(line):
    if line and any(k in line for k in ('開市前', 'pre-market', '개장 전')):
        return _keep_frame(line)
    return _short_headline(line)


def _assemble_lang_lines(pairs, disc, extra=''):
    """Each headline followed by that language's URL, then the optional ticker block and disclaimer."""
    out = []
    for line, url in pairs:
        if line:
            out.append(line)
        if url:
            out.append(url)
    if extra:
        out.append(extra.strip('\n'))
    if disc:
        out.append(disc)
    return '\n'.join(out)


def _cap_pairs(pairs, disc):
    """Shorten the longest headline until the post is within 280. Language URLs stay.

    The cut is taken off the end, so a leading ticker and language marker stay.
    """
    ps = [(line, url) for line, url in pairs]
    text = _assemble_lang_lines(ps, disc)
    for _ in range(400):
        if xlen(text) <= 280:
            return text
        i = max(range(len(ps)), key=lambda k: xlen(ps[k][0] or ''))
        line, url = ps[i]
        if not line or xlen(line) <= 12:
            break
        drop = 8 if len(line) > 24 else 2
        cut = line[:-drop].rstrip()
        if not cut or cut == line:
            break
        ps[i] = (cut + '…', url)
        text = _assemble_lang_lines(ps, disc)
    return text


def _fit_lang_lines(pairs, disc, shorten=True):
    """Fit headline/URL pairs into 280. Every language URL stays.

    Full disclaimer first, then SHORT['en']['disc'], then a shorter headline, then the ticker clause.
    """
    en = SHORT['en']['disc']

    def try_fit(ps, d):
        text = _assemble_lang_lines(ps, d)
        return text if xlen(text) <= 280 else None

    hit = try_fit(pairs, disc)
    if hit:
        return hit
    hit = try_fit(pairs, en)
    if hit or not shorten:
        return hit or _assemble_lang_lines(pairs, en)
    shrunk = [(_shrink_headline(line), url) for line, url in pairs]
    hit = try_fit(shrunk, disc) or try_fit(shrunk, en)
    if hit:
        return hit
    facts = [(_ticker_fact(line) or line, url) for line, url in shrunk]
    return try_fit(facts, en) or _cap_pairs(facts, en)


def _split_lang_post(text):
    """(headline, url) pairs and the disclaimer. Bullet lines are dropped. Missing URLs use premarket."""
    pairs, disc, pending = [], None, None
    for ln in (text or '').split('\n'):
        s = ln.strip()
        if not s or s.startswith('・'):
            continue
        if re.fullmatch(r'https?://\S+', s):
            if pending is not None:
                pairs.append((pending, s))
                pending = None
            elif pairs and pairs[-1][1] is None:
                pairs[-1] = (pairs[-1][0], s)
            else:
                pairs.append(('', s))
            continue
        um = re.search(r'https?://\S+', s)
        if um and um.start() > 0:
            if pending is not None:
                pairs.append((pending, None))
                pending = None
            pairs.append((s[:um.start()].strip(), um.group(0)))
            continue
        if s.startswith(('⚠', '#')):
            disc = s
            continue
        if pending is not None:
            pairs.append((pending, None))
        pending = s
    if pending is not None:
        pairs.append((pending, None))
    filled = []
    for i, (head, url) in enumerate(pairs):
        if not url and i < len(LANGS):
            url = _x_link(LANGS[i], 'premarket')
        filled.append((head, url))
    return filled, disc or _disc_line()


def trilingual_text(posts, campaign):
    """One X post, zh then en then ko, from the headlines and joint-bull lines already in posts[lang]['x'].

    Each language headline is followed by that language's home URL (same utm: source x, this campaign).
    Full form also keeps the joint-bull ticker lines and the one-line disclaimer. When that is over 280
    (X count, each URL 23), the short form drops the ticker lines, then SHORT['en']['disc'], then the
    ticker clause only. The three language links stay. Returns (text, form) or None when there is no headline.
    """
    rows = []
    for lang in LANGS:
        p = posts.get(lang) if isinstance(posts, dict) else None
        head, _ = _x_head_body(p.get('x') if isinstance(p, dict) else '')
        if not head:
            continue
        rows.append((lang, head, _short_headline(head)))
    if not rows:
        return None
    urls = [_x_link(lang, campaign) for lang, _, _ in rows]
    disc = _disc_line()
    tick = _ticker_block(posts)
    full_pairs = [(head, url) for (_, head, _), url in zip(rows, urls)]
    full = _assemble_lang_lines(full_pairs, disc, tick)
    if xlen(full) <= 280:
        return full, 'full'
    short_pairs = [(short, url) for (_, _, short), url in zip(rows, urls)]
    text = _assemble_lang_lines(short_pairs, disc)
    if xlen(text) <= 280:
        return text, 'short'
    text = _assemble_lang_lines(short_pairs, SHORT['en']['disc'])
    if xlen(text) <= 280:
        return text, 'short'
    facts = [(_ticker_fact(short) or short, url) for (_, _, short), url in zip(rows, urls)]
    text = _assemble_lang_lines(facts, SHORT['en']['disc'])
    if xlen(text) > 280:
        text = _cap_pairs(facts, SHORT['en']['disc'])
    return text, 'short'


def _text_ticker(text):
    """The first $TICKER the X text features, or None."""
    m = _XTICK.search(text or '')
    return m.group(1) if m else None


def _x_headlines(text):
    """zh/en/ko headline lines from a trilingual X post, verbatim."""
    heads = []
    for ln in (text or '').split('\n'):
        s = ln.strip()
        if not s:
            continue
        if re.search(r'https?://', s) or s.startswith('⚠') or s.startswith('#') or s.startswith('・'):
            continue
        heads.append(s)
        if len(heads) == 3:
            break
    return {lang: heads[i] for i, lang in enumerate(LANGS) if i < len(heads)}


_BUNDLE = None


def _picture_bundle(day=None):
    """langs, items, dash-data, daily stats — the same sources build() uses. Cached per process."""
    global _BUNDLE
    st = read_json(work('stats.json'))
    if not st or 'daily' not in st:
        return None, None, None, None
    day = day or st.get('today')
    key = (day, st.get('today'), st['daily'].get('from'), st['daily'].get('to'))
    if _BUNDLE and _BUNDLE[0] == key:
        return _BUNDLE[1]
    d = _dash_data()
    ch = read_json('data/consensus-history.json', {'days': {}})
    langs, items = build(d, st['daily'], ch, day)
    bundle = (langs, items, d, st['daily'])
    _BUNDLE = (key, bundle)
    return bundle


def _x_facts(d, items, s=None):
    """Per-ticker facts frozen with the captions, so later card rebuilds match the text."""
    av = lambda h: d['accounts'].get(h, {}).get('avatar') or d.get('avmini', {}).get(h, '')
    out = {}
    for x in items:
        facts = {k: x[k] for k in ('n', 'bull', 'bear', 'streak', 'spark', 'd1')}
        row = next((r for r in ((s or {}).get('top') or []) if r.get('t') == x['t']), None)
        if row and row.get('accounts') is not None:
            facts['n'] = row['accounts']  # accounts mentioning, as on the card's label
        accs = x.get('accs') or []
        facts['avs'] = [av(h) for h in accs[:4]]
        more = len(accs) - 4
        if more > 0:
            facts['more'] = more
        out[x['t']] = facts
    return out


def xcard_data(sp, kind, ticker, text):
    """Per-ticker card payload from build() / stats / dash-data. Omit a field when it is missing."""
    data = {'ticker': ticker, 'date': sp.get('date') or '', 'kind': kind}
    heads = _x_headlines(text)
    if heads:
        data['heads'] = heads
    langs, items, d, daily = _picture_bundle(sp.get('date'))
    zh = (langs or {}).get('zh') or {}
    if zh.get('mode'):
        data['mode'] = zh['mode']
    if zh.get('tape'):
        data['tape'] = zh['tape']
    xf = sp.get('x_facts')
    snap = xf.get(ticker) if isinstance(xf, dict) else None
    if isinstance(snap, dict):
        for k in ('n', 'bull', 'bear'):
            if snap.get(k) is not None:
                data[k] = snap[k]
        if snap.get('streak') and snap['streak'] >= 2:
            data['streak'] = snap['streak']
        if snap.get('spark'):
            data['spark'] = snap['spark']
        if snap.get('d1') is not None:
            data['d1'] = snap['d1']
        if snap.get('avs'):
            data['avs'] = snap['avs']
        if snap.get('more'):
            data['more'] = snap['more']
        return data
    hit = next((x for x in (items or []) if x.get('t') == ticker), None)
    top_row = next((x for x in ((daily or {}).get('top') or []) if x.get('t') == ticker), None)
    av = None
    if d:
        av = lambda h: d['accounts'].get(h, {}).get('avatar') or d.get('avmini', {}).get(h, '')
    if top_row:
        if top_row.get('accounts') is not None:
            data['n'] = top_row['accounts']
        if top_row.get('bull_accounts') is not None:
            data['bull'] = top_row['bull_accounts']
        if top_row.get('bear_accounts') is not None:
            data['bear'] = top_row['bear_accounts']
        accs = top_row.get('accs') or []
        if av and accs and 'avs' not in data:
            avs = [av(h) for h in accs[:4] if av(h)]
            if avs:
                data['avs'] = avs
            extra = len(accs) - len(avs or [])
            if extra > 0:
                data['more'] = extra
    if hit:
        if 'bull' not in data and hit.get('bull') is not None:
            data['bull'] = hit['bull']
        if 'bear' not in data and hit.get('bear') is not None:
            data['bear'] = hit['bear']
        if 'n' not in data and hit.get('n') is not None:
            data['n'] = hit['n']
        if hit.get('streak') and hit['streak'] >= 2:
            data['streak'] = hit['streak']
        if hit.get('spark'):
            data['spark'] = hit['spark']
        if hit.get('d1') is not None:
            data['d1'] = hit['d1']
        accs = hit.get('accs') or []
        if av and accs:
            avs = [av(h) for h in accs[:4] if av(h)]
            if avs:
                data['avs'] = avs
            extra = len(accs) - 4
            if extra > 0:
                data['more'] = extra
            else:
                data.pop('more', None)
    if 'spark' not in data and d:
        c = [r[1] for r in (d.get('prices', {}).get(ticker) or {}).get('c', []) if r[1] is not None]
        spark = c[-22:]
        if len(spark) > 1:
            data['spark'] = spark
        if len(c) > 1 and c[-2]:
            data['d1'] = round((c[-1] / c[-2] - 1) * 100, 2)
    return data


def xcard_job(sp, kind, ticker, text, out=None):
    return {'kind': kind, 'ticker': ticker, 'date': sp.get('date') or '',
            'out': out or f'og/x-{kind}.png', 'data': xcard_data(sp, kind, ticker, text)}


def _queue_xcard(job):
    """Merge a per-ticker X card job into work/xcards.json, replacing the same kind."""
    path = work('xcards.json')
    raw = read_json(path, {'jobs': []})
    jobs = raw.get('jobs') if isinstance(raw, dict) else raw
    if not isinstance(jobs, list):
        jobs = []
    jobs = [j for j in jobs if j.get('kind') != job.get('kind')]
    jobs.append(job)
    write_json(path, {'jobs': jobs}, indent=1)


def x_image(sp, kind, ticker=None):
    """Per-ticker X card when the text features a $TICKER; otherwise the generic English picture."""
    if ticker:
        day = sp.get('date') or ''
        return f'{SITE}og/x-{kind}.png?v={day}-{ticker}'
    return (sp.get('images') or {}).get('en') or ''


_PM_MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def _minus_urls(text):
    """Post body with every URL removed, for comparing premarket with afterclose."""
    return re.sub(r'https?://\S+', '', text or '').strip()


def _count(rec, key):
    """Integer count stored on an x_facts row, or None when that count is not a real number."""
    if not isinstance(rec, dict) or rec.get(key) is None or isinstance(rec.get(key), bool):
        return None
    v = rec[key]
    if isinstance(v, int) and v >= 0:
        return v
    if isinstance(v, float) and v >= 0 and v.is_integer():
        return int(v)
    if isinstance(v, str) and re.fullmatch(r'\d+', v.strip()):
        return int(v.strip())
    return None


def _pm_md_mon(sp):
    """(M/D, Mon D) for the premarket framing. `sp['date']` when it is a real day, else the afterclose date."""
    day = sp.get('date') if isinstance(sp, dict) else None
    if isinstance(day, str):
        try:
            dt = datetime.strptime(day, '%Y-%m-%d')
            return f'{dt.month}/{dt.day}', f'{_PM_MONTHS[dt.month - 1]} {dt.day}'
        except ValueError:
            pass
    text = _afterclose_text(sp) if isinstance(sp, dict) else ''
    m = _XDATE.search(text or '')
    if not m:
        return '', ''
    token = m.group(1)
    if '/' in token:
        mo, d = (int(p) for p in token.split('/'))
        mon = f'{_PM_MONTHS[mo - 1]} {d}' if 1 <= mo <= 12 else ''
        return f'{mo}/{d}', mon
    parts = token.split()
    if len(parts) == 2 and parts[0] in _PM_MONTHS and parts[1].isdigit():
        return f'{_PM_MONTHS.index(parts[0]) + 1}/{int(parts[1])}', f'{parts[0]} {int(parts[1])}'
    return '', ''


def _pm_frames(sp):
    """(zh, en, ko) framing lines. Chinese uses a fullwidth colon and no trailing space."""
    md, mon = _pm_md_mon(sp)
    zh = f'{md} 開市前：' if md else '開市前：'
    en = f'{mon} pre-market:' if mon else 'pre-market:'
    ko = f'{md} 개장 전:' if md else '개장 전:'
    return zh, en, ko


def _afterclose_text(sp):
    """Stored afterclose post, or the text trilingual_text would write for it."""
    tri = sp.get('x_trilingual') if isinstance(sp.get('x_trilingual'), dict) else None
    ac = tri.get('afterclose') if isinstance(tri, dict) else None
    if isinstance(ac, dict) and ac.get('text'):
        return ac['text']
    built = trilingual_text(sp.get('posts') or {}, 'afterclose')
    return built[0] if built else ''


def _remember_tickers(text, seen):
    for t in _XTICK.findall(text or ''):
        if t not in seen:
            seen.append(t)


def _afterclose_ticker_order(sp):
    """Tickers in the order the afterclose post names them.

    A shortened afterclose line often keeps only the headline ticker. The rest of the order is the
    headline plus the joint-bull block trilingual_text is cut down from, then any other x_facts key.
    """
    seen = []
    _remember_tickers(_afterclose_text(sp), seen)
    posts = sp.get('posts') or {}
    for lang in LANGS:
        p = posts.get(lang) if isinstance(posts, dict) else None
        head, _ = _x_head_body(p.get('x') if isinstance(p, dict) else '')
        _remember_tickers(head, seen)
    _remember_tickers(_ticker_block(posts), seen)
    return seen


def _premarket_rows(sp):
    """(ticker, bull) in afterclose order, using only x_facts rows that have a real bull count."""
    xf = sp.get('x_facts') if isinstance(sp.get('x_facts'), dict) else None
    if not xf:
        return []
    rows, seen = [], set()

    def take(t):
        if not isinstance(t, str) or t in seen or t not in xf:
            return
        bull = _count(xf[t], 'bull')
        if bull is None:
            return
        seen.add(t)
        rows.append((t, bull))

    for t in _afterclose_ticker_order(sp):
        take(t)
    for t in xf:
        take(t)
    return rows


def _lead_lines(sp, rows):
    """Three language lines. A bull tie leads with both tickers; otherwise the next ticker is a count only."""
    zh_f, en_f, ko_f = _pm_frames(sp)
    a, na = rows[0]
    tie = len(rows) >= 2 and rows[1][1] == na
    if tie:
        b = rows[1][0]
        zh = f'{zh_f}${a}、${b} 各 {na} 個帳號睇好'
        en = f'{en_f} ${a}, ${b}, {na} accounts bullish each'
        ko = f'{ko_f} ${a}·${b} 각각 계정 {na}개 강세'
    elif len(rows) >= 2:
        b, nb = rows[1]
        zh = f'{zh_f}${a} {na} 個帳號睇好 · ${b} {nb} 個'
        en = f'{en_f} ${a} {na} accounts bullish · ${b} {nb}'
        ko = f'{ko_f} ${a} 계정 {na}개 강세 · ${b} {nb}개'
    else:
        zh = f'{zh_f}${a} {na} 個帳號睇好'
        en = f'{en_f} ${a} {na} accounts bullish'
        ko = f'{ko_f} ${a} 계정 {na}개 강세'
    return zh, en, ko


def _fit_premarket(text):
    """Drop joint-bull bullets, then the long disclaimer, until the post is within 280.

    Each language line keeps its own URL. Headlines are shortened only after SHORT['en']['disc']
    still does not fit.
    """
    if xlen(text) <= 280:
        return text
    pairs, disc = _split_lang_post(text)
    return _fit_lang_lines(pairs, disc, shorten=True)


def _apply_frame(line, frame, token):
    s = line.strip()
    if s.startswith(frame):
        return s
    rest = s
    if token and s.startswith(token):
        rest = s[len(token):].lstrip(' ·・')
    if not rest:
        return frame
    if frame.endswith('：'):
        return f'{frame}{rest}'
    return f'{frame} {rest}'


def _prefix_premarket_headlines(text, sp):
    """Prefix each trilingual headline with the premarket framing. The framing already carries the date."""
    md, mon = _pm_md_mon(sp)
    posts = sp.get('posts') or {}
    langs = []
    for lang in LANGS:
        p = posts.get(lang) if isinstance(posts, dict) else None
        head, _ = _x_head_body(p.get('x') if isinstance(p, dict) else '')
        if head:
            langs.append(lang)
    if not langs:
        langs = list(LANGS)
    frames = {'zh': f'{md} 開市前：' if md else '開市前：',
              'en': f'{mon} pre-market:' if mon else 'pre-market:',
              'ko': f'{md} 개장 전:' if md else '개장 전:'}
    tokens = {'zh': md, 'en': mon, 'ko': md}
    lines, hi = [], 0
    for ln in (text or '').split('\n'):
        s = ln.strip()
        is_head = bool(s) and not re.search(r'https?://', s) and not s.startswith(('⚠', '#', '・'))
        if is_head and hi < len(langs):
            lang = langs[hi]
            lines.append(_apply_frame(s, frames[lang], tokens[lang]))
            hi += 1
        else:
            lines.append(ln)
    return '\n'.join(lines)


def _premarket_fallback(sp):
    """trilingual_text (campaign premarket) with each headline prefixed by the framing."""
    built = trilingual_text(sp.get('posts') or {}, 'premarket')
    if not built:
        return None
    text, form = built
    prefixed = _fit_premarket(_prefix_premarket_headlines(text, sp))
    return prefixed, 'short' if prefixed != text else form


def premarket_text(sp, force_fallback=False):
    """zh/en/ko premarket post. Bull counts come from x_facts, in afterclose ticker order.

    When the top two of that order tie on bull, both lead (`各 N` / `each` / `각각`).
    Otherwise the first ticker leads with its bull count and the next ticker is named with its count.
    Missing or empty x_facts uses trilingual headlines prefixed by the premarket framing.
    Returns (text, form) or None. Each language line has its own URL (campaign premarket), then
    _disc_line() or SHORT['en']['disc'] when that is what fits. xlen is at most 280.
    """
    if not isinstance(sp, dict):
        sp = {}
    ac = _minus_urls(_afterclose_text(sp))
    facts = None
    if not force_fallback:
        rows = _premarket_rows(sp)
        if rows:
            urls = [_x_link(lang, 'premarket') for lang in LANGS]
            lines = list(_lead_lines(sp, rows))
            text = _fit_lang_lines(list(zip(lines, urls)), _disc_line(), shorten=False)
            if xlen(text) > 280 and len(rows) >= 2:
                lines = list(_lead_lines(sp, rows[:1]))
                text = _fit_lang_lines(list(zip(lines, urls)), _disc_line(), shorten=False)
            if xlen(text) > 280:
                text = _fit_lang_lines(list(zip(lines, urls)), _disc_line(), shorten=True)
            if xlen(text) <= 280:
                facts = (text, 'short')
                if _minus_urls(text) != ac:
                    return facts
    built = _premarket_fallback(sp)
    if built:
        text, form = built
        if xlen(text) > 280:
            text = _fit_premarket(text)
        if facts is None or _minus_urls(text) != ac:
            return text, form
    return facts or built


def _counts_from_facts(sp, ticker):
    """bull/bear/n for the card, from x_facts only."""
    xf = sp.get('x_facts') if isinstance(sp.get('x_facts'), dict) else None
    snap = xf.get(ticker) if isinstance(xf, dict) else None
    if not isinstance(snap, dict):
        return None
    counts = {k: snap[k] for k in ('bull', 'bear', 'n') if k in snap and snap[k] is not None}
    return counts or None


def x_entry(sp, kind, force_fallback=False):
    """One x_trilingual entry, or None when there is no post to make.

    Premarket uses premarket_text. image_ticker is the first $TICKER in that text.
    Premarket card counts come from x_facts. Afterclose stays on trilingual_text.
    """
    if kind == 'premarket':
        built = premarket_text(sp, force_fallback=force_fallback)
    else:
        built = trilingual_text(sp.get('posts') or {}, kind)
    if not built:
        return None
    text, form = built
    ticker = _text_ticker(text)
    entry = {'post_at_hkt': X_WHEN[kind], 'text': text, 'image': x_image(sp, kind, ticker),
             'image_ticker': ticker, 'xlen': xlen(text), 'form': form}
    if ticker:
        job = xcard_job(sp, kind, ticker, text)
        _queue_xcard(job)
        if kind == 'premarket':
            counts = _counts_from_facts(sp, ticker)
        else:
            data = job['data']
            counts = {k: data[k] for k in ('bull', 'bear', 'n') if k in data}
        if counts:
            entry['counts'] = counts
    return entry


def build_x_trilingual(sp, rebuild_premarket=False):
    """premarket and afterclose. Rebuilds premarket when asked (the 2030 slot just got its picture).

    If the premarket body with URLs removed still equals afterclose, premarket is rebuilt from the
    framed-headline fallback so the two posts are not the same text.
    """
    tri = sp.get('x_trilingual')
    if not isinstance(tri, dict):
        tri = {}
    if rebuild_premarket or 'premarket' not in tri:
        entry = x_entry(sp, 'premarket')
        if entry:
            tri['premarket'] = entry
    if 'afterclose' not in tri:
        entry = x_entry(sp, 'afterclose')
        if entry:
            tri['afterclose'] = entry
    pm = tri.get('premarket') if isinstance(tri.get('premarket'), dict) else None
    ac = tri.get('afterclose') if isinstance(tri.get('afterclose'), dict) else None
    if pm and ac and pm.get('text') and ac.get('text') and _minus_urls(pm['text']) == _minus_urls(ac['text']):
        entry = x_entry(sp, 'premarket', force_fallback=True)
        if entry:
            tri['premarket'] = entry
    if not tri:
        return None
    return {k: tri[k] for k in ('premarket', 'afterclose') if k in tri}


def build_ig_threads_daily(sp):
    """Where the bot posts the 12:30 pictures and the 19:00 single-picture / text posts."""
    posts = sp.get('posts') or {}
    images = sp.get('images') or {}
    day = sp['date']
    slot = (sp.get('slots') or {}).get('1230') if isinstance(sp.get('slots'), dict) else None
    if not isinstance(slot, dict) or (sp.get('date') and slot.get('day') and slot.get('day') != sp.get('date')):
        slot = {}
    out = {}
    for lang in LANGS:
        row = {}
        sl_posts = (slot.get('posts') or {}).get(lang)
        sl_imgs = (slot.get('images') or {}).get(lang)
        if isinstance(sl_posts, dict) and sl_imgs:
            row['image_post'] = {
                'slot': '1230',
                'field': f'slots.1230.posts.{lang}.instagram / .threads',
                'post_at_hkt': (slot.get('post_at') or {}).get(lang) or '',
                'images': list(sl_imgs)}
        p = posts.get(lang)
        if isinstance(p, dict) and (p.get('instagram') or p.get('threads')):
            item = {'field': f'posts.{lang}.instagram / posts.{lang}.threads', 'post_at_hkt': '19:00'}
            if images.get(lang):
                item['image'] = images[lang]
            row['text_post'] = item
            row['ig_image'] = f'{SITE}og/ig-{lang}.png?v={day}'
        if row:
            out[lang] = row
    return out or None


def attach_new_posts(sp, rebuild_premarket=False):
    """Add the new keys. Does not change facebook, x, or any other existing post text."""
    if isinstance(sp.get('posts'), dict):
        add_facebook_ctas(sp['posts'])
    for sl in (sp.get('slots') or {}).values():
        if isinstance(sl, dict):
            add_facebook_ctas(sl.get('posts'))
    tri = build_x_trilingual(sp, rebuild_premarket=rebuild_premarket)
    if tri:
        sp['x_trilingual'] = tri
    daily = build_ig_threads_daily(sp)
    if daily:
        sp['ig_threads_daily'] = daily
    return sp


def _box(title, text, n, h='h3'):
    return (f'<{h}>{title}</{h}><textarea readonly rows="{n}">{html.escape(text)}</textarea>'
            '<button onclick="navigator.clipboard.writeText(this.previousElementSibling.value);this.textContent=\'已複製 ✓\'">複製</button>')


def _xtri_html(sp):
    tri = sp.get('x_trilingual') if isinstance(sp.get('x_trilingual'), dict) else None
    if not tri:
        return ''
    names = {'premarket': '開市前', 'afterclose': '收市後'}
    blocks = []
    for key in ('premarket', 'afterclose'):
        e = tri.get(key)
        if not isinstance(e, dict) or not e.get('text'):
            continue
        img = e.get('image') or ''
        pic = f'<a href="{html.escape(img)}" download><img src="{html.escape(img)}" alt=""></a>' if img else ''
        when = html.escape(str(e.get('post_at_hkt') or ''))
        form = html.escape(str(e.get('form') or ''))
        n = e.get('xlen', '')
        blocks.append(f'<h3>{names.get(key, key)} · {when} HKT · {n}/280 · {form}</h3>{pic}'
                      f'<textarea readonly rows="8">{html.escape(e["text"])}</textarea>'
                      '<button onclick="navigator.clipboard.writeText(this.previousElementSibling.value);this.textContent=\'已複製 ✓\'">複製</button>')
    if not blocks:
        return ''
    return '<section class="xtri"><h2>X 三語帖</h2>' + ''.join(blocks) + '</section>'


def _ig_daily_html(sp):
    daily = sp.get('ig_threads_daily') if isinstance(sp.get('ig_threads_daily'), dict) else None
    if not daily:
        return ''
    names = {'zh': '中文', 'en': 'English', 'ko': '한국어'}
    rows = []
    for lang in LANGS:
        row = daily.get(lang)
        if not isinstance(row, dict):
            continue
        img_p = row.get('image_post') if isinstance(row.get('image_post'), dict) else {}
        txt_p = row.get('text_post') if isinstance(row.get('text_post'), dict) else {}
        thumbs = ''.join(f'<a href="{html.escape(u)}" download><img src="{html.escape(u)}" alt=""></a>'
                         for u in (img_p.get('images') or []))
        one = txt_p.get('image') or ''
        one_html = f'<a href="{html.escape(one)}" download><img src="{html.escape(one)}" alt=""></a>' if one else ''
        cells = (('語言', names[lang]),
                 ('圖帖', f'<code>{html.escape(img_p.get("field") or "—")}</code>'),
                 ('圖帖時間', html.escape(str(img_p.get("post_at_hkt") or "—"))),
                 ('圖片', thumbs or '—'),
                 ('文字帖', f'<code>{html.escape(txt_p.get("field") or "—")}</code>'),
                 ('文字時間', html.escape(str(txt_p.get("post_at_hkt") or "—"))),
                 ('IG 圖', one_html or '—'))
        rows.append('<tr>' + ''.join(
            f'<td data-label="{html.escape(label)}"{" class=\"pics\"" if label in ("圖片", "IG 圖") else ""}>{val}</td>'
            for label, val in cells) + '</tr>')
    if not rows:
        return ''
    return ('<section class="daily"><h2>IG / Threads 每日</h2>'
            '<p>12:30 圖帖用該時段多圖。19:00 文字帖：IG 配一張圖，Threads 只發文字。</p>'
            '<table><tr><th>語言</th><th>圖帖</th><th>時間</th><th>圖片</th>'
            '<th>文字帖</th><th>時間</th><th>IG 圖</th></tr>'
            + ''.join(rows) + '</table></section>')


def social_page(sp):
    """A plain page for Tim to read the day's posts and save the pictures (not for search engines)."""
    rows = []
    for lang, name in (('zh', '中文'), ('en', 'English'), ('ko', '한국어')):
        img = sp['images'][lang]
        story = sp['stories'][lang]
        p = sp['posts'][lang]
        cta = p.get('facebook_cta') if isinstance(p, dict) else None
        rows.append(f'''<section><h2>{name}</h2><a href="{html.escape(img)}" download><img src="{html.escape(img)}" alt=""></a>
{_box('Instagram', p['instagram'], 18)}{_box('Threads', p['threads'], 10)}{_box('X', p['x'], 6)}
{_box('Reddit 標題', p['reddit']['title'], 2)}{_box('Reddit 內文', p['reddit']['body'], 14)}{_box('Facebook', p['facebook'], 18)}
{( _box('Facebook 電子報', cta, 18) if cta else '' )}
{_box('IG Story hashtag', p['story'], 2)}<h3>IG Story（1080×1920）</h3><a href="{html.escape(story)}" download><img class="story" src="{html.escape(story)}" alt=""></a></section>''')
    extras = _xtri_html(sp) + _ig_daily_html(sp)
    old = '<h2 style="margin-top:32px">舊格式（單圖，只作參考）</h2>' if sp.get('slots') else ''
    return f'''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="/favicon.ico" sizes="any"><link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="robots" content="noindex"><title>每日社交媒體貼文 {sp['date']}｜The Crowd Tape</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;margin:0 auto;max-width:760px;padding:16px;background:#f7f8fb;color:#151a2c;overflow-wrap:anywhere}}
html{{overflow-x:clip}}
section{{background:#fff;border-radius:14px;padding:16px;margin:16px 0;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
img{{width:100%;border-radius:10px}}img.story{{width:min(100%,320px);display:block;margin-top:6px}}textarea{{width:100%;box-sizing:border-box;font:inherit;margin-top:4px}}h3{{margin:18px 0 0;font-size:15px}}
button{{margin-top:8px;padding:8px 16px;border-radius:999px;border:0;background:#151a2c;color:#fff;font:inherit}}
.money-bar,.site-nav{{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;max-width:100%;min-width:0}}
.money-bar{{margin:0 0 12px;padding:8px 10px;border:1px dashed #c9c3b8;border-radius:12px;background:#fff;font-size:14px;font-weight:700}}
.tag{{font-size:11px;font-weight:700;border:1px solid #ddd;border-radius:999px;padding:1px 8px;color:#666}}
.site-foot{{margin-top:18px;padding-top:12px;border-top:1px solid #e4e7ef;font-size:13px;color:#5c6578}}
a{{color:#8a5a22}}
table{{width:100%;border-collapse:collapse;font-size:14px}}td,th{{border-bottom:1px solid #e4e7ef;padding:6px 4px;text-align:left;vertical-align:top}}
code{{font-size:12px}}.daily{{overflow-x:auto}}td.pics a{{display:inline-block;width:48px;margin:0 4px 4px 0}}td.pics img{{width:48px;height:auto}}
.xtri img{{width:min(100%,420px);display:block}}
@media (max-width:700px){{.daily table,.daily tr,.daily td{{display:block;width:auto}}.daily tr:first-child{{display:none}}
.daily td{{border:0;padding:2px 0}}.daily td::before{{content:attr(data-label);font-weight:700;display:block;font-size:12px;color:#5c6578}}
.daily tr{{padding:10px 0;border-bottom:1px solid #e4e7ef}}}}</style>
<nav class="site-nav" aria-label="網站"><a href="/zh/tools/">工具</a> · <a href="/zh/support/">支持我哋</a></nav>
<nav class="money-bar" aria-label="推廣"><span class="tag">推廣</span><a href="/zh/tools/">工具</a><a href="/zh/support/">支持我哋</a><a href="https://www.tradingview.com/?aff_id=1172819" rel="sponsored noopener" target="_blank" data-tool="tradingview" data-placement="money-bar">TradingView</a><a href="https://www.stockrover.com/thecrowdtape" rel="sponsored nofollow noopener" target="_blank" data-tool="stockrover" data-placement="money-bar">Stock Rover</a></nav>
<h1>{sp['date']} 社交媒體貼文</h1><p>{html.escape(sp['window'])}｜製作時間 {sp['made_hkt']} HKT｜撳圖片可以下載｜<a href="/social/tutorial.html">週末教學貼文</a>｜<a href="/social/macro.html">星期六宏觀貼文</a></p>
<!--slots-->
{extras}{old}
{''.join(rows)}
<footer class="site-foot"><p><a href="/zh/tools/">工具</a> · <a href="/zh/support/">支持我哋</a> · <a href="/zh/newsletter/">電子報</a> · <a href="https://www.tradingview.com/?aff_id=1172819" rel="sponsored noopener" target="_blank" data-tool="tradingview">TradingView <span class="tag">推廣</span></a> · <a href="https://www.stockrover.com/thecrowdtape" rel="sponsored nofollow noopener" target="_blank" data-tool="stockrover">Stock Rover <span class="tag">推廣</span></a></p></footer>
<script>document.addEventListener('click',function(e){{var a=e.target.closest&&e.target.closest('a[data-tool]');if(a&&window.gtag)gtag('event','affiliate_click',{{tool:a.dataset.tool,lang:document.documentElement.lang}});}});</script>
</html>
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
    old = old or ('story' not in ((sp.get('posts') or {}).get('zh') or {'story': 1})) or 'stories' not in sp  # before Facebook, Story and hashtags on every version
    social = bool(items) and (sp.get('date') != day and now.hour >= SOCIAL_HOUR and trading_day(day) or old or os.environ.get('SOCIAL_FORCE') == '1')
    if social:
        win = window(s)
        sp = {'date': day, 'made_hkt': now.strftime('%Y-%m-%d %H:%M'), 'window': win,
              'no_post_days': sorted(h for h in US_HOLIDAYS if h >= day),  # weekdays the Grok bot skips
              'images': {l: f'{SITE}og/social-{l}.png?v={day}' for l in LANGS},
              'stories': {l: f'{SITE}og/story-{l}.png?v={day}' for l in LANGS},
              'posts': {l: caption(l, day, s, items, win, langs[l]['quote']) for l in LANGS}}
        sp['x_facts'] = _x_facts(d, items, s)
        tag_posts(sp['posts'], 'daily')
        fit_threads_posts(sp['posts'])
        attach_new_posts(sp, rebuild_premarket=True)  # both X posts; carousel rebuilds premarket after the 2030 slot
        write_json('data/social-posts.json', sp, indent=1)
        os.makedirs('social', exist_ok=True)
        open('social/index.html', 'w', encoding='utf-8').write(social_page(sp))
        write_feeds(sp)
        notice(f'今日社交媒體貼文已寫好：{SITE}social/')
    if draw or social:
        write_json(work('og.json'), {'date': day, 'hash': digest, 'social': social, 'langs': langs})

    h = open(HTML, encoding='utf-8').read()
    h = re.sub(r'(?:' + re.escape(SITE) + r'|https://xmktradar\.github\.io/)og/[\w-]+\.png(\?v=[\w-]+)?', lambda m: f'{SITE}og/{day}.png?v={digest}', h)
    open(HTML, 'w', encoding='utf-8').write(h)
    print(f"share {day} mode {langs['zh']['mode']} hero {items[0]['t'] if items else '-'} draw {draw} social {social}")


def _dash_data():
    """Full dash-data from index.html, including slim pages that split accounts/prices out."""
    try:
        from slim_pages import full_data
        return full_data(open(HTML, encoding='utf-8').read())
    except Exception:
        return load(HTML)


def og_only():
    """Write work/og.json from current dash-data + work/stats.json. No social posts, no index.html rewrite."""
    st = read_json(work('stats.json'))
    if not st or 'today' not in st or 'daily' not in st:
        raise SystemExit('share --og-only: work/stats.json missing (run tools/stats.js first)')
    d = _dash_data()
    ch = read_json('data/consensus-history.json', {'days': {}})
    day, s = st['today'], st['daily']
    langs, items = build(d, s, ch, day)
    digest = hashlib.sha1(json.dumps(langs, sort_keys=True, ensure_ascii=False).encode() + open('tools/og.html', 'rb').read()).hexdigest()[:10]
    write_json(work('og.json'), {'date': day, 'hash': digest, 'social': False, 'langs': langs})
    print(f"og-only {day} mode {langs['zh']['mode']} hero {items[0]['t'] if items else '-'} langs {','.join(langs)}")


if __name__ == '__main__':
    if '--og-only' in sys.argv:
        og_only()
    else:
        main()
