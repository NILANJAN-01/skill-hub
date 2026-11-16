#!/usr/bin/env python3
"""Tests for inspect_image.py. Standard library only; tests that need Pillow are skipped without it.
Run: python -m unittest discover -s scripts -p "test_*.py" """

import io
import json
import os
import random
import struct
import subprocess
import sys
import tempfile
import types
import unittest
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import inspect_image as ii  # noqa: E402

try:
    import PIL  # noqa: F401
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

NCH = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _filter(ft, line, prev, bpp):
    out = bytearray()
    for i, v in enumerate(line):
        a = line[i - bpp] if i >= bpp else 0
        b = prev[i]
        c = prev[i - bpp] if i >= bpp else 0
        if ft == 0:
            pred = 0
        elif ft == 1:
            pred = a
        elif ft == 2:
            pred = b
        elif ft == 3:
            pred = (a + b) >> 1
        else:
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            pred = a if pa <= pb and pa <= pc else b if pb <= pc else c
        out.append((v - pred) & 255)
    return out


def make_png(w, h, sample, ctype, depth, interlace=False, plte=None, trns=None):
    """Encode a PNG. sample(x, y) -> tuple of raw sample values. Rows cycle through all five filter types."""
    nch = NCH[ctype]
    bpp = max(1, nch * depth // 8)
    raw = bytearray()
    passes = ii.ADAM7 if interlace else ((0, 0, 1, 1),)
    row_no = 0
    for x0, y0, dx, dy in passes:
        xs, ys = list(range(x0, w, dx)), list(range(y0, h, dy))
        if not xs or not ys:
            continue
        prev = bytearray((len(xs) * nch * depth + 7) // 8)
        for y in ys:
            samples = [v for x in xs for v in sample(x, y)]
            if depth == 16:
                line = bytearray(b"".join(struct.pack(">H", v) for v in samples))
            elif depth == 8:
                line = bytearray(samples)
            else:
                line = bytearray()
                per = 8 // depth
                for i in range(0, len(samples), per):
                    byte = 0
                    for k, v in enumerate(samples[i:i + per]):
                        byte |= v << (8 - depth * (k + 1))
                    line.append(byte)
            ft = row_no % 5
            raw.append(ft)
            raw += _filter(ft, line, prev, bpp)
            prev = line
            row_no += 1
    out = ii.PNG_SIG + _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, depth, ctype, 0, 0, 1 if interlace else 0))
    if plte:
        out += _chunk(b"PLTE", bytes(v for rgb in plte for v in rgb))
    if trns is not None:
        out += _chunk(b"tRNS", trns)
    return out + _chunk(b"IDAT", zlib.compress(bytes(raw))) + _chunk(b"IEND", b"")


def make_bmp(w, h, rgb, bpp=24, top_down=False, alpha=None):
    stride = ((bpp * w + 31) // 32) * 4
    rows = []
    for row in range(h):
        y = row if top_down else h - 1 - row
        line = bytearray()
        for x in range(w):
            r, g, b = rgb(x, y)
            line += bytes((b, g, r)) + (bytes((alpha(x, y) if alpha else 0,)) if bpp == 32 else b"")
        rows.append(bytes(line).ljust(stride, b"\0"))
    pixels = b"".join(rows)
    dib = struct.pack("<IiiHHIIiiII", 40, w, -h if top_down else h, 1, bpp, 0, len(pixels), 2835, 2835, 0, 0)
    head = b"BM" + struct.pack("<IHHI", 14 + 40 + len(pixels), 0, 0, 54)
    return head + dib + pixels


def raster(w, h, f, mode="RGBA"):
    data = bytearray()
    for y in range(h):
        for x in range(w):
            data += bytes(f(x, y)[:ii.Raster.CHANNELS[mode]])
    return ii.Raster(w, h, mode, data)


class TempDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, blob):
        p = self.dir / name
        p.write_bytes(blob)
        return p


class PngDecoderTests(TempDir):
    W, H = 13, 9            # odd sizes exercise partial bytes and empty Adam7 passes

    def check(self, blob, expected):
        r = ii.decode_png(blob)
        self.assertEqual((r.width, r.height), (self.W, self.H))
        for y in range(self.H):
            for x in range(self.W):
                self.assertEqual(r.get(x, y), expected(x, y), (x, y))
        return r

    def test_every_colour_type_depth_and_interlace(self):
        cases = [(0, d) for d in (1, 2, 4, 8, 16)] + [(2, 8), (2, 16), (4, 8), (4, 16), (6, 8), (6, 16)]
        for ctype, depth in cases:
            for interlace in (False, True):
                with self.subTest(ctype=ctype, depth=depth, interlace=interlace):
                    mx = (1 << depth) - 1

                    def s(x, y, k=0):
                        return (x * 7 + y * 13 + k * 31) % (mx + 1)

                    def scale(v):
                        return v >> 8 if depth == 16 else v * 255 // mx

                    blob = make_png(self.W, self.H, lambda x, y: tuple(s(x, y, k) for k in range(NCH[ctype])),
                                    ctype, depth, interlace)

                    def expected(x, y):
                        v = [scale(s(x, y, k)) for k in range(NCH[ctype])]
                        if ctype == 0:
                            return v[0], v[0], v[0], 255
                        if ctype == 4:
                            return v[0], v[0], v[0], v[1]
                        return (v[0], v[1], v[2], v[3] if ctype == 6 else 255)
                    self.check(blob, expected)

    def test_palette_with_transparency_all_depths(self):
        for depth in (1, 2, 4, 8):
            for interlace in (False, True):
                with self.subTest(depth=depth, interlace=interlace):
                    n = min(1 << depth, 6)
                    pal = [(i * 40, 255 - i * 30, (i * 77) % 256) for i in range(n)]
                    alphas = bytes([0, 128][:n])

                    def idx(x, y):
                        return (x + y) % n
                    blob = make_png(self.W, self.H, lambda x, y: (idx(x, y),), 3, depth, interlace, pal, alphas)
                    self.check(blob, lambda x, y: pal[idx(x, y)] + ((0, 128)[idx(x, y)] if idx(x, y) < len(alphas)
                                                                      else 255,))

    def test_trns_colour_key_for_gray_and_rgb(self):
        blob = make_png(self.W, self.H, lambda x, y: ((x * 20) % 256,), 0, 8, trns=struct.pack(">H", 0))
        r = self.check(blob, lambda x, y: ((x * 20) % 256,) * 3 + (0 if x * 20 % 256 == 0 else 255,))
        self.assertEqual(r.mode, "LA")
        key = (10, 20, 30)
        blob = make_png(self.W, self.H, lambda x, y: key if x == y else (200, 100, 50), 2, 8,
                        trns=struct.pack(">HHH", *key))
        self.check(blob, lambda x, y: key + (0,) if x == y else (200, 100, 50, 255))

    def test_truncated_png_is_reported(self):
        blob = make_png(40, 40, lambda x, y: (x, y, 0), 2, 8)
        with self.assertRaises(ii.ImageError) as cm:
            ii.decode_png(blob[:len(blob) // 2])
        self.assertIn("truncated", str(cm.exception))

    def test_bmp_24_32_and_top_down(self):
        f = lambda x, y: (x * 10, y * 20, 99)  # noqa: E731
        for bpp in (24, 32):
            for top in (False, True):
                with self.subTest(bpp=bpp, top_down=top):
                    r = ii.decode_bmp(make_bmp(7, 5, f, bpp, top))
                    self.assertEqual(r.get(3, 4), (30, 80, 99, 255))       # unused alpha byte -> opaque
        r = ii.decode_bmp(make_bmp(4, 2, f, 32, alpha=lambda x, y: 50 * x))
        self.assertEqual(r.get(2, 1), (20, 20, 99, 100))

    def test_rejects_non_images(self):
        cases = {"page.html": b"<!DOCTYPE html><html><body><img src=x.png></body></html>",
                 "logo.svg": b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>',
                 "empty.png": b"", "notes.png": b"just some text"}
        expect = {"page.html": "HTML page", "logo.svg": "SVG", "empty.png": "empty", "notes.png": "unknown file type"}
        for name, blob in cases.items():
            with self.subTest(name):
                with self.assertRaises(ii.ImageError) as cm:
                    ii.load(self.write(name, blob), use_pillow=False)
                self.assertIn(expect[name], str(cm.exception))

    def test_header_only_sizes_without_pillow(self):
        gif = b"GIF89a" + struct.pack("<HH", 320, 200) + b"\0" * 20
        ld = ii.load(self.write("a.gif", gif), use_pillow=False)
        self.assertEqual((ld.width, ld.height, ld.raster), (320, 200, None))
        self.assertIn("pip install Pillow", ld.warnings[0])
        jpeg = b"\xff\xd8\xff\xe0" + struct.pack(">H", 16) + b"JFIF\0" + b"\0" * 9 + \
            b"\xff\xc0" + struct.pack(">HBHHB", 17, 8, 480, 640, 3) + b"\0" * 9 + b"\xff\xd9"
        ld = ii.load(self.write("a.jpg", jpeg), use_pillow=False)
        self.assertEqual((ld.format, ld.width, ld.height), ("JPEG", 640, 480))


class AnalysisTests(unittest.TestCase):
    def test_solid_gray_image(self):
        a = ii.analyse(raster(50, 40, lambda x, y: (128, 128, 128, 255)))
        c = a["colors"]
        self.assertTrue(c["grayscale"])
        self.assertEqual(c["mean"]["hex"], "#808080")
        self.assertEqual([(d["name"], d["percent"]) for d in c["dominant"]], [("gray", 100.0)])
        self.assertEqual(c["unique_colors_in_sample"], 1)
        self.assertEqual(c["contrast"]["level"], "low")
        self.assertIn("flat graphic", a["texture"]["kind_guess"])
        self.assertIn("gray across the whole image", a["layout"]["notes"])

    def test_two_colours_percentages_and_layout(self):
        # top quarter white, rest navy
        a = ii.analyse(raster(40, 40, lambda x, y: (255, 255, 255, 255) if y < 10 else (15, 25, 95, 255)))
        dom = {d["name"]: d["percent"] for d in a["colors"]["dominant"]}
        self.assertEqual(dom, {"navy": 75.0, "white": 25.0})
        self.assertIn("brighter at the top than the bottom", a["layout"]["notes"])
        self.assertFalse(a["colors"]["grayscale"])

    def test_transparency_is_excluded_from_colours(self):
        a = ii.analyse(raster(20, 20, lambda x, y: (220, 30, 30, 255) if x < 10 else (0, 0, 0, 0)))
        self.assertEqual(a["transparency"]["transparent_percent"], 50.0)
        self.assertEqual(a["colors"]["dominant"][0]["name"], "red")
        self.assertEqual(a["colors"]["dominant"][0]["percent"], 100.0)
        self.assertEqual(a["layout"]["grid_3x3"][0][2]["name"], "transparent")

    def test_fully_transparent_image(self):
        a = ii.analyse(raster(8, 8, lambda x, y: (0, 0, 0, 0)))
        self.assertTrue(a["empty"])

    def test_noise_looks_like_a_photo(self):
        rnd = random.Random(3)
        a = ii.analyse(raster(120, 90, lambda x, y: (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256), 255)))
        self.assertIn("photograph", a["texture"]["kind_guess"])
        self.assertEqual(a["texture"]["detail"], "lots of fine detail or noise")

    def test_large_images_are_sampled(self):
        r = ii.Raster(2000, 1000, "L", bytearray(2000 * 1000))
        a = ii.analyse(r)
        self.assertGreater(a["sampling"]["step"], 1)
        self.assertLessEqual(a["sampling"]["sampled_pixels"], ii.MAX_SAMPLES * 1.1)
        self.assertEqual(a["colors"]["dominant"][0]["name"], "black")

    def test_pixel_region_and_map(self):
        r = raster(30, 20, lambda x, y: (x * 8, y * 12, 0, 255 if x else 128))
        p = ii.pixel_info(r, "3,4")
        self.assertEqual((p["rgba"], p["hex"]), ([24, 48, 0, 255], "#183000"))
        self.assertEqual(ii.pixel_info(r, "0,0")["hex"], "#00000080")
        with self.assertRaises(ii.ImageError):
            ii.pixel_info(r, "30,0")
        with self.assertRaises(ii.ImageError):
            ii.pixel_info(r, "1;2")
        reg = ii.region_info(r, "20,10,50,50")
        self.assertEqual((reg["x"], reg["y"], reg["width"], reg["height"]), (20, 10, 10, 10))
        self.assertEqual(reg["clipped_from"], "20,10,50,50")
        pm = ii.pixel_map(r, 6)
        self.assertEqual((pm["columns"], pm["rows"], len(pm["hex"]), len(pm["hex"][0])), (6, 4, 4, 6))

    def test_aspect_and_colour_names(self):
        self.assertEqual(ii.aspect(1920, 1080), "16:9")
        self.assertEqual(ii.aspect(1080, 2400), "9:20")
        self.assertEqual(ii.aspect(1366, 768), "16:9 (approx.)")
        self.assertEqual(ii.aspect(1000, 333), "3.00:1")
        for rgb, name in (((250, 250, 250), "white"), ((5, 5, 5), "black"), ((200, 20, 30), "red"),
                          ((30, 90, 210), "blue"), ((255, 145, 10), "orange"), ((40, 150, 60), "green")):
            self.assertEqual(ii.color_name(rgb), name)

    def test_ocr_with_fake_tesseract(self):
        fake = types.ModuleType("pytesseract")
        fake.Output = types.SimpleNamespace(DICT="dict")
        fake.image_to_data = lambda img, lang, output_type: {
            "text": ["Sign", "in", "", "Help"], "conf": ["96", "91.5", "-1", "88"],
            "left": [10, 60, 0, 10], "top": [5, 5, 0, 40], "width": [40, 20, 0, 30], "height": [12, 12, 0, 12],
            "block_num": [1, 1, 1, 2], "par_num": [1, 1, 1, 1], "line_num": [1, 1, 1, 1]}
        img = types.SimpleNamespace(convert=lambda mode: img)
        sys.modules["pytesseract"] = fake
        try:
            res, warn = ii.run_ocr(img, "eng")
        finally:
            del sys.modules["pytesseract"]
        self.assertIsNone(warn)
        self.assertEqual(res["text"], "Sign in\nHelp")
        self.assertEqual(res["words"][0], {"text": "Sign", "confidence": 96.0, "box": [10, 5, 40, 12]})
        self.assertIsNone(ii.run_ocr(None, "eng")[0])


class CliTests(TempDir):
    def cli(self, *args):
        return subprocess.run([sys.executable, str(HERE / "inspect_image.py"), *args], cwd=self.dir,
                              capture_output=True, text=True, encoding="utf-8")

    def test_writes_report_and_description(self):
        self.write("ui.png", make_png(60, 120, lambda x, y: (33, 150, 243) if y < 20 else (255, 255, 255), 2, 8))
        p = self.cli("ui.png", "--no-pillow", "--pixel", "5,5", "--region", "0,20,60,100", "--grid", "4")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("ui.png is a 60x120 PNG image", p.stdout)
        rep = json.loads((self.dir / "image-reports" / "ui.json").read_text(encoding="utf-8"))
        self.assertEqual(rep["generator"]["backend"], "standard library")
        self.assertEqual(rep["image"]["aspect_ratio"], "1:2")
        self.assertEqual(rep["pixels"][0]["hex"], "#2196f3")
        self.assertEqual(rep["regions"][0]["mean"]["name"], "white")
        self.assertEqual(rep["pixel_map"]["hex"][0][0], "#2196f3")
        self.assertEqual(rep["colors"]["dominant"][0]["name"], "white")
        self.assertTrue(rep["description"].startswith("ui.png is a 60x120 PNG image"))

    def test_folder_name_collision_csv_and_errors(self):
        d = self.dir / "shots"
        d.mkdir()
        (d / "a.png").write_bytes(make_png(3, 2, lambda x, y: (x, y, 9), 2, 8))
        (d / "a.bmp").write_bytes(make_bmp(3, 2, lambda x, y: (x, y, 9)))
        (d / "readme.txt").write_text("not an image")
        p = self.cli("shots", "--no-pillow", "--pixels-csv")
        self.assertEqual(p.returncode, 0, p.stderr)
        names = sorted(f.name for f in (self.dir / "image-reports").iterdir())
        self.assertEqual(names, ["a.json", "a.pixels.csv", "a_png.json", "a_png.pixels.csv"])
        csv = (self.dir / "image-reports" / "a.pixels.csv").read_text().splitlines()
        self.assertEqual(csv[:3], ["x,y,r,g,b,a", "0,0,0,0,9,255", "1,0,1,0,9,255"])
        self.assertEqual(len(csv), 7)
        p = self.cli("shots/a.png", "--no-pillow", "--pixels-csv", "--max-csv-pixels", "2", "--out", "o2")
        self.assertIn("--pixels-csv skipped", p.stdout)
        self.write("bad.png", b"\x89PNG\r\n\x1a\n" + b"\0" * 30)
        p = self.cli("bad.png", "--no-pillow")
        self.assertEqual(p.returncode, 2)
        self.assertIn("ERROR", p.stderr)

    def test_stdout_json(self):
        self.write("g.png", make_png(4, 4, lambda x, y: (200,), 0, 8))
        p = self.cli("g.png", "--no-pillow", "--stdout", "--grid", "0")
        rep = json.loads(p.stdout)
        self.assertNotIn("pixel_map", rep)
        self.assertTrue(rep["colors"]["grayscale"])
        self.assertFalse((self.dir / "image-reports").exists())


@unittest.skipUnless(HAVE_PIL, "Pillow not installed")
class PillowTests(TempDir):
    def test_pillow_matches_stdlib_decoder(self):
        for interlace in (False, True):
            blob = make_png(17, 11, lambda x, y: (x * 15, y * 23, (x * y) % 256, 255 - x * 5), 6, 8, interlace)
            p = self.write(f"i{interlace}.png", blob)
            a, b = ii.load(p).raster, ii.load(p, use_pillow=False).raster
            self.assertEqual([a.get(x, y) for y in range(11) for x in range(17)],
                             [b.get(x, y) for y in range(11) for x in range(17)])

    def test_jpeg_exif_orientation_and_gps(self):
        from PIL import Image
        im = Image.new("RGB", (300, 100), (30, 80, 220))
        exif = Image.Exif()
        exif[0x0112] = 6                      # rotate 90 degrees when displayed
        exif[0x010F] = "TestCam"
        exif.get_ifd(0x8825).update({1: "N", 2: (52.0, 31.0, 12.0), 3: "E", 4: (13.0, 24.0, 0.0)})
        buf = io.BytesIO()
        im.save(buf, "JPEG", exif=exif, quality=95)
        p = self.write("photo.jpg", buf.getvalue())
        ld = ii.load(p)
        self.assertEqual((ld.format, ld.width, ld.height), ("JPEG", 100, 300))
        self.assertTrue(ld.info["exif_orientation_applied"])
        self.assertEqual(ld.info["exif"]["make"], "TestCam")
        self.assertNotIn("gps", ld.info["exif"])
        self.assertTrue(any("GPS" in w for w in ld.warnings))
        gps = ii.load(p, include_gps=True).info["exif"]["gps"]
        self.assertAlmostEqual(gps["latitude"], 52.52, places=2)
        a = ii.analyse(ld.raster)
        self.assertEqual(a["colors"]["dominant"][0]["name"], "blue")

    def test_sixteen_bit_and_animated(self):
        from PIL import Image
        vals = [(i * 997) % 65536 for i in range(20 * 10)]
        p = self.dir / "g16.png"
        Image.frombytes("I;16", (20, 10), struct.pack("<%dH" % len(vals), *vals)).save(p)
        a, b = ii.load(p).raster, ii.load(p, use_pillow=False).raster
        self.assertLessEqual(max(abs(a.get(x, y)[0] - b.get(x, y)[0]) for y in range(10) for x in range(20)), 1)
        frames = [Image.new("RGB", (10, 10), c) for c in ("red", "blue")]
        g = self.dir / "anim.gif"
        frames[0].save(g, save_all=True, append_images=frames[1:])
        ld = ii.load(g)
        self.assertEqual(ld.info["frames"], 2)
        self.assertTrue(any("first frame" in w for w in ld.warnings))


if __name__ == "__main__":
    unittest.main(verbosity=1)
