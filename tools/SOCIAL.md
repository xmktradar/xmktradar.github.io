# Social post slots

`tools/share.py` writes `data/social-posts.json` on the daily social run (`main()` when `social` is true: first update at or after `SOCIAL_HOUR` 07:00 HKT on a trading day, or `SOCIAL_FORCE=1`). Two slots are added beside the existing daily posts.

Numbers are copied from the files below. A missing count is skipped. An empty list is a translated "none today" line, not a filled-in row.

## `top5`

Today's five most bullish and five most bearish names, in the order `data/writeup-input.json` `daily.bull` / `daily.bear` already uses.

| Field | Source |
| --- | --- |
| `bull[].n` | `daily.bull[].nb` (accounts bullish) |
| `bear[].n` | `daily.bear[].nr` (accounts bearish) |
| `window` | `daily.from` and `daily.to`, joined with ` – ` |
| `date` | The social run's HKT day |

```json
{
  "date": "2026-10-23",
  "made_hkt": "2026-10-23 07:18",
  "window": "2026-10-23T00:00 – 2026-10-23T23:59",
  "source": "data/writeup-input.json daily",
  "bull": [{"t": "RSP", "n": 2}],
  "bear": [{"t": "QQQ", "n": 4}],
  "images": {
    "zh": {
      "portrait": "https://thecrowdtape.com/og/top5-zh.png?v=2026-10-23",
      "square": "https://thecrowdtape.com/og/top5-zh-sq.png?v=2026-10-23"
    }
  },
  "posts": {
    "zh": {"x": "", "instagram": "", "threads": "", "facebook": ""}
  }
}
```

`images` and `posts` have `zh`, `en`, and `ko`. Portrait is 1080×1350 (`og/top5-<lang>.png`, for X, Instagram, and Threads). Square is 1080×1080 (`og/top5-<lang>-sq.png`, for Facebook).

Headings, copied exactly:

- zh: `今日 X 大神共識：最看好／最看淡 5 隻`
- en: `Top X accounts consensus today: 5 most bullish / bearish`
- ko: `오늘 X 인플루언서 컨센서스: 가장 강세 / 약세 5종목`

Each post also has the date, the data window, both lists with account counts, `SHORT[lang]['disc']`, and the usual hashtags (`#美股` / `#StockMarket` / `#미국주식`, plus tickers). Links use `tools/utm.py` `tag_url(url, platform, 'top5')` and the language home of that post (`/<lang>/stock/<T>/`).

- X: one link, the first bull's stock page, or `/<lang>/` when there is no bull. `xlen` ≤ 280. Names that do not fit are dropped from the end of the longer list. The link stays on the lead bull.
- Threads: the same single link, then `fit_threads` (≤ 500 Unicode code points, at most one link).
- Instagram and Facebook: one stock link per listed ticker (`utm_source` `ig` / `fb`).

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
