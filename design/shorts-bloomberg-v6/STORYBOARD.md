# Terminal Shorts 分鏡（Bloomberg／終端風）

Tim 揀、CEO 急。視覺取代 comic `carousel_scene.html` + `carousel_scenes.js`。旁白、≤29s、中英規則唔改。

畫幅 **1080×1920**。動效只得 **fade／slide（translateY）／count-up**。無 emoji、無彩紙、無 shake、無白閃砸落。

第 0 格（封面）已經見到 **$代號 + 主數字**。Hook 唔再出「？？？」。

---

## 時間軸（生產片 · 無 VO 拉長）

`carousel_video.js` 而家：封面 17 格（≈0.71s）+ `BASE` 8 段。一拍 `BEAT = 60/124 ≈ 0.484s`。有旁白嘅段會加拍，總長（連封面）≤29s。

| 鏡 | scene 名 | 生產位置 | 基長 | 畫面上嘅字（sample） | 動 | 停 |
|---|---|---|---|---|---|---|
| 1 封面 | `cover` | 0.00–0.71s | 0.71s（17 格） | LIVE / TAPE / TCT / The Crowd Tape · 2026-11-03 · 今日焦點 · **$NVDA** · **+12%** · 看多人氣 · 42 看多 / 11 看空 · @thecrowdtape · thecrowdtape.com | 無。t=0 已經畫完（cover.jpg 海報） | 全程靜止 |
| 2 鎖定 | `hook` | 0.71s 起，5 拍 ≈2.42s | 5 拍 | 頂欄 quote：**$NVDA +12% 看多人氣**（一入場就喺）· SESSION · 今日焦點 · 01 看多人氣 · 02 $NVDA +12% | 標題 fade+slide；log 行逐行 0.22s 入場 | 最後一拍 hold |
| 3 揭曉 | `reveal` | hook 之後，4 拍 ≈1.94s | 4 拍 | LAST · SYM · **$NVDA** · **+12%** · 看多人氣 | 代號 slide 入；主數字 count-up；label fade | 數字到位後 hold |
| 4 多空 | `vs` | reveal 之後，6 拍 ≈2.90s | 6 拍 | BULL / BEAR · 看多 **42** · 看空 **11** · 79% / 21% · 一條幼 bar · 01 討論量較昨日 +38% · 02 55 個帳號提及 | 數字 count-up；bar 由 0 拉闊；兩句數據 ~1.2s fade 入 | 最後兩拍 hold |
| 5 數據 | `facts` | **可選**。生產唔改 `BASE` 就摺喺 vs 下半 | 預覽 2.5s | DATA · 關鍵數據 · 01 討論量較昨日 +38% · 02 55 個帳號提及 | 兩行相隔 0.22s fade+slide | hold |
| 6 CTA | `outro` | s1–s4 之後，7 拍 ≈3.39s | 7 拍 | FOLLOW · **thecrowdtape.com** · **@thecrowdtape** · 其餘 D.t 行（已剝 emoji） | URL → handle → 其餘行逐行 fade | 最後兩拍 hold |

s1–s4 仍由 `carousel.html` + `carousel_motion.js` 畫，本模版唔改。

VO 拉長時，動畫時間表唔變，只係停得耐啲（同而家規則）。

---

## 每鏡細節

### 1 · cover · 短封面

- **時間**：片頭 0.00–0.71s。`draw` 每格都叫，畫面唔郁。
- **畫面字**：品牌終端頂欄（LIVE 綠點、TAPE、TCT、The Crowd Tape、日期）。主區 EQTY · US、標題「今日焦點」、SYM / LAST、巨號 `$NVDA`、綠色 `+12%`、灰標「看多人氣」。有數就出幼多空。底欄 handle · 網址 · 免責（若 D.foot）。
- **動**：無。
- **停**：全程。第 0 格等於海報。

### 2 · hook · 主 ticker 已鎖定

- **時間**：5 拍（VO 可加拍）。
- **畫面字**：頂欄 quote 一入場就有 `$NVDA +12%`。主區 SESSION、標題、編號 log（舊 `D.t` 去掉 emoji 同「？？？」；sample 用 heroLabel + 代號行）。
- **動**：標題 0.00s fade+slide 18px；log 0.12s 起每隔 0.22s。
- **停**：約 t≥1.0s 之後。

### 3 · reveal · 主數字揭曉

- **時間**：4 拍。
- **畫面字**：LAST / SYM / `$NVDA` / `+12%` / 看多人氣。Quote 條仍在。
- **動**：kicker 即入；代號 0.08s slide；數字 0.16s 起 count-up（+、% 保留）；label 0.36s fade。
- **停**：count-up 完（~0.56s）到段尾。

### 4 · vs · 多空數字 + 幼 bar

- **時間**：6 拍。
- **畫面字**：看多 42（綠）· 看空 11（紅）· 百分比 · 一條 8px 雙色 bar · 最多兩句數據。舊稿無 fact 就用剝咗 emoji 嘅 `D.t[2]` 做一句。
- **動**：label fade；0.18s 起 count-up；0.35s bar 拉闊；1.15s／1.37s 數據行。
- **停**：數據行入完到段尾。

### 5 · facts · 最多兩句（可選 scene）

- **時間**：預覽當獨立鏡。生產摺入 vs，**唔加 BASE 段、唔改 8 句旁白**。
- **畫面字**：DATA · 關鍵數據 · 01 … · 02 …
- **動**：兩行 fade+slide。
- **停**：第二行入完。

### 6 · outro · CTA

- **時間**：7 拍。
- **畫面字**：FOLLOW · thecrowdtape.com · @thecrowdtape · 其餘 outro 行（「想看完整內容？」「免費・無需登入・每 4 小時更新」「不構成投資建議」——⚠️🔔👇 已剝）。
- **動**：URL 0.08s、handle 0.22s、其餘每隔 0.18s。
- **停**：最後約 2 拍。

---

## Sample 對白面上嘅字

```
date        2026-11-03
title       今日焦點
ticker      NVDA          → $NVDA
hero        +12%          → 綠、count-up
heroLabel   看多人氣
bull / bear 42 / 11
bullL/bearL 看多 / 看空
fact1       討論量較昨日 +38%
fact2       55 個帳號提及
cta         thecrowdtape.com
handle      @thecrowdtape
```

負數 hero（例如 `-3.2%`）用熊紅 `#ff4757`。
