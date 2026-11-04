# Tape Cats — VO ↔ reaction cue table（v1）

Aligns with `STORYBOARD-EN-v6.md`. Sample VO ~28s total（adjust to real VO length; scale cues by `t / duration`).

Assume sample:
```
0.0  open:  Everyone's yelling about $TSLA — who actually has an edge?
5.5  split: Six accounts bullish, zero bear — the crowd is long.
11.0 m1:    On X, @TrendSpider says: Algo just flashed the next $TSLA entry…
18.0 m2:    One voice. Twenty related posts on the tape today.
23.0 cta:   Full tape, free — thecrowdtape.com
28.0 end
```

| t (s) | scene | VO fragment | cat | pose / face | mouth |
|---|---|---|---|---|---|
| 0.0 | open | (enter) | Specs | `raise` | closed |
| 0.4 | open | “Everyone's yelling…” | Specs | `raise`→idle | talk cycle |
| 1.2 | open | “**$TSLA**” | Specs | `point-R` at ticker + **nod** | open |
| 2.4 | open | “who actually has an edge?” | Specs | `point-R` hold | talk |
| 5.5 | split | “Six accounts **bullish**…” | Specs | `point-L` bull side + nod | talk |
| 7.0 | split | “**zero bear**” | Specs | `point-R` bear side | half |
| 8.5 | split | “crowd is long” | Specs | `nod` | closed |
| 11.0 | m1 | “On X,” | Wave | `idle` enter | closed |
| 11.6 | m1 | “**@TrendSpider**” | Wave | `point-L/R` at handle + **surprise** | open |
| 13.0 | m1 | quote lines… | Wave | `point` hold + soft nod | talk cycle |
| 16.5 | m1 | (end quote) | Wave | `nod` | closed |
| 18.0 | m2 | “**One voice**…” | Boom | enter `idle` | talk |
| 19.5 | m2 | “**Twenty** related posts” | Boom | `nod` toward numbers | open |
| 21.0 | m2 | punch hold | Boom | prep drum | half |
| 23.0 | cta | “Full tape, free” | Boom | **`cheer`** drum／ingot up | open |
| 25.5 | cta | “thecrowdtape.com” | Boom | `cheer` hold + nod | talk |
| 27.5 | cta | end | Boom | `cheer` | closed |

### Mouth cycle while `talk`
Swap every ~90–110ms: `closed → half → open → half → closed`（pseudo lip-sync; no phoneme engine in v1）.

### Blink
Independent: every 2.8s ±0.6, duration 2 frames (~120ms), use `blink` (eyes closed, mouth inherits current).

### Head
CSS while mouth≠idle: `rotate` ±2.5° @ 1.2s + vertical bob 6px @ 2.4s.

### Wire note — Specs point-L
No `specs-point-L.png` in v1 pack. Use CSS `transform: scaleX(-1)` on `specs-point-R` for bull-side point (cue t≈5.5). Keep Wave L/R as separate files.
