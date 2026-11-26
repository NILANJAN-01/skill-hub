#!/usr/bin/env python3
"""Tests for image_codecs.py. The fixtures were written by Pillow, and fixtures/codecs_expected.json holds the
SHA-256 of the pixels Pillow decodes from them, so these tests prove the pure-Python decoders give the same
pixels, without needing Pillow."""

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import image_codecs as ic  # noqa: E402
import inspect_image as ii  # noqa: E402

FIX = HERE / "fixtures"
EXPECTED = json.loads((FIX / "codecs_expected.json").read_text(encoding="utf-8"))


class SameAsPillow(unittest.TestCase):
    def test_every_fixture_decodes_to_pillows_pixels(self):
        for name, exp in EXPECTED.items():
            with self.subTest(name):
                ld = ii.load(FIX / name, use_pillow=False)
                r = ld.raster
                self.assertEqual([r.width, r.height], exp["size"])
                self.assertEqual(r.mode, exp["mode"])
                self.assertEqual(hashlib.sha256(bytes(r.data[:r.width * r.height * r.channels])).hexdigest(),
                                 exp["sha256"])
                self.assertEqual(ld.backend, "standard library")


class Metadata(unittest.TestCase):
    def test_exif_orientation_and_gps(self):
        ld = ii.load(FIX / "exif_rot6.jpg", use_pillow=False)
        self.assertEqual((ld.width, ld.height), (23, 37))
        self.assertTrue(ld.info["exif_orientation_applied"])
        self.assertEqual(ld.info["exif"]["make"], "TestCam")
        self.assertNotIn("gps", ld.info["exif"])
        self.assertTrue(any("GPS" in w for w in ld.warnings))
        gps = ii.load(FIX / "exif_rot6.jpg", use_pillow=False, include_gps=True).info["exif"]["gps"]
        self.assertAlmostEqual(gps["latitude"], 52.52, places=2)
        self.assertAlmostEqual(gps["longitude"], 13.4, places=2)

    def test_frames_modes_and_progressive_flag(self):
        anim = ii.load(FIX / "anim.gif", use_pillow=False)
        self.assertEqual(anim.info["frames"], 2)
        self.assertTrue(any("first frame" in w for w in anim.warnings))
        self.assertEqual(ii.load(FIX / "gray16.tif", use_pillow=False).info["mode"], "I;16")
        self.assertTrue(ic.decode_jpeg((FIX / "progressive_444.jpg").read_bytes())[4]["progressive"])
        self.assertTrue(ii.load(FIX / "interlaced_transparent.gif", use_pillow=False).info["has_alpha"])

    def test_exif_parser_rationals_and_strings(self):
        e = "<"
        entries = [(0x010F, 2, 4, b"Cam\x00"), (0x011A, 5, 1, struct.pack(e + "II", 300, 1))]
        data_off = 8 + 2 + 12 * len(entries) + 4
        body, extra = b"", b""
        for tag, typ, count, val in entries:
            if len(val) <= 4:
                body += struct.pack(e + "HHI", tag, typ, count) + val.ljust(4, b"\x00")
            else:
                body += struct.pack(e + "HHII", tag, typ, count, data_off + len(extra))
                extra += val
        blob = b"II*\x00" + struct.pack(e + "I", 8) + struct.pack(e + "H", len(entries)) + body + b"\x00" * 4 + extra
        ex = ic.parse_exif(blob)
        self.assertEqual(ex["ifd0"][0x010F], "Cam")
        self.assertEqual(ex["ifd0"][0x011A], 300.0)


class Helpers(unittest.TestCase):
    def test_orientation_transforms(self):
        # 2x3 image, pixel value = index; check the eight EXIF orientations against PIL's definitions
        w, h = 2, 3
        data = bytearray(range(6))
        expect = {2: (2, 3, [1, 0, 3, 2, 5, 4]), 3: (2, 3, [5, 4, 3, 2, 1, 0]), 4: (2, 3, [4, 5, 2, 3, 0, 1]),
                  5: (3, 2, [0, 2, 4, 1, 3, 5]), 6: (3, 2, [4, 2, 0, 5, 3, 1]), 7: (3, 2, [5, 3, 1, 4, 2, 0]),
                  8: (3, 2, [1, 3, 5, 0, 2, 4])}
        for o, (ew, eh, px) in expect.items():
            with self.subTest(orientation=o):
                nw, nh, out = ic.orient(w, h, 1, data, o)
                self.assertEqual((nw, nh, list(out)), (ew, eh, px))

    def test_png_writer_round_trip(self):
        data = bytearray(range(4 * 3 * 2))
        blob = ic.encode_png(4, 2, "RGB", data)
        r = ii.decode_png(blob)
        self.assertEqual((r.width, r.height, r.mode, bytes(r.data)), (4, 2, "RGB", bytes(data)))

    def test_unsupported_jpeg_is_a_codec_error(self):
        blob = bytearray((FIX / "gray.jpg").read_bytes())
        i = blob.find(b"\xff\xc0")
        blob[i + 1] = 0xC9                                   # pretend it is arithmetic-coded
        with self.assertRaises(ic.CodecError):
            ic.decode_jpeg(bytes(blob))


if __name__ == "__main__":
    unittest.main()
