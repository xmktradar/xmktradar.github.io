"""Refresh stock prices, intraday lines, market caps and macro rows in index.html.

Covers every ticker mentioned in the embedded posts, so a newly mentioned stock
gets its price line automatically. Uses Yahoo Finance's public chart API.
"""
import http.cookiejar
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HTML = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
HK = timezone(timedelta(hours=8))
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
CRYPTO = {'BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'ADA', 'BNB'}
EXCH_TV = {'NMS': 'NASDAQ', 'NGM': 'NASDAQ', 'NCM': 'NASDAQ', 'NAS': 'NASDAQ', 'NYQ': 'NYSE', 'NYS': 'NYSE',
           'ASE': 'AMEX', 'PCX': 'AMEX', 'BTS': 'AMEX', 'ASX': 'ASX', 'LSE': 'LSE', 'VAN': 'TSXV', 'TOR': 'TSX'}
MACRO = [('ES=F', '標普500期貨', None), ('NQ=F', '納指100期貨', None), ('YM=F', '道指期貨', None),
         ('^VIX', 'VIX', None), ('^TNX', 'US10Y', 'Yahoo Finance（^TNX）'), ('CL=F', 'WTI', 'Yahoo Finance（CL=F）')]

NY = ZoneInfo('America/New_York')
EARNINGS_DAYS = 14  # tag a stock with its next results date when it falls within the next two weeks
# US high-impact economic events for the strip under 大市背景 (public weekly feed, no key). Chinese names here;
# i18n/en.json and ko.json map them back to the English names. Unlisted events keep the feed's English name.
EVENTS_URL = 'https://nfs.faireconomy.media/ff_calendar_thisweek.json'
EVENT_ZH = {
    'CPI m/m': 'CPI 按月', 'CPI y/y': 'CPI 按年', 'Core CPI m/m': '核心 CPI 按月', 'Core CPI y/y': '核心 CPI 按年',
    'PPI m/m': 'PPI 按月', 'Core PPI m/m': '核心 PPI 按月', 'Non-Farm Employment Change': '非農就業人數',
    'Unemployment Rate': '失業率', 'Average Hourly Earnings m/m': '平均時薪按月', 'Federal Funds Rate': '聯儲局利率決議',
    'FOMC Statement': '聯儲局議息聲明', 'FOMC Press Conference': '聯儲局記者會', 'FOMC Meeting Minutes': '聯儲局會議紀錄',
    'FOMC Economic Projections': '聯儲局經濟預測', 'Fed Chair Powell Speaks': '聯儲局主席講話', 'Advance GDP q/q': 'GDP 初值按季',
    'Prelim GDP q/q': 'GDP 修訂值按季', 'Final GDP q/q': 'GDP 終值按季', 'Core PCE Price Index m/m': '核心 PCE 物價按月',
    'Retail Sales m/m': '零售銷售按月', 'Core Retail Sales m/m': '核心零售銷售按月', 'Unemployment Claims': '首次申領失業救濟金',
    'ISM Manufacturing PMI': 'ISM 製造業 PMI', 'ISM Services PMI': 'ISM 服務業 PMI', 'JOLTS Job Openings': 'JOLTS 職位空缺',
    'Prelim UoM Consumer Sentiment': '密歇根大學消費者信心初值', 'CB Consumer Confidence': '世企研究會消費者信心',
    'ADP Non-Farm Employment Change': 'ADP 就業人數', 'Empire State Manufacturing Index': '紐約州製造業指數',
    'Philly Fed Manufacturing Index': '費城聯儲製造業指數', 'Durable Goods Orders m/m': '耐用品訂單按月',
    'Core Durable Goods Orders m/m': '核心耐用品訂單按月',
}

# Tickers Yahoo knows under another symbol: indices people write without the ^, and a few foreign
# companies people call by name (Tim, 2026-10-20)
INDEX_SYMBOLS = {'LVMH': 'MC.PA', 'VIX': '^VIX', 'RUT': '^RUT', 'RTY': '^RUT', 'SOX': '^SOX', 'NYSE': '^NYA', 'COMP': '^IXIC',
                 'IXIC': '^IXIC', 'DJI': '^DJI', 'DXY': 'DX-Y.NYB', 'MOVE': '^MOVE', 'NYA': '^NYA'}
US_EXCH = {'NMS', 'NGM', 'NCM', 'NAS', 'NYQ', 'NYS', 'ASE', 'PCX', 'BTS', 'PNK', 'OQB', 'OQX', 'OBB'}
GIVE_UP_HOURS = 24  # a ticker Yahoo can't find for this long is marked 未確認 (no price, no footer warning)
RECHECK_DAYS = 1  # ... and looked up again daily, in case it lists later (a new IPO) or Yahoo was wrong
AUTO_RULES = 2  # bump when the matching rules change: older automatic matches are redone

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json,text/plain,*/*'})
            with opener.open(req, timeout=25) as r:
                return r.read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429 or e.code >= 500:
                time.sleep(2 ** i * 2)
                continue
            return None
        except Exception:
            time.sleep(2 ** i)
    return None


def chart(sym, rng, interval):
    q = urllib.parse.quote(sym, safe='')
    body = get(f'https://query1.finance.yahoo.com/v8/finance/chart/{q}?range={rng}&interval={interval}&includePrePost=false')
    if not body:
        return None
    try:
        res = json.loads(body)['chart']['result'][0]
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    ts = res.get('timestamp') or []
    closes = ((res.get('indicators') or {}).get('quote') or [{}])[0].get('close') or []
    return res['meta'], [(t, c) for t, c in zip(ts, closes) if c is not None]


def search(t):
    """Yahoo's symbol search. None if Yahoo didn't answer, so an outage never counts as 'not found'."""
    body = get('https://query2.finance.yahoo.com/v1/finance/search?q=' + urllib.parse.quote(t) +
               '&quotesCount=8&newsCount=0&listsCount=0&enableFuzzyQuery=false')
    try:
        return [q for q in json.loads(body).get('quotes') or [] if q.get('symbol')]
    except (TypeError, ValueError, AttributeError):
        return None


def candidates(t, found):
    """Symbols worth trying for ticker t, best first: a known symbol (VIX -> ^VIX), the symbol itself on a US
    exchange, then t as an index. Company-name matches are not used: they picked the wrong stock
    (SATS -> SATS Ltd in Singapore when posts meant Strive's $SATS, 2026-10-20)."""
    out = [INDEX_SYMBOLS[t]] if t in INDEX_SYMBOLS else []
    exact = []
    for q in found:
        sym = q['symbol']
        base = re.split(r'[.\-=]', sym.lstrip('^'))[0].upper()
        kind = q.get('quoteType')
        if kind not in ('EQUITY', 'ETF', 'INDEX'):
            continue
        if base == t and (q.get('exchange') in US_EXCH or kind == 'INDEX'):
            exact.append(sym)
    return list(dict.fromkeys(out + exact + ['^' + t]))


def lookup(t):
    """Find ticker t on Yahoo when its own symbol has no prices. Returns (symbol, chart), 'none' when Yahoo
    answered but has nothing, or None when Yahoo didn't answer."""
    found = search(t)
    time.sleep(0.3)
    if found is None:
        return None
    for sym in candidates(t, found):
        r = chart(sym, '1y', '1d')
        time.sleep(0.3)
        if r and r[1]:
            return sym, r
    return 'none'


def auto_override(ov, t, sym, meta, stamp):
    """Remember how ticker t was matched, so later runs go straight to the right symbol."""
    o = {'confirmed': True, 'auto': AUTO_RULES, 'symbol': sym, 'name': meta.get('longName') or meta.get('shortName') or t,
         'matched_hkt': stamp}
    if meta.get('exchangeName') not in US_EXCH and meta.get('instrumentType') != 'INDEX':
        o['exchange'] = EXCH_TV.get(meta.get('exchangeName')) or meta.get('fullExchangeName') or meta.get('exchangeName')
        o['currency'] = meta.get('currency')
    ov[t] = o


def note_miss(ov, t, now, stamp):
    """Yahoo has no such ticker: after GIVE_UP_HOURS mark it 未確認 (a word, a delisted or private name)."""
    o = ov.setdefault(t, {'auto': AUTO_RULES, 'first_miss_hkt': stamp})
    o.setdefault('first_miss_hkt', stamp)
    o.pop('confirmed', None)
    first = datetime.strptime(o['first_miss_hkt'], '%Y-%m-%d %H:%M').replace(tzinfo=HK)
    if now - first >= timedelta(hours=GIVE_UP_HOURS):
        o.update(unconfirmed=True, checked=now.date().isoformat(),
                 note='Yahoo Finance 搵唔到呢個代號（可能係普通字、已除牌或未上市），自動標為未確認，唔顯示股價')
        return True
    return False


def local_date(ts, meta):
    return datetime.fromtimestamp(ts + (meta.get('gmtoffset') or 0), timezone.utc).date().isoformat()


def quotes_for(symbols):
    """Market caps via the v7 quote API (needs Yahoo's cookie + crumb); empty dict if unavailable."""
    get('https://fc.yahoo.com/')
    crumb = get('https://query1.finance.yahoo.com/v1/test/getcrumb')
    if not crumb or len(crumb) > 40 or '<' in crumb:
        return {}
    out = {}
    syms = list(symbols)
    for i in range(0, len(syms), 50):
        part = ','.join(syms[i:i + 50])
        body = get('https://query1.finance.yahoo.com/v7/finance/quote?symbols=' + urllib.parse.quote(part, safe=',') +
                   '&crumb=' + urllib.parse.quote(crumb))
        try:
            for q in json.loads(body)['quoteResponse']['result']:
                out[q['symbol']] = q
        except Exception:
            pass
        time.sleep(0.5)
    return out


def earnings_flags(d, tickers, sym_of, qs, now):
    """Next results date from the v7 quote data (Yahoo); replaces older 業績 tags for the same stock."""
    today = now.astimezone(NY).date()
    flags = d['macro'].setdefault('flags', [])
    for t in tickers:
        q = qs.get(sym_of.get(t)) or {}
        ts = q.get('earningsTimestampStart') or q.get('earningsTimestamp')
        if q.get('quoteType') != 'EQUITY' or not ts:
            continue
        day = datetime.fromtimestamp(ts, NY).date()
        if not today <= day <= today + timedelta(days=EARNINGS_DAYS):
            continue
        est = bool(q.get('isEarningsDateEstimate'))
        note = f'{day.month}/{day.day}（美國時間）公布季度業績' + ('，預計日期未經公司確認' if est else '') + '（Yahoo Finance）'
        flags[:] = [f for f in flags if not (f.get('t') == t and f.get('type') == '業績')]
        flags.append({'t': t, 'type': '業績', 'date': day.isoformat(), 'note': note, 'auto': True,
                      'url': f'https://finance.yahoo.com/quote/{urllib.parse.quote(sym_of[t])}/'})


def econ_events(stamp):
    """This week's remaining US high-impact events, times in HKT; None if the feed is unavailable."""
    body = get(EVENTS_URL)
    try:
        rows = json.loads(body)
    except (TypeError, ValueError):
        return None
    out = []
    for r in rows if isinstance(rows, list) else []:
        if r.get('country') != 'USD' or r.get('impact') != 'High':
            continue
        try:
            t = datetime.fromisoformat(r['date'])
        except (KeyError, ValueError):
            continue
        if t.astimezone(NY).strftime('%H:%M') == '00:00':
            continue  # all-day or tentative, no real time
        hk = t.astimezone(HK).strftime('%Y-%m-%d %H:%M')
        if hk < stamp:
            continue
        title = r.get('title') or ''
        out.append({'time': hk, 'title': EVENT_ZH.get(title) or ('聯儲局主席講話' if re.match(r'Fed Chair(man)? \w+ Speaks$', title) else title), 'imp': '高', 'url': 'https://www.forexfactory.com/calendar', 'auto': True})
    return sorted(out, key=lambda e: e['time'])


def main():
    s = open(HTML, encoding='utf-8').read()
    m = re.search(r'(<script type="application/json" id="dash-data">)(.*?)(</script>)', s, re.S)
    d = json.loads(m.group(2))
    n_posts = len(d['posts'])
    ov = d.setdefault('overrides', {})
    now = datetime.now(HK)
    stamp = now.strftime('%Y-%m-%d %H:%M')

    tickers = set()  # every ticker in the kept posts (stock posts stay 28 days, merge_posts.py)
    for p in d['posts']:
        sbt = p.get('stance_by_ticker') if isinstance(p.get('stance_by_ticker'), dict) else {}
        for t in list(p.get('tickers') or []) + list(sbt):
            t = str(t).lstrip('$').upper().strip()
            if t and re.fullmatch(r'[A-Z0-9.\-=^]{1,12}', t):
                tickers.add(t)
    # Drop data for stocks no post mentions any more, so search and the disclaimer only list live stocks
    # (px/<ticker>.json follows d['prices'] in build_langs.py). A stock mentioned again is re-fetched in full.
    dropped = []
    for key in ('prices', 'intraday', 'quotes', 'tv_symbols'):
        for t in [t for t in d.get(key, {}) if t not in tickers]:
            del d[key][t]
            if key == 'prices':
                dropped.append(t)
    for t in [t for t, o in ov.items() if o.get('auto') and (t not in tickers or o['auto'] != AUTO_RULES)]:
        del ov[t]  # automatic matches follow the posts, like prices do, and are redone when the rules change
        for key in ('prices', 'intraday', 'quotes', 'tv_symbols'):
            d.get(key, {}).pop(t, None)  # its old symbol lives there too
    recheck = (now - timedelta(days=RECHECK_DAYS)).date().isoformat()
    due = lambda o: o.get('auto') and o.get('checked', '') <= recheck  # an automatic 未確認 is retried weekly
    tickers = sorted(t for t in tickers if t not in CRYPTO and not ov.get(t, {}).get('drop') and
                     (not ov.get(t, {}).get('unconfirmed') or due(ov[t])))

    missing, ok = [], 0
    matched, gave_up = [], []
    sym_of = {}
    for t in tickers:
        sym = ov.get(t, {}).get('symbol') or d['prices'].get(t, {}).get('symbol') or t
        sym_of[t] = sym
        daily = chart(sym, '1y', '1d')
        time.sleep(0.3)
        mine = t not in ov or ov[t].get('auto')  # never second-guess a hand-written override
        if (not daily or not daily[1]) and mine:
            r = lookup(t)
            if isinstance(r, tuple):
                sym, daily = r
                sym_of[t] = sym
                auto_override(ov, t, sym, daily[0], stamp)
                matched.append(f'{t}->{sym}')
            elif r == 'none' and note_miss(ov, t, now, stamp):
                gave_up.append(t)
                continue  # 未確認 now: no price, not listed as missing
        elif daily and daily[1] and mine and t in ov and not ov[t].get('symbol'):
            del ov[t]  # it was only waiting on a miss; its own symbol works again
        if not daily or not daily[1]:
            missing.append(t)
            continue
        meta, rows = daily
        c = [[local_date(ts, meta), round(v, 4)] for ts, v in rows]
        dedup = {}
        for day, v in c:
            dedup[day] = v
        c = [[k, v] for k, v in sorted(dedup.items())]
        old = d['prices'].get(t, {})
        d['prices'][t] = {'source': 'Yahoo Finance', 'name': meta.get('longName') or meta.get('shortName') or old.get('name') or t,
                          'instrument_type': meta.get('instrumentType') or old.get('instrument_type'),
                          'exchange': meta.get('fullExchangeName') or old.get('exchange'), 'currency': meta.get('currency') or old.get('currency'),
                          'as_of': c[-1][0], 'first_date': c[0][0], 'fetched_hkt': stamp, 'symbol': sym, 'c': c}
        intra = {}
        for key, rng, iv in (('1d', '1d', '5m'), ('5d', '5d', '30m')):
            r = chart(sym, rng, iv)
            time.sleep(0.3)
            if r and r[1]:
                intra[key] = [[ts * 1000, round(v, 4)] for ts, v in r[1]]
        if intra:
            intra['fetched_hkt'] = stamp
            d['intraday'][t] = intra
        ex = EXCH_TV.get(meta.get('exchangeName'))
        if ex and t not in d.get('tv_symbols', {}):
            d.setdefault('tv_symbols', {})[t] = f'{ex}:{sym.split(".")[0]}'
        ok += 1

    qs = quotes_for(sym_of[t] for t in tickers if t not in missing)
    for t in tickers:
        q = qs.get(sym_of.get(t))
        if q and q.get('marketCap'):
            d['quotes'][t] = {'mcap': q['marketCap'], 'type': q.get('quoteType'), 'cur': q.get('currency'), 'date': now.date().isoformat()}

    rows = []
    for sym, name, src in MACRO:
        # range 1d: chartPreviousClose is the previous session's close (with 5d it was the close
        # before the 5-day window, so the strip showed a 5-day change as if it were today's)
        r = chart(sym, '1d', '5m')
        time.sleep(0.3)
        if not r:
            continue
        meta = r[0]
        price, prev = meta.get('regularMarketPrice'), meta.get('previousClose') or meta.get('chartPreviousClose')
        ts = meta.get('regularMarketTime')
        if price is None or ts is None:
            continue
        row = {'name': name, 'value': round(price, 3), 'pct': None, 'bp': None,
               'time': datetime.fromtimestamp(ts, HK).strftime('%Y-%m-%d %H:%M'), 'src': src or 'Yahoo Finance'}
        if sym == '^TNX':
            row['bp'] = round((price - prev) * 100, 1) if prev else None
        elif prev:
            row['pct'] = round((price / prev - 1) * 100, 2)
        rows.append(row)
    if rows:
        d['macro']['rows'] = rows
        d['macro']['date'] = now.date().isoformat()
        d['macro']['as_of'] = stamp
    d['macro']['events'] = [e for e in d['macro'].get('events', []) if e.get('time', '') >= stamp]
    ev = econ_events(stamp)
    if ev is not None:
        d['macro']['events'] = ev
    earnings_flags(d, tickers, sym_of, qs, now)
    # stock tags: news shows for 3 days, earnings until the day after (US results land on the HK morning after)
    keep = lambda f: f.get('date', '') >= (now - timedelta(days=1 if f.get('type') == '業績' else 3)).date().isoformat()
    d['macro']['flags'] = [f for f in d['macro'].get('flags', []) if keep(f)]
    d['meta']['price_missing'] = missing

    assert len(d['posts']) == n_posts
    blob = json.dumps(d, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    s = s[:m.start(2)] + blob + s[m.end(2):]
    open(HTML, 'w', encoding='utf-8').write(s)
    print(f'tickers {len(tickers)} ok {ok} missing {len(missing)} quotes {len(qs)} macro {len(rows)}')
    print('missing:', ','.join(missing))
    print('auto-matched:', ','.join(matched) or '-', '| marked 未確認:', ','.join(gave_up) or '-')
    print(f'dropped {len(dropped)} no longer mentioned:', ','.join(sorted(dropped)))
    if ok < len(tickers) * 0.5:
        sys.exit('too many price failures; not publishing')


if __name__ == '__main__':
    main()
