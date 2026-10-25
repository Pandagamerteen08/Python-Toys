#!/usr/bin/env python3
"""fractals.py v2 - fractal lab. Standard library only (multi-core via multiprocessing).

Fractals : mandelbrot julia ship tricorn celtic multibrot phoenix newton magnet
Colouring: smooth bands angle trap dist(ance-estimate)       Palettes: 12 built in

    python fractals.py                                     # Mandelbrot in your terminal (truecolour)
    python fractals.py --preset seahorse --palette ultra
    python fractals.py --set julia --c -0.8,0.156 --mode angle
    python fractals.py --set newton --power 5 --png newton5.png --png-size 1280x800 --ssaa 2
    python fractals.py --set multibrot --power 4 --mode trap --palette neon
    python fractals.py --explore                           # interactive: arrows pan, +/- zoom, j = Julia here
    python fractals.py --gif zoom.gif --preset seahorse --zoom-end 4000 --frames 40   # animated zoom
    python fractals.py --gallery gallery/ --png-size 640x400     # render every preset to PNGs
    python fractals.py --tour                              # show all presets in the terminal
    python fractals.py --list

Everything (PNG, GIF) is written by hand with zlib/LZW, so no Pillow or numpy is needed.
Doubles run out of precision around zoom 1e13, where images turn blocky - that is normal.
"""
import sys, os, math, argparse, zlib, struct, time
import multiprocessing as mp

os.system("")  # enable ANSI in old Windows consoles
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

KINDS = ["mandelbrot", "julia", "ship", "tricorn", "celtic", "multibrot", "phoenix", "newton", "magnet"]
MODES = ["smooth", "bands", "angle", "trap", "dist"]

# name: (kind, cx, cy, zoom, extra params)
PRESETS = {
    "full": ("mandelbrot", -0.5, 0.0, 1.0, {}),
    "seahorse": ("mandelbrot", -0.743643887037151, 0.131825904205330, 400, {}),
    "lightning": ("mandelbrot", -0.1011, 0.9563, 20, {}),
    "spiral": ("mandelbrot", -0.7269, 0.1889, 80, {}),
    "tentacles": ("mandelbrot", -0.1592, 1.0317, 40, {}),
    "seahorse-deep": ("mandelbrot", -0.77568377, 0.13646737, 2000, {}),
    "dendrite": ("mandelbrot", 0.001643721971153, 0.822467633298876, 500, {}),
    "starfish": ("mandelbrot", -0.374004139, 0.659792175, 800, {}),
    "minibrot": ("mandelbrot", -1.7548776662466927, 0.0, 60, {}),
    "feigenbaum": ("mandelbrot", -1.401155, 0.0, 30, {}),
    "valley": ("mandelbrot", -0.7463, 0.1102, 120, {}),
    "julia-a": ("julia", 0.0, 0.0, 0.9, {"c": (-0.8, 0.156)}),
    "julia-rabbit": ("julia", 0.0, 0.0, 0.9, {"c": (-0.123, 0.745)}),
    "julia-snow": ("julia", 0.0, 0.0, 0.9, {"c": (-0.4, 0.6)}),
    "julia-dust": ("julia", 0.0, 0.0, 0.9, {"c": (0.285, 0.01)}),
    "julia-siegel": ("julia", 0.0, 0.0, 0.9, {"c": (-0.391, -0.587)}),
    "julia-dragon": ("julia", 0.0, 0.0, 0.9, {"c": (-0.70176, -0.3842)}),
    "ship": ("ship", -0.4, -0.6, 0.7, {}),
    "ship-hull": ("ship", -1.7443, -0.0173, 25, {}),
    "ship-towers": ("ship", -1.755, -0.03, 30, {}),
    "tricorn": ("tricorn", 0.0, 0.0, 0.8, {}),
    "celtic": ("celtic", -0.3, 0.0, 0.8, {}),
    "multibrot3": ("multibrot", 0.0, 0.0, 0.9, {"power": 3}),
    "multibrot5": ("multibrot", 0.0, 0.0, 0.9, {"power": 5}),
    "phoenix": ("phoenix", 0.0, 0.0, 0.9, {"c": (0.5667, 0.0), "p": (-0.5, 0.0)}),
    "newton3": ("newton", 0.0, 0.0, 0.8, {"power": 3}),
    "newton5": ("newton", 0.0, 0.0, 0.8, {"power": 5}),
    "magnet": ("magnet", 1.0, 0.0, 0.6, {}),
}

# cosine palettes: colour(t) = a + b*cos(2*pi*(c*t + d))   (Inigo Quilez)
PALETTES = {
    "fire":    ((.5, .5, .5), (.5, .5, .5), (1, 1, 1), (0.0, 0.10, 0.20)),
    "ocean":   ((.2, .45, .6), (.3, .35, .4), (1, 1, 1), (0.0, 0.10, 0.20)),
    "neon":    ((.5, .5, .5), (.5, .5, .5), (1, 1, 1), (0.0, 0.33, 0.67)),
    "forest":  ((.25, .45, .2), (.3, .45, .25), (1, 1, 1), (0.3, 0.15, 0.55)),
    "rainbow": ((.5, .5, .5), (.5, .5, .5), (1, 1, 1), (0.0, 0.33, 0.67)),
    "ice":     ((.7, .85, .95), (.3, .25, .15), (1, 1, 1), (0.55, 0.6, 0.65)),
    "sunset":  ((.55, .35, .45), (.45, .4, .35), (1, 1, .8), (0.0, 0.25, 0.5)),
    "candy":   ((.7, .5, .7), (.3, .4, .3), (1, 1, 1), (0.0, 0.5, 0.25)),
    "ultra":   ((.3, .25, .45), (.6, .55, .5), (1, .8, .6), (0.65, 0.45, 0.2)),
    "electric": ((.1, .15, .45), (.5, .5, .55), (1, 1, 1), (0.6, 0.3, 0.0)),
    "grape":   ((.4, .2, .5), (.4, .3, .4), (1, 1, 1), (0.1, 0.25, 0.45)),
    "mono":    ((.5, .5, .5), (.5, .5, .5), (1, 1, 1), (0, 0, 0)),
}
LUTN = 1024
def make_lut(name, invert=False):
    a, b, c, d = PALETTES[name]; out = []
    for i in range(LUTN):
        t = i / LUTN; col = tuple(max(0, min(255, int(255 * (a[k] + b[k] * math.cos(6.283185 * (c[k] * t + d[k])))))) for k in range(3))
        out.append((255 - col[0], 255 - col[1], 255 - col[2]) if invert else col)
    return out

# ---------------------------------------------------------------- iteration kernels
def point(P, px, py, pix):
    """Return a float colour parameter for one pixel, or None for 'inside the set'."""
    kind, maxit, mode, bail = P["kind"], P["maxit"], P["mode"], P["bail"]; pw = P["power"]
    lb = math.log(bail); lp = math.log(max(pw, 2)); trap = 1e30; dz = 1 + 0j
    if kind == "newton":
        z = complex(px, py); roots = [complex(math.cos(6.283185 * k / pw), math.sin(6.283185 * k / pw)) for k in range(pw)]
        for n in range(maxit):
            if z == 0: return None
            z -= (z ** pw - 1) / (pw * z ** (pw - 1))
            for k, r in enumerate(roots):
                if abs(z - r) < 1e-6: return k + max(0.0, 1.0 - n / 40.0)
        return None
    if kind == "magnet":
        c = complex(px, py); z = 0j
        for n in range(maxit):
            den = 2 * z + c - 2
            if den == 0: return None
            z = ((z * z + c - 1) / den) ** 2
            if abs(z - 1) < 1e-6: return None
            m = z.real * z.real + z.imag * z.imag
            if m > bail * bail: return n + 1 - math.log(math.log(m) / 2 / lb) / math.log(2) if m > 1 else n
        return None
    if kind == "julia": z = complex(px, py); c = complex(*P["c"])
    elif kind == "phoenix": z = complex(px, py); c = complex(*P["c"]); pp = complex(*P["p"]); zprev = 0j
    else: z = 0j; c = complex(px, py)
    if kind == "mandelbrot" and pw == 2:  # skip the main cardioid and period-2 bulb instantly
        q = (px - .25) ** 2 + py * py
        if q * (q + (px - .25)) <= .25 * py * py or (px + 1) ** 2 + py * py <= .0625: return None
    cx = P.get("trapx", 0.0); b2 = bail * bail
    for n in range(maxit):
        if kind == "ship": z = complex(abs(z.real), abs(z.imag)); z = z * z + c
        elif kind == "tricorn": z = z.conjugate(); z = z * z + c
        elif kind == "celtic": w = z * z; z = complex(abs(w.real), w.imag) + c
        elif kind == "phoenix": z, zprev = z * z + c + pp * zprev, z
        elif pw == 2:
            if mode == "dist" and kind in ("mandelbrot", "julia"): dz = 2 * z * dz + (1 if kind == "mandelbrot" else 0)
            z = z * z + c
        else: z = z ** pw + c
        m = z.real * z.real + z.imag * z.imag
        if mode == "trap": trap = min(trap, min(abs(z.real - cx), abs(z.imag)))
        if m > b2:
            if mode == "bands": return float(n)
            if mode == "dist" and kind in ("mandelbrot", "julia") and pw == 2:
                az = math.sqrt(m); d = az * math.log(az) / max(abs(dz), 1e-300) * .5
                return (d / pix) ** .25 * 24
            s = n + 1 - math.log(math.log(m) / 2 / lb * lb / lb) / lp if m > 1 else n
            if mode == "angle": s += math.atan2(z.imag, z.real) / 6.283185 * 24
            elif mode == "trap": s = -math.log(trap + 1e-6) * 5 + n * .1
            return s
    return None

def rgb_of(t, P, lut):
    if t is None: return (0, 0, 0)
    if P["kind"] == "newton":
        r = int(t); f = t - r; base = lut[int(((r / P["power"]) + P["shift"]) * LUTN) % LUTN]; k = .25 + .75 * f
        return (int(base[0] * k), int(base[1] * k), int(base[2] * k))
    return lut[int(t * 32 * P["scale"] + P["shift"] * LUTN) % LUTN]

def _rows(job):
    P, w, h, rows = job; span = 3.5 / P["zoom"]; sc = span / w; out = []
    lut = make_lut(P["palette"], P["invert"]); pix = sc
    for y in range(rows[0], rows[1], rows[2]):
        py = P["cy"] + (y - h / 2 + .5) * sc
        out.append((y, [rgb_of(point(P, P["cx"] + (x - w / 2 + .5) * sc, py, pix), P, lut) for x in range(w)]))
    return out

_pool = None
def get_pool(jobs):
    global _pool
    if jobs > 1 and _pool is None:
        try: _pool = mp.Pool(jobs)
        except Exception: _pool = False
    return _pool

def render_rgb(P, w, h, jobs, progress=False):
    """Return h rows of w (r,g,b) tuples, computed on several cores."""
    pool = get_pool(jobs); n = max(1, jobs) * 4 if pool else 1
    work = [(P, w, h, (r, h, n)) for r in range(n)]
    img = [None] * h; done = 0
    it = pool.imap_unordered(_rows, work) if pool else map(_rows, work)
    for chunk in it:
        for y, row in chunk: img[y] = row
        done += 1
        if progress: print(f"\r  rendering {100 * done // len(work)}%", end="", file=sys.stderr, flush=True)
    if progress: print("\r" + " " * 24 + "\r", end="", file=sys.stderr)
    return img

# ---------------------------------------------------------------- output formats
def draw_terminal(img, ascii_mode=False):
    h = len(img); lines = []
    if ascii_mode:
        ramp = " .:-=+*#%@"
        for row in img: lines.append("".join(ramp[min(9, sum(px) // 77)] for px in row))
        return "\n".join(lines)
    for y in range(0, h - 1, 2):
        lines.append("".join(f"\033[38;2;{a[0]};{a[1]};{a[2]};48;2;{b[0]};{b[1]};{b[2]}m▀" for a, b in zip(img[y], img[y + 1])) + "\033[0m")
    return "\n".join(lines)

def chunk(tag, data): return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
def save_png(path, img):
    h, w = len(img), len(img[0])
    raw = b"".join(b"\x00" + bytes(v for px in row for v in px) for row in img)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))

def downsample(img, k):
    if k <= 1: return img
    h, w = len(img) // k, len(img[0]) // k; out = []
    for y in range(h):
        row = []
        for x in range(w):
            r = g = b = 0
            for dy in range(k):
                for dx in range(k): px = img[y * k + dy][x * k + dx]; r += px[0]; g += px[1]; b += px[2]
            n = k * k; row.append((r // n, g // n, b // n))
        out.append(row)
    return out

# ----- GIF (palette-indexed frames, hand-written LZW)
def lzw(indices):
    clear, eoi = 256, 257; size = 9; nxt = 258; table = {}; out = bytearray(); acc = nb = 0
    def emit(code):
        nonlocal acc, nb
        acc |= code << nb; nb += size
        while nb >= 8: out.append(acc & 255); acc >>= 8; nb -= 8
    emit(clear); prefix = indices[0]
    for px in indices[1:]:
        key = (prefix, px)
        if key in table: prefix = table[key]; continue
        emit(prefix); table[key] = nxt; nxt += 1
        if nxt > (1 << size) and size < 12: size += 1
        if nxt >= 4095: emit(clear); table = {}; size = 9; nxt = 258
        prefix = px
    emit(prefix); emit(eoi)
    if nb: out.append(acc & 255)
    return bytes(out)

def gif_index(t, P):
    if t is None: return 0
    if P["kind"] == "newton": return 1 + int(t * 30 + P["shift"] * 255) % 255
    return 1 + int(t * 32 * P["scale"] * 255 / LUTN + P["shift"] * 255) % 255

def _idx_rows(job):
    P, w, h, rows = job; span = 3.5 / P["zoom"]; sc = span / w; out = []
    for y in range(rows[0], rows[1], rows[2]):
        py = P["cy"] + (y - h / 2 + .5) * sc
        out.append((y, [gif_index(point(P, P["cx"] + (x - w / 2 + .5) * sc, py, sc), P) for x in range(w)]))
    return out

def write_gif(path, frames, w, h, palette, delay_cs):
    gct = [(0, 0, 0)] + [palette[int(i * LUTN / 255) % LUTN] for i in range(255)]
    out = bytearray(b"GIF89a" + struct.pack("<HHBBB", w, h, 0xF7, 0, 0))
    for c in gct: out += bytes(c)
    out += b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"
    for f in frames:
        out += b"\x21\xf9\x04\x00" + struct.pack("<H", delay_cs) + b"\x00\x00"
        out += b"\x2c" + struct.pack("<HHHHB", 0, 0, w, h, 0) + b"\x08"
        data = lzw([v for row in f for v in row])
        for i in range(0, len(data), 255): blk = data[i:i + 255]; out += bytes([len(blk)]) + blk
        out += b"\x00"
    out += b"\x3b"
    open(path, "wb").write(out)

# ---------------------------------------------------------------- params
def build_params(a, preset=None):
    name = preset or a.preset or ("full" if not a.set else {"mandelbrot": "full", "julia": "julia-a", "ship": "ship", "tricorn": "tricorn", "celtic": "celtic",
                                  "multibrot": "multibrot3", "phoenix": "phoenix", "newton": "newton3", "magnet": "magnet"}[a.set])
    kind, cx, cy, zoom, ex = PRESETS[name]
    if a.set and not preset: kind = a.set
    P = dict(kind=kind, cx=a.cx if a.cx is not None else cx, cy=a.cy if a.cy is not None else cy, zoom=a.zoom if a.zoom is not None else zoom,
             c=ex.get("c", (-0.8, 0.156)), p=ex.get("p", (-0.5, 0.0)), power=ex.get("power", 2), mode=a.mode, palette=a.palette, invert=a.invert,
             scale=a.scale, shift=a.shift, bail=a.bail)
    if kind == "multibrot" and "power" not in ex: P["power"] = 3
    if kind == "newton" and P["power"] < 3: P["power"] = 3
    if a.power and not preset: P["power"] = a.power
    if a.c and not preset: P["c"] = tuple(float(v) for v in a.c.split(","))
    if a.p and not preset: P["p"] = tuple(float(v) for v in a.p.split(","))
    if P["zoom"] > 1e13: print("warning: zoom beyond double precision; image will look blocky", file=sys.stderr)
    P["maxit"] = a.iter or int(120 + 70 * math.log2(max(P["zoom"], 1) + 1))
    if kind == "newton": P["maxit"] = max(40, min(P["maxit"], 80))
    P["bail"] = max(2.0, P["bail"]) if kind != "newton" else 2.0
    return P

def describe(P):
    s = f"{P['kind']} | centre ({P['cx']:.12g}, {P['cy']:.12g}) | zoom {P['zoom']:.6g} | {P['maxit']} it | {P['mode']}/{P['palette']}"
    if P["kind"] in ("julia", "phoenix"): s += f" | c = {P['c'][0]}{P['c'][1]:+}i"
    if P["kind"] in ("multibrot", "newton"): s += f" | power {P['power']}"
    return s

# ---------------------------------------------------------------- interactive explorer
def getch():
    if os.name == "nt":
        import msvcrt
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"): return {"H": "up", "P": "down", "K": "left", "M": "right"}.get(msvcrt.getwch(), "")
        if ch == "\x03": raise KeyboardInterrupt
        return ch
    import termios, tty, select
    fd = sys.stdin.fileno(); old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd, termios.TCSADRAIN); ch = sys.stdin.read(1)
        if ch == "\x03": raise KeyboardInterrupt
        if ch == "\x1b" and select.select([sys.stdin], [], [], .05)[0]:
            return {"[A": "up", "[B": "down", "[D": "left", "[C": "right"}.get(sys.stdin.read(2), "")
        return ch
    finally: termios.tcsetattr(fd, termios.TCSADRAIN, old)

def explore(a, P):
    if not sys.stdin.isatty(): sys.exit("--explore needs an interactive terminal")
    cols, rows = a.cols, a.rows * 2; pal = list(PALETTES); modes = MODES; saved = 0
    print("\033[2J\033[?25l", end="")
    try:
        while True:
            t0 = time.time(); img = render_rgb(P, cols, rows, a.jobs); dt = time.time() - t0
            print("\033[H" + draw_terminal(img, a.ascii) + f"\033[0m\n{describe(P)}  [{dt:.1f}s]\033[K\n"
                  "arrows/WASD pan  +/- zoom  i/k iterations  p palette  m mode  j Julia-here  t type  [ ] power  r reset  e export PNG  q quit\033[K")
            k = getch(); k = k.lower() if len(k) == 1 else k; span = 3.5 / P["zoom"]
            if k in ("q", "\x1b"): break
            elif k in ("up", "w"): P["cy"] -= span * .2
            elif k in ("down", "s"): P["cy"] += span * .2
            elif k == "e": saved += 1; fn = f"fractal_{saved}.png"; save_png(fn, render_rgb(P, 640, 400, a.jobs)); print(f"\nsaved {fn}", end="")
            elif k in ("left", "a"): P["cx"] -= span * .2
            elif k in ("right", "d"): P["cx"] += span * .2
            elif k in ("+", "="): P["zoom"] *= 1.6; P["maxit"] = int(P["maxit"] * 1.04)
            elif k in ("-", "_"): P["zoom"] /= 1.6
            elif k == "i": P["maxit"] = int(P["maxit"] * 1.4)
            elif k == "k": P["maxit"] = max(20, int(P["maxit"] / 1.4))
            elif k == "p": P["palette"] = pal[(pal.index(P["palette"]) + 1) % len(pal)]
            elif k == "m": P["mode"] = modes[(modes.index(P["mode"]) + 1) % len(modes)]
            elif k == "t": P["kind"] = KINDS[(KINDS.index(P["kind"]) + 1) % len(KINDS)]; P.update(zoom=.9 if P["kind"] != "mandelbrot" else 1.0, cx=0.0, cy=0.0)
            elif k == "j" and P["kind"] == "mandelbrot": P.update(kind="julia", c=(P["cx"], P["cy"]), cx=0.0, cy=0.0, zoom=.9)
            elif k in ("[", "]") and P["kind"] in ("multibrot", "newton"): P["power"] = max(2 if P["kind"] == "multibrot" else 3, P["power"] + (1 if k == "]" else -1))
            elif k == "r": P.update(build_params(a))
    finally: print("\033[?25h\033[0m")

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Fractal lab")
    ap.add_argument("--set", choices=KINDS); ap.add_argument("--preset", choices=list(PRESETS))
    ap.add_argument("--cx", type=float); ap.add_argument("--cy", type=float); ap.add_argument("--zoom", type=float)
    ap.add_argument("--c", help="Julia/Phoenix constant 're,im'"); ap.add_argument("--p", help="Phoenix memory constant 're,im'")
    ap.add_argument("--power", type=int, help="multibrot / newton exponent"); ap.add_argument("--iter", type=int)
    ap.add_argument("--bail", type=float, default=16.0); ap.add_argument("--mode", choices=MODES, default="smooth")
    ap.add_argument("--palette", choices=list(PALETTES), default="fire"); ap.add_argument("--invert", action="store_true")
    ap.add_argument("--scale", type=float, default=1.0, help="colour cycling frequency"); ap.add_argument("--shift", type=float, default=0.0, help="palette offset 0-1")
    ap.add_argument("--cols", type=int, default=100); ap.add_argument("--rows", type=int, default=28); ap.add_argument("--ascii", action="store_true")
    ap.add_argument("--png"); ap.add_argument("--png-size", default="800x500"); ap.add_argument("--ssaa", type=int, default=1, help="supersampling factor (2 = 4x slower, smoother)")
    ap.add_argument("--gif"); ap.add_argument("--frames", type=int, default=30); ap.add_argument("--zoom-end", type=float, help="final zoom for --gif")
    ap.add_argument("--gif-size", default="320x200"); ap.add_argument("--fps", type=int, default=15); ap.add_argument("--pingpong", action="store_true")
    ap.add_argument("--gallery", metavar="DIR"); ap.add_argument("--tour", action="store_true"); ap.add_argument("--explore", action="store_true")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1); ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        for k, (kind, cx, cy, z, ex) in PRESETS.items(): print(f"{k:<14}{kind:<11} centre=({cx}, {cy}) zoom={z} {ex or ''}")
        print("modes:", ", ".join(MODES)); print("palettes:", ", ".join(PALETTES)); return
    if a.tour:
        for name in PRESETS:
            P = build_params(a, name); print(draw_terminal(render_rgb(P, a.cols, a.rows * 2, a.jobs), a.ascii), "\033[0m\n" + name + ": " + describe(P) + "\n")
        return
    if a.gallery:
        os.makedirs(a.gallery, exist_ok=True); w, h = (int(v) for v in a.png_size.lower().split("x"))
        for name in PRESETS:
            P = build_params(a, name); t0 = time.time(); save_png(os.path.join(a.gallery, name + ".png"), downsample(render_rgb(P, w * a.ssaa, h * a.ssaa, a.jobs), a.ssaa))
            print(f"{name:<14} {time.time() - t0:5.1f}s")
        return
    P = build_params(a)
    if a.explore: return explore(a, P)
    if a.gif:
        w, h = (int(v) for v in a.gif_size.lower().split("x")); z0, z1 = P["zoom"], a.zoom_end or P["zoom"] * 200; frames = []
        pool = get_pool(a.jobs); lut = make_lut(P["palette"], P["invert"])
        for f in range(a.frames):
            Q = dict(P); Q["zoom"] = z0 * (z1 / z0) ** (f / max(1, a.frames - 1)); Q["maxit"] = int(120 + 70 * math.log2(Q["zoom"] + 1))
            n = max(1, a.jobs) * 4; work = [(Q, w, h, (r, h, n)) for r in range(n)]; img = [None] * h
            for chunk_ in (pool.imap_unordered(_idx_rows, work) if pool else map(_idx_rows, work)):
                for y, row in chunk_: img[y] = row
            frames.append(img); print(f"\r  frame {f + 1}/{a.frames}", end="", file=sys.stderr, flush=True)
        if a.pingpong: frames += frames[-2:0:-1]
        write_gif(a.gif, frames, w, h, lut, max(2, 100 // a.fps)); print(f"\nwrote {a.gif} ({len(frames)} frames, {w}x{h})"); return
    t0 = time.time(); img = render_rgb(P, a.cols, a.rows * 2, a.jobs)
    print(draw_terminal(img, a.ascii) + "\033[0m"); print(describe(P) + f" | {time.time() - t0:.1f}s")
    if a.png:
        w, h = (int(v) for v in a.png_size.lower().split("x"))
        save_png(a.png, downsample(render_rgb(P, w * a.ssaa, h * a.ssaa, a.jobs, True), a.ssaa)); print(f"wrote {a.png} ({w}x{h}, ssaa {a.ssaa})")


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
    mp.freeze_support()  # needed for Windows + multiprocessing
    _launch(main)
