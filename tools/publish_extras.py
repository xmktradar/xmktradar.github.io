"""Step 8: consensus history, share image alt text, meta tags and sitemap, from work/stats.json.

The share pictures themselves are prepared by tools/share.py.
"""
import json
import re
import sys
import urllib.request

from sitedata import load, notice, read_json, save, work, write_json

HTML = 'index.html'
VIEWS_BASE = 397  # same base as the counter script in index.html
VIEWS_API = 'https://abacus.jasoncameron.dev/get/xmktradar/views'


def view_count():
    """Current view count, so the page shows a recent number even when a phone blocks or delays the
    counter request (it used to fall back to the bare base, 397). None when the counter can't be read."""
    try:
        with urllib.request.urlopen(VIEWS_API, timeout=10) as r:
            v = json.load(r).get('value')
        return VIEWS_BASE + v if isinstance(v, int) and v >= 0 else None
    except Exception:
        return None


def lst(groups, key, n):
    return '、'.join(f"{g['t']}（{key(g)}）" for g in groups[:n])


def main():
    st = read_json(work('stats.json'))
    mg = read_json(work('merge.json'), {})
    day, s = st['today'], st['daily']
    d = load(HTML)
    gen = d['meta']['generated_hkt']
    bull = [g['t'] for g in s['bull']]
    bear = [g['t'] for g in s['bear']]
    split = [g['t'] for g in s['split']]
    d.setdefault('cons_hist', {})[day] = {'bull': bull, 'bear': bear}
    save(d, HTML)

    ch = read_json('data/consensus-history.json', {'days': {}})
    ch['days'][day] = {'bull': bull, 'bear': bear, 'split': split, 'window': [s['from'], s['to']],
                     'top': [g['t'] for g in s['top'][:10]], 'src': 'live', 'updated_hkt': gen}
    ch['updated_hkt'] = gen
    write_json('data/consensus-history.json', ch, indent=1)

    nb = lambda g: g['nb']
    nr = lambda g: g['nr']
    both = lambda g: g['nb'] + g['nr']
    picks = (lst(s['bull'], nb, 3) + ('等' if len(s['bull']) > 3 else '')) if s['bull'] else '暫時未有'
    n = f"今日 {s['accounts']} 個帳號有發文"
    alt = f"今日 X 大神共同看好：{picks}｜{n}｜共同看淡：{lst(s['bear'], nr, 2) or '無'}｜分歧：{lst(s['split'], both, 3) or '無'}"

    h = open(HTML, encoding='utf-8').read()
    bid = d['meta']['build_id'].replace('build-', '')
    h = re.sub(r'<meta name="generator" content="market-consensus build-[^"]+">', f'<meta name="generator" content="market-consensus build-{bid}">', h)
    h = re.sub(r'(<meta (?:property="og:image:alt"|name="twitter:image:alt") content=")[^"]*(")', lambda m: m.group(1) + alt + m.group(2), h)
    views = view_count()
    if views:
        h = re.sub(r'(<b id="viewcount">)[^<]*(</b>)', lambda m: m.group(1) + f'{views:,}' + m.group(2), h, count=1)
    open(HTML, 'w', encoding='utf-8').write(h)

    sm = open('sitemap.xml', encoding='utf-8').read()
    sm = re.sub(r'(<loc>https://xmktradar\.github\.io/</loc><lastmod>)[^<]+', rf"\g<1>{gen.replace(' ', 'T')}:00+08:00", sm)
    open('sitemap.xml', 'w', encoding='utf-8').write(sm)
    notice(f"共識 {day}（{s['from']} 至 {s['to']}）：看好 {'、'.join(bull) or '無'}｜看淡 {'、'.join(bear) or '無'}｜分歧 {'、'.join(split) or '無'}")


if __name__ == '__main__':
    main()
