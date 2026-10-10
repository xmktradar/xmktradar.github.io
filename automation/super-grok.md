# SuperGrok 交摘要（2026-10-10 Tim 決定，同 README 第 3 步衝突時以本檔為準）

帖文摘要不再呼叫 xAI API。API credits 用完，而且以後尋找同翻譯都用 SuperGrok 訂閱做。

## 分工

1. **掰全文**：GitHub Actions 步驟 2 仍然用公開嘋 fxtwitter 抓 100 個追蹤帳號嘋新帖，放入 `data/pending-posts.json`。呢步唔使 API key，亦唔使 SuperGrok。SuperGrok 嘋 X 搜尋一次只返幾則，唔可以取代呢步，否則會漏回覆同長文。
2. **判斷同翻譯**：SuperGrok 每 4 小時讀 `data/pending-posts.json`。有新市場想法先抽詳細摘要；純生活、玩笑、唔有市場內容就寫一句「沒有新的市場觀點。沒有提及個股。」中文用普通話書面語、繁體字，同時寫韓文 `ko_summary`。規則同 `automation/post-analysis-prompt.md`。
3. **交檔**：寫入 `data/super-grok-analysis.json`，格式係 `{ "updated_hkt": "...", "posts": { "<帖文 id>": {分析} } }`。要同舊檔合併，唔好整份覆蓋掉上一次尚未上傳嘋 id。
4. **上傳網頁**：GitHub Actions「Update site」讀呢個檔，合併入網站，再發布。`tools/analyse_posts.py` 唔會再呼叫 xAI API。

唔好再開電腦上舊嘋 Grok bot。
