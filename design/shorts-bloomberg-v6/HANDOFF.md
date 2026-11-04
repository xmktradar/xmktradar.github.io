# HANDOFF — Terminal Shorts 落地（交 HTML 管理者）

**唔開 production PR。** 本目錄係設計包。你落地時先對 `tools/` 做本機對位，確認封面第 0 格、zh/en、VO 長度，先至開 PR。

作者：Grok（CEO 急、Tim 揀 Bloomberg／終端風）。日期：2026-11-04。

---

## 換邊啲檔

| 本目錄 | 落到 | 作用 |
|---|---|---|
| `tokens.css` | `tools/tokens.css`（新檔） | 色／字／間距／終端零件 |
| `terminal_scene.html` | **取代** `tools/carousel_scene.html` | 1080×1920 殼 |
| `terminal_scenes.js` | **取代** `tools/carousel_scenes.js` | `setup` / `draw` |
| `STORYBOARD.md` | 可放 `tools/` 或設計檔 | 分鏡 |
| `PREVIEW.html` | 可放 `tools/` 或只喺簽收用 | 六鏡靜態預覽 |
| `HANDOFF.md` | 本說明 | — |

`carousel_video.js` 而家：

```js
await sp.goto('file://' + path.join(TOOLS, 'carousel_scene.html'), …);
await sp.addScriptTag({ content: header(total) + fs.readFileSync(path.join(TOOLS, 'carousel_scenes.js'), 'utf8') });
```

所以落地最乾淨係 **用新內容覆蓋舊兩個檔名**（html 入面 `<link href="tokens.css">` 要同目錄）。唔好改 `goto` 檔名除非你一齊改 JS。

`social_apple.css` **唔好**再 link 入 scene 殼——會打爆終端風。

`#bg` `#c` `#flash` `#rays` 都仲喺。`#rays` 隱藏。`#flash` 永遠 opacity 0。`chrome()` 畫嘅 `#pbar` 喺 `draw` 入面改成 3px 牛綠，無黃條陰影。

---

## Scene 名映射

**保留** `cover / hook / reveal / vs / outro`。`carousel_video.js` 嘅 `BASE` **唔使改**（改咗就改咗 8 句旁白同 29s 計法）。

| 舊 comic | 新終端 | 邊個 call |
|---|---|---|
| `cover` | `cover` 短封面，t=0 已見 $代號+主數字 | `setup('cover', C)` 17 格 |
| `hook` | `hook` 鎖定；quote 條一入場就有代號；**唔出 ？？？** | `setup('hook', { t: W.hook })` |
| `reveal` | `reveal` 巨號 + count-up | `setup('reveal', { big, reveal })` |
| `vs` | `vs` 數字 + 幼 bar；有 `fact1`/`fact2` 就喺下半出 | `setup('vs', { t, bull, bear })` |
| — | `facts` 可選；PREVIEW 用。**唔加入 BASE** | 無 call 就當摺入 vs |
| `outro` | `outro` CTA | `setup('outro', { t: W.outro })` |
| s1–s4 | **唔改** | `carousel.html` |

VO 規則原封：8 句、封面無旁白、中英、失敗就唔出嗰條語言、總長（連封面）≤29.0s。本包無改 `carousel_vo.py`。

---

## Data 形狀

`pack()` 食兩套，舊 call 仍然得。

**新（PREVIEW sample）**

```json
{
  "date": "2026-11-03",
  "title": "今日焦點",
  "ticker": "NVDA",
  "hero": "+12%",
  "heroLabel": "看多人氣",
  "bull": 42,
  "bear": 11,
  "bullL": "看多",
  "bearL": "看空",
  "fact1": "討論量較昨日 +38%",
  "fact2": "55 個帳號提及",
  "cta": "thecrowdtape.com",
  "handle": "@thecrowdtape"
}
```

**舊（而家 `carousel_video.js` 逐 scene 傳）**

| setup | D | 點解讀 |
|---|---|---|
| cover | `coverPack`：title, date, discussed, discussedN, discussedL, bull（字串代號）, bullN, bullL, posted, foot | `ticker←discussed`，`hero←discussedN` |
| hook | `{ t: [4 句] }` | 頂欄 quote 用 `window.TAPE`（封面寫入嘅 ticker/hero）。`t[3]` 若係 `???`／`？？？` 會刪 |
| reveal | `{ big, reveal }` | `ticker←big`，`heroLabel←reveal`，hero 承 TAPE |
| vs | `{ t:[看好,看空,判決], bull, bear }` | 數字 count-up；判決剝 emoji 做第三行（無 fact 時） |
| outro | `{ t:[5 句] }` | 剝 emoji 後逐行；網址／handle 另外強調 |

`D.bull` 喺 cover 係代號字串、喺 vs 係數字——用 `isCount()` 分。

建議（可選、一行）hook 都傳代號，唔靠 TAPE：

```js
await scene(0, { t: W.hook, ticker: W.big, hero: String(W.n) });
```

有 `fact1`/`fact2` 就 pass 入 vs。無就用舊判決句。

所有字都會剝 emoji。負 hero（`-3%`）熊紅，`+` 牛綠。

---

## 你唔需要改

- `carousel_vo.py` 稿、聲線、語速、29s
- `BASE` 拍數、`COVER_FRAMES`
- s1–s4 靜圖／`carousel_motion.js`
- 出片 slot、語言（zh,en）

`header()` 入面 `chrome()` 仍然會寫黃 `#pbar` inline style——`draw()` 每格覆寫成綠幼條。想源頭改可以，但唔係落地必須。

字型：scene 殼 load Inter 400–800 + Noto Sans TC 400–700。出片腳本而家 `document.fonts.load('900 80px "Noto Sans TC"')` 仍然得（系統有 Noto Sans CJK TC 700）。終端風用 500–700，唔用 900 砸字。

---

## 驗收

1. 開 `PREVIEW.html`（要有網路 load Google Fonts）。六鏡：$NVDA、+12% 綠色、42／11、兩句數據、CTA。無 emoji／彩紙／漫畫邊／彩虹底。
2. 本機：`carousel_scene.html` 換新殼，注入 `header+terminal_scenes.js`，`setup('cover', C)` 影第 0 格——**0.71s 內已經見到 $代號+主數字**。
3. zh + en 各一條；旁白 8 句對得上段；`ffprobe` duration ≤29.0；有聲軌。
4. Hook 畫面無「？？？」。
5. 進度條係頂部 3px 綠，唔係 16px 黃漫畫條。
6. cover.jpg 當海報都睇得明品牌、日期、代號、主數字。

---

## 風險

- 舊 hook 文案仍講「討論最多的是…？？？」——**旁白可照讀**，畫面唔跟「？？？」。若 Tim 要旁白都唔賣關子，先另開 VO 稿，唔喺呢包做。
- Cover 0.71s 好短；海報靠靜格，唔靠動畫。
- `chrome()` 嘅 scale pulse 我哋唔用（`#c` transform 永遠 none）。
- 長代號（GOOGL、BRK.B）會細一級字。
- PREVIEW 用 `transform: scale(0.4)` 睇；真片 1080×1920。
