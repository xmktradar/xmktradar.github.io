"""Step 8c: the three daily multi-picture posts on US trading days (Tim, 2026-10-15).

Each language posts three times a day, one theme per time slot, each post a set of 4 pictures (1080x1350) that
the Grok bot puts on X, Threads, an Instagram post and Facebook:
  1230  today's snapshot   written by the first update after 07:00 HKT (posted 12:30 zh, 13:00 en, 13:30 ko)
  1630  bull vs bear       written by the first update after 15:00 HKT (posted 16:30 zh, 17:00 en, 17:30 ko)
  2030  before the open    written by the first update after 19:00 HKT (posted 20:30 zh, 21:00 en, 21:30 ko)
Each slot is written once per day and kept; a later slot never rewrites an earlier one. No Grok: the text comes
from the summaries already on the site. Writes data/social-posts.json "slots" (next to the older single-picture
fields, which tools/share.py still writes) and social/index.html via work/ (copied in once the pictures are drawn),
and work/carousel.json for tools/carousel.js, which draws og/c/<day>-<slot>-<lang>-<n>.jpg.
"""
import html
import os
import re
from datetime import datetime, timedelta

from share import (SHORT, SITE, LANGS, attach_new_posts, clean, fit_threads, fit_threads_posts,
                    likes, page_url, social_page, tags, trading_day, xlen)
from sitedata import load, notice, now_hk, parse_iso, read_json, work, write_json
from utm import tag_posts

HTML = 'index.html'
SLOTS = (('1230', 7, ('12:30', '13:00', '13:30')),
         ('1630', 15, ('16:30', '17:00', '17:30')),
         ('2030', 19, ('20:30', '21:00', '21:30')))
THEME = {'1230': 'snap', '1630': 'duel', '2030': 'focus'}
TITLE = {'1230': {'zh': '今日快照', 'en': "Today's snapshot", 'ko': '오늘의 스냅샷'},
         '1630': {'zh': '好淡對決', 'en': 'Bull vs bear', 'ko': '강세 vs 약세'},
         '2030': {'zh': '開市前焦點', 'en': 'Before the open', 'ko': '개장 전 포커스'}}
TARGET_DAYS = 7  # price targets from the last week
TALK = {'zh': '🗣️ 大神點講', 'en': '🗣️ What the accounts say', 'ko': '🗣️ 계정들의 의견'}

ZH_PT = re.compile(r'目標價[^\d$。；，]{0,12}?(?:由\s*\$?[\d,.]+\s*(?:美元)?\s*(?:上調|下調|調)?(?:至|到)\s*)?\$?\s?(\d+(?:,\d{3})*(?:\.\d+)?)')
EN_PT = re.compile(r'(?:price target|\bPT\b)[^\d$.;]{0,25}?(?:from \$?[\d,.]+ to )?\$\s?(\d+(?:,\d{3})*(?:\.\d+)?)'
                   r'|\$(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:price target|PT\b)', re.I)

U = {
    'zh': dict(acc=lambda n: f'{n} 個帳號', bull='睇好', bear='睇淡', nb=lambda n: f'{n} 個睇好', nr=lambda n: f'{n} 個睇淡',
               swipe='👉 向左滑睇 4 張', foot='⚠️ 唔構成投資建議', follow='Follow @thecrowdtape',
               site='最新數字：thecrowdtape.com', give='☕ 支持我哋：網站底部 PayPal', posted=lambda n: f'{n} 個帳號發文',
               stocks=lambda n: f'{n} 隻股票', talk='🔥 最多人討論 Top 4', jb='🟢 共同看多', jr='🔴 共同看空', split='⚖️ 好淡分歧',
               none='今日暫時未有', vs=lambda b, r: f'{b} 好 vs {r} 淡', who='你企邊邊？留言話我知 👇', heat='📈 升溫榜（24 小時 vs 前 24 小時）',
               now=lambda a, b: f'{a} 個帳號（之前 {b}）', pt='🎯 帳號講過嘅目標價', views=lambda t: f'💬 帳號點睇 ${t}',
               hot=lambda a, b: f'24 小時內 {a} 個帳號講（之前 {b} 個）', ask='💬 一句觀點', d1='今日'),
    'en': dict(acc=lambda n: f'{n} account{"" if n == 1 else "s"}', bull='Bullish', bear='Bearish', nb=lambda n: f'{n} bullish',
               nr=lambda n: f'{n} bearish', swipe='👉 Swipe for all 4', foot='⚠️ Not investment advice', follow='Follow @thecrowdtape',
               site='Live numbers: thecrowdtape.com', give='☕ Support us: PayPal at the bottom of the site',
               posted=lambda n: f'{n} accounts posted', stocks=lambda n: f'{n} stocks', talk='🔥 Most discussed · Top 4',
               jb='🟢 Joint bullish', jr='🔴 Joint bearish', split='⚖️ Split views', none='None yet today',
               vs=lambda b, r: f'{b} bull vs {r} bear', who='Which side are you on? Tell us below 👇',
               heat='📈 Heating up (24h vs the 24h before)', now=lambda a, b: f'{a} accounts (was {b})', pt='🎯 Price targets accounts shared',
               views=lambda t: f'💬 What accounts say about ${t}', hot=lambda a, b: f'{a} accounts in 24h (was {b})',
               ask='💬 One view', d1='Today'),
    'ko': dict(acc=lambda n: f'계정 {n}개', bull='강세', bear='약세', nb=lambda n: f'강세 {n}', nr=lambda n: f'약세 {n}',
               swipe='👉 옆으로 넘겨 4장 보기', foot='⚠️ 투자 조언 아님', follow='Follow @thecrowdtape',
               site='최신 수치: thecrowdtape.com', give='☕ 후원: 사이트 하단 PayPal', posted=lambda n: f'계정 {n}개 게시',
               stocks=lambda n: f'종목 {n}개', talk='🔥 최다 언급 Top 4', jb='🟢 공동 강세', jr='🔴 공동 약세', split='⚖️ 의견 엇갈림',
               none='오늘은 아직 없음', vs=lambda b, r: f'강세 {b} vs 약세 {r}', who='여러분은 어느 쪽인가요? 댓글로 알려주세요 👇',
               heat='📈 관심 급상승 (24시간 vs 직전 24시간)', now=lambda a, b: f'계정 {a}개 (이전 {b}개)', pt='🎯 계정들이 언급한 목표가',
               views=lambda t: f'💬 ${t}에 대한 계정 의견', hot=lambda a, b: f'24시간 내 계정 {a}개 언급 (이전 {b}개)',
               ask='💬 한 줄 의견', d1='오늘'),
}
STANCE = {'睇好': 'bull', '睇淡': 'bear'}


class Site:
    def __init__(self, d):
        self.d = d
        self.by_url = {p['url']: p for p in d['posts']}

    def av(self, h):
        return self.d['accounts'].get(h, {}).get('avatar') or self.d.get('avmini', {}).get(h, '')

    def name(self, h):
        return self.d['accounts'].get(h, {}).get('name') or h

    def text(self, p, lang, n):
        t = {'zh': p.get('zh_summary') or p.get('summary_zh'), 'ko': p.get('ko_summary'),
             'en': p.get('en_summary') or p.get('text')}[lang]
        t = re.sub(r'^\((?:Reposted|轉發|리포스트)\)\s*', '', t or '')
        return clean(t, n)

    def px(self, t):
        c = [r[1] for r in (self.d.get('prices', {}).get(t) or {}).get('c', []) if r[1] is not None]
        return c[-22:], (round((c[-1] / c[-2] - 1) * 100, 2) if len(c) > 1 and c[-2] else None)


def card(site, t, rk, pills, accs=(), note=''):
    spark, d1 = site.px(t)
    return {'rk': rk, 't': t, 'pills': pills, 'avs': [site.av(h) for h in list(accs)[:4]], 'more': max(0, len(accs) - 4),
            'spark': spark, 'note': note, 'accs': list(accs)}


def qtext(site, p, lang, n):
    """A post's summary without the account's own @handle or name in front (it is already shown in bold)."""
    text = site.text(p, lang, 400)
    text = re.sub(r'^[(（](?:Reposted by|[^)）]*(?:轉發|转发|리포스트))[^)）]*[)）]\s*', '', text)  # "(Reposted by @x)" lead-in
    text = re.sub(r'^(?:(?:@?' + re.escape(p['handle']) + r'|' + re.escape(site.name(p['handle'])) + r')\s*[:：]?\s*)+', '', text, flags=re.I)
    return clean(text, n)


def side_quotes(site, t, lang, skip=(), n=2):
    """Up to n featured posts on stock t for a cover, from different accounts, most liked first, leaving out posts used elsewhere."""
    ps = [p for p in site.d['posts'] if t in (p.get('tickers') or []) and p['url'] not in skip]
    ps.sort(key=lambda p: (likes(p), p.get('time_utc', '')), reverse=True)
    out = []
    for p in ps:
        text = qtext(site, p, lang, (100 if lang == 'en' else 56) * (8 if n == 1 else 5) // 5)  # a lone quote gets more room
        if len(out) < n and len(text) >= 10 and p['handle'] not in [q['acc'] for q in out]:
            out.append({'acc': p['handle'], 'av': site.av(p['handle']), 'text': text, 'url': p['url']})
    return out


def add_quotes(site, slides, lang):
    """One featured post under every stock card: an account named on the card first, most liked first, newest as tie-break;
    never the same post twice in one carousel."""
    used = {q.get('url') for sl in slides for q in sl.get('quotes') or []}
    for sl in slides:
        for sec in sl.get('secs') or []:
            for c in sec['cards']:
                ps = [p for p in site.d['posts'] if c['t'] in (p.get('tickers') or [])]
                ps.sort(key=lambda p: (p['handle'] in c.get('accs', ()), likes(p), p.get('time_utc', '')), reverse=True)
                for p in ps:
                    text = qtext(site, p, lang, 90 if lang == 'en' else 46)
                    if len(text) >= 10 and p['url'] not in used:
                        used.add(p['url'])
                        c['q'] = {'acc': p['handle'], 'av': site.av(p['handle']), 'text': text}
                        break
    return slides


def stance_pills(lang, b, r, n):
    u = U[lang]
    out = []
    if b:
        out.append({'c': 'g', 'x': u['nb'](b)})
    if r:
        out.append({'c': 'r', 'x': u['nr'](r)})
    return out or [{'c': 'n', 'x': u['acc'](n)}]


def cta(lang):
    u = U[lang]
    return [u['follow'], u['site'], u['give']]


# ---------- 12:30 today's snapshot ----------
def snap(site, s, lang, day, win):
    u = U[lang]
    top = s['top']
    hero = top[0] if top else None
    qs = []  # up to 2 featured posts from different accounts, most liked first
    if hero:
        ps = sorted([site.by_url[x] for x in hero.get('urls', []) if x in site.by_url], key=lambda p: -likes(p))
        for p in ps:
            if len(qs) < 2 and p['handle'] not in [x['acc'] for x in qs] and site.text(p, lang, 10):
                qs.append({'acc': p['handle'], 'av': site.av(p['handle']), 'text': site.text(p, lang, 100 if lang == 'en' else 56), 'url': p['url']})
    q = qs[0] if qs else None
    cover = {'kind': 'cover', 'kicker': TITLE['1230'][lang], 'win': win,
             'lead': {'zh': '今日最多人講', 'en': 'Most talked-about today', 'ko': '오늘 가장 많이 언급된 종목'}[lang],
             'big': hero['t'] if hero else '', 'sub': u['acc'](hero['accounts']) if hero else '',
             'pills': stance_pills(lang, hero.get('bull_accounts', 0), hero.get('bear_accounts', 0), hero['accounts']) if hero else [],
             'stats': [{'c': 'b', 'l': u['posted'](s['accounts'])}, {'c': 'p', 'l': u['stocks'](s.get('tickers', 0))}],
             'quote': q, 'quotes': qs, 'swipe': u['swipe']}
    talk = {'kind': 'cards', 'secs': [{'h': u['talk'], 'cards': [
        card(site, x['t'], i + 1, stance_pills(lang, x.get('bull_accounts', 0), x.get('bear_accounts', 0), x['accounts']), x['accs'])
        for i, x in enumerate(top[:4])]}]}

    def grp(gs, side):
        return [card(site, g['t'], i + 1, stance_pills(lang, g['nb'], g['nr'], g['nb'] + g['nr']),
                     list(dict.fromkeys(r['acc'] for r in g['rows'] if r['s'] == side))) for i, g in enumerate(gs[:3])]
    joint = {'kind': 'cards', 'secs': [{'h': u['jb'], 'cards': grp(sorted(s['bull'], key=lambda g: -g['nb']), 'bull'), 'empty': u['none']},
                                       {'h': u['jr'], 'cards': grp(sorted(s['bear'], key=lambda g: -g['nr']), 'bear'), 'empty': u['none']}]}
    sp = sorted(s['split'], key=lambda g: -(g['nb'] + g['nr']))[:3]
    split = {'kind': 'cards', 'secs': [{'h': u['split'], 'cards': [
        card(site, g['t'], i + 1, [{'c': 'g', 'x': u['nb'](g['nb'])}, {'c': 'r', 'x': u['nr'](g['nr'])}],
             list(dict.fromkeys(r['acc'] for r in g['rows']))) for i, g in enumerate(sp)], 'empty': u['none']}], 'cta': cta(lang)}
    return [cover, talk, joint, split]


# ---------- 16:30 bull vs bear ----------
def duel_pick(site, s, day, used=()):
    """The most argued-over stock today (one the earlier slot did not lead with, when there is a choice), with each
    account's latest view on it; fallback: the most discussed stock."""
    groups = sorted(s['split'], key=lambda g: -(g['nb'] + g['nr']))
    groups = [g for g in groups if g['t'] not in used] + [g for g in groups if g['t'] in used]
    if groups:
        g = groups[0]
        rows, seen = [], set()
        for r in sorted(g['rows'], key=lambda r: -r.get('ms', 0)):
            if r['acc'] not in seen:
                seen.add(r['acc'])
                rows.append(r)
        return g['t'], g['nb'], g['nr'], rows
    if not s['top']:
        return None, 0, 0, []
    t = s['top'][0]['t']
    rows, seen = [], set()
    ps = [site.by_url[u] for u in s['top'][0].get('urls', []) if u in site.by_url]
    for p in sorted(ps, key=lambda p: p.get('time_utc', ''), reverse=True):
        st = STANCE.get((p.get('stance_by_ticker') or {}).get(t) or p.get('stance'), 'neutral')
        if p['handle'] not in seen:
            seen.add(p['handle'])
            rows.append({'acc': p['handle'], 's': st, 'url': p['url']})
    return t, sum(r['s'] == 'bull' for r in rows), sum(r['s'] == 'bear' for r in rows), rows


def duel_three(rows):
    """Three accounts for slides 2-4: alternate bull and bear so both sides get heard."""
    b = [r for r in rows if r['s'] == 'bull']
    r_ = [r for r in rows if r['s'] == 'bear']
    n = [r for r in rows if r['s'] not in ('bull', 'bear')]
    out = []
    while len(out) < 3 and (b or r_ or n):
        for side in (b, r_):
            if side and len(out) < 3:
                out.append(side.pop(0))
        if not b and not r_ and n and len(out) < 3:
            out.append(n.pop(0))
    return out


def duel(site, s, lang, day, win, pick):
    u = U[lang]
    t, nb, nr, rows = pick
    spark, d1 = site.px(t) if t else ([], None)
    cover = {'kind': 'cover', 'kicker': TITLE['1630'][lang], 'win': win,
             'lead': {'zh': '今日分歧最大', 'en': 'Most divided today', 'ko': '오늘 가장 엇갈린 종목'}[lang] if s['split'] else
                     {'zh': '今日最多人講', 'en': 'Most talked-about today', 'ko': '오늘 가장 많이 언급된 종목'}[lang],
             'big': t or '', 'sub': u['vs'](nb, nr), 'bar': [nb, nr], 'spark': spark, 'd1': d1, 'd1l': u['d1'],
             'quote': None, 'swipe': u['swipe'], 'note': u['who']}
    cover['quotes'] = side_quotes(site, t, lang, skip={r['url'] for r in duel_three(rows)}, n=1) if t else []
    slides = [cover]
    for i, r in enumerate(duel_three(rows)):
        p = site.by_url.get(r['url'], {})
        slides.append({'kind': 'account', 'kicker': TITLE['1630'][lang], 't': t, 'acc': r['acc'], 'name': site.name(r['acc']),
                       'av': site.av(r['acc']), 'side': r['s'],
                       'badge': u['bull'] if r['s'] == 'bull' else (u['bear'] if r['s'] == 'bear' else {'zh': '中性', 'en': 'Neutral', 'ko': '중립'}[lang]),
                       'text': site.text(p, lang, 330 if lang == 'en' else 170) or clean(r.get('why', ''), 170),
                       'when': (p.get('time_hkt') or '')[5:16].replace('T', ' ').replace('-', '/') + ' HKT' if p else ''})
    while len(slides) < 4:  # fewer than three accounts: close with the call to action
        slides.append({'kind': 'cards', 'secs': [], 'cta': cta(lang)})
    return slides


# ---------- 20:30 before the open ----------
def heat(d, now):
    """Accounts mentioning each stock in the last 24 hours vs the 24 hours before."""
    a, b = {}, {}
    for p in d['posts']:
        try:
            ts = parse_iso(p['time_utc'])
        except (KeyError, ValueError):
            continue
        age = (now - ts).total_seconds() / 3600
        box = a if 0 <= age < 24 else (b if 24 <= age < 48 else None)
        if box is None:
            continue
        for t in p.get('tickers') or []:
            box.setdefault(t, set()).add(p['handle'])
    rows = [{'t': t, 'now': len(h), 'was': len(b.get(t, ())), 'accs': sorted(h)} for t, h in a.items() if len(h) >= 2]
    rows.sort(key=lambda x: (-(x['now'] - x['was']), -x['now']))
    return rows


def targets(site, now):
    """Price targets written in the summaries of the last week: ticker, price, account, newest first."""
    out, seen = [], set()
    cut = now - timedelta(days=TARGET_DAYS)
    for p in site.d['posts']:
        try:
            ts = parse_iso(p['time_utc'])
        except (KeyError, ValueError):
            continue
        if ts < cut:
            continue
        for f, rx in (('zh_summary', ZH_PT), ('en_summary', EN_PT)):
            t = p.get(f) or ''
            for m in rx.finditer(t):
                v = m.group(1) or (m.group(2) if m.lastindex and m.lastindex >= 2 else None)
                if not v:
                    continue
                pre = re.findall(r'\$([A-Z]{1,6})\b', t[max(0, m.start() - 60):m.start()])
                tk = pre[-1] if pre else (p['tickers'][0] if len(p.get('tickers') or []) == 1 else None)
                key = (p['handle'], tk)
                if not tk or key in seen:
                    continue
                seen.add(key)
                out.append({'t': tk, 'pt': v, 'acc': p['handle'], 'url': p['url'], 'ts': p['time_utc'], 'day': p.get('day', '')})
    out.sort(key=lambda x: x['ts'], reverse=True)
    one, seen_acc = [], set()  # one target per account, so a single analyst-notes post does not fill the list
    for x in out:
        if x['acc'] not in seen_acc:
            seen_acc.add(x['acc'])
            one.append(x)
    return one


def focus_pick(site, s, now, used=()):
    """Stocks heating up, leading with one the earlier slots did not lead with when there is a choice."""
    hot = heat(site.d, now)
    hot = [x for x in hot if x['t'] not in used] + [x for x in hot if x['t'] in used]
    pts = targets(site, now)[:4]
    lead = {hot[0]['t']} if hot else set()
    alt = next((x for x in s['top'] if x['t'] not in lead | set(used)), None)
    return hot, pts, alt


def views_of(site, x, lang):
    rows, seen = [], set()
    ps = [site.by_url[u] for u in x.get('urls', []) if u in site.by_url]
    for p in sorted(ps, key=lambda p: -likes(p)):
        if p['handle'] in seen or not site.text(p, lang, 10):
            continue
        seen.add(p['handle'])
        st = STANCE.get((p.get('stance_by_ticker') or {}).get(x['t']) or p.get('stance'), 'neutral')
        rows.append({'acc': p['handle'], 's': st, 'text': site.text(p, lang, 110 if lang == 'en' else 60), 'url': p['url']})
        if len(rows) == 3:
            break
    return rows


def focus(site, s, lang, day, win, pick):
    u = U[lang]
    hot, pts, alt = pick
    h0 = hot[0] if hot else None
    spark, d1 = site.px(h0['t']) if h0 else ([], None)
    q = None
    if h0:
        for p in sorted([p for p in site.d['posts'] if h0['t'] in (p.get('tickers') or [])], key=lambda p: p.get('time_utc', ''), reverse=True)[:8]:
            if site.text(p, lang, 10):
                q = {'acc': p['handle'], 'av': site.av(p['handle']), 'text': site.text(p, lang, 200 if lang == 'en' else 110), 'url': p['url']}
                break
    cover = {'kind': 'cover', 'kicker': TITLE['2030'][lang], 'win': win,
             'lead': {'zh': '升溫最快', 'en': 'Heating up fastest', 'ko': '가장 빠르게 뜨는 종목'}[lang],
             'big': h0['t'] if h0 else '', 'sub': u['hot'](h0['now'], h0['was']) if h0 else '', 'spark': spark, 'd1': d1, 'd1l': u['d1'],
             'quote': None, 'swipe': u['swipe']}
    cover['quotes'] = side_quotes(site, h0['t'], lang, skip={q['url']} if q else (), n=1) if h0 else []
    rise = {'kind': 'cards', 'secs': [{'h': u['heat'], 'cards': [
        card(site, x['t'], i + 1, [{'c': 'o', 'x': f"+{x['now'] - x['was']}" if x['now'] > x['was'] else '±0'}, {'c': 'n', 'x': u['now'](x['now'], x['was'])}], x['accs'])
        for i, x in enumerate(hot[:4])], 'empty': u['none']}]}
    if pts:
        third = {'kind': 'targets', 'h': u['pt'], 'rows': [
            {'t': x['t'], 'pt': x['pt'], 'acc': x['acc'], 'av': site.av(x['acc']), 'day': x['day'][5:].replace('-', '/'),
             'text': qtext(site, site.by_url[x['url']], lang, 90 if lang == 'en' else 46) if x['url'] in site.by_url else ''} for x in pts]}
    elif alt:
        third = {'kind': 'views', 'h': u['views'](alt['t']), 't': alt['t'], 'rows': [
            dict(r, av=site.av(r['acc']), badge=u['bull'] if r['s'] == 'bull' else (u['bear'] if r['s'] == 'bear' else {'zh': '中性', 'en': 'Neutral', 'ko': '중립'}[lang]))
            for r in views_of(site, alt, lang)]}
    else:
        third = {'kind': 'cards', 'secs': [], 'cta': cta(lang)}
    last = {'kind': 'quote', 'h': u['ask'] + (f" · ${h0['t']}" if h0 else ''), 'quote': q, 'cta': cta(lang)}
    return [cover, rise, third, last]


# Picture 3 carries a "what the accounts say" label. The characters were dropped on 2026-10-23 (Tim: looked unprofessional).
def label_talk(slides, lang):
    slides[2]['talk'] = TALK[lang]
    return slides


# ---------- captions ----------
def head_line(slot, lang, day, lead):
    m, dd = int(day[5:7]), int(day[8:10])
    if lang == 'en':
        mon = datetime.strptime(day, '%Y-%m-%d').strftime('%b %-d')
        return f'{mon} · {TITLE[slot][lang]}: {lead}'
    return f'{m}/{dd} {TITLE[slot][lang]}：{lead}' if lang == 'zh' else f'{m}/{dd} {TITLE[slot][lang]}: {lead}'


END = {'zh': ['👉 左右滑睇晒 4 張圖', '網站約每 4 個鐘更新，最新數字 👉 link in bio (thecrowdtape.com)', '☕ 鍾意就請我哋飲杯咖啡：link in bio，網站底部 PayPal 捐款 🙏', 'Follow @thecrowdtape 每日睇街貨點諗。'],
       'en': ['👉 Swipe through all 4 pictures', 'Updated about every 4 hours. Latest numbers 👉 link in bio (thecrowdtape.com)', '☕ Enjoy it? Buy us a coffee: link in bio, PayPal at the bottom of the site 🙏', 'Follow @thecrowdtape for the daily read on what the crowd thinks.'],
       'ko': ['👉 옆으로 넘겨 4장 모두 보기', '약 4시간마다 업데이트, 최신 수치 👉 프로필 링크 (thecrowdtape.com)', '☕ 도움이 되셨다면 커피 한 잔 후원해 주세요: 프로필 링크, 사이트 하단 PayPal 🙏', '@thecrowdtape 팔로우하고 매일 시장 분위기를 확인하세요.']}


FB_TAP = {'zh': '👉 撳圖睇晒 4 張', 'en': '👉 Tap a picture to see all 4', 'ko': '👉 사진을 눌러 4장 모두 보기'}  # Facebook has no swiping


def versions(lang, head, body, tks):
    """Instagram, Facebook, Threads and X versions from a headline and body blocks (most important first)."""
    tg = tags(lang, tks)
    url = page_url(lang)
    short = SHORT[lang]
    give = f"{short['give']}{url}#donate"
    ig = '\n\n'.join([head, *body, '\n'.join(END[lang]), short['disc_long'], tg])
    fb = '\n\n'.join([head, *body, f"{FB_TAP[lang]}\n{short['live']}{url}\n{give}", short['disc_long'], tg])

    def fit(blocks, limit, size, tail):
        blocks = [b for b in blocks if b]
        while True:
            txt = '\n\n'.join(blocks + [tail])
            if size(txt) <= limit or len(blocks) <= 1:
                break
            last = blocks[-1].split('\n')
            if len(last) > 1:
                blocks[-1] = '\n'.join(last[:-1])
            else:
                blocks.pop()
        while size(txt) > limit and len(blocks[0]) > 20:  # a very long headline
            blocks[0] = blocks[0][:-12].rstrip() + '…'
            txt = '\n\n'.join(blocks + [tail])
        return txt
    threads = fit_threads('\n\n'.join([b for b in [head, *body] if b] + [
        f"{short['live']}{url}\n{give}\n{short['disc']}\n{tg.split(' ')[0]}"]), lang)
    xt = [x for x in tks if re.fullmatch(r'[A-Z]{1,6}', x)]
    xtags = ' '.join([tg.split(' ')[0]] + [f'#{t}' for t in xt[:2]])
    n = 90 if lang == 'en' else 45  # X has little room: shorten each line
    xbody = ['\n'.join(clean(ln, n) for ln in body[0].split('\n'))] if body else []
    x = None
    for tail in (f"{short['live']}{url}\n{give}\n{short['disc']}\n{xtags}", f"{short['live']}{url}\n{short['disc']}\n{xtags}",
                 f"{short['live']}{url}\n{short['disc']}\n{tg.split(' ')[0]}"):
        x = fit([head, *xbody], 270, xlen, tail)
        if xlen(x) <= 270 and len(x.split('\n\n')) > 2:
            break
    return {'instagram': ig, 'threads': threads, 'x': x, 'facebook': fb}


def cap_duel(site, s, lang, day, pick):
    u = U[lang]
    t, nb, nr, rows = pick
    if not t:
        return None
    head = head_line('1630', lang, day, f'${t} {u["vs"](nb, nr)} ⚔️')
    lines = []
    for r in duel_three(rows):
        p = site.by_url.get(r['url'], {})
        icon = '🟢' if r['s'] == 'bull' else ('🔴' if r['s'] == 'bear' else '⚪')
        lines.append(f"{icon} @{r['acc']}：{site.text(p, lang, 150 if lang == 'en' else 80)}" if lang == 'zh' else
                     f"{icon} @{r['acc']}: {site.text(p, lang, 150 if lang == 'en' else 80)}")
    return versions(lang, head, ['\n'.join(lines), u['who']], [t])


def cap_focus(site, s, lang, day, pick):
    u = U[lang]
    hot, pts, alt = pick
    if not hot and not alt:
        return None
    h0 = hot[0] if hot else None
    sep = '：' if lang == 'zh' else ': '
    head = head_line('2030', lang, day, f"${h0['t']} 🚀 {u['hot'](h0['now'], h0['was'])}" if h0 else f"${alt['t']}")
    body = []
    if hot:
        body.append('\n'.join([u['heat']] + [f"・${x['t']}{sep}{u['now'](x['now'], x['was'])}" for x in hot[:5]]))
    if pts:
        body.append('\n'.join([u['pt']] + [f"・${x['t']} ${x['pt']}（@{x['acc']}，{x['day'][5:].replace('-', '/')}）" if lang == 'zh' else
                                           f"・${x['t']} ${x['pt']} (@{x['acc']}, {x['day'][5:].replace('-', '/')})" for x in pts]))
    elif alt:
        vs = views_of(site, alt, lang)
        if vs:
            body.append('\n'.join([u['views'](alt['t'])] + [
                f"{'🟢' if r['s'] == 'bull' else ('🔴' if r['s'] == 'bear' else '⚪')} @{r['acc']}{sep}{r['text']}" for r in vs]))
    tks = [x['t'] for x in hot[:3]] + [x['t'] for x in pts[:2]] + ([alt['t']] if alt else [])
    return versions(lang, head, body, list(dict.fromkeys(tks)))


def slot_page(sp):
    """The three time slots at the top of /social/: 4 pictures and each platform's text."""
    out = []
    names = {'zh': '中文', 'en': 'English', 'ko': '한국어'}
    box = lambda title, text, n: (f'<h4>{title}</h4><textarea readonly rows="{n}">{html.escape(text)}</textarea>'
                                  '<button onclick="navigator.clipboard.writeText(this.previousElementSibling.value);this.textContent=\'已複製 ✓\'">複製</button>')
    for key, _, times in SLOTS:
        sl = sp.get('slots', {}).get(key)
        if not sl:
            out.append(f'<section class="slot"><h2>{times[0]} {TITLE[key]["zh"]}</h2><p>今日未寫好（{SLOT_HOUR[key]:02d}:05 後第一次網站更新先寫）。</p></section>')
            continue
        langs = []
        for i, lang in enumerate(LANGS):
            p = sl['posts'][lang]
            imgs = ''.join(f'<a href="{html.escape(u)}" download><img src="{html.escape(u)}" alt="{n + 1}"></a>' for n, u in enumerate(sl['images'][lang]))
            langs.append(f'<details{" open" if lang == "zh" else ""}><summary>{names[lang]}・{times[i]} 發</summary><div class="grid">{imgs}</div>'
                         f"{box('X', p['x'], 7)}{box('Threads', p['threads'], 10)}{box('Instagram', p['instagram'], 16)}"
                         + (f'<h4>Facebook 用正方形圖</h4><div class="grid">' + ''.join(f'<a href="{html.escape(u)}" download><img src="{html.escape(u)}" alt="FB {n + 1}"></a>'
                                                                              for n, u in enumerate(sl['images_fb'][lang])) + '</div>' if sl.get('images_fb') else '')
                         + f"{box('Facebook', p['facebook'], 16)}"
                         + (box('Facebook 電子報', p['facebook_cta'], 18) if p.get('facebook_cta') else '')
                         + (box('IG Story hashtag', p.get('story', ''), 2) if sl.get('story') else '') + '</details>')
        out.append(f'<section class="slot"><h2>{times[0]} {TITLE[key]["zh"]}</h2><p>製作時間 {sl["made_hkt"]} HKT・'
                   f'{"有 IG Story（圖喺下面每個語言嘅舊格式部分）" if sl.get("story") else "冇 IG Story"}</p>{"".join(langs)}</section>')
    css = ('<style>.slot .grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:8px}.slot .grid img{border-radius:6px}'
           'details{margin-top:10px}summary{font-weight:700;cursor:pointer}h4{margin:12px 0 0;font-size:14px}</style>')
    return css + '<h2 style="margin-top:24px">今日三個時段（多圖帖，Grok bot 用呢度）</h2>' + ''.join(out)


SLOT_HOUR = {k: h for k, h, _ in SLOTS}


def write_page(sp, path):
    page = social_page(sp)
    block = slot_page(sp)
    if '<!--slots-->' in page:
        page = page.replace('<!--slots-->', block, 1)
    else:
        i = page.index('<section>') if '<section>' in page else page.rindex('</html>')
        page = page[:i] + block + page[i:]
    open(path, 'w', encoding='utf-8').write(page)


def main():
    st = read_json(work('stats.json'))
    if not st:
        return
    day, s = st['today'], st['daily']
    sp = read_json('data/social-posts.json', {})
    force = os.environ.get('CAROUSEL_FORCE') == '1'
    if sp.get('date') != day or not (trading_day(day) or force):
        print('carousel: no posts today')
        return
    now = now_hk()
    slots = sp.get('slots') or {}
    if force or any(v.get('day') != day for v in slots.values()):
        slots = {}
    todo = [k for k, h, _ in SLOTS if (now.hour >= h or force) and (k not in slots or force)]
    if not todo:
        return
    site = Site(load(HTML))
    from share import window
    win = window(s)
    jobs, written = [], []
    used = [s['top'][0]['t']] if s['top'] else []  # each slot leads with a different stock when it can
    used += [v['ticker'] for v in slots.values() if v.get('ticker')]
    for key in todo:
        if key == '1230':
            pick = None
        elif key == '1630':
            pick = duel_pick(site, s, day, used)
            used.append(pick[0])
        else:
            pick = focus_pick(site, s, now, used)
        made = {}
        for lang in LANGS:
            if key == '1230':
                slides = snap(site, s, lang, day, win)
                posts = dict(sp['posts'][lang])
                posts.pop('reddit', None)
                for k, see in (('instagram', END[lang][0]), ('facebook', FB_TAP[lang])):  # single-picture text, plus "swipe"/"tap" under the headline
                    posts[k] = posts[k].replace('\n\n', f'\n\n{see}\n\n', 1)
                for k, v in posts.items():
                    if isinstance(v, str):
                        posts[k] = v.replace('utm_campaign=daily', 'utm_campaign=carousel')
            elif key == '1630':
                slides = duel(site, s, lang, day, win, pick)
                posts = cap_duel(site, s, lang, day, pick)
            else:
                slides = focus(site, s, lang, day, win, pick)
                posts = cap_focus(site, s, lang, day, pick)
            if not posts:
                break
            slides = add_quotes(site, slides, lang)
            slides = label_talk(slides, lang)
            files = [f'og/c/{day}-{key}-{lang}-{n + 1}.jpg' for n in range(4)]
            fb = [f'og/c/{day}-{key}-{lang}-{n + 1}-fb.jpg' for n in range(4)]
            jobs.append({'slot': key, 'theme': THEME[key], 'lang': lang, 'date': day, 'slides': slides, 'files': files, 'fb': fb})
            made[lang] = {'images': [f'{SITE}{f}' for f in files], 'images_fb': [f'{SITE}{f}' for f in fb], 'posts': posts}
        if len(made) != len(LANGS):
            notice(f'{key} 時段冇足夠數據，今次唔寫', 'warning')
            continue
        times = dict(zip(LANGS, next(t for k, _, t in SLOTS if k == key)))
        lead = {'1230': s['top'][0]['t'] if s['top'] else None, '1630': pick[0] if key == '1630' else None,
                '2030': (pick[0][0]['t'] if pick[0] else (pick[2] or {}).get('t')) if key == '2030' else None}[key]
        slots[key] = {'day': day, 'theme': THEME[key], 'ticker': lead, 'title': TITLE[key], 'made_hkt': now.strftime('%Y-%m-%d %H:%M'),
                      'post_at': times, 'story': key == '1230',
                      'platforms': ['x', 'threads', 'instagram', 'instagram_story', 'facebook'] if key == '1230' else ['x', 'threads', 'instagram', 'facebook'],
                      'images': {l: made[l]['images'] for l in LANGS}, 'images_fb': {l: made[l]['images_fb'] for l in LANGS}, 'posts': {l: made[l]['posts'] for l in LANGS}}
        if key == '1230':
            slots[key]['stories'] = sp.get('stories', {})
        written.append(key)
    if not jobs:
        return
    sp['slots'] = {k: slots[k] for k, _, _ in SLOTS if k in slots}
    sp.pop('pose_log', None)
    for sl in (sp.get('slots') or {}).values():
        if sl.get('posts'):
            tag_posts(sl['posts'], 'carousel')
            fit_threads_posts(sl['posts'])
    # 19:05 writes the 2030 slot before the 21:00 trilingual post, so premarket is rebuilt with that day's card.
    attach_new_posts(sp, rebuild_premarket='2030' in written)
    # The new text goes into place only after tools/carousel.js has drawn the pictures (see update-site.yml).
    write_json(work('carousel.json'), {'date': day, 'jobs': jobs})
    write_json(work('social-posts.json'), sp, indent=1)
    write_page(sp, work('social.html'))
    notice(f"社交多圖帖已寫好：{', '.join(todo)}（{SITE}social/）")


if __name__ == '__main__':
    main()
