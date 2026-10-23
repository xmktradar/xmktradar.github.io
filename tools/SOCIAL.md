# Social post slots

`tools/share.py` writes `data/social-posts.json` on the daily social run. `social_actions` decides the branch. On a trading day, at or after `SOCIAL_HOUR` 07:00 HKT (or `SOCIAL_FORCE=1`, or a legacy file), `main()` rebuilds the weekday posts and then adds `top5`, Friday `weekly_thread`, `hot_stock`, `discussion` and `atomic_posts`. Saturday and Sunday, at or after the same hour, write `weekend` and `atomic_posts` only. They do not rebuild weekday posts, `top5`, the Friday thread, `social/index.html` or the feeds. 07:00 HKT is 08:00 KST, before the first atomic slot at 09:00 KST. A US-holiday weekday is not a weekend and does not run the weekday branch unless forced.

Numbers are copied from the files below. A missing count is skipped. An empty list is a translated "none today" line, not a filled-in row.

## `top5`

Today's five most bullish and five most bearish names. `tools/ranking.py` `rank_rows` orders each side by that side's account count (`bull` uses `nb`, `bear` uses `nr`) descending, then `n_posts` descending, then ticker ascending. At most five names a side. The same order is used for the text, the card, and the mp4 job, and for the carousel's joint bull and bear cards.

| Field | Source |
| --- | --- |
| `bull[].n` | `daily.bull[].nb` (accounts bullish) |
| `bear[].n` | `daily.bear[].nr` (accounts bearish) |
| `window` | `MM/DD HH:MM – HH:MM HKT`: start is `daily.from`, cutoff is the latest `rows[].ms` in daily bull/bear/split converted to HKT (never ISO `T`, never a fake 23:59). Falls back to the social-posts.json `window` end time. |
| `date` | The social run's HKT day |

```json
{
  "date": "2026-10-23",
  "made_hkt": "2026-10-23 07:18",
  "window": "10/23 00:00 – 09:55 HKT",
  "source": "data/writeup-input.json daily",
  "bull": [{"t": "RSP", "n": 2}],
  "bear": [{"t": "QQQ", "n": 4}],
  "images": {
    "zh": {
      "portrait": "https://thecrowdtape.com/og/top5-zh.png?v=2026-10-23",
      "square": "https://thecrowdtape.com/og/top5-zh-sq.png?v=2026-10-23"
    }
  },
  "format": "image_card",
  "video": {
    "zh": "https://thecrowdtape.com/og/top5-zh.mp4?v=2026-10-23"
  },
  "posts": {
    "zh": {"x": "", "instagram": "", "threads": "", "facebook": "", "has_link": {}, "first_comment": {}}
  }
}
```

`images`, `video` and `posts` have `zh`, `en`, and `ko`. Portrait is 1080×1350 (`og/top5-<lang>.png`, for X, Instagram, and Threads). Square is 1080×1080 (`og/top5-<lang>-sq.png`, for Facebook). `video.<lang>` points at `og/top5-<lang>.mp4` (1080×1920, about 12 seconds, silent), made by `tools/top5video.sh` from the portrait PNG. The update workflow runs that script after `top5card.js` when `ffmpeg` is on `PATH` and the PNG exists.

Headings use the real list length on each side (5 kept when 5):

- zh: `今日 X 大神共識：最看好 N 隻／最看淡 N 隻` (column `最看好 N 隻` / `最看淡 N 隻`)
- en: `Top X accounts consensus today: Top N bullish / Top N bearish`
- ko: `오늘 X 인플루언서 컨센서스: 강세 상위 N종목 / 약세 상위 N종목`

Each post also has the date, the data window (`10/23 00:00 – HH:MM HKT`), both lists with account counts, `SHORT[lang]['disc']`, and hashtags. Instagram is capped at 5 hashtags (language base tags first, at most 2 ticker tags). Links use `tools/utm.py` `tag_url(url, platform, 'top5')` (`utm_source` is `x`, `threads`, `instagram` or `facebook`, `utm_medium=social`, `utm_campaign=top5`) and that post's language (`/<lang>/stock/<T>/`).

- X: one link in the body, the first bull's stock page, or `/<lang>/` when there is no bull. `xlen` ≤ 280. Names that do not fit are dropped from the end of the longer list. The link stays on the lead bull. `has_link.x` is true when that URL is present.
- Instagram: no URLs and no `thecrowdtape.com`. Exactly one link-in-bio line (`連結在個人簡介` / `link in bio` / `프로필 링크`). `has_link.instagram` is false. Stock links stay on Facebook / Threads `first_comment`.
- Threads and Facebook: the body has no URL. The link moves to `first_comment.threads` (the lead bull, or `/<lang>/` when there is no bull) and `first_comment.facebook` (one line per listed ticker). `has_link.threads` is true. `has_link.facebook` is true when either side has a name. Threads is passed through `fit_threads` (≤ 500 Unicode code points).

Empty side copy: zh `今日暫無`, en `None today`, ko `오늘 없음`.

`share.py` writes `work/top5cards.json` (`sitedata.work()`). The update workflow, in **Share image and social posts**, runs `node tools/top5card.js` right after `tools/xcard.js`. The renderer is `tools/top5card.html` + `tools/top5card.js` (Playwright, `CHROME_PATH` the same way as `tools/xcard.js`, IBM Plex Mono and Noto Sans TC / KR). Published pictures are under `og/`, which the publish step already `git add`s.

## `weekly_thread`

Written in that same social run only when the HKT day is a Friday. Content is 本週共識變化.

```json
{
  "date": "2026-10-23",
  "range": {"from": "2026-10-17", "to": "2026-10-23"},
  "langs": {"en": ["post 1", "post 2"], "zh": [], "ko": []},
  "note": "where the counts and the joins come from"
}
```

| Piece | Source |
| --- | --- |
| `range.from` / `range.to` | `weekly.from` / `weekly.to` in `data/writeup-input.json` |
| Bull lines | `weekly.bull` order, count = `nb`. `bull_total` on post 1 when it is a number |
| Bear lines | `weekly.bear` order, count = `nr`. `bear_total` on post 1 when it is a number |
| Joins and drops | `data/consensus-history.json` `days[<date>].bull` and `.bear` ticker lists |

History days inside `weekly.from`–`weekly.to` are sorted. The first day and the last day are compared. A name on the last day's bull list but not the first day's is "joined bullish"; a name on the first but not the last is "left bullish". The same for bear. Days in between are not listed. If either endpoint does not store `bull` and `bear` as lists, the thread has no join/drop post and says so in `note`.

Posts, at most five, each `xlen` ≤ 280:

1. Heading (`本週共識變化` / `This week's consensus changes` / `이번 주 컨센서스 변화`) and the range.
2. Top bulls, when the list is not empty.
3. Top bears, when the list is not empty.
4. Changes, when history supports the comparison. No movement is the translated "no joins or drops" line.
5. Last post: that language's short disclaimer and `https://thecrowdtape.com/<lang>/` from `tag_url(..., 'x', 'weekly_thread')`. English is `/en/`, Chinese `/zh/`, Korean `/ko/`.

A list that does not fit in 280 keeps a prefix of the real names. `+N` is how many of those names were left off.

`langs.<lang>` is a list of strings. `tools/utm.py` tags each of those strings as X posts (`utm_source=x`, `utm_campaign=weekly_thread`). An older `posts.<lang>.{x|text}` shape is still tagged the same way.

## Shared fields

Every slot carries `format`: `image_card`, `carousel`, `text_question` or `poll`. A poll also has `poll.<lang> = {question, options}` with 2–4 options. `top5` is `image_card`. `hot_stock` is `carousel`. `discussion` is `poll`. Weekend angles use the formats in the table below. An atomic `number` is `text_question`, `stock` is `image_card`, `expert_view` is `carousel`.

Every body ends with `SHORT[lang]['disc']` (`⚠️ 唔構成投資建議` / `⚠️ Not investment advice` / `⚠️ 투자 조언 아님`) and a hashtag line: `#美股` / `#StockMarket` / `#미국주식`, plus `#TICKER` when the post names one ticker. Threads bodies are ≤ 500 code points (`fit_threads`). X bodies are ≤ 280 (`xlen`).

About half of Threads and Facebook copies have no link in the body. The index walks `zh`, `en`, `ko` and, within each language, `threads` then `facebook`. Even indexes get a link. The URL is not left in the body. It is stored on `first_comment`, with `SHORT[lang]['live']` (`最新數字 👉 ` / `Live numbers 👉 ` / `최신 수치 👉 `) in front, and `has_link` is true for that platform. Odd indexes set `has_link` false and omit that platform's comment. On `top5`, X keeps the link in the body; Instagram has no URL (`has_link.instagram` false, one link-in-bio line). Threads and Facebook still get `first_comment`. Atomic posts use one string, so `has_link` is a boolean on the flat zh-then-en-then-ko list (even indexes) and `first_comment` is a string tagged `utm_source=threads`. Every `.instagram` field is passed through `sanitize_instagram` (also from `utm.normalize_all`) so captions stay URL-free.

`utm_campaign` is the slot name: `hot_stock`, `discussion`, `weekend`. Atomic posts use `atomic`. The platform is the field name (`threads` or `facebook`). A `first_comment` object is tagged per key. A `first_comment` string uses `threads`.

Numbers in the no-repeat guard are the integers left after stripping URLs, ISO dates, `M/D`, `Month D`, `HH:MM` and years `19xx`/`20xx`. A ticker is a `$SYMBOL` that contains a letter. A full-body match (whitespace collapsed) across two different slots is a duplicate. Threads and Facebook of the same slot may share a body. `guard_slots` reports those problems. The builders drop a clashing `hot_stock` or `discussion`, drop a weekend item that clashes, and omit `weekend` if that leaves fewer than two posts. They omit `atomic_posts` when a body would copy another slot or when fewer than four points fit.

## `hot_stock`

Weekday only. One popular name from `daily.bull` / `daily.bear` / `daily.split`, the highest `nb+nr` then `n_posts`, that has at least one `rows[].acc` and `rows[].why`. The ticker must not be a top5 lead (`bull[0]`, `bear[0]`), the main post's first `$TICKER`, an `x_trilingual` ticker, the discussion ticker, or a `hot_stock` / `discussion` ticker from the previous 7 days (`data/social-history.json`). If none qualifies, the key is omitted.

```json
{
  "date": "2026-10-23",
  "format": "carousel",
  "ticker": "SPCX",
  "nb": 4,
  "nr": 3,
  "source": "data/writeup-input.json daily",
  "accounts": ["chamath"],
  "posts": {
    "zh": {
      "threads": "",
      "facebook": "",
      "has_link": {"threads": true, "facebook": false},
      "first_comment": {"threads": "最新數字 👉 https://thecrowdtape.com/zh/stock/SPCX/?utm_source=threads&utm_medium=social&utm_campaign=hot_stock"}
    }
  }
}
```

`posts` has `zh`, `en` and `ko`. `nb` / `nr` are copied when they are numbers. Up to three `why` lines are quoted, trimmed from the end only so the Threads body stays within 500, and attributed `@acc：` unless the handle is already in the line. Chinese keeps those lines verbatim. English and Korean use the fixed title, the real counts and the `@handles`. They do not translate `why`. The link is `https://thecrowdtape.com/<lang>/stock/<T>/` with campaign `hot_stock`.

## `discussion`

Weekday only. The next counted name (`nb` or `nr` is a number) that is not the hot-stock ticker and is not in the blocked set above. Omitted when none qualifies. `format` is `poll`.

```json
{
  "date": "2026-10-23",
  "format": "poll",
  "ticker": "SPY",
  "nb": 2,
  "nr": 1,
  "source": "data/writeup-input.json daily",
  "poll": {
    "zh": {"question": "你點睇 $SPY？", "options": ["看好", "看淡", "中性"]},
    "en": {"question": "What do you think of $SPY?", "options": ["Bullish", "Bearish", "Neutral"]},
    "ko": {"question": "$SPY 어떻게 보세요?", "options": ["강세", "약세", "중립"]}
  },
  "posts": {
    "en": {"threads": "", "facebook": "", "poll": {"question": "", "options": []}, "has_link": {}, "first_comment": {}}
  }
}
```

The body is the question, the real count line (`n` bullish / `n` bearish accounts; a missing count is skipped; `1` stays singular in English) and the disclaimer plus hashtags. The same `poll` object sits on the slot and on each language. The link campaign is `discussion`.

## `weekend`

Saturday and Sunday (HKT date). `build_weekend` returns at least two posts or the key is omitted. Source is `weekly` in `data/writeup-input.json`. Saturday leads with the bullish names, then the week's bull/bear totals. Sunday leads with the bearish names, then a poll on the strongest split that those posts have not already led with. Later angles fill in only when an earlier one has no numbers.

| Day | id | format | Content |
| --- | --- | --- | --- |
| Saturday | `weekend-sat-bulls` | `image_card` | `weekly.bull` order, count = `nb`, up to five |
| Saturday | `weekend-sat-totals` | `text_question` | `bull_total` and `bear_total` |
| Sunday | `weekend-sun-bears` | `carousel` | `weekly.bear` order, count = `nr`, up to five |
| Sunday | `weekend-sun-split_poll` | `poll` | one split row, options as in `discussion` |

```json
{
  "date": "2026-10-24",
  "source": "data/writeup-input.json weekly",
  "posts": [
    {
      "id": "weekend-sat-bulls",
      "format": "image_card",
      "ticker": "AMZN",
      "langs": {
        "zh": {"threads": "", "facebook": "", "has_link": {"threads": true, "facebook": false}, "first_comment": {}}
      }
    }
  ]
}
```

Each item has `langs.zh`, `langs.en` and `langs.ko`. A poll item also has `poll` and `langs.<lang>.poll`. Campaign is `weekend`. The home URL is used when the item has no ticker.

## `atomic_posts`

4 or 5 posts per language, including Saturdays and Sundays (15 items when five points fit, 12 when only four do). The array is all Chinese posts, then English, then Korean. Each item is one point. The same point shares `slot_kst` across languages.

| Field | Meaning |
| --- | --- |
| `id` | `<lang>-number-<daily\|weekly>-<key>`, `<lang>-stock-<T>` or `<lang>-expert-<T>` |
| `lang` | `zh`, `en` or `ko` |
| `slot_kst` | `09:00`, `11:30`, `14:00`, `17:00`, `20:00`, `22:30` (KST, one hour ahead of HKT), first N for N points |
| `format` | `text_question` (number), `image_card` (stock), `carousel` (expert view) |
| `point_type` | `number`, `stock` or `expert_view` |
| `ticker` | present for stock and expert view |
| `hook` | the one-line fact |
| `text` | body, disclaimer and hashtags |
| `hashtags` | the hashtag line |
| `has_link` | boolean |
| `first_comment` | present when `has_link` is true |

Points are chosen from `daily` then `weekly`: aggregate counts (`posts`, `accounts`, `originals`, `reposts`, `bull_views`, `bear_views`, `clear_accounts`, `bull_total`, `bear_total`, `split_total`), then a stock row, then an expert row. A number or ticker already used that day, including inside `hot_stock` quotes, is skipped. An expert `why` is shown only in Chinese, and only when it adds no extra number and no extra ticker. Otherwise the line is omitted. A number post links to `/<lang>/`. A stock or expert post links to `/<lang>/stock/<T>/`. Campaign is `atomic`.

## `data/social-history.json`

```json
{"2026-10-23": {"hot_stock": ["SPCX"], "discussion": ["SPY"], "top5": ["RSP", "QQQ"], "atomic": ["TSLA", "GOOG"]}}
```

`{date: {slot: [tickers]}}`. The weekday run records `hot_stock`, `discussion`, `top5` (the two leads) and `atomic`. The weekend run records `weekend` and `atomic`. Dates are trimmed to the newest 14. The 7-day block on `hot_stock` / `discussion` looks at earlier dates only, so rewriting today does not ban today's ticker. `SOCIAL_HISTORY` overrides the path. Tests pass `save=False` so they do not write the repo file.

