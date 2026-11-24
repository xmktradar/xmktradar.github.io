"""Start Update site or Update prices when GitHub never started the scheduled run.

GitHub sometimes drops a cron. This looks at recent workflow runs and dispatches
the overdue one. It does nothing when a run is already queued or in progress, or
when one started in the last 90 minutes. Update site covers prices, so a site
dispatch skips a separate price run.

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
SITE = 'update-site.yml'
PRICES = 'update-prices.yml'
ACTIVE = {'queued', 'in_progress', 'waiting', 'pending', 'requested'}
SITE_STALE = timedelta(hours=9)
QUIET = timedelta(minutes=90)


def parse_time(s: str) -> datetime:
    return datetime.fromisoformat(s.replace('Z', '+00:00'))


def latest(runs: list, key: str) -> datetime | None:
    times = []
    for r in runs:
        raw = r.get(key)
        if raw:
            times.append(parse_time(raw))
    return max(times) if times else None


def should_dispatch(runs: list, now: datetime, stale_after: datetime, quiet: timedelta = QUIET) -> bool:
    """True when nothing is running, nothing started during the quiet period, and the last success is too old."""
    if any(r.get('status') in ACTIVE for r in runs):
        return False
    started = latest(runs, 'created_at')
    if started and now - started < quiet:
        return False
    ok = latest([r for r in runs if r.get('conclusion') == 'success'], 'created_at')
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


def plan(site_runs: list, price_runs: list, now: datetime) -> list[str]:
    """Workflow filenames to dispatch, site first. A site run also refreshes prices."""
    out = []
    if should_dispatch(site_runs, now, now - SITE_STALE):
        out.append(SITE)
    cutoff = price_cutoff(now)
    if cutoff and SITE not in out and should_dispatch(price_runs + site_runs, now, cutoff):
        out.append(PRICES)
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


def dispatch(repo: str, workflow: str, token: str) -> None:
    url = f'https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches'
    api('POST', url, token, {'ref': 'main'})


def self_test() -> None:
    now = datetime(2026, 11, 24, 2, 0, tzinfo=timezone.utc)  # Mon 21:00 ET, after the cash close
    after_close = [{'status': 'completed', 'conclusion': 'success', 'created_at': '2026-11-24T01:00:00Z'}]
    before_close = [{'status': 'completed', 'conclusion': 'success', 'created_at': '2026-11-23T20:00:00Z'}]
    old = [{'status': 'completed', 'conclusion': 'success', 'created_at': '2026-11-23T10:00:00Z'}]
    running = [{'status': 'in_progress', 'conclusion': None, 'created_at': '2026-11-23T10:00:00Z'}]
    assert plan(after_close, after_close, now) == [], plan(after_close, after_close, now)
    assert plan(old, old, now) == [SITE], plan(old, old, now)
    assert plan(running, old, now) == [], plan(running, old, now)
    # Site ran before the close and is still inside 9 hours. Prices still need the close.
    assert plan(before_close, old, now) == [PRICES], plan(before_close, old, now)
    sunday = datetime(2026, 11, 22, 15, 0, tzinfo=timezone.utc)
    assert price_cutoff(sunday) is None
    assert plan(after_close, old, sunday) == []
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
    todo = plan(site_runs, price_runs, now)
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
