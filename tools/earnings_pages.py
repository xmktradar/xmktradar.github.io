"""Earnings briefs, step 2: static pages from data/earnings/co/*.json (written by tools/earnings_data.py).

Writes /zh/earnings/<T>/ and /en/earnings/<T>/ (5 chapters: results vs estimates, growth, revenue lines, margins,
cash flow), the list pages /zh/earnings/ and /en/earnings/ (last 30 days, next 14 days, all companies), a link on
each stock page /<lang>/stock/<T>/ that has a brief, a link row on the homepages, and the sitemap rows.
Pages of companies that left the list are deleted. Readable without JavaScript. No AI: every number comes from
SEC filings or Yahoo Finance, with the source named on the page. Run after tools/stock_pages.js.
"""
import html
import json
import os
import re
import shutil
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sitedata import notice, read_json  # noqa: E402

SITE = 'https://thecrowdtape.com/'
LANGS = {'zh': 'zh-Hant', 'en': 'en'}
HK = timezone(timedelta(hours=8))
CO_DIR = 'data/earnings/co'
MARK = '<!-- earnings-link -->'
GA = ('<script async src="https://www.googletagmanager.com/gtag/js?id=G-42CSNJ8DF9"></script>\n'
      "<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','G-42CSNJ8DF9');</script>")
E = html.escape

L = {
    'zh': dict(
        brief='財報簡報', list_title='最新財報簡報：市值 500 億美元以上美股｜The Crowd Tape',
        list_h1='最新財報簡報', list_lead='市值 500 億美元以上嘅美國上市公司，每間最新一季財報整理成 5 章：結果 vs 預期、成長率、收入線、利潤率、現金流。數字全部來自 SEC 文件同 Yahoo Finance，每 4 小時自動更新。',
        list_desc='市值 500 億美元以上美股最新季度財報：收入、EPS 對比市場預期、按年增長、業務線拆解、利潤率同現金流，每 4 小時自動更新。',
        recent='過去 30 日公布', upcoming='未來 14 日將公布', all='全部公司', none='暫時冇。',
        th_date='日期', th_co='公司', th_q='財季', th_rev='收入按年', th_eps='EPS vs 預期',
        title=lambda t, n, q: f'{t} 財報簡報 {q}：收入、EPS、利潤率同現金流｜{n}｜The Crowd Tape',
        desc=lambda t, n, q, r, y: f'{n}（{t}）{q} 財報：收入 {r}，按年 {y}。對比市場預期、業務線拆解、利潤率同自由現金流，數字來自 SEC 文件。',
        h1=lambda t, q: f'{t} 財報簡報：{q}',
        meta=lambda n, e, f: f'{n}｜季度截至 {e}｜{f} 向 SEC 提交',
        mcap='市值', next='下次財報', us_time='（美國日期，Yahoo Finance）',
        pending=lambda q, a, s: f'⏳ 截至 {q} 嘅一季已經公布：經調整 EPS {a}' + (f'（市場預期 {s}）' if s else '') + '。完整數字要等公司向 SEC 提交 10-Q／10-K，之後自動更新。',
        c1='結果 vs 預期', c2='成長率表現', c3='收入線拆解', c4='利潤率分析', c5='現金流：撐得幾耐',
        actual='實際', est='市場預期', diff='差距', beat='好過預期', miss='差過預期', inline='符合預期',
        rev='收入', eps_adj='EPS（經調整）', eps_gaap='GAAP 攤薄 EPS', no_est='冇預期數據',
        est_note=lambda s: f'收入預期係 {s} 喺 Yahoo Finance 記錄嘅分析師平均；EPS 實際同預期來自 Yahoo Finance（經調整口徑，同公司 GAAP 數字可能唔同）。',
        est_note_eps='EPS 實際同預期來自 Yahoo Finance（經調整口徑，同公司 GAAP 數字可能唔同）。',
        yoy='按年', qoq='按季', ni='淨利潤', q8='最近季度收入', growth_note='按年 = 同去年同一季比；按季 = 同上一季比。',
        seg_none='公司喺 SEC 文件冇清楚按業務線拆解收入（或者拆解加唔埋總數），所以呢章唔顯示。',
        seg_year='公司喺年報（10-K）只公布全年嘅業務線數字，以下係全年數字。', share='佔比', other='其他',
        gm='毛利率', om='經營利潤率', nm='淨利率', this_q='今季', last_q='上季', last_y='去年同季', na='不適用',
        bank_note='銀行同金融公司冇「毛利」概念，收入係扣除利息支出後嘅淨收入。',
        cash='現金同短期投資', debt='債務（長期債 + 短期借款）', net_cash='淨現金', net_debt='淨負債',
        ocf='經營現金流（今季）', capex='資本開支（今季）', fcf='自由現金流（今季）', fcf_ttm='自由現金流（過去 4 季）',
        runway=lambda m: f'⚠️ 過去 4 季自由現金流係負數。照呢個速度，現金同短期投資大約撐到 {m} 個月。',
        runway_ok='✅ 過去 4 季自由現金流係正數，日常運作唔使靠消耗現有現金。',
        runway_na='現金流數據未齊，暫時計唔到。',
        runway_bank='銀行嘅現金流主要受存款同貸款變動影響，唔適合用嚟計「撐得幾耐」。',
        source=lambda f: f'資料來源：SEC EDGAR（XBRL，{f} 提交）、Yahoo Finance。只係整理公開數字，唔構成投資建議。',
        updated='更新時間', back='返回最新財報列表', home='首頁', stock='大神點睇呢隻股', all_briefs='最新財報簡報',
        link_row='📊 最新財報簡報', link_note='市值 500 億美元以上美股', bn=lambda v: fmt_zh(v),
        nav='網站', lang_nav='語言', na_short='—',
    ),
    'en': dict(
        brief='Earnings brief', list_title='Latest earnings briefs: US stocks worth $50B+ | The Crowd Tape',
        list_h1='Latest earnings briefs', list_lead="Every US-listed company worth $50B or more, its latest quarter in 5 chapters: results vs estimates, growth, revenue lines, margins and cash flow. All numbers come from SEC filings and Yahoo Finance and update automatically every 4 hours.",
        list_desc='Latest quarterly results of US stocks worth $50B+: revenue and EPS vs estimates, growth, revenue lines, margins and cash flow, updated every 4 hours.',
        recent='Reported in the last 30 days', upcoming='Reporting in the next 14 days', all='All companies', none='None right now.',
        th_date='Date', th_co='Company', th_q='Quarter', th_rev='Revenue YoY', th_eps='EPS vs est.',
        title=lambda t, n, q: f'{t} earnings brief {q}: revenue, EPS, margins and cash flow | {n} | The Crowd Tape',
        desc=lambda t, n, q, r, y: f'{n} ({t}) {q} results: revenue {r}, {y} year on year. Estimates, revenue lines, margins and free cash flow from SEC filings.',
        h1=lambda t, q: f'{t} earnings brief: {q}',
        meta=lambda n, e, f: f'{n} | quarter ended {e} | filed with the SEC on {f}',
        mcap='Market cap', next='Next results', us_time=' (US date, Yahoo Finance)',
        pending=lambda q, a, s: f'⏳ The quarter ended {q} is out: adjusted EPS {a}' + (f' (estimate {s})' if s else '') + '. The full numbers follow once the company files its 10-Q/10-K with the SEC.',
        c1='Results vs estimates', c2='Growth', c3='Revenue lines', c4='Margins', c5='Cash flow: how long it lasts',
        actual='Actual', est='Estimate', diff='Difference', beat='Beat', miss='Miss', inline='In line',
        rev='Revenue', eps_adj='EPS (adjusted)', eps_gaap='GAAP diluted EPS', no_est='no estimate',
        est_note=lambda s: f'The revenue estimate is the analyst average Yahoo Finance showed on {s}. EPS actual and estimate are from Yahoo Finance (adjusted basis; may differ from GAAP).',
        est_note_eps='EPS actual and estimate are from Yahoo Finance (adjusted basis; may differ from GAAP).',
        yoy='YoY', qoq='QoQ', ni='Net income', q8='Revenue by quarter', growth_note='YoY = against the same quarter last year; QoQ = against the previous quarter.',
        seg_none="The company's SEC filing has no clear revenue breakdown (or the lines do not add up to the total), so this chapter is left out.",
        seg_year='The annual report (10-K) only gives full-year numbers for the revenue lines, so these are full-year figures.', share='Share', other='Other',
        gm='Gross margin', om='Operating margin', nm='Net margin', this_q='This qtr', last_q='Last qtr', last_y='Year ago', na='n/a',
        bank_note='Banks and financial companies have no gross profit; revenue is net of interest expense.',
        cash='Cash and short-term investments', debt='Debt (long-term debt + short-term borrowings)', net_cash='Net cash', net_debt='Net debt',
        ocf='Operating cash flow (quarter)', capex='Capital spending (quarter)', fcf='Free cash flow (quarter)', fcf_ttm='Free cash flow (last 4 quarters)',
        runway=lambda m: f'⚠️ Free cash flow over the last 4 quarters is negative. At that pace, cash and short-term investments last about {m} months.',
        runway_ok='✅ Free cash flow over the last 4 quarters is positive: the business does not live off its cash pile.',
        runway_na='Cash flow figures are incomplete, so this cannot be worked out yet.',
        runway_bank="A bank's cash flow mostly moves with deposits and loans, so 'how long the cash lasts' does not apply.",
        source=lambda f: f'Sources: SEC EDGAR (XBRL, filed {f}), Yahoo Finance. A summary of public numbers, not investment advice.',
        updated='Updated', back='Back to the latest earnings briefs', home='Home', stock='What the accounts say about this stock', all_briefs='Latest earnings briefs',
        link_row='📊 Latest earnings briefs', link_note='US stocks worth $50B+', bn=lambda v: fmt_en(v),
        nav='Site', lang_nav='Language', na_short='—',
    ),
}

CSS = """:root{--bg:#fbf6ec;--surface:#fffaf2;--ink:#3b2f24;--muted:#87776a;--line:#ece1cc;--accent:#a5672c;--accent-soft:#f8ecda;
--up:#1d7a45;--down:#b23a48;--f-display:"Noto Serif TC","Songti TC",serif;
--f-body:"Noto Sans TC","PingFang TC","Microsoft JhengHei",system-ui,sans-serif;--f-data:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace;color-scheme:light}
*{box-sizing:border-box}html{overflow-x:clip}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--f-body);font-size:16px;line-height:1.6;overflow-wrap:anywhere}
a{color:var(--accent)}.wrap{max-width:820px;margin:0 auto;padding:20px 16px 48px}
header{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px 16px;margin-bottom:18px}
.brand{font-family:var(--f-display);font-weight:700;font-size:20px;color:var(--ink);text-decoration:none}
.site-nav,.lang{display:flex;flex-wrap:wrap;gap:6px}
.site-nav a,.lang a{font-size:13px;font-weight:700;padding:5px 10px;border:1px solid var(--line);border-radius:999px;color:var(--ink);text-decoration:none;background:var(--surface)}
.lang a[aria-current]{color:var(--accent);border-color:var(--accent);background:var(--accent-soft)}
h1{font-family:var(--f-display);font-size:28px;line-height:1.3;margin:0 0 6px}
.meta{color:var(--muted);font-size:14px;margin:0 0 4px}.lead{margin:0 0 16px}
.note{margin:12px 0;padding:12px 14px;border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:0 12px 12px 0;background:var(--accent-soft);font-size:14px}
.ch{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:16px;margin:14px 0}
.ch h2{font-size:19px;margin:0 0 10px;display:flex;gap:10px;align-items:baseline}
.ch h2 .no{font-family:var(--f-data);color:var(--accent);font-size:15px}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%;font-size:14.5px}
th,td{padding:7px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left;white-space:normal;min-width:7.5em}
th{font-size:12.5px;color:var(--muted);font-weight:700}
.n{font-family:var(--f-data);font-variant-numeric:tabular-nums}
.up{color:var(--up);font-weight:700}.down{color:var(--down);font-weight:700}
.tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;font-weight:700;border:1px solid}
.tag.up{background:#e3f4ea;border-color:#9fd3b2}.tag.down{background:#fbe6e9;border-color:#e4a9b1}.tag.flat{color:var(--muted);border-color:var(--line)}
.small{font-size:12.5px;color:var(--muted);margin:8px 0 0}
.bars{display:flex;align-items:flex-end;gap:6px;height:150px;margin:6px 0 2px}
.bar{flex:1;min-width:0;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;height:100%}
.bar i{display:block;width:100%;background:var(--accent);border-radius:6px 6px 0 0;opacity:.75}
.bar.last i{opacity:1}
.bar b{font:600 10.5px var(--f-data);color:var(--ink);margin-bottom:2px;white-space:nowrap}
.bar small{font:500 10px var(--f-data);color:var(--muted);margin-top:3px;white-space:nowrap}
.seg{height:10px;border-radius:5px;background:var(--accent);display:block;min-width:2px}
.pill-row{display:flex;flex-wrap:wrap;gap:6px 10px;margin:6px 0}
.alpha a{display:inline-block;margin:0 8px 4px 0;font-family:var(--f-data);font-size:13.5px}
.site-foot{margin-top:22px;padding-top:14px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}
@media(max-width:480px){h1{font-size:23px}.wrap{padding:16px 14px 40px}th,td{padding:6px 5px;font-size:13.5px}.bar b{font-size:9px}.bar small{font-size:8.5px}}
"""


# ---------- number formatting ----------

def fmt_zh(v):
    if v is None:
        return '—'
    a = abs(v)
    if a >= 1e12:
        s = f'{v / 1e12:,.2f} 萬億'
    elif a >= 1e8:
        s = f'{v / 1e8:,.1f} 億' if a < 1e10 else f'{v / 1e8:,.0f} 億'
    elif a >= 1e4:
        s = f'{v / 1e4:,.0f} 萬'
    else:
        s = f'{v:,.0f}'
    return 'US$' + s


def fmt_en(v):
    if v is None:
        return '—'
    a = abs(v)
    if a >= 1e12:
        s = f'{v / 1e12:,.2f}T'
    elif a >= 1e9:
        s = f'{v / 1e9:,.2f}B' if a < 1e11 else f'{v / 1e9:,.1f}B'
    elif a >= 1e6:
        s = f'{v / 1e6:,.0f}M'
    else:
        s = f'{v:,.0f}'
    return ('-$' if v < 0 else '$') + s.lstrip('-')


def money(v, lang):
    return L[lang]['bn'](v)


def pct(a, b):
    """Change from b to a, or None."""
    if a is None or b is None or b == 0:
        return None
    return (a - b) / abs(b) * 100


def spct(x, digits=1):
    if x is None:
        return '—'
    return f'{x:+.{digits}f}%'


def cls(x):
    return '' if x is None else ('up' if x > 0 else 'down' if x < 0 else '')


def span_pct(x, digits=1):
    return f'<span class="n {cls(x)}">{spct(x, digits)}</span>'


def eps_s(v):
    return '—' if v is None else (f'-${abs(v):.2f}' if v < 0 else f'${v:.2f}')


def margin(a, b):
    return None if a is None or not b else a / b * 100


def verdict(act, est, lang):
    """Beat / miss tag: within 0.5% counts as in line."""
    d = pct(act, est)
    if d is None:
        return '', None
    if abs(d) < 0.5:
        return f'<span class="tag flat">{L[lang]["inline"]}</span>', d
    return (f'<span class="tag up">{L[lang]["beat"]}</span>' if d > 0 else f'<span class="tag down">{L[lang]["miss"]}</span>'), d


# ---------- page parts ----------

def shell(lang, title, desc, canon_path, body, alt_paths=None, ld=None):
    alt = ''.join(f'<link rel="alternate" hreflang="{LANGS[k]}" href="{SITE}{k}/{canon_path}">' for k in LANGS)
    switch = ''.join(f'<a href="/{k}/{canon_path}" hreflang="{LANGS[k]}"{" aria-current=\"page\"" if k == lang else ""}>{"中" if k == "zh" else "EN"}</a>' for k in LANGS)
    t = L[lang]
    ldj = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>' if ld else ''
    return f"""<!DOCTYPE html>
<html lang="{LANGS[lang]}">
<head>
{GA}
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="index,follow,max-image-preview:large">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<link rel="canonical" href="{SITE}{lang}/{canon_path}">
{alt}
<meta property="og:type" content="article"><meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{SITE}{lang}/{canon_path}"><meta property="og:image" content="{SITE}og/ig-{lang}.png">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="192x192" href="/assets/icon-192.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=Noto+Serif+TC:wght@700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>{CSS}</style>
{ldj}
</head>
<body>
<div class="wrap">
<header>
  <a class="brand" href="/{lang}/">The Crowd Tape</a>
  <nav class="site-nav" aria-label="{t['nav']}"><a href="/{lang}/earnings/">{t['all_briefs']}</a></nav>
  <nav class="lang" aria-label="{t['lang_nav']}">{switch}</nav>
</header>
<main>
{body}
</main>
<footer class="site-foot"><p><a href="/{lang}/">{t['home']}</a> · <a href="/{lang}/earnings/">{t['all_briefs']}</a> · <a href="/{lang}/support/">{'支持我們' if lang == 'zh' else 'Support us'}</a></p></footer>
</div>
</body>
</html>
"""


def ch(no, title, inner):
    return f'<section class="ch"><h2><span class="no">{no:02d}</span>{E(title)}</h2>{inner}</section>'


def table(head, rows):
    th = ''.join(f'<th>{h}</th>' for h in head)
    tr = ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>' for r in rows)
    return f'<div class="tw"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def by_end(co):
    return {q['end']: q for q in co['q']}


def year_ago(co, end):
    """The quarter about one year before `end`."""
    e = date.fromisoformat(end)
    for q in co['q']:
        if 350 <= (e - date.fromisoformat(q['end'])).days <= 380:
            return q
    return None


def prev_q(co, end):
    i = [q['end'] for q in co['q']].index(end)
    return co['q'][i - 1] if i > 0 else None


def chap1(co, lang):
    t, q, est = L[lang], co['q'][-1], co.get('est') or {}
    rows = []
    v, d = verdict(q['rev'], est.get('rev_est'), lang)
    rows.append([t['rev'], f'<span class="n">{money(q["rev"], lang)}</span>',
                 f'<span class="n">{money(est.get("rev_est"), lang)}</span>' if est.get('rev_est') else t['no_est'],
                 f'{span_pct(d)} {v}' if d is not None else '—'])
    v, d = verdict(est.get('eps_act'), est.get('eps_est'), lang)
    rows.append([t['eps_adj'], f'<span class="n">{eps_s(est.get("eps_act"))}</span>',
                 f'<span class="n">{eps_s(est.get("eps_est"))}</span>' if est.get('eps_est') is not None else t['no_est'],
                 f'{span_pct(d)} {v}' if d is not None else '—'])
    rows.append([t['eps_gaap'], f'<span class="n">{eps_s(q.get("eps"))}</span>', '—', '—'])
    note = t['est_note'](est['rev_est_seen']) if est.get('rev_est') else t['est_note_eps']
    return ch(1, t['c1'], table(['', t['actual'], t['est'], t['diff']], rows) + f'<p class="small">{E(note)}</p>')


def chap2(co, lang):
    t, q = L[lang], co['q'][-1]
    ya, pq = year_ago(co, q['end']), prev_q(co, q['end'])
    rows = []
    for name, k in ((t['rev'], 'rev'), (t['ni'], 'ni'), (t['eps_gaap'], 'eps')):
        cur = q.get(k)
        val = eps_s(cur) if k == 'eps' else money(cur, lang)
        rows.append([name, f'<span class="n">{val}</span>', span_pct(pct(cur, (ya or {}).get(k))), span_pct(pct(cur, (pq or {}).get(k)))])
    last8 = co['q'][-8:]
    top = max((x['rev'] for x in last8), default=0) or 1
    bars = []
    for x in last8:
        y = year_ago(co, x['end'])
        g = pct(x['rev'], (y or {}).get('rev'))
        h = max(3, round(x['rev'] / top * 100))
        lab = x['label'].split(' ')[1] + "'" + x['label'][4:6]  # FY2026 Q3 -> Q3'26
        bars.append(f'<div class="bar{" last" if x is last8[-1] else ""}"><b class="{cls(g)}">{spct(g, 0) if g is not None else ""}</b>'
                    f'<i style="height:{h}%"></i><small>{E(lab)}</small></div>')
    chart = (f'<p class="small" style="margin:12px 0 0">{E(t["q8"])}（{E(t["yoy"])}）</p>' if lang == 'zh' else
             f'<p class="small" style="margin:12px 0 0">{E(t["q8"])} ({E(t["yoy"])})</p>') + f'<div class="bars">{"".join(bars)}</div>'
    return ch(2, t['c2'], table(['', t['this_q'], t['yoy'], t['qoq']], rows) + chart + f'<p class="small">{E(t["growth_note"])}</p>')


def chap3(co, lang):
    t, seg = L[lang], co.get('seg')
    if not seg or seg.get('none') or not seg.get('rows'):
        return ch(3, t['c3'], f'<p class="small" style="margin:0">{E(t["seg_none"])}</p>')
    tot = sum(r['val'] for r in seg['rows']) or 1
    rows = []
    for r in seg['rows']:
        share = r['val'] / tot * 100
        name = t['other'] if r.get('other') else r['name']
        rows.append([f'{E(name)}<span class="seg" style="width:{max(2, round(share))}%"></span>',
                     f'<span class="n">{money(r["val"], lang)}</span>', f'<span class="n">{share:.0f}%</span>',
                     span_pct(pct(r['val'], r.get('prev')))])
    note = f'<p class="small">{E(t["seg_year"])}</p>' if seg.get('basis') == 'year' else ''
    return ch(3, t['c3'], table(['', t['rev'], t['share'], t['yoy']], rows) + note)


def chap4(co, lang):
    t, q = L[lang], co['q'][-1]
    ya, pq = year_ago(co, q['end']), prev_q(co, q['end'])
    rows = []
    for name, k in ((t['gm'], 'gp'), (t['om'], 'op'), (t['nm'], 'ni')):
        vals = [margin(x.get(k), x.get('rev')) if x else None for x in (q, pq, ya)]
        if vals[0] is None:
            rows.append([name, t['na'], '—', '—', '—'])
            continue
        ch_y = (vals[0] - vals[2]) if vals[2] is not None else None
        rows.append([name] + [f'<span class="n">{v:.1f}%</span>' if v is not None else '—' for v in vals]
                    + [f'<span class="n {cls(ch_y)}">{ch_y:+.1f} pp</span>' if ch_y is not None else '—'])
    note = f'<p class="small">{E(t["bank_note"])}</p>' if co.get('bank') else ''
    head = ['', t['this_q'], t['last_q'], t['last_y'], t['yoy']]
    return ch(4, t['c4'], table(head, rows) + note)


def ttm_fcf(co):
    last4 = co['q'][-4:]
    if len(last4) < 4 or any(x.get('fcf') is None for x in last4):
        return None
    return sum(x['fcf'] for x in last4)


def chap5(co, lang):
    t, q, bal = L[lang], co['q'][-1], co.get('bal') or {}
    liquid = None if bal.get('cash') is None else bal['cash'] + (bal.get('sti') or 0)
    debt = bal.get('debt')
    rows = [[t['cash'], f'<span class="n">{money(liquid, lang)}</span>'],
            [t['debt'], f'<span class="n">{money(debt, lang)}</span>']]
    if liquid is not None and debt is not None:
        net = liquid - debt
        rows.append([t['net_cash'] if net >= 0 else t['net_debt'], f'<span class="n {cls(net)}">{money(abs(net), lang)}</span>'])
    rows += [[t['ocf'], f'<span class="n">{money(q.get("ocf"), lang)}</span>'],
             [t['capex'], f'<span class="n">{money(q.get("capex"), lang)}</span>'],
             [t['fcf'], f'<span class="n {cls(q.get("fcf"))}">{money(q.get("fcf"), lang)}</span>']]
    ttm = ttm_fcf(co)
    rows.append([t['fcf_ttm'], f'<span class="n {cls(ttm)}">{money(ttm, lang)}</span>'])
    if co.get('bank'):
        msg = t['runway_bank']
    elif ttm is None or liquid is None:
        msg = t['runway_na']
    elif ttm >= 0:
        msg = t['runway_ok']
    else:
        msg = t['runway'](max(0, round(liquid / (-ttm / 12))))
    return ch(5, t['c5'], table(['', ''], rows) + f'<p class="note" style="margin-bottom:0">{E(msg)}</p>')


def headline(co, lang):
    q = co['q'][-1]
    ya = year_ago(co, q['end'])
    return money(q['rev'], lang), spct(pct(q['rev'], (ya or {}).get('rev')))


def brief_page(co, lang, stamp, has_stock):
    t, q, tk = L[lang], co['q'][-1], co['t']
    r, y = headline(co, lang)
    title = t['title'](tk, co['name'], q['label'])
    desc = t['desc'](tk, co['name'], q['label'], r, y)
    parts = [f'<h1>{E(t["h1"](tk, q["label"]))}</h1>',
             f'<p class="meta">{E(t["meta"](co["name"], q["end"], co["latest"].get("filed") or "—"))}</p>']
    info = []
    if co.get('mcap'):
        info.append(f'{t["mcap"]} <b class="n">{money(co["mcap"], lang)}</b>')
    today = datetime.now(HK).date().isoformat()
    if co.get('next') and co['next'] >= today:
        info.append(f'{t["next"]} <b class="n">{co["next"]}</b>{E(t["us_time"])}')
    if has_stock:
        info.append(f'<a href="/{lang}/stock/{tk}/">{E(t["stock"])} →</a>')
    if info:
        parts.append(f'<p class="meta pill-row">{" · ".join(info)}</p>')
    p = co.get('pending')
    if p:
        parts.append(f'<p class="note">{E(t["pending"](p["q"], eps_s(p["eps_act"]), eps_s(p["eps_est"]) if p.get("eps_est") is not None else ""))}</p>')
    parts += [chap1(co, lang), chap2(co, lang), chap3(co, lang), chap4(co, lang), chap5(co, lang)]
    parts.append(f'<p class="small">{E(t["source"](co["latest"].get("filed") or "—"))} {t["updated"]} {stamp} HKT</p>')
    parts.append(f'<p><a href="/{lang}/earnings/">← {E(t["back"])}</a></p>')
    ld = {'@context': 'https://schema.org', '@type': 'Article', 'headline': title[:110], 'description': desc,
          'inLanguage': LANGS[lang], 'dateModified': datetime.now(HK).isoformat(timespec='minutes'),
          'about': {'@type': 'Corporation', 'name': co['name'], 'tickerSymbol': tk},
          'publisher': {'@type': 'Organization', 'name': 'The Crowd Tape', 'url': SITE}}
    return shell(lang, title, desc, f'earnings/{tk}/', '\n'.join(parts), ld=ld)


def report_day(co):
    """The day the results came out: Yahoo's results date when it is on or after the quarter end, else the SEC filing day."""
    lr = co.get('last_report')
    end = co['latest']['end']
    if lr and lr > end and (date.fromisoformat(lr) - date.fromisoformat(end)).days <= 70:
        return lr
    return co['latest'].get('filed') or end


def list_page(cos, lang, stamp):
    t = L[lang]
    today = datetime.now(HK).date()
    recent = []
    for co in cos:
        rd = report_day(co)
        if (today - date.fromisoformat(rd)).days <= 30:
            recent.append((rd, co))
    recent.sort(key=lambda x: (x[0], x[1].get('mcap') or 0), reverse=True)
    rows = []
    for rd, co in recent:
        q = co['q'][-1]
        ya = year_ago(co, q['end'])
        est = co.get('est') or {}
        v, d = verdict(est.get('eps_act'), est.get('eps_est'), lang)
        rows.append([f'<a href="/{lang}/earnings/{co["t"]}/"><b>{co["t"]}</b></a> <small>{E(co["name"])}</small>',
                     f'<span class="n">{rd[5:]}</span>', E(q['label']), span_pct(pct(q['rev'], (ya or {}).get('rev'))), v or '—'])
    up = sorted(((co['next'], co) for co in cos if co.get('next') and 0 <= (date.fromisoformat(co['next']) - today).days <= 14),
                key=lambda x: (x[0], -(x[1].get('mcap') or 0)))
    up_rows = [[f'<a href="/{lang}/earnings/{co["t"]}/"><b>{co["t"]}</b></a> <small>{E(co["name"])}</small>',
                f'<span class="n">{nd[5:]}</span>', f'<span class="n">{money(co.get("mcap"), lang)}</span>'] for nd, co in up]
    alpha = ' '.join(f'<a href="/{lang}/earnings/{co["t"]}/">{co["t"]}</a>' for co in sorted(cos, key=lambda c: c['t']))
    body = [f'<h1>{E(t["list_h1"])}</h1>', f'<p class="lead">{E(t["list_lead"])}</p>',
            ch(1, t['recent'], table([t['th_co'], t['th_date'], t['th_q'], t['th_rev'], t['th_eps']], rows) if rows else f'<p class="small">{t["none"]}</p>'),
            ch(2, t['upcoming'], table([t['th_co'], t['th_date'], t['mcap']], up_rows) + f'<p class="small">{E(t["us_time"].strip(" （）()"))}</p>'
               if up_rows else f'<p class="small">{t["none"]}</p>'),
            ch(3, f'{t["all"]}（{len(cos)}）' if lang == 'zh' else f'{t["all"]} ({len(cos)})', f'<p class="alpha">{alpha}</p>'),
            f'<p class="small">{E(t["source"]("10-Q / 10-K"))} {t["updated"]} {stamp} HKT</p>']
    return shell(lang, t['list_title'], t['list_desc'], 'earnings/', '\n'.join(body))


# ---------- links, sitemap ----------

def link_row(lang):
    t = L[lang]
    return (f'{MARK}<nav id="earnings-link" class="wrap" aria-label="{E(t["all_briefs"])}" style="font-size:13.5px;line-height:1.8;padding:10px 16px 0">'
            f'<a href="/{lang}/earnings/"><b>{E(t["link_row"])}</b></a> <small style="color:var(--muted)">{E(t["link_note"])}</small></nav>{MARK}')


def add_home_links():
    foot = '<!-- stock-index -->'
    # master index.html is the source of /en/ too (tools/build_langs.py), so it never gets a link, only loses old ones
    s = open('index.html', encoding='utf-8').read()
    clean = re.sub(re.escape(MARK) + r'.*?' + re.escape(MARK), '', s, flags=re.S)
    if clean != s:
        open('index.html', 'w', encoding='utf-8').write(clean)
    for path, lang in (('zh/index.html', 'zh'), ('en/index.html', 'en')):
        if not os.path.exists(path):
            continue
        s = open(path, encoding='utf-8').read()
        s = re.sub(re.escape(MARK) + r'.*?' + re.escape(MARK), '', s, flags=re.S)
        if foot in s:
            s = s.replace(foot, link_row(lang) + foot, 1)
        elif '<footer class="wrap foot" id="foot">' in s:
            s = s.replace('<footer class="wrap foot" id="foot">', link_row(lang) + '<footer class="wrap foot" id="foot">', 1)
        else:
            notice(f'財報：{path} 搵唔到放連結嘅位', 'warning')
            continue
        open(path, 'w', encoding='utf-8').write(s)


def add_stock_links(tickers):
    n = 0
    for lang in LANGS:
        t = L[lang]
        for tk in tickers:
            path = f'{lang}/stock/{tk}/index.html'
            if not os.path.exists(path):
                continue
            s = open(path, encoding='utf-8').read()
            s = re.sub(re.escape(MARK) + r'.*?' + re.escape(MARK), '', s, flags=re.S)
            box = (f'{MARK}<nav class="wrap earnings-link" style="font-size:14px;padding:6px 16px 10px">'
                   f'<a href="/{lang}/earnings/{tk}/"><b>📊 {E(t["brief"])}：{tk}</b></a></nav>{MARK}' if lang == 'zh' else
                   f'{MARK}<nav class="wrap earnings-link" style="font-size:14px;padding:6px 16px 10px">'
                   f'<a href="/{lang}/earnings/{tk}/"><b>📊 {tk} {E(t["brief"].lower())}</b></a></nav>{MARK}')
            if '<footer' not in s:
                continue
            i = s.index('<footer')
            s = s[:i] + box + s[i:]
            open(path, 'w', encoding='utf-8').write(s)
            n += 1
    return n


def sitemap(tickers):
    path = 'sitemap.xml'
    if not os.path.exists(path):
        return
    sm = open(path, encoding='utf-8').read()
    sm = re.sub(r'\s*<url><loc>' + re.escape(SITE) + r'(?:zh|en|ko)/earnings/[^<]*</loc>.*?</url>', '', sm, flags=re.S)
    last = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    rows = []
    for sub in [''] + [f'{tk}/' for tk in tickers]:
        alt = ''.join(f'<xhtml:link rel="alternate" hreflang="{LANGS[k]}" href="{SITE}{k}/earnings/{sub}"/>' for k in LANGS)
        for k in LANGS:
            rows.append(f'\n  <url><loc>{SITE}{k}/earnings/{sub}</loc><lastmod>{last}</lastmod><changefreq>daily</changefreq>{alt}</url>')
    sm = sm.replace('</urlset>', ''.join(rows) + '\n</urlset>')
    open(path, 'w', encoding='utf-8').write(sm)


def load_briefs():
    cos = []
    if not os.path.isdir(CO_DIR):
        return cos
    uni = (read_json('data/earnings/universe.json', {}) or {}).get('companies') or {}
    for f in sorted(os.listdir(CO_DIR)):
        if not f.endswith('.json'):
            continue
        co = read_json(f'{CO_DIR}/{f}')
        if not co or not co.get('q') or co['t'] not in uni:
            continue
        if co['q'][-1].get('rev') is None:
            continue
        cos.append(co)
    return cos


def main():
    cos = load_briefs()
    if not cos:
        notice('財報頁：未有數據，今次唔整', 'warning')
        return
    stamp = datetime.now(HK).strftime('%Y-%m-%d %H:%M')
    keep = {co['t'] for co in cos}
    for lang in LANGS:
        base = f'{lang}/earnings'
        os.makedirs(base, exist_ok=True)
        for d_ in os.listdir(base):
            if os.path.isdir(f'{base}/{d_}') and d_ not in keep:
                shutil.rmtree(f'{base}/{d_}')
        for co in cos:
            has_stock = os.path.exists(f'{lang}/stock/{co["t"]}/index.html')
            os.makedirs(f'{base}/{co["t"]}', exist_ok=True)
            open(f'{base}/{co["t"]}/index.html', 'w', encoding='utf-8').write(brief_page(co, lang, stamp, has_stock))
        open(f'{base}/index.html', 'w', encoding='utf-8').write(list_page(cos, lang, stamp))
    # English pages must not carry Chinese (company names and revenue lines come from SEC, in English)
    han = re.compile(r'[一-鿿]')
    for co in cos[:400]:
        body = open(f'en/earnings/{co["t"]}/index.html', encoding='utf-8').read()
        body = re.sub(r'<nav class="lang".*?</nav>', '', body, flags=re.S)
        if han.search(body):
            notice(f'財報：en/earnings/{co["t"]} 有中文：{"".join(han.findall(body)[:10])}', 'warning')
            break
    links = add_stock_links(sorted(keep))
    add_home_links()
    sitemap(sorted(keep))
    notice(f'財報頁：{len(cos)} 間公司 × 2 個語言，個股頁連結 {links} 個')


if __name__ == '__main__':
    main()
