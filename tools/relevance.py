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
pboc|s&p|s&p 500|nasdaq|dow|spx|ndx|russell|vix|stocks?|equities|earnings|ipo|etf|bull market|bear market|
sell-?off|rally|valuation|economy|economic|housing|mortgage|gold|silver|copper|bitcoin|btc|crypto|markets?|
breadth|semis|semiconductors?|chips?|miners|debt|capex|data cent(?:er|re)s?|hyperscalers?|openai|anthropic|
short squeeze|options?|calls|puts|price target|upgrade|downgrade|guidance|revenue|margins?|buyback|dividend|energy|electricity|power prices|carry trade'''

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
    words = sorted(names, key=len, reverse=True)
    rx = r'\b(' + '|'.join(re.escape(w) for w in words) + r'|' + MACRO.replace('\n', '') + r')\b'
    return re.compile(rx, re.I), re.compile(r'\b(' + '|'.join(sorted(tickers)) + r')\b') if tickers else None


def relevant(x, rx):
    """True when the post (or the post it quotes) has a $ticker, a known company or ticker, or macro words."""
    words, tick = rx
    text = (x.get('text') or '') + '\n' + ((x.get('quoted') or {}).get('text') or '')
    if x.get('cashtags') or re.search(r'\$[A-Za-z]{1,6}\b', text):
        return True
    if x.get('type') != 'reply' and (x.get('n_media') or x.get('media')):
        return True  # an own post or repost with a picture is often a chart; let Grok look
    return bool(words.search(text) or (tick and tick.search(text)))
