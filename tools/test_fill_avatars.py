"""A fxtwitter HTTP 404 is a retry, not a seven-day avatar miss."""
import json
import os
import shutil
import sys
import tempfile
import urllib.error
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fill_avatars as F  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_MISS = os.path.join(ROOT, 'data', 'avatar-miss.json')


def test_404_is_not_recorded_as_a_miss():
    before = open(REAL_MISS, 'rb').read()
    tmp = tempfile.mkdtemp(prefix='fill-avatars-')
    miss_path = os.path.join(tmp, 'avatar-miss.json')
    json.dump({'keepme': '2026-11-25'}, open(miss_path, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    data = {
        'posts': [
            {'handle': 'flaky404'},
            {'handle': 'forbid403'},
            {'handle': 'nophoto'},
        ],
    }

    def fake_get(url, timeout=20, accept='application/json'):
        if str(url).endswith('/flaky404'):
            raise urllib.error.HTTPError(url, 404, 'Not Found', None, None)
        if str(url).endswith('/forbid403'):
            raise urllib.error.HTTPError(url, 403, 'Forbidden', None, None)
        if str(url).endswith('/nophoto'):
            return 200, 'application/json', b'{"user":{}}'
        raise AssertionError(url)

    cwd = os.getcwd()
    old_budget = os.environ.get('FILL_AVATAR_SECONDS')
    old = (F.MISS, F.load, F.save, F.get)
    os.environ['FILL_AVATAR_SECONDS'] = '60'
    F.MISS = miss_path
    F.load = lambda: data
    F.save = lambda d: None
    F.get = fake_get
    real_sleep = F.time.sleep
    F.time.sleep = lambda *a, **k: None
    try:
        F.main()
        written = json.load(open(miss_path, encoding='utf-8'))
    finally:
        F.MISS, F.load, F.save, F.get = old
        F.time.sleep = real_sleep
        os.chdir(cwd)
        if old_budget is None:
            os.environ.pop('FILL_AVATAR_SECONDS', None)
        else:
            os.environ['FILL_AVATAR_SECONDS'] = old_budget
        shutil.rmtree(tmp, ignore_errors=True)

    assert open(REAL_MISS, 'rb').read() == before
    today = date.today().isoformat()
    assert 'flaky404' not in written, written
    assert written['forbid403'] == today, written
    assert written['nophoto'] == today, written
    assert written['keepme'] == '2026-11-25', written
    assert set(written) == {'keepme', 'forbid403', 'nophoto'}, written


if __name__ == '__main__':
    test_404_is_not_recorded_as_a_miss()
    print('ok fill avatars')
