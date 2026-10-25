#!/usr/bin/env python3
"""lsystem.py - grow fractals, plants and curves from tiny rewriting rules.

An L-system is an axiom plus rules; each generation rewrites every symbol, then a
"turtle" walks the result.  Output to the terminal (Braille dots), SVG or PNG.
No dependencies. Python 3.8+.

  python lsystem.py --preset dragon -n 10
  python lsystem.py --preset plant --png plant.png --svg plant.svg
  python lsystem.py --axiom F --rule "F=F+F-F-F+F" --angle 90 -n 3
  python lsystem.py --preset bush --seed 5 --stoch          # stochastic variants
  python lsystem.py --list
  python lsystem.py --gallery out/                           # every preset as SVG

Turtle alphabet:  F G = draw forward   f g = move without drawing   + - = turn
  | = turn 180   [ ] = push/pop state   ! = shrink width   ' = shift colour
  Any other symbol is ignored by the turtle (it only exists for rewriting).
Rules:  "X=F+[[X]-X]-F[-FX]+X"  stochastic:  "F=0.6:FF" "F=0.4:F[+F]F"
"""
import argparse
import math
import os
import random
import struct
import sys
import zlib

PRESETS = {
    # name: (axiom, rules, angle, default generations, description)
    "koch": ("F", ["F=F+F-F-F+F"], 90, 4, "quadratic Koch curve"),
    "snowflake": ("F++F++F", ["F=F-F++F-F"], 60, 4, "Koch snowflake"),
    "sierpinski": ("F-G-G", ["F=F-G+F+G-F", "G=GG"], 120, 6, "Sierpinski triangle"),
    "arrowhead": ("A", ["A=B-A-B", "B=A+B+A"], 60, 7, "Sierpinski arrowhead curve"),
    "dragon": ("FX", ["X=X+YF+", "Y=-FX-Y"], 90, 11, "Heighway dragon"),
    "twindragon": ("FX+FX+", ["X=X+YF", "Y=FX-Y"], 90, 10, "twin dragon"),
    "terdragon": ("F", ["F=F+F-F"], 120, 8, "terdragon"),
    "levy": ("F", ["F=+F--F+"], 45, 12, "Levy C curve"),
    "hilbert": ("A", ["A=-BF+AFA+FB-", "B=+AF-BFB-FA+"], 90, 5, "Hilbert space-filling curve"),
    "peano": ("X", ["X=XFYFX+F+YFXFY-F-XFYFX", "Y=YFXFY-F-XFYFX+F+YFXFY"], 90, 3, "Peano curve"),
    "gosper": ("A", ["A=A-B--B+A++AA+B-", "B=+A-BB--B-A++A+B"], 60, 4, "Gosper (flowsnake) curve"),
    "moore": ("LFL+F+LFL", ["L=-RF+LFL+FR-", "R=+LF-RFR-FL+"], 90, 5, "Moore curve (closed Hilbert)"),
    "cross": ("F+F+F+F", ["F=F+F-F-FF+F+F-F"], 90, 3, "cross-stitch"),
    "islands": ("F+F+F+F", ["F=F+f-FF+F+FF+Ff+FF-f+FF-F-FF-Ff-FFF", "f=ffffff"], 90, 2, "Mandelbrot islands"),
    "tree": ("X", ["X=F[+X][-X]FX", "F=FF"], 25.7, 6, "symmetric binary tree"),
    "plant": ("X", ["X=F+[[X]-X]-F[-FX]+X", "F=FF"], 25, 5, "classic fractal plant"),
    "bush": ("F", ["F=FF-[-F+F+F]+[+F-F-F]"], 22.5, 4, "bush"),
    "weed": ("X", ["X=F[+X]F[-X]+X", "F=FF"], 20, 6, "weed"),
    "fern": ("X", ["X=F+[[X]-X]-F[-FX]+X", "F=FF"], 25, 5, "fern-like frond"),
    "seaweed": ("F", ["F=F[+F]F[-F]F"], 25.7, 5, "seaweed"),
    "pentaplexity": ("F++F++F++F++F", ["F=F++F++F|F-F++F"], 36, 3, "pentaplexity"),
    "board": ("F+F+F+F", ["F=FF+F+F+F+FF"], 90, 3, "board"),
    "sticks": ("X", ["X=F[+X]F[-X]+X", "F=FF"], 20, 7, "sticks"),
    "crystal": ("F+F+F+F", ["F=FF+F++F+F"], 90, 4, "crystal"),
    "rings": ("F+F+F+F", ["F=FF+F+F+F+F+F-F"], 90, 4, "rings"),
}

DRAW = {"arrowhead": "AB", "gosper": "AB"}   # presets whose drawing symbols are not F/G

STOCH_PRESETS = {
    "bush": ("F", ["F=0.33:F[+F]F[-F]F", "F=0.33:F[+F]F", "F=0.34:F[-F]F"], 25.7, 5),
    "weed": ("X", ["X=0.5:F[+X]F[-X]+X", "X=0.5:F[-X]F[+X]-X", "F=FF"], 20, 6),
}


# ---------------------------------------------------------------- rewriting
def parse_rules(rule_strs):
    """Return {symbol: [(weight, replacement), ...]}"""
    rules = {}
    for r in rule_strs:
        if "=" not in r:
            raise ValueError("rule %r needs the form X=replacement" % r)
        lhs, rhs = r.split("=", 1)
        lhs = lhs.strip()
        if len(lhs) != 1:
            raise ValueError("rule left side must be one symbol: %r" % r)
        w = 1.0
        if ":" in rhs:
            head, tail = rhs.split(":", 1)
            try:
                w = float(head)
                rhs = tail
            except ValueError:
                pass
        rules.setdefault(lhs, []).append((w, rhs.strip()))
    return rules


def rewrite(axiom, rules, gens, rnd=None, limit=3_000_000):
    s = axiom
    for _ in range(gens):
        out = []
        for c in s:
            opts = rules.get(c)
            if not opts:
                out.append(c)
            elif len(opts) == 1:
                out.append(opts[0][1])
            else:
                if rnd is None:
                    out.append(opts[0][1])
                else:
                    tot = sum(w for w, _ in opts)
                    x = rnd.random() * tot
                    for w, rep in opts:
                        x -= w
                        if x <= 0:
                            out.append(rep)
                            break
                    else:
                        out.append(opts[-1][1])
        s = "".join(out)
        if len(s) > limit:
            raise ValueError("string grew past %d symbols - use fewer generations" % limit)
    return s


# ---------------------------------------------------------------- turtle
def turtle(s, angle, jitter=0.0, rnd=None, step=1.0, draw="FG"):
    """Walk the string; return list of segments (x1,y1,x2,y2,depth,width_level,color_shift)."""
    x = y = 0.0
    heading = 90.0
    depth = 0
    wlevel = 0
    shift = 0
    stack = []
    segs = []
    rad = math.pi / 180
    for c in s:
        if c in draw:
            a = heading
            if jitter and rnd:
                a += rnd.uniform(-jitter, jitter)
            nx = x + step * math.cos(a * rad)
            ny = y + step * math.sin(a * rad)
            segs.append((x, y, nx, ny, depth, wlevel, shift))
            x, y = nx, ny
        elif c in "fg" and c not in draw:
            x += step * math.cos(heading * rad)
            y += step * math.sin(heading * rad)
        elif c == "+":
            heading += angle + (rnd.uniform(-jitter, jitter) if jitter and rnd else 0)
        elif c == "-":
            heading -= angle + (rnd.uniform(-jitter, jitter) if jitter and rnd else 0)
        elif c == "|":
            heading += 180
        elif c == "[":
            stack.append((x, y, heading, depth, wlevel, shift))
            depth += 1
        elif c == "]":
            if stack:
                x, y, heading, depth, wlevel, shift = stack.pop()
        elif c == "!":
            wlevel += 1
        elif c == "'":
            shift += 1
    return segs


def bounds(segs):
    xs = [v for s in segs for v in (s[0], s[2])]
    ys = [v for s in segs for v in (s[1], s[3])]
    return min(xs), min(ys), max(xs), max(ys)


def stats(s, segs):
    if not segs:
        return "no drawn segments"
    x0, y0, x1, y1 = bounds(segs)
    return "%d symbols, %d segments, width %.1f x height %.1f units, max branch depth %d" % (
        len(s), len(segs), x1 - x0, y1 - y0, max(g[4] for g in segs))


def color_for(seg, mode, maxdepth, idx, total):
    depth = seg[4]
    if mode == "depth":
        t = depth / max(maxdepth, 1)
        r = int(110 - 80 * t)
        g = int(70 + 160 * t)
        b = int(40 + 20 * t)
        return r, g, b
    if mode == "rainbow":
        t = idx / max(total, 1)
        return (int(127 + 127 * math.sin(6.28 * t)),
                int(127 + 127 * math.sin(6.28 * t + 2.1)),
                int(127 + 127 * math.sin(6.28 * t + 4.2)))
    if mode == "mono":
        return 30, 30, 30
    return 255, 255, 255


# ---------------------------------------------------------------- outputs
def to_svg(segs, path, color="depth", bg="#fdf6e3", size=800, stroke=1.2):
    x0, y0, x1, y1 = bounds(segs)
    w, h = x1 - x0 or 1, y1 - y0 or 1
    scale = (size - 40) / max(w, h)
    maxd = max(g[4] for g in segs)
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
           % (w * scale + 40, h * scale + 40, w * scale + 40, h * scale + 40),
           '<rect width="100%%" height="100%%" fill="%s"/>' % bg,
           '<g stroke-linecap="round" fill="none">']
    for k, g in enumerate(segs):
        r, gg, b = color_for(g, color, maxd, k, len(segs))
        sw = max(0.4, stroke * (0.85 ** g[5]))
        out.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="rgb(%d,%d,%d)" stroke-width="%.2f"/>' % (
            (g[0] - x0) * scale + 20, (y1 - g[1]) * scale + 20,
            (g[2] - x0) * scale + 20, (y1 - g[3]) * scale + 20, r, gg, b, sw))
    out.append("</g></svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def write_png(path, width, height, rgb_bytes):
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)

    raw = b"".join(b"\x00" + rgb_bytes[y * width * 3:(y + 1) * width * 3] for y in range(height))
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def raster(segs, size, color, bg=(253, 246, 227), ss=2):
    """Draw anti-aliased-ish lines by supersampling a plain Bresenham raster."""
    x0, y0, x1, y1 = bounds(segs)
    w, h = x1 - x0 or 1, y1 - y0 or 1
    scale = (size * ss - 20 * ss) / max(w, h)
    W, H = int(w * scale) + 20 * ss, int(h * scale) + 20 * ss
    buf = bytearray(bytes(bg) * (W * H))
    maxd = max(g[4] for g in segs)
    for k, g in enumerate(segs):
        c = bytes(color_for(g, color, maxd, k, len(segs)))
        ax, ay = int((g[0] - x0) * scale) + 10 * ss, int((y1 - g[1]) * scale) + 10 * ss
        bx, by = int((g[2] - x0) * scale) + 10 * ss, int((y1 - g[3]) * scale) + 10 * ss
        dx, dy = abs(bx - ax), -abs(by - ay)
        sx, sy = (1 if ax < bx else -1), (1 if ay < by else -1)
        err = dx + dy
        thick = 1 if g[5] > 1 else ss
        while True:
            for ox in range(thick):
                for oy in range(thick):
                    px, py = ax + ox, ay + oy
                    if 0 <= px < W and 0 <= py < H:
                        buf[(py * W + px) * 3:(py * W + px) * 3 + 3] = c
            if ax == bx and ay == by:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                ax += sx
            if e2 <= dx:
                err += dx
                ay += sy
    # downsample by ss
    if ss > 1:
        w2, h2 = W // ss, H // ss
        out = bytearray(w2 * h2 * 3)
        for y in range(h2):
            for x in range(w2):
                r = g = b = 0
                for oy in range(ss):
                    base = ((y * ss + oy) * W + x * ss) * 3
                    for ox in range(ss):
                        r += buf[base + ox * 3]
                        g += buf[base + ox * 3 + 1]
                        b += buf[base + ox * 3 + 2]
                n = ss * ss
                o = (y * w2 + x) * 3
                out[o], out[o + 1], out[o + 2] = r // n, g // n, b // n
        return w2, h2, bytes(out)
    return W, H, bytes(buf)


def braille(segs, cols, rows):
    """Plot segments on a Braille canvas (2x4 dots per character)."""
    px_w, px_h = cols * 2, rows * 4
    x0, y0, x1, y1 = bounds(segs)
    w, h = x1 - x0 or 1, y1 - y0 or 1
    scale = min((px_w - 1) / w, (px_h - 1) / h)
    grid = [[0] * cols for _ in range(rows)]
    bit = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))

    def plot(x, y):
        if 0 <= x < px_w and 0 <= y < px_h:
            grid[y // 4][x // 2] |= bit[y % 4][x % 2]

    for g in segs:
        ax, ay = int((g[0] - x0) * scale), int((y1 - g[1]) * scale)
        bx, by = int((g[2] - x0) * scale), int((y1 - g[3]) * scale)
        dx, dy = abs(bx - ax), -abs(by - ay)
        sx, sy = (1 if ax < bx else -1), (1 if ay < by else -1)
        err = dx + dy
        while True:
            plot(ax, ay)
            if ax == bx and ay == by:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                ax += sx
            if e2 <= dx:
                err += dx
                ay += sy
    return "\n".join("".join(chr(0x2800 + v) for v in row).rstrip("⠀") for row in grid)


def dedupe(segs):
    seen, out = set(), []
    for g in segs:
        key = (round(min((g[0], g[1]), (g[2], g[3]))[0], 4), round(min((g[0], g[1]), (g[2], g[3]))[1], 4),
               round(max((g[0], g[1]), (g[2], g[3]))[0], 4), round(max((g[0], g[1]), (g[2], g[3]))[1], 4))
        if key not in seen:
            seen.add(key)
            out.append(g)
    return out


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="L-system fractal and plant generator.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--preset", "-p", default=None)
    ap.add_argument("--axiom")
    ap.add_argument("--rule", "-r", action="append", default=[])
    ap.add_argument("--angle", type=float)
    ap.add_argument("-n", "--gens", type=int)
    ap.add_argument("--stoch", action="store_true", help="use the stochastic version of a preset (bush, weed)")
    ap.add_argument("--jitter", type=float, default=0.0, help="random angle wobble in degrees")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--color", default="depth", choices=["depth", "rainbow", "mono"])
    ap.add_argument("--svg")
    ap.add_argument("--png")
    ap.add_argument("--size", type=int, default=800)
    ap.add_argument("--cols", type=int, default=None, help="terminal width in characters")
    ap.add_argument("--rows", type=int, default=None)
    ap.add_argument("--string", action="store_true", help="print the final string (truncated)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--gallery", metavar="DIR", help="write every preset as SVG")
    a = ap.parse_args(argv)

    if a.list:
        for k, (ax, rules, ang, g, d) in PRESETS.items():
            print("%-13s angle %-5s gens %-2d  %s" % (k, ang, g, d))
        return 0
    if a.gallery:
        os.makedirs(a.gallery, exist_ok=True)
        for k, (ax, rules, ang, g, d) in PRESETS.items():
            s = rewrite(ax, parse_rules(rules), g)
            segs = turtle(s, ang, draw=DRAW.get(k, "FG"))
            if segs:
                to_svg(segs, os.path.join(a.gallery, k + ".svg"))
                print("wrote %s.svg (%d segments)" % (k, len(segs)))
        return 0

    rnd = random.Random(a.seed)
    if a.axiom:
        axiom, rules_s, angle, gens = a.axiom, a.rule, a.angle or 90.0, a.gens or 4
        if not rules_s:
            ap.error("--axiom needs at least one --rule")
        name = "custom"
    else:
        name = a.preset or "dragon"
        if name not in PRESETS:
            import difflib
            m = difflib.get_close_matches(name, list(PRESETS), 1)
            ap.error("unknown preset %r%s" % (name, " - did you mean %s?" % m[0] if m else ""))
        axiom, rules_s, angle, gens, _ = PRESETS[name]
        if a.stoch:
            if name not in STOCH_PRESETS:
                ap.error("no stochastic variant of %r (try: %s)" % (name, ", ".join(STOCH_PRESETS)))
            axiom, rules_s, angle, gens = STOCH_PRESETS[name]
        if a.rule:
            rules_s = a.rule
        if a.angle is not None:
            angle = a.angle
        if a.gens is not None:
            gens = a.gens
    try:
        rules = parse_rules(rules_s)
        s = rewrite(axiom, rules, gens, rnd if (a.stoch or any(len(v) > 1 for v in rules.values())) else None)
    except ValueError as e:
        print("error:", e, file=sys.stderr)
        return 2
    segs = turtle(s, angle, a.jitter, rnd, draw=DRAW.get(name, "FG") if not a.axiom else "FG")
    if not segs:
        print("nothing to draw (no F/G in the result)", file=sys.stderr)
        return 2
    segs = dedupe(segs)
    print("%s: axiom=%s angle=%g gens=%d - %s" % (name, axiom, angle, gens, stats(s, segs)), file=sys.stderr)
    if a.string:
        print(s[:2000] + ("..." if len(s) > 2000 else ""))
    wrote = False
    if a.svg:
        to_svg(segs, a.svg, a.color, size=a.size)
        print("wrote", a.svg, file=sys.stderr)
        wrote = True
    if a.png:
        w, h, data = raster(segs, a.size, a.color)
        write_png(a.png, w, h, data)
        print("wrote %s (%dx%d)" % (a.png, w, h), file=sys.stderr)
        wrote = True
    if not wrote or not (a.svg or a.png):
        import shutil
        tw, th = shutil.get_terminal_size((100, 40))
        cols = a.cols or min(tw - 1, 110)
        rows = a.rows or min(th - 3, 44)
        print(braille(segs, cols, rows))
    return 0


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
