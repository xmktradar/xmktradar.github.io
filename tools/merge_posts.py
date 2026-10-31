"""Step 4: add analysed posts to the site data; keep the rest for the next run.

Updates posts, days, meta.cutoff_hkt / generated_hkt / build_id and data/pending-posts.json.
Writes work/merge.json with what changed, for the analysis step.
"""
import re
from datetime import timezone

from analyse_posts import NOT_TICKERS
from macro_themes import tag_posts
from relevance import build, relevant, tier
from sitedata import ET, HK, load, notice, now_hk, parse_iso, read_json, save, work, write_json

PENDING = 'data/pending-posts.json'
WAIT_HOURS = 24  # posts with no summary after this long stop waiting (Tim, 2026-10-12)
# "Update site" runs at HKT 03:05, 07:05 ... 23:05 (.github/workflows/update-site.yml). GitHub starts it
# 20-30 minutes late and it takes about 11 minutes, so posts are fetched around :30 and the new page is
# usually up around :40. The header's 下次更新 shows the next of these.
UPDATE_SLOTS = ['03:40', '07:40', '11:40', '15:40', '19:40', '23:40']
SCRAPE_SLOTS = ['03:30', '07:30', '11:30', '15:30', '19:30', '23:30']


def has_stock(x):
    """A $cashtag in the post or the post it quotes: these go first in the queue for Grok."""
    q = (x.get('quoted') or {}).get('text') or ''
    return bool(x.get('cashtags')) or bool(re.search(r'\$[A-Za-z]{1,6}\b', q))


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
    for k in ('stance_by_ticker', 'ticker_notes', 'promo'):
        if a.get(k):
            p[k] = a[k]
    p['zh_summary'] = a['zh_summary']
    for k in ('en_summary',):
        if a.get(k):
            p[k] = a[k]
    p['macro'] = bool(a.get('macro'))
    if 'macro_theme' in a:
        p['macro_theme'] = a['macro_theme']
        if a.get('macro_impact'):
            p['macro_impact'] = a['macro_impact']
    if (x.get('text') or '').strip():
        p['text'] = x['text'][:1500]  # original wording, shown on the English page
    return p


def keep_days(p):
    """Retention: stock or macro posts 28 days (so the monthly view sees 28 days), everything else 2 days (2026-10-10)."""
    has_stock = bool(p.get('tickers') or p.get('stance_by_ticker') or p.get('hidden_tickers'))
    return 28 if has_stock or p.get('macro') else 2


def prune(d, now):
    keep = [p for p in d['posts'] if (now - parse_iso(p['time_utc'])).total_seconds() < keep_days(p) * 86400]
    gone = len(d['posts']) - len(keep)
    if gone > len(d['posts']) / 2:
        raise SystemExit(f'刪帖規則要刪 {gone}／{len(d["posts"])} 則，超過一半，停止更新')
    d['posts'] = keep
    live = {p['day'] for p in keep}
    d['days'] = [x for x in d.get('days', []) if x['day'] in live]
    return gone


CRYPTO = {'BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'ADA', 'BNB'}  # same list as update_prices.py
CASHTAG = re.compile(r'\$([A-Za-z]{1,6})\b')
NAME_TICKERS = {'SPCX': re.compile(r'\bspace ?x\b', re.I)}  # posts often say SpaceX, not $SPCX (Tim, 2026-10-18)


def backfill_tickers(d):
    """Add stocks a summarised post plainly names ($cashtag, or SpaceX) but Grok left out (Tim, 2026-10-18).

    Only tickers the site already knows (a price line or a confirmed override). The added ticker is 未表態,
    unless the post had no ticker at all, has a 睇好/睇淡 stance and names just this one stock.
    """
    ov = d.get('overrides') or {}
    ok = set(d.get('prices') or {}) | {t for t, v in ov.items() if v.get('confirmed')}
    ok -= CRYPTO | NOT_TICKERS | {t for t, v in ov.items() if v.get('unconfirmed') or v.get('drop')}
    n = 0
    for p in d['posts']:
        text = p.get('text') or ''
        if not text or not p.get('zh_summary'):
            continue
        found = {t.upper() for t in CASHTAG.findall(text)} | {t for t, rx in NAME_TICKERS.items() if rx.search(text)}
        have = list(p.get('tickers') or [])
        add = sorted((found & ok) - set(have))
        if not add:
            continue
        sbt = p.get('stance_by_ticker') if isinstance(p.get('stance_by_ticker'), dict) else {}
        for t in add:
            sbt[t] = p['stance'] if not have and len(add) == 1 and p.get('stance') in ('睇好', '睇淡') else '未表態'
        p['tickers'] = have + add
        p['stance_by_ticker'] = sbt
        if 'specific' not in p:
            p['specific'] = False
        n += 1
    if n:
        notice(f'補回帖文提到但漏咗嘅股票代號 {n} 則')
    return n


def known(d):
    """Handles whose posts belong on the site: only Tim's tracked list (2026-10-11), not accounts from older lists."""
    return {a['handle'].lower() for a in d['tracked']['accounts']}


def ours(p, hs):
    """Posts by a tracked account or reposted by one. Strangers replying in a tracked account's thread are not."""
    return bool(p.get('reposted_by')) or p['handle'].lower() in hs


def main():
    d = load()
    hs = known(d)
    strangers = [p for p in d['posts'] if not ours(p, hs)]
    if strangers:
        d['posts'] = [p for p in d['posts'] if ours(p, hs)]
        notice(f'刪除唔喺追蹤名單帳號嘅帖 {len(strangers)} 則')
    # BULLSHIT is not a ticker (team, 2026-10-08): clear it from posts already on the site
    n = 0
    for p in d['posts']:
        changed = False
        if 'tickers' in p:
            tickers = [t for t in p['tickers'] if t not in NOT_TICKERS]
            changed = tickers != p['tickers']
            p['tickers'] = tickers
        if isinstance(p.get('stance_by_ticker'), dict):
            for k in [k for k in p['stance_by_ticker'] if k in NOT_TICKERS]:
                del p['stance_by_ticker'][k]
                changed = True
        if changed:
            n += 1
    if n:
        notice(f'剔走非股票代號（{"、".join(sorted(NOT_TICKERS))}）{n} 則')
    # Korean was removed from the site (Tim, 2026-10-27): drop Korean text kept in the data.
    for p in d['posts']:
        p.pop('ko_summary', None)
        p.pop('summary_ko', None)
    for k in [k for k in d if k.endswith('_ko')]:
        del d[k]
    new = read_json(work('new_posts.json'), {'posts': [], 'failed': [], 'accounts': 0})
    done = read_json(work('analysed.json'), {})
    have = {p['url'].lower() for p in d['posts']}
    add, keep = [], []
    for x in new['posts']:
        if x['url'].lower() in have or not ours(x, hs):
            continue
        (add if x['id'] in done else keep).append(x)
    now = now_hk()
    fresh = [x for x in keep if (now - parse_iso(x['time_utc'])).total_seconds() < WAIT_HOURS * 3600]
    expired = len(keep) - len(fresh)
    # Chit-chat never goes to Grok and never reaches the site: only stock or macro posts wait (Tim, 2026-10-13).
    rx = build(d.get('prices') or {})
    useful = [x for x in fresh if relevant(x, rx)]
    chitchat = len(fresh) - len(useful)
    fresh = useful
    # Grok works from the top of the file: $ticker posts, then company posts, then macro-only; newest first in each.
    keep = sorted(fresh, key=lambda x: x['time_utc'], reverse=True)
    keep.sort(key=lambda x: 0 if has_stock(x) else tier(x, rx))
    old_cutoff = d['meta']['cutoff_hkt']
    added = [site_post(x, done[x['id']]) for x in add]
    d['posts'] = sorted(d['posts'] + added, key=lambda p: p['time_utc'], reverse=True)
    write_json(PENDING, {'note': f'已抓取但未經 Grok 分析嘅帖，只收股票同宏觀帖（閒聊帖唔寫），有股票代號嘅排最前，等超過 {WAIT_HOURS} 個鐘就唔再等。',
                         'posts': keep}, indent=1)

    gen = now.strftime('%Y-%m-%d %H:%M')
    d['meta']['generated_hkt'] = gen
    d['meta']['build_id'] = 'build-' + now.strftime('%Y%m%d-%H%M%S')
    d['meta']['update_slots_hkt'] = UPDATE_SLOTS
    d['meta']['scrape_slots_hkt'] = SCRAPE_SLOTS
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
        for key in ('summaries', 'summaries_en'):
            for x in d.get(key, {}).get('daily', []):
                if x.get('date') == last_day and isinstance(x.get('win'), dict):
                    x['win']['to'] = latest[:16]
    texts = read_json(work('text_backfill.json'), {})
    for p in d['posts']:
        if 'text' not in p and p['url'].lower() in texts:
            p['text'] = texts[p['url'].lower()]
    backfill_tickers(d)
    tag_posts(d['posts'])
    pruned = prune(d, now)
    save(d)
    write_json(work('merge.json'), {'added': len(added), 'pruned': pruned, 'pending': len(keep),
                                     'pending_stock': sum(1 for x in keep if has_stock(x)), 'expired': expired, 'chitchat': chitchat, 'old_cutoff': old_cutoff,
                                     'cutoff': d['meta']['cutoff_hkt'], 'days': sorted({p['day'] for p in added}),
                                     'generated_hkt': gen, 'failed': new.get('failed') or [],
                                     'added_without_en': sum(1 for p in added if not p.get('en_summary'))})
    notice(f'加入網站：新帖 {len(added)} 則，等待分析 {len(keep)} 則，等超過 {WAIT_HOURS} 個鐘唔再等 {expired} 則，閒聊帖唔寫 {chitchat} 則，按保留規則刪除 {pruned} 則，資料截止 {d["meta"]["cutoff_hkt"]}')


if __name__ == '__main__':
    main()
