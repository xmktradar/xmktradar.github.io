"""Step 8b: share image data (one picture per language) and the daily social media posts.

Reads work/stats.json, the data in index.html and data/consensus-history.json.
Writes work/og.json for tools/og.js when a picture needs drawing, points the master page's
og:image at today's picture, and once a day (first update after 07:00 HKT) writes
data/social-posts.json and social/index.html: posts in Chinese, English and Korean for Instagram
(the @thecrowdtape format), Threads, X, Reddit and Facebook, for the Grok bot to post with og/social-<lang>.png,
plus a 1080x1920 Instagram Story picture og/story-<lang>.png and a native 1080x1350
Instagram text-post picture og/ig-<lang>.png. Every version asks readers to support the site (PayPal).
Also writes x_trilingual (one zh+en+ko X post at 21:00 and 08:00 HKT, picture og/x-<kind>.png for the $TICKER in the text), facebook_cta and ig_threads_daily.
The same daily social run writes top5, and on Friday (HKT) weekly_thread. It also writes
hot_stock, discussion, three_lines, why_posts and atomic_posts. On Saturday and Sunday
(HKT) it writes weekend and atomic_posts without rebuilding the weekday posts, and it does
not write three_lines or why_posts. Schemas are on the build_* functions and in tools/SOCIAL.md.
python3 tools/share.py --og-only writes work/og.json from dash-data + work/stats.json and stops
(no social posts, no index.html rewrite); used by tools/ig_sample.js.
python3 tools/share.py --backfill-date-kst adds date_kst on data/social-posts.json and does not rewrite post text.
"""
import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime

from ranking import rank_rows
from sitedata import HK, load, notice, now_hk, read_json, work, write_json
from utm import PLATFORM, normalize_file, tag_posts, tag_url
import date_kst
import three_why

build_three_lines = three_why.build_three_lines
build_why_posts = three_why.build_why_posts
three_lines_calc = three_why.three_lines_calc
schedule_why_atomic = three_why.schedule_why_atomic

HTML = 'index.html'
SITE = 'https://thecrowdtape.com/'
LANGS = ('zh', 'en', 'ko')
SOCIAL_HOUR = 7  # first update at or after this HKT hour writes the day's posts


def page_url(lang, path=''):
    """Absolute page URL under /{lang}/.

    Stock pages are /{lang}/stock/<T>/ (root /stock/<T>/ is 404). A path that already
    starts with zh/, en/, ko/, or a leading slash is rewritten under `lang`.
    """
    if lang not in LANGS:
        lang = 'en'
    path = (path or '').strip()
    if path.startswith('http://') or path.startswith('https://'):
        return path
    if path.startswith('/'):
        path = path[1:]
    for pfx in ('zh/', 'en/', 'ko/'):
        if path.startswith(pfx):
            path = path[len(pfx):]
            break
    if path.startswith('#'):
        return f'{SITE}{lang}/{path}'
    if path and not path.endswith('/'):
        path += '/'
    return f'{SITE}{lang}/{path}'


def stock_url(lang, ticker):
    """/{lang}/stock/<TICKER>/ . Root /stock/<TICKER>/ is 404."""
    ticker = re.sub(r'[^A-Z0-9.\-]', '', (ticker or '').strip().lstrip('$').upper())
    return page_url(lang, f'stock/{ticker}/')
# Social posts only go out on US trading days, Monday to Friday (Tim, 2026-10-12). NYSE full-day closures:
US_HOLIDAYS = {'2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25', '2026-06-19', '2026-07-03',
               '2026-09-07', '2026-11-26', '2026-12-25',
               '2027-01-01', '2027-01-18', '2027-02-15', '2027-03-26', '2027-05-31', '2027-06-18', '2027-07-05',
               '2027-09-06', '2027-11-25', '2027-12-24'}


def trading_day(day):
    return datetime.strptime(day, '%Y-%m-%d').weekday() < 5 and day not in US_HOLIDAYS


def likes(p):
    v = str(p.get('likes') or '0').replace(',', '').strip().upper()
    m = re.match(r'([\d.]+)([KM]?)', v)
    return float(m.group(1)) * {'': 1, 'K': 1e3, 'M': 1e6}[m.group(2)] if m else 0


def clean(t, n):
    t = re.sub(r'https?://\S+', '', t or '')
    t = re.sub(r'\s+', ' ', t).strip()
    return t if len(t) <= n else t[:n - 1].rstrip() + '…'


def streak(days, day, t, key):
    """Days in a row, ending today, that t was in that day's list."""
    n, cur = 0, datetime.strptime(day, '%Y-%m-%d')
    while True:
        rec = days.get(cur.strftime('%Y-%m-%d'))
        if not rec or t not in rec.get(key, []):
            return n
        n += 1
        cur = datetime.fromordinal(cur.toordinal() - 1)


def hk(ms):
    return datetime.fromtimestamp(ms / 1000, HK)


def window(s):
    if s.get('first_ms') and s.get('last_ms'):
        a, b = hk(s['first_ms']), hk(s['last_ms'])
        return f"{a.month}/{a.day} {a:%H:%M} – {b.month}/{b.day} {b:%H:%M} HKT"
    return f"{s['from']} – {s['to']} HKT"


def quote(d, urls, t, lang):
    by = {p['url']: p for p in d['posts']}
    ps = [by[u] for u in urls if u in by]
    ps.sort(key=lambda p: (bool(p.get('reposted_by')), -likes(p)))
    for p in ps:
        txt = {'zh': p.get('zh_summary'), 'ko': p.get('ko_summary'),
               'en': p.get('en_summary') or p.get('text')}[lang]
        txt = re.sub(r'^\((?:Reposted|轉發|리포스트)\)\s*', '', txt or '')
        # English card only: a quote with CJK or Hangul is skipped for the next post. Korean is left as-is.
        if lang == 'en' and re.search('[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\uf900-\ufaff]', txt):
            continue
        if txt:
            h = p['handle']
            a = d['accounts'].get(h, {}).get('avatar') or d.get('avmini', {}).get(h, '')
            return {'acc': h, 'text': clean(dedupe_handle(h, txt), 150 if lang == 'en' else 90), 'av': a, 'url': p['url']}
    return None


def build(d, s, ch, day):
    """Picture data per language, plus the facts the captions are written from."""
    days = ch.get('days', {})
    prices = d.get('prices', {})
    av = lambda h: d['accounts'].get(h, {}).get('avatar') or d.get('avmini', {}).get(h, '')

    def px(t):
        c = [r[1] for r in (prices.get(t) or {}).get('c', []) if r[1] is not None]
        return c[-22:], (round((c[-1] / c[-2] - 1) * 100, 2) if len(c) > 1 and c[-2] else None)

    bull = bool(s['bull'])
    if bull:
        groups = sorted(s['bull'], key=lambda g: -g['nb'])
        items = []
        for g in groups:
            accs = list(dict.fromkeys(r['acc'] for r in g['rows'] if r['s'] == 'bull'))
            items.append({'t': g['t'], 'n': g['nb'], 'bull': g['nb'], 'bear': g['nr'], 'accs': accs,
                          'urls': [r['url'] for r in g['rows'] if r['s'] == 'bull'],
                          'streak': streak(days, day, g['t'], 'bull')})
    else:
        items = [{'t': x['t'], 'n': x['accounts'], 'bull': x.get('bull_accounts', 0), 'bear': x.get('bear_accounts', 0),
                  'accs': x['accs'], 'urls': x.get('urls', []), 'streak': streak(days, day, x['t'], 'top')}
                 for x in s['top']]
    for x in items:
        x['spark'], x['d1'] = px(x['t'])
    top = [{k: x[k] for k in ('t', 'n', 'bull', 'bear', 'streak', 'spark', 'd1')} | {'avs': [av(h) for h in x['accs'][:4]]}
           for x in items[:4]]
    tape = [{'t': x['t'], 'd1': x['d1']} for x in items[:12] if x['d1'] is not None]
    while tape and len(tape) < 10:
        tape = tape + tape
    hero = items[0] if items else None
    win = window(s)
    out = {}
    for lang in LANGS:
        out[lang] = {'mode': 'bull' if bull else 'talk', 'date': day, 'win': win, 'acc': s['accounts'], 'posts': s['posts'],
                     'n_tk': s.get('tickers', len(s['top'])), 'bull_n': len(s['bull']), 'bear_n': len(s['bear']),
                     'top': top, 'tape': tape[:20], 'quote': quote(d, hero['urls'], hero['t'], lang) if hero else None}
    return out, items


def tags(lang, tks):
    base = {'zh': '#美股 #港人投資 #美股投資 #投資 #USStocks #StockMarket #香港投資',
            'en': '#StockMarket #USStocks #Stocks #Investing #FinTwit #WallStreet',
            'ko': '#미국주식 #미장 #해외주식 #주식 #투자 #USStocks'}[lang]
    return base + ''.join(f' #{t}' for t in tks[:5] if re.fullmatch(r'[A-Z]{1,6}', t))


# Instagram captions: no URLs, no domain, one link-in-bio line, 3–5 hashtags (≤2 tickers).
# Min 3 by filling language base tags; max 5.
# A key-point first line comes from the generator (top5 lead bull/bear, macro top theme).
# sanitize_instagram never moves or deletes a body line to invent one. It may prepend
# a key line built from structured data only when line 1 has neither a $TICKER nor a digit.
IG_BIO = {'zh': '連結在個人簡介', 'en': 'link in bio', 'ko': '프로필 링크'}
IG_BASE_TAGS = {
    'zh': ('#美股', '#美股投資', '#港人投資'),
    'en': ('#StockMarket', '#USStocks', '#Stocks'),
    'ko': ('#미국주식', '#미장', '#해외주식'),
}
IG_MIN_TAGS = 3
IG_MAX_TAGS = 5
IG_CTA_COPY = {
    'zh': '覺得有用？收藏＋追蹤 @thecrowdtape，每日睇大神共識',
    'en': 'Found this useful? Save + follow @thecrowdtape for daily consensus',
    'ko': '유용했다면 저장 + 팔로우 @thecrowdtape',
}
IG_CTA_REL = 'og/cta/ig-cta-{lang}.jpg'


def ig_cta_url(lang):
    """Absolute URL of the static follow/save CTA JPEG for one language."""
    lang = lang if lang in LANGS else 'en'
    return f'{SITE}{IG_CTA_REL.format(lang=lang)}'


IG_FOLLOW = {
    'zh': 'Follow @thecrowdtape 每日睇街貨點諗。',
    'en': 'Follow @thecrowdtape for the daily read on what the crowd thinks.',
    'ko': '@thecrowdtape 팔로우하고 매일 시장 분위기를 확인하세요.',
}
_HANDLE_LEAD = re.compile(r'^@([A-Za-z0-9_]+)[：:]\s*')
_DUP_HANDLE_RE = re.compile(r'(@(\w+))([：:])\s*("?)@\2[：:]\s*', re.I)
_HASHTAG_TOKEN = re.compile(r'#[^\s#]+')
_IG_URL_RE = re.compile(r'https?://\S+', re.I)
_IG_DOMAIN_RE = re.compile(r'\(?thecrowdtape\.com\)?', re.I)


def ig_tags(lang, tks):
    """Language base tags first, then at most 2 ticker tags, 3–5 hashtags total.

    Fewer than 3: fill from the language base. More than 5: drop from the end.
    """
    lang = lang if lang in LANGS else 'en'
    base = list(IG_BASE_TAGS[lang])
    extra = []
    for t in tks or []:
        if re.fullmatch(r'[A-Z]{1,6}', t) and f'#{t}' not in extra and f'#{t}' not in base:
            extra.append(f'#{t}')
        if len(extra) >= 2:
            break
    room = max(0, IG_MAX_TAGS - len(extra))
    tags = base[:room] + extra
    if len(tags) < IG_MIN_TAGS:
        for tok in base:
            if tok not in tags:
                tags.append(tok)
            if len(tags) >= IG_MIN_TAGS:
                break
    return ' '.join(tags[:IG_MAX_TAGS])


def dedupe_handle(acc, why):
    """Strip a leading @handle： / @handle: when it matches acc. Keep a different handle (repost)."""
    acc = str(acc or '').strip().lstrip('@')
    why = (why or '').strip()
    if len(why) >= 2 and why[0] == '"' and why[-1] == '"':
        why = why[1:-1].strip()
    if not acc or not why:
        return why
    m = _HANDLE_LEAD.match(why)
    if m and m.group(1).lower() == acc.lower():
        return why[m.end():].lstrip()
    return why


def quote_line(acc, why, lang='zh'):
    """One 💬 @handle：text line. why is passed through dedupe_handle."""
    why = dedupe_handle(acc, why)
    handle = '@' + str(acc or '').lstrip('@')
    if lang == 'zh':
        return f'💬 {handle}：{why}'
    return f'💬 {handle}: "{why}"'


def strip_dup_handles(text):
    """Collapse '@h：@h：' / '@h: \"@h: ' so a quoted why is prefixed once."""
    if not isinstance(text, str) or '@' not in text:
        return text
    prev = None
    out = text
    while out != prev:
        prev = out

        def repl(m):
            quote = m.group(4) or ''
            if quote:
                return f'{m.group(1)}{m.group(3)} {quote}'
            return f'{m.group(1)}{m.group(3)}'

        out = _DUP_HANDLE_RE.sub(repl, out)
    return out


def strip_dup_handles_tree(obj):
    """Walk a JSON tree and strip duplicate @handle prefixes in every string."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str):
                obj[key] = strip_dup_handles(value)
            elif isinstance(value, (dict, list)):
                strip_dup_handles_tree(value)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            if isinstance(value, str):
                obj[i] = strip_dup_handles(value)
            elif isinstance(value, (dict, list)):
                strip_dup_handles_tree(value)
    return obj


def _guess_ig_lang(text):
    t = text or ''
    if '連結在個人簡介' in t or '唔構成' in t or '#美股' in t or '大神' in t:
        return 'zh'
    if '프로필 링크' in t or '투자 조언' in t or '#미국주식' in t:
        return 'ko'
    return 'en'


def _ig_drop_line(s, lang, bio):
    """True for live-link, donate-link, domain, and old link-in-bio lines."""
    if not s:
        return False
    low = s.lower()
    if s == bio or s in IG_BIO.values():
        return True
    if 'link in bio' in low or '連結在個人簡介' in s or '프로필 링크' in s:
        return True
    if 'thecrowdtape.com' in low:
        return True
    live = SHORT.get(lang, SHORT['en'])['live'].strip()
    if live and s.startswith(live):
        return True
    if s.startswith('☕') and any(m in s for m in ('link in bio', '個人簡介', '프로필', 'PayPal', 'paypal')):
        return True
    if s in ('👉', '最新數字 👉', 'Live numbers 👉', '최신 수치 👉'):
        return True
    return False


def _ig_tag_line(lang, found, body=''):
    tickers = []
    for tok in found or []:
        body_tok = tok[1:] if tok.startswith('#') else tok
        tag = f'#{body_tok}'
        if re.fullmatch(r'[A-Z]{1,6}', body_tok) and tag not in tickers:
            tickers.append(tag)
        if len(tickers) >= 2:
            break
    if len(tickers) < 2:
        for m in re.finditer(r'\$([A-Z]{1,6})\b', body or ''):
            tag = f'#{m.group(1)}'
            if tag not in tickers and tag not in IG_BASE_TAGS.get(lang, ()):
                tickers.append(tag)
            if len(tickers) >= 2:
                break
    return ig_tags(lang, [t[1:] for t in tickers])


_IG_TICKER_RE = re.compile(r'\$[A-Z]{1,6}\b')


def _ig_has_key_marker(line):
    """True when the line already names a $TICKER or contains a digit."""
    s = line or ''
    return bool(_IG_TICKER_RE.search(s) or re.search(r'\d', s))


def ig_non_hashtag_lines(text):
    """Non-empty lines that are not a hashtag-only line, in order."""
    out = []
    for ln in (text or '').split('\n'):
        s = ln.strip()
        if s and not re.fullmatch(r'(?:#[^\s#]+\s*)+', s):
            out.append(s)
    return out


def install_ig_headline(text, key_line):
    """Prepend a generator key-point line. Existing lines stay, in order.

    No-op when key_line is blank or already the first non-empty line.
    Does not delete or reorder body lines. Callers that already put the
    headline in the caption (the generators) hit the no-op.
    """
    if not isinstance(text, str):
        return text
    key_line = (key_line or '').strip()
    if not key_line:
        return text
    lines = text.split('\n')
    first_i = next((i for i, ln in enumerate(lines) if ln.strip()), None)
    if first_i is None:
        return key_line
    if lines[first_i].strip() == key_line:
        return text
    head = lines[:first_i] + [key_line]
    if lines[first_i].strip():
        head.append('')
    return '\n'.join(head + lines[first_i:])


def _ig_prepend_key_line(lines, key_line):
    """Prepend key_line only when line 1 has neither a $TICKER nor a digit.

    Never pops, moves, or deletes a line. No key_line: leave the lines as they are.
    """
    key_line = (key_line or '').strip()
    first_i = next((i for i, ln in enumerate(lines) if ln.strip()), None)
    if first_i is None:
        return [key_line] if key_line else lines
    if _ig_has_key_marker(lines[first_i]) or not key_line:
        return lines
    if lines[first_i].strip() == key_line:
        return lines
    lines.insert(first_i, key_line)
    if lines[first_i + 1].strip():
        lines.insert(first_i + 1, '')
    return lines


def sanitize_instagram(text, lang=None, key_line=None):
    """One Instagram caption: no URLs/domain, one bio line, 3–5 hashtags.

    key_line, when passed, is prepended only if line 1 has neither a $TICKER nor a
    digit. Body lines are never moved or deleted to manufacture a key point.
    """
    if not isinstance(text, str):
        return text
    lang = lang if lang in LANGS else _guess_ig_lang(text)
    bio = IG_BIO[lang]
    text = strip_dup_handles(text)
    text = _IG_URL_RE.sub('', text)
    text = _IG_DOMAIN_RE.sub('', text)
    found_tags = []
    kept = []
    for ln in text.split('\n'):
        cleaned = re.sub(r'[ \t]{2,}', ' ', ln).rstrip()
        s = cleaned.strip()
        if s and re.fullmatch(r'(?:#[^\s#]+\s*)+', s):
            found_tags.extend(_HASHTAG_TOKEN.findall(s))
            continue
        if _ig_drop_line(s, lang, bio):
            continue
        kept.append(cleaned)
    while kept and not kept[0].strip():
        kept.pop(0)
    while kept and not kept[-1].strip():
        kept.pop()
    compact = []
    for ln in kept:
        if not ln.strip() and compact and not compact[-1].strip():
            continue
        compact.append(ln)
    compact = _ig_prepend_key_line(compact, key_line)
    insert_at = None
    for i, ln in enumerate(compact):
        s = ln.strip()
        if s.startswith('Follow @') or s.startswith('@thecrowdtape') or s.startswith('⚠'):
            insert_at = i
            break
    if insert_at is None:
        compact.append(bio)
    else:
        compact.insert(insert_at, bio)
        if insert_at > 0 and compact[insert_at - 1].strip():
            compact.insert(insert_at, '')
    # Exactly one bio line.
    seen = False
    unique = []
    for ln in compact:
        if ln.strip() == bio:
            if seen:
                continue
            seen = True
        unique.append(ln)
    while unique and not unique[-1].strip():
        unique.pop()
    unique.append('')
    unique.append(_ig_tag_line(lang, found_tags, '\n'.join(unique)))
    return '\n'.join(unique).strip('\n')


def _sanitize_ig_value(value, lang):
    lang = lang if lang in LANGS else (lang or 'en')
    if isinstance(value, str):
        return sanitize_instagram(value, lang)
    if isinstance(value, dict) and isinstance(value.get('text'), str):
        value['text'] = sanitize_instagram(value['text'], lang)
    return value


def sanitize_instagram_tree(obj, lang=None):
    """Sanitize every Instagram caption (string, {text}, or ig_reel.caption) and clear has_link.instagram."""
    if isinstance(obj, dict):
        this_lang = obj.get('lang') if obj.get('lang') in LANGS else lang
        ig = obj.get('instagram')
        if isinstance(ig, str):
            obj['instagram'] = sanitize_instagram(ig, this_lang or lang or 'en')
        elif isinstance(ig, dict):
            for key, value in ig.items():
                lg = key if key in LANGS else this_lang
                ig[key] = _sanitize_ig_value(value, lg or 'en')
        cap = obj.get('caption')
        if isinstance(cap, dict) and ('video_path' in obj or 'video_expected_path' in obj):
            for key, value in cap.items():
                if key in LANGS and isinstance(value, str):
                    cap[key] = sanitize_instagram(value, key)
        hl = obj.get('has_link')
        if isinstance(hl, dict) and 'instagram' in hl:
            if isinstance(hl['instagram'], dict):
                for key in list(hl['instagram']):
                    hl['instagram'][key] = False
            else:
                hl['instagram'] = False
        for key, value in obj.items():
            if key == 'instagram':
                continue
            if key == 'caption' and ('video_path' in obj or 'video_expected_path' in obj):
                continue
            next_lang = key if key in LANGS else this_lang
            if isinstance(value, (dict, list)):
                sanitize_instagram_tree(value, next_lang)
    elif isinstance(obj, list):
        for value in obj:
            if isinstance(value, (dict, list)):
                sanitize_instagram_tree(value, lang)
    return obj


def mix(x, wrap, both, bull, bear):
    """How many of the accounts were bullish or bearish, leaving out a side with none."""
    b, r = x['bull'], x['bear']
    if not b and not r:
        return ''
    return wrap.format(both.format(b, r) if b and r else (bull.format(b) if b else bear.format(r)))


def caption(lang, day, s, items, win, quote_):
    m, dd = int(day[5:7]), int(day[8:10])
    bull = bool(s['bull'])
    T = lambda t: f'${t}'
    sep = '、 ' if lang == 'zh' else (', ' if lang == 'en' else ', ')
    lines = []
    if lang == 'zh':
        acc = lambda n: f'{n} 個帳號'
        if bull:
            h = items[0]
            lines.append(f'{m}/{dd} X 大神共識快照：最多人睇好 {T(h["t"])}（{acc(h["n"])}）📊')
        else:
            h = items[0] if items else None
            lines.append(f'{m}/{dd} X 大神快照：今日最多人講 {T(h["t"])}（{acc(h["n"])}）💬' if h else f'{m}/{dd} X 大神快照 💬')
        lines += ['', f'數據範圍：{win}', '']
    elif lang == 'en':
        acc = lambda n: f'{n} account{"" if n == 1 else "s"}'
        mon = datetime.strptime(day, '%Y-%m-%d').strftime('%b %-d')
        if bull:
            h = items[0]
            lines.append(f'{mon} · Most bullish: {T(h["t"])}, {acc(h["n"])} 📊')
        else:
            h = items[0] if items else None
            lines.append(f'{mon} · Most talked-about stock on X today: {T(h["t"])} ({acc(h["n"])}) 💬' if h else f'{mon} · X snapshot 💬')
        lines += ['', f'Data window: {win}', '']
    else:
        acc = lambda n: f'계정 {n}개'
        if bull:
            h = items[0]
            lines.append(f'{m}/{dd} X 인플루언서 컨센서스: 가장 강세 {T(h["t"])} ({acc(h["n"])}) 📊')
        else:
            h = items[0] if items else None
            lines.append(f'{m}/{dd} X 스냅샷: 오늘 가장 많이 언급된 종목 {T(h["t"])} ({acc(h["n"])}) 💬' if h else f'{m}/{dd} X 스냅샷 💬')
        lines += ['', f'데이터 범위: {win}', '']

    L = {'zh': dict(cb=f'🔵 共同看多：{len(s["bull"])} 隻・共同看空：{len(s["bear"])} 隻', rest=lambda k, n: f'・其餘 {k} 隻各 {n} 個帳號',
                    more=lambda k: f' 等 {k} 隻', bear='🔴 共同看空：', split='⚖️ 好淡分歧：', sp=lambda b, r: f'（{b} 好 {r} 淡）',
                    stk='🔥 連續 2 日或以上都喺共同看多：', sd=lambda n: f'（{n} 日）', none='今日暫時未有共同看多（要最少 2 個帳號最新立場都睇好）。',
                    talk='💬 最多人討論：', tr=lambda x: acc(x['n']) + mix(x, '（{}）', '{} 好 {} 淡', '{} 個睇好', '{} 個睇淡'),
                    sum=f'🗣️ 今日 {s["accounts"]} 個帳號發文，講咗 {s.get("tickers", 0)} 隻股票。',
                    q=lambda q: quote_line(q['acc'], q['text'], 'zh'),
                    note='(共同看多＝最少 2 個帳號最新立場睇好，唔計市場快訊帳號)',
                    end=[IG_BIO['zh'], IG_FOLLOW['zh'], '',
                         '⚠️ 只係整理公開社交媒體貼文，唔構成投資建議。網站嘅機械人頁只係紙上交易。投資有風險，請自行判斷。']),
         'en': dict(cb=f'🔵 Joint bullish: {len(s["bull"])} · Joint bearish: {len(s["bear"])}', rest=lambda k, n: f'・{k} more with {n} accounts each',
                    more=lambda k: f' +{k} more', bear='🔴 Joint bearish: ', split='⚖️ Split views: ', sp=lambda b, r: f' ({b} bull / {r} bear)',
                    stk='🔥 Joint bullish 2+ days in a row: ', sd=lambda n: f' ({n}d)', none='No joint bullish stock yet today (needs 2+ accounts whose latest view is bullish).',
                    talk='💬 Most discussed:', tr=lambda x: acc(x['n']) + mix(x, ' ({})', '{} bull / {} bear', '{} bullish', '{} bearish'),
                    sum=f'🗣️ {s["accounts"]} accounts posted today, covering {s.get("tickers", 0)} stocks.',
                    q=lambda q: quote_line(q['acc'], q['text'], 'en'),
                    note='(Joint bullish = at least 2 accounts whose latest view is bullish; news-wire accounts not counted)',
                    end=[IG_BIO['en'], IG_FOLLOW['en'], '',
                         '⚠️ A summary of public social media posts, not investment advice. The site\'s bot pages are paper trading only. Investing involves risk; do your own research.']),
         'ko': dict(cb=f'🔵 공동 강세: {len(s["bull"])}개・공동 약세: {len(s["bear"])}개', rest=lambda k, n: f'・나머지 {k}개 종목은 각 계정 {n}개',
                    more=lambda k: f' 외 {k}개', bear='🔴 공동 약세: ', split='⚖️ 의견 엇갈림: ', sp=lambda b, r: f' (강세 {b} / 약세 {r})',
                    stk='🔥 2일 이상 연속 공동 강세: ', sd=lambda n: f' ({n}일)', none='오늘은 아직 공동 강세 종목이 없습니다 (최신 의견이 강세인 계정이 2개 이상 필요).',
                    talk='💬 가장 많이 언급된 종목:', tr=lambda x: acc(x['n']) + mix(x, ' ({})', '강세 {} / 약세 {}', '강세 {}', '약세 {}'),
                    sum=f'🗣️ 오늘 계정 {s["accounts"]}개가 글을 올렸고, 언급된 종목은 {s.get("tickers", 0)}개입니다.',
                    q=lambda q: quote_line(q['acc'], q['text'], 'ko'),
                    note='(공동 강세 = 최신 의견이 강세인 계정 2개 이상, 뉴스 속보 계정 제외)',
                    end=[IG_BIO['ko'], IG_FOLLOW['ko'], '',
                         '⚠️ 공개 SNS 게시물을 정리한 것으로 투자 조언이 아닙니다. 사이트의 봇 페이지는 모의 거래입니다. 투자에는 위험이 따르니 스스로 판단하세요.'])}[lang]
    join = lambda ts, cap=8: sep.join(T(t) for t in ts[:cap]) + (L['more'](len(ts) - cap) if len(ts) > cap else '')
    lead = ' ' if lang == 'zh' else ''
    head, win_line = lines[0], lines[2]
    main = []
    if bull:
        main.append(L['cb'])
        by = {}
        for x in items:
            by.setdefault(x['n'], []).append(x['t'])
        for n in sorted(by, reverse=True):
            ts = by[n]
            if n >= 3 or len(ts) <= 4:
                main.append(f'・{acc(n)}：{lead}{join(ts)}' if lang == 'zh' else f'・{acc(n)}: {join(ts)}')
            else:
                main.append(L['rest'](len(ts), n))
    else:
        main += [L['none'], L['talk']]
        for x in items[:5]:
            main.append(f'・{T(x["t"])}：{L["tr"](x)}' if lang == 'zh' else f'・{T(x["t"])}: {L["tr"](x)}')
    if s['bear']:
        main.append(L['bear'] + lead + sep.join(f'{T(g["t"])}' + (f'（{acc(g["nr"])}）' if lang == 'zh' else f' ({acc(g["nr"])})') for g in s['bear'][:5]))
    extra = []  # optional blocks, most important first
    if s['split']:
        extra.append(L['split'] + lead + sep.join(T(g['t']) + L['sp'](g['nb'], g['nr']) for g in s['split'][:4]))
    if bull:
        st = sorted([x for x in items if x['streak'] >= 2], key=lambda x: -x['streak'])[:6]
        if st:
            extra.append(L['stk'] + lead + sep.join(T(x['t']) + L['sd'](x['streak']) for x in st))
    else:
        extra.append(L['sum'])
    q = L['q'](quote_) if quote_ and quote_.get('text') else None
    tg = tags(lang, [x['t'] for x in items])
    ig_tg = ig_tags(lang, [x['t'] for x in items])
    url = page_url(lang)
    short = SHORT[lang]

    # Instagram: no URLs. One link-in-bio line, 3–5 hashtags.
    ig = [head, '', win_line, '', *main]
    for b in extra + ([q] if q else []):
        ig += ['', b]
    ig += ['', L['note'], '', *L['end'], '', ig_tg]

    # X (280, CJK counted double): drop the least important blocks until it fits.
    # Threads is fit afterwards by fit_threads (500 code points, URLs counted in full).
    def fit(blocks, limit, size):
        blocks = [b for b in blocks if b]
        while len(blocks) > 3 and size('\n\n'.join(blocks)) > limit:
            blocks.pop(-3)  # keep the headline and the link + disclaimer at the end
        return '\n\n'.join(blocks)
    give = f"{short['give']}{url}#donate"
    tail = f"{short['live']}{url}\n{short['disc']}"
    # Threads shows one topic tag per post, so it gets the first hashtag only.
    threads = fit_threads('\n\n'.join(b for b in [
        head, win_line, '\n'.join(main[:6]), *extra, q,
        f"{short['live']}{url}\n{give}\n{short['disc']}", tg.split(' ')[0]] if b), lang)
    xs = [head, '\n'.join([t for t in main if t != L['none']][:3]), tail]
    x = fit(xs, 270, xlen)
    while xlen(x) > 270 and len(xs[1].split('\n')) > 1:
        xs[1] = '\n'.join(xs[1].split('\n')[:-1])
        x = '\n\n'.join(xs)
    # Every post carries hashtags (Tim, 2026-10-12). X gets a short set; then the donation line when it still fits,
    # dropping list lines for them but keeping at least one.
    tks = [t for t in [x_['t'] for x_ in items] if re.fullmatch(r'[A-Z]{1,6}', t)]
    xtags = ' '.join([tg.split(' ')[0]] + [f'#{t}' for t in tks[:2]])
    lines_ = xs[1].split('\n')
    done = False
    for end in (f"{short['live']}{url}\n{give}\n{short['disc']}\n{xtags}", f"{tail}\n{xtags}", f"{tail}\n{tg.split(' ')[0]}"):
        for k in range(len(lines_), 0, -1):
            xd = '\n\n'.join([head, '\n'.join(lines_[:k]), end])
            if xlen(xd) <= 270:
                x, done = xd, True
                break
        if done:
            break

    # Reddit: a title plus a Markdown body, hashtags on the last line.
    md = lambda t: re.sub(r'^・', '- ', t)
    body = [win_line, '\n'.join(md(t) for t in main)] + extra + ([f'> {q}'] if q else [])
    body += [L['note'], f"{short['live']}[{url}]({url})", f"{short['give']}[{url}#donate]({url}#donate)", short['disc_long'], tg]

    # Facebook: the Instagram post with clickable links in place of "link in bio".
    fb = [head, '', win_line, '', *main]
    for b in extra + ([q] if q else []):
        fb += ['', b]
    fb += ['', L['note'], '', f"{short['live']}{url}", give, '', short['disc_long'], '', tg]
    return {'instagram': sanitize_instagram('\n'.join(ig), lang), 'threads': threads, 'x': x,
            'reddit': {'title': re.sub(r'\s*[📊💬]$', '', head), 'body': '\n\n'.join(body)},
            'facebook': '\n'.join(fb),
            # Instagram Story: hashtags for a hashtag sticker or small text on the Story picture.
            'story': ' '.join(tg.split(' ')[:3] + [f'#{t}' for t in tks[:2]])}


# URL body is ASCII. CJK, Hangul and emoji after a link are weighted on their own, not swallowed into the 23.
_XURL = re.compile(r'https?://[A-Za-z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+')


def xlen(t):
    """Length as X counts it: each URL counts 23, Chinese, Japanese, Korean and emoji count 2."""
    def weight(s):
        return sum(2 if ord(c) >= 0x1100 else 1 for c in s)

    n, i = 0, 0
    for m in _XURL.finditer(t or ''):
        n += weight(t[i:m.start()]) + 23
        i = m.end()
    return n + weight((t or '')[i:])


SHORT = {'zh': {'live': '最新數字 👉 ', 'give': '☕ 鍾意就支持我哋 👉 ', 'disc': '⚠️ 唔構成投資建議', 'disc_long': '⚠️ 只係整理公開社交媒體貼文，唔構成投資建議。投資有風險，請自行判斷。'},
         'en': {'live': 'Live numbers 👉 ', 'give': '☕ Support the site 👉 ', 'disc': '⚠️ Not investment advice', 'disc_long': '⚠️ A summary of public social media posts, not investment advice. Investing involves risk; do your own research.'},
         'ko': {'live': '최신 수치 👉 ', 'give': '☕ 후원하기 👉 ', 'disc': '⚠️ 투자 조언 아님', 'disc_long': '⚠️ 공개 SNS 게시물을 정리한 것으로 투자 조언이 아닙니다. 투자에는 위험이 따르니 스스로 판단하세요.'}}

# Threads rejects a post past 500 Unicode code points. len() is that count; a URL counts in full.
THREADS_MAX = 500
_THREADS_URL = re.compile(r'https?://\S+')


def _truncate_ending(line, target):
    """Shorten `line` to at most `target` code points, ending with …. None if it would not get shorter."""
    if target >= len(line):
        return line
    if target < 1:
        return None
    raw = line[:-1].rstrip() if line.endswith('…') else line
    keep = target - 1
    cut = raw[:keep].rstrip(' \t') if keep > 0 else ''
    while cut and ord(cut[-1]) in (0xfe0f, 0x200d):
        cut = cut[:-1].rstrip(' \t')
    new = (cut + '…') if cut else '…'
    if len(new) > target:
        extra = len(new) - target
        cut = cut[:-extra] if extra < len(cut) else ''
        while cut and ord(cut[-1]) in (0xfe0f, 0x200d):
            cut = cut[:-1]
        new = (cut + '…') if cut else '…'
        if len(new) > target:
            new = new[:target]
    if len(new) >= len(line):
        return None
    return new


def _threads_join(parts):
    blocks = []
    for lines in parts:
        if any(ln.strip() for ln in lines):
            blocks.append('\n'.join(lines))
    return '\n\n'.join(blocks)


def _is_quote_line(line):
    """A 💬 quote (💬 @name：…), not a section label and not a headline that merely ends with 💬."""
    s = line.strip()
    return s.startswith('💬') and '@' in s


def _is_donate_line(line):
    s = line.strip()
    return s.startswith('☕') or '#donate' in s


def _is_live_line(line, lang):
    s = line.strip()
    if not s or _is_donate_line(s) or s.startswith('⚠') or s.startswith('#'):
        return False
    live = SHORT.get(lang, SHORT['en'])['live'].strip()
    return s.startswith(live)


def _sole_link(parts):
    """Index of the only non-donate URL line, if there is exactly one."""
    spots = []
    for i, lines in enumerate(parts):
        for j, ln in enumerate(lines):
            if _THREADS_URL.search(ln) and not _is_donate_line(ln):
                spots.append((i, j))
    return spots[0] if len(spots) == 1 else None


def _threads_fixed(i, j, line):
    """Headline, disclaimer and the hashtag line are never dropped."""
    if i == 0 and j == 0:
        return True
    s = line.strip()
    return s.startswith('#') or s.startswith('⚠')


def fit_threads(text, lang):
    """Fit a Threads caption into 500 code points.

    When len(text) > 500, trim in order: shorten the 💬 quote (ellipsis), then drop it;
    drop the ☕ donate line so at most one link remains (the language's 最新數字 / Live numbers /
    최신 수치 link); drop the 🔥 streak paragraph, then the ⚖️ split paragraph, then ticker
    lines (・) from the bottom. The headline, the disclaimer and the hashtag line stay.
    """
    if text is None:
        return ''
    if not isinstance(text, str):
        text = str(text)
    if lang not in LANGS:
        lang = 'en'
    if len(text) <= THREADS_MAX:
        return text
    parts = [p.split('\n') for p in text.split('\n\n')]

    def total():
        return len(_threads_join(parts))

    def quote_spots():
        found = []
        for i, lines in enumerate(parts):
            for j, ln in enumerate(lines):
                if _is_quote_line(ln) and not _threads_fixed(i, j, ln):
                    found.append((i, j))
        return found

    guard = 0
    while total() > THREADS_MAX and guard < 10000:
        guard += 1
        spots = quote_spots()
        if not spots:
            break
        i, j = spots[-1]
        saved = parts[i][j]
        parts[i].pop(j)
        without = total()
        parts[i].insert(j, saved)
        if without > THREADS_MAX:
            parts[i].pop(j)  # even an empty quote cannot get the post under the limit
            continue
        new = _truncate_ending(saved, len(saved) - (total() - THREADS_MAX))
        if not new or len(new) >= len(saved):
            parts[i].pop(j)
            continue
        parts[i][j] = new

    def drop_where(pred):
        for i, lines in enumerate(parts):
            parts[i] = [ln for j, ln in enumerate(lines) if _threads_fixed(i, j, ln) or not pred(ln)]

    if total() > THREADS_MAX:
        drop_where(_is_donate_line)
        # Any other extra link goes too, leaving the live-numbers link when it is there.
        while total() > THREADS_MAX and len(_THREADS_URL.findall(_threads_join(parts))) > 1 and guard < 10000:
            guard += 1
            spot = None
            for i, lines in enumerate(parts):
                for j, ln in enumerate(lines):
                    if _THREADS_URL.search(ln) and not _threads_fixed(i, j, ln) and not _is_live_line(ln, lang):
                        spot = (i, j)
            if not spot:
                break
            before = total()
            parts[spot[0]].pop(spot[1])
            if total() >= before:
                break

    if total() > THREADS_MAX:
        drop_where(lambda ln: ln.strip().startswith('🔥'))
    if total() > THREADS_MAX:
        drop_where(lambda ln: ln.strip().startswith('⚖'))
    while total() > THREADS_MAX and guard < 10000:
        guard += 1
        spot = None
        for i, lines in enumerate(parts):
            for j, ln in enumerate(lines):
                if ln.strip().startswith('・') and not _threads_fixed(i, j, ln):
                    spot = (i, j)
        if not spot:
            break
        before = total()
        parts[spot[0]].pop(spot[1])
        if total() >= before:
            break

    # Body lines that are not the ticker list (carousel duel rows, window, quotes) go next, from the bottom.
    # The one remaining link stays, even when it is not the live-numbers line.
    while total() > THREADS_MAX and guard < 10000:
        guard += 1
        sole = _sole_link(parts)
        spot = None
        for i, lines in enumerate(parts):
            for j, ln in enumerate(lines):
                if not ln.strip() or _threads_fixed(i, j, ln) or _is_live_line(ln, lang):
                    continue
                if sole == (i, j):
                    continue
                spot = (i, j)
        if not spot:
            break
        before = total()
        parts[spot[0]].pop(spot[1])
        if total() >= before:
            break

    while total() > THREADS_MAX and parts and parts[0] and guard < 10000:
        guard += 1
        head = parts[0][0]
        new = _truncate_ending(head, max(1, len(head) - (total() - THREADS_MAX)))
        if not new or len(new) >= len(head):
            break
        parts[0][0] = new

    out = _threads_join(parts)
    if len(out) <= THREADS_MAX:
        return out
    return _threads_force(parts, lang)


def _threads_force(parts, lang):
    """Last resort: keep a headline prefix, the disclaimer and the hashtag, and stay within 500."""
    head = parts[0][0] if parts and parts[0] else ''
    disc, tag, live = '', '', ''
    for i, lines in enumerate(parts):
        for j, ln in enumerate(lines):
            s = ln.strip()
            if not s or (i == 0 and j == 0):
                continue
            if s.startswith('⚠') and not disc:
                disc = s
            elif s.startswith('#') and not tag:
                tag = s
            elif _is_live_line(s, lang) and not live:
                live = s

    def assemble(head_line, live_line):
        chunks = []
        if head_line:
            chunks.append(head_line)
        mid = [ln for ln in (live_line, disc) if ln]
        if mid:
            chunks.append('\n'.join(mid))
        if tag and tag != head_line:
            chunks.append(tag)
        return '\n\n'.join(chunks)

    out = assemble(head, live)
    guard = 0
    while len(out) > THREADS_MAX and len(head) > 1 and guard < 5000:
        guard += 1
        new = _truncate_ending(head, max(1, len(head) - (len(out) - THREADS_MAX)))
        if not new or len(new) >= len(head):
            head = head[:-1].rstrip()
            if head and not head.endswith('…'):
                head = head[:-1] + '…' if len(head) > 1 else '…'
        else:
            head = new
        out = assemble(head, live)
    if len(out) > THREADS_MAX:
        out = assemble(head, '')
    if len(out) > THREADS_MAX:
        tail = '\n'.join(ln for ln in (disc, tag) if ln)
        room = THREADS_MAX - (len(tail) + 2 if tail else 0)
        if tail and room >= 1:
            piece = _truncate_ending(head, room) or '…'
            if len(piece) > room:
                piece = piece[:room]
            out = piece + '\n\n' + tail
        elif tail and len(tail) <= THREADS_MAX:
            # Headline gets one character so it is not dropped, tag and disc fill the rest.
            room = THREADS_MAX - 1 - (2 if tail else 0)
            keep = tail[-room:] if room > 0 else ''
            out = ('…\n\n' + keep) if keep else '…'
        else:
            out = (out or '')[:THREADS_MAX]
    if len(out) > THREADS_MAX:
        out = out[:THREADS_MAX]
    return out


def fit_threads_posts(posts):
    """Fit every language's threads string. Mutates `posts` ({lang: {threads: str}}) and returns it."""
    if not isinstance(posts, dict):
        return posts
    for lang, p in posts.items():
        if lang in LANGS and isinstance(p, dict) and isinstance(p.get('threads'), str):
            p['threads'] = fit_threads(p['threads'], lang)
    return posts

# One extra line under the Facebook post. The link is that language's home, campaign newsletter.
FB_CTA = {'zh': '📬 訂閱免費電子報 👉 ', 'en': '📬 Get the free newsletter 👉 ', 'ko': '📬 무료 뉴스레터 구독 👉 '}
X_WHEN = {'premarket': '21:00', 'afterclose': '08:00'}
_XDATE = re.compile(r'^(\d{1,2}/\d{1,2}|[A-Z][a-z]{2}\s+\d{1,2})')
_XTICK = re.compile(r'\$([A-Z]{1,6})\b')
_XEMOJI = re.compile(r'\s*[📊💬🚀⚔️]+\s*$')


def facebook_cta(text, lang):
    """Facebook text plus the newsletter line. `text` is kept as it already is."""
    line = FB_CTA[lang] + tag_url(page_url(lang), 'facebook', 'newsletter')
    text = (text or '').rstrip()
    return f'{text}\n\n{line}' if text else line


def add_facebook_ctas(posts):
    """Set posts[lang]['facebook_cta'] from the existing facebook text. Idempotent."""
    if not isinstance(posts, dict):
        return posts
    for lang, p in posts.items():
        if isinstance(p, dict) and isinstance(p.get('facebook'), str) and lang in FB_CTA:
            p['facebook_cta'] = facebook_cta(p['facebook'], lang)
    return posts


def _x_head_body(text):
    """Headline (first block of an X post) and the joint-bull lines under it, without the link tail."""
    paras = (text or '').strip().split('\n\n')
    head = paras[0].strip() if paras else ''
    body = []
    for p in paras[1:]:
        s = p.strip()
        if not s or re.search(r'https?://', s) or s.startswith('⚠') or s.startswith('#'):
            continue
        body.append(s)
    return head, '\n'.join(body)


def _short_headline(head):
    """Date plus the ticker clause of the X headline. Same words, without the long label."""
    bare = _XEMOJI.sub('', head).strip()
    m = _XDATE.match(bare)
    date = m.group(1) if m else ''
    sm = re.search(r'\$[A-Z]{1,6}.*$', bare)
    fact = sm.group(0).strip() if sm else bare
    if date and fact and not fact.startswith(date):
        return f'{date} {fact}'.strip()
    return fact or bare


def _ticker_block(posts):
    """Verbatim joint-bull ticker lines from the X post that kept the most tickers."""
    best, best_n = '', -1
    for lang in LANGS:
        p = posts.get(lang)
        text = p.get('x') if isinstance(p, dict) else ''
        _, body = _x_head_body(text or '')
        lines = [ln for ln in body.split('\n') if _XTICK.search(ln)]
        n = len(set(_XTICK.findall('\n'.join(lines))))
        if n > best_n:
            best, best_n = '\n'.join(lines), n
    return best


def _disc_line():
    """One line, the short disclaimer in each language (SHORT['disc'], not the long one)."""
    return ' · '.join(SHORT[lang]['disc'] for lang in LANGS)


def _x_link(lang, campaign):
    """Language home for an X post: utm_source=x, utm_medium=social, this campaign."""
    return tag_url(page_url(lang), 'x', campaign)


def _ticker_fact(line):
    m = re.search(r'\$[A-Z]{1,6}.*$', line or '')
    return m.group(0) if m else (line or '')


def _keep_frame(line):
    """Shorten a premarket line without dropping 開市前 / pre-market / 개장 전."""
    for frame in ('開市前：', 'pre-market:', '개장 전:'):
        i = (line or '').find(frame)
        if i < 0:
            continue
        pre = line[:i + len(frame)]
        fact = _ticker_fact(line[i + len(frame):].strip())
        if not fact:
            return pre
        if pre.endswith('：'):
            return f'{pre}{fact}'
        return f'{pre} {fact}'
    return _short_headline(line)


def _shrink_headline(line):
    if line and any(k in line for k in ('開市前', 'pre-market', '개장 전')):
        return _keep_frame(line)
    return _short_headline(line)


def _assemble_lang_lines(pairs, disc, extra=''):
    """Each headline followed by that language's URL, then the optional ticker block and disclaimer."""
    out = []
    for line, url in pairs:
        if line:
            out.append(line)
        if url:
            out.append(url)
    if extra:
        out.append(extra.strip('\n'))
    if disc:
        out.append(disc)
    return '\n'.join(out)


def _cap_pairs(pairs, disc):
    """Shorten the longest headline until the post is within 280. Language URLs stay.

    The cut is taken off the end, so a leading ticker and language marker stay.
    """
    ps = [(line, url) for line, url in pairs]
    text = _assemble_lang_lines(ps, disc)
    for _ in range(400):
        if xlen(text) <= 280:
            return text
        i = max(range(len(ps)), key=lambda k: xlen(ps[k][0] or ''))
        line, url = ps[i]
        if not line or xlen(line) <= 12:
            break
        drop = 8 if len(line) > 24 else 2
        cut = line[:-drop].rstrip()
        if not cut or cut == line:
            break
        ps[i] = (cut + '…', url)
        text = _assemble_lang_lines(ps, disc)
    return text


def _fit_lang_lines(pairs, disc, shorten=True):
    """Fit headline/URL pairs into 280. Every language URL stays.

    Full disclaimer first, then SHORT['en']['disc'], then a shorter headline, then the ticker clause.
    """
    en = SHORT['en']['disc']

    def try_fit(ps, d):
        text = _assemble_lang_lines(ps, d)
        return text if xlen(text) <= 280 else None

    hit = try_fit(pairs, disc)
    if hit:
        return hit
    hit = try_fit(pairs, en)
    if hit or not shorten:
        return hit or _assemble_lang_lines(pairs, en)
    shrunk = [(_shrink_headline(line), url) for line, url in pairs]
    hit = try_fit(shrunk, disc) or try_fit(shrunk, en)
    if hit:
        return hit
    facts = [(_ticker_fact(line) or line, url) for line, url in shrunk]
    return try_fit(facts, en) or _cap_pairs(facts, en)


def _split_lang_post(text):
    """(headline, url) pairs and the disclaimer. Bullet lines are dropped. Missing URLs use premarket."""
    pairs, disc, pending = [], None, None
    for ln in (text or '').split('\n'):
        s = ln.strip()
        if not s or s.startswith('・'):
            continue
        if re.fullmatch(r'https?://\S+', s):
            if pending is not None:
                pairs.append((pending, s))
                pending = None
            elif pairs and pairs[-1][1] is None:
                pairs[-1] = (pairs[-1][0], s)
            else:
                pairs.append(('', s))
            continue
        um = re.search(r'https?://\S+', s)
        if um and um.start() > 0:
            if pending is not None:
                pairs.append((pending, None))
                pending = None
            pairs.append((s[:um.start()].strip(), um.group(0)))
            continue
        if s.startswith(('⚠', '#')):
            disc = s
            continue
        if pending is not None:
            pairs.append((pending, None))
        pending = s
    if pending is not None:
        pairs.append((pending, None))
    filled = []
    for i, (head, url) in enumerate(pairs):
        if not url and i < len(LANGS):
            url = _x_link(LANGS[i], 'premarket')
        filled.append((head, url))
    return filled, disc or _disc_line()


def trilingual_text(posts, campaign):
    """One X post, zh then en then ko, from the headlines and joint-bull lines already in posts[lang]['x'].

    Each language headline is followed by that language's home URL (same utm: source x, this campaign).
    Full form also keeps the joint-bull ticker lines and the one-line disclaimer. When that is over 280
    (X count, each URL 23), the short form drops the ticker lines, then SHORT['en']['disc'], then the
    ticker clause only. The three language links stay. Returns (text, form) or None when there is no headline.
    """
    rows = []
    for lang in LANGS:
        p = posts.get(lang) if isinstance(posts, dict) else None
        head, _ = _x_head_body(p.get('x') if isinstance(p, dict) else '')
        if not head:
            continue
        rows.append((lang, head, _short_headline(head)))
    if not rows:
        return None
    urls = [_x_link(lang, campaign) for lang, _, _ in rows]
    disc = _disc_line()
    tick = _ticker_block(posts)
    full_pairs = [(head, url) for (_, head, _), url in zip(rows, urls)]
    full = _assemble_lang_lines(full_pairs, disc, tick)
    if xlen(full) <= 280:
        return full, 'full'
    short_pairs = [(short, url) for (_, _, short), url in zip(rows, urls)]
    text = _assemble_lang_lines(short_pairs, disc)
    if xlen(text) <= 280:
        return text, 'short'
    text = _assemble_lang_lines(short_pairs, SHORT['en']['disc'])
    if xlen(text) <= 280:
        return text, 'short'
    facts = [(_ticker_fact(short) or short, url) for (_, _, short), url in zip(rows, urls)]
    text = _assemble_lang_lines(facts, SHORT['en']['disc'])
    if xlen(text) > 280:
        text = _cap_pairs(facts, SHORT['en']['disc'])
    return text, 'short'


def _text_ticker(text):
    """The first $TICKER the X text features, or None."""
    m = _XTICK.search(text or '')
    return m.group(1) if m else None


def _x_headlines(text):
    """zh/en/ko headline lines from a trilingual X post, verbatim."""
    heads = []
    for ln in (text or '').split('\n'):
        s = ln.strip()
        if not s:
            continue
        if re.search(r'https?://', s) or s.startswith('⚠') or s.startswith('#') or s.startswith('・'):
            continue
        heads.append(s)
        if len(heads) == 3:
            break
    return {lang: heads[i] for i, lang in enumerate(LANGS) if i < len(heads)}


_BUNDLE = None


def _picture_bundle(day=None):
    """langs, items, dash-data, daily stats — the same sources build() uses. Cached per process."""
    global _BUNDLE
    st = read_json(work('stats.json'))
    if not st or 'daily' not in st:
        return None, None, None, None
    day = day or st.get('today')
    key = (day, st.get('today'), st['daily'].get('from'), st['daily'].get('to'))
    if _BUNDLE and _BUNDLE[0] == key:
        return _BUNDLE[1]
    d = _dash_data()
    ch = read_json('data/consensus-history.json', {'days': {}})
    langs, items = build(d, st['daily'], ch, day)
    bundle = (langs, items, d, st['daily'])
    _BUNDLE = (key, bundle)
    return bundle


def _x_facts(d, items, s=None):
    """Per-ticker facts frozen with the captions, so later card rebuilds match the text."""
    av = lambda h: d['accounts'].get(h, {}).get('avatar') or d.get('avmini', {}).get(h, '')
    out = {}
    for x in items:
        facts = {k: x[k] for k in ('n', 'bull', 'bear', 'streak', 'spark', 'd1')}
        row = next((r for r in ((s or {}).get('top') or []) if r.get('t') == x['t']), None)
        if row and row.get('accounts') is not None:
            facts['n'] = row['accounts']  # accounts mentioning, as on the card's label
        accs = x.get('accs') or []
        facts['avs'] = [av(h) for h in accs[:4]]
        more = len(accs) - 4
        if more > 0:
            facts['more'] = more
        out[x['t']] = facts
    return out


def xcard_data(sp, kind, ticker, text):
    """Per-ticker card payload from build() / stats / dash-data. Omit a field when it is missing."""
    data = {'ticker': ticker, 'date': sp.get('date') or '', 'kind': kind}
    heads = _x_headlines(text)
    if heads:
        data['heads'] = heads
    langs, items, d, daily = _picture_bundle(sp.get('date'))
    zh = (langs or {}).get('zh') or {}
    if zh.get('mode'):
        data['mode'] = zh['mode']
    if zh.get('tape'):
        data['tape'] = zh['tape']
    xf = sp.get('x_facts')
    snap = xf.get(ticker) if isinstance(xf, dict) else None
    if isinstance(snap, dict):
        for k in ('n', 'bull', 'bear'):
            if snap.get(k) is not None:
                data[k] = snap[k]
        if snap.get('streak') and snap['streak'] >= 2:
            data['streak'] = snap['streak']
        if snap.get('spark'):
            data['spark'] = snap['spark']
        if snap.get('d1') is not None:
            data['d1'] = snap['d1']
        if snap.get('avs'):
            data['avs'] = snap['avs']
        if snap.get('more'):
            data['more'] = snap['more']
        return data
    hit = next((x for x in (items or []) if x.get('t') == ticker), None)
    top_row = next((x for x in ((daily or {}).get('top') or []) if x.get('t') == ticker), None)
    av = None
    if d:
        av = lambda h: d['accounts'].get(h, {}).get('avatar') or d.get('avmini', {}).get(h, '')
    if top_row:
        if top_row.get('accounts') is not None:
            data['n'] = top_row['accounts']
        if top_row.get('bull_accounts') is not None:
            data['bull'] = top_row['bull_accounts']
        if top_row.get('bear_accounts') is not None:
            data['bear'] = top_row['bear_accounts']
        accs = top_row.get('accs') or []
        if av and accs and 'avs' not in data:
            avs = [av(h) for h in accs[:4] if av(h)]
            if avs:
                data['avs'] = avs
            extra = len(accs) - len(avs or [])
            if extra > 0:
                data['more'] = extra
    if hit:
        if 'bull' not in data and hit.get('bull') is not None:
            data['bull'] = hit['bull']
        if 'bear' not in data and hit.get('bear') is not None:
            data['bear'] = hit['bear']
        if 'n' not in data and hit.get('n') is not None:
            data['n'] = hit['n']
        if hit.get('streak') and hit['streak'] >= 2:
            data['streak'] = hit['streak']
        if hit.get('spark'):
            data['spark'] = hit['spark']
        if hit.get('d1') is not None:
            data['d1'] = hit['d1']
        accs = hit.get('accs') or []
        if av and accs:
            avs = [av(h) for h in accs[:4] if av(h)]
            if avs:
                data['avs'] = avs
            extra = len(accs) - 4
            if extra > 0:
                data['more'] = extra
            else:
                data.pop('more', None)
    if 'spark' not in data and d:
        c = [r[1] for r in (d.get('prices', {}).get(ticker) or {}).get('c', []) if r[1] is not None]
        spark = c[-22:]
        if len(spark) > 1:
            data['spark'] = spark
        if len(c) > 1 and c[-2]:
            data['d1'] = round((c[-1] / c[-2] - 1) * 100, 2)
    return data


def xcard_job(sp, kind, ticker, text, out=None):
    return {'kind': kind, 'ticker': ticker, 'date': sp.get('date') or '',
            'out': out or f'og/x-{kind}.png', 'data': xcard_data(sp, kind, ticker, text)}


def _queue_xcard(job):
    """Merge a per-ticker X card job into work/xcards.json, replacing the same kind."""
    path = work('xcards.json')
    raw = read_json(path, {'jobs': []})
    jobs = raw.get('jobs') if isinstance(raw, dict) else raw
    if not isinstance(jobs, list):
        jobs = []
    jobs = [j for j in jobs if j.get('kind') != job.get('kind')]
    jobs.append(job)
    write_json(path, {'jobs': jobs}, indent=1)


def x_image(sp, kind, ticker=None):
    """Per-ticker X card when the text features a $TICKER; otherwise the generic English picture."""
    if ticker:
        day = sp.get('date') or ''
        return f'{SITE}og/x-{kind}.png?v={day}-{ticker}'
    return (sp.get('images') or {}).get('en') or ''


_PM_MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def _minus_urls(text):
    """Post body with every URL removed, for comparing premarket with afterclose."""
    return re.sub(r'https?://\S+', '', text or '').strip()


def _count(rec, key):
    """Integer count stored on an x_facts row, or None when that count is not a real number."""
    if not isinstance(rec, dict) or rec.get(key) is None or isinstance(rec.get(key), bool):
        return None
    v = rec[key]
    if isinstance(v, int) and v >= 0:
        return v
    if isinstance(v, float) and v >= 0 and v.is_integer():
        return int(v)
    if isinstance(v, str) and re.fullmatch(r'\d+', v.strip()):
        return int(v.strip())
    return None


def _pm_md_mon(sp):
    """(M/D, Mon D) for the premarket framing. `sp['date']` when it is a real day, else the afterclose date."""
    day = sp.get('date') if isinstance(sp, dict) else None
    if isinstance(day, str):
        try:
            dt = datetime.strptime(day, '%Y-%m-%d')
            return f'{dt.month}/{dt.day}', f'{_PM_MONTHS[dt.month - 1]} {dt.day}'
        except ValueError:
            pass
    text = _afterclose_text(sp) if isinstance(sp, dict) else ''
    m = _XDATE.search(text or '')
    if not m:
        return '', ''
    token = m.group(1)
    if '/' in token:
        mo, d = (int(p) for p in token.split('/'))
        mon = f'{_PM_MONTHS[mo - 1]} {d}' if 1 <= mo <= 12 else ''
        return f'{mo}/{d}', mon
    parts = token.split()
    if len(parts) == 2 and parts[0] in _PM_MONTHS and parts[1].isdigit():
        return f'{_PM_MONTHS.index(parts[0]) + 1}/{int(parts[1])}', f'{parts[0]} {int(parts[1])}'
    return '', ''


def _pm_frames(sp):
    """(zh, en, ko) framing lines. Chinese uses a fullwidth colon and no trailing space."""
    md, mon = _pm_md_mon(sp)
    zh = f'{md} 開市前：' if md else '開市前：'
    en = f'{mon} pre-market:' if mon else 'pre-market:'
    ko = f'{md} 개장 전:' if md else '개장 전:'
    return zh, en, ko


def _afterclose_text(sp):
    """Stored afterclose post, or the text trilingual_text would write for it."""
    tri = sp.get('x_trilingual') if isinstance(sp.get('x_trilingual'), dict) else None
    ac = tri.get('afterclose') if isinstance(tri, dict) else None
    if isinstance(ac, dict) and ac.get('text'):
        return ac['text']
    built = trilingual_text(sp.get('posts') or {}, 'afterclose')
    return built[0] if built else ''


def _remember_tickers(text, seen):
    for t in _XTICK.findall(text or ''):
        if t not in seen:
            seen.append(t)


def _afterclose_ticker_order(sp):
    """Tickers in the order the afterclose post names them.

    A shortened afterclose line often keeps only the headline ticker. The rest of the order is the
    headline plus the joint-bull block trilingual_text is cut down from, then any other x_facts key.
    """
    seen = []
    _remember_tickers(_afterclose_text(sp), seen)
    posts = sp.get('posts') or {}
    for lang in LANGS:
        p = posts.get(lang) if isinstance(posts, dict) else None
        head, _ = _x_head_body(p.get('x') if isinstance(p, dict) else '')
        _remember_tickers(head, seen)
    _remember_tickers(_ticker_block(posts), seen)
    return seen


def _premarket_rows(sp):
    """(ticker, bull) in afterclose order, using only x_facts rows that have a real bull count."""
    xf = sp.get('x_facts') if isinstance(sp.get('x_facts'), dict) else None
    if not xf:
        return []
    rows, seen = [], set()

    def take(t):
        if not isinstance(t, str) or t in seen or t not in xf:
            return
        bull = _count(xf[t], 'bull')
        if bull is None:
            return
        seen.add(t)
        rows.append((t, bull))

    for t in _afterclose_ticker_order(sp):
        take(t)
    for t in xf:
        take(t)
    return rows


def _lead_lines(sp, rows):
    """Three language lines. A bull tie leads with both tickers; otherwise the next ticker is a count only."""
    zh_f, en_f, ko_f = _pm_frames(sp)
    a, na = rows[0]
    tie = len(rows) >= 2 and rows[1][1] == na
    if tie:
        b = rows[1][0]
        zh = f'{zh_f}${a}、${b} 各 {na} 個帳號睇好'
        en = f'{en_f} ${a}, ${b}, {na} accounts bullish each'
        ko = f'{ko_f} ${a}·${b} 각각 계정 {na}개 강세'
    elif len(rows) >= 2:
        b, nb = rows[1]
        zh = f'{zh_f}${a} {na} 個帳號睇好 · ${b} {nb} 個'
        en = f'{en_f} ${a} {na} accounts bullish · ${b} {nb}'
        ko = f'{ko_f} ${a} 계정 {na}개 강세 · ${b} {nb}개'
    else:
        zh = f'{zh_f}${a} {na} 個帳號睇好'
        en = f'{en_f} ${a} {na} accounts bullish'
        ko = f'{ko_f} ${a} 계정 {na}개 강세'
    return zh, en, ko


def _fit_premarket(text):
    """Drop joint-bull bullets, then the long disclaimer, until the post is within 280.

    Each language line keeps its own URL. Headlines are shortened only after SHORT['en']['disc']
    still does not fit.
    """
    if xlen(text) <= 280:
        return text
    pairs, disc = _split_lang_post(text)
    return _fit_lang_lines(pairs, disc, shorten=True)


def _apply_frame(line, frame, token):
    s = line.strip()
    if s.startswith(frame):
        return s
    rest = s
    if token and s.startswith(token):
        rest = s[len(token):].lstrip(' ·・')
    if not rest:
        return frame
    if frame.endswith('：'):
        return f'{frame}{rest}'
    return f'{frame} {rest}'


def _prefix_premarket_headlines(text, sp):
    """Prefix each trilingual headline with the premarket framing. The framing already carries the date."""
    md, mon = _pm_md_mon(sp)
    posts = sp.get('posts') or {}
    langs = []
    for lang in LANGS:
        p = posts.get(lang) if isinstance(posts, dict) else None
        head, _ = _x_head_body(p.get('x') if isinstance(p, dict) else '')
        if head:
            langs.append(lang)
    if not langs:
        langs = list(LANGS)
    frames = {'zh': f'{md} 開市前：' if md else '開市前：',
              'en': f'{mon} pre-market:' if mon else 'pre-market:',
              'ko': f'{md} 개장 전:' if md else '개장 전:'}
    tokens = {'zh': md, 'en': mon, 'ko': md}
    lines, hi = [], 0
    for ln in (text or '').split('\n'):
        s = ln.strip()
        is_head = bool(s) and not re.search(r'https?://', s) and not s.startswith(('⚠', '#', '・'))
        if is_head and hi < len(langs):
            lang = langs[hi]
            lines.append(_apply_frame(s, frames[lang], tokens[lang]))
            hi += 1
        else:
            lines.append(ln)
    return '\n'.join(lines)


def _premarket_fallback(sp):
    """trilingual_text (campaign premarket) with each headline prefixed by the framing."""
    built = trilingual_text(sp.get('posts') or {}, 'premarket')
    if not built:
        return None
    text, form = built
    prefixed = _fit_premarket(_prefix_premarket_headlines(text, sp))
    return prefixed, 'short' if prefixed != text else form


def premarket_text(sp, force_fallback=False):
    """zh/en/ko premarket post. Bull counts come from x_facts, in afterclose ticker order.

    When the top two of that order tie on bull, both lead (`各 N` / `each` / `각각`).
    Otherwise the first ticker leads with its bull count and the next ticker is named with its count.
    Missing or empty x_facts uses trilingual headlines prefixed by the premarket framing.
    Returns (text, form) or None. Each language line has its own URL (campaign premarket), then
    _disc_line() or SHORT['en']['disc'] when that is what fits. xlen is at most 280.
    """
    if not isinstance(sp, dict):
        sp = {}
    ac = _minus_urls(_afterclose_text(sp))
    facts = None
    if not force_fallback:
        rows = _premarket_rows(sp)
        if rows:
            urls = [_x_link(lang, 'premarket') for lang in LANGS]
            lines = list(_lead_lines(sp, rows))
            text = _fit_lang_lines(list(zip(lines, urls)), _disc_line(), shorten=False)
            if xlen(text) > 280 and len(rows) >= 2:
                lines = list(_lead_lines(sp, rows[:1]))
                text = _fit_lang_lines(list(zip(lines, urls)), _disc_line(), shorten=False)
            if xlen(text) > 280:
                text = _fit_lang_lines(list(zip(lines, urls)), _disc_line(), shorten=True)
            if xlen(text) <= 280:
                facts = (text, 'short')
                if _minus_urls(text) != ac:
                    return facts
    built = _premarket_fallback(sp)
    if built:
        text, form = built
        if xlen(text) > 280:
            text = _fit_premarket(text)
        if facts is None or _minus_urls(text) != ac:
            return text, form
    return facts or built


def _counts_from_facts(sp, ticker):
    """bull/bear/n for the card, from x_facts only."""
    xf = sp.get('x_facts') if isinstance(sp.get('x_facts'), dict) else None
    snap = xf.get(ticker) if isinstance(xf, dict) else None
    if not isinstance(snap, dict):
        return None
    counts = {k: snap[k] for k in ('bull', 'bear', 'n') if k in snap and snap[k] is not None}
    return counts or None


def x_entry(sp, kind, force_fallback=False):
    """One x_trilingual entry, or None when there is no post to make.

    Premarket uses premarket_text. image_ticker is the first $TICKER in that text.
    Premarket card counts come from x_facts. Afterclose stays on trilingual_text.
    """
    if kind == 'premarket':
        built = premarket_text(sp, force_fallback=force_fallback)
    else:
        built = trilingual_text(sp.get('posts') or {}, kind)
    if not built:
        return None
    text, form = built
    ticker = _text_ticker(text)
    entry = {'post_at_hkt': X_WHEN[kind], 'text': text, 'image': x_image(sp, kind, ticker),
             'image_ticker': ticker, 'xlen': xlen(text), 'form': form}
    if ticker:
        job = xcard_job(sp, kind, ticker, text)
        _queue_xcard(job)
        if kind == 'premarket':
            counts = _counts_from_facts(sp, ticker)
        else:
            data = job['data']
            counts = {k: data[k] for k in ('bull', 'bear', 'n') if k in data}
        if counts:
            entry['counts'] = counts
    return entry


def build_x_trilingual(sp, rebuild_premarket=False):
    """premarket and afterclose. Rebuilds premarket when asked (the 2030 slot just got its picture).

    If the premarket body with URLs removed still equals afterclose, premarket is rebuilt from the
    framed-headline fallback so the two posts are not the same text.
    """
    tri = sp.get('x_trilingual')
    if not isinstance(tri, dict):
        tri = {}
    if rebuild_premarket or 'premarket' not in tri:
        entry = x_entry(sp, 'premarket')
        if entry:
            tri['premarket'] = entry
    if 'afterclose' not in tri:
        entry = x_entry(sp, 'afterclose')
        if entry:
            tri['afterclose'] = entry
    pm = tri.get('premarket') if isinstance(tri.get('premarket'), dict) else None
    ac = tri.get('afterclose') if isinstance(tri.get('afterclose'), dict) else None
    if pm and ac and pm.get('text') and ac.get('text') and _minus_urls(pm['text']) == _minus_urls(ac['text']):
        entry = x_entry(sp, 'premarket', force_fallback=True)
        if entry:
            tri['premarket'] = entry
    if not tri:
        return None
    return {k: tri[k] for k in ('premarket', 'afterclose') if k in tri}


def build_ig_threads_daily(sp):
    """Where the bot posts the 12:30 pictures and the 19:00 single-picture / text posts."""
    posts = sp.get('posts') or {}
    images = sp.get('images') or {}
    day = sp['date']
    slot = (sp.get('slots') or {}).get('1230') if isinstance(sp.get('slots'), dict) else None
    if not isinstance(slot, dict) or (sp.get('date') and slot.get('day') and slot.get('day') != sp.get('date')):
        slot = {}
    out = {}
    for lang in LANGS:
        row = {}
        sl_posts = (slot.get('posts') or {}).get(lang)
        sl_imgs = (slot.get('images') or {}).get(lang)
        if isinstance(sl_posts, dict) and sl_imgs:
            row['image_post'] = {
                'slot': '1230',
                'field': f'slots.1230.posts.{lang}.instagram / .threads',
                'post_at_hkt': (slot.get('post_at') or {}).get(lang) or '',
                'images': list(sl_imgs)}
        p = posts.get(lang)
        if isinstance(p, dict) and (p.get('instagram') or p.get('threads')):
            item = {'field': f'posts.{lang}.instagram / posts.{lang}.threads', 'post_at_hkt': '19:00'}
            if images.get(lang):
                item['image'] = images[lang]
            row['text_post'] = item
            row['ig_image'] = f'{SITE}og/ig-{lang}.png?v={day}'
        if row:
            out[lang] = row
    return out or None


def attach_new_posts(sp, rebuild_premarket=False):
    """Add the new keys. Does not change facebook, x, or any other existing post text."""
    if isinstance(sp.get('posts'), dict):
        add_facebook_ctas(sp['posts'])
    for sl in (sp.get('slots') or {}).values():
        if isinstance(sl, dict):
            add_facebook_ctas(sl.get('posts'))
    tri = build_x_trilingual(sp, rebuild_premarket=rebuild_premarket)
    if tri:
        sp['x_trilingual'] = tri
    daily = build_ig_threads_daily(sp)
    if daily:
        sp['ig_threads_daily'] = daily
    return sp


def _box(title, text, n, h='h3'):
    return (f'<{h}>{title}</{h}><textarea readonly rows="{n}">{html.escape(text)}</textarea>'
            '<button onclick="navigator.clipboard.writeText(this.previousElementSibling.value);this.textContent=\'已複製 ✓\'">複製</button>')


def _xtri_html(sp):
    tri = sp.get('x_trilingual') if isinstance(sp.get('x_trilingual'), dict) else None
    if not tri:
        return ''
    names = {'premarket': '開市前', 'afterclose': '收市後'}
    blocks = []
    for key in ('premarket', 'afterclose'):
        e = tri.get(key)
        if not isinstance(e, dict) or not e.get('text'):
            continue
        img = e.get('image') or ''
        pic = f'<a href="{html.escape(img)}" download><img src="{html.escape(img)}" alt=""></a>' if img else ''
        when = html.escape(str(e.get('post_at_hkt') or ''))
        form = html.escape(str(e.get('form') or ''))
        n = e.get('xlen', '')
        blocks.append(f'<h3>{names.get(key, key)} · {when} HKT · {n}/280 · {form}</h3>{pic}'
                      f'<textarea readonly rows="8">{html.escape(e["text"])}</textarea>'
                      '<button onclick="navigator.clipboard.writeText(this.previousElementSibling.value);this.textContent=\'已複製 ✓\'">複製</button>')
    if not blocks:
        return ''
    return '<section class="xtri"><h2>X 三語帖</h2>' + ''.join(blocks) + '</section>'


def _ig_daily_html(sp):
    daily = sp.get('ig_threads_daily') if isinstance(sp.get('ig_threads_daily'), dict) else None
    if not daily:
        return ''
    names = {'zh': '中文', 'en': 'English', 'ko': '한국어'}
    rows = []
    for lang in LANGS:
        row = daily.get(lang)
        if not isinstance(row, dict):
            continue
        img_p = row.get('image_post') if isinstance(row.get('image_post'), dict) else {}
        txt_p = row.get('text_post') if isinstance(row.get('text_post'), dict) else {}
        thumbs = ''.join(f'<a href="{html.escape(u)}" download><img src="{html.escape(u)}" alt=""></a>'
                         for u in (img_p.get('images') or []))
        one = txt_p.get('image') or ''
        one_html = f'<a href="{html.escape(one)}" download><img src="{html.escape(one)}" alt=""></a>' if one else ''
        cells = (('語言', names[lang]),
                 ('圖帖', f'<code>{html.escape(img_p.get("field") or "—")}</code>'),
                 ('圖帖時間', html.escape(str(img_p.get("post_at_hkt") or "—"))),
                 ('圖片', thumbs or '—'),
                 ('文字帖', f'<code>{html.escape(txt_p.get("field") or "—")}</code>'),
                 ('文字時間', html.escape(str(txt_p.get("post_at_hkt") or "—"))),
                 ('IG 圖', one_html or '—'))
        rows.append('<tr>' + ''.join(
            f'<td data-label="{html.escape(label)}"{" class=\"pics\"" if label in ("圖片", "IG 圖") else ""}>{val}</td>'
            for label, val in cells) + '</tr>')
    if not rows:
        return ''
    return ('<section class="daily"><h2>IG / Threads 每日</h2>'
            '<p>12:30 圖帖用該時段多圖。19:00 文字帖：IG 配一張圖，Threads 只發文字。</p>'
            '<table><tr><th>語言</th><th>圖帖</th><th>時間</th><th>圖片</th>'
            '<th>文字帖</th><th>時間</th><th>IG 圖</th></tr>'
            + ''.join(rows) + '</table></section>')


def social_page(sp):
    """A plain page for Tim to read the day's posts and save the pictures (not for search engines)."""
    rows = []
    for lang, name in (('zh', '中文'), ('en', 'English'), ('ko', '한국어')):
        img = sp['images'][lang]
        story = sp['stories'][lang]
        p = sp['posts'][lang]
        cta = p.get('facebook_cta') if isinstance(p, dict) else None
        rows.append(f'''<section><h2>{name}</h2><a href="{html.escape(img)}" download><img src="{html.escape(img)}" alt=""></a>
{_box('Instagram', p['instagram'], 18)}{_box('Threads', p['threads'], 10)}{_box('X', p['x'], 6)}
{_box('Reddit 標題', p['reddit']['title'], 2)}{_box('Reddit 內文', p['reddit']['body'], 14)}{_box('Facebook', p['facebook'], 18)}
{( _box('Facebook 電子報', cta, 18) if cta else '' )}
{_box('IG Story hashtag', p['story'], 2)}<h3>IG Story（1080×1920）</h3><a href="{html.escape(story)}" download><img class="story" src="{html.escape(story)}" alt=""></a></section>''')
    extras = _xtri_html(sp) + _ig_daily_html(sp)
    old = '<h2 style="margin-top:32px">舊格式（單圖，只作參考）</h2>' if sp.get('slots') else ''
    return f'''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="/favicon.ico" sizes="any"><link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="robots" content="noindex"><title>每日社交媒體貼文 {sp['date']}｜The Crowd Tape</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;margin:0 auto;max-width:760px;padding:16px;background:#f7f8fb;color:#151a2c;overflow-wrap:anywhere}}
html{{overflow-x:clip}}
section{{background:#fff;border-radius:14px;padding:16px;margin:16px 0;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
img{{width:100%;border-radius:10px}}img.story{{width:min(100%,320px);display:block;margin-top:6px}}textarea{{width:100%;box-sizing:border-box;font:inherit;margin-top:4px}}h3{{margin:18px 0 0;font-size:15px}}
button{{margin-top:8px;padding:8px 16px;border-radius:999px;border:0;background:#151a2c;color:#fff;font:inherit}}
.money-bar,.site-nav{{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;max-width:100%;min-width:0}}
.money-bar{{margin:0 0 12px;padding:8px 10px;border:1px dashed #c9c3b8;border-radius:12px;background:#fff;font-size:14px;font-weight:700}}
.tag{{font-size:11px;font-weight:700;border:1px solid #ddd;border-radius:999px;padding:1px 8px;color:#666}}
.site-foot{{margin-top:18px;padding-top:12px;border-top:1px solid #e4e7ef;font-size:13px;color:#5c6578}}
a{{color:#8a5a22}}
table{{width:100%;border-collapse:collapse;font-size:14px}}td,th{{border-bottom:1px solid #e4e7ef;padding:6px 4px;text-align:left;vertical-align:top}}
code{{font-size:12px}}.daily{{overflow-x:auto}}td.pics a{{display:inline-block;width:48px;margin:0 4px 4px 0}}td.pics img{{width:48px;height:auto}}
.xtri img{{width:min(100%,420px);display:block}}
@media (max-width:700px){{.daily table,.daily tr,.daily td{{display:block;width:auto}}.daily tr:first-child{{display:none}}
.daily td{{border:0;padding:2px 0}}.daily td::before{{content:attr(data-label);font-weight:700;display:block;font-size:12px;color:#5c6578}}
.daily tr{{padding:10px 0;border-bottom:1px solid #e4e7ef}}}}</style>
<nav class="site-nav" aria-label="網站"><a href="/zh/tools/">工具</a> · <a href="/zh/support/">支持我哋</a></nav>
<nav class="money-bar" aria-label="推廣"><span class="tag">推廣</span><a href="/zh/tools/">工具</a><a href="/zh/support/">支持我哋</a><a href="https://www.tradingview.com/?aff_id=1172819" rel="sponsored noopener" target="_blank" data-tool="tradingview" data-placement="money-bar">TradingView</a><a href="https://www.stockrover.com/thecrowdtape" rel="sponsored nofollow noopener" target="_blank" data-tool="stockrover" data-placement="money-bar">Stock Rover</a></nav>
<h1>{sp['date']} 社交媒體貼文</h1><p>{html.escape(sp['window'])}｜製作時間 {sp['made_hkt']} HKT｜撳圖片可以下載｜<a href="/social/tutorial.html">週末教學貼文</a>｜<a href="/social/macro.html">星期六宏觀貼文</a></p>
<!--slots-->
{extras}{old}
{''.join(rows)}
<footer class="site-foot"><p><a href="/zh/tools/">工具</a> · <a href="/zh/support/">支持我哋</a> · <a href="/zh/newsletter/">電子報</a> · <a href="https://www.tradingview.com/?aff_id=1172819" rel="sponsored noopener" target="_blank" data-tool="tradingview">TradingView <span class="tag">推廣</span></a> · <a href="https://www.stockrover.com/thecrowdtape" rel="sponsored nofollow noopener" target="_blank" data-tool="stockrover">Stock Rover <span class="tag">推廣</span></a></p></footer>
<script>document.addEventListener('click',function(e){{var a=e.target.closest&&e.target.closest('a[data-tool]');if(a&&window.gtag)gtag('event','affiliate_click',{{tool:a.dataset.tool,lang:document.documentElement.lang}});}});</script>
</html>
'''


FEED_KEEP = 30  # days kept in each RSS feed
FEED_META = {'zh': ('The Crowd Tape｜X 大神每日共識', 'zh-Hant-HK', '每日整理 X 上美股大神的共同看好、看淡同分歧。唔構成投資建議。'),
             'en': ('The Crowd Tape · Daily X consensus', 'en', 'What top X stock accounts agree and disagree on, once a day. Not investment advice.'),
             'ko': ('The Crowd Tape · X 일일 컨센서스', 'ko', 'X 주식 인플루언서들의 공동 강세·약세·의견 엇갈림을 매일 정리합니다. 투자 조언 아님.')}


def write_feeds(sp):
    """/<lang>/feed.xml: one item per day (the day's snapshot), newest first, last FEED_KEEP days."""
    when = datetime.strptime(sp['made_hkt'], '%Y-%m-%d %H:%M').replace(tzinfo=HK)
    for lang in LANGS:
        path = f'{lang}/feed.xml'
        old = open(path, encoding='utf-8').read() if os.path.exists(path) else ''
        items = [i for i in re.findall(r'<item>.*?</item>', old, re.S) if f'#{sp["date"]}<' not in i]
        p = sp['posts'][lang]
        paras = []
        for block in p['reddit']['body'].split('\n\n'):
            block = html.escape(block.lstrip('> '))
            block = re.sub(r'\[(https?://[^\]]+)\]\((https?://[^)]+)\)', r'<a href="\2">\1</a>', block)
            paras.append('<p>' + block.replace('\n', '<br>') + '</p>')
        body = f'<p><img src="{html.escape(sp["images"][lang])}" alt=""></p>' + ''.join(paras)
        item = (f'<item><title>{html.escape(p["reddit"]["title"])}</title><link>{SITE}{lang}/</link>'
                f'<guid isPermaLink="false">{SITE}{lang}/#{sp["date"]}</guid>'
                f'<pubDate>{when.strftime("%a, %d %b %Y %H:%M:%S %z")}</pubDate>'
                f'<description><![CDATA[{body}]]></description></item>')
        title, code, desc = FEED_META[lang]
        xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
               f'<title>{html.escape(title)}</title><link>{SITE}{lang}/</link><description>{html.escape(desc)}</description>'
               f'<language>{code}</language><lastBuildDate>{when.strftime("%a, %d %b %Y %H:%M:%S %z")}</lastBuildDate>'
               f'<atom:link href="{SITE}{lang}/feed.xml" rel="self" type="application/rss+xml"/>'
               f'<image><url>{SITE}assets/icon-192.png</url><title>{html.escape(title)}</title><link>{SITE}{lang}/</link></image>\n'
               + '\n'.join([item] + items[:FEED_KEEP - 1]) + '\n</channel></rss>\n')
        os.makedirs(lang, exist_ok=True)
        open(path, 'w', encoding='utf-8').write(xml)


# Side labels and the main title use the real list length (5 kept when 5).
TOP5_META = {
    'zh': {'bull_x': '看好帳號', 'bear_x': '看淡帳號', 'none': '今日暫無', 'win': '數據範圍'},
    'en': {'bull_x': 'Bullish accounts', 'bear_x': 'Bearish accounts', 'none': 'None today', 'win': 'Data window'},
    'ko': {'bull_x': '강세 계정', 'bear_x': '약세 계정', 'none': '오늘 없음', 'win': '데이터 범위'},
}


def top5_labels(lang, n_bull, n_bear):
    """Heading and column labels for the real counts on each side."""
    n_bull = int(n_bull or 0)
    n_bear = int(n_bear or 0)
    if lang == 'zh':
        bull, bear = f'最看好 {n_bull} 隻', f'最看淡 {n_bear} 隻'
        heading = f'今日 X 大神共識：{bull}／{bear}'
    elif lang == 'ko':
        bull, bear = f'강세 상위 {n_bull}종목', f'약세 상위 {n_bear}종목'
        heading = f'오늘 X 인플루언서 컨센서스: {bull} / {bear}'
    else:
        bull, bear = f'Top {n_bull} bullish', f'Top {n_bear} bearish'
        heading = f'Top X accounts consensus today: {bull} / {bear}'
    return {'heading': heading, 'bull': bull, 'bear': bear}


def top5_copy(lang, n_bull=5, n_bear=5):
    lang = lang if lang in LANGS else 'en'
    out = dict(TOP5_META[lang])
    out.update(top5_labels(lang, n_bull, n_bear))
    return out


TOP5_COPY = {lang: top5_copy(lang, 5, 5) for lang in LANGS}
WEEK_COPY = {
    'zh': {'head': '本週共識變化', 'bulls': '本週最看好', 'bears': '本週最看淡',
           'joined_bull': '新入看好', 'dropped_bull': '退出看好', 'joined_bear': '新入看淡', 'dropped_bear': '退出看淡',
           'no_change': '本週暫無新增或退出', 'bull_total': '看好', 'bear_total': '看淡'},
    'en': {'head': "This week's consensus changes", 'bulls': 'Most bullish this week', 'bears': 'Most bearish this week',
           'joined_bull': 'Joined bullish', 'dropped_bull': 'Left bullish', 'joined_bear': 'Joined bearish', 'dropped_bear': 'Left bearish',
           'no_change': 'No joins or drops this week', 'bull_total': 'Bullish', 'bear_total': 'Bearish'},
    'ko': {'head': '이번 주 컨센서스 변화', 'bulls': '이번 주 가장 강세', 'bears': '이번 주 가장 약세',
           'joined_bull': '새로 강세', 'dropped_bull': '강세에서 제외', 'joined_bear': '새로 약세', 'dropped_bear': '약세에서 제외',
           'no_change': '이번 주 신규·이탈 없음', 'bull_total': '강세', 'bear_total': '약세'},
}
WEEK_NOTE = (
    '本週共識變化. Counts come only from data/writeup-input.json weekly: '
    'bull[].nb (accounts bullish), bear[].nr (accounts bearish), bull_total, bear_total. '
    'Joins and drops compare bull and bear ticker lists in data/consensus-history.json '
    'on the first day versus the last day inside weekly.from–weekly.to. '
    'Not investment advice.'
)


def _is_num(n):
    return isinstance(n, (int, float)) and not isinstance(n, bool)


def _as_int(n):
    """Whole floats become ints so a count of 2.0 is stored as 2."""
    if isinstance(n, float) and n == int(n):
        return int(n)
    return n


def _as_day(s):
    m = re.match(r'(\d{4}-\d{2}-\d{2})', str(s or '').strip())
    return m.group(1) if m else ''


def _is_friday(day):
    day = _as_day(day)
    return bool(day) and datetime.strptime(day, '%Y-%m-%d').weekday() == 4


def _is_weekend(day):
    """Saturday or Sunday on the calendar date (the social run uses HKT dates)."""
    day = _as_day(day)
    return bool(day) and datetime.strptime(day, '%Y-%m-%d').weekday() >= 5


def _ticker_sym(t):
    return re.sub(r'[^A-Z0-9.\-]', '', str(t or '').strip().lstrip('$').upper())


def _side_rows(rows, key, limit=5):
    """{t, n} in the given order. n is that side's count only. Missing counts are skipped."""
    out = []
    for r in rows or []:
        if limit is not None and len(out) >= limit:
            break
        if not isinstance(r, dict):
            continue
        t = _ticker_sym(r.get('t'))
        n = r.get(key)
        if not t or not _is_num(n):
            continue
        out.append({'t': t, 'n': _as_int(n)})
    return out


def _acc(lang, n):
    if lang == 'zh':
        return f'{n} 個帳號'
    if lang == 'ko':
        return f'계정 {n}개'
    return f'{n} account' if n == 1 else f'{n} accounts'


def _camp_url(lang, platform, campaign, ticker=None):
    src = PLATFORM[platform]
    url = stock_url(lang, ticker) if ticker else page_url(lang)
    return tag_url(url, src, campaign)


def _primary_tag(lang):
    return tags(lang, []).split()[0]


def _hash_tags(tickers):
    out = []
    for t in tickers:
        if re.fullmatch(r'[A-Z]{1,6}', t) and f'#{t}' not in out:
            out.append(f'#{t}')
    return out


def _trim_x(text, limit=280):
    lines = (text or '').split('\n')
    while lines and xlen('\n'.join(lines)) > limit:
        lines.pop()
    return '\n'.join(lines).strip()


def _xside(label, rows, none):
    if not rows:
        return f'{label}: {none}'
    return label + ': ' + ' · '.join(f'${r["t"]} {r["n"]}' for r in rows)


def _x_top5_text(lang, day, window, bulls, bears):
    """One X post: heading, date, window, both lists, one link, disclaimer, hashtags. xlen <= 280."""
    L = top5_copy(lang, len(bulls), len(bears))
    link = _camp_url(lang, 'x', 'top5', bulls[0]['t'] if bulls else None)
    bs, rs = list(bulls), list(bears)
    extra = _hash_tags([r['t'] for r in bs + rs])

    def render(bs, rs, extra):
        lines = [L['heading']]
        if day:
            lines.append(day)
        if window:
            lines.append(f"{L['win']}: {window}")
        lines.append(_xside(L['bull_x'], bs, L['none']))
        lines.append(_xside(L['bear_x'], rs, L['none']))
        lines.append(link)
        lines.append(SHORT[lang]['disc'])
        lines.append(' '.join([_primary_tag(lang), *extra]))
        return '\n'.join(lines)

    guard = 0
    while guard < 200:
        guard += 1
        text = render(bs, rs, extra)
        if xlen(text) <= 280:
            return text
        if extra:
            extra = extra[:-1]
            continue
        if len(rs) > 1 and len(rs) >= len(bs):
            rs = rs[:-1]
            extra = _hash_tags([r['t'] for r in bs + rs])
            continue
        if len(bs) > 1:
            bs = bs[:-1]
            extra = _hash_tags([r['t'] for r in bs + rs])
            continue
        if len(rs) > 1:
            rs = rs[:-1]
            extra = _hash_tags([r['t'] for r in bs + rs])
            continue
        break
    text = render(bs, rs, [])
    return text if xlen(text) <= 280 else _trim_x(text)


def top5_ig_key_line(lang, bulls, bears):
    """Instagram line 1: lead bull and lead bear with their real counts.

    zh '最看好 $RSP（3 個帳號）・最看淡 $QQQ（5 個帳號）'
    en 'Most bullish $RSP (3 accounts) · most bearish $QQQ (5 accounts)'
    ko '가장 강세 $RSP (계정 3개) · 가장 약세 $QQQ (계정 5개)'
    Empty when neither side has a counted row. One side alone is that clause only.
    """
    lang = lang if lang in LANGS else 'en'

    def lead(rows):
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            t = _ticker_sym(row.get('t'))
            n = row.get('n')
            if t and _is_num(n):
                return t, _as_int(n)
        return None

    b, r = lead(bulls), lead(bears)
    if lang == 'zh':
        bits = []
        if b:
            bits.append(f'最看好 ${b[0]}（{_acc("zh", b[1])}）')
        if r:
            bits.append(f'最看淡 ${r[0]}（{_acc("zh", r[1])}）')
        return '・'.join(bits)
    if lang == 'ko':
        bits = []
        if b:
            bits.append(f'가장 강세 ${b[0]} ({_acc("ko", b[1])})')
        if r:
            bits.append(f'가장 약세 ${r[0]} ({_acc("ko", r[1])})')
        return ' · '.join(bits)
    if b and r:
        return f'Most bullish ${b[0]} ({_acc("en", b[1])}) · most bearish ${r[0]} ({_acc("en", r[1])})'
    if b:
        return f'Most bullish ${b[0]} ({_acc("en", b[1])})'
    if r:
        return f'Most bearish ${r[0]} ({_acc("en", r[1])})'
    return ''


def _list_lines(lang, label, rows, platform=None):
    lines = [label]
    if not rows:
        lines.append(top5_copy(lang).get('none') or TOP5_META[lang]['none'])
        return lines
    for r in rows:
        lines.append(f'・${r["t"]} {_acc(lang, r["n"])}')
        if platform:
            lines.append(_camp_url(lang, platform, 'top5', r['t']))
    return lines


def _long_top5_text(lang, day, window, bulls, bears, platform):
    """Facebook lists every name. Instagram has no URLs: one bio line and 3–5 hashtags.

    Instagram line 1 is the lead-bull / lead-bear key point. The old heading and
    every list row stay under it.
    """
    L = top5_copy(lang, len(bulls), len(bears))
    ig = platform == 'instagram'
    parts = []
    if ig:
        key = top5_ig_key_line(lang, bulls, bears)
        if key:
            parts.append(key)
    parts.append(L['heading'])
    meta = [ln for ln in (day, f"{L['win']}: {window}" if window else '') if ln]
    if meta:
        parts.append('\n'.join(meta))
    parts.append('\n'.join(_list_lines(lang, L['bull'], bulls, None if ig else platform)))
    parts.append('\n'.join(_list_lines(lang, L['bear'], bears, None if ig else platform)))
    if ig:
        parts.append(IG_BIO[lang])
        parts.append(SHORT[lang]['disc'])
        parts.append(ig_tags(lang, [r['t'] for r in bulls + bears]))
        return sanitize_instagram('\n\n'.join(parts), lang)
    parts.append(SHORT[lang]['disc'])
    parts.append(tags(lang, [r['t'] for r in bulls + bears]))
    return '\n\n'.join(parts)


def _threads_top5_text(lang, day, window, bulls, bears):
    """Threads caption passed through fit_threads. The stock link lives in first_comment, not here."""
    L = top5_copy(lang, len(bulls), len(bears))
    parts = [L['heading']]
    meta = [ln for ln in (day, f"{L['win']}: {window}" if window else '') if ln]
    if meta:
        parts.append('\n'.join(meta))
    parts.append('\n'.join(_list_lines(lang, L['bull'], bulls)))
    parts.append('\n'.join(_list_lines(lang, L['bear'], bears)))
    parts.append(SHORT[lang]['disc'])
    parts.append(tags(lang, [r['t'] for r in bulls + bears]))
    return fit_threads('\n\n'.join(parts), lang)


def _decorate_top5_posts(posts, bulls, bears):
    """X keeps its in-body link. Threads and Facebook move theirs into first_comment."""
    for lang in LANGS:
        p = posts[lang]
        fc = {'threads': SHORT[lang]['live'] + _camp_url(lang, 'threads', 'top5', bulls[0]['t'] if bulls else None)}
        hl = {
            'x': 'https://thecrowdtape.com' in (p.get('x') or ''),
            'instagram': False,
            'threads': True,
            'facebook': bool(bulls or bears),
        }
        if bulls or bears:
            fc['facebook'] = '\n'.join(
                SHORT[lang]['live'] + _camp_url(lang, 'facebook', 'top5', r['t'])
                for r in list(bulls) + list(bears))
        p['first_comment'] = fc
        p['has_link'] = hl
    return posts


def _top5_card_data(slot, lang):
    bulls, bears = slot.get('bull') or [], slot.get('bear') or []
    L = top5_copy(lang, len(bulls), len(bears))
    return {'lang': lang, 'date': slot.get('date') or '', 'window': slot.get('window') or '',
            'win_label': L['win'], 'heading': L['heading'], 'bull_label': L['bull'], 'bear_label': L['bear'],
            'none': L['none'], 'bull': bulls, 'bear': bears,
            'foot': SHORT[lang]['disc']}


def _parse_daily_clock(s):
    """Parse daily.from / daily.to / a window fragment into an HKT datetime."""
    s = str(s or '').strip()
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})', s)
    if m:
        y, mo, d, h, mi = map(int, m.groups())
        return datetime(y, mo, d, h, mi, tzinfo=HK)
    m = re.search(r'(\d{1,2})/(\d{1,2})\s+(\d{2}):(\d{2})', s)
    if m:
        mo, d, h, mi = map(int, m.groups())
        year = now_hk().year
        return datetime(year, mo, d, h, mi, tzinfo=HK)
    return None


def _latest_row_ms(daily):
    latest = None
    for side in ('bull', 'bear', 'split'):
        for row in (daily or {}).get(side) or []:
            if not isinstance(row, dict):
                continue
            for item in row.get('rows') or []:
                if not isinstance(item, dict):
                    continue
                ms = item.get('ms')
                if isinstance(ms, (int, float)) and not isinstance(ms, bool):
                    latest = ms if latest is None else max(latest, ms)
    return latest


def _fallback_end_hhmm(window):
    m = re.search(r'–\s*(?:\d{1,2}/\d{1,2}\s+)?(\d{2}:\d{2})', window or '')
    return m.group(1) if m else None


def top5_window(daily, fallback=None):
    """Human window 'MM/DD HH:MM – HH:MM HKT'. Cutoff is the latest rows[].ms in HKT.

    Start is daily.from. End is the latest writeup row timestamp, then the
    social-posts.json window end, then daily.to when that time is not 23:59.
    Never stores an ISO 'T' and never a fake 23:59.
    """
    daily = daily if isinstance(daily, dict) else {}
    start_dt = _parse_daily_clock(daily.get('from'))
    start = f'{start_dt.month:02d}/{start_dt.day:02d} {start_dt:%H:%M}' if start_dt else ''
    end = None
    ms = _latest_row_ms(daily)
    if ms is not None:
        end = hk(ms).strftime('%H:%M')
    if not end:
        end = _fallback_end_hhmm(fallback or '')
    if not end:
        to_dt = _parse_daily_clock(daily.get('to'))
        if to_dt and (to_dt.hour, to_dt.minute) != (23, 59):
            end = to_dt.strftime('%H:%M')
    if start and end:
        return f'{start} – {end} HKT'
    return ''


def build_top5(daily, day, made_hkt, fallback_window=None):
    """Daily top-5 card slot. Counts are copied, never invented.

    top5 = {
      date: 'YYYY-MM-DD',
      made_hkt: 'YYYY-MM-DD HH:MM',
      window: 'MM/DD HH:MM – HH:MM HKT' (real cutoff, never ISO T / fake 23:59),
      source: 'data/writeup-input.json daily',
      bull: [{t, n}],   # up to 5, rank_rows bull: nb desc, n_posts desc, ticker asc
      bear: [{t, n}],   # up to 5, rank_rows bear: nr desc, n_posts desc, ticker asc
      images: {zh|en|ko: {
        portrait: SITE+'og/top5-<lang>.png?v=<date>',       # 1080x1350, X / IG / Threads
        square:   SITE+'og/top5-<lang>-sq.png?v=<date>'}},  # 1080x1080, Facebook
      format: image_card,
      video: {zh|en|ko: SITE+'og/top5-<lang>.mp4?v=<date>'},
      posts: {zh|en|ko: {x, instagram, threads, facebook, has_link, first_comment}},
    }

    Fewer than five names on a side: those names only, and the heading uses that count
    (最看好 N 隻 / Top N bullish / 강세 상위 N종목). An empty side is the translated
    'none today' line (今日暫無 / None today / 오늘 없음), never a made-up row.
    X carries one link in the body: the lead bull's /<lang>/stock/<T>/, or /<lang>/ when there is no bull.
    Threads and Facebook keep that link in first_comment (threads: the lead bull, or the language
    home when there is no bull; facebook: one stock link per listed name). Instagram has no URL:
    one link-in-bio line and has_link.instagram false. Its first line is top5_ig_key_line
    (lead bull and lead bear); the heading and every ・ list row stay under that line.
    Threads is fit_threads (500 code points).
    Every thecrowdtape.com link is tag_url(..., platform, 'top5').
    Each post ends with SHORT[lang]['disc'] and the usual hashtags.
    format is image_card. video.<lang> points at og/top5-<lang>.mp4.
    """
    daily = daily if isinstance(daily, dict) else {}
    bulls = _side_rows(rank_rows(daily.get('bull'), 'bull'), 'nb', 5)
    bears = _side_rows(rank_rows(daily.get('bear'), 'bear'), 'nr', 5)
    window = top5_window(daily, fallback_window)
    day = _as_day(day) or str(day or '')
    posts = {}
    for lang in LANGS:
        posts[lang] = {
            'x': _x_top5_text(lang, day, window, bulls, bears),
            'instagram': _long_top5_text(lang, day, window, bulls, bears, 'instagram'),
            'threads': _threads_top5_text(lang, day, window, bulls, bears),
            'facebook': _long_top5_text(lang, day, window, bulls, bears, None),
        }
    _decorate_top5_posts(posts, bulls, bears)
    return {
        'date': day,
        'made_hkt': made_hkt,
        'window': window,
        'source': 'data/writeup-input.json daily',
        'format': 'image_card',
        'bull': bulls,
        'bear': bears,
        'images': {lang: {'portrait': f'{SITE}og/top5-{lang}.png?v={day}',
                          'square': f'{SITE}og/top5-{lang}-sq.png?v={day}'} for lang in LANGS},
        'video': {lang: f'{SITE}og/top5-{lang}.mp4?v={day}' for lang in LANGS},
        'posts': posts,
    }


def write_top5_jobs(slot):
    """work/top5cards.json for tools/top5card.js. One portrait and one square job per language."""
    jobs = []
    for lang in LANGS:
        data = _top5_card_data(slot, lang)
        jobs.append({'lang': lang, 'size': 'portrait', 'out': f'og/top5-{lang}.png', 'data': data})
        jobs.append({'lang': lang, 'size': 'square', 'out': f'og/top5-{lang}-sq.png', 'data': data})
    write_json(work('top5cards.json'), {'jobs': jobs}, indent=1)
    return jobs


def _hist_days(history):
    if not isinstance(history, dict):
        return {}
    days = history.get('days') if isinstance(history.get('days'), dict) else history
    return days if isinstance(days, dict) else {}


def _hist_list(rec, key):
    """Ticker list, or None when this record does not store that side as a list."""
    if not isinstance(rec, dict) or key not in rec or not isinstance(rec.get(key), list):
        return None
    out = []
    for x in rec[key]:
        if isinstance(x, str):
            t = _ticker_sym(x)
            if t:
                out.append(t)
    return out


def consensus_week_changes(history, start, end):
    """Tickers that joined or left joint bull/bear between the first and last day in [start, end].

    consensus-history days store bull and bear as ticker lists (joint names, no counts).
    A side is unsupported when either endpoint is missing that list. Days outside the range,
    and days between the endpoints, are not a join or a drop.
    """
    start, end = _as_day(start), _as_day(end)
    empty = {'supported': False, 'first': None, 'last': None,
             'joined_bull': [], 'dropped_bull': [], 'joined_bear': [], 'dropped_bear': []}
    if not start or not end:
        return empty
    keys = []
    for k, rec in _hist_days(history).items():
        day = _as_day(k)
        if day and start <= day <= end and isinstance(rec, dict):
            keys.append((day, rec))
    keys.sort(key=lambda x: x[0])
    if len(keys) < 2:
        if keys:
            empty['first'] = empty['last'] = keys[0][0]
        return empty
    first_day, first = keys[0]
    last_day, last = keys[-1]
    fb, lb = _hist_list(first, 'bull'), _hist_list(last, 'bull')
    fr, lr = _hist_list(first, 'bear'), _hist_list(last, 'bear')
    if fb is None or lb is None or fr is None or lr is None:
        return {**empty, 'first': first_day, 'last': last_day}
    return {
        'supported': True,
        'first': first_day,
        'last': last_day,
        'joined_bull': [t for t in lb if t not in set(fb)],
        'dropped_bull': [t for t in fb if t not in set(lb)],
        'joined_bear': [t for t in lr if t not in set(fr)],
        'dropped_bear': [t for t in fr if t not in set(lr)],
    }


def _week_close(lang):
    url = tag_url(page_url(lang), 'x', 'weekly_thread')
    text = f"{WEEK_COPY[lang]['head']}\n{SHORT[lang]['disc']}\n{url}"
    if xlen(text) <= 280:
        return text
    text = f"{SHORT[lang]['disc']}\n{url}"
    return text if xlen(text) <= 280 else _trim_x(text)


def _week_head(lang, weekly):
    L = WEEK_COPY[lang]
    lines = [L['head']]
    frm, to = weekly.get('from'), weekly.get('to')
    if frm and to:
        lines.append(f'{frm} – {to}')
    bits = []
    if _is_num(weekly.get('bull_total')):
        bits.append(f"{L['bull_total']} {_as_int(weekly['bull_total'])}")
    if _is_num(weekly.get('bear_total')):
        bits.append(f"{L['bear_total']} {_as_int(weekly['bear_total'])}")
    if bits:
        lines.append(' · '.join(bits))
    text = '\n'.join(lines)
    if xlen(text) <= 280:
        return text
    text = '\n'.join(lines[:2])
    return text if xlen(text) <= 280 else L['head']


def _week_list(lang, title, rows):
    """As many names as fit, in order. +N is how many of these rows were left off."""
    kept = []
    for r in rows:
        line = f'${r["t"]} {_acc(lang, r["n"])}'
        if xlen('\n'.join([title, *kept, line])) <= 280:
            kept.append(line)
        else:
            break
    omitted = len(rows) - len(kept)
    if not omitted:
        return '\n'.join([title, *kept])
    while True:
        extra = f'+{omitted}'
        trial = '\n'.join([title, *kept, extra])
        if xlen(trial) <= 280:
            return trial
        if not kept:
            return title if xlen(title) <= 280 else _trim_x(title)
        kept.pop()
        omitted = len(rows) - len(kept)


def _week_changes_post(lang, changes):
    L = WEEK_COPY[lang]
    span = f"{changes['first']} → {changes['last']}"
    groups = []
    for key in ('joined_bull', 'dropped_bull', 'joined_bear', 'dropped_bear'):
        ticks = list(changes.get(key) or [])
        if ticks:
            groups.append([L[key], ticks, len(ticks)])
    if not groups:
        text = f"{span}\n{L['no_change']}"
        return text if xlen(text) <= 280 else _trim_x(text)

    def render():
        lines = [span]
        for label, ticks, shown in groups:
            if shown <= 0:
                lines.append(f'{label} +{len(ticks)}')
                continue
            part = ticks[:shown]
            omitted = len(ticks) - shown
            line = label + ''.join(f' ${t}' for t in part)
            if omitted:
                line += f' +{omitted}'
            lines.append(line)
        return '\n'.join(lines)

    guard = 0
    while xlen(render()) > 280 and guard < 400:
        guard += 1
        idx = next((i for i in range(len(groups) - 1, -1, -1) if groups[i][2] > 0), None)
        if idx is None:
            break
        groups[idx][2] -= 1
    text = render()
    return text if xlen(text) <= 280 else _trim_x(text)


def build_weekly_thread(weekly, history, day):
    """Friday X thread for 本週共識變化, or None on any other day.

    weekly_thread = {
      date: 'YYYY-MM-DD',                 # the Friday
      range: {from, to},                   # weekly.from / weekly.to, unchanged
      langs: {en: [post, ...], zh: [...], ko: [...]},
      note: str,
    }

    Each language has at most 5 posts and each post has xlen <= 280.
    Post 1 is the heading plus the weekly range (and bull_total / bear_total when those
    fields are numbers). Then the bullish names (weekly.bull order, count = nb), the bearish
    names (weekly.bear order, count = nr), then joins and drops when history supports them.
    The last post includes SHORT[lang]['disc'] and SITE+'<lang>/' from tag_url(..., 'x', 'weekly_thread').
    An empty side is omitted. No join/drop post is written when the history shape cannot support it.
    """
    if not _is_friday(day):
        return None
    weekly = weekly if isinstance(weekly, dict) else {}
    changes = consensus_week_changes(history, weekly.get('from'), weekly.get('to'))
    note = WEEK_NOTE
    if not changes['supported']:
        note += ' Consensus history did not have comparable bull/bear lists for that range, so no join/drop tickers are listed.'
    bulls = _side_rows(weekly.get('bull'), 'nb', None)
    bears = _side_rows(weekly.get('bear'), 'nr', None)
    langs = {}
    for lang in ('en', 'zh', 'ko'):
        posts = [_week_head(lang, weekly)]
        if bulls:
            posts.append(_week_list(lang, WEEK_COPY[lang]['bulls'], bulls))
        if bears:
            posts.append(_week_list(lang, WEEK_COPY[lang]['bears'], bears))
        if changes['supported']:
            posts.append(_week_changes_post(lang, changes))
        posts.append(_week_close(lang))
        if len(posts) > 5:
            posts = posts[:4] + [_week_close(lang)]
        langs[lang] = posts
    return {'date': _as_day(day) or str(day or ''),
            'range': {'from': weekly.get('from'), 'to': weekly.get('to')},
            'langs': langs, 'note': note}


def attach_top5_and_weekly(sp, day, made_hkt, history, writeup=None):
    """Set sp['top5'] and, on Friday, sp['weekly_thread']. Write work/top5cards.json."""
    if writeup is None:
        writeup = read_json('data/writeup-input.json', {}) or {}
    if not isinstance(writeup, dict):
        writeup = {}
    sp['top5'] = build_top5(writeup.get('daily') or {}, day, made_hkt,
                           fallback_window=sp.get('window') if isinstance(sp, dict) else None)
    write_top5_jobs(sp['top5'])
    thread = build_weekly_thread(writeup.get('weekly') or {}, history, day)
    if thread:
        sp['weekly_thread'] = thread
    return sp


# --- hot_stock, discussion, weekend, atomic_posts ---------------------------------
# Counts and quotes come only from writeup-input rows (nb/nr, rows[].acc/why) and the
# aggregate fields on daily/weekly. A missing count is left out. Nothing here is filled in.

HISTORY_KEEP = 14
HISTORY_LOOKBACK = 7
ATOMIC_TIMES = ('09:00', '11:30', '14:00', '17:00', '20:00', '22:30')
ATOMIC_MIN = 4
ATOMIC_TARGET = 5
AGG_KEYS = ('posts', 'accounts', 'originals', 'reposts', 'bull_views', 'bear_views',
            'clear_accounts', 'bull_total', 'bear_total', 'split_total')
_DATE_TOKEN = re.compile(
    r'\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?)?'
    r'|\b\d{1,2}/\d{1,2}\b'
    r'|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}\b'
    r'|\b\d{1,2}:\d{2}\b',
    re.I)
_YEAR_TOKEN = re.compile(r'\b(?:19|20)\d{2}\b')

HOT_COPY = {
    'zh': {'title': '今日熱門 {t}：專家觀點', 'who': '帳號'},
    'en': {'title': 'Popular stock today: expert views on {t}', 'who': 'Accounts'},
    'ko': {'title': '오늘 인기 종목: {t} 전문가 시각', 'who': '계정'},
}
ASK_COPY = {
    'zh': {'q': '你點睇 {t}？', 'opts': ('看好', '看淡', '中性')},
    'en': {'q': 'What do you think of {t}?', 'opts': ('Bullish', 'Bearish', 'Neutral')},
    'ko': {'q': '{t} 어떻게 보세요?', 'opts': ('강세', '약세', '중립')},
}
AGG_LABEL = {
    'zh': {
        'posts': ('今日帖文數', '本週帖文數'),
        'accounts': ('今日帳號數', '本週帳號數'),
        'originals': ('今日原創帖', '本週原創帖'),
        'reposts': ('今日轉帖', '本週轉帖'),
        'bull_views': ('今日看好觀點', '本週看好觀點'),
        'bear_views': ('今日看淡觀點', '本週看淡觀點'),
        'clear_accounts': ('今日清晰立場帳號', '本週清晰立場帳號'),
        'bull_total': ('今日看好標的數', '本週看好標的數'),
        'bear_total': ('今日看淡標的數', '本週看淡標的數'),
        'split_total': ('今日分歧標的數', '本週分歧標的數'),
    },
    'en': {
        'posts': ('Posts today', 'Posts this week'),
        'accounts': ('Accounts today', 'Accounts this week'),
        'originals': ('Original posts today', 'Original posts this week'),
        'reposts': ('Reposts today', 'Reposts this week'),
        'bull_views': ('Bullish views today', 'Bullish views this week'),
        'bear_views': ('Bearish views today', 'Bearish views this week'),
        'clear_accounts': ('Clear-stance accounts today', 'Clear-stance accounts this week'),
        'bull_total': ('Bullish names today', 'Bullish names this week'),
        'bear_total': ('Bearish names today', 'Bearish names this week'),
        'split_total': ('Split names today', 'Split names this week'),
    },
    'ko': {
        'posts': ('오늘 게시물', '이번 주 게시물'),
        'accounts': ('오늘 계정', '이번 주 계정'),
        'originals': ('오늘 원글', '이번 주 원글'),
        'reposts': ('오늘 리포스트', '이번 주 리포스트'),
        'bull_views': ('오늘 강세 의견', '이번 주 강세 의견'),
        'bear_views': ('오늘 약세 의견', '이번 주 약세 의견'),
        'clear_accounts': ('오늘 입장 분명한 계정', '이번 주 입장 분명한 계정'),
        'bull_total': ('오늘 강세 종목 수', '이번 주 강세 종목 수'),
        'bear_total': ('오늘 약세 종목 수', '이번 주 약세 종목 수'),
        'split_total': ('오늘 의견 갈린 종목 수', '이번 주 의견 갈린 종목 수'),
    },
}
NUM_Q = {
    'zh': '你點睇呢個數？',
    'en': 'What do you make of this number?',
    'ko': '이 숫자 어떻게 보세요?',
}
WEEKEND_COPY = {
    'zh': {
        'bulls': '本週最看好', 'bears': '本週最看淡', 'totals': '本週共識數字',
        'splits': '本週分歧', 'split_q': '你點睇本週分歧 {t}？',
        'bull_total': '看好標的', 'bear_total': '看淡標的', 'ask': '你點睇呢組數字？',
    },
    'en': {
        'bulls': 'Most bullish this week', 'bears': 'Most bearish this week',
        'totals': "This week's consensus counts", 'splits': "This week's splits",
        'split_q': "What do you think of this week's split, {t}?",
        'bull_total': 'Bullish names', 'bear_total': 'Bearish names',
        'ask': 'What do you make of these counts?',
    },
    'ko': {
        'bulls': '이번 주 가장 강세', 'bears': '이번 주 가장 약세', 'totals': '이번 주 컨센서스 숫자',
        'splits': '이번 주 의견 분열', 'split_q': '이번 주 의견이 갈린 {t}, 어떻게 보세요?',
        'bull_total': '강세 종목', 'bear_total': '약세 종목', 'ask': '이 숫자 어떻게 보세요?',
    },
}
WEEKEND_FMT = {
    'bulls': 'image_card', 'bears': 'carousel', 'totals': 'text_question',
    'splits': 'carousel', 'split_poll': 'poll',
}


def history_path():
    return os.environ.get('SOCIAL_HISTORY') or 'data/social-history.json'


def _norm_text(s):
    return re.sub(r'\s+', ' ', (s or '')).strip()


def content_numbers(text):
    """Integers in a caption that are not part of a date, a clock time, a year or a URL."""
    t = re.sub(r'https?://\S+', ' ', text or '')
    t = _DATE_TOKEN.sub(' ', t)
    t = _YEAR_TOKEN.sub(' ', t)
    return {int(x) for x in re.findall(r'\d+', t)}


def content_tickers(text):
    out = set()
    for raw in re.findall(r'\$([A-Za-z0-9.\-]+)', text or ''):
        t = _ticker_sym(raw)
        if t and re.search(r'[A-Z]', t):
            out.add(t)
    return out


def _trim_verbatim(text, limit):
    """Collapse whitespace and cut a long quote from the end. The start stays as written."""
    text = re.sub(r'https?://\S+', '', text or '')
    text = re.sub(r'\s+', ' ', text).strip()
    if limit and len(text) > limit:
        text = text[:max(1, limit - 1)].rstrip() + '…'
    return text


def _assemble(parts):
    return '\n\n'.join(p.strip('\n') for p in parts if p and str(p).strip())


def _close(lang, tickers):
    tag = ' '.join([_primary_tag(lang), *_hash_tags([t for t in tickers if t])])
    return SHORT[lang]['disc'] + '\n' + tag


def _tag_line(lang, tickers):
    return _close(lang, tickers).split('\n', 1)[1]


def _count_phrase(lang, side, n):
    n = _as_int(n)
    if lang == 'en':
        word = 'account' if n == 1 else 'accounts'
        adj = 'bullish' if side == 'bull' else 'bearish'
        return f'{n} {adj} {word}'
    if lang == 'ko':
        adj = '강세' if side == 'bull' else '약세'
        return f'{adj} 계정 {n}개'
    adj = '看好' if side == 'bull' else '看淡'
    return f'{n} 個帳號{adj}'


def _as_threads(text, lang):
    out = fit_threads(text, lang)
    disc = SHORT[lang]['disc']
    if disc not in out:
        out = fit_threads(f'{out}\n\n{disc}', lang)
    return out


def _count_bits(lang, nb, nr):
    bits = []
    if _is_num(nb):
        bits.append(_count_phrase(lang, 'bull', nb))
    if _is_num(nr):
        bits.append(_count_phrase(lang, 'bear', nr))
    return ' · '.join(bits)


def _quote_rows(row, limit=3):
    out = []
    for item in (row or {}).get('rows') or []:
        if not isinstance(item, dict):
            continue
        acc = str(item.get('acc') or '').strip().lstrip('@')
        why = _trim_verbatim(item.get('why') or '', 220)
        if not acc or not why:
            continue
        out.append({'acc': acc, 'why': why})
        if len(out) >= limit:
            break
    return out


def _attr_line(acc, why):
    handle = '@' + str(acc).lstrip('@')
    why = dedupe_handle(acc, why)
    if not why:
        return handle
    return f'{handle}：{why}'


def _copy_row(row):
    if not isinstance(row, dict):
        return None
    t = _ticker_sym(row.get('t'))
    if not t:
        return None
    item = {'t': t, 'rows': row.get('rows') or []}
    for key in ('nb', 'nr', 'n_posts'):
        if key in row:
            item[key] = row.get(key)
    return item


def _named_rows(block):
    out, seen = [], set()
    for side in ('bull', 'bear', 'split'):
        for row in (block or {}).get(side) or []:
            item = _copy_row(row)
            if not item or item['t'] in seen:
                continue
            seen.add(item['t'])
            out.append(item)
    return out


def _row_score(row):
    nb = row.get('nb') if _is_num(row.get('nb')) else 0
    nr = row.get('nr') if _is_num(row.get('nr')) else 0
    nps = row.get('n_posts') if _is_num(row.get('n_posts')) else 0
    return (nb + nr, nps)


def _rank_rows(rows):
    return [row for _, row in sorted(enumerate(rows), key=lambda iv: (-_row_score(iv[1])[0], -_row_score(iv[1])[1], iv[0]))]


def select_slot_rows(daily, blocked):
    """Hottest quoted name for hot_stock, next counted name for discussion. Either may be None."""
    blocked = {_ticker_sym(t) for t in (blocked or []) if _ticker_sym(t)}
    ranked = _rank_rows(_named_rows(daily))
    hot = next((r for r in ranked if r['t'] not in blocked and _quote_rows(r)), None)
    talk = next((r for r in ranked
                 if r['t'] not in blocked and (hot is None or r['t'] != hot['t'])
                 and (_is_num(r.get('nb')) or _is_num(r.get('nr')))), None)
    return hot, talk


def top5_lead_tickers(top5):
    """First bull and first bear on the top5 card. Those are the lead names."""
    out = []
    if not isinstance(top5, dict):
        return out
    for side in ('bull', 'bear'):
        rows = top5.get(side) or []
        if rows and isinstance(rows[0], dict):
            t = _ticker_sym(rows[0].get('t'))
            if t:
                out.append(t)
    return out


def headline_ticker(sp):
    """First $TICKER on the main post's opening line."""
    posts = (sp or {}).get('posts') or {}
    for lang in LANGS:
        by = posts.get(lang)
        text = by.get('x') or by.get('threads') or '' if isinstance(by, dict) else (by or '')
        for line in str(text).splitlines():
            line = line.strip()
            if not line or line.startswith('⚠') or line.startswith('#'):
                continue
            m = re.search(r'\$([A-Za-z0-9.\-]+)', line)
            if not m:
                continue
            t = _ticker_sym(m.group(1))
            if t and re.search(r'[A-Z]', t):
                return t
    return None


def xtri_tickers(sp):
    out = []
    tri = (sp or {}).get('x_trilingual') or {}
    if not isinstance(tri, dict):
        return out
    for entry in tri.values():
        text = ''
        if isinstance(entry, dict):
            t = _ticker_sym(entry.get('image_ticker'))
            if t and re.search(r'[A-Z]', t) and t not in out:
                out.append(t)
            text = entry.get('text') or ''
        elif isinstance(entry, str):
            text = entry
        for t in content_tickers(text):
            if t not in out:
                out.append(t)
    return out


def recent_slot_tickers(history, day, slots=('hot_stock', 'discussion'), within=HISTORY_LOOKBACK):
    """Tickers used by hot_stock or discussion on the previous `within` days, not today."""
    day = _as_day(day)
    if not day or not isinstance(history, dict):
        return set()
    today = datetime.strptime(day, '%Y-%m-%d')
    out = set()
    for key, rec in history.items():
        d = _as_day(key)
        if not d or not isinstance(rec, dict):
            continue
        delta = (today - datetime.strptime(d, '%Y-%m-%d')).days
        if delta <= 0 or delta > within:
            continue
        for slot in slots:
            for t in rec.get(slot) or []:
                sym = _ticker_sym(t)
                if sym:
                    out.add(sym)
    return out


def blocked_tickers_for_slots(sp, history, day):
    out = set(top5_lead_tickers((sp or {}).get('top5')))
    head = headline_ticker(sp)
    if head:
        out.add(head)
    out.update(xtri_tickers(sp))
    out.update(recent_slot_tickers(history or {}, day))
    return out


def load_social_history(path=None):
    data = read_json(path or history_path(), {}) or {}
    return data if isinstance(data, dict) else {}


def save_social_history(history, path=None):
    """Keep the newest HISTORY_KEEP dates. Shape is {date: {slot: [tickers]}}."""
    history = history if isinstance(history, dict) else {}
    days = sorted({_as_day(k) for k in history if _as_day(k)})
    keep = set(days[-HISTORY_KEEP:])
    for key in list(history):
        if _as_day(key) not in keep:
            history.pop(key, None)
    write_json(path or history_path(), history, indent=1)
    return history


def remember_slots(history, day, slot_map):
    day = _as_day(day)
    if not day:
        return history
    rec = history.get(day) if isinstance(history.get(day), dict) else {}
    for slot, ticks in (slot_map or {}).items():
        clean = []
        for t in ticks or []:
            sym = _ticker_sym(t)
            if sym and sym not in clean:
                clean.append(sym)
        rec[slot] = clean
    history[day] = rec
    return history


def _link_entries(bodies_by_lang, campaign, ticker=None):
    """About half the threads/facebook bodies get a first_comment link. Bodies stay link-free."""
    out = {}
    i = 0
    for lang in LANGS:
        entry = {'threads': bodies_by_lang[lang], 'facebook': bodies_by_lang[lang]}
        hl, fc = {}, {}
        for plat in ('threads', 'facebook'):
            take = (i % 2 == 0)
            i += 1
            hl[plat] = take
            if take:
                fc[plat] = SHORT[lang]['live'] + _camp_url(lang, plat, campaign, ticker)
        entry['has_link'] = hl
        if fc:
            entry['first_comment'] = fc
        out[lang] = entry
    return out


def _hot_body(lang, ticker, nb, nr, quotes):
    title = HOT_COPY[lang]['title'].format(t=f'${ticker}')
    counts = _count_bits(lang, nb, nr)
    end = _close(lang, [ticker])
    if lang != 'zh':
        who = ''
        if quotes:
            who = HOT_COPY[lang]['who'] + ': ' + ' '.join(f'@{q["acc"]}' for q in quotes)
        return _as_threads(_assemble([title, counts, who, end]), lang)
    lines = [_attr_line(q['acc'], q['why']) for q in quotes]
    use = list(lines)
    while True:
        block = '\n'.join(use) if use else ''
        body = _assemble([title, counts, block, end])
        if len(body) <= THREADS_MAX or not use:
            return _as_threads(body, lang)
        if len(use) > 1:
            use.pop()
            continue
        room = THREADS_MAX - len(_assemble([title, counts, end])) - 2
        if room < 24:
            use = []
            continue
        use = [_trim_verbatim(use[0], room)]
        body = _assemble([title, counts, use[0], end])
        return _as_threads(body, lang)


def build_hot_stock(row, day):
    """Expert views on one name. zh quotes why verbatim. en/ko keep handles, ticker and counts."""
    if not row:
        return None
    quotes = _quote_rows(row, 3)
    if not quotes:
        return None
    ticker = row['t']
    nb = row.get('nb') if _is_num(row.get('nb')) else None
    nr = row.get('nr') if _is_num(row.get('nr')) else None
    bodies = {lang: _hot_body(lang, ticker, nb, nr, quotes) for lang in LANGS}
    posts = _link_entries(bodies, 'hot_stock', ticker)
    slot = {
        'date': _as_day(day) or str(day or ''),
        'format': 'carousel',
        'ticker': ticker,
        'source': 'data/writeup-input.json daily',
        'accounts': [q['acc'] for q in quotes],
        'posts': posts,
    }
    if nb is not None:
        slot['nb'] = _as_int(nb)
    if nr is not None:
        slot['nr'] = _as_int(nr)
    return slot


def build_discussion(row, day):
    """Poll: what do you think of $T, with the row's real bull and bear account counts."""
    if not row:
        return None
    if not (_is_num(row.get('nb')) or _is_num(row.get('nr'))):
        return None
    ticker = row['t']
    nb = row.get('nb') if _is_num(row.get('nb')) else None
    nr = row.get('nr') if _is_num(row.get('nr')) else None
    bodies = {}
    polls = {}
    for lang in LANGS:
        q = ASK_COPY[lang]['q'].format(t=f'${ticker}')
        counts = _count_bits(lang, nb, nr)
        bodies[lang] = _as_threads(_assemble([q, counts, _close(lang, [ticker])]), lang)
        polls[lang] = {'question': q, 'options': list(ASK_COPY[lang]['opts'])}
    posts = _link_entries(bodies, 'discussion', ticker)
    for lang in LANGS:
        posts[lang]['poll'] = polls[lang]
    slot = {
        'date': _as_day(day) or str(day or ''),
        'format': 'poll',
        'ticker': ticker,
        'source': 'data/writeup-input.json daily',
        'poll': polls,
        'posts': posts,
    }
    if nb is not None:
        slot['nb'] = _as_int(nb)
    if nr is not None:
        slot['nr'] = _as_int(nr)
    return slot


def _side_lines(lang, title, rows, field, side, limit=5):
    lines = []
    tickers = []
    for row in rows or []:
        if len(lines) >= limit:
            break
        item = _copy_row(row)
        if not item or not _is_num(item.get(field)):
            continue
        lines.append(f'${item["t"]} {_count_phrase(lang, side, item[field])}')
        tickers.append(item['t'])
    if not lines:
        return None, []
    body = _as_threads(_assemble([title, '\n'.join(lines), _close(lang, tickers)]), lang)
    return body, tickers


def _totals_body(lang, weekly):
    bits = []
    if _is_num((weekly or {}).get('bull_total')):
        bits.append(f"{WEEKEND_COPY[lang]['bull_total']} {_as_int(weekly['bull_total'])}")
    if _is_num((weekly or {}).get('bear_total')):
        bits.append(f"{WEEKEND_COPY[lang]['bear_total']} {_as_int(weekly['bear_total'])}")
    if not bits:
        return None
    return _as_threads(_assemble([
        WEEKEND_COPY[lang]['totals'], ' · '.join(bits), WEEKEND_COPY[lang]['ask'], _close(lang, []),
    ]), lang)


def _best_split(weekly, avoid):
    best, best_key = None, None
    for i, row in enumerate((weekly or {}).get('split') or []):
        item = _copy_row(row)
        if not item or item['t'] in avoid:
            continue
        if not (_is_num(item.get('nb')) or _is_num(item.get('nr'))):
            continue
        score = _row_score(item)
        key = (-score[0], -score[1], i)
        if best_key is None or key < best_key:
            best, best_key = item, key
    return best


def _weekend_pieces(weekly, day):
    """Two different angles. Saturday leads with bulls, Sunday with bears."""
    weekly = weekly if isinstance(weekly, dict) else {}
    wd = datetime.strptime(_as_day(day), '%Y-%m-%d').weekday()
    plan = ['bulls', 'totals', 'splits', 'bears'] if wd == 5 else ['bears', 'split_poll', 'bulls', 'totals']
    prefix = 'weekend-sat' if wd == 5 else 'weekend-sun'
    made = []
    used_tickers = set()
    for angle in plan:
        if len(made) >= 2:
            break
        bodies, ticker, poll = {}, None, None
        if angle == 'bulls':
            tickers = []
            for lang in LANGS:
                body, tickers = _side_lines(lang, WEEKEND_COPY[lang]['bulls'], weekly.get('bull'), 'nb', 'bull')
                if not body:
                    bodies = {}
                    break
                bodies[lang] = body
            ticker = tickers[0] if tickers else None
        elif angle == 'bears':
            tickers = []
            for lang in LANGS:
                body, tickers = _side_lines(lang, WEEKEND_COPY[lang]['bears'], weekly.get('bear'), 'nr', 'bear')
                if not body:
                    bodies = {}
                    break
                bodies[lang] = body
            ticker = tickers[0] if tickers else None
        elif angle == 'totals':
            for lang in LANGS:
                body = _totals_body(lang, weekly)
                if not body:
                    bodies = {}
                    break
                bodies[lang] = body
        elif angle == 'splits':
            tickers = []
            for lang in LANGS:
                lines, ts = [], []
                for row in _rank_rows(_named_rows({'split': weekly.get('split')}))[:3]:
                    if not (_is_num(row.get('nb')) or _is_num(row.get('nr'))):
                        continue
                    bits = _count_bits(lang, row.get('nb') if _is_num(row.get('nb')) else None,
                                       row.get('nr') if _is_num(row.get('nr')) else None)
                    if not bits:
                        continue
                    lines.append(f'${row["t"]} {bits}')
                    ts.append(row['t'])
                if not lines:
                    bodies = {}
                    break
                bodies[lang] = _as_threads(_assemble([
                    WEEKEND_COPY[lang]['splits'], '\n'.join(lines), _close(lang, ts)]), lang)
                tickers = ts
            ticker = tickers[0] if tickers else None
        elif angle == 'split_poll':
            row = _best_split(weekly, used_tickers)
            if not row:
                continue
            ticker = row['t']
            poll = {}
            for lang in LANGS:
                q = WEEKEND_COPY[lang]['split_q'].format(t=f'${ticker}')
                counts = _count_bits(lang, row.get('nb') if _is_num(row.get('nb')) else None,
                                     row.get('nr') if _is_num(row.get('nr')) else None)
                bodies[lang] = _as_threads(_assemble([q, counts, _close(lang, [ticker])]), lang)
                poll[lang] = {'question': q, 'options': list(ASK_COPY[lang]['opts'])}
        if len(bodies) != len(LANGS):
            continue
        made.append({'angle': angle, 'id': f'{prefix}-{angle}', 'ticker': ticker, 'bodies': bodies, 'poll': poll})
        if ticker:
            used_tickers.add(ticker)
    return made


def build_weekend(weekly, day):
    """Saturday/Sunday posts from weekly writeup data. None on other days or when fewer than 2 fit."""
    if not _is_weekend(day):
        return None
    made = _weekend_pieces(weekly, day)
    if len(made) < 2:
        return None
    posts = []
    i = 0
    for piece in made:
        langs = {}
        for lang in LANGS:
            body = piece['bodies'][lang]
            entry = {
                'threads': body,
                'facebook': body,
                'instagram': sanitize_instagram(body, lang),
            }
            hl, fc = {}, {}
            for plat in ('threads', 'facebook'):
                take = (i % 2 == 0)
                i += 1
                hl[plat] = take
                if take:
                    fc[plat] = SHORT[lang]['live'] + _camp_url(lang, plat, 'weekend', piece.get('ticker'))
            hl['instagram'] = False
            entry['has_link'] = hl
            if fc:
                entry['first_comment'] = fc
            if piece.get('poll'):
                entry['poll'] = piece['poll'][lang]
            langs[lang] = entry
        item = {'id': piece['id'], 'format': WEEKEND_FMT[piece['angle']], 'langs': langs}
        if piece.get('poll'):
            item['poll'] = piece['poll']
        if piece.get('ticker'):
            item['ticker'] = piece['ticker']
        posts.append(item)
    day_s = _as_day(day)
    return {
        'date': day_s,
        'date_kst': date_kst.kst_date(day_s, date_kst.WEEKEND_KST),
        'source': 'data/writeup-input.json weekly',
        'posts': posts,
    }


def _free_side(row, used_n):
    for side, field in (('bull', 'nb'), ('bear', 'nr')):
        if _is_num(row.get(field)):
            n = _as_int(row[field])
            if n not in used_n:
                return side, n
    return None, None


def _first_acc(row):
    for item in row.get('rows') or []:
        if isinstance(item, dict):
            acc = str(item.get('acc') or '').strip().lstrip('@')
            if acc:
                return acc
    return None


def _clean_why(why, ticker, n):
    """A quote atomic posts may show: no extra ticker and no extra number."""
    why = _trim_verbatim(why, 180)
    if not why:
        return None
    allowed = set() if n is None else {n}
    if not content_numbers(why) <= allowed:
        return None
    if not content_tickers(why) <= {ticker}:
        return None
    return why


def _expert_quote(row, ticker, n):
    for item in row.get('rows') or []:
        if not isinstance(item, dict):
            continue
        acc = str(item.get('acc') or '').strip().lstrip('@')
        why = _clean_why(item.get('why') or '', ticker, n)
        if acc and why:
            return acc, why
    return None, None


def _atomic_candidates(writeup, used_n, used_t):
    experts, stocks, numbers = [], [], []
    seen_e, seen_s = set(), set()
    for scope in ('daily', 'weekly'):
        block = (writeup or {}).get(scope) or {}
        labels = AGG_LABEL['en']
        for key in AGG_KEYS:
            if key not in labels or not _is_num(block.get(key)):
                continue
            n = _as_int(block[key])
            if n in used_n:
                continue
            numbers.append({'point_type': 'number', 'scope': scope, 'key': key, 'n': n,
                            'id': f'number-{scope}-{key}'})
        for row in _named_rows(block):
            if row['t'] in used_t:
                continue
            side, n = _free_side(row, used_n)
            if n is None:
                continue
            acc = _first_acc(row)
            if acc and row['t'] not in seen_e:
                qacc, why = _expert_quote(row, row['t'], n)
                experts.append({
                    'point_type': 'expert_view', 'ticker': row['t'], 'side': side, 'n': n,
                    'acc': qacc or acc, 'why': why, 'id': f'expert-{row["t"]}',
                })
                seen_e.add(row['t'])
            if row['t'] not in seen_s:
                stocks.append({
                    'point_type': 'stock', 'ticker': row['t'], 'side': side, 'n': n,
                    'id': f'stock-{row["t"]}',
                })
                seen_s.add(row['t'])
    return experts, stocks, numbers


def _render_atomic(pt, lang):
    ticker = pt.get('ticker')
    n = pt.get('n')
    if pt['point_type'] == 'number':
        label = AGG_LABEL[lang][pt['key']][0 if pt['scope'] == 'daily' else 1]
        fact = f'{label} {n}'
        body = _assemble([fact, NUM_Q[lang], _close(lang, [])])
        return _as_threads(body, lang), fact, _tag_line(lang, [])
    if pt['point_type'] == 'stock':
        fact = f'${ticker} {_count_phrase(lang, pt["side"], n)}'
        body = _assemble([fact, _close(lang, [ticker])])
        return _as_threads(body, lang), fact, _tag_line(lang, [ticker])
    handle = '@' + str(pt.get('acc') or '').lstrip('@')
    if lang == 'zh':
        fact = f'{handle} 提到 ${ticker}'
    elif lang == 'ko':
        fact = f'{handle} 가 본 ${ticker}'
    else:
        fact = f'{handle} on ${ticker}'
    parts = [fact]
    if n is not None:
        parts.append(_count_phrase(lang, pt['side'], n))
    if lang == 'zh' and pt.get('why'):
        parts.append(_attr_line(pt['acc'], pt['why']))
    body = _assemble(parts + [_close(lang, [ticker])])
    return _as_threads(body, lang), fact, _tag_line(lang, [ticker])


def _atomic_format(point_type):
    if point_type == 'expert_view':
        return 'carousel'
    if point_type == 'number':
        return 'text_question'
    return 'image_card'


def _try_point(pt, used_n, used_t, used_text, retried=False):
    rendered = {}
    expect_n = set() if pt.get('n') is None else {pt['n']}
    expect_t = set() if not pt.get('ticker') else {pt['ticker']}
    for lang in LANGS:
        text, hook, tags = _render_atomic(pt, lang)
        nums, ticks = content_numbers(text), content_tickers(text)
        if nums != expect_n or ticks != expect_t:
            if pt.get('why') and not retried:
                alt = dict(pt)
                alt['why'] = None
                return _try_point(alt, used_n, used_t, used_text, True)
            return None
        if nums & used_n or ticks & used_t or _norm_text(text) in used_text:
            return None
        if len(text) > THREADS_MAX or SHORT[lang]['disc'] not in text:
            return None
        rendered[lang] = (text, hook, tags, pt)
    return rendered


def build_atomic_posts(writeup, used_n, used_t, used_text, target=None, minimum=None):
    """One fact per post. Defaults are 4–5 posts per language. Chinese posts come first.

    `target` and `minimum` let the weekday run leave room for why_posts (together 4–6).
    The weekend run and a direct call keep the 4–5 default.
    """
    if target is None:
        target = ATOMIC_TARGET
    if minimum is None:
        minimum = ATOMIC_MIN
    target = max(0, min(int(target), len(ATOMIC_TIMES)))
    minimum = max(0, min(int(minimum), target))
    if target <= 0:
        return []
    used_n, used_t, used_text = set(used_n or ()), set(used_t or ()), set(used_text or ())
    experts, stocks, numbers = _atomic_candidates(writeup, used_n, used_t)
    chosen = []

    def take(pt):
        if pt.get('n') in used_n:
            return False
        if pt.get('ticker') and pt['ticker'] in used_t:
            return False
        rendered = _try_point(pt, used_n, used_t, used_text)
        if not rendered:
            return False
        # _try_point may have cleared why; keep the point it actually rendered.
        kept = rendered[LANGS[0]][3]
        chosen.append((kept, rendered))
        if kept.get('n') is not None:
            used_n.add(kept['n'])
        if kept.get('ticker'):
            used_t.add(kept['ticker'])
        for text, _hook, _tags, _pt in rendered.values():
            used_text.add(_norm_text(text))
        return True

    if numbers:
        take(numbers.pop(0))
    for pt in stocks:
        if take(pt):
            break
    for pt in experts:
        if pt.get('ticker') in used_t:
            continue
        if take(pt):
            break
    for pt in numbers:
        if len(chosen) >= target:
            break
        take(pt)
    for pool in (stocks, experts, numbers):
        if len(chosen) >= minimum:
            break
        for pt in pool:
            if len(chosen) >= target:
                break
            take(pt)
    if len(chosen) < minimum:
        return []
    chosen = chosen[:target]
    seq = []
    for lang in LANGS:
        for i, (pt, rendered) in enumerate(chosen):
            text, hook, tags, _pt = rendered[lang]
            seq.append((i, lang, pt, text, hook, tags))
    items = []
    for n, (i, lang, pt, text, hook, tags) in enumerate(seq):
        item = {
            'id': f'{lang}-{pt["id"]}',
            'lang': lang,
            'slot_kst': ATOMIC_TIMES[i],
            'format': _atomic_format(pt['point_type']),
            'point_type': pt['point_type'],
            'hook': hook,
            'text': text,
            'hashtags': tags,
            'has_link': (n % 2 == 0),
        }
        if pt.get('ticker'):
            item['ticker'] = pt['ticker']
        if item['has_link']:
            item['first_comment'] = SHORT[lang]['live'] + _camp_url(lang, 'threads', 'atomic', pt.get('ticker'))
        items.append(item)
    return items


_BODY_FIELDS = ('x', 'threads', 'instagram', 'facebook', 'text')


def _platform_bodies(posts):
    out = []
    if not isinstance(posts, dict):
        return out
    for by in posts.values():
        if not isinstance(by, dict):
            continue
        for field in _BODY_FIELDS:
            if isinstance(by.get(field), str):
                out.append(by[field])
    return out


def _body_groups(sp):
    """Platform bodies by slot. Hashtag stickers and image URLs are not bodies."""
    sp = sp or {}
    groups = {}
    bodies = _platform_bodies(sp.get('posts'))
    if bodies:
        groups['posts'] = bodies
    top = _platform_bodies((sp.get('top5') or {}).get('posts'))
    if top:
        groups['top5'] = top
    weekly = []
    langs = (sp.get('weekly_thread') or {}).get('langs') if isinstance(sp.get('weekly_thread'), dict) else None
    if isinstance(langs, dict):
        for posts in langs.values():
            if isinstance(posts, list):
                weekly.extend(p for p in posts if isinstance(p, str))
            elif isinstance(posts, str):
                weekly.append(posts)
    if weekly:
        groups['weekly_thread'] = weekly
    tri = []
    xtri = sp.get('x_trilingual')
    if isinstance(xtri, dict):
        for entry in xtri.values():
            if isinstance(entry, dict) and isinstance(entry.get('text'), str):
                tri.append(entry['text'])
            elif isinstance(entry, str):
                tri.append(entry)
    if tri:
        groups['x_trilingual'] = tri
    slots = sp.get('slots')
    if isinstance(slots, dict):
        for key, sl in slots.items():
            bodies = _platform_bodies((sl or {}).get('posts') if isinstance(sl, dict) else None)
            if bodies:
                groups[f'slots.{key}'] = bodies
    for name in ('hot_stock', 'discussion'):
        node = sp.get(name)
        if isinstance(node, dict):
            bodies = _platform_bodies(node.get('posts'))
            if bodies:
                groups[name] = bodies
    weekend_bodies = []
    weekend = sp.get('weekend')
    if isinstance(weekend, dict):
        for item in weekend.get('posts') or []:
            if isinstance(item, dict):
                weekend_bodies.extend(_platform_bodies(item.get('langs')))
    if weekend_bodies:
        groups['weekend'] = weekend_bodies
    atomic = [p.get('text') for p in sp.get('atomic_posts') or [] if isinstance(p, dict) and isinstance(p.get('text'), str)]
    if atomic:
        groups['atomic_posts'] = atomic
    intra = sp.get('intraday')
    if isinstance(intra, dict):
        for key, sl in (intra.get('slots') or {}).items():
            if not isinstance(sl, dict):
                continue
            blobs = []
            xen = (sl.get('x') or {}).get('en') if isinstance(sl.get('x'), dict) else None
            if isinstance(xen, dict) and isinstance(xen.get('text'), str):
                blobs.append(xen['text'])
            elif isinstance(xen, str):
                blobs.append(xen)
            th = sl.get('threads') if isinstance(sl.get('threads'), dict) else {}
            for lang in LANGS:
                node = th.get(lang)
                if isinstance(node, dict) and isinstance(node.get('text'), str):
                    blobs.append(node['text'])
                elif isinstance(node, str):
                    blobs.append(node)
            if blobs:
                groups[f'intraday.{key}'] = blobs
    for name in ('three_lines', 'why_posts'):
        blobs = [t for t in three_why.collect_texts(sp.get(name)) if isinstance(t, str)]
        if blobs:
            groups[name] = blobs
    return groups


def _union_facts(groups, skip=()):
    nums, ticks, texts = set(), set(), set()
    for name, blobs in groups.items():
        if name in skip:
            continue
        for raw in blobs:
            nums |= content_numbers(raw)
            ticks |= content_tickers(raw)
            key = _norm_text(raw)
            if key:
                texts.add(key)
    return nums, ticks, texts


def _text_clashes(groups, slot):
    others = {}
    for name, blobs in groups.items():
        if name == slot:
            continue
        for raw in blobs:
            others.setdefault(_norm_text(raw), name)
    hits = []
    for raw in groups.get(slot) or []:
        key = _norm_text(raw)
        if key and key in others:
            hits.append(others[key])
    return hits


def _atomic_group(item):
    i = item.get('id') or ''
    lang = item.get('lang') or ''
    prefix = f'{lang}-'
    return i[len(prefix):] if lang and i.startswith(prefix) else i


def guard_slots(sp):
    """Problems when two slots share a full body, or atomic facts repeat. Empty means clean."""
    problems = []
    groups = _body_groups(sp)
    seen = {}
    for slot, blobs in groups.items():
        local = set()
        for raw in blobs:
            key = _norm_text(raw)
            if not key:
                continue
            if slot == 'atomic_posts':
                if key in local:
                    problems.append(f'duplicate atomic text: {key[:60]}')
                local.add(key)
            prev = seen.get(key)
            if prev and prev != slot:
                problems.append(f'duplicate text in {prev} and {slot}')
            else:
                seen.setdefault(key, slot)
    atomic = [p for p in (sp.get('atomic_posts') or []) if isinstance(p, dict)]
    other_n, other_t, _other_text = _union_facts(groups, skip=('atomic_posts',))
    by_point = {}
    for item in atomic:
        by_point.setdefault(_atomic_group(item), []).append(item)
    used_n, used_t = set(), set()
    for gid, items in by_point.items():
        sets_n = [content_numbers(i.get('text') or '') for i in items]
        sets_t = [content_tickers(i.get('text') or '') for i in items]
        if any(s != sets_n[0] for s in sets_n):
            problems.append(f'atomic point {gid} numbers differ by language')
        if any(s != sets_t[0] for s in sets_t):
            problems.append(f'atomic point {gid} tickers differ by language')
        if sets_n[0] & other_n:
            problems.append(f'atomic point {gid} reuses numbers {sorted(sets_n[0] & other_n)}')
        if sets_t[0] & other_t:
            problems.append(f'atomic point {gid} reuses tickers {sorted(sets_t[0] & other_t)}')
        if sets_n[0] & used_n:
            problems.append(f'atomic number overlap on {gid}')
        if sets_t[0] & used_t:
            problems.append(f'atomic ticker overlap on {gid}')
        used_n |= sets_n[0]
        used_t |= sets_t[0]
    return problems


def _tickers_of_atomic(posts):
    out = []
    for item in posts or []:
        t = _ticker_sym((item or {}).get('ticker'))
        if t and t not in out:
            out.append(t)
    return out


def _tickers_in_texts(blobs):
    out = []
    for raw in blobs or []:
        for t in content_tickers(raw):
            if t not in out:
                out.append(t)
    return out


def refresh_top5(sp, daily, day, made_hkt):
    sp['top5'] = build_top5(daily or {}, day, made_hkt,
                           fallback_window=sp.get('window') if isinstance(sp, dict) else None)
    return sp


def _keep_why_posts(sp, posts):
    """Drop a why post whose body copies another slot or an earlier why post."""
    kept = []
    for post in posts or []:
        if not isinstance(post, dict):
            continue
        sp['why_posts'] = kept + [post]
        groups = _body_groups(sp)
        others = {}
        for name, blobs in groups.items():
            if name == 'why_posts':
                continue
            for raw in blobs:
                others[_norm_text(raw)] = name
        texts = [_norm_text(t) for t in three_why.collect_texts(post)]
        prev = {_norm_text(t) for older in kept for t in three_why.collect_texts(older)}
        if any(t and (t in others or t in prev) for t in texts):
            continue
        kept.append(post)
    if kept:
        sp['why_posts'] = kept
    else:
        sp.pop('why_posts', None)
    return kept


def attach_market_slots(sp, day, writeup, history=None, save=False, dash=None):
    """Weekday hot_stock, discussion, three_lines, why_posts and atomic_posts.

    Omits a slot when nothing real is eligible. Weekends use attach_weekend_slots
    and do not build three_lines or why_posts. `dash` is the homepage post corpus;
    tests leave it empty and the three lines fall back to the writeup rows.
    """
    if history is None:
        history = load_social_history()
        save = True
    writeup = writeup if isinstance(writeup, dict) else {}
    day = _as_day(day) or str(day or '')
    sp.pop('atomic_posts', None)
    sp.pop('three_lines', None)
    sp.pop('why_posts', None)
    blocked = blocked_tickers_for_slots(sp, history, day)
    daily = writeup.get('daily') or {}
    hot_row, talk_row = select_slot_rows(daily, blocked)
    sp.pop('hot_stock', None)
    sp.pop('discussion', None)
    if hot_row:
        built = build_hot_stock(hot_row, day)
        if built:
            sp['hot_stock'] = built
            if _text_clashes(_body_groups(sp), 'hot_stock'):
                sp.pop('hot_stock', None)
                hot_row = None
    if talk_row and hot_row and talk_row['t'] == hot_row['t']:
        talk_row = None
    if talk_row:
        built = build_discussion(talk_row, day)
        if built:
            sp['discussion'] = built
            if _text_clashes(_body_groups(sp), 'discussion'):
                sp.pop('discussion', None)
                talk_row = None
    window_fb = sp.get('window') if isinstance(sp, dict) else None
    # why posts take early KST slots. Atomic fills what is left, same ticker dropped.
    # Together that is 4–6 posts per language when the writeup has the facts.
    three_why.fill_three_why(
        sp, day, writeup, history, dash=dash, window_fallback=window_fb)
    remember_slots(history, day, {
        'hot_stock': [hot_row['t']] if hot_row and sp.get('hot_stock') else [],
        'discussion': [talk_row['t']] if talk_row and sp.get('discussion') else [],
        'top5': top5_lead_tickers(sp.get('top5')),
        'atomic': _tickers_of_atomic(sp.get('atomic_posts')),
        'why': [p.get('ticker') for p in sp.get('why_posts') or []],
    })
    rec = history.get(day) if isinstance(history.get(day), dict) else None
    if rec is not None:
        rec['why_text'] = [
            _norm_text(t)
            for p in sp.get('why_posts') or []
            for t in three_why.collect_texts(p.get('threads'))
        ]
        rec['three_lines_text'] = [
            _norm_text(t) for t in three_why.collect_texts((sp.get('three_lines') or {}).get('threads'))
        ]
    if save:
        save_social_history(history)
    date_kst.apply_date_kst(sp, atomic_day=day)
    return sp


def _atomic_would_clash(atomic, texts):
    seen = set(texts)
    for item in atomic:
        key = _norm_text(item.get('text') or '')
        if key in seen:
            return True
        seen.add(key)
    return False


def attach_weekend_slots(sp, day, writeup, history=None, save=False):
    """Saturday/Sunday: write weekend and atomic_posts. Leave weekday keys in place."""
    if history is None:
        history = load_social_history()
        save = True
    writeup = writeup if isinstance(writeup, dict) else {}
    day = _as_day(day) or str(day or '')
    sp.pop('atomic_posts', None)
    weekend = build_weekend(writeup.get('weekly') or {}, day)
    if weekend:
        sp['weekend'] = weekend
        if _text_clashes(_body_groups(sp), 'weekend'):
            # Keep the posts that do not copy another slot. Drop the whole slot if that leaves < 2.
            kept = []
            others = {}
            groups = _body_groups(sp)
            for name, blobs in groups.items():
                if name == 'weekend':
                    continue
                for raw in blobs:
                    others[_norm_text(raw)] = name
            for item in weekend['posts']:
                blobs = _platform_bodies(item.get('langs'))
                if any(_norm_text(b) in others for b in blobs):
                    continue
                kept.append(item)
            if len(kept) >= 2:
                weekend['posts'] = kept
                sp['weekend'] = weekend
            else:
                sp.pop('weekend', None)
                weekend = None
    else:
        sp.pop('weekend', None)
    nums, ticks, texts = _union_facts(_body_groups(sp))
    atomic = build_atomic_posts(writeup, nums, ticks, texts)
    if atomic and not _atomic_would_clash(atomic, texts):
        sp['atomic_posts'] = atomic
    weekend_ticks = _tickers_in_texts(_body_groups(sp).get('weekend'))
    remember_slots(history, day, {
        'weekend': weekend_ticks,
        'atomic': _tickers_of_atomic(sp.get('atomic_posts')),
    })
    if save:
        save_social_history(history)
    date_kst.apply_date_kst(sp, atomic_day=day)
    return sp


def carry_intraday(sp, prev, day):
    """Keep a same-date intraday block when weekday posts are rebuilt from scratch.

    `prev` is the social-posts object read before the rebuild. A different date
    stays off the new file; that day's slots are written by the intraday job.
    """
    if not isinstance(sp, dict):
        return sp
    intra = prev.get('intraday') if isinstance(prev, dict) else None
    if isinstance(intra, dict) and _as_day(intra.get('date')) and _as_day(intra.get('date')) == _as_day(day):
        sp['intraday'] = intra
    return sp


def social_actions(day, sp, hour, has_items, legacy, force=False):
    """Which branch main() runs.

    Trading days at or after SOCIAL_HOUR write the weekday posts (unless today's file
    is already there). Saturday and Sunday write weekend and atomic_posts only, also
    from SOCIAL_HOUR, and do not rebuild the weekday posts. `force` reruns that day's
    branch. `legacy` still rebuilds a weekday file.
    """
    day = _as_day(day) or day
    sp = sp or {}
    due = bool(force) or (isinstance(hour, int) and hour >= SOCIAL_HOUR)
    if _is_weekend(day):
        done = isinstance(sp.get('weekend'), dict) and sp['weekend'].get('date') == day
        return {'weekday': False, 'weekend': bool(due and (force or not done))}
    if not has_items:
        return {'weekday': False, 'weekend': False}
    already = sp.get('date') == day
    run = bool(force or legacy or (due and not already and trading_day(day)))
    return {'weekday': run, 'weekend': False}

def main():
    st = read_json(work('stats.json'))
    d = _dash_data()
    ch = read_json('data/consensus-history.json', {'days': {}})
    day, s = st['today'], st['daily']
    langs, items = build(d, s, ch, day)
    # A new picture design (tools/og.html) also counts as a change.
    digest = hashlib.sha1(json.dumps(langs, sort_keys=True, ensure_ascii=False).encode() + open('tools/og.html', 'rb').read()).hexdigest()[:10]
    last = read_json('og/latest.json', {})
    draw = last.get('hash') != digest or last.get('date') != day or not os.path.exists(f'og/{day}.png')

    sp = read_json('data/social-posts.json', {})
    prev_sp = sp if isinstance(sp, dict) else {}
    now = now_hk()
    old = isinstance((sp.get('posts') or {}).get('zh'), str)  # written before the per-platform versions existed
    old = old or not os.path.exists('zh/feed.xml')  # first run with RSS feeds
    old = old or ('story' not in ((sp.get('posts') or {}).get('zh') or {'story': 1})) or 'stories' not in sp  # before Facebook, Story and hashtags on every version
    actions = social_actions(day, sp, now.hour, bool(items), old, force=os.environ.get('SOCIAL_FORCE') == '1')
    social = actions['weekday']
    if social:
        win = window(s)
        sp = {'date': day, 'made_hkt': now.strftime('%Y-%m-%d %H:%M'), 'window': win,
              'no_post_days': sorted(h for h in US_HOLIDAYS if h >= day),  # weekdays the Grok bot skips
              'images': {l: f'{SITE}og/social-{l}.png?v={day}' for l in LANGS},
              'stories': {l: f'{SITE}og/story-{l}.png?v={day}' for l in LANGS},
              'posts': {l: caption(l, day, s, items, win, langs[l]['quote']) for l in LANGS}}
        sp['x_facts'] = _x_facts(d, items, s)
        tag_posts(sp['posts'], 'daily')
        fit_threads_posts(sp['posts'])
        attach_new_posts(sp, rebuild_premarket=True)  # both X posts; carousel rebuilds premarket after the 2030 slot
        attach_top5_and_weekly(sp, day, sp['made_hkt'], ch)
        writeup = read_json('data/writeup-input.json', {}) or {}
        attach_market_slots(
            sp, day, writeup if isinstance(writeup, dict) else {}, load_social_history(),
            save=True, dash=d)
        carry_intraday(sp, prev_sp, day)
        date_kst.apply_date_kst(sp, atomic_day=day)
        write_json('data/social-posts.json', sp, indent=1)
        normalize_file('data/social-posts.json')
        from ig_boost import apply_social_file
        apply_social_file('data/social-posts.json')
        sp = read_json('data/social-posts.json')
        os.makedirs('social', exist_ok=True)
        open('social/index.html', 'w', encoding='utf-8').write(social_page(sp))
        write_feeds(sp)
        notice(f'今日社交媒體貼文已寫好：{SITE}social/')
    elif actions['weekend']:
        # Weekend slots only. Weekday posts, top5 and the Friday thread stay as they are.
        writeup = read_json('data/writeup-input.json', {}) or {}
        attach_weekend_slots(sp, day, writeup if isinstance(writeup, dict) else {}, load_social_history(), save=True)
        date_kst.apply_date_kst(sp, atomic_day=day)
        write_json('data/social-posts.json', sp, indent=1)
        normalize_file('data/social-posts.json')
        from ig_boost import apply_social_file
        apply_social_file('data/social-posts.json')
        notice(f'週末社交槽已寫好：{day}')
    if draw or social:
        write_json(work('og.json'), {'date': day, 'hash': digest, 'social': social, 'langs': langs})

    h = open(HTML, encoding='utf-8').read()
    h = re.sub(r'(?:' + re.escape(SITE) + r'|https://xmktradar\.github\.io/)og/[\w-]+\.png(\?v=[\w-]+)?', lambda m: f'{SITE}og/{day}.png?v={digest}', h)
    open(HTML, 'w', encoding='utf-8').write(h)
    print(f"share {day} mode {langs['zh']['mode']} hero {items[0]['t'] if items else '-'} draw {draw} social {social}")


def _dash_data():
    """Full dash-data from index.html, including slim pages that split accounts/prices out."""
    try:
        from slim_pages import full_data
        return full_data(open(HTML, encoding='utf-8').read())
    except Exception:
        return load(HTML)


def og_only():
    """Write work/og.json from current dash-data + work/stats.json. No social posts, no index.html rewrite."""
    st = read_json(work('stats.json'))
    if not st or 'today' not in st or 'daily' not in st:
        raise SystemExit('share --og-only: work/stats.json missing (run tools/stats.js first)')
    d = _dash_data()
    ch = read_json('data/consensus-history.json', {'days': {}})
    day, s = st['today'], st['daily']
    langs, items = build(d, s, ch, day)
    digest = hashlib.sha1(json.dumps(langs, sort_keys=True, ensure_ascii=False).encode() + open('tools/og.html', 'rb').read()).hexdigest()[:10]
    write_json(work('og.json'), {'date': day, 'hash': digest, 'social': False, 'langs': langs})
    print(f"og-only {day} mode {langs['zh']['mode']} hero {items[0]['t'] if items else '-'} langs {','.join(langs)}")


if __name__ == '__main__':
    if '--og-only' in sys.argv:
        og_only()
    elif '--backfill-date-kst' in sys.argv:
        path = 'data/social-posts.json'
        args = [a for a in sys.argv[1:] if a != '--backfill-date-kst' and not a.startswith('-')]
        if args:
            path = args[0]
        date_kst.backfill_file(path)
    else:
        main()
