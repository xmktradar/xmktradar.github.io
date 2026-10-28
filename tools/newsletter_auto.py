"""Weekly newsletter, written and sent with no AI and no hands (Tim, 2026-10-28).

Spec: /mnt/project-files/dashboard/newsletter-auto-spec.md.
Runs in Update site before "Newsletter pages". On the first run on or after Monday 07:00 HKT it writes last
week's issue (Monday to Sunday, HKT days) in the issue-1 format: English text plus a Chinese summary.
- Numbers come from tools/stats.js run on index.html with the week as its window (the site's own consensus code).
- Macro rows come from macro_week.week() (same counts as the Saturday macro post).
- data/newsletter/issue-<n>.txt + a row in data/newsletter-issues.json; tools/newsletter.py builds the archive page.
- Sending: Resend broadcast to the subscriber audience (secret RESEND_API_KEY; RESEND_AUDIENCE_ID optional, found from the account when unset). A broadcast
  named "The Crowd Tape weekly #<n>" that Resend already has is never sent again, so reruns cannot double-send.
  No key or a failed send: warning only; the archive still ships and later Monday runs try again.
Usage: python3 tools/newsletter_auto.py [--week YYYY-MM-DD (the Monday)] [--no-send] [--out file]
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sitedata import HK, load, read_json, work  # noqa: E402
import macro_week  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://thecrowdtape.com/'
ISSUES = os.path.join(ROOT, 'data', 'newsletter-issues.json')
DIR = os.path.join(ROOT, 'data', 'newsletter')
SENT = os.path.join(ROOT, 'data', 'newsletter-sent.json')
FROM = os.environ.get('NEWSLETTER_FROM') or 'The Crowd Tape <digest@thecrowdtape.com>'
API = 'https://api.resend.com'
SEND_HOUR = 7


def notice(msg, level='warning'):
    print(f'::{level}::{msg}')


def week_of(now):
    """Last Monday-Sunday (HKT days) once it is Monday 07:00 or later; None on other days."""
    if now.weekday() != 0 or now.hour < SEND_HOUR:
        return None
    d1 = now.date() - timedelta(days=1)
    return d1 - timedelta(days=6), d1


def fmt_dates(d0, d1):
    a = f'{d0:%b} {d0.day}'
    b = f'{d1.day}' if d0.month == d1.month else f'{d1:%b} {d1.day}'
    return f'{a}–{b}, {d1.year}'


def zh_dates(d0, d1):
    return f'{d0.month}月{d0.day}日至{"" if d0.month == d1.month else f"{d1.month}月"}{d1.day}日'


def run_stats(d0, d1):
    win = work('newsletter-window.json')
    out = work('newsletter-stats.json')
    json.dump({'daily': {'from': d0.isoformat(), 'to': d1.isoformat()}}, open(win, 'w'))
    subprocess.run(['node', os.path.join(ROOT, 'tools', 'stats.js'), os.path.join(ROOT, 'index.html'), win, out], check=True)
    return json.load(open(out))['daily']


def clip(t, n):
    t = re.sub(r'\s+', ' ', str(t or '')).strip()
    return t if len(t) <= n else t[:n - 1].rstrip(' ，,。.;；') + '…'


def quote(group, en_by_url):
    """Newest row of the group's side with a summary: (@acc, english text, chinese text)."""
    rows = sorted(group.get('rows') or [], key=lambda r: r.get('ms') or 0, reverse=True)
    want = 'bull' if group['nb'] >= group['nr'] else 'bear'
    for r in rows:
        if r.get('s') == want and (r.get('why') or '').strip():
            return r['acc'], en_by_url.get(r.get('url')) or '', r['why']
    return None


def strip_handle(t, acc):
    return re.sub(r'^\s*(?:[（(][^）)]{0,40}[）)]\s*)?@' + re.escape(acc) + r'\s*[:：,，]?\s*', '', t or '').strip()


def build(st, macro, d0, d1, n, D):
    en_by_url = {p.get('url'): p.get('en_summary') or '' for p in D.get('posts') or []}
    bull = sorted(st['bull'], key=lambda g: (-g['nb'], -g['n_posts'], g['t']))
    bear = sorted(st['bear'], key=lambda g: (-g['nr'], -g['n_posts'], g['t']))
    split = sorted(st['split'], key=lambda g: (-min(g['nb'], g['nr']), -g['n_posts'], g['t']))[:4]
    dates = fmt_dates(d0, d1)
    L = []
    L.append(f'THE CROWD TAPE — Weekly digest #{n} ({dates})')
    L.append(f'What ~{st["accounts"]} US-stock accounts on X said this week, tallied bull vs bear. Not investment advice.')
    L.append('')
    L.append('THE WEEK IN NUMBERS')
    L.append(f'{st["posts"]:,} posts from {st["accounts"]} accounts ({st["originals"]:,} originals, {st["reposts"]:,} reposts). '
             f'{st["bull_views"]:,} bullish vs {st["bear_views"]:,} bearish.')

    def side(title, rows, key, word):
        L.append('')
        if not rows:
            L.append(f'{title}: none this week')
            return
        g = rows[0]
        L.append(f'{title}: ${g["t"]}')
        line = f'{g["nb"]} bulls, {g["nr"]} bears, {g["n_posts"]} mentions.'
        q = quote(g, en_by_url)
        if q and q[1]:
            line += f' @{q[0]}: {clip(strip_handle(q[1], q[0]), 220)}'
        L.append(line)
        more = [f'${x["t"]} ({x[key]} {word})' for x in rows[1:3]]
        if more:
            L.append(f'Also {title.lower()}: ' + ', '.join(more) + '.')

    side('JOINT BULLISH', bull, 'nb', 'bulls')
    side('JOINT BEARISH', bear, 'nr', 'bears')
    if split:
        L.append('')
        L.append('MOST SPLIT')
        L.append(' · '.join(f'${g["t"]} {g["nb"]}/{g["nr"]} ({g["n_posts"]})' for g in split))
    rows = {r['theme']: r for r in macro['themes']}
    # top themes by accounts with a stance, without the catch-all "other"
    top = sorted((r for r in macro['themes'] if r['theme'] != 'other' and r['n'] >= macro_week.MIN_STANCED),
                 key=lambda r: (-r['n'], -r['accounts']))[:2]
    if top:
        L.append('')
        L.append('MACRO')
        for r in top:
            s = f'{macro_week.NAMES["en"][r["theme"]]}: {r["accounts"]} accounts, {r["bear"]} bearish vs {r["bull"]} bullish'
            q = r['quotes'].get('en')
            if q:
                s += f' (@{q["acc"]}: {clip(strip_handle(q["text"], q["acc"]), 140)})'
            L.append(s + '.')
    # Chinese summary
    zh = [f'過去7日（{zh_dates(d0, d1)}）：{st["accounts"]}個帳號、{st["posts"]}則帖文，看好{st["bull_views"]}對看淡{st["bear_views"]}。']
    if bull:
        g = bull[0]
        s = f'共同看好最齊心係 ${g["t"]}（{g["nb"]}好{g["nr"]}淡，{g["n_posts"]}次提及）'
        q = quote(g, en_by_url)
        if q and q[2]:
            s += f'，@{q[0]}：{clip(strip_handle(q[2], q[0]), 70)}'
        zh.append(s + '。')
    if bear:
        g = bear[0]
        zh.append(f'共同看淡係 ${g["t"]}（{g["nb"]}好{g["nr"]}淡）。')
    if split:
        zh.append('分歧最大：' + '、'.join(f'${g["t"]} {g["nb"]}好{g["nr"]}淡' for g in split[:2]) + '。')
    if top:
        zh.append('宏觀：' + '；'.join(f'{macro_week.NAMES["zh"][r["theme"]]} {r["accounts"]}個帳號，利淡{r["bear"]}對利好{r["bull"]}' for r in top) + '。')
    zh.append('非投資建議。')
    L += ['', '中文摘要', ''.join(zh), '']
    L.append(f'See today\'s tally: {SITE}?utm_source=newsletter&utm_medium=email&utm_campaign=issue{n}')
    L.append(f'Support: {SITE}support?utm_source=newsletter&utm_medium=email&utm_campaign=issue{n} · X: https://x.com/thecrowdtape')
    L.append('Unsubscribe: {{{RESEND_UNSUBSCRIBE_URL}}}')
    return '\n'.join(L) + '\n'


def email_html(text, n):
    """Plain text as simple HTML: $TICKER -> stock page, @handle -> account page (when they exist), links kept."""
    stocks = set(os.listdir(os.path.join(ROOT, 'en', 'stock'))) if os.path.isdir(os.path.join(ROOT, 'en', 'stock')) else set()
    accs = set(os.listdir(os.path.join(ROOT, 'en', 'account'))) if os.path.isdir(os.path.join(ROOT, 'en', 'account')) else set()
    utm = f'utm_source=newsletter&utm_medium=email&utm_campaign=issue{n}'
    tok = re.compile(r'https?://[^\s<]+|\{\{\{RESEND_UNSUBSCRIBE_URL\}\}\}|(?<![\w.])@[A-Za-z0-9_]{1,30}|\$[A-Z][A-Z0-9.]{0,9}')

    def one(line):
        out, pos = [], 0
        for m in tok.finditer(line):
            out.append(html.escape(line[pos:m.start()]))
            t = m.group(0)
            if t.startswith('{{{'):
                out.append(f'<a href="{t}">{t}</a>')
            elif t.startswith('http'):
                out.append(f'<a href="{html.escape(t)}">{html.escape(t)}</a>')
            elif t.startswith('@') and t[1:].lower() in accs:
                out.append(f'<a href="{SITE}en/account/{t[1:].lower()}/?{utm}">{html.escape(t)}</a>')
            elif t.startswith('$') and t[1:].rstrip('.') in stocks:
                tk = t[1:].rstrip('.')
                out.append(f'<a href="{SITE}en/stock/{tk}/?{utm}">${tk}</a>' + ('.' if t.endswith('.') else ''))
            else:
                out.append(html.escape(t))
            pos = m.end()
        out.append(html.escape(line[pos:]))
        return ''.join(out)

    body = []
    for line in text.rstrip('\n').split('\n'):
        if not line:
            continue
        if line.isupper() or line == '中文摘要' or line.startswith('THE CROWD TAPE'):
            body.append(f'<h3 style="margin:18px 0 6px;font-size:15px">{one(line)}</h3>')
        else:
            body.append(f'<p style="margin:0 0 8px">{one(line)}</p>')
    return ('<div style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;'
            'font-size:15px;line-height:1.5;color:#1d1d1f;max-width:620px">' + ''.join(body) + '</div>')


def resend(method, path, body=None):
    key = os.environ.get('RESEND_API_KEY', '')
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
                                          'User-Agent': 'thecrowdtape-newsletter'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or '{}')


def find_audience():
    """The subscriber list, when the RESEND_AUDIENCE_ID secret is not set: the only audience (or segment) in
    the Resend account, or the one whose name says newsletter / subscribers. None when that is not clear."""
    for path in ('/audiences', '/segments'):
        try:
            rows = resend('GET', path).get('data') or []
        except urllib.error.HTTPError:
            continue
        if len(rows) == 1:
            return rows[0].get('id')
        named = [r for r in rows if re.search(r'newsletter|subscri|crowd', r.get('name') or '', re.I)]
        if len(named) == 1:
            return named[0].get('id')
        if rows:
            notice('Resend 有幾個訂戶名單：' + '、'.join(r.get('name') or '?' for r in rows)
                   + '。請喺 GitHub 加 RESEND_AUDIENCE_ID 揀邊個')
            return None
    return None


def send(n, subject, text, html_body):
    if not os.environ.get('RESEND_API_KEY'):
        notice(f'電子報 #{n} 已寫好，但 GitHub 未有 RESEND_API_KEY，今次冇寄出')
        return None
    name = f'The Crowd Tape weekly #{n}'
    try:
        audience = os.environ.get('RESEND_AUDIENCE_ID') or find_audience()
        if not audience:
            notice(f'電子報 #{n} 已寫好，但搵唔到 Resend 訂戶名單，今次冇寄出')
            return None
        got = resend('GET', '/broadcasts')
        for b in got.get('data') or []:
            if b.get('name') == name and b.get('status') in ('sent', 'queued', 'scheduled', 'sending'):
                print(f'newsletter #{n}: Resend already has it ({b.get("status")}), not sending again')
                return b.get('id')
        body = {'audience_id': audience, 'from': FROM, 'subject': subject,
                'html': html_body, 'text': text, 'name': name}
        try:
            made = resend('POST', '/broadcasts', body)
        except urllib.error.HTTPError as e:
            if e.code != 422:
                raise
            body['segment_id'] = body.pop('audience_id')  # newer Resend accounts call audiences segments
            made = resend('POST', '/broadcasts', body)
        bid = made.get('id')
        resend('POST', f'/broadcasts/{bid}/send', {})
        print(f'newsletter #{n}: sent broadcast {bid}')
        return bid
    except Exception as e:  # never break the site build
        detail = e.read().decode()[:300] if isinstance(e, urllib.error.HTTPError) else str(e)
        notice(f'電子報 #{n} 寄唔到：{detail}')
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--week', help='Monday of the week to write (testing)')
    ap.add_argument('--no-send', action='store_true')
    ap.add_argument('--out', help='write the text here instead of the archive (sample)')
    a = ap.parse_args()
    now = datetime.now(HK)
    if a.week:
        d0 = date.fromisoformat(a.week)
        d1 = d0 + timedelta(days=6)
    else:
        w = week_of(now)
        if not w:
            print('newsletter: not Monday 07:00+ HKT, nothing to do')
            return
        d0, d1 = w
    issues = read_json(ISSUES, []) or []
    sent = read_json(SENT, {}) or {}
    row = next((r for r in issues if r.get('from') == d0.isoformat()), None)
    if row and str(row['n']) in sent:
        print(f'newsletter #{row["n"]}: already sent')
        return
    D = load(os.path.join(ROOT, 'index.html'))
    n = row['n'] if row else max([int(r.get('n') or 0) for r in issues] + [0]) + 1
    path = os.path.join(DIR, f'issue-{n}.txt')
    if row and os.path.isfile(path) and not a.out:
        text = open(path, encoding='utf-8').read()
    else:
        st = run_stats(d0, d1)
        if st['posts'] < 50:
            notice(f'電子報：{d0}–{d1} 得 {st["posts"]} 則帖，數據唔夠，今星期唔出')
            return
        text = build(st, macro_week.week(D, d1), d0, d1, n, D)
    if a.out:
        open(a.out, 'w', encoding='utf-8').write(text)
        open(a.out + '.html', 'w', encoding='utf-8').write(email_html(text, n))
        print('sample written:', a.out)
        return
    if not row:
        os.makedirs(DIR, exist_ok=True)
        open(path, 'w', encoding='utf-8').write(text)
        row = {'n': n, 'slug': f'issue-{n}', 'title': f'Weekly digest #{n}', 'dates': fmt_dates(d0, d1),
               'from': d0.isoformat(), 'to': d1.isoformat()}
        issues.append(row)
        json.dump(issues, open(ISSUES, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        open(ISSUES, 'a').write('\n')
        print(f'newsletter #{n}: written ({row["dates"]})')
    if a.no_send:
        return
    subject = f'The Crowd Tape weekly #{n} · {row["dates"]} · 一週大神好淡'
    bid = send(n, subject, text, email_html(text, n))
    if bid:
        sent[str(n)] = {'broadcast': bid, 'sent_hkt': now.strftime('%Y-%m-%d %H:%M')}
        json.dump(sent, open(SENT, 'w', encoding='utf-8'), indent=1)


if __name__ == '__main__':
    main()
