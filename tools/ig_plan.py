"""Instagram plan (Tim, 2026-10-29, thread 「制定 IG 吸引人流方案」): last pass on the post files before Publish.

  1. Instagram and Threads get Chinese only (Threads added by Tim 2026-10-29: 「IG & Threads 之後永遠只係發中文」).
     Every English Instagram caption, Story tag line, Reel caption and Threads text is emptied, and the
     English half of ig_threads_daily is dropped; X and Facebook keep their English text. An empty
     instagram / threads field tells the bots not to post that one there.
  2. Earnings picture posts: at most IG_EARNINGS_PER_DAY (2) a day go to Instagram, the largest market
     caps first, the 10:00 slot before the 22:00 one. Each item gets ig: true/false; the captions are kept
     (the 11:00 earnings video copies its caption from an item).
  3. Each Chinese Instagram caption ends with one genuine question about the post, written here from
     the caption itself. It never asks people to like, share, tag or comment. A caption that already
     has a question line keeps it and gets no second one.

Runs on data/social-posts.json, data/earnings-posts.json, data/tutorial-posts.json, data/macro-week.json
(the files that exist). Idempotent: running it again changes nothing.

  python3 tools/ig_plan.py            # rewrite the files
  python3 tools/ig_plan.py --check    # exit 1 when a file does not follow the plan (no writing)
"""
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from humanize import BRAND, TAG_RE  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ('data/social-posts.json', 'data/earnings-posts.json', 'data/tutorial-posts.json', 'data/macro-week.json')
IG_LANGS = ('zh',)
THREADS_LANGS = ('zh',)
TH_KEYS = ('threads',)  # a string under one of these is a Threads text
IG_EARNINGS_PER_DAY = 2
IG_KEYS = ('instagram', 'ig_reel')  # a string under one of these is an Instagram caption
SKIP_KEYS = {'url', 'urls', 'link', 'title', 'quotes', 'themes', 'slides', 'av', 'avatar', 'bull_reasons', 'bear_reasons',
             'images', 'images_x', 'images_fb', 'stories', 'ig_images', 'video_cover', 'field', 'post_at_hkt',
             'video_path', 'video_expected_path', 'ig_threads_daily', 'image', 'ig_image'}

TICKER = re.compile(r'\$([A-Z][A-Z0-9.]{0,5})\b')
BAIT = re.compile(r'讚好|按讚|點讚|分享|轉發|標記|tag|like|share|follow|追蹤|留言告訴|留言|comment', re.I)
QUESTIONS = {
    'earnings': ('你覺得 ${t} 這次財報是好是壞？', '看完 ${t} 這份成績單，你最在意哪個數字？'),
    'duel': ('你站在看多還是看空那一邊？', '多空兩邊的理由，你覺得哪邊更有說服力？'),
    'macro': ('這週哪個宏觀消息最影響你的判斷？', '你覺得下週市場最該留意哪個數據？'),
    'guide': ('你平常用什麼方法找值得留意的股票？', '這個功能你會怎樣用在自己的投資上？'),
    'ticker': ('你怎麼看 ${t} 接下來的走勢？', '${t} 這麼多人討論，你會跟還是不跟？'),
    'plain': ('今天這些股票裡，你最留意哪一檔？', '你覺得今天市場的情緒是偏多還是偏空？'),
}


def kind_of(text):
    if '財報' in text:
        return 'earnings'
    if re.search('分歧|對決|多空|看多還是看空', text):
        return 'duel'
    if re.search('宏觀|聯儲|利率|CPI|非農', text):
        return 'macro'
    if re.search('教學|第 ?\\d+ ?集|功能', text):
        return 'guide'
    return 'ticker' if TICKER.search(text) else 'plain'


def question_for(text):
    head = next((ln for ln in text.split('\n') if ln.strip()), '')
    k = 'earnings' if '財報' in text else kind_of(head)
    m = TICKER.search(text)
    if k == 'earnings' and not m:
        k = 'plain'
    opts = QUESTIONS[k]
    q = opts[int(hashlib.md5(text.encode('utf-8')).hexdigest(), 16) % len(opts)]
    return q.replace('${t}', '$' + m.group(1)) if m else q


def _is_question(line):
    """A question to the reader (a title like 「那 201 個帳號是誰？」 does not count)."""
    return line.rstrip().endswith(('？', '?')) and '你' in line


def add_question(text):
    """A zh Instagram caption (humanize layout: body, '', brand, disclaimer, '', tags) with one question
    as its last body line. Text without a brand line is not a full caption and is returned as is."""
    if not isinstance(text, str) or not text.strip():
        return text
    lines = text.split('\n')
    bi = next((i for i, ln in enumerate(lines) if ln.strip() in BRAND['zh']), None)
    if bi is None:
        return text
    body = [ln for ln in lines[:bi] if ln.strip()]
    if any(_is_question(ln) for ln in body):
        return text
    head = lines[:bi]
    while head and not head[-1].strip():
        head.pop()
    q = question_for('\n'.join(body))
    return '\n'.join(head + ['', q, ''] + lines[bi:])


def _walk(obj, lang=None, ig=False, key=None, th=False):
    """Rewrite Instagram and Threads strings under obj in place."""
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if k in SKIP_KEYS:
                continue
            lg = k if k in ('zh', 'en') else lang
            ig_here = ig or k in IG_KEYS
            th_here = th or k in TH_KEYS
            if isinstance(v, str):
                obj[k] = _fix(v, lg, ig_here, k, th_here)
            elif isinstance(v, (dict, list)):
                _walk(v, lg, ig_here, k, th_here)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, str):
                obj[i] = _fix(v, lang, ig, key, th)
            elif isinstance(v, (dict, list)):
                _walk(v, lang, ig, key, th)
    return obj


def _fix(v, lang, ig, key, th=False):
    if re.fullmatch(r'https?://\S+', v.strip() or 'x'):
        return v
    if lang == 'en' and (ig or th or key == 'story'):
        return ''  # Instagram (posts, Story, Reels) and Threads are Chinese only
    if lang == 'zh' and ig:
        return add_question(v)
    return v


def _earnings(ep):
    """ig: true on at most IG_EARNINGS_PER_DAY items a day, largest market cap first, 10:00 before 22:00."""
    slots = ep.get('slots') or {}
    used = {}
    for key in sorted(slots, key=lambda k: (slots[k].get('day') or '', k)):
        s = slots[key]
        items = s.get('items') or []
        fixed = [i for i in items if isinstance(i.get('ig'), bool)]
        if len(fixed) == len(items):  # marked by an earlier run: keep, the bot may have posted already
            used[s.get('day')] = used.get(s.get('day'), 0) + sum(1 for i in items if i['ig'])
            continue
        room = max(0, IG_EARNINGS_PER_DAY - used.get(s.get('day'), 0))
        pick = {id(i) for i in sorted(items, key=lambda i: -(i.get('mcap') or 0))[:room]}
        for i in items:
            i['ig'] = id(i) in pick
        used[s.get('day')] = used.get(s.get('day'), 0) + len(pick)
    return ep


def apply(data, name=''):
    _walk(data)
    if name.endswith('earnings-posts.json'):
        _earnings(data)
    daily = data.get('ig_threads_daily')
    if isinstance(daily, dict):
        for lang in [k for k in daily if k not in IG_LANGS]:
            del daily[lang]  # the daily IG + Threads posts are Chinese only
    data['ig_langs'] = list(IG_LANGS)
    data['threads_langs'] = list(THREADS_LANGS)
    return data


def problems(data, name=''):
    """What in data breaks the plan (empty list when fine)."""
    out = []

    def walk(o, path, lang=None, ig=False, key=None, th=False):
        if isinstance(o, dict):
            for k, v in o.items():
                if k not in SKIP_KEYS:
                    walk(v, f'{path}.{k}', k if k in ('zh', 'en') else lang, ig or k in IG_KEYS, k, th or k in TH_KEYS)
        elif isinstance(o, list):
            for n, v in enumerate(o):
                walk(v, f'{path}[{n}]', lang, ig, key, th)
        elif isinstance(o, str) and o.strip() and not re.fullmatch(r'https?://\S+', o.strip()):
            if lang == 'en' and (ig or key == 'story'):
                out.append(f'{path}: English Instagram text')
            elif lang == 'en' and th:
                out.append(f'{path}: English Threads text')
            if lang == 'zh' and ig and any(ln.strip() in BRAND['zh'] for ln in o.split('\n')):
                body = o.split('\n')[:[ln.strip() in BRAND['zh'] for ln in o.split('\n')].index(True)]
                if not any(_is_question(ln) for ln in body):
                    out.append(f'{path}: no question')
    walk(data, name)
    out += [f'{name}: ig_threads_daily.{k} is not Chinese' for k in (data.get('ig_threads_daily') or {}) if k not in IG_LANGS]
    if name.endswith('earnings-posts.json'):
        per_day = {}
        for s in (data.get('slots') or {}).values():
            for i in s.get('items') or []:
                if not isinstance(i.get('ig'), bool):
                    out.append(f'{name}: {i.get("t")} has no ig mark')
                elif i['ig']:
                    per_day[s.get('day')] = per_day.get(s.get('day'), 0) + 1
        out += [f'{name}: {d} has {n} Instagram earnings posts' for d, n in per_day.items() if n > IG_EARNINGS_PER_DAY]
    return out


def main():
    check = '--check' in sys.argv
    bad = []
    for name in FILES:
        path = os.path.join(ROOT, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8') as f:
            raw = f.read()
        data = json.loads(raw)
        if check:
            bad += problems(data, name)
            continue
        apply(data, name)
        indent = 1 if re.match(r'\{\n \S', raw) else (2 if raw.startswith('{\n  ') else None)
        out = json.dumps(data, ensure_ascii=False, indent=indent)
        if out.strip() != raw.strip():
            with open(path, 'w', encoding='utf-8') as f:
                f.write(out + ('\n' if raw.endswith('\n') else ''))
            print(f'ig_plan: {name} updated')
    if check:
        for b in bad:
            print('IG PLAN:', b)
        sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
