# 輪播圖動態片：規格、任務、驗收清單

> 2026-10-24，Tim 喺「寫 30 秒宣傳片腳本」thread 揀好：
> ① GitHub 每日自動整（唔用 Grok 寫或者畫）；② 字同卡片都會郁（B）；③ 只係 12:30 今日快照出片；④（12:59 改）片入面**自帶程式生成嘅節拍同音效**，唔再靠 app 加音樂；⑤ 跟第 2 版樣板做：開場鈎、大標題、震動、結尾 CTA；⑥（13:16 加）中文版加**普通話配音**，用 edge-tts 免費語音，第一條真片當樣板。
> ⑦（15:41 Tim OK）跟**第 4 版樣板**做：跟拍剪接、全畫面快閃大字、VS 對決、輪播圖完整顯示（唔放大）加黃色發光框。
> 樣板：Claude 項目檔 `motion-sample/sample-1230-zh-v4.mp4`；試做程式：repo `tools/motion_proto/`（`motion3.js`、`slideanim.js`、`audio3.py`；舊版 `motion2.js`、`audio.py` 只作參考）。
> 畫面設計原稿：Claude 項目檔 `carousel-motion-video-script.md`（本檔第一節已經包括最新設計）。

---

## 一、規格

### 要解決咩問題
每日輪播帖只係靜態圖。IG 同 Facebook 而家主力推 Reels（短片），靜態帖觸及少。網站每日已經自動畫好 4 張輪播圖，但冇片可以發。

### 成功係咩樣
1. 美股交易日，12:30「今日快照」輪播圖畫好之後，同一次網站更新順手出 **3 條動態片**（中、英、韓各一條）。
2. 每條片：**1080×1920 直片、mp4（H.264 + AAC 聲）**，IG／FB Reels 直接用得。冇配音約 23 秒；有配音每段按旁白長度加長（以拍為單位），約 26 至 32 秒。
3. 節拍 124 BPM（一拍約 0.48 秒），所有剪接對準拍子，冇轉場效果（硬剪 + 一下白閃）。全片頂部有黃色**進度條**由左行到右。片分 8 段（括號係拍數）：
   - **① 快閃開場（5 拍）**：全畫面大字逐拍出：「今日」→「X 上 200 個美股大神」→「最多人講嘅係…」→「？？？」（搖晃），背景顏色每拍轉（深藍、紫、紅、黃、藍），配鼓聲越打越急，未有完整節拍。
   - **② 揭曉（4 拍）**：音樂完整爆出（drop），全畫面「$代號」白底大字砸落，畫面震、閃白光，🔥🚀👀💥📈🤯 向四邊飛；第 3 拍出「{N} 個帳號講緊！」。黃粉漸變背景＋轉動放射線。
   - **③ VS 對決（6 拍）**：綠（左）紅（右）兩半由兩邊衝入；「🟢 睇好」「🔴 睇淡」彈出；第 2 拍「VS」砸落（震、閃光）；第 3、4 拍好淡人數各自砸落並由 0 跳上去；第 5 拍人數多嗰邊推闊；最後出「淡友大勝？😱」／「好友大勝？🚀」／「打和！🤝」。
   - **④–⑦ 4 張輪播圖（7、7、6、6 拍）**：**成張圖全程完整顯示，唔放大、唔裁走任何資訊**；字同數字一隻都唔改。圖入面元素照第 2 版動畫出場（砸落代號、跳數、卡逐張彈入、畫走勢線、Follow 框彈），速度快 1.35 倍。講到邊度，嗰度加**黃色發光框**（跟拍子閃），其他位調暗少少：圖 1 大代號 → 引言；圖 2 Top 4 逐張卡；圖 3 共同看多 → 共同看空；圖 4 最後 Follow 框。代號砸落嗰下震＋白閃＋emoji 飛。
   - 4 張圖頂部黃色大標題（輕輕搖）：① 「大神點講 $代號？💬」② 「🔥 熱度 Top 4」③ 「一齊睇好 🟢 定睇淡 🔴」④ 「⚔️ 爭拗最大！你企邊？」；底部大網址 thecrowdtape.com；深色背景＋轉動放射線。
   - **⑧ 結尾（7 拍）**：紫粉漸變，彩紙落，逐句彈出「想睇晒全部？👇」、thecrowdtape.com、「免費・唔使登入・每 4 小時更新」、「Follow @thecrowdtape 🔔」、「⚠️ 唔構成投資建議」。
   - 英文、韓文版用同一設計，字換成該語言。
   - **聲**：程式生成（唔用任何音樂檔、冇版權問題）。開場只有 hi-hat 同越打越急嘅拍手聲；揭曉嗰下「轟」＋完整節拍（kick、clap、hi-hat、低音、和弦）。音效對準動作：每段開始「嗖」、彈出「啵」、砸落「轟」、人數「啪」、跳數「滴滴」、畫線同推闊「咻」上升聲、結尾網址「叮」；最後 1.2 秒淡出。
   - **普通話配音（只係中文版）**：GitHub 每次按當日數據自動寫旁白，用 edge-tts（免費、唔使 API key）`zh-CN-XiaoxiaoNeural` 女聲、語速 +10% 讀出。每段一句，對應畫面：
     - ① 快閃開場：「X 上兩百位美股大神，今天最熱門的是哪一檔？」
     - ② 揭曉：「答案是 {代號}！{N} 個帳號在討論！」
     - ③ VS：「{好} 個看好，{淡} 個看空，{多數嗰邊}方佔上風！」（打和就讀「好淡打成平手！」）
     - ④ 圖 1：「看看大神們怎麼說。」
     - ⑤ 圖 2：「熱度前四名：{代號1}、{代號2}、{代號3}、{代號4}。」
     - ⑥ 圖 3：「大神一起看好 {共同看多第 1}，一起看空 {共同看空第 1}。」（冇嗰邊就唔讀嗰半句）
     - ⑦ 圖 4：「分歧最大的是 {分歧股第 1}，你站哪一邊？」
     - ⑧ 結尾：「完整內容上 thecrowdtape.com，記得追蹤我們！」
     - 旁白比嗰段長，嗰段就加整數拍（旁白 + 0.4 秒，向上捨入到拍），動畫時間表唔變，只係停留長啲。
     - 代號逐個字母讀（例如 S、P、Y）；數字同輪播圖一樣；旁白永遠唔講買、賣、目標價或者預測。
     - 講嘢期間節拍自動收細到約 35%，講完回復；音效照出。
   - 配音失敗（edge-tts 連唔到、出錯）：自動出冇配音版（約 23 秒），唔會令出片或者網站更新失敗，喺 Actions 出警告。
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
| **V1** | 畫圖網頁加「動畫模式」（參考 `tools/motion_proto/slideanim.js`）：同一個輪播網頁，每個元素按時間出場（砸落、跳數、彈入、畫線、黃色發光框、其他位調暗），可以停喺任何一格時間。唔開動畫模式時，畫出嚟嘅靜態圖同而家一模一樣。 | 靜態圖同改之前逐點比較一樣；喺瀏覽器拉時間軸睇到每個動作 | — |
| **V2** | 逐格錄製 + 砌片 + 聲：8 段（快閃開場、揭曉、VS、4 張圖、結尾）逐格影相（24 fps）、跟拍硬剪、頂部進度條同大標題、底部網址；按動作時間生成節拍同音效；ffmpeg 砌成 1080×1920 mp4（約 23 秒、有聲）。參考 `tools/motion_proto/motion3.js`、`audio3.py`。 | 本機出到中英韓 3 條片，同 v4 樣板一樣效果，Tim 睇過 | V1 |
| **V2b** | 普通話配音：按當日數據寫 8 句旁白，edge-tts 讀出，按旁白長度調整每段時間，節拍收細；失敗就出冇配音版。 | 用真數據出中文片，聽到 8 句旁白、同畫面對得上；斷網時出到冇配音版 | V2 |
| **V3** | 接入每日更新：12:30 時段寫好之後先出片；寫入 `slots.1230.video`；出片時段做成一個設定；出錯只出警告唔令更新失敗；片 2 日後刪除。 | 一次真實「Update site」跑完：網站有 3 條片、`social-posts.json` 有 `video`；故意令出片失敗，更新照樣成功 | V2 |
| **V4** | `/social/` 頁 12:30 嗰格加片（可播放、可下載）。 | 打開 thecrowdtape.com/social/ 睇到同下載到 3 條片 | V3 |
| **V5** | Grok bot 手冊：第 7 節 12:30／13:00／13:30 三個例行程序加「IG Reels + FB Reels」步驟（唔使加音樂、冇片就跳過並 email）；`bot-schedules.md` 加時間；寫一份只有改動部分嘅更新檔俾 Tim 轉交。 | Tim 收到更新檔；Grok bot 改好 3 個例行程序 | V3（要知道 `video` 嘅確實位置） |
| **V6** | 測試：自動測試檢查 `video` 格式、只喺設定時段出片、失敗唔拖累更新、舊片會刪。 | GitHub「Build check」綠色 | V3 |

先後次序：V1 → V2 → V2b → V3 →（V4、V5、V6 可以同時做）。

---

## 三、驗收 checklist

- [ ] V1 靜態輪播圖同改之前一樣（冇走位、冇少字）
- [ ] V1 動畫模式每個動作都出現：砸落代號、跳數、彈入卡片、畫走勢線、黃色發光框（其他位調暗）、Follow 框彈一下
- [ ] V1 輪播圖全程完整顯示，冇放大、冇裁走任何資訊
- [ ] V2 樣片：1080×1920、約 23 秒、mp4，喺 iPhone 播到，有節拍同音效
- [ ] V2 有快閃開場、揭曉、VS 對決、每張圖頂部大標題、砸落時震動閃光同 emoji、結尾彩紙同 CTA、頂部進度條
- [ ] V2 剪接對準拍子；揭曉嗰下音樂爆出
- [ ] V2 音效對準動作（每段嗖、砸落轟、人數啪、跳數滴滴、網址叮）
- [ ] V2 樣片入面嘅字同數字同當日 4 張輪播圖完全一樣
- [ ] V2 底有 thecrowdtape.com、輪播圖同結尾都有「唔構成投資建議」
- [ ] V2 中、英、韓 3 條都啱語言
- [ ] V2b 中文片有普通話旁白，8 句同畫面對得上，代號逐個字母讀，數字同圖一樣
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
2. V2：新檔 `tools/carousel_video.js`（由 `tools/motion_proto/motion3.js` + `slideanim.js` 改成正式版）：讀 `work/carousel.json`，只處理 `slot` 喺 `VIDEO_SLOTS`（預設 `['1230']`，可用環境變數 `VIDEO_SLOTS=1230,1630` 改）嘅 job。開場、4 張圖、結尾逐格影相（24 fps），記低每個動作嘅開始時間（`events.json`），交 `tools/motion_proto/audio3.py`（numpy 生成節拍同音效，workflow 要 `pip install numpy`）出 wav，再用 ffmpeg 直接砌成（硬剪，唔用 xfade） `og/c/<day>-<slot>-<lang>.mp4`（H.264 + AAC）。**要加快**：樣板單綫做一個語言約 2 分鐘；正式版 3 個語言用 3 個 page 同時做，或者只影有變化嘅格，目標 12:30 嗰次更新多唔超過 3 分鐘。
3. V3：`carousel.py` 喺 `VIDEO_SLOTS` 嘅時段寫 `slots.<slot>.video = {zh, en, ko}`（`https://thecrowdtape.com/og/c/<day>-<slot>-<lang>.mp4`）。`update-site.yml` 喺「Daily multi-picture posts」之後加一步「Carousel motion video」：`continue-on-error: true`、`timeout-minutes: 10`，跑 `node tools/carousel_video.js`，之後檢查邊個 mp4 唔存在，就喺 `data/social-posts.json` 刪走嗰個語言（全部冇就刪成格 `video`）。
4. V4：`carousel.py` 嘅 `slot_page()` 有 `video` 就加 `<video controls playsinline>` 同下載連結。
5. V6：`tools/test_motion_video.py`（跟 `tools/test_slots.py` 寫法）。

---

**試做程式（樣板用，未接入 workflow）**
- **第 4 版（Tim 揀咗，照呢個做）**：`node tools/motion_proto/motion3.js work/carousel.json 1230 zh out.mp4`（喺 repo 根目錄跑）。`motion3.js` 管 8 段時間（`SC`，以拍計）、快閃開場／揭曉／VS／結尾全畫面場景（`setup()`、`draw()`）、逐格影相、`events3.json`；`slideanim.js` 管輪播圖動畫（`prep()`、`seek()`）、外框、大標題、黃色發光框（`setupSlide()`、`drawSlide()`）；`audio3.py` 讀 `{total, bpm, drop, events:[{at,type}]}` 生成聲。中文字（`T`）寫死咗，正式版要中英韓各一套。
- 以下係第 2 版，只作參考：
- `tools/motion_proto/motion2.js`：`node tools/motion_proto/motion2.js work/carousel.json 1230 zh out.mp4`（要先有 `work/carousel.json`，即係跑完 stats.js 同 carousel.py）。入面有 `prep()`（排動作時間表）、`seek(ms)`（逐格設定位置／透明度／放大）、`frame()`（1080×1920 外框、大標題、閃光）、開場同結尾 `scene()`、ffmpeg 砌片。`REPO` 路徑寫死咗，正式版要改。
- `tools/motion_proto/audio.py`：`python3 audio.py events.json out.wav`，全部聲用 numpy 生成，冇音樂檔。段落開始時間 `seg` 寫死咗（2 秒開場、4 秒一張、0.3 秒轉場），正式版要由 js 傳入。

**配音（V2b）做法**
- workflow 出片步驟加 `pip install edge-tts==7.3.1`（鎖死版本）。GitHub runner 連得到 edge-tts；Claude 雲端環境連唔到，所以樣板未有配音。
- 旁白由 `work/carousel.json` 同一份 slides 數據寫（`slides[0].big`、`sub`、`pills`；`slides[1]` 首 4 張卡 `t`；`slides[2]` 共同看多／看空第 1 張卡；`slides[3]` 第 1 張卡）。代號寫成 `S P Y` 咁樣（字母中間加空格）令佢逐個字母讀。
- 每句 `edge-tts --voice zh-CN-XiaoxiaoNeural --rate=+10% --text ... --write-media seg<n>.mp3`，每句最多等 30 秒、失敗重試 1 次；任何一句失敗就成條片唔配音（唔好出半條有聲）。
- 用 ffprobe 量每句長度 → 該段拍數 = max(預設拍數, ceil((旁白 + 0.4 秒) / 拍長)) → 重新計 `starts`，逐格影相用新段長（動畫時間表唔變，停留時間拉長）。
- `audio3.py` 要加：旁白檔同開始時間由 js 傳入；旁白喺每段開始後 0.15 秒入；旁白期間音樂乘 0.35（前後 0.15 秒過渡）；音效唔收細。
- 設定：`VO_LANGS`（預設 `zh`）、`VO_VOICE_zh`（預設 `zh-CN-XiaoxiaoNeural`）。
