"""Last pass on every social caption the site writes (Tim, 2026-10-29: 「人性化點，不要再貼網站連結，唔好搞到好似詐騙」).

humanize(text, lang, kind) makes one caption follow the house rules:

  - no URLs at all, not even the bare domain or a Markdown link (pictures and videos keep their small
    "@thecrowdtape · thecrowdtape.com" footer; that is not in the caption)
  - no link, donate, newsletter, "link in bio" or "Follow" lines; one plain brand line instead, naming
    The Crowd Tape so people can search for it
  - no emoji bullets and no 👉 ☕ 🙏; at most 2 emoji in the whole caption
  - one short disclaimer line
  - at most 3 hashtags: one general tag plus at most 2 tickers, on the last line
  - zh is standard written Chinese (Mandarin), Traditional characters, not Cantonese

kind 'post' adds the brand and disclaimer lines, 'comment' (a first comment) only strips links and
returns '' when nothing is left, 'tags' (an Instagram Story hashtag line) only caps the hashtags.
It is idempotent: running it again on its own output changes nothing.

humanize_tree(obj) walks a whole posts object (data/social-posts.json, tutorial, earnings, macro)
and rewrites every caption field in place. tools/utm.py normalize_obj and tag_posts call it, and
share.sanitize_instagram ends with it, so every writer of those files goes through it.
"""
import hashlib
import re

LANGS = ('zh', 'en')

BRAND = {
    'zh': ('詳細數據在我們網站，搜尋 The Crowd Tape 就能找到。',
           '想看完整數據，搜尋 The Crowd Tape 就可以。',
           '更多細節都整理在 The Crowd Tape 網站上。'),
    'en': ('Full numbers are on our site. Just search The Crowd Tape.',
           'Want the full breakdown? Search The Crowd Tape.',
           'More detail is on The Crowd Tape website.'),
}
DISC = {'zh': '（僅整理公開資料，不構成投資建議）', 'en': '(Based on public info, not investment advice)'}
GENERAL_TAG = {'zh': '#美股', 'en': '#StockMarket'}
MAX_TAGS = 3
MAX_EMOJI = 2
X_MAX = 270  # X allows 280; the generators keep 10 spare
THREADS_MAX = 500

URL_RE = re.compile(r'https?://\S+|(?:www\.)?thecrowdtape\.com(?:/\S*)?', re.I)
MD_LINK_RE = re.compile(r'\[([^\]]*)\]\((?:https?://[^)]*)\)')
TAG_RE = re.compile(r'(?<![\w&])#[^\s#，。、！？,.!?()（）]+')
TICKER_TAG = re.compile(r'#[A-Z][A-Z0-9.]{0,5}')
EMOJI_RE = re.compile('[\U0001F000-\U0001FAFF☀-➿⬀-⯿⌚-⏿]'
                      '(?:️|⃣|[\U0001F3FB-\U0001F3FF]|‍[\U0001F000-\U0001FAFF☀-➿])*')
DROP_EMOJI = re.compile('[👉👇☕🙏🔔📬]️?')
LEAD_EMOJI = re.compile('^(?:' + EMOJI_RE.pattern + r'|\s)+')

# A line is dropped once its link is gone when what is left is only a call to action.
CTA_RE = re.compile(
    r'^(?:最新數字|最新数字|即時數字|試吓|試試|完整|全文|詳情|詳細|睇晒|看完整|更多|支持|鍾意|喜歡|捐|訂閱|電子報|免費電子報|'
    r'網站|個股頁|財報頁|大神點睇|連結|link|live numbers|support|subscribe|newsletter|try it|full|read|see|more|details|'
    r'all \d|the site|get the|buy us|enjoy it|website|stock page|\d+ 個主題)', re.I)
# Old fixed lines that the brand line replaces.
OLD_LINES = re.compile(
    r'連結在個人簡介|連結喺 ?bio|bio 連結|link in bio|^follow @thecrowdtape|^追蹤 ?@thecrowdtape|^@thecrowdtape|網站免費|the site is free|'
    r'支持我哋|支持我們|support the site|support us|buy us a coffee|paypal|訂閱免費電子報|free newsletter|'
    r'左右滑|向左滑|撳圖|點圖看|swipe|tap a picture', re.I)
DISC_RE = re.compile(r'投資建議|投资建议|investment advice|financial advice|投資有風險|do your own research|紙上交易|paper trading', re.I)

# Cantonese to standard written Chinese. Longer phrases first; single characters last.
ZH_PHRASES = [
    ('只係整理公開社交媒體貼文', '僅整理公開社交媒體貼文'), ('大神點睇', '大神怎麼看'), ('帳號點睇', '帳號怎麼看'),
    ('點睇', '怎麼看'), ('點諗', '怎麼想'), ('點解', '為什麼'), ('點樣', '怎樣'), ('點用', '怎麼用'),
    ('睇好', '看多'), ('睇淡', '看空'), ('看淡', '看空'), ('利淡', '利空'), ('好淡', '多空'), ('唱淡', '唱空'),
    ('差唔多', '差不多'), ('睇唔晒', '看不完'), ('唔得閒', '沒空'), ('唔使', '不用'), ('唔該', '請'),
    ('有冇', '有沒有'), ('係咪', '是不是'), ('係邊個', '是誰'), ('邊個', '誰'), ('邊隻', '哪一檔'), ('邊啲', '哪些'),
    ('邊幾個', '哪幾個'), ('邊邊', '哪一邊'), ('邊度', '哪裡'),
    ('喺度', '在這裡'), ('呢度', '這裡'), ('呢個', '這個'), ('呢條', '這條'), ('呢啲', '這些'), ('呢隻', '這檔'),
    ('呢集', '這集'), ('嗰個', '那個'), ('嗰啲', '那些'), ('嗰隻', '那檔'), ('嗰行', '那一行'), ('嗰幾分鐘', '那幾分鐘'),
    ('我哋', '我們'), ('佢哋', '他們'), ('你哋', '你們'),
    ('講緊', '在講'), ('做緊', '在做'), ('講咗', '說了'), ('一齊', '一起'), ('一撳', '一點'), ('撳落去', '點下去'),
    ('話你知', '告訴你'), ('話我知', '告訴我們'), ('留言話', '留言告訴'), ('鍾意', '喜歡'), ('好似', '好像'),
    ('好有', '很有'), ('好熱', '很熱'), ('好多', '很多'), ('淨係', '只'), ('只係', '只是'), ('都係', '都是'),
    ('睇晒', '看完'), ('列晒', '列出'), ('講晒', '講完'), ('全部喺', '全部在'), ('列埋', '一併列出'), ('數埋', '也算上'),
    ('試吓', '試試'), ('睇吓', '看看'), ('核實吓', '核實一下'), ('碌到', '滑到'), ('放大縮細', '放大縮小'),
    ('去返', '回到'), ('返頁頂', '回到頁頂'), ('彈出嚟', '彈出來'), ('日日', '每天'), ('每日', '每天'), ('今日', '今天'),
    ('琴日', '昨天'), ('尋日', '昨天'), ('聽日', '明天'), ('夜晚', '晚上'), ('啱啱', '剛剛'), ('冇人', '沒有人'),
    ('街貨', '市場'), ('企邊', '站哪'), ('企哪', '站哪'), ('咁樣', '這樣'), ('噉樣', '這樣'),
]
ZH_CHARS = [
    ('唔', '不'), ('嘅', '的'), ('喺', '在'), ('冇', '沒有'), ('咗', '了'), ('啲', '些'), ('嗰', '那'),
    ('佢', '他'), ('睇', '看'), ('撳', '點'), ('揀', '選'), ('搵', '找'), ('諗', '想'), ('仲', '還'), ('俾', '給'),
    ('畀', '給'), ('嚟', '來'), ('嘢', '東西'), ('咩', '什麼'), ('乜', '什麼'), ('啱', '合適'), ('隻', '檔'),
    ('咁', '這樣'), ('噉', '這樣'), ('吓', '一下'), ('㗎', ''), ('囉', ''), ('喎', ''), ('嘞', ''),
]
CANTONESE = re.compile('[唔嘅喺冇咗啲嗰哋佢睇撳揀搵諗俾畀嚟嘢咩乜啱㗎囉喎嘞噉]')


def zh_written(text):
    """Cantonese words in a zh caption to standard written Chinese (Traditional)."""
    if not isinstance(text, str) or not text:
        return text
    for a, b in ZH_PHRASES:
        text = text.replace(a, b)
    text = re.sub(r'(\d+) ?好 ?(\d+) ?淡', r'\1 多 \2 空', text)
    text = re.sub(r'(\d+) 好 vs (\d+) 淡', r'\1 多 vs \2 空', text)
    text = re.sub(r'(\d+) ?日(或以上|）|\))', r'\1 天\2', text)
    text = re.sub('係(?!數)', '是', text.replace('關係', '\0關\0').replace('體係', '體是')).replace('\0關\0', '關係')
    text = re.sub(r'呢(?=[一-鿿0-9 ])', '這', text)
    for a, b in ZH_CHARS:
        text = text.replace(a, b)
    return text


def guess_lang(text):
    return 'zh' if re.search('[一-鿿]', text or '') else 'en'


def xlen(t):
    """X length: CJK and emoji count 2 (no URLs are left to weigh)."""
    return sum(2 if ord(c) >= 0x1100 else 1 for c in t or '')


def _pick_brand(lang, seed):
    h = int(hashlib.md5((seed or '').encode('utf-8')).hexdigest(), 16)
    return BRAND[lang][h % len(BRAND[lang])]


def _cap_emoji(text):
    seen = 0

    def keep(m):
        nonlocal seen
        seen += 1
        return m.group(0) if seen <= MAX_EMOJI else ''
    return EMOJI_RE.sub(keep, text)


def pick_tags(found, lang):
    """One general tag (the first non-ticker one, else the language default) plus at most 2 tickers."""
    general, tickers = None, []
    for t in found:
        if TICKER_TAG.fullmatch(t):
            if t not in tickers:
                tickers.append(t)
        elif general is None:
            general = zh_written(t) if lang == 'zh' else t
    return ' '.join([general or GENERAL_TAG[lang]] + tickers[:MAX_TAGS - 1])


def _clean_line(ln, lang):
    """One body line without links or emoji bullets. None drops the line."""
    s = ln.strip()
    if not s:
        return ''
    if s in BRAND['zh'] or s in BRAND['en'] or s in DISC.values():
        return None
    if DISC_RE.search(s) and len(s) < 220:
        return None
    if OLD_LINES.search(s):
        return None
    had_link = bool(URL_RE.search(s) or MD_LINK_RE.search(s))
    s = re.sub('(\\d)\uFE0F?\u20E3', r'\\1.', s)  # 1️⃣ -> 1.
    s = MD_LINK_RE.sub(lambda m: '' if URL_RE.search(m.group(1)) or not m.group(1).strip() else m.group(1), s)
    s = URL_RE.sub('', s)
    s = DROP_EMOJI.sub('', s)
    s = LEAD_EMOJI.sub('', s)
    s = re.sub(r'[ \t]{2,}', ' ', s).strip()
    if had_link:
        s = re.sub(r'[\s:：→»>-]+$', '', s).strip()
        bare = re.sub(r'[\s\W_]+', '', s)
        if not bare or CTA_RE.match(s) or len(bare) <= 6:
            return None
    if not re.sub(r'[\s\W_]+', '', s):
        return None
    return s


def _body(text, lang):
    tags, out = [], []
    for ln in text.split('\n'):
        s = ln.strip()
        if s and re.fullmatch(r'(?:' + TAG_RE.pattern + r'\s*)+', s):
            tags += TAG_RE.findall(s)
            continue
        m = re.search(r'(?:\s+' + TAG_RE.pattern + r')+\s*$', ln)
        if m and not URL_RE.search(m.group(0)):
            tags += TAG_RE.findall(m.group(0))
            ln = ln[:m.start()]
        c = _clean_line(ln, lang)
        if c is None:
            continue
        if c == '' and (not out or out[-1] == ''):
            continue
        out.append(c)
    while out and out[-1] == '':
        out.pop()
    return out, tags


LOW_VALUE = re.compile(r'^(?:\d{4}-\d{2}-\d{2}$|數據範圍|Data window|[(（](?:共同看多＝|Joint bullish =))')


def _fit(body, ok):
    """Drop lines from the end, keeping the first line; the last kept line may be shortened with …
    when that keeps at least two thirds of it, otherwise it goes too."""
    body = list(body)

    def drop_last(b):
        b = b[:[i for i, x in enumerate(b) if x][-1]]
        while b and b[-1] == '':
            b.pop()
        return b
    while not ok(body):
        filled = [i for i, b in enumerate(body) if b]
        low = [i for i in filled[1:] if LOW_VALUE.match(body[i])]
        if low:  # dates, data windows and footnotes go before any list line
            body = [b for i, b in enumerate(body) if i != low[-1]]
            body = [b for i, b in enumerate(body) if b or (i and body[i - 1])]
            while body and body[-1] == '':
                body.pop()
            continue
        if len(filled) > 2:
            body = drop_last(body)
            continue
        if not filled:
            break
        last, line = filled[-1], body[filled[-1]]
        cut = line
        while len(cut) > 12 and (len(line) > 60 or len(filled) == 1):
            cut = cut[:-max(2, len(cut) // 12)].rstrip(' ，,、…')
            if ' ' in cut and not re.search('[\u4e00-\u9fff]', cut[-1:]):
                cut = cut.rsplit(' ', 1)[0]  # whole words in English
            cut = re.sub(r'\$[A-Z.]*$', '', cut).rstrip(' ，,、…') + '…'  # never half a ticker
            if ok(body[:last] + [cut] + body[last + 1:]):
                break
        fits = ok(body[:last] + [cut] + body[last + 1:])
        if fits and (len(cut) >= len(line) * 2 // 3 or len(filled) == 1):
            body[last] = cut
        elif len(filled) > 1:
            body = drop_last(body)
        else:
            body[last] = cut
            break
    return body


def _join(body, brand, disc, tags):
    return '\n'.join(body + ([''] if body else []) + [brand, disc, '', tags])


def humanize(text, lang=None, kind='post', platform=None):
    """One caption under the house rules. See the module docstring."""
    if not isinstance(text, str) or not text.strip():
        return text
    if re.fullmatch(r'https?://\S+', text.strip()) and _asset(text.strip()):
        return text  # a picture or video URL, not a caption
    lang = lang if lang in LANGS else guess_lang(text)
    if kind == 'tags':
        return pick_tags(TAG_RE.findall(text), lang)
    body, tags = _body(text, lang)
    if lang == 'zh':
        body = [zh_written(b) for b in body]
    body = _cap_emoji('\n'.join(body)).split('\n') if body else []
    body = [re.sub(r'[ \t]{2,}', ' ', b).strip() for b in body]
    if kind == 'comment':
        return '\n'.join(body).strip()
    tag_line = pick_tags(tags, lang)
    brand = _pick_brand(lang, body[0] if body else '')
    disc = DISC[lang]
    out = _join(body, brand, disc, tag_line)
    size, limit = (xlen, X_MAX) if platform == 'x' else ((len, THREADS_MAX) if platform == 'threads' else (None, None))
    if size:
        body = _fit(body, lambda b: size(_join(b, brand, disc, tag_line)) <= limit)
        out = _join(body, brand, disc, tag_line)
        if size(out) > limit:
            brand = min(BRAND[lang], key=len)
            body = _fit(body, lambda b: size(_join(b, brand, disc, tag_line)) <= limit)
            out = _join(body, brand, disc, tag_line)
        if platform == 'x' and xlen(out) > 280:  # hard ceiling: never emit an over-long X post
            body = _fit(body, lambda b: xlen(_join(b, brand, disc, tag_line)) <= limit)
            out = _join(body, brand, disc, tag_line)
            while xlen(out) > 280 and tag_line:
                tag_line = ' '.join(tag_line.split()[:-1])
                out = _join(body, brand, disc, tag_line)
            while xlen(out) > 280 and body:
                body = body[:-1]
                out = _join(body, brand, disc, tag_line)
    return out


CAPTION_KEYS = ('x', 'instagram', 'threads', 'facebook', 'facebook_cta', 'text', 'caption', 'body', 'hook', 'question', 'options')
SKIP_KEYS = {'url', 'urls', 'link', 'title', 'quotes', 'themes', 'slides', 'av', 'avatar', 'bull_reasons', 'bear_reasons'}


def _platform(key, parent_key):
    for k in (key, parent_key):
        if k in ('x', 'threads', 'instagram', 'facebook'):
            return k
    return None


PLATFORMS = ('x', 'threads', 'instagram', 'facebook')


def humanize_tree(obj, lang=None, key=None, parent_key=None, platform=None):
    """Rewrite every caption string under obj in place. Returns obj.
    platform is inherited from the nearest x/threads/instagram/facebook ancestor key,
    so x.en.text is still fitted to X's limit. x_trilingual (zh+en afterclose/premarket)
    is X-only, so it inherits platform='x' the same way."""
    if key in PLATFORMS:
        platform = key
    elif key == 'x_trilingual':
        platform = 'x'
    if isinstance(obj, dict):
        this = obj.get('lang') if obj.get('lang') in LANGS else lang
        for k, v in list(obj.items()):
            if k in SKIP_KEYS:
                continue
            lg = k if k in LANGS else this
            if isinstance(v, str):
                obj[k] = _humanize_field(v, lg, k, key, k if k in PLATFORMS else platform)
            elif isinstance(v, (dict, list)):
                humanize_tree(v, lg, k, key, platform)
        # Afterclose/premarket entries store xlen beside text; keep it in sync after X fit.
        if platform == 'x' and isinstance(obj.get('text'), str) and isinstance(obj.get('xlen'), (int, float)):
            obj['xlen'] = xlen(obj['text'])
        hl = obj.get('has_link')
        if isinstance(hl, bool):
            obj['has_link'] = False
        elif isinstance(hl, dict):
            for k in list(hl):
                hl[k] = {kk: False for kk in hl[k]} if isinstance(hl[k], dict) else False
        for k in ('url', 'link'):
            if isinstance(obj.get(k), str) and _caption_parent(key) and not _asset(obj[k]):
                obj[k] = ''
    elif isinstance(obj, list):
        last = max((i for i, v in enumerate(obj) if isinstance(v, str) and v.strip()), default=-1)
        for i, v in enumerate(obj):
            if isinstance(v, str):
                # An X thread is a list of posts: the brand and disclaimer go on the last one only.
                obj[i] = _humanize_field(v, lang, key, parent_key, platform) if i == last else \
                    _humanize_field(v, lang, 'first_comment', parent_key)
            elif isinstance(v, (dict, list)):
                humanize_tree(v, lang, key, parent_key, platform)
    return obj


def _asset(url):
    return bool(re.search(r'\.(png|jpe?g|webp|gif|mp4|xml)(\?|$)', url or '', re.I))


def _caption_parent(key):
    return key in ('x', 'threads', 'facebook', 'instagram') or key in LANGS


def _humanize_field(v, lang, key, parent_key, platform=None):
    if key == 'first_comment' or parent_key == 'first_comment':
        return humanize(v, lang, 'comment')
    if key in ('story', 'hashtags'):
        return humanize(v, lang, 'tags') if TAG_RE.search(v) else v
    if key in CAPTION_KEYS or key in LANGS or parent_key in ('x', 'threads', 'instagram', 'facebook') or \
            (isinstance(key, str) and key in ('posts', 'langs')):
        if '\n' not in v and not URL_RE.search(v) and len(v) < 60 and not TAG_RE.search(v):
            return humanize(v, lang, 'comment') if lang == 'zh' else v  # a short label: wording only
        return humanize(v, lang, 'post', platform or _platform(key, parent_key))
    return v
