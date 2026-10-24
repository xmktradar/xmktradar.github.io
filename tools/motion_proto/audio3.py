# Synth beat + sound effects (all generated, no samples, no copyright).
import json, sys, wave
import numpy as np
SR = 44100
J = json.load(open(sys.argv[1])); ev = J['events']; TOTAL = J['total']; DROP = J['drop']
n = int(SR * TOTAL); mus = np.zeros(n); fx = np.zeros(n)
rng = np.random.default_rng(7)
def t_(d): return np.arange(int(SR * d)) / SR
def put(buf, at, x, g=1.0):
    i = int(at * SR)
    if i >= len(buf): return
    x = x[:len(buf) - i]; buf[i:i + len(x)] += g * x
def kick():
    t = t_(.35); f = 50 + 110 * np.exp(-t * 30); return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
def clap():
    t = t_(.22); return rng.standard_normal(len(t)) * np.exp(-t * 22) * .7
def hat(open_=False):
    t = t_(.12 if open_ else .05); x = rng.standard_normal(len(t)); x = np.diff(x, prepend=0); return x * np.exp(-t * (25 if open_ else 80)) * .25
def saw(f, d):
    t = t_(d); return 2 * ((t * f) % 1) - 1
def pluck(fs, d, g=.18):
    t = t_(d); x = sum(np.tanh(2 * np.sin(2 * np.pi * f * t)) for f in fs) / len(fs); return x * np.exp(-t * 6) * g
BPM = J['bpm']; beat = 60 / BPM
prog = [[220, 261.6, 329.6], [174.6, 220, 261.6], [261.6, 329.6, 392], [196, 246.9, 293.7]]  # Am F C G
bass = [55, 43.65, 65.4, 49]
b = 0; t = 0.0
while t < DROP - 1e-6:
    put(mus, t, hat(), 1); put(mus, t + beat / 2, hat(), .8)
    t += beat
k = 0; rt = beat * 3
while rt < DROP:
    step = beat / (2 if rt < DROP - beat else 4); put(mus, rt, clap(), .25 + .5 * (rt / DROP)); rt += step
t = DROP; b = 0
while t < TOTAL:
    bar, pos = divmod(b, 4); ch = prog[bar % 4]
    if pos in (0, 2) or (pos == 3 and bar % 2): put(mus, t, kick(), .9)
    if pos == 2 and bar % 2 == 0: put(mus, t + beat * .75, kick(), .5)
    if pos in (1, 3): put(mus, t, clap(), .55)
    for k in range(2): put(mus, t + k * beat / 2, hat(k == 1 and pos == 3), 1)
    if bar >= 1 and pos % 2 == 1: put(mus, t + beat * .75, hat(), 1); put(mus, t + beat * .875, hat(), .8)
    put(mus, t, np.sin(2 * np.pi * bass[bar % 4] * t_(beat * .9)) * np.exp(-t_(beat * .9) * 2) * .55)
    if pos in (0, 1, 3): put(mus, t + (beat / 2 if pos == 1 else 0), pluck(ch, beat * .8))
    t += beat; b += 1
# sound effects
def pop(f=900):
    t = t_(.09); return np.sin(2 * np.pi * (f + 1400 * np.exp(-t * 60)) * t) * np.exp(-t * 40) * .5
def whoosh(d=.35):
    t = t_(d); x = rng.standard_normal(len(t)); env = np.sin(np.pi * t / d) ** 2
    y = np.zeros_like(x); a = 0
    for i in range(len(x)):  # sweeping one-pole low-pass
        c = .02 + .25 * t[i] / d; a += c * (x[i] - a); y[i] = a
    return y * env * 1.4
def boom():
    t = t_(.8); f = 35 + 90 * np.exp(-t * 12)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4) * 1.1 + rng.standard_normal(len(t)) * np.exp(-t * 18) * .4)
def tick(): t = t_(.03); return np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 150) * .35
def ding():
    t = t_(1.2); return sum(np.sin(2 * np.pi * f * t) * np.exp(-t * 3.5) for f in (1318.5, 1975.5, 2637)) * .25
def rise(d=.6):
    t = t_(d); return np.sin(2 * np.pi * np.cumsum(500 + 1500 * t / d) / SR) * (t / d) * np.exp(-((t - d) ** 2) * 20) * .12
def hit():
    x = boom() * .7; c = clap(); x[:len(c)] += c * .6; return x
for e in ev:
    at, ty = e['at'], e['type']
    if ty == 'slam' or ty == 'boom': put(fx, at + (.25 if ty == 'slam' else 0), boom())
    elif ty == 'bigdrop': put(fx, at, boom(), 1.2); put(fx, at, ding(), .5)
    elif ty == 'drop': put(fx, at + .1, pop(600), .6)
    elif ty == 'hit': put(fx, at, hit())
    elif ty == 'roll':
        for k in range(10): put(fx, at + k * .045, tick(), 1.4)
    elif ty in ('pop', 'wob', 'bounce'): put(fx, at, pop(800 + 150 * (int(at * 10) % 4)), .7)
    elif ty == 'whoosh': put(fx, at - .15, whoosh(), .9)
    elif ty == 'right': put(fx, at, whoosh(.25), .4)
    elif ty == 'stamp': put(fx, at, clap(), 1.3); put(fx, at, boom(), .4)
    elif ty == 'draw' or ty == 'rise': put(fx, at, rise(), 1.2)
    elif ty == 'count':
        for k in range(8): put(fx, at + k * .07, tick())
    elif ty == 'ding': put(fx, at, ding())
# duck music under the boom, fade out
mus *= .55; mix = mus + fx
fade = np.ones(n); k = int(SR * 1.2); fade[-k:] = np.linspace(1, 0, k); mix *= fade
mix = np.tanh(mix * 1.1) * .85
pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
st = np.stack([pcm, pcm], 1)
with wave.open(sys.argv[2], 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())
print('audio', sys.argv[2])
