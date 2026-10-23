"""Fill data/sectors.json with Yahoo Finance sector/industry (or ETF category) for every stock page ticker.
Only tickers not yet in the file are looked up; failures are skipped (no guessing). Needs: pip install yfinance."""
import json, os, sys
try:
    import yfinance as yf
except ImportError:
    sys.exit('sectors: yfinance not installed, skipped')
F = 'data/sectors.json'
d = json.load(open(F)) if os.path.exists(F) else {}
tks = sorted(os.listdir('zh/stock'))
for t in tks:
    if t in d:
        continue
    o = json.load(open('data/dash/overrides.json')).get(t, {}) if os.path.exists('data/dash/overrides.json') else {}
    try:
        i = yf.Ticker(t).info or {}
    except Exception:
        continue
    s = i.get('sector') or (('ETF: ' + i['category']) if i.get('quoteType') == 'ETF' and i.get('category') else None)
    if s:
        d[t] = {'sector': s, 'industry': i.get('industry') or i.get('category') or ''}
json.dump(d, open(F, 'w'), indent=0, sort_keys=True, ensure_ascii=False)
print(f'sectors: {len(d)}/{len(tks)} tickers have a sector')
