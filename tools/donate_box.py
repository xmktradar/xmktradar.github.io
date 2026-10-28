"""Small PayPal donate box on the stock, earnings and account pages (Tim, 2026-10-28).

Spec: /mnt/project-files/dashboard/account-pages-spec.md. Runs after stock_pages.js, earnings_pages.py and
account_pages.js. Idempotent: a box already on the page (between the markers) is replaced.
Place: after the page content, before the disclaimer / promo lines:
  stock pages    before <p class="tv-line">
  earnings pages before the last <p class="small"> (sources + not-advice line)
  account pages  before <p class="ac-px-note">
PayPal only, the same link as the homepage box. A click sends the GA event donate_click.
"""
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYPAL = 'https://www.paypal.com/qrcodes/p2pqrc/3KT8QNVNRWJMA'
OPEN, CLOSE = '<!-- donate-box -->', '<!-- /donate-box -->'
TEXT = {
    'zh': ('本頁免費、每 4 小時自動更新。覺得有用的話，歡迎請我們喝杯咖啡 ☕', '用 PayPal 支持'),
    'en': ('This page is free and updates every 4 hours. If it helps you, you can buy us a coffee ☕', 'Support with PayPal'),
}
CSS = ('.ct-donate{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;box-sizing:border-box;max-width:100%;'
       'margin:16px 0;padding:12px 14px;border-radius:16px;background:var(--accent-soft,#f8ecda);'
       'font-size:14px;line-height:1.45;color:var(--ink,#3b2f24)}'
       '.ct-donate p{flex:1 1 220px;min-width:0;margin:0;overflow-wrap:anywhere}'
       '.ct-donate a{flex:0 0 auto;display:inline-block;padding:8px 16px;border-radius:999px;background:var(--accent,#a5672c);'
       'color:#fff!important;font-weight:600;text-decoration:none;white-space:nowrap}'
       '.ct-donate.k-stock{margin:16px}')


def box(lang, kind):
    msg, btn = TEXT[lang]
    click = ("if(window.gtag)gtag('event','donate_click',{method:'paypal',page:'%s',lang:'%s'})" % (kind, lang))
    return (f'{OPEN}<style>{CSS}</style><aside class="ct-donate k-{kind}" aria-label="{btn}"><p>{msg}</p>'
            f'<a href="{PAYPAL}" target="_blank" rel="noopener" onclick="{click}">{btn}</a></aside>{CLOSE}')


def anchor_at(html, kind):
    if kind == 'stock':
        return html.find('<p class="tv-line">')
    if kind == 'account':
        return html.find('<p class="ac-px-note">')
    end = html.find('</main>')
    return html.rfind('<p class="small">', 0, end) if end > 0 else -1


def apply(html, lang, kind):
    html = re.sub(re.escape(OPEN) + r'.*?' + re.escape(CLOSE), '', html, flags=re.S)
    i = anchor_at(html, kind)
    if i < 0:
        return None
    return html[:i] + box(lang, kind) + html[i:]


def main():
    done, missed = 0, []
    for lang in TEXT:
        for kind, sub in (('stock', 'stock'), ('earnings', 'earnings'), ('account', 'account')):
            for f in sorted(glob.glob(os.path.join(ROOT, lang, sub, '*', 'index.html'))):
                s = open(f, encoding='utf-8').read()
                out = apply(s, lang, kind)
                if out is None:
                    missed.append(os.path.relpath(f, ROOT))
                    continue
                if out != s:
                    open(f, 'w', encoding='utf-8').write(out)
                done += 1
    print(f'donate box: {done} pages, {len(missed)} without a place')
    if missed:
        print('::warning::捐款盒搵唔到位置：' + '、'.join(missed[:20]))


if __name__ == '__main__':
    main()
