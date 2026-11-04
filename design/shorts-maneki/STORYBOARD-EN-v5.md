# Shorts EN v5 — Tape Cats + real X quote + bright BG

**Locks:** EN only · **#281 HOLD** · real `@handle` quote · bright cream world · maneki cast from `CHARACTER-BIBLE.md` · no dark Bloomberg · no rock parable · no comic emoji／紙屑／shake.

**Tim／CEO:** 招財貓角色講解經濟／股票／X 大神分析；亮＋有趣；指住真實引句同數字.

---

## Daily copy fields（unchanged）

`hook_q` · `ticker` · `metric` · `stance` · `quote_handle` · `quote_text` · `punch` · `cta`  
Pack map same as v3／v4. `m1.mode = 'quote'`.

---

## Visual stack
1. Bright BG — `token-bright.css` / `VISUAL-BG.md`（cream + petals／orbs）  
2. White content cards + dark ink  
3. **Tape Cats PNG sprites** layered on top（see landable plan）

---

## Beat / shot / VO / cat

| # | scene | On-screen | Cat | BG | VO |
|---|---|---|---|---|---|
| 1 | `open` | `hook_q` + `$ticker` + `metric` | **Specs** `raise`→`point-R` at metric | cream + apricot／coral petals | Question |
| 2 | `split` | bull／bear from `stance` | **Specs** between L/R blobs（or peek） | lilac→mint soft split | Stakes |
| 3 | `m1` | `ON X` · `quote_handle` · `quote_text` on white card | **Wave** `point-L/R` at quote card | lilac／lemon petals | Named real take |
| 4 | `m2` | tape numbers + `punch` | **Boom** enters `cheer`（or Wave points numbers） | quieter sky | Numbers／punch |
| 5 | `cta` | site + `@thecrowdtape` | **Boom** `cheer` + big yuanbao | mint wash + orb | CTA |

---

## Sample（illustrative）

```
hook_q:         Everyone's yelling about $TSLA — who actually has an edge?
ticker:         TSLA
metric:         6 accounts bullish
stance:         6 bull / 0 bear — crowd long
quote_handle:   @TrendSpider
quote_text:     Algo just flashed the next $TSLA entry — strategy mark 102% vs buy-and-hold 79%.
punch:          One voice. Twenty related posts on the tape today.
cta:            Full tape, free — thecrowdtape.com
```

---

## Landable for GitHub（pick · recommended A）

**A — Static PNG sprites（recommended）**  
- Commit transparent PNGs under e.g. `design/shorts-maneki/assets/`  
- Renderer composites `<img>`／canvas `drawImage` over bright BG; CSS bob／slide only  
- Matches Tim’s physical ref; regenerate with Imagine／GenerateImage once  
- Pipeline change: small — layer images by scene id  

**B — CSS-only shapes** — reject for hero cats（can’t hit sunglasses ¥／drum／yuanbao fidelity）  

**C — Lottie／Rive** — only if pipeline already ships; else slower than A  

Design delivers: bible + storyboard + ref photo + bright tokens.  
GitHub: wire A + re-render #281 sample after sprites land.  
UI 設計 can GenerateImage first sprite sheet on Tim／CEO「生成」go-ahead.
