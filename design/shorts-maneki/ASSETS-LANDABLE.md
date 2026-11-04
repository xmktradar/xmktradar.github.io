# Tape Cats — assets landable v2（vTuber-lite）

## Decision
**Plan A** locked: transparent PNG + CSS bob／head sway + **frame-swap** mouth／blink／reaction.  
No Live2D／Rive in v1（faster ship）.

## Directory
`design/shorts-maneki/assets/`

### v1 base poses（done）
```
specs-idle.png  specs-raise.png  specs-point-R.png
wave-idle.png   wave-point-L.png wave-point-R.png
boom-idle.png   boom-cheer.png
```

### v2 talking／reaction（this pass）
```
specs-talk-closed.png  specs-talk-half.png  specs-talk-open.png  specs-blink.png  specs-nod.png
wave-talk-closed.png   wave-talk-half.png   wave-talk-open.png   wave-blink.png   wave-nod.png  wave-surprise.png
boom-talk-closed.png   boom-talk-half.png   boom-talk-open.png   boom-blink.png   boom-nod.png
```

Same framing within each character’s talk／blink／nod set so swaps don’t jump.

## Wire hints
```js
// pseudo
onCue('ticker', () => setCat('specs','point-R') + nod())
onCue('handle', () => setCat('wave','surprise') → point → talkCycle())
onCue('cta',    () => setCat('boom','cheer') + talkCycle())
whileSpeaking(cat) { mouthCycle(90); headBob(); maybeBlink(); }
```

See `CUE-TABLE.md` for timestamps.

## Missing pose fallback
`specs-point-L` — not shipped; mirror `specs-point-R` with `scaleX(-1)`.
