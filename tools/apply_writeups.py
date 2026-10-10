"""Apply the daily write-ups SuperGrok wrote into data/super-grok-writeups.json.

SuperGrok (the subscription) writes the daily, weekly and monthly analysis, highlight
cards and briefing once a day, in Chinese, English and Korean. This step checks each
part, removes anything unsafe from the HTML, and puts it into the page data. A part
that fails a check is skipped and logged; the rest still goes in.
"""
import re
from html import escape
from html.parser import HTMLParser

from sitedata import load, notice, read_json, save, work, write_json

INBOX = 'data/super-grok-writeups.json'
LANGS = {'zh': '', 'en': '_en', 'ko': '_ko'}
PERIODS = ('daily', 'weekly', 'monthly')
DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
STAMP = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$')
TAGS = {'p', 'h3', 'h4', 'h5', 'ul', 'ol', 'li', 'strong', 'em', 'b', 'i', 'br', 'a', 'code', 'span'}
VOID = {'br'}
LINK = re.compile(r'^(#stock/[A-Za-z0-9.\-]+|#account/[A-Za-z0-9_]+|https://(x|twitter)\.com/[\w/.\-?=&%]+)$')


class Clean(HTMLParser):
    """Keep a small set of tags; links only to stock pages or X; drop scripts and styles."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.open, self.skip = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1
            return
        if self.skip or tag not in TAGS:
            return
        a = dict(attrs)
        extra = ''
        if tag == 'a':
            href = (a.get('href') or '').strip()
            if not LINK.match(href):
                self.open.append('')  # keep the words, drop the link
                return
            extra = f' href="{escape(href)}"' + ('' if href.startswith('#') else ' target="_blank" rel="noopener"')
            if a.get('class') == 'tk':
                extra = ' class="tk"' + extra
        self.out.append(f'<{tag}{extra}>')
        if tag not in VOID:
            self.open.append(tag)

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)
            return
        if self.skip or tag not in TAGS or tag in VOID:
            return
        if tag in self.open or (tag == 'a' and '' in self.open):
            while self.open:
                t = self.open.pop()
                if t:
                    self.out.append(f'</{t}>')
                if t == tag or (tag == 'a' and t == ''):
                    break

    def handle_data(self, data):
        if not self.skip:
            self.out.append(escape(data, quote=False))

    def result(self):
        self.out += [f'</{t}>' for t in reversed(self.open) if t]
        return ''.join(self.out).replace('——', '，').replace('—', '，')


def clean_html(s):
    if not isinstance(s, str) or not s.strip():
        return None
    p = Clean()
    p.feed(s)
    p.close()
    return p.result().strip() or None


def plain(s, limit=400):
    """Card text is shown as plain text: no tags, no dashes."""
    if not isinstance(s, str):
        return None
    s = re.sub(r'<[^>]*>', '', s).replace('<', '').replace('>', '').replace('——', '，').replace('—', '，').strip()
    return s[:limit] or None


def summary_item(x, win=None):
    if not isinstance(x, dict) or not DATE.match(str(x.get('date', ''))):
        return None
    item = {'date': x['date']}
    for k in ('brief', 'full', 'html'):
        v = clean_html(x.get(k))
        if not v:
            return None
        item[k] = v
    w = win or x.get('win')
    if isinstance(w, dict) and STAMP.match(str(w.get('from', ''))) and STAMP.match(str(w.get('to', ''))):
        item['win'] = {'from': w['from'], 'to': w['to']}
    return item


def card(c):
    if not isinstance(c, dict) or not plain(c.get('headline')):
        return None
    o = {k: plain(c.get(k), 200) for k in ('headline', 'theme', 'source_note')}
    o['tone'] = c.get('tone') if c.get('tone') in ('看好', '看淡', '分歧', '中性') else '中性'
    o['points'] = [p for p in (plain(x, 200) for x in (c.get('points') or [])[:5]) if p]
    o['tickers'] = [str(t).upper().lstrip('$') for t in (c.get('tickers') or [])[:8] if re.match(r'^\$?[A-Za-z0-9.\-]{1,12}$', str(t))]
    o['handles'] = [str(h).lstrip('@') for h in (c.get('handles') or [])[:8] if re.match(r'^@?\w{1,30}$', str(h))]
    big = c.get('big')
    if isinstance(big, dict) and plain(big.get('value'), 40):
        o['big'] = {'value': plain(big.get('value'), 40), 'label': plain(big.get('label'), 60) or ''}
    return {k: v for k, v in o.items() if v is not None}


def highlights_item(x):
    if not isinstance(x, dict) or not DATE.match(str(x.get('date', ''))):
        return None, None
    cards = [c for c in (card(c) for c in (x.get('cards') or [])[:4]) if c]
    if not cards:
        return None, None
    o = {'cards': cards}
    for k in ('range', 'stats_note'):
        if plain(x.get(k)):
            o[k] = plain(x.get(k))
    return x['date'], o


def upsert(lst, item):
    """Replace the entry for the same date, or add it; keep the list in date order."""
    lst[:] = [x for x in lst if not (isinstance(x, dict) and x.get('date') == item['date'])] + [item]
    lst.sort(key=lambda x: x.get('date', '') if isinstance(x, dict) else '')


def main():
    raw = read_json(INBOX, {})
    if not isinstance(raw, dict) or not any(isinstance(raw.get(l), dict) for l in LANGS):
        notice('分析：SuperGrok 未交分析檔，今次照用舊分析')
        return
    d = load()
    done, bad = [], []
    wins = {}
    for lang, sfx in LANGS.items():  # zh first, so English and Korean reuse its time window
        part = raw.get(lang)
        if not isinstance(part, dict):
            continue
        for period in PERIODS:
            if period not in part:
                continue
            item = summary_item(part[period], wins.get(period) if lang != 'zh' else None)
            if not item:
                bad.append(f'{lang}/{period}')
                continue
            if lang == 'zh' and 'win' in item:
                wins[period] = item['win']
            upsert(d.setdefault('summaries' + sfx, {}).setdefault(period, []), item)
            done.append(f'{lang}/{period} {item["date"]}')
        if 'highlights' in part:
            day, hl = highlights_item(part['highlights'])
            if hl:
                d.setdefault('highlights' + sfx, {})[day] = hl
                done.append(f'{lang}/highlights {day}')
            else:
                bad.append(f'{lang}/highlights')
        if 'briefing' in part:
            b = part['briefing']
            html = clean_html(b.get('html')) if isinstance(b, dict) else None
            if html and DATE.match(str(b.get('date', ''))):
                upsert(d.setdefault('briefings' + sfx, []), {'date': b['date'], 'html': html})
                done.append(f'{lang}/briefing {b["date"]}')
            else:
                bad.append(f'{lang}/briefing')
    save(d)
    write_json(work('writeups.json'), {'applied': done, 'rejected': bad, 'updated_hkt': raw.get('updated_hkt')})
    notice(f'分析：放入 {len(done)} 份 SuperGrok 分析' + (f'；格式唔啱跳過：{"、".join(bad)}' if bad else ''),
           'warning' if bad else 'notice')


if __name__ == '__main__':
    main()
