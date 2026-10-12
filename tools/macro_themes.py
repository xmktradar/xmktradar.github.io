"""Keyword themes for the macro tab (Tim, 2026-10-13). No AI.

SuperGrok writes macro_theme / macro_impact for new posts. Macro posts it never judged (posts from
before the new prompt, or batches written with the old one) get macro_kw here instead: the theme
whose keywords appear most often in the original text and the summaries. These carry no stance, so
the page lists them under the theme but leaves them out of the bullish / bearish counts.
A post with no keyword gets no theme and stays off the tab (plain index talk is on the daily tab).
"""
import re

ORDER = ('rates', 'inflation', 'jobs', 'growth', 'yields', 'fx', 'energy', 'policy', 'other')
WORDS = {
    'rates': r'\bfed\b|fomc|powell|rate cuts?|rate hikes?|interest rates?|fed funds|dot plot|central bank|\becb\b|\bboj\b|'
             r'\bwaller\b|\bbowman\b|\bqt\b|balance sheet|減息|加息|降息|聯儲|聯準會|央行|利率',
    'inflation': r'inflation|\bcpi\b|\bpce\b|\bppi\b|deflation|disinflation|prices paid|通脹|通膨|物價',
    'jobs': r'payrolls?|\bnfp\b|jobless|unemployment|jobs report|labou?r market|initial claims|\bjolts\b|layoffs|非農|失業|就業',
    'growth': r'\bgdp\b|recession|\bism\b|\bpmi\b|retail sales|consumer spending|consumer confidence|soft landing|'
              r'hard landing|economic growth|the economy|slowdown|housing|home sales|home prices|mortgage|經濟增長|經濟衰退|衰退|消費者信心|零售銷售',
    'yields': r'yields?\b|treasur|10-?year|\b10y\b|2-?year|\b2y\b|\b30-?year|bonds?\b|yield curve|term premium|'
              r'auction|\btlt\b|債息|國債|美債|孳息',
    'fx': r'\bdollar\b|\bdxy\b|\busd\b|\byen\b|\beuro\b|yuan|currenc|\bforex\b|美元|匯率|日圓|日元|人民幣',
    'energy': r'\boil\b|crude|\bwti\b|brent|\bopec\b|natural gas|gasoline|油價|原油|天然氣',
    'policy': r'tariffs?|trade war|trade deal|sanctions?|\bwar\b|geopolit|\biran\b|israel|russia|ukraine|'
              r'government shutdown|\bshutdown\b|white house|congress|election|關稅|貿易戰|制裁|戰爭|地緣|停擺',
    'other': r'liquidity|deficit|national debt|debt ceiling|\bm2\b|credit spreads?|赤字|國債上限|流動性',
}
RX = {k: re.compile(v, re.I) for k, v in WORDS.items()}


def theme_of(p):
    q = p.get('quoted') if isinstance(p.get('quoted'), dict) else {}
    text = ' '.join(str(x or '') for x in (p.get('text'), q.get('text'), p.get('en_summary'), p.get('zh_summary')))
    hits = {k: len(RX[k].findall(text)) for k in ORDER}
    best = max(ORDER, key=lambda k: (hits[k], -ORDER.index(k)))
    return best if hits[best] else None


def tag_posts(posts):
    """Fill macro_kw on macro posts SuperGrok has not themed. Returns how many have a keyword theme."""
    n = 0
    for p in posts:
        p.pop('macro_kw', None)
        if not p.get('macro') or 'macro_theme' in p:
            continue
        t = theme_of(p)
        if t:
            p['macro_kw'] = t
            n += 1
    return n
