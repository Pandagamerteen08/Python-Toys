#!/usr/bin/env python3
"""cipher.py - classical ciphers, codes, code-breaking and an Enigma M3 simulator.

No dependencies. Python 3.8+.

  python cipher.py caesar "Hello" --key 3
  python cipher.py caesar "Khoor" --key 3 -d
  python cipher.py crack "Wkh txlfn eurzq ira mxpsv ryhu wkh odcb grj"
  python cipher.py vigenere "ATTACKATDAWN" --key LEMON
  python cipher.py vigenere "<ciphertext>" --crack
  python cipher.py playfair "hide the gold in the tree stump" --key "playfair example"
  python cipher.py railfence "WEAREDISCOVEREDFLEEATONCE" --key 3
  python cipher.py enigma "HELLOWORLD" --rotors I,II,III --start AAA --plug AB,CD
  python cipher.py morse "SOS" ;  python cipher.py base64 "hi"
  python cipher.py --list ;  python cipher.py --selftest
"""
import os
import argparse
import base64
import binascii
import collections
import math
import string
import sys

A = string.ascii_uppercase

ENGLISH_FREQ = {
    'E': 12.70, 'T': 9.06, 'A': 8.17, 'O': 7.51, 'I': 6.97, 'N': 6.75, 'S': 6.33,
    'H': 6.09, 'R': 5.99, 'D': 4.25, 'L': 4.03, 'C': 2.78, 'U': 2.76, 'M': 2.41,
    'W': 2.36, 'F': 2.23, 'G': 2.02, 'Y': 1.97, 'P': 1.93, 'B': 1.49, 'V': 0.98,
    'K': 0.77, 'J': 0.15, 'X': 0.15, 'Q': 0.10, 'Z': 0.07}

COMMON_WORDS = ("THE", "AND", "THAT", "HAVE", "FOR", "NOT", "WITH", "YOU", "THIS",
                "BUT", "HIS", "FROM", "THEY", "SAY", "HER", "SHE", "WILL", "ONE",
                "ALL", "WOULD", "THERE", "THEIR", "WHAT", "OUT", "ABOUT", "WHO",
                "WHICH", "WHEN", "MAKE", "CAN", "LIKE", "TIME", "JUST", "KNOW",
                "TAKE", "INTO", "YEAR", "YOUR", "SOME", "COULD", "THEM", "SEE",
                "OTHER", "THAN", "THEN", "NOW", "LOOK", "ONLY", "COME", "OVER",
                "QUICK", "BROWN", "FOX", "JUMPS", "LAZY", "DOG", "ATTACK", "DAWN")


# ---------------------------------------------------------------- helpers
def letters(text):
    return "".join(c for c in text.upper() if c in A)


def keep_case_shift(text, fn):
    """Apply fn(index_in_alphabet, position_among_letters) to letters, keep others."""
    out, n = [], 0
    for c in text:
        if c.isalpha() and c.upper() in A:
            base = 'A' if c.isupper() else 'a'
            out.append(chr(ord(base) + fn(ord(c.upper()) - 65, n) % 26))
            n += 1
        else:
            out.append(c)
    return "".join(out)


def score_english(text):
    """Higher is more English-like (chi-squared against letter frequencies, negated)
    plus a bonus for common words."""
    t = letters(text)
    if not t:
        return -1e9
    cnt = collections.Counter(t)
    n = len(t)
    chi = 0.0
    for ch, f in ENGLISH_FREQ.items():
        e = f / 100 * n
        chi += (cnt.get(ch, 0) - e) ** 2 / e
    bonus = sum(t.count(w) * len(w) for w in COMMON_WORDS) / n * 40
    return -chi / n * 10 + bonus


def index_of_coincidence(text):
    t = letters(text)
    n = len(t)
    if n < 2:
        return 0.0
    cnt = collections.Counter(t)
    return sum(v * (v - 1) for v in cnt.values()) / (n * (n - 1))


def mod_inv(a, m):
    a %= m
    for x in range(1, m):
        if a * x % m == 1:
            return x
    raise ValueError("%d has no inverse mod %d" % (a, m))


# ---------------------------------------------------------------- ciphers
# Each cipher: name -> (encode(text, key), decode(text, key), key help)
def caesar(text, key, decode=False):
    k = int(key) % 26
    if decode:
        k = -k
    return keep_case_shift(text, lambda i, n: i + k)


def rot13(text, key=None, decode=False):
    return caesar(text, 13)


def atbash(text, key=None, decode=False):
    return keep_case_shift(text, lambda i, n: 25 - i)


def affine(text, key, decode=False):
    a, b = [int(x) for x in str(key).split(",")]
    if math.gcd(a, 26) != 1:
        raise ValueError("affine: a must be coprime with 26 (1,3,5,7,9,11,15,17,19,21,23,25)")
    if decode:
        ai = mod_inv(a, 26)
        return keep_case_shift(text, lambda i, n: ai * (i - b))
    return keep_case_shift(text, lambda i, n: a * i + b)


def vigenere(text, key, decode=False):
    k = [ord(c) - 65 for c in letters(key)]
    if not k:
        raise ValueError("vigenere: key must contain letters")
    s = -1 if decode else 1
    return keep_case_shift(text, lambda i, n: i + s * k[n % len(k)])


def beaufort(text, key, decode=False):
    k = [ord(c) - 65 for c in letters(key)]
    if not k:
        raise ValueError("beaufort: key must contain letters")
    return keep_case_shift(text, lambda i, n: k[n % len(k)] - i)


def autokey(text, key, decode=False):
    k = [ord(c) - 65 for c in letters(key)]
    if not k:
        raise ValueError("autokey: key must contain letters")
    stream = list(k)
    out, n = [], 0
    for c in text:
        if c.upper() in A and c.isalpha():
            base = 'A' if c.isupper() else 'a'
            i = ord(c.upper()) - 65
            if decode:
                p = (i - stream[n]) % 26
                stream.append(p)
                out.append(chr(ord(base) + p))
            else:
                stream.append(i)
                out.append(chr(ord(base) + (i + stream[n]) % 26))
            n += 1
        else:
            out.append(c)
    return "".join(out)


def keyed_alphabet(key):
    seen = []
    for c in letters(key) + A:
        if c not in seen:
            seen.append(c)
    return "".join(seen)


def substitution(text, key, decode=False):
    """Key is a keyword (keyed alphabet) or a full 26-letter permutation."""
    k = letters(key)
    alpha = k if len(set(k)) == 26 and len(k) == 26 else keyed_alphabet(k)
    src, dst = (alpha, A) if decode else (A, alpha)
    table = {s: d for s, d in zip(src, dst)}
    return "".join((table[c.upper()] if c.isupper() else table[c.upper()].lower())
                   if c.upper() in table and c.isalpha() else c for c in text)


def playfair_square(key):
    seq = keyed_alphabet(letters(key).replace("J", "I"))
    seq = "".join(c for c in seq if c != "J")
    return seq


def playfair(text, key, decode=False):
    sq = playfair_square(key)
    pos = {c: divmod(i, 5) for i, c in enumerate(sq)}
    t = letters(text).replace("J", "I")
    if decode:
        pairs = [t[i:i + 2] for i in range(0, len(t) - len(t) % 2, 2)]
    else:
        pairs, i = [], 0
        while i < len(t):
            a = t[i]
            b = t[i + 1] if i + 1 < len(t) else "X"
            if a == b:
                b = "X" if a != "X" else "Q"
                i += 1
            else:
                i += 2
            pairs.append(a + b)
    d = -1 if decode else 1
    out = []
    for a, b in pairs:
        (r1, c1), (r2, c2) = pos[a], pos[b]
        if r1 == r2:
            out.append(sq[r1 * 5 + (c1 + d) % 5] + sq[r2 * 5 + (c2 + d) % 5])
        elif c1 == c2:
            out.append(sq[((r1 + d) % 5) * 5 + c1] + sq[((r2 + d) % 5) * 5 + c2])
        else:
            out.append(sq[r1 * 5 + c2] + sq[r2 * 5 + c1])
    return "".join(out)


def railfence(text, key, decode=False):
    n = int(key)
    t = text
    if n < 2 or n >= len(t):
        return t
    cycle = list(range(n)) + list(range(n - 2, 0, -1))
    rails = [cycle[i % len(cycle)] for i in range(len(t))]
    order = sorted(range(len(t)), key=lambda i: (rails[i], i))
    if not decode:
        return "".join(t[i] for i in order)
    out = [""] * len(t)
    for ch, i in zip(t, order):
        out[i] = ch
    return "".join(out)


def columnar(text, key, decode=False):
    k = letters(key)
    if not k:
        raise ValueError("columnar: key must contain letters")
    order = sorted(range(len(k)), key=lambda i: (k[i], i))
    t = text
    cols = len(k)
    rows = -(-len(t) // cols)
    if not decode:
        t = t + "X" * (rows * cols - len(t))
        return "".join(t[c::cols] for c in order)
    out = [[""] * cols for _ in range(rows)]
    pos = 0
    for c in order:
        for r in range(rows):
            out[r][c] = t[pos]
            pos += 1
    return "".join("".join(r) for r in out)


def scytale(text, key, decode=False):
    n = int(key)
    t = text
    rows = -(-len(t) // n)
    if not decode:
        t = t + " " * (rows * n - len(t))
        return "".join(t[i::n] for i in range(n)).rstrip()
    cols = -(-len(t) // n)
    t = t + " " * (n * cols - len(t))
    return "".join(t[i::cols] for i in range(cols)).rstrip()


def hill(text, key, decode=False):
    """2x2 Hill cipher; key like 3,3,2,5."""
    a, b, c, d = [int(x) for x in str(key).split(",")]
    det = (a * d - b * c) % 26
    if math.gcd(det, 26) != 1:
        raise ValueError("hill: determinant %d is not invertible mod 26" % det)
    if decode:
        di = mod_inv(det, 26)
        a, b, c, d = (d * di) % 26, (-b * di) % 26, (-c * di) % 26, (a * di) % 26
    t = letters(text)
    if len(t) % 2:
        t += "X"
    out = []
    for i in range(0, len(t), 2):
        x, y = ord(t[i]) - 65, ord(t[i + 1]) - 65
        out.append(A[(a * x + b * y) % 26] + A[(c * x + d * y) % 26])
    return "".join(out)


def bacon(text, key=None, decode=False):
    if decode:
        bits = "".join("1" if c in "BbIi" and False else c for c in text)
        bits = "".join("0" if c in "Aa0" else "1" for c in text if c in "ABab01")
        return "".join(A[int(bits[i:i + 5], 2)] if int(bits[i:i + 5], 2) < 26 else "?"
                       for i in range(0, len(bits) - 4, 5))
    return " ".join("".join("B" if b == "1" else "A" for b in format(ord(c) - 65, "05b"))
                    for c in letters(text))


def polybius(text, key=None, decode=False):
    sq = playfair_square(key or "")
    if decode:
        d = [c for c in text if c in "12345"]
        return "".join(sq[(int(d[i]) - 1) * 5 + int(d[i + 1]) - 1] for i in range(0, len(d) - 1, 2))
    return " ".join("%d%d" % (sq.index(c) // 5 + 1, sq.index(c) % 5 + 1)
                    for c in letters(text).replace("J", "I"))


def xor_cipher(text, key, decode=False):
    kb = str(key).encode()
    if decode:
        raw = binascii.unhexlify("".join(text.split()))
        return bytes(b ^ kb[i % len(kb)] for i, b in enumerate(raw)).decode("utf-8", "replace")
    raw = text.encode("utf-8")
    return bytes(b ^ kb[i % len(kb)] for i, b in enumerate(raw)).hex()


# ---------------------------------------------------------------- morse & encodings
MORSE = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.', 'G': '--.',
    'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.',
    'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-', 'U': '..-',
    'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--', 'Z': '--..',
    '0': '-----', '1': '.----', '2': '..---', '3': '...--', '4': '....-', '5': '.....',
    '6': '-....', '7': '--...', '8': '---..', '9': '----.',
    '.': '.-.-.-', ',': '--..--', '?': '..--..', "'": '.----.', '!': '-.-.--',
    '/': '-..-.', '(': '-.--.', ')': '-.--.-', '&': '.-...', ':': '---...',
    ';': '-.-.-.', '=': '-...-', '+': '.-.-.', '-': '-....-', '_': '..--.-',
    '"': '.-..-.', '$': '...-..-', '@': '.--.-.'}
MORSE_REV = {v: k for k, v in MORSE.items()}


def morse(text, key=None, decode=False):
    if decode:
        words = text.strip().replace("|", "/").split("/")
        return " ".join("".join(MORSE_REV.get(s, "?") for s in w.split()) for w in words)
    return " / ".join(" ".join(MORSE[c] for c in w if c in MORSE) for w in text.upper().split())


def b64(text, key=None, decode=False):
    if decode:
        return base64.b64decode(text.encode()).decode("utf-8", "replace")
    return base64.b64encode(text.encode()).decode()


def b32(text, key=None, decode=False):
    if decode:
        return base64.b32decode(text.encode()).decode("utf-8", "replace")
    return base64.b32encode(text.encode()).decode()


def b85(text, key=None, decode=False):
    if decode:
        return base64.b85decode(text.encode()).decode("utf-8", "replace")
    return base64.b85encode(text.encode()).decode()


def hexenc(text, key=None, decode=False):
    if decode:
        return binascii.unhexlify("".join(text.split())).decode("utf-8", "replace")
    return text.encode().hex()


def binenc(text, key=None, decode=False):
    if decode:
        b = text.split()
        return bytes(int(x, 2) for x in b).decode("utf-8", "replace")
    return " ".join(format(x, "08b") for x in text.encode())


def urlenc(text, key=None, decode=False):
    from urllib.parse import quote, unquote
    return unquote(text) if decode else quote(text, safe="")


def leet(text, key=None, decode=False):
    m = {'a': '4', 'e': '3', 'i': '1', 'o': '0', 's': '5', 't': '7', 'b': '8', 'g': '9'}
    if decode:
        r = {v: k for k, v in m.items()}
        return "".join(r.get(c, c) for c in text)
    return "".join(m.get(c.lower(), c) for c in text)


def reverse(text, key=None, decode=False):
    return text[::-1]


def pigpen_ascii(text, key=None, decode=False):
    return " ".join(c for c in text)  # placeholder-free: spacing out letters


NATO = dict(zip(A, "Alfa Bravo Charlie Delta Echo Foxtrot Golf Hotel India Juliett Kilo Lima "
                   "Mike November Oscar Papa Quebec Romeo Sierra Tango Uniform Victor Whiskey "
                   "Xray Yankee Zulu".split()))
NATO_REV = {v.upper(): k for k, v in NATO.items()}


def nato(text, key=None, decode=False):
    if decode:
        return "".join(NATO_REV.get(w.upper(), "?") for w in text.split())
    return " ".join(NATO[c] for c in letters(text))


def a1z26(text, key=None, decode=False):
    if decode:
        return "".join(A[int(x) - 1] if x.isdigit() and 1 <= int(x) <= 26 else "?" for x in text.split())
    return " ".join(str(ord(c) - 64) for c in letters(text))


def tapcode(text, key=None, decode=False):
    sq = playfair_square("").replace("I", "I")
    sq = "ABCDEFGHIKLMNOPQRSTUVWXYZ"  # classic tap code: C and K share a cell
    if decode:
        out = []
        for g in text.split():
            if len(g) == 2 and g.isdigit():
                r, c = int(g[0]), int(g[1])
                out.append(sq[(r - 1) * 5 + c - 1] if 1 <= r <= 5 and 1 <= c <= 5 else "?")
        return "".join(out)
    t = letters(text).replace("J", "I")
    return " ".join("%d%d" % (sq.index(c) // 5 + 1, sq.index(c) % 5 + 1) for c in t)


# ---------------------------------------------------------------- Enigma M3
ROTORS = {  # wiring, notch letters
    "I": ("EKMFLGDQVZNTOWYHXUSPAIBRCJ", "Q"),
    "II": ("AJDKSIRUXBLHWTMCQGZNPYFVOE", "E"),
    "III": ("BDFHJLCPRTXVZNYEIWGAKMUSQO", "V"),
    "IV": ("ESOVPZJAYQUIRHXLNFTGKDCMWB", "J"),
    "V": ("VZBRGITYUPSDNHLXAWMJQOFECK", "Z"),
    "VI": ("JPGVOUMFYQBENHZRDKASXLICTW", "ZM"),
    "VII": ("NZJHGRCXMYSWBOUFAIVLPEKQDT", "ZM"),
    "VIII": ("FKQHTLXOCBJSPDZRAMEWNIUYGV", "ZM"),
}
REFLECTORS = {
    "B": "YRUHQSLDPXNGOKMIEBFZCWVJAT",
    "C": "FVPJIAOYEDRZXWGCTKUQSBNMHL",
    "A": "EJMZALYXVBWFCRQUONTSPIKHGD",
}


class Enigma:
    def __init__(self, rotors=("I", "II", "III"), reflector="B", rings="AAA",
                 start="AAA", plug=""):
        if len(rotors) != 3:
            raise ValueError("enigma: need exactly 3 rotors")
        for r in rotors:
            if r not in ROTORS:
                raise ValueError("unknown rotor %r (use %s)" % (r, ",".join(ROTORS)))
        if reflector not in REFLECTORS:
            raise ValueError("unknown reflector %r (use A, B or C)" % reflector)
        if len(set(rotors)) != 3:
            raise ValueError("enigma: rotors must be different")
        self.names = rotors
        self.wire = [[ord(c) - 65 for c in ROTORS[r][0]] for r in rotors]
        self.inv = []
        for w in self.wire:
            i = [0] * 26
            for a, b in enumerate(w):
                i[b] = a
            self.inv.append(i)
        self.notch = [[ord(c) - 65 for c in ROTORS[r][1]] for r in rotors]
        self.refl = [ord(c) - 65 for c in REFLECTORS[reflector]]
        self.rings = [self._pos(c) for c in self._three(rings)]
        self.pos = [self._pos(c) for c in self._three(start)]
        self.plug = list(range(26))
        pairs = [p for p in plug.replace(",", " ").upper().split() if p]
        used = set()
        for p in pairs:
            if len(p) != 2 or p[0] not in A or p[1] not in A or p[0] == p[1]:
                raise ValueError("bad plugboard pair %r" % p)
            if p[0] in used or p[1] in used:
                raise ValueError("letter reused in plugboard: %r" % p)
            used.update(p)
            a, b = ord(p[0]) - 65, ord(p[1]) - 65
            self.plug[a], self.plug[b] = b, a
        if len(pairs) > 13:
            raise ValueError("too many plugboard pairs")

    @staticmethod
    def _three(s):
        s = s.upper()
        if len(s) != 3 or any(c not in A for c in s):
            raise ValueError("expected 3 letters, got %r" % s)
        return s

    @staticmethod
    def _pos(c):
        return ord(c) - 65

    def step(self):
        l, m, r = self.pos
        m_at_notch = m in self.notch[1]
        r_at_notch = r in self.notch[2]
        if m_at_notch:                  # double step
            self.pos[0] = (l + 1) % 26
            self.pos[1] = (m + 1) % 26
        elif r_at_notch:
            self.pos[1] = (m + 1) % 26
        self.pos[2] = (r + 1) % 26

    def _pass(self, c, i, forward):
        shift = self.pos[i] - self.rings[i]
        c = (c + shift) % 26
        c = self.wire[i][c] if forward else self.inv[i][c]
        return (c - shift) % 26

    def press(self, ch):
        self.step()
        c = self.plug[ord(ch) - 65]
        for i in (2, 1, 0):
            c = self._pass(c, i, True)
        c = self.refl[c]
        for i in (0, 1, 2):
            c = self._pass(c, i, False)
        return chr(self.plug[c] + 65)

    def run(self, text, keep=False):
        out = []
        for ch in text.upper():
            if ch in A:
                out.append(self.press(ch))
            elif keep:
                out.append(ch)
        return "".join(out)

    def position(self):
        return "".join(chr(p + 65) for p in self.pos)


def enigma_cmd(text, args):
    rotors = tuple(x.strip().upper() for x in args.rotors.split(","))
    e = Enigma(rotors, args.reflector.upper(), args.rings, args.start, args.plug)
    out = e.run(text, keep=args.keep)
    if not args.keep:
        out = " ".join(out[i:i + 5] for i in range(0, len(out), 5))
    return out


# ---------------------------------------------------------------- cracking
def crack_caesar(text, top=3):
    res = []
    for k in range(26):
        p = caesar(text, k, decode=True)
        res.append((score_english(p), k, p))
    res.sort(reverse=True)
    return res[:top]


def friedman_key_length(text, maxlen=16):
    t = letters(text)
    scores = []
    for L in range(1, min(maxlen, len(t) // 2) + 1):
        avg = 0.0
        for i in range(L):
            avg += index_of_coincidence(t[i::L])
        scores.append((avg / L, L))
    best = max(s for s, _ in scores)
    # shortest length whose IoC is close to the best (avoids picking multiples)
    for s, L in scores:
        if s >= best * 0.92 and s > 0.055:
            return L
    return max(scores)[1]


def _best_shift(col):
    n = len(col)
    cnt = collections.Counter(col)
    best, bk = None, 0
    for k in range(26):
        chi = 0.0
        for ch in A:
            e = ENGLISH_FREQ[ch] / 100 * n
            o = cnt.get(A[(ord(ch) - 65 + k) % 26], 0)
            chi += (o - e) ** 2 / e
        if best is None or chi < best:
            best, bk = chi, k
    return bk


def crack_vigenere(text, maxlen=16):
    """Try every key length, solve each column by chi-squared, keep the most
    English-looking result (preferring shorter keys when scores are close)."""
    t = letters(text)
    if len(t) < 20:
        raise ValueError("vigenere crack needs at least ~20 letters of ciphertext")
    cands = []
    for L in range(1, min(maxlen, len(t) // 3) + 1):
        key = "".join(A[_best_shift(t[i::L])] for i in range(L))
        plain = vigenere(t, key, decode=True)
        cands.append((score_english(plain) - 2.0 * L, key))
    key = max(cands)[1]
    # polish: coordinate ascent on the whole-text English score
    for _ in range(3):
        for i in range(len(key)):
            best = max(range(26), key=lambda k: score_english(
                vigenere(t, key[:i] + A[k] + key[i + 1:], decode=True)))
            key = key[:i] + A[best] + key[i + 1:]
    # collapse a repeated key (e.g. SECRETSECRET -> SECRET)
    for d in range(1, len(key)):
        if len(key) % d == 0 and key[:d] * (len(key) // d) == key:
            key = key[:d]
            break
    return key, vigenere(text, key, decode=True)


BIGRAMS = ("TH HE IN ER AN RE ON AT EN ND TI ES OR TE OF ED IS IT AL AR ST TO NT NG SE HA AS OU "
           "IO LE VE CO ME DE HI RI RO IC NE EA RA CE LI CH LL BE MA SI OM UR").split()
TRIGRAMS = ("THE AND ING ENT ION HER FOR THA NTH INT ERE TIO OUR WAS ETH VER ALL HIS "
            "EST ITH OFT STH ATI NOT ONS RES ERS").split()


def _sub_score(p):
    s = 0.0
    for g in BIGRAMS:
        s += p.count(g) * 3.0
    for g in TRIGRAMS:
        s += p.count(g) * 7.0
    for w in ("THE", "AND", "WAS", "OF", "TO", "IT"):
        s += p.count(w) * 2.0
    for w in COMMON_WORDS:
        if len(w) >= 4:
            s += p.count(w) * len(w) * 1.5
    return s


def crack_substitution(text, iters=10000, restarts=12, seed=1):
    """Random-restart hill climbing for a monoalphabetic substitution.
    Works best with 150+ letters of English."""
    import random
    rnd = random.Random(seed)
    t = letters(text)
    if len(t) < 60:
        raise ValueError("substitution crack needs ~60+ letters")
    ranked = [c for c, _ in collections.Counter(t).most_common()]
    ranked += [c for c in A if c not in ranked]
    eng = [c for c, _ in sorted(ENGLISH_FREQ.items(), key=lambda kv: -kv[1])]

    def apply(k):
        table = {c: k[i] for i, c in enumerate(A)}
        return "".join(table[c] for c in t)

    gbest, gkey = -1e9, None
    for r in range(restarts):
        key = [""] * 26
        for c, e in zip(ranked, eng):
            key[ord(c) - 65] = e
        if r:  # perturb the frequency-based start
            for _ in range(r * 3):
                i, j = rnd.randrange(26), rnd.randrange(26)
                key[i], key[j] = key[j], key[i]
        cur = _sub_score(apply(key))
        for _ in range(iters):
            i, j = rnd.randrange(26), rnd.randrange(26)
            if i == j:
                continue
            key[i], key[j] = key[j], key[i]
            s = _sub_score(apply(key))
            temp = 3.0 * (1 - _ / iters) + 0.01
            if s >= cur or rnd.random() < math.exp((s - cur) / temp):
                cur = s
                if cur > gbest:
                    gbest, gkey = cur, key[:]
            else:
                key[i], key[j] = key[j], key[i]
    table = {c: gkey[i] for i, c in enumerate(A)}
    plain = "".join(table[c] if c in table else c for c in text.upper())
    inv = "".join(A[gkey.index(c)] for c in A)   # cipher alphabet that was used to encrypt
    return plain, inv


def freq_table(text):
    t = letters(text)
    n = len(t) or 1
    cnt = collections.Counter(t)
    lines = ["  letters: %d   IoC: %.4f  (English ~0.066, random ~0.038)" % (len(t), index_of_coincidence(t))]
    top = max(cnt.values()) if cnt else 1
    for ch in A:
        v = cnt.get(ch, 0)
        lines.append("  %s %5.1f%% %s" % (ch, v / n * 100, "#" * int(40 * v / top)))
    return "\n".join(lines)


# ---------------------------------------------------------------- registry
CIPHERS = collections.OrderedDict([
    ("caesar", (caesar, "shift", "int shift, e.g. 3")),
    ("rot13", (rot13, "", "no key")),
    ("atbash", (atbash, "", "no key")),
    ("affine", (affine, "a,b", "a coprime with 26, e.g. 5,8")),
    ("vigenere", (vigenere, "word", "keyword")),
    ("beaufort", (beaufort, "word", "keyword (self-reciprocal)")),
    ("autokey", (autokey, "word", "primer keyword")),
    ("substitution", (substitution, "word|26 letters", "keyword or a full alphabet")),
    ("playfair", (playfair, "word", "keyword (J=I)")),
    ("railfence", (railfence, "rails", "int rails >= 2")),
    ("columnar", (columnar, "word", "keyword")),
    ("scytale", (scytale, "n", "int rod circumference")),
    ("hill", (hill, "a,b,c,d", "2x2 matrix, e.g. 3,3,2,5")),
    ("bacon", (bacon, "", "5-bit A/B code")),
    ("polybius", (polybius, "word?", "optional keyword")),
    ("tapcode", (tapcode, "", "prisoner tap code")),
    ("xor", (xor_cipher, "text", "repeating-key XOR (hex output)")),
    ("morse", (morse, "", "Morse code")),
    ("nato", (nato, "", "NATO phonetic alphabet")),
    ("a1z26", (a1z26, "", "A=1 ... Z=26")),
    ("base64", (b64, "", "Base64")),
    ("base32", (b32, "", "Base32")),
    ("base85", (b85, "", "Base85")),
    ("hex", (hexenc, "", "hexadecimal")),
    ("binary", (binenc, "", "8-bit binary")),
    ("url", (urlenc, "", "percent-encoding")),
    ("leet", (leet, "", "1337 speak")),
    ("reverse", (reverse, "", "reverse the text")),
])


def selftest():
    cases = [
        ("caesar", caesar("HELLO", 3), "KHOOR"),
        ("vigenere", vigenere("ATTACKATDAWN", "LEMON"), "LXFOPVEFRNHR"),
        ("railfence", railfence("WEAREDISCOVEREDFLEEATONCE", 3), "WECRLTEERDSOEEFEAOCAIVDEN"),
        ("playfair", playfair("hide the gold in the tree stump", "playfair example"), "BMODZBXDNABEKUDMUIXMMOUVIF"),
        ("enigma", Enigma().run("AAAAA"), "BDZGO"),
        ("morse", morse("SOS"), "... --- ..."),
        ("affine", affine("AFFINE", "5,8"), "IHHWVC"),
        ("hill", hill("HELP", "3,3,2,5"), "HIAT"),
    ]
    bad = 0
    for name, got, want in cases:
        ok = got == want
        bad += not ok
        print("  %-10s %s  %s" % (name, "ok  " if ok else "FAIL", got if ok else "%s (want %s)" % (got, want)))
    # round trips
    msg = "Attack at Dawn! 123"
    for name in ("caesar", "atbash", "affine", "vigenere", "beaufort", "autokey", "substitution"):
        fn, _, _ = CIPHERS[name]
        key = {"caesar": 7, "affine": "5,8", "vigenere": "LEMON", "beaufort": "KEY",
               "autokey": "QUEEN", "substitution": "ZEBRAS"}.get(name)
        if fn(fn(msg, key), key, decode=True) != msg and name not in ("atbash",):
            print("  roundtrip FAIL", name)
            bad += 1
    e1, e2 = Enigma(plug="AB CD"), Enigma(plug="AB CD")
    if e2.run(e1.run("ENIGMAISRECIPROCAL")) != "ENIGMAISRECIPROCAL":
        print("  enigma reciprocal FAIL")
        bad += 1
    print("selftest:", "all good" if not bad else "%d problem(s)" % bad)
    return bad


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Classical ciphers, encodings, code-breaking and Enigma M3.")
    ap.add_argument("cmd", nargs="?", help="cipher name, or crack / freq / enigma")
    ap.add_argument("text", nargs="*", help="text (or - for stdin)")
    ap.add_argument("-k", "--key", default=None)
    ap.add_argument("-d", "--decode", action="store_true")
    ap.add_argument("--crack", action="store_true", help="vigenere/substitution: break it")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rotors", default="I,II,III")
    ap.add_argument("--reflector", default="B")
    ap.add_argument("--rings", default="AAA")
    ap.add_argument("--start", default="AAA")
    ap.add_argument("--plug", default="")
    ap.add_argument("--keep", action="store_true", help="enigma: keep spaces/punctuation")
    a = ap.parse_args(argv)

    if a.selftest:
        return 1 if selftest() else 0
    if a.list or not a.cmd:
        print("ciphers and encodings:")
        for n, (_, k, h) in CIPHERS.items():
            print("  %-13s key: %-16s %s" % (n, k or "-", h))
        print("  %-13s key: %-16s %s" % ("enigma", "--rotors etc.", "Enigma M3, rotors I-VIII, reflectors A/B/C, plugboard"))
        print("tools:\n  crack         brute-force Caesar and rank by English-ness\n"
              "  freq          letter frequency + index of coincidence\n"
              "  vigenere --crack, substitution --crack")
        return 0

    text = " ".join(a.text)
    if text == "-" or (not text and not sys.stdin.isatty()):
        text = sys.stdin.read().rstrip("\n")
    if not text:
        ap.error("no text given")
    try:
        if a.cmd == "crack":
            for sc, k, p in crack_caesar(text):
                print("  shift %2d  score %6.1f  %s" % (k, sc, p))
        elif a.cmd == "freq":
            print(freq_table(text))
        elif a.cmd == "enigma":
            print(enigma_cmd(text, a))
        elif a.cmd in CIPHERS:
            fn, _, _ = CIPHERS[a.cmd]
            if a.crack and a.cmd == "vigenere":
                key, plain = crack_vigenere(text)
                print("key length %d, key %s\n%s" % (len(key), key, plain))
            elif a.crack and a.cmd == "substitution":
                plain, key = crack_substitution(text)
                print("key %s\n%s" % (key, plain))
            else:
                if a.key is None and CIPHERS[a.cmd][1] not in ("", "word?"):
                    ap.error("%s needs --key (%s)" % (a.cmd, CIPHERS[a.cmd][2]))
                print(fn(text, a.key, decode=a.decode))
        else:
            import difflib
            m = difflib.get_close_matches(a.cmd, list(CIPHERS) + ["crack", "freq", "enigma"], 1)
            ap.error("unknown cipher %r%s" % (a.cmd, " - did you mean %s?" % m[0] if m else ""))
    except (ValueError, binascii.Error, KeyError) as e:
        print("error:", e, file=sys.stderr)
        return 2
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
