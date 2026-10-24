# Social post slots

`tools/share.py` writes `data/social-posts.json` on the daily social run. `social_actions` decides the branch. `tools/intraday.py` adds the `intraday` key during US market hours (spec `kr` is stored as `ko`). On a trading day, at or after `SOCIAL_HOUR` 07:00 HKT (or `SOCIAL_FORCE=1`, or a legacy file), `main()` rebuilds the weekday posts and then adds `top5`, Friday `weekly_thread`, `hot_stock`, `discussion`, `three_lines`, `why_posts` and `atomic_posts`. Saturday and Sunday, at or after the same hour, write `weekend` and `atomic_posts` only. They do not rebuild weekday posts, `top5`, the Friday thread, `three_lines`, `why_posts`, `social/index.html` or the feeds. 07:00 HKT is 08:00 KST. `three_lines` is suggested at 08:30 KST, before the first shared slot at 09:00 KST. That rebuild keeps an existing `intraday` object when its `date` is the same day. A US-holiday weekday is not a weekend and does not run the weekday branch unless forced.

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

Every slot carries `format`: `image_card`, `carousel`, `text_question` or `poll`. A poll also has `poll.<lang> = {question, options}` with 2–4 options. `top5` is `image_card`. `hot_stock` and `why_posts` are `carousel`. `discussion` is `poll`. `three_lines` is `text_question`. Weekend angles use the formats in the table below. An atomic `number` is `text_question`, `stock` is `image_card`, `expert_view` is `carousel`.

Every body ends with `SHORT[lang]['disc']` (`⚠️ 唔構成投資建議` / `⚠️ Not investment advice` / `⚠️ 투자 조언 아님`) and a hashtag line: `#美股` / `#StockMarket` / `#미국주식`, plus `#TICKER` when the post names one ticker. Threads bodies are ≤ 500 code points (`fit_threads`). X bodies are ≤ 280 (`xlen`).

About half of Threads and Facebook copies have no link in the body. The index walks `zh`, `en`, `ko` and, within each language, `threads` then `facebook`. Even indexes get a link. The URL is not left in the body. It is stored on `first_comment`, with `SHORT[lang]['live']` (`最新數字 👉 ` / `Live numbers 👉 ` / `최신 수치 👉 `) in front, and `has_link` is true for that platform. Odd indexes set `has_link` false and omit that platform's comment. On `top5`, X keeps the link in the body; Instagram has no URL (`has_link.instagram` false, one link-in-bio line). Threads and Facebook still get `first_comment`. Atomic posts use one string, so `has_link` is a boolean on the flat zh-then-en-then-ko list (even indexes) and `first_comment` is a string tagged `utm_source=threads`. Every `.instagram` field is passed through `sanitize_instagram` (also from `utm.normalize_all`) so captions stay URL-free.

`utm_campaign` is the slot name: `hot_stock`, `discussion`, `weekend`, `three_lines`, `why`. Atomic posts use `atomic`. The platform is the field name (`x`, `threads`, `facebook` or `instagram`). A `first_comment` object is tagged per key. A `first_comment` string uses `threads`. `three_lines` and `why_posts` store the link on `{text, url}` (`url` is null when that copy has no link). Instagram never has a `url`.

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

Each item has `langs.zh`, `langs.en` and `langs.ko`. A poll item also has `poll` and `langs.<lang>.poll`. Campaign is `weekend`. The home URL is used when the item has no ticker. `date_kst` on the weekend object is the Asia/Seoul date of that Saturday or Sunday (the run is 07:00 HKT, 08:00 KST). A Saturday morning run is that Saturday.

## `three_lines`

Weekday only, in the same 07:00 HKT social run. Not written on Saturday or Sunday. One post: the homepage "today in 3 lines" block, in zh, en and ko (spec `kr` is `ko`).

The lines are the page's `RUX.threeLines` on the daily-tab rows. When `main()` can read the homepage dash (`tools/slim_pages.full_data`), the rows, the previous window and the sample are the same ones the daily tab uses (`dist`, `dailyWindow`, stance changes). Without that corpus, the fallback is `data/writeup-input.json` `daily.bull` / `bear` / `split` (`nb`, `nr`, `n_posts`). That fallback has no previous window, so it does not invent a consensus shift.

| Field | Meaning |
| --- | --- |
| `date` | The social run's HKT day |
| `date_kst` | Asia/Seoul date of `suggested_kst` (08:30) on that posting day |
| `generated_at` | ISO time in `+08:00` |
| `window` | `MM/DD HH:MM – HH:MM HKT`. Dash: 00:00 of the window's start day (or the timed start) through the latest valid post. Writeup fallback: the same cutoff rule as `top5` |
| `sample` | `{posts, accounts}`. Dash: valid posts in the window, and accounts with a non-folded post in the window. Writeup fallback: `daily.posts` and `daily.accounts` |
| `suggested_kst` | `08:30` |
| `format` | `text_question` |
| `source` | Which corpus the lines came from |
| `x` / `threads` / `facebook` | `{zh, en, ko: {text, url}}`. `url` is null when that copy has no link |
| `instagram` | `{zh, en, ko: {text}}`. No `url` |
| `has_link` | Per platform, per language |

Wording matches the daily tab (single spaces). zh `今日三句重點` / `共識變化最大` / `最多人討論` / `分歧最大`. en `Today in 3 lines` / `Biggest consensus shift` / `Most mentioned` / `Biggest disagreement`. ko `오늘의 3줄 요약` / `합의 변화 최대` / `최다 언급` / `의견 차이 최대`. A missing line is left out. If all three are missing and the sample or window is real, the body is the page's empty sentence for that language.

The consensus-shift line uses the i18n phrase for `對比昨日（今日至今）` once, with no outer parentheses around it: zh `淨看多比例 -100% → +75% 對比昨日（今日至今）`, en `net bullish -100% → +75% vs yesterday (today so far)`, ko `순강세 비율 -100% → +75% 어제 대비 (오늘 현재까지)`.

Every body includes the window and the sample, for example `10/23 00:00 – 09:55 HKT · 120 posts / 45 accounts` (zh `則貼文` / `個帳號`, ko `게시물` / `계정`). Counts are copied. A missing count is left out.

X is ≤ 280 by `xlen`. Threads is ≤ 500 by `fit_threads`. About half of the six X and Threads copies carry a link: zh and ko on X, en on Threads. Facebook always has the language home URL in the body and in `url`. Instagram has no URL, one link-in-bio line, and at most 5 hashtags. Links are `tag_url(url, platform, 'three_lines')` on `/<lang>/`.

## `why_posts`

Weekday only, same run. Not written on Saturday or Sunday. One object per hot name, at most 5. Hot names are `ranking.rank_rows` across `daily.bull` (`nb`), `daily.bear` (`nr`) and `daily.split` (the stronger of `nb` and `nr`), then `n_posts`, then ticker. A ticker is kept once. `side` is `split` when both counts are greater than 0, otherwise `bull` when `nb` ≥ `nr`, otherwise `bear`.

| Field | Meaning |
| --- | --- |
| `ticker`, `side` | The name and the side above |
| `bull`, `bear` | `nb` and `nr` when that number is on the row, including 0. Omitted when the row has no such number |
| `accounts` | `nb + nr` when at least one of them is a number. Not the length of the quote list |
| `window`, `sample` | The same window and sample as `three_lines` when that slot was built, otherwise the top5 window and `daily.posts` / `daily.accounts` |
| `bull_reasons`, `bear_reasons` | `[{acc, text}]`. Omitted when that side has none |
| `threads` | `{zh, en, ko: {text, url}}` |
| `x` | `{en: {text, url}}` only when the English body fits in 280 (`xlen`) |
| `suggested_kst` | One of `09:00`, `11:30`, `14:00`, `17:00`, `20:00`, `22:30`, earliest free slots |
| `date_kst` | On each list item: Asia/Seoul date of `suggested_kst` on that item's posting day. The list shape stays. Top-level `why_posts_date_kst` is the earliest of those |
| `format` | `carousel` |
| `has_link` | `{threads: {zh, en, ko}, x?: {en}}` |

Each language quotes that language's real summary, the same source as the homepage why-line. Chinese is `rows[].why` (the page's `zh_summary`). English is the row's `why_en` / `en_summary`, or the dash post with the same url: `en_summary`, then the original `text` when that summary is missing or still contains CJK Han. Korean is the row's `why_ko` / `ko_summary`, or the post's `ko_summary` (no English fallback). `/en/` and `/ko/` copy those fields into `zh_summary` before rendering the why-line (`build_langs.swap_data`). The quote is the sentence that names the ticker (`RUX.clauseFor`), with the leading `@handle` stripped once (`dedupe_handle`) and URLs removed. It is not translated and not invented. English and Korean text that still contains CJK Han outside a `$TICKER` or `#TICKER` is omitted. `rows[].s` picks the side. A bull-list or bear-list row with no `s` uses that list's side. A split row with no `s` is skipped. A side with no real summary in that language is omitted from that language; the counts line stays. A name with no reason in any language is omitted. `bull_reasons` and `bear_reasons` store the Chinese quotes. The post attributes the line to `@handle`.

`python3 tools/three_why.py --merge-into data/social-posts.json` recomputes `three_lines`, `why_posts` and the adjusted `atomic_posts`, and writes only those keys.

Each language states the account count (`accounts`, and `nb` / `nr` when present) and the window plus sample. Threads ≤ 500. About half of the Threads copies have a language stock link (`utm_campaign=why`, `/<lang>/stock/<T>/`); the link is on `url`, not in the body. English X is included only when it fits, and its link follows the same half rule. No Instagram.

`why_posts` replace atomic slots. Atomic posts for the same ticker are dropped. The two lists share the six KST times, why posts first, and the total per language stays in 4–6 when the writeup has enough unused facts. Nothing is invented to fill a gap. A why body that copies another slot, or a body already stored on an earlier day in `social-history.json` (`why_text`), is dropped.

## `atomic_posts`

4 or 5 posts per language, including Saturdays and Sundays (15 items when five points fit, 12 when only four do). The array is all Chinese posts, then English, then Korean. Each item is one point. The same point shares `slot_kst` across languages.

| Field | Meaning |
| --- | --- |
| `id` | `<lang>-number-<daily\|weekly>-<key>`, `<lang>-stock-<T>` or `<lang>-expert-<T>` |
| `lang` | `zh`, `en` or `ko` |
| `slot_kst` | `09:00`, `11:30`, `14:00`, `17:00`, `20:00`, `22:30` (KST, one hour ahead of HKT). On a weekday, `why_posts` take the earliest of these and atomic posts take the times that remain. On a weekend, the first N times, one per point |
| `date_kst` | Asia/Seoul date of `slot_kst` on the posting day. A Saturday HKT morning run uses that Saturday, not the weekday `date` |
| `format` | `text_question` (number), `image_card` (stock), `carousel` (expert view) |
| `point_type` | `number`, `stock` or `expert_view` |
| `ticker` | present for stock and expert view |
| `hook` | the one-line fact |
| `text` | body, disclaimer and hashtags |
| `hashtags` | the hashtag line |
| `has_link` | boolean |
| `first_comment` | present when `has_link` is true |

Points are chosen from `daily` then `weekly`: aggregate counts (`posts`, `accounts`, `originals`, `reposts`, `bull_views`, `bear_views`, `clear_accounts`, `bull_total`, `bear_total`, `split_total`), then a stock row, then an expert row. A number or ticker already used that day, including inside `hot_stock` quotes, is skipped. An expert `why` is shown only in Chinese, and only when it adds no extra number and no extra ticker. Otherwise the line is omitted. A number post links to `/<lang>/`. A stock or expert post links to `/<lang>/stock/<T>/`. Campaign is `atomic`.

## `date_kst`

`YYYY-MM-DD` in Asia/Seoul for the intended posting time. Existing `date` fields stay the HKT social day or the ET trade date. The value is computed from the suggested KST clock, or from the ET post time, plus that section's posting day.

The top-level key is the Seoul date of the earliest suggested post on the file's posting day (`date`). A weekday run at 07:05 HKT posts 08:30–22:30 KST that same calendar day. `why_posts` stays a list: each item gets `date_kst`, and top-level `why_posts_date_kst` is the earliest. Atomic posts are a list too, so each item carries `date_kst` (the weekend date when the weekend run wrote them). `python3 tools/share.py --backfill-date-kst` adds only these keys on an existing file. `three_why.py --merge-into` and `intraday.py --merge-from` set them on the keys they write.

## `data/social-history.json`

```json
{"2026-10-23": {"hot_stock": ["SPCX"], "discussion": ["SPY"], "top5": ["RSP", "QQQ"], "atomic": ["TSLA", "GOOG"]}}
```

`{date: {slot: [tickers]}}`. The weekday run records `hot_stock`, `discussion`, `top5` (the two leads), `atomic` and `why`. It also stores `why_text` and `three_lines_text` (normalized bodies from earlier days, so a later day can drop a repeated post). The weekend run records `weekend` and `atomic` and does not write `three_lines` or `why_posts`. The intraday run records `intraday`, the slot name, and `intraday_x` (normalized English X bodies, so a later slot does not repeat one). `--merge-from` appends that X text the same way. Dates are trimmed to the newest 14. The 7-day block on `hot_stock` / `discussion`, and the text block on `why` / `three_lines`, look at earlier dates only, so rewriting today does not ban today's ticker or today's text. `SOCIAL_HISTORY` overrides the path. Tests pass `save=False` so they do not write the repo file.

## `intraday`

Written by `python3 tools/intraday.py --slot <name|auto>` (workflow `.github/workflows/intraday.yml`). One slot per run. Merged under the top-level `intraday` key; other top-level keys stay as they are. Slots of the same ET trade date are kept; a new date resets `slots`. No Facebook. Spec `kr` = `ko`.

Schedule: `*/15 * * * 1-5` (every 15 minutes Mon–Fri UTC). The Guard step resolves America/New_York time and only continues within ±20 minutes of a generation time (5 min before each post: 09:40, 10:55, 12:10, 13:25, 14:40, 15:35 ET) on a NYSE trading day. A dispatch up to 10 minutes early or late still selects that slot. Off-window, weekend, and holiday runs exit immediately. Early-close days reject slots after 13:00 ET. This replaced twelve sparse EDT/EST crons that never fired after the workflow was added (GitHub often skips new sparse schedules). Manual runs: `gh workflow run intraday.yml -f slot=intraday_3` or `slot=force`.

The workflow concurrency group is `intraday` with `cancel-in-progress: false`. It is separate from `update-site.yml`'s `site-update` group. That job can run 60–90 minutes, and GitHub keeps only one pending run in a group, so sharing the group queues a slot past its window or cancels the older pending run.

Generation also writes `$WORK_DIR/intraday-slot.json` (`slot`, `date`, `generated_at`, `generated_hkt`, `entry`). Publish retries up to 6 times: `git stash -u`, `git fetch origin main`, `git reset --hard origin/main`, `python3 tools/intraday.py --merge-from "$WORK_DIR/intraday-slot.json"`, commit `data/social-posts.json` and `data/social-history.json`, then `git push origin HEAD:main`. The sleep between tries is `i * 8` seconds. `--merge-from` does not fetch quotes. It merges that one slot with the same date/reset rules and appends its English X text to `data/social-history.json`.

When `share.py` `main()` rebuilds weekday posts from scratch, it copies `intraday` from the file it read when `intraday.date` equals that social day. A different date is left off the new file. The weekend branch edits the existing object, so an `intraday` key already in it stays.

Post times are US/Eastern. HKT is ET+12 while EDT is in force, ET+13 after the first Sunday in November (from 2026-11-02). KST is one hour ahead of HKT, so an afternoon ET slot is the next Seoul calendar day. Generation is 5 minutes before each post. Early-close days (2026-11-27, 2026-12-24) skip slots after 13:00 ET. NYSE full closures are `tools/market_holidays.json`.

| Slot | ET | HKT summer (EDT, until 11/1) | HKT winter (EST, from 11/2) | Generate ET |
| --- | --- | --- | --- | --- |
| `intraday_open` | 09:45 | 21:45 | 22:45 | 09:40 |
| `intraday_1` | 11:00 | 23:00 | 00:00 next day | 10:55 |
| `intraday_2` | 12:15 | 00:15 next day | 01:15 next day | 12:10 |
| `intraday_3` | 13:30 | 01:30 next day | 02:30 next day | 13:25 |
| `intraday_4` | 14:45 | 02:45 next day | 03:45 next day | 14:40 |
| `intraday_close` | 15:40 | 03:40 next day | 04:40 next day | 15:35 |

`auto` picks the slot whose generation time is the nearest one within ±20 minutes of now in `America/New_York`, and only on a NYSE trading day. Generation windows do not overlap, so a dispatch from 10 minutes early to 10 minutes late still selects that slot. Weekends, full closures, and early-close slots after 13:00 ET do not match. `force` (workflow_dispatch slot value, or `--force`) bypasses the time guard and still writes. A named slot does not re-check the clock: Guard resolves `auto`, then the write step uses that name after the fetch.

Open is the market-open snapshot plus top consensus. Slots 1–4 are hot names plus bullish/bearish list changes since the previous snapshot (earlier slot that day, else `data/consensus-history.json` / yesterday). Close is a recap before the bell. Counts come from `data/writeup-input.json` daily bull/bear/split (`rank_rows`) or `work/stats.json` when the light scrape just ran. Tickers and counts are never invented.

Live quotes: Yahoo chart API (same `update_prices.chart` session) for SPY, QQQ, DIA and the hot tickers. If any index is missing, `quotes_ok` is false, `fallback` is true, and texts use site numbers only (no `%`). A ticker that failed to fetch is omitted from `%` lines. The as-of line uses the latest fetched `regularMarketTime` (`As of HH:MM ET (HH:MM HKT)`), not the slot post time. In that fallback the line is site data as of `data/writeup-input.json` `generated_hkt`.

```json
{
  "date": "2026-10-23",
  "date_kst": "2026-10-24",
  "generated_at": "2026-10-23T10:55:00-04:00",
  "generated_hkt": "2026-10-23 22:55",
  "slots": {
    "intraday_1": {
      "post_et": "11:00",
      "post_hkt": "23:00",
      "generated_at": "2026-10-23T10:55:00-04:00",
      "date": "2026-10-23",
      "date_kst": "2026-10-24",
      "quotes": {
        "SPY": {"price": 670.12, "prev_close": 668.0, "chg_pct": 0.32, "time": "2026-10-23T11:00:00-04:00"}
      },
      "quote_time": {"et": "2026-10-23T11:00:00-04:00", "hkt": "2026-10-23 23:00"},
      "quote_source": "Yahoo Finance",
      "quotes_ok": true,
      "fallback": false,
      "hot": [{"ticker": "NVDA", "chg_pct": 2.1, "bull": 8, "bear": 1, "accounts": ["leadbull"]}],
      "x": {"en": {"text": "Late morning · As of 11:00 ET (23:00 HKT)\n\n…", "url": "https://thecrowdtape.com/en/?utm_source=x&utm_medium=social&utm_campaign=intraday_1"}},
      "threads": {
        "zh": {"text": "…", "url": "https://thecrowdtape.com/zh/?utm_source=threads&utm_medium=social&utm_campaign=intraday_1"},
        "en": {"text": "…", "url": null},
        "ko": {"text": "…", "url": "https://thecrowdtape.com/ko/?utm_source=threads&utm_medium=social&utm_campaign=intraday_1"}
      },
      "has_link": {"x": true, "threads": {"zh": true, "en": false, "ko": true}}
    }
  }
}
```

| Field | Meaning |
| --- | --- |
| `date` | ET trade date |
| `date_kst` | Asia/Seoul date of that slot's ET post time. The intraday object uses the earliest slot present. `intraday_3` at 2026-10-23 13:30 ET is 2026-10-24. `intraday_1` in the example above is the only slot, so the object is 2026-10-24 as well |
| `generated_at` | ISO-8601 with offset |
| `generated_hkt` | `YYYY-MM-DD HH:MM` |
| `quotes` | `{TICKER: {price, prev_close, chg_pct, time}}` from Yahoo; omitted when that ticker failed |
| `quote_time` | latest `regularMarketTime`, ISO ET plus HKT string |
| `quotes_ok` / `fallback` | false / true when any of SPY, QQQ, DIA is missing |
| `hot` | site rows only: `ticker`, `chg_pct` (null if no quote), `bull`, `bear`, `accounts` |
| `x` | English only, `xlen` ≤ 280. Link `https://thecrowdtape.com/en/` with `utm_source=x&utm_medium=social&utm_campaign=<slot>` when the post includes a link. No zh/ko X. |
| `threads` | zh/en/ko, ≤ 500 code points (`fit_threads`). Language-matched `/zh/`, `/en/`, `/ko/` (spec `/` for Chinese is the `/zh/` helper). About half of slots include a link, alternating by slot index and flipping on date parity. |
| `has_link` | `x` boolean and `threads.{zh,en,ko}` booleans |

Texts state the quote time (`As of HH:MM ET (HH:MM HKT)` from the latest `regularMarketTime`), not the slot post time. With no quotes, texts say site data as of the writeup `generated_hkt`. Index `%` and hot `%` sit next to the site account counts (`NVDA +2.1%, 8 accounts bullish on site`). `utm.normalize_file` runs after each write.

