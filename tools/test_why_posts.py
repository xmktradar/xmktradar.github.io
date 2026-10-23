"""Per-stock why posts: real writeup reasons, Threads-first, atomic slots shared.

Run from the repo root: python3 tools/test_why_posts.py
"""
import os
import re
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['WORK_DIR'] = tempfile.mkdtemp(prefix='why-posts-test-')
os.environ['SOCIAL_HISTORY'] = os.path.join(os.environ['WORK_DIR'], 'social-history.json')

import share  # noqa: E402
import three_why  # noqa: E402
from sitedata import HK  # noqa: E402

DAY = '2026-10-23'
URL_RE = re.compile(r'https?://', re.I)
WIN_RE = re.compile(r'^\d\d/\d\d \d\d:\d\d – \d\d:\d\d HKT$')


def _ms(hm, day=DAY):
    return int(datetime.strptime(f'{day} {hm}', '%Y-%m-%d %H:%M').replace(tzinfo=HK).timestamp() * 1000)


def _clean(why):
    text = re.sub(r'https?://\S+', ' ', why or '')
    return re.sub(r'\s+', ' ', text).strip()


def _daily():
    return {
        'from': '2026-10-23T00:00',
        'to': '2026-10-23T23:59',
        'posts': 120,
        'accounts': 45,
        'bull': [{
            't': 'NVDA', 'nb': 4, 'n_posts': 8,
            'rows': [
                {'acc': 'alpha', 's': 'bull', 'why': '@alpha：NVDA 財報勝預期，數據中心營收大增。', 'ms': _ms('09:00')},
                {'acc': 'beta', 's': 'bull', 'why': '$AAPL 財報強。$MSFT 估值合理。', 'ms': _ms('09:10')},
                {'acc': 'lone', 'why': 'https://news.example/a NVDA 指引強勁', 'ms': _ms('09:12')},
            ],
        }],
        'bear': [{
            't': 'QQQ', 'nr': 5, 'n_posts': 6,
            'rows': [
                {'acc': 'bear1', 's': 'bear', 'why': '覺得 QQQ 走勢弱', 'ms': _ms('09:20')},
            ],
        }],
        'split': [{
            't': 'SPCX', 'nb': 3, 'nr': 3, 'n_posts': 9,
            'rows': [
                {'acc': 'sam', 's': 'bull', 'why': 'SPCX 訂單落地。', 'ms': _ms('09:30')},
                {'acc': 'sue', 's': 'bear', 'why': 'SPCX 估值太貴。', 'ms': _ms('09:55')},
                {'acc': 'skip', 'why': '沒有方向', 'ms': _ms('09:40')},
            ],
        }],
    }


def _sources(daily):
    out = {}
    for side in ('bull', 'bear', 'split'):
        for row in daily.get(side) or []:
            out.setdefault(row['t'], []).extend(row.get('rows') or [])
    return out


def test_reasons_are_real_and_labelled():
    daily = _daily()
    posts = share.build_why_posts(daily, DAY)
    by = {p['ticker']: p for p in posts}
    # rank_rows: QQQ nr 5, then NVDA nb 4, then SPCX max(nb,nr) 3.
    assert [p['ticker'] for p in posts] == ['QQQ', 'NVDA', 'SPCX']
    assert all('suggested_kst' not in p for p in posts)
    nv = by['NVDA']
    assert nv['side'] == 'bull'
    assert nv['bull'] == 4 and 'bear' not in nv
    assert nv['accounts'] == 4
    assert nv['format'] == 'carousel'
    assert WIN_RE.match(nv['window']), nv['window']
    assert nv['sample'] == {'posts': 120, 'accounts': 45}
    assert 'instagram' not in nv
    texts = [r['text'] for r in nv['bull_reasons']]
    assert any('財報勝預期' in t for t in texts)
    assert all('http' not in t and 'example' not in t for t in texts)
    assert not any('AAPL' in t or 'MSFT' in t for t in texts)
    # Leading @handle is stripped once; the line is still the source summary.
    src = _sources(daily)['NVDA']
    cleaned = [_clean(share.dedupe_handle(r['acc'], r['why'])) for r in src]
    for reason in nv['bull_reasons']:
        assert reason['acc'] in {r['acc'] for r in src}
        assert any(reason['text'] in c or all(part in c for part in reason['text'].split(' ') if part) for c in cleaned)
    assert {r['acc'] for r in nv['bull_reasons']} == {'alpha', 'lone'}
    spx = by['SPCX']
    assert spx['side'] == 'split' and spx['bull'] == 3 and spx['bear'] == 3
    assert {r['acc'] for r in spx['bull_reasons']} == {'sam'}
    assert {r['acc'] for r in spx['bear_reasons']} == {'sue'}
    assert 'skip' not in {r['acc'] for r in spx.get('bull_reasons', []) + spx.get('bear_reasons', [])}
    qqq = by['QQQ']
    assert qqq['side'] == 'bear' and qqq['bear'] == 5 and 'bull' not in qqq
    assert 'bear_reasons' in qqq and 'bull_reasons' not in qqq
    # No s on a split row: do not guess a side, so the name is omitted.
    bare = {'split': [{'t': 'BARE', 'nb': 4, 'nr': 4, 'n_posts': 3, 'rows': [{'acc': 'z', 'why': 'BARE 無方向'}]}]}
    assert share.build_why_posts(bare, DAY) == []
    linked = 0
    total = 0
    for post in posts:
        assert post['date'] == DAY
        assert set(post['threads']) == set(share.LANGS)
        for lang, entry in post['threads'].items():
            total += 1
            text = entry['text']
            assert len(text) <= 500, (post['ticker'], lang, len(text))
            assert share.SHORT[lang]['disc'] in text
            assert post['window'] in text
            assert '120' in text and '45' in text
            assert URL_RE.search(text) is None
            assert f"${post['ticker']}" in text
            if lang == 'zh':
                assert f"@{post['bull_reasons'][0]['acc'] if post.get('bull_reasons') else post['bear_reasons'][0]['acc']}" in text or '@' in text
            if entry.get('url'):
                linked += 1
                assert f"/{lang}/stock/{post['ticker']}/" in entry['url']
                assert f'utm_source=threads&utm_medium=social&utm_campaign=why' in entry['url']
            else:
                assert post['has_link']['threads'][lang] is False
        if 'x' in post:
            assert set(post['x']) == {'en'}
            xen = post['x']['en']
            assert share.xlen(xen['text']) <= 280
            assert share.SHORT['en']['disc'] in xen['text']
            assert post['window'] in xen['text']
            if xen.get('url'):
                assert 'utm_source=x&utm_medium=social&utm_campaign=why' in xen['url']
                assert '/en/stock/' in xen['url']
    assert abs(linked - (total - linked)) <= 1
    assert linked and linked < total


def test_atomic_slots_do_not_share_ticker_or_time():
    daily = _daily()
    daily.update({
        'originals': 77, 'reposts': 11, 'bull_views': 36, 'bear_views': 41,
        'clear_accounts': 28, 'bull_total': 2, 'bear_total': 1, 'split_total': 7,
    })
    writeup = {
        'daily': daily,
        'weekly': {
            'from': '2026-10-17', 'to': DAY,
            'bull_total': 19, 'bear_total': 8, 'split_total': 64,
            'posts': 400, 'accounts': 128,
            'bull': [{'t': 'AMZN', 'nb': 12, 'rows': [{'acc': 'a', 's': 'bull', 'why': '週看好'}]}],
            'bear': [{'t': 'MRNA', 'nr': 9, 'rows': [{'acc': 'c', 's': 'bear', 'why': '週看淡'}]}],
            'split': [],
        },
    }
    hist = {}
    sp = {'date': DAY, 'window': '10/23 00:00 – 09:55 HKT', 'posts': {'zh': {'x': 'headline $NONE'}}}
    share.attach_market_slots(sp, DAY, writeup, hist, save=False)
    why = sp.get('why_posts') or []
    atomic = sp.get('atomic_posts') or []
    assert why and atomic
    assert [p['suggested_kst'] for p in why] == list(share.ATOMIC_TIMES[:len(why)])
    assert len({p['suggested_kst'] for p in why}) == len(why)
    why_t = {p['ticker'] for p in why}
    atom_t = {p.get('ticker') for p in atomic if p.get('ticker')}
    assert why_t.isdisjoint(atom_t)
    why_times = {p['suggested_kst'] for p in why}
    atom_times = {p['slot_kst'] for p in atomic}
    assert why_times.isdisjoint(atom_times)
    why_pairs = {(p['ticker'], p['suggested_kst']) for p in why}
    atom_pairs = {(p['ticker'], p['slot_kst']) for p in atomic if p.get('ticker')}
    assert why_pairs.isdisjoint(atom_pairs)
    n_atom = len([p for p in atomic if p['lang'] == 'zh'])
    assert 4 <= len(why) + n_atom <= 6
    assert share.guard_slots(sp) == []
    assert hist[DAY]['why'] == [p['ticker'] for p in why]
    assert hist[DAY]['why_text']
    assert os.path.exists(os.environ['SOCIAL_HISTORY']) is False
    # An earlier day's body is not repeated. Today's own history does not ban a rewrite.
    assert three_why.prior_texts({DAY: {'why_text': list(hist[DAY]['why_text'])}}, DAY) == set()
    prev = {'2026-10-22': {'why_text': list(hist[DAY]['why_text'])}}
    kept = three_why.drop_repeated(why, three_why.prior_texts(prev, DAY))
    assert len(kept) < len(why)


def test_schedule_drops_same_ticker():
    why = [{'ticker': 'AAA'}, {'ticker': 'BBB'}]
    atomic = [
        {'lang': 'zh', 'ticker': 'AAA', 'slot_kst': '09:00', 'text': 'za'},
        {'lang': 'en', 'ticker': 'AAA', 'slot_kst': '09:00', 'text': 'ea'},
        {'lang': 'ko', 'ticker': 'AAA', 'slot_kst': '09:00', 'text': 'ka'},
        {'lang': 'zh', 'slot_kst': '11:30', 'text': 'zn'},
        {'lang': 'en', 'slot_kst': '11:30', 'text': 'en'},
        {'lang': 'ko', 'slot_kst': '11:30', 'text': 'kn'},
    ]
    why, atomic = share.schedule_why_atomic(why, atomic)
    assert [p['suggested_kst'] for p in why] == ['09:00', '11:30']
    assert all(a.get('ticker') != 'AAA' for a in atomic)
    assert {a['slot_kst'] for a in atomic} == {'14:00'}
    assert len(atomic) == 3


def main():
    test_reasons_are_real_and_labelled()
    test_atomic_slots_do_not_share_ticker_or_time()
    test_schedule_drops_same_ticker()
    print('test_why_posts: reasons, labels, UTM, atomic slots ok')


if __name__ == '__main__':
    main()
