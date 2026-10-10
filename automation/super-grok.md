# SuperGrok 交摘要（2026-10-10 Tim 決定，同 README 第 3 步衝突時以本檔為準）

帖文摘要不再呼叫 xAI API。API credits 用完，而且以後尋找同翻譯都用 SuperGrok 訂閱做。

## 分工

1. **掰全文**：GitHub Actions 步驟 2 仍然用公開嘋 fxtwitter 抓 100 個追蹤帳號嘋新帖，放入 `data/pending-posts.json`。呢步唔使 API key，亦唔使 SuperGrok。SuperGrok 嘋 X 搜尋一次只返幾則，唔可以取代呢步，否則會漏回覆同長文。
2. **判斷同翻譯**：SuperGrok 每 4 小時讀 `data/pending-posts.json`，必須把入面每一個未交摘要的帖都寫完。唔可以每輪止係 40 則。有新市場想法就寫詳細摘要；純生活、玩笑、唔有市場內容亦都要交，摘要寫一句「沒有新的市場觀點。沒有提及個股。」中文用普通話書面語、繁體字，同時寫韓文 `ko_summary`。規則同 `automation/post-analysis-prompt.md`。內部可以每批大約 40 則寫，但係要一直做到清。
3. **交檔**：寫入 `data/super-grok-analysis.json`，格式係 `{ "updated_hkt": "...", "posts": { "<帖文 id>": {分析} } }`。每批完成就合併推上，唔好整份覆蓋掉上一次尚未上傳嘋 id。中途寫唔完就下一輪由剩低嘋繼續，唔可以丟掉。
4. **上傳網頁**：GitHub Actions「Update site」讀呢個檔，合併入網站，再發布。`tools/analyse_posts.py` 唔會再呼叫 xAI API。

唔好再開電腦上舊嘋 Grok bot。

## 5. 每日寫分析（香港時間 09:05，每日一次）

1. 讀 `data/writeup-input.json`：網頁自己計好嘅每日、每週（7 日）、每月（28 日）共識數字（`bull` 共同看好、`bear` 共同看淡、`split` 分歧、`top` 最多人講）。分析入面嘅數字只可以用呢個檔，唔准作。再讀網站 `index.html` 入面嘅帖做理由同引用。
2. 寫 `data/super-grok-writeups.json`，每日整份覆蓋一次：

```json
{
  "updated_hkt": "YYYY-MM-DD HH:MM",
  "zh": {
    "daily":   {"date": "今日香港日期", "win": {"from": "YYYY-MM-DDTHH:MM", "to": "YYYY-MM-DDTHH:MM"}, "brief": "<p>…</p>", "full": "<h5>共識</h5><p>…</p>", "html": "<h4>短摘要</h4><p>…</p>"},
    "weekly":  {同 daily 一樣嘅欄位},
    "monthly": {同 daily 一樣嘅欄位},
    "highlights": {"date": "今日", "range": "…", "stats_note": "…", "cards": [{"headline": "…", "theme": "…", "tone": "看好", "points": ["@帳號：…"], "tickers": ["NVDA"], "handles": ["帳號"], "source_note": "據 @… 貼文", "big": {"value": "5 個帳號", "label": "看好 $NVDA"}}]},
    "briefing": {"date": "今日", "html": "<h3>…</h3><p>…</p>"}
  },
  "en": {同 zh 一樣嘅結構，英文},
  "ko": {同 zh 一樣嘅結構，韓文}
}
```

- `win` 用 `writeup-input.json` 對應期間嘅 `from`、`to`；英文同韓文唔使寫 `win`，會自動跟中文。
- 內容結構同 `automation/README.md` 第 3 節第 7 步一樣：`brief` 一段講共識、分歧、最大變化同數據範圍；`full` 分「共識／共同看淡／分歧／其他值得留意」，每個論點附 `@帳號` 同原帖連結。重點卡 3 張，`tone` 只可以係 `看好`、`看淡`、`分歧`、`中性`。
- 中文用普通話書面語、繁體字；英文、韓文意思同中文一樣，數字一樣。全部唔用破折號。
- HTML 只可以用 `p h3 h4 h5 ul ol li strong em br a code`。連結只可以去 `#stock/<代號>`（加 `class="tk"`）或者 `https://x.com/...`，其他連結同標籤會被清走。
- 推上 `main` 之後網站自動更新。格式唔啱嘅部分會被跳過，寫喺 `data/site-status.json` 嘅 `writeups_rejected`。

## 6. 每日檢查（香港時間 10:05，每日一次）

讀 `data/site-status.json`（GitHub 每次更新都會寫）。任務結果設定用 email 通知 Tim。以下任何一樣成立，結果第一行寫「有問題」，再逐樣寫清楚數字：

- `generated_hkt` 早過而家 5 個鐘以上（網站停咗更新）。
- `waiting_for_summary` 大過 300，或者 `fetch_failed` 唔係空。
- `latest_writeups` 入面 `zh`、`en`、`ko` 嘅 `daily` 唔係今日或者昨日。
- `writeups_rejected` 唔係空。

全部正常就第一行寫「一切正常」。

要改程式或者版面先修得好嘅問題：開 PR（branch 名 `grok-fix-<日期>`），寫清楚改咗咩，等 Tim 講「合併」先生效。唔准直接改 `main` 上面嘅 `tools/`、`.github/`、`index.html`。資料檔（`data/super-grok-analysis.json`、`data/super-grok-writeups.json`）照舊直接推。

## 6a. 寫作語氣（帖文摘要同所有分析都適用，2026-10-10 Tim 要求）

要寫得似一個熟市場嘅朋友喺度同讀者傾偈，唔好似填表。

- 先講最重要嗰樣嘢同點解要留意，再講細節。唔好每段都用同一個開頭（例如「共識：」「本輪」）。
- 講清楚帳號點解咁睇：佢嘅理由、擔心乜、同其他人邊度唔同。用自己嘅說話轉述，唔好逐字照抄。
- 句子長短交替，可以用「不過」「反而」「值得留意嘅係」呢類轉折，令文章有起伏。
- 分歧要寫成對話感：「@A 覺得……，但 @B 擔心……」。
- 數字照用 `data/writeup-input.json`，但唔好一段塞晒所有數字，揀最有意思嘅兩三個講。
- 唔用「綜上所述」「總括而言」「值得注意的是」呢類套話，唔用破折號，唔加原帖冇嘅事實，唔做投資建議。
- **有目標價一定要寫出嚟**：帖文提到目標價、價位目標或者止蝕位，摘要同分析都要寫明代號、價位同邊個帳號講，例如「@A 將 $NVDA 目標價上調至 250 美元」。英文、韓文版本一樣要有。
- 閒聊帖照寫一句短摘要就得，唔使硬加分析。

## 7. 唔做

- 唔出社交媒體帖。
- 唔自己搜 X 帖代替 GitHub 抓帖。
- 唔加減追蹤帳號。
