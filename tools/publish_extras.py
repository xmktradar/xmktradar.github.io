"""Step 8: consensus history, share image text, meta tags and sitemap, from work/stats.json.

Writes work/og.json (share image text) only when the day's consensus changed, so the
image is re-rendered only then.
"""
import json
import re
import sys

from sitedata import load, notice, read_json, save, work, write_json

HTML = 'index.html'


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
    ch['days'][day] = {'bull': bull, 'bear': bear, 'split': split, 'window': [s['from'], s['to']], 'src': 'live', 'updated_hkt': gen}
    ch['updated_hkt'] = gen
    write_json('data/consensus-history.json', ch, indent=1)

    nb = lambda g: g['nb']
    nr = lambda g: g['nr']
    both = lambda g: g['nb'] + g['nr']
    picks = (lst(s['bull'], nb, 3) + ('等' if len(s['bull']) > 3 else '')) if s['bull'] else '暫時未有'
    params = {'date': day, 'picks': picks, 'n': f"今日 {s['accounts']} 個帳戶有出帖",
              'bear': '共同睇淡：' + (lst(s['bear'], nr, 2) or '冇'), 'split': '分歧：' + (lst(s['split'], both, 2) or '冇')}
    alt = f"今日 X 大神共同睇好：{picks}｜{params['n']}｜{params['bear']}｜分歧：{lst(s['split'], both, 3) or '冇'}"

    h = open(HTML, encoding='utf-8').read()
    cur = re.search(r'<meta property="og:image:alt" content="([^"]*)"', h)
    cur_img = re.search(r'https://xmktradar\.github\.io/og/(\d{4}-\d{2}-\d{2})\.png\?v=([\w-]+)', h)
    changed = not cur or cur.group(1) != alt or not cur_img or cur_img.group(1) != day
    bid = d['meta']['build_id'].replace('build-', '')
    h = re.sub(r'<meta name="generator" content="market-consensus build-[^"]+">', f'<meta name="generator" content="market-consensus build-{bid}">', h)
    if changed:
        h = re.sub(r'(https://xmktradar\.github\.io/og/)\d{4}-\d{2}-\d{2}\.png\?v=[\w-]+', rf'\g<1>{day}.png?v={bid}', h)
        h = re.sub(r'(<meta (?:property="og:image:alt"|name="twitter:image:alt") content=")[^"]*(")', lambda m: m.group(1) + alt + m.group(2), h)
        write_json(work('og.json'), params)
    open(HTML, 'w', encoding='utf-8').write(h)

    sm = open('sitemap.xml', encoding='utf-8').read()
    sm = re.sub(r'(<loc>https://xmktradar\.github\.io/</loc><lastmod>)[^<]+', rf"\g<1>{gen.replace(' ', 'T')}:00+08:00", sm)
    open('sitemap.xml', 'w', encoding='utf-8').write(sm)
    notice(f"共識 {day}（{s['from']} 至 {s['to']}）：睇好 {'、'.join(bull) or '冇'}｜睇淡 {'、'.join(bear) or '冇'}｜分歧 {'、'.join(split) or '冇'}"
           + ('｜分享圖要重畫' if changed else ''))


if __name__ == '__main__':
    main()
