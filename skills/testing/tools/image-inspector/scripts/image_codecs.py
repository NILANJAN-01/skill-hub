"""Image decoders and helpers in pure Python (standard library only), used by inspect_image.py.

    decode_jpeg(blob) -> (width, height, mode, pixels, info)     baseline and progressive JPEG
    decode_gif(blob)  -> (width, height, mode, pixels, info)     first frame, frame count, transparency
    decode_tiff(blob) -> (width, height, mode, pixels, info)     strips/tiles, none/LZW/Deflate/PackBits
    decode_pnm(blob)  -> (width, height, mode, pixels, info)     PBM/PGM/PPM, ASCII and binary
    parse_exif(tiff_bytes) -> {"ifd0": {...}, "exif": {...}, "gps": {...}}
    orient(w, h, channels, pixels, orientation) -> (w, h, pixels)   apply an EXIF orientation
    encode_png(w, h, mode, pixels) -> bytes

`mode` is "L", "LA", "RGB" or "RGBA" with 8 bits per channel. The JPEG decoder follows libjpeg(-turbo)'s
default path - the accurate integer IDCT ("islow"), fancy (triangle) upsampling for 2x1, 1x2 and 2x2 chroma
and its fixed-point YCbCr->RGB tables - so its pixels match what Pillow decodes.

Raises CodecError for files it cannot decode (arithmetic-coded or lossless JPEG, JPEG-in-TIFF, ...);
the caller then falls back to another decoder.
"""
from __future__ import annotations

import re
import struct
import zlib
from array import array


class CodecError(Exception):
    """The file is damaged, or uses a feature these decoders do not support."""


# =========================================================================== JPEG

ZIGZAG = [0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5, 12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6,
          7, 14, 21, 28, 35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51, 58, 59, 52, 45, 38, 31,
          39, 46, 53, 60, 61, 54, 47, 55, 62, 63] + [63] * 16          # extra entries guard corrupt data
LOOK = 9


def _huff_table(counts, symbols):
    """Lookup table for the first LOOK bits plus the slow path (maxcode/valoffset) for longer codes."""
    look = [-1] * (1 << LOOK)
    maxcode = [-1] * 18
    valoff = [0] * 18
    code = k = 0
    for length in range(1, 17):
        n = counts[length - 1]
        if n:
            valoff[length] = k - code
            for _ in range(n):
                if length <= LOOK:
                    shift = LOOK - length
                    for fill in range(1 << shift):
                        look[(code << shift) | fill] = (length << 8) | symbols[k]
                code += 1
                k += 1
            maxcode[length] = code - 1
        code <<= 1
    maxcode[17] = 0x7FFFFFFF
    return look, maxcode, valoff, symbols


class _Bits:
    """Bit reader over one entropy-coded interval (byte stuffing already removed)."""
    __slots__ = ("d", "p", "n", "acc", "nb")

    def __init__(self, data):
        self.d, self.p, self.n, self.acc, self.nb = data, 0, len(data), 0, 0

    def fill(self):
        acc, nb, p, d, n = self.acc & ((1 << self.nb) - 1), self.nb, self.p, self.d, self.n
        while nb < 25:
            acc = (acc << 8) | (d[p] if p < n else 0)          # past the end: zeros, like libjpeg
            p += 1
            nb += 8
        self.acc, self.nb, self.p = acc, nb, p

    def huff(self, tab):
        if self.nb < 16:
            self.fill()
        look, maxcode, valoff, syms = tab
        e = look[(self.acc >> (self.nb - LOOK)) & ((1 << LOOK) - 1)]
        if e >= 0:
            self.nb -= e >> 8
            return e & 255
        for length in range(LOOK + 1, 17):
            code = (self.acc >> (self.nb - length)) & ((1 << length) - 1)
            if code <= maxcode[length]:
                self.nb -= length
                i = code + valoff[length]
                return syms[i] if 0 <= i < len(syms) else 0
        self.nb -= 16                                         # corrupt data: skip
        return 0

    def bits(self, s):
        if self.nb < s:
            self.fill()
        self.nb -= s
        return (self.acc >> self.nb) & ((1 << s) - 1)

    def extend(self, s):
        if not s:
            return 0
        if self.nb < s:
            self.fill()
        self.nb -= s
        v = (self.acc >> self.nb) & ((1 << s) - 1)
        return v if v >= (1 << (s - 1)) else v - (1 << s) + 1


# libjpeg jidctint.c constants (CONST_BITS = 13, PASS1_BITS = 2)
F0298, F0390, F0541, F0765, F0899, F1175, F1501 = 2446, 3196, 4433, 6270, 7373, 9633, 12299
F1847, F1961, F2053, F2562, F3072 = 15137, 16069, 16819, 20995, 25172


def _idct_islow(c, q, out, o, stride):
    """libjpeg's jpeg_idct_islow: dequantise 64 coefficients c (natural order), write 8x8 samples."""
    ws = [0] * 64
    for col in range(8):
        if not (c[col + 8] or c[col + 16] or c[col + 24] or c[col + 32] or c[col + 40] or c[col + 48]
                or c[col + 56]):
            dc = (c[col] * q[col]) << 2
            for r in range(col, 64, 8):
                ws[r] = dc
            continue
        z2, z3 = c[col + 16] * q[col + 16], c[col + 48] * q[col + 48]
        z1 = (z2 + z3) * F0541
        tmp2, tmp3 = z1 - z3 * F1847, z1 + z2 * F0765
        z2, z3 = c[col] * q[col], c[col + 32] * q[col + 32]
        tmp0, tmp1 = (z2 + z3) << 13, (z2 - z3) << 13
        t10, t13, t11, t12 = tmp0 + tmp3, tmp0 - tmp3, tmp1 + tmp2, tmp1 - tmp2
        tmp0, tmp1 = c[col + 56] * q[col + 56], c[col + 40] * q[col + 40]
        tmp2, tmp3 = c[col + 24] * q[col + 24], c[col + 8] * q[col + 8]
        z1, z2, z3, z4 = tmp0 + tmp3, tmp1 + tmp2, tmp0 + tmp2, tmp1 + tmp3
        z5 = (z3 + z4) * F1175
        tmp0, tmp1, tmp2, tmp3 = tmp0 * F0298, tmp1 * F2053, tmp2 * F3072, tmp3 * F1501
        z1, z2, z3, z4 = -z1 * F0899, -z2 * F2562, -z3 * F1961 + z5, -z4 * F0390 + z5
        tmp0 += z1 + z3
        tmp1 += z2 + z4
        tmp2 += z2 + z3
        tmp3 += z1 + z4
        ws[col] = (t10 + tmp3 + 1024) >> 11
        ws[col + 56] = (t10 - tmp3 + 1024) >> 11
        ws[col + 8] = (t11 + tmp2 + 1024) >> 11
        ws[col + 48] = (t11 - tmp2 + 1024) >> 11
        ws[col + 16] = (t12 + tmp1 + 1024) >> 11
        ws[col + 40] = (t12 - tmp1 + 1024) >> 11
        ws[col + 24] = (t13 + tmp0 + 1024) >> 11
        ws[col + 32] = (t13 - tmp0 + 1024) >> 11
    lim = _LIMIT
    for row in range(0, 64, 8):
        w0 = ws[row]
        if not (ws[row + 1] or ws[row + 2] or ws[row + 3] or ws[row + 4] or ws[row + 5] or ws[row + 6]
                or ws[row + 7]):
            v = lim[((w0 + 16) >> 5) & 1023]
            out[o:o + 8] = bytes((v,)) * 8
            o += stride
            continue
        z2, z3 = ws[row + 2], ws[row + 6]
        z1 = (z2 + z3) * F0541
        tmp2, tmp3 = z1 - z3 * F1847, z1 + z2 * F0765
        tmp0, tmp1 = (w0 + ws[row + 4]) << 13, (w0 - ws[row + 4]) << 13
        t10, t13, t11, t12 = tmp0 + tmp3, tmp0 - tmp3, tmp1 + tmp2, tmp1 - tmp2
        tmp0, tmp1, tmp2, tmp3 = ws[row + 7], ws[row + 5], ws[row + 3], ws[row + 1]
        z1, z2, z3, z4 = tmp0 + tmp3, tmp1 + tmp2, tmp0 + tmp2, tmp1 + tmp3
        z5 = (z3 + z4) * F1175
        tmp0, tmp1, tmp2, tmp3 = tmp0 * F0298, tmp1 * F2053, tmp2 * F3072, tmp3 * F1501
        z1, z2, z3, z4 = -z1 * F0899, -z2 * F2562, -z3 * F1961 + z5, -z4 * F0390 + z5
        tmp0 += z1 + z3
        tmp1 += z2 + z4
        tmp2 += z2 + z3
        tmp3 += z1 + z4
        out[o:o + 8] = bytes((lim[((t10 + tmp3 + 131072) >> 18) & 1023], lim[((t11 + tmp2 + 131072) >> 18) & 1023],
                              lim[((t12 + tmp1 + 131072) >> 18) & 1023], lim[((t13 + tmp0 + 131072) >> 18) & 1023],
                              lim[((t13 - tmp0 + 131072) >> 18) & 1023], lim[((t12 - tmp1 + 131072) >> 18) & 1023],
                              lim[((t11 - tmp2 + 131072) >> 18) & 1023], lim[((t10 - tmp3 + 131072) >> 18) & 1023]))
        o += stride


# libjpeg's post-IDCT range limit, indexed by (value & 1023): v + 128 clamped to 0..255
_LIMIT = list(range(128, 256)) + [255] * 384 + [0] * 384 + list(range(128))
_MARKER = re.compile(rb"\xff[^\x00\xd0-\xd7]")
_RST = re.compile(rb"\xff[\xd0-\xd7]")


def _segments(blob):
    """Yield (marker, payload_start, payload_end, scan_end) for each JPEG segment; scan_end is the end of
    the entropy-coded data after an SOS segment (None for other segments)."""
    i, n = 2, len(blob)
    while i < n:
        if blob[i] != 0xFF:
            i += 1
            continue
        while i < n and blob[i] == 0xFF:
            i += 1
        if i >= n:
            return
        m = blob[i]
        i += 1
        if m == 0xD9:
            return
        if m in (0x00, 0x01) or 0xD0 <= m <= 0xD7:
            continue
        if i + 2 > n:
            return
        ln = (blob[i] << 8) | blob[i + 1]
        end = min(n, i + ln)
        if m == 0xDA:
            mm = _MARKER.search(blob, end)
            scan_end = mm.start() if mm else n
            yield m, i + 2, end, scan_end
            i = scan_end
        else:
            yield m, i + 2, end, None
            i += ln


def decode_jpeg(blob):
    qt = {}
    dc_tabs, ac_tabs = {}, {}
    frame = None
    comps = []
    restart = 0
    adobe = None
    jfif = None
    exif = None
    progressive = False
    for m, a, b, scan_end in _segments(blob):
        seg = blob[a:b]
        if m == 0xDB:
            k = 0
            while k < len(seg):
                pq, tq = seg[k] >> 4, seg[k] & 15
                k += 1
                if pq:
                    vals = struct.unpack(">64H", seg[k:k + 128])
                    k += 128
                else:
                    vals = seg[k:k + 64]
                    k += 64
                t = [0] * 64
                for z, v in enumerate(vals):
                    t[ZIGZAG[z]] = v
                qt[tq] = t
        elif m == 0xC4:
            k = 0
            while k + 17 <= len(seg):
                tc, th = seg[k] >> 4, seg[k] & 15
                counts = list(seg[k + 1:k + 17])
                total = sum(counts)
                syms = list(seg[k + 17:k + 17 + total])
                k += 17 + total
                (ac_tabs if tc else dc_tabs)[th] = _huff_table(counts, syms)
        elif m in (0xC0, 0xC1, 0xC2):
            if seg[0] != 8:
                raise CodecError("%d-bit JPEG samples are not supported" % seg[0])
            progressive = m == 0xC2
            h, w, nc = struct.unpack(">HHB", seg[1:6])
            if not w or not h:
                raise CodecError("JPEG with a zero size (DNL marker) is not supported")
            comps = []
            for c in range(nc):
                cid, hv, tq = seg[6 + 3 * c:9 + 3 * c]
                comps.append({"id": cid, "h": hv >> 4 or 1, "v": hv & 15 or 1, "tq": tq})
            hmax, vmax = max(c["h"] for c in comps), max(c["v"] for c in comps)
            mcux, mcuy = -(-w // (8 * hmax)), -(-h // (8 * vmax))
            for c in comps:
                c["bw"], c["bh"] = mcux * c["h"], mcuy * c["v"]                  # padded block grid
                c["cw"], c["ch"] = -(-w * c["h"] // hmax), -(-h * c["v"] // vmax)   # real samples
                c["coef"] = array("i", bytes(4 * 64 * c["bw"] * c["bh"]))
            frame = (w, h, hmax, vmax, mcux, mcuy)
        elif 0xC3 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
            raise CodecError("this JPEG uses %s coding, which is not supported"
                             % ("arithmetic" if m >= 0xC9 else "lossless or hierarchical"))
        elif m == 0xDD:
            restart = (seg[0] << 8) | seg[1]
        elif m == 0xEE and seg[:5] == b"Adobe":
            adobe = seg[11] if len(seg) > 11 else 0
        elif m == 0xE0 and seg[:5] == b"JFIF\x00":
            jfif = (seg[7], (seg[8] << 8) | seg[9], (seg[10] << 8) | seg[11])
        elif m == 0xE1 and seg[:6] == b"Exif\x00\x00" and exif is None:
            exif = seg[6:]
        elif m == 0xDA:
            if frame is None:
                raise CodecError("JPEG scan before the frame header")
            ns = seg[0]
            sc = []
            for k in range(ns):
                cid, t = seg[1 + 2 * k], seg[2 + 2 * k]
                c = next((c for c in comps if c["id"] == cid), None)
                if c is None:
                    raise CodecError("JPEG scan refers to an unknown component")
                sc.append((c, t >> 4, t & 15))
            ss, se, ahl = seg[1 + 2 * ns], seg[2 + 2 * ns], seg[3 + 2 * ns]
            _decode_scan(blob[b:scan_end], frame, sc, dc_tabs, ac_tabs, restart, progressive, ss, se,
                         ahl >> 4, ahl & 15)
    if frame is None:
        raise CodecError("JPEG without a frame header (truncated?)")
    w, h, hmax, vmax, mcux, mcuy = frame
    for c in comps:
        if c["tq"] not in qt:
            raise CodecError("JPEG quantisation table missing")
        c["plane"] = _idct_component(c, qt[c["tq"]])
    planes = [_upsample(c, w, h, hmax, vmax) for c in comps]
    info = {"progressive": progressive}
    if jfif and jfif[0] in (1, 2) and jfif[1] and jfif[2]:
        f = 1.0 if jfif[0] == 1 else 2.54
        info["dpi"] = (jfif[1] * f, jfif[2] * f)
    if exif:
        info["exif_raw"] = exif
    nc = len(comps)
    if nc == 1:
        return w, h, "L", planes[0], dict(info, mode="L")
    if nc == 3:
        ids = tuple(c["id"] for c in comps)
        if adobe == 0 or ids == (82, 71, 66):
            return w, h, "RGB", _interleave(planes), dict(info, mode="RGB")
        return w, h, "RGB", _ycc_to_rgb(*planes), dict(info, mode="RGB")
    if nc == 4:
        if adobe == 2:
            r, g, b_ = _split(_ycc_to_rgb(*planes[:3]))
            planes = [bytes(255 - v for v in r), bytes(255 - v for v in g), bytes(255 - v for v in b_), planes[3]]
        if adobe is not None:
            planes = [bytes(255 - v for v in p) for p in planes]
        return w, h, "RGB", _cmyk_to_rgb(*planes), dict(info, mode="CMYK")
    raise CodecError("JPEG with %d components is not supported" % nc)


def _decode_scan(data, frame, sc, dc_tabs, ac_tabs, restart, progressive, ss, se, ah, al):
    w, h, hmax, vmax, mcux, mcuy = frame
    intervals = [part.replace(b"\xff\x00", b"\xff") for part in _RST.split(data)] if restart else \
        [data.replace(b"\xff\x00", b"\xff")]
    single = len(sc) == 1
    if single:
        c = sc[0][0]
        nbx, nby = -(-c["cw"] // 8), -(-c["ch"] // 8)
        units = [(c, by * c["bw"] + bx) for by in range(nby) for bx in range(nbx)]
        mcus = [[u] for u in units]
        tabs = [sc[0]]
    else:
        mcus = []
        for my in range(mcuy):
            for mx in range(mcux):
                blocks = []
                for c, _, _ in sc:
                    for v in range(c["v"]):
                        for hh in range(c["h"]):
                            blocks.append((c, (my * c["v"] + v) * c["bw"] + mx * c["h"] + hh))
                mcus.append(blocks)
        tabs = sc
    tabmap = {id(c): (dc_tabs.get(td), ac_tabs.get(ta)) for c, td, ta in tabs}
    per = restart or len(mcus)
    eobrun = [0]
    for iv, start in enumerate(range(0, len(mcus), per)):
        bits = _Bits(intervals[iv] if iv < len(intervals) else b"")
        pred = {}
        eobrun[0] = 0
        for blocks in mcus[start:start + per]:
            for c, bi in blocks:
                dct, act = tabmap[id(c)]
                coef = c["coef"]
                base = bi * 64
                if not progressive:
                    _baseline_block(bits, dct, act, coef, base, pred, c)
                elif ss == 0:
                    if ah == 0:
                        s = bits.huff(dct)
                        p = pred.get(id(c), 0) + bits.extend(s)
                        pred[id(c)] = p
                        coef[base] = p * (1 << al)
                    elif bits.bits(1):
                        coef[base] |= 1 << al
                elif ah == 0:
                    _ac_first(bits, act, coef, base, ss, se, al, eobrun)
                else:
                    _ac_refine(bits, act, coef, base, ss, se, al, eobrun)


def _baseline_block(bits, dct, act, coef, base, pred, c):
    if dct is None or act is None:
        raise CodecError("JPEG Huffman table missing")
    s = bits.huff(dct)
    p = pred.get(id(c), 0) + bits.extend(s)
    pred[id(c)] = p
    coef[base] = p
    k = 1
    huff, extend, zz = bits.huff, bits.extend, ZIGZAG
    while k < 64:
        rs = huff(act)
        r, s = rs >> 4, rs & 15
        if s:
            k += r
            coef[base + zz[k]] = extend(s)
            k += 1
        elif r == 15:
            k += 16
        else:
            break


def _ac_first(bits, act, coef, base, ss, se, al, eobrun):
    if eobrun[0] > 0:
        eobrun[0] -= 1
        return
    k = ss
    zz = ZIGZAG
    while k <= se:
        rs = bits.huff(act)
        r, s = rs >> 4, rs & 15
        if s:
            k += r
            coef[base + zz[k]] = bits.extend(s) * (1 << al)
            k += 1
        elif r == 15:
            k += 16
        else:
            run = 1 << r
            if r:
                run += bits.bits(r)
            eobrun[0] = run - 1
            break


def _ac_refine(bits, act, coef, base, ss, se, al, eobrun):
    p1, m1 = 1 << al, -1 << al
    zz = ZIGZAG
    k = ss
    if eobrun[0] == 0:
        while k <= se:
            rs = bits.huff(act)
            r, s = rs >> 4, rs & 15
            if s:
                s = p1 if bits.bits(1) else m1
            elif r != 15:
                run = 1 << r
                if r:
                    run += bits.bits(r)
                eobrun[0] = run
                break
            while k <= se:
                z = base + zz[k]
                v = coef[z]
                if v:
                    if bits.bits(1) and not (v & p1):
                        coef[z] = v + (p1 if v >= 0 else m1)
                else:
                    if r == 0:
                        break
                    r -= 1
                k += 1
            if s and k <= 63:
                coef[base + zz[k]] = s
            k += 1
    if eobrun[0] > 0:
        while k <= se:
            z = base + zz[k]
            v = coef[z]
            if v and bits.bits(1) and not (v & p1):
                coef[z] = v + (p1 if v >= 0 else m1)
            k += 1
        eobrun[0] -= 1


def _idct_component(c, q):
    bw, bh = c["bw"], c["bh"]
    stride = bw * 8
    plane = bytearray(stride * bh * 8)
    coef = c["coef"]
    lim = _LIMIT
    for by in range(bh):
        for bx in range(bw):
            base = (by * bw + bx) * 64
            blk = coef[base:base + 64]
            o = by * 8 * stride + bx * 8
            if not any(blk[1:]):                                    # flat block: one value
                v = bytes((lim[((((blk[0] * q[0]) << 2) + 16) >> 5) & 1023],)) * 8
                for r in range(8):
                    plane[o:o + 8] = v
                    o += stride
                continue
            _idct_islow(blk, q, plane, o, stride)
    c["stride"] = stride
    return plane


def _upsample(c, w, h, hmax, vmax):
    """Component plane -> w*h samples, with libjpeg's upsampling rules."""
    stride, cw, ch = c["stride"], c["cw"], c["ch"]
    src = c["plane"]
    rows = [src[y * stride:y * stride + cw] for y in range(ch)]
    fh, fv = hmax // c["h"], vmax // c["v"]
    if hmax % c["h"] or vmax % c["v"]:
        raise CodecError("fractional JPEG sampling factors are not supported")
    if fh == 1 and fv == 1:
        return b"".join(r[:w] for r in rows[:h])
    if fh == 2 and fv == 1 and cw > 2:
        out = [_h2v1(r) for r in rows]
    elif fh == 1 and fv == 2:
        out = []
        for y in range(ch):
            r0 = rows[y]
            up, down = rows[max(0, y - 1)], rows[min(ch - 1, y + 1)]
            out.append(bytes(((3 * a + b + 1) >> 2) for a, b in zip(r0, up)))
            out.append(bytes(((3 * a + b + 2) >> 2) for a, b in zip(r0, down)))
    elif fh == 2 and fv == 2 and cw > 2:
        out = []
        for y in range(ch):
            r0 = rows[y]
            for nb in (rows[max(0, y - 1)], rows[min(ch - 1, y + 1)]):
                cs = [3 * a + b for a, b in zip(r0, nb)]
                line = bytearray(2 * cw)
                line[0] = (cs[0] * 4 + 8) >> 4
                line[1] = (cs[0] * 3 + cs[1] + 7) >> 4
                line[2:2 * cw - 2:2] = bytes((3 * t + l + 8) >> 4 for t, l in zip(cs[1:-1], cs[:-2]))
                line[3:2 * cw - 2:2] = bytes((3 * t + n + 7) >> 4 for t, n in zip(cs[1:-1], cs[2:]))
                line[2 * cw - 2] = (cs[-1] * 3 + cs[-2] + 8) >> 4
                line[2 * cw - 1] = (cs[-1] * 4 + 7) >> 4
                out.append(bytes(line))
    else:                                                            # plain replication
        out = []
        for r in rows:
            line = bytes(v for v in r for _ in range(fh))
            out.extend([line] * fv)
    return b"".join(r[:w] for r in out[:h])


def _h2v1(r):
    n = len(r)
    line = bytearray(2 * n)
    line[0] = r[0]
    line[1] = (r[0] * 3 + r[1] + 2) >> 2
    line[2:2 * n - 2:2] = bytes((3 * t + l + 1) >> 2 for t, l in zip(r[1:-1], r[:-2]))
    line[3:2 * n - 2:2] = bytes((3 * t + nx + 2) >> 2 for t, nx in zip(r[1:-1], r[2:]))
    line[2 * n - 2] = (r[-1] * 3 + r[-2] + 1) >> 2
    line[2 * n - 1] = r[-1]
    return bytes(line)


def _fix(x):
    return int(x * 65536 + 0.5)


_CR_R = [(_fix(1.40200) * (i - 128) + 32768) >> 16 for i in range(256)]
_CB_B = [(_fix(1.77200) * (i - 128) + 32768) >> 16 for i in range(256)]
_CR_G = [-_fix(0.71414) * (i - 128) for i in range(256)]
_CB_G = [-_fix(0.34414) * (i - 128) + 32768 for i in range(256)]
_CLAMP = bytes([0] * 256 + list(range(256)) + [255] * 256)          # index v + 256


def _ycc_to_rgb(y, cb, cr):
    cl = _CLAMP
    r = bytes(cl[a + _CR_R[c] + 256] for a, c in zip(y, cr))
    g = bytes(cl[a + ((_CB_G[b] + _CR_G[c]) >> 16) + 256] for a, b, c in zip(y, cb, cr))
    b_ = bytes(cl[a + _CB_B[b] + 256] for a, b in zip(y, cb))
    return _interleave((r, g, b_))


def _cmyk_to_rgb(c, m, y, k):
    """Pillow's CMYK -> RGB conversion."""
    def ch(x, kk):
        nk = 255 - kk
        t = x * nk + 128
        return max(0, nk - (((t >> 8) + t) >> 8))
    return _interleave((bytes(ch(a, kk) for a, kk in zip(c, k)), bytes(ch(a, kk) for a, kk in zip(m, k)),
                        bytes(ch(a, kk) for a, kk in zip(y, k))))


def _interleave(planes):
    n = len(planes)
    out = bytearray(len(planes[0]) * n)
    for i, p in enumerate(planes):
        out[i::n] = p
    return out


def _split(data, n=3):
    return [bytes(data[i::n]) for i in range(n)]


# =========================================================================== GIF

def _gif_lzw(data, mincode, npix):
    clear, end = 1 << mincode, (1 << mincode) + 1
    out = bytearray()
    table = [bytes((i,)) for i in range(clear)] + [b"", b""]
    size = mincode + 1
    prev = None
    acc = nb = 0
    for byte in data:
        acc |= byte << nb
        nb += 8
        while nb >= size:
            code = acc & ((1 << size) - 1)
            acc >>= size
            nb -= size
            if code == clear:
                table = table[:end + 1]
                size, prev = mincode + 1, None
                continue
            if code == end:
                return bytes(out[:npix])
            if prev is None:
                entry = table[code] if code < len(table) else b"\x00"
            elif code < len(table):
                entry = table[code]
                if len(table) < 4096:
                    table.append(prev + entry[:1])
            else:
                entry = prev + prev[:1]
                if len(table) < 4096:
                    table.append(entry)
            out += entry
            prev = entry
            if len(table) == (1 << size) and size < 12:
                size += 1
            if len(out) >= npix:
                return bytes(out[:npix])
    return bytes(out[:npix]) + bytes(max(0, npix - len(out)))


def decode_gif(blob):
    if len(blob) < 13:
        raise CodecError("GIF is truncated")
    w, h, flags, bg = struct.unpack("<HHBB", blob[6:12])
    pos = 13
    gct = None
    if flags & 0x80:
        n = 2 << (flags & 7)
        gct = blob[pos:pos + 3 * n]
        pos += 3 * n
    transparent, first, frames, pending = None, None, 0, None
    while pos < len(blob):
        b = blob[pos]
        if b == 0x21:
            label = blob[pos + 1] if pos + 1 < len(blob) else 0
            pos += 2
            if label == 0xF9 and pos + 5 <= len(blob) and blob[pos] >= 4:
                pending = blob[pos + 4] if blob[pos + 1] & 1 else None
            while pos < len(blob) and blob[pos]:
                pos += blob[pos] + 1
            pos += 1
        elif b == 0x2C:
            if pos + 10 > len(blob):
                break
            x, y, fw, fh, pk = struct.unpack("<HHHHB", blob[pos + 1:pos + 10])
            pos += 10
            lct = None
            if pk & 0x80:
                n = 2 << (pk & 7)
                lct = blob[pos:pos + 3 * n]
                pos += 3 * n
            mincode = blob[pos] if pos < len(blob) else 8
            pos += 1
            chunks = []
            while pos < len(blob) and blob[pos]:
                chunks.append(blob[pos + 1:pos + 1 + blob[pos]])
                pos += blob[pos] + 1
            pos += 1
            frames += 1
            if first is None:
                first = (x, y, fw, fh, bool(pk & 0x40), lct or gct, mincode, b"".join(chunks))
                transparent = pending
            pending = None
        else:
            break
    if first is None:
        raise CodecError("GIF has no image")
    x0, y0, fw, fh, interlaced, pal, mincode, data = first
    if not pal:
        pal = bytes(v for i in range(256) for v in (i, i, i))
    idx = _gif_lzw(data, min(max(mincode, 2), 11), fw * fh)
    if interlaced:
        order = list(range(0, fh, 8)) + list(range(4, fh, 8)) + list(range(2, fh, 4)) + list(range(1, fh, 2))
        rows = [None] * fh
        for k, r in enumerate(order):
            rows[r] = idx[k * fw:(k + 1) * fw]
        idx = b"".join(rows)
    ncol = len(pal) // 3
    gray = all(pal[3 * i] == pal[3 * i + 1] == pal[3 * i + 2] for i in range(ncol))
    alpha = transparent is not None
    mode = ("LA" if alpha else "L") if gray else ("RGBA" if alpha else "RGB")
    nch = len(mode)
    lut = []
    for i in range(256):
        rgb = tuple(pal[3 * i:3 * i + 3]) if i < ncol else (0, 0, 0)
        px = (rgb[0],) if gray else rgb
        lut.append(bytes(px + ((0 if i == transparent else 255,) if alpha else ())))
    fill = lut[transparent if alpha else (bg if bg < 256 else 0)]
    out = bytearray(fill * (w * h))
    for r in range(fh):
        yy = y0 + r
        if yy >= h:
            break
        line = b"".join(lut[v] for v in idx[r * fw:(r + 1) * fw])
        x1 = min(w, x0 + fw)
        if x1 > x0:
            out[(yy * w + x0) * nch:(yy * w + x1) * nch] = line[:(x1 - x0) * nch]
    return w, h, mode, out, {"frames": frames, "mode": "L" if gray else "P", "has_alpha": alpha}


# =========================================================================== TIFF / EXIF

_TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 13: 4, 16: 8}
_TYPE_FMT = {1: "B", 3: "H", 4: "I", 6: "b", 8: "h", 9: "i", 11: "f", 12: "d", 13: "I", 16: "Q"}


def _read_ifd(data, off, e):
    """{tag: value} for the IFD at off, plus the offset of the next IFD."""
    if off + 2 > len(data):
        raise CodecError("TIFF directory outside the file")
    n = struct.unpack(e + "H", data[off:off + 2])[0]
    out = {}
    for i in range(n):
        p = off + 2 + 12 * i
        if p + 12 > len(data):
            break
        tag, typ, count = struct.unpack(e + "HHI", data[p:p + 8])
        size = _TYPE_SIZE.get(typ)
        if size is None or count > 10_000_000:
            continue
        total = size * count
        vp = p + 8 if total <= 4 else struct.unpack(e + "I", data[p + 8:p + 12])[0]
        raw = data[vp:vp + total]
        if len(raw) < total:
            continue
        if typ == 2:
            val = raw.split(b"\x00", 1)[0].decode("utf-8", "replace")
        elif typ in (7,):
            val = raw
        elif typ in (5, 10):
            nums = struct.unpack(e + ("%d%s" % (2 * count, "I" if typ == 5 else "i")), raw)
            vals = [nums[2 * k] / nums[2 * k + 1] if nums[2 * k + 1] else float("nan") for k in range(count)]
            val = vals[0] if count == 1 else tuple(vals)
        else:
            vals = struct.unpack(e + "%d%s" % (count, _TYPE_FMT[typ]), raw)
            val = vals[0] if count == 1 else tuple(vals)
        out[tag] = val
    np_ = off + 2 + 12 * n
    nxt = struct.unpack(e + "I", data[np_:np_ + 4])[0] if np_ + 4 <= len(data) else 0
    return out, nxt


def _endian(data):
    if data[:2] == b"II":
        return "<"
    if data[:2] == b"MM":
        return ">"
    raise CodecError("not TIFF/EXIF data")


def parse_exif(data):
    """EXIF/TIFF bytes -> {"ifd0", "exif", "gps"} dicts of tag -> value (rationals as floats)."""
    e = _endian(data)
    ifd0, _ = _read_ifd(data, struct.unpack(e + "I", data[4:8])[0], e)
    res = {"ifd0": ifd0, "exif": {}, "gps": {}}
    for tag, key in ((0x8769, "exif"), (0x8825, "gps")):
        off = ifd0.get(tag)
        if isinstance(off, int) and 0 < off < len(data):
            try:
                res[key] = _read_ifd(data, off, e)[0]
            except (CodecError, struct.error):
                pass
    return res


def _lzw_tiff(data):
    out = bytearray()
    table = [bytes((i,)) for i in range(256)] + [b"", b""]
    bits, acc, nb, prev = 9, 0, 0, None
    for byte in data:
        acc = (acc << 8) | byte
        nb += 8
        while nb >= bits:
            nb -= bits
            code = (acc >> nb) & ((1 << bits) - 1)
            acc &= (1 << nb) - 1
            if code == 256:
                table, bits, prev = table[:258], 9, None
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
            n = len(table) + 1
            bits = 12 if n >= 2048 else 11 if n >= 1024 else 10 if n >= 512 else 9
    return bytes(out)


def _packbits(data):
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        c = data[i]
        if c < 128:
            out += data[i + 1:i + 2 + c]
            i += 2 + c
        elif c > 128:
            out += data[i + 1:i + 2] * (257 - c)
            i += 2
        else:
            i += 1
    return bytes(out)


def decode_tiff(blob):
    e = _endian(blob)
    if struct.unpack(e + "H", blob[2:4])[0] != 42:
        raise CodecError("BigTIFF is not supported")
    off = struct.unpack(e + "I", blob[4:8])[0]
    ifd, nxt = _read_ifd(blob, off, e)
    frames, seen = 1, {off}
    while nxt and nxt not in seen and frames < 10000:
        seen.add(nxt)
        try:
            nxt = _read_ifd(blob, nxt, e)[1]
        except (CodecError, struct.error):
            break
        frames += 1

    def arr(tag, default=None):
        v = ifd.get(tag, default)
        return list(v) if isinstance(v, tuple) else ([v] if v is not None else [])

    w, h = ifd.get(256), ifd.get(257)
    if not isinstance(w, int) or not isinstance(h, int) or not w or not h:
        raise CodecError("TIFF without a size")
    spp = ifd.get(277, 1)
    bps = arr(258, 1)[0]
    comp = ifd.get(259, 1)
    photo = ifd.get(262, 1)
    planar = ifd.get(284, 1)
    pred = ifd.get(317, 1)
    extra = arr(338)
    if ifd.get(339, 1) not in (1, 2) or (isinstance(ifd.get(339), tuple) and ifd[339][0] not in (1, 2)):
        raise CodecError("floating-point TIFF samples are not supported")
    if comp not in (1, 5, 8, 32946, 32773):
        raise CodecError("TIFF compression %s is not supported" % comp)
    if photo not in (0, 1, 2, 3, 5) or bps not in (1, 2, 4, 8, 16):
        raise CodecError("TIFF colour type %s with %s-bit samples is not supported" % (photo, bps))
    if 322 in ifd:
        tw, tl = ifd[322], ifd[323]
        offs, counts = arr(324), arr(325)
        tiles_x = -(-w // tw)
        pieces = [(offs[i], counts[i], (i % tiles_x) * tw, (i // tiles_x) * tl, tw, tl) for i in range(len(offs))]
    else:
        rps = min(ifd.get(278, h) or h, h)
        offs, counts = arr(273), arr(279)
        pieces = [(offs[i], counts[i] if i < len(counts) else len(blob), 0, i * rps, w, rps) for i in range(len(offs))]
    nplanes = spp if planar == 2 else 1
    sp = 1 if planar == 2 else spp
    row_bytes_full = (w * sp * bps + 7) // 8
    planes = [bytearray(row_bytes_full * h) for _ in range(nplanes)]
    per_plane = len(pieces) // nplanes if planar == 2 else len(pieces)
    for k, (o, cnt, px, py, pw, ph) in enumerate(pieces):
        plane = planes[k // per_plane] if planar == 2 else planes[0]
        raw = blob[o:o + cnt]
        if comp == 5:
            raw = _lzw_tiff(raw)
        elif comp in (8, 32946):
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                raw = zlib.decompressobj().decompress(raw)
        elif comp == 32773:
            raw = _packbits(raw)
        rb = (pw * sp * bps + 7) // 8
        for r in range(ph):
            yy = py + r
            if yy >= h:
                break
            line = bytearray(raw[r * rb:(r + 1) * rb])
            if len(line) < rb:
                line += bytes(rb - len(line))
            if pred == 2:
                _undo_predictor(line, sp, bps, e)
            if px == 0 and pw >= w:
                plane[yy * row_bytes_full:(yy + 1) * row_bytes_full] = line[:row_bytes_full]
            else:
                b0 = px * sp * bps // 8
                take = min(rb, row_bytes_full - b0)
                plane[yy * row_bytes_full + b0:yy * row_bytes_full + b0 + take] = line[:take]
    if planar == 2:
        data = _interleave([bytes(p) for p in planes])
    else:
        data = planes[0]
    samples = _tiff_samples(data, w * h * spp, bps, e, w * spp, row_bytes_full * (spp if planar == 2 else 1))
    info = {"frames": frames}
    xr, yr, unit = ifd.get(282), ifd.get(283), ifd.get(296, 2)
    if isinstance(xr, float) and isinstance(yr, float) and xr == xr and unit in (2, 3):
        f = 1.0 if unit == 2 else 2.54
        info["dpi"] = (xr * f, yr * f)
    has_alpha = bool(extra) and extra[0] in (1, 2)
    if photo in (0, 1):
        maxv = (1 << bps) - 1
        if bps == 16:
            vals = [v // 257 for v in samples]            # what Pillow's I;16 -> L conversion gives
        else:
            vals = [v * 255 // maxv for v in samples] if bps < 8 else samples
        if photo == 0:
            vals = [255 - v for v in vals]
        mode = "LA" if spp >= 2 and has_alpha else "L"
        n = 2 if mode == "LA" else 1
        out = bytearray(w * h * n)
        out[0::n] = bytes(vals[0::spp])
        if n == 2:
            out[1::2] = bytes(vals[1::spp])
        name = "1" if bps == 1 else ("I;16" if bps == 16 else mode)
        return w, h, mode, out, dict(info, mode=name, has_alpha=n == 2)
    if bps == 16:
        samples = [v >> 8 for v in samples]
    if photo == 3:
        cmap = arr(320)
        n = 1 << bps
        if len(cmap) < 3 * n:
            raise CodecError("palette TIFF without a colour map")
        pal = [bytes((cmap[i] >> 8, cmap[n + i] >> 8, cmap[2 * n + i] >> 8)) for i in range(n)]
        out = b"".join(pal[v] if v < n else b"\x00\x00\x00" for v in samples[0::spp])
        return w, h, "RGB", bytearray(out), dict(info, mode="P", has_alpha=False)
    if photo == 2:
        mode = "RGBA" if spp >= 4 and has_alpha else "RGB"
        n = len(mode)
        out = bytearray(w * h * n)
        for i in range(n):
            out[i::n] = bytes(samples[i::spp])
        return w, h, mode, out, dict(info, mode=mode, has_alpha=n == 4)
    if spp < 4:
        raise CodecError("CMYK TIFF with fewer than 4 samples")
    planes4 = [bytes(samples[i::spp]) for i in range(4)]
    return w, h, "RGB", _cmyk_to_rgb(*planes4), dict(info, mode="CMYK", has_alpha=False)


def _undo_predictor(line, sp, bps, e):
    if bps == 8:
        for i in range(sp, len(line)):
            line[i] = (line[i] + line[i - sp]) & 255
    elif bps == 16:
        vals = list(struct.unpack(e + "%dH" % (len(line) // 2), bytes(line[:len(line) // 2 * 2])))
        for i in range(sp, len(vals)):
            vals[i] = (vals[i] + vals[i - sp]) & 0xFFFF
        line[:len(vals) * 2] = struct.pack(e + "%dH" % len(vals), *vals)


def _tiff_samples(data, total, bps, e, per_row, row_bytes):
    if bps == 8:
        return data[:total]
    if bps == 16:
        n = min(total, len(data) // 2)
        return list(struct.unpack(e + "%dH" % n, bytes(data[:n * 2])))
    out = []
    mask = (1 << bps) - 1
    nrows = len(data) // row_bytes if row_bytes else 0
    for r in range(nrows):
        row = data[r * row_bytes:(r + 1) * row_bytes]
        vals = []
        for byte in row:
            for k in range(8 // bps):
                vals.append((byte >> (8 - bps * (k + 1))) & mask)
        out.extend(vals[:per_row])
    return out[:total]


# =========================================================================== PNM

def decode_pnm(blob):
    m = re.match(rb"P([1-6])\s+(?:#[^\n]*\s+)*(\d+)\s+(?:#[^\n]*\s+)*(\d+)\s+", blob)
    if not m:
        raise CodecError("bad PNM header")
    kind, w, h = int(m.group(1)), int(m.group(2)), int(m.group(3))
    pos = m.end()
    maxv = 1
    if kind not in (1, 4):
        m2 = re.match(rb"(?:#[^\n]*\s+)*(\d+)\s", blob[pos:])
        if not m2:
            raise CodecError("bad PNM header")
        maxv = int(m2.group(1))
        pos += m2.end()
    nch = 3 if kind in (3, 6) else 1
    n = w * h * nch
    if kind in (1, 2, 3):
        vals = [int(v) for v in re.findall(rb"\d+", blob[pos:])[:n]] if kind != 1 else \
            [int(c) for c in re.sub(rb"[^01]", b"", blob[pos:])[:n].decode()]
    elif kind == 4:
        rb = (w + 7) // 8
        vals = []
        for r in range(h):
            row = blob[pos + r * rb:pos + (r + 1) * rb]
            vals.extend([(byte >> (7 - k)) & 1 for byte in row for k in range(8)][:w])
    elif maxv < 256:
        vals = blob[pos:pos + n]
    else:
        vals = struct.unpack(">%dH" % n, blob[pos:pos + 2 * n])
    if len(vals) < n:
        raise CodecError("PNM pixel data is truncated")
    if kind in (1, 4):
        data = bytes(0 if v else 255 for v in vals)
    elif maxv == 255:
        data = bytes(vals)
    else:
        data = bytes(min(255, (v * 255 + maxv // 2) // maxv) for v in vals)
    return w, h, "RGB" if nch == 3 else "L", bytearray(data), {"mode": "RGB" if nch == 3 else "L"}


# =========================================================================== helpers

def orient(w, h, nch, data, o):
    """Apply EXIF orientation o (2..8) like PIL.ImageOps.exif_transpose. Returns (w, h, data)."""
    rows = [bytes(data[y * w * nch:(y + 1) * w * nch]) for y in range(h)]

    def flip(row):
        return b"".join(row[x * nch:(x + 1) * nch] for x in range(w - 1, -1, -1))
    if o == 2:
        return w, h, bytearray(b"".join(flip(r) for r in rows))
    if o == 3:
        return w, h, bytearray(b"".join(flip(r) for r in reversed(rows)))
    if o == 4:
        return w, h, bytearray(b"".join(reversed(rows)))
    px = [[r[x * nch:(x + 1) * nch] for x in range(w)] for r in rows]
    nw, nh = h, w
    if o == 5:
        f = lambda x, y: px[x][y]                      # noqa: E731  transpose
    elif o == 6:
        f = lambda x, y: px[h - 1 - x][y]              # noqa: E731  rotate 90 clockwise
    elif o == 7:
        f = lambda x, y: px[h - 1 - x][w - 1 - y]      # noqa: E731  transverse
    elif o == 8:
        f = lambda x, y: px[x][w - 1 - y]              # noqa: E731  rotate 90 counter-clockwise
    else:
        return w, h, data
    return nw, nh, bytearray(b"".join(f(x, y) for y in range(nh) for x in range(nw)))


def encode_png(w, h, mode, data):
    ctype = {"L": 0, "LA": 4, "RGB": 2, "RGBA": 6}[mode]
    n = len(mode)
    raw = b"".join(b"\x00" + bytes(data[y * w * n:(y + 1) * w * n]) for y in range(h))

    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
