"""Write the weekly comparison page in Chinese and English.

Writes zh/weekly/index.html and en/weekly/index.html. /weekly/ redirects to
the Chinese page and keeps the query and hash. Monday's comparison includes
the weekly report; it is not a second product.

The subscribe button links to the Stripe Payment Link for USD 5/month
(same tab). The tracked-account count is len(tracked.accounts) from the
Chinese master dash-data in index.html.
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone

import pay_moments

SITE = 'https://thecrowdtape.com/'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYMENT_LINK = 'https://buy.stripe.com/cNiaEXfyE8961qM83H2cg02'
REDIRECT = '<script>(function(){location.replace("/zh/weekly/"+location.search+location.hash)})();</script>'
DASH = re.compile(r'<script type="application/json" id="dash-data">(.*?)</script>', re.S)
# Placeholder copy and lookalikes that must not return. A billing-portal id can
# resemble a Payment Link id; only PAYMENT_LINK is allowed.
FORBIDDEN = (
    'Checkout 尚未接通',
    '唔會收費',
    '#checkout-placeholder',
    'cta-wait',
    'wait-note',
    'aria-disabled',
    'donate.stripe.com',
    'tip-usd-5',
    'billing.stripe.com',
    'invoice.stripe.com',
    'paypal.com',
    'application/ld+json',
    'price_',
)


def dash():
    master = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    m = DASH.search(master)
    if not m:
        raise SystemExit('index.html has no dash-data block')
    return json.loads(m.group(1).replace('<\\/', '</'))


def account_count():
    """Official roster size: len(tracked.accounts) in index.html dash-data.

    index.html is the Chinese master. zh/index.html can lag it, so do not read that copy.
    """
    data = dash()
    accounts = (data.get('tracked') or {}).get('accounts')
    if not isinstance(accounts, list) or not accounts:
        raise SystemExit('dash-data has no tracked.accounts')
    return len(accounts)


def pct(value):
    if value is None:
        return '—'
    return f'{"+" if value > 0 else ""}{value * 100:.1f}%'


def sample_html(t):
    """Eight redacted slots. No tickers and no numbers from the public scorecard."""
    parts = [
        f'<h2>{t["sample_h"]}</h2>',
        f'<p>{t["sample_p"]}</p>',
    ]
    for n in range(1, 9):
        parts.append(
            f'<div class="wk-row"><span class="wk-t">{n}. $____</span>'
            f'<span class="wk-side">{t["sample_side"]}</span>'
            f'<span class="wk-meta">{t["sample_meta"]}</span></div>'
        )
    return ''.join(parts)


def by_move(row):
    """Highest price gain first, biggest drop last. Missing prices go last."""
    ret = row.get('ret')
    if not isinstance(ret, (int, float)):
        return (1, 0, str(row.get('ticker') or ''))
    return (0, -ret, str(row.get('ticker') or ''))


def scorecard_html(t):
    """Public settled week, sorted by price move. No current-week tickers."""
    data = dash()
    hist = data.get('cons_hist') or {}
    if not hist:
        return f'<section class="wk"><p>{t["no_hist"]}</p></section>'
    today = max(hist)
    eps = pay_moments.episodes(hist)
    start = pay_moments.monday(today)
    end = pay_moments.plus_days(start, 6)
    current = pay_moments.week_rows(eps, start, end)
    bulls = sum(1 for row in current if row['side'] == 'bull')
    bears = sum(1 for row in current if row['side'] == 'bear')
    ft_path = os.path.join(ROOT, 'data', 'followthrough.json')
    ft = {}
    if os.path.isfile(ft_path):
        ft = json.load(open(ft_path, encoding='utf-8'))
    pub_start, pub_rows = pay_moments.public_score(ft, today)
    parts = ['<section class="wk" id="settled">', sample_html(t)]
    if pub_start and pub_rows:
        pub_end = pay_moments.plus_days(pub_start, 6)
        xs = [row['xs'] for row in pub_rows if isinstance(row.get('xs'), (int, float))]
        directional = [row for row in pub_rows if row.get('side') in ('bull', 'bear') and isinstance(row.get('xs'), (int, float))]
        hits = [row for row in directional if row['xs'] > 0]
        avg = sum(xs) / len(xs) if xs else None
        hit = f'{round(100 * len(hits) / len(directional))}%' if directional else '—'
        span = pay_moments.zh_span(pub_start, pub_end) if t['lang'] == 'zh' else f'{pub_start.month}/{pub_start.day}–{pub_end.month}/{pub_end.day}'
        parts.append(f'<h2>{t["settled_h"]} · {span}</h2>')
        parts.append(
            f'<p>{t["settled_p"].format(n=len(pub_rows), avg=pct(avg), hit=hit)}</p>'
        )
        parts.append('<div>')
        ordered = sorted(pub_rows, key=by_move)
        for row in ordered:
            ticker = str(row.get('ticker') or '')
            if row.get('side') == 'bull':
                side = f'<span class="wk-side wk-up">{t["bull"]}</span>'
            elif row.get('side') == 'bear':
                side = f'<span class="wk-side wk-dn">{t["bear"]}</span>'
            else:
                side = f'<span class="wk-side">{t["split"]}</span>'
            xs_v = row.get('xs')
            klass = 'wk-up' if isinstance(xs_v, (int, float)) and xs_v > 0 else 'wk-dn' if isinstance(xs_v, (int, float)) and xs_v < 0 else ''
            beat = t['beat'] if isinstance(xs_v, (int, float)) and xs_v > 0 else t['miss'] if isinstance(xs_v, (int, float)) and xs_v < 0 else ''
            parts.append(
                f'<div class="wk-row"><span class="wk-t">{ticker}</span>{side}'
                f'<span class="wk-meta">{t["price"]} {pct(row.get("ret"))}'
                f' · <span class="{klass}">{t["vs"]} {pct(xs_v)} {beat}</span></span></div>'
            )
        parts.append('</div>')
    else:
        parts.append(f'<h2>{t["settled_h"]}</h2><p>{t["no_settled"]}</p>')
    parts.append('</section>')
    parts.append('<section class="wk" id="this-week">')
    span = pay_moments.zh_span(start, end) if t['lang'] == 'zh' else f'{start.month}/{start.day}–{end.month}/{end.day}'
    parts.append(f'<h2>{t["week_h"]} · {span}</h2>')
    mentions, posts_by_day = pay_moments.load_mentions()
    focus = pay_moments.focus_rows(current, mentions, posts_by_day)
    parts.append(t['week_p'].format(today=today, bulls=bulls, bears=bears, focus=len(focus)))
    parts.append('</section>')
    html = ''.join(parts)
    public = {str(row.get('ticker') or '') for row in pub_rows}
    public.add('QQQ')
    leaked = sorted({row['t'] for row in current if row['t'] not in public})
    for ticker in leaked:
        if re.search(r'(?<![A-Z0-9])' + re.escape(ticker) + r'(?![A-Z0-9])', html):
            raise SystemExit('weekly page leaked a current-week name: ' + ticker)
    rets = [row.get('ret') for row in ordered] if pub_start and pub_rows else []
    nums = [v for v in rets if isinstance(v, (int, float))]
    if nums != sorted(nums, reverse=True):
        raise SystemExit('settled rows are not sorted from biggest gain to biggest drop')
    return html


ZH = {
    'lang': 'zh', 'html_lang': 'zh-Hant', 'canon': SITE + 'zh/weekly/', 'home': '/zh/',
    'zh_current': 'aria-current="page"', 'en_current': '',
    'title': '對倉，不是跟單｜The Crowd Tape 週報',
    'desc': '星期一的對倉包括週報。上週新列入、上次跟了會否跑輸，名稱只在電郵。已結算成績由升幅最高排到跌幅最多。每月 USD 5。不是投資建議。',
    'nav_label': '網站', 'lang_label': '語言', 'nav_tools': '工具', 'nav_support': '支持我們', 'nav_news': '電子報', 'aff_tag': '推廣',
    'h1': '對倉，不是跟單',
    'checkout_ok': '訂閱已完成。下一個週一早上開始收到對倉，當中包括週報。',
    'lead': '今日名單免費。星期一替你對倉，而對倉包括週報：上週新列入、上次跟了會否跑輸，以及那封寫好的週報。名稱只在電郵。',
    'cta': '星期一替我對倉，每月 USD 5（隨時可取消）',
    'form_lead': '用付款同一個電郵，填最多八隻持倉。星期一的對倉包括週報，另有一段只寫這八隻。未填的人仍會收到週報，但沒有個人那一段。',
    'email_label': '付款電郵', 'hold_label': '持倉，最多八隻', 'save_btn': '儲存持倉',
    'saved': '已儲存。下一個週一的對倉會包括這八隻。',
    'save_fail': '未能儲存。請用付款同一個電郵再試一次。',
    'save_later': '未能儲存。請稍後再試。',
    'includes': '追蹤 {{accounts}} 個帳號。這次訂閱就是星期一的對倉，對倉包括週報，不是另買一份。週報照固定結構寫。價格未核對的會寫「未核」，不補數字。',
    'inc1': '本週一句話，以及方向最齊、討論最多但意見最分裂的對照',
    'inc2': '相對上一期的淨值變化；上期未進入前列的，不寫成上期是零',
    'inc3': '歷史準確度留固定位置；未核對 QQQ、SOX 收市價就不報勝率',
    'inc4': '下週要回答的問題，只追本期寫過的名稱',
    'fit': '適合已經持有美股、不想每星期自己對名單的人。電郵不叫人買，也不叫人賣。下一個週一早上開始收到。',
    'disclaimer': '免責：內容只供參考，不構成投資建議。投資涉及風險，包括可能損失本金。',
    'aff_title': '聯盟推廣連結聲明',
    'aff_body': '本站部分連結屬聯盟推廣連結。你經由連結註冊或購買，我們可能獲得佣金，你無需多付。佣金不會影響好淡統計。本站內容不構成投資建議。',
    'back': '返回首頁',
    'sample_h': '星期一電郵最多八隻',
    'sample_p': '對倉包括週報。這八隻只挑上週新列入、上次同類又跑輸最多的。名稱只在電郵。',
    'sample_side': '共同看好或共同看淡',
    'sample_meta': '上次同類：跑輸。今次是新列入。不是投資建議。',
    'no_hist': '共識紀錄暫時讀不到。',
    'settled_h': '已結算成績',
    'settled_p': '這是最近一個已經有 10 個交易日收市價的星期。共 {n} 段，相對 QQQ 平均 {avg}。看好或看淡裡，正數佔 {hit}。下面由股價升幅最高排到跌幅最多。看淡的正數代表當時看淡之後跑贏 QQQ，不是股價上升。不是投資建議。',
    'bull': '共同看好', 'bear': '共同看淡', 'split': '分歧',
    'price': '股價', 'vs': '相對 QQQ', 'beat': '跑贏', 'miss': '跑輸',
    'no_settled': '暫時沒有已結算的星期。',
    'week_h': '今個星期',
    'week_p': '<p>截至 {today}，新列入<span class="wk-up">共同看好</span> {bulls} 次、<span class="wk-dn">共同看淡</span> {bears} 次。其中討論突然集中 {focus} 隻。名稱只在星期一的對倉電郵，而那封電郵包括週報。這不是即將爆發。不是投資建議。</p>',
    'count': '{n} 個帳號',
}


EN = {
    'lang': 'en', 'html_lang': 'en', 'canon': SITE + 'en/weekly/', 'home': '/en/',
    'zh_current': '', 'en_current': 'aria-current="page"',
    'title': 'Compare your book, do not copy the crowd | The Crowd Tape',
    'desc': 'Monday\'s comparison includes the weekly report. New names from last week stay in the email. Settled results run from the biggest gain to the biggest drop. USD 5 a month. Not investment advice.',
    'nav_label': 'Site', 'lang_label': 'Language', 'nav_tools': 'Tools', 'nav_support': 'Support', 'nav_news': 'Newsletter', 'aff_tag': 'Affiliate',
    'h1': 'Compare your book. Do not copy it.',
    'checkout_ok': 'You are subscribed. Next Monday\'s comparison includes the weekly report.',
    'lead': 'Today\'s list is free. On Monday the comparison includes the weekly report: last week\'s new names, whether that kind of call beat QQQ, and the written brief. Names stay in the email.',
    'cta': 'Compare my book on Monday, USD 5 a month (cancel any time)',
    'form_lead': 'Use the same email you paid with. Save up to eight holdings. Monday\'s comparison includes the weekly report, plus a short section on these eight. If you leave this blank, you still get the report, without that section.',
    'email_label': 'Payment email', 'hold_label': 'Holdings, up to eight', 'save_btn': 'Save holdings',
    'saved': 'Saved. Next Monday\'s comparison will include these eight.',
    'save_fail': 'Not saved. Use the same email you paid with and try again.',
    'save_later': 'Not saved. Try again later.',
    'includes': 'Tracking {{accounts}} accounts. This subscription is the Monday comparison, and the comparison includes the weekly report. It is not a second purchase. Where a price has not been checked, the report says so and does not fill in a number.',
    'inc1': 'One line on the week, plus the most agreed name and the most divided name',
    'inc2': 'How the net bullish count changed from the previous issue',
    'inc3': 'A fixed place for the track record; no win rate unless QQQ and SOX closes were checked',
    'inc4': 'Three questions the next issue has to answer, only about names already written up',
    'fit': 'For people who already hold US stocks and do not want to check the list themselves every week. The email does not say buy or sell. It starts next Monday morning.',
    'disclaimer': 'Disclaimer: for reference only, not investment advice. Investing involves risk, including loss of principal.',
    'aff_title': 'Affiliate links',
    'aff_body': 'Some links are affiliate links. If you sign up or buy through them, we may earn a commission at no extra cost to you. Commission does not change the bullish or bearish counts. This is not investment advice.',
    'back': 'Back to the homepage',
    'sample_h': 'Monday\'s email names at most eight',
    'sample_p': 'The comparison includes the weekly report. These eight are last week\'s new names whose previous call of the same kind lagged the most. The names stay in the email.',
    'sample_side': 'Jointly bullish or jointly bearish',
    'sample_meta': 'Previous call of the same kind lagged. This one is newly listed. Not investment advice.',
    'no_hist': 'The consensus record is not available.',
    'settled_h': 'Settled results',
    'settled_p': 'This is the latest week that already has ten session closes. {n} episodes, average versus QQQ {avg}. Of the bullish or bearish calls, {hit} were positive versus QQQ. Listed from the biggest price gain to the biggest drop. A positive number on a bearish call means the bearish call beat QQQ, not that the stock rose. Not investment advice.',
    'bull': 'Jointly bullish', 'bear': 'Jointly bearish', 'split': 'Split',
    'price': 'Price', 'vs': 'vs QQQ', 'beat': 'ahead', 'miss': 'behind',
    'no_settled': 'No settled week yet.',
    'week_h': 'This week',
    'week_p': '<p>As of {today}, newly listed <span class="wk-up">jointly bullish</span> {bulls}, <span class="wk-dn">jointly bearish</span> {bears}. Discussion suddenly concentrated: {focus}. Names stay in Monday\'s comparison email, and that email includes the weekly report. This is not a list of stocks about to surge. Not investment advice.</p>',
    'count': '{n} accounts',
}


def page(template, text, accounts, scorecard):
    html = template
    for key, value in text.items():
        if key in ('lang',):
            continue
        html = html.replace('{{' + key + '}}', value)
    html = html.replace('{{lang}}', text['html_lang'])
    html = html.replace('{{accounts}}', str(accounts))
    html = html.replace('{{scorecard}}', scorecard)
    return html


def with_zh_redirect(html):
    """Root /weekly/ always goes to /zh/weekly/. Not the language-detect script."""
    if '</head>' not in html:
        raise SystemExit('weekly template has no </head>')
    return html.replace('</head>', REDIRECT + '</head>', 1)


def write(path, html):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w', encoding='utf-8').write(html)
    print(path)


def dedupe_sitemap(sm):
    """One <url> per <loc>; the last copy wins."""
    found = []
    for m in re.finditer(r'\s*<url>.*?</url>', sm, flags=re.S):
        loc = re.search(r'<loc>([^<]*)</loc>', m.group())
        found.append((m, loc.group(1) if loc else None))
    last = {}
    for i, (_, loc) in enumerate(found):
        if loc is not None:
            last[loc] = i
    out, pos = [], 0
    for i, (m, loc) in enumerate(found):
        if loc is not None and last[loc] != i:
            out.append(sm[pos:m.start()])
            pos = m.end()
    out.append(sm[pos:])
    return ''.join(out)


def now_hkt():
    return datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%dT%H:%M:%S+08:00')


def sitemap():
    """Add only the ZH weekly URL. lastmod matches support.py when the bare
    root row is present (publish_extras.py stamps it during Update site).
    """
    path = os.path.join(ROOT, 'sitemap.xml')
    if not os.path.exists(path):
        return
    sm = open(path, encoding='utf-8').read()
    root = re.search(r'<loc>' + re.escape(SITE) + r'</loc><lastmod>([^<]+)', sm)
    prev = re.search(r'<loc>' + re.escape(SITE) + r'zh/weekly/</loc><lastmod>([^<]+)</lastmod>', sm)
    if root:
        last = root.group(1)
    elif prev:
        last = prev.group(1)
    else:
        last = now_hkt()
    sm = re.sub(
        r'\s*<url><loc>' + re.escape(SITE) + r'(?:(?:zh|en|ko)/)?weekly/</loc>.*?</url>',
        '', sm, flags=re.S)
    alt = (
        f'<xhtml:link rel="alternate" hreflang="zh-Hant" href="{SITE}zh/weekly/"/>'
        f'<xhtml:link rel="alternate" hreflang="en" href="{SITE}en/weekly/"/>'
        f'<xhtml:link rel="alternate" hreflang="x-default" href="{SITE}zh/weekly/"/>'
    )
    rows = (
        f'\n  <url><loc>{SITE}zh/weekly/</loc><lastmod>{last}</lastmod>'
        f'<changefreq>monthly</changefreq>{alt}</url>'
        f'\n  <url><loc>{SITE}en/weekly/</loc><lastmod>{last}</lastmod>'
        f'<changefreq>monthly</changefreq>{alt}</url>'
    )
    sm = re.sub(r'\s*</urlset>\s*$', rows + '\n</urlset>\n', sm, count=1)
    sm = dedupe_sitemap(sm)
    if not sm.endswith('\n'):
        sm += '\n'
    open(path, 'w', encoding='utf-8').write(sm)
    print('sitemap weekly')


def check(html, root_html, en_html, accounts):
    if '畎' in html or '畎' in en_html:
        raise SystemExit('weekly page still has 畎; use 畀')
    for doc in (html, en_html):
        if doc.count('<h1') != 1:
            raise SystemExit('weekly page must have one h1')
        cta = re.search(r'<a\b[^>]*\bhref="' + re.escape(PAYMENT_LINK) + r'"[^>]*>', doc)
        if not cta:
            raise SystemExit('weekly CTA must use the Stripe Payment Link')
        if 'target=' in cta.group(0):
            raise SystemExit('weekly CTA must be a same-tab subscribe link')
        missed = re.findall(r'\{\{[a-z0-9_]+\}\}', doc)
        if missed:
            raise SystemExit('weekly page has unfilled placeholders: ' + ', '.join(missed))
        for bad in FORBIDDEN:
            if bad in doc:
                raise SystemExit('weekly page must not contain ' + bad)
    if f'{accounts} 個' not in html:
        raise SystemExit('Chinese weekly page is missing the tracked account count')
    if f'{accounts} accounts' not in en_html:
        raise SystemExit('English weekly page is missing the tracked account count')
    if '/en/weekly/' not in html or '/zh/weekly/' not in en_html:
        raise SystemExit('weekly pages must link to each other')
    if '對倉包括週報' not in html or 'includes the weekly report' not in en_html:
        raise SystemExit('the comparison must say it includes the weekly report')
    if '<a class="btn"' in html.split('id="settled"')[-1].split('id="this-week"')[0]:
        raise SystemExit('do not put the subscribe button inside a stock row')
    if REDIRECT not in root_html:
        raise SystemExit('root weekly redirect missing')
    if os.path.isdir(os.path.join(ROOT, 'ko/weekly')):
        raise SystemExit('refusing to leave ko/weekly')


def main():
    os.chdir(ROOT)
    accounts = account_count()
    template = open(os.path.join(ROOT, 'tools', 'weekly.html'), encoding='utf-8').read()
    zh = page(template, ZH, accounts, scorecard_html(ZH))
    en = page(template, EN, accounts, scorecard_html(EN))
    root_html = with_zh_redirect(zh)
    check(zh, root_html, en, accounts)
    write('zh/weekly/index.html', zh)
    write('en/weekly/index.html', en)
    write('weekly/index.html', root_html)
    sitemap()
    print('accounts', accounts)


if __name__ == '__main__':
    main()
