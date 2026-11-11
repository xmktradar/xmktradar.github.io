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
    'zh': ('本頁免費、每 8 小時自動更新。覺得有用的話，歡迎請我們喝杯咖啡 ☕', '用 PayPal 支持'),
    'en': ('This page is free and updates every 8 hours. If it helps you, you can buy us a coffee ☕', 'Support with PayPal'),
}
CSS = ('.ct-donate{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;box-sizing:border-box;max-width:100%;'
       'margin:16px 0;padding:12px 14px;border-radius:16px;background:var(--accent-soft,#f8ecda);'
       'font-size:14px;line-height:1.45;color:var(--ink,#3b2f24)}'
       '.ct-donate p{flex:1 1 220px;min-width:0;margin:0;overflow-wrap:anywhere}'
       '.ct-donate a{flex:0 0 auto;display:inline-block;padding:8px 16px;border-radius:999px;background:var(--accent,#a5672c);'
       'color:#fff!important;font-weight:600;text-decoration:none;white-space:nowrap}'
       '.ct-donate.k-stock{margin:16px}')
# Earnings only. The shared `.ct-donate a` rule paints every anchor as the pill button, so the QR link opts out.
CSS_QR = ('.ct-donate .ct-donate-pay{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;flex:0 1 auto;min-width:0}'
          '.ct-donate a.ct-donate-qr{flex:0 0 auto;display:block;padding:0;background:transparent!important;border-radius:8px;'
          'line-height:0;white-space:normal}'
          '.ct-donate a.ct-donate-qr img{display:block;width:120px;height:120px;max-width:100%;background:#fff;'
          'border:1px solid var(--line,#e3e3e8);border-radius:8px;padding:4px;box-sizing:border-box}'
          '@media(max-width:480px){.ct-donate .ct-donate-pay{flex:1 1 100%}.ct-donate a.ct-donate-qr img{width:140px;height:140px}}')
QR_ALT = {'zh': 'PayPal 捐贈 QR code', 'en': 'PayPal donation QR code'}


def box(lang, kind):
    msg, btn = TEXT[lang]
    click = ("if(window.gtag)gtag('event','donate_click',{method:'paypal',page:'%s',lang:'%s'})" % (kind, lang))
    link = f'<a href="{PAYPAL}" target="_blank" rel="noopener" onclick="{click}">{btn}</a>'
    css = CSS
    if kind == 'earnings':
        css = CSS + CSS_QR
        link = (f'<span class="ct-donate-pay">{link}'
                f'<a class="ct-donate-qr" href="{PAYPAL}" target="_blank" rel="noopener" onclick="{click}">'
                f'<img src="/assets/donate/paypal.png" alt="{QR_ALT[lang]}" width="120" height="120" '
                f'loading="lazy" decoding="async"></a></span>')
    return (f'{OPEN}<style>{css}</style><aside class="ct-donate k-{kind}" aria-label="{btn}"><p>{msg}</p>'
            f'{link}</aside>{CLOSE}')


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
