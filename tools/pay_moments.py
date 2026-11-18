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


def load_followthrough():
    path = os.path.join(ROOT, 'data', 'followthrough.json')
    if not os.path.isfile(path):
        return {}
    return json.load(open(path, encoding='utf-8'))


def email_rows(rows, ft, limit=8):
    """At most eight new inclusions, the ones whose last same-side call lagged QQQ the most."""
    lagged = []
    for row in rows:
        prev = prior_settled(ft, row['t'], row['side'], row['d'])
        if not prev or not isinstance(prev.get('xs'), (int, float)) or prev['xs'] >= 0:
            continue
        lagged.append((prev['xs'], row['t'], row))
    lagged.sort()
    return [row for _, _, row in lagged[:limit]]


def email_block(rows, ft):
    """Subscriber email only. At most eight names, each with the previous settled miss."""
    chosen = email_rows(rows, ft)
    lines = [
        '',
        '對倉，不是跟單',
        '這一封最多八隻。只寫上週新列入、上次同類已結算又跑輸最多的。同一方向連續留在名單上只計第一次。不是投資建議。',
    ]
    if not chosen:
        lines.append('上週新列入裡，沒有上次同類已結算而且跑輸的名稱。今次不列名單。')
        return '\n'.join(lines)
    for row in chosen:
        side = '共同看好' if row['side'] == 'bull' else '共同看淡'
        lines.append(f"{row['d'][5:]} ${row['t']} {side}")
        prev = prior_settled(ft, row['t'], row['side'], row['d'])
        xs = prev['xs']
        lines.append(f'上次同類已結算：10 日相對 QQQ {signed_pct(xs)}，跑輸')
        lines.append('今次是新列入。不是投資建議。')
        lines.append('')
    return '\n'.join(lines).rstrip()


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
