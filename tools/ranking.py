"""Shared bull/bear order for the top-5 card and the carousel.

Account count is `nb` on a bull list and `nr` on a bear list. Post count is
`n_posts` (missing counts as 0). Order is account count descending, then post
count descending, then ticker ascending. A row with no ticker or no numeric
account count is left out. The input list is not reordered.
"""
import re


def _is_num(n):
    return isinstance(n, (int, float)) and not isinstance(n, bool)


def _ticker(row):
    return re.sub(r'[^A-Z0-9.\-]', '', str((row or {}).get('t') or '').strip().lstrip('$').upper())


def rank_rows(rows, side):
    """Return `rows` for one side, highest account count first.

    `side` is 'bull' or 'bear'. Each item in the result is the original row.
    """
    key = {'bull': 'nb', 'bear': 'nr'}.get(side)
    if key is None:
        raise ValueError(side)
    kept = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        ticker = _ticker(row)
        accounts = row.get(key)
        if not ticker or not _is_num(accounts):
            continue
        posts = row.get('n_posts')
        posts = posts if _is_num(posts) else 0
        kept.append((row, accounts, posts, ticker))
    kept.sort(key=lambda item: (-item[1], -item[2], item[3]))
    return [item[0] for item in kept]
