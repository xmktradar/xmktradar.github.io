"""Step 4: add analysed posts to the site data; keep the rest for the next run.

Updates posts, days, meta.cutoff_hkt / generated_hkt / build_id and data/pending-posts.json.
Writes work/merge.json with what changed, for the analysis step.
"""
from datetime import timezone

from sitedata import ET, HK, load, notice, now_hk, parse_iso, read_json, save, work, write_json

PENDING = 'data/pending-posts.json'


def site_post(x, a):
    t = parse_iso(x['time_utc']).astimezone(timezone.utc)
    p = {'handle': x['handle']}
    if x.get('name'):
        p['name'] = x['name']
    if x.get('reposted_by'):
        p['reposted_by'] = x['reposted_by']
    p.update(time_utc=x['time_utc'], time_hkt=t.astimezone(HK).isoformat(timespec='seconds'))
    if x.get('likes') is not None:
        p['likes'] = str(x['likes'])
    if x.get('views') is not None:
        p['views'] = str(x['views'])
    p.update(url=x['url'], truncated=False, tickers=a.get('tickers') or [],
             day=t.astimezone(HK).date().isoformat(), date_et=t.astimezone(ET).date().isoformat())
    if x.get('media'):
        p['media'] = x['media']
    if not (x.get('text') or '').strip() and x.get('media') and not x.get('quoted'):
        p['media_only'] = True
    for k in ('stance', 'horizon', 'basis'):
        if a.get(k):
            p[k] = a[k]
    if a.get('tickers'):
        p['specific'] = bool(a.get('specific'))
    for k in ('stance_by_ticker', 'ticker_notes'):
        if a.get(k):
            p[k] = a[k]
    p['zh_summary'] = a['zh_summary']
    return p


def main():
    d = load()
    new = read_json(work('new_posts.json'), {'posts': [], 'failed': [], 'accounts': 0})
    done = read_json(work('analysed.json'), {})
    have = {p['url'].lower() for p in d['posts']}
    add, keep = [], []
    for x in new['posts']:
        if x['url'].lower() in have:
            continue
        (add if x['id'] in done else keep).append(x)
    old_cutoff = d['meta']['cutoff_hkt']
    added = [site_post(x, done[x['id']]) for x in add]
    d['posts'] = sorted(d['posts'] + added, key=lambda p: p['time_utc'], reverse=True)
    write_json(PENDING, {'note': '已抓取但未經 Grok 分析嘅帖，下次更新會再試。', 'posts': keep}, indent=1)

    now = now_hk()
    gen = now.strftime('%Y-%m-%d %H:%M')
    d['meta']['generated_hkt'] = gen
    d['meta']['build_id'] = 'build-' + now.strftime('%Y%m%d-%H%M%S')
    warn = [w for w in (d['meta'].get('warnings') or []) if not str(w).startswith(('攞帖失敗', '未分析'))]
    if new.get('failed'):
        warn.append('攞帖失敗：' + '、'.join(f.split('（')[0] for f in new['failed']))
    if keep:
        warn.append(f'未分析：{len(keep)} 則新帖等待 Grok 分析')
    d['meta']['warnings'] = warn
    if added:
        latest = max(p['time_hkt'] for p in d['posts'])
        d['meta']['cutoff_hkt'] = latest
        days = {x['day']: x for x in d.get('days', [])}
        for day in sorted({p['day'] for p in added}):
            ps = [p for p in d['posts'] if p['day'] == day]
            x = days.setdefault(day, {'day': day})
            x.update(coverage_start_hkt=min(p['time_hkt'] for p in ps), coverage_end_hkt=max(p['time_hkt'] for p in ps),
                     updated_hkt=gen, source_accounts=new.get('accounts') or x.get('source_accounts'),
                     cutoff_hkt=max(p['time_hkt'] for p in ps), n_posts=len(ps))
        d['days'] = [days[k] for k in sorted(days)]
    save(d)
    write_json(work('merge.json'), {'added': len(added), 'pending': len(keep), 'old_cutoff': old_cutoff,
                                     'cutoff': d['meta']['cutoff_hkt'], 'days': sorted({p['day'] for p in added}),
                                     'generated_hkt': gen, 'failed': new.get('failed') or []})
    notice(f'加入網站：新帖 {len(added)} 則，等待分析 {len(keep)} 則，資料截止 {d["meta"]["cutoff_hkt"]}')


if __name__ == '__main__':
    main()
