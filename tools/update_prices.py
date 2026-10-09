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

HTML = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
HK = timezone(timedelta(hours=8))
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
CRYPTO = {'BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'ADA', 'BNB'}
EXCH_TV = {'NMS': 'NASDAQ', 'NGM': 'NASDAQ', 'NCM': 'NASDAQ', 'NAS': 'NASDAQ', 'NYQ': 'NYSE', 'NYS': 'NYSE',
           'ASE': 'AMEX', 'PCX': 'AMEX', 'BTS': 'AMEX', 'ASX': 'ASX', 'LSE': 'LSE', 'VAN': 'TSXV', 'TOR': 'TSX'}
MACRO = [('ES=F', '標普500期貨', None), ('NQ=F', '納指100期貨', None), ('YM=F', '道指期貨', None),
         ('^VIX', 'VIX', None), ('^TNX', '10 年期債息', 'Yahoo Finance（^TNX）'), ('CL=F', 'WTI', 'Yahoo Finance（CL=F）')]

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


def main():
    s = open(HTML, encoding='utf-8').read()
    m = re.search(r'(<script type="application/json" id="dash-data">)(.*?)(</script>)', s, re.S)
    d = json.loads(m.group(2))
    n_posts = len(d['posts'])
    ov = d.get('overrides', {})
    now = datetime.now(HK)
    stamp = now.strftime('%Y-%m-%d %H:%M')

    tickers = set()
    for p in d['posts']:
        sbt = p.get('stance_by_ticker') if isinstance(p.get('stance_by_ticker'), dict) else {}
        for t in list(p.get('tickers') or []) + list(sbt):
            t = str(t).lstrip('$').upper().strip()
            if t and re.fullmatch(r'[A-Z0-9.\-=^]{1,12}', t):
                tickers.add(t)
    tickers = sorted(t for t in tickers if t not in CRYPTO and not ov.get(t, {}).get('unconfirmed') and not ov.get(t, {}).get('drop'))

    missing, ok = [], 0
    sym_of = {}
    for t in tickers:
        sym = ov.get(t, {}).get('symbol') or d['prices'].get(t, {}).get('symbol') or t
        sym_of[t] = sym
        daily = chart(sym, '1y', '1d')
        time.sleep(0.3)
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
        r = chart(sym, '5d', '5m')
        time.sleep(0.3)
        if not r:
            continue
        meta = r[0]
        price, prev = meta.get('regularMarketPrice'), meta.get('chartPreviousClose') or meta.get('previousClose')
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
    d['meta']['price_missing'] = missing

    assert len(d['posts']) == n_posts
    blob = json.dumps(d, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    s = s[:m.start(2)] + blob + s[m.end(2):]
    open(HTML, 'w', encoding='utf-8').write(s)
    print(f'tickers {len(tickers)} ok {ok} missing {len(missing)} quotes {len(qs)} macro {len(rows)}')
    print('missing:', ','.join(missing))
    if ok < len(tickers) * 0.5:
        sys.exit('too many price failures; not publishing')


if __name__ == '__main__':
    main()
