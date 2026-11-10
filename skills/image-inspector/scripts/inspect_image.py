#!/usr/bin/env python3
"""Read an image (PNG, JPEG, WebP, GIF, BMP, TIFF, ...) and report its pixels and a plain-text description.

    python inspect_image.py photo.jpg                       # -> image-reports/photo.json + description on the console
    python inspect_image.py screenshots/ --out reports      # every image in a folder, one JSON each
    python inspect_image.py ui.png --pixel 120,48 --pixel 10,10      # exact colour of given pixels
    python inspect_image.py ui.png --region 0,0,400,80      # average / dominant colours of a rectangle
    python inspect_image.py ui.png --grid 32                # 32-column pixel map (downsampled colours) in the JSON
    python inspect_image.py ui.png --pixels-csv             # every pixel as x,y,r,g,b,a in image-reports/ui.pixels.csv
    python inspect_image.py scan.png --ocr                  # also extract text (needs pytesseract + tesseract)
    python inspect_image.py photo.jpg --stdout              # print the JSON instead of writing files
    python inspect_image.py screen.png --find play_icon.png # where is this icon? (box, centre, score)  [OpenCV]
    python inspect_image.py after.png --compare before.png  # what changed? (% + boxes + diff image)   [OpenCV]

Backends: Pillow when installed (all common formats, EXIF). Without Pillow, PNG (every colour type, bit depth and
interlacing) and BMP are decoded with the standard library; for JPEG/WebP/GIF/TIFF only the size is read and a
warning asks for `pip install Pillow`. --find / --compare and the sharpness score need OpenCV
(`pip install opencv-python-headless`, see cv_features.py). Python 3.8+.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import struct
import sys
import zlib
from pathlib import Path

VERSION = "1.1"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".jpe", ".jfif", ".bmp", ".dib", ".gif", ".webp", ".tif", ".tiff",
              ".ico", ".ppm", ".pgm", ".pbm", ".tga", ".heic", ".heif", ".avif"}
MAX_SAMPLES = 250_000          # pixels looked at for the statistics (the image is sampled on a regular grid)


class ImageError(Exception):
    """The file could not be read as an image. The message says why and what to do."""


# --------------------------------------------------------------------------------------------- raster

class Raster:
    """Decoded pixels: 8 bits per channel, row-major, mode L / LA / RGB / RGBA."""

    CHANNELS = {"L": 1, "LA": 2, "RGB": 3, "RGBA": 4}

    def __init__(self, width: int, height: int, mode: str, data):
        self.width, self.height, self.mode = width, height, mode
        self.channels = self.CHANNELS[mode]
        self.data = data
        if len(data) < width * height * self.channels:
            raise ImageError("decoded pixel data is shorter than the image size (truncated file?)")

    def get(self, x: int, y: int):
        c = self.channels
        o = (y * self.width + x) * c
        d = self.data
        if c == 3:
            return d[o], d[o + 1], d[o + 2], 255
        if c == 4:
            return d[o], d[o + 1], d[o + 2], d[o + 3]
        v = d[o]
        return (v, v, v, 255) if c == 1 else (v, v, v, d[o + 1])


class Loaded:
    def __init__(self):
        self.raster = None            # Raster, or None when only the header could be read
        self.format = ""
        self.width = self.height = 0
        self.info = {}                # extra facts for the "image" section
        self.backend = ""
        self.warnings = []
        self.pil = None               # Pillow image (for OCR), when available


# ------------------------------------------------------------------------------------- stdlib decoders

PNG_SIG = b"\x89PNG\r\n\x1a\n"
ADAM7 = ((0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2))


def _unfilter(data, pos: int, row_bytes: int, rows: int, bpp: int):
    out = bytearray(row_bytes * rows)
    prev = bytearray(row_bytes)
    for r in range(rows):
        if pos + 1 + row_bytes > len(data):
            raise ImageError("PNG pixel data is truncated. The file was cut off; get a complete copy")
        ft = data[pos]
        line = bytearray(data[pos + 1:pos + 1 + row_bytes])
        pos += 1 + row_bytes
        if ft == 1:
            for i in range(bpp, row_bytes):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif ft == 2:
            line = bytearray((a + b) & 255 for a, b in zip(line, prev))
        elif ft == 3:
            for i in range(row_bytes):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif ft == 4:
            for i in range(row_bytes):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        elif ft != 0:
            raise ImageError(f"invalid PNG filter type {ft} (corrupt file)")
        out[r * row_bytes:(r + 1) * row_bytes] = line
        prev = line
    return out, pos


def _samples(line, depth: int, n: int):
    if depth == 8:
        return line[:n]
    if depth == 16:
        return [(line[2 * i] << 8) | line[2 * i + 1] for i in range(n)]
    per, mask, out = 8 // depth, (1 << depth) - 1, []
    for byte in line:
        for k in range(per):
            out.append((byte >> (8 - depth * (k + 1))) & mask)
    return out[:n]


def decode_png(blob: bytes) -> Raster:
    pos, ihdr, plte, trns, idat = 8, None, None, None, []
    while pos + 8 <= len(blob):
        length, ctype = struct.unpack(">I4s", blob[pos:pos + 8])
        chunk = blob[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", chunk[:13])
        elif ctype == b"PLTE":
            plte = chunk
        elif ctype == b"tRNS":
            trns = chunk
        elif ctype == b"IDAT":
            idat.append(chunk)
        elif ctype == b"IEND":
            break
    if not ihdr or not idat:
        raise ImageError("PNG has no IHDR or IDAT chunk (truncated or not really a PNG)")
    w, h, depth, ctype, _comp, _filt, interlace = ihdr
    nch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctype)
    if nch is None or depth not in (1, 2, 4, 8, 16) or w == 0 or h == 0:
        raise ImageError(f"unsupported PNG header (colour type {ctype}, bit depth {depth}, {w}x{h})")
    if ctype == 3 and not plte:
        raise ImageError("palette PNG without a PLTE chunk (corrupt file)")
    try:
        data = zlib.decompress(b"".join(idat))
    except zlib.error:
        try:                                            # truncated stream: decode what is there
            data = zlib.decompressobj().decompress(b"".join(idat))
        except zlib.error as e:
            raise ImageError(f"PNG pixel data is corrupt ({e})") from None

    alpha = ctype in (4, 6) or trns is not None
    mode = ("LA" if alpha else "L") if ctype in (0, 4) else ("RGBA" if alpha else "RGB")
    oc = Raster.CHANNELS[mode]
    out = bytearray(w * h * oc)
    mask = (1 << depth) - 1
    key = None
    if trns is not None and ctype == 0 and len(trns) >= 2:
        key = struct.unpack(">H", trns[:2])[0]
    elif trns is not None and ctype == 2 and len(trns) >= 6:
        key = struct.unpack(">HHH", trns[:6])
    pal = []
    if ctype == 3:
        for i in range(len(plte) // 3):
            a = trns[i] if trns is not None and i < len(trns) else 255
            pal.append((plte[3 * i], plte[3 * i + 1], plte[3 * i + 2], a))

    def scale(v):
        return v >> 8 if depth == 16 else (v if depth == 8 else v * 255 // mask)

    passes = ADAM7 if interlace == 1 else ((0, 0, 1, 1),)
    pos = 0
    bpp = max(1, nch * depth // 8)
    for x0, y0, dx, dy in passes:
        pw, ph = (w - x0 + dx - 1) // dx, (h - y0 + dy - 1) // dy
        if pw <= 0 or ph <= 0:
            continue
        row_bytes = (pw * nch * depth + 7) // 8
        rows, pos = _unfilter(data, pos, row_bytes, ph, bpp)
        fast = interlace == 0 and depth == 8 and trns is None and ctype in (0, 2, 4, 6)
        for r in range(ph):
            line = rows[r * row_bytes:(r + 1) * row_bytes]
            y = y0 + r * dy
            if fast:
                out[y * w * oc:(y + 1) * w * oc] = line
                continue
            s = _samples(line, depth, pw * nch)
            for i in range(pw):
                x = x0 + i * dx
                o = (y * w + x) * oc
                if ctype == 3:
                    idx = s[i]
                    px = pal[idx] if idx < len(pal) else (0, 0, 0, 255)
                    out[o:o + oc] = bytes(px[:oc])
                elif ctype == 0:
                    v = s[i]
                    out[o] = scale(v)
                    if oc == 2:
                        out[o + 1] = 0 if v == key else 255
                elif ctype == 4:
                    out[o], out[o + 1] = scale(s[2 * i]), scale(s[2 * i + 1])
                elif ctype == 2:
                    rgb = (s[3 * i], s[3 * i + 1], s[3 * i + 2])
                    out[o], out[o + 1], out[o + 2] = scale(rgb[0]), scale(rgb[1]), scale(rgb[2])
                    if oc == 4:
                        out[o + 3] = 0 if rgb == key else 255
                else:
                    for k in range(4):
                        out[o + k] = scale(s[4 * i + k])
    return Raster(w, h, mode, out)


def png_header(blob: bytes):
    w, h, depth, ctype, _c, _f, interlace = struct.unpack(">IIBBBBB", blob[16:29])
    names = {0: "grayscale", 2: "RGB", 3: "palette", 4: "grayscale+alpha", 6: "RGBA"}
    return w, h, {"bit_depth": depth, "color_type": names.get(ctype, str(ctype)), "interlaced": interlace == 1}


def decode_bmp(blob: bytes) -> Raster:
    if len(blob) < 26:
        raise ImageError("BMP file is truncated")
    offset, hsize = struct.unpack("<I", blob[10:14])[0], struct.unpack("<I", blob[14:18])[0]
    if hsize == 12:
        w, h, _planes, bpp = struct.unpack("<HHHH", blob[18:26])
        comp, ncolors, pal_entry = 0, 0, 3
    else:
        w, h, _planes, bpp, comp = struct.unpack("<iiHHI", blob[18:34])
        ncolors = struct.unpack("<I", blob[46:50])[0] if hsize >= 40 else 0
        pal_entry = 4
    top_down = h < 0
    h = abs(h)
    if w <= 0 or h == 0:
        raise ImageError(f"invalid BMP size {w}x{h}")
    if comp not in (0, 3) or bpp not in (1, 4, 8, 24, 32) or (comp == 3 and bpp != 32):
        raise ImageError(f"BMP with {bpp}-bit pixels / compression {comp} needs Pillow: pip install Pillow")
    if comp == 3:
        masks = struct.unpack("<III", blob[54:66]) if hsize >= 52 or hsize == 40 else (0, 0, 0)
        if masks != (0x00FF0000, 0x0000FF00, 0x000000FF):
            raise ImageError("BMP with custom bit masks needs Pillow: pip install Pillow")
    stride = ((bpp * w + 31) // 32) * 4
    if offset + stride * h > len(blob):
        raise ImageError("BMP pixel data is truncated")
    pal = []
    if bpp <= 8:
        start = 14 + hsize
        for i in range(ncolors or (1 << bpp)):
            b, g, r = blob[start + i * pal_entry:start + i * pal_entry + 3]
            pal.append((r, g, b))
    mode = "RGBA" if bpp == 32 else "RGB"
    oc = 4 if bpp == 32 else 3
    out = bytearray(w * h * oc)
    any_alpha = False
    for row in range(h):
        y = row if top_down else h - 1 - row
        line = blob[offset + row * stride:offset + (row + 1) * stride]
        o = y * w * oc
        if bpp == 24:
            for x in range(w):
                b, g, r = line[3 * x:3 * x + 3]
                out[o + 3 * x:o + 3 * x + 3] = bytes((r, g, b))
        elif bpp == 32:
            for x in range(w):
                b, g, r, a = line[4 * x:4 * x + 4]
                any_alpha = any_alpha or a != 0
                out[o + 4 * x:o + 4 * x + 4] = bytes((r, g, b, a))
        else:
            s = _samples(line, bpp, w)
            for x in range(w):
                out[o + 3 * x:o + 3 * x + 3] = bytes(pal[s[x]] if s[x] < len(pal) else (0, 0, 0))
    if bpp == 32 and not any_alpha:                       # alpha byte unused: the image is opaque
        for i in range(3, len(out), 4):
            out[i] = 255
    return Raster(w, h, mode, out)


def sniff(blob: bytes) -> str:
    if blob.startswith(PNG_SIG):
        return "PNG"
    if blob[:3] == b"\xff\xd8\xff":
        return "JPEG"
    if blob[:6] in (b"GIF87a", b"GIF89a"):
        return "GIF"
    if blob[:2] == b"BM":
        return "BMP"
    if blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        return "WEBP"
    if blob[:4] in (b"II*\x00", b"MM\x00*"):
        return "TIFF"
    if blob[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1", b"ftypavif"):
        return "HEIF/AVIF"
    head = blob[:256].lstrip().lower()
    if head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in blob[:2048].lower()):
        return "SVG"
    if head.startswith(b"<!doctype html") or head.startswith(b"<html"):
        return "HTML"
    return ""


def header_size(fmt: str, blob: bytes):
    """Width and height from the header only (used when Pillow is missing)."""
    try:
        if fmt == "GIF":
            return struct.unpack("<HH", blob[6:10])
        if fmt == "WEBP":
            kind = blob[12:16]
            if kind == b"VP8X":
                return (int.from_bytes(blob[24:27], "little") + 1, int.from_bytes(blob[27:30], "little") + 1)
            if kind == b"VP8L":
                b = int.from_bytes(blob[21:25], "little")
                return (b & 0x3FFF) + 1, ((b >> 14) & 0x3FFF) + 1
            if kind == b"VP8 ":
                w, h = struct.unpack("<HH", blob[26:30])
                return w & 0x3FFF, h & 0x3FFF
        if fmt == "JPEG":
            i = 2
            while i + 9 < len(blob):
                if blob[i] != 0xFF:
                    i += 1
                    continue
                marker = blob[i + 1]
                if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7 or marker == 0xFF:
                    i += 1 if marker == 0xFF else 2
                    continue
                seg = struct.unpack(">H", blob[i + 2:i + 4])[0]
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                    h, w = struct.unpack(">HH", blob[i + 5:i + 9])
                    return w, h
                i += 2 + seg
    except struct.error:
        pass
    return 0, 0


# ------------------------------------------------------------------------------------------ loading

def _json_safe(v):
    if isinstance(v, bytes):
        v = v.decode("utf-8", "replace")
    if isinstance(v, str):
        return v.strip("\x00 ").strip()
    if isinstance(v, (int, bool)) or v is None:
        return v
    try:
        f = float(v)
        return round(f, 4) if math.isfinite(f) else None
    except (TypeError, ValueError):
        return str(v)


def _exif(im, include_gps: bool):
    try:
        ex = im.getexif()
    except Exception:
        return {}, False
    if not ex:
        return {}, False
    names = {0x010F: "make", 0x0110: "model", 0x0131: "software", 0x0132: "datetime", 0x0112: "orientation",
             0x9003: "datetime_original", 0x829A: "exposure_time", 0x829D: "f_number", 0x8827: "iso",
             0x920A: "focal_length", 0xA405: "focal_length_35mm", 0xA434: "lens_model"}
    out = {}
    for tag, val in ex.items():
        if tag in names:
            out[names[tag]] = _json_safe(val)
    try:
        for tag, val in ex.get_ifd(0x8769).items():
            if tag in names:
                out[names[tag]] = _json_safe(val)
    except Exception:
        pass
    gps = {}
    try:
        gps = dict(ex.get_ifd(0x8825))
    except Exception:
        pass
    if gps and include_gps:
        def deg(vals, ref):
            d = sum(float(v) / f for v, f in zip(vals, (1, 60, 3600)))
            return round(-d if ref in ("S", "W") else d, 6)
        try:
            out["gps"] = {"latitude": deg(gps[2], gps.get(1)), "longitude": deg(gps[4], gps.get(3))}
        except Exception:
            out["gps"] = "present (could not decode)"
    return {k: v for k, v in out.items() if v not in ("", None)}, bool(gps)


def load_with_pillow(path: Path, include_gps: bool) -> Loaded:
    from PIL import Image, ImageOps, __version__ as pil_version
    ld = Loaded()
    ld.backend = f"Pillow {pil_version}"
    try:
        im = Image.open(path)
        im.load()
    except Exception as e:
        raise ImageError(f"cannot read the image ({e.__class__.__name__}: {e})") from None
    ld.format = im.format or path.suffix.lstrip(".").upper()
    orig_mode = im.mode
    frames = getattr(im, "n_frames", 1)
    exif, has_gps = _exif(im, include_gps)
    src, im = im, im.copy()                             # work on a copy so the file can be closed now
    src.close()
    orientation = exif.get("orientation")
    if orientation in (2, 3, 4, 5, 6, 7, 8):
        im = ImageOps.exif_transpose(im)
        ld.info["exif_orientation_applied"] = True
    has_alpha = ("A" in im.mode or "a" in im.mode or "transparency" in im.info)
    gray = im.mode in ("1", "L", "LA", "La", "I", "F") or im.mode.startswith("I;")
    if im.mode == "I" or im.mode.startswith("I;"):
        sixteen = im.mode.startswith("I;16")
        im = im.convert("I")
        if sixteen or im.getextrema()[1] > 255:           # 16-bit samples: 0..65535 -> 0..255
            im = im.point(lambda v: v * (1 / 257))
        im = im.convert("L")
    target = ("LA" if has_alpha else "L") if gray else ("RGBA" if has_alpha else "RGB")
    if im.mode != target:
        im = im.convert("RGBA" if has_alpha else ("L" if gray else "RGB"))
        if im.mode != target:
            im = im.convert(target)
    ld.width, ld.height = im.size
    ld.raster = Raster(ld.width, ld.height, target, im.tobytes())
    ld.pil = im
    dpi = im.info.get("dpi")
    ld.info.update({"mode": orig_mode, "frames": frames, "has_alpha": has_alpha})
    if dpi:
        ld.info["dpi"] = [round(float(d)) for d in dpi]
    if exif:
        ld.info["exif"] = exif
    if has_gps:
        ld.info["has_gps_location"] = True
        if not include_gps:
            ld.warnings.append("The file contains GPS location data (left out of this report; "
                               "--include-gps adds it). Remove it before sharing the image publicly.")
    if frames > 1:
        ld.warnings.append(f"Animated/multi-page image with {frames} frames: only the first frame is analysed.")
    return ld


def load_stdlib(path: Path, blob: bytes, fmt: str) -> Loaded:
    ld = Loaded()
    ld.backend = "standard library"
    ld.format = fmt
    if fmt == "PNG":
        ld.raster = decode_png(blob)
        _, _, extra = png_header(blob)
        ld.info.update(extra)
    elif fmt == "BMP":
        ld.raster = decode_bmp(blob)
    else:
        ld.width, ld.height = header_size(fmt, blob)
        ld.warnings.append(f"{fmt} pixels can't be decoded without Pillow, so only the size is reported. "
                           "Install it and run again: pip install Pillow")
        ld.info["has_alpha"] = None
        return ld
    ld.width, ld.height = ld.raster.width, ld.raster.height
    ld.info["has_alpha"] = ld.raster.mode in ("LA", "RGBA")
    return ld


def load(path: Path, use_pillow: bool = True, include_gps: bool = False) -> Loaded:
    try:
        blob = path.read_bytes()
    except OSError as e:
        raise ImageError(f"cannot open the file ({e.strerror or e})") from None
    if not blob:
        raise ImageError("the file is empty")
    fmt = sniff(blob)
    if fmt == "SVG":
        raise ImageError("this is an SVG (vector) file, not pixels. Export or render it to PNG first")
    if fmt == "HTML":
        raise ImageError("this is an HTML page, not an image. Save the image itself (or a screenshot) first")
    if use_pillow:
        try:
            import PIL  # noqa: F401
        except ImportError:
            use_pillow = False
    if use_pillow:
        ld = load_with_pillow(path, include_gps)
    else:
        if not fmt:
            raise ImageError("unknown file type (not PNG, JPEG, GIF, BMP, WebP or TIFF). "
                             "If it is an image, install Pillow: pip install Pillow")
        ld = load_stdlib(path, blob, fmt)
    ld.info["file_bytes"] = len(blob)
    return ld


# ----------------------------------------------------------------------------------------- analysis

COLOR_NAMES = [
    ("black", (0, 0, 0)), ("dark gray", (64, 64, 64)), ("gray", (128, 128, 128)),
    ("light gray", (192, 192, 192)), ("off-white", (240, 240, 235)), ("white", (255, 255, 255)),
    ("red", (220, 30, 30)), ("dark red", (130, 10, 10)), ("maroon", (110, 25, 45)), ("pink", (255, 175, 195)),
    ("hot pink", (255, 90, 170)), ("orange", (255, 140, 0)), ("brown", (135, 80, 35)),
    ("tan", (210, 180, 140)), ("beige", (235, 225, 195)), ("cream", (255, 250, 220)),
    ("yellow", (250, 220, 30)), ("olive", (128, 128, 0)), ("lime", (150, 230, 50)), ("green", (30, 160, 50)),
    ("dark green", (10, 80, 30)), ("teal", (0, 128, 128)), ("cyan", (0, 210, 230)),
    ("light blue", (170, 210, 245)), ("sky blue", (100, 170, 230)), ("blue", (30, 80, 220)),
    ("navy", (15, 25, 95)), ("purple", (120, 30, 140)), ("violet", (160, 100, 220)),
    ("lavender", (210, 200, 240)), ("magenta", (220, 0, 200)), ("slate", (90, 105, 125)),
]


def dist(c1, c2) -> float:
    """'Redmean' colour distance: cheap and close to how different two colours look."""
    rm = (c1[0] + c2[0]) / 2
    dr, dg, db = c1[0] - c2[0], c1[1] - c2[1], c1[2] - c2[2]
    return math.sqrt((2 + rm / 256) * dr * dr + 4 * dg * dg + (2 + (255 - rm) / 256) * db * db)


def color_name(rgb) -> str:
    return min(COLOR_NAMES, key=lambda nc: dist(rgb, nc[1]))[0]


def hexc(rgb, a=None) -> str:
    s = "#{:02x}{:02x}{:02x}".format(*[int(round(v)) for v in rgb[:3]])
    return s + "{:02x}".format(int(round(a))) if a is not None and a < 255 else s


def luma(r, g, b) -> float:
    return 0.299 * r + 0.587 * g + 0.114 * b


def level(value, bands):
    for limit, name in bands:
        if value < limit:
            return name
    return bands[-1][1]


BRIGHTNESS = ((50, "very dark"), (95, "dark"), (160, "medium"), (205, "bright"), (999, "very bright"))
CONTRAST = ((25, "low"), (60, "medium"), (999, "high"))
SATURATION = ((0.08, "almost none (near grayscale)"), (0.25, "muted"), (0.5, "moderate"), (9, "vivid"))
DETAIL = ((3, "very smooth (large flat areas)"), (8, "smooth"), (20, "moderate detail"),
          (999, "lots of fine detail or noise"))


def aspect(w: int, h: int) -> str:
    g = math.gcd(w, h)
    a, b = w // g, h // g
    if a <= 32 and b <= 32:
        return f"{a}:{b}"
    common = [(1, 1), (4, 3), (3, 2), (16, 9), (16, 10), (21, 9), (5, 4), (2, 1), (9, 19.5), (9, 20)]
    for x, y in common + [(y, x) for x, y in common]:
        if abs(w / h - x / y) / (x / y) < 0.01:
            return f"{x:g}:{y:g} (approx.)"
    return f"{w / h:.2f}:1"


def dominant_colors(pixels, k: int):
    """Cluster the sampled colours; return [(count, (r,g,b))] largest first."""
    buckets = {}
    for r, g, b in pixels:
        key = (r >> 4, g >> 4, b >> 4)
        e = buckets.get(key)
        if e is None:
            buckets[key] = [1, r, g, b]
        else:
            e[0] += 1
            e[1] += r
            e[2] += g
            e[3] += b
    clusters = []                                        # [count, sum_r, sum_g, sum_b]
    for n, sr, sg, sb in sorted(buckets.values(), reverse=True):
        mean = (sr / n, sg / n, sb / n)
        for c in clusters:
            if dist(mean, (c[1] / c[0], c[2] / c[0], c[3] / c[0])) < 45:
                c[0] += n
                c[1] += sr
                c[2] += sg
                c[3] += sb
                break
        else:
            clusters.append([n, sr, sg, sb])
    clusters.sort(reverse=True)
    return [(c[0], (c[1] / c[0], c[2] / c[0], c[3] / c[0])) for c in clusters[:k]]


def color_entry(rgb, count=None, total=None, alpha=None):
    e = {"hex": hexc(rgb, alpha), "rgb": [int(round(v)) for v in rgb], "name": color_name(rgb)}
    if alpha is not None and alpha < 255:
        e["alpha"] = int(round(alpha))
    if count is not None and total:
        e["percent"] = round(100 * count / total, 1)
    return e


def analyse(r: Raster, k: int = 6):
    w, h = r.width, r.height
    step = max(1, math.ceil(math.sqrt(w * h / MAX_SAMPLES)))
    xs, ys = range(0, w, step), range(0, h, step)
    opaque, lumas, exact = [], [], {}
    transparent = translucent = gray_like = 0
    sum_r = sum_g = sum_b = sum_s = 0.0
    lmin, lmax = 255.0, 0.0
    hist = [0] * 8
    cells = [[[0, 0.0, 0.0, 0.0] for _ in range(3)] for _ in range(3)]
    luma_rows = []
    get = r.get
    for y in ys:
        cy = min(2, y * 3 // h)
        row = []
        for x in xs:
            pr, pg, pb, pa = get(x, y)
            if pa == 0:
                transparent += 1
                row.append(None)
                continue
            if pa < 255:
                translucent += 1
            lv = 0.299 * pr + 0.587 * pg + 0.114 * pb
            row.append(lv)
            opaque.append((pr, pg, pb))
            key = (pr << 16) | (pg << 8) | pb
            exact[key] = exact.get(key, 0) + 1
            sum_r += pr
            sum_g += pg
            sum_b += pb
            mx, mn = max(pr, pg, pb), min(pr, pg, pb)
            sum_s += (mx - mn) / mx if mx else 0.0
            if mx - mn <= 10:
                gray_like += 1
            lumas.append(lv)
            lmin, lmax = min(lmin, lv), max(lmax, lv)
            hist[min(7, int(lv) // 32)] += 1
            c = cells[cy][min(2, x * 3 // w)]
            c[0] += 1
            c[1] += pr
            c[2] += pg
            c[3] += pb
        luma_rows.append(row)
    sampled = len(xs) * len(ys)
    n = len(opaque)
    res = {"sampling": {"step": step, "sampled_pixels": sampled,
                        "note": "statistics use every pixel" if step == 1 else
                        f"statistics use every {step}{ordinal(step)} pixel in each direction"}}
    res["transparency"] = {"transparent_percent": round(100 * transparent / sampled, 1),
                           "translucent_percent": round(100 * translucent / sampled, 1)}
    if n == 0:
        res["empty"] = True
        return res
    mean_l = sum(lumas) / n
    std_l = math.sqrt(sum((v - mean_l) ** 2 for v in lumas) / n)
    mean_rgb = (sum_r / n, sum_g / n, sum_b / n)
    sat = sum_s / n
    res["colors"] = {
        "mean": color_entry(mean_rgb),
        "grayscale": gray_like / n >= 0.99,
        "saturation": {"mean": round(sat, 3), "level": level(sat, SATURATION)},
        "brightness": {"mean": round(mean_l, 1), "min": round(lmin), "max": round(lmax),
                       "level": level(mean_l, BRIGHTNESS)},
        "contrast": {"luma_std": round(std_l, 1), "level": level(std_l, CONTRAST)},
        "luma_histogram_percent": [round(100 * c / n, 1) for c in hist],
        "unique_colors_in_sample": len(exact),
        "dominant": [color_entry(rgb, cnt, n) for cnt, rgb in dominant_colors(opaque, k)],
    }
    grid = []
    for row in cells:
        out = []
        for cnt, cr, cg, cb in row:
            if cnt:
                rgb = (cr / cnt, cg / cnt, cb / cnt)
                e = color_entry(rgb)
                e["brightness"] = round(luma(*rgb), 1)
            else:
                e = {"hex": None, "name": "transparent", "brightness": None}
            out.append(e)
        grid.append(out)
    diffs = []
    for i, row in enumerate(luma_rows):
        for j in range(len(row) - 1):
            if row[j] is not None and row[j + 1] is not None:
                diffs.append(abs(row[j] - row[j + 1]))
            if i + 1 < len(luma_rows) and row[j] is not None and luma_rows[i + 1][j] is not None:
                diffs.append(abs(row[j] - luma_rows[i + 1][j]))
    detail = sum(diffs) / len(diffs) if diffs else 0.0
    top10 = sum(sorted(exact.values(), reverse=True)[:10]) / n
    unique_ratio = len(exact) / n
    if top10 >= 0.6 and unique_ratio < 0.05:
        kind = "a flat graphic (screenshot, UI, diagram, icon or logo)"
    elif unique_ratio > 0.2 and top10 < 0.3:
        kind = "a photograph or other continuous-tone image"
    else:
        kind = "a mix of flat areas and photo-like content (for example a screenshot with photos, or a compressed graphic)"
    res["layout"] = {"grid_3x3": grid, "notes": layout_notes(grid)}
    res["texture"] = {"edge_strength": round(detail, 2), "detail": level(detail, DETAIL),
                      "top10_colors_cover_percent": round(100 * top10, 1), "kind_guess": kind}
    return res


def ordinal(n: int) -> str:
    return "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def layout_notes(grid):
    def avg(cells):
        vals = [c["brightness"] for c in cells if c["brightness"] is not None]
        return sum(vals) / len(vals) if vals else None
    notes = []
    pairs = [("top", grid[0], "bottom", grid[2]),
             ("left", [row[0] for row in grid], "right", [row[2] for row in grid])]
    for a_name, a, b_name, b in pairs:
        la, lb = avg(a), avg(b)
        if la is not None and lb is not None and abs(la - lb) > 35:
            hi, lo = (a_name, b_name) if la > lb else (b_name, a_name)
            notes.append(f"brighter at the {hi} than the {lo}")
    center = grid[1][1]["brightness"]
    border = avg([c for i, row in enumerate(grid) for j, c in enumerate(row) if (i, j) != (1, 1)])
    if center is not None and border is not None and abs(center - border) > 35:
        notes.append("the centre is " + ("brighter" if center > border else "darker") + " than the edges")
    names = [c["name"] for row in grid for c in row]
    if len(set(names)) == 1 and names[0] != "transparent":
        notes.append(f"{names[0]} across the whole image")
    return notes


def pixel_map(r: Raster, cols: int):
    """Downsampled colour grid: each cell is the average of up to 8x8 pixels inside it."""
    cols = max(1, min(cols, r.width))
    rows = max(1, min(r.height, round(cols * r.height / r.width)))
    cw, ch = r.width / cols, r.height / rows
    alpha = r.mode in ("LA", "RGBA")
    out = []
    for j in range(rows):
        y0, y1 = int(j * ch), max(int(j * ch) + 1, int((j + 1) * ch))
        line = []
        for i in range(cols):
            x0, x1 = int(i * cw), max(int(i * cw) + 1, int((i + 1) * cw))
            sx, sy = max(1, (x1 - x0) // 8), max(1, (y1 - y0) // 8)
            tot = [0, 0, 0, 0]
            n = 0
            for y in range(y0, y1, sy):
                for x in range(x0, x1, sx):
                    p = r.get(x, y)
                    for q in range(4):
                        tot[q] += p[q]
                    n += 1
            line.append(hexc([t / n for t in tot[:3]], tot[3] / n if alpha else None))
        out.append(line)
    return {"columns": cols, "rows": rows, "cell_width": round(cw, 2), "cell_height": round(ch, 2),
            "format": "#rrggbb" + ("[aa] (aa only when not fully opaque)" if alpha else ""), "hex": out}


def parse_ints(text: str, n: int, what: str):
    try:
        vals = [int(v) for v in text.replace(" ", "").split(",")]
    except ValueError:
        vals = []
    if len(vals) != n:
        raise ImageError(f"{what} must be {n} comma-separated integers, got '{text}'")
    return vals


def pixel_info(r: Raster, spec: str):
    x, y = parse_ints(spec, 2, "--pixel")
    if not (0 <= x < r.width and 0 <= y < r.height):
        raise ImageError(f"pixel {x},{y} is outside the image (0..{r.width - 1}, 0..{r.height - 1})")
    pr, pg, pb, pa = r.get(x, y)
    e = {"x": x, "y": y, "rgba": [pr, pg, pb, pa]}
    e.update(color_entry((pr, pg, pb), alpha=pa))
    e["rgba"] = [pr, pg, pb, pa]
    return e


def region_info(r: Raster, spec: str):
    x, y, w, h = parse_ints(spec, 4, "--region")
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(r.width, x + w), min(r.height, y + h)
    if x1 <= x0 or y1 <= y0:
        raise ImageError(f"region {spec} is outside the image ({r.width}x{r.height})")
    step = max(1, math.ceil(math.sqrt((x1 - x0) * (y1 - y0) / MAX_SAMPLES)))
    px = []
    transparent = 0
    for yy in range(y0, y1, step):
        for xx in range(x0, x1, step):
            p = r.get(xx, yy)
            if p[3] == 0:
                transparent += 1
            else:
                px.append(p[:3])
    e = {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}
    if (x0, y0, x1 - x0, y1 - y0) != (x, y, w, h):
        e["clipped_from"] = spec
    if not px:
        e["fully_transparent"] = True
        return e
    n = len(px)
    mean = tuple(sum(p[i] for p in px) / n for i in range(3))
    lv = [luma(*p) for p in px]
    e["mean"] = color_entry(mean)
    e["brightness"] = round(sum(lv) / n, 1)
    e["transparent_percent"] = round(100 * transparent / (n + transparent), 1)
    e["dominant"] = [color_entry(rgb, cnt, n) for cnt, rgb in dominant_colors(px, 3)]
    return e


def run_ocr(pil_image, lang: str):
    """Text in the image via Tesseract. Returns (result dict | None, warning | None)."""
    if pil_image is None:
        return None, "OCR needs Pillow: pip install Pillow pytesseract (and the Tesseract program)"
    try:
        import pytesseract
    except ImportError:
        return None, ("OCR unavailable: pip install pytesseract and install the Tesseract program "
                      "(https://github.com/tesseract-ocr/tesseract). Or read the text from the image directly.")
    try:
        img = pil_image.convert("RGB")
        data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
    except Exception as e:
        return None, f"OCR failed ({e.__class__.__name__}: {e}). Is the Tesseract program installed and on PATH?"
    words, lines = [], {}
    for i, txt in enumerate(data.get("text", [])):
        txt = (txt or "").strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1
        if not txt or conf < 0:
            continue
        box = [int(data[k][i]) for k in ("left", "top", "width", "height")]
        words.append({"text": txt, "confidence": round(conf, 1), "box": box})
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(txt)
    text = "\n".join(" ".join(v) for _, v in sorted(lines.items()))
    return {"engine": "tesseract", "lang": lang, "text": text, "words": words[:2000]}, None


# -------------------------------------------------------------------------------------- description

def describe(name: str, ld: Loaded, a: dict, ocr) -> str:
    w, h = ld.width, ld.height
    orient = "square" if w == h else ("landscape" if w > h else "portrait")
    mp = w * h / 1e6
    parts = [f"{name} is a {w}x{h} {ld.format} image ({mp:.2g} MP, {aspect(w, h)}, {orient})." if mp < 1 else
             f"{name} is a {w}x{h} {ld.format} image ({mp:.1f} MP, {aspect(w, h)}, {orient})."]
    if not a:
        return parts[0] + " Its pixels could not be decoded (see warnings)."
    t = a["transparency"]
    if a.get("empty"):
        return parts[0] + " Every pixel is fully transparent."
    c = a["colors"]
    dom, seen = [], set()
    for d in c["dominant"]:
        if d["name"] not in seen and (d["percent"] >= 3 or not dom):
            seen.add(d["name"])
            dom.append(f"{d['name']} ({d['percent']:g}%)")
        if len(dom) == 4:
            break
    tone = "It is grayscale" if c["grayscale"] else f"It is in colour, saturation {c['saturation']['level']}"
    parts.append(f"Main colours: {', '.join(dom)}.")
    parts.append(f"{tone}; brightness is {c['brightness']['level']} (average {c['brightness']['mean']:g}/255) "
                 f"with {c['contrast']['level']} contrast.")
    if a["layout"]["notes"]:
        notes = a["layout"]["notes"]
        parts.append(notes[0][0].upper() + notes[0][1:] + "".join("; " + n for n in notes[1:]) + ".")
    g = a["layout"]["grid_3x3"]
    parts.append("Top row: " + ", ".join(x["name"] for x in g[0]) + "; middle: "
                 + ", ".join(x["name"] for x in g[1]) + "; bottom: " + ", ".join(x["name"] for x in g[2]) + ".")
    parts.append(f"Texture: {a['texture']['detail']}; it looks like {a['texture']['kind_guess']}.")
    if t["transparent_percent"] or t["translucent_percent"]:
        parts.append(f"{t['transparent_percent']:g}% of the pixels are fully transparent"
                     + (f" and {t['translucent_percent']:g}% partly transparent." if t["translucent_percent"] else "."))
    if ocr is not None:
        txt = " ".join(ocr["text"].split())
        parts.append(f'Text found (OCR): "{txt[:300]}{"..." if len(txt) > 300 else ""}"' if txt
                     else "OCR found no text.")
    return " ".join(parts)


# ---------------------------------------------------------------------------------------------- CLI

def reference_for(path: Path, ref: Path) -> Path:
    """--compare may name one file, or a folder with images of the same names (baseline folder)."""
    return ref / path.name if ref.is_dir() else ref


def cv_sections(path: Path, ld: Loaded, report: dict, opts, stem: str, templates):
    """Sharpness, --find and --compare (OpenCV). Returns extra description sentences."""
    import cv_features as cvf
    extra = []
    if "texture" in report:
        report["texture"]["sharpness"] = cvf.sharpness(ld.raster)
        if report["texture"]["kind_guess"].startswith("a photograph"):
            extra.append(f"Sharpness: {report['texture']['sharpness']['level']}.")
    if templates:
        found = []
        for tname, traster in templates:
            matches, warns = cvf.find_template(ld.raster, traster, opts.threshold, opts.max_matches, opts.scales)
            ld.warnings.extend(f"{tname}: {w}" for w in warns)
            found.append({"template": tname, "found": len(matches), "matches": matches})
            if matches:
                m = matches[0]
                extra.append(f"{tname} found {len(matches)} time(s); first at x={m['x']}, y={m['y']} "
                             f"({m['width']}x{m['height']}, centre {m['center'][0]},{m['center'][1]}, "
                             f"score {m['score']:g}).")
            else:
                extra.append(f"{tname} was not found (threshold {opts.threshold:g}).")
        report["find"] = found
    if opts.compare:
        ref_path = reference_for(path, opts.compare)
        if not ref_path.is_file():
            ld.warnings.append(f"--compare: no reference image {ref_path}")
        else:
            ref = load(ref_path, use_pillow=not opts.no_pillow)
            if ref.raster is None:
                ld.warnings.append(f"--compare: could not decode {ref_path} (" + "; ".join(ref.warnings) + ")")
            else:
                diff_path = None if opts.stdout else opts.out / f"{stem}.diff.png"
                res, warns = cvf.compare(ld.raster, ref.raster, opts.diff_threshold, opts.min_area,
                                         opts.ignore_boxes, diff_path)
                res = dict({"reference": str(ref_path)}, **res)
                ld.warnings.extend(warns)
                report["comparison"] = res
                if res["identical"]:
                    extra.append(f"It is pixel-identical to {ref_path.name}.")
                else:
                    where = ""
                    if res["changed_regions"]:
                        where = "; the largest is at x={x}, y={y} ({width}x{height})".format(**res["changed_regions"][0])
                    extra.append(f"Compared with {ref_path.name}: {res['changed_percent']:g}% of the pixels changed, "
                                 f"in {len(res['changed_regions'])} area(s){where}.")
    return extra


def inspect(path: Path, opts, stem: str = "", templates=()):
    ld = load(path, use_pillow=not opts.no_pillow, include_gps=opts.include_gps)
    report = {"generator": {"name": "image-inspector", "version": VERSION, "backend": ld.backend},
              "file": {"name": path.name, "path": str(path), "bytes": ld.info.pop("file_bytes"),
                       "format": ld.format}}
    w, h = ld.width, ld.height
    img = {"width": w, "height": h, "megapixels": round(w * h / 1e6, 2), "aspect_ratio": aspect(w, h) if h else "",
           "orientation": "square" if w == h else ("landscape" if w > h else "portrait")}
    img.update(ld.info)
    report["image"] = img
    a = {}
    if ld.raster is not None:
        a = analyse(ld.raster, opts.colors)
        report["sampling"] = a.get("sampling")
        report["transparency"] = a.get("transparency")
        for key in ("colors", "layout", "texture"):
            if key in a:
                report[key] = a[key]
        if opts.grid:
            report["pixel_map"] = pixel_map(ld.raster, opts.grid)
        if opts.pixel:
            report["pixels"] = [pixel_info(ld.raster, s) for s in opts.pixel]
        if opts.region:
            report["regions"] = [region_info(ld.raster, s) for s in opts.region]
    elif opts.pixel or opts.region or opts.pixels_csv:
        ld.warnings.append("--pixel / --region / --pixels-csv were ignored because the pixels could not be decoded.")
    ocr = None
    if opts.ocr:
        ocr, warn = run_ocr(ld.pil, opts.ocr_lang)
        if warn:
            ld.warnings.append(warn)
        if ocr is not None:
            report["ocr"] = ocr
    report["description"] = describe(path.name, ld, a, ocr)
    if ld.raster is not None and getattr(opts, "cv", False):
        extra = cv_sections(path, ld, report, opts, stem or path.stem, templates)
        if extra:
            report["description"] += " " + " ".join(extra)
    elif ld.raster is None and (templates or opts.compare):
        ld.warnings.append("--find / --compare were skipped because the pixels could not be decoded.")
    report["warnings"] = ld.warnings
    return report, ld


def write_csv(ld: Loaded, dest: Path, limit: int):
    r = ld.raster
    if r.width * r.height > limit:
        return (f"--pixels-csv skipped: {r.width * r.height:,} pixels is more than --max-csv-pixels {limit:,}. "
                "Raise the limit, or use --region / --grid for a smaller view.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="\n") as f:
        f.write("x,y,r,g,b,a\n")
        for y in range(r.height):
            f.write("".join("%d,%d,%d,%d,%d,%d\n" % ((x, y) + r.get(x, y)) for x in range(r.width)))
    return None


def collect(inputs):
    files = []
    for raw in inputs:
        p = Path(raw)
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in IMAGE_EXTS)
        else:
            files.append(p)
    return files


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Report the pixels of an image and describe it in plain text.")
    ap.add_argument("inputs", nargs="+", help="image files or folders")
    ap.add_argument("--out", type=Path, default=Path("image-reports"), help="folder for the reports (default: ./image-reports)")
    ap.add_argument("--stdout", action="store_true", help="print the JSON instead of writing files")
    ap.add_argument("--pixel", action="append", metavar="X,Y", help="report the exact colour of this pixel (repeatable)")
    ap.add_argument("--region", action="append", metavar="X,Y,W,H", help="report the colours of a rectangle (repeatable)")
    ap.add_argument("--grid", type=int, default=16, metavar="N", help="columns of the downsampled pixel map (default 16, 0 = off)")
    ap.add_argument("--colors", type=int, default=6, metavar="K", help="number of dominant colours (default 6)")
    ap.add_argument("--pixels-csv", action="store_true", help="also write every pixel to <name>.pixels.csv")
    ap.add_argument("--max-csv-pixels", type=int, default=2_000_000, help="refuse --pixels-csv above this many pixels")
    ap.add_argument("--ocr", action="store_true", help="extract text with Tesseract (needs pytesseract + tesseract)")
    ap.add_argument("--ocr-lang", default="eng", help="Tesseract language(s), e.g. eng+deu (default eng)")
    ap.add_argument("--include-gps", action="store_true", help="include GPS coordinates from EXIF (left out by default)")
    ap.add_argument("--no-pillow", action="store_true", help="use only the standard-library decoders (PNG, BMP)")
    cv = ap.add_argument_group("OpenCV features (pip install opencv-python-headless)")
    cv.add_argument("--find", action="append", type=Path, metavar="TEMPLATE",
                    help="find this image (icon, button) inside each input; repeatable")
    cv.add_argument("--threshold", type=float, default=0.8, help="--find: minimum match score 0..1 (default 0.8)")
    cv.add_argument("--max-matches", type=int, default=20, help="--find: most matches per template (default 20)")
    cv.add_argument("--scales", default="1.0", metavar="S1,S2",
                    help="--find: template scales to try, e.g. 0.75,1,1.25,1.5 for other screen densities")
    cv.add_argument("--compare", type=Path, metavar="REFERENCE",
                    help="compare each input with this image, or with the same-named image in this folder")
    cv.add_argument("--diff-threshold", type=int, default=25,
                    help="--compare: per-channel difference (0..255) that counts as changed (default 25)")
    cv.add_argument("--min-area", type=int, default=16, help="--compare: smallest changed box to report, in pixels")
    cv.add_argument("--ignore", action="append", metavar="X,Y,W,H",
                    help="--compare: rectangle to ignore, e.g. a clock (repeatable)")
    cv.add_argument("--fail-on-diff", type=float, metavar="PERCENT",
                    help="--compare: exit with code 1 when more than PERCENT %% of the pixels changed")
    opts = ap.parse_args(argv)

    try:
        opts.ignore_boxes = [tuple(parse_ints(b, 4, "--ignore")) for b in opts.ignore or []]
    except ImageError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 2
    try:
        opts.scales = tuple(float(v) for v in opts.scales.split(",") if v.strip())
        if not opts.scales or min(opts.scales) <= 0:
            raise ValueError
    except ValueError:
        print(f"ERROR --scales must be positive numbers separated by commas, got '{opts.scales}'", file=sys.stderr)
        return 2
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import cv_features
    opts.cv = cv_features.available()
    templates = []
    if (opts.find or opts.compare) and not opts.cv:
        print(f"ERROR --find and --compare need OpenCV: {cv_features.INSTALL_HINT}", file=sys.stderr)
        return 2
    for t in opts.find or []:
        try:
            tl = load(t, use_pillow=not opts.no_pillow)
        except ImageError as e:
            print(f"ERROR template {t}: {e}", file=sys.stderr)
            return 2
        if tl.raster is None:
            print(f"ERROR template {t}: " + "; ".join(tl.warnings), file=sys.stderr)
            return 2
        templates.append((t.name, tl.raster))

    files = collect(opts.inputs)
    if not files:
        print("ERROR no image files found in " + ", ".join(opts.inputs), file=sys.stderr)
        return 2
    failed, over, used = 0, 0, set()
    for path in files:
        stem = path.stem if path.stem not in used else f"{path.stem}_{path.suffix.lstrip('.').lower()}"
        try:
            report, ld = inspect(path, opts, stem, templates)
        except ImageError as e:
            print(f"ERROR {path}: {e}", file=sys.stderr)
            failed += 1
            continue
        cmp_ = report.get("comparison")
        if opts.fail_on_diff is not None and cmp_ and cmp_["changed_percent"] > opts.fail_on_diff:
            over += 1
        if opts.stdout:
            print(json.dumps(report, indent=2, ensure_ascii=False))
            continue
        used.add(stem)
        dest = opts.out / f"{stem}.json"
        if opts.pixels_csv and ld.raster is not None:
            warn = write_csv(ld, opts.out / f"{stem}.pixels.csv", opts.max_csv_pixels)
            if warn:
                report["warnings"].append(warn)
            else:
                report["pixels_csv"] = str(opts.out / f"{stem}.pixels.csv")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        extras = [report.get("pixels_csv"), (cmp_ or {}).get("diff_image")]
        print(f"Wrote {dest}" + "".join(f"  (+ {e})" for e in extras if e))
        print("  " + report["description"])
        for wmsg in report["warnings"]:
            print(f"  WARNING {wmsg}")
    if len(files) > 1 and not opts.stdout:
        print(f"{len(files) - failed} of {len(files)} image(s) inspected.")
    if over:
        print(f"{over} image(s) changed by more than {opts.fail_on_diff:g}% (--fail-on-diff).", file=sys.stderr)
    return 2 if failed else (1 if over else 0)


if __name__ == "__main__":
    sys.exit(main())
