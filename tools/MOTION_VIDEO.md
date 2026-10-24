# 輪播圖動態片：規格、任務、驗收清單

> 2026-10-24，Tim 喺「寫 30 秒宣傳片腳本」thread 揀好：
> ① GitHub 每日自動整（唔用 Grok 寫或者畫）；② 字同卡片都會郁（B）；③ 只係 12:30 今日快照出片；④（12:59 改）片入面**自帶程式生成嘅節拍同音效**，唔再靠 app 加音樂；⑤ 跟第 2 版樣板做：開場鈎、大標題、震動、結尾 CTA；⑥（13:16 加）中文版加**普通話配音**，用 edge-tts 免費語音，第一條真片當樣板。
> 樣板：Claude 項目檔 `motion-sample/sample-1230-zh-v2.mp4`；試做程式：repo `tools/motion_proto/`（`motion2.js`、`audio.py`）。
> 畫面設計原稿：Claude 項目檔 `carousel-motion-video-script.md`（本檔第一節已經包括）。

---

## 一、規格

### 要解決咩問題
每日輪播帖只係靜態圖。IG 同 Facebook 而家主力推 Reels（短片），靜態帖觸及少。網站每日已經自動畫好 4 張輪播圖，但冇片可以發。

### 成功係咩樣
1. 美股交易日，12:30「今日快照」輪播圖畫好之後，同一次網站更新順手出 **3 條動態片**（中、英、韓各一條）。
2. 每條片：**1080×1920 直片、mp4（H.264 + AAC 聲）**，IG／FB Reels 直接用得。冇配音約 19 秒；有配音每段按旁白長度拉長，約 25 至 30 秒。
3. 片分 6 段：開場鈎 2 秒 → 4 張輪播圖各 4 秒 → 結尾 2.5 秒（有配音時每段 = 最少呢個長度，或者旁白長度 + 0.5 秒，揀長嗰個），段與段之間 0.3 秒「向左滑」轉場（最後一下放大轉場）。
   - **開場鈎**：logo、「X 上面 200 個美股大神」「今日最多人講邊隻？👀」「20 秒話你知 ⏱️」逐句彈出（中英韓各自一套字）。
   - **每張圖頂部大標題**（白底黑框貼紙，輕輕搖）：① 「全場最多人講 👉 $代號」② 「🔥 熱度 Top 4，邊隻上榜？」③ 「大神一齊睇好 🟢 定睇淡 🔴？」④ 「⚔️ 好淡開戰！你企邊邊？」；底部大網址 thecrowdtape.com；背景放射線慢慢轉。
   - 4 張圖嘅內容**字同數字一隻都唔改**，只係加動作。停留時慢慢放大；
   - 第 1 張：日期貼紙彈入、大代號「砸」落位（嗰下成個畫面震、閃白光、🔥🚀👀💥 向四邊飛出）、黃底色畫出、帳號數由 0 跳上去、好淡數逐個彈出、引言框滑入；
   - 第 2 至 4 張：股票卡／區塊逐張彈入，走勢線由左畫到右；
   - 最後「Follow @thecrowdtape」框彈一下。
   - **結尾**：「想睇晒全部？👇」、thecrowdtape.com、「免費・唔使登入」、「每 4 小時自動更新」、「Follow @thecrowdtape 🔔」、「⚠️ 唔構成投資建議」逐句彈出。
   - **聲**：程式生成（唔用任何音樂檔、冇版權問題）約 124 BPM 輕快節拍（kick、clap、hi-hat、低音、和弦），加對準動作嘅音效：轉場「嗖」、彈出「啵」、砸落「轟」、跳數「滴滴」、畫線「咻」上升聲、結尾網址「叮」；最後 1.2 秒淡出。
   - **普通話配音（只係中文版）**：GitHub 每次按當日數據自動寫旁白，用 edge-tts（免費、唔使 API key）`zh-CN-XiaoxiaoNeural` 女聲、語速 +10% 讀出。每段一句，對應畫面：
     - 開場：「X 上兩百位美股大神，今天最熱門的是哪一檔？」
     - 圖 1：「答案是 {代號}！{N} 個帳號在討論，{好} 個看好，{淡} 個看空。」
     - 圖 2：「熱度前四名：{代號1}、{代號2}、{代號3}、{代號4}。」
     - 圖 3：「大神一起看好 {共同看多第 1}，一起看空 {共同看空第 1}。」（冇嗰邊就唔讀嗰半句）
     - 圖 4：「分歧最大的是 {分歧股第 1}，你站哪一邊？」
     - 結尾：「完整內容上 thecrowdtape.com，記得追蹤我們！」
     - 代號逐個字母讀（例如 S、P、Y）；數字同輪播圖一樣；旁白永遠唔講買、賣、目標價或者預測。
     - 講嘢期間節拍自動收細到約 35%，講完回復；音效照出。
   - 配音失敗（edge-tts 連唔到、出錯）：自動出冇配音版（19 秒），唔會令出片或者網站更新失敗，喺 Actions 出警告。
   - 英文、韓文版暫時冇配音；以後要加，只係改一個設定（配音語言清單同每個語言嘅聲）。
4. `data/social-posts.json` 嘅 `slots.1230` 多一格 `video`（每個語言一條片網址），`/social/` 頁 12:30 嗰格可以直接睇同下載條片。
5. Grok bot 角色 ① 喺原本 12:30／13:00／13:30 例行程序，發完 Facebook 多圖帖之後，**再發 IG Reels 同 FB Reels**：用 `slots.1230.video.<語言>`，文字用同一時段嘅 IG／Facebook 文字。**唔使加音樂**（片已經有聲）。唔開新例行程序。
6. 片同輪播圖一樣**保留 2 日**，之後自動刪。
7. 出唔到片（例如程式出錯）：輪播圖同其他帖照出照發，唔會令網站更新失敗；`video` 嗰格冇內容，Grok bot 就跳過 Reels，喺完成 email 講「冇片」。
8. 以後想擴大到 16:30／20:30，只係改一個設定（出片時段清單），唔使改程式。

### 明確唔做
- 唔用外來音樂檔；唔用付費配音服務；英文、韓文版暫時唔配音。
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
| **V2** | 逐格錄製 + 砌片 + 聲：開場鈎、4 張圖（V1 逐格影相，24 fps）、結尾，加頂部大標題同底部網址；按動作時間生成節拍同音效；ffmpeg 砌成 1080×1920 mp4（約 19 秒、有聲）。參考 `tools/motion_proto/`。 | 本機出到中英韓 3 條片，同 v2 樣板一樣效果，Tim 睇過 | V1 |
| **V2b** | 普通話配音：按當日數據寫 6 句旁白，edge-tts 讀出，按旁白長度調整每段時間，節拍收細；失敗就出冇配音版。 | 用真數據出中文片，聽到 6 句旁白、同畫面對得上；斷網時出到冇配音版 | V2 |
| **V3** | 接入每日更新：12:30 時段寫好之後先出片；寫入 `slots.1230.video`；出片時段做成一個設定；出錯只出警告唔令更新失敗；片 2 日後刪除。 | 一次真實「Update site」跑完：網站有 3 條片、`social-posts.json` 有 `video`；故意令出片失敗，更新照樣成功 | V2 |
| **V4** | `/social/` 頁 12:30 嗰格加片（可播放、可下載）。 | 打開 thecrowdtape.com/social/ 睇到同下載到 3 條片 | V3 |
| **V5** | Grok bot 手冊：第 7 節 12:30／13:00／13:30 三個例行程序加「IG Reels + FB Reels」步驟（唔使加音樂、冇片就跳過並 email）；`bot-schedules.md` 加時間；寫一份只有改動部分嘅更新檔俾 Tim 轉交。 | Tim 收到更新檔；Grok bot 改好 3 個例行程序 | V3（要知道 `video` 嘅確實位置） |
| **V6** | 測試：自動測試檢查 `video` 格式、只喺設定時段出片、失敗唔拖累更新、舊片會刪。 | GitHub「Build check」綠色 | V3 |

先後次序：V1 → V2 → V2b → V3 →（V4、V5、V6 可以同時做）。

---

## 三、驗收 checklist

- [ ] V1 靜態輪播圖同改之前一樣（冇走位、冇少字）
- [ ] V1 動畫模式每個動作都出現：掃入、慢推鏡、砸落代號、跳數、彈入卡片、畫走勢線、Follow 框彈一下
- [ ] V2 樣片：1080×1920、約 19 秒、mp4，喺 iPhone 播到，有節拍同音效
- [ ] V2 有開場鈎、每張圖頂部大標題、砸落時震動閃光同 emoji、結尾 CTA
- [ ] V2 音效對準動作（轉場嗖、砸落轟、跳數滴滴、網址叮）
- [ ] V2 樣片入面嘅字同數字同當日 4 張輪播圖完全一樣
- [ ] V2 底有 thecrowdtape.com、輪播圖同結尾都有「唔構成投資建議」
- [ ] V2 中、英、韓 3 條都啱語言
- [ ] V2b 中文片有普通話旁白，6 句同畫面對得上，代號逐個字母讀，數字同圖一樣
- [ ] V2b 旁白冇講買、賣、目標價或者預測
- [ ] V2b 講嘢時節拍收細，聽得清楚
- [ ] V2b 配音失敗時自動出冇配音版，網站更新照常
- [ ] V2b 第一條真片（樣板）Tim 聽過 OK
- [ ] V3 交易日 12:30 時段出咗 3 條片，`slots.1230.video` 有 3 個網址
- [ ] V3 16:30、20:30、週末都冇出片
- [ ] V3 出片失敗時，網站更新同輪播帖照常
- [ ] V3 2 日前嘅片已經自動刪除
- [ ] V3 只有 12:30 嗰次更新變慢，而且多唔超過 3 分鐘（樣板程式單綫做一個語言要約 2 分鐘，3 個語言要同時做或者加快）；其他時段唔變
- [ ] V4 /social/ 頁睇到、播到、下載到 3 條片
- [ ] V5 Tim 收到手冊改動部分；Grok bot 3 個例行程序已改
- [ ] V5 第一個交易日：IG Reels、FB Reels 中英韓都發咗，有聲
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
2. V2：新檔 `tools/carousel_video.js`（由 `tools/motion_proto/motion2.js` 改成正式版）：讀 `work/carousel.json`，只處理 `slot` 喺 `VIDEO_SLOTS`（預設 `['1230']`，可用環境變數 `VIDEO_SLOTS=1230,1630` 改）嘅 job。開場、4 張圖、結尾逐格影相（24 fps），記低每個動作嘅開始時間（`events.json`），交 `tools/motion_proto/audio.py`（numpy 生成節拍同音效，workflow 要 `pip install numpy`）出 wav，再用 ffmpeg `xfade` 砌成 `og/c/<day>-<slot>-<lang>.mp4`（H.264 + AAC）。**要加快**：樣板單綫做一個語言約 2 分鐘；正式版 3 個語言用 3 個 page 同時做，或者只影有變化嘅格，目標 12:30 嗰次更新多唔超過 3 分鐘。
3. V3：`carousel.py` 喺 `VIDEO_SLOTS` 嘅時段寫 `slots.<slot>.video = {zh, en, ko}`（`https://thecrowdtape.com/og/c/<day>-<slot>-<lang>.mp4`）。`update-site.yml` 喺「Daily multi-picture posts」之後加一步「Carousel motion video」：`continue-on-error: true`、`timeout-minutes: 10`，跑 `node tools/carousel_video.js`，之後檢查邊個 mp4 唔存在，就喺 `data/social-posts.json` 刪走嗰個語言（全部冇就刪成格 `video`）。
4. V4：`carousel.py` 嘅 `slot_page()` 有 `video` 就加 `<video controls playsinline>` 同下載連結。
5. V6：`tools/test_motion_video.py`（跟 `tools/test_slots.py` 寫法）。

---

**試做程式（樣板用，未接入 workflow）**
- `tools/motion_proto/motion2.js`：`node tools/motion_proto/motion2.js work/carousel.json 1230 zh out.mp4`（要先有 `work/carousel.json`，即係跑完 stats.js 同 carousel.py）。入面有 `prep()`（排動作時間表）、`seek(ms)`（逐格設定位置／透明度／放大）、`frame()`（1080×1920 外框、大標題、閃光）、開場同結尾 `scene()`、ffmpeg 砌片。`REPO` 路徑寫死咗，正式版要改。
- `tools/motion_proto/audio.py`：`python3 audio.py events.json out.wav`，全部聲用 numpy 生成，冇音樂檔。段落開始時間 `seg` 寫死咗（2 秒開場、4 秒一張、0.3 秒轉場），正式版要由 js 傳入。

**配音（V2b）做法**
- workflow 出片步驟加 `pip install edge-tts==7.3.1`（鎖死版本）。GitHub runner 連得到 edge-tts；Claude 雲端環境連唔到，所以樣板未有配音。
- 旁白由 `work/carousel.json` 同一份 slides 數據寫（`slides[0].big`、`sub`、`pills`；`slides[1]` 首 4 張卡 `t`；`slides[2]` 共同看多／看空第 1 張卡；`slides[3]` 第 1 張卡）。代號寫成 `S P Y` 咁樣（字母中間加空格）令佢逐個字母讀。
- 每句 `edge-tts --voice zh-CN-XiaoxiaoNeural --rate=+10% --text ... --write-media seg<n>.mp3`，每句最多等 30 秒、失敗重試 1 次；任何一句失敗就成條片唔配音（唔好出半條有聲）。
- 用 ffprobe 量每句長度 → 段長 = max(預設段長, 旁白 + 0.5 秒) → 逐格影相時用新段長（動畫時間表唔變，停留時間拉長，慢推鏡按新長度）。
- `audio.py` 要改：段落開始時間由 js 傳入；旁白喺每段開始後 0.15 秒入；旁白期間音樂乘 0.35（前後 0.15 秒過渡）；音效唔收細。
- 設定：`VO_LANGS`（預設 `zh`）、`VO_VOICE_zh`（預設 `zh-CN-XiaoxiaoNeural`）。

