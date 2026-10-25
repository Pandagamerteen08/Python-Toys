#!/usr/bin/env python3
"""sortviz.py - watch sorting algorithms work in your terminal, race them, benchmark
them, or listen to them (WAV sonification).  No dependencies. Python 3.8+.

  python sortviz.py                          # animate quicksort on a shuffled array
  python sortviz.py heap --size 40 --pattern reversed
  python sortviz.py --race quick merge heap shell bubble
  python sortviz.py --bench                  # comparisons / swaps / time for every sorter
  python sortviz.py merge --audio merge.wav  # sorting you can hear
  python sortviz.py --list
"""
import argparse
import math
import os
import random
import shutil
import struct
import sys
import time
import wave

# Each algorithm is a generator over a list `a` (sorted in place). It yields
# (kind, i, j) events: "cmp" (compared a[i], a[j]), "swap" (swapped / wrote at i, j).
# Counting events gives comparison and write counts without touching the algorithms.


def bubble(a):
    n = len(a)
    for end in range(n - 1, 0, -1):
        swapped = False
        for i in range(end):
            yield "cmp", i, i + 1
            if a[i] > a[i + 1]:
                a[i], a[i + 1] = a[i + 1], a[i]
                swapped = True
                yield "swap", i, i + 1
        if not swapped:
            return


def cocktail(a):
    lo, hi = 0, len(a) - 1
    while lo < hi:
        sw = False
        for i in range(lo, hi):
            yield "cmp", i, i + 1
            if a[i] > a[i + 1]:
                a[i], a[i + 1] = a[i + 1], a[i]
                sw = True
                yield "swap", i, i + 1
        hi -= 1
        for i in range(hi, lo, -1):
            yield "cmp", i - 1, i
            if a[i - 1] > a[i]:
                a[i - 1], a[i] = a[i], a[i - 1]
                sw = True
                yield "swap", i - 1, i
        lo += 1
        if not sw:
            return


def selection(a):
    n = len(a)
    for i in range(n - 1):
        m = i
        for j in range(i + 1, n):
            yield "cmp", m, j
            if a[j] < a[m]:
                m = j
        if m != i:
            a[i], a[m] = a[m], a[i]
            yield "swap", i, m


def insertion(a):
    for i in range(1, len(a)):
        j = i
        while j > 0:
            yield "cmp", j - 1, j
            if a[j - 1] > a[j]:
                a[j - 1], a[j] = a[j], a[j - 1]
                yield "swap", j - 1, j
                j -= 1
            else:
                break


def gnome(a):
    i = 0
    while i < len(a):
        if i == 0:
            i += 1
            continue
        yield "cmp", i - 1, i
        if a[i - 1] <= a[i]:
            i += 1
        else:
            a[i - 1], a[i] = a[i], a[i - 1]
            yield "swap", i - 1, i
            i -= 1


def comb(a):
    n = len(a)
    gap, done = n, False
    while not done:
        gap = max(1, int(gap / 1.3))
        done = gap == 1
        for i in range(n - gap):
            yield "cmp", i, i + gap
            if a[i] > a[i + gap]:
                a[i], a[i + gap] = a[i + gap], a[i]
                done = False
                yield "swap", i, i + gap


def shell(a):
    n = len(a)
    gap = n // 2
    while gap > 0:
        for i in range(gap, n):
            j = i
            while j >= gap:
                yield "cmp", j - gap, j
                if a[j - gap] > a[j]:
                    a[j - gap], a[j] = a[j], a[j - gap]
                    yield "swap", j - gap, j
                    j -= gap
                else:
                    break
        gap //= 2


def quick(a):
    stack = [(0, len(a) - 1)]
    while stack:
        lo, hi = stack.pop()
        if lo >= hi:
            continue
        mid = (lo + hi) // 2           # median-of-three pivot
        for x, y in ((lo, mid), (mid, hi), (lo, mid)):
            yield "cmp", x, y
            if a[x] > a[y]:
                a[x], a[y] = a[y], a[x]
                yield "swap", x, y
        a[mid], a[hi] = a[hi], a[mid]
        yield "swap", mid, hi
        p = a[hi]
        i = lo
        for j in range(lo, hi):
            yield "cmp", j, hi
            if a[j] < p:
                if i != j:
                    a[i], a[j] = a[j], a[i]
                    yield "swap", i, j
                i += 1
        if i != hi:
            a[i], a[hi] = a[hi], a[i]
            yield "swap", i, hi
        stack.append((lo, i - 1))
        stack.append((i + 1, hi))


def heap(a):
    n = len(a)

    def sift(start, end):
        root = start
        while 2 * root + 1 <= end:
            child = 2 * root + 1
            if child + 1 <= end:
                yield "cmp", child, child + 1
                if a[child] < a[child + 1]:
                    child += 1
            yield "cmp", root, child
            if a[root] < a[child]:
                a[root], a[child] = a[child], a[root]
                yield "swap", root, child
                root = child
            else:
                return

    for start in range((n - 2) // 2, -1, -1):
        yield from sift(start, n - 1)
    for end in range(n - 1, 0, -1):
        a[0], a[end] = a[end], a[0]
        yield "swap", 0, end
        yield from sift(0, end - 1)


def merge(a):
    """Bottom-up merge sort; writes are reported as 'swap' events at the write index."""
    n = len(a)
    width = 1
    while width < n:
        for lo in range(0, n, 2 * width):
            mid, hi = min(lo + width, n), min(lo + 2 * width, n)
            left, right = a[lo:mid], a[mid:hi]
            i = j = 0
            k = lo
            while i < len(left) and j < len(right):
                yield "cmp", lo + i, mid + j
                if left[i] <= right[j]:
                    a[k] = left[i]
                    i += 1
                else:
                    a[k] = right[j]
                    j += 1
                yield "swap", k, k
                k += 1
            while i < len(left):
                a[k] = left[i]
                i += 1
                yield "swap", k, k
                k += 1
            while j < len(right):
                a[k] = right[j]
                j += 1
                yield "swap", k, k
                k += 1
        width *= 2


def counting(a):
    if not a:
        return
    lo, hi = min(a), max(a)
    cnt = [0] * (hi - lo + 1)
    for v in a:
        cnt[v - lo] += 1
    k = 0
    for v, c in enumerate(cnt):
        for _ in range(c):
            a[k] = v + lo
            yield "swap", k, k
            k += 1


def radix(a):
    if not a:
        return
    exp = 1
    mx = max(a)
    while mx // exp > 0:
        buckets = [[] for _ in range(10)]
        for v in a:
            buckets[(v // exp) % 10].append(v)
        k = 0
        for b in buckets:
            for v in b:
                a[k] = v
                yield "swap", k, k
                k += 1
        exp *= 10


def bitonic(a):
    """Bitonic sorting network; pads conceptually to a power of two (skips out-of-range)."""
    n = len(a)
    size = 1
    while size < n:
        size *= 2
    k = 2
    while k <= size:
        j = k // 2
        while j > 0:
            for i in range(size):
                l = i ^ j
                if l > i and l < n and i < n:
                    asc = (i & k) == 0
                    yield "cmp", i, l
                    if (a[i] > a[l]) == asc and a[i] != a[l]:
                        a[i], a[l] = a[l], a[i]
                        yield "swap", i, l
            j //= 2
        k *= 2
    # out-of-range padding makes plain bitonic imperfect for non power-of-two n; finish cleanly
    yield from insertion(a)


def oddeven(a):
    n = len(a)
    done = False
    while not done:
        done = True
        for start in (1, 0):
            for i in range(start, n - 1, 2):
                yield "cmp", i, i + 1
                if a[i] > a[i + 1]:
                    a[i], a[i + 1] = a[i + 1], a[i]
                    done = False
                    yield "swap", i, i + 1


def cycle(a):
    n = len(a)
    for start in range(n - 1):
        item = a[start]
        pos = start
        for i in range(start + 1, n):
            yield "cmp", i, start
            if a[i] < item:
                pos += 1
        if pos == start:
            continue
        while item == a[pos]:
            pos += 1
        a[pos], item = item, a[pos]
        yield "swap", pos, pos
        while pos != start:
            pos = start
            for i in range(start + 1, n):
                yield "cmp", i, start
                if a[i] < item:
                    pos += 1
            while item == a[pos]:
                pos += 1
            a[pos], item = item, a[pos]
            yield "swap", pos, pos


def pancake(a):
    def flip(k):
        i, j = 0, k
        while i < j:
            a[i], a[j] = a[j], a[i]
            yield "swap", i, j
            i += 1
            j -= 1

    for size in range(len(a), 1, -1):
        m = 0
        for i in range(1, size):
            yield "cmp", m, i
            if a[i] > a[m]:
                m = i
        if m != size - 1:
            if m:
                yield from flip(m)
            yield from flip(size - 1)


def stooge(a, i=0, j=None):
    if j is None:
        j = len(a) - 1
    if i >= j:
        return
    yield "cmp", i, j
    if a[i] > a[j]:
        a[i], a[j] = a[j], a[i]
        yield "swap", i, j
    if j - i + 1 > 2:
        t = (j - i + 1) // 3
        yield from stooge(a, i, j - t)
        yield from stooge(a, i + t, j)
        yield from stooge(a, i, j - t)


def bogo(a):
    """Shuffles until sorted. Only sensible for tiny arrays; capped at 200000 shuffles."""
    rnd = random.Random(1)
    for _ in range(200000):
        ok = True
        for i in range(len(a) - 1):
            yield "cmp", i, i + 1
            if a[i] > a[i + 1]:
                ok = False
                break
        if ok:
            return
        rnd.shuffle(a)
        yield "swap", 0, len(a) - 1


ALGOS = {
    "bubble": (bubble, "O(n^2)", "swap neighbours until nothing moves"),
    "cocktail": (cocktail, "O(n^2)", "bubble sort in both directions"),
    "selection": (selection, "O(n^2)", "repeatedly pick the minimum"),
    "insertion": (insertion, "O(n^2)", "grow a sorted prefix; great on nearly sorted data"),
    "gnome": (gnome, "O(n^2)", "a garden gnome sorting flower pots"),
    "comb": (comb, "O(n^2) worst", "bubble sort with shrinking gaps"),
    "shell": (shell, "~O(n^1.3)", "insertion sort with gaps"),
    "quick": (quick, "O(n log n) avg", "partition around a median-of-three pivot"),
    "heap": (heap, "O(n log n)", "binary-heap selection"),
    "merge": (merge, "O(n log n)", "bottom-up merging of runs"),
    "counting": (counting, "O(n + k)", "tally values, no comparisons"),
    "radix": (radix, "O(d n)", "LSD base-10 bucket passes"),
    "bitonic": (bitonic, "O(n log^2 n)", "sorting network (with a cleanup pass)"),
    "oddeven": (oddeven, "O(n^2)", "parallel-friendly neighbour exchanges"),
    "cycle": (cycle, "O(n^2)", "minimum possible number of writes"),
    "pancake": (pancake, "O(n^2)", "only prefix reversals allowed"),
    "stooge": (stooge, "O(n^2.7)", "recursively sort 2/3, 2/3, 2/3: deliberately slow"),
    "bogo": (bogo, "O(n!)", "shuffle until sorted (tiny arrays only!)"),
}


# ---------------------------------------------------------------- data patterns
def make_data(n, pattern, rnd):
    base = list(range(1, n + 1))
    if pattern == "shuffled":
        rnd.shuffle(base)
    elif pattern == "reversed":
        base.reverse()
    elif pattern == "sorted":
        pass
    elif pattern == "nearly":
        for _ in range(max(1, n // 10)):
            i, j = rnd.randrange(n), rnd.randrange(n)
            base[i], base[j] = base[j], base[i]
    elif pattern == "fewunique":
        base = [rnd.randint(1, 5) * (n // 5 or 1) for _ in range(n)]
    elif pattern == "sawtooth":
        base = [(i * 4) % n + 1 for i in range(n)]
    elif pattern == "organpipe":
        base = list(range(1, n // 2 + 1)) + list(range(n - n // 2, 0, -1))
        base = base[:n]
    elif pattern == "sine":
        base = [int((math.sin(i / n * 4 * math.pi) * 0.5 + 0.5) * (n - 1)) + 1 for i in range(n)]
        rnd.shuffle(base)
    elif pattern == "random":
        base = [rnd.randint(1, n) for _ in range(n)]
    else:
        raise ValueError("unknown pattern %r" % pattern)
    return base


PATTERNS = ["shuffled", "reversed", "sorted", "nearly", "fewunique", "sawtooth",
            "organpipe", "sine", "random"]


# ---------------------------------------------------------------- running / measuring
def run(name, data):
    """Sort a copy to completion; return (sorted_list, comparisons, swaps, seconds)."""
    a = list(data)
    cmp_n = sw_n = 0
    t0 = time.perf_counter()
    for kind, _, _ in ALGOS[name][0](a):
        if kind == "cmp":
            cmp_n += 1
        else:
            sw_n += 1
    return a, cmp_n, sw_n, time.perf_counter() - t0


# ---------------------------------------------------------------- terminal drawing
BLOCKS = " ▁▂▃▄▅▆▇█"
RESET = "\x1b[0m"


def setup_term():
    if os.name == "nt":
        os.system("")
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass


def rgb(t):
    """Rainbow-ish colour for t in 0..1."""
    r = int(127 + 127 * math.sin(6.28 * t))
    g = int(127 + 127 * math.sin(6.28 * t + 2.1))
    b = int(127 + 127 * math.sin(6.28 * t + 4.2))
    return r, g, b


def draw_bars(a, hi_cmp, hi_swap, height, color=True):
    n, mx = len(a), max(a) if a else 1
    lines = []
    for row in range(height, 0, -1):
        out = []
        for idx, v in enumerate(a):
            eighths = v / mx * height * 8
            full = int(eighths // 8)
            if row <= full:
                ch = "█"
            elif row == full + 1:
                ch = BLOCKS[int(eighths % 8)]
            else:
                ch = " "
            if ch == " ":
                out.append(" ")
                continue
            if color:
                if idx in hi_swap:
                    out.append("\x1b[1;91m%s%s" % (ch, RESET))
                elif idx in hi_cmp:
                    out.append("\x1b[1;97m%s%s" % (ch, RESET))
                else:
                    r, g, b = rgb(v / mx * 0.8)
                    out.append("\x1b[38;2;%d;%d;%dm%s%s" % (r, g, b, ch, RESET))
            else:
                out.append(ch)
        lines.append("".join(out))
    return lines


def animate(name, data, fps, no_color, steps_per_frame):
    setup_term()
    cols, rows = shutil.get_terminal_size((80, 24))
    height = max(6, rows - 5)
    a = list(data)
    n = len(a)
    if n > cols:
        sys.exit("array size %d is wider than your terminal (%d columns); use --size %d" % (n, cols, cols))
    gen = ALGOS[name][0](a)
    cmp_n = sw_n = 0
    t0 = time.time()
    sys.stdout.write("\x1b[2J\x1b[?25l")
    try:
        done = False
        while not done:
            hc, hs = set(), set()
            for _ in range(steps_per_frame):
                try:
                    kind, i, j = next(gen)
                except StopIteration:
                    done = True
                    break
                if kind == "cmp":
                    cmp_n += 1
                    hc.update((i, j))
                else:
                    sw_n += 1
                    hs.update((i, j))
            frame = draw_bars(a, hc, hs, height, not no_color)
            head = " %s  %s   n=%d  comparisons=%d  writes=%d  %.1fs" % (
                name, ALGOS[name][1], n, cmp_n, sw_n, time.time() - t0)
            sys.stdout.write("\x1b[H" + head + "\x1b[K\n" + "\n".join(frame) + "\x1b[J")
            sys.stdout.flush()
            time.sleep(1.0 / fps)
        # victory sweep
        for k in range(n + 1):
            frame = draw_bars(a, set(), set(range(k)), height, not no_color)
            sys.stdout.write("\x1b[H" + " sorted!" + "\x1b[K\n" + "\n".join(frame))
            sys.stdout.flush()
            time.sleep(0.4 / max(n, 1))
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[?25h\x1b[0m\n")
    ok = all(a[i] <= a[i + 1] for i in range(n - 1))
    print("%s: %s - %d comparisons, %d writes" % (name, "sorted correctly" if ok else "NOT SORTED", cmp_n, sw_n))


def race(names, data, fps, no_color):
    setup_term()
    cols, rows = shutil.get_terminal_size((80, 24))
    k = len(names)
    n = len(data)
    panel_h = max(4, (rows - 3) // k - 1)
    arrays = [list(data) for _ in names]
    gens = [ALGOS[nm][0](ar) for nm, ar in zip(names, arrays)]
    counts = [[0, 0] for _ in names]
    finish = [None] * k
    t0 = time.time()
    step = 0
    sys.stdout.write("\x1b[2J\x1b[?25l")
    try:
        while any(f is None for f in finish):
            hc = [set() for _ in names]
            hs = [set() for _ in names]
            for idx, g in enumerate(gens):
                if finish[idx] is not None:
                    continue
                try:
                    kind, i, j = next(g)
                except StopIteration:
                    finish[idx] = (sum(1 for f in finish if f is not None) + 1, step)
                    continue
                if kind == "cmp":
                    counts[idx][0] += 1
                    hc[idx].update((i, j))
                else:
                    counts[idx][1] += 1
                    hs[idx].update((i, j))
            step += 1
            if step % 3 == 0 or all(f is not None for f in finish):
                out = ["\x1b[H race: one step per sorter per tick   tick %d\x1b[K" % step]
                for idx, nm in enumerate(names):
                    tag = (" FINISHED #%d" % finish[idx][0]) if finish[idx] else ""
                    out.append(" %-9s cmp=%-7d wr=%-7d%s\x1b[K" % (nm, counts[idx][0], counts[idx][1], tag))
                    out.extend(draw_bars(arrays[idx], hc[idx], hs[idx], panel_h, not no_color))
                sys.stdout.write("\n".join(out) + "\x1b[J")
                sys.stdout.flush()
                time.sleep(1.0 / fps)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[?25h\x1b[0m\n")
    print("podium (by ticks, one tick = one comparison or write):")
    for nm, f in sorted(zip(names, finish), key=lambda x: x[1][1] if x[1] else 1 << 60):
        print("  %-9s %s" % (nm, "%d ticks" % f[1] if f else "did not finish"))


# ---------------------------------------------------------------- sound
def sonify(name, data, path, rate=22050, max_seconds=60):
    """Each event becomes a short tone whose pitch follows the value being touched."""
    a = list(data)
    mx = max(a)
    count = sum(1 for _ in ALGOS[name][0](list(data)))
    dur = min(0.03, max_seconds / max(count, 1))
    nsamp = max(1, int(rate * dur))
    twopi = 2 * math.pi
    pcm = bytearray()
    phase = 0.0
    for kind, i, j in ALGOS[name][0](a):      # a is mutated live, so a[i] is the current value
        v = a[i]
        freq = 200 + 1000 * v / mx
        amp = 0.35 if kind == "swap" else 0.2
        step = twopi * freq / rate
        for s in range(nsamp):
            env = min(1.0, s / 20.0, (nsamp - s) / 20.0)
            phase += step
            pcm += struct.pack("<h", int(32767 * amp * env * math.sin(phase)))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(pcm))
    return count, len(pcm) / 2 / rate


def bench(names, sizes, pattern, seed):
    rnd = random.Random(seed)
    print("pattern=%s  seed=%d" % (pattern, seed))
    for n in sizes:
        data = make_data(n, pattern, rnd)
        print("\nn = %d" % n)
        print("  %-10s %12s %12s %10s  %s" % ("algorithm", "comparisons", "writes", "ms", "ok"))
        rows = []
        for nm in names:
            if nm == "bogo" and n > 8:
                continue
            if nm == "stooge" and n > 300:
                continue
            a, c, s, t = run(nm, data)
            rows.append((c + s, nm, c, s, t, a == sorted(data)))
        for _, nm, c, s, t, ok in sorted(rows):
            print("  %-10s %12d %12d %10.2f  %s" % (nm, c, s, t * 1000, "yes" if ok else "NO"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sorting algorithm visualizer, racer and benchmark.")
    ap.add_argument("algo", nargs="?", default="quick", help="algorithm name (see --list)")
    ap.add_argument("-n", "--size", type=int, default=None)
    ap.add_argument("-p", "--pattern", default="shuffled", choices=PATTERNS)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--speed", type=int, default=None, help="algorithm steps per frame")
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument("--race", nargs="+", metavar="ALGO")
    ap.add_argument("--bench", nargs="*", metavar="ALGO", help="benchmark (default: all)")
    ap.add_argument("--sizes", default="100,1000", help="bench sizes, comma separated")
    ap.add_argument("--audio", metavar="WAV", help="write a sonification instead of animating")
    ap.add_argument("--no-anim", action="store_true", help="just sort and print stats")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)

    if a.list:
        print("%-10s %-15s %s" % ("algorithm", "complexity", "idea"))
        for k, (_, c, d) in ALGOS.items():
            print("%-10s %-15s %s" % (k, c, d))
        print("\npatterns:", ", ".join(PATTERNS))
        return 0

    seed = a.seed if a.seed is not None else random.randrange(1 << 30)
    rnd = random.Random(seed)

    if a.bench is not None:
        names = a.bench or [k for k in ALGOS if k not in ("bogo",)]
        for nm in names:
            if nm not in ALGOS:
                ap.error("unknown algorithm %r" % nm)
        bench(names, [int(x) for x in a.sizes.split(",")], a.pattern, seed)
        return 0

    names = a.race if a.race else [a.algo]
    for nm in names:
        if nm not in ALGOS:
            import difflib
            m = difflib.get_close_matches(nm, list(ALGOS), 1)
            ap.error("unknown algorithm %r%s" % (nm, " - did you mean %s?" % m[0] if m else ""))

    cols = shutil.get_terminal_size((80, 24)).columns
    n = a.size or (24 if "bogo" in names else (min(60, cols - 2) if not a.race else min(40, cols - 2)))
    if "bogo" in names and n > 8 and not a.size:
        n = 7
    data = make_data(n, a.pattern, rnd)

    if a.audio:
        ev, secs = sonify(names[0], data, a.audio)
        print("wrote %s (%d events, %.1f s)" % (a.audio, ev, secs))
        return 0
    if a.no_anim or not sys.stdout.isatty():
        for nm in names:
            out, c, s, t = run(nm, data)
            print("%-10s n=%d  comparisons=%d  writes=%d  %.2f ms  %s" % (
                nm, n, c, s, t * 1000, "sorted" if out == sorted(data) else "NOT SORTED"))
        return 0
    if a.race:
        race(names, data, a.fps, a.no_color)
    else:
        spf = a.speed or max(1, n // 12)
        animate(names[0], data, a.fps, a.no_color, spf)
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
