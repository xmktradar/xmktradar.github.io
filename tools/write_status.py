"""Write two small files SuperGrok reads:

- data/writeup-input.json: the consensus numbers the page computed (daily, weekly,
  monthly), so SuperGrok's write-ups use the same numbers as the page, plus a few
  reasons and post links per ticker for quoting.
- data/site-status.json: when the site last updated, how many posts wait for a
  summary, warnings, and the newest write-up dates. The daily check reads this.

It also removes summaries the site has already used: data/grok-inbox/ batch files are
deleted once used, and data/super-grok-analysis.json is reset if it holds used or broken
content. The GitHub connector SuperGrok uses can't read or write large files.
"""
import os

from analyse_posts import INBOX, clean, inbox_files, inbox_posts
from sitedata import load, now_hk, read_json, work, write_json

GROUP_CAP = {'bull': 12, 'bear': 8, 'split': 8}  # tickers kept per side, strongest first
ROWS_PER_GROUP = 3
WHY_CHARS = 100


def latest(lst):
    return max((x.get('date', '') for x in lst if isinstance(x, dict)), default=None)


def slim(period):
    """Keep every number; keep only the strongest tickers and a few reasons each."""
    out = dict(period)
    for side, cap in GROUP_CAP.items():
        groups = period.get(side) or []
        out[side] = [{**g, 'rows': [{**r, 'why': (r.get('why') or '')[:WHY_CHARS]}
                                    for r in (g.get('rows') or [])[:ROWS_PER_GROUP]]}
                     for g in groups[:cap]]
        out[side + '_total'] = len(groups)
    return out


def prune_inbox():
    """Keep only well-formed summaries for posts still waiting; the rest are on the site already."""
    waiting = {str(p.get('id')) for p in read_json('data/pending-posts.json', {'posts': []})['posts']}
    raw = read_json(INBOX, None)
    posts = inbox_posts(raw)
    keep = {k: v for k, v in posts.items() if k in waiting and clean(v)}
    if not isinstance(raw, dict) or not isinstance(raw.get('posts'), dict) or len(keep) != len(posts):
        write_json(INBOX, {'updated_hkt': (raw or {}).get('updated_hkt') if isinstance(raw, dict) else None,
                           'posts': keep}, indent=1)
    for f in inbox_files():
        posts = inbox_posts(read_json(f, None))
        keep = {k: v for k, v in posts.items() if k in waiting and clean(v)}
        if not keep:
            os.remove(f)
        elif len(keep) != len(posts):
            write_json(f, {'posts': keep}, indent=1)


def main():
    d = load()
    st = read_json(work('stats.json'), {}) or {}
    mg = read_json(work('merge.json'), {}) or {}
    wr = read_json(work('writeups.json'), {}) or {}
    gen = d['meta'].get('generated_hkt')
    keep = ('from', 'to', 'posts', 'accounts', 'originals', 'reposts', 'bull_views', 'bear_views',
            'clear_accounts', 'bull', 'bear', 'split', 'top')
    write_json('data/writeup-input.json', {
        'note': 'Numbers computed by the page. SuperGrok write-ups must use these numbers. '
                'bull/bear/split list the strongest tickers (count in *_total) with up to 3 reasons and post links each.',
        'generated_hkt': gen, 'today': st.get('today'),
        **{p: slim({k: v for k, v in (st.get(p) or {}).items() if k in keep}) for p in ('daily', 'weekly', 'monthly')},
    })
    dates = {}
    for sfx, lang in (('', 'zh'), ('_en', 'en'), ('_ko', 'ko')):
        s = d.get('summaries' + sfx, {})
        dates[lang] = {p: latest(s.get(p, [])) for p in ('daily', 'weekly', 'monthly')}
        dates[lang]['highlights'] = max(d.get('highlights' + sfx, {}) or [''], default='') or None
        dates[lang]['briefing'] = latest(d.get('briefings' + sfx, []))
    write_json('data/site-status.json', {
        'note': 'Written by GitHub Actions on every update. SuperGrok daily check reads this.',
        'checked_hkt': now_hk().strftime('%Y-%m-%d %H:%M'),
        'generated_hkt': gen, 'cutoff_hkt': d['meta'].get('cutoff_hkt'),
        'posts_on_site': len(d.get('posts', [])),
        'added_this_run': mg.get('added'), 'waiting_for_summary': mg.get('pending'),
        'pruned_this_run': mg.get('pruned'), 'fetch_failed': mg.get('failed') or [],
        'warnings': d['meta'].get('warnings') or [],
        'writeups_applied': wr.get('applied') or [], 'writeups_rejected': wr.get('rejected') or [],
        'latest_writeups': dates,
    }, indent=1)
    prune_inbox()


if __name__ == '__main__':
    main()
