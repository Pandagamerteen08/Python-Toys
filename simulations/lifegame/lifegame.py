#!/usr/bin/env python3
"""lifegame.py - Conway's Game of Life and friends. Standard library only.

    python lifegame.py                          # a Gosper glider gun on an infinite plane
    python lifegame.py acorn --gens 400 --follow
    python lifegame.py --random 0.3 --size 80x40 --torus --rule highlife
    python lifegame.py pulsar --gif pulsar.gif  # animated GIF (hand-written encoder)
    python lifegame.py --rle glider.rle         # paste any pattern from the LifeWiki (RLE format)
    python lifegame.py --wolfram 110            # 1-D elementary automaton (rules 0-255)
    python lifegame.py --ant RL                 # Langton's ant (try LLRR, RLR, LRRRRRLLR)
    python lifegame.py --brain --random 0.2     # Brian's Brain (3 states)
    python lifegame.py --list

Rules are Life-like "B3/S23" strings or names: life highlife seeds daynight maze replicator 34life coral diamoeba.
The world is an unbounded sparse set of cells (use --torus WxH for a wrapping board). The program also detects
still lifes, oscillators and spaceships by remembering past states.
"""
import sys, os, re, time, random, argparse, struct, zlib
from collections import Counter

os.system("")
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

RULES = {"life": "B3/S23", "highlife": "B36/S23", "seeds": "B2/S", "daynight": "B3678/S34678", "maze": "B3/S12345", "replicator": "B1357/S1357",
         "34life": "B34/S34", "coral": "B3/S45678", "diamoeba": "B35678/S5678", "2x2": "B36/S125", "anneal": "B4678/S35678"}
PATTERNS = {
    "glider": ".O./..O/OOO", "blinker": "OOO", "block": "OO/OO", "beehive": ".OO./O..O/.OO.", "toad": ".OOO/OOO.",
    "lwss": ".O..O/O..../O...O/OOOO.", "r-pentomino": ".OO/OO./.O.", "acorn": ".O...../...O.../OO..OOO", "diehard": "......O./OO....../.O...OOO",
    "pentadecathlon": "..O....O../OO.OOOO.OO/..O....O..",
    "pulsar": "..OOO...OOO../............./O....O.O....O/O....O.O....O/O....O.O....O/..OOO...OOO../............./..OOO...OOO../O....O.O....O/O....O.O....O/O....O.O....O/............./..OOO...OOO..",
    "gosper-gun": "........................O.........../......................O.O........./............OO......OO............OO/...........O...O....OO............OO/OO........O.....O...OO............../OO........O...O.OO....O.O.........../..........O.....O.......O.........../...........O...O..................../............OO........................",
    "infinite-growth": "......O./....O.OO/....O.O./....O.../..O...../O.O.....",
}

def parse_rule(s):
    s = RULES.get(s.lower(), s); m = re.fullmatch(r"[Bb](\d*)/[Ss](\d*)", s)
    if not m: raise SystemExit(f"bad rule '{s}': use names ({', '.join(RULES)}) or B3/S23 style")
    return set(map(int, m.group(1))), set(map(int, m.group(2)))

def from_rows(spec, ox=0, oy=0):
    return {(x + ox, y + oy) for y, row in enumerate(spec.split("/")) for x, ch in enumerate(row) if ch in "Oo#*1"}

def parse_rle(text):
    rule = None; body = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"): continue
        if line.lower().startswith("x"):
            m = re.search(r"rule\s*=\s*([^\s,]+)", line, re.I)
            if m: rule = m.group(1)
            continue
        body.append(line)
    cells = set(); x = y = 0
    for count, tag in re.findall(r"(\d*)([bo$!]|[A-Za-z])", "".join(body)):
        n = int(count or 1)
        if tag == "!": break
        if tag == "$": y += n; x = 0
        elif tag == "o" or tag == "O":
            for i in range(n): cells.add((x + i, y))
            x += n
        else: x += n
    return cells, rule

NB = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
BRAIN_NAME = "Brian's Brain"


def step(cells, B, S, wrap=None):
    cnt = Counter()
    if wrap:
        W, H = wrap
        for x, y in cells:
            for dx, dy in NB: cnt[((x + dx) % W, (y + dy) % H)] += 1
    else:
        for x, y in cells:
            for dx, dy in NB: cnt[(x + dx, y + dy)] += 1
    new = {c for c, n in cnt.items() if (n in B and c not in cells) or (n in S and c in cells)}
    if 0 in S: new |= {c for c in cells if c not in cnt}
    return new

def brain_step(on, dying, wrap=None):
    cnt = Counter()
    for x, y in on:
        for dx, dy in NB: cnt[(((x + dx) % wrap[0], (y + dy) % wrap[1]) if wrap else (x + dx, y + dy))] += 1
    born = {c for c, n in cnt.items() if n == 2 and c not in on and c not in dying}
    return born, set(on)

def normalise(cells):
    if not cells: return frozenset(), (0, 0)
    mx, my = min(x for x, _ in cells), min(y for _, y in cells); return frozenset((x - mx, y - my) for x, y in cells), (mx, my)

class Detector:
    """Spot still lifes, oscillators and spaceships: remember every state (shape + position)."""
    def __init__(self): self.seen = {}; self.found = None
    def feed(self, gen, cells):
        if self.found: return
        shape, pos = normalise(cells)
        if shape in self.seen:
            g0, p0 = self.seen[shape]; period = gen - g0; d = (pos[0] - p0[0], pos[1] - p0[1])
            kind = ("still life" if period == 1 else f"oscillator, period {period}") if d == (0, 0) else f"spaceship, period {period}, moves {d} per cycle"
            self.found = f"gen {g0}: {kind}"
        else: self.seen[shape] = (gen, pos)

def age_color(a):
    if a <= 1: return (255, 250, 210)
    t = min(1.0, (a - 1) / 40); return (int(255 - 90 * t), int(190 * (1 - t) + 60 * t), int(60 + 150 * t))
BG = (16, 18, 28)

def draw(cells, ages, cols, rows, center, states=None):
    H = rows * 2; cx, cy = center; x0, y0 = cx - cols // 2, cy - H // 2; px = {}
    for (x, y) in cells:
        if x0 <= x < x0 + cols and y0 <= y < y0 + H: px[(x - x0, y - y0)] = (states or {}).get((x, y)) or age_color(ages.get((x, y), 1))
    out = []
    for r in range(rows):
        line = []
        for c in range(cols):
            a = px.get((c, 2 * r), BG); b = px.get((c, 2 * r + 1), BG)
            line.append(f"\033[38;2;{a[0]};{a[1]};{a[2]};48;2;{b[0]};{b[1]};{b[2]}m▀")
        out.append("".join(line) + "\033[0m")
    return "\n".join(out)

def centre_of(cells, mode="bbox"):
    if not cells: return (0, 0)
    xs = [x for x, _ in cells]; ys = [y for _, y in cells]; return ((min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2)

# ----- PNG + GIF writers
def chunk(tag, data): return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
def save_png(path, rows):
    h, w = len(rows), len(rows[0]); raw = b"".join(b"\x00" + bytes(v for px in r for v in px) for r in rows)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
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
def write_gif(path, frames, w, h, palette, delay_cs):
    out = bytearray(b"GIF89a" + struct.pack("<HHBBB", w, h, 0xF7, 0, 0))
    for c in palette + [(0, 0, 0)] * (256 - len(palette)): out += bytes(c)
    out += b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"
    for f in frames:
        out += b"\x21\xf9\x04\x00" + struct.pack("<H", delay_cs) + b"\x00\x00" + b"\x2c" + struct.pack("<HHHHB", 0, 0, w, h, 0) + b"\x08"
        data = lzw(f)
        for i in range(0, len(data), 255): blk = data[i:i + 255]; out += bytes([len(blk)]) + blk
        out += b"\x00"
    open(path, "wb").write(bytes(out) + b"\x3b")

GIF_PAL = [BG] + [age_color(a) for a in range(1, 256)]
def frame_indices(cells, ages, box, scale):
    x0, y0, w, h = box; idx = [[0] * (w * scale) for _ in range(h * scale)]
    for (x, y) in cells:
        if 0 <= x - x0 < w and 0 <= y - y0 < h:
            v = min(255, ages.get((x, y), 1))
            for dy in range(scale):
                row = idx[(y - y0) * scale + dy]
                for dx in range(scale): row[(x - x0) * scale + dx] = v
    return [v for r in idx for v in r]

# ----- other automata
def wolfram(rule, width, rows, init=None):
    table = [(rule >> i) & 1 for i in range(8)]; row = [0] * width; row[width // 2] = 1
    if init == "random": row = [random.random() < .5 for _ in range(width)]
    out = []
    for _ in range(rows):
        out.append(row); row = [table[(row[(i - 1) % width] << 2) | (row[i] << 1) | row[(i + 1) % width]] for i in range(width)]
    return out

def langton(rule, steps):
    grid = {}; x = y = 0; d = 0; n = len(rule)  # d: 0 up, 1 right, 2 down, 3 left
    for _ in range(steps):
        s = grid.get((x, y), 0); d = (d + (1 if rule[s] == "R" else -1)) % 4; grid[(x, y)] = (s + 1) % n
        x += (0, 1, 0, -1)[d]; y += (-1, 0, 1, 0)[d]
    return grid, (x, y)

ANT_COLORS = [(16, 18, 28), (255, 200, 60), (80, 200, 255), (255, 90, 120), (140, 255, 140), (200, 120, 255), (255, 140, 40), (240, 240, 240)]

def render_grid_colors(grid, cols, rows, palette):
    if not grid: return ""
    xs = [x for x, _ in grid]; ys = [y for _, y in grid]; x0, y0 = min(xs), min(ys); w, h = max(xs) - x0 + 1, max(ys) - y0 + 1
    sx, sy = max(1, -(-w // cols)), max(1, -(-h // (rows * 2))); out = []
    for r in range(0, -(-h // sy), 2):
        line = []
        for c in range(-(-w // sx)):
            def at(rr):
                best = 0
                for yy in range(rr * sy, min(h, (rr + 1) * sy)):
                    for xx in range(c * sx, min(w, (c + 1) * sx)):
                        v = grid.get((x0 + xx, y0 + yy), 0)
                        if v: best = v
                return palette[best % len(palette)]
            a, b = at(r), at(r + 1); line.append(f"\033[38;2;{a[0]};{a[1]};{a[2]};48;2;{b[0]};{b[1]};{b[2]}m▀")
        out.append("".join(line) + "\033[0m")
    return "\n".join(out)

def spark(vals, width=60):
    if not vals: return ""
    if len(vals) > width: vals = [vals[int(i * len(vals) / width)] for i in range(width)]
    lo, hi = min(vals), max(vals); return "".join("▁▂▃▄▅▆▇█"[min(7, int((v - lo) / ((hi - lo) or 1) * 8))] for v in vals)

def main():
    ap = argparse.ArgumentParser(description="Game of Life and other cellular automata")
    ap.add_argument("pattern", nargs="?", default=None, help="pattern name (see --list)")
    ap.add_argument("--rule", default="life"); ap.add_argument("--gens", type=int, default=200); ap.add_argument("--delay", type=float, default=.05)
    ap.add_argument("--random", type=float, metavar="DENSITY"); ap.add_argument("--size", default="80x40"); ap.add_argument("--torus", action="store_true")
    ap.add_argument("--rle", metavar="FILE"); ap.add_argument("--seed", type=int); ap.add_argument("--follow", action="store_true", help="camera follows the pattern")
    ap.add_argument("--cols", type=int, default=100); ap.add_argument("--rows", type=int, default=24)
    ap.add_argument("--gif"); ap.add_argument("--png"); ap.add_argument("--scale", type=int, default=4); ap.add_argument("--no-anim", action="store_true", help="print the final state only")
    ap.add_argument("--wolfram", type=int, metavar="RULE"); ap.add_argument("--ant", metavar="LR-STRING", nargs="?", const="RL"); ap.add_argument("--steps", type=int, default=11000)
    ap.add_argument("--brain", action="store_true"); ap.add_argument("--list", action="store_true")
    a = ap.parse_args(); random.seed(a.seed)
    if a.list:
        print("patterns:", ", ".join(PATTERNS)); print("rules   :", ", ".join(f"{k}={v}" for k, v in RULES.items())); return
    if a.wolfram is not None:
        if not 0 <= a.wolfram <= 255: sys.exit("wolfram rule must be 0-255")
        w = a.cols - 1; rows = wolfram(a.wolfram, w, a.rows * 2 - 2)
        print("\n".join("".join("█" if v else " " for v in r) for r in rows)); print(f"\nRule {a.wolfram}  (binary {a.wolfram:08b})"); return
    if a.ant:
        if not re.fullmatch(r"[LR]{2,8}", a.ant.upper()): sys.exit("--ant takes a string of L and R, e.g. RL or LLRR")
        grid, pos = langton(a.ant.upper(), a.steps); print(render_grid_colors(grid, a.cols, a.rows, ANT_COLORS)); print(f"\nLangton's ant {a.ant.upper()}: {a.steps} steps, {len(grid)} cells visited, ant at {pos}"); return
    W, H = (int(v) for v in a.size.lower().split("x")); wrap = (W, H) if a.torus else None
    if a.rle: cells, rl = parse_rle(open(a.rle).read()); rule = rl or a.rule
    elif a.random is not None: cells = {(x, y) for x in range(W) for y in range(H) if random.random() < a.random}; rule = a.rule
    else:
        name = a.pattern or "gosper-gun"
        if name not in PATTERNS: sys.exit(f"unknown pattern '{name}'. Try --list")
        cells = from_rows(PATTERNS[name], 5, 5); rule = a.rule
    B, S = parse_rule(rule) if not a.brain else (set(), set()); ages = {c: 1 for c in cells}; det = Detector(); pops = []; dying = set()
    center = centre_of(cells) if not wrap else (W // 2, H // 2); anim = not a.no_anim and not a.gif and sys.stdout.isatty()
    frames = []; box = None; hist_minmax = None
    if a.gif:
        pad = 8; xs = [x for x, _ in cells] or [0]; ys = [y for _, y in cells] or [0]
        box = (min(xs) - pad, min(ys) - pad, 100, 60) if not wrap else (0, 0, W, H)
    try:
        if anim: print("\033[2J\033[?25l", end="")
        for g in range(a.gens + 1):
            pops.append(len(cells)); det.feed(g, cells if not a.brain else cells | dying)
            if a.gif and g % 1 == 0: frames.append(frame_indices(cells, ages, box, a.scale))
            if anim:
                if a.follow and cells and not wrap: c0 = centre_of(cells); center = (center[0] + (c0[0] - center[0]) // 2, center[1] + (c0[1] - center[1]) // 2)
                states = {c: (90, 90, 200) for c in dying} if a.brain else None
                print("\033[H" + draw(cells | dying, ages, a.cols, a.rows, center, states) + f"\033[0m\ngen {g:<5} pop {len(cells):<6} {det.found or '':<60}", flush=True); time.sleep(a.delay)
            if a.brain: cells, dying = brain_step(cells, dying, wrap)
            else:
                new = step(cells, B, S, wrap); ages = {c: ages.get(c, 0) + 1 if c in cells else 1 for c in new}; cells = new
            if not cells and not dying: break
    finally:
        if anim: print("\033[?25h", end="")
    if not anim:
        print(draw(cells | dying, ages, a.cols, a.rows, centre_of(cells) if not wrap else (W // 2, H // 2)) + "\033[0m")
    print(f"generations: {len(pops) - 1}   final population: {pops[-1]}   peak: {max(pops)}   rule: {rule if not a.brain else BRAIN_NAME}")
    print("population:", spark(pops)); print("detected  :", det.found or "no repeat found (still evolving)")
    if a.gif: write_gif(a.gif, frames, box[2] * a.scale, box[3] * a.scale, GIF_PAL, max(2, int(a.delay * 100))); print("wrote", a.gif)
    if a.png:
        sc = a.scale; xs = [x for x, _ in cells] or [0]; ys = [y for _, y in cells] or [0]; x0, y0 = min(xs), min(ys); w, h = max(xs) - x0 + 1, max(ys) - y0 + 1
        rows_ = [[(age_color(ages.get((x0 + x // sc, y0 + y // sc), 1)) if (x0 + x // sc, y0 + y // sc) in cells else BG) for x in range(w * sc)] for y in range(h * sc)]
        save_png(a.png, rows_); print("wrote", a.png)


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
