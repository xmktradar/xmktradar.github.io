"""Per-stock why posts: real writeup reasons, Threads-first, atomic slots shared.

Run from the repo root: python3 tools/test_why_posts.py
"""
import json
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


def _quotes(text):
    out = []
    for line in (text or '').splitlines():
        m = re.match(r'^@([A-Za-z0-9_]+)[：:]\s*(.*)$', line.strip())
        if m and m.group(2):
            out.append((m.group(1), m.group(2)))
    return out


def _daily():
    return {
        'from': '2026-10-23T00:00',
        'to': '2026-10-23T23:59',
        'posts': 120,
        'accounts': 45,
        'bull': [{
            't': 'NVDA', 'nb': 4, 'n_posts': 8,
            'rows': [
                {
                    'acc': 'alpha', 's': 'bull', 'ms': _ms('09:00'),
                    'why': '@alpha：NVDA 財報勝預期，數據中心營收大增。',
                    'why_en': '@alpha: NVDA earnings beat estimates and data-center revenue jumped.',
                },
                {'acc': 'beta', 's': 'bull', 'why': '$AAPL 財報強。$MSFT 估值合理。', 'ms': _ms('09:10')},
                {
                    'acc': 'lone', 'ms': _ms('09:12'),
                    'why': 'https://news.example/a NVDA 指引強勁',
                    'why_en': 'NVDA guidance is strong.',
                },
                {
                    'acc': 'gap', 's': 'bull', 'ms': _ms('09:13'),
                    'why': 'NVDA 缺英文就要三語一起掉。',
                },
            ],
        }],
        'bear': [{
            't': 'QQQ', 'nr': 5, 'n_posts': 6,
            'rows': [
                {
                    'acc': 'bear1', 's': 'bear', 'ms': _ms('09:20'),
                    'why': '覺得 QQQ 走勢弱',
                    'why_en': 'QQQ looks weak.',
                },
            ],
        }],
        'split': [{
            't': 'SPCX', 'nb': 3, 'nr': 3, 'n_posts': 9,
            'rows': [
                {
                    'acc': 'sam', 's': 'bull', 'ms': _ms('09:30'),
                    'why': 'SPCX 訂單落地。',
                    'why_en': 'SPCX orders landed.',
                },
                {
                    'acc': 'sue', 's': 'bear', 'ms': _ms('09:55'),
                    'why': 'SPCX 估值太貴。',
                    'why_en': 'SPCX is too expensive.',
                },
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
    assert [r['acc'] for r in nv['bull_reasons']] == ['alpha', 'lone']
    assert 'gap' not in {r['acc'] for r in nv['bull_reasons']}
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
            accs = [r['acc'] for r in (post.get('bull_reasons') or [])]
            accs += [r['acc'] for r in (post.get('bear_reasons') or [])]
            assert [a for a, _q in _quotes(text)] == accs
            assert 'gap' not in text
            if lang != 'zh':
                assert not three_why.han_outside_tickers(text)
                assert '財報' not in text and '走勢' not in text and '估值' not in text
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
            assert not three_why.han_outside_tickers(xen['text'])
            assert '財報' not in xen['text']
            xaccs = [r['acc'] for r in (post.get('bull_reasons') or [])]
            xaccs += [r['acc'] for r in (post.get('bear_reasons') or [])]
            assert [a for a, _q in _quotes(xen['text'])] == xaccs
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
    assert sp['date'] == DAY
    assert sp['date_kst'] == DAY
    assert sp.get('why_posts_date_kst') == DAY
    three = sp.get('three_lines') or {}
    assert three.get('date') == DAY and three.get('date_kst') == DAY
    assert all(p.get('date') == DAY and p.get('date_kst') == DAY for p in why)
    assert all(a.get('date_kst') == DAY for a in atomic)
    assert hist[DAY]['why'] == [p['ticker'] for p in why]
    assert hist[DAY]['why_text']
    assert os.path.exists(os.environ['SOCIAL_HISTORY']) is False
    # An earlier day's body is not repeated. Today's own history does not ban a rewrite.
    assert three_why.prior_texts({DAY: {'why_text': list(hist[DAY]['why_text'])}}, DAY) == set()
    prev = {'2026-10-22': {'why_text': list(hist[DAY]['why_text'])}}
    kept = three_why.drop_repeated(why, three_why.prior_texts(prev, DAY))
    assert len(kept) < len(why)


def test_language_matched_summaries():
    url_beta = 'https://x.com/beta/status/111'
    url_bear = 'https://x.com/bear1/status/222'
    url_alpha = 'https://x.com/alpha/status/333'
    long_en = 'LONG ' + ('demand stays firm ' * 30)
    assert len(long_en) > 160
    daily = {
        'from': '2026-10-23T00:00',
        'to': '2026-10-23T23:59',
        'posts': 120,
        'accounts': 45,
        'bull': [{
            't': 'NVDA', 'nb': 4, 'n_posts': 8,
            'rows': [
                {
                    'acc': 'alpha', 's': 'bull', 'url': url_alpha,
                    'why': '@alpha：NVDA 財報勝預期。',
                    'why_en': '@alpha: NVDA earnings beat estimates.',
                    'ms': _ms('09:00'),
                },
                {
                    'acc': 'beta', 's': 'bull', 'url': url_beta,
                    'why': '@beta：NVDA 需求仍然強。',
                    'ms': _ms('09:10'),
                },
                {
                    'acc': 'han', 's': 'bull',
                    'why': 'NVDA 中英混在英文欄就整句唔用。',
                    'why_en': 'NVDA mixed line 但呢句有中文 unique-han-phrase',
                    'ms': _ms('09:14'),
                },
            ],
        }, {
            't': 'LONG', 'nb': 3, 'n_posts': 3,
            'rows': [{
                'acc': 'long', 's': 'bull',
                'why': 'LONG 長文只留中文。',
                'why_en': long_en,
                'ms': _ms('09:12'),
            }],
        }],
        'bear': [{
            't': 'QQQ', 'nr': 5, 'n_posts': 6,
            'rows': [{
                'acc': 'bear1', 's': 'bear', 'url': url_bear,
                'why': '覺得 QQQ 走勢弱',
                'ms': _ms('09:20'),
            }],
        }, {
            't': 'ONLY', 'nr': 2, 'n_posts': 2,
            'rows': [{'acc': 'zonly', 's': 'bear', 'why': 'ONLY 只得中文摘要', 'ms': _ms('09:25')}],
        }],
    }
    dash = {'posts': [
        {
            'url': url_alpha,
            'en_summary': 'NVDA dash should lose because the row field wins.',
            'text': 'NVDA original text is not used when why_en exists.',
        },
        {
            'url': url_beta,
            'en_summary': '@beta: NVDA demand is still strong.',
            'zh_summary': '@beta：NVDA 需求仍然強。',
            'text': 'NVDA this original text is not the English summary.',
        },
        {
            'url': url_bear,
            'en_summary': '覺得 QQQ 走勢弱',
            'text': 'QQQ looks weak into the close.',
            'zh_summary': '覺得 QQQ 走勢弱',
        },
    ]}
    sources = {
        ('zh', 'alpha'): '@alpha：NVDA 財報勝預期。',
        ('zh', 'beta'): '@beta：NVDA 需求仍然強。',
        ('zh', 'long'): 'LONG 長文只留中文。',
        ('zh', 'han'): 'NVDA 中英混在英文欄就整句唔用。',
        ('zh', 'bear1'): '覺得 QQQ 走勢弱',
        ('zh', 'zonly'): 'ONLY 只得中文摘要',
        ('en', 'alpha'): '@alpha: NVDA earnings beat estimates.',
        ('en', 'beta'): '@beta: NVDA demand is still strong.',
        ('en', 'long'): long_en,
        ('en', 'bear1'): 'QQQ looks weak into the close.',
    }
    posts = three_why.build_why_posts(daily, DAY, dash=dash)
    by = {p['ticker']: p for p in posts}
    # ONLY has Chinese only, so the shared list is empty and the name is omitted.
    assert set(by) == {'QQQ', 'NVDA', 'LONG'}
    assert 'ONLY' not in by
    nv, qqq, lng = by['NVDA'], by['QQQ'], by['LONG']
    assert [r['acc'] for r in nv['bull_reasons']] == ['alpha', 'beta']
    assert any('財報勝預期' in r['text'] for r in nv['bull_reasons'])
    assert all('中英混' not in r['text'] for r in nv['bull_reasons'])
    assert any('走勢弱' in r['text'] for r in qqq['bear_reasons'])
    assert not three_why.han_outside_tickers('Watch $NVDA and #QQQ')
    assert three_why.han_outside_tickers('看好 $NVDA')
    assert not three_why.han_outside_tickers('NVDA 실적이 예상을 웃돌았다')
    for ticker, post in by.items():
        for lang in ('en',):
            text = post['threads'][lang]['text']
            assert not three_why.han_outside_tickers(text), (ticker, lang, text)
            assert '財報' not in text and '走勢' not in text and '只得中文' not in text
            assert 'unique-han-phrase' not in text
            assert '120' in text and '45' in text
            for acc, quote in _quotes(text):
                src = _clean(sources[(lang, acc)])
                assert quote in src, (ticker, lang, acc, quote, src)
                assert '…' not in quote and not quote.endswith('...')
                assert len(quote) <= 160
        if 'x' in post:
            assert not three_why.han_outside_tickers(post['x']['en']['text'])
    en_nv = dict(_quotes(nv['threads']['en']['text']))
    assert set(en_nv) == {'alpha', 'beta'}
    assert 'NVDA earnings beat estimates.' == en_nv['alpha']
    assert 'dash should lose' not in nv['threads']['en']['text']
    assert 'Bullish reasons' in nv['threads']['en']['text']
    en_long = dict(_quotes(lng['threads']['en']['text']))
    assert set(en_long) == {'long'}
    assert en_long['long'] == long_en[:160].rstrip()
    assert en_long['long'] in long_en
    assert [r['acc'] for r in lng['bull_reasons']] == ['long']
    en_qq = qqq['threads']['en']['text']
    zh_qq = qqq['threads']['zh']['text']
    assert 'QQQ looks weak into the close.' in en_qq
    assert 'Bearish reasons' in en_qq
    assert [a for a, _q in _quotes(zh_qq)] == ['bear1']
    assert [a for a, _q in _quotes(en_qq)] == ['bear1']
    assert [r['acc'] for r in qqq['bear_reasons']] == ['bear1']


def _writeup_for_slots(daily):
    daily = dict(daily)
    daily.update({
        'originals': 77, 'reposts': 11, 'bull_views': 36, 'bear_views': 41,
        'clear_accounts': 28, 'bull_total': 2, 'bear_total': 1, 'split_total': 7,
    })
    return {
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


def test_merge_into_touches_only_three_keys():
    daily = _daily()
    daily['bull'][0]['rows'][0]['why_en'] = '@alpha: NVDA earnings beat estimates.'
    path = os.path.join(os.environ['WORK_DIR'], 'social-posts.json')
    original = {
        'date': DAY,
        'why_posts': [{'ticker': 'STALE', 'threads': {'en': {'text': '$QQQ跌破700'}}}],
        'note': 'keep-me',
        'three_lines': {'stale': True},
        'posts': {'zh': {'x': 'headline $NONE'}, 'en': {'x': 'leave this English headline'}},
        'window': '10/23 00:00 – 09:55 HKT',
        'atomic_posts': [{'ticker': 'STALE', 'lang': 'zh', 'text': 'old atomic', 'slot_kst': '09:00'}],
        'extra': {'nested': [1, {'a': 'b'}]},
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(original, f, ensure_ascii=False, indent=1)
        f.write('\n')
    hist = {}
    ordered = three_why.merge_into(path, writeup=_writeup_for_slots(daily), dash={'posts': []}, history=hist)
    loaded = json.load(open(path, encoding='utf-8'))
    assert loaded == ordered
    assert list(loaded) == [
        'date', 'date_kst', 'why_posts_date_kst', 'why_posts', 'note',
        'three_lines', 'posts', 'window', 'atomic_posts', 'extra',
    ]
    for key in ('date', 'note', 'posts', 'window', 'extra'):
        assert loaded[key] == original[key]
    assert loaded['date_kst'] == DAY
    assert loaded['why_posts_date_kst'] == DAY
    assert hist == {}
    assert os.path.exists(os.environ['SOCIAL_HISTORY']) is False
    assert loaded['three_lines'].get('stale') is not True
    assert loaded['three_lines']['date'] == DAY
    assert loaded['three_lines']['date_kst'] == DAY
    assert loaded['three_lines']['threads']['en']['text']
    assert '(vs yesterday (today so far))' not in json.dumps(loaded['three_lines'], ensure_ascii=False)
    why = loaded['why_posts']
    atomic = loaded['atomic_posts']
    assert why and atomic
    assert all(p.get('ticker') != 'STALE' for p in why)
    assert all(a.get('ticker') != 'STALE' for a in atomic)
    blob = json.dumps(why, ensure_ascii=False)
    assert '跌破' not in blob
    nv = next(p for p in why if p['ticker'] == 'NVDA')
    en = nv['threads']['en']['text']
    assert 'NVDA earnings beat estimates.' in en
    assert not three_why.han_outside_tickers(en)
    for post in why:
        for lang in ('en',):
            assert not three_why.han_outside_tickers(post['threads'][lang]['text'])
    why_t = {p['ticker'] for p in why}
    atom_t = {a.get('ticker') for a in atomic if a.get('ticker')}
    assert why_t.isdisjoint(atom_t)
    assert {p['suggested_kst'] for p in why}.isdisjoint({a['slot_kst'] for a in atomic})
    assert all(p.get('date') == DAY and p.get('date_kst') == DAY for p in why)
    assert all(a.get('date_kst') == DAY for a in atomic)
    assert isinstance(loaded['why_posts'], list) and isinstance(loaded['atomic_posts'], list)
    # A file whose recompute has no why/three/atomic loses those keys and keeps the rest.
    empty_path = os.path.join(os.environ['WORK_DIR'], 'social-empty.json')
    stale = {
        'note': 'still-here',
        'why_posts': [{'ticker': 'QQQ', 'threads': {'en': {'text': '跌破700'}}}],
        'posts': {'zh': {'x': 'unchanged'}},
    }
    with open(empty_path, 'w', encoding='utf-8') as f:
        json.dump(stale, f, ensure_ascii=False, indent=1)
        f.write('\n')
    emptied = three_why.merge_into(
        empty_path,
        writeup={'daily': {'bull': [], 'bear': [], 'split': []}, 'weekly': {}},
        dash={'posts': []},
        history={},
    )
    assert list(emptied) == ['note', 'posts']
    assert emptied['note'] == 'still-here'
    assert emptied['posts']['zh']['x'] == 'unchanged'
    assert 'why_posts' not in emptied and 'three_lines' not in emptied and 'atomic_posts' not in emptied
    assert 'date_kst' not in emptied and 'why_posts_date_kst' not in emptied


def _reason_accs(post):
    accs = [r['acc'] for r in (post.get('bull_reasons') or [])]
    accs += [r['acc'] for r in (post.get('bear_reasons') or [])]
    return accs


def test_shared_reason_list_drops_untranslated():
    """zh and en quote the same accounts in the same order.

    The list is chosen once. A row missing any language is dropped from the
    stored reasons and from every language body. $EWZ on 2026-10-27 kept
    @KawzInvests in zh and left it out of English.
    """
    daily = {
        'from': '2026-10-23T00:00',
        'to': '2026-10-23T23:59',
        'posts': 46,
        'accounts': 27,
        'split': [{
            't': 'EWZ', 'nb': 1, 'nr': 4, 'n_posts': 12,
            'rows': [
                {
                    'acc': 'LynAldenContact', 's': 'bull',
                    'why': '價值投資者正關注今晚巴西選舉引發的拋售。',
                    'why_en': 'Value investors are watching the EWZ election selloff.',
                },
                {
                    'acc': 'SJosephBurns', 's': 'bear',
                    'why': '巴西 ETF EWZ 開盤跳空下跌 30%。',
                    'why_en': 'EWZ gapped down 30% at the open.',
                },
                {
                    'acc': 'KawzInvests', 's': 'bear',
                    'why': '巴西ETF $EWZ在隔夜交易中暴跌近20%。',
                },
                {
                    'acc': 'hanmix', 's': 'bear',
                    'why': 'EWZ 中英混就不留。',
                    'why_en': 'EWZ mixed line 但有中文',
                },
                {
                    'acc': 'nozh', 's': 'bear',
                    'why_en': 'EWZ English without a Chinese summary.',
                },
                {
                    'acc': 'later', 's': 'bear',
                    'why': 'EWZ 選後賣壓持續。',
                    'why_en': 'EWZ selling continued after the election.',
                    'url': 'https://x.com/later/status/1',
                },
                {
                    'acc': 'later', 's': 'bear',
                    'why': 'EWZ 同一則再出現一次就丟掉。',
                    'why_en': 'EWZ duplicate of the same post is one reason.',
                    'url': 'https://x.com/later/status/1',
                },
            ],
        }],
    }
    posts = three_why.build_why_posts(daily, DAY)
    assert [p['ticker'] for p in posts] == ['EWZ']
    post = posts[0]
    assert post['bull'] == 1 and post['bear'] == 4 and post['accounts'] == 5
    assert [r['acc'] for r in post['bull_reasons']] == ['LynAldenContact']
    assert [r['acc'] for r in post['bear_reasons']] == ['SJosephBurns', 'later']
    stored = _reason_accs(post)
    assert stored == ['LynAldenContact', 'SJosephBurns', 'later']
    for lang in share.LANGS:
        text = post['threads'][lang]['text']
        assert [a for a, _q in _quotes(text)] == stored
        assert 'KawzInvests' not in text and 'hanmix' not in text and 'nozh' not in text
        assert '暴跌近20%' not in text and '但有中文' not in text
    if 'x' in post:
        assert [a for a, _q in _quotes(post['x']['en']['text'])] == stored
    # Same account, different post, both languages: both stay, same order.
    twice = {
        'bear': [{
            't': 'QQQ', 'nr': 2, 'n_posts': 2,
            'rows': [
                {
                    'acc': 'sue', 's': 'bear',
                    'why': 'QQQ 第一則。',
                    'why_en': 'QQQ first note.',
                    'url': 'https://x.com/sue/status/1',
                },
                {
                    'acc': 'sue', 's': 'bear',
                    'why': 'QQQ 第二則。',
                    'why_en': 'QQQ second note.',
                    'url': 'https://x.com/sue/status/2',
                },
            ],
        }],
    }
    again = three_why.build_why_posts(twice, DAY)
    assert [r['acc'] for r in again[0]['bear_reasons']] == ['sue', 'sue']
    assert [r['text'] for r in again[0]['bear_reasons']] == ['QQQ 第一則。', 'QQQ 第二則。']
    for lang in share.LANGS:
        assert [a for a, _q in _quotes(again[0]['threads'][lang]['text'])] == ['sue', 'sue']
    assert [a for a, _q in _quotes(again[0]['x']['en']['text'])] == ['sue', 'sue']
    only_zh = {
        'bull': [{
            't': 'ONLY', 'nb': 2, 'n_posts': 2,
            'rows': [{'acc': 'zonly', 's': 'bull', 'why': 'ONLY 只得中文摘要'}],
        }],
    }
    assert three_why.build_why_posts(only_zh, DAY) == []


def test_schedule_drops_same_ticker():
    why = [{'ticker': 'AAA'}, {'ticker': 'BBB'}]
    atomic = [
        {'lang': 'zh', 'ticker': 'AAA', 'slot_kst': '09:00', 'text': 'za'},
        {'lang': 'en', 'ticker': 'AAA', 'slot_kst': '09:00', 'text': 'ea'},
        {'lang': 'zh', 'slot_kst': '11:30', 'text': 'zn'},
        {'lang': 'en', 'slot_kst': '11:30', 'text': 'en'},
    ]
    why, atomic = share.schedule_why_atomic(why, atomic)
    assert [p['suggested_kst'] for p in why] == ['09:00', '11:30']
    assert all(a.get('ticker') != 'AAA' for a in atomic)
    assert {a['slot_kst'] for a in atomic} == {'14:00'}
    assert len(atomic) == 2


def main():
    test_reasons_are_real_and_labelled()
    test_language_matched_summaries()
    test_shared_reason_list_drops_untranslated()
    test_merge_into_touches_only_three_keys()
    test_atomic_slots_do_not_share_ticker_or_time()
    test_schedule_drops_same_ticker()
    print('test_why_posts: reasons, labels, UTM, atomic slots ok')


if __name__ == '__main__':
    main()
