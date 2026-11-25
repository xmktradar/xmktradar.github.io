"""Start the site jobs when GitHub never started the scheduled run.

Covers the full publish, prices, and 齊聲之後 (follow-through). GitHub sometimes
drops a cron. This looks at recent runs and dispatches whatever is overdue.
It does nothing when a run is already queued or in progress, or when one
started in the last 90 minutes. A full site run refreshes prices and
follow-through, so those are not dispatched again in the same pass.

A workflow conclusion of "success" is not enough: the gate job can skip the
real work (update / prices / follow) and the run still succeeds. Only a
successful heavy job counts as a refresh. Live generated_hkt is the primary
signal for Update site.

  python3 tools/ensure_runs.py --self-test
  python3 tools/ensure_runs.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
HK = timezone(timedelta(hours=8))
SITE = 'update-site.yml'
PRICES = 'update-prices.yml'
FOLLOW = 'update-followthrough.yml'
HEAVY_JOB = {SITE: 'update', PRICES: 'prices', FOLLOW: 'follow'}
LIVE_STATUS = 'https://thecrowdtape.com/data/site-status.json'
ACTIVE = {'queued', 'in_progress', 'waiting', 'pending', 'requested'}
SITE_STALE = timedelta(hours=9)
QUIET = timedelta(minutes=90)


def parse_time(s: str) -> datetime:
    return datetime.fromisoformat(s.replace('Z', '+00:00'))


def parse_hkt(s: str) -> datetime:
    s = (s or '').strip().replace('T', ' ')
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(s[:19] if len(s) >= 19 else s, fmt).replace(tzinfo=HK)
        except ValueError:
            continue
    raise ValueError(f'bad generated_hkt: {s!r}')


def latest(runs: list, key: str) -> datetime | None:
    times = []
    for r in runs:
        raw = r.get(key)
        if raw:
            times.append(parse_time(raw))
    return max(times) if times else None


def heavy_job_success(run: dict, job_name: str) -> bool:
    jobs = run.get('jobs') or []
    return any(j.get('name') == job_name and j.get('conclusion') == 'success' for j in jobs)


def last_real_success(runs: list, job_name: str) -> datetime | None:
    """Latest created_at of a successful run whose heavy job actually succeeded.

    Runs that omit a jobs list (or only have a skipped heavy job) do not count.
    """
    times = []
    for r in runs:
        if r.get('conclusion') != 'success':
            continue
        if 'jobs' not in r:
            continue
        if not heavy_job_success(r, job_name):
            continue
        raw = r.get('created_at')
        if raw:
            times.append(parse_time(raw))
    return max(times) if times else None


def blocked(runs: list, now: datetime, quiet: timedelta = QUIET) -> bool:
    if any(r.get('status') in ACTIVE for r in runs):
        return True
    started = latest(runs, 'created_at')
    return bool(started and now - started < quiet)


def should_dispatch(
    runs: list,
    now: datetime,
    stale_after: datetime,
    quiet: timedelta = QUIET,
    generated: datetime | None = None,
    job_name: str | None = None,
) -> bool:
    """True when nothing is running, nothing started during the quiet period, and the last real refresh is too old."""
    if blocked(runs, now, quiet):
        return False
    if generated is not None:
        return generated < stale_after
    ok = last_real_success(runs, job_name) if job_name else None
    if ok and ok >= stale_after:
        return False
    return True


def refresh_overdue(work_runs: list, site_runs: list, now: datetime, stale_after: datetime, work_job: str) -> bool:
    """Prices / follow-through: overdue unless a real work job or a real site update landed after stale_after."""
    if blocked(work_runs + site_runs, now):
        return False
    times = []
    for t in (last_real_success(work_runs, work_job), last_real_success(site_runs, 'update')):
        if t:
            times.append(t)
    ok = max(times) if times else None
    if ok and ok >= stale_after:
        return False
    return True


def price_cutoff(now: datetime) -> datetime | None:
    """US cash close that should already be on the site, or None when no close is due."""
    et = now.astimezone(ET)
    wd = et.weekday()  # Mon=0 … Sun=6
    if wd == 6:
        return None
    close = et.replace(hour=16, minute=0, second=0, microsecond=0)
    due = close.replace(minute=40)
    if wd == 5:
        return close - timedelta(days=1)
    if et >= due:
        return close
    if wd == 0:
        return None
    return close - timedelta(days=1)


def plan(site_runs: list, price_runs: list, now: datetime, ft_runs: list | None = None, site_generated: datetime | None = None) -> list[str]:
    """Workflow filenames to dispatch. A site run also refreshes prices and follow-through."""
    out = []
    if should_dispatch(site_runs, now, now - SITE_STALE, generated=site_generated, job_name='update'):
        out.append(SITE)
    cutoff = price_cutoff(now)
    if not cutoff or SITE in out:
        return out
    if refresh_overdue(price_runs, site_runs, now, cutoff, 'prices'):
        out.append(PRICES)
    ft = site_runs if ft_runs is None else ft_runs
    if refresh_overdue(ft, site_runs, now, cutoff, 'follow'):
        out.append(FOLLOW)
    return out


def api(method: str, url: str, token: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'CrowdTape-AutoRun',
    })
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', 'replace')[:300]
        raise SystemExit(f'GitHub API {e.code} {url}: {detail}') from e


def runs_of(repo: str, workflow: str, token: str) -> list:
    url = f'https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs?per_page=20'
    return (api('GET', url, token).get('workflow_runs') or [])


def attach_jobs(repo: str, runs: list, token: str, job_name: str) -> None:
    """Fill run['jobs'] for recent successes until a real heavy-job success is found."""
    successes = [r for r in runs if r.get('conclusion') == 'success' and r.get('created_at')]
    successes.sort(key=lambda r: parse_time(r['created_at']), reverse=True)
    for r in successes:
        if 'jobs' in r:
            if heavy_job_success(r, job_name):
                return
            continue
        run_id = r.get('id')
        if not run_id:
            r['jobs'] = []
            continue
        url = f'https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs?per_page=20'
        r['jobs'] = (api('GET', url, token).get('jobs') or [])
        if heavy_job_success(r, job_name):
            return


def dispatch(repo: str, workflow: str, token: str) -> None:
    url = f'https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches'
    api('POST', url, token, {'ref': 'main'})


def live_generated(url: str = LIVE_STATUS) -> datetime | None:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'CrowdTape-AutoRun'})
        with urllib.request.urlopen(req, timeout=45) as resp:
            st = json.loads(resp.read().decode())
        raw = st.get('generated_hkt')
        if not raw:
            return None
        return parse_hkt(str(raw))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError, ValueError) as e:
        print(f'live generated_hkt unavailable: {e}')
        return None


def _ok(created: str, job: str, job_conclusion: str = 'success', status: str = 'completed') -> dict:
    conclusion = 'success' if status == 'completed' else None
    jobs = [{'name': 'gate', 'conclusion': 'success'}, {'name': job, 'conclusion': job_conclusion}]
    return {'status': status, 'conclusion': conclusion, 'created_at': created, 'jobs': jobs}


def self_test() -> None:
    now = datetime(2026, 11, 24, 2, 0, tzinfo=timezone.utc)  # Mon 21:00 ET, after the cash close
    after_close = [_ok('2026-11-24T01:00:00Z', 'update')]
    before_close = [_ok('2026-11-23T20:00:00Z', 'update')]
    old = [_ok('2026-11-23T10:00:00Z', 'update')]
    old_prices = [_ok('2026-11-23T10:00:00Z', 'prices')]
    old_ft = [_ok('2026-11-23T10:00:00Z', 'follow')]
    running = [{'status': 'in_progress', 'conclusion': None, 'created_at': '2026-11-23T10:00:00Z'}]
    assert plan(after_close, after_close, now) == [], plan(after_close, after_close, now)
    assert plan(old, old, now) == [SITE], plan(old, old, now)
    assert plan(running, old, now) == [], plan(running, old, now)
    # Site ran before the close and is still inside 9 hours. Prices and 齊聲之後 still need the close.
    assert plan(before_close, old_prices, now, old_ft) == [PRICES, FOLLOW], plan(before_close, old_prices, now, old_ft)
    sunday = datetime(2026, 11, 22, 15, 0, tzinfo=timezone.utc)
    assert price_cutoff(sunday) is None
    assert plan(after_close, old, sunday) == []

    # 2026-11-24 20:56 HKT Auto run: 11:00 HKT slots were gate-skips; 19:00 HKT never started.
    skipped_1124 = [_ok('2026-11-24T04:21:26Z', 'update', job_conclusion='skipped')]
    late_auto = datetime(2026, 11, 24, 12, 57, tzinfo=timezone.utc)
    gen_1058 = parse_hkt('2026-11-24 10:58')
    assert plan(skipped_1124, skipped_1124, late_auto, site_generated=gen_1058) == [SITE], plan(skipped_1124, skipped_1124, late_auto, site_generated=gen_1058)
    # Without live generated_hkt, the skip still must not count as a refresh.
    assert plan(skipped_1124, skipped_1124, late_auto) == [SITE], plan(skipped_1124, skipped_1124, late_auto)
    # A later real site publish after the close covers prices and follow-through.
    assert plan(after_close, old_prices, now, old_ft) == [], plan(after_close, old_prices, now, old_ft)
    # Fresh live generated_hkt suppresses Update site even if recent runs were skips.
    fresh = datetime(2026, 11, 24, 1, 30, tzinfo=timezone.utc)
    assert plan(skipped_1124, skipped_1124, now, site_generated=fresh) == [], plan(skipped_1124, skipped_1124, now, site_generated=fresh)
    print('ok ensure_runs')


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--self-test', action='store_true')
    args = p.parse_args()
    if args.self_test:
        self_test()
        return
    repo = os.environ.get('GITHUB_REPOSITORY', 'xmktradar/xmktradar.github.io')
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token:
        raise SystemExit('GH_TOKEN missing')
    now = datetime.now(timezone.utc)
    site_runs = runs_of(repo, SITE, token)
    price_runs = runs_of(repo, PRICES, token)
    ft_runs = runs_of(repo, FOLLOW, token)
    attach_jobs(repo, site_runs, token, 'update')
    attach_jobs(repo, price_runs, token, 'prices')
    attach_jobs(repo, ft_runs, token, 'follow')
    generated = live_generated()
    if generated is not None:
        print(f'live generated_hkt={generated.astimezone(HK).strftime("%Y-%m-%d %H:%M")} HKT')
    todo = plan(site_runs, price_runs, now, ft_runs, generated)
    if not todo:
        print(f'nothing overdue at {now.strftime("%Y-%m-%d %H:%M")} UTC')
        return
    for name in todo:
        if args.dry_run:
            print(f'would dispatch {name}')
            continue
        dispatch(repo, name, token)
        print(f'dispatched {name}')


if __name__ == '__main__':
    main()
