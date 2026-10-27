"""Earnings briefs, step 1: numbers for every US-listed common stock worth US$50B or more (Tim, 2026-10-27).

Spec: Claude project file dashboard/earnings-brief-spec.md. No AI, no paid API:
  - company list: SEC's ticker list (Nasdaq/NYSE) + Yahoo v7 quotes (market cap, next results date), once a day
  - reported numbers: SEC XBRL companyfacts (10-Q / 10-K). Only companies that file 10-Q get a brief.
  - revenue lines: the segment facts inside the latest 10-Q / 10-K instance (SEC Archives)
  - estimates: Yahoo quoteSummary (earningsHistory = EPS actual vs estimate; earningsTrend = revenue estimate,
    saved before the results so it can be compared afterwards)
Writes data/earnings/universe.json, data/earnings/state.json and data/earnings/co/<TICKER>.json (only when changed).
A source that fails is retried next run; this step never stops the site update (continue-on-error).
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sitedata import notice, read_json, write_json  # noqa: E402

HK = timezone(timedelta(hours=8))
NYZ = timezone(timedelta(hours=-5))  # date of the US session; DST is not needed for a calendar day
DIR = 'data/earnings'
CO_DIR = f'{DIR}/co'
UNIVERSE = f'{DIR}/universe.json'
STATE = f'{DIR}/state.json'
MIN_CAP = 50e9
QUARTERS_KEPT = 12
SEC_UA = 'TheCrowdTape grokbottimli@gmail.com'
YH_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
BUDGET = float(os.environ.get('EARNINGS_BUDGET', '540'))  # seconds; the rest waits for the next run
START = time.time()

REV = ('Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'RevenueFromContractWithCustomerIncludingAssessedTax',
       'SalesRevenueNet', 'SalesRevenueGoodsNet', 'RevenuesNetOfInterestExpense')
BANK_REV = 'RevenuesNetOfInterestExpense'
COST = ('CostOfRevenue', 'CostOfGoodsAndServicesSold', 'CostOfGoodsSold')
DUR = {
    'gp': ('GrossProfit',),
    'op': ('OperatingIncomeLoss',),
    'ni': ('NetIncomeLoss', 'NetIncomeLossAvailableToCommonStockholdersBasic', 'ProfitLoss'),
    'ocf': ('NetCashProvidedByUsedInOperatingActivities', 'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'),
    'capex': ('PaymentsToAcquirePropertyPlantAndEquipment', 'PaymentsToAcquireProductiveAssets'),
}
EPS = ('EarningsPerShareDiluted', 'EarningsPerShareBasicAndDiluted')
INST = {
    'cash': ('CashAndCashEquivalentsAtCarryingValue', 'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents', 'CashAndDueFromBanks'),
    'sti': ('ShortTermInvestments', 'MarketableSecuritiesCurrent', 'AvailableForSaleSecuritiesDebtSecuritiesCurrent'),
    'ltd': ('LongTermDebt',),
    'ltd_nc': ('LongTermDebtNoncurrent', 'LongTermDebtAndCapitalLeaseObligations'),
    'ltd_c': ('LongTermDebtCurrent', 'LongTermDebtAndCapitalLeaseObligationsCurrent'),
    'std': ('ShortTermBorrowings', 'CommercialPaper'),
}
SEG_AXES = ('srt:ProductOrServiceAxis', 'us-gaap:StatementBusinessSegmentsAxis')
RULES = 3  # bump when the extraction rules change: every company is read again from SEC
STALE_DAYS = 125  # a latest quarter older than this is checked against SEC again once a day
QMIN, QMAX = 75, 120  # days in a quarter: 13 weeks, or 16 weeks for retailers such as AZO and COST
FILED_GAP = 100  # latest quarter older than this: look for newer 10-Q / 10-K filings companyfacts does not carry yet


def left():
    return BUDGET - (time.time() - START)


# ---------- HTTP ----------

def _open(url, headers, timeout=40, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with OPENER.open(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (429, 403) or e.code >= 500:
                time.sleep(2 + 3 * i)
                continue
            return None
        except Exception:
            time.sleep(1 + i)
    return None


import http.cookiejar  # noqa: E402
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
_last_sec = [0.0]


def sec(url):
    """SEC asks for at most 10 requests a second and a User-Agent with a contact address."""
    wait = 0.15 - (time.time() - _last_sec[0])
    if wait > 0:
        time.sleep(wait)
    _last_sec[0] = time.time()
    return _open(url, {'User-Agent': SEC_UA, 'Accept': 'application/json,text/xml,*/*'}, timeout=60)


def sec_json(url):
    body = sec(url)
    try:
        return json.loads(body) if body else None
    except ValueError:
        return None


_crumb = [None]


def yahoo(url):
    body = _open(url, {'User-Agent': YH_UA, 'Accept': 'application/json,text/plain,*/*'}, timeout=25)
    try:
        return json.loads(body) if body else None
    except ValueError:
        return None


def crumb():
    if _crumb[0] is None:
        _open('https://fc.yahoo.com/', {'User-Agent': YH_UA}, tries=1)
        c = _open('https://query1.finance.yahoo.com/v1/test/getcrumb', {'User-Agent': YH_UA})
        c = c.decode('utf-8', 'replace').strip() if c else ''
        _crumb[0] = c if c and len(c) < 40 and '<' not in c else ''
    return _crumb[0]


def quotes(symbols):
    c = crumb()
    if not c:
        return {}
    out, syms = {}, list(symbols)
    for i in range(0, len(syms), 50):
        part = ','.join(syms[i:i + 50])
        j = yahoo('https://query1.finance.yahoo.com/v7/finance/quote?symbols=' + urllib.parse.quote(part, safe=',') +
                  '&crumb=' + urllib.parse.quote(c))
        for q in ((j or {}).get('quoteResponse') or {}).get('result') or []:
            if q.get('symbol'):
                out[q['symbol']] = q
        time.sleep(0.4)
    return out


def summary(sym):
    c = crumb()
    if not c:
        return None
    j = yahoo(f'https://query2.finance.yahoo.com/v10/finance/quoteSummary/{urllib.parse.quote(sym)}'
              f'?modules=earningsHistory,earningsTrend&crumb={urllib.parse.quote(c)}')
    try:
        return j['quoteSummary']['result'][0]
    except (TypeError, KeyError, IndexError):
        return None


def raw(x):
    if isinstance(x, dict):
        x = x.get('raw')
    return x if isinstance(x, (int, float)) else None


# ---------- dates ----------

def d(s):
    return date.fromisoformat(s[:10])


def days(a, b):
    return (d(b) - d(a)).days


def today_ny():
    return datetime.now(NYZ).date()


# ---------- XBRL companyfacts -> quarters ----------

def entries(facts, name, unit='USD'):
    for tax in ('us-gaap', 'ifrs-full'):
        c = ((facts.get('facts') or {}).get(tax) or {}).get(name)
        if c:
            u = c.get('units') or {}
            got = u.get(unit) or (u.get('USD/shares') if unit == 'USD/shares' else None)
            if got:
                return [e for e in got if str(e.get('form', '')).startswith(('10-Q', '10-K')) and 'val' in e]
    return []


def best(es):
    """One value per (start, end): the latest filing (restated numbers win)."""
    out = {}
    for e in es:
        k = (e.get('start'), e['end'])
        if k not in out or e.get('filed', '') >= out[k].get('filed', ''):
            out[k] = e
    return out


def quarterly(es):
    """{quarter end: value} for flow items; a quarter missing as a 3-month figure is year-to-date minus the
    year-to-date that ended one quarter earlier (cash flow in 10-Q, Q4 in the 10-K)."""
    b = best(es)
    q = {}
    for (s, e), x in b.items():
        if s and QMIN <= days(s, e) <= QMAX:
            q[e] = x['val']
    by_start = {}
    for (s, e), x in b.items():
        if s:
            by_start.setdefault(s, {})[e] = x['val']
    for s, ends in by_start.items():
        for e, v in ends.items():
            if e in q or days(s, e) < 150:
                continue
            for e2, v2 in ends.items():
                if QMIN <= days(e2, e) <= QMAX:
                    q[e] = v - v2
                    break
    return q


def instants(es):
    b = best(es)
    return {e: x['val'] for (s, e), x in b.items() if not s}


def first_of(facts, names, fn, unit='USD'):
    """Merge the candidates: for each date the first name (in order) that has a value."""
    out = {}
    for n in names:
        for k, v in fn(entries(facts, n, unit)).items():
            out.setdefault(k, v)
    return out


def revenue(facts):
    """Total revenue per quarter. Banks: net revenue. Others: the largest candidate (a candidate that is only part
    of revenue, such as fee income, is never bigger than the total)."""
    bank = quarterly(entries(facts, BANK_REV))
    per = [quarterly(entries(facts, n)) for n in REV if n != BANK_REV]
    out = {}
    for s in per:
        for e, v in s.items():
            if e not in out or v > out[e]:
                out[e] = v
    out.update(bank)
    # banks that tag no total revenue in their 10-Q (BNY): fee and other income + net interest income
    fees = quarterly(entries(facts, 'NoninterestIncome'))
    nii = quarterly(entries(facts, 'InterestIncomeExpenseNet'))
    derived = {e: fees[e] + nii[e] for e in fees if e in nii and e not in out}
    if derived and max(derived) > max(out, default=''):
        out.update(derived)
        return out, True
    return out, bool(bank)


def periods(facts):
    """{period end: (label, filed, accn, form)} from the filing that first reported that end as its own period.
    A comparative figure (filed a year or more after its end) takes the fiscal year it belongs to, and an end that no
    labelled fact covers gets its label from the fiscal year-end month (XOM in 2026-10)."""
    first, any_ = {}, {}
    fye = None
    for tax in ('us-gaap', 'dei'):
        for c in ((facts.get('facts') or {}).get(tax) or {}).values():
            for es in (c.get('units') or {}).values():
                for e in es:
                    form = str(e.get('form', ''))
                    if not form.startswith(('10-Q', '10-K')):
                        continue
                    k = e['end']
                    if k not in any_ or e.get('filed', '') < any_[k].get('filed', ''):
                        any_[k] = e
                    if not e.get('fy') or not e.get('fp'):
                        continue
                    if e['fp'] == 'FY' and e.get('start') and days(e['start'], k) > 340 and days(k, e.get('filed', k)) < 200 \
                            and (fye is None or k > fye[0]) and str(e['fy']).isdigit():
                        fye = (k, int(e['fy']))
                    if k not in first or e.get('filed', '') < first[k].get('filed', ''):
                        first[k] = e
    out = {}
    for k, e in first.items():
        fp = e['fp'] if e['fp'] != 'FY' else 'Q4'
        if fp not in ('Q1', 'Q2', 'Q3', 'Q4'):
            continue
        fy = e['fy']
        lag = days(k, e['filed']) if e.get('filed') else 0
        if lag > 200 and str(fy).isdigit():
            fy = int(fy) - round((lag - 60) / 365)
        out[k] = {'label': f"FY{fy} {fp}", 'filed': e.get('filed'), 'accn': e.get('accn'), 'form': e.get('form')}
    if fye:
        def month(d):  # 52/53-week periods ending in the first days of a month belong to the month before
            y, m = int(d[:4]), int(d[5:7]) - (1 if int(d[8:10]) <= 7 else 0)
            return (y - 1, 12) if m == 0 else (y, m)
        fy_end, fm = month(fye[0])
        shift = fye[1] - fy_end  # the company's own fiscal-year numbering
        for k, e in any_.items():
            if k in out:
                continue
            y, m = month(k)
            q = ((m - fm - 1) % 12) // 3 + 1
            out[k] = {'label': f"FY{(y if m <= fm else y + 1) + shift} Q{q}", 'filed': e.get('filed'), 'accn': e.get('accn'), 'form': e.get('form')}
    return out


WANT = set(REV) | set(COST) | set(EPS) | {'NoninterestIncome', 'InterestIncomeExpenseNet'} | \
    {n for v in DUR.values() for n in v} | {n for v in INST.values() for n in v}


def instance_facts(xml_bytes):
    """Facts without dimensions from a filing's XBRL instance: [(concept, start, end, value, unit)], fiscal year, period."""
    root = ET.fromstring(xml_bytes)
    ctx, units, out, fy, fp = {}, {}, [], None, None
    for c in root.iter():
        n = local(c.tag)
        if n == 'context':
            s = e = None
            dims = False
            for x in c.iter():
                m = local(x.tag)
                if m == 'startDate':
                    s = (x.text or '').strip()
                elif m in ('endDate', 'instant'):
                    e = (x.text or '').strip()
                elif m in ('explicitMember', 'typedMember'):
                    dims = True
            if not dims:
                ctx[c.get('id')] = (s, e)
        elif n == 'unit':
            units[c.get('id')] = ''.join((x.text or '').strip().lower() for x in c.iter() if local(x.tag) == 'measure')
    for x in root:
        n = local(x.tag)
        if n == 'DocumentFiscalYearFocus':
            fy = (x.text or '').strip()
        elif n == 'DocumentFiscalPeriodFocus':
            fp = (x.text or '').strip()
        elif n in WANT and x.get('contextRef') in ctx and x.text and x.get('{http://www.w3.org/2001/XMLSchema-instance}nil') != 'true':
            try:
                v = float(x.text.strip())
            except ValueError:
                continue
            s, e = ctx[x.get('contextRef')]
            u = units.get(x.get('unitRef'), '')
            out.append((n, s, e, int(v) if v.is_integer() else v, 'USD/shares' if 'shares' in u else 'USD' if 'usd' in u else None))
    return out, fy, fp


def supplement(facts, cik, after):
    """companyfacts can lag a company's filings by months (KO, V, C ... in 2026-10). Read the 10-Q / 10-K filings that
    report a period after `after` straight from their XBRL instance and add their facts in the companyfacts shape."""
    sub = sec_json(f'https://data.sec.gov/submissions/CIK{int(cik):010d}.json')
    r = ((sub or {}).get('filings') or {}).get('recent') or {}
    rows = zip(r.get('form') or [], r.get('accessionNumber') or [], r.get('filingDate') or [], r.get('reportDate') or [])
    todo = sorted((rep, accn, filed, form) for form, accn, filed, rep in rows
                  if form in ('10-Q', '10-K') and rep and rep > after)[:4]
    added = 0
    for rep, accn, filed, form in todo:
        if left() < 60:
            break
        folder = f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace("-", "")}'
        items = ((sec_json(folder + '/index.json') or {}).get('directory') or {}).get('item') or []
        names = [i.get('name', '') for i in items]
        inst = next((n for n in names if n.endswith('_htm.xml')), None)
        body = sec(f'{folder}/{inst}') if inst else None
        if not body:
            continue
        try:
            got, fy, fp = instance_facts(body)
        except ET.ParseError:
            continue
        fy = fy or rep[:4]
        fp = fp or ('FY' if form == '10-K' else None)
        gaap = facts.setdefault('facts', {}).setdefault('us-gaap', {})
        for n, st, en, v, unit in got:
            if not unit or not en:
                continue
            e = {'end': en, 'val': v, 'accn': accn, 'fy': int(fy) if str(fy).isdigit() else fy, 'fp': fp, 'form': form, 'filed': filed}
            if st:
                e['start'] = st
            gaap.setdefault(n, {}).setdefault('units', {}).setdefault(unit, []).append(e)
        added += 1
    return added


def build_quarters(facts):
    rev, bank = revenue(facts)
    if not rev:
        return None
    per = periods(facts)
    flows = {k: first_of(facts, v, quarterly) for k, v in DUR.items()}
    cost = first_of(facts, COST, quarterly)
    eps = first_of(facts, EPS, quarterly, unit='USD/shares')
    ends = sorted(e for e in rev if e in per)[-QUARTERS_KEPT:]
    if not ends:
        return None
    qs = []
    for e in ends:
        r = rev[e]
        gp = flows['gp'].get(e)
        if gp is None and e in cost and not bank:
            gp = r - cost[e]
        ocf, capex = flows['ocf'].get(e), flows['capex'].get(e)
        qs.append({'end': e, 'label': per[e]['label'], 'rev': r, 'gp': gp, 'op': flows['op'].get(e), 'ni': flows['ni'].get(e),
                   'eps': eps.get(e), 'ocf': ocf, 'capex': capex,
                   'fcf': (ocf - capex) if ocf is not None and capex is not None else None})
    last = ends[-1]
    inst = {k: first_of(facts, v, instants) for k, v in INST.items()}
    bal_end = max((e for e in inst['cash'] if e <= last), default=None)
    bal = None
    if bal_end:
        g = lambda k: inst[k].get(bal_end)  # noqa: E731
        ltd = g('ltd')
        if ltd is None and (g('ltd_nc') is not None or g('ltd_c') is not None):
            ltd = (g('ltd_nc') or 0) + (g('ltd_c') or 0)
        debt = None if ltd is None and g('std') is None else (ltd or 0) + (g('std') or 0)
        bal = {'end': bal_end, 'cash': g('cash'), 'sti': g('sti'), 'debt': debt}
    return {'q': qs, 'latest': dict(per[last], end=last), 'bal': bal, 'bank': bank, 'diag': diagnose(facts, last)}


def newest_period(facts):
    """End of the newest period any 10-Q / 10-K reported (a duration fact that ended on or before its filing)."""
    best_ = None
    for tax, cs in (facts.get('facts') or {}).items():
        if tax == 'dei':
            continue
        for c in cs.values():
            for es in (c.get('units') or {}).values():
                for e in es:
                    if e.get('start') and str(e.get('form', '')).startswith(('10-Q', '10-K')) and e['end'] <= e.get('filed', ''):
                        if best_ is None or e['end'] > best_:
                            best_ = e['end']
    return best_


def diagnose(facts, rev_last):
    """When revenue stops before the newest filed period, list the revenue-like concepts that do have that period,
    so the next fix can be made from the data (written to the company file as "diag")."""
    newest = newest_period(facts)
    if not newest or not rev_last or days(rev_last, newest) < 30:
        return None
    found = []
    for tax, cs in (facts.get('facts') or {}).items():
        for name, c in cs.items():
            if not re.search(r'revenue|sales', name, re.I):
                continue
            for unit, es in (c.get('units') or {}).items():
                for e in es:
                    if e['end'] == newest and e.get('start') and str(e.get('form', '')).startswith(('10-Q', '10-K')):
                        found.append({'c': f'{tax}:{name}', 'start': e['start'], 'end': e['end'], 'val': e['val'], 'form': e.get('form'),
                                      'fp': e.get('fp'), 'filed': e.get('filed')})
    last = {}
    for n in REV:
        es = entries(facts, n)
        if es:
            x = max(es, key=lambda e: (e['end'], e.get('filed', '')))
            last[n] = {k: x.get(k) for k in ('start', 'end', 'form', 'fp', 'filed')}
    return {'newest': newest, 'rev_last': rev_last, 'have': found[:20], 'rev_concepts_last': last}


# ---------- revenue lines from the filing's own XBRL instance ----------

def local(tag):
    return tag.rsplit('}', 1)[-1]


def parse_instance(xml_bytes):
    """contexts {id: (start, end, ((axis, member),...))}, facts {concept: [(ctx, value)]} for revenue concepts."""
    ctx, facts = {}, {}
    root = ET.fromstring(xml_bytes)
    for c in root.iter():
        if local(c.tag) != 'context':
            continue
        s = e = None
        dims = []
        for x in c.iter():
            n = local(x.tag)
            if n == 'startDate':
                s = (x.text or '').strip()
            elif n in ('endDate', 'instant'):
                e = (x.text or '').strip()
            elif n == 'explicitMember':
                dims.append((x.get('dimension'), (x.text or '').strip()))
            elif n == 'typedMember':
                dims.append((x.get('dimension'), '?'))
        ctx[c.get('id')] = (s, e, tuple(dims))
    for x in root:
        n = local(x.tag)
        if n in REV and x.get('contextRef') and x.text:
            try:
                facts.setdefault(n, []).append((x.get('contextRef'), float(x.text.strip())))
            except ValueError:
                pass
    return ctx, facts


def parse_labels(xml_bytes):
    """{'aapl_IPhoneMember': 'iPhone'} from the label linkbase (standard label role)."""
    out = {}
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return out
    XL = '{http://www.w3.org/1999/xlink}'
    for link in root.iter():
        if local(link.tag) != 'labelLink':
            continue
        loc, lab, arcs = {}, {}, []
        for x in link:
            n = local(x.tag)
            if n == 'loc':
                loc[x.get(XL + 'label')] = (x.get(XL + 'href') or '').split('#')[-1]
            elif n == 'label':
                role = x.get(XL + 'role') or ''
                if role.endswith('/label') or role.endswith('/terseLabel'):
                    lab.setdefault(x.get(XL + 'label'), {})[role.rsplit('/', 1)[-1]] = (x.text or '').strip()
            elif n == 'labelArc':
                arcs.append((x.get(XL + 'from'), x.get(XL + 'to')))
        for f, t in arcs:
            if f in loc and t in lab:
                got = lab[t]
                out.setdefault(loc[f], got.get('terseLabel') or got.get('label'))
    return out


def member_name(qname, labels):
    frag = qname.replace(':', '_')
    name = labels.get(frag)
    if not name:
        base = qname.split(':')[-1]
        base = re.sub(r'(Segment)?Member$', '', base)
        name = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', base)
    name = re.sub(r'\s*\[Member\]\s*$', '', name).strip()
    name = re.sub(r'\s+(Segment|segment|Member)$', '', name).strip()
    return name or qname


def reconcile(members, total):
    """Members that add up to the total (within 1.5%): drop one aggregate member if that makes it add up;
    a gap of at most 25% becomes 'Other'. None when the lines can't be trusted."""
    if not total or total <= 0 or len(members) < 2 or any(v < 0 for v in members.values()):
        return None
    s = sum(members.values())
    if abs(s - total) / total <= 0.015:
        return dict(members), False
    if s > total:
        for m, v in sorted(members.items(), key=lambda kv: -kv[1]):
            if abs(s - v - total) / total <= 0.015 and len(members) > 2:
                return {k: x for k, x in members.items() if k != m}, False
        return None
    if (total - s) / total <= 0.25:
        return dict(members), True
    return None


def segments(ctx, facts, end, total, total_year):
    """Best revenue breakdown for the quarter ending `end` (or the year, when a 10-K has no 3-month figures)."""
    def pick(lo, hi, tot):
        groups = {}
        for concept, vals in facts.items():
            for cid, v in vals:
                c = ctx.get(cid)
                if not c or not c[0] or c[1] != end or len(c[2]) != 1:
                    continue
                if not lo <= days(c[0], c[1]) <= hi:
                    continue
                axis, mem = c[2][0]
                if axis in SEG_AXES:
                    groups.setdefault((concept, axis), {})[mem] = v
        best_ = None
        for (concept, axis), mems in groups.items():
            if not 2 <= len(mems) <= 12:
                continue
            r = reconcile(mems, tot)
            if not r:
                continue
            score = (min(len(r[0]), 10), axis == SEG_AXES[0])
            if best_ is None or score > best_[0]:
                best_ = (score, concept, axis, r)
        return best_
    got = pick(QMIN, QMAX, total)
    basis = 'quarter'
    if not got and total_year:
        got, basis = pick(340, 380, total_year), 'year'
    if not got:
        return None
    _, concept, axis, (mems, other) = got
    span = ctx_span(ctx, facts, concept, axis, end)
    prev = {}
    for cid, v in facts.get(concept, []):
        c = ctx.get(cid)
        if not c or not c[0] or len(c[2]) != 1 or c[2][0][0] != axis or c[2][0][1] not in mems:
            continue
        if 355 <= days(c[1], end) <= 375 and span and abs(days(c[0], c[1]) - span) <= 15:
            prev[c[2][0][1]] = v
    return {'axis': axis, 'basis': basis, 'members': mems, 'prev': prev, 'other': other}


def ctx_span(ctx, facts, concept, axis, end):
    """Length in days of the current-period contexts used for the breakdown (the prior year must match it)."""
    for cid, _ in facts.get(concept, []):
        c = ctx.get(cid)
        if c and c[0] and c[1] == end and len(c[2]) == 1 and c[2][0][0] == axis:
            return days(c[0], c[1])
    return None


def fetch_segments(cik, accn, end, total, total_year):
    folder = f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace("-", "")}'
    idx = sec_json(folder + '/index.json')
    items = ((idx or {}).get('directory') or {}).get('item') or []
    names = [i.get('name', '') for i in items]
    inst = next((n for n in names if n.endswith('_htm.xml')), None)
    if not inst:
        inst = next((n for n in names if n.endswith('.xml') and not re.search(r'_(cal|def|lab|pre)\.xml$|FilingSummary|^R\d', n)), None)
    if not inst:
        return None
    body = sec(f'{folder}/{inst}')
    if not body:
        return None
    try:
        ctx, facts = parse_instance(body)
    except ET.ParseError:
        return None
    seg = segments(ctx, facts, end, total, total_year)
    if not seg:
        return {'none': True}
    lab = next((n for n in names if n.endswith('_lab.xml')), None)
    labels = parse_labels(sec(f'{folder}/{lab}') or b'') if lab else {}
    rows = [{'name': member_name(m, labels), 'val': v, 'prev': seg['prev'].get(m)} for m, v in
            sorted(seg['members'].items(), key=lambda kv: -kv[1])]
    if seg['other']:
        t = total if seg['basis'] == 'quarter' else total_year
        rows.append({'name': 'Other', 'val': t - sum(seg['members'].values()), 'prev': None, 'other': True})
    return {'axis': seg['axis'], 'basis': seg['basis'], 'rows': rows}


def year_total(facts, end):
    for n in REV:
        for (s, e), x in best(entries(facts, n)).items():
            if e == end and s and 340 <= days(s, e) <= 380:
                return x['val']
    return None


# ---------- company list ----------

def refresh_universe(old):
    lst = sec_json('https://www.sec.gov/files/company_tickers_exchange.json')
    if not lst:
        notice('財報：SEC 公司名單攞唔到，沿用舊名單', 'warning')
        return old
    f = lst.get('fields') or []
    rows = [dict(zip(f, r)) for r in lst.get('data') or []]
    rows = [r for r in rows if r.get('exchange') in ('Nasdaq', 'NYSE') and r.get('ticker')]
    cik_of = {}
    for r in rows:
        cik_of.setdefault(r['ticker'].upper(), r['cik'])
    qs = quotes(cik_of)
    if len(qs) < len(cik_of) * 0.5:
        notice(f'財報：Yahoo 市值只攞到 {len(qs)}/{len(cik_of)}，沿用舊名單', 'warning')
        return old
    seen, out = set(), {}
    for t, q in sorted(qs.items(), key=lambda kv: -(kv[1].get('marketCap') or 0)):
        cik = cik_of.get(t)
        cap = q.get('marketCap') or 0
        if cap < MIN_CAP or q.get('quoteType') != 'EQUITY' or (q.get('currency') or 'USD') != 'USD' or cik in seen:
            continue
        seen.add(cik)
        out[t] = {'cik': cik, 'name': q.get('longName') or q.get('shortName') or t, 'mcap': cap}
    return {'day': datetime.now(HK).strftime('%Y-%m-%d'), 'companies': out}


# ---------- per company ----------

def next_date(q):
    ts = q.get('earningsTimestampStart') or q.get('earningsTimestamp')
    if not ts:
        return None
    return datetime.fromtimestamp(ts, NYZ).date().isoformat()


def update_estimates(t, st, latest_end):
    s = summary(t)
    if not s:
        return False
    hist = []
    for h in ((s.get('earningsHistory') or {}).get('history') or []):
        qd = (h.get('quarter') or {}).get('fmt')
        if qd:
            hist.append({'q': qd, 'act': raw(h.get('epsActual')), 'est': raw(h.get('epsEstimate'))})
    if hist:
        st['eps_hist'] = hist[-8:]
    for tr in ((s.get('earningsTrend') or {}).get('trend') or []):
        if tr.get('period') != '0q' or not tr.get('endDate'):
            continue
        end = tr['endDate']
        if latest_end and end <= latest_end:
            continue  # already reported: keep the estimate saved before the results
        est = st.setdefault('rev_est', {})
        est[end] = {'rev': raw((tr.get('revenueEstimate') or {}).get('avg')),
                    'eps': raw((tr.get('earningsEstimate') or {}).get('avg')),
                    'seen': datetime.now(HK).strftime('%Y-%m-%d')}
        for k in sorted(est)[:-6]:
            del est[k]
    st['est_day'] = datetime.now(HK).strftime('%Y-%m-%d')
    return True


def near(a, b, tol=12):
    return a and b and abs(days(a, b)) <= tol


def estimate_for(st, end):
    eps = next((h for h in st.get('eps_hist') or [] if near(h['q'], end)), None)
    rev = next((v for k, v in (st.get('rev_est') or {}).items() if near(k, end)), None)
    return {'eps_act': eps and eps['act'], 'eps_est': eps and eps['est'],
            'rev_est': rev and rev.get('rev'), 'rev_est_seen': rev and rev.get('seen')}


def write_if_changed(path, obj):
    old = read_json(path)
    if old == obj:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_json(path, obj, indent=1)
    return True


def main():
    os.makedirs(CO_DIR, exist_ok=True)
    now = datetime.now(HK)
    stamp = now.strftime('%Y-%m-%d %H:%M')
    today = now.strftime('%Y-%m-%d')
    uni = read_json(UNIVERSE, {}) or {}
    if uni.get('day') != today and (now.hour >= 6 or not uni.get('companies')):
        uni = refresh_universe(uni)
        if uni.get('companies'):
            write_json(UNIVERSE, uni, indent=1)
    cos = uni.get('companies') or {}
    if not cos:
        notice('財報：未有公司名單，今次唔做', 'warning')
        return
    state = read_json(STATE, {}) or {}
    first_run = not state
    sts = state.setdefault('co', {})
    events = state.setdefault('new', [])
    # Next results dates and market caps, every run (one quote call per 50 companies)
    qs = quotes(cos)
    tny = today_ny().isoformat()
    for t, q in qs.items():
        st = sts.setdefault(t, {})
        if q.get('marketCap'):
            cos[t]['mcap'] = q['marketCap']
        nd = next_date(q)
        if st.get('next') and st['next'] != nd and st['next'] <= tny:
            st['last_report'] = st['next']  # the date we were waiting for has passed
        if nd:
            if nd <= tny and (not st.get('last_report') or nd > st['last_report']):
                st['last_report'] = nd
            st['next'] = nd
    done = fetched = 0
    order = sorted(cos, key=lambda t: -(cos[t].get('mcap') or 0))
    for t in order:
        if left() < 20:
            notice(f'財報：時間到，處理咗 {done}/{len(order)} 間，其餘下次再做', 'warning')
            break
        info, st = cos[t], sts.setdefault(t, {})
        path = f'{CO_DIR}/{t}.json'
        co = read_json(path)
        latest_end = (co or {}).get('latest', {}).get('end')
        lr = st.get('last_report')
        waiting = lr and latest_end and lr > latest_end and days(lr, tny) <= 60
        checked = st.get('facts_hkt')
        stale = not checked or (now - datetime.fromisoformat(checked).replace(tzinfo=HK)) >= timedelta(hours=3)
        if co is None and st.get('no_10q') and checked and (now - datetime.fromisoformat(checked).replace(tzinfo=HK)) < timedelta(days=7):
            done += 1
            continue  # foreign filer (20-F / 6-K): checked again weekly
        old = latest_end and days(latest_end, tny) > STALE_DAYS and (
            not checked or (now - datetime.fromisoformat(checked).replace(tzinfo=HK)) >= timedelta(hours=24))
        if co is None or (waiting and stale) or old or co.get('rules') != RULES:
            facts = sec_json(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{int(info["cik"]):010d}.json')
            st['facts_hkt'] = stamp
            fetched += 1
            if facts:
                b = build_quarters(facts)
                if b and (days(b['latest']['end'], tny) > FILED_GAP or (lr and lr > b['latest']['end'])):
                    try:
                        if supplement(facts, info['cik'], b['latest']['end']):
                            b = build_quarters(facts)
                    except Exception as e:  # a strange filing must not stop the others
                        print(f'supplement {t}: {e}', file=sys.stderr)
                if not b:
                    st['no_10q'] = True
                    done += 1
                    continue
                st.pop('no_10q', None)
                new_end = b['latest']['end']
                fresh = b['latest'].get('filed') and days(b['latest']['filed'], tny) <= 5  # never post an old quarter found late
                if co and latest_end and new_end > latest_end and fresh:
                    events.append({'t': t, 'end': new_end, 'label': b['latest']['label'], 'filed': b['latest']['filed'],
                                   'report': lr if lr and lr >= new_end else b['latest']['filed'], 'found_hkt': stamp,
                                   'first_run': first_run})
                seg = (co or {}).get('seg')
                if not seg or seg.get('accn') != b['latest']['accn']:
                    try:
                        got = fetch_segments(info['cik'], b['latest']['accn'], new_end, b['q'][-1]['rev'], year_total(facts, new_end))
                    except Exception as e:  # a strange filing must not stop the others
                        print(f'segments {t}: {e}', file=sys.stderr)
                        got = None
                    if got is not None:
                        seg = dict(got, accn=b['latest']['accn'])
                    elif seg and seg.get('accn') != b['latest']['accn']:
                        seg = None
                co = {'t': t, 'name': info['name'], 'cik': info['cik'], 'q': b['q'], 'latest': b['latest'], 'bal': b['bal'],
                      'bank': b['bank'], 'seg': seg, 'rules': RULES}
                if b['diag']:
                    co['diag'] = b['diag']
                latest_end = new_end
        if co is None:
            done += 1
            continue
        # estimates: once a day, and every run around the results date
        nd = st.get('next')
        hot = (nd and -1 <= days(tny, nd) <= 3) or waiting
        if st.get('est_day') != today or hot:
            update_estimates(t, st, latest_end)
            time.sleep(0.3)
        co['name'] = info['name']
        co['mcap'] = info.get('mcap')
        co['next'] = st.get('next')
        co['last_report'] = st.get('last_report')
        co['est'] = estimate_for(st, latest_end)
        newer = [h for h in st.get('eps_hist') or [] if latest_end and h['q'] > latest_end and days(latest_end, h['q']) >= 60
                 and h.get('act') is not None]
        co['pending'] = ({'q': newer[-1]['q'], 'eps_act': newer[-1]['act'], 'eps_est': newer[-1]['est']} if newer else None)
        write_if_changed(path, co)
        done += 1
    # companies that left the list keep their file for 30 days, then go
    for f in os.listdir(CO_DIR):
        t = f[:-5]
        if t not in cos:
            st = sts.get(t) or {}
            gone = st.setdefault('gone', today)
            if days(gone, today) > 30:
                os.remove(f'{CO_DIR}/{f}')
                sts.pop(t, None)
        elif (sts.get(t) or {}).get('gone'):
            sts[t].pop('gone', None)
    state['new'] = [e for e in events if days(e['found_hkt'][:10], today) <= 7]
    state['run_hkt'] = stamp
    write_json(STATE, state, indent=1)
    write_json(UNIVERSE, uni, indent=1)
    have = sum(1 for f in os.listdir(CO_DIR) if f.endswith('.json'))
    notice(f'財報數據：名單 {len(cos)} 間，有財報 {have} 間，今次讀 SEC {fetched} 次，新財報 {len([e for e in events if e["found_hkt"] == stamp])} 份')


if __name__ == '__main__':
    main()
