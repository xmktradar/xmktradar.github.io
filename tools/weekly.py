"""Write the weekly sales page in Chinese and English.

Writes zh/weekly/index.html and en/weekly/index.html. /weekly/ redirects to
the Chinese page and keeps the query and hash. The subscription is the Monday
brief plus the names to watch. It is not a second product.

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


def vs_html(t, label, value):
    if not isinstance(value, (int, float)):
        return f'{label} {t["unchecked"]}'
    word = t['beat'] if value > 0 else t['miss'] if value < 0 else t['flat']
    klass = 'wk-up' if value > 0 else 'wk-dn' if value < 0 else ''
    return f'<span class="{klass}">{label} {pct(value)} {word}</span>'


def by_move(row):
    """Highest price gain first, biggest drop last. Missing prices go last."""
    ret = row.get('ret')
    if not isinstance(ret, (int, float)):
        return (1, 0, str(row.get('ticker') or ''))
    return (0, -ret, str(row.get('ticker') or ''))


def public_settled():
    """Latest public settled week, plus this-week context for the scorecard."""
    data = dash()
    hist = data.get('cons_hist') or {}
    out = {
        'hist': hist,
        'today': None,
        'pub_start': None,
        'pub_end': None,
        'pub_rows': [],
        'avg': None,
        'spy_avg': None,
        'hit': '—',
        'current': [],
        'start': None,
        'end': None,
        'bulls': 0,
        'bears': 0,
    }
    if not hist:
        return out
    today = max(hist)
    out['today'] = today
    eps = pay_moments.episodes(hist)
    start = pay_moments.monday(today)
    end = pay_moments.plus_days(start, 6)
    current = pay_moments.week_rows(eps, start, end)
    out['start'] = start
    out['end'] = end
    out['current'] = current
    out['bulls'] = sum(1 for row in current if row['side'] == 'bull')
    out['bears'] = sum(1 for row in current if row['side'] == 'bear')
    ft_path = os.path.join(ROOT, 'data', 'followthrough.json')
    ft = {}
    if os.path.isfile(ft_path):
        ft = json.load(open(ft_path, encoding='utf-8'))
    pub_start, pub_rows = pay_moments.public_score(ft, today)
    if pub_start and pub_rows:
        pub_end = pay_moments.plus_days(pub_start, 6)
        xs = [row['xs'] for row in pub_rows if isinstance(row.get('xs'), (int, float))]
        spy_xs = [row['xs_spy'] for row in pub_rows if isinstance(row.get('xs_spy'), (int, float))]
        directional = [
            row for row in pub_rows
            if row.get('side') in ('bull', 'bear')
            and isinstance(row.get('xs'), (int, float))
            and isinstance(row.get('xs_spy'), (int, float))
        ]
        hits = [row for row in directional if row['xs'] > 0 and row['xs_spy'] > 0]
        out['pub_start'] = pub_start
        out['pub_end'] = pub_end
        out['pub_rows'] = pub_rows
        out['avg'] = sum(xs) / len(xs) if xs else None
        out['spy_avg'] = sum(spy_xs) / len(spy_xs) if spy_xs else None
        out['hit'] = f'{round(100 * len(hits) / len(directional))}%' if directional else '—'
    return out


def span_for(t, start, end):
    if t['lang'] == 'zh':
        return pay_moments.zh_span(start, end)
    return f'{start.month}/{start.day}–{end.month}/{end.day}'


def ticker_rows_html(t, pub_rows):
    parts = ['<div>']
    ordered = sorted(pub_rows, key=by_move)
    for row in ordered:
        ticker = str(row.get('ticker') or '')
        if row.get('side') == 'bull':
            side = f'<span class="wk-side wk-up">{t["bull"]}</span>'
        elif row.get('side') == 'bear':
            side = f'<span class="wk-side wk-dn">{t["bear"]}</span>'
        else:
            side = f'<span class="wk-side">{t["split"]}</span>'
        bits = [f'{t["price"]} {pct(row.get("ret"))}']
        xs_v = row.get('xs')
        spy_v = row.get('xs_spy')
        if ticker != 'QQQ':
            bits.append(vs_html(t, t['vs_qqq'], xs_v))
        if ticker != 'SPY':
            bits.append(vs_html(t, t['vs_spy'], spy_v))
        parts.append(
            f'<div class="wk-row"><span class="wk-t">{ticker}</span>{side}'
            f'<span class="wk-meta">{" · ".join(bits)}</span></div>'
        )
    parts.append('</div>')
    return ''.join(parts), ordered


def footnote_html(t):
    note = t['summary_note']
    href = '/zh/weekly/' if t['lang'] == 'zh' else '/en/weekly/'
    if t['lang'] == 'zh':
        note = note.replace('每週頁', f'<a href="{href}">每週頁</a>', 1)
    else:
        note = note.replace('weekly page', f'<a href="{href}">weekly page</a>', 1)
    return f'<p class="wk-sum-note">{note}</p>'


def summary_table_html(t, settled, *, homepage=False):
    parts = ['<section class="wk-summary" id="settled-summary">', f'<h2>{t["summary_h"]}</h2>']
    if settled['pub_start'] and settled['pub_rows']:
        span = span_for(t, settled['pub_start'], settled['pub_end'])
        n = len(settled['pub_rows'])
        parts.append('<div class="wk-sum-wrap"><table class="wk-sum"><thead><tr>')
        for col in ('summary_col_period', 'summary_col_n', 'summary_col_qqq', 'summary_col_spy', 'summary_col_both'):
            parts.append(f'<th>{t[col]}</th>')
        parts.append('</tr></thead><tbody><tr>')
        parts.append(f'<td>{span}</td>')
        parts.append(f'<td>{t["summary_n"].format(n=n)}</td>')
        parts.append(f'<td>{t["summary_avg"].format(v=pct(settled["avg"]))}</td>')
        parts.append(f'<td>{t["summary_avg"].format(v=pct(settled["spy_avg"]))}</td>')
        parts.append(f'<td>{settled["hit"]}</td>')
        parts.append('</tr></tbody></table></div>')
        parts.append(footnote_html(t))
        if homepage:
            rows, _ = ticker_rows_html(t, settled['pub_rows'])
            parts.append(rows)
    else:
        parts.append(f'<p>{t["no_settled"]}</p>')
    parts.append('</section>')
    return ''.join(parts)


def settled_sample_html(t):
    """Fixed settled sample restored from public Weekly digest #4 and #3.

    Not the original email, not live current-week names, and not a holdings form.
    """
    if t['lang'] == 'zh':
        body = (
            '<h2>週報・潛力觀察（已結算樣本）</h2>'
            '<p class="wk-sample-label">此為已結算樣本，不是當時電郵原文，不是投資建議。電郵不叫人買，也不叫人賣。</p>'
            '<p>期間：2026年11月9日至15日</p>'
            '<p>本週一句話：239 個帳號、1,743 則帖文，看好 701、看淡 330。</p>'
            '<p>方向最齊：$AMD（共同看好，14 好 0 淡，63 次提及）</p>'
            '<p>意見最分裂：$NVDA（16 好 36 淡，703 次提及）</p>'
            '<p>跟上期（11月2日至8日）：帳號由 84 增至 239，帖文由 557 增至 1,743；共同看好由 $SPCX 改為 $AMD，共同看淡由 $ASTS 改為 $MSTR。兩期覆蓋帳號數不同，規模不要直接當同一口徑。</p>'
            '<p>整體好淡有沒有跟上 QQQ 和 SPY：未核，不報勝率。</p>'
            '<p>潛力觀察（當時新列入，現已滿十個交易日）：用來對照持倉，不是買入名單。納入條件是上一次共同看好其後十個交易日同時跑贏 QQQ 和 SPY，不是業績承諾。</p>'
            '<ol>'
            '<li>$AMZN 共同看好 股價 -4.3% · 相對 QQQ -0.2% 跑輸 · 相對 SPY -0.3% 跑輸</li>'
            '<li>$ARM 共同看好 股價 -5.2% · 相對 QQQ -1.0% 跑輸 · 相對 SPY -1.1% 跑輸</li>'
            '<li>$LITE 共同看好 股價 -8.7% · 相對 QQQ -4.5% 跑輸 · 相對 SPY -4.6% 跑輸</li>'
            '<li>$AMD 共同看好 股價 -10.8% · 相對 QQQ -6.7% 跑輸 · 相對 SPY -6.8% 跑輸</li>'
            '<li>$SHOP 共同看好 股價 -11.7% · 相對 QQQ -7.5% 跑輸 · 相對 SPY -7.6% 跑輸</li>'
            '</ol>'
            '<p>共 5 次列入。相對 QQQ 平均 -4.0%，相對 SPY 平均 -4.1%。當中 0% 同時跑贏兩個指數。</p>'
        )
    else:
        body = (
            '<h2>Weekly brief and names to watch (settled sample)</h2>'
            '<p class="wk-sample-label">This is a settled sample, not the original email, and not investment advice. The email does not say buy or sell.</p>'
            '<p>Period: 9–15 Nov 2026</p>'
            '<p>The week in one line: 239 accounts, 1,743 posts, 701 bullish vs 330 bearish.</p>'
            '<p>Most agreed: $AMD (jointly bullish, 14 bull / 0 bear, 63 mentions)</p>'
            '<p>Most divided: $NVDA (16 bull / 36 bear, 703 mentions)</p>'
            '<p>Change from last issue (2–8 Nov): Accounts 84 to 239, posts 557 to 1,743; lead jointly bullish name moved from $SPCX to $AMD, jointly bearish from $ASTS to $MSTR. Coverage is not the same size, so do not read the two issues as one consistent sample.</p>'
            "<p>Whether the crowd's direction matched QQQ and SPY: not checked. No win rate.</p>"
            '<p>Names to watch (newly listed then; ten session closes now in): For comparing with what you hold, not a buy list. Inclusion required that the previous joint bullish call beat both QQQ and SPY over the following ten sessions. That is a filter, not a performance promise.</p>'
            '<ol>'
            '<li>$AMZN jointly bullish Price -4.3% · vs QQQ -0.2% behind · vs SPY -0.3% behind</li>'
            '<li>$ARM jointly bullish Price -5.2% · vs QQQ -1.0% behind · vs SPY -1.1% behind</li>'
            '<li>$LITE jointly bullish Price -8.7% · vs QQQ -4.5% behind · vs SPY -4.6% behind</li>'
            '<li>$AMD jointly bullish Price -10.8% · vs QQQ -6.7% behind · vs SPY -6.8% behind</li>'
            '<li>$SHOP jointly bullish Price -11.7% · vs QQQ -7.5% behind · vs SPY -7.6% behind</li>'
            '</ol>'
            '<p>5 listings. Average versus QQQ -4.0%, average versus SPY -4.1%. 0% beat both indexes.</p>'
        )
    return '<section class="wk" id="settled-sample">' + body + '</section>'


def scorecard_html(t, settled=None):
    """Public settled week, sorted by price move. No current-week tickers."""
    if settled is None:
        settled = public_settled()
    if not settled['hist']:
        return f'<section class="wk"><p>{t["no_hist"]}</p></section>'
    today = settled['today']
    start = settled['start']
    end = settled['end']
    current = settled['current']
    bulls = settled['bulls']
    bears = settled['bears']
    pub_start = settled['pub_start']
    pub_rows = settled['pub_rows']
    parts = ['<section class="wk" id="settled">', sample_html(t)]
    ordered = []
    if pub_start and pub_rows:
        span = span_for(t, pub_start, settled['pub_end'])
        parts.append(f'<h2>{t["settled_h"]} · {span}</h2>')
        parts.append(
            f'<p>{t["settled_p"].format(n=len(pub_rows), avg=pct(settled["avg"]), spy=pct(settled["spy_avg"]), hit=settled["hit"])}</p>'
        )
        rows, ordered = ticker_rows_html(t, pub_rows)
        parts.append(rows)
    else:
        parts.append(f'<h2>{t["settled_h"]}</h2><p>{t["no_settled"]}</p>')
    parts.append('</section>')
    parts.append(settled_sample_html(t))
    parts.append('<section class="wk" id="this-week">')
    span = span_for(t, start, end)
    parts.append(f'<h2>{t["week_h"]} · {span}</h2>')
    mentions, posts_by_day = pay_moments.load_mentions()
    focus = pay_moments.focus_rows(current, mentions, posts_by_day)
    shown = today
    if t['lang'] == 'zh' and today and len(str(today)) >= 10:
        shown = f'{int(str(today)[5:7])}月{int(str(today)[8:10])}日'
    parts.append(t['week_p'].format(today=shown, bulls=bulls, bears=bears, focus=len(focus)))
    parts.append('</section>')
    html = ''.join(parts)
    public = {str(row.get('ticker') or '') for row in pub_rows}
    public.add('QQQ')
    public.add('SPY')
    leaked = sorted({row['t'] for row in current if row['t'] not in public})
    # The settled sample may legally name historical tickers that also appear
    # in the current unpublished week. Scan the rest of the page only.
    scan = re.sub(
        r'<section\b[^>]*\bid="settled-sample"[^>]*>.*?</section>',
        '',
        html,
        flags=re.S,
    )
    for ticker in leaked:
        # Lower case counts as part of a word. Otherwise ticker P matches PingFang, Plex and Pro, and the whole site update stops before prices are published.
        if len(ticker) < 2:
            continue
        if re.search(r'(?<![A-Za-z0-9])' + re.escape(ticker) + r'(?![A-Za-z0-9])', scan):
            raise SystemExit('weekly page leaked a current-week name: ' + ticker)

    rets = [row.get('ret') for row in ordered] if pub_start and pub_rows else []
    nums = [v for v in rets if isinstance(v, (int, float))]
    if nums != sorted(nums, reverse=True):
        raise SystemExit('settled rows are not sorted from biggest gain to biggest drop')
    return html


HOME_MARK_START = '<!-- settled-home -->'
HOME_MARK_END = '<!-- /settled-home -->'


def fill_home_region(path, inner):
    html = open(path, encoding='utf-8').read()
    start = html.find(HOME_MARK_START)
    end = html.find(HOME_MARK_END)
    if start < 0 or end < 0 or end < start:
        raise SystemExit(path + ' is missing settled-home markers')
    new = html[:start] + HOME_MARK_START + '\n' + inner + '\n' + html[end:]
    if new != html:
        open(path, 'w', encoding='utf-8').write(new)
        print(path)


def inject_homepage_tables(settled):
    """Fill generated language homepages only.

    The Chinese master keeps empty markers so build_langs + test_no_cjk do not
    need short i18n keys that would collide with dash-data or Follow-through
    copy (期間, 相對 QQQ, 跑贏).
    """
    fill_home_region(os.path.join(ROOT, 'zh/index.html'), summary_table_html(ZH, settled, homepage=True))
    fill_home_region(os.path.join(ROOT, 'en/index.html'), summary_table_html(EN, settled, homepage=True))



ZH = {
    'lang': 'zh', 'html_lang': 'zh-Hant', 'canon': SITE + 'zh/weekly/', 'home': '/zh/',
    'zh_current': 'aria-current="page"', 'en_current': '',
    'title': '週報・潛力觀察｜The Crowd Tape',
    'desc': '星期一電郵有週報，另加最多八隻做多的名字。上週新列入看好，上一次看好之後跑贏 QQQ，也跑贏 SPY。名稱只寫在電郵。每月 USD 5。不是投資建議。',
    'nav_label': '網站', 'lang_label': '語言', 'nav_tools': '工具', 'nav_support': '支持我們', 'nav_news': '電子報', 'aff_tag': '推廣',
    'h1': '週報・潛力觀察',
    'checkout_ok': '訂閱已完成。下星期一早上開始收到週報，以及最多八隻潛力觀察。',
    'lead': '今日共識名單免費。星期一電郵另寫簡報，同最多八隻觀察名單。納入條件係：上一次共同看好，其後十個交易日同時跑贏 QQQ 同 SPY。呢個係篩選規則，唔係業績承諾。名稱只寫在電郵。',
    'get_h': '訂閱後，每星期一你會收到',
    'get1': '你自己的持倉，最多八隻，對照這一期群眾怎麼講。沒有填的話，週報仍會寄出，只是沒有那封持倉對照。',
    'get2': '最多八隻做多的名字：上週新列入的共同看好，而且上一次看好之後，十個交易日跑贏 QQQ，也跑贏 SPY。用來對照你的持倉，不是買入名單。',
    'get3': '週報本身：本週一句話、方向最齊的一隻、意見最分裂的一隻、跟上期的變化，以及整體好淡有沒有跟上 QQQ 和 SPY。收市價未核對就寫「未核」，不報勝率。',
    'cta': '訂週報・潛力觀察，每月 USD 5（隨時可取消）',
    'form_lead': '請用付款時的電郵，填最多八隻持倉。填了的話，星期一另寄一封，只寫這八隻。沒填的話，週報仍會寄出。',
    'email_label': '付款電郵', 'hold_label': '持倉，最多八隻', 'save_btn': '儲存持倉',
    'saved': '已儲存。下星期一另有一封寫這八隻。週報仍會寄出。',
    'save_fail': '未能儲存。請用付款同一個電郵再試一次。',
    'save_later': '未能儲存。請稍後再試。',
    'includes': '追蹤 {{accounts}} 個帳號。週報和潛力觀察是同一次訂閱，不是另買一份。電郵不叫人買，也不叫人賣。',
    'inc1': '上一期沒有出現的名稱，不會寫成上一期是零',
    'inc2': 'QQQ 和 SPY 的收市價未核對，就不報勝率',
    'inc3': '下一期只追問這一期寫過的名稱',
    'inc4': '潛力觀察不是保證再升。條件只是上一次做多之後跑贏 QQQ 和 SPY，而且這一期才新列入',
    'fit': '適合已經持有美股、想每星期知道群眾在講什麼、又不想自己逐隻核對的人。下星期一早上開始寄出。',
    'disclaimer': '免責：內容只供參考，不構成投資建議。投資涉及風險，包括可能損失本金。',
    'aff_title': '聯盟推廣連結聲明',
    'aff_body': '本站部分連結屬聯盟推廣連結。你經由連結註冊或購買，我們可能獲得佣金，你無需多付。佣金不會影響好淡統計。本站內容不構成投資建議。',
    'back': '返回首頁',
    'sample_h': '潛力觀察，最多八隻',
    'sample_p': '這八隻都是做多。上週才被寫成共同看好；上一次看好之後，十個交易日跑贏了 QQQ，也跑贏了 SPY。星期一用來看看這段升勢還在不在，再對照你自己的持倉。名稱只寫在電郵，不列在這一頁。',
    'sample_side': '共同看好',
    'sample_meta': '上一次做多，十個交易日跑贏 QQQ 和 SPY。這一期新列入。',
    'no_hist': '共識紀錄暫時讀不到。',
    'settled_h': '已結算成績',
    'summary_h': '已結算成績（目前只有一週公開）',
    'summary_col_period': '期間',
    'summary_col_n': '列入次數',
    'summary_col_qqq': '相對 QQQ',
    'summary_col_spy': '相對 SPY',
    'summary_col_both': '同時跑贏兩個指數',
    'summary_n': '{n} 次',
    'summary_avg': '平均 {v}',
    'summary_note': '列入唔等於下次會再升。完整規則同細則見每週頁。',
    'sample_label': '此為已結算樣本，不是當時電郵原文，不是投資建議。電郵不叫人買，也不叫人賣。',
    'settled_p': '以下是最近一個已滿十個交易日的星期，共 {n} 次列入。相對 QQQ 平均 {avg}，相對 SPY 平均 {spy}。當中 {hit} 同時跑贏兩個指數。次序由股價升幅最高排到跌幅最多。看淡若顯示跑贏，是指那次看淡之後股價弱過指數，不是股價上升。不是投資建議。',
    'bull': '共同看好', 'bear': '共同看淡', 'split': '分歧',
    'price': '股價', 'vs_qqq': '相對 QQQ', 'vs_spy': '相對 SPY', 'beat': '跑贏', 'miss': '跑輸', 'flat': '持平', 'unchecked': '未核',
    'no_settled': '暫時沒有已結算的星期。',
    'week_h': '今個星期',
    'week_p': '<p>截至 {today}，本週新列入<span class="wk-up">共同看好</span> {bulls} 隻、<span class="wk-dn">共同看淡</span> {bears} 隻。其中討論較集中的有 {focus} 隻。名稱只寫在星期一電郵，這不是即將爆發的名單。不是投資建議。</p>',
    'count': '{n} 個帳號',
}


EN = {
    'lang': 'en', 'html_lang': 'en', 'canon': SITE + 'en/weekly/', 'home': '/en/',
    'zh_current': '', 'en_current': 'aria-current="page"',
    'title': 'Weekly brief and names to watch | The Crowd Tape',
    'desc': 'Monday\'s email is a written brief plus at most eight bullish names. Newly listed as bullish last week, after the previous bullish call beat QQQ and also beat SPY. Tickers are only in the email. USD 5 a month. Not investment advice.',
    'nav_label': 'Site', 'lang_label': 'Language', 'nav_tools': 'Tools', 'nav_support': 'Support', 'nav_news': 'Newsletter', 'aff_tag': 'Affiliate',
    'h1': 'Weekly brief and names to watch',
    'checkout_ok': 'You are subscribed. From next Monday morning you get the brief, plus at most eight names to watch.',
    'lead': 'Today\'s consensus list is free. Monday\'s email is a written brief plus at most eight names to watch. A name is included only if the last joint bullish call beat both QQQ and SPY over the following ten sessions. That is an inclusion filter, not a performance promise. Tickers are only in the email.',
    'get_h': 'What you get every Monday',
    'get1': 'Your own holdings, up to eight, set against what the crowd said that week. If you leave them blank, the brief still goes out. You just do not get the separate holdings note.',
    'get2': 'Up to eight bullish names: newly listed as jointly bullish last week, and the previous bullish call beat QQQ and also beat SPY over ten sessions. For comparing with what you hold, not a buy list.',
    'get3': 'The brief itself: one line on the week, the most agreed name, the most divided name, the change from last issue, and whether the crowd\'s direction matched QQQ and SPY. If a close was not checked, it says so and gives no win rate.',
    'cta': 'Get the Monday brief, USD 5 a month (cancel any time)',
    'form_lead': 'Use the email you paid with. Enter up to eight holdings. If you do, Monday also sends a separate note on just these eight. If you leave this blank, the brief still goes out.',
    'email_label': 'Payment email', 'hold_label': 'Holdings, up to eight', 'save_btn': 'Save holdings',
    'saved': 'Saved. Next Monday also sends a note on these eight. The brief still goes out.',
    'save_fail': 'Not saved. Use the same email you paid with and try again.',
    'save_later': 'Not saved. Try again later.',
    'includes': 'Tracking {{accounts}} accounts. The brief and the names to watch are one subscription, not a second purchase. The email does not say buy or sell.',
    'inc1': 'A name that was not on last issue is not written as zero for last issue',
    'inc2': 'No win rate unless the QQQ and SPY closes were checked',
    'inc3': 'The next issue only follows up on names already written this issue',
    'inc4': 'Names to watch are not a promise they rise again. The only rule is that the last bullish call beat QQQ and SPY, and the name is newly listed this issue',
    'fit': 'For people who already hold US stocks and want a weekly picture of what the crowd said, without checking every name themselves. The email starts next Monday morning.',
    'disclaimer': 'Disclaimer: for reference only, not investment advice. Investing involves risk, including loss of principal.',
    'aff_title': 'Affiliate links',
    'aff_body': 'Some links are affiliate links. If you sign up or buy through them, we may earn a commission at no extra cost to you. Commission does not change the bullish or bearish counts. This is not investment advice.',
    'back': 'Back to the homepage',
    'sample_h': 'Names to watch, at most eight',
    'sample_p': 'These eight are bullish names. They were newly marked jointly bullish last week, and the previous bullish call beat QQQ and also beat SPY over ten sessions. On Monday you can see whether that rise is still there, then compare it with what you hold. Tickers are only in the email, not on this page.',
    'sample_side': 'Jointly bullish',
    'sample_meta': 'The last bullish call beat QQQ and SPY over ten sessions. Newly listed this issue.',
    'no_hist': 'The consensus record is not available.',
    'settled_h': 'Settled results',
    'summary_h': 'Settled results (only one week is public so far)',
    'summary_col_period': 'Period',
    'summary_col_n': 'Listings',
    'summary_col_qqq': 'vs QQQ',
    'summary_col_spy': 'vs SPY',
    'summary_col_both': 'Beat both indexes',
    'summary_n': '{n}',
    'summary_avg': 'average {v}',
    'summary_note': 'A listing does not mean it will rise next time. Full rules and details are on the weekly page.',
    'sample_label': 'This is a settled sample, not the original email, and not investment advice. The email does not say buy or sell.',
    'settled_p': 'This is the latest week that already has ten session closes: {n} listings. Average versus QQQ {avg}, average versus SPY {spy}. {hit} beat both indexes. Ordered from the biggest price gain to the biggest drop. If a bearish name shows as ahead, the stock lagged the index after that bearish call. It does not mean the stock rose. Not investment advice.',
    'bull': 'Jointly bullish', 'bear': 'Jointly bearish', 'split': 'Split',
    'price': 'Price', 'vs_qqq': 'vs QQQ', 'vs_spy': 'vs SPY', 'beat': 'ahead', 'miss': 'behind', 'flat': 'flat', 'unchecked': 'not checked',
    'no_settled': 'No settled week yet.',
    'week_h': 'This week',
    'week_p': '<p>As of {today}, this week newly listed <span class="wk-up">jointly bullish</span> {bulls} and <span class="wk-dn">jointly bearish</span> {bears}. Discussion was more concentrated on {focus} of them. Names are only in Monday\'s email. This is not a list of stocks about to surge. Not investment advice.</p>',
    'count': '{n} accounts',
}


def page(template, text, accounts, scorecard, summary_table=''):
    html = template
    for key, value in text.items():
        if key in ('lang',):
            continue
        html = html.replace('{{' + key + '}}', value)
    html = html.replace('{{lang}}', text['html_lang'])
    html = html.replace('{{accounts}}', str(accounts))
    html = html.replace('{{scorecard}}', scorecard)
    html = html.replace('{{summary_table}}', summary_table)
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
    if '對倉' in html or '對倉' in en_html:
        raise SystemExit('subscription name is no longer 對倉')
    if '潛力觀察' not in html or 'names to watch' not in en_html:
        raise SystemExit('weekly page is missing the subscription name')
    if html.find('class="wk-get"') > html.find('class="lead-cta"'):
        raise SystemExit('what you get must sit above the subscribe button')
    if '你會收到' not in html or 'What you get' not in en_html:
        raise SystemExit('weekly page must say what the subscriber gets')
    if '不是另買一份' not in html or 'not a second purchase' not in en_html:
        raise SystemExit('one subscription must include the brief')
    if '<a class="btn"' in html.split('id="settled"')[-1].split('id="this-week"')[0]:
        raise SystemExit('do not put the subscribe button inside a stock row')
    if '今日共識名單免費' not in html or "Today's consensus list is free" not in en_html:
        raise SystemExit('weekly lead must use the approved hero copy')
    if '唔係業績承諾' not in html or 'not a performance promise' not in en_html:
        raise SystemExit('weekly lead must say the rule is not a performance promise')
    if '已結算成績（目前只有一週公開）' not in html or 'Settled results (only one week is public so far)' not in en_html:
        raise SystemExit('weekly page missing settled summary title')
    if '列入唔等於下次會再升' not in html or 'does not mean it will rise next time' not in en_html:
        raise SystemExit('weekly page missing settled summary footnote')
    if '週報・潛力觀察（已結算樣本）' not in html or 'Weekly brief and names to watch (settled sample)' not in en_html:
        raise SystemExit('weekly page missing settled sample')
    if '不是當時電郵原文' not in html or 'not the original email' not in en_html:
        raise SystemExit('settled sample must be labeled as not the original email')
    if '未核，不報勝率' not in html or 'not checked. No win rate' not in en_html:
        raise SystemExit('settled sample must say crowd vs QQQ/SPY was not checked')
    if html.find('class="wk-summary"') < html.find('class="lead-cta"'):
        raise SystemExit('settled summary must sit under the subscribe button')
    if html.find('id="book-mail"') < html.find('class="wk-summary"'):
        raise SystemExit('settled summary must sit above the holdings form')
    if html.count('$____') != 8 or en_html.count('$____') != 8:
        raise SystemExit('weekly page must keep eight redacted name slots')
    if REDIRECT not in root_html:
        raise SystemExit('root weekly redirect missing')


def main():
    os.chdir(ROOT)
    accounts = account_count()
    template = open(os.path.join(ROOT, 'tools', 'weekly.html'), encoding='utf-8').read()
    settled = public_settled()
    zh = page(template, ZH, accounts, scorecard_html(ZH, settled), summary_table_html(ZH, settled))
    en = page(template, EN, accounts, scorecard_html(EN, settled), summary_table_html(EN, settled))
    root_html = with_zh_redirect(zh)
    check(zh, root_html, en, accounts)
    write('zh/weekly/index.html', zh)
    write('en/weekly/index.html', en)
    write('weekly/index.html', root_html)
    inject_homepage_tables(settled)
    sitemap()
    print('accounts', accounts)


if __name__ == '__main__':
    main()
