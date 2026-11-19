"""Paid weekly letter. Section order matches the Notion template.

Prices, win rates and outside indicators are left unwritten when this run has
not checked them. No section invents a number.
"""

HEADS = (
    '歷史準確度紀錄',
    '淨情緒方向變化',
    '本週異常',
    '誰在講',
    '與其他常見情緒指標',
    '情緒能維持多久',
    '敘事摘要',
    '下週觀察框架',
    '數字底（供核對，不是本週主體）',
    '方法論附註',
    '局限',
    '下期會回答',
    '免責與工具',
)
MIN_VOTES = 8


def _pct(part, whole):
    if not whole:
        return '數據不足'
    return f'{round(100 * part / whole)}%'


def _signed(n):
    return f'＋{n}' if n > 0 else str(n)


def _by_ticker(st):
    out = {}
    for key in ('bull', 'bear', 'split'):
        for group in (st or {}).get(key) or []:
            out.setdefault(group['t'], group)
    return out


def _votes(group):
    return int(group.get('nb') or 0) + int(group.get('nr') or 0)


def _aligned(st):
    rows = []
    for group in (st or {}).get('bull') or []:
        if group.get('nr') == 0 and _votes(group) >= MIN_VOTES:
            rows.append(group)
    for group in (st or {}).get('bear') or []:
        if group.get('nb') == 0 and _votes(group) >= MIN_VOTES:
            rows.append(group)
    rows.sort(key=lambda g: (-_votes(g), -g.get('n_posts', 0), g['t']))
    return rows[0] if rows else None


def _split(st):
    rows = [g for g in (st or {}).get('split') or [] if g.get('nb') and g.get('nr') and _votes(g) >= MIN_VOTES]
    rows.sort(key=lambda g: (-g.get('n_posts', 0), -min(g['nb'], g['nr']), g['t']))
    return rows[0] if rows else None


def _quote(group):
    want = 'bull' if group.get('nb', 0) >= group.get('nr', 0) else 'bear'
    rows = sorted(group.get('rows') or [], key=lambda r: r.get('ms') or 0, reverse=True)
    for row in rows:
        why = ' '.join(str(row.get('why') or '').split())
        if row.get('s') != want or not why or why.startswith('@') or why.count('@') >= 2:
            continue
        if len(why) > 80:
            why = why[:79].rstrip('，,。') + '…'
        return row.get('acc') or '', why
    return None


def _focus(st):
    picked = []
    seen = set()
    for group in (_aligned(st), _split(st)):
        if group and group['t'] not in seen:
            picked.append(group)
            seen.add(group['t'])
    rest = sorted(((st or {}).get('bull') or []) + ((st or {}).get('bear') or []), key=lambda g: (-_votes(g), g['t']))
    for group in rest:
        if group['t'] in seen:
            continue
        if len(picked) >= 3:
            break
        picked.append(group)
        seen.add(group['t'])
    return picked


def _gate(group):
    half = max(1, int(group.get('n_posts') or 0) // 2)
    line = f"${group['t']}：本期 {group['nb']} 好 / {group['nr']} 淡，提及 {group['n_posts']} 次。下期若提及少於 {half} 次，記為討論量下降。"
    if group.get('nr') == 0 and group.get('nb'):
        line += '若出現至少 1 個看淡，記為不再高度一致。'
    elif group.get('nr', 0) > group.get('nb', 0):
        line += '若看淡票仍多於看好票，記為偏淡維持；若看好票多於或等於看淡票，記為偏淡不再成立。'
    elif group.get('nb') and group.get('nr'):
        line += '若看淡票再增加至少 3 個，記為分歧繼續打開。'
    return line


def paid_letter(st, prior, d0, d1, n, tracked, theme_line=''):
    """Traditional Chinese letter. prior is last week's stats dict, or None."""
    bull_n = int(st.get('bull_views') or 0)
    bear_n = int(st.get('bear_views') or 0)
    posts = int(st.get('posts') or 0)
    labeled = bull_n + bear_n
    accounts = int(st.get('accounts') or 0)
    dates = f'{d0.month}月{d0.day}日至{d1.month}月{d1.day}日'
    aligned = _aligned(st)
    torn = _split(st)
    lines = [
        f'Crowd Tape 週報｜第 {n} 期｜{dates}',
        '',
        '你好，',
        '',
        f'本週一句話：整體 {bull_n} 好 / {bear_n} 淡。價格對照本期未核，不寫與 QQQ 或 SPY 同向或背離。',
        '',
    ]
    if aligned and torn and aligned['t'] != torn['t']:
        lines.append(
            f"本週最值得付費關注的觀察：方向最齊的是 ${aligned['t']}（{aligned['nb']} 好 / {aligned['nr']} 淡）；"
            f"討論量最高但意見最分裂的是 ${torn['t']}（{torn['nb']} 好 / {torn['nr']} 淡，{torn['n_posts']} 次提及）。"
            '少於 8 票的不列入這組對照。'
        )
    elif aligned:
        lines.append(f"本週最值得付費關注的觀察：方向最齊的是 ${aligned['t']}（{aligned['nb']} 好 / {aligned['nr']} 淡）。本期沒有達到 8 票的分裂名稱。")
    elif torn:
        lines.append(f"本週最值得付費關注的觀察：討論量最高但意見最分裂的是 ${torn['t']}（{torn['nb']} 好 / {torn['nr']} 淡，{torn['n_posts']} 次提及）。本期沒有達到 8 票的單邊名稱。")
    else:
        lines.append('本週最值得付費關注的觀察：沒有達到 8 票的單邊或分裂名稱。不另找股票填這一段。')
    lines += [
        '',
        f'本報已把官方追蹤的 {tracked} 個帳號之中，本週有發帖的 {accounts} 個帳號、{posts:,} 則帖，做好淡分類。'
        f'其中有標註好淡 {labeled:,} 則，約 {_pct(labeled, posts)}（{labeled:,}／{posts:,}）。'
        '這是已追蹤名單的公開討論統計，不是全部市場，也不是只挑選部分帖文；尚未做影響力加權或帳號分散度。',
        '',
        f'以下只反映已追蹤帳號在 {dates}（美東）的公開討論，並與上一期的點數對照。觀察與對照不是買賣訊號，也不構成投資建議。',
        '',
        '歷史準確度紀錄',
        '這是以後每期的固定位置。口徑是整體好淡方向，對當週 QQQ 與 SPY（上週五收市對本週五收市）。'
        '本期未核對這兩個收市價，不報勝率，也不倒推未核期數。',
        '',
        '淨情緒方向變化',
    ]
    net = bull_n - bear_n
    if prior and prior.get('posts'):
        pnet = int(prior.get('bull_views') or 0) - int(prior.get('bear_views') or 0)
        lines.append(
            f"上一期淨值 {_signed(pnet)}（{int(prior.get('bull_views') or 0)} 好 / {int(prior.get('bear_views') or 0)} 淡），"
            f"本期 {_signed(net)}（{bull_n} 好 / {bear_n} 淡）。"
            f"帳號由 {int(prior.get('accounts') or 0)} 個變為 {accounts} 個，帖由 {int(prior.get('posts') or 0):,} 則變為 {posts:,} 則。"
            '樣本大小不同，不宜直接理解成市場突然轉強或轉弱。'
        )
    else:
        lines.append(f'本期淨值 {_signed(net)}（{bull_n} 好 / {bear_n} 淡）。上一期點數本期未取出，不把上期淨值寫成 0。')
    lines += ['', '本週異常']
    prior_map = _by_ticker(prior)
    focus = _focus(st)
    if not focus:
        lines.append('本期沒有可寫的名稱。')
    for group in focus:
        old = prior_map.get(group['t'])
        if old:
            change = f"上一期 {old['nb']} 好 / {old['nr']} 淡，提及 {old['n_posts']} 次。"
        else:
            change = '上一期未進入前列，不把上期淨值寫成 0。'
        small = ''
        if _votes(group) < MIN_VOTES:
            small = '票數少於 8，不宜過讀。'
        lines.append(
            f"${group['t']}：本期 {group['nb']} 好 / {group['nr']} 淡，提及 {group['n_posts']} 次。{change}"
            f'價格對照本期未核，不寫同向或背離。{small}'
        )
    lines += [
        '',
        '誰在講',
        '本期尚未做帳戶類型標記，也未做粉絲分桶，不能寫看淡或多方來自哪一類帳號。個股好淡是帳號最新立場，帳號等權，未做影響力加權。',
        '',
        '與其他常見情緒指標',
        '本期未獨立核對散戶調查或期權討論，不寫同向或背離。',
        '',
        '情緒能維持多久',
    ]
    held = None
    for group in focus:
        old = prior_map.get(group['t'])
        if old and (old.get('nb') == 0 or old.get('nr') == 0) and _votes(old) >= MIN_VOTES:
            held = (old, group)
            break
    if held:
        old, group = held
        lines.append(
            f"上期 ${old['t']} 為 {old['nb']} 好 / {old['nr']} 淡、提及 {old['n_posts']} 次；"
            f"本期 {group['nb']} 好 / {group['nr']} 淡、提及 {group['n_posts']} 次。"
            '只是一筆已能對上的觀察，不寫成慣例或預測。'
        )
    else:
        lines.append('上一期沒有可對上的極端單邊，本期不倒推「極端之後討論通常會下降」。')
    lines += [
        '',
        '敘事摘要',
        '本期未提供理由分類次數，不估計各理由出現幾次，也不自行歸類。下面只附已有的中文摘要；沒有摘要就不引用。',
    ]
    quoted = False
    for group in focus:
        found = _quote(group)
        if not found:
            continue
        quoted = True
        lines.append(f"${group['t']}：@{found[0]}：{found[1]}")
    if theme_line:
        lines.append(theme_line + '本期未核對主題相符的引文，只報統計。')
    if not quoted and not theme_line:
        lines.append('本期沒有可引用的中文摘要。')
    gates = [_gate(g) for g in focus if _votes(g) >= MIN_VOTES][:3]
    lines += [
        '',
        '下週觀察框架',
        '這節追蹤本期寫過的名稱，不另開一組新訊號。下列門檻用來標記情緒有沒有轉變，不是已驗證法則，也不是買賣訊號。',
    ]
    if gates:
        lines.extend(gates)
    else:
        lines.append('本期沒有達到 8 票的名稱，不另立門檻。')
    lines += [
        '',
        '數字底（供核對，不是本週主體）',
        '討論量是關注度，好淡比是方向一致性，提及多並不等於看多。',
        f"整體（帖）｜{bull_n} 好｜{bear_n} 淡｜淨值 {_signed(net)}｜{posts:,} 則帖｜有標註 {_pct(labeled, posts)}",
    ]
    shown = set()
    for group in focus:
        if group['t'] in shown:
            continue
        shown.add(group['t'])
        cover = _pct(_votes(group), group.get('n_posts') or 0)
        lines.append(
            f"${group['t']}｜{group['nb']} 好｜{group['nr']} 淡｜淨值 {_signed(group['nb'] - group['nr'])}｜提及 {group['n_posts']}｜覆蓋率 {cover}"
        )
    lines += [
        '',
        '方法論附註',
        f"官方追蹤 {tracked} 個帳號。{accounts} 是當週有帖被收入的帳號，不是名單縮減。"
        f"原創 {int(st.get('originals') or 0):,} 則，轉發 {int(st.get('reposts') or 0):,} 則，未再拆好淡。"
        '目前只計有沒有標好淡，未分強烈或一般。未做帳戶類型標記，也未做粉絲分桶。',
        '',
        '局限',
        '這是公開討論計數，不是資金流向。高度一致不等於正確。請配合價格、成交量與基本面一起看，不要單獨作為買賣依據。',
        '',
        '下期會回答',
    ]
    if gates:
        asked = 0
        for group in focus:
            if _votes(group) < MIN_VOTES:
                continue
            half = max(1, int(group.get('n_posts') or 0) // 2)
            lines.append(f"${group['t']} 的提及會否少於 {half} 次？本期的好淡方向會否仍然成立？")
            asked += 1
            if asked >= 3:
                break
    else:
        lines.append('本期沒有立下門檻，下期不回答未立的問題。')
    lines += [
        '',
        '免責與工具',
        'Crowd Tape 整理已追蹤帳號的公開討論。統計只反映當時的觀點分佈。投資涉及風險，請自行判斷。',
        '網站：https://thecrowdtape.com/',
        '工具頁：https://thecrowdtape.com/tools/',
        '如需取消訂閱，請使用郵件底部的連結。',
        'Unsubscribe: {{{RESEND_UNSUBSCRIBE_URL}}}',
        '',
    ]
    return '\n'.join(lines)
