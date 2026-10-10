"""Step 3: apply summaries SuperGrok already wrote. Do not call the xAI API.

SuperGrok (the subscription, not API credits) reads new posts, keeps the ones with a
market idea, and writes Traditional Chinese plus Korean summaries into
data/super-grok-analysis.json. This step only copies well-formed rows into
work/analysed.json. Posts that are not in that file stay in data/pending-posts.json.
"""
import json
import os
import urllib.request

from sitedata import notice, read_json, work, write_json

REMOTE = "https://raw.githubusercontent.com/timlika1121-alt/crowd-tape-inbox/main/analysis.json"

INBOX = os.path.join(os.path.dirname(__file__), '..', 'data', 'super-grok-analysis.json')
VALID = {'睇好', '睇淡', '中性', '未表態'}


def clean(a):
    """Keep only well-formed fields so one odd answer can't break the page."""
    if not isinstance(a, dict) or not isinstance(a.get('zh_summary'), str) or not a['zh_summary'].strip():
        return None
    sbt = a.get('stance_by_ticker') if isinstance(a.get('stance_by_ticker'), dict) else {}
    sbt = {str(k).upper().lstrip('$'): v for k, v in sbt.items() if v in VALID and str(k).strip()}
    tickers = [str(t).upper().lstrip('$') for t in (a.get('tickers') or []) if str(t).strip()]
    tickers = list(dict.fromkeys(tickers + [t for t in sbt if t not in tickers]))
    for t in tickers:
        sbt.setdefault(t, '未表態')
    o = {'zh_summary': a['zh_summary'].strip().replace('——', '，').replace('—', '，'), 'tickers': tickers}
    if isinstance(a.get('ko_summary'), str) and a['ko_summary'].strip():
        o['ko_summary'] = a['ko_summary'].strip().replace('——', ', ').replace('—', ', ')
    o['macro'] = bool(a.get('macro'))
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
    notes = {str(k).upper().lstrip('$'): str(v)[:40] for k, v in notes.items()}
    notes = {k: v for k, v in notes.items() if sbt.get(k) in ('睇好', '睇淡')}
    if notes:
        o['ticker_notes'] = notes
    return o


def main():
    posts = read_json(work('new_posts.json'), {'posts': []})['posts']
    done = read_json(work('analysed.json'), {})
    if not isinstance(done, dict):
        done = {}
    raw = read_json(INBOX, {})
    inbox = raw.get('posts') if isinstance(raw, dict) else None
    if not isinstance(inbox, dict):
        inbox = {}
    try:
        with urllib.request.urlopen(REMOTE, timeout=60) as r:
            remote = json.loads(r.read().decode())
        extra = remote.get('posts') if isinstance(remote, dict) else None
        if isinstance(extra, dict):
            inbox.update(extra)
            notice(f'分析：讀到 SuperGrok 遠端摘要 {len(extra)} 則')
    except Exception as e:
        notice('讀唔到 SuperGrok 遠端摘要：' + str(e)[:200], 'warning')
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
