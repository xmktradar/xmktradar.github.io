# Tape Cats — character bible v2（vTuber-lite）

**Ref:** `shorts-maneki-ref.jpg`  
**World:** bright cream (`token-bright.css`). No dark Bloomberg.  
**EN only.** Real `@handle` quotes — cats host／react, never invent copy.

---

## Cast

| ID | Name | Props (ref) | Hosts |
|---|---|---|---|
| `specs` | **Specs** | ¥ sunglasses · small yuanbao | Hook／ticker／metric／stance numbers |
| `wave` | **Wave** | koban 萬兩 · wave paw | Real X quote card |
| `boom` | **Boom** | den-den daiko · big yuanbao | Punch／CTA |

Look lock: white body · orange ear tips · red whiskers · red collar + gold bell · green floral bib · squint smile.

---

## vTuber motion model（Plan A PNG layers）

Not Live2D／Rive in v1 — **frame-swap PNG** (same camera lock).

### Layers / swaps
| Layer | Files | Drive |
|---|---|---|
| Body pose | `{id}-{pose}.png` | beat pose |
| Mouth | `{id}-mouth-closed\|half\|open.png` **or** full-frame `{id}-talk-*` | VO amplitude／phoneme proxy |
| Blink | `{id}-blink.png` | every 2.5–4s, 120ms |
| Head | CSS `rotate(±3deg)` + bob | continuous while talking |
| Reaction | `{id}-nod\|surprise\|point-*\|cheer` | **VO cue table** (not idle loop) |

### VO → reaction rule（Tim）
| When VO says… | Who | Reaction |
|---|---|---|
| ticker／metric／numbers／bull／bear | **Specs** | `point-*` + `nod`；mouth talk |
| `@handle`／quote lines | **Wave** | `point` at quote card + `surprise` then `nod`；mouth talk |
| punch／CTA／site | **Boom** | `cheer`（drum up／ingot）；mouth talk |

Idle bob only when not on a cue. **Cues beat loops.**

---

## Pose catalog

`idle` · `raise` · `point-L` · `point-R` · `nod` · `surprise` · `cheer` · `talk-closed` · `talk-half` · `talk-open` · `blink`

---
## Schedule
See `SCHEDULE-BEATS.md`: weekday Tape Take (Wave) / Crowd Heat (Specs→Boom); Sat Week Tape; Sun off. 30–40s.
