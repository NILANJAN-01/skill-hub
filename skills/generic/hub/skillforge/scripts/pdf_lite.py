"""pdf_lite.py - read the text of a PDF with its layout, using only the Python standard library.

    doc = PdfDocument("book.pdf")         # raises PdfError if the file cannot be read
    doc.title, doc.toc, len(doc.pages)    # toc: [(level, title, page_number)]
    page = doc.pages[0]
    page.width, page.height
    page.text_dict(sort=True)             # {"blocks": [{"bbox", "lines": [{"bbox", "spans": [...]}]}]}

Each span is {"text", "font", "size", "flags", "bbox", "origin", "ascender", "descender"}. Coordinates
have the origin at the top left of the page with y going down, and flags use bit 1 = italic,
4 = serif, 8 = monospaced, 16 = bold. The shape follows PyMuPDF's page.get_text("dict"), and lines
and blocks are grouped the same way: characters on one baseline form a line, a gap of more than
0.8 em along the baseline starts a new line, and a move of more than 1.5 em off it starts a new block.

Supported: classic and compressed cross-reference tables (with repair when they are broken),
object streams, Flate/LZW/ASCII85/ASCIIHex/RunLength filters with PNG and TIFF predictors,
RC4 and AES (128 and 256 bit) encryption with an empty user password, Type1/TrueType/Type3/Type0
(CID) fonts, ToUnicode maps, built-in, standard and Differences encodings, TrueType cmap tables
when a CID font has no ToUnicode map, form XObjects, outlines and document info.

Not supported: scanned pages without a text layer (no OCR), vertical writing, password-protected
files that need a real user password.
"""
from __future__ import annotations

import base64
import binascii
import codecs
import hashlib
import math
import re
import struct
import unicodedata
import zlib

__all__ = ["PdfDocument", "PdfError"]


class PdfError(Exception):
    """The file is not a PDF this module can read (damaged, password-protected, ...)."""


# =========================================================================== objects

class Name(str):
    """A PDF name such as /Font (stored without the slash)."""
    __slots__ = ()


class Ref:
    __slots__ = ("num", "gen")

    def __init__(self, num, gen):
        self.num, self.gen = num, gen

    def __eq__(self, other):
        return isinstance(other, Ref) and self.num == other.num and self.gen == other.gen

    def __hash__(self):
        return hash((self.num, self.gen))

    def __repr__(self):
        return "Ref(%d, %d)" % (self.num, self.gen)


class Stream:
    __slots__ = ("attrs", "raw", "ref", "data")

    def __init__(self, attrs, raw, ref=None):
        self.attrs, self.raw, self.ref, self.data = attrs, raw, ref, None

    def get(self, key, default=None):
        return self.attrs.get(key, default)


class Op(str):
    """A content-stream operator or a bare keyword."""
    __slots__ = ()


_WS = b"\x00\t\n\x0c\r "
_REG = rb"[^\x00\t\n\x0c\r ()<>\[\]{}/%]"
_TOKEN = re.compile(rb"(?:[\x00\t\n\x0c\r ]+|%[^\r\n]*)*(?:(<<|>>|[\[\]{}])|/(" + _REG + rb"*)|(\()|(<)|(" + _REG + rb"+))")
_NUM = re.compile(rb"[+-]?(?:\d+\.?\d*|\.\d+)\Z")
_SIMPLE_STR = re.compile(rb"\(((?:[^()\\]|\\.)*)\)", re.S)
_NAME_ESC = re.compile(rb"#([0-9A-Fa-f]{2})")
_STR_ESC = re.compile(rb"\\(?:([0-7]{1,3})|(\r\n|\r|\n)|(.))", re.S)
_STR_ESC_MAP = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\x0c"}
_INT = re.compile(rb"[+-]?\d+\Z")


def _unescape_str(raw):
    if b"\\" not in raw:
        return raw

    def rep(m):
        if m.group(1):
            return bytes([int(m.group(1), 8) & 0xFF])
        if m.group(2):
            return b""
        c = m.group(3)
        return _STR_ESC_MAP.get(c, c)
    return _STR_ESC.sub(rep, raw)


def _literal(data, pos):
    """Parse a literal string starting after '(' at pos. Return (bytes, new_pos)."""
    m = _SIMPLE_STR.match(data, pos - 1)
    if m:
        return _unescape_str(m.group(1)), m.end()
    depth, i, n = 1, pos, len(data)
    while i < n:
        c = data[i]
        if c == 0x5C:            # backslash
            i += 2
            continue
        if c == 0x28:
            depth += 1
        elif c == 0x29:
            depth -= 1
            if depth == 0:
                return _unescape_str(data[pos:i]), i + 1
        i += 1
    return _unescape_str(data[pos:]), n


def _hexstr(data, pos):
    end = data.find(b">", pos)
    if end < 0:
        end = len(data)
    digits = re.sub(rb"[^0-9A-Fa-f]", b"", data[pos:end])
    if len(digits) % 2:
        digits += b"0"
    return binascii.unhexlify(digits), end + 1


def _name(raw):
    if b"#" in raw:
        raw = _NAME_ESC.sub(lambda m: bytes([int(m.group(1), 16)]), raw)
    return Name(raw.decode("latin-1"))


def _regular(tok):
    """A regular token: number, true/false/null or a keyword."""
    c = tok[0]
    if c in b"+-.0123456789" and _NUM.match(tok):
        if b"." in tok:
            return float(tok)
        return int(tok)
    if tok == b"true":
        return True
    if tok == b"false":
        return False
    if tok == b"null":
        return None
    return Op(tok.decode("latin-1"))


class _Parser:
    """Parses objects from a byte string (file data or a decoded stream)."""

    def __init__(self, data):
        self.data = data

    def token(self, pos):
        m = _TOKEN.match(self.data, pos)
        if not m:
            return None, None, len(self.data)
        return m.lastindex, m.group(m.lastindex), m.end()

    def obj(self, pos, refs=True):
        """Parse one object at pos. Return (value, pos). Keywords come back as Op."""
        kind, tok, pos = self.token(pos)
        if kind is None:
            raise PdfError("unexpected end of data")
        if kind == 1:
            if tok == b"[":
                out = []
                while True:
                    k2, t2, p2 = self.token(pos)
                    if k2 is None:
                        return out, p2
                    if k2 == 1 and t2 == b"]":
                        return out, p2
                    v, pos = self.obj(pos, refs)
                    out.append(v)
            if tok == b"<<":
                out = {}
                while True:
                    k2, t2, p2 = self.token(pos)
                    if k2 is None:
                        return out, p2
                    if k2 == 1 and t2 == b">>":
                        return out, p2
                    if k2 != 2:                  # damaged dictionary: skip the token
                        if k2 == 5 and t2 in (b"endobj", b"stream"):
                            return out, pos
                        _, pos = self.obj(pos, refs)
                        continue
                    key = _name(t2)
                    k3, t3, p3 = self.token(p2)
                    if k3 == 1 and t3 == b">>":
                        out[key] = None
                        return out, p3
                    v, pos = self.obj(p2, refs)
                    out[key] = v
            return Op(tok.decode("latin-1")), pos        # ], >>, { or }
        if kind == 2:
            return _name(tok), pos
        if kind == 3:
            return _literal(self.data, pos)
        if kind == 4:
            return _hexstr(self.data, pos)
        v = _regular(tok)
        if refs and isinstance(v, int) and not isinstance(v, bool) and _INT.match(tok):
            k2, t2, p2 = self.token(pos)
            if k2 == 5 and _INT.match(t2):
                k3, t3, p3 = self.token(p2)
                if k3 == 5 and t3 == b"R":
                    return Ref(v, int(t2)), p3
        return v, pos


# =========================================================================== filters

def _flate(data):
    try:
        return zlib.decompress(data)
    except zlib.error:
        pass
    for wbits in (15, -15, 31):                  # damaged stream: keep what can be read
        d = zlib.decompressobj(wbits)
        try:
            out = d.decompress(data)
            if out:
                return out
        except zlib.error:
            continue
    return b""


def _lzw(data, early=1):
    out = bytearray()
    table = [bytes([i]) for i in range(256)] + [b"", b""]
    bits, buf, nbits, prev = 9, 0, 0, None
    for byte in data:
        buf = (buf << 8) | byte
        nbits += 8
        while nbits >= bits:
            nbits -= bits
            code = (buf >> nbits) & ((1 << bits) - 1)
            if code == 256:
                table = table[:258]
                bits, prev = 9, None
                continue
            if code == 257:
                return bytes(out)
            if prev is None:
                entry = table[code] if code < len(table) else b""
            elif code < len(table):
                entry = table[code]
                table.append(prev + entry[:1])
            else:
                entry = prev + prev[:1]
                table.append(entry)
            out += entry
            prev = entry
            if len(table) > 4096:                          # corrupt data: a code table never grows past 12 bits
                del table[4096:]
            size = len(table) + early                      # EarlyChange=1 widens one code early
            bits = 12 if size >= 2048 else 11 if size >= 1024 else 10 if size >= 512 else 9
    return bytes(out)


def _a85(data):
    data = re.sub(rb"[\x00\t\n\x0c\r ]", b"", data)
    if data.startswith(b"<~"):
        data = data[2:]
    end = data.find(b"~>")
    if end >= 0:
        data = data[:end]
    try:
        return base64.a85decode(data)
    except ValueError:
        return b""


def _ahex(data):
    end = data.find(b">")
    if end >= 0:
        data = data[:end]
    digits = re.sub(rb"[^0-9A-Fa-f]", b"", data)
    if len(digits) % 2:
        digits += b"0"
    return binascii.unhexlify(digits)


def _runlength(data):
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        c = data[i]
        if c == 128:
            break
        if c < 128:
            out += data[i + 1:i + 2 + c]
            i += 2 + c
        else:
            out += data[i + 1:i + 2] * (257 - c)
            i += 2
    return bytes(out)


def _predict(data, parms):
    pred = parms.get("Predictor", 1) if isinstance(parms, dict) else 1
    if not isinstance(pred, int) or pred < 2:
        return data
    colors = parms.get("Colors", 1) or 1
    bpc = parms.get("BitsPerComponent", 8) or 8
    cols = parms.get("Columns", 1) or 1
    bpp = max(1, colors * bpc // 8)
    rowlen = (colors * bpc * cols + 7) // 8
    if pred == 2:
        if bpc != 8:
            return data
        out = bytearray(data)
        for r in range(0, len(out), rowlen):
            for i in range(r + bpp, min(r + rowlen, len(out))):
                out[i] = (out[i] + out[i - bpp]) & 0xFF
        return bytes(out)
    out = bytearray()
    prev = bytearray(rowlen)
    i = 0
    n = len(data)
    while i < n:
        ftype = data[i]
        row = bytearray(data[i + 1:i + 1 + rowlen])
        i += 1 + rowlen
        if len(row) < rowlen:
            row += bytes(rowlen - len(row))
        if ftype == 1:
            for k in range(bpp, rowlen):
                row[k] = (row[k] + row[k - bpp]) & 0xFF
        elif ftype == 2:
            for k in range(rowlen):
                row[k] = (row[k] + prev[k]) & 0xFF
        elif ftype == 3:
            for k in range(rowlen):
                left = row[k - bpp] if k >= bpp else 0
                row[k] = (row[k] + ((left + prev[k]) >> 1)) & 0xFF
        elif ftype == 4:
            for k in range(rowlen):
                a = row[k - bpp] if k >= bpp else 0
                b = prev[k]
                c = prev[k - bpp] if k >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                row[k] = (row[k] + (a if pa <= pb and pa <= pc else (b if pb <= pc else c))) & 0xFF
        out += row
        prev = row
    return bytes(out)


# =========================================================================== encryption

_PAD = binascii.unhexlify("28BF4E5E4E758A4164004E56FFFA01082E2E00B6D0683E802F0CA9FE6453697A")


def _rc4(key, data):
    s = list(range(256))
    j = 0
    klen = len(key)
    for i in range(256):
        j = (j + s[i] + key[i % klen]) & 0xFF
        s[i], s[j] = s[j], s[i]
    out = bytearray(len(data))
    i = j = 0
    for k, byte in enumerate(data):
        i = (i + 1) & 0xFF
        j = (j + s[i]) & 0xFF
        s[i], s[j] = s[j], s[i]
        out[k] = byte ^ s[(s[i] + s[j]) & 0xFF]
    return bytes(out)


class _AES:
    """Plain AES (FIPS-197) for CBC decryption of PDF data and the R6 password hash."""
    _tables = None

    @classmethod
    def tables(cls):
        if cls._tables is None:
            exp, log = [0] * 512, [0] * 256
            x = 1
            for i in range(255):
                exp[i], log[x] = x, i
                x ^= ((x << 1) ^ (0x1B if x & 0x80 else 0)) & 0xFF
            for i in range(255, 512):
                exp[i] = exp[i - 255]
            sbox, inv = [0] * 256, [0] * 256
            for i in range(256):
                b = 0 if i == 0 else exp[255 - log[i]]
                s = b
                for sh in (1, 2, 3, 4):
                    s ^= ((b << sh) | (b >> (8 - sh))) & 0xFF
                s ^= 0x63
                sbox[i], inv[s] = s, i

            def mul(a, c):
                return 0 if a == 0 or c == 0 else exp[log[a] + log[c]]
            m = {k: [mul(i, k) for i in range(256)] for k in (2, 3, 9, 11, 13, 14)}
            cls._tables = (sbox, inv, m)
        return cls._tables

    def __init__(self, key):
        sbox, _, _ = self.tables()
        nk = len(key) // 4
        self.rounds = nk + 6
        w = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
        rcon = 1
        for i in range(nk, 4 * (self.rounds + 1)):
            t = list(w[i - 1])
            if i % nk == 0:
                t = [sbox[t[1]] ^ rcon, sbox[t[2]], sbox[t[3]], sbox[t[0]]]
                rcon = ((rcon << 1) ^ (0x1B if rcon & 0x80 else 0)) & 0xFF
            elif nk > 6 and i % nk == 4:
                t = [sbox[b] for b in t]
            w.append([a ^ b for a, b in zip(w[i - nk], t)])
        self.rk = [sum(w[4 * r:4 * r + 4], []) for r in range(self.rounds + 1)]

    def encrypt_block(self, block):
        sbox, _, m = self.tables()
        m2, m3 = m[2], m[3]
        s = [b ^ k for b, k in zip(block, self.rk[0])]
        for r in range(1, self.rounds + 1):
            s = [sbox[b] for b in s]
            s = [s[0], s[5], s[10], s[15], s[4], s[9], s[14], s[3],
                 s[8], s[13], s[2], s[7], s[12], s[1], s[6], s[11]]
            if r != self.rounds:
                t = []
                for c in range(0, 16, 4):
                    a0, a1, a2, a3 = s[c:c + 4]
                    t += [m2[a0] ^ m3[a1] ^ a2 ^ a3, a0 ^ m2[a1] ^ m3[a2] ^ a3,
                          a0 ^ a1 ^ m2[a2] ^ m3[a3], m3[a0] ^ a1 ^ a2 ^ m2[a3]]
                s = t
            s = [b ^ k for b, k in zip(s, self.rk[r])]
        return bytes(s)

    def decrypt_block(self, block):
        _, inv, m = self.tables()
        m9, m11, m13, m14 = m[9], m[11], m[13], m[14]
        s = [b ^ k for b, k in zip(block, self.rk[self.rounds])]
        for r in range(self.rounds - 1, -1, -1):
            s = [s[0], s[13], s[10], s[7], s[4], s[1], s[14], s[11],
                 s[8], s[5], s[2], s[15], s[12], s[9], s[6], s[3]]
            s = [inv[b] for b in s]
            s = [b ^ k for b, k in zip(s, self.rk[r])]
            if r:
                t = []
                for c in range(0, 16, 4):
                    a0, a1, a2, a3 = s[c:c + 4]
                    t += [m14[a0] ^ m11[a1] ^ m13[a2] ^ m9[a3], m9[a0] ^ m14[a1] ^ m11[a2] ^ m13[a3],
                          m13[a0] ^ m9[a1] ^ m14[a2] ^ m11[a3], m11[a0] ^ m13[a1] ^ m9[a2] ^ m14[a3]]
                s = t
        return bytes(s)

    def cbc_decrypt(self, iv, data):
        out = bytearray()
        prev = iv
        for i in range(0, len(data) - len(data) % 16, 16):
            blk = data[i:i + 16]
            out += bytes(a ^ b for a, b in zip(self.decrypt_block(blk), prev))
            prev = blk
        return bytes(out)

    def cbc_encrypt(self, iv, data):
        out = bytearray()
        prev = iv
        for i in range(0, len(data), 16):
            prev = self.encrypt_block(bytes(a ^ b for a, b in zip(data[i:i + 16], prev)))
            out += prev
        return bytes(out)


def _aes_decrypt(key, data):
    if len(data) < 32:
        return b""
    plain = _AES(key).cbc_decrypt(data[:16], data[16:])
    if plain and 1 <= plain[-1] <= 16 and plain.endswith(bytes([plain[-1]]) * plain[-1]):
        plain = plain[:-plain[-1]]
    return plain


class _Security:
    """Standard security handler with an empty user password."""

    def __init__(self, enc, file_id):
        self.v = enc.get("V", 0)
        self.r = enc.get("R", 2)
        o, u = enc.get("O", b""), enc.get("U", b"")
        p = enc.get("P", 0)
        self.stm = self.str = "RC4"
        if self.v >= 4:
            cf = enc.get("CF") or {}

            def method(name):
                if name == "Identity":
                    return None
                d = cf.get(name) or {}
                cfm = d.get("CFM", "V2")
                return {"V2": "RC4", "AESV2": "AES", "AESV3": "AES256", "None": None}.get(cfm, "RC4")
            self.stm = method(enc.get("StmF", "Identity"))
            self.str = method(enc.get("StrF", "Identity"))
        if self.r >= 5:
            self.key = self._key_r6(u, enc.get("UE", b""))
        else:
            n = 5 if self.r == 2 else (enc.get("Length", 40) or 40) // 8
            h = hashlib.md5(_PAD + o[:32] + struct.pack("<i", p if p < 2 ** 31 else p - 2 ** 32) + file_id)
            if self.r >= 4 and enc.get("EncryptMetadata", True) is False:
                h.update(b"\xff\xff\xff\xff")
            key = h.digest()
            if self.r >= 3:
                for _ in range(50):
                    key = hashlib.md5(key[:n]).digest()
            self.key = key[:n]
            if self.r == 2:
                ok = _rc4(self.key, _PAD) == u[:32]
            else:
                x = _rc4(self.key, hashlib.md5(_PAD + file_id).digest())
                for i in range(1, 20):
                    x = _rc4(bytes(b ^ i for b in self.key), x)
                ok = x[:16] == u[:16]
            if not ok:
                raise PdfError("The PDF is password-protected.")

    def _key_r6(self, u, ue):
        if len(u) < 48:
            raise PdfError("damaged encryption dictionary")
        check = hashlib.sha256(u[32:40]).digest() if self.r == 5 else self._hash2b(b"", u[32:40])
        if check != u[:32]:
            raise PdfError("The PDF is password-protected.")
        k = hashlib.sha256(u[40:48]).digest() if self.r == 5 else self._hash2b(b"", u[40:48])
        return _AES(k).cbc_decrypt(bytes(16), ue[:32])

    @staticmethod
    def _hash2b(pw, salt, udata=b""):
        k = hashlib.sha256(pw + salt + udata).digest()
        i = 0
        while True:
            k1 = (pw + k + udata) * 64
            e = _AES(k[:16]).cbc_encrypt(k[16:32], k1)
            k = (hashlib.sha256, hashlib.sha384, hashlib.sha512)[sum(e[:16]) % 3](e).digest()
            i += 1
            if i >= 64 and e[-1] <= i - 32:
                return k[:32]

    def decrypt(self, data, ref, kind):
        method = self.stm if kind == "stream" else self.str
        if method is None or not data:
            return data
        if method == "AES256":
            return _aes_decrypt(self.key, data)
        salt = b"sAlT" if method == "AES" else b""
        k = hashlib.md5(self.key + struct.pack("<I", ref.num)[:3] + struct.pack("<H", ref.gen & 0xFFFF)
                        + salt).digest()[:min(len(self.key) + 5, 16)]
        return _aes_decrypt(k, data) if method == "AES" else _rc4(k, data)


# =========================================================================== encodings

_STD_NAMES = ("space exclam quotedbl numbersign dollar percent ampersand quoteright parenleft parenright "
              "asterisk plus comma hyphen period slash zero one two three four five six seven eight nine "
              "colon semicolon less equal greater question at A B C D E F G H I J K L M N O P Q R S T U V W "
              "X Y Z bracketleft backslash bracketright asciicircum underscore quoteleft a b c d e f g h i j "
              "k l m n o p q r s t u v w x y z braceleft bar braceright asciitilde").split()
_WIN_HIGH = ("Euro - quotesinglbase florin quotedblbase ellipsis dagger daggerdbl circumflex perthousand "
             "Scaron guilsinglleft OE - Zcaron - - quoteleft quoteright quotedblleft quotedblright bullet "
             "endash emdash tilde trademark scaron guilsinglright oe - zcaron Ydieresis space exclamdown "
             "cent sterling currency yen brokenbar section dieresis copyright ordfeminine guillemotleft "
             "logicalnot hyphen registered macron degree plusminus twosuperior threesuperior acute mu "
             "paragraph periodcentered cedilla onesuperior ordmasculine guillemotright onequarter onehalf "
             "threequarters questiondown Agrave Aacute Acircumflex Atilde Adieresis Aring AE Ccedilla "
             "Egrave Eacute Ecircumflex Edieresis Igrave Iacute Icircumflex Idieresis Eth Ntilde Ograve "
             "Oacute Ocircumflex Otilde Odieresis multiply Oslash Ugrave Uacute Ucircumflex Udieresis Yacute "
             "Thorn germandbls agrave aacute acircumflex atilde adieresis aring ae ccedilla egrave eacute "
             "ecircumflex edieresis igrave iacute icircumflex idieresis eth ntilde ograve oacute ocircumflex "
             "otilde odieresis divide oslash ugrave uacute ucircumflex udieresis yacute thorn ydieresis").split()
_STD_HIGH = {0xA1: "exclamdown", 0xA2: "cent", 0xA3: "sterling", 0xA4: "fraction", 0xA5: "yen", 0xA6: "florin",
             0xA7: "section", 0xA8: "currency", 0xA9: "quotesingle", 0xAA: "quotedblleft", 0xAB: "guillemotleft",
             0xAC: "guilsinglleft", 0xAD: "guilsinglright", 0xAE: "fi", 0xAF: "fl", 0xB1: "endash",
             0xB2: "dagger", 0xB3: "daggerdbl", 0xB4: "periodcentered", 0xB6: "paragraph", 0xB7: "bullet",
             0xB8: "quotesinglbase", 0xB9: "quotedblbase", 0xBA: "quotedblright", 0xBB: "guillemotright",
             0xBC: "ellipsis", 0xBD: "perthousand", 0xBF: "questiondown", 0xC1: "grave", 0xC2: "acute",
             0xC3: "circumflex", 0xC4: "tilde", 0xC5: "macron", 0xC6: "breve", 0xC7: "dotaccent",
             0xC8: "dieresis", 0xCA: "ring", 0xCB: "cedilla", 0xCD: "hungarumlaut", 0xCE: "ogonek",
             0xCF: "caron", 0xD0: "emdash", 0xE1: "AE", 0xE3: "ordfeminine", 0xE8: "Lslash", 0xE9: "Oslash",
             0xEA: "OE", 0xEB: "ordmasculine", 0xF1: "ae", 0xF5: "dotlessi", 0xF8: "lslash", 0xF9: "oslash",
             0xFA: "oe", 0xFB: "germandbls"}
_EXTRA_GLYPHS = {"quotesingle": "'", "grave": "`", "minus": "\u2212", "fraction": "\u2044", "dotlessi": "\u0131",
                 "Lslash": "\u0141", "lslash": "\u0142", "breve": "\u02d8", "dotaccent": "\u02d9", "ring": "\u02da",
                 "ogonek": "\u02db", "hungarumlaut": "\u02dd", "caron": "\u02c7", "fi": "fi", "fl": "fl",
                 "ff": "ff", "ffi": "ffi", "ffl": "ffl", "nbspace": "\u00a0", "sfthyphen": "\u00ad",
                 "nonbreakingspace": "\u00a0", "dotlessj": "\u0237", "arrowright": "\u2192", "arrowleft": "\u2190",
                 "arrowup": "\u2191", "arrowdown": "\u2193", "arrowboth": "\u2194", "bulletmath": "\u2219",
                 "lessequal": "\u2264", "greaterequal": "\u2265", "notequal": "\u2260", "infinity": "\u221e",
                 "approxequal": "\u2248", "summation": "\u2211", "product": "\u220f", "radical": "\u221a",
                 "integral": "\u222b", "partialdiff": "\u2202", "element": "\u2208", "multiply": "\u00d7",
                 "checkmark": "\u2713", "Omega": "\u03a9", "Delta": "\u0394", "mu": "\u00b5", "pi": "\u03c0",
                 "copyright": "\u00a9", "registered": "\u00ae", "trademark": "\u2122", "Euro": "\u20ac",
                 "space": " ", "hyphen": "-", "quoteleft": "\u2018", "quoteright": "\u2019"}


def _build_glyph_map():
    gm = {}
    for i, name in enumerate(_STD_NAMES):
        gm[name] = chr(32 + i)
    for i, name in enumerate(_WIN_HIGH):
        if name != "-":
            ch = bytes([0x80 + i]).decode("cp1252", "replace")
            gm.setdefault(name, ch)
    gm.update(_EXTRA_GLYPHS)
    gm["quoteright"], gm["quoteleft"] = "\u2019", "\u2018"
    return gm


_GLYPHS = _build_glyph_map()
_UNI_NAME = re.compile(r"uni([0-9A-Fa-f]{4})+\Z|u([0-9A-Fa-f]{4,6})\Z")


def glyph_to_unicode(name):
    """Unicode text for a PostScript glyph name ('A', 'eacute', 'uni00E9', 'f_i', 'a.sc'), or None."""
    if name in _GLYPHS:
        return _GLYPHS[name]
    base = name.split(".", 1)[0]
    if base != name and base in _GLYPHS:
        return _GLYPHS[base]
    if "_" in base:
        parts = [glyph_to_unicode(p) for p in base.split("_")]
        return "".join(parts) if all(parts) else None
    m = _UNI_NAME.match(base)
    if m:
        if m.group(2):
            try:
                return chr(int(m.group(2), 16))
            except (ValueError, OverflowError):
                return None
        hexs = base[3:]
        return "".join(chr(int(hexs[i:i + 4], 16)) for i in range(0, len(hexs), 4))
    if base.isalpha() and len(base) > 1:
        for form in ("GREEK %s LETTER %s", "LATIN %s LETTER %s"):
            try:
                case = "CAPITAL" if base[0].isupper() else "SMALL"
                return unicodedata.lookup(form % (case, base.upper()))
            except KeyError:
                continue
    return None


def _encoding_table(name):
    """code -> unicode for a named base encoding."""
    if name == "WinAnsiEncoding":
        return {c: bytes([c]).decode("cp1252") for c in range(32, 256) if c not in (0x81, 0x8D, 0x8F, 0x90, 0x9D)}
    if name == "MacRomanEncoding":
        return {c: bytes([c]).decode("mac_roman") for c in range(32, 256)}
    if name == "PDFDocEncoding":
        return {c: bytes([c]).decode("latin-1") for c in range(32, 256)}
    table = {32 + i: _GLYPHS[n] for i, n in enumerate(_STD_NAMES)}     # StandardEncoding
    for c, n in _STD_HIGH.items():
        table[c] = glyph_to_unicode(n)
    return table


def _text_string(s):
    """Decode a PDF text string (UTF-16 with BOM, UTF-8 with BOM, or PDFDocEncoding)."""
    if not isinstance(s, (bytes, bytearray)):
        return str(s) if s is not None else ""
    if s[:2] == b"\xfe\xff":
        return s[2:].decode("utf-16-be", "replace")
    if s[:2] == b"\xff\xfe":
        return s[2:].decode("utf-16-le", "replace")
    if s[:3] == b"\xef\xbb\xbf":
        return s[3:].decode("utf-8", "replace")
    return s.decode("cp1252", "replace")


# Widths (1/1000 em) of printable ASCII for fonts that do not carry a Widths array.
_HELV = [278, 278, 355, 556, 556, 889, 667, 222, 333, 333, 389, 584, 278, 333, 278, 278] + [556] * 10 + \
    [278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722,
     778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 222, 556, 556, 500,
     556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500,
     500, 500, 334, 260, 334, 584]
_TIMES = [250, 333, 408, 500, 500, 833, 778, 333, 333, 333, 500, 564, 250, 333, 250, 278] + [500] * 10 + \
    [278, 278, 564, 564, 564, 444, 921, 722, 667, 667, 722, 611, 556, 722, 722, 333, 389, 722, 611, 889, 722,
     722, 556, 722, 667, 556, 611, 722, 722, 944, 722, 722, 611, 333, 278, 333, 469, 500, 333, 444, 500, 444,
     500, 444, 333, 500, 500, 278, 278, 500, 278, 778, 500, 500, 500, 500, 333, 389, 278, 500, 500, 722, 500,
     500, 444, 480, 200, 480, 541]
_BOLD_NAME = re.compile(r"bold|black|heavy|semibold|demibold|\bdemi\b|extrabold|ultrabold|-bol\b|-medi(?:ital)?\b",
                        re.I)
_ITALIC_NAME = re.compile(r"italic|oblique|\bit\b|-it\b", re.I)
_MONO_NAME = re.compile(r"courier|mono|consol|menlo|code", re.I)


# =========================================================================== CMaps

class _CMap:
    """A ToUnicode or encoding CMap: code space ranges plus code -> unicode / cid maps."""

    def __init__(self):
        self.space = []          # (nbytes, lo, hi)
        self.uni = {}            # code -> str
        self.uni_ranges = []     # (lo, hi, start_int, nbytes) or (lo, hi, [str...])
        self.cid = {}
        self.cid_ranges = []     # (lo, hi, cid_start)
        self.identity = False

    def parse(self, data, doc=None, depth=0):
        toks = list(_content_tokens(data))
        i, n = 0, len(toks)
        while i < n:
            t = toks[i]
            if isinstance(t, Op):
                if t == "usecmap" and i and isinstance(toks[i - 1], Name):
                    self.use(toks[i - 1], doc, depth)
                elif t in ("begincodespacerange", "beginbfchar", "beginbfrange", "begincidchar", "begincidrange"):
                    end = "end" + t[5:]
                    j = i + 1
                    args = []
                    while j < n and not (isinstance(toks[j], Op) and toks[j] == end):
                        args.append(toks[j])
                        j += 1
                    self._section(t[5:], args)
                    i = j
            i += 1
        return self

    def use(self, name, doc=None, depth=0):
        if isinstance(name, Name) and name.startswith("Identity"):
            self.identity = True
            if not self.space:
                self.space.append((2, 0, 0xFFFF))

    def _section(self, kind, args):
        if kind == "codespacerange":
            for k in range(0, len(args) - 1, 2):
                lo, hi = args[k], args[k + 1]
                if isinstance(lo, bytes) and isinstance(hi, bytes):
                    self.space.append((len(lo), int.from_bytes(lo, "big"), int.from_bytes(hi, "big")))
        elif kind == "bfchar":
            for k in range(0, len(args) - 1, 2):
                src, dst = args[k], args[k + 1]
                if isinstance(src, bytes):
                    self.uni[int.from_bytes(src, "big")] = _dst_text(dst)
        elif kind == "bfrange":
            for k in range(0, len(args) - 2, 3):
                lo, hi, dst = args[k], args[k + 1], args[k + 2]
                if not (isinstance(lo, bytes) and isinstance(hi, bytes)):
                    continue
                lo_i, hi_i = int.from_bytes(lo, "big"), int.from_bytes(hi, "big")
                if isinstance(dst, list):
                    self.uni_ranges.append((lo_i, hi_i, [_dst_text(d) for d in dst]))
                elif isinstance(dst, bytes) and dst:
                    self.uni_ranges.append((lo_i, hi_i, int.from_bytes(dst, "big"), len(dst)))
        elif kind == "cidchar":
            for k in range(0, len(args) - 1, 2):
                if isinstance(args[k], bytes) and isinstance(args[k + 1], int):
                    self.cid[int.from_bytes(args[k], "big")] = args[k + 1]
        elif kind == "cidrange":
            for k in range(0, len(args) - 2, 3):
                lo, hi, start = args[k], args[k + 1], args[k + 2]
                if isinstance(lo, bytes) and isinstance(hi, bytes) and isinstance(start, int):
                    self.cid_ranges.append((int.from_bytes(lo, "big"), int.from_bytes(hi, "big"), start))

    def unicode(self, code):
        s = self.uni.get(code)
        if s is not None:
            return s
        for r in self.uni_ranges:
            if r[0] <= code <= r[1]:
                if len(r) == 3:
                    k = code - r[0]
                    s = r[2][k] if k < len(r[2]) else None
                else:
                    v = r[2] + code - r[0]
                    s = _dst_text(v.to_bytes(max(r[3], (v.bit_length() + 7) // 8), "big"))
                self.uni[code] = s
                return s
        return None

    def to_cid(self, code):
        c = self.cid.get(code)
        if c is not None:
            return c
        for lo, hi, start in self.cid_ranges:
            if lo <= code <= hi:
                return start + code - lo
        return code if self.identity or not (self.cid or self.cid_ranges) else 0

    def split(self, s):
        """Split a byte string into codes using the code space ranges."""
        if not self.space:
            return [(b, 1) for b in s]
        lens = sorted({r[0] for r in self.space})
        if lens == [2]:
            n = len(s) - len(s) % 2
            out = [((s[i] << 8) | s[i + 1], 2) for i in range(0, n, 2)]
            if len(s) % 2:
                out.append((s[-1], 1))
            return out
        out = []
        i, n = 0, len(s)
        while i < n:
            for ln in lens:
                if i + ln > n:
                    break
                v = int.from_bytes(s[i:i + ln], "big")
                if any(r[0] == ln and r[1] <= v <= r[2] for r in self.space):
                    out.append((v, ln))
                    i += ln
                    break
            else:
                ln = lens[0]
                out.append((int.from_bytes(s[i:i + ln], "big"), ln))
                i += ln
        return out


def _dst_text(dst):
    if isinstance(dst, Name):
        return glyph_to_unicode(dst) or ""
    if not isinstance(dst, (bytes, bytearray)):
        return ""
    if len(dst) == 1:
        return chr(dst[0])
    if len(dst) % 2:
        dst = b"\x00" + dst
    return dst.decode("utf-16-be", "replace")


def _truetype_cmap(data):
    """glyph id -> unicode from a TrueType font program's (3,1)/(3,10)/(0,x) cmap subtable."""
    try:
        num = struct.unpack(">H", data[4:6])[0]
        cmap_off = None
        for i in range(num):
            tag, _, off, _ = struct.unpack(">4sIII", data[12 + 16 * i:28 + 16 * i])
            if tag == b"cmap":
                cmap_off = off
        if cmap_off is None:
            return {}
        ntab = struct.unpack(">H", data[cmap_off + 2:cmap_off + 4])[0]
        subs = []
        for i in range(ntab):
            pid, eid, off = struct.unpack(">HHI", data[cmap_off + 4 + 8 * i:cmap_off + 12 + 8 * i])
            pri = {(3, 10): 0, (3, 1): 1, (0, 4): 2, (0, 3): 3}.get((pid, eid), 9 if pid == 0 else None)
            if pri is not None:
                subs.append((pri, cmap_off + off))
        out = {}
        for _, off in sorted(subs):
            fmt = struct.unpack(">H", data[off:off + 2])[0]
            if fmt == 4:
                segx2 = struct.unpack(">H", data[off + 6:off + 8])[0]
                seg = segx2 // 2
                ends = struct.unpack(">%dH" % seg, data[off + 14:off + 14 + segx2])
                p = off + 16 + segx2
                starts = struct.unpack(">%dH" % seg, data[p:p + segx2])
                deltas = struct.unpack(">%dh" % seg, data[p + segx2:p + 2 * segx2])
                ro_pos = p + 2 * segx2
                ros = struct.unpack(">%dH" % seg, data[ro_pos:ro_pos + segx2])
                for k in range(seg):
                    if starts[k] == 0xFFFF:
                        continue
                    for c in range(starts[k], ends[k] + 1):
                        if ros[k] == 0:
                            g = (c + deltas[k]) & 0xFFFF
                        else:
                            gp = ro_pos + 2 * k + ros[k] + 2 * (c - starts[k])
                            g = struct.unpack(">H", data[gp:gp + 2])[0]
                            if g:
                                g = (g + deltas[k]) & 0xFFFF
                        if g and g not in out:
                            out[g] = chr(c)
            elif fmt == 12:
                ngroups = struct.unpack(">I", data[off + 12:off + 16])[0]
                for k in range(ngroups):
                    s, e, g0 = struct.unpack(">III", data[off + 16 + 12 * k:off + 28 + 12 * k])
                    for c in range(s, min(e, s + 0x10000) + 1):
                        out.setdefault(g0 + c - s, chr(c))
            if out:
                return out
        return out
    except (struct.error, ValueError, OverflowError):
        return {}


def _font_program_style(doc, fd):
    """(bold, italic) read from the embedded font program, or (None, None) when unknown."""
    r = doc.resolve
    ff2 = r(fd.get("FontFile2"))
    if isinstance(ff2, Stream):
        data = doc.stream_data(ff2)
        try:
            num = struct.unpack(">H", data[4:6])[0]
            tables = {}
            for i in range(num):
                tag, _, off, _ = struct.unpack(">4sIII", data[12 + 16 * i:28 + 16 * i])
                tables[tag] = off
            bold = italic = False
            if b"OS/2" in tables:
                o = tables[b"OS/2"]
                sel = struct.unpack(">H", data[o + 62:o + 64])[0]
                bold, italic = bool(sel & 32), bool(sel & 1)
            if b"head" in tables:
                o = tables[b"head"]
                mac = struct.unpack(">H", data[o + 44:o + 46])[0]
                bold, italic = bold or bool(mac & 1), italic or bool(mac & 2)
            if tables:
                return bold, italic
        except struct.error:
            pass
        return None, None
    ff = r(fd.get("FontFile"))
    if isinstance(ff, Stream):
        m = re.search(rb"/Weight\s*\(([^)]*)\)", doc.stream_data(ff)[:20000])
        if m:
            return bool(re.search(rb"bold|black|heavy|semi|demi", m.group(1), re.I)), None
    return None, None


def _type1_builtin_encoding(data, length1):
    """code -> unicode from the clear-text part of an embedded Type1 font program."""
    head = data[:length1] if isinstance(length1, int) and length1 > 0 else data[:20000]
    if b"/Encoding" not in head or b"StandardEncoding def" in head:
        return None
    out = {}
    for m in re.finditer(rb"dup\s+(\d+)\s*/([^\s/\[\]]+)\s+put", head):
        u = glyph_to_unicode(m.group(2).decode("latin-1"))
        if u is not None:
            out[int(m.group(1))] = u
    return out or None


# =========================================================================== fonts

_LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st",
              "ﬆ": "st"}


def _clean(text):
    """Normalise mapped text: ligatures become letters, tabs and line breaks become spaces, other
    control characters (broken ToUnicode maps) count as unmapped."""
    if not text:
        return text
    if text in _LIGATURES:
        return _LIGATURES[text]
    if text[0] < " ":
        if text in ("\t", "\n", "\r", "\r\n"):
            return " "
        text = "".join(c for c in text if c >= " ")
        return text or None
    return text


class _Font:
    def __init__(self, doc, fdict):
        r = doc.resolve
        self.subtype = r(fdict.get("Subtype")) or "Type1"
        base = r(fdict.get("BaseFont")) or r(fdict.get("Name")) or ("Type3" if self.subtype == "Type3" else "")
        base = str(base)
        if len(base) > 7 and base[6] == "+" and base[:6].isalnum():
            base = base[7:]                                   # subset tag
        self.name = base
        self.type3 = self.subtype == "Type3"
        self.cid = self.subtype == "Type0"
        desc_font = None
        if self.cid:
            df = r(fdict.get("DescendantFonts"))
            if isinstance(df, list) and df:
                desc_font = r(df[0])
        fd = r((desc_font or fdict).get("FontDescriptor")) if isinstance(desc_font or fdict, dict) else None
        fd = fd if isinstance(fd, dict) else {}
        dflags = r(fd.get("Flags")) or 0
        dflags = dflags if isinstance(dflags, int) else 0
        weight = r(fd.get("FontWeight")) or 0
        self.flags = 0
        # Like MuPDF: the embedded font program's style bits win; descriptor and name are the fallback.
        prog_bold, prog_italic = _font_program_style(doc, fd)
        if prog_italic if prog_italic is not None else (
                (dflags & 64) or _ITALIC_NAME.search(base) or (r(fd.get("ItalicAngle")) or 0) not in (0, 0.0)):
            self.flags |= 2
        if dflags & 2:
            self.flags |= 4
        if (dflags & 1) or _MONO_NAME.search(base):
            self.flags |= 8
        if prog_bold if prog_bold is not None else (
                (dflags & (1 << 18)) or (isinstance(weight, (int, float)) and weight >= 600) or _BOLD_NAME.search(base)):
            self.flags |= 16
        asc, desc = r(fd.get("Ascent")), r(fd.get("Descent"))
        bbox = r(fd.get("FontBBox")) or r(fdict.get("FontBBox"))
        self.fm = 0.001
        self.t3_scale = 1.0
        if self.type3:
            # Type3 glyph units are arbitrary (bitmap fonts often use FontMatrix [1 0 0 -1 0 0]), so the
            # em used for sizes and spacing is the height of the FontBBox in text space.
            fmx = [r(x) for x in (r(fdict.get("FontMatrix")) or [])]
            if len(fmx) == 6 and all(isinstance(x, (int, float)) for x in fmx):
                self.fm = float(fmx[0]) or 0.001
                if isinstance(bbox, list) and len(bbox) == 4 and all(isinstance(x, (int, float)) for x in bbox):
                    ys = sorted((bbox[1] * fmx[3], bbox[3] * fmx[3]))
                    h = ys[1] - ys[0]
                    if h > 0:
                        self.t3_scale = h
                        asc, desc = ys[1] / h * 1000, ys[0] / h * 1000
        if not isinstance(asc, (int, float)) or not asc:
            asc = bbox[3] if isinstance(bbox, list) and len(bbox) == 4 and bbox[3] else None
        if not isinstance(desc, (int, float)) or not desc:
            desc = bbox[1] if isinstance(bbox, list) and len(bbox) == 4 and isinstance(bbox[1], (int, float)) else None
        std = self._std_metrics(base)
        self.ascent = (float(asc) / 1000) if isinstance(asc, (int, float)) and asc else std[0]
        self.descent = (float(desc) / 1000) if isinstance(desc, (int, float)) and desc else std[1]
        if self.descent > 0 and not self.type3:
            self.descent = -self.descent                      # some producers write Descent without the sign
        if (self.ascent - self.descent < 0.5 or self.ascent > 3) and not self.type3:
            self.ascent, self.descent = 0.8, -0.2
        tu = r(fdict.get("ToUnicode"))
        self.tounicode = _CMap().parse(doc.stream_data(tu), doc) if isinstance(tu, Stream) else None
        if self.cid:
            self._init_cid(doc, fdict, desc_font or {}, fd)
        else:
            self._init_simple(doc, fdict, fd, base, dflags)
        self.cache = {}

    @staticmethod
    def _std_metrics(base):
        b = base.lower()
        if "courier" in b:
            return 0.629, -0.157
        if "times" in b:
            return 0.683, -0.217
        if "helvetica" in b or "arial" in b:
            return 0.718, -0.207
        return 0.8, -0.2

    def _init_simple(self, doc, fdict, fd, base, dflags):
        r = doc.resolve
        first = r(fdict.get("FirstChar"))
        widths = r(fdict.get("Widths"))
        self.widths = {}
        if isinstance(first, int) and isinstance(widths, list):
            for i, w in enumerate(widths):
                w = r(w)
                if isinstance(w, (int, float)):
                    self.widths[first + i] = float(w)
        mw = r(fd.get("MissingWidth"))
        lb = base.lower()
        if isinstance(mw, (int, float)) and mw:
            self.default_w = float(mw)
        elif self.type3:
            self.default_w = 0.0
        else:
            self.default_w = 600.0 if "courier" in lb else (500.0 if "times" in lb else 556.0)
        if not self.widths and not self.type3:
            table = None if "courier" in lb else (_TIMES if "times" in lb else _HELV)
            if table:
                self.widths = {32 + i: float(w) for i, w in enumerate(table)}
        enc = r(fdict.get("Encoding"))
        symbolic = bool(dflags & 4) and not (dflags & 32)
        table = None
        diffs = None
        if isinstance(enc, Name):
            table = _encoding_table(enc)
        elif isinstance(enc, dict):
            be = r(enc.get("BaseEncoding"))
            if isinstance(be, Name):
                table = _encoding_table(be)
            diffs = r(enc.get("Differences"))
        if table is None:
            builtin = None
            ff = r(fd.get("FontFile"))
            if isinstance(ff, Stream):
                builtin = _type1_builtin_encoding(doc.stream_data(ff), r(ff.get("Length1")))
            if builtin:
                table = builtin
            elif symbolic and self.subtype == "TrueType":
                table = {c: chr(c) for c in range(256)}
            elif self.subtype == "TrueType" or self.type3:
                table = _encoding_table("WinAnsiEncoding")
            else:
                table = _encoding_table("StandardEncoding")
        table = dict(table)
        if isinstance(diffs, list):
            code = 0
            for d in diffs:
                d = r(d)
                if isinstance(d, int):
                    code = d
                elif isinstance(d, Name):
                    u = glyph_to_unicode(d)
                    table[code] = u if u is not None else "\ufffd"
                    code += 1
        self.table = table

    def _init_cid(self, doc, fdict, dfont, fd):
        r = doc.resolve
        enc = r(fdict.get("Encoding"))
        self.cmap = _CMap()
        if isinstance(enc, Stream):
            self.cmap.parse(doc.stream_data(enc), doc)
            use = r(enc.get("UseCMap"))
            if isinstance(use, Name):
                self.cmap.use(use)
            if not self.cmap.space:
                self.cmap.space.append((2, 0, 0xFFFF))
        else:
            self.cmap.use(Name("Identity-H"))
        self.dw = r(dfont.get("DW"))
        self.dw = float(self.dw) if isinstance(self.dw, (int, float)) else 1000.0
        self.widths = {}
        w = r(dfont.get("W"))
        if isinstance(w, list):
            i = 0
            w = [r(x) for x in w]
            while i < len(w):
                start = w[i]
                if i + 1 < len(w) and isinstance(w[i + 1], list):
                    for k, x in enumerate(w[i + 1]):
                        x = r(x)
                        if isinstance(x, (int, float)) and isinstance(start, int):
                            self.widths[start + k] = float(x)
                    i += 2
                elif i + 2 < len(w):
                    lo, hi, x = w[i], w[i + 1], w[i + 2]
                    if isinstance(lo, int) and isinstance(hi, int) and isinstance(x, (int, float)):
                        for c in range(lo, min(hi, lo + 65536) + 1):
                            self.widths[c] = float(x)
                    i += 3
                else:
                    break
        self.gid_uni = None
        if self.tounicode is None:
            ff = r(fd.get("FontFile2"))
            if isinstance(ff, Stream):
                g2u = _truetype_cmap(doc.stream_data(ff))
                c2g = r(dfont.get("CIDToGIDMap"))
                if isinstance(c2g, Stream):
                    m = doc.stream_data(c2g)
                    self.gid_uni = {cid: g2u[(m[2 * cid] << 8) | m[2 * cid + 1]]
                                    for cid in range(len(m) // 2) if ((m[2 * cid] << 8) | m[2 * cid + 1]) in g2u}
                else:
                    self.gid_uni = g2u

    def decode(self, s):
        """bytes -> [(text, width_em, is_space_code)]."""
        hit = self.cache.get(s)
        if hit is not None:
            return hit
        out = []
        if self.cid:
            for code, nb in self.cmap.split(s):
                cid = self.cmap.to_cid(code)
                text = _clean(self.tounicode.unicode(code)) if self.tounicode else None
                if text is None and self.gid_uni:
                    text = _clean(self.gid_uni.get(cid))
                if text is None:
                    text = "\ufffd"
                w = self.widths.get(cid, self.dw) / 1000.0
                out.append((text, w, nb == 1 and code == 32))
        else:
            tu = self.tounicode
            for code in s:
                text = _clean(tu.unicode(code)) if tu else None
                if text is None:
                    text = _clean(self.table.get(code))
                    if text is None:
                        text = chr(code) if 32 <= code < 127 else "\ufffd"
                w = self.widths.get(code, self.default_w) * (self.fm if self.type3 else 0.001)
                out.append((text, w, code == 32))
        if len(self.cache) < 20000:
            self.cache[s] = out
        return out


# =========================================================================== content streams

_CONTENT = re.compile(
    rb"([+-]?(?:\d+\.?\d*|\.\d+))(?!" + _REG + rb")"            # 1 number
    rb"|/(" + _REG + rb"*)"                                      # 2 name
    rb"|\(((?:[^()\\]|\\.)*)\)"                                  # 3 literal string without nesting
    rb"|(\()"                                                    # 4 literal string with nested ()
    rb"|<([0-9A-Fa-f]*)>"                                        # 5 compact hex string
    rb"|(<<|>>|[\[\]{}])"                                        # 6 delimiter
    rb"|(<)"                                                     # 7 hex string with spaces
    rb"|(" + _REG + rb"+)"                                       # 8 operator / keyword
    rb"|(%[^\r\n]*)", re.S)                                      # 9 comment
_OPS = {}


def _content_tokens(data):
    """Yield operands and operators of a content stream. Arrays become lists, dicts become dicts."""
    stack = []
    cur = None
    it = _CONTENT.finditer(data)
    ops = _OPS
    unhex = binascii.unhexlify
    while True:
        for m in it:
            k = m.lastindex
            if k == 1:
                t = m.group(1)
                v = float(t) if b"." in t else int(t)
            elif k == 8:
                t = m.group(8)
                v = ops.get(t)
                if v is None:
                    if t == b"true":
                        v = True
                    elif t == b"false":
                        v = False
                    elif t == b"null":
                        v = None
                    else:
                        v = ops[t] = Op(t.decode("latin-1"))
                if v.__class__ is Op and cur is None:
                    if v == "BI":
                        it = _CONTENT.finditer(data, _skip_inline_image(data, m.end()))
                        break
                    yield v
                    continue
            elif k == 3:
                v = _unescape_str(m.group(3))
            elif k == 5:
                h = m.group(5)
                v = unhex(h if not len(h) % 2 else h + b"0")
            elif k == 2:
                v = _name(m.group(2))
            elif k == 6:
                t = m.group(6)
                if t == b"[" or t == b"<<":
                    stack.append(cur)
                    cur = [] if t == b"[" else ("dict", [])
                    continue
                if t == b"]" or t == b">>":
                    if cur is None:
                        continue
                    v = cur if cur.__class__ is list else dict(zip(cur[1][0::2], cur[1][1::2]))
                    cur = stack.pop() if stack else None
                else:
                    continue                                    # { } in PostScript calculator code
            elif k == 4:
                v, pos = _literal(data, m.end())
                it = _CONTENT.finditer(data, pos)
                if cur is None:
                    yield v
                elif cur.__class__ is list:
                    cur.append(v)
                else:
                    cur[1].append(v)
                break
            elif k == 7:
                v, pos = _hexstr(data, m.end())
                it = _CONTENT.finditer(data, pos)
                if cur is None:
                    yield v
                elif cur.__class__ is list:
                    cur.append(v)
                else:
                    cur[1].append(v)
                break
            else:
                continue                                        # comment
            if cur is None:
                yield v
            elif cur.__class__ is list:
                cur.append(v)
            else:
                cur[1].append(v)
        else:
            return


_EI = re.compile(rb"[\x00\t\n\x0c\r ]EI(?=[\x00\t\n\x0c\r ]|$)")


def _skip_inline_image(data, pos):
    i = data.find(b"ID", pos)
    if i < 0:
        return len(data)
    m = _EI.search(data, i + 3)
    return m.end() if m else len(data)


def _mul(m1, m2):
    a, b, c, d, e, f = m1
    A, B, C, D, E, F = m2
    return (a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D, e * A + f * C + E, e * B + f * D + F)


_IDENT = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
SPACE_DIST, SPACE_MAX_DIST, BASE_MAX_DIST, PARAGRAPH_DIST = 0.15, 0.8, 0.8, 1.5


class _Collector:
    """Groups characters into spans, lines and blocks, the way MuPDF's structured-text device does."""

    def __init__(self, width, height):
        self.width, self.height = width, height
        self.blocks = []
        self.line = None
        self.pen = None
        self.dir = None
        self.last_char = None

    def add(self, text, ox, oy, ex, ey, lin, font):
        """One glyph: origin (ox, oy) and end of its advance (ex, ey); lin holds the up vector (one
        size long), the unit direction, the size and the span key (see Page._show)."""
        ux, uy, dx, dy, size, key = lin[6:]
        if size <= 0:
            return
        asc, desc = font.ascent, font.descent
        xs = (ox + ux * asc, ox + ux * desc, ex + ux * asc, ex + ux * desc)
        ys = (oy + uy * asc, oy + uy * desc, ey + uy * asc, ey + uy * desc)
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        if x1 < 0 or y1 < 0 or x0 > self.width or y0 > self.height:
            return                                             # outside the page (like a media-box clip)
        new_line = new_para = add_space = False
        if self.line is None:
            new_para = True
        else:
            lc = self.last_char
            if lc and lc[0] == text and abs(lc[1] - ox) < 0.1 * size and abs(lc[2] - oy) < 0.1 * size:
                return                                         # fake bold: same glyph printed twice
            pdx, pdy = self.dir
            if abs(pdx * dx + pdy * dy) < 0.95:
                new_para = True
            else:
                mx, my = ox - self.pen[0], oy - self.pen[1]
                spacing = (dx * mx + dy * my) / size
                base = (-dy * mx + dx * my) / size
                if abs(base) < BASE_MAX_DIST:
                    if abs(spacing) < SPACE_DIST:
                        pass
                    elif abs(spacing) < SPACE_MAX_DIST:
                        add_space = True
                    else:
                        new_line = True
                elif abs(base) < PARAGRAPH_DIST:
                    new_line = True
                else:
                    new_para = True
        if new_para:
            self.blocks.append([])
            self.line = None
        if new_para or new_line:
            self.line = {"dir": (dx, dy), "spans": []}
            self.blocks[-1].append(self.line)
        spans = self.line["spans"]
        if add_space and spans and not spans[-1]["chars"][-1][0].isspace() and not text.isspace():
            sp = spans[-1]
            px, py = self.pen
            sp["chars"].append((" ", sp["chars"][-1][1], sp["chars"][-1][2], px, sp["chars"][-1][4]))
            sp["bbox"][2] = max(sp["bbox"][2], px)
        if not spans or spans[-1]["key"] != key:
            spans.append({"key": key, "font": font.name, "size": size, "flags": font.flags,
                          "ascender": asc, "descender": desc, "origin": (ox, oy),
                          "bbox": [x0, y0, x1, y1], "chars": []})
        sp = spans[-1]
        sp["chars"].append((text, x0, y0, x1, y1))
        b = sp["bbox"]
        if x0 < b[0]:
            b[0] = x0
        if y0 < b[1]:
            b[1] = y0
        if x1 > b[2]:
            b[2] = x1
        if y1 > b[3]:
            b[3] = y1
        self.pen = (ex, ey)
        self.dir = (dx, dy)
        self.last_char = (text, ox, oy)

    def result(self, sort):
        blocks = []
        for blk in self.blocks:
            lines = []
            for ln in blk:
                spans = []
                for sp in ln["spans"]:
                    text = "".join(c[0] for c in sp["chars"])
                    spans.append({"size": sp["size"], "flags": sp["flags"], "font": sp["font"], "color": 0,
                                  "ascender": sp["ascender"], "descender": sp["descender"], "text": text,
                                  "origin": sp["origin"], "bbox": tuple(sp["bbox"])})
                if spans:
                    bb = _union(s["bbox"] for s in spans)
                    lines.append({"spans": spans, "wmode": 0, "dir": ln["dir"], "bbox": bb})
            if lines:
                blocks.append({"type": 0, "number": len(blocks), "lines": lines,
                               "bbox": _union(l["bbox"] for l in lines)})
        if sort:
            blocks.sort(key=lambda b: (b["bbox"][3], b["bbox"][0]))
        return {"width": self.width, "height": self.height, "blocks": blocks}


def _union(boxes):
    boxes = list(boxes)
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


class _GState:
    __slots__ = ("ctm", "font", "fs", "tc", "tw", "th", "tl", "rise", "clip")

    def __init__(self, ctm):
        self.ctm = ctm
        self.font, self.fs, self.tc, self.tw, self.th, self.tl, self.rise = None, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0
        self.clip = None                       # bounding box of the clipping path in page space

    def copy(self):
        g = _GState(self.ctm)
        g.font, g.fs, g.tc, g.tw, g.th, g.tl, g.rise = self.font, self.fs, self.tc, self.tw, self.th, self.tl, self.rise
        g.clip = self.clip
        return g


_PATH_POINTS = {"m": 2, "l": 2, "c": 6, "v": 4, "y": 4}
_PAINT = {"n", "S", "s", "f", "F", "f*", "B", "B*", "b", "b*"}


class Page:
    def __init__(self, doc, pdict, number):
        self.doc, self.dict, self.number = doc, pdict, number
        r = doc.resolve
        box = r(pdict.get("CropBox")) or r(pdict.get("MediaBox")) or [0, 0, 612, 792]
        box = [float(r(v)) if isinstance(r(v), (int, float)) else 0.0 for v in box][:4]
        if len(box) < 4:
            box = [0.0, 0.0, 612.0, 792.0]
        x0, y0, x1, y1 = min(box[0], box[2]), min(box[1], box[3]), max(box[0], box[2]), max(box[1], box[3])
        rot = r(pdict.get("Rotate")) or 0
        rot = int(rot) % 360 if isinstance(rot, (int, float)) else 0
        if rot == 90:
            self.matrix = (0.0, 1.0, 1.0, 0.0, -x0, -y0)
            self.width, self.height = y1 - y0, x1 - x0
        elif rot == 180:
            self.matrix = (-1.0, 0.0, 0.0, 1.0, x1, -y0)
            self.width, self.height = x1 - x0, y1 - y0
        elif rot == 270:
            self.matrix = (0.0, -1.0, -1.0, 0.0, y1, x1)
            self.width, self.height = y1 - y0, x1 - x0
        else:
            self.matrix = (1.0, 0.0, 0.0, -1.0, -x0, y1)
            self.width, self.height = x1 - x0, y1 - y0

    @property
    def rect(self):
        return self

    def text_dict(self, sort=False):
        col = _Collector(self.width, self.height)
        contents = self.doc.resolve(self.dict.get("Contents"))
        parts = contents if isinstance(contents, list) else [contents]
        data = b"\n".join(self.doc.stream_data(self.doc.resolve(p)) for p in parts
                          if isinstance(self.doc.resolve(p), Stream))
        res = self.doc.resolve(self.dict.get("Resources")) or {}
        try:
            self._run(data, res if isinstance(res, dict) else {}, _GState(self.matrix), col, 0)
        except RecursionError:
            pass
        return col.result(sort)

    def _font(self, res, name):
        fonts = self.doc.resolve(res.get("Font")) if isinstance(res, dict) else None
        if not isinstance(fonts, dict):
            return None
        ref = fonts.get(name)
        key = ref if isinstance(ref, Ref) else id(ref)
        cache = self.doc.font_cache
        if key not in cache:
            fd = self.doc.resolve(ref)
            try:
                cache[key] = _Font(self.doc, fd) if isinstance(fd, dict) else None
            except (PdfError, ValueError, TypeError, KeyError, IndexError, struct.error):
                cache[key] = None
        return cache[key]

    def _run(self, data, res, gs, col, depth):
        if depth > 12:
            return
        stack = []
        ops = []
        tm = tlm = _IDENT
        num = (int, float)
        doc = self.doc
        path, clip_next = None, False
        for tok in _content_tokens(data):
            if not isinstance(tok, Op):
                ops.append(tok)
                continue
            try:
                if tok == "Tj" or tok == "TJ" or tok == "'" or tok == '"':
                    if tok == "'" or tok == '"':
                        if tok == '"' and len(ops) >= 3:
                            gs.tw, gs.tc = float(ops[-3]), float(ops[-2])
                        tlm = (tlm[0], tlm[1], tlm[2], tlm[3], -gs.tl * tlm[2] + tlm[4], -gs.tl * tlm[3] + tlm[5])
                        tm = tlm
                    if not ops or gs.font is None:
                        ops = []
                        continue
                    arg = ops[-1]
                    tm = self._show(arg if isinstance(arg, list) else [arg], gs, tm, col)
                elif tok == "Td":
                    tx, ty = float(ops[-2]), float(ops[-1])
                    tlm = (tlm[0], tlm[1], tlm[2], tlm[3], tx * tlm[0] + ty * tlm[2] + tlm[4],
                           tx * tlm[1] + ty * tlm[3] + tlm[5])
                    tm = tlm
                elif tok == "Tf":
                    gs.font = self._font(res, ops[-2]) if len(ops) >= 2 else None
                    gs.fs = float(ops[-1]) if ops and isinstance(ops[-1], num) else 0.0
                elif tok == "Tm":
                    tm = tlm = tuple(float(x) for x in ops[-6:])
                elif tok == "TD":
                    tx, ty = float(ops[-2]), float(ops[-1])
                    gs.tl = -ty
                    tlm = (tlm[0], tlm[1], tlm[2], tlm[3], tx * tlm[0] + ty * tlm[2] + tlm[4],
                           tx * tlm[1] + ty * tlm[3] + tlm[5])
                    tm = tlm
                elif tok == "T*":
                    tlm = (tlm[0], tlm[1], tlm[2], tlm[3], -gs.tl * tlm[2] + tlm[4], -gs.tl * tlm[3] + tlm[5])
                    tm = tlm
                elif tok == "BT":
                    tm = tlm = _IDENT
                elif tok == "q":
                    stack.append(gs.copy())
                elif tok == "Q":
                    if stack:
                        gs = stack.pop()
                elif tok == "cm":
                    gs.ctm = _mul(tuple(float(x) for x in ops[-6:]), gs.ctm)
                elif tok == "Tc":
                    gs.tc = float(ops[-1])
                elif tok == "Tw":
                    gs.tw = float(ops[-1])
                elif tok == "Tz":
                    gs.th = float(ops[-1]) / 100.0
                elif tok == "TL":
                    gs.tl = float(ops[-1])
                elif tok == "Ts":
                    gs.rise = float(ops[-1])
                elif tok == "Do" and ops:
                    xo = doc.resolve((doc.resolve(res.get("XObject")) or {}).get(ops[-1]))
                    if isinstance(xo, Stream) and doc.resolve(xo.get("Subtype")) == "Form":
                        sub = gs.copy()
                        mx = doc.resolve(xo.get("Matrix"))
                        if isinstance(mx, list) and len(mx) == 6:
                            sub.ctm = _mul(tuple(float(doc.resolve(x)) for x in mx), sub.ctm)
                        bb = doc.resolve(xo.get("BBox"))
                        if isinstance(bb, list) and len(bb) == 4:
                            bb = [float(doc.resolve(x)) for x in bb]
                            m = sub.ctm
                            pts = [(x * m[0] + y * m[2] + m[4], x * m[1] + y * m[3] + m[5])
                                   for x in (bb[0], bb[2]) for y in (bb[1], bb[3])]
                            box = [min(p[0] for p in pts), min(p[1] for p in pts),
                                   max(p[0] for p in pts), max(p[1] for p in pts)]
                            c = sub.clip
                            sub.clip = box if c is None else [max(c[0], box[0]), max(c[1], box[1]),
                                                              min(c[2], box[2]), min(c[3], box[3])]
                        xres = doc.resolve(xo.get("Resources"))
                        self._run(doc.stream_data(xo), xres if isinstance(xres, dict) else res, sub, col, depth + 1)
                elif tok in _PATH_POINTS or tok == "re":
                    vals = [float(x) for x in ops[-(4 if tok == "re" else _PATH_POINTS[tok]):]]
                    if tok == "re":
                        x, y, w, h = vals
                        vals = [x, y, x + w, y, x, y + h, x + w, y + h]
                    m = gs.ctm
                    for k in range(0, len(vals) - 1, 2):
                        px = vals[k] * m[0] + vals[k + 1] * m[2] + m[4]
                        py = vals[k] * m[1] + vals[k + 1] * m[3] + m[5]
                        if path is None:
                            path = [px, py, px, py]
                        else:
                            path = [min(path[0], px), min(path[1], py), max(path[2], px), max(path[3], py)]
                elif tok == "W" or tok == "W*":
                    clip_next = True
                elif tok in _PAINT:
                    if clip_next and path is not None:
                        c = gs.clip
                        gs.clip = path if c is None else [max(c[0], path[0]), max(c[1], path[1]),
                                                          min(c[2], path[2]), min(c[3], path[3])]
                    clip_next, path = False, None
                elif tok == "gs" and ops:
                    eg = doc.resolve((doc.resolve(res.get("ExtGState")) or {}).get(ops[-1]))
                    fnt = doc.resolve(eg.get("Font")) if isinstance(eg, dict) else None
                    if isinstance(fnt, list) and len(fnt) == 2:
                        fd = doc.resolve(fnt[0])
                        if isinstance(fd, dict):
                            key = fnt[0] if isinstance(fnt[0], Ref) else id(fd)
                            if key not in doc.font_cache:
                                doc.font_cache[key] = _Font(doc, fd)
                            gs.font, gs.fs = doc.font_cache[key], float(fnt[1])
            except (IndexError, ValueError, TypeError):
                pass
            ops = []

    def _show(self, items, gs, tm, col):
        font = gs.font
        fs, th, tc, tw, rise = gs.fs, gs.th, gs.tc, gs.tw, gs.rise
        ctm = gs.ctm
        ck = (tm[0], tm[1], tm[2], tm[3], ctm[0], ctm[1], ctm[2], ctm[3], fs, th, font)
        lin = self.doc.lin_cache.get(ck)
        if lin is None:
            a1, b1 = tm[0] * ctm[0] + tm[1] * ctm[2], tm[0] * ctm[1] + tm[1] * ctm[3]
            c1, d1 = tm[2] * ctm[0] + tm[3] * ctm[2], tm[2] * ctm[1] + tm[3] * ctm[3]
            sx = fs * th
            ta, tb, tcc, td = sx * a1, sx * b1, fs * c1, fs * d1
            size = math.sqrt(abs(ta * td - tb * tcc)) * font.t3_scale
            ln = math.hypot(ta, tb) or 1.0
            ulen = math.hypot(tcc, td) or 1.0
            # up vector in page space: the text y axis, one size long
            lin = (a1, b1, c1, d1, ta, tb, tcc / ulen * size, td / ulen * size, ta / ln, tb / ln, size,
                   (font.name, round(size, 3), font.flags))
            if len(self.doc.lin_cache) > 50000:
                self.doc.lin_cache.clear()
            self.doc.lin_cache[ck] = lin
        a1, b1, c1, d1, ta, tb = lin[:6]
        tma, tmb, tme, tmf = tm[0], tm[1], tm[4], tm[5]
        e1 = tme * ctm[0] + tmf * ctm[2] + ctm[4]
        f1 = tme * ctm[1] + tmf * ctm[3] + ctm[5]
        add = col.add
        clip = gs.clip
        ux3, uy3 = lin[6] * 0.3, lin[7] * 0.3
        for it in items:
            if isinstance(it, (bytes, bytearray)):
                for text, w, is_space in font.decode(bytes(it)):
                    ox = rise * c1 + e1
                    oy = rise * d1 + f1
                    if text:
                        ex, ey = ox + w * ta, oy + w * tb
                        if clip is not None:            # skip glyphs hidden by the clipping path
                            cx, cy = (ox + ex) / 2 + ux3, (oy + ey) / 2 + uy3
                            if not (clip[0] - 1 <= cx <= clip[2] + 1 and clip[1] - 1 <= cy <= clip[3] + 1):
                                text = ""
                        if text:
                            add(text, ox, oy, ex, ey, lin, font)
                    tx = w * fs * th + (tc + (tw if is_space else 0.0)) * th
                    e1 += tx * a1
                    f1 += tx * b1
                    tme += tx * tma
                    tmf += tx * tmb
            elif isinstance(it, (int, float)):
                tx = -float(it) / 1000.0 * fs * th
                e1 += tx * a1
                f1 += tx * b1
                tme += tx * tma
                tmf += tx * tmb
        return (tm[0], tm[1], tm[2], tm[3], tme, tmf)


# =========================================================================== document

_OBJ_HEAD = re.compile(rb"(\d+)[\x00\t\n\x0c\r ]+(\d+)[\x00\t\n\x0c\r ]+obj\b")


class PdfDocument:
    def __init__(self, path):
        with open(path, "rb") as fh:
            self.data = fh.read()
        if b"%PDF" not in self.data[:1024]:
            raise PdfError("not a PDF file")
        self.parser = _Parser(self.data)
        self.cache = {}
        self.font_cache = {}
        self.lin_cache = {}
        self.security = None
        self.xref = {}
        self.trailer = {}
        self.repaired = False
        try:
            self._load_xref()
            root = self.resolve(self.trailer.get("Root"))
            if not isinstance(root, dict):
                raise PdfError("no document catalog")
        except (PdfError, ValueError, IndexError, TypeError, struct.error):
            self._repair()
        self._init_security()
        root = self.resolve(self.trailer.get("Root"))
        if not isinstance(root, dict):
            if not self.repaired:
                self._repair()
                root = self.resolve(self.trailer.get("Root"))
            if not isinstance(root, dict):
                raise PdfError("damaged PDF: no document catalog")
        self.root = root
        self.pages = self._load_pages()
        if not self.pages and not self.repaired:
            self._repair()
            self.root = self.resolve(self.trailer.get("Root")) or {}
            self.pages = self._load_pages()
        info = self.resolve(self.trailer.get("Info"))
        self.metadata = {}
        if isinstance(info, dict):
            for k, v in info.items():
                v = self.resolve(v)
                if isinstance(v, (bytes, str)):
                    self.metadata[k.lower()] = _text_string(v).strip("\x00 ")
        self.title = self.metadata.get("title", "")

    # ---------------------------------------------------------------- xref
    def _load_xref(self):
        data = self.data
        sx = data.rfind(b"startxref")
        if sx < 0:
            raise PdfError("no startxref")
        m = re.match(rb"startxref[\x00\t\n\x0c\r ]+(\d+)", data[sx:sx + 40])
        if not m:
            raise PdfError("bad startxref")
        pos = int(m.group(1))
        seen = set()
        first = True
        while pos is not None and pos not in seen and 0 <= pos < len(data):
            seen.add(pos)
            p = pos
            while p < len(data) and data[p] in _WS:
                p += 1
            if data.startswith(b"xref", p):
                trailer = self._xref_table(p + 4)
                xs = self.resolve(trailer.get("XRefStm"))
                if isinstance(xs, int):
                    try:
                        self._xref_stream(xs)
                    except PdfError:
                        pass
            else:
                trailer = self._xref_stream(p)
            for k, v in trailer.items():
                if first or k not in self.trailer:
                    self.trailer.setdefault(k, v)
            first = False
            prev = trailer.get("Prev")
            pos = prev if isinstance(prev, int) else None

    def _xref_table(self, pos):
        data = self.data
        line = re.compile(rb"[\x00\t\n\x0c\r ]*(\d+)[ ]+(\d+)[ \t]*\r?\n?")
        entry = re.compile(rb"[\x00\t\n\x0c\r ]*(\d{1,10})[ ]+(\d{1,5})[ ]+([nf])")
        while True:
            m = line.match(data, pos)
            if not m:
                break
            start, count = int(m.group(1)), int(m.group(2))
            pos = m.end()
            for i in range(count):
                e = entry.match(data, pos)
                if not e:
                    break
                pos = e.end()
                num = start + i
                if e.group(3) == b"n" and num not in self.xref:
                    self.xref[num] = (1, int(e.group(1)), int(e.group(2)))
                elif num not in self.xref:
                    self.xref[num] = (0, 0, 0)
        t = data.find(b"trailer", pos)
        if t < 0:
            raise PdfError("no trailer")
        trailer, _ = self.parser.obj(t + 7)
        if not isinstance(trailer, dict):
            raise PdfError("bad trailer")
        return trailer

    def _xref_stream(self, pos):
        m = _OBJ_HEAD.match(self.data, pos)
        if not m:
            raise PdfError("bad xref offset")
        stm = self._parse_indirect(pos, Ref(int(m.group(1)), int(m.group(2))), decrypt=False)
        if not isinstance(stm, Stream):
            raise PdfError("xref is not a stream")
        attrs = stm.attrs
        w = [self.resolve(x) for x in self.resolve(attrs.get("W"))]
        size = self.resolve(attrs.get("Size")) or 0
        index = self.resolve(attrs.get("Index")) or [0, size]
        raw = self._decode(stm, crypt=False)
        width = sum(w)
        k = 0
        for s in range(0, len(index) - 1, 2):
            start, count = index[s], index[s + 1]
            for i in range(count):
                if k + width > len(raw):
                    break
                vals = []
                for wn in w:
                    vals.append(int.from_bytes(raw[k:k + wn], "big") if wn else None)
                    k += wn
                t = vals[0] if w[0] else 1
                num = start + i
                if num in self.xref:
                    continue
                if t == 1:
                    self.xref[num] = (1, vals[1], vals[2] or 0)
                elif t == 2:
                    self.xref[num] = (2, vals[1], vals[2] or 0)
                else:
                    self.xref[num] = (0, 0, 0)
        return attrs

    def _repair(self):
        """Rebuild the object table by scanning the whole file."""
        self.repaired = True
        self.xref = {}
        self.cache = {}
        data = self.data
        for m in _OBJ_HEAD.finditer(data):
            self.xref[int(m.group(1))] = (1, m.start(), int(m.group(2)))
        trailer = {}
        for m in re.finditer(rb"trailer[\x00\t\n\x0c\r ]*<<", data):
            try:
                t, _ = self.parser.obj(m.end() - 2)
                if isinstance(t, dict):
                    trailer.update(t)
            except PdfError:
                continue
        objstms = []
        for num, (_, off, gen) in list(self.xref.items()):
            head = data[off:off + 400]
            if b"/ObjStm" in head or b"/XRef" in head:
                try:
                    o = self._parse_indirect(off, Ref(num, gen), decrypt=False)
                except PdfError:
                    continue
                if isinstance(o, Stream) and o.get("Type") == "XRef":
                    for k in ("Root", "Info", "Encrypt", "ID"):
                        if k in o.attrs and k not in trailer:
                            trailer[k] = o.attrs[k]
                elif isinstance(o, Stream) and o.get("Type") == "ObjStm":
                    objstms.append(num)
        self.trailer = trailer
        for stm_num in objstms:
            try:
                stm = self.get(Ref(stm_num, self.xref[stm_num][2]))
                for idx, (num, _) in enumerate(self._objstm_index(stm)):
                    if num not in self.xref:
                        self.xref[num] = (2, stm_num, idx)
            except (PdfError, ValueError, IndexError):
                continue
        if not isinstance(self.resolve(trailer.get("Root")), dict):
            for num in sorted(self.xref):
                o = self.get(Ref(num, self.xref[num][2] if self.xref[num][0] == 1 else 0))
                if isinstance(o, dict) and o.get("Type") == "Catalog":
                    self.trailer["Root"] = Ref(num, self.xref[num][2] if self.xref[num][0] == 1 else 0)
                    break

    def _init_security(self):
        enc = self.resolve(self.trailer.get("Encrypt"))
        if not isinstance(enc, dict):
            return
        if self.resolve(enc.get("Filter")) != "Standard":
            raise PdfError("The PDF uses an unsupported encryption handler.")
        ids = self.resolve(self.trailer.get("ID"))
        file_id = self.resolve(ids[0]) if isinstance(ids, list) and ids else b""
        enc_ref = self.trailer.get("Encrypt")
        enc = {k: self.resolve(v) for k, v in enc.items()}
        self.security = _Security(enc, file_id if isinstance(file_id, bytes) else b"")
        self.enc_ref = enc_ref if isinstance(enc_ref, Ref) else None
        self.cache = {k: v for k, v in self.cache.items() if isinstance(v, (int, float, Name))}

    # ---------------------------------------------------------------- objects
    def resolve(self, v):
        depth = 0
        while isinstance(v, Ref) and depth < 32:
            v = self.get(v)
            depth += 1
        return v

    def get(self, ref):
        if ref in self.cache:
            return self.cache[ref]
        self.cache[ref] = None                                  # guard against reference loops
        entry = self.xref.get(ref.num)
        val = None
        try:
            if entry and entry[0] == 1:
                val = self._parse_indirect(entry[1], ref)
            elif entry and entry[0] == 2:
                stm = self.get(Ref(entry[1], 0))
                if isinstance(stm, Stream):
                    val = self._from_objstm(stm, ref.num, entry[2])
        except (PdfError, ValueError, IndexError, TypeError, RecursionError):
            val = None
        self.cache[ref] = val
        return val

    def _parse_indirect(self, pos, ref, decrypt=True):
        data = self.data
        m = _OBJ_HEAD.match(data, pos)
        if not m:
            near = _OBJ_HEAD.search(data, max(0, pos - 64), pos + 64)   # offsets that are slightly off
            if near and int(near.group(1)) == ref.num:
                m = near
            else:
                for cand in re.finditer(rb"(?<!\d)" + str(ref.num).encode() + rb"[\x00\t\n\x0c\r ]+" +
                                        str(ref.gen).encode() + rb"[\x00\t\n\x0c\r ]+obj\b", data):
                    m = cand
                if not m:
                    raise PdfError("object %d not found" % ref.num)
        val, p = self.parser.obj(m.end())
        k, tok, p2 = self.parser.token(p)
        if isinstance(val, dict) and k == 5 and tok == b"stream":
            start = p2
            if data[start:start + 2] == b"\r\n":
                start += 2
            elif data[start:start + 1] in (b"\n", b"\r"):
                start += 1
            length = val.get("Length")
            if isinstance(length, Ref):
                length = self.resolve(length) if length.num != ref.num else None
            end = None
            if isinstance(length, int) and length >= 0:
                end = start + length
                tail = data[end:end + 32].lstrip(_WS)
                if not tail.startswith(b"endstream"):
                    end = None
            if end is None:
                e = data.find(b"endstream", start)
                end = e if e >= 0 else len(data)
                while end > start and data[end - 1] in b"\r\n":
                    end -= 1
            raw = data[start:end]
            if decrypt and self.security and val.get("Type") != "XRef":
                raw = self.security.decrypt(raw, ref, "stream")
                if self.security.stm is not None:
                    filters = val.get("Filter")
                    if isinstance(filters, list) and filters and filters[0] == "Crypt":
                        val = dict(val)
            return Stream(val, raw, ref)
        if decrypt and self.security and not (self.enc_ref and ref == self.enc_ref):
            val = self._decrypt_strings(val, ref)
        return val

    def _decrypt_strings(self, v, ref):
        if isinstance(v, bytes):
            return self.security.decrypt(v, ref, "string")
        if isinstance(v, list):
            return [self._decrypt_strings(x, ref) for x in v]
        if isinstance(v, dict):
            return {k: self._decrypt_strings(x, ref) for k, x in v.items()}
        return v

    def _objstm_index(self, stm):
        data = self.stream_data(stm)
        n = self.resolve(stm.get("N")) or 0
        first = self.resolve(stm.get("First")) or 0
        nums = re.findall(rb"\d+", data[:first])
        pairs = [(int(nums[i]), int(nums[i + 1])) for i in range(0, min(len(nums) - 1, 2 * n), 2)]
        return pairs

    def _from_objstm(self, stm, num, idx):
        key = ("objstm", stm.ref)
        parsed = self.cache.get(key)
        if parsed is None:
            data = self.stream_data(stm)
            first = self.resolve(stm.get("First")) or 0
            parsed = (data, first, self._objstm_index(stm), _Parser(data))
            self.cache[key] = parsed
        data, first, pairs, parser = parsed
        if idx < len(pairs) and pairs[idx][0] == num:
            off = pairs[idx][1]
        else:
            off = next((o for n2, o in pairs if n2 == num), None)
            if off is None:
                return None
        val, _ = parser.obj(first + off)
        return val

    # ---------------------------------------------------------------- streams
    def stream_data(self, stm):
        if not isinstance(stm, Stream):
            return b""
        if stm.data is None:
            try:
                stm.data = self._decode(stm)
            except (PdfError, ValueError, TypeError, IndexError, zlib.error):
                stm.data = b""
        return stm.data

    def _decode(self, stm, crypt=True):
        data = stm.raw
        filters = self.resolve(stm.get("Filter"))
        parms = self.resolve(stm.get("DecodeParms"))
        if filters is None:
            return data
        if not isinstance(filters, list):
            filters, parms = [filters], [parms]
        elif not isinstance(parms, list):
            parms = [parms] * len(filters)
        for i, f in enumerate(filters):
            f = self.resolve(f)
            p = self.resolve(parms[i]) if i < len(parms) else None
            p = {k: self.resolve(v) for k, v in p.items()} if isinstance(p, dict) else {}
            if f in ("FlateDecode", "Fl"):
                data = _predict(_flate(data), p)
            elif f in ("LZWDecode", "LZW"):
                data = _predict(_lzw(data, p.get("EarlyChange", 1)), p)
            elif f in ("ASCII85Decode", "A85"):
                data = _a85(data)
            elif f in ("ASCIIHexDecode", "AHx"):
                data = _ahex(data)
            elif f in ("RunLengthDecode", "RL"):
                data = _runlength(data)
            elif f == "Crypt":
                continue
            else:
                return data            # image codecs (DCT, JPX, CCITT, JBIG2): not needed for text
        return data

    # ---------------------------------------------------------------- pages / outline
    def _load_pages(self):
        out = []
        self.page_index = {}
        root_pages = self.root.get("Pages") if isinstance(self.root, dict) else None
        seen = set()

        def walk(node_ref, inherited, depth):
            node = self.resolve(node_ref)
            if not isinstance(node, dict) or depth > 64:
                return
            key = node_ref if isinstance(node_ref, Ref) else id(node)
            if key in seen:
                return
            seen.add(key)
            inh = dict(inherited)
            for k in ("Resources", "MediaBox", "CropBox", "Rotate"):
                if k in node:
                    inh[k] = node[k]
            kids = self.resolve(node.get("Kids"))
            if node.get("Type") == "Pages" or (isinstance(kids, list) and node.get("Type") != "Page"):
                for kid in kids if isinstance(kids, list) else []:
                    walk(kid, inh, depth + 1)
            else:
                pd = dict(node)
                for k, v in inh.items():
                    pd.setdefault(k, v)
                if isinstance(node_ref, Ref):
                    self.page_index[node_ref] = len(out)
                out.append(Page(self, pd, len(out)))
        walk(root_pages, {}, 0)
        return out

    @property
    def toc(self):
        """[(level, title, page_number)] from the document outline; page is -1 when unknown."""
        out = []
        outlines = self.resolve(self.root.get("Outlines"))
        if not isinstance(outlines, dict):
            return out
        seen = set()

        def dest_page(item):
            d = self.resolve(item.get("Dest"))
            if d is None:
                a = self.resolve(item.get("A"))
                if isinstance(a, dict) and self.resolve(a.get("S")) == "GoTo":
                    d = self.resolve(a.get("D"))
            if isinstance(d, (bytes, Name)):
                d = self._named_dest(d)
            if isinstance(d, dict):
                d = self.resolve(d.get("D"))
            if isinstance(d, list) and d:
                if isinstance(d[0], Ref) and d[0] in self.page_index:
                    return self.page_index[d[0]] + 1
                if isinstance(d[0], int):
                    return d[0] + 1
            return -1

        def walk(ref, level):
            count = 0
            while ref is not None and count < 100000:
                key = ref if isinstance(ref, Ref) else None
                if key in seen:
                    return
                if key:
                    seen.add(key)
                item = self.resolve(ref)
                if not isinstance(item, dict):
                    return
                title = _text_string(self.resolve(item.get("Title"))).strip()
                out.append((level, title, dest_page(item)))
                if item.get("First") is not None:
                    walk(item.get("First"), level + 1)
                ref = item.get("Next")
                count += 1
        walk(outlines.get("First"), 1)
        return out

    def _named_dest(self, name):
        if not hasattr(self, "_dests"):
            self._dests = {}
            names = self.resolve(self.root.get("Names"))
            tree = self.resolve(names.get("Dests")) if isinstance(names, dict) else None
            stack = [tree] if isinstance(tree, dict) else []
            guard = 0
            while stack and guard < 100000:
                guard += 1
                node = stack.pop()
                arr = self.resolve(node.get("Names"))
                if isinstance(arr, list):
                    for i in range(0, len(arr) - 1, 2):
                        k = self.resolve(arr[i])
                        self._dests[bytes(k) if isinstance(k, bytes) else str(k).encode("latin-1", "replace")] = arr[i + 1]
                for kid in self.resolve(node.get("Kids")) or []:
                    kid = self.resolve(kid)
                    if isinstance(kid, dict):
                        stack.append(kid)
            old = self.resolve(self.root.get("Dests"))
            if isinstance(old, dict):
                for k, v in old.items():
                    self._dests.setdefault(k.encode("latin-1", "replace"), v)
        key = bytes(name) if isinstance(name, bytes) else str(name).encode("latin-1", "replace")
        return self.resolve(self._dests.get(key))

    def __len__(self):
        return len(self.pages)
