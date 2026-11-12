"""Missing work/new_posts.json must not wipe data/pending-posts.json.

inbox-lite skips fetch_posts.py. analyse_posts / merge_posts used to treat a missing
fetch file as {posts: []} and overwrite the waiting queue. Run from the repo root:

    python3 tools/test_merge_pending_without_fetch.py
"""
import json
import os
import shutil
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('WORK_DIR', tempfile.mkdtemp(prefix='merge-pending-work-'))

import analyse_posts  # noqa: E402
import merge_posts  # noqa: E402
import sitedata  # noqa: E402

HK = timezone(timedelta(hours=8))


def utc_iso(hours_ago=1):
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime('%Y-%m-%dT%H:%M:%SZ')


def pending_post(pid, hours_ago=1, text='$NVDA looks strong into earnings'):
    return {
        'id': str(pid),
        'handle': 'alpha',
        'name': 'Alpha',
        'type': 'post',
        'time_utc': utc_iso(hours_ago),
        'url': f'https://x.com/alpha/status/{pid}',
        'text': text,
        'cashtags': ['NVDA'],
        'quoted': None,
        'media': [],
        'likes': 10,
        'views': 100,
    }


def site_post(pid, hours_ago=3):
    t = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    hkt = t.astimezone(HK)
    return {
        'handle': 'alpha',
        'time_utc': t.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'time_hkt': hkt.isoformat(timespec='seconds'),
        'url': f'https://x.com/alpha/status/{pid}',
        'tickers': ['NVDA'],
        'day': hkt.date().isoformat(),
        'date_et': t.date().isoformat(),
        'zh_summary': '已有帖',
        'en_summary': 'already on the site',
        'text': '$NVDA already on the site',
        'macro': False,
    }


def dash(posts):
    now = datetime.now(HK)
    cutoff = (now - timedelta(hours=4)).isoformat(timespec='seconds')
    return {
        'meta': {
            'generated_hkt': now.strftime('%Y-%m-%d %H:%M'),
            'cutoff_hkt': cutoff,
            'warnings': [],
        },
        'tracked': {'accounts': [{'handle': 'alpha', 'platform': 'x'}]},
        'posts': posts,
        'days': [{'day': posts[0]['day']}] if posts else [],
        'prices': {'NVDA': {'name': 'NVIDIA'}},
        'overrides': {},
    }


def write_index(d):
    blob = json.dumps(d, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    open('index.html', 'w', encoding='utf-8').write(
        '<!doctype html><html><body>'
        f'<script type="application/json" id="dash-data">{blob}</script>'
        '</body></html>')


def write_json(path, obj):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    json.dump(obj, open(path, 'w', encoding='utf-8'), ensure_ascii=False)


def pending_ids():
    return [str(p.get('id')) for p in sitedata.read_json('data/pending-posts.json', {'posts': []})['posts']]


def site_urls():
    return {p['url'] for p in sitedata.load()['posts']}


def analysis_row():
    return {
        'en_summary': 'Alpha is bullish on NVDA into earnings.',
        'zh_summary': 'Alpha睇好NVDA業績。',
        'tickers': ['NVDA'],
        'stance': '睇好',
        'stance_by_ticker': {'NVDA': '睇好'},
        'horizon': '短線',
        'basis': '技術面',
        'specific': True,
        'macro': False,
    }


@contextmanager
def sandbox():
    tmp = tempfile.mkdtemp(prefix='merge-pending-')
    cwd = os.getcwd()
    old_work = sitedata.WORK
    old_inbox = analyse_posts.INBOX
    old_inbox_dir = analyse_posts.INBOX_DIR
    try:
        os.chdir(tmp)
        sitedata.WORK = os.path.join(tmp, 'work')
        os.makedirs('data/grok-inbox', exist_ok=True)
        os.makedirs(sitedata.WORK, exist_ok=True)
        analyse_posts.INBOX = os.path.join(tmp, 'data', 'super-grok-analysis.json')
        analyse_posts.INBOX_DIR = os.path.join(tmp, 'data', 'grok-inbox')
        yield tmp
    finally:
        os.chdir(cwd)
        sitedata.WORK = old_work
        analyse_posts.INBOX = old_inbox
        analyse_posts.INBOX_DIR = old_inbox_dir
        shutil.rmtree(tmp, ignore_errors=True)


def test_missing_fetch_keeps_unanalysed_pending():
    """No new_posts.json: unanalysed pending posts stay in the queue (not [])."""
    waiting = [pending_post(1001), pending_post(1002), pending_post(1003, hours_ago=2)]
    with sandbox():
        write_index(dash([site_post(1), site_post(2, hours_ago=4)]))
        write_json('data/pending-posts.json', {'posts': waiting})
        assert not os.path.isfile(os.path.join(sitedata.WORK, 'new_posts.json'))
        merge_posts.main()
        got = pending_ids()
        assert got == ['1001', '1002', '1003'], got
        assert 'https://x.com/alpha/status/1001' not in site_urls()


def test_missing_fetch_applies_inbox_analysis():
    """No new_posts.json: grok-inbox analysis for one pending id is merged onto the site."""
    waiting = [pending_post(2001), pending_post(2002)]
    with sandbox() as tmp:
        write_index(dash([site_post(1), site_post(2, hours_ago=4)]))
        write_json('data/pending-posts.json', {'posts': waiting})
        write_json(os.path.join(tmp, 'data', 'grok-inbox', 'batch.json'), {
            'posts': {'2001': analysis_row()},
        })
        analyse_posts.main()
        merge_posts.main()
        urls = site_urls()
        assert 'https://x.com/alpha/status/2001' in urls
        assert 'https://x.com/alpha/status/2002' not in urls
        assert pending_ids() == ['2002']


def test_fetch_path_still_adds_and_keeps_pending():
    """work/new_posts.json present: analysed posts go on the site; unanalysed stock stays pending."""
    analysed = pending_post(3001)
    waiting = pending_post(3002)
    with sandbox():
        write_index(dash([site_post(1), site_post(2, hours_ago=4)]))
        write_json('data/pending-posts.json', {'posts': [waiting]})
        write_json(os.path.join(sitedata.WORK, 'new_posts.json'), {
            'posts': [analysed, waiting],
            'failed': [],
            'accounts': 1,
        })
        write_json(os.path.join(sitedata.WORK, 'analysed.json'), {'3001': analysis_row()})
        merge_posts.main()
        urls = site_urls()
        assert 'https://x.com/alpha/status/3001' in urls
        assert 'https://x.com/alpha/status/3002' not in urls
        assert pending_ids() == ['3002']


if __name__ == '__main__':
    test_missing_fetch_keeps_unanalysed_pending()
    test_missing_fetch_applies_inbox_analysis()
    test_fetch_path_still_adds_and_keeps_pending()
    print('ok')
