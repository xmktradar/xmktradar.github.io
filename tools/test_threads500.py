"""Threads captions stay within 500 Unicode code points.

Threads counts len() (code points) and counts every URL in full, not as 23
the way X does. fit_threads trims a too-long post in order: shorten then drop
the 💬 quote, drop the ☕ donate line (one language link left), drop the 🔥
streak, drop the ⚖️ split, then ticker lines from the bottom. The headline,
the disclaimer and the hashtag line stay.

Run from pages/: python3 tools/test_threads500.py
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import carousel  # noqa: E402
import share  # noqa: E402
from utm import tag_posts  # noqa: E402

URL_RE = re.compile(r'https?://\S+')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS = os.path.join(ROOT, 'data', 'social-posts.json')

LIVE = {
    'zh': 'https://thecrowdtape.com/zh/?utm_source=threads&utm_medium=post&utm_campaign=daily',
    'en': 'https://thecrowdtape.com/en/?utm_source=threads&utm_medium=post&utm_campaign=daily',
    'ko': 'https://thecrowdtape.com/ko/?utm_source=threads&utm_medium=post&utm_campaign=daily',
}
TAG = {'zh': '#美股', 'en': '#StockMarket', 'ko': '#미국주식'}
HEAD = {
    'zh': '10/21 X 大神共識快照： $SPCX 8 個帳號一齊睇好 📊',
    'en': 'Oct 21 · What top X accounts agree on: $SPCX, 8 accounts bullish 📊',
    'ko': '10/21 X 인플루언서 컨센서스: $SPCX 계정 8개 동시 강세 📊',
}
WIN = {
    'zh': '數據範圍：10/21 00:21 – 10/21 06:10 HKT',
    'en': 'Data window: 10/21 00:21 – 10/21 06:10 HKT',
    'ko': '데이터 범위: 10/21 00:21 – 10/21 06:10 HKT',
}
BLUE = {
    'zh': '🔵 共同看多：4 隻・共同看空：0 隻',
    'en': '🔵 Joint bullish: 4 · Joint bearish: 0',
    'ko': '🔵 공동 강세: 4개・공동 약세: 0개',
}


def _ticker(lang, n, names):
    if lang == 'zh':
        return f'・{n} 個帳號： ' + '、 '.join(f'${t}' for t in names)
    if lang == 'ko':
        return f'・계정 {n}개: ' + ', '.join(f'${t}' for t in names)
    return f'・{n} accounts: ' + ', '.join(f'${t}' for t in names)


def _quote(lang, text):
    if lang == 'zh':
        return f'💬 @KobeissiLetter：{text}'
    return f'💬 @KobeissiLetter: "{text}"'


def _split(lang):
    if lang == 'zh':
        return '⚖️ 好淡分歧： $CRWV（2 好 2 淡）、 $COIN（3 好 3 淡）、 $MARA（2 好 2 淡）'
    if lang == 'ko':
        return '⚖️ 의견 엇갈림: $CRWV (강세 2 / 약세 2), $COIN (강세 3 / 약세 3), $MARA (강세 2 / 약세 2)'
    return '⚖️ Split views: $CRWV (2 bull / 2 bear), $COIN (3 bull / 3 bear), $MARA (2 bull / 2 bear)'


def _streak(lang):
    if lang == 'zh':
        return '🔥 連續 2 日或以上都喺共同看多： $AMZN（6 日）、 $TSLA（5 日）、 $NVDA（4 日）、 $META（3 日）、 $AAPL（2 日）'
    if lang == 'ko':
        return '🔥 2일 이상 연속 공동 강세: $AMZN (6일), $TSLA (5일), $NVDA (4일), $META (3일), $AAPL (2일)'
    return '🔥 Joint bullish 2+ days in a row: $AMZN (6d), $TSLA (5d), $NVDA (4d), $META (3d), $AAPL (2d)'


def build(lang, n_rows, quote_text, donate=True, streak=True, split=True, n_names=4):
    """A daily Threads post in the same shape caption() writes, with full URLs."""
    short = share.SHORT[lang]
    rows = [BLUE[lang]]
    names = ['SPCX', 'TSLA', 'AMZN', 'NVDA', 'META', 'AAPL', 'MSFT', 'GOOG', 'AMD', 'AVGO'][:n_names]
    for i in range(n_rows):
        rows.append(_ticker(lang, n_rows - i + 1, names))
    blocks = [HEAD[lang], WIN[lang], '\n'.join(rows)]
    if split:
        blocks.append(_split(lang))
    if streak:
        blocks.append(_streak(lang))
    if quote_text is not None:
        blocks.append(_quote(lang, quote_text))
    foot = [f"{short['live']}{LIVE[lang]}"]
    if donate:
        foot.append(f"{short['give']}{LIVE[lang]}#donate")
    foot.append(short['disc'])
    blocks.append('\n'.join(foot))
    blocks.append(TAG[lang])
    return '\n\n'.join(blocks)


def _lines(text):
    return text.split('\n')


def assert_kept(lang, src, out):
    head = src.split('\n', 1)[0]
    assert out.split('\n', 1)[0] == head, (lang, out.split('\n', 1)[0], head)
    assert share.SHORT[lang]['disc'] in _lines(out), (lang, out)
    assert TAG[lang] in _lines(out), (lang, _lines(out)[-3:])
    assert len(out) <= 500, (lang, len(out))
    urls = URL_RE.findall(out)
    assert len(urls) <= 1, (lang, urls)
    if urls:
        assert f'/{lang}/' in urls[0], (lang, urls)
        assert '#donate' not in urls[0], (lang, urls)
        assert urls[0] == LIVE[lang], (lang, urls)
    return urls


def test_short_is_unchanged():
    for lang in share.LANGS:
        text = build(lang, 1, 'Hi', donate=True, streak=False, split=False, n_names=1)
        assert len(text) <= 500, (lang, len(text))
        assert share.fit_threads(text, lang) == text
    data = json.load(open(POSTS, encoding='utf-8'))
    for lang in share.LANGS:
        raw = data['posts'][lang]['threads']
        assert len(raw) <= 500, (lang, len(raw))
        assert share.fit_threads(raw, lang) == raw
        slot = data['slots']['1230']['posts'][lang]['threads']
        assert len(slot) <= 500
        assert share.fit_threads(slot, lang) == slot


def _with_quote(lang, base, body):
    """Insert a 💬 quote paragraph in front of the live-numbers line."""
    parts = base.split('\n\n')
    live = share.SHORT[lang]['live'].strip()
    at = next(i for i, p in enumerate(parts) if live in p)
    parts.insert(at, _quote(lang, body))
    return '\n\n'.join(parts)


def test_quote_shortened_before_other_cuts():
    """A little over the limit: shorten the quote, keep donate, streak, split and every ticker line."""
    split = {'zh': '⚖️ 好淡分歧： $CRWV（2 好 2 淡）', 'en': '⚖️ Split: $CRWV', 'ko': '⚖️ 의견 엇갈림: $CRWV'}
    streak = {'zh': '🔥 連續 2 日或以上都喺共同看多： $AMZN（3 日）', 'en': '🔥 Streak: $AMZN', 'ko': '🔥 연속 강세: $AMZN'}
    for lang in share.LANGS:
        base = build(lang, 1, None, donate=True, streak=False, split=False, n_names=1)
        parts = base.split('\n\n')
        parts.insert(-2, split[lang])
        parts.insert(-2, streak[lang])
        base = '\n\n'.join(parts)
        assert len(base) < 500, (lang, len(base))
        filler = '甲' if lang == 'zh' else ('가' if lang == 'ko' else 'market ')
        # Long enough to cross 500, short enough that a truncated quote still fits.
        body = filler * (560 - len(base))
        text = _with_quote(lang, base, body)
        assert len(text) > 500, (lang, len(text))
        out = share.fit_threads(text, lang)
        assert len(out) <= 500, (lang, len(out))
        assert out.split('\n', 1)[0] == text.split('\n', 1)[0]
        assert share.SHORT[lang]['disc'] in _lines(out)
        assert TAG[lang] in _lines(out)
        assert '💬 @KobeissiLetter' in out
        assert '…' in out
        assert '☕' in out
        assert '🔥' in out
        assert '⚖' in out
        assert out.count('\n・') == text.count('\n・')
        urls = URL_RE.findall(out)
        assert urls == [LIVE[lang], LIVE[lang] + '#donate'], (lang, urls)


def test_long_drops_quote_then_donate_keeps_rest():
    """Quote cannot close the gap: drop it, then the donate line. Streak and split stay."""
    split = {'zh': '⚖️ 好淡分歧： $CRWV（2 好 2 淡）', 'en': '⚖️ Split: $CRWV', 'ko': '⚖️ 의견 엇갈림: $CRWV'}
    streak = {'zh': '🔥 連續 2 日或以上都喺共同看多： $AMZN（3 日）', 'en': '🔥 Streak: $AMZN', 'ko': '🔥 연속 강세: $AMZN'}
    for lang in share.LANGS:
        base = build(lang, 1, None, donate=True, streak=False, split=False, n_names=1)
        parts = base.split('\n\n')
        parts.insert(-2, split[lang])
        parts.insert(-2, streak[lang])
        # Pad the streak until the donate line is what puts the post over 500.
        while True:
            trial = '\n\n'.join(parts)
            donate_off = trial.replace(f"\n{share.SHORT[lang]['give']}{LIVE[lang]}#donate", '')
            if len(trial) > 530 and len(donate_off) <= 500:
                break
            if len(donate_off) > 500:
                raise AssertionError((lang, len(trial), len(donate_off)))
            parts[parts.index(streak[lang])] = streak[lang] = streak[lang] + ('。' if lang == 'zh' else '가' if lang == 'ko' else ' x')
        text = _with_quote(lang, '\n\n'.join(parts), '短' if lang == 'zh' else 'x')
        no_quote = '\n\n'.join(parts)
        assert len(text) > 500 and len(no_quote) > 500, (lang, len(text), len(no_quote))
        out = share.fit_threads(text, lang)
        urls = assert_kept(lang, text, out)
        assert urls == [LIVE[lang]]
        assert '💬 @KobeissiLetter' not in out
        assert '☕' not in out
        assert '#donate' not in out
        assert '🔥' in out
        assert '⚖' in out


def test_then_streak_split_and_ticker_lines():
    """Past donate: drop 🔥, then ⚖️, then ・ lines from the bottom. The first ticker line stays."""
    for lang in share.LANGS:
        text = build(lang, 10, '甲' * 30 if lang != 'en' else 'word ' * 30, n_names=6)
        assert len(text) > 500
        out = share.fit_threads(text, lang)
        urls = assert_kept(lang, text, out)
        assert urls == [LIVE[lang]], (lang, urls)
        assert '💬' not in out
        assert '☕' not in out
        assert '🔥' not in out
        assert '⚖' not in out
        src_tickers = [ln for ln in _lines(text) if ln.startswith('・')]
        out_tickers = [ln for ln in _lines(out) if ln.startswith('・')]
        assert out_tickers, (lang, out)
        assert len(out_tickers) < len(src_tickers)
        assert out_tickers[0] == src_tickers[0]
        assert src_tickers[-1] not in out_tickers
        assert share.fit_threads(out, lang) == out


def test_json_style_samples():
    """Long posts built from today's data/social-posts.json threads text."""
    data = json.load(open(POSTS, encoding='utf-8'))
    for lang in share.LANGS:
        raw = data['posts'][lang]['threads']
        head = raw.split('\n', 1)[0]
        tag = raw.strip().split('\n')[-1]
        assert tag == TAG[lang]
        assert head == HEAD[lang] or head.startswith(head[:8])
        parts = raw.split('\n\n')
        live_at = next(i for i, p in enumerate(parts) if share.SHORT[lang]['live'].strip() in p)
        bullets = parts[2]
        extra = '\n'.join(_ticker(lang, n, ['SPCX', 'TSLA', 'AMZN', 'NVDA', 'META', 'AAPL']) for n in range(12, 2, -1))
        parts[2] = bullets + '\n' + extra
        quote = _quote(lang, ('這段引述很長，講合併同超智能。' if lang == 'zh' else
                              '속보 인용문이 아주 깁니다. ' if lang == 'ko' else
                              'A very long quote about the merger and the accounts. ') * 8)
        url = URL_RE.search(parts[live_at]).group(0)
        disc = share.SHORT[lang]['disc']
        parts[live_at] = '\n'.join([
            f"{share.SHORT[lang]['live']}{url}",
            f"{share.SHORT[lang]['give']}{url}#donate",
            disc])
        parts.insert(live_at, quote)
        text = '\n\n'.join(parts)
        assert len(text) > 500, (lang, len(text))
        out = share.fit_threads(text, lang)
        assert len(out) <= 500, (lang, len(out))
        assert out.split('\n', 1)[0] == head
        assert tag in _lines(out)
        assert disc in _lines(out)
        urls = URL_RE.findall(out)
        assert len(urls) == 1, (lang, urls)
        assert urls[0] == url
        assert f'/{lang}/' in urls[0]
        assert '#donate' not in out
        assert '☕' not in out
        # Hashtag line is the topic tag, not a ticker hash.
        assert any(ln.strip() == tag for ln in _lines(out))


def test_generators_and_utm():
    tickers = ['NVDA', 'AAPL', 'TSLA', 'AMZN', 'META', 'MSFT', 'GOOG', 'AMD', 'AVGO', 'NFLX', 'COST', 'CRM']
    items = [{'t': t, 'n': 8, 'bull': 6, 'bear': 1, 'streak': 4} for t in tickers]
    s = {'bull': [{'t': t, 'nb': 6, 'nr': 1} for t in tickers],
         'bear': [{'t': 'BA', 'nr': 4}, {'t': 'DIS', 'nr': 3}],
         'split': [{'t': 'COIN', 'nb': 3, 'nr': 3}, {'t': 'MARA', 'nb': 2, 'nr': 2}],
         'accounts': 90, 'tickers': 40}
    quote = {'acc': 'KobeissiLetter', 'text': 'BREAKING ' + ('merger committee ' * 30)}
    win = '10/21 00:21 – 10/21 06:10 HKT'
    posts = {}
    for lang in share.LANGS:
        cap = share.caption(lang, '2026-10-21', s, items, win, quote)
        assert len(cap['threads']) <= 500, (lang, len(cap['threads']))
        assert cap['threads'].split('\n', 1)[0] == cap['instagram'].split('\n', 1)[0]
        assert TAG[lang] in cap['threads'].split('\n')
        assert share.SHORT[lang]['disc'] in cap['threads']
        posts[lang] = {'threads': cap['threads'], 'x': cap['x']}
        body = ['\n'.join(f'🟢 @acc{n}：' + ('理由' * 40) for n in range(6)), '你企邊邊？留言話我知 👇']
        ver = carousel.versions(lang, cap['threads'].split('\n', 1)[0], body, tickers[:3])
        assert len(ver['threads']) <= 500, (lang, len(ver['threads']))
        assert ver['threads'].split('\n', 1)[0].startswith(cap['threads'].split('\n', 1)[0][:12])
        assert TAG[lang] in ver['threads'].split('\n')
    tag_posts(posts, 'daily')
    for lang, p in posts.items():
        assert len(p['threads']) <= 500, (lang, len(p['threads']))
        urls = URL_RE.findall(p['threads'])
        assert len(urls) <= 1
        assert all(f'/{lang}/' in u and 'utm_source=threads' in u for u in urls)
        assert 'utm_campaign=daily' in p['threads']
        # X is not run through the Threads fitter.
        assert '☕' in p['x'] or 'http' in p['x']


def test_always_under_cap():
    huge = 'H' * 900 + '\n\n⚠️ Not investment advice\n\n#StockMarket'
    out = share.fit_threads(huge, 'en')
    assert len(out) <= 500
    assert out.split('\n', 1)[0].startswith('H')
    assert '…' in out.split('\n', 1)[0]
    assert '⚠️ Not investment advice' in out
    assert '#StockMarket' in out.split('\n')
    assert len(share.fit_threads('x' * 800, 'zh')) <= 500
    assert share.fit_threads('', 'en') == ''
    assert share.fit_threads(None, 'ko') == ''


def main():
    test_short_is_unchanged()
    test_quote_shortened_before_other_cuts()
    test_long_drops_quote_then_donate_keeps_rest()
    test_then_streak_split_and_ticker_lines()
    test_json_style_samples()
    test_generators_and_utm()
    test_always_under_cap()
    print('test_threads500: zh/en/ko long posts, json style, caption, carousel <=500')


if __name__ == '__main__':
    main()
