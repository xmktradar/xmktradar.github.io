#!/usr/bin/env python3
"""Keep user-facing roster-count copy in sync with official tracked.accounts.

The official list is index.html #dash-data → tracked.accounts (not
data/dash/master-core.json). This rewrites only known marketing frames so a
later expansion (e.g. 454 → 500) does not leave stale 200/201/208/454
literals. It never pads the roster and never writes a target size.

Skip: dash-data JSON, historical test fixtures, post bodies, years,「200 億」.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH_RE = re.compile(
    r'<script type="application/json" id="dash-data">(.*?)</script>',
    re.S,
)

# Source + already-published pages that can still show a stale count until
# the next generator run. Fixtures (test_ig_boost.py) are intentionally omitted.
FILES = [
    'index.html',
    'i18n/zh.json',
    'i18n/en.json',
    'llms.txt',
    'llms-full.txt',
    'tools/weekly.html',
    'tools/advertise.html',
    'tools/toolspage.html',
    'tools/MOTION_VIDEO.md',
    'weekly/index.html',
    'zh/weekly/index.html',
    'zh/index.html',
    'en/index.html',
    'zh/about/index.html',
    'en/about/index.html',
    'about/index.html',
    'zh/advertise/index.html',
    'en/advertise/index.html',
    'advertise/index.html',
    'zh/tools/index.html',
    'en/tools/index.html',
    'tools/index.html',
    'social/macro.html',
    'data/macro-week.json',
]


def official_counts(html: str) -> tuple[int, int, int]:
    blob = DASH_RE.search(html)
    if not blob:
        raise SystemExit('sync_roster_copy: no #dash-data in index.html')
    accounts = json.loads(blob.group(1))['tracked']['accounts']
    n = len(accounts)
    if n == 0:
        raise SystemExit('sync_roster_copy: official list is empty')
    nx = sum(1 for a in accounts if (a.get('platform') or 'x').lower() in ('x', 'twitter', ''))
    # Truth Social (and any other non-X) is the remainder
    nt = n - nx
    return n, nx, nt


def apply_frames(text: str, n: int, nx: int, nt: int) -> str:
    """Replace digits only inside known roster-count frames."""
    subs = [
        (r'目前追蹤 \d+ 個帳號，其中 \d+ 個在 X、\d+ 個在 Truth Social',
         f'目前追蹤 {n} 個帳號，其中 {nx} 個在 X、{nt} 個在 Truth Social'),
        (r'It currently tracks \d+ accounts: \d+ on X and \d+ on Truth Social',
         f'It currently tracks {n} accounts: {nx} on X and {nt} on Truth Social'),
        (r'It currently tracks \d+ accounts \(\d+ on X and \d+ on Truth Social\)',
         f'It currently tracks {n} accounts ({nx} on X and {nt} on Truth Social)'),
        (r'\d+ 帳號｜6 類｜每 8 小時更新',
         f'{n} 帳號｜6 類｜每 8 小時更新'),
        (r'\d+ accounts · 6 categories · every 8 hours',
         f'{n} accounts · 6 categories · every 8 hours'),
        (r'\d+ 個美股帳號',
         f'{n} 個美股帳號'),
        (r'\d+ US-stock accounts',
         f'{n} US-stock accounts'),
        (r'我哋追蹤大約 \d+ 個 X 上最受關注嘅美股帳號',
         f'我哋追蹤 {n} 個美股帳號'),
        (r'我哋追蹤 \d+ 個美股帳號',
         f'我哋追蹤 {n} 個美股帳號'),
        (r'We track about \d+ of the top US-stock accounts(?: on X)?',
         f'We track {n} of the top US-stock accounts'),
        (r'We track \d+ of the top US-stock accounts',
         f'We track {n} of the top US-stock accounts'),
        (r'The Crowd Tape 統計 X 上大約 \d+ 個美股帳號',
         f'The Crowd Tape 統計 {n} 個美股帳號'),
        (r'The Crowd Tape 統計 \d+ 個美股帳號',
         f'The Crowd Tape 統計 {n} 個美股帳號'),
        (r'what ~\d+ US-stock accounts on X are saying',
         f'what {n} US-stock accounts are saying'),
        (r'what \d+ US-stock accounts are saying',
         f'what {n} US-stock accounts are saying'),
        (r'唔使自己再翻 \d+ 個帳號',
         f'唔使自己再翻 {n} 個帳號'),
        (r'看清 \d+ 個美股帳號',
         f'看清 {n} 個美股帳號'),
        (r'X 上 \d+ 個美股大神',
         f'{n} 個美股帳號'),
        (r'這星期我們追蹤的 \d+ 個 X 帳號',
         f'這星期我們追蹤的 {nx} 個 X 帳號'),
        (r'The macro topics the \d+ X accounts we follow',
         f'The macro topics the {nx} X accounts we follow'),
        # llms-full.txt block (generated, but refresh if the file is stale)
        (r'Tracked accounts: \d+\n- X: \d+\n- Truth Social: \d+',
         f'Tracked accounts: {n}\n- X: {nx}\n- Truth Social: {nt}'),
    ]
    out = text
    for pat, rep in subs:
        out = re.sub(pat, rep, out)
    return out


def patch_file(path: Path, n: int, nx: int, nt: int) -> bool:
    raw = path.read_text(encoding='utf-8')
    # Do not touch official data: rewrite around the dash-data script only.
    parts = DASH_RE.split(raw)
    if len(parts) == 3:
        # parts = [before, dash-json, after]
        new = apply_frames(parts[0], n, nx, nt) + \
            f'<script type="application/json" id="dash-data">{parts[1]}</script>' + \
            apply_frames(parts[2], n, nx, nt)
    else:
        new = apply_frames(raw, n, nx, nt)
    if new != raw:
        path.write_text(new, encoding='utf-8')
        return True
    return False


def main() -> int:
    root = ROOT
    html = (root / 'index.html').read_text(encoding='utf-8')
    n, nx, nt = official_counts(html)
    changed = []
    for rel in FILES:
        p = root / rel
        if not p.exists():
            continue
        if patch_file(p, n, nx, nt):
            changed.append(rel)
    print(f'sync_roster_copy: official {n} accounts ({nx} on X, {nt} on Truth Social)')
    if changed:
        print('updated: ' + ', '.join(changed))
    else:
        print('already in sync')
    return 0


if __name__ == '__main__':
    sys.exit(main())
