"""Step 3: apply summaries SuperGrok already wrote. Do not call the xAI API.

SuperGrok (the subscription, not API credits) reads new posts and writes an English summary
first, then a Traditional Chinese translation of it (2026-10-11; Korean dropped 2026-10-27), one small file per batch, into data/grok-inbox/
(the older single file data/super-grok-analysis.json is still read). This step only
copies well-formed rows into work/analysed.json. Posts without a summary stay in
data/pending-posts.json. write_status.py removes inbox files once the site has used them.
"""
import glob
import json
import os
import re

from sitedata import notice, read_json, work, write_json

try:  # SuperGrok sometimes slips into Simplified Chinese when translating from English (2026-10-11)
    import opencc
    _S2T = opencc.OpenCC('s2t').convert
except ImportError:
    _S2T = None


def traditional(s):
    return _S2T(s) if _S2T else s

INBOX = os.path.join(os.path.dirname(__file__), '..', 'data', 'super-grok-analysis.json')
INBOX_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'grok-inbox')
VALID = {'睇好', '睇淡', '中性', '未表態'}
NOT_TICKERS = {'BULLSHIT'}  # not a stock ticker (team, 2026-10-08): a swear word. SPCX is SpaceX, Nasdaq-listed since 2026-06-12 (Tim, 2026-10-18)
# Macro tab (Tim, 2026-10-13): fixed theme codes and the post's effect on US stocks
MACRO_THEMES = ('rates', 'inflation', 'jobs', 'growth', 'yields', 'fx', 'energy', 'policy', 'other')
MACRO_IMPACT = {'bullish': 'bullish', 'bearish': 'bearish', 'neutral': 'neutral',
                '利好': 'bullish', '利淡': 'bearish', '中性': 'neutral'}


def clean(a):
    """Keep only well-formed fields so one odd answer can't break the page."""
    if not isinstance(a, dict) or not isinstance(a.get('zh_summary'), str) or not a['zh_summary'].strip():
        return None
    sbt = a.get('stance_by_ticker') if isinstance(a.get('stance_by_ticker'), dict) else {}
    sbt = {str(k).upper().lstrip('$'): v for k, v in sbt.items() if v in VALID and str(k).strip() and str(k).upper().lstrip("$") not in NOT_TICKERS}
    tickers = [str(t).upper().lstrip('$') for t in (a.get('tickers') or []) if str(t).strip() and str(t).upper().lstrip("$") not in NOT_TICKERS]
    tickers = list(dict.fromkeys(tickers + [t for t in sbt if t not in tickers]))
    for t in tickers:
        sbt.setdefault(t, '未表態')
    o = {'zh_summary': traditional(a['zh_summary'].strip()).replace('——', '，').replace('—', '，'), 'tickers': tickers}
    for k in ('en_summary',):
        if isinstance(a.get(k), str) and a[k].strip():
            o[k] = a[k].strip().replace('——', ', ').replace('—', ', ')
    o['macro'] = bool(a.get('macro'))
    if 'macro_theme' in a:  # present (even null) = SuperGrok judged it; null means plain index talk, not on the macro tab
        th = a.get('macro_theme')
        o['macro_theme'] = th if o['macro'] and th in MACRO_THEMES else None
        o['macro_impact'] = MACRO_IMPACT.get(a.get('macro_impact')) if o['macro_theme'] else None
    st = a.get('stance') if a.get('stance') in ('睇好', '睇淡', '中性') else None
    if tickers:
        o['stance_by_ticker'] = sbt
        if st is None and any(v != '未表態' for v in sbt.values()):
            dirs = {v for v in sbt.values() if v in ('睇好', '睇淡')}
            st = dirs.pop() if len(dirs) == 1 else '中性'
    o['stance'] = st
    if st in ('睇好', '睇淡') and a.get('horizon') in ('短線', '中線', '長線'):
        o['horizon'] = a['horizon']
    if a.get('basis') in ('基本面', '技術面', '催化劑', '宏觀', '估值', '情緒'):
        o['basis'] = a['basis']
    if tickers:
        o['specific'] = bool(a.get('specific'))
    notes = a.get('ticker_notes') if isinstance(a.get('ticker_notes'), dict) else {}
    notes = {str(k).upper().lstrip('$'): traditional(str(v))[:40] for k, v in notes.items()}
    notes = {k: v for k, v in notes.items() if sbt.get(k) in ('睇好', '睇淡')}
    if notes:
        o['ticker_notes'] = notes
    return o


def inbox_posts(raw):
    """A batch file is {"posts": {id: row}} or just {id: row}. Anything else counts as empty."""
    if not isinstance(raw, dict):
        return {}
    posts = raw.get('posts', raw)
    return posts if isinstance(posts, dict) else {}


POST_KEY = re.compile(r'"(\d{6,})"\s*:\s*\{')


def read_inbox(path):
    """Read a batch file; when Grok breaks the JSON (e.g. an extra closing brace), pull out each post row anyway."""
    try:
        return json.load(open(path, encoding='utf-8'))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        text = open(path, encoding='utf-8').read()
    dec, posts = json.JSONDecoder(), {}
    for m in POST_KEY.finditer(text):
        try:
            row, _ = dec.raw_decode(text, m.end() - 1)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and 'en_summary' in row:
            posts[m.group(1)] = row
    notice(f'{os.path.basename(path)} is not valid JSON; recovered {len(posts)} posts')
    return {'posts': posts}


def inbox_files():
    return sorted(glob.glob(os.path.join(INBOX_DIR, '*.json')))


def load_inbox():
    inbox = dict(inbox_posts(read_json(INBOX, {})))
    for f in inbox_files():
        inbox.update(inbox_posts(read_inbox(f)))
    return inbox


def main():
    posts = read_json(work('new_posts.json'), {'posts': []})['posts']
    done = read_json(work('analysed.json'), {})
    if not isinstance(done, dict):
        done = {}
    inbox = load_inbox()
    if _S2T is None:
        notice('未裝 opencc，中文摘要冇自動轉繁體', 'warning')
    applied = 0
    for p in posts:
        pid = str(p.get('id'))
        if not pid or pid in done:
            continue
        a = clean(inbox.get(pid))
        if a:
            done[pid] = a
            applied += 1
    write_json(work('analysed.json'), done)
    left = len([p for p in posts if str(p.get('id')) not in done])
    notice(f'分析：SuperGrok 摘要套用 {applied} 則，未完成 {left} 則（唔再呼叫 xAI API）')
    if left and applied == 0:
        notice('SuperGrok 尚未交低新摘要，新帖留待下次', 'warning')


if __name__ == '__main__':
    main()
