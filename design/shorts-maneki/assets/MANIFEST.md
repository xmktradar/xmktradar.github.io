# Tape Cats sprites — v1 poses + v2 mouth/reaction

Path: `design/shorts-maneki/assets/`

## Base poses (v1)
specs-idle, specs-raise, specs-point-R  
wave-idle, wave-point-L, wave-point-R  
boom-idle, boom-cheer

## Talk / blink / reaction (v2) — frame-swap mouth
| file | use |
|---|---|
| specs-talk-closed/half/open | Specs lip-sync |
| specs-blink, specs-nod | blink / agree on numbers |
| wave-talk-closed/half/open | Wave lip-sync |
| wave-blink, wave-nod, wave-surprise | quote reactions |
| boom-talk-closed/half/open | Boom lip-sync |
| boom-blink, boom-nod | numbers / prep |
| boom-cheer | CTA (v1) |

Drive with `CUE-TABLE.md`. Cream BG via token-bright.css.

## Fallback
`specs-point-L` → CSS mirror of `specs-point-R` (`scaleX(-1)`).
