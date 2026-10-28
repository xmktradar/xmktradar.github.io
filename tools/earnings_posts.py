"""Earnings briefs, step 3: one social post per company after its results (Tim, 2026-10-27), all made here (no AI).

New results come from data/earnings/state.json "new" (tools/earnings_data.py). Each company waits in a queue for the
next posting slot of a US-results day:
  1000  filled by the first update between 06:00 and 09:40 HKT, posted 10:00 HKT (zh, then en)
  2200  filled by the first update between 18:00 and 21:40 HKT, posted 22:00 HKT (zh, then en)
At most DAILY_CAP companies a day (per language, same companies in both), largest market cap first; a company still
waiting 72 hours after its results was found is dropped (the brief page stays on the site). Each post is 4 pictures
(1080x1350, plus square copies for Facebook) drawn by tools/earnings_cards.js from work/earnings_cards.json, and
captions for X, Threads, Instagram and Facebook. Writes data/earnings-posts.json and social/earnings.html via work/
(copied in by update-site.yml once the pictures exist). The first slot of the day also picks the day's video:
the largest company posted since the previous morning (work/earnings_video.json, tools/earnings_video.py).
"""
import html
import os
import re
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from earnings_pages import L as PL, by_end, money, pct, prev_q, spct, ttm_fcf, year_ago, eps_s, margin  # noqa: E402
from share import SITE, LANGS, ig_tags, sanitize_instagram, xlen  # noqa: E402
from sitedata import notice, now_hk, read_json, work, write_json  # noqa: E402

DATA = 'data/earnings-posts.json'
STATE = 'data/earnings/state.json'
CO_DIR = 'data/earnings/co'
DAILY_CAP = 5
WAIT_HOURS = 72
SLOTS = {'1000': ((6, 0), (9, 40), '10:00'), '2200': ((18, 0), (21, 40), '22:00')}
VIDEO_AT = '11:00'

T = {
    'zh': dict(head=lambda t, q: f'📊 ${t} 財報（{q}）', rev=lambda r, y: f'收入 {r}，按年 {y}',
               vs_rev=lambda d, w: f'，{w}市場預期 {abs(d):.1f}%', better='好過', worse='差過', inline='，同市場預期差唔多',
               eps=lambda a, e, ok: f'經調整 EPS {a}' + (f'，預期 {e} {ok}' if e else ''),
               margins=lambda g, n: '｜'.join(x for x in (f'毛利率 {g}' if g else '', f'淨利率 {n}' if n else '') if x),
               seg=lambda n, s, y: f'最大收入線：{n} 佔 {s}' + (f'（按年 {y}）' if y else ''),
               fcf=lambda v: f'自由現金流（過去 4 季）{v}', link='完整 5 章簡報 👉 ', bio='完整 5 章簡報：連結在個人簡介',
               give='☕ 鍾意就支持我哋 👉 ', disc='⚠️ 只係整理公開財報數字，唔構成投資建議。',
               tags='#美股 #財報 #美股投資 #港人投資', swipe=lambda n: f'👉 向左滑睇 {n} 張',
               views=lambda b, r: f'🗣 X 大神點睇（近 28 日）：{b} 個看多、{r} 個看空 👉 ', views_none='🗣 X 大神點睇 👉 ',
               why=lambda s, a, r: f"{'🟢 看多' if s == 'bull' else '🔴 看空'} @{a}：{r}"),
    'en': dict(head=lambda t, q: f'📊 ${t} earnings ({q})', rev=lambda r, y: f'Revenue {r}, {y} YoY',
               vs_rev=lambda d, w: f', {w} estimates by {abs(d):.1f}%', better='beat', worse='missed', inline=', in line with estimates',
               eps=lambda a, e, ok: f'Adjusted EPS {a}' + (f' vs {e} expected {ok}' if e else ''),
               margins=lambda g, n: ' | '.join(x for x in (f'Gross margin {g}' if g else '', f'Net margin {n}' if n else '') if x),
               seg=lambda n, s, y: f'Biggest line: {n}, {s} of revenue' + (f' ({y} YoY)' if y else ''),
               fcf=lambda v: f'Free cash flow (last 4 quarters) {v}', link='Full 5-chapter brief 👉 ', bio='Full 5-chapter brief: link in bio',
               give='☕ Support the site 👉 ', disc='⚠️ A summary of public results, not investment advice.',
               tags='#StockMarket #Earnings #USStocks #Investing', swipe=lambda n: f'👉 Swipe for all {n}',
               views=lambda b, r: f'🗣 What X accounts say (28 days): {b} bullish, {r} bearish 👉 ', views_none='🗣 What X accounts say 👉 ',
               why=lambda s, a, r: f"{'🟢 Bull' if s == 'bull' else '🔴 Bear'} @{a}: {r}"),
}
CARD = {
    'zh': dict(kick='財報速覽', rev='收入', eps='經調整 EPS', est='預期', beat='好過預期', miss='差過預期', inline='符合預期',
               growth='成長同利潤率', yoy='按年', qoq='按季', gm='毛利率', om='經營利潤率', nm='淨利率', rev8='最近 8 季收入',
               lines='收入線拆解', share='佔比', noseg='公司冇按業務線拆解收入', cash='現金流', liquid='現金 + 短期投資', debt='債務',
               fcf_q='自由現金流（今季）', fcf_4='自由現金流（4 季）', net_cash='淨現金', net_debt='淨負債',
               ok='✅ 自由現金流為正', bad=lambda m: f'⚠️ 現金大約撐 {m} 個月', bank='銀行唔計撐得幾耐',
               more='完整 5 章 👉 thecrowdtape.com', foot='⚠️ 唔構成投資建議', nodata='—', year='全年數字',
               views='X 大神點睇', views_sub='近 28 日，每個帳號最新立場', bull='看多', bear='看空', neu='中性', views_more='全部大神點睇 👉 ',
               others=lambda n: f'仲有 {n} 個大神，睇網站'),
    'en': dict(kick='Earnings at a glance', rev='Revenue', eps='Adjusted EPS', est='est.', beat='Beat', miss='Miss', inline='In line',
               growth='Growth and margins', yoy='YoY', qoq='QoQ', gm='Gross margin', om='Operating margin', nm='Net margin', rev8='Revenue, last 8 quarters',
               lines='Revenue lines', share='share', noseg='No revenue breakdown in the filing', cash='Cash flow', liquid='Cash + short-term inv.', debt='Debt',
               fcf_q='Free cash flow (qtr)', fcf_4='Free cash flow (4 qtrs)', net_cash='Net cash', net_debt='Net debt',
               ok='✅ Free cash flow is positive', bad=lambda m: f'⚠️ Cash lasts about {m} months', bank='Banks: runway does not apply',
               more='Full brief 👉 thecrowdtape.com', foot='⚠️ Not investment advice', nodata='—', year='full-year figures',
               views='What X accounts say', views_sub="Each account's latest stance, last 28 days", bull='Bullish', bear='Bearish', neu='Neutral', views_more='All views 👉 ',
               others=lambda n: f'+{n} more accounts on the site'),
}


def brief_url(lang, t):
    return f'{SITE}{lang}/earnings/{t}/'


def stock_url(lang, t):
    """The stock's account-views page (tools/stock_pages.js), or None when the site has no page for it."""
    slug = re.sub(r'[^A-Za-z0-9.\-]', '_', t)
    return f'{SITE}{lang}/stock/{slug}/' if os.path.isdir(f'{lang}/stock/{slug}') else None


_VIEWS = {}


POSTS_GLOB = 'data/dash/master-posts-*.json'
STANCE = {'睇好': 'bull', '睇淡': 'bear', '中性': 'neu'}


def views(t):
    """Each tracked account's latest stance on t in the last 28 days, from the site's own post data (the
    same posts the stock page lists), or None when no account was clearly bullish or bearish."""
    if 'by' not in _VIEWS:
        import glob
        cut = (datetime.utcnow() - timedelta(days=28)).strftime('%Y-%m-%dT%H:%M:%SZ')
        last = {}
        for f in sorted(glob.glob(POSTS_GLOB)):
            for p in read_json(f, []) or []:
                if p.get('reposted_by') or p.get('folded_into') or (p.get('time_utc') or '') < cut:
                    continue
                for tk, s in (p.get('stance_by_ticker') or {}).items():
                    k = (tk, p.get('handle'))
                    if s in STANCE and (k not in last or p['time_utc'] > last[k]['time_utc']):
                        last[k] = p
        by = {}
        for (tk, h), p in last.items():
            by.setdefault(tk, []).append({'acc': h, 's': STANCE[p['stance_by_ticker'][tk]], 'p': p, 'at': p['time_utc']})
        _VIEWS['by'] = by
    rows = _VIEWS['by'].get(t) or []
    nb, nr = sum(r['s'] == 'bull' for r in rows), sum(r['s'] == 'bear' for r in rows)
    if not nb + nr:
        return None
    # Posts about this stock first (a reason written for it, or few tickers), then the newest
    side = lambda s: sorted((r for r in rows if r['s'] == s), key=lambda r: (on_topic(r['p'], t), r['at']), reverse=True)  # noqa: E731
    a, b = (side('bull'), side('bear')) if nb >= nr else (side('bear'), side('bull'))
    mixed = [x for pair in zip(a, b) for x in pair] + a[len(b):] + b[len(a):]  # both sides near the top
    return {'nb': nb, 'nr': nr, 'neu': len(rows) - nb - nr, 'accs': mixed}


def on_topic(p, t):
    """2: the post has a reason written for t; 1: it names at most 3 tickers; 0: a market roundup."""
    return 2 if (p.get('ticker_notes') or {}).get(t) else (1 if len(p.get('tickers') or []) <= 3 else 0)


CJK = re.compile('[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff]')


def reason(row, t, lang, cut=None):
    """One account's reason for its stance on t, from its post (ticker note, else the summary), or ''."""
    p = row.get('p') or {}
    if not on_topic(p, t):
        return ''  # a roundup's summary is not a reason for this stock
    note, few = (p.get('ticker_notes') or {}).get(t) or '', len(p.get('tickers') or []) <= 3
    if lang == 'zh':
        z = p.get('zh_summary') or ''
        txt = note if CJK.search(note) or not (few and CJK.search(z)) else z
        txt = txt or z
    else:
        txt = p.get('en_summary') or p.get('text') or ''
        if not few:  # a roundup: keep only the sentence about this stock
            hit = [x for x in re.split(r'(?<=[.;!?])\s+|\s+\|\s+', txt) if re.search(r'\$?\b' + re.escape(t) + r'\b', x)]
            txt = hit[0] if hit else ''
    txt = re.sub(r'^\((?:Reposted|轉發)\)\s*', '', txt)
    h = re.sub(r'[^A-Za-z0-9_]', '', row.get('acc') or '')
    sep = r'\s*(?:[:：]|表示|指出|認為|稱)'
    txt = re.sub(r'^\s*(?:@' + h + f'(?:{sep})?|' + h + sep + r')\s*', '', txt, flags=re.I) if h else txt
    txt = txt[:1].upper() + txt[1:] if lang == 'en' else txt
    txt = re.sub(r'https?://\S+', '', txt)
    txt = ' '.join(txt.split())
    if lang == 'en' and CJK.search(txt):
        return ''
    cut = cut or (60 if lang == 'zh' else 110)
    return txt if len(txt) <= cut else txt[:cut - 1].rstrip() + '…'


def view_lines(v, t, lang):
    """Caption lines: the latest bullish and the latest bearish account, each with its reason."""
    w, out = T[lang], []
    for s in ('bull', 'bear'):
        for a in v['accs']:
            if a['s'] == s:
                why = reason(a, t, lang)
                if why:
                    out.append(w['why'](s, a['acc'], why))
                    break
    return out


def facts(co):
    """The numbers every picture and caption uses, from the brief data only."""
    q = co['q'][-1]
    ya, pq = year_ago(co, q['end']), prev_q(co, q['end'])
    est = co.get('est') or {}
    seg = co.get('seg') or {}
    rows = [r for r in seg.get('rows') or [] if not r.get('other')] if not seg.get('none') else []
    tot = sum(r['val'] for r in seg.get('rows') or []) or None
    bal = co.get('bal') or {}
    liquid = None if bal.get('cash') is None else bal['cash'] + (bal.get('sti') or 0)
    return {
        'q': q, 'ya': ya, 'pq': pq, 'est': est,
        'rev_yoy': pct(q['rev'], (ya or {}).get('rev')), 'rev_qoq': pct(q['rev'], (pq or {}).get('rev')),
        'ni_yoy': pct(q.get('ni'), (ya or {}).get('ni')),
        'rev_vs': pct(q['rev'], est.get('rev_est')), 'eps_vs': pct(est.get('eps_act'), est.get('eps_est')),
        'gm': margin(q.get('gp'), q['rev']), 'om': margin(q.get('op'), q['rev']), 'nm': margin(q.get('ni'), q['rev']),
        'gm_y': margin((ya or {}).get('gp'), (ya or {}).get('rev')), 'om_y': margin((ya or {}).get('op'), (ya or {}).get('rev')),
        'nm_y': margin((ya or {}).get('ni'), (ya or {}).get('rev')),
        'seg': [dict(r, share=r['val'] / tot * 100 if tot else None, yoy=pct(r['val'], r.get('prev'))) for r in rows[:5]],
        'seg_year': seg.get('basis') == 'year', 'liquid': liquid, 'debt': bal.get('debt'), 'fcf_q': q.get('fcf'),
        'fcf_4': ttm_fcf(co), 'bank': co.get('bank'),
    }


def tag(d, lang):
    c = CARD[lang]
    if d is None:
        return None
    return 'flat' if abs(d) < 0.5 else ('up' if d > 0 else 'down')


def slides(co, lang):
    f, c, t = facts(co), CARD[lang], co['t']
    q = f['q']
    p = lambda v: None if v is None else f'{v:.1f}%'  # noqa: E731
    s1 = {'kind': 'cover', 'kick': c['kick'], 'ticker': t, 'name': co['name'], 'label': q['label'],
          'rows': [{'k': c['rev'], 'v': money(q['rev'], lang), 'e': (f"{c['est']} {money(f['est'].get('rev_est'), lang)}" if f['est'].get('rev_est') else None),
                    'd': spct(f['rev_vs']) if f['rev_vs'] is not None else None, 'tag': tag(f['rev_vs'], lang)},
                   {'k': c['eps'], 'v': eps_s(f['est'].get('eps_act')) if f['est'].get('eps_act') is not None else eps_s(q.get('eps')),
                    'e': (f"{c['est']} {eps_s(f['est'].get('eps_est'))}" if f['est'].get('eps_est') is not None else None),
                    'd': spct(f['eps_vs']) if f['eps_vs'] is not None else None, 'tag': tag(f['eps_vs'], lang)}],
          'tags': {'up': c['beat'], 'down': c['miss'], 'flat': c['inline']}}
    last8 = co['q'][-8:]
    top = max(x['rev'] for x in last8) or 1
    bars = []
    for x in last8:
        y = year_ago(co, x['end'])
        g = pct(x['rev'], (y or {}).get('rev'))
        bars.append({'h': max(3, round(x['rev'] / top * 100)), 'g': spct(g, 0) if g is not None else '',
                     'up': (g or 0) >= 0, 'l': x['label'].split(' ')[1] + "'" + x['label'][4:6]})
    s2 = {'kind': 'growth', 'title': c['growth'], 'stats': [
        {'k': f"{c['rev']} {c['yoy']}", 'v': spct(f['rev_yoy']), 'up': (f['rev_yoy'] or 0) >= 0},
        {'k': f"{c['rev']} {c['qoq']}", 'v': spct(f['rev_qoq']), 'up': (f['rev_qoq'] or 0) >= 0}],
        'margins': [{'k': c[k], 'v': p(f[k]), 'y': (f'{f[k] - f[k + "_y"]:+.1f}pp' if f[k] is not None and f[k + '_y'] is not None else '')}
                    for k in ('gm', 'om', 'nm') if f[k] is not None],
        'bars': bars, 'bars_title': c['rev8']}
    if f['seg']:
        s3 = {'kind': 'segs', 'title': c['lines'] + (f"（{c['year']}）" if lang == 'zh' and f['seg_year'] else (f" ({c['year']})" if f['seg_year'] else '')),
              'rows': [{'k': r['name'], 'v': money(r['val'], lang), 's': r['share'], 'y': spct(r['yoy']) if r['yoy'] is not None else '',
                        'up': (r['yoy'] or 0) >= 0} for r in f['seg']]}
    else:
        s3 = {'kind': 'segs', 'title': c['lines'], 'empty': c['noseg'], 'rows': []}
    rows = [{'k': c['liquid'], 'v': money(f['liquid'], lang)}, {'k': c['debt'], 'v': money(f['debt'], lang)}]
    if f['liquid'] is not None and f['debt'] is not None:
        net = f['liquid'] - f['debt']
        rows.append({'k': c['net_cash'] if net >= 0 else c['net_debt'], 'v': money(abs(net), lang), 'up': net >= 0})
    rows += [{'k': c['fcf_q'], 'v': money(f['fcf_q'], lang), 'up': (f['fcf_q'] or 0) >= 0},
             {'k': c['fcf_4'], 'v': money(f['fcf_4'], lang), 'up': (f['fcf_4'] or 0) >= 0}]
    if f['bank']:
        verdict = c['bank']
    elif f['fcf_4'] is None or f['liquid'] is None:
        verdict = ''
    elif f['fcf_4'] >= 0:
        verdict = c['ok']
    else:
        verdict = c['bad'](max(0, round(f['liquid'] / (-f['fcf_4'] / 12))))
    s4 = {'kind': 'cash', 'title': c['cash'], 'rows': rows, 'verdict': verdict, 'more': c['more'].replace('thecrowdtape.com', f'thecrowdtape.com/{lang}/earnings/{t}/')}
    out = [s1, s2, s3, s4]
    v, su = views(t), stock_url(lang, t)
    if v and su:
        out.append({'kind': 'views', 'title': c['views'], 'sub': c['views_sub'], 'ticker': t, 'nb': v['nb'], 'nr': v['nr'], 'neu': v['neu'],
                    'labels': {'bull': c['bull'], 'bear': c['bear'], 'neu': c['neu']},
                    'accs': [{'acc': a['acc'], 's': a['s'], 'why': reason(a, t, lang, 70 if lang == 'zh' else 120)} for a in v['accs'][:4]],
                    'extra': c['others'](len(v['accs']) - 4) if len(v['accs']) > 4 else '',
                    'more': c['views_more'] + su.replace('https://', '')})
    for x in out:
        x['of'] = len(out)
    return out


def caption_lines(co, lang):
    f, w, t = facts(co), T[lang], co['t']
    q = f['q']
    r1 = w['rev'](money(q['rev'], lang), spct(f['rev_yoy']))
    if f['rev_vs'] is not None:
        r1 += w['inline'] if abs(f['rev_vs']) < 0.5 else w['vs_rev'](f['rev_vs'], w['better'] if f['rev_vs'] > 0 else w['worse'])
    lines = [r1]
    if f['est'].get('eps_act') is not None:
        ok = '' if f['eps_vs'] is None else ('✅' if f['eps_vs'] >= 0.5 else ('❌' if f['eps_vs'] <= -0.5 else '➖'))
        lines.append(w['eps'](eps_s(f['est']['eps_act']), eps_s(f['est'].get('eps_est')) if f['est'].get('eps_est') is not None else None, ok))
    m = w['margins'](f'{f["gm"]:.1f}%' if f['gm'] is not None else None, f'{f["nm"]:.1f}%' if f['nm'] is not None else None)
    if m:
        lines.append(m)
    if f['seg']:
        s = f['seg'][0]
        lines.append(w['seg'](s['name'], f'{s["share"]:.0f}%', spct(s['yoy']) if s['yoy'] is not None else None))
    if f['fcf_4'] is not None and not f['bank']:
        lines.append(w['fcf'](money(f['fcf_4'], lang)))
    return w['head'](t, q['label']), lines


def captions(co, lang):
    w, t = T[lang], co['t']
    head, lines = caption_lines(co, lang)
    url = brief_url(lang, t)
    give = f"{w['give']}{SITE}{lang}/#donate"
    tg = f"{w['tags']} #{t}" if re.fullmatch(r'[A-Z]{1,6}', t) else w['tags']
    body = '\n'.join(f'・{x}' for x in lines)
    v, su = views(t), stock_url(lang, t)
    n = 5 if v and su else 4
    say = (w['views'](v['nb'], v['nr']) if v else w['views_none']) + su if su else None
    why = '\n'.join(view_lines(v, t, lang)) if v and su else ''
    say_long = f'{say}\n{why}' if why else say
    fb = '\n\n'.join([head, w['swipe'](n), body] + ([say_long] if say else []) + [f"{w['link']}{url}\n{give}", w['disc'], tg])
    ig = sanitize_instagram('\n\n'.join([f'{head}｜{lines[0]}' if lang == 'zh' else f'{head}: {lines[0]}', w['swipe'](n), body] + ([say_long.replace(' 👉 ' + su, '')] if v and su else []) + [w['bio'], w['disc'],
                                         ig_tags(lang, [t])]), lang)
    threads = '\n\n'.join([head, body] + ([say_long] if say else []) + [f"{w['link']}{url}\n{give}", w['disc'], f"{w['tags'].split(' ')[0]} #{t}"])
    if len(threads) > 490 and why:
        threads = '\n\n'.join([head, body, say, f"{w['link']}{url}\n{give}", w['disc'], f"{w['tags'].split(' ')[0]} #{t}"])
    keep = list(lines)
    while len(threads) > 490 and len(keep) > 1:
        keep.pop()
        threads = '\n\n'.join([head, '\n'.join(f'・{x}' for x in keep)] + ([say] if say else []) + [f"{w['link']}{url}", w['disc'], f"{w['tags'].split(' ')[0]} #{t}"])
    keep = list(lines)
    while True:
        x = '\n\n'.join([head, '\n'.join(f'・{y}' for y in keep)] + ([say] if say else []) + [f"{w['link']}{url}", w['disc'].split('，')[0].split(',')[0] if lang == 'zh' else '⚠️ Not investment advice',
                         f"#{'財報' if lang == 'zh' else 'Earnings'} #{t}"])
        if xlen(x) <= 270 or len(keep) <= 1:
            break
        keep.pop()
    return {'x': x, 'threads': threads, 'instagram': ig, 'facebook': fb}


def load_co(t):
    return read_json(f'{CO_DIR}/{t}.json')


def slot_now(now):
    m = now.hour * 60 + now.minute
    for k, ((h0, m0), (h1, m1), _) in SLOTS.items():
        if h0 * 60 + m0 <= m <= h1 * 60 + m1:
            return k
    return None


def social_html(ep):
    names = {'zh': '中文', 'en': 'English'}
    box = lambda title, text, n: (f'<h4>{title}</h4><textarea readonly rows="{n}">{html.escape(text)}</textarea>'  # noqa: E731
                                  '<button onclick="navigator.clipboard.writeText(this.previousElementSibling.value);this.textContent=\'已複製 ✓\'">複製</button>')
    out = []
    for key, (_, _, at) in SLOTS.items():
        sl = (ep.get('slots') or {}).get(key)
        if not sl or not sl.get('items'):
            out.append(f'<section><h2>{at} 財報貼文</h2><p>今個時段冇新財報（或者已經用晒每日 {DAILY_CAP} 篇上限）。</p></section>')
            continue
        items = []
        for it in sl['items']:
            langs = []
            for lang in LANGS:
                imgs = ''.join(f'<a href="{html.escape(u)}" download><img src="{html.escape(u)}" alt="{n + 1}"></a>' for n, u in enumerate(it['images'][lang]))
                fbs = ''.join(f'<a href="{html.escape(u)}" download><img src="{html.escape(u)}" alt="FB {n + 1}"></a>' for n, u in enumerate(it['images_fb'][lang]))
                p = it['posts'][lang]
                langs.append(f'<details{" open" if lang == "zh" else ""}><summary>{names[lang]}</summary><div class="grid">{imgs}</div>'
                             f"{box('X', p['x'], 7)}{box('Threads', p['threads'], 10)}{box('Instagram', p['instagram'], 14)}"
                             f'<h4>Facebook 用正方形圖</h4><div class="grid">{fbs}</div>{box("Facebook", p["facebook"], 14)}</details>')
            items.append(f'<article><h3>${it["t"]} {html.escape(it["name"])}・{it["label"]}</h3>{"".join(langs)}</article>')
        out.append(f'<section><h2>{at} 財報貼文（{sl["day"]}，{len(sl["items"])} 間）</h2><p>製作時間 {sl["made_hkt"]} HKT</p>{"".join(items)}</section>')
    v = ep.get('video') or {}
    if v.get('video'):
        vids = ''.join(f'<h4>{names[l]}</h4><video controls playsinline preload="none" src="{html.escape(u)}"></video><p><a href="{html.escape(u)}" download>下載短片</a></p>'
                       for l, u in v['video'].items())
        out.append(f'<section><h2>{VIDEO_AT} 財報短片（{v["day"]}，${v["t"]}）</h2>{vids}</section>')
    css = ('<style>body{font-family:system-ui,sans-serif;max-width:900px;margin:0 auto;padding:16px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:8px}'
           '.grid img{width:100%;border-radius:6px}textarea{width:100%;font:13px/1.4 monospace}video{width:240px;max-width:100%}details{margin-top:10px}'
           'summary{font-weight:700;cursor:pointer}h4{margin:12px 0 4px;font-size:14px}article{border-top:1px solid #ddd;margin-top:14px;padding-top:6px}</style>')
    return (f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="robots" content="noindex"><title>財報貼文</title>{css}</head><body><h1>財報貼文（Grok bot／Reels bot 用）</h1>'
            f'<p>數據：<a href="/data/earnings-posts.json">data/earnings-posts.json</a>。圖、片同文字全部由 GitHub 整好，照原文發，唔使改。</p>{"".join(out)}</body></html>')


def main():
    now = now_hk()
    today = now.strftime('%Y-%m-%d')
    stamp = now.strftime('%Y-%m-%d %H:%M')
    state = read_json(STATE, {}) or {}
    ep = read_json(DATA, {}) or {}
    queue, done = ep.setdefault('queue', []), ep.setdefault('done', [])
    have = {(x['t'], x['end']) for x in queue} | {(x['t'], x['end']) for x in done}
    for e in state.get('new') or []:
        if e.get('first_run') or (e['t'], e['end']) in have:
            continue
        queue.append({'t': e['t'], 'end': e['end'], 'label': e['label'], 'found_hkt': e['found_hkt']})
        have.add((e['t'], e['end']))
    cutoff = now - timedelta(hours=WAIT_HOURS)
    fresh = []
    for x in queue:
        if datetime.fromisoformat(x['found_hkt']).replace(tzinfo=now.tzinfo) < cutoff:
            done.append(dict(x, dropped=True))
        else:
            fresh.append(x)
    queue[:] = fresh
    ep['done'] = [x for x in done if (now - datetime.fromisoformat(x['found_hkt']).replace(tzinfo=now.tzinfo)).days <= 60]
    key = slot_now(now) if os.environ.get('EARNINGS_SLOT') is None else os.environ['EARNINGS_SLOT']
    slots = ep.setdefault('slots', {})
    jobs, made = [], False
    if key and (slots.get(key) or {}).get('day') != today:
        used = sum(len(v.get('items') or []) for v in slots.values() if v.get('day') == today)
        room = max(0, DAILY_CAP - used)
        cands = []
        for x in queue:
            co = load_co(x['t'])
            if co and co['q'] and co['q'][-1]['end'] == x['end']:
                cands.append((co.get('mcap') or 0, x, co))
        cands.sort(key=lambda c: -c[0])
        items = []
        for _, x, co in cands[:room]:
            it = {'t': co['t'], 'name': co['name'], 'label': x['label'], 'end': x['end'], 'mcap': co.get('mcap'),
                  'images': {}, 'images_fb': {}, 'posts': {}, 'url': {l: brief_url(l, co['t']) for l in LANGS}}
            for lang in LANGS:
                ss = slides(co, lang)
                files = [f'og/e/{today}-{key}-{co["t"]}-{lang}-{n + 1}.jpg' for n in range(len(ss))]
                fb = [f'og/e/{today}-{key}-{co["t"]}-{lang}-{n + 1}-fb.jpg' for n in range(len(ss))]
                jobs.append({'lang': lang, 'date': today, 'ticker': co['t'], 'slides': ss, 'files': files, 'fb': fb})
                it['images'][lang] = [SITE + f for f in files]
                it['images_fb'][lang] = [SITE + f for f in fb]
                it['posts'][lang] = captions(co, lang)
            items.append(it)
        picked = {(i['t'], i['end']) for i in items}
        queue[:] = [x for x in queue if (x['t'], x['end']) not in picked]
        ep['done'] += [dict(x, posted=today, slot=key) for _, x, _ in cands if (x['t'], x['end']) in picked]
        slots[key] = {'day': today, 'post_at': SLOTS[key][2], 'made_hkt': stamp, 'platforms': ['x', 'threads', 'instagram', 'facebook'], 'items': items}
        try:
            from utm import tag_posts
            for it in items:
                tag_posts(it['posts'], 'earnings')
        except Exception as e:  # tags are a nice-to-have
            print('utm', e)
        made = True
        notice(f'財報貼文：{key} 時段 {len(items)} 間（{", ".join(i["t"] for i in items) or "冇"}），隊列尚餘 {len(queue)}')
    # The day's video: on the morning slot, the largest company posted since yesterday's 22:00 slot
    vid = None
    if key == '1000' and (ep.get('video') or {}).get('day') != today:
        y = (now - timedelta(days=1)).strftime('%Y-%m-%d')
        pool = [i for k, v in slots.items() for i in v.get('items') or []
                if (k == '1000' and v.get('day') == today) or (k == '2200' and v.get('day') == y)]
        if pool:
            top = max(pool, key=lambda i: i.get('mcap') or 0)
            co = load_co(top['t'])
            if co:
                vid = {'date': today, 'ticker': co['t'], 'lines': {l: video_lines(co, l) for l in LANGS},
                       'images': {l: [f'og/e/{today}-video-{co["t"]}-{l}-{n + 1}.jpg' for n in range(4)] for l in LANGS},
                       'slides': {l: [dict(x, of=4) for x in slides(co, l)[:4]] for l in LANGS}, 'out': {l: f'og/e/{today}-video-{l}.mp4' for l in LANGS},
                       'cover': {l: f'og/e/{today}-video-{l}-cover.jpg' for l in LANGS}}
                for l in LANGS:
                    jobs.append({'lang': l, 'date': today, 'ticker': co['t'], 'slides': vid['slides'][l], 'files': vid['images'][l], 'fb': None})
                ep['video'] = {'day': today, 't': co['t'], 'post_at': VIDEO_AT, 'video': {l: SITE + vid['out'][l] for l in LANGS},
                               'video_cover': {l: SITE + vid['cover'][l] for l in LANGS},
                               'posts': {l: {'instagram': top['posts'][l]['instagram'], 'facebook': top['posts'][l]['facebook']} for l in LANGS}}
                made = True
    if not made:
        print('earnings posts: nothing new for a slot')
        write_json(DATA, ep, indent=1)  # queue changes only
        return
    write_json(work('earnings_cards.json'), {'date': today, 'jobs': jobs})
    if vid:
        write_json(work('earnings_video.json'), vid)
    write_json(work('earnings-posts.json'), ep, indent=1)
    open(work('earnings.html'), 'w', encoding='utf-8').write(social_html(ep))


def video_lines(co, lang):
    """Voiceover, one line per picture plus an outro. Tickers spelt out; numbers from the brief only."""
    f, t = facts(co), co['t']
    spelt = ' '.join(t) if lang == 'en' else '、'.join(t)
    q = f['q']
    if lang == 'zh':  # read by a Mandarin voice, so Mandarin wording (as the daily shorts)
        r = money(q['rev'], 'zh').replace('US$', '').replace(' ', '')
        l1 = f'{spelt} 公布財報，收入{r}美元' + (f'，同比{"增長" if f["rev_yoy"] >= 0 else "下跌"}{abs(f["rev_yoy"]):.0f}%' if f['rev_yoy'] is not None else '') + '。'
        if f['rev_vs'] is not None and abs(f['rev_vs']) >= 0.5:
            l1 += f'{"好於" if f["rev_vs"] > 0 else "低於"}市場預期。'
        l2 = (f'毛利率{f["gm"]:.0f}%，' if f['gm'] is not None else '') + (f'淨利率{f["nm"]:.0f}%。' if f['nm'] is not None else '')
        l3 = (f'最大收入來源是{f["seg"][0]["name"]}，佔{f["seg"][0]["share"]:.0f}%。' if f['seg'] else '再看看收入和利潤的走勢。')
        if f['bank']:
            l4 = '銀行的現金流，就不計算能撐多久了。'
        elif f['fcf_4'] is not None:
            l4 = f'過去四個季度，自由現金流{"為正" if f["fcf_4"] >= 0 else "為負"}。'
        else:
            l4 = '現金流的數據，請看網站。'
        l5 = '完整五章財報簡報，請上 thecrowdtape.com，記得關注我們！'
        if not l2:
            l2 = '再看看利潤率。'
        return [l1, l2, l3, l4, l5]
    r = money(q['rev'], 'en').replace('$', '')
    unit = {'T': ' trillion', 'B': ' billion', 'M': ' million'}.get(r[-1:], '')
    r = r[:-1] if unit else r
    l1 = f'{spelt} reported revenue of {r}{unit} dollars' + (f', {"up" if f["rev_yoy"] >= 0 else "down"} {abs(f["rev_yoy"]):.0f} percent' if f['rev_yoy'] is not None else '') + '.'
    if f['rev_vs'] is not None and abs(f['rev_vs']) >= 0.5:
        l1 += f' That {"beat" if f["rev_vs"] > 0 else "missed"} estimates.'
    parts = []
    if f['gm'] is not None:
        parts.append(f'gross margin {f["gm"]:.0f} percent')
    if f['nm'] is not None:
        parts.append(f'net margin {f["nm"]:.0f} percent')
    l2 = (', '.join(parts).capitalize() + '.') if parts else 'Here are the margins.'
    l3 = f'The biggest line is {f["seg"][0]["name"]}, at {f["seg"][0]["share"]:.0f} percent.' if f['seg'] else 'Here is the revenue trend.'
    if f['bank']:
        l4 = 'For a bank, cash runway does not apply.'
    elif f['fcf_4'] is not None:
        l4 = f'Free cash flow over four quarters is {"positive" if f["fcf_4"] >= 0 else "negative"}.'
    else:
        l4 = 'Cash flow details are on the site.'
    return [l1, l2, l3, l4, 'Full five-chapter brief at thecrowdtape.com. Follow us!']


if __name__ == '__main__':
    main()
