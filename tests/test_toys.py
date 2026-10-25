#!/usr/bin/env python3
"""test_toys.py - unit tests for every toy currently in the repository.

Run from the repository root:

    python -m unittest discover -s tests -v

Nothing is imported by package name because the toy folders reuse stdlib names
(``math/``, ``audio/``, ``secrets``-style helpers), so each script is loaded from
its path instead. The tests check results - known test vectors, conservation of
cell counts, round-trips, determinism from a seed - not merely that a script
starts up.
"""
import argparse
import importlib.util
import math
import os
import random
import struct
import sys
import tempfile
import unittest
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name, relpath):
    """Import a single-file script by path under a private module name."""
    path = os.path.join(ROOT, relpath)
    if not os.path.isfile(path):
        raise unittest.SkipTest("%s is not in this checkout" % relpath)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- cipher
class CipherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load("toy_cipher", os.path.join("utilities", "cipher.py"))

    def test_published_test_vectors(self):
        m = self.m
        self.assertEqual(m.caesar("HELLO", 3), "KHOOR")
        self.assertEqual(m.vigenere("ATTACKATDAWN", "LEMON"), "LXFOPVEFRNHR")
        self.assertEqual(m.railfence("WEAREDISCOVEREDFLEEATONCE", 3),
                         "WECRLTEERDSOEEFEAOCAIVDEN")
        self.assertEqual(m.playfair("hide the gold in the tree stump", "playfair example"),
                         "BMODZBXDNABEKUDMUIXMMOUVIF")
        self.assertEqual(m.affine("AFFINE", "5,8"), "IHHWVC")
        self.assertEqual(m.hill("HELP", "3,3,2,5"), "HIAT")
        self.assertEqual(m.morse("SOS"), "... --- ...")

    def test_enigma_m3_known_answers(self):
        """Default M3 rotor set (I II III), reflector B, rings AAA, start AAA."""
        m = self.m
        self.assertEqual(m.Enigma().run("AAAAA"), "BDZGO")
        # A press only depends on the rotor positions reached before it, so a longer
        # message must extend the shorter one rather than change it.
        six = m.Enigma().run("AAAAAA")
        self.assertEqual(len(six), 6)
        self.assertTrue(six.startswith("BDZGO"))

    def test_enigma_is_reciprocal_with_plugboard(self):
        m = self.m
        msg = "ENIGMAISRECIPROCAL"
        enc = m.Enigma(plug="AB CD EF").run(msg)
        self.assertNotEqual(enc, msg)
        dec = m.Enigma(plug="AB CD EF").run(enc)
        self.assertEqual(dec, msg)

    def test_enigma_double_step_advances_middle_rotor_at_notch(self):
        """Rotor II's notch is E: with the middle already on E, one press pushes both
        the middle and the left rotor (the historical double-step anomaly)."""
        m = self.m
        e = m.Enigma(start="AEA")            # left A, middle on notch E, right A
        e.press("A")
        self.assertEqual(e.position(), "BFB")   # left AND middle advanced, right normal

    def test_enigma_rejects_bad_settings(self):
        m = self.m
        with self.assertRaises(ValueError):
            m.Enigma(rotors=("I", "II"))
        with self.assertRaises(ValueError):
            m.Enigma(rotors=("I", "I", "III"))
        with self.assertRaises(ValueError):
            m.Enigma(start="AB")
        with self.assertRaises(ValueError):
            m.Enigma(plug="AA")

    def test_round_trips(self):
        m = self.m
        msg = "Attack at Dawn! 123"
        letters_only = "ATTACKATDAWN"
        exact = {
            "caesar": 7, "affine": "5,8", "vigenere": "LEMON", "beaufort": "KEY",
            "autokey": "QUEEN", "substitution": "ZEBRAS", "railfence": 4,
            "scytale": 5, "xor": "correct horse", "base64": None, "base32": None,
            "base85": None, "hex": None, "binary": None, "url": None,
        }
        for name, key in exact.items():
            fn = m.CIPHERS[name][0]
            text = msg if name in ("base64", "base32", "base85", "hex", "binary", "url", "xor") else letters_only
            dec = fn(fn(text, key), key, decode=True)
            self.assertEqual(dec.strip(), text, "round-trip failed for %s" % name)
        # These pad the message (X fillers, paired letters), so the plaintext returns as a prefix.
        for name, key in {"playfair": "MONARCHY", "columnar": "ZEBRAS", "hill": "3,3,2,5"}.items():
            fn = m.CIPHERS[name][0]
            self.assertTrue(fn(fn(letters_only, key), key, decode=True).startswith(letters_only), name)
        self.assertEqual(m.atbash(m.atbash(msg)), msg)
        self.assertEqual(m.reverse(m.reverse(msg)), msg)
        self.assertEqual(m.morse(m.morse("SOS SOS"), decode=True), "SOS SOS")
        self.assertEqual(m.leet(m.leet("elite"), decode=True), "elite")

    def test_caesar_cracker_recovers_shift(self):
        m = self.m
        plain = "the quick brown fox jumps over the lazy dog"
        ct = m.caesar(plain, 11)
        best = m.crack_caesar(ct)[0]
        self.assertEqual(best[1], 11)
        self.assertEqual(best[2], plain)

    def test_vigenere_cracker_recovers_key_length_and_most_letters(self):
        """The cracker is a frequency heuristic, not a proof: it must find the right
        key length and recover the large majority of the plaintext."""
        m = self.m
        plain = ("It was the best of times, it was the worst of times, it was the age "
                 "of wisdom, it was the age of foolishness, it was the epoch of belief.")
        ct = m.vigenere(plain, "LEMON")
        key, recovered = m.crack_vigenere(ct)
        self.assertEqual(len(key), 5)
        hits = sum(a == b for a, b in zip(recovered.lower(), plain))
        self.assertGreaterEqual(hits / len(plain), 0.8)

    def test_index_of_coincidence_separates_english_from_random(self):
        m = self.m
        english = ("It was the best of times, it was the worst of times, it was the age "
                   "of wisdom, it was the age of foolishness, it was the epoch of belief, "
                   "it was the season of light, it was the season of darkness.")
        rnd = random.Random(7)
        random_letters = "".join(rnd.choice(m.A) for _ in range(len(english)))
        self.assertGreater(m.index_of_coincidence(english), 0.06)     # English ~0.066
        self.assertLess(m.index_of_coincidence(random_letters), 0.05)  # random ~0.038

    def test_case_and_punctuation_preserved(self):
        self.assertEqual(self.m.caesar("Hello, World!", 1), "Ifmmp, Xpsme!")
        self.assertEqual(self.m.caesar("Hello, World!", 1, decode=True), "Gdkkn, Vnqkc!")

    def test_affine_rejects_non_invertible_key(self):
        with self.assertRaises(ValueError):
            self.m.affine("HELLO", "2,3")


# ---------------------------------------------------------------- sortviz
class SortvizTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load("toy_sortviz", os.path.join("math", "sortviz", "sortviz.py"))

    def data(self, n=40, pattern="shuffled", seed=3):
        return self.m.make_data(n, pattern, random.Random(seed))

    def test_every_algorithm_sorts(self):
        for name in self.m.ALGOS:
            n = 6 if name == "bogo" else 40
            size = 12 if name == "stooge" else n
            data = self.data(size, "shuffled", seed=5)
            out, cmps, writes, secs = self.m.run(name, data)
            self.assertEqual(out, sorted(data), "%s did not sort" % name)
            self.assertGreaterEqual(cmps + writes, 0)
            self.assertGreaterEqual(secs, 0.0)

    def test_every_algorithm_handles_sorted_reversed_and_duplicates(self):
        for name in ("bubble", "insertion", "selection", "merge", "quick", "heap",
                     "shell", "comb", "cycle", "pancake", "oddeven", "counting",
                     "radix", "bitonic"):
            for pattern in ("sorted", "reversed", "fewunique", "random"):
                data = self.data(24, pattern, seed=9)
                out = self.m.run(name, data)[0]
                self.assertEqual(out, sorted(data), "%s failed on %s" % (name, pattern))

    def test_comparison_sorters_do_compare_but_counting_and_radix_do_not(self):
        data = self.data(30)
        self.assertGreater(self.m.run("bubble", data)[1], 0)
        self.assertEqual(self.m.run("counting", data)[1], 0)
        self.assertEqual(self.m.run("radix", data)[1], 0)

    def test_insertion_sort_is_linear_on_sorted_input(self):
        data = self.data(60, "sorted")
        cmps = self.m.run("insertion", data)[1]
        self.assertEqual(cmps, len(data) - 1)

    def test_bubble_sort_early_exit_on_sorted_input(self):
        data = self.data(50, "sorted")
        self.assertEqual(self.m.run("bubble", data)[1], len(data) - 1)

    def test_run_does_not_mutate_input(self):
        data = self.data(25)
        snapshot = list(data)
        self.m.run("quick", data)
        self.assertEqual(data, snapshot)

    def test_same_seed_same_data(self):
        self.assertEqual(self.m.make_data(30, "shuffled", random.Random(4)),
                         self.m.make_data(30, "shuffled", random.Random(4)))

    def test_patterns_have_requested_size_and_span(self):
        for pattern in self.m.PATTERNS:
            data = self.data(31, pattern)
            self.assertEqual(len(data), 31, pattern)
            self.assertLessEqual(max(data), 31, pattern)
            self.assertGreaterEqual(min(data), 0, pattern)

    def test_merge_writes_every_slot_once_per_pass(self):
        """Bottom-up merge rewrites all n slots on each of its log2(n) passes."""
        data = self.data(16, "reversed")
        _, _, writes, _ = self.m.run("merge", data)
        self.assertEqual(writes, 16 * 4)

    def test_draw_bars_dimensions(self):
        data = self.data(10)
        lines = self.m.draw_bars(data, {0}, {1}, 5, color=False)
        self.assertEqual(len(lines), 5)
        for line in lines:
            self.assertEqual(len(line), len(data))

    def test_sonify_writes_playable_wav(self):
        data = self.data(12)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sort.wav")
            events, secs = self.m.sonify("quick", data, path)
            self.assertGreater(events, 0)
            self.assertGreater(secs, 0)
            with wave.open(path, "rb") as w:
                self.assertEqual(w.getnchannels(), 1)
                self.assertEqual(w.getsampwidth(), 2)
                self.assertEqual(w.getframerate(), 22050)
                self.assertGreater(w.getnframes(), 0)


# ---------------------------------------------------------------- lsystem
class LsystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load("toy_lsystem", os.path.join("math", "lsystem", "lsystem.py"))

    def test_rewrite_expands_one_generation(self):
        rules = self.m.parse_rules(["F=F+F-F-F+F"])
        self.assertEqual(self.m.rewrite("F", rules, 1), "F+F-F-F+F")
        self.assertEqual(self.m.rewrite("F", rules, 2).count("F"), 5 * 5)

    def test_rewrite_keeps_unknown_symbols(self):
        rules = self.m.parse_rules(["X=FX"])
        self.assertEqual(self.m.rewrite("XY", rules, 1), "FXY")

    def test_rewrite_rejects_runaway_strings(self):
        rules = self.m.parse_rules(["F=FFFF"])
        with self.assertRaises(ValueError):
            self.m.rewrite("F", rules, 30)

    def test_rule_parsing_weights_and_errors(self):
        rules = self.m.parse_rules(["F=0.6:FF", "F=0.4:F[+F]F"])
        self.assertEqual([w for w, _ in rules["F"]], [0.6, 0.4])
        self.assertEqual(rules["F"][1][1], "F[+F]F")
        with self.assertRaises(ValueError):
            self.m.parse_rules(["FX=FF"])
        with self.assertRaises(ValueError):
            self.m.parse_rules(["no equals sign"])

    def test_turtle_draws_one_segment_per_draw_symbol(self):
        segs = self.m.turtle("F+F+F", 90)
        self.assertEqual(len(segs), 3)

    def test_turtle_brackets_restore_state(self):
        """[ and ] must return to the saved position, so a branch does not move the turtle."""
        plain = self.m.turtle("F F F", 90)                  # spaces ignored by the turtle
        branched = self.m.turtle("F[+F]F F", 90)
        self.assertEqual(plain[-1][2:4], branched[-1][2:4])

    def test_turtle_geometry(self):
        """Four left turns at 90 degrees close a unit square; the Koch expansion keeps
        unit segment length but grows to five segments."""
        square = self.m.turtle("F+F+F+F", 90)
        self.assertEqual(len(square), 4)
        self.assertAlmostEqual(square[-1][2], square[0][0], places=9)
        self.assertAlmostEqual(square[-1][3], square[0][1], places=9)
        for x1, y1, x2, y2, *_ in square:
            self.assertAlmostEqual(math.hypot(x2 - x1, y2 - y1), 1.0, places=9)
        koch = self.m.turtle(self.m.rewrite("F", self.m.parse_rules(["F=F+F-F-F+F"]), 1), 90)
        self.assertEqual(len(koch), 5)

    def test_presets_all_build_and_draw(self):
        for name, (axiom, rules, angle, gens, _desc) in self.m.PRESETS.items():
            s = self.m.rewrite(axiom, self.m.parse_rules(rules), gens)
            segs = self.m.turtle(s, angle, draw=self.m.DRAW.get(name, "FG"))
            self.assertGreater(len(segs), 0, name)

    def test_svg_and_png_output(self):
        segs = self.m.turtle(self.m.rewrite("F", self.m.parse_rules(["F=F+F-F-F+F"]), 3), 90)
        with tempfile.TemporaryDirectory() as tmp:
            svg = os.path.join(tmp, "k.svg")
            png = os.path.join(tmp, "k.png")
            self.m.to_svg(segs, svg, size=120)
            with open(svg, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("<svg", text)
            self.assertEqual(text.count("<line"), len(segs))
            w, h, data = self.m.raster(segs, 100, "depth", ss=1)
            self.m.write_png(png, w, h, data)
            with open(png, "rb") as fh:
                head = fh.read(33)
            self.assertEqual(head[:8], b"\x89PNG\r\n\x1a\n")
            iw, ih = struct.unpack(">II", head[16:24])
            self.assertEqual((iw, ih), (w, h))
            self.assertEqual(len(data), w * h * 3)

    def test_braille_output_is_unicode_and_non_empty(self):
        segs = self.m.turtle(self.m.rewrite("F", self.m.parse_rules(["F=F+F-F-F+F"]), 2), 90)
        art = self.m.braille(segs, 30, 10)
        self.assertTrue(art.strip())
        self.assertTrue(any(0x2800 <= ord(c) <= 0x28FF for c in art))

    def test_stochastic_preset_is_seed_deterministic(self):
        axiom, rules, angle, gens = self.m.STOCH_PRESETS["bush"]
        parsed = self.m.parse_rules(rules)
        a = self.m.rewrite(axiom, parsed, gens, random.Random(11))
        b = self.m.rewrite(axiom, parsed, gens, random.Random(11))
        c = self.m.rewrite(axiom, parsed, gens, random.Random(12))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_dedupe_never_grows_and_drops_exact_repeats(self):
        segs = [(0, 0, 1, 0, 0, 0, 0), (0, 0, 1, 0, 0, 0, 0), (1, 0, 2, 0, 0, 0, 0)]
        out = self.m.dedupe(segs)
        self.assertEqual(len(out), 2)


# ---------------------------------------------------------------- fractals
def fractals_namespace(fractals_module, **over):
    ns = dict(set=None, preset=None, cx=None, cy=None, zoom=None, c=None, p=None,
              power=None, mode="smooth", palette="fire", invert=False, scale=1.0,
              shift=0.0, bail=16.0, iter=None)
    ns.update(over)
    return argparse.Namespace(**ns)


class FractalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load("toy_fractals", os.path.join("math", "fractals", "fractals.py"))

    def params(self, **over):
        return self.m.build_params(fractals_namespace(self.m, **over))

    def test_mandelbrot_interior_and_exterior(self):
        P = self.params(iter=50)
        self.assertIsNone(self.m.point(P, 0.0, 0.0, 0.001))     # origin never escapes
        self.assertIsNone(self.m.point(P, -1.0, 0.0, 0.001))    # period-2 bulb
        self.assertIsNotNone(self.m.point(P, 2.0, 2.0, 0.001))  # far outside

    def test_julia_known_interior_point(self):
        P = self.params(set="julia", c="-0.8,0.156", iter=60)
        self.assertIsNone(self.m.point(P, 0.0, 0.0, 0.001))

    def test_newton_labels_the_basin_it_converges_to(self):
        """The colour parameter is the root index plus a fade; starting exactly on the
        root z = 1 must return the first basin (index 0, fade 1 on iteration 0)."""
        P = self.params(set="newton", power=3, iter=60)
        val = self.m.point(P, 1.0, 0.0, 0.001)
        self.assertIsNotNone(val)
        self.assertAlmostEqual(val, 1.0, places=6)

    def test_render_grid_shape_and_colour_range(self):
        P = self.params(iter=40)
        img = self.m.render_rgb(P, 12, 8, jobs=1)
        self.assertEqual(len(img), 8)
        for row in img:
            self.assertEqual(len(row), 12)
            for px in row:
                self.assertEqual(len(px), 3)
                self.assertTrue(all(0 <= v <= 255 for v in px))

    def test_centre_pixel_is_inside_set_colour(self):
        P = self.params(iter=60)
        img = self.m.render_rgb(P, 9, 9, jobs=1)   # centre is near (-0.5, 0): inside
        self.assertEqual(img[4][4], (0, 0, 0))

    def test_render_is_deterministic(self):
        P = self.params(preset="seahorse", iter=40)
        a = self.m.render_rgb(P, 10, 6, jobs=1)
        b = self.m.render_rgb(P, 10, 6, jobs=1)
        self.assertEqual(a, b)

    def test_palette_lut(self):
        lut = self.m.make_lut("fire")
        self.assertEqual(len(lut), self.m.LUTN)
        self.assertTrue(all(0 <= c <= 255 for px in lut for c in px))
        inv = self.m.make_lut("fire", invert=True)
        self.assertEqual(inv[0], tuple(255 - c for c in lut[0]))

    def test_downsample_averages_pixels(self):
        img = [[(0, 0, 0), (10, 10, 10)], [(20, 20, 20), (30, 30, 30)]]
        self.assertEqual(self.m.downsample(img, 2), [[(15, 15, 15)]])

    def test_png_writer_header(self):
        P = self.params(iter=20)
        img = self.m.render_rgb(P, 7, 5, jobs=1)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "f.png")
            self.m.save_png(path, img)
            with open(path, "rb") as fh:
                raw = fh.read()
            self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", raw[16:24]), (7, 5))

    def test_lzw_round_trip(self):
        """Includes a run long enough to cross the 9->10 bit code-width boundary and
        the 4095-entry dictionary reset."""
        rnd = random.Random(2)
        for n in (1, 5, 300, 5000):
            src = [rnd.randrange(1, 256) for _ in range(n)]
            self.assertEqual(gif_lzw_decode(self.m.lzw(src)), src, "n=%d" % n)

    def test_gif_writer_structure(self):
        P = self.params(iter=20)
        img = self.m.render_rgb(P, 6, 4, jobs=1)
        idx = [[self.m.gif_index(self.m.point(P, 0.0, 0.0, .01), P) for _ in range(6)] for _ in range(4)]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.gif")
            self.m.write_gif(path, [idx, idx], 6, 4, self.m.make_lut("fire"), 5)
            with open(path, "rb") as fh:
                raw = fh.read()
            size, frames = gif_structure(raw)
            self.assertEqual(size, (6, 4))
            self.assertEqual(frames, 2)
            self.assertIn(b"NETSCAPE2.0", raw)
            self.assertEqual(raw[-1:], b"\x3b")

    def test_params_from_preset(self):
        P = self.params(preset="seahorse")
        self.assertEqual(P["kind"], "mandelbrot")
        self.assertAlmostEqual(P["zoom"], 400)
        self.assertAlmostEqual(P["cx"], -0.743643887037151)
        self.assertAlmostEqual(P["cy"], 0.131825904205330)
        self.assertEqual(P["maxit"], int(120 + 70 * math.log2(401)))
        self.assertIn("mandelbrot", self.m.describe(P))


def gif_structure(raw):
    """Walk a GIF file block by block; return ((width, height), image count)."""
    def skip_blocks(pos):
        while True:
            n = raw[pos]
            pos += 1
            if n == 0:
                return pos
            pos += n

    if raw[:6] != b"GIF89a":
        raise ValueError("not a GIF89a file")
    width, height = struct.unpack("<HH", raw[6:10])
    flags = raw[10]
    pos = 13
    if flags & 0x80:                       # global colour table follows
        pos += 3 * (2 ** ((flags & 0x07) + 1))
    frames = 0
    while pos < len(raw):
        block = raw[pos]
        if block == 0x3B:                  # trailer
            break
        if block == 0x21:                  # extension: label byte, then sub-blocks
            pos = skip_blocks(pos + 2)
        elif block == 0x2C:                # image descriptor
            frames += 1
            # 0x2C + 4x uint16 + flags byte, then the LZW minimum code size byte
            pos = skip_blocks(pos + 11)
        else:
            raise ValueError("unexpected block 0x%02x at offset %d" % (block, pos))
    return (width, height), frames


def gif_lzw_decode(data):
    """Reference GIF LZW decoder used only to verify the toy's encoder."""
    clear, eoi = 256, 257
    size, nxt, prev = 9, 258, None
    table = {i: [i] for i in range(256)}
    out = []
    acc = bits = pos = 0
    while True:
        while bits < size and pos < len(data):
            acc |= data[pos] << bits
            bits += 8
            pos += 1
        if bits < size:
            break
        code = acc & ((1 << size) - 1)
        acc >>= size
        bits -= size
        if code == clear:
            table, nxt, size, prev = {i: [i] for i in range(256)}, 258, 9, None
            continue
        if code == eoi:
            break
        if code in table:
            entry = table[code]
        elif prev is not None:
            entry = prev + [prev[0]]
        else:
            raise ValueError("invalid LZW stream")
        out.extend(entry)
        if prev is not None:
            table[nxt] = prev + [entry[0]]
            nxt += 1
            # The decoder is always one dictionary entry behind the encoder, so it must
            # widen at 2^size rather than at 2^size + 1.
            if nxt >= (1 << size) and size < 12:
                size += 1
        prev = entry
    return out


# ---------------------------------------------------------------- lifegame
class LifeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load("toy_lifegame", os.path.join("simulations", "lifegame.py"))
        cls.B, cls.S = cls.m.parse_rule("life")

    def step(self, cells):
        return self.m.step(cells, self.B, self.S)

    def test_block_is_a_still_life(self):
        block = {(0, 0), (1, 0), (0, 1), (1, 1)}
        self.assertEqual(self.step(block), block)

    def test_blinker_oscillates_with_period_two(self):
        horiz = {(0, 0), (1, 0), (2, 0)}
        vert = self.step(horiz)
        self.assertEqual(vert, {(1, -1), (1, 0), (1, 1)})
        self.assertEqual(self.step(vert), horiz)

    def test_glider_keeps_its_shape_and_moves_one_cell_every_four_generations(self):
        start = self.m.from_rows(self.m.PATTERNS["glider"])
        cells = set(start)
        for _ in range(4):
            cells = self.step(cells)
        shape0, pos0 = self.m.normalise(start)
        shape1, pos1 = self.m.normalise(cells)
        self.assertEqual(shape0, shape1)                        # still a glider
        self.assertEqual((abs(pos1[0] - pos0[0]), abs(pos1[1] - pos0[1])), (1, 1))

    def test_population_of_empty_world_stays_empty(self):
        self.assertEqual(self.step(set()), set())

    def test_births_and_survivals_are_exactly_the_rule(self):
        """A single cell dies (0 neighbours) and three in a row births the middle pair."""
        self.assertEqual(self.step({(5, 5)}), set())
        born = self.step({(0, 0), (1, 0), (2, 0)})
        self.assertEqual(len(born), 3)

    def test_torus_wraps_instead_of_growing(self):
        """A blinker straddling the seam must oscillate across it, staying in bounds."""
        cells = {(0, 0), (9, 0), (1, 0)}
        wrapped = self.m.step(cells, self.B, self.S, wrap=(10, 10))
        self.assertEqual(wrapped, {(0, 0), (0, 1), (0, 9)})
        self.assertTrue(all(0 <= x < 10 and 0 <= y < 10 for x, y in wrapped))
        self.assertEqual(self.m.step(wrapped, self.B, self.S, wrap=(10, 10)), cells)

    def test_normalise_is_translation_invariant(self):
        a, _ = self.m.normalise({(10, 10), (11, 10), (12, 10)})
        b, _ = self.m.normalise({(0, 0), (1, 0), (2, 0)})
        self.assertEqual(a, b)

    def test_detector_finds_oscillator_and_spaceship(self):
        blinker = {(0, 0), (1, 0), (2, 0)}
        det = self.m.Detector()
        for gen in range(3):
            det.feed(gen, blinker if gen % 2 == 0 else self.step(blinker))
        self.assertIn("oscillator", det.found)
        self.assertIn("period 2", det.found)

        glider = {(0, 0), (1, 0), (2, 0), (2, 1), (1, 2)}
        det2 = self.m.Detector()
        state = glider
        for gen in range(5):
            det2.feed(gen, state)
            state = self.step(state)
        self.assertIn("spaceship", det2.found)

    def test_rule_parsing(self):
        m = self.m
        self.assertEqual(m.parse_rule("B3/S23"), ({3}, {2, 3}))
        self.assertEqual(m.parse_rule("life"), ({3}, {2, 3}))
        self.assertEqual(m.parse_rule("highlife"), ({3, 6}, {2, 3}))
        self.assertEqual(m.parse_rule("B2/S"), ({2}, set()))
        with self.assertRaises(SystemExit):
            m.parse_rule("nonsense")

    def test_from_rows_offsets(self):
        cells = self.m.from_rows("O./.O", 3, 4)
        self.assertEqual(cells, {(3, 4), (4, 5)})

    def test_rle_import(self):
        rle = "#N glider\nx = 3, y = 3, rule = B3/S23\nbo$2bo$3o!"
        cells, rule = self.m.parse_rle(rle)
        self.assertEqual(rule, "B3/S23")
        self.assertEqual(cells, {(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)})

    def test_wolfram_rule_90_is_sierpinski(self):
        """Rule 90 is left XOR right, giving the Sierpinski pattern from one seed cell."""
        rows = self.m.wolfram(90, 15, 4)
        as_bits = ["".join("1" if v else "0" for v in r) for r in rows]
        self.assertEqual(as_bits, ["000000010000000", "000000101000000",
                                   "000001000100000", "000010101010000"])

    def test_wolfram_rule_110_row_length_and_binary(self):
        rows = self.m.wolfram(110, 20, 5)
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(len(r) == 20 for r in rows))
        self.assertEqual(rows[0].count(1), 1)

    def test_langton_ant_writes_one_cell_per_step(self):
        grid, pos = self.m.langton("RL", 200)
        self.assertLessEqual(len(grid), 200)
        self.assertGreater(len(grid), 0)
        self.assertTrue(all(0 <= v < 2 for v in grid.values()))

    def test_projectors_and_png(self):
        cells = self.m.from_rows(self.m.PATTERNS["pulsar"])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.png")
            sc = 2
            xs = [x for x, _ in cells]
            ys = [y for _, y in cells]
            x0, y0 = min(xs), min(ys)
            w, h = max(xs) - x0 + 1, max(ys) - y0 + 1
            ages = {c: 1 for c in cells}
            rows = [[(self.m.age_color(1) if (x0 + x // sc, y0 + y // sc) in cells else self.m.BG)
                     for x in range(w * sc)] for y in range(h * sc)]
            self.m.save_png(path, rows)
            with open(path, "rb") as fh:
                raw = fh.read()
            self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", raw[16:24]), (w * sc, h * sc))

    def test_gif_writer_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.gif")
            frames = [[0, 1, 2, 3], [3, 2, 1, 0]]
            self.m.write_gif(path, frames, 2, 2, self.m.GIF_PAL, 5)
            with open(path, "rb") as fh:
                raw = fh.read()
            self.assertEqual(gif_structure(raw), ((2, 2), 2))
            self.assertEqual(raw[-1:], b"\x3b")

    def test_age_colour_gets_cooler_with_age(self):
        young = self.m.age_color(1)
        old = self.m.age_color(60)
        self.assertGreater(young[0], old[0])
        self.assertEqual(young, (255, 250, 210))


# ---------------------------------------------------------------- worldgen
class WorldgenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load("toy_worldgen", os.path.join("worldgen", "worldgen.py"))

    def make_world(self, seed=5, w=40, h=24, **kw):
        kw.setdefault("rivers", 3)
        kw.setdefault("towns", 4)
        return self.m.generate(seed, w, h, **kw)

    def test_perlin_is_seed_deterministic_and_bounded(self):
        a = self.m.Perlin(random.Random(1))
        b = self.m.Perlin(random.Random(1))
        c = self.m.Perlin(random.Random(2))
        vals_a = [a.noise(x * 0.7, 1.3) for x in range(20)]
        vals_b = [b.noise(x * 0.7, 1.3) for x in range(20)]
        vals_c = [c.noise(x * 0.7, 1.3) for x in range(20)]
        self.assertEqual(vals_a, vals_b)
        self.assertNotEqual(vals_a, vals_c)
        self.assertTrue(all(-2.0 <= v <= 2.0 for v in vals_a))

    def test_fbm_has_more_octaves_more_detail(self):
        p = self.m.Perlin(random.Random(3))
        coarse = [p.fbm(x * 0.2, 0.4, 1) for x in range(50)]
        fine = [p.fbm(x * 0.2, 0.4, 6) for x in range(50)]
        self.assertNotEqual(coarse, fine)

    def test_normalize_bounds(self):
        grid = self.m.normalize([[0.0, 2.0], [1.0, 4.0]])
        self.assertEqual(min(min(r) for r in grid), 0.0)
        self.assertEqual(max(max(r) for r in grid), 1.0)

    def test_height_methods_have_requested_size_and_range(self):
        for method in ("fbm", "dsquare"):
            g = self.m.height_fbm(12, 8, random.Random(4)) if method == "fbm" else self.m.height_dsquare(12, 8, random.Random(4))
            self.assertEqual(len(g), 8, method)
            self.assertTrue(all(len(r) == 12 for r in g), method)
            self.assertGreaterEqual(min(min(r) for r in g), 0.0, method)
            self.assertLessEqual(max(max(r) for r in g), 1.0, method)

    def test_island_mask_lowers_edges_relative_to_centre(self):
        flat = self.m.normalize([[0.5 + 0.001 * x for x in range(20)] for _ in range(20)])
        masked = self.m.island_mask(flat, 0.8)
        centre = masked[10][10]
        corners = (masked[0][0] + masked[0][-1] + masked[-1][0] + masked[-1][-1]) / 4
        self.assertGreater(centre, corners)

    def test_thermal_erosion_smooths_a_spike(self):
        grid = [[0.0] * 9 for _ in range(9)]
        grid[4][4] = 1.0
        before = grid[4][4]
        self.m.thermal_erosion(grid, 5)
        self.assertLess(grid[4][4], before)
        self.assertGreater(grid[4][5], 0.0)

    def test_hydraulic_erosion_conserves_rough_mass(self):
        grid = self.m.normalize([[random.Random(1).random() for _ in range(12)] for _ in range(12)])
        total = sum(sum(r) for r in grid)
        self.m.hydraulic_erosion(grid, 60, random.Random(2))
        moved = sum(sum(r) for r in grid)
        self.assertAlmostEqual(moved, total, places=6)

    def test_generated_world_is_consistent(self):
        wd = self.make_world()
        self.assertEqual((wd.w, wd.h), (40, 24))
        self.assertEqual(len(wd.biomes), 24)
        self.assertTrue(all(len(r) == 40 for r in wd.biomes))
        for row in wd.biomes:
            for b in row:
                self.assertIn(b, self.m.BIOMES)
        self.assertLessEqual(len(wd.towns), 4)
        self.assertTrue(wd.name)
        for t in wd.towns:
            self.assertNotIn(wd.biomes[t["y"]][t["x"]], ("deep ocean", "ocean", "shallows"))
            self.assertTrue(0 <= t["x"] < wd.w and 0 <= t["y"] < wd.h)
            self.assertIn(t["kind"], ("capital", "city", "town", "village"))

    def test_world_is_reproducible_from_seed(self):
        a = self.make_world(seed=9)
        b = self.make_world(seed=9)
        c = self.make_world(seed=10)
        self.assertEqual(a.biomes, b.biomes)
        self.assertEqual(a.rivers, b.rivers)
        self.assertNotEqual(a.biomes, c.biomes)

    def test_climate_values_are_unit_interval(self):
        wd = self.make_world(seed=4)
        for grid in (wd.temp, wd.moist):
            self.assertTrue(all(0.0 <= v <= 1.0 for row in grid for v in row))

    def test_sea_level_matches_requested_fraction(self):
        wd = self.make_world(seed=6, sea=0.5)
        water = sum(1 for row in wd.biomes for b in row
                    if b in ("deep ocean", "ocean", "shallows"))
        self.assertAlmostEqual(water / (wd.w * wd.h), 0.5, delta=0.06)

    def test_gazetteer_reports_the_world(self):
        wd = self.make_world(seed=8)
        text = self.m.gazetteer(wd)
        self.assertIn(wd.name.upper(), text)
        self.assertIn("Land covers", text)
        self.assertIn("SETTLEMENTS", text)

    def test_png_export(self):
        wd = self.make_world(seed=2, w=16, h=12)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "world.png")
            self.m.write_png(path, wd, scale=2)
            with open(path, "rb") as fh:
                raw = fh.read()
            self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", raw[16:24]), (32, 24))

    def test_ascii_and_colour_rendering_produce_the_right_number_of_rows(self):
        wd = self.make_world(seed=1, w=20, h=10)
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.m.print_ascii(wd)
        lines = buf.getvalue().rstrip("\n").split("\n")
        self.assertEqual(len(lines), 5)          # two cell rows per text row
        self.assertTrue(all(len(line) == 20 for line in lines))


# ---------------------------------------------------------------- beatbox
class BeatboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load("toy_beatbox", os.path.join("audio", "beatbox", "beatbox.py"))

    def args(self, **over):
        base = dict(seed=1, random=False, bpm=None, bars=None, song=False, room="studio", pattern=None)
        base.update(over)
        return argparse.Namespace(**base)

    def test_voices_and_styles_are_well_formed(self):
        m = self.m
        self.assertEqual(len(m.VOICES), 33)
        for key, voice in m.VOICES.items():
            self.assertEqual(len(voice), 7, key)
            self.assertEqual(len(voice[5]), 16, key)
            self.assertTrue(callable(voice[0]))
        for name, (bpm, beats, layers) in m.STYLES.items():
            self.assertEqual(len({len(p) for p in layers.values()}), 1, name)
            self.assertTrue(50 <= bpm <= 240, name)

    def test_prompt_sets_style_tempo_and_length(self):
        cfg = self.m.parse("fast aggressive trap 8 bars", self.args())
        self.assertEqual(cfg["style"], "trap")
        self.assertEqual(cfg["bpm"], 158)          # trap 140 + 18 for "fast"
        self.assertEqual(cfg["bars"], 8)
        self.assertTrue(cfg["busy"])

    def test_explicit_flags_win_over_the_prompt(self):
        cfg = self.m.parse("trap 8 bars", self.args(bpm=90, bars=2, room="hall"))
        self.assertEqual((cfg["bpm"], cfg["bars"], cfg["room"]), (90, 2, "hall"))

    def test_same_prompt_same_beat(self):
        a = self.m.parse("boombap swing 60%", self.args())
        b = self.m.parse("boombap swing 60%", self.args())
        self.assertEqual(a["pats"], b["pats"])
        self.assertEqual(a["seed"], b["seed"])

    def test_seed_changes_the_beat(self):
        a = self.m.parse("dubstep 4 bars", self.args(seed=1))
        b = self.m.parse("dubstep 4 bars", self.args(seed=2))
        self.assertEqual(a["seed"], 1)
        self.assertEqual(b["seed"], 2)

    def test_negation_removes_a_voice(self):
        cfg = self.m.parse("trap with hats no hats", self.args())
        self.assertNotIn("h", cfg["pats"])

    def test_everything_adds_voices(self):
        base = self.m.parse("classic", self.args())
        many = self.m.parse("everything", self.args())
        self.assertGreater(len(many["pats"]), len(base["pats"]))

    def test_pattern_override(self):
        cfg = self.m.parse("trap", self.args(pattern=["k=x.....x.....x..."]))
        self.assertEqual(cfg["pats"]["k"], "x.....x.....x...")

    def test_song_arrangement_has_intro_groove_and_drop(self):
        plan, fills = self.m.section_plan(16, True)
        self.assertEqual(len(plan), 16)
        self.assertEqual(plan[0], 0)               # intro is thinnest
        self.assertIn(3, plan)                     # a drop exists
        self.assertTrue(fills)

    def test_arrangement_only_uses_known_voices(self):
        cfg = self.m.parse("house 2 bars", self.args())
        ev = self.m.arrange(cfg, random.Random(cfg["seed"]))
        self.assertTrue(ev)
        for pos, voice, vel, pitch in ev:
            self.assertIn(voice, self.m.VOICES)
            self.assertGreaterEqual(pos, 0)
            self.assertGreater(vel, 0)
        self.assertEqual(ev, self.m.arrange(cfg, random.Random(cfg["seed"])))

    def test_lowpass_rejects_high_frequencies(self):
        m = self.m
        old = m.SR
        try:
            m.SR = 22050
            high = [math.sin(2 * math.pi * 8000 * i / m.SR) for i in range(2000)]
            low = [math.sin(2 * math.pi * 100 * i / m.SR) for i in range(2000)]
            rms = lambda x: math.sqrt(sum(v * v for v in x) / len(x))
            self.assertLess(rms(m.lp(high, 500)), rms(m.lp(low, 500)) * 0.2)
        finally:
            m.SR = old

    def test_fade_ends_at_zero(self):
        x = self.m.fade([1.0] * 1000)
        self.assertAlmostEqual(x[-1], 0.0)
        self.assertGreater(x[0], 0.5)

    def test_voice_rendering_is_deterministic_per_variant(self):
        m = self.m
        old = m.SR
        try:
            m.SR = 8000
            for voice in ("k", "s", "h", "lr", "wub", "tb"):
                first = m.render_voice(voice, 0, 1.0)
                again = m.render_voice(voice, 0, 1.0)
                other = m.render_voice(voice, 1, 1.0)
                self.assertTrue(first, voice)
                self.assertEqual(first, again, voice)
                self.assertNotEqual(first, other, voice)
                self.assertLessEqual(max(abs(v) for v in first), 1.0, voice)
        finally:
            m.SR = old

    def test_render_produces_bounded_stereo_audio(self):
        m = self.m
        old = m.SR
        try:
            m.SR = 8000
            cfg = m.parse("boombap 1 bar", self.args())
            cfg["room"] = "dry"
            ev = m.arrange(cfg, random.Random(cfg["seed"]))
            L, R = m.render(cfg, ev, random.Random(2), humanize=0.0, dry=True)
            self.assertEqual(len(L), len(R))
            self.assertGreater(len(L), 0)
            self.assertLessEqual(max(abs(v) for v in L), 1.0)
            self.assertLessEqual(max(abs(v) for v in R), 1.0)
            self.assertGreater(max(abs(v) for v in L), 0.01)
        finally:
            m.SR = old

    def test_wav_export_has_correct_container(self):
        m = self.m
        old = m.SR
        try:
            m.SR = 8000
            L = [math.sin(i / 10.0) * 0.5 for i in range(800)]
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "beat.wav")
                m.write_wav(path, L, L)
                with wave.open(path, "rb") as w:
                    self.assertEqual(w.getnchannels(), 2)
                    self.assertEqual(w.getsampwidth(), 2)
                    self.assertEqual(w.getframerate(), 8000)
                    self.assertEqual(w.getnframes(), len(L))
        finally:
            m.SR = old

    def test_midi_export_has_header_track_and_tempo(self):
        m = self.m
        old = m.SR
        try:
            m.SR = 8000
            cfg = m.parse("trap 1 bar", self.args())
            ev = m.arrange(cfg, random.Random(cfg["seed"]))
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "beat.mid")
                m.write_midi(path, ev, cfg)
                with open(path, "rb") as fh:
                    raw = fh.read()
                self.assertEqual(raw[:4], b"MThd")
                self.assertEqual(struct.unpack(">I", raw[4:8])[0], 6)
                self.assertEqual(struct.unpack(">H", raw[8:10])[0], 0)   # format 0
                self.assertEqual(struct.unpack(">H", raw[10:12])[0], 1)   # one track
                self.assertEqual(struct.unpack(">H", raw[12:14])[0], 480)  # ticks per quarter
                self.assertIn(b"MTrk", raw)
                self.assertIn(b"\xff\x51\x03", raw)                       # tempo meta-event
                self.assertTrue(raw.endswith(b"\x00\xff\x2f\x00"))
        finally:
            m.SR = old


if __name__ == "__main__":
    unittest.main(verbosity=2)
