"""Write two small files SuperGrok reads (rules: automation/super-grok.md):

- data/writeup-input.json: the consensus numbers the page computed (daily, weekly,
  monthly), so SuperGrok's write-ups use the same numbers as the page.
- data/site-status.json: when the site last updated, how many posts wait for a
  summary, warnings, and the newest write-up dates. The daily check reads this.
"""
from sitedata import load, now_hk, read_json, work, write_json


def latest(lst):
    return max((x.get('date', '') for x in lst if isinstance(x, dict)), default=None)


def main():
    d = load()
    st = read_json(work('stats.json'), {}) or {}
    mg = read_json(work('merge.json'), {}) or {}
    wr = read_json(work('writeups.json'), {}) or {}
    gen = d['meta'].get('generated_hkt')
    keep = ('from', 'to', 'posts', 'accounts', 'originals', 'reposts', 'bull_views', 'bear_views',
            'clear_accounts', 'bull', 'bear', 'split', 'top')
    write_json('data/writeup-input.json', {
        'note': 'Numbers computed by the page. SuperGrok write-ups must use these numbers.',
        'generated_hkt': gen, 'today': st.get('today'),
        **{p: {k: v for k, v in (st.get(p) or {}).items() if k in keep} for p in ('daily', 'weekly', 'monthly')},
    }, indent=1)
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


if __name__ == '__main__':
    main()
