"""Site Check: fail if live generated_hkt is older than MAX_AGE_H hours.

Replaces the SuperGrok Site Check automation. Reads
https://thecrowdtape.com/data/site-status.json (fallback: repo file).
Exit 0 = fresh enough; exit 1 = stale / unreadable (GitHub Actions fails the job).
No xAI / Post Summary calls — Tim has no API key for that path.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

HK = timezone(timedelta(hours=8))
LIVE_URL = 'https://thecrowdtape.com/data/site-status.json'
DEFAULT_MAX_AGE_H = 9.0


def parse_hkt(s: str) -> datetime:
    s = (s or '').strip().replace('T', ' ')
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(s[:19] if len(s) >= 19 else s, fmt).replace(tzinfo=HK)
        except ValueError:
            continue
    raise ValueError(f'bad generated_hkt: {s!r}')


def load_status(path: str | None, url: str) -> dict:
    if path:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    req = urllib.request.Request(url, headers={'User-Agent': 'CrowdTape-SiteCheck/1.0'})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode('utf-8'))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Fail if site generated_hkt is older than N hours')
    ap.add_argument('--max-age-h', type=float, default=DEFAULT_MAX_AGE_H,
                    help='stale threshold in hours (default 9; Tim/CEO 2026-11-05 with 8h Update)')
    ap.add_argument('--path', default=None, help='read local JSON instead of live URL')
    ap.add_argument('--url', default=LIVE_URL)
    args = ap.parse_args(argv)

    try:
        st = load_status(args.path, args.url)
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        print(f'::error::Site Check could not read status: {e}')
        return 1

    gen = st.get('generated_hkt')
    if not gen:
        print('::error::Site Check: site-status.json missing generated_hkt')
        return 1

    try:
        gen_dt = parse_hkt(str(gen))
    except ValueError as e:
        print(f'::error::Site Check: {e}')
        return 1

    now = datetime.now(HK)
    age_h = (now - gen_dt).total_seconds() / 3600.0
    print(f'Site Check: generated_hkt={gen} age_h={age_h:.2f} max={args.max_age_h} '
          f'checked_hkt={st.get("checked_hkt")} waiting={st.get("waiting_for_summary")}')

    if age_h > args.max_age_h:
        print(f'::error::Site stale: generated_hkt {gen} is {age_h:.1f}h old '
              f'(threshold {args.max_age_h}h). Update site may have missed a slot.')
        return 1

    print('Site Check OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
