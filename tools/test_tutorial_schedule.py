"""Weekend guide schedule (Tim 2026-10-27): new episodes are shown first, one per weekend day from new_first.from,
then the normal loop carries on where it stopped and goes through every episode."""
import json
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from tutorial import episode_for  # noqa: E402

cfg = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'data', 'tutorial-episodes.json'), encoding='utf-8'))
eps, start, first = cfg['episodes'], date.fromisoformat(cfg['start']), cfg.get('new_first')
total = len(eps)
assert [e['n'] for e in eps] == list(range(1, total + 1)), 'episode numbers must run 1..N'
for e in eps:
    for lang in ('zh', 'en'):
        assert all(e[lang].get(k) for k in ('t', 'b', 'how')), f'episode {e["n"]} {lang} missing text'
    assert e['shot'].get('sel') or e['shot'].get('image'), f'episode {e["n"]} has no shot'

seq = []
d = start
while len(seq) < total * 2 + 20:
    n = episode_for(d, start, total, first)
    assert (n is None) == (d.weekday() < 5), d
    if n:
        seq.append((d, n))
    d += timedelta(days=1)
assert episode_for(date(2026, 10, 31), start, total, first) == 28
assert episode_for(date(2026, 11, 1), start, total, first) == 29
before = [n for day, n in seq if first and day < date.fromisoformat(first['from'])]
block = [n for day, n in seq if first and day >= date.fromisoformat(first['from'])][:len(first['episodes'])]
after = [n for day, n in seq if first and day >= date.fromisoformat(first['from'])][len(first['episodes']):]
assert block == first['episodes'], block
assert after[0] == before[-1] % total + 1, (before[-1], after[0])  # the loop resumes where it stopped
assert sorted(set(after[:total])) == list(range(1, total + 1)), 'one full loop shows every episode'
print('test_tutorial_schedule ok:', ' '.join(f'{d:%m/%d}={n}' for d, n in seq[:16]))
