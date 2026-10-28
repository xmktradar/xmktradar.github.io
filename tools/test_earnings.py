"""Tests for the earnings briefs (tools/earnings_data.py, earnings_pages.py, earnings_posts.py). Run: python3 tools/test_earnings.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import earnings_data as ed  # noqa: E402


def fact(start, end, val, fy, fp, form='10-Q', filed=None, accn='a'):
    e = {'end': end, 'val': val, 'fy': fy, 'fp': fp, 'form': form, 'filed': filed or end, 'accn': accn}
    if start:
        e['start'] = start
    return e


def facts_fixture():
    # FY = calendar year. Q1-Q3 3-month revenue in 10-Q, Q4 only as the full year in the 10-K.
    rev = [
        fact('2025-01-01', '2025-03-31', 100, 2025, 'Q1', filed='2025-04-30', accn='q1'),
        fact('2025-04-01', '2025-06-30', 110, 2025, 'Q2', filed='2025-07-30', accn='q2'),
        fact('2025-01-01', '2025-06-30', 210, 2025, 'Q2', filed='2025-07-30', accn='q2'),
        fact('2025-07-01', '2025-09-30', 120, 2025, 'Q3', filed='2025-10-30', accn='q3'),
        fact('2025-01-01', '2025-09-30', 330, 2025, 'Q3', filed='2025-10-30', accn='q3'),
        fact('2025-01-01', '2025-12-31', 460, 2025, 'FY', form='10-K', filed='2026-02-10', accn='k'),
    ]
    fee = [fact('2025-07-01', '2025-09-30', 30, 2025, 'Q3', filed='2025-10-30', accn='q3')]  # part of revenue only
    ocf = [  # year to date only, as in a real 10-Q
        fact('2025-01-01', '2025-03-31', 20, 2025, 'Q1', filed='2025-04-30', accn='q1'),
        fact('2025-01-01', '2025-06-30', 50, 2025, 'Q2', filed='2025-07-30', accn='q2'),
        fact('2025-01-01', '2025-09-30', 90, 2025, 'Q3', filed='2025-10-30', accn='q3'),
        fact('2025-01-01', '2025-12-31', 140, 2025, 'FY', form='10-K', filed='2026-02-10', accn='k'),
    ]
    capex = [fact('2025-01-01', '2025-09-30', 30, 2025, 'Q3', filed='2025-10-30', accn='q3'),
             fact('2025-01-01', '2025-12-31', 45, 2025, 'FY', form='10-K', filed='2026-02-10', accn='k')]
    cash = [fact(None, '2025-12-31', 500, 2025, 'FY', form='10-K', filed='2026-02-10', accn='k')]
    debt = [fact(None, '2025-12-31', 200, 2025, 'FY', form='10-K', filed='2026-02-10', accn='k')]
    eps = [fact('2025-07-01', '2025-09-30', 1.2, 2025, 'Q3', filed='2025-10-30', accn='q3')]
    u = lambda es: {'units': {'USD': es}}  # noqa: E731
    return {'facts': {'us-gaap': {
        'Revenues': u(rev), 'RevenueFromContractWithCustomerExcludingAssessedTax': u(fee),
        'NetCashProvidedByUsedInOperatingActivities': u(ocf), 'PaymentsToAcquirePropertyPlantAndEquipment': u(capex),
        'CashAndCashEquivalentsAtCarryingValue': u(cash), 'LongTermDebt': u(debt),
        'EarningsPerShareDiluted': {'units': {'USD/shares': eps}},
    }}}


def test_quarters():
    b = ed.build_quarters(facts_fixture())
    q = {x['end']: x for x in b['q']}
    assert q['2025-12-31']['rev'] == 130, q['2025-12-31']  # Q4 = year - 9 months
    assert q['2025-09-30']['rev'] == 120  # the fee-only concept never wins over total revenue
    assert q['2025-06-30']['ocf'] == 30 and q['2025-12-31']['ocf'] == 50  # YTD differences
    assert q['2025-12-31']['capex'] == 15 and q['2025-12-31']['fcf'] == 35
    assert q['2025-09-30']['eps'] == 1.2
    assert b['latest']['end'] == '2025-12-31' and b['latest']['label'] == 'FY2025 Q4' and b['latest']['accn'] == 'k'
    assert q['2025-09-30']['label'] == 'FY2025 Q3'
    assert b['bal'] == {'end': '2025-12-31', 'cash': 500, 'sti': None, 'debt': 200}


def test_bank_revenue():
    f = facts_fixture()
    f['facts']['us-gaap']['RevenuesNetOfInterestExpense'] = {'units': {'USD': [
        fact('2025-07-01', '2025-09-30', 90, 2025, 'Q3', filed='2025-10-30', accn='q3')]}}
    b = ed.build_quarters(f)
    q = {x['end']: x for x in b['q']}
    assert q['2025-09-30']['rev'] == 90 and b['bank']


def test_reconcile():
    # Apple style: Products is the sum of iPhone + Mac, so it is dropped
    m, other = ed.reconcile({'iPhone': 50, 'Mac': 10, 'Products': 60, 'Services': 30}, 90)
    assert set(m) == {'iPhone', 'Mac', 'Services'} and not other
    m, other = ed.reconcile({'A': 60, 'B': 25}, 100)
    assert other
    assert ed.reconcile({'A': 10, 'B': 10}, 100) is None
    assert ed.reconcile({'A': -5, 'B': 105}, 100) is None


INSTANCE = b'''<?xml version="1.0"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
 xmlns:us-gaap="http://fasb.org/us-gaap/2025" xmlns:srt="http://fasb.org/srt/2025" xmlns:abc="http://abc.com/2025">
<xbrli:context id="c1"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier></xbrli:entity>
 <xbrli:period><xbrli:startDate>2025-07-01</xbrli:startDate><xbrli:endDate>2025-09-30</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:context id="c2"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier><xbrli:segment>
 <xbrldi:explicitMember dimension="srt:ProductOrServiceAxis">abc:ChipsMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity>
 <xbrli:period><xbrli:startDate>2025-07-01</xbrli:startDate><xbrli:endDate>2025-09-30</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:context id="c3"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier><xbrli:segment>
 <xbrldi:explicitMember dimension="srt:ProductOrServiceAxis">abc:SoftwareSegmentMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity>
 <xbrli:period><xbrli:startDate>2025-07-01</xbrli:startDate><xbrli:endDate>2025-09-30</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:context id="c4"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier><xbrli:segment>
 <xbrldi:explicitMember dimension="srt:ProductOrServiceAxis">abc:ChipsMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity>
 <xbrli:period><xbrli:startDate>2024-07-01</xbrli:startDate><xbrli:endDate>2024-09-30</xbrli:endDate></xbrli:period></xbrli:context>
<us-gaap:Revenues contextRef="c1" unitRef="usd" decimals="-6">120</us-gaap:Revenues>
<us-gaap:Revenues contextRef="c2" unitRef="usd" decimals="-6">80</us-gaap:Revenues>
<us-gaap:Revenues contextRef="c3" unitRef="usd" decimals="-6">40</us-gaap:Revenues>
<us-gaap:Revenues contextRef="c4" unitRef="usd" decimals="-6">50</us-gaap:Revenues>
</xbrli:xbrl>'''

LABELS = b'''<?xml version="1.0"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink">
<link:labelLink xlink:type="extended" xlink:role="http://www.xbrl.org/2003/role/link">
<link:loc xlink:type="locator" xlink:href="abc-20250930.xsd#abc_ChipsMember" xlink:label="loc_1"/>
<link:label xlink:type="resource" xlink:label="lab_1" xlink:role="http://www.xbrl.org/2003/role/label">Chips &amp; Boards [Member]</link:label>
<link:labelArc xlink:type="arc" xlink:from="loc_1" xlink:to="lab_1"/>
</link:labelLink></link:linkbase>'''


def test_segments():
    ctx, facts = ed.parse_instance(INSTANCE)
    seg = ed.segments(ctx, facts, '2025-09-30', 120, None)
    assert seg['members'] == {'abc:ChipsMember': 80, 'abc:SoftwareSegmentMember': 40}, seg
    assert seg['prev'] == {'abc:ChipsMember': 50}
    labels = ed.parse_labels(LABELS)
    assert ed.member_name('abc:ChipsMember', labels) == 'Chips & Boards'
    assert ed.member_name('abc:SoftwareSegmentMember', labels) == 'Software'


def test_estimates():
    st = {'eps_hist': [{'q': '2025-09-30', 'act': 1.3, 'est': 1.1}], 'rev_est': {'2025-09-28': {'rev': 118, 'seen': '2025-10-20'}}}
    e = ed.estimate_for(st, '2025-09-30')
    assert e['eps_act'] == 1.3 and e['eps_est'] == 1.1 and e['rev_est'] == 118


def fixture_co(bank=False, seg=True):
    ends = ['2024-07-28', '2024-10-27', '2025-01-26', '2025-04-27', '2025-07-27', '2025-10-26', '2026-01-25', '2026-04-26', '2026-07-26']
    q = []
    for i, e in enumerate(ends):
        r = (30 + 6 * i) * 1e9
        q.append({'end': e, 'label': f'FY{2025 + (i + 1) // 4} Q{(i + 1) % 4 + 1}', 'rev': r, 'gp': None if bank else r * .7, 'op': r * .6,
                  'ni': r * .5, 'eps': 1 + i / 10, 'ocf': r * .5, 'capex': r * .05, 'fcf': r * .45})
    return {'t': 'ABCD', 'name': 'Abcd Corp', 'cik': 1, 'q': q, 'latest': {'end': ends[-1], 'label': q[-1]['label'], 'filed': '2026-08-27', 'accn': 'x'},
            'bal': {'end': ends[-1], 'cash': 1e10, 'sti': 2e10, 'debt': 5e9}, 'bank': bank, 'mcap': 6e11, 'next': '2026-11-19',
            'seg': {'basis': 'quarter', 'rows': [{'name': 'Chips', 'val': 60e9, 'prev': 40e9}, {'name': 'Software', 'val': 18e9, 'prev': 15e9}]} if seg else {'none': True},
            'est': {'eps_act': 1.9, 'eps_est': 1.8, 'rev_est': 77e9, 'rev_est_seen': '2026-08-20'}, 'pending': None}


def test_pages_and_posts():
    import re
    import earnings_pages as ep
    import earnings_posts as eo
    from share import xlen
    for bank, seg in ((False, True), (True, False)):
        co = fixture_co(bank, seg)
        for lang in ('zh', 'en'):
            page = ep.brief_page(co, lang, '2026-10-27 20:00', False)
            assert '<h1>' in page and 'ABCD' in page
            if lang == 'en':
                body = re.sub(r'<nav class="lang".*?</nav>', '', page, flags=re.S)
                assert not re.search(r'[\u4e00-\u9fff]', body), re.findall(r'[\u4e00-\u9fff]+', body)[:5]
            caps = eo.captions(co, lang)
            assert xlen(caps['x']) <= 270, caps['x']
            assert len(caps['threads']) <= 500
            assert 'https://' not in caps['instagram']
            assert len(eo.slides(co, lang)) == 4
            lines = eo.video_lines(co, lang)
            assert len(lines) == 5 and all(lines)
        assert ep.list_page([co], 'en', 'x')
    # X-account views: a 5th picture and a caption line linking the stock page (2026-10-28)
    eo._VIEWS['m'] = {'split': [{'t': 'ABCD', 'nb': 3, 'nr': 1, 'rows': [
        {'acc': 'a1', 's': 'bull', 'ms': 3}, {'acc': 'a2', 's': 'bear', 'ms': 2}, {'acc': 'a3', 's': 'bull', 'ms': 1},
        {'acc': 'a4', 's': 'bull', 'ms': 4}, {'acc': 'a5', 's': 'neu', 'ms': 5}]}]}
    real = eo.stock_url
    eo.stock_url = lambda lang, t: f'{eo.SITE}{lang}/stock/{t}/'
    try:
        co = fixture_co(False, True)
        for lang in ('zh', 'en'):
            ss = eo.slides(co, lang)
            assert len(ss) == 5 and ss[4]['kind'] == 'views' and ss[4]['nb'] == 3 and ss[4]['neu'] == 1 and all(x['of'] == 5 for x in ss)
            assert [a['acc'] for a in ss[4]['accs']] == ['a4', 'a1', 'a2', 'a3']
            caps = eo.captions(co, lang)
            for k in ('x', 'threads', 'facebook'):
                assert f'{lang}/stock/ABCD/' in caps[k], (k, caps[k])
            assert xlen(caps['x']) <= 270 and len(caps['threads']) <= 500
            assert ('5 張' if lang == 'zh' else 'all 5') in caps['facebook']
        eo._VIEWS['m'] = {}
        assert len(eo.slides(co, 'zh')) == 4 and '/zh/stock/ABCD/' in eo.captions(co, 'zh')['facebook']
    finally:
        eo.stock_url = real
        eo._VIEWS.clear()
    assert ep.fmt_zh(81.2e9) == 'US$812 億' and ep.fmt_en(81.2e9) == '$81.20B' and ep.fmt_en(-2e9) == '-$2.00B'


INSTANCE_Q = b"""<?xml version="1.0"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:us-gaap="http://fasb.org/us-gaap/2025" xmlns:dei="http://xbrl.sec.gov/dei/2025"
 xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:iso4217="http://www.xbrl.org/2003/iso4217">
<xbrli:context id="q"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2026-01-01</xbrli:startDate><xbrli:endDate>2026-03-31</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:context id="seg"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier><xbrli:segment><xbrldi:explicitMember dimension="srt:ProductOrServiceAxis">x:A</xbrldi:explicitMember></xbrli:segment></xbrli:entity><xbrli:period><xbrli:startDate>2026-01-01</xbrli:startDate><xbrli:endDate>2026-03-31</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:context id="i"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2026-03-31</xbrli:instant></xbrli:period></xbrli:context>
<xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
<xbrli:unit id="ps"><xbrli:divide><xbrli:unitNumerator><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unitNumerator><xbrli:unitDenominator><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unitDenominator></xbrli:divide></xbrli:unit>
<dei:DocumentFiscalYearFocus contextRef="q">2026</dei:DocumentFiscalYearFocus><dei:DocumentFiscalPeriodFocus contextRef="q">Q1</dei:DocumentFiscalPeriodFocus>
<us-gaap:Revenues contextRef="q" unitRef="usd" decimals="-6">150000000</us-gaap:Revenues>
<us-gaap:Revenues contextRef="seg" unitRef="usd" decimals="-6">90000000</us-gaap:Revenues>
<us-gaap:EarningsPerShareDiluted contextRef="q" unitRef="ps" decimals="2">1.35</us-gaap:EarningsPerShareDiluted>
<us-gaap:CashAndCashEquivalentsAtCarryingValue contextRef="i" unitRef="usd" decimals="-6">700000000</us-gaap:CashAndCashEquivalentsAtCarryingValue>
</xbrli:xbrl>"""


def test_supplement():
    """companyfacts stops at FY2025; the newer 10-Q is read from its own XBRL instance."""
    calls = []

    def fake_json(url):
        calls.append(url)
        if 'submissions' in url:
            return {'filings': {'recent': {'form': ['10-Q', '8-K', '10-Q'], 'accessionNumber': ['0000-26-1', '0000-26-2', '0000-25-9'],
                                           'filingDate': ['2026-04-30', '2026-04-29', '2025-10-30'],
                                           'reportDate': ['2026-03-31', '2026-04-29', '2025-09-30']}}}
        return {'directory': {'item': [{'name': 'x-20260331_htm.xml'}, {'name': 'x-20260331_lab.xml'}]}}

    old = ed.sec_json, ed.sec
    ed.sec_json, ed.sec = fake_json, lambda url: INSTANCE_Q
    try:
        f = facts_fixture()
        assert ed.supplement(f, 1, '2025-12-31') == 1
    finally:
        ed.sec_json, ed.sec = old
    assert [c for c in calls if 'index.json' in c] == ['https://www.sec.gov/Archives/edgar/data/1/0000261/index.json'], calls  # only the 10-Q after 2025-12-31
    b = ed.build_quarters(f)
    last = b['q'][-1]
    assert last['end'] == '2026-03-31' and last['rev'] == 150000000 and last['eps'] == 1.35, last  # the segment fact is ignored
    assert b['latest']['label'] == 'FY2026 Q1' and b['latest']['accn'] == '0000-26-1' and b['latest']['filed'] == '2026-04-30'
    assert b['bal']['cash'] == 700000000


def test_16_week_quarters():
    """AZO / COST: a 16-week quarter (112 days) is still a quarter, and Q4 = year - 36 weeks."""
    rev = [fact('2025-08-31', '2025-11-22', 100, 2026, 'Q1', filed='2025-12-10'),
           fact('2025-08-31', '2026-05-09', 400, 2026, 'Q3', filed='2026-05-30'),
           fact('2026-02-15', '2026-05-09', 110, 2026, 'Q3', filed='2026-05-30'),
           fact('2025-08-31', '2026-08-29', 560, 2026, 'FY', form='10-K', filed='2026-10-26')]
    b = ed.build_quarters({'facts': {'us-gaap': {'Revenues': {'units': {'USD': rev}}}}})
    q = {x['end']: x['rev'] for x in b['q']}
    assert q.get('2026-08-29') == 160 and b['latest']['label'] == 'FY2026 Q4', q


def test_bank_net_revenue_from_parts():
    """BNY: no total revenue tag in the 10-Q, so fee income + net interest income."""
    u = lambda es: {'units': {'USD': es}}  # noqa: E731
    f = {'facts': {'us-gaap': {
        'Revenues': u([fact('2025-01-01', '2025-12-31', 1000, 2025, 'FY', form='10-K', filed='2026-02-25')]),
        'NoninterestIncome': u([fact('2026-04-01', '2026-06-30', 3800, 2026, 'Q2', filed='2026-07-31')]),
        'InterestIncomeExpenseNet': u([fact('2026-04-01', '2026-06-30', 1200, 2026, 'Q2', filed='2026-07-31')]),
    }}}
    rev, bank = ed.revenue(f)
    assert rev['2026-06-30'] == 5000 and bank


def test_labels_without_fiscal_period():
    """XOM: quarters companyfacts gives without fy/fp get their label from the fiscal year end; a comparative figure
    filed a year later keeps its own year."""
    def lab(es):
        return {k: v['label'] for k, v in ed.periods({'facts': {'us-gaap': {'Revenues': {'units': {'USD': es}}}}}).items()}
    got = lab([fact('2025-01-01', '2025-12-31', 1, 2025, 'FY', form='10-K', filed='2026-02-20'),
               fact('2026-01-01', '2026-04-03', 1, None, None), fact('2025-07-01', '2025-10-03', 1, None, None),
               fact('2025-04-01', '2025-06-30', 1, 2026, 'Q2', filed='2026-08-03')])
    assert got == {'2025-12-31': 'FY2025 Q4', '2026-04-03': 'FY2026 Q1', '2025-10-03': 'FY2025 Q3', '2025-06-30': 'FY2025 Q2'}, got
    got = lab([fact('2025-02-02', '2026-01-31', 1, 2026, 'FY', form='10-K', filed='2026-03-20'),
               fact('2026-02-01', '2026-05-02', 1, None, None)])  # NVDA-style year ending in January
    assert got['2026-05-02'] == 'FY2027 Q1', got


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print('ok', name)
