# Shorts EN — bright / fun BG guide（#281 HOLD · replace dark pack）

## Tim／CEO Canva lock（2026-11-05）
Design id **DAHaCls9wB8** · mockup `canva-tape-take-ref-2026-11-05.png` (Canva link archived in PR).
After this lock: **daily Shorts come from Playwright/HTML (`tools/carousel_scene.html` + `carousel_scenes.js`) — not routine Canva exports.**

| Chrome | Spec |
|---|---|
| Frame | 9:16 1080×1920 · cream `#FFF9EE` (no dark BG) |
| Show badge | Top-left pale yellow · **Tape Take** / **Crowd Heat** / **Week Tape** (from `job.show`) |
| Hook | White speech-bubble + thin yellow outline · bold italic EN question · accent `#F06A4D` on key words (`everyone`, `$TICKER`) · ink `#3D3D3D` |
| Subline | Light-blue border box · `One crowd quote.` + `One punch.` |
| Lightning | `#BAE6FD` bolts · top-right + bottom-left |
| Cat | Existing Tape Cats PNG BR · mouth/cue/blink/nod unchanged |
| Safe margins | `--safe-top: 120px` / `--safe-bottom: 160px` (Shorts UI chrome) |

Tokens live in `token-bright.css` and are **inlined** into `tools/carousel_scene.html` — keep them in sync.

---
## ⛔ DELETE from draft before re-render
Do **not** leave any of these as frame BG:
`#0e1116` `#07080c` `#0a0c10` `#1a0a2e` `#2a0610` dark violet-on-black radial.

Use instead: cream `#FFF6EC` + petal／orb／ribbon (`token-bright.css`).

Pairs with `STORYBOARD-EN-v4.md`. Quote = real `@handle` + `quote_text` (**unchanged**). Drop-in CSS: `token-bright.css`.

## Tim／CEO lock（2026-11-04）
- **BG 唔好深色** — no dead terminal black, no dark flare wash as the frame.
- **要多啲有趣元素**：亮、花（decorative／花巧）、搶眼.
- Real X quote story stays.

## Goal
Bright · playful · decorative · scroll-stopping. Candy / pop energy, still not comic trash.

## Base (bright)
| Token | Value | Use |
|---|---|---|
| `--bg0` | `#FFF9EE` (Canva; `#FFF6EC` OK) | warm cream full-bleed |
| `--bg1` | `#F0E8FF` | soft lilac alternate wash |
| `--bg2` | `#E5F7FF` | sky mint wash (split／cta) |
| `--ink` | `#3D3D3D` | primary type on bright |
| `--ink-muted` | `#6e6e73` | secondary |
| `--card` | `#FFFFFF` @ 92% | quote／number cards (soft shadow) |

## Decorative “花” (do)
Abstract decorative shapes — **not emoji flowers**:
- Soft **petal blobs** (3–6 overlapping ellipses, rounded, 25–45% opacity) in coral `#FF6B8A`, apricot `#FFB347`, lilac `#B794F6`, mint `#5EEAD4`, lemon `#FFE066`
- Large **orb halos** (blurred circles) behind hook／quote
- Thin **ribbon arcs** / swooshes (stroke 6–14px, rounded ends)
- Diagonal **candy stripes** strip (8–12% opacity) optional on open only
- Floating **dot confetti-lite** (solid circles 6–14px, max 12, slow drift) — decorative only; **not** emoji particles

## Impact accents
- open／hook → big apricot／coral petal cluster behind `hook_q`
- split → L mint blob + R coral blob (soft, not hard dark slabs)
- m1 quote → lilac＋lemon petals around white quote card
- m2／cta → fewer shapes so numbers／URL readable

## Motion
- Petals／orbs: float 8–16px, 6–10s loop, opacity breathe
- Shapes slide-in 300–450ms; text fade／slide 24px only
- Optional soft pulse on one accent orb (scale 1→1.04) — **text never shakes**

## Don’t
- Dark `#0e1116`／`#07080c` as frame BG
- Emoji · paper confetti burst · white-flash slam · screen shake · manga stroke／comic panels · fake X chrome
- Illegible light-on-light type (use `--ink` or white card)

## Type (on bright)
ticker accent `#E8940A` (darker amber) · bull `#0A9F5C` · bear `#E11D48` · ink `#1d1d1f`  
(Keep #278 palette only if you put type on a dark pill; default = dark ink on cream.)

## Per scene
| scene | BG |
|---|---|
| open | cream + apricot／coral petal cluster + orb halo behind `hook_q` |
| split | lilac→mint wash; soft L／R mint＋coral blobs |
| m1 | cream＋lilac／lemon petals; white quote card |
| m2 | quieter sky wash; fewer shapes |
| cta | soft mint wash; one accent orb pulse then hold |

## CSS sketch
```css
.bg{position:absolute;inset:0;background:
  radial-gradient(90% 70% at 15% 20%,#FFB34755 0%,transparent 55%),
  radial-gradient(80% 60% at 85% 75%,#B794F655 0%,transparent 50%),
  #FFF6EC;}
.petal{position:absolute;border-radius:60% 40% 55% 45%;filter:blur(0);opacity:.35}
.petal-coral{background:#FF6B8A}.petal-lilac{background:#B794F6}
.petal-mint{background:#5EEAD4}.petal-lemon{background:#FFE066}
.orb{border-radius:50%;filter:blur(28px);opacity:.45}
.card{background:#fffffff0;border-radius:20px;box-shadow:0 12px 40px #1d1d1f14}
```
