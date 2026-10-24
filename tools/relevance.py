"""Which waiting posts are worth a Grok summary: stocks or macro only (Tim, 2026-10-13).

Chit-chat (no $ticker, no known company name, no macro words) is not sent to Grok and not shown on the site.
No AI here: cashtags, company names from the site's price data plus a few aliases, and a macro word list.
"""
import re

ALIASES = ['Nvidia', 'Tesla', 'SpaceX', 'Google', 'Meta', 'Facebook', 'Microsoft', 'Netflix', 'Micron', 'Palantir',
           'Berkshire', 'TSMC', 'Samsung', 'SK hynix', 'Hynix', 'Oracle', 'Salesforce', 'Qualcomm', 'Coinbase',
           'MicroStrategy', 'Bitcoin', 'Ethereum', 'Uber', 'Boeing', 'Walmart', 'JPMorgan', 'Goldman', 'Nike',
           'Starbucks', 'Disney', 'Shopify', 'Snowflake', 'Supermicro', 'Super Micro', 'Arm Holdings', 'xAI']

MACRO = r'''fed|fomc|powell|rate cuts?|rate hikes?|interest rates?|inflation|cpi|ppi|pce|payrolls?|nfp|jobs report|
unemployment|jobless|gdp|recession|treasury|treasuries|yields?|bonds?|10-year|2-year|dxy|dollar|yen|yuan|euro|
oil|crude|opec|brent|wti|natural gas|tariffs?|stimulus|deficit|debt ceiling|liquidity|qe|qt|central bank|ecb|boj|
pboc|s&p|s&p 500|nasdaq|dow|spx|ndx|russell|vix|earnings|ipo|etf|bull market|bear market|
sell-?off|bitcoin|btc|crypto|
short squeeze|price target|upgrade|downgrade|guidance|buyback|dividend|power prices|carry trade'''

SUFFIX = re.compile(r',?\s*\b(inc|corp|corporation|company|co|holdings?|ltd|limited|plc|n\.v|ag|s\.a|group|'
                    r'enterprises|the)\b\.?', re.I)
STOP = {'ALL', 'NOW', 'ON', 'IT', 'ARE', 'FOR', 'ONE', 'BIG', 'CAN', 'OUT', 'NEW', 'TWO', 'ANY', 'WAY', 'KEY',
        'BEST', 'REAL', 'LOVE', 'PLAY', 'TEAM', 'LIFE', 'HAS', 'SEE', 'GO', 'BE', 'ES', 'AI', 'CEO', 'USA', 'GDP',
        'CPI', 'ETF', 'IPO', 'THE', 'AND', 'NOT', 'YOU', 'OPEN', 'FAST', 'MORE', 'WELL', 'GOOD', 'TRUE', 'CASH'}


def build(prices):
    """One regex from the site's known tickers and company names."""
    names = set(ALIASES)
    for v in prices.values():
        n = SUFFIX.sub('', (v.get('name') or '').replace('.com', '')).strip(' ,.')
        if len(n) >= 4:
            names.add(n)
    tickers = {t for t in prices if len(t) >= 3 and t.isalpha() and t.upper() not in STOP}
    words = '|'.join(re.escape(w) for w in sorted(names, key=len, reverse=True))
    rx = r'\b(' + words + r'|' + MACRO.replace('\n', '') + r')\b'
    return (re.compile(rx, re.I), re.compile(r'\b(' + '|'.join(sorted(tickers)) + r')\b') if tickers else None,
            re.compile(r'\b(' + words + r')\b', re.I))


def relevant(x, rx):
    """True when the post (or the post it quotes) has a $ticker, a known company or ticker, or macro words."""
    words, tick, _ = rx
    text = (x.get('text') or '') + '\n' + ((x.get('quoted') or {}).get('text') or '')
    if x.get('cashtags') or re.search(r'\$[A-Za-z]{1,6}\b', text):
        return True
    return bool(words.search(text) or (tick and tick.search(text)))


def tier(x, rx):
    """Queue order for Grok (Tim, 2026-10-24): 0 = $ticker, 1 = names a company or bare ticker, 2 = macro words only."""
    _, tick, company = rx
    text = (x.get('text') or '') + '\n' + ((x.get('quoted') or {}).get('text') or '')
    if x.get('cashtags') or re.search(r'\$[A-Za-z]{1,6}\b', text):
        return 0
    return 1 if company.search(text) or (tick and tick.search(text)) else 2
