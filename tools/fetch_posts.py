"""Step 2: fetch new posts from the tracked X accounts via the public fxtwitter API.

Writes work/new_posts.json: posts newer than meta.cutoff_hkt that are not on the site yet,
plus anything still waiting in data/pending-posts.json from an earlier run.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from sitedata import load, notice, parse_iso, read_json, work, write_json

API = 'https://api.fxtwitter.com/2/profile/{}/statuses'
STATUS = 'https://api.fxtwitter.com/2/status/{}'
BACKFILL = 800  # older site posts per run that get their original text (English page)
UA = 'TheCrowdTape/1.0 (+https://xmktradar.github.io/)'
PENDING = 'data/pending-posts.json'


def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status == 204:
                    return {'results': [], 'cursor': {}}
                return json.loads(r.read().decode('utf-8', 'replace'))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {'results': [], 'cursor': {}, 'missing': True}
            if e.code == 429 or e.code >= 500:
                time.sleep(3 * 2 ** i)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(3 * 2 ** i)
    raise RuntimeError('fxtwitter 冇回應：' + url)


def media_of(st):
    m = st.get('media') or {}
    out = []
    for x in m.get('all') or []:
        if x.get('type') in ('video', 'gif'):
            out.append(x.get('thumbnail_url') or x.get('url'))
        else:
            out.append(x.get('url'))
    return [u for u in out if u]


def text_of(st):
    return (st.get('text') or (st.get('raw_text') or {}).get('text') or '').strip()


def normalize(st, tracked):
    """One fxtwitter status -> the shape the analyser and merger use."""
    a = st.get('author') or {}
    rb = (st.get('reposted_by') or {}).get('screen_name')
    rt = st.get('replying_to') or {}
    q = st.get('quote')
    quoted = None
    if isinstance(q, dict) and q.get('type') != 'tombstone':
        quoted = {'handle': (q.get('author') or {}).get('screen_name'), 'text': text_of(q)[:1500]}
    ts = st.get('created_timestamp')
    t = datetime.fromtimestamp(ts, timezone.utc) if ts else parse_iso(st['created_at']).astimezone(timezone.utc)
    p = {
        'id': str(st['id']),
        'handle': a.get('screen_name') or tracked,
        'name': a.get('name'),
        'type': 'repost' if rb else ('reply' if rt.get('screen_name') else 'post'),
        'reposted_by': tracked if rb else None,
        'replying_to': {'screen_name': rt.get('screen_name')} if rt.get('screen_name') else None,
        'time_utc': t.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'url': f"https://x.com/{a.get('screen_name') or tracked}/status/{st['id']}",
        'text': text_of(st)[:4000],
        'quoted': quoted,
        'media': media_of(st),
        'likes': st.get('likes'),
        'views': st.get('views'),
        'cashtags': sorted({w[1:].upper().strip('.,!?:;)') for w in text_of(st).split() if w.startswith('$') and w[1:2].isalpha()}),
    }
    p['n_media'] = len(p['media'])
    return p


def main():
    d = load()
    cutoff = parse_iso(d['meta']['cutoff_hkt'])
    since = int(cutoff.timestamp())
    have = {p['url'].lower() for p in d['posts']}
    accounts = [a for a in d['tracked']['accounts'] if a.get('platform', 'x') == 'x']
    pending = read_json(PENDING, {'posts': []})['posts']
    got, failed = {}, []
    for acc in accounts:
        h = acc['handle']
        cursor, pages = None, 0
        try:
            while pages < 5:
                q = {'count': 100, 'with_replies': '1'}
                q.update({'cursor': cursor} if cursor else {'since': since})
                r = get(API.format(urllib.parse.quote(h)) + '?' + urllib.parse.urlencode(q))
                pages += 1
                rows = r.get('results') or []
                old = False
                for e in rows:
                    for st in (e.get('statuses') if e.get('type') == 'thread' else [e]):
                        if not st or not st.get('id'):
                            continue
                        p = normalize(st, h)
                        if parse_iso(p['time_utc']) <= cutoff:
                            old = True
                            continue
                        if p['url'].lower() in have:
                            continue
                        got.setdefault(p['url'].lower(), p)
                cursor = (r.get('cursor') or {}).get('bottom')
                if old or not rows or not cursor:
                    break
        except Exception as e:  # one account failing must not stop the run
            failed.append(f'{h}（{e}）')
        time.sleep(0.3)
    for p in pending:
        if p['url'].lower() not in have:
            got.setdefault(p['url'].lower(), p)
    posts = sorted(got.values(), key=lambda p: p['time_utc'], reverse=True)
    write_json(work('new_posts.json'), {'posts': posts, 'failed': failed, 'accounts': len(accounts)})
    notice(f'攞帖：{len(accounts)} 個 X 帳號，新帖 {len(posts)} 則（包括上次未分析 {len(pending)} 則），失敗 {len(failed)} 個')
    if failed:
        notice('攞帖失敗：' + '、'.join(failed[:20]), 'warning')
    if len(failed) > len(accounts) * 0.8:
        raise SystemExit('大部分帳號都攞唔到帖，停止更新')
    backfill_text(d)


def backfill_text(d):
    """Posts added before the English page existed have no original text; fetch some each run."""
    todo = [p for p in d['posts'] if 'text' not in p][:BACKFILL]
    got, bad = {}, 0
    for p in todo:
        try:
            st = (get(STATUS.format(p['url'].rstrip('/').split('/')[-1]), tries=2) or {}).get('status') or {}
            got[p['url'].lower()] = text_of(st)[:1500]
        except Exception:
            bad += 1
        time.sleep(0.2)
    write_json(work('text_backfill.json'), got)
    if todo:
        notice(f'補原文：{len(got)} 則，失敗 {bad} 則，仲有 {sum("text" not in p for p in d["posts"]) - len(got)} 則未補')


if __name__ == '__main__':
    main()
