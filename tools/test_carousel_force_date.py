"""CAROUSEL_FORCE show date and skip jobs (tools/carousel.py).

Offline. No ffmpeg, no network, no Playwright. Run from the repo root:
    python3 tools/test_carousel_force_date.py
"""
import io
import json
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import carousel  # noqa: E402
import sitedata  # noqa: E402
import video_signal  # noqa: E402

NY = ZoneInfo('America/New_York')


def _post(url='https://x.com/example/status/1'):
    return {
        'url': url,
        'handle': 'example',
        'time_utc': '2026-11-11T22:43:00+00:00',
        'time_hkt': '2026-11-12T06:43:00+08:00',
        'tickers': ['INTC'],
        'text': 'Intel is the name accounts are on today.',
        'en_summary': 'Intel is the name accounts are on today.',
        'zh_summary': '帳號今天在討論 Intel。',
        'stance': '睇好',
        'likes': '3',
    }


def _top(t='INTC', accounts=8, bull=8, bear=0, url='https://x.com/example/status/1'):
    return {
        't': t,
        'accounts': accounts,
        'bull_accounts': bull,
        'bear_accounts': bear,
        'urls': [url] if url else [],
        'accs': ['example'] if url else [],
    }


def _daily(top):
    return {
        'top': top,
        'split': [],
        'bull': [],
        'bear': [],
        'accounts': sum(x.get('accounts') or 0 for x in top),
        'tickers': len(top),
        'from': '11/10 19:30',
        'to': '11/12 01:51',
    }


def _social(date):
    def lang(text):
        return {
            'instagram': text, 'threads': text, 'x': text, 'facebook': text, 'story': '#tape',
            'reddit': {'title': text, 'body': text},
        }
    return {
        'date': date,
        'made_hkt': '2026-11-11 11:48',
        'window': '11/10 19:30 – 11/12 01:51 HKT',
        'images': {
            'zh': 'https://thecrowdtape.com/og/social-zh.png',
            'en': 'https://thecrowdtape.com/og/social-en.png',
        },
        'stories': {
            'zh': 'https://thecrowdtape.com/og/story-zh.png',
            'en': 'https://thecrowdtape.com/og/story-en.png',
        },
        'posts': {'zh': lang('中文'), 'en': lang('English')},
        'slots': {},
    }


def _index(posts):
    data = {'posts': posts, 'accounts': {'example': {'name': 'Example', 'avatar': ''}}, 'prices': {}}
    blob = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')
    return '<!doctype html><script type="application/json" id="dash-data">' + blob + '</script>'


def _no_ta(decision, **_kwargs):
    return {'tickers': []}


def _run(stats, social, slots, force, when, posts=None):
    """Run carousel.main() in a temp cwd. Returns (exit_code, stdout, carousel_or_None)."""
    tmp = tempfile.mkdtemp(prefix='carousel-force-')
    work = os.path.join(tmp, 'work')
    os.makedirs(os.path.join(tmp, 'data'))
    os.makedirs(work)
    social_path = os.path.join(tmp, 'data', 'social-posts.json')
    with open(social_path, 'w', encoding='utf-8') as f:
        json.dump(social, f)
    before = open(social_path, 'rb').read()
    with open(os.path.join(work, 'stats.json'), 'w', encoding='utf-8') as f:
        json.dump(stats, f)
    with open(os.path.join(tmp, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(_index(posts if posts is not None else [_post()]))

    old_cwd = os.getcwd()
    old_work = sitedata.WORK
    old_slots = carousel.VIDEO_SLOTS
    old_now = carousel.now_et
    old_ta = video_signal.textbook_ta.publish_ta
    env_keys = ('CAROUSEL_FORCE', 'VIDEO_SLOTS', 'CAROUSEL_ONLY_SLOTS', 'WORK_DIR')
    old_env = {k: os.environ.get(k) for k in env_keys}
    buf = io.StringIO()
    code = 0
    try:
        os.chdir(tmp)
        sitedata.WORK = work
        os.environ['WORK_DIR'] = work
        os.environ['VIDEO_SLOTS'] = slots
        os.environ['CAROUSEL_ONLY_SLOTS'] = slots
        carousel.VIDEO_SLOTS = tuple(x for x in slots.split(',') if x)
        if force:
            os.environ['CAROUSEL_FORCE'] = '1'
        else:
            os.environ.pop('CAROUSEL_FORCE', None)
        if when is None:
            def _boom(now=None):
                raise AssertionError('now_et called without CAROUSEL_FORCE')
            carousel.now_et = _boom
        else:
            frozen = when if when.tzinfo else when.replace(tzinfo=NY)
            carousel.now_et = lambda now=None, frozen=frozen: frozen
        video_signal.textbook_ta.publish_ta = _no_ta
        try:
            with redirect_stdout(buf):
                carousel.main()
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
        text = buf.getvalue()
        path = os.path.join(work, 'carousel.json')
        payload = json.load(open(path, encoding='utf-8')) if os.path.isfile(path) else None
        after = open(social_path, 'rb').read()
        assert after == before, 'data/social-posts.json was rewritten'
        return code, text, payload
    finally:
        os.chdir(old_cwd)
        sitedata.WORK = old_work
        carousel.VIDEO_SLOTS = old_slots
        carousel.now_et = old_now
        video_signal.textbook_ta.publish_ta = old_ta
        for key, prev in old_env.items():
            if prev is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev
        shutil.rmtree(tmp, ignore_errors=True)


def _en(payload, slot):
    jobs = [j for j in (payload or {}).get('jobs') or [] if j.get('slot') == slot and j.get('lang') == 'en']
    assert len(jobs) == 1, payload
    return jobs[0]


def _no_mp4(job):
    blob = json.dumps(job)
    assert '.mp4' not in blob, blob
    assert 'http' not in blob or 'mp4' not in blob, blob


def test_now_et_is_new_york():
    now = carousel.now_et()
    key = getattr(now.tzinfo, 'key', None) or str(now.tzinfo)
    assert key == 'America/New_York', key
    # 2026-11-11 is after the US clock change. A fixed UTC-4 offset would still say 18:55.
    winter = carousel.now_et(datetime(2026, 11, 11, 17, 55))
    assert winter.utcoffset().total_seconds() == -5 * 3600, winter
    assert winter.date().isoformat() == '2026-11-11'


def test_force_1630_date_mismatch_writes_show_date():
    """Failed 06:55 HKT run: stats.today is 2026-11-12, social-posts is still 2026-11-11."""
    when = datetime(2026, 11, 11, 17, 55, tzinfo=NY)
    stats = {'today': '2026-11-12', 'daily': _daily([_top()])}
    code, out, payload = _run(stats, _social('2026-11-11'), '1630', True, when)
    assert code == 0, out
    assert 'carousel: no posts today' not in out, out
    assert payload is not None, out
    assert payload['date'] == '2026-11-11', payload['date']
    assert payload['date'] != '2026-11-12'
    job = _en(payload, '1630')
    assert job['date'] == '2026-11-11', job
    assert job.get('show') == 'crowd-heat', job
    assert job.get('publishable') is True, job
    assert not job.get('video_skip'), job
    assert job.get('beats'), job
    names = job.get('names') or []
    assert names and names[0]['t'] == 'INTC', job
    assert names[0]['bull_accounts'] == 8 and names[0]['bear_accounts'] == 0, names
    blob = json.dumps(job)
    assert '0 bulls versus 0 bears' not in blob
    assert '0 bull / 0 bear' not in blob
    for j in payload['jobs']:
        assert j['date'] == '2026-11-11', j


def test_force_saturday_week_tape_uses_saturday():
    when = datetime(2026, 11, 7, 14, 52, tzinfo=NY)
    stats = {
        'today': '2026-11-07',
        'daily': _daily([_top(accounts=8, bull=8, bear=0)]),
        'weekly': {'top': [], 'split': [], 'bull': [], 'bear': []},
    }
    code, out, payload = _run(stats, _social('2026-11-06'), 'sat', True, when)
    assert code == 0, out
    assert 'carousel: no posts today' not in out, out
    assert payload is not None, out
    assert payload['date'] == '2026-11-07', payload
    job = _en(payload, 'sat')
    assert job['date'] == '2026-11-07', job
    assert job.get('show') == 'week-tape', job
    assert job.get('video_skip') is True or job.get('publishable') is False, job
    assert job.get('publishable') is not True, job
    _no_mp4(job)
    assert not job.get('beats'), job


def test_force_zero_stance_is_skip():
    """0 bull / 0 bear is a real skip. Do not publish a comparison clip to go green."""
    when = datetime(2026, 11, 11, 17, 55, tzinfo=NY)
    top = [_top(t='SPY', accounts=12, bull=0, bear=0, url='https://x.com/example/status/9')]
    stats = {'today': '2026-11-12', 'daily': _daily(top)}
    code, out, payload = _run(stats, _social('2026-11-11'), '1630', True, when, posts=[_post('https://x.com/example/status/9')])
    assert code == 0, out
    assert 'carousel: no posts today' not in out, out
    assert payload is not None, out
    assert payload['date'] == '2026-11-11'
    job = _en(payload, '1630')
    assert job.get('video_skip') is True, job
    assert job.get('publishable') is False, job
    signal = job.get('signal') or {}
    assert signal.get('publishable') is False, job
    assert signal.get('reason') == 'zero_stance', job
    assert job.get('mode') == 'skip', job
    assert not job.get('beats'), job
    assert not job.get('names'), job
    assert job.get('skip_stills') is True, job
    _no_mp4(job)
    assert '0 bulls versus 0 bears' not in json.dumps(job)
    assert all(j.get('publishable') is not True for j in payload['jobs'])


def test_force_empty_top_is_skip():
    when = datetime(2026, 11, 11, 17, 55, tzinfo=NY)
    stats = {'today': '2026-11-12', 'daily': _daily([])}
    code, out, payload = _run(stats, _social('2026-11-11'), '1630', True, when, posts=[])
    assert code == 0, out
    assert 'carousel: no posts today' not in out, out
    assert payload is not None, out
    job = _en(payload, '1630')
    assert job['date'] == '2026-11-11', job
    assert job.get('video_skip') is True, job
    assert job.get('publishable') is False, job
    assert (job.get('signal') or {}).get('reason') == 'no_heat', job
    assert not job.get('beats'), job
    assert job.get('skip_stills') is True, job
    _no_mp4(job)


def test_no_force_date_mismatch_does_not_write():
    stats = {'today': '2026-11-12', 'daily': _daily([_top()])}
    code, out, payload = _run(stats, _social('2026-11-11'), '1630', False, None)
    assert code == 0, out
    assert 'carousel: no posts today' in out, out
    assert payload is None

    # Same social-posts date, but Saturday is not a trading day: still no rewrite.
    weekend = {'today': '2026-11-07', 'daily': _daily([_top()])}
    code, out, payload = _run(weekend, _social('2026-11-07'), '1630', False, None)
    assert code == 0, out
    assert 'carousel: no posts today' in out, out
    assert payload is None


def main():
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print('ok', name)


if __name__ == '__main__':
    main()
