"""Homepage pay moments, and the weekly inclusion list.

The public weekly page shows the last settled 10-session scorecard.
Names newly added this week are not written into that page. The Monday
email appends them for subscribers only.

python3 tools/pay_moments.py   injects the homepage bridge (also called
from tools/board_page.py after the pages are slimmed).
"""
import json
import os
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKER = '/* ct-pay-bridge */'
TAG = '<script src="/embed/pay-moments.js" defer></script>'
PAGES = ('index.html', 'zh/index.html', 'en/index.html')
BRIDGE = r"""
/* ct-pay-bridge */
function ctGroups(from,to,allow){
  const ok=h=>{if(!inCons(h))return false;if(!allow)return true;const c=CAT[String(h).toLowerCase()];return !c||allow[c]===true};
  const out={bull:[],bear:[],split:[]};
  TICKERS.forEach(t=>{if(UNC(t)||!isUS(t))return;const rows=accsOf(from,to).filter(ok).map(a=>latest(a,t,from,to)).filter(Boolean);if(!rows.length)return;const nb=rows.filter(x=>x.s==='bull').length,nr=rows.filter(x=>x.s==='bear').length;const k=nb&&nr?'split':nb>=2?'bull':nr>=2?'bear':null;if(!k)return;const nPosts=new Set(postsIn(from,to).filter(x=>x.t===t).map(x=>x.url)).size;out[k].push({t,nb,nr,nPosts})});
  ['bull','bear','split'].forEach(k=>out[k].sort((a,b)=>(b.nb+b.nr)-(a.nb+a.nr)||b.nPosts-a.nPosts||a.t.localeCompare(b.t)));
  return out;
}
window.__ct={win:function(){return dailyWindow()},groups:ctGroups,cats:function(){return ((D.tracked&&D.tracked.categories)||[]).map(function(c){return c.name}).filter(Boolean)}};
(function(){if(typeof render!=='function'||render.__ct)return;var prev=render;var wrapped=function(){var out=prev.apply(this,arguments);if(window.__ctAfter)try{window.__ctAfter()}catch(e){console.error(e)}return out};wrapped.__ct=1;render=wrapped})();
"""


def monday(iso):
    y, m, d = (int(x) for x in str(iso)[:10].split('-'))
    dt = date(y, m, d)
    return dt - timedelta(days=dt.weekday())


def plus_days(dt, n):
    return dt + timedelta(days=n)


def zh_span(d0, d1):
    if d0.month == d1.month:
        return f'{d0.month}月{d0.day}日至{d1.day}日'
    return f'{d0.month}月{d0.day}日至{d1.month}月{d1.day}日'


def prior_settled(ft, ticker, side, before):
    """Latest settled episode of this ticker and side before this inclusion."""
    best = None
    before = str(before)[:10]
    for row in (ft or {}).get('rows') or []:
        if row.get('ticker') != ticker or row.get('side') != side:
            continue
        if not isinstance(row.get('xs'), (int, float)):
            continue
        signal = str(row.get('signal') or '')[:10]
        if len(signal) != 10 or signal >= before:
            continue
        if best is None or signal > str(best.get('signal') or '')[:10]:
            best = row
    return best


def signed_pct(value):
    return f'{"+" if value > 0 else ""}{value * 100:.1f}%'


def beat_both(xs, xs_spy):
    return isinstance(xs, (int, float)) and isinstance(xs_spy, (int, float)) and xs > 0 and xs_spy > 0


def index_clause(xs, xs_spy):
    """Excess versus QQQ and SPY. 跑贏 only when both are ahead. Missing SPY stays 未核."""
    if isinstance(xs_spy, (int, float)):
        spy = f'，相對 SPY {signed_pct(xs_spy)}'
        if beat_both(xs, xs_spy):
            word = '，跑贏'
        elif xs < 0 or xs_spy < 0:
            word = '，跑輸'
        else:
            word = '，持平'
    else:
        spy, word = '，相對 SPY 未核', ''
    return f'相對 QQQ {signed_pct(xs)}{spy}{word}'


def load_followthrough():
    path = os.path.join(ROOT, 'data', 'followthrough.json')
    if not os.path.isfile(path):
        return {}
    return json.load(open(path, encoding='utf-8'))


BEAT_FROM = date(2026, 11, 23)  # first Monday letter that names beats, not lags


def lagged_rows(rows, ft, limit=8):
    """Old rule, used only to settle letters sent before BEAT_FROM."""
    lagged = []
    for row in rows:
        prev = prior_settled(ft, row['t'], row['side'], row['d'])
        if not prev or not isinstance(prev.get('xs'), (int, float)) or prev['xs'] >= 0:
            continue
        lagged.append((prev['xs'], str(row.get('t') or ''), row))
    lagged.sort()
    return [row for _, _, row in lagged[:limit]]


def email_rows(rows, ft, limit=8):
    """At most eight new inclusions. Bullish only, and the last long call beat both QQQ and SPY."""
    ranked = []
    for row in rows:
        if row.get('side') != 'bull':
            continue
        prev = prior_settled(ft, row['t'], row['side'], row['d'])
        spy = None if not prev else prev.get('xs_spy')
        if not prev or not isinstance(prev.get('xs'), (int, float)) or not isinstance(spy, (int, float)):
            continue
        if not beat_both(prev['xs'], spy):
            continue
        ranked.append((-min(prev['xs'], spy), str(row.get('t') or ''), row))
    ranked.sort()
    return [row for _, _, row in ranked[:limit]]


def email_block(rows, ft):
    """Subscriber email only. At most eight bullish names that beat both QQQ and SPY."""
    chosen = email_rows(rows, ft)
    lines = [
        '',
        '週報・潛力觀察',
        '這一封是週報，名單最多八隻，以做多為主。只寫上週新列入共同看好、上次同類已結算又同時跑贏 QQQ 同 SPY 的。先看升勢還在不在，再對照自己的倉。不是買入名單。同一方向連續留在名單上只計第一次。不是投資建議。',
    ]
    if not chosen:
        lines.append('上週新列入裡，沒有上次做多已結算而且同時跑贏 QQQ 同 SPY 的名稱。今次不列名單。')
        return '\n'.join(lines)
    for row in chosen:
        side = '共同看好' if row['side'] == 'bull' else '共同看淡'
        lines.append(f"{row['d'][5:]} ${row['t']} {side}")
        prev = prior_settled(ft, row['t'], row['side'], row['d'])
        lines.append(f"上次同類已結算：10 日{index_clause(prev['xs'], prev.get('xs_spy'))}")
        lines.append('今次是新列入。不是投資建議。')
        lines.append('')
    return '\n'.join(lines).rstrip()


def load_mentions():
    """Counts from the Chinese post archive. Empty when that archive is absent."""
    mentions = {}
    posts_by_day = {}
    seen = set()
    folder = os.path.join(ROOT, 'data', 'dash')
    if not os.path.isdir(folder):
        return mentions, posts_by_day
    for name in sorted(os.listdir(folder)):
        if not (name.startswith('zh-posts-') and name.endswith('.json')):
            continue
        try:
            posts = json.load(open(os.path.join(folder, name), encoding='utf-8'))
        except (OSError, ValueError):
            continue
        for post in posts or []:
            url = post.get('url')
            if url:
                if url in seen:
                    continue
                seen.add(url)
            day = str(post.get('day') or '')[:10]
            if len(day) != 10:
                continue
            posts_by_day[day] = posts_by_day.get(day, 0) + 1
            tickers = set()
            for raw in post.get('tickers') or []:
                tickers.add(str(raw).lstrip('$').upper())
            stance = post.get('stance_by_ticker') or {}
            if isinstance(stance, dict):
                for raw in stance:
                    tickers.add(str(raw).lstrip('$').upper())
            for ticker in tickers:
                if ticker:
                    mentions[(day, ticker)] = mentions.get((day, ticker), 0) + 1
    return mentions, posts_by_day


def _mention_span(mentions, posts_by_day, ticker, end):
    year, month, day = (int(part) for part in str(end)[:10].split('-'))
    cursor = date(year, month, day)
    hits = posts = 0
    for _ in range(7):
        key = cursor.isoformat()
        posts += posts_by_day.get(key, 0)
        hits += mentions.get((key, ticker), 0)
        cursor -= timedelta(days=1)
    return hits, posts


def focus_rows(rows, mentions, posts_by_day, limit=None):
    """New inclusions whose share of posts at least doubled.

    The 7 days ending on the inclusion need at least 8 mentions and 2% of
    posts in that window. The prior 7 days must already have mentions, so a
    thin archive week cannot look like a surge.
    """
    ranked = []
    for row in rows:
        now, posts = _mention_span(mentions, posts_by_day, row['t'], row['d'])
        prev_end = plus_days(date.fromisoformat(str(row['d'])[:10]), -7).isoformat()
        prev, prev_posts = _mention_span(mentions, posts_by_day, row['t'], prev_end)
        if now < 8 or posts < 1 or prev < 1 or prev_posts < 1:
            continue
        share = now / posts
        prev_share = prev / prev_posts
        if share < 0.02 or share < 2 * prev_share:
            continue
        ranked.append((share / prev_share, now, {
            'd': row['d'], 't': row['t'], 'side': row['side'],
            'mentions': now, 'share': share, 'prev_share': prev_share,
        }))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]['t']))
    chosen = [item[2] for item in ranked]
    return chosen[:limit] if limit is not None else chosen


def focus_block(rows, mentions, posts_by_day, ft, limit=8):
    """Subscriber email only. Names whose discussion share jumped. Not a forecast."""
    chosen = focus_rows(rows, mentions, posts_by_day, limit)
    lines = [
        '',
        '本週討論突然集中',
        '只寫今次新列入、這 7 日提及佔全站比例至少是之前 7 日兩倍、這 7 日至少 8 則、而且佔全站至少 2% 的名稱。最多八隻。這不是即將爆發。不是投資建議。',
    ]
    if not chosen:
        lines.append('上週新列入裡，沒有符合這條的名稱。今次不列。')
        return '\n'.join(lines)
    for row in chosen:
        side = '共同看好' if row['side'] == 'bull' else '共同看淡'
        lines.append(f"{row['d'][5:]} ${row['t']} {side}")
        lines.append(
            f"這 7 日 {row['mentions']} 則，佔全站 {row['share'] * 100:.1f}%；之前 7 日佔 {row['prev_share'] * 100:.1f}%。"
        )
        prev = prior_settled(ft, row['t'], row['side'], row['d'])
        if prev and isinstance(prev.get('xs'), (int, float)):
            lines.append(f"上次同類已結算：10 日{index_clause(prev['xs'], prev.get('xs_spy'))}")
        else:
            lines.append('上次同類未有已結算紀錄。')
        lines.append('不是投資建議。')
        lines.append('')
    return '\n'.join(lines).rstrip()


def receipt_block(cons_hist, ft, mail_start):
    """Email only. Settles the names the letter three weeks earlier would have named.

    Uses the same eight-name rule as that letter. A name is listed only after its
    own 10-session result is in the settled file. Nothing here is written to the site.
    """
    start = mail_start if isinstance(mail_start, date) else date.fromisoformat(str(mail_start)[:10])
    start = plus_days(start, -21)
    end = plus_days(start, 6)
    chosen = (email_rows if start >= BEAT_FROM else lagged_rows)(
        week_rows(episodes(cons_hist), start, end), ft)
    lines = [
        '',
        '三週前回條',
        f'{zh_span(start, end)} 那封點過名的，有 10 日結果才在這裡結算。名稱不在網站。不是投資建議。',
    ]
    if not chosen:
        lines.append('那一週沒有符合點名規則的名稱。今次沒有回條。')
        return '\n'.join(lines)
    index = {}
    for row in (ft or {}).get('rows') or []:
        signal = str(row.get('signal') or '')[:10]
        index[(row.get('ticker'), row.get('side'), signal)] = row
    settled = []
    pending = 0
    for row in chosen:
        hit = index.get((row['t'], row['side'], row['d']))
        if not hit or not isinstance(hit.get('xs'), (int, float)) or not isinstance(hit.get('ret'), (int, float)):
            pending += 1
            continue
        settled.append((row, hit))
    if not settled:
        lines.append(f'那封點名 {len(chosen)} 隻，尚未有 10 日結算。今次不列結果。')
        return '\n'.join(lines)
    wins = 0
    for row, hit in settled:
        side = '共同看好' if row['side'] == 'bull' else '共同看淡'
        if beat_both(hit['xs'], hit.get('xs_spy')):
            wins += 1
        lines.append(f"{row['d'][5:]} ${row['t']} {side}")
        lines.append(f"10 日股價 {signed_pct(hit['ret'])}，{index_clause(hit['xs'], hit.get('xs_spy'))}")
        lines.append('')
    lines.append(f'已結算 {len(settled)} 隻，其中 {wins} 隻同時跑贏 QQQ 同 SPY。')
    if pending:
        lines.append(f'其餘 {pending} 隻未到 10 日，不先報。')
    return '\n'.join(lines).rstrip()


def parse_holdings(text, limit=8):
    """Up to eight tickers. Order kept, duplicates dropped."""
    raw = str(text or '').upper()
    tickers = []
    seen = set()
    cur = []

    def flush():
        ticker = ''.join(cur)
        cur.clear()
        if not ticker or ticker in seen or len(tickers) >= limit:
            return
        if len(ticker) > 10 or not ticker[0].isalpha():
            return
        if any(not (ch.isalnum() or ch == '.') for ch in ticker):
            return
        seen.add(ticker)
        tickers.append(ticker)

    for ch in raw:
        if ch.isalnum() or ch == '.':
            cur.append(ch)
        else:
            flush()
    flush()
    return tickers


def book_block(tickers, rows, ft):
    """First lines of one subscriber's Monday letter. Not written on the site."""
    chosen = parse_holdings(tickers if isinstance(tickers, str) else ','.join(tickers or []))
    lines = ['', '你的持倉']
    if not chosen:
        lines.append('你未填持倉，今次沒有個人那一封。週報仍會寄出。')
        return '\n'.join(lines)
    by = {}
    for row in rows or []:
        by.setdefault(row['t'], row)
    hits = [by[ticker] for ticker in chosen if ticker in by]
    if not hits:
        lines.append('你呢八隻今次沒有新列入。')
        lines.append('不是投資建議。')
        return '\n'.join(lines)
    for row in hits:
        side = '共同看好' if row['side'] == 'bull' else '共同看淡'
        lines.append(f"${row['t']} 今次新列入{side}。")
        prev = prior_settled(ft, row['t'], row['side'], row['d'])
        if prev and isinstance(prev.get('xs'), (int, float)):
            lines.append(f"上次同類：10 日{index_clause(prev['xs'], prev.get('xs_spy'))}。")
        else:
            lines.append('上次同類未有已結算紀錄。')
    if len(hits) < len(chosen):
        lines.append('其餘沒有新列入。')
    lines.append('不是投資建議。')
    return '\n'.join(lines)


def episodes(cons_hist):
    """First day a ticker enters bull or bear. A repeat of the same side does not count."""
    active = set()
    out = []
    for day in sorted(cons_hist or {}):
        snap = cons_hist[day] or {}
        today = set()
        for side in ('bull', 'bear'):
            for ticker in snap.get(side) or []:
                if isinstance(ticker, str) and ticker:
                    today.add((ticker, side))
        for ticker, side in sorted(today - active):
            out.append({'d': day, 't': ticker, 'side': side})
        active = today
    return out


def week_rows(rows, start, end):
    a, b = start.isoformat(), end.isoformat()
    return [row for row in rows if a <= row['d'] <= b]


def public_score(ft, today):
    """Latest follow-through week that is already closed. Current week stays out."""
    cur = monday(today)
    weeks = {}
    for row in (ft or {}).get('rows') or []:
        signal = str(row.get('signal') or '')[:10]
        if len(signal) != 10:
            continue
        start = monday(signal)
        if start >= cur:
            continue
        weeks.setdefault(start, []).append(row)
    if not weeks:
        return None, []
    start = max(weeks)
    return start, weeks[start]


def inject_html(html):
    if 'function consGroups' not in html:
        raise SystemExit('pay moments: page has no consGroups')
    if MARKER not in html:
        i = html.find('function consGroups')
        j = html.find('</script>', i)
        if j < 0:
            raise SystemExit('pay moments: dashboard script is not closed')
        html = html[:j] + BRIDGE + '\n' + html[j:]
    if TAG not in html:
        if '</body>' not in html:
            raise SystemExit('pay moments: page has no </body>')
        html = html.replace('</body>', TAG + '\n</body>', 1)
    return html


def inject_all():
    for rel in PAGES:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            raise SystemExit('pay moments: missing ' + rel)
        html = open(path, encoding='utf-8').read()
        out = inject_html(html)
        if out != html:
            open(path, 'w', encoding='utf-8').write(out)
            print('pay moments injected', rel)
        else:
            print('pay moments already in', rel)


if __name__ == '__main__':
    inject_all()
