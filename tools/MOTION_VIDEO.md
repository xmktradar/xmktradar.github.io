# 輪播圖動態片：規格、任務、驗收清單

> 2026-10-24，Tim 喺「寫 30 秒宣傳片腳本」thread 揀好：
> ① GitHub 每日自動整（唔用 Grok 寫或者畫）；② 字同卡片都會郁（B）；③ 片冇聲，IG／FB 由 Grok bot 喺 app 加音樂；④ 只係 12:30 今日快照出片。
> 畫面設計跟 本檔第五節。

---

## 一、規格

### 要解決咩問題
每日輪播帖只係靜態圖。IG 同 Facebook 而家主力推 Reels（短片），靜態帖觸及少。網站每日已經自動畫好 4 張輪播圖，但冇片可以發。

### 成功係咩樣
1. 美股交易日，12:30「今日快照」輪播圖畫好之後，同一次網站更新順手出 **3 條動態片**（中、英、韓各一條）。
2. 每條片：**1080×1920 直片、約 16 秒、mp4、冇聲**，IG／FB Reels 直接用得。
3. 片入面係同日 4 張輪播圖嘅內容，**字同數字一隻都唔改**，只係加動作：
   - 每張圖由右向左掃入，停留時慢慢放大；
   - 第 1 張：日期貼紙彈入、大代號「砸」落位、帳號數由 0 跳上去、好淡數逐個彈出、引言框滑入；
   - 第 2 至 4 張：股票卡／區塊逐張彈入，走勢線由左畫到右；
   - 最後「Follow @thecrowdtape」框彈一下。
   - 上下多出嘅位用同款漫畫背景填滿，頂有 logo，底有 thecrowdtape.com；「⚠️ 唔構成投資建議」全片都喺度。
4. `data/social-posts.json` 嘅 `slots.1230` 多一格 `video`（每個語言一條片網址），`/social/` 頁 12:30 嗰格可以直接睇同下載條片。
5. Grok bot 角色 ① 喺原本 12:30／13:00／13:30 例行程序，發完 Facebook 多圖帖之後，**再發 IG Reels 同 FB Reels**：用 `slots.1230.video.<語言>`，文字用同一時段嘅 IG／Facebook 文字；喺 app 音樂庫揀一首輕快、冇歌詞嘅純音樂（同 Story 一樣，同上一次唔同）。唔開新例行程序。
6. 片同輪播圖一樣**保留 2 日**，之後自動刪。
7. 出唔到片（例如程式出錯）：輪播圖同其他帖照出照發，唔會令網站更新失敗；`video` 嗰格冇內容，Grok bot 就跳過 Reels，喺完成 email 講「冇片」。
8. 以後想擴大到 16:30／20:30，只係改一個設定（出片時段清單），唔使改程式。

### 明確唔做
- 唔配音樂、唔加旁白、唔用 AI 配音。
- 唔改輪播圖本身嘅設計、字或者數字；唔用 Grok Imagine 重畫。
- 唔做 16:30、20:30、週末教學、星期六宏觀帖嘅片。
- X、Threads 唔發片（照舊發 4 張圖）。
- 唔用角色。
- 片唔放喺網站主頁或者個股頁（唔影響網站載入速度）。

---

## 二、任務（每項可以獨立驗收）

| # | 任務 | 完成後點檢驗 | 依賴 |
|---|---|---|---|
| **V1** | 畫圖網頁加「動畫模式」：同一個輪播網頁，每個元素按時間出場（掃入、砸落、跳數、彈入、畫線），可以停喺任何一格時間。唔開動畫模式時，畫出嚟嘅靜態圖同而家一模一樣。 | 靜態圖同改之前逐點比較一樣；喺瀏覽器拉時間軸睇到每個動作 | — |
| **V2** | 逐格錄製 + 砌片：用 V1 逐格影相（24 fps），加上下背景、logo、網址、免責，用 ffmpeg 砌成 1080×1920 mp4（約 16 秒、冇聲）。 | 本機用 10/23 數據出到中英韓 3 條片，Tim 睇樣片 | V1 |
| **V3** | 接入每日更新：12:30 時段寫好之後先出片；寫入 `slots.1230.video`；出片時段做成一個設定；出錯只出警告唔令更新失敗；片 2 日後刪除。 | 一次真實「Update site」跑完：網站有 3 條片、`social-posts.json` 有 `video`；故意令出片失敗，更新照樣成功 | V2 |
| **V4** | `/social/` 頁 12:30 嗰格加片（可播放、可下載）。 | 打開 thecrowdtape.com/social/ 睇到同下載到 3 條片 | V3 |
| **V5** | Grok bot 手冊：第 7 節 12:30／13:00／13:30 三個例行程序加「IG Reels + FB Reels」步驟（加音樂、冇片就跳過並 email）；`bot-schedules.md` 加時間；寫一份只有改動部分嘅更新檔俾 Tim 轉交。 | Tim 收到更新檔；Grok bot 改好 3 個例行程序 | V3（要知道 `video` 嘅確實位置） |
| **V6** | 測試：自動測試檢查 `video` 格式、只喺設定時段出片、失敗唔拖累更新、舊片會刪。 | GitHub「Build check」綠色 | V3 |

先後次序：V1 → V2 → V3 →（V4、V5、V6 可以同時做）。

---

## 三、驗收 checklist

- [ ] V1 靜態輪播圖同改之前一樣（冇走位、冇少字）
- [ ] V1 動畫模式每個動作都出現：掃入、慢推鏡、砸落代號、跳數、彈入卡片、畫走勢線、Follow 框彈一下
- [ ] V2 樣片：1080×1920、約 16 秒、冇聲、mp4，喺 iPhone 播到
- [ ] V2 樣片入面嘅字同數字同當日 4 張輪播圖完全一樣
- [ ] V2 頂有 logo、底有 thecrowdtape.com、全片有「唔構成投資建議」
- [ ] V2 中、英、韓 3 條都啱語言
- [ ] V3 交易日 12:30 時段出咗 3 條片，`slots.1230.video` 有 3 個網址
- [ ] V3 16:30、20:30、週末都冇出片
- [ ] V3 出片失敗時，網站更新同輪播帖照常
- [ ] V3 2 日前嘅片已經自動刪除
- [ ] V3 網站每次更新時間冇明顯變慢（12:30 嗰次多唔超過約 1 分鐘）
- [ ] V4 /social/ 頁睇到、播到、下載到 3 條片
- [ ] V5 Tim 收到手冊改動部分；Grok bot 3 個例行程序已改
- [ ] V5 第一個交易日：IG Reels、FB Reels 中英韓都發咗，有音樂
- [ ] V6 自動測試全部通過

---

## 四、做法提示（俾 Grok Build；必須遵守）

**唔好郁嘅嘢**
- 主頁結構同 build contract：唔好改 `index.html`、`tools/check_contract.py` 檢查嘅任何嘢。每個 PR 都要「Build check」綠色先合併。
- 唔加動畫模式時，`tools/carousel.html` 畫出嚟嘅 4 張 jpg 要同而家一模一樣（V1 驗收）。
- 出片步驟唔可以令「Update site」失敗。

**現有程式（照住呢個模式做）**
- `tools/carousel.py` 寫 `work/carousel.json`（`jobs[]`：`slot`、`theme`、`lang`、`date`、`slides`、`files`、`fb`）同 `data/social-posts.json` 嘅 `slots`。
- `tools/carousel.js` 用 Playwright 開 `tools/carousel.html`，`render(lang, theme, date, page, slide)` 畫每張圖，影成 `og/c/<day>-<slot>-<lang>-<n>.jpg`；結尾刪走尋日之前嘅 `og/c/` 檔（按檔名開頭日期），所以片放喺 `og/c/` 就會自動跟住 2 日規則刪。
- `tools/top5video.sh` 係現成 ffmpeg 例子（1080×1920、`libx264`、`-crf 28`、`-pix_fmt yuv420p`、`-movflags +faststart`、`-an`）。GitHub runner 已經有 ffmpeg。
- `.github/workflows/update-site.yml` 嘅「Daily multi-picture posts」步驟跑 carousel.py + carousel.js。

**建議做法**
1. V1：`carousel.html` 加 `window.ANIM`（預設 false）。true 時，各元素加 CSS animation（`animation-play-state: paused`），並提供 `seek(ms)`：用 `document.getAnimations()` 將每個動畫 `currentTime` 設成 `ms`。咁每格都係準確、可重複嘅畫面。
2. V2：新檔 `tools/carousel_video.js`：讀 `work/carousel.json`，只處理 `slot` 喺 `VIDEO_SLOTS`（預設 `['1230']`，可用環境變數 `VIDEO_SLOTS=1230,1630` 改）嘅 job。每張圖 4 秒 × 24 fps，逐格 `seek` + screenshot（1080×1350），放喺 1080×1920 外框（上下同款背景、頂 logo、底網址同「唔構成投資建議」，按語言），pipe 入 ffmpeg 出 `og/c/<day>-<slot>-<lang>.mp4`。
3. V3：`carousel.py` 喺 `VIDEO_SLOTS` 嘅時段寫 `slots.<slot>.video = {zh, en, ko}`（`https://thecrowdtape.com/og/c/<day>-<slot>-<lang>.mp4`）。`update-site.yml` 喺「Daily multi-picture posts」之後加一步「Carousel motion video」：`continue-on-error: true`、`timeout-minutes: 6`，跑 `node tools/carousel_video.js`，之後檢查邊個 mp4 唔存在，就喺 `data/social-posts.json` 刪走嗰個語言（全部冇就刪成格 `video`）。
4. V4：`carousel.py` 嘅 `slot_page()` 有 `video` 就加 `<video controls playsinline>` 同下載連結。
5. V6：`tools/test_motion_video.py`（跟 `tools/test_slots.py` 寫法）。

---

## 五、畫面設計（逐鏡）

約 16 秒，4 張圖每張 4 秒。
- 共通：每張圖由右向左掃入（0.3 秒），停留時 100% → 105% 慢推鏡；頁碼跟住跳；底部「⚠️ 唔構成投資建議」常駐。
- 第 1 張（0–4 秒）：日期貼紙彈入 → 大代號由大縮細「砸」落位，黃色底色由左畫到右 → 帳號數由 0 跳到實數 → 綠「睇好」、紅「睇淡」逐個彈出 → 引言框由右滑入。
- 第 2 張（4–8 秒）：股票卡由上而下逐張彈入（每張隔 0.2 秒）→ 走勢線由左畫到右。
- 第 3 張（8–12 秒）：「共同看多」區先出，卡逐張彈入；再「共同看空」區。
- 第 4 張（12–16 秒）：分歧卡逐張彈入 → 黑色「Follow @thecrowdtape」框彈一下。
- 動作只改位置、大小、透明度；字同數字最後一格必須同靜態圖一樣。
