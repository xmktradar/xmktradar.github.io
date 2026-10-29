"""Instagram plan (Tim, 2026-10-29): Chinese only on Instagram and Threads, at most 2 earnings picture posts a day there,
and every Chinese Instagram caption ends with a genuine question that never asks for likes or shares.
Checks tools/ig_plan.py on fixtures and on every post file in data/ (after applying it to a copy).

  python3 tools/test_ig_plan.py
"""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ig_plan  # noqa: E402
from humanize import BRAND, CANTONESE, DISC, humanize  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ZH = humanize('今天最多人看多 $MU（7 個帳號）\n\n・7 個帳號： $MU\n#美股 #MU', 'zh', 'post', 'instagram')
EN = humanize('Most bullish: $MU (7 accounts)\n#StockMarket #MU', 'en', 'post', 'instagram')


def _lines(text):
    return [ln.strip() for ln in text.split('\n')]


def test_questions_are_clean():
    for kind, qs in ig_plan.QUESTIONS.items():
        for q in qs:
            assert not ig_plan.BAIT.search(q), (kind, q)
            assert not CANTONESE.search(q), (kind, q)
            assert q.endswith('？') and '你' in q, (kind, q)


def test_caption():
    out = ig_plan.add_question(ZH)
    lines = _lines(out)
    bi = next(i for i, ln in enumerate(lines) if ln in BRAND['zh'])
    assert lines[bi - 1] == '' and lines[bi - 2].endswith('？'), out
    assert '$MU' in lines[bi - 2], out
    assert lines.count(DISC['zh']) == 1
    assert ig_plan.add_question(out) == out  # idempotent
    assert humanize(out, 'zh', 'post', 'instagram') == out  # humanize keeps it
    asked = ZH.replace('今天最多人看多 $MU（7 個帳號）', '今天 $MU 最分歧，你怎麼看？')
    assert ig_plan.add_question(asked) == asked  # already asks the reader
    assert ig_plan.add_question('#美股 #MU') == '#美股 #MU'  # not a full caption
    assert '財報' in ig_plan.question_for('$NVDA 財報（FY2027 Q3）｜收入 US$500 億') or \
        '成績單' in ig_plan.question_for('$NVDA 財報（FY2027 Q3）｜收入 US$500 億')


def test_tree():
    data = {'posts': {'zh': {'instagram': ZH, 'x': ZH, 'story': '#美股 #MU'},
                      'en': {'instagram': EN, 'x': EN, 'threads': EN, 'story': '#StockMarket #MU'}},
            'three_lines': {'instagram': {'zh': {'text': ZH}, 'en': {'text': EN}}, 'x': {'en': {'text': EN}},
                            'threads': {'zh': {'text': ZH, 'url': ''}, 'en': {'text': EN, 'url': 'https://thecrowdtape.com/en/'}}},
            'why_posts': [{'threads': {'zh': {'text': ZH}, 'en': {'text': EN}}, 'x': {'en': {'text': EN}}}],
            'ig_threads_daily': {'zh': {'text_post': {'field': 'posts.zh.threads'}}, 'en': {'text_post': {'field': 'posts.en.threads'}}},
            'ig_reel': {'caption': {'zh': ZH, 'en': EN}},
            'images': {'en': ['https://thecrowdtape.com/og/a.jpg']}}
    ig_plan.apply(data)
    p = data['posts']
    assert p['en']['instagram'] == '' and p['en']['story'] == ''
    assert p['en']['x'] == EN and p['en']['threads'] == ''  # X keeps English, Threads is Chinese only
    assert data['three_lines']['threads']['en']['text'] == '' and data['three_lines']['threads']['zh']['text'] == ZH
    assert data['three_lines']['threads']['en']['url'] == 'https://thecrowdtape.com/en/'
    assert data['why_posts'][0]['threads']['en']['text'] == '' and data['why_posts'][0]['x']['en']['text'] == EN
    assert data['why_posts'][0]['threads']['zh']['text'] == ZH  # zh Threads gets no Instagram question
    assert list(data['ig_threads_daily']) == ['zh'] and data['threads_langs'] == ['zh']
    assert p['zh']['x'] == ZH and p['zh']['story'] == '#美股 #MU'  # only Instagram captions get the question
    assert p['zh']['instagram'] != ZH and '？' in p['zh']['instagram']
    assert data['three_lines']['instagram']['en']['text'] == ''
    assert data['three_lines']['x']['en']['text'] == EN
    assert data['ig_reel']['caption']['en'] == '' and '？' in data['ig_reel']['caption']['zh']
    assert data['images']['en'] == ['https://thecrowdtape.com/og/a.jpg']
    assert data['ig_langs'] == ['zh']
    again = copy.deepcopy(data)
    ig_plan.apply(again)
    assert again == data
    assert ig_plan.problems(data) == []
    bad = copy.deepcopy(data)
    bad['posts']['en']['threads'] = EN
    assert ig_plan.problems(bad) == ['.posts.en.threads: English Threads text']


def _item(t, mcap):
    return {'t': t, 'mcap': mcap, 'posts': {'zh': {'instagram': ZH}, 'en': {'instagram': EN, 'x': EN}}}


def test_earnings_cap():
    ep = {'slots': {'1000': {'day': '2026-11-02', 'items': [_item('KO', 300), _item('MSFT', 3900), _item('PG', 360)]}},
          'video': {'day': '2026-11-02', 'posts': {'zh': {'instagram': ZH}, 'en': {'instagram': EN}}}}
    ig_plan.apply(ep, 'data/earnings-posts.json')
    assert [i['ig'] for i in ep['slots']['1000']['items']] == [False, True, True]  # 2 largest
    assert ep['slots']['1000']['items'][0]['posts']['zh']['instagram']  # caption kept (the video copies it)
    assert ep['video']['posts']['en']['instagram'] == ''
    # The 22:00 slot the same day: the morning used the 2, so none
    ep['slots']['2200'] = {'day': '2026-11-02', 'items': [_item('NVDA', 5000)]}
    ig_plan.apply(ep, 'data/earnings-posts.json')
    assert ep['slots']['2200']['items'][0]['ig'] is False
    assert [i['ig'] for i in ep['slots']['1000']['items']] == [False, True, True]  # marks kept
    # Next day's morning: fresh quota; a 1-item morning leaves 1 for the evening
    ep['slots']['1000'] = {'day': '2026-11-03', 'items': [_item('AAPL', 4000)]}
    ep['slots']['2200'] = {'day': '2026-11-03', 'items': [_item('V', 600), _item('MA', 500)]}
    ig_plan.apply(ep, 'data/earnings-posts.json')
    assert ep['slots']['1000']['items'][0]['ig'] is True
    assert [i['ig'] for i in ep['slots']['2200']['items']] == [True, False]
    assert ig_plan.problems(ep, 'data/earnings-posts.json') == []
    bad = copy.deepcopy(ep)
    for i in bad['slots']['2200']['items']:
        i['ig'] = True
    assert ig_plan.problems(bad, 'data/earnings-posts.json')


def test_real_files():
    n = 0
    for name in ig_plan.FILES:
        path = os.path.join(ROOT, name)
        if not os.path.exists(path):
            continue
        data = ig_plan.apply(json.load(open(path, encoding='utf-8')), name)
        assert ig_plan.problems(data, name) == [], (name, ig_plan.problems(data, name)[:5])
        assert ig_plan.problems(ig_plan.apply(copy.deepcopy(data), name), name) == []
        n += 1
    assert n >= 2, n


def main():
    test_questions_are_clean()
    test_caption()
    test_tree()
    test_earnings_cap()
    test_real_files()
    print('test_ig_plan: Instagram + Threads Chinese only, earnings <=2 a day, one clean question per zh caption ok')


if __name__ == '__main__':
    main()
