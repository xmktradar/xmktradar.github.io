"""IndexNow rotating backfill: order, daily slice, hour gate, notices. No network.

Run from the repo root: python3 tools/test_indexnow.py
"""
import io
import json
import math
import os
import sys
import urllib.error
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import indexnow as I  # noqa: E402

SITE = I.SITE
TODAY = date(2026, 10, 26)
# date.toordinal() for 2026-10-26. (739915 * 150) % 12 == 6 and % 160 == 50.
DAY_NUM = 739915
HK = timezone(timedelta(hours=8))
MORNING = datetime(2026, 10, 26, 3, 5, tzinfo=HK)   # 03:05 HKT, the only backfill slot
LATER = datetime(2026, 10, 26, 7, 5, tzinfo=HK)     # next scheduled slot, same HKT day
NOON = datetime(2026, 10, 26, 12, 0, tzinfo=HK)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SENT_PATH = os.path.join(ROOT, 'data', 'indexnow-sent.json')


def U(path):
    return SITE + path


SITEMAP = [
    U('zh/advertise/'),
    U('en/advertise/'),
    U('ko/advertise/'),
    U('zh/'),
    U('en/'),
    U('ko/'),
    U('zh/support/'),
    U('en/about/'),
    U('newsletter/issue-1/'),
    U('zh/stock/SPY/'),
    U('en/stock/SPY/'),
    U('zh/stock/QQQ/'),
]

# Priority order, independent of where the day's window starts.
ORDERED = [
    U('zh/'), U('en/'), U('ko/'),
    U('zh/advertise/'), U('en/advertise/'), U('ko/advertise/'),
    U('zh/support/'), U('en/about/'), U('newsletter/issue-1/'),
    U('zh/stock/SPY/'), U('en/stock/SPY/'), U('zh/stock/QQQ/'),
]
# N=12 < 150, so the slice is the whole list rotated to index 6.
SLICE_1026 = ORDERED[6:] + ORDERED[:6]


class FakeResp:
    def __init__(self, status=200, body=b''):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_priority_order():
    assert I.order_urls(SITEMAP) == ORDERED
    # Homes stay zh, en, ko even when the sitemap lists them the other way. Duplicates drop.
    mixed = [U('ko/'), U('en/'), U('zh/'), U('en/'), U('tools/'), U('zh/stock/AAA/'), U('en/stock/AAA/')]
    assert I.order_urls(mixed) == [
        U('zh/'), U('en/'), U('ko/'), U('tools/'), U('zh/stock/AAA/'), U('en/stock/AAA/'),
    ]


def test_slice_for_2026_10_26_and_the_next_day():
    assert I.day_number(TODAY) == DAY_NUM
    assert (DAY_NUM * I.BACKFILL) % len(ORDERED) == 6
    assert I.pick_backfill(SITEMAP, [], TODAY) == SLICE_1026
    # 150 % 12 == 6, so the next day starts at index 0: the priority order itself.
    assert I.pick_backfill(SITEMAP, [], TODAY + timedelta(days=1)) == ORDERED
    assert I.pick_backfill(SITEMAP, [], TODAY) == I.pick_backfill(SITEMAP, [], TODAY)


def test_window_is_150_and_wraps():
    sitemap = [U(f'zh/stock/T{i:04d}/') for i in range(160)]
    assert (DAY_NUM * I.BACKFILL) % 160 == 50
    got = I.pick_backfill(sitemap, [], TODAY)
    assert len(got) == I.BACKFILL == 150
    assert len(set(got)) == 150
    assert got[0] == U('zh/stock/T0050/')
    assert got[-1] == U('zh/stock/T0039/')  # 50 + 149 wraps past the end
    assert U('zh/stock/T0000/') in got
    assert U('zh/stock/T0040/') not in got
    assert U('zh/stock/T0049/') not in got
    nxt = I.pick_backfill(sitemap, [], TODAY + timedelta(days=1))
    assert nxt[0] == U('zh/stock/T0040/')  # the step is 150 mod 160 = 150, so 50+150 → 40
    assert set(got) | set(nxt) == set(sitemap)
    assert I.pick_backfill(sitemap, [], TODAY, cap=10) == got[:10]
    assert I.rotating_slice(sitemap, 0) == sitemap[:150]
    assert I.rotating_slice(sitemap, 1) == sitemap[150:] + sitemap[:140]


def test_cycle_covers_every_url_about_once():
    # 3 homes + 19 other + 1125 stock = 1147. ceil(1147/150) = 8, same as the live sitemap.
    urls = [U('ko/'), U('en/'), U('zh/')]
    urls += [U(f'page/{i}/') for i in range(19)]
    urls += [U(f'zh/stock/T{i:04d}/') for i in range(1125)]
    ordered = I.order_urls(urls)
    assert ordered[:4] == [U('zh/'), U('en/'), U('ko/'), U('page/0/')]
    assert ordered[22] == U('zh/stock/T0000/')
    days = math.ceil(len(ordered) / I.BACKFILL)
    assert days == 8
    counts = {}
    for i in range(days):
        part = I.pick_backfill(urls, [], TODAY + timedelta(days=i))
        assert len(part) == I.BACKFILL
        assert len(set(part)) == len(part)
        for u in part:
            counts[u] = counts.get(u, 0) + 1
    assert set(counts) == set(ordered)
    assert all(v >= 1 for v in counts.values())
    # 8*150 - 1147 = 53 URLs fall in the wrap overlap and are sent twice in the cycle, the rest once.
    assert sum(1 for v in counts.values() if v == 2) == 8 * I.BACKFILL - len(ordered)
    assert max(counts.values()) == 2


def test_changed_urls_are_dropped_and_not_replaced():
    sitemap = [U(f'zh/stock/T{i:04d}/') for i in range(160)]
    window = I.pick_backfill(sitemap, [], TODAY)
    skip = [window[0], window[10]]
    picked = I.pick_backfill(sitemap, skip, TODAY)
    assert picked == [u for u in window if u not in skip]
    assert len(picked) == 148
    assert U('zh/stock/T0040/') not in picked  # first URL past today's window
    # Changed URLs that are not in the sitemap stay out of the slice and do not shift it.
    extra = I.pick_backfill(SITEMAP, [U('zh/stock/SPY/'), U('gone/')], TODAY)
    assert U('zh/stock/SPY/') not in extra
    assert extra == [u for u in SLICE_1026 if u != U('zh/stock/SPY/')]


def test_backfill_gate_is_hour_before_4_or_env():
    assert I.want_backfill(datetime(2026, 10, 26, 0, 30, tzinfo=HK))
    assert I.want_backfill(MORNING)
    assert I.want_backfill(datetime(2026, 10, 26, 3, 59, tzinfo=HK))
    assert not I.want_backfill(datetime(2026, 10, 26, 4, 0, tzinfo=HK))
    assert not I.want_backfill(LATER)
    assert not I.want_backfill(datetime(2026, 10, 26, 23, 5, tzinfo=HK))
    with patch.dict(os.environ, {'INDEXNOW_BACKFILL': '1'}):
        assert I.want_backfill(NOON)
    with patch.dict(os.environ, {'INDEXNOW_BACKFILL': '0'}):
        assert I.want_backfill(MORNING)       # only "1" forces it; the hour still decides
        assert not I.want_backfill(NOON)


def run_main(sitemap, changed, status=202, event='schedule', argv=None, http_error=None,
             when=None, backfill=None, url_error=False):
    """Drive main() with faked clock and HTTP. Returns (notes, posts)."""
    when = NOON if when is None else when
    notes, posts = [], []

    def fake_open(req, timeout=None):
        url = req if isinstance(req, str) else req.full_url
        if str(url).endswith('.txt'):
            return FakeResp(200, I.KEY.encode())
        if url_error:
            raise urllib.error.URLError('down')
        if http_error is not None:
            raise urllib.error.HTTPError(url, http_error, 'nope', hdrs=None, fp=io.BytesIO(b'bad'))
        posts.append(json.loads(req.data.decode()))
        return FakeResp(status, b'')

    argv = ['tools/indexnow.py'] if argv is None else argv
    env = {'GITHUB_EVENT_NAME': event}
    if backfill is not None:
        env['INDEXNOW_BACKFILL'] = backfill
    with patch.object(I, 'now_hk', lambda: when), \
            patch.object(I, 'notice', lambda msg, level='notice': notes.append((level, msg))), \
            patch.object(I.urllib.request, 'urlopen', fake_open), \
            patch.object(sys, 'argv', argv), \
            patch.dict(os.environ, env, clear=False):
        if backfill is None:
            os.environ.pop('INDEXNOW_BACKFILL', None)
        real_everything, real_changed = I.everything, I.changed
        I.everything = lambda path='sitemap.xml': list(sitemap)
        I.changed = lambda: list(changed)
        try:
            I.main()
        finally:
            I.everything, I.changed = real_everything, real_changed
    return notes, posts


def test_morning_post_notice_and_no_state_file():
    changed = [U('zh/stock/QQQ/'), U('newsletter/issue-1/')]
    notes, posts = run_main(SITEMAP, changed, status=202, when=MORNING)
    assert len(posts) == 1, posts
    body = posts[0]
    assert body['host'] == 'thecrowdtape.com'
    assert body['key'] == I.KEY
    assert body['keyLocation'] == f'{SITE}{I.KEY}.txt'
    assert body['urlList'][:2] == changed
    fill = body['urlList'][2:]
    assert fill == [u for u in SLICE_1026 if u not in changed]
    assert len(body['urlList']) == len(set(body['urlList'])) <= I.MAX
    assert notes == [('notice', f'IndexNow：已通知 {len(body["urlList"])} 個網頁（2 今次改動 + {len(fill)} 補交），回應 202')]
    assert not os.path.exists(SENT_PATH)
    src = open(os.path.join(ROOT, 'tools', 'indexnow.py'), encoding='utf-8').read()
    assert 'indexnow-sent' not in src
    assert 'load_sent' not in src and 'save_sent' not in src


def test_later_slot_same_day_has_no_backfill():
    changed = [U('zh/stock/SPY/')]
    morning_notes, morning_posts = run_main(SITEMAP, changed, when=MORNING)
    later_notes, later_posts = run_main(SITEMAP, changed, when=LATER)
    fill = [u for u in morning_posts[0]['urlList'] if u != changed[0]]
    assert morning_posts[0]['urlList'][0] == changed[0]
    assert fill == [u for u in SLICE_1026 if u != changed[0]]
    assert '1 今次改動 + %d 補交' % len(fill) in morning_notes[0][1]
    assert later_posts[0]['urlList'] == changed
    assert '1 今次改動 + 0 補交' in later_notes[0][1]
    assert '回應 202' in later_notes[0][1]
    # A URL that did not change is submitted in the morning slice only.
    quiet = U('zh/')
    assert quiet in fill
    assert quiet not in later_posts[0]['urlList']


def test_env_override_matches_the_morning_slice():
    changed = [U('en/')]
    forced_notes, forced_posts = run_main(SITEMAP, changed, when=NOON, backfill='1')
    morning_notes, morning_posts = run_main(SITEMAP, changed, when=MORNING)
    assert forced_posts[0]['urlList'] == morning_posts[0]['urlList']
    assert '1 今次改動 +' in forced_notes[0][1] and '補交' in forced_notes[0][1]
    off_notes, off_posts = run_main(SITEMAP, changed, when=NOON, backfill='0')
    assert off_posts[0]['urlList'] == changed
    assert '1 今次改動 + 0 補交' in off_notes[0][1]


def test_http_error_warns_and_writes_nothing():
    notes, posts = run_main(SITEMAP, [U('en/')], when=MORNING, http_error=400)
    assert posts == []
    assert notes[0][0] == 'warning'
    assert '400' in notes[0][1]
    assert not os.path.exists(SENT_PATH)
    notes, posts = run_main(SITEMAP, [U('en/')], when=MORNING, url_error=True)
    assert posts == []
    assert notes[0][0] == 'warning'
    assert '連唔到' in notes[0][1]


def test_all_sends_sitemap_without_backfill_split():
    notes, posts = run_main(SITEMAP, [U('zh/')], status=200, event='workflow_dispatch', when=MORNING, backfill='1')
    assert len(posts) == 1
    assert posts[0]['urlList'] == SITEMAP
    assert '全部' in notes[0][1]
    assert '補交' not in notes[0][1]
    notes, posts = run_main(SITEMAP, [U('zh/')], status=200, argv=['tools/indexnow.py', '--all'], when=LATER)
    assert posts[0]['urlList'] == SITEMAP
    assert '全部' in notes[0][1]


def test_empty_does_not_post():
    notes, posts = run_main([], [], when=LATER)
    assert posts == []
    assert '冇網頁改動' in notes[0][1]
    # No changed pages on a backfill morning still submits the slice.
    notes, posts = run_main(SITEMAP, [], when=MORNING)
    assert posts[0]['urlList'] == SLICE_1026
    assert '0 今次改動 + %d 補交' % len(SLICE_1026) in notes[0][1]


def test_workflow_submits_only_after_publish():
    text = open(os.path.join(ROOT, '.github', 'workflows', 'update-site.yml'), encoding='utf-8').read()
    assert text.count('name: Tell search engines (IndexNow)') == 1
    assert text.index('name: Publish') < text.index('name: Tell search engines (IndexNow)')
    cond = 'if [ -f "$WORK_DIR/published" ] || [ "$GITHUB_EVENT_NAME" = workflow_dispatch ]; then python3 tools/indexnow.py; fi'
    assert cond in text
    assert 'indexnow-sent' not in text


def main():
    test_priority_order()
    test_slice_for_2026_10_26_and_the_next_day()
    test_window_is_150_and_wraps()
    test_cycle_covers_every_url_about_once()
    test_changed_urls_are_dropped_and_not_replaced()
    test_backfill_gate_is_hour_before_4_or_env()
    test_morning_post_notice_and_no_state_file()
    test_later_slot_same_day_has_no_backfill()
    test_env_override_matches_the_morning_slice()
    test_http_error_warns_and_writes_nothing()
    test_all_sends_sitemap_without_backfill_split()
    test_empty_does_not_post()
    test_workflow_submits_only_after_publish()
    print('test_indexnow: order, rotating slice, hour gate, notices, no sent state')


if __name__ == '__main__':
    main()
