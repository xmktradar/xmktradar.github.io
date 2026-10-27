"""hot_stock and discussion: real rows only, no repeat, poll, half the links in first_comment.

Offline fixtures. Tickers come from daily bull/bear/split rows and must differ from the
top5 leads, the main headline, x_trilingual, each other, and hot_stock/discussion names
from the previous 7 days. Quotes stay verbatim on zh. en keeps handles, tickers and
counts. Run from the repo root: python3 tools/test_slots.py
"""
import inspect
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['WORK_DIR'] = tempfile.mkdtemp(prefix='slots-test-')
os.environ['SOCIAL_HISTORY'] = os.path.join(os.environ['WORK_DIR'], 'social-history.json')

import share  # noqa: E402

DAY = '2026-10-23'
URL = 'https://thecrowdtape.com'


def _row(t, nb=None, nr=None, n_posts=1, why='觀點沒有數字', acc='someone'):
    row = {'t': t, 'n_posts': n_posts, 'rows': [{'acc': acc, 'why': why}]}
    if nb is not None:
        row['nb'] = nb
    if nr is not None:
        row['nr'] = nr
    return row


def _daily():
    return {
        'from': '2026-10-23T00:00',
        'to': '2026-10-23T23:59',
        'posts': 88,
        'accounts': 34,
        'bull': [
            _row('RSP', nb=2, n_posts=7, acc='leadbull'),
            _row('WMT', nb=2, n_posts=2, acc='retail'),
        ],
        'bear': [_row('QQQ', nr=4, n_posts=6, acc='leadbear')],
        'split': [
            _row('SPCX', nb=4, nr=3, n_posts=10, why='ZQXQZX 原文開始', acc='chamath'),
            _row('SPY', nb=2, nr=1, n_posts=9, why='另一段原文', acc='other'),
            _row('BE', nb=1, nr=2, n_posts=5, why='第三段', acc='third'),
            _row('GLD', nb=1, nr=1, n_posts=3, why='第四段', acc='fourth'),
        ],
    }


def _sp():
    return {
        'date': '2026-10-22',
        'posts': {'zh': {'x': '$WMT 標題\n$MSFT 後面'}},
        'x_trilingual': {'premarket': {'image_ticker': 'WMT', 'text': 'premarket $WMT'}},
        'top5': {
            'bull': [{'t': 'RSP', 'n': 2}, {'t': 'WMT', 'n': 2}],
            'bear': [{'t': 'QQQ', 'n': 4}, {'t': 'MRNA', 'n': 3}],
        },
    }


def _bodies(slot):
    out = []
    for lang in share.LANGS:
        for plat in ('threads', 'facebook'):
            out.append((lang, plat, slot['posts'][lang][plat]))
    return out


def _assert_common(slot, campaign, ticker):
    assert slot['format'] in ('image_card', 'carousel', 'text_question', 'poll')
    assert slot['ticker'] == ticker
    assert slot['date'] == DAY
    linked = 0
    total = 0
    for lang in share.LANGS:
        posts = slot['posts'][lang]
        assert set(posts['has_link']) == {'threads', 'facebook'}
        for plat in ('threads', 'facebook'):
            total += 1
            text = posts[plat]
            assert URL not in text, (lang, plat)
            assert share.SHORT[lang]['disc'] in text
            assert len(text) <= 500, (lang, plat, len(text))
            tag = {'zh': '#美股', 'en': '#StockMarket'}[lang]
            assert tag in text
            assert f'#{ticker}' in text
            assert text.strip().split('\n')[-1].startswith('#')
            if posts['has_link'][plat]:
                linked += 1
                fc = posts['first_comment'][plat]
                assert fc.startswith(share.SHORT[lang]['live'])
                assert f'/{lang}/stock/{ticker}/?' in fc
                assert f'utm_source={plat}&utm_medium=social&utm_campaign={campaign}' in fc
            else:
                assert plat not in (posts.get('first_comment') or {})
    assert linked == total // 2 == 2, (linked, total)


def test_content_tokens():
    text = 'on 2026-10-23 at 09:00 see 10/23 and Oct 23 plus 2027 and 88'
    assert share.content_numbers(text) == {88}
    assert share.content_numbers('https://thecrowdtape.com/zh/?x=12 leftover 3') == {3}
    assert share.content_tickers('$121 $SPCX $spy') == {'SPCX', 'SPY'}
    assert share.top5_lead_tickers(_sp()['top5']) == ['RSP', 'QQQ']
    assert share.headline_ticker(_sp()) == 'WMT'
    assert share.xtri_tickers(_sp()) == ['WMT']


def test_no_repeat_including_history():
    daily = _daily()
    blocked = share.blocked_tickers_for_slots(_sp(), {}, DAY)
    assert blocked == {'RSP', 'QQQ', 'WMT'}
    hot, talk = share.select_slot_rows(daily, blocked)
    assert hot['t'] == 'SPCX' and talk['t'] == 'SPY'
    assert hot['t'] != talk['t']

    hist = {'2026-10-22': {'hot_stock': ['SPCX'], 'discussion': ['SPY']}}
    blocked2 = share.blocked_tickers_for_slots(_sp(), hist, DAY)
    assert {'SPCX', 'SPY'} <= blocked2
    hot2, talk2 = share.select_slot_rows(daily, blocked2)
    assert hot2['t'] == 'BE' and talk2['t'] == 'GLD'
    assert 'SPCX' not in {hot2['t'], talk2['t']}

    # Same calendar day does not block a re-pick. Eight days back does not either.
    assert 'SPCX' not in share.recent_slot_tickers({DAY: {'hot_stock': ['SPCX']}}, DAY)
    assert 'EDGE' in share.recent_slot_tickers({'2026-10-16': {'discussion': ['EDGE']}}, DAY)
    assert 'OUT' not in share.recent_slot_tickers({'2026-10-15': {'hot_stock': ['OUT']}}, DAY)

    bare = {'split': [{'t': 'AAA', 'nb': 9, 'rows': []}]}
    hot3, talk3 = share.select_slot_rows(bare, set())
    assert hot3 is None and talk3['t'] == 'AAA'
    assert share.build_hot_stock(hot3, DAY) is None
    assert share.build_discussion({'t': 'AAA', 'rows': []}, DAY) is None


def test_hot_and_discussion_shape():
    daily = _daily()
    hot_row, talk_row = share.select_slot_rows(daily, {'RSP', 'QQQ', 'WMT'})
    hot = share.build_hot_stock(hot_row, DAY)
    talk = share.build_discussion(talk_row, DAY)
    assert hot['format'] == 'carousel'
    assert talk['format'] == 'poll'
    _assert_common(hot, 'hot_stock', 'SPCX')
    _assert_common(talk, 'discussion', 'SPY')
    # zh keeps the verbatim start of why. en does not translate it.
    zh = hot['posts']['zh']['threads']
    assert 'ZQXQZX 原文開始' in zh
    assert '@chamath' in zh
    for lang in ('en',):
        body = hot['posts'][lang]['threads']
        assert 'ZQXQZX' not in body and '原文開始' not in body
        assert '@chamath' in body
        assert '$SPCX' in body
        assert '4' in body and '3' in body
    assert hot['posts']['en']['threads'] == hot['posts']['en']['facebook']
    # Poll: question plus 2–4 options, translated. Counts are the row's real nb/nr.
    assert talk['poll']['zh'] == {'question': '你點睇 $SPY？', 'options': ['看好', '看淡', '中性']}
    assert talk['poll']['en'] == {
        'question': 'What do you think of $SPY?',
        'options': ['Bullish', 'Bearish', 'Neutral'],
    }
    for lang in share.LANGS:
        poll = talk['posts'][lang]['poll']
        assert poll == talk['poll'][lang]
        assert 2 <= len(poll['options']) <= 4
        assert poll['question'] in talk['posts'][lang]['threads']
    en = talk['posts']['en']['threads']
    assert '2 bullish accounts' in en and '1 bearish account' in en
    assert '1 bearish accounts' not in en
    # A long quote is trimmed, not dropped, and the Threads body stays within 500.
    long_row = _row('LONG', nb=2, nr=0, why='ZQXQZX' + ('很長' * 800), acc='longacc')
    long = share.build_hot_stock(long_row, DAY)
    assert long['posts']['zh']['threads'].startswith('今日熱門 $LONG') or 'ZQXQZX' in long['posts']['zh']['threads']
    assert 'ZQXQZX' in long['posts']['zh']['threads']
    assert len(long['posts']['zh']['threads']) <= 500
    assert 'ZQXQZX' not in long['posts']['en']['facebook']
    # Bodies of the two slots are not the same string.
    hot_text = {share._norm_text(t) for _l, _p, t in _bodies(hot)}
    talk_text = {share._norm_text(t) for _l, _p, t in _bodies(talk)}
    assert hot_text.isdisjoint(talk_text)


def test_attach_omits_and_guards():
    daily = _daily()
    hist = {}
    sp = _sp()
    share.attach_market_slots(sp, DAY, {'daily': daily}, hist, save=False)
    assert sp['hot_stock']['ticker'] == 'SPCX'
    assert sp['discussion']['ticker'] == 'SPY'
    assert hist[DAY]['hot_stock'] == ['SPCX']
    assert hist[DAY]['discussion'] == ['SPY']
    assert hist[DAY]['top5'] == ['RSP', 'QQQ']
    assert os.path.exists(os.environ['SOCIAL_HISTORY']) is False

    # An exact copy of another slot's body drops hot_stock. discussion stays.
    clash = _sp()
    preview = share.build_hot_stock(share.select_slot_rows(daily, {'RSP', 'QQQ', 'WMT'})[0], DAY)
    clash['posts']['en'] = {'threads': preview['posts']['zh']['threads']}
    share.attach_market_slots(clash, DAY, {'daily': daily}, {}, save=False)
    assert 'hot_stock' not in clash
    assert clash['discussion']['ticker'] == 'SPY'
    problems = share.guard_slots({
        'hot_stock': preview,
        'posts': {'zh': {'x': preview['posts']['zh']['threads']}},
    })
    assert any('duplicate text' in p for p in problems)

    # Nothing eligible: both slots stay absent.
    only = {'bull': [_row('RSP', nb=2)]}
    quiet = _sp()
    share.attach_market_slots(quiet, DAY, {'daily': only}, {}, save=False)
    assert 'hot_stock' not in quiet and 'discussion' not in quiet


def test_history_keeps_14():
    path = os.path.join(os.environ['WORK_DIR'], 'hist.json')
    hist = {}
    from datetime import datetime, timedelta
    end = datetime(2026, 10, 23)
    for i in range(20):
        d = (end - timedelta(days=19 - i)).strftime('%Y-%m-%d')
        hist[d] = {'hot_stock': ['OLD'], 'discussion': []}
    share.save_social_history(hist, path)
    loaded = share.load_social_history(path)
    assert len(loaded) == 14
    assert DAY in loaded
    assert (end - timedelta(days=19)).strftime('%Y-%m-%d') not in loaded


def test_social_actions_and_main_gate():
    # Friday at/after 07:00 writes the weekday branch. Earlier, or already written, does not.
    assert share.social_actions(DAY, {'date': '2026-10-22'}, 7, True, False) == {
        'weekday': True, 'weekend': False}
    assert share.social_actions(DAY, {'date': '2026-10-22'}, 6, True, False) == {
        'weekday': False, 'weekend': False}
    assert share.social_actions(DAY, {'date': DAY}, 9, True, False)['weekday'] is False
    assert share.social_actions(DAY, {'date': DAY}, 9, True, True)['weekday'] is True
    assert share.social_actions(DAY, {}, 9, False, False) == {'weekday': False, 'weekend': False}
    # A weekday holiday is not a weekend, and it does not run unless forced.
    holiday = '2026-11-26'
    assert share._is_weekend(holiday) is False
    assert share.social_actions(holiday, {'date': '2026-11-25'}, 8, True, False) == {
        'weekday': False, 'weekend': False}
    assert share.social_actions(holiday, {'date': '2026-11-25'}, 8, True, False, force=True)['weekday'] is True
    # Saturday and Sunday run the weekend branch without a trading-day post list.
    for day in ('2026-10-24', '2026-10-25'):
        assert share._is_weekend(day) is True
        assert share.social_actions(day, {}, 7, False, False) == {'weekday': False, 'weekend': True}
        assert share.social_actions(day, {}, 6, False, False)['weekend'] is False
        done = {'weekend': {'date': day}}
        assert share.social_actions(day, done, 9, False, False)['weekend'] is False
        assert share.social_actions(day, done, 9, False, False, force=True)['weekend'] is True
    src = inspect.getsource(share.main)
    assert 'social_actions(' in src
    assert 'attach_market_slots(' in src
    assert 'attach_weekend_slots(' in src


def test_carry_intraday_same_date():
    """A weekday rebuild keeps today's intraday block and drops a different date."""
    prev = {
        'date': '2026-10-22',
        'posts': {'en': {'x': 'old'}},
        'intraday': {
            'date': DAY,
            'generated_at': '2026-10-23T09:35:00-04:00',
            'slots': {'intraday_open': {'post_et': '09:45', 'x': {'en': {'text': 'Open tape'}}}},
        },
    }
    rebuilt = {'date': DAY, 'posts': {'en': {'x': 'rebuilt'}}, 'top5': {'bull': [{'t': 'RSP'}]}}
    share.carry_intraday(rebuilt, prev, DAY)
    assert rebuilt['posts']['en']['x'] == 'rebuilt'
    assert rebuilt['top5']['bull'][0]['t'] == 'RSP'
    assert rebuilt['intraday']['slots']['intraday_open']['x']['en']['text'] == 'Open tape'
    # A timestamp date still counts as that day.
    prev['intraday']['date'] = '2026-10-23T09:35:00-04:00'
    again = {'date': DAY}
    share.carry_intraday(again, prev, DAY)
    assert again['intraday']['slots']['intraday_open']['post_et'] == '09:45'
    stale = {'date': '2026-10-22', 'intraday': {'date': '2026-10-22', 'slots': {'intraday_close': {'post_et': '15:40'}}}}
    fresh = {'date': DAY, 'posts': {'en': {'x': 'rebuilt'}}}
    share.carry_intraday(fresh, stale, DAY)
    assert 'intraday' not in fresh
    share.carry_intraday(fresh, {'date': DAY}, DAY)
    assert 'intraday' not in fresh
    share.carry_intraday(fresh, {'intraday': {'slots': {}}}, DAY)
    assert 'intraday' not in fresh
    src = inspect.getsource(share.main)
    rebuild_at = src.find("sp = {'date': day")
    carry_at = src.find('carry_intraday(')
    write_at = src.find("write_json('data/social-posts.json'", rebuild_at)
    assert 0 <= rebuild_at < carry_at < write_at


def main():
    test_content_tokens()
    test_no_repeat_including_history()
    test_hot_and_discussion_shape()
    test_attach_omits_and_guards()
    test_history_keeps_14()
    test_social_actions_and_main_gate()
    test_carry_intraday_same_date()
    print('test_slots: hot_stock, discussion, history, poll, links, intraday carry ok')


if __name__ == '__main__':
    main()
