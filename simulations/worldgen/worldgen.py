#!/usr/bin/env python3
"""worldgen.py - generate a fantasy world map: terrain, rivers, biomes, towns and names.

Pipeline: fractal noise (fBm / diamond-square) -> island mask -> thermal + hydraulic
erosion -> sea level -> temperature and rainfall -> biomes -> rivers -> settlements.
Output: colour terminal map, plain ASCII, PNG (hand-written encoder) and a text gazetteer.
No dependencies. Python 3.8+.

  python worldgen.py                               # colour map in the terminal
  python worldgen.py --seed 42 --png world.png --size 512
  python worldgen.py --seed 7 --ascii --towns 12
  python worldgen.py --method dsquare --erosion 40 --sea 0.45
  python worldgen.py --seed 3 --gazetteer
"""
import argparse
import math
import os
import random
import struct
import sys
import zlib

# ---------------------------------------------------------------- noise
class Perlin:
    def __init__(self, rnd):
        p = list(range(256))
        rnd.shuffle(p)
        self.p = p * 2

    @staticmethod
    def fade(t):
        return t * t * t * (t * (t * 6 - 15) + 10)

    @staticmethod
    def grad(h, x, y):
        h &= 7
        u, v = (x, y) if h < 4 else (y, x)
        return (u if h & 1 == 0 else -u) + (v if h & 2 == 0 else -v) * 2.0 / 2.0

    def noise(self, x, y):
        X, Y = int(math.floor(x)) & 255, int(math.floor(y)) & 255
        x -= math.floor(x)
        y -= math.floor(y)
        u, v = self.fade(x), self.fade(y)
        p = self.p
        a, b = p[X] + Y, p[X + 1] + Y
        g = self.grad
        x1 = g(p[a], x, y) * (1 - u) + g(p[b], x - 1, y) * u
        x2 = g(p[a + 1], x, y - 1) * (1 - u) + g(p[b + 1], x - 1, y - 1) * u
        return x1 * (1 - v) + x2 * v

    def fbm(self, x, y, octaves=6, lac=2.0, gain=0.5):
        s, amp, f, norm = 0.0, 1.0, 1.0, 0.0
        for _ in range(octaves):
            s += self.noise(x * f, y * f) * amp
            norm += amp
            amp *= gain
            f *= lac
        return s / norm


def normalize(grid):
    lo = min(min(r) for r in grid)
    hi = max(max(r) for r in grid)
    span = (hi - lo) or 1.0
    return [[(v - lo) / span for v in r] for r in grid]


def height_fbm(w, h, rnd, scale=3.0):
    pn = Perlin(rnd)
    ox, oy = rnd.uniform(0, 100), rnd.uniform(0, 100)
    # warp the domain a little for more natural coastlines
    pw = Perlin(rnd)
    g = []
    for y in range(h):
        row = []
        for x in range(w):
            nx, ny = x / w * scale + ox, y / h * scale + oy
            wx = nx + pw.fbm(nx * 0.7, ny * 0.7, 3) * 0.6
            wy = ny + pw.fbm(nx * 0.7 + 9, ny * 0.7 + 9, 3) * 0.6
            row.append(pn.fbm(wx, wy, 6))
        g.append(row)
    return normalize(g)


def height_dsquare(w, h, rnd, rough=0.55):
    n = 1
    while n < max(w, h) - 1:
        n *= 2
    size = n + 1
    g = [[0.0] * size for _ in range(size)]
    for c in ((0, 0), (0, n), (n, 0), (n, n)):
        g[c[1]][c[0]] = rnd.random()
    step, amp = n, 1.0
    while step > 1:
        half = step // 2
        for y in range(half, size, step):
            for x in range(half, size, step):
                avg = (g[y - half][x - half] + g[y - half][x + half] + g[y + half][x - half] + g[y + half][x + half]) / 4
                g[y][x] = avg + rnd.uniform(-amp, amp)
        for y in range(0, size, half):
            for x in range((y // half + 1) % 2 * half, size, step):
                vals = []
                for dx, dy in ((-half, 0), (half, 0), (0, -half), (0, half)):
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < size and 0 <= yy < size:
                        vals.append(g[yy][xx])
                g[y][x] = sum(vals) / len(vals) + rnd.uniform(-amp, amp)
        step //= 2
        amp *= rough
    g = [row[:w] for row in g[:h]]
    return normalize(g)


def island_mask(grid, strength):
    h, w = len(grid), len(grid[0])
    out = []
    for y in range(h):
        row = []
        for x in range(w):
            dx, dy = (x / (w - 1) - 0.5) * 2, (y / (h - 1) - 0.5) * 2
            d = min(1.0, math.sqrt(dx * dx + dy * dy) / 1.1)
            row.append(grid[y][x] * (1 - strength * d ** 2.2) - strength * 0.15 * d ** 3)
        out.append(row)
    return normalize(out)


# ---------------------------------------------------------------- erosion
def thermal_erosion(grid, iters, talus=0.012):
    h, w = len(grid), len(grid[0])
    for _ in range(iters):
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                c = grid[y][x]
                low, ld = None, 0.0
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    d = c - grid[y + dy][x + dx]
                    if d > ld:
                        ld, low = d, (x + dx, y + dy)
                if low and ld > talus:
                    mv = (ld - talus) * 0.4
                    grid[y][x] -= mv
                    grid[low[1]][low[0]] += mv
    return grid


def hydraulic_erosion(grid, drops, rnd, inertia=0.05, capacity=4.0, erode=0.3, deposit=0.3, evap=0.02, steps=30):
    """Particle-based erosion: droplets roll downhill, picking up and dropping sediment."""
    h, w = len(grid), len(grid[0])

    def sample(x, y):
        xi, yi = int(x), int(y)
        fx, fy = x - xi, y - yi
        a, b = grid[yi][xi], grid[yi][xi + 1]
        c, d = grid[yi + 1][xi], grid[yi + 1][xi + 1]
        hgt = a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy
        gx = (b - a) * (1 - fy) + (d - c) * fy
        gy = (c - a) * (1 - fx) + (d - b) * fx
        return hgt, gx, gy

    def add(x, y, amt):
        xi, yi = int(x), int(y)
        fx, fy = x - xi, y - yi
        grid[yi][xi] += amt * (1 - fx) * (1 - fy)
        grid[yi][xi + 1] += amt * fx * (1 - fy)
        grid[yi + 1][xi] += amt * (1 - fx) * fy
        grid[yi + 1][xi + 1] += amt * fx * fy

    for _ in range(drops):
        x, y = rnd.uniform(1, w - 3), rnd.uniform(1, h - 3)
        dx = dy = 0.0
        speed, water, sed = 1.0, 1.0, 0.0
        for _ in range(steps):
            hgt, gx, gy = sample(x, y)
            dx = dx * inertia - gx * (1 - inertia)
            dy = dy * inertia - gy * (1 - inertia)
            ln = math.hypot(dx, dy)
            if ln < 1e-9:
                break
            dx, dy = dx / ln, dy / ln
            nx, ny = x + dx, y + dy
            if not (1 <= nx < w - 2 and 1 <= ny < h - 2):
                break
            nh = sample(nx, ny)[0]
            delta = nh - hgt
            cap = max(-delta, 0.01) * speed * water * capacity
            if sed > cap or delta > 0:
                amt = min(delta, sed) if delta > 0 else (sed - cap) * deposit
                sed -= amt
                add(x, y, amt)
            else:
                amt = min((cap - sed) * erode, -delta)
                sed += amt
                add(x, y, -amt)
            speed = math.sqrt(max(0.0, speed * speed + delta * 4))
            water *= 1 - evap
            x, y = nx, ny
    return grid


# ---------------------------------------------------------------- climate & biomes
def climate(h, w, elev, sea, rnd, wet_bias=0.0):
    """Return (temperature, moisture) grids in 0..1."""
    pn = Perlin(rnd)
    ox, oy = rnd.uniform(0, 100), rnd.uniform(0, 100)
    temp = [[0.0] * w for _ in range(h)]
    moist = [[0.0] * w for _ in range(h)]
    for y in range(h):
        lat = abs(y / (h - 1) - 0.5) * 2          # 0 equator, 1 pole
        for x in range(w):
            e = elev[y][x]
            alt = max(0.0, (e - sea) / (1 - sea))
            temp[y][x] = max(0.0, min(1.0, 1 - lat * 0.85 - alt * 0.55 + pn.fbm(x / w * 3 + ox, y / h * 3 + oy, 3) * 0.2))
    # moisture: noise plus proximity to the sea (cheap distance transform, 2 passes)
    dist = [[0 if elev[y][x] < sea else 10 ** 6 for x in range(w)] for y in range(h)]
    for y in range(h):
        for x in range(w):
            if y:
                dist[y][x] = min(dist[y][x], dist[y - 1][x] + 1)
            if x:
                dist[y][x] = min(dist[y][x], dist[y][x - 1] + 1)
    for y in range(h - 1, -1, -1):
        for x in range(w - 1, -1, -1):
            if y < h - 1:
                dist[y][x] = min(dist[y][x], dist[y + 1][x] + 1)
            if x < w - 1:
                dist[y][x] = min(dist[y][x], dist[y][x + 1] + 1)
    for y in range(h):
        for x in range(w):
            near = math.exp(-dist[y][x] / (w * 0.12))
            n = pn.fbm(x / w * 4 + ox + 50, y / h * 4 + oy + 50, 4) * 0.5 + 0.5
            moist[y][x] = max(0.0, min(1.0, 0.45 * near + 0.55 * n + wet_bias))
    return temp, moist


BIOMES = {  # name: (rgb, ascii char)
    "deep ocean": ((18, 41, 94), "~"), "ocean": ((29, 66, 138), "~"), "shallows": ((52, 105, 175), "-"),
    "beach": ((231, 213, 150), "."), "ice": ((235, 245, 250), "*"), "tundra": ((170, 186, 170), ","),
    "taiga": ((60, 110, 90), "T"), "forest": ((38, 112, 54), "f"), "rainforest": ((12, 92, 40), "F"),
    "grassland": ((124, 170, 76), '"'), "savanna": ((178, 178, 84), ";"), "desert": ((226, 196, 118), ":"),
    "shrubland": ((140, 150, 90), "s"), "swamp": ((72, 106, 80), "%"),
    "hills": ((120, 118, 88), "n"), "mountain": ((125, 120, 115), "^"), "snowcap": ((248, 248, 252), "A"),
    "river": ((60, 120, 200), "="), "lake": ((50, 100, 180), "o"),
}


def biome(e, t, m, sea):
    if e < sea - 0.18:
        return "deep ocean"
    if e < sea - 0.05:
        return "ocean"
    if e < sea:
        return "shallows"
    if e < sea + 0.015:
        return "beach" if t > 0.25 else "ice"
    alt = (e - sea) / (1 - sea)
    if alt > 0.72:
        return "snowcap"
    if alt > 0.55:
        return "mountain"
    if t < 0.12:
        return "ice"
    if alt > 0.38:
        return "hills" if m < 0.6 else "taiga" if t < 0.4 else "hills"
    if t < 0.28:
        return "tundra" if m < 0.5 else "taiga"
    if t < 0.5:
        return "taiga" if m > 0.55 else "grassland" if m > 0.35 else "shrubland"
    if t < 0.72:
        if m > 0.7:
            return "swamp" if alt < 0.05 else "forest"
        return "forest" if m > 0.5 else "grassland" if m > 0.3 else "shrubland"
    if m > 0.68:
        return "rainforest"
    return "savanna" if m > 0.4 else "desert"


# ---------------------------------------------------------------- rivers & lakes
def make_rivers(elev, sea, rnd, count):
    h, w = len(elev), len(elev[0])
    # fill depressions crudely so water can always run to the sea
    flow = [[0] * w for _ in range(h)]
    filled = [row[:] for row in elev]
    for _ in range(3):
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if filled[y][x] >= sea:
                    m = min(filled[y + dy][x + dx] for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                                                                   (1, 1), (-1, -1), (1, -1), (-1, 1)))
                    if m >= filled[y][x]:
                        filled[y][x] = m + 1e-4
    rivers = set()
    cand = [(x, y) for y in range(h) for x in range(w) if filled[y][x] > sea + (1 - sea) * 0.45]
    rnd.shuffle(cand)
    for sx, sy in cand[:count]:
        x, y = sx, sy
        path = []
        seen = set()
        while 0 <= x < w and 0 <= y < h and filled[y][x] >= sea and (x, y) not in seen:
            seen.add((x, y))
            path.append((x, y))
            best, bv = None, filled[y][x]
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and filled[ny][nx] < bv:
                    best, bv = (nx, ny), filled[ny][nx]
            if best is None:
                break
            x, y = best
        reached_sea = not path or (x, y) not in seen and not (0 <= x < w and 0 <= y < h and filled[y][x] >= sea) or \
            (0 <= x < w and 0 <= y < h and elev[y][x] < sea)
        if len(path) > max(8, w // 20) and reached_sea:
            rivers.update(path)
    return rivers


# ---------------------------------------------------------------- names & towns
ONSETS = ["b", "br", "c", "d", "dr", "f", "g", "gl", "h", "k", "l", "m", "n", "p", "r", "s", "st", "t", "th", "v", "w", "z"]
VOW = ["a", "e", "i", "o", "u", "ae", "ia", "ou"]
CODAS = ["", "", "n", "r", "l", "s", "th", "nd", "rn", "k"]
ENDS = ["ia", "land", "mere", "dale", "ford", "wick", "haven", "mark", "reach", "shire", "moor", "fell", "gard", "ton"]


def place_name(rnd, kind="town"):
    n = "".join(rnd.choice(ONSETS) + rnd.choice(VOW) + rnd.choice(CODAS) for _ in range(1 if kind == "region" else rnd.randint(1, 2)))
    if kind == "region":
        return (n.rstrip("nrlsdk") + rnd.choice(["ia", "land", "mark", "reach", "shire", "moor"])).capitalize()
    if rnd.random() < 0.5:
        n += rnd.choice(ENDS)
    return n.capitalize()


def settle(elev, biomes, rivers, sea, rnd, count):
    h, w = len(elev), len(elev[0])
    good = {"grassland": 3, "forest": 2, "savanna": 2, "shrubland": 1, "beach": 1, "swamp": 0.3, "taiga": 1, "hills": 1.2}
    scores = []
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            b = biomes[y][x]
            if b not in good:
                continue
            s = good[b]
            near_river = any((x + dx, y + dy) in rivers for dx in range(-2, 3) for dy in range(-2, 3))
            coast = any(elev[y + dy][x + dx] < sea for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            s += 2.0 * near_river + 1.5 * coast + rnd.random() * 0.6
            scores.append((s, x, y, coast, near_river))
    scores.sort(reverse=True)
    towns, mind = [], max(4, w // 12)
    for s, x, y, coast, riv in scores:
        if all(math.hypot(x - t["x"], y - t["y"]) >= mind for t in towns):
            pop = int(300 + s * 900 * rnd.uniform(0.6, 1.6))
            towns.append({"x": x, "y": y, "name": place_name(rnd), "pop": pop, "coast": coast, "river": riv,
                          "biome": biomes[y][x]})
            if len(towns) >= count:
                break
    towns.sort(key=lambda t: -t["pop"])
    for i, t in enumerate(towns):
        t["kind"] = "capital" if i == 0 else "city" if t["pop"] > 2500 else "town" if t["pop"] > 1000 else "village"
    return towns


# ---------------------------------------------------------------- build
class World:
    pass


def generate(seed, w, h, method="fbm", sea=0.5, erosion=0, island=0.7, rivers=14, towns=10, scale=3.0, wet=0.0):
    rnd = random.Random(seed)
    base = height_dsquare(w, h, rnd) if method == "dsquare" else height_fbm(w, h, rnd, scale)
    elev = island_mask(base, island) if island > 0 else base
    if erosion:
        elev = thermal_erosion(elev, max(1, erosion // 8))
        elev = hydraulic_erosion(elev, erosion * w * h // 40, rnd)
        elev = normalize(elev)
    # pick the sea level so that `sea` of cells... is a *quantile*, so maps are never all-ocean
    flat = sorted(v for r in elev for v in r)
    sea_level = flat[int(min(0.95, max(0.05, sea)) * (len(flat) - 1))]
    temp, moist = climate(h, w, elev, sea_level, rnd, wet)
    biomes = [[biome(elev[y][x], temp[y][x], moist[y][x], sea_level) for x in range(w)] for y in range(h)]
    riv = make_rivers(elev, sea_level, rnd, rivers)
    for (x, y) in riv:
        if biomes[y][x] not in ("deep ocean", "ocean", "shallows", "mountain", "snowcap"):
            biomes[y][x] = "river"
    tw = settle(elev, biomes, riv, sea_level, rnd, towns)
    wd = World()
    wd.w, wd.h, wd.elev, wd.biomes, wd.rivers, wd.towns = w, h, elev, biomes, riv, tw
    wd.sea, wd.seed, wd.temp, wd.moist = sea_level, seed, temp, moist
    wd.name = place_name(rnd, "region")
    return wd


# ---------------------------------------------------------------- output
def shade(rgb, e, sea, nbr):
    """Simple hillshade-ish tint from the height difference to the up-left neighbour."""
    k = max(-0.25, min(0.25, (e - nbr) * 18))
    return tuple(max(0, min(255, int(c * (1 + k)))) for c in rgb)


def color_at(wd, x, y):
    b = wd.biomes[y][x]
    rgb = BIOMES[b][0]
    if b in ("deep ocean", "ocean", "shallows"):
        return rgb
    nb = wd.elev[y - 1][x - 1] if x and y else wd.elev[y][x]
    return shade(rgb, wd.elev[y][x], wd.sea, nb)


def print_color(wd):
    if os.name == "nt":
        os.system("")
    lines = []
    town_at = {(t["x"], t["y"]): t for t in wd.towns}
    for y in range(0, wd.h - 1, 2):
        row = []
        for x in range(wd.w):
            top, bot = color_at(wd, x, y), color_at(wd, x, y + 1)
            t = town_at.get((x, y)) or town_at.get((x, y + 1))
            if t:
                ch = "\x1b[1;91m●" if t["kind"] in ("capital", "city") else "\x1b[1;93m•"
                row.append("\x1b[48;2;%d;%d;%dm%s\x1b[0m" % (top[0], top[1], top[2], ch))
            else:
                row.append("\x1b[38;2;%d;%d;%dm\x1b[48;2;%d;%d;%dm▀\x1b[0m" % (top + bot))
        lines.append("".join(row))
    print("\n".join(lines))


def print_ascii(wd):
    town_at = {(t["x"], t["y"]): t for t in wd.towns}
    for y in range(0, wd.h, 2):
        row = []
        for x in range(wd.w):
            t = town_at.get((x, y)) or town_at.get((x, y + 1))
            row.append("#" if t and t["kind"] in ("capital", "city") else "+" if t else BIOMES[wd.biomes[y][x]][1])
        print("".join(row))


def write_png(path, wd, scale=1):
    w, h = wd.w * scale, wd.h * scale
    town_at = {(t["x"], t["y"]): t for t in wd.towns}
    rows = []
    for y in range(h):
        sy = y // scale
        row = bytearray(b"\x00")
        for x in range(w):
            sx = x // scale
            t = town_at.get((sx, sy))
            if t and scale >= 2 and abs(x % scale - scale // 2) <= scale // 3 and abs(y % scale - scale // 2) <= scale // 3:
                row += bytes((220, 30, 30) if t["kind"] in ("capital", "city") else (250, 200, 30))
            else:
                row += bytes(color_at(wd, sx, sy))
        rows.append(bytes(row))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))


def gazetteer(wd):
    cnt = {}
    for row in wd.biomes:
        for b in row:
            cnt[b] = cnt.get(b, 0) + 1
    total = wd.w * wd.h
    out = ["THE LAND OF %s  (seed %d, %dx%d)" % (wd.name.upper(), wd.seed, wd.w, wd.h), ""]
    land = sum(v for k, v in cnt.items() if k not in ("deep ocean", "ocean", "shallows"))
    out.append("Land covers %.0f%% of the map." % (100 * land / total))
    out.append("Terrain: " + ", ".join("%s %.0f%%" % (k, 100 * v / total) for k, v in sorted(cnt.items(), key=lambda kv: -kv[1])[:7]))
    out.append("")
    out.append("SETTLEMENTS")
    for t in wd.towns:
        notes = []
        if t["coast"]:
            notes.append("port")
        if t["river"]:
            notes.append("on a river")
        notes.append("amid " + t["biome"])
        out.append("  %-12s %-8s pop %6d  (%d,%d)  %s" % (t["name"], t["kind"], t["pop"], t["x"], t["y"], ", ".join(notes)))
    return "\n".join(out)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Fantasy world map generator.")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--width", "-W", type=int, default=None)
    ap.add_argument("--height", "-H", type=int, default=None)
    ap.add_argument("--size", type=int, default=None, help="PNG map size in cells (square-ish, default 256)")
    ap.add_argument("--method", choices=["fbm", "dsquare"], default="fbm")
    ap.add_argument("--sea", type=float, default=0.5, help="fraction of the map under water (0.05-0.95)")
    ap.add_argument("--island", type=float, default=0.7, help="0 = continent filling the map, 1 = small island")
    ap.add_argument("--erosion", type=int, default=0, help="erosion strength (0 = off, try 20-60)")
    ap.add_argument("--rivers", type=int, default=14)
    ap.add_argument("--towns", type=int, default=10)
    ap.add_argument("--scale", type=float, default=3.0, help="feature size (higher = more, smaller landmasses)")
    ap.add_argument("--wet", type=float, default=0.0, help="rainfall bias (-0.3 .. 0.3)")
    ap.add_argument("--ascii", action="store_true")
    ap.add_argument("--png")
    ap.add_argument("--pixel", type=int, default=2, help="PNG pixels per cell")
    ap.add_argument("--gazetteer", action="store_true")
    ap.add_argument("--legend", action="store_true")
    a = ap.parse_args(argv)

    import shutil
    tw, th = shutil.get_terminal_size((100, 40))
    size = a.size or 256
    if a.png:
        w, h = a.width or size, a.height or size * 3 // 4
    else:
        w = a.width or min(tw - 1, 110)
        h = a.height or min((th - 3) * 2, 70)
    seed = a.seed if a.seed is not None else random.randrange(1 << 30)
    wd = generate(seed, w, h, a.method, a.sea, a.erosion, a.island, a.rivers, a.towns, a.scale, a.wet)
    if a.png:
        write_png(a.png, wd, a.pixel)
        print("wrote %s (%dx%d px) - %s, seed %d" % (a.png, w * a.pixel, h * a.pixel, wd.name, seed))
    elif a.ascii:
        print_ascii(wd)
    else:
        print_color(wd)
    if a.legend:
        print("legend:", "  ".join("%s=%s" % (BIOMES[k][1], k) for k in BIOMES), " #=city +=town")
    if a.gazetteer or not a.png:
        print()
        print(gazetteer(wd))
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
