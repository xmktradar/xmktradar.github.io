"""Bull/bear account counts in stats.json (used by the carousel pictures and the Reels VS scene) must match the site.

The site counts each account once, by its latest view on the stock in the window (consGroups). For every stock in
top[] that also appears in a consensus group, bull_accounts/bear_accounts must equal the group's nb/nr, and no
account may be counted on both sides. Usage: python3 tools/test_vs_counts.py <stats.json>
"""
import json, sys


def check(r):
    bad, n = [], 0
    for k in ('daily', 'weekly', 'monthly'):
        d = r.get(k) or {}
        site = {g['t']: (g['nb'], g['nr']) for side in ('bull', 'bear', 'split') for g in d.get(side) or []}
        for x in d.get('top') or []:
            got = (x.get('bull_accounts', 0), x.get('bear_accounts', 0))
            if got[0] + got[1] > x['accounts']:
                bad.append(f'{k} {x["t"]}: {got[0]} vs {got[1]} counts more than {x["accounts"]} accounts')
            if x['t'] in site:
                n += 1
                if got != site[x['t']]:
                    bad.append(f'{k} {x["t"]}: {got[0]} vs {got[1]}, site shows {site[x["t"]][0]} vs {site[x["t"]][1]}')
    return bad, n


if __name__ == '__main__':
    bad, n = check(json.load(open(sys.argv[1], encoding='utf-8')))
    for b in bad:
        print('MISMATCH', b)
    print(f'{n} stocks compared with the site, {len(bad)} mismatches')
    sys.exit(1 if bad or not n else 0)
