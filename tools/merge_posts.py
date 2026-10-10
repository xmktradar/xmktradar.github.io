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
    if a.get('ko_summary'):
        p['ko_summary'] = a['ko_summary']
    p['macro'] = bool(a.get('macro'))
    if (x.get('text') or '').strip():
        p['text'] = x['text'][:1500]  # original wording, shown on the English page
    return p


def keep_days(p):
    """Retention (automation/README.md 9.3): stock or macro posts 28 days, everything else 7 days."""
    has_stock = bool(p.get('tickers') or p.get('stance_by_ticker'))
    return 28 if has_stock or p.get('macro') else 7


def prune(d, now):
    keep = [p for p in d['posts'] if (now - parse_iso(p['time_utc'])).total_seconds() < keep_days(p) * 86400]
    gone = len(d['posts']) - len(keep)
    if gone > len(d['posts']) / 2:
        raise SystemExit(f'刪帖規則要刪 {gone}／{len(d["posts"])} 則，超過一半，停止更新')
    d['posts'] = keep
    live = {p['day'] for p in keep}
    d['days'] = [x for x in d.get('days', []) if x['day'] in live]
    return gone


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
        # Keep today's daily view current: stretch the latest write-up's window to the new cutoff.
        # Grok rewrites the text itself in write_analysis.py when it is available.
        last_day = latest[:10]
        for key in ('summaries', 'summaries_en', 'summaries_ko'):
            for x in d.get(key, {}).get('daily', []):
                if x.get('date') == last_day and isinstance(x.get('win'), dict):
                    x['win']['to'] = latest[:16]
    texts = read_json(work('text_backfill.json'), {})
    for p in d['posts']:
        if 'text' not in p and p['url'].lower() in texts:
            p['text'] = texts[p['url'].lower()]
    pruned = prune(d, now)
    save(d)
    write_json(work('merge.json'), {'added': len(added), 'pruned': pruned, 'pending': len(keep), 'old_cutoff': old_cutoff,
                                     'cutoff': d['meta']['cutoff_hkt'], 'days': sorted({p['day'] for p in added}),
                                     'generated_hkt': gen, 'failed': new.get('failed') or []})
    notice(f'加入網站：新帖 {len(added)} 則，等待分析 {len(keep)} 則，按保留規則刪除 {pruned} 則，資料截止 {d["meta"]["cutoff_hkt"]}')


if __name__ == '__main__':
    main()
