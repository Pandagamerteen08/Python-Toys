#!/usr/bin/env python3
"""beatbox.py v2 - prompt-to-beatbox engine. Pure Python standard library, no GUI.

Every mouth sound is built from a rough model of how it is made: plosive bursts,
fricative noise, resonant mouth cavities (formant filters), vibrating lips, a glottal
buzz for voiced sounds. Each hit is humanized (timing, velocity, pitch, round-robin
variants) and the mix goes through stereo panning, room reverb, a bus compressor,
soft clipping and dither.  It will not fool you into thinking a human is in the room -
for that, point --samples at a folder of real recordings (see below).

QUICK START (PowerShell / Git Bash / cmd / macOS / Linux terminal)
    python beatbox.py "fast aggressive trap 8 bars with lip roll and laser"
    python beatbox.py "dubstep song with wobble and throat bass"      # full arrangement
    python beatbox.py "boombap 90 bpm swing 60% dark no hats"
    python beatbox.py "everything"                                    # all voices at once
    python beatbox.py --list                                          # voices, styles, words
    python beatbox.py --preview s                                     # audition one voice
    python beatbox.py "garage 6 bars" --midi beat.mid --out garage.wav
    python beatbox.py "trap" --pattern k=x..x..x...x..... s=....x.......x...
    python beatbox.py "house" --samples my_recordings/                # use real sounds

PROMPT WORDS
    style   any name from --list (also hip hop, drum and bass, 2 step, ...)
    tempo   "N bpm", fast, slow, double time, half time
    length  "N bars", "song" / "full track" (intro > groove > fill > drop > outro)
    feel    swing / shuffle / "swing 60%", tight, hard / aggressive / busy / wild, laid back
    mood    dark, bright, lofi, dry, wet / huge / cavernous
    sounds  any voice keyword (lip roll, scratch, whistle, dog, laser, ...)
    remove  "no hats", "without snare"
Same prompt = same beat (seeded from the text). Use --random for a new take each time.

CUSTOM REAL SAMPLES
    --samples DIR looks for DIR/<voice>.wav, DIR/<voice>_1.wav, DIR/<voice>_2.wav ...
    (e.g. k.wav, s.wav, h.wav, lr_1.wav). 16/24-bit PCM, mono or stereo, any rate.
    Voices with a file are played from it (with humanization); the rest stay synthesized.
"""
import sys, os, re, math, wave, random, struct, hashlib, argparse, array, shutil, subprocess

SR = 44100
TAU = 2 * math.pi
RNG = random.Random(0)

# ============================================================================
#  DSP toolbox
# ============================================================================
def N(sec): return max(1, int(SR * sec))
def nz(n):
    r = RNG.random
    return [2 * r() - 1 for _ in range(n)]
def gain(x, g): return [s * g for s in x]
def norm(x, peak=1.0):
    m = max((abs(s) for s in x), default=0.0) or 1.0
    k = peak / m
    return [s * k for s in x]
def mixl(*parts):
    """parts = (signal, gain, offset_seconds) ... -> summed list."""
    n = max(len(s) + int(o * SR) for s, g, o in parts)
    out = [0.0] * n
    for s, g, o in parts:
        b = int(o * SR)
        seg = out[b:b + len(s)]
        out[b:b + len(s)] = [a + v * g for a, v in zip(seg, s)]
    return out
def env(n, atk, dec):
    a = max(atk * SR, 1.0)
    return [min(1.0, i / a) * math.exp(-i * dec / SR) for i in range(n)]
def shape(x, atk, dec): return [s * e for s, e in zip(x, env(len(x), atk, dec))]
def fade(x, ms=4):
    k = min(len(x), max(1, int(SR * ms / 1000)))
    x = list(x)
    for i in range(k): x[-1 - i] *= i / k
    return x
def sat(x, d):
    t = math.tanh(d)
    return [math.tanh(d * s) / t for s in x]

def biquad(x, kind, f, q=0.707, g=0.0):
    f = max(20.0, min(f, SR * 0.45))
    w = TAU * f / SR; cw = math.cos(w); al = math.sin(w) / (2 * q)
    if kind == "lp":   b0 = b2 = (1 - cw) / 2; b1 = 1 - cw; a0 = 1 + al; a1 = -2 * cw; a2 = 1 - al
    elif kind == "hp": b0 = b2 = (1 + cw) / 2; b1 = -(1 + cw); a0 = 1 + al; a1 = -2 * cw; a2 = 1 - al
    elif kind == "bp": b0 = al; b1 = 0.0; b2 = -al; a0 = 1 + al; a1 = -2 * cw; a2 = 1 - al
    else:  # peaking EQ
        A = 10 ** (g / 40); b0 = 1 + al * A; b1 = -2 * cw; b2 = 1 - al * A
        a0 = 1 + al / A; a1 = -2 * cw; a2 = 1 - al / A
    b0 /= a0; b1 /= a0; b2 /= a0; a1 /= a0; a2 /= a0
    y = [0.0] * len(x); x1 = x2 = y1 = y2 = 0.0
    for i, s in enumerate(x):
        o = b0 * s + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2 = x1; x1 = s; y2 = y1; y1 = o; y[i] = o
    return y
def lp(x, f, q=0.707): return biquad(x, "lp", f, q)
def hp(x, f, q=0.707): return biquad(x, "hp", f, q)
def bp(x, f, q=1.0): return biquad(x, "bp", f, q)
def pk(x, f, q, g): return biquad(x, "pk", f, q, g)

def svf_lp(x, fcs, q=0.9):
    """Chamberlin state-variable lowpass with a per-sample cutoff (wobble / filter sweeps)."""
    low = band = 0.0; d = 1 / q; out = []
    for s, fc in zip(x, fcs):
        f = 2 * math.sin(math.pi * min(fc, SR / 6) / SR)
        low += f * band; high = s - low - d * band; band += f * high; out.append(low)
    return out

VOWELS = {  # (centre Hz, bandwidth Hz) for F1..F3 - average adult male values
    "a": ((730, 90), (1090, 110), (2440, 160)), "e": ((530, 60), (1840, 100), (2480, 150)),
    "i": ((270, 60), (2290, 90), (3010, 150)), "o": ((570, 80), (840, 80), (2410, 140)),
    "u": ((300, 70), (870, 80), (2240, 140)), "@": ((500, 90), (1500, 100), (2500, 150)),
}
def formant(x, vowel, shift=1.0):
    """Push a source through the resonances of a vowel-shaped mouth."""
    out = [0.0] * len(x)
    for k, (f, bw) in enumerate(VOWELS[vowel]):
        y = bp(x, f * shift, f / bw); w = (1.0, 0.6, 0.35)[k]
        out = [o + w * s for o, s in zip(out, y)]
    return out

def voiced(dur, f0, f1=None, vib=0.0, vibhz=5.5, jitter=0.004, tilt=3500):
    """Glottal-style buzz: a sawtooth with pitch glide, vibrato and jitter, spectrally tilted."""
    n = N(dur); ph = 0.0; out = []; f1 = f0 if f1 is None else f1
    for i in range(n):
        f = (f0 + (f1 - f0) * i / n) * (1 + vib * math.sin(TAU * vibhz * i / SR) + RNG.uniform(-jitter, jitter))
        ph = (ph + f / SR) % 1.0
        out.append(2 * ph - 1)
    return lp(out, tilt)

def sweep(f0, f1, rate, dur, decay):
    ph = 0.0; out = []
    for i in range(N(dur)):
        t = i / SR
        ph += TAU * (f1 + (f0 - f1) * math.exp(-t * rate)) / SR
        out.append(math.sin(ph) * math.exp(-t * decay))
    return out

def ring(f, q, dur):
    """A struck resonance: impulse into a high-Q bandpass (mouth/tongue/lip cavities ringing)."""
    x = [0.0] * N(dur); x[0] = 1.0
    for i in range(1, min(6, len(x))): x[i] = RNG.uniform(-0.3, 0.3)
    return norm(bp(x, f, q))

# ============================================================================
#  Voices - each returns a mono list of floats. p = pitch multiplier (~1.0)
# ============================================================================
def v_kick(p):   # bilabial "b": lip pop + chest thump + closed-mouth cavity
    body = norm(sweep(150 * p, 46 * p, 36, .34, 10))
    pop = norm(shape(bp(nz(N(.03)), 650 * p, 1.1), .0006, 150))
    uh = norm(shape(formant(voiced(.14, 82 * p, tilt=520), "o"), .004, 22))
    x = lp(mixl((body, 1, 0), (pop, .5, 0), (uh, .35, 0)), 1200 * p)
    click = shape(bp(nz(N(.006)), 2300, 1.5), .0003, 650)
    return norm(sat(mixl((x, 1, 0), (norm(click), .18, 0)), 1.5), .95)
def v_kickpunch(p):  # tighter, clickier "b!" (inward lip smack on top)
    body = norm(sweep(210 * p, 55 * p, 52, .2, 15))
    pop = norm(shape(bp(nz(N(.02)), 900 * p, 1.2), .0004, 220))
    click = norm(shape(bp(nz(N(.008)), 2800, 1.2), .0002, 500))
    return norm(sat(mixl((body, 1, 0), (pop, .6, 0), (click, .3, 0)), 1.8), .95)
def v_sub(p):    # hummed/throat 808
    return norm(sat(shape(sweep(95 * p, 38 * p, 7, .8, 3.2), .003, 0), 1.6), .95)
def v_snare(p):  # "pf" - labiodental plosive: p-burst, f-fricative, cavity ring
    burst = norm(shape(bp(nz(N(.014)), 1900 * p, .9), .0004, 260))
    fric = norm(hp(shape(bp(nz(N(.2)), 4300, .5), .004, 30), 2200))
    cav = norm(shape(mixl((ring(210 * p, 7, .14), 1, 0), (ring(1650 * p, 9, .06), .5, 0)), .0005, 18))
    return norm(mixl((burst, .8, 0), (fric, .5, .004), (cav, .8, 0)), .95)
def v_spit(p):   # "psh" spit snare: sweeping affricate
    n = N(.13); x = nz(n); out = []
    for i in range(0, n, 256):
        f = (2200 + 5500 * (i / n)) * p
        out += bp(x[i:i + 256], f, .7)
    return norm(shape(out, .0008, 30), .9)
def v_inward(p): # inward "K"/clap snare: reversed airflow click
    k = norm(shape(bp(nz(N(.012)), 1500 * p, 1.4), .0003, 300))
    b = norm(shape(mixl((ring(330 * p, 8, .1), 1, 0), (ring(2100, 10, .05), .6, 0)), .0004, 28))
    return norm(mixl((k, .8, 0), (b, .7, .001)), .9)
def v_clap(p):
    parts = [(norm(shape(bp(nz(N(.03)), 1250 * p, 1.1), .0004, 140)), .8, i * RNG.uniform(.007, .012)) for i in range(3)]
    tail = norm(shape(bp(nz(N(.2)), 1250 * p, .9), .002, 20))
    return norm(mixl(*parts, (tail, .6, .02)), .9)
def v_rim(p):    # velar click "K": sharp transient + tongue-cavity resonances
    return norm(mixl((ring(1000 * p, 8, .06), 1, 0), (ring(2600 * p, 12, .04), .6, 0),
                      (shape(nz(N(.004)), .0001, 800), .25, 0)), .9)
def v_hat(p):    # tongue-tip "t"
    n = hp(bp(nz(N(.06)), 5600 * p, .7), 3200)
    return norm(shape(n, .0004, 85), .7)
def v_open(p):   # "tss"
    n = hp(bp(nz(N(.3)), 5300 * p, .5), 2800)
    tick = norm(shape(bp(nz(N(.01)), 5000, 1), .0002, 300))
    return norm(mixl((shape(n, .004, 17), 1, 0), (tick, .3, 0)), .65)
def v_shaker(p):
    return norm(shape(hp(bp(nz(N(.11)), 6600 * p, .6), 4000), .012, 32), .6)
def v_crash(p):
    n = nz(N(1.4)); a = hp(bp(n, 4000, .35), 2000)
    shimmer = [s * (.7 + .3 * math.sin(TAU * 11 * i / SR)) for i, s in enumerate(a)]
    return norm(shape(shimmer, .003, 3.4), .75)
def v_tom(p):
    return norm(sat(mixl((sweep(210 * p, 105 * p, 11, .35, 9), 1, 0),
                          (norm(shape(bp(nz(N(.02)), 700, 1), .0005, 150)), .35, 0)), 1.3), .9)
def v_cowbell(p):
    n = N(.28); a = [(1 if (540 * p * i / SR) % 1 < .5 else -1) + (1 if (810 * p * i / SR) % 1 < .5 else -1) for i in range(n)]
    return norm(shape(bp(a, 800 * p, 2.2), .0005, 13), .7)
def v_liproll(p):  # lip trill / "brrr": jittery pulse train, voiced buzz, u-vowel mouth
    dur = .6; n = N(dur); exc = [0.0] * n; t = 0.0; rate = 24.0
    while t < n:
        exc[int(t)] = RNG.uniform(.6, 1.0)
        t += SR / (rate * p) * RNG.uniform(.88, 1.12); rate = min(36.0, rate + .35)
    burst = shape(lp(nz(N(.007)), 1400), .0002, 380)
    pulses = [0.0] * (n + len(burst))
    for i, a in enumerate(exc):
        if a:
            for j, b in enumerate(burst): pulses[i + j] += a * b
    pulses = pulses[:n]
    buzz = voiced(dur, 160 * p, 190 * p, jitter=.02, tilt=1800)
    gate = lp([abs(s) for s in pulses], 60)
    x = [bz * min(1, g * 8) * .5 + pu for bz, g, pu in zip(buzz, gate, pulses)]
    return norm(shape(formant(x, "u"), .015, 3.0), .85)
def v_wobble(p):
    n = N(.55); x = voiced(.55, 55 * p, jitter=.0005, tilt=6000)
    f = [160 + 1700 * (.5 + .5 * math.sin(TAU * 5.0 * i / SR - 1.5)) for i in range(n)]
    sub = [.5 * math.sin(TAU * 55 * p * i / SR) for i in range(n)]
    y = [a + b for a, b in zip(sat(svf_lp(x, f, 1.4), 2.0), sub)]
    return norm(shape(y, .01, 1.8), .9)
def v_throat(p):  # throat/vocal-fry bass: formant-swept saw with AM
    x = voiced(.35, 62 * p, 52 * p, jitter=.01, tilt=4500); o = formant(x, "o"); a = formant(x, "a")
    y = [(o[i] * (1 - i / len(x)) + a[i] * i / len(x)) * (.65 + .35 * math.sin(TAU * 26 * i / SR)) for i in range(len(x))]
    return norm(shape(sat(y, 2.5), .006, 5), .9)
def v_trumpet(p):  # brass imitation with vibrato and bright onset
    x = voiced(.45, 392 * p, vib=.012, vibhz=5.8, jitter=.002, tilt=5200)
    x = pk(pk(x, 1250, 2, 10), 2900, 2, 7)
    return norm(shape(x, .035, 2.6), .85)
def v_scratch(p):  # "wikka": platter speed drives pitch and loudness
    n = N(.32); ph = 0.0; out = []
    for i in range(n):
        t = i / SR; sp = math.sin(TAU * 6.5 * t)
        ph += (240 + 560 * abs(sp)) * p / SR
        out.append((2 * (ph % 1) - 1) * (.12 + .88 * abs(sp)) + RNG.uniform(-.1, .1))
    return norm(shape(formant(out, "a", 1.1), .004, 4.5), .85)
def v_clickroll(p):
    t = 0.0; gap = .03; parts = []
    while t < .42:
        parts.append((ring(1900 * p, 12, .012), RNG.uniform(.7, 1), t)); t += gap; gap = max(.011, gap * .9)
    return norm(mixl(*parts), .8)
def v_dog(p):
    x = voiced(.24, 340 * p, 185 * p, jitter=.012, tilt=3200); a = formant(x, "a"); o = formant(x, "o")
    m = [a[i] * (1 - i / len(x)) + o[i] * i / len(x) for i in range(len(x))]
    gr = shape(bp(nz(N(.24)), 1800, .8), .002, 18)
    return norm(shape(mixl((m, 1, 0), (gr, .2, 0)), .006, 9), .9)
def v_laser(p):
    ph = 0.0; out = []
    for i in range(N(.3)):
        t = i / SR; ph += TAU * (180 + 3000 * math.exp(-t * 22)) * p / SR
        out.append(math.sin(ph + 2.5 * math.sin(TAU * 38 * t)) * math.exp(-t * 7))
    return norm(out, .8)
def v_drop(p):   # water drop "bloop"
    ph = 0.0; out = []
    for i in range(N(.14)):
        t = i / SR; ph += TAU * min(1900, 330 * math.exp(t * 22)) * p / SR
        out.append(math.sin(ph) * math.exp(-t * 36) * min(1, t / .002))
    return norm(out, .75)
def v_zip(p):
    n = N(.34); ph = 0.0; x = bp(nz(n), 3200, 1.0); out = []
    for i in range(n):
        ph += (60 + 150 * i / n) / SR
        out.append(x[i] * (1 if ph % 1 < .5 else .15))
    return norm(shape(out, .02, 4), .7)
def v_hum(p):
    x = voiced(.5, 118 * p, vib=.01, tilt=1000)
    return norm(shape(formant(x, "u"), .02, 3.2), .85)
def v_whistle(p):
    ph = 0.0; out = []
    for i in range(N(.4)):
        t = i / SR; ph += TAU * 2200 * p * (1 + .012 * math.sin(TAU * 5.5 * t)) * (.96 + .04 * min(1, t * 6)) / SR
        out.append(math.sin(ph))
    out = mixl((shape(out, .04, 4.5), 1, 0), (shape(bp(nz(N(.4)), 2200 * p, 8), .04, 4.5), .5, 0))
    return norm(out, .6)
def v_robot(p):
    x = voiced(.28, 110 * p, jitter=0, tilt=7000)
    x = [round(s * (1 if (30 * i / SR) % 1 < .5 else -1) * 6) / 6 for i, s in enumerate(x)]
    return norm(shape(formant(x, "a", .9), .004, 6), .8)
def v_pop(p):
    return norm(mixl((shape(bp(nz(N(.03)), 520 * p, .9), .0004, 140), 1, 0), (sweep(380 * p, 90 * p, 70, .08, 55), .8, 0)), .85)
def v_siren(p):
    ph = 0.0; out = []
    for i in range(N(.6)):
        t = i / SR; tri = abs(2 * ((2.2 * t) % 1) - 1)
        ph += TAU * (700 + 420 * tri) * p / SR; out.append(math.sin(ph) + .25 * math.sin(2 * ph))
    return norm(shape(out, .03, 2.4), .6)
def v_choke(p):
    return norm(shape(bp(nz(N(.04)), 4600 * p, 1.2), .0006, 130), .7)
def v_didge(p):  # didgeridoo: drone, lip buzz, vowel sweeping a<->u
    n = N(1.0); x = voiced(1.0, 72 * p, jitter=.002, tilt=3000)
    a = formant(x, "a", .8); u = formant(x, "u", .8)
    y = [(a[i] * (w := .5 + .5 * math.sin(TAU * 2.2 * i / SR)) + u[i] * (1 - w)) * (.75 + .25 * math.sin(TAU * 8 * i / SR)) for i in range(n)]
    return norm(shape(sat(y, 1.8), .05, 1.0), .85)
def v_mouthbass(p):
    x = lp(voiced(.4, 65 * p, 60 * p, jitter=.004, tilt=900), 700)
    return norm(shape(sat(formant(x, "o", .8), 2.0), .008, 5), .9)
def v_breath(p):  # inhale "hhh" - the natural gap-filler between phrases
    x = hp(bp(nz(N(.4)), 1800, .5), 500)
    e = [math.sin(math.pi * min(1.0, (i / len(x)) ** .7)) ** 2 for i in range(len(x))]
    return norm([a * b for a, b in zip(x, e)], .45)

# key: (fn, gain, pan, description, keyword regex, default 16-step pattern, GM drum note)
VOICES = {
    "k":   (v_kick,      1.00,  0.0, "kick 'b'",              r"\bkick\b|\bboots\b",          "x.......x.......", 36),
    "kp":  (v_kickpunch, .90,   0.0, "punch kick 'b!'",       r"punch|\bkick ?drum\b",        "x.....x.....x...", 35),
    "sub": (v_sub,       .80,   0.0, "808 / sub drop",        r"808|\bsub\b|bass ?drop",      "x.......x.......", 36),
    "s":   (v_snare,     .95,   0.0, "snare 'pf'",            r"\bsnare\b|\bpf\b",            "....x.......x...", 38),
    "sp":  (v_spit,      .70,   .1,  "spit snare 'psh'",      r"spit|psh",                    "..............x.", 40),
    "si":  (v_inward,    .80,  -.1,  "inward snare / K-snare", r"inward|reverse snare",       "......x.......x.", 40),
    "cl":  (v_clap,      .80,   0.0, "clap",                  r"clap",                        "....x.......x...", 39),
    "rim": (v_rim,       .70,  -.2,  "rimshot / click 'tk'",  r"\brim|\btk\b",                "..x.......x...x.", 37),
    "h":   (v_hat,       .55,   .3,  "closed hat 't'",        r"hi ?hat|\bhats?\b",           "x.x.x.x.x.x.x.x.", 42),
    "o":   (v_open,      .55,   .35, "open hat 'tss'",        r"open ?hat|\btss\b",           "..x.......x.....", 46),
    "ts":  (v_shaker,    .50,  -.3,  "shaker 'ts'",           r"shaker|\bts\b",               "x.x.x.x.x.x.x.x.", 70),
    "cr":  (v_crash,     .60,   .1,  "crash 'tsshh'",         r"crash|cymbal",                "x...............", 49),
    "tm":  (v_tom,       .85,  -.25, "tom",                   r"\btoms?\b",                   "............x.x.", 45),
    "cb":  (v_cowbell,   .45,   .25, "cowbell",               r"cowbell|\bbell\b",            "x.x...x.x...x...", 56),
    "lr":  (v_liproll,   .70,   0.0, "lip roll 'brrr'",       r"lip ?roll|trill|brr",         "..............x.", 54),
    "wub": (v_wobble,    .75,   0.0, "wobble bass",           r"wub|wobble",                  "x.......x.x.....", 36),
    "tb":  (v_throat,    .80,   0.0, "throat bass / growl",   r"throat|growl",                "x..x..x.........", 36),
    "tr":  (v_trumpet,   .55,   .15, "trumpet / brass",       r"trumpet|brass|horn",          "x.......x.......", 56),
    "sc":  (v_scratch,   .65,  -.15, "vocal scratch 'wikka'", r"scratch|\bdj\b",              "......x.......x.", 56),
    "cr2": (v_clickroll, .65,   .2,  "click roll",            r"click",                       "x...x.......x...", 75),
    "dg":  (v_dog,       .70,   0.0, "dog bark 'woof'",       r"\bdogs?\b|bark|woof",         "......x.........", 56),
    "lz":  (v_laser,     .55,   .3,  "laser 'pew'",           r"laser|zap|pew",               "..........x.....", 56),
    "wd":  (v_drop,      .55,  -.3,  "water drop 'bloop'",    r"water|bloop|\bdrops?\b",      "..x.......x.....", 56),
    "zip": (v_zip,       .50,   0.0, "zipper",                r"zip",                         "..............x.", 56),
    "hm":  (v_hum,       .65,   0.0, "humming bass",          r"\bhum",                       "x...............", 56),
    "wh":  (v_whistle,   .40,   .2,  "whistle",               r"whistle",                     "....x...........", 56),
    "rb":  (v_robot,     .55,   0.0, "robot / vocoder voice", r"robot|vocoder",               "..x...x.........", 56),
    "pop": (v_pop,       .70,   0.0, "lip pop",               r"\bpops?\b",                   "x.x.....x.x.....", 56),
    "sir": (v_siren,     .45,   0.0, "siren",                 r"siren",                       "x...............", 56),
    "ch":  (v_choke,     .55,   .3,  "choke 'kss'",           r"choke|\bkss\b",               "...x.......x....", 44),
    "dj":  (v_didge,     .70,   0.0, "didgeridoo drone",      r"didge|didgeridoo",            "x...............", 56),
    "mb":  (v_mouthbass, .85,   0.0, "mouth bass pluck",      r"mouth ?bass|bass ?pluck",     "x..x......x.....", 36),
    "br":  (v_breath,    .50,   0.0, "inhale / breath",       r"breath|inhale",               "..............x.", 56),
}
GROUPS = {"o": ("h", "ch")}  # open hat is choked by closed hat / choke sounds

# ============================================================================
#  Styles: bpm, beats per bar, layers {voice: pattern}. Pattern length = steps per bar.
# ============================================================================
S16 = lambda **kw: kw
STYLES = {
    "classic":   (95, 4, S16(k="x.....x.x.......", s="....x.......x...", h="x.x.x.x.x.x.x.x.", o="..............x.")),
    "boombap":   (90, 4, S16(k="x.....x...x.....", s="....x.......x...", h="x.x.x.x.x.x.x.x.", sp="..............x.")),
    "trap":      (140, 4, S16(k="x.......x..x....", s="........x.......", h="x.x.xxx.x.x.xxx.", o="......x......x..", sub="x.......x.......")),
    "drill":     (144, 4, S16(k="x.....x...x.....", s="........x.......", h="x.x.x.xxx.x.x.x.", sub="x.....x.........")),
    "grime":     (140, 4, S16(k="x.....x.....x...", s="........x.......", h="x.x.x.x.x.x.x.x.", cl="........x.......", sub="x..........x....")),
    "dnb":       (172, 4, S16(k="x.........x.....", s="....x.......x...", h="x.x.x.x.x.x.x.x.", o="......x.........")),
    "jungle":    (165, 4, S16(k="x.x.......x.....", s="....x..x.x..x...", h="x.xxx.x.xx.xx.x.", ts="..x.......x.....")),
    "breakbeat": (130, 4, S16(k="x.....x...x.x...", s="....x.......x..x", h="x.x.x.x.x.x.x.x.", o="..x.......x.....")),
    "garage":    (132, 4, S16(k="x.........x.....", s="....x.......x...", h="x.x.x.x.x.x.x.x.", o="..x.......x.....", sp="..........x..x..")),
    "house":     (124, 4, S16(k="x...x...x...x...", cl="....x.......x...", o="..x...x...x...x.", h="x.x.x.x.x.x.x.x.")),
    "techno":    (135, 4, S16(k="x...x...x...x...", ts="x.x.x.x.x.x.x.x.", h="..x...x...x...x.", rb="..........x.....")),
    "trance":    (138, 4, S16(k="x...x...x...x...", cl="....x.......x...", o="..x...x...x...x.", ts="x.x.x.x.x.x.x.x.", sub="x...x...x...x...")),
    "hardstyle": (150, 4, S16(kp="x...x...x...x...", sub="..x...x...x...x.", cl="....x.......x...", o="..x...x...x...x.", h="x.x.x.x.x.x.x.x.")),
    "dubstep":   (140, 4, S16(k="x.........x.....", s="........x.......", wub="x.......x.x.....", h="..x...x...x...x.")),
    "reggaeton": (95, 4, S16(k="x...x...x...x...", s="...x..x....x..x.", h="x.x.x.x.x.x.x.x.")),
    "funk":      (105, 4, S16(k="x..x..x...x.x...", s="....x..x.x..x..x", h="x.xxx.xxx.xxx.xx", o="..x.......x.....")),
    "afrobeat":  (112, 4, S16(k="x.....x...x.....", s="....x.......x...", cb="x..x..x...x.x...", ts="x.x.x.x.x.x.x.x.")),
    "bossa":     (92, 4, S16(k="x..x..x.x..x..x.", rim="x..x..x...x..x..", h="x.x.x.x.x.x.x.x.")),
    "lofi":      (75, 4, S16(k="x.....x...x.....", s="........x.......", h="x.x.x.x.x.x.x.x.", hm="......x.........", pop="..x.......x.x...")),
    "footwork":  (160, 4, S16(k="x..x..x...x..x..", s="....x.......x...", cl="..x..x..x..x..x.", h="x.x.x.x.x.x.x.x.")),
    "halftime":  (70, 4, S16(k="x.........x.....", s="........x.......", h="x...x...x...x...", o="......x.........")),
    "oldschool": (100, 4, S16(k="x.....x...x.....", s="....x.......x...", cl="....x.......x...", h="x.x.x.x.x.x.x.x.", tm="..............x.")),
    "shuffle":   (100, 4, S16(k="x.....x.....", s="...x.....x..", h="x.xx.xx.xx.x")),
    "waltz":     (138, 3, S16(k="x...........", s="....x...x...", h="x.x.x.x.x.x.")),
    "showcase":  (110, 4, S16(kp="x.....x...x.....", s="....x.......x...", sp="..x.......x.....", si="......x.........",
                              h="x.x.x.x.x.x.x.x.", o="..............x.", lr="..........x.....", sc="..............x.", cr2="x...............")),
}
SYN = [
    (r"boom ?bap|hip ?hop|\brap\b|rapper", "boombap"), (r"drum ?(and|n|&) ?bass|\bd ?& ?b\b|\bdnb\b", "dnb"),
    (r"old ?school", "oldschool"), (r"half ?time", "halftime"), (r"lo ?-?fi|\bchill\b", "lofi"),
    (r"juke|ghetto", "footwork"), (r"dembow|latin|perreo", "reggaeton"), (r"\bbreaks?\b|\bbreakbeats?\b", "breakbeat"),
    (r"\bedm\b|dance|four on the floor", "house"), (r"2 ?-?step|two ?step|\buk\b", "garage"), (r"dub ?step|\bdub\b|brostep", "dubstep"),
    (r"blues|swung|triplet", "shuffle"), (r"3/4|three four|vals", "waltz"), (r"hard ?dance|gabber|\bhard ?core\b", "hardstyle"),
    (r"afro|highlife", "afrobeat"), (r"bossa|samba|brazil", "bossa"), (r"uk drill|\bdrill\b", "drill"), (r"all ?styles|demo|show ?off", "showcase"),
]

def resample_pat(pat, steps):
    if len(pat) == steps: return pat
    out = ["."] * steps
    for i, c in enumerate(pat):
        if c == "x": out[min(steps - 1, round(i * steps / len(pat)))] = "x"
    return "".join(out)

def style_steps(name): return len(next(iter(STYLES[name][2].values())))
for _n, (_b, _be, _p) in STYLES.items():
    assert len({len(v) for v in _p.values()}) == 1, "pattern lengths differ in " + _n
assert all(len(v[5]) == 16 for v in VOICES.values())

# ============================================================================
#  Prompt parsing
# ============================================================================
def md5int(s): return int(hashlib.md5(s.encode()).hexdigest(), 16)

def parse(prompt, a):
    p = prompt.lower()
    seed = a.seed if a.seed is not None else (random.SystemRandom().randrange(2**32) if a.random else md5int(p) % 2**32)
    hits = [(m.start(), s) for s in STYLES for m in [re.search(r"\b" + s + r"s?\b", p)] if m]
    hits += [(m.start(), s) for rx, s in SYN for m in [re.search(rx, p)] if m]
    style = min(hits)[1] if hits else None
    if style is None:
        names = [s for s in STYLES if s != "showcase"]; style = names[seed % len(names)]
    bpm0, beats, layers = STYLES[style]; bpm = bpm0
    m = re.search(r"(\d{2,3})\s*bpm", p)
    if a.bpm: bpm = a.bpm
    elif m: bpm = int(m.group(1))
    else:
        if re.search(r"double ?time", p): bpm *= 2 if bpm < 100 else 1
        if re.search(r"half ?time", p) and style != "halftime": bpm = bpm / 2 if bpm > 110 else bpm
        if re.search(r"very fast|crazy fast|insane", p): bpm += 40
        elif re.search(r"\bfast|\bquick|energetic|upbeat", p): bpm += 18
        if re.search(r"very slow|super slow", p): bpm -= 30
        elif re.search(r"\bslow|\bsleepy|relax", p): bpm -= 16
    bpm = max(50, min(int(bpm), 240))
    song = bool(a.song or re.search(r"\bsong\b|full track|arrangement|whole track|\btrack\b", p))
    m = re.search(r"(\d+)\s*bars?", p)
    bars = a.bars or (int(m.group(1)) if m else (16 if song else 4)); bars = max(1, min(bars, 64))
    m = re.search(r"swing\s*(\d{1,3})\s*%", p)
    swing = int(m.group(1)) / 100 * .5 if m else (.17 if re.search(r"swing|groove|bounce|shuffle|laid ?back", p) else 0.0)
    laid = bool(re.search(r"laid ?back|lazy|behind the beat", p))
    busy = bool(re.search(r"hard|aggressive|wild|busy|chaotic|insane|crazy|frantic", p))
    tight = bool(re.search(r"tight|robotic|quantized|machine", p))
    mood = {k: bool(re.search(k, p)) for k in ("dark", "bright", "lofi|lo-fi|dusty|vintage", "dry|close|intimate", "wet|huge|cavernous|hall|space")}
    dry_or_wet = "dry" if mood["dry|close|intimate"] else ("hall" if mood["wet|huge|cavernous|hall|space"] or mood["dark"] else a.room)
    pats = {v: resample_pat(pt, len(next(iter(layers.values())))) for v, pt in layers.items()}
    steps = len(next(iter(pats.values())))
    allv = re.search(r"everything|kitchen sink|\ball sounds\b|every sound|every kind|all the sounds|loaded", p)
    extras = []
    for v, (_, _, _, _, rx, pat, _) in VOICES.items():
        if (allv or re.search(rx, p)) and v not in pats:
            pats[v] = resample_pat(pat, steps); extras.append(v)
    for m in re.finditer(r"(?:\bno|without|minus|\bnot|skip)\s+(?:any\s+)?([a-z ]{2,18})", p):
        words = m.group(1)
        for v, (_, _, _, _, rx, _, _) in VOICES.items():
            if re.search(rx, words) and v in pats and len(pats) > 1: pats.pop(v); extras = [e for e in extras if e != v]
    for spec in a.pattern or []:
        k, _, pt = spec.partition("=")
        if k in VOICES and pt:
            pats[k] = resample_pat(pt.replace("-", ".").lower(), steps)
    if not pats: pats["k"] = resample_pat(VOICES["k"][5], steps)
    return dict(style=style, bpm=bpm, beats=beats, steps=steps, bars=bars, swing=swing, busy=busy, tight=tight,
                mood=mood, laid=laid, room=dry_or_wet, pats=pats, extras=extras, song=song, seed=seed)

# ============================================================================
#  Arrangement: pattern -> events (position in steps, voice, velocity, pitch multiplier)
# ============================================================================
CORE0 = {"k", "kp", "sub", "h", "ts", "mb"}; CORE1 = CORE0 | {"s", "cl", "rim", "sp"}
def section_plan(bars, song):
    """Return per-bar intensity 0..3 and fill flags."""
    if not song: return [2] * bars, set(range(3, bars, 4))
    plan = []
    intro = min(2, max(1, bars // 8)); outro = 1 if bars >= 8 else 0
    body = bars - intro - outro
    for i in range(bars):
        if i < intro: plan.append(0)
        elif i >= bars - outro: plan.append(1)
        else:
            j = i - intro; frac = j / max(1, body)
            plan.append(1 if frac < .2 else 2 if frac < .5 else 0 if frac < .58 else 3)
    fills = {i for i in range(3, bars - 1, 4)} | {intro - 1 if intro else 0}
    fills.add(max(0, bars - outro - 1))
    return plan, {f for f in fills if 0 <= f < bars}

def make_fill(rng, steps, voices_have):
    ev = []; q = steps // 4
    kind = rng.choice(["snare", "tom", "kick", "hat", "mixed"])
    if kind == "snare" or (kind == "tom" and "tm" not in voices_have):
        for i in range(q * 3, steps):
            ev.append((i, "s", .55 + .45 * (i - q * 3) / q, 1.0))
            ev.append((i + .5, "s", .4 + .3 * (i - q * 3) / q, 1.0))
    elif kind == "tom":
        for k, pitch in enumerate((1.2, 1.1, .95, .8)):
            ev.append((q * 3 + k * q / 4, "tm", .9, pitch))
        ev.append((steps - 1, "tm", 1.0, .72))
    elif kind == "kick":
        for i in (q * 3, q * 3 + 1, q * 3 + 2, q * 3 + 3):
            ev.append((i, "kp", .9, 1.0)); ev.append((i + .5, "sp", .6, 1.0))
    elif kind == "hat":
        for k in range(q * 2):
            ev.append((q * 3 + k / 2, "h", .4 + .6 * k / (q * 2), 1.0))
    else:
        ev += [(q * 3, "s", .8, 1.0), (q * 3 + 1, "s", .7, 1.0), (q * 3 + 2, "kp", 1.0, 1.0), (q * 3 + 3, "s", 1.0, 1.0),
               (steps - .5, "br", .6, 1.0)]
    return ev

def hat_velocity(i, steps, rng):
    spb = steps / 4
    if i % spb == 0: v = 1.0
    elif i % (spb / 2) == 0: v = .78
    else: v = .56
    return v * rng.uniform(.88, 1.06)

def arrange(cfg, rng):
    steps, bars, pats = cfg["steps"], cfg["bars"], cfg["pats"]
    plan, fills = section_plan(bars, cfg["song"])
    ev = []; var = .55 if cfg["busy"] else (0.0 if cfg["tight"] else .3)
    fillable = {"k", "kp", "h", "ts", "rim", "pop", "o", "tm", "cb"}
    for b in range(bars):
        lvl = plan[b]
        for v, pat in pats.items():
            if lvl == 0 and v not in CORE0: continue
            if lvl == 1 and v not in CORE1 and not (cfg["song"] is False): continue
            if v in cfg["extras"] and lvl < 2: continue
            row = list(pat)
            if rng.random() < var and v in fillable:  # bar mutation: nudge one non-anchor step
                i = rng.randrange(steps)
                if i != 0:
                    if row[i] == "." and v in {"k", "kp", "rim", "pop", "tm", "cb", "h", "ts"}: row[i] = "x"
                    elif row[i] == "x" and v in {"h", "ts", "o", "pop", "cb"}: row[i] = "."
            for i, c in enumerate(row):
                if c != "x": continue
                vel = hat_velocity(i, steps, rng) if v in ("h", "ts") else rng.uniform(.9, 1.0)
                if v in ("k", "kp", "s", "cl") and i == 0 and b % 4 == 0: vel = 1.0
                ev.append((b * steps + i, v, vel, 1.0))
        ghost = .06 + (.14 if cfg["busy"] else 0)
        if lvl >= 2:  # ghost notes: tiny kicks / hats between the main hits, only where nothing else sits
            for v in ("k", "h"):
                if v in pats:
                    for i in range(steps):
                        if pats[v][i] != "x" and not any(pats.get(x, "." * steps)[i] == "x" for x in ("s", "cl")) and rng.random() < ghost / 2:
                            ev.append((b * steps + i, v, rng.uniform(.28, .45), 1.0))
        if b in fills and lvl >= 1 and (b + 1 < bars or not cfg["song"]):
            f = make_fill(rng, steps, pats)
            cut = steps * 3 // 4
            ev = [e for e in ev if not (b * steps + cut <= e[0] < (b + 1) * steps and e[1] in ("k", "kp", "s", "cl", "h", "ts", "rim", "sp", "si"))]
            ev += [(b * steps + pos, v, vel, pit) for pos, v, vel, pit in f]
        if cfg["song"] and lvl == 3 and (b == 0 or plan[b - 1] != 3) and "cr" in VOICES:
            ev.append((b * steps, "cr", 1.0, 1.0))  # crash on the drop
        if cfg["song"] and b == bars - 1 and "cr" not in pats:
            ev.append((b * steps, "cr", .8, 1.0))
        if (b % 4 == 3) and "br" in pats: ev.append((b * steps + steps - 2, "br", .6, 1.0))
    return ev

# ============================================================================
#  Rendering
# ============================================================================
_cache = {}
_samples = {}
def load_wav(path):
    with wave.open(path, "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes(); raw = w.readframes(n)
    if sw == 2: vals = struct.unpack("<%dh" % (len(raw) // 2), raw); sc = 32768.0
    elif sw == 3: vals = [int.from_bytes(raw[i:i + 3], "little", signed=True) for i in range(0, len(raw), 3)]; sc = 8388608.0
    elif sw == 1: vals = [b - 128 for b in raw]; sc = 128.0
    else: raise ValueError("only 8/16/24-bit PCM WAV supported: " + path)
    mono = [sum(vals[i:i + ch]) / ch / sc for i in range(0, len(vals) - ch + 1, ch)]
    if sr != SR:
        out = []; r = sr / SR
        for i in range(int(len(mono) / r)):
            x = i * r; j = int(x); f = x - j
            out.append(mono[j] * (1 - f) + mono[min(j + 1, len(mono) - 1)] * f)
        mono = out
    return norm(mono, .95)

def scan_samples(d):
    for f in sorted(os.listdir(d)):
        m = re.fullmatch(r"([a-z0-9]+?)(?:_\d+)?\.wav", f.lower())
        if m and m.group(1) in VOICES:
            _samples.setdefault(m.group(1), []).append(load_wav(os.path.join(d, f)))

def render_voice(v, variant, pitch):
    key = (v, variant, round(pitch, 2))
    if key not in _cache:
        if v in _samples:
            s = _samples[v][variant % len(_samples[v])]
            if abs(pitch - 1) > .02:  # cheap pitch shift by resampling
                s = [s[min(len(s) - 1, int(i * pitch))] for i in range(int(len(s) / pitch))]
            _cache[key] = s
        else:
            RNG.seed(md5int("%s%d" % (v, variant)) % 2**32)
            _cache[key] = fade(VOICES[v][0](pitch * (1 + (variant - 1) * .022)), 6)
    return _cache[key]

def reverb(L, R, wet=.14, size=1.0, predelay=.012):
    """Freeverb-style: damped parallel combs into series allpasses, decorrelated per channel."""
    n = len(L); mono = [(a + b) * .5 for a, b in zip(L, R)]; pd = int(predelay * SR); k = SR / 44100 * size
    def chan(offset):
        out = [0.0] * n
        for d, fb in ((1116, .84), (1188, .83), (1277, .82), (1356, .81)):
            d = int((d + offset) * k); buf = [0.0] * d; idx = 0; lpv = 0.0; damp = .5
            for i in range(pd, n):
                y = buf[idx]; lpv = y * (1 - damp) + lpv * damp
                buf[idx] = mono[i - pd] + lpv * fb; idx = idx + 1 if idx + 1 < d else 0
                out[i] += y * .25
        for d in (556, 441):
            d = int((d + offset // 2) * k); buf = [0.0] * d; idx = 0
            for i in range(n):
                z = buf[idx]; x = out[i]; buf[idx] = x + z * .5; out[i] = z - x * .5 + z * .0
                idx = idx + 1 if idx + 1 < d else 0
        return out
    wl, wr = chan(0), chan(23)
    return [a + wet * b for a, b in zip(L, wl)], [a + wet * b for a, b in zip(R, wr)]

def compress(L, R, thr=.4, ratio=3.2, atk=.004, rel=.09):
    a = math.exp(-1 / (atk * SR)); r = math.exp(-1 / (rel * SR)); e = 0.0
    for i in range(len(L)):
        lv = max(abs(L[i]), abs(R[i]))
        e = a * e + (1 - a) * lv if lv > e else r * e + (1 - r) * lv
        if e > thr:
            g = (thr + (e - thr) / ratio) / e; L[i] *= g; R[i] *= g
    return L, R

def render(cfg, ev, rng, humanize=1.0, dry=False):
    steps_per_beat = cfg["steps"] / cfg["beats"]; step = 60 / cfg["bpm"] / steps_per_beat
    total_steps = cfg["bars"] * cfg["steps"]; tail = 2.5 if cfg["room"] != "dry" else .8
    n = int(SR * (total_steps * step + tail)); L = [0.0] * n; R = [0.0] * n
    ev = sorted(ev, key=lambda e: e[0]); starts = {}
    for pos, v, vel, pit in ev: starts.setdefault(v, []).append(pos)
    mood = cfg["mood"]; shift = .9 if mood["dark"] else (1.08 if mood["bright"] else 1.0)
    for pos, v, vel, pit in ev:
        fn, g, pan, *_ = VOICES[v]
        swing = cfg["swing"] * step if (cfg["steps"] % 4 == 0 and int(pos) % 2 == 1 and pos == int(pos)) else 0.0
        jit = (rng.uniform(-.002, .002) if v in ("k", "kp", "sub") else rng.uniform(-.004, .004)) * humanize
        lag = (.003 if v in ("s", "cl") else 0.0) * humanize * (3.0 if cfg.get("laid") else 1.0)
        t = max(0.0, pos * step + swing + jit + lag)
        sig = render_voice(v, rng.randrange(3), pit * (shift if v in ("k", "kp", "tm", "sub", "s") else 1.0))
        if v in GROUPS:  # choke: cut this sound when a chokers hits
            nxt = [q for c in GROUPS[v] for q in starts.get(c, []) if q > pos]
            if nxt:
                cut = int((min(nxt) - pos) * step * SR); sig = fade(sig[:max(80, cut)], 4)
        b = int(t * SR); sig = sig[:max(0, n - b)]
        if not sig: continue
        pl = max(-1, min(1, pan + rng.uniform(-.05, .05) * humanize)); gl = math.cos((pl + 1) * math.pi / 4); gr = math.sin((pl + 1) * math.pi / 4)
        k = g * vel * (1.0 if v != "o" else .9)
        seg = L[b:b + len(sig)]; L[b:b + len(sig)] = [a + s * k * gl for a, s in zip(seg, sig)]
        seg = R[b:b + len(sig)]; R[b:b + len(sig)] = [a + s * k * gr for a, s in zip(seg, sig)]
    if mood["lofi|lo-fi|dusty|vintage"]:
        L, R = lp(L, 6500), lp(R, 6500)
        L = [round(s * 24) / 24 * .6 + s * .4 for s in L]; R = [round(s * 24) / 24 * .6 + s * .4 for s in R]
        L = [s + RNG.uniform(-.004, .004) for s in L]; R = [s + RNG.uniform(-.004, .004) for s in R]
    if not dry and cfg["room"] != "dry":
        wet, size = {"small": (.09, .7), "studio": (.11, 1.0), "hall": (.26, 1.9)}.get(cfg["room"], (.14, 1.0))
        L, R = reverb(L, R, wet, size)
    L, R = compress(L, R)
    pk_ = max(max(abs(s) for s in L), max(abs(s) for s in R)) or 1.0; k = .89 / pk_
    L = [math.tanh(s * k * 1.1) / math.tanh(1.1) for s in L]; R = [math.tanh(s * k * 1.1) / math.tanh(1.1) for s in R]
    end = n
    while end > 1 and abs(L[end - 1]) < 1e-4 and abs(R[end - 1]) < 1e-4: end -= 1
    return L[:end + int(.1 * SR)], R[:end + int(.1 * SR)]

def write_wav(path, L, R):
    rnd = random.Random(1).random; out = array.array("h")
    for a, b in zip(L, R):
        out.append(max(-32768, min(32767, int(a * 32767 + (rnd() - rnd())))))
        out.append(max(-32768, min(32767, int(b * 32767 + (rnd() - rnd())))))
    if sys.byteorder == "big": out.byteswap()
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(out.tobytes())

def write_midi(path, ev, cfg):
    tpb = 480; steps_per_beat = cfg["steps"] / cfg["beats"]; tps = tpb / steps_per_beat
    def vlq(n):
        b = [n & 127]; n >>= 7
        while n: b.append((n & 127) | 128); n >>= 7
        return bytes(reversed(b))
    items = []
    for pos, v, vel, pit in ev:
        t = int(pos * tps); note = VOICES[v][6]
        items.append((t, 0x99, note, max(1, min(127, int(vel * 110))))); items.append((t + int(tps * .9), 0x89, note, 0))
    items.sort(key=lambda e: (e[0], e[1] == 0x99))
    trk = b"\x00\xff\x51\x03" + int(60_000_000 / cfg["bpm"]).to_bytes(3, "big")
    trk += b"\x00\xff\x58\x04" + bytes([cfg["beats"], 2, 24, 8]); last = 0
    for t, st, nt, vl in items: trk += vlq(t - last) + bytes([st, nt, vl]); last = t
    trk += b"\x00\xff\x2f\x00"
    with open(path, "wb") as fh:
        fh.write(b"MThd" + struct.pack(">IHHH", 6, 0, 1, tpb) + b"MTrk" + struct.pack(">I", len(trk)) + trk)

def score(cfg, ev, all_bars):
    steps = cfg["steps"]; rows = {}
    show = range(cfg["bars"] if all_bars else 1)
    for b in show:
        for v in cfg["pats"]: rows.setdefault(v, [])
    lines = []
    used = {vv for pos, vv, *_ in ev if int(pos // steps) in show}
    for v in sorted((r for r in rows if r in used), key=lambda x: list(VOICES).index(x)):
        s = ""
        for b in show:
            cells = ["."] * steps
            for pos, vv, vel, _ in ev:
                if vv == v and b * steps <= pos < (b + 1) * steps:
                    cells[int(pos - b * steps)] = "x" if vel > .5 else "o"
            s += "".join(cells) + " | "
        lines.append(f"{v:<4} {s}")
    return "\n".join(lines)

def play(path):
    if os.name == "nt":
        import winsound; winsound.PlaySound(path, winsound.SND_FILENAME)
    else:
        for cmd in (["afplay"], ["paplay"], ["aplay", "-q"], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]):
            if shutil.which(cmd[0]):
                subprocess.run(cmd + [path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); return

def list_all():
    print("STYLES:", ", ".join(STYLES))
    print("\nVOICES (key | keyword regex | description):")
    for v, t in VOICES.items(): print(f"  {v:<4} {t[4]:<30} {t[3]}")
    print("\nWORDS: fast slow 'N bpm' 'N bars' song swing 'swing 60%' tight busy dark bright lofi dry huge  'no hats'  everything")

def main():
    global SR
    ap = argparse.ArgumentParser(description="Prompt-to-beatbox beat engine", epilog="Example: python beatbox.py \"fast trap 8 bars with lip roll\"")
    ap.add_argument("prompt", nargs="*", help="describe the beat in plain words")
    ap.add_argument("--out", default="beat.wav"); ap.add_argument("--midi", help="also write a drum MIDI file")
    ap.add_argument("--bpm", type=int); ap.add_argument("--bars", type=int); ap.add_argument("--song", action="store_true")
    ap.add_argument("--seed", type=int); ap.add_argument("--random", action="store_true", help="new random take every run")
    ap.add_argument("--room", choices=["dry", "small", "studio", "hall"], default="studio")
    ap.add_argument("--rate", type=int, default=44100, help="sample rate (22050 renders ~4x faster)")
    ap.add_argument("--humanize", type=float, default=1.0, help="0 = robot-perfect, 1 = human, 2 = drunk")
    ap.add_argument("--pattern", nargs="+", metavar="V=xxxx", help="override voices, e.g. k=x...x... s=....x...")
    ap.add_argument("--samples", metavar="DIR"); ap.add_argument("--preview", metavar="VOICE", help="audition one voice")
    ap.add_argument("--score", action="store_true", help="print every bar, not just the first")
    ap.add_argument("--no-play", "--noplay", dest="noplay", action="store_true"); ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list: return list_all()
    SR = a.rate
    if a.samples: scan_samples(a.samples); print("loaded samples for:", ", ".join(sorted(_samples)) or "(none found)", file=sys.stderr)
    if a.preview:
        if a.preview not in VOICES: sys.exit("unknown voice; try --list")
        sig = []; gap = [0.0] * int(SR * .15)
        for var in range(3): sig += list(render_voice(a.preview, var, 1.0)) + gap
        sig = [s * VOICES[a.preview][1] * .9 for s in sig]
        write_wav(a.out, sig, sig); print(f"{VOICES[a.preview][3]} x3 variants -> {a.out}")
        if not a.noplay: play(a.out)
        return
    prompt = " ".join(a.prompt) or _read_long("Beat prompt (or @file.md, or <<< to paste lots of text): ")
    cfg = parse(prompt, a); rng = random.Random(cfg["seed"])
    ev = arrange(cfg, rng)
    ev = [e for e in ev if e[1] in cfg["pats"] or e[1] in ("s", "kp", "sp", "tm", "br", "cr", "h")]
    print(f"rendering: {cfg['style']} | {cfg['bpm']} bpm | {cfg['bars']} bars{' | song' if cfg['song'] else ''} | {len(ev)} hits | room={cfg['room']}", file=sys.stderr)
    L, R = render(cfg, ev, rng, a.humanize)
    write_wav(a.out, L, R)
    if a.midi: write_midi(a.midi, ev, cfg)
    print(f"\n{cfg['style']} | {cfg['bpm']} bpm | {cfg['bars']} bars | {len(L) / SR:.1f}s -> {a.out}" + (f" + {a.midi}" if a.midi else "") + "\n")
    print(score(cfg, ev, a.score))
    if cfg["song"]:
        pl = section_plan(cfg["bars"], True)[0]; seen = False; letters = []
        for x in pl:
            if x != 0: seen = True
            letters.append("ibgfD"[(1 if seen else 0) if x == 0 else x + 1] if x else ("b" if seen else "i"))
        print("\narrangement:", " ".join(letters), " (i=intro b=breakdown g=groove f=full D=drop)")
    if not a.noplay: play(a.out)


# ---------------------------------------------------------------------------
# Launcher. Makes double-clicking on Windows friendly: the window stays open after the
# run and you can keep typing options.  Also lets any argument "@notes.md" be replaced
# by that file's text, so prompts can be any length (the command line itself is limited).
def _slurp(path):
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        return fh.read()


def _at_text(text):
    """A text that argparse will not mistake for an option."""
    return " " + text if text.lstrip().startswith("-") and not text.startswith(" ") else text


def _expand_at_files(args):
    out = []
    for a in args:
        if len(a) > 1 and a[0] == "@" and os.path.isfile(a[1:].strip('"')):
            out.append(_at_text(_slurp(a[1:].strip('"'))))
        else:
            out.append(a)
    return out


def _read_long(prompt):
    """input() that also takes '@file.md' or a pasted block: type <<< then your text, then END."""
    line = input(prompt)
    s = line.strip()
    if s == "<<<":
        print("Paste your text, then finish with a line containing only END.")
        buf = []
        try:
            while True:
                row = input()
                if row.strip() == "END":
                    break
                buf.append(row)
        except EOFError:
            pass
        return "\n".join(buf)
    if len(s) > 1 and s[0] == "@" and os.path.isfile(s[1:].strip('"')):
        return _slurp(s[1:].strip('"'))
    return line


def _split_line(line):
    import shlex
    try:
        parts = shlex.split(line, posix=False)
        return [p[1:-1] if len(p) > 1 and p[0] == p[-1] and p[0] in "\"'" else p for p in parts]
    except ValueError:
        return line.split()


def _launch(main):
    sys.argv[1:] = _expand_at_files(sys.argv[1:])
    loop = ((os.name == "nt" or os.environ.get("TOYS_FORCE_LOOP")) and len(sys.argv) == 1 and sys.stdin is not None
            and sys.stdin.isatty() and not os.environ.get("TOYS_NO_LOOP"))

    def once():
        try:
            return main()
        except SystemExit as e:
            return e.code
        except BrokenPipeError:
            return 0
        except KeyboardInterrupt:
            sys.stdout.write("\x1b[?25h\x1b[0m\n")
            return 130
        except Exception:
            import traceback
            traceback.print_exc()
            return 1

    if not loop:
        rc = once()
        sys.exit(rc if rc is not None else 0)

    name = os.path.basename(sys.argv[0])
    once()
    import re
    ex = [m.group(1).strip() for m in (re.match(r"\s*python\s+\S+\.py\s*(.*?)\s*(#.*)?$", l)
                                       for l in (__doc__ or "").splitlines()) if m and m.group(1).strip()]
    print("\n" + "-" * 60)
    print("Finished. This window stays open. Type options for another run, e.g.:")
    for e in ex[:8]:
        print("   " + e)
    print("Enter = run again with defaults   ?  = help   q = quit")
    print("Long text: type @yourfile.md   or   <<<  then paste, then END")
    while True:
        try:
            line = _read_long("\n%s> " % name)
        except (EOFError, KeyboardInterrupt):
            break
        s = line.strip()
        if s.lower() in ("q", "quit", "exit"):
            break
        if s == "?":
            args = ["--help"]
        elif "\n" in line or len(line) > 4000:      # pasted block or file text: it is one prompt
            args = [_at_text(line)]
        else:
            args = _expand_at_files(_split_line(line))
        sys.argv[1:] = args
        once()


if __name__ == "__main__":
    _launch(main)
