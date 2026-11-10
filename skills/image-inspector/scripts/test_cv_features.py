#!/usr/bin/env python3
"""Tests for the OpenCV features (--find, --compare, sharpness). Skipped when OpenCV is not installed."""

import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cv_features as cvf  # noqa: E402
import inspect_image as ii  # noqa: E402
from test_inspect_image import make_png  # noqa: E402

HAVE_CV = cvf.available()


def icon(x, y):
    """24x24 test icon: a filled diamond in green with a white dot, transparent corners."""
    d = abs(x - 12) + abs(y - 12)
    if d > 11:
        return (0, 0, 0, 0)
    if abs(x - 12) <= 2 and abs(y - 12) <= 2:
        return (255, 255, 255, 255)
    return (40, 160, 70, 255)


def scene_pixel(x, y, spots, bg, scale=1.0):
    for sx, sy in spots:
        ix, iy = int((x - sx) / scale), int((y - sy) / scale)
        if 0 <= ix < 24 and 0 <= iy < 24 and x >= sx and y >= sy:
            p = icon(ix, iy)
            if p[3]:
                return p[:3]
    return bg(x, y)


def as_raster(w, h, f, mode="RGB"):
    data = bytearray()
    for y in range(h):
        for x in range(w):
            data += bytes(f(x, y)[:ii.Raster.CHANNELS[mode]])
    return ii.Raster(w, h, mode, data)


@unittest.skipUnless(HAVE_CV, "OpenCV not installed (pip install opencv-python-headless)")
class FindTests(unittest.TestCase):
    def setUp(self):
        rnd = random.Random(7)
        noise = [[(200 + rnd.randrange(30), 200 + rnd.randrange(30), 210 + rnd.randrange(30)) for _ in range(200)]
                 for _ in range(120)]
        self.bg = lambda x, y: noise[y][x]
        self.tpl = as_raster(24, 24, icon, "RGBA")

    def test_finds_every_copy_with_transparent_corners(self):
        spots = [(10, 10), (150, 20), (60, 80)]
        scene = as_raster(200, 120, lambda x, y: scene_pixel(x, y, spots, self.bg))
        matches, warns = cvf.find_template(scene, self.tpl)
        self.assertEqual(warns, [])
        self.assertEqual([(m["x"], m["y"]) for m in matches], [(10, 10), (150, 20), (60, 80)])
        self.assertEqual(matches[0]["center"], [22, 22])
        self.assertGreater(matches[0]["score"], 0.95)

    def test_not_found_and_colour_matters(self):
        scene = as_raster(200, 120, self.bg)
        self.assertEqual(cvf.find_template(scene, self.tpl)[0], [])
        red = as_raster(24, 24, lambda x, y: (220, 30, 30, 255) if icon(x, y)[3] and icon(x, y)[0] != 255
                        else icon(x, y), "RGBA")
        scene = as_raster(200, 120, lambda x, y: scene_pixel(x, y, [(40, 40)], self.bg))
        found = cvf.find_template(scene, red, threshold=0.9)[0]
        self.assertEqual(found, [], "a red icon must not match the green one")

    def test_other_scale(self):
        scene = as_raster(200, 120, lambda x, y: scene_pixel(x, y, [(50, 30)], self.bg, scale=1.5))
        self.assertEqual(cvf.find_template(scene, self.tpl, threshold=0.85)[0], [])
        m = cvf.find_template(scene, self.tpl, threshold=0.75, scales=(1.0, 1.5))[0]
        self.assertEqual(len(m), 1)
        self.assertEqual((m[0]["scale"], abs(m[0]["x"] - 50) <= 2, abs(m[0]["y"] - 30) <= 2), (1.5, True, True))

    def test_flat_template_warns(self):
        flat = as_raster(10, 10, lambda x, y: (255, 255, 255, 255), "RGBA")
        scene = as_raster(60, 40, lambda x, y: (255, 255, 255) if x < 30 else (0, 0, 0))
        matches, warns = cvf.find_template(scene, flat, max_matches=3)
        self.assertTrue(warns and "flat colour" in warns[0])
        self.assertTrue(all(m["x"] + 10 <= 30 for m in matches))


@unittest.skipUnless(HAVE_CV, "OpenCV not installed (pip install opencv-python-headless)")
class CompareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_identical_and_changes(self):
        base = lambda x, y: (240, 240, 240)  # noqa: E731
        a = as_raster(100, 60, base)
        res, warns = cvf.compare(a, as_raster(100, 60, base))
        self.assertTrue(res["identical"])
        self.assertEqual((res["changed_pixels"], res["changed_regions"], warns), (0, [], []))
        b = as_raster(100, 60, lambda x, y: (20, 20, 200) if 10 <= x < 30 and 5 <= y < 15 else
                      ((0, 0, 0) if 70 <= x < 90 and 40 <= y < 50 else base(x, y)))
        res, _ = cvf.compare(b, a, diff_path=self.dir / "d.png")
        self.assertFalse(res["identical"])
        self.assertEqual(res["changed_pixels"], 400)
        boxes = sorted((r["x"], r["y"], r["width"], r["height"]) for r in res["changed_regions"])
        self.assertEqual(boxes, [(10, 5, 20, 10), (70, 40, 20, 10)])
        self.assertTrue((self.dir / "d.png").is_file())
        res, _ = cvf.compare(b, a, ignore=[(60, 30, 40, 30)])
        self.assertEqual([(r["x"], r["y"]) for r in res["changed_regions"]], [(10, 5)])
        self.assertEqual(res["ignored_regions"], [{"x": 60, "y": 30, "width": 40, "height": 30}])

    def test_small_differences_below_threshold_and_size_mismatch(self):
        a = as_raster(50, 50, lambda x, y: (100, 100, 100))
        b = as_raster(50, 50, lambda x, y: (110, 100, 100))      # JPEG-noise sized difference
        res, _ = cvf.compare(a, b)
        self.assertEqual((res["changed_pixels"], res["max_difference"], res["identical"]), (0, 10, False))
        res, warns = cvf.compare(a, as_raster(100, 100, lambda x, y: (100, 100, 100)))
        self.assertTrue(res["size_mismatch"])
        self.assertIn("different sizes", warns[0])

    def test_sharpness(self):
        rnd = random.Random(1)
        sharp = cvf.sharpness(as_raster(80, 80, lambda x, y: (rnd.randrange(256),) * 3))
        flat = cvf.sharpness(as_raster(80, 80, lambda x, y: (128, 128, 128)))
        self.assertEqual((sharp["level"], flat["level"]), ("sharp", "blurry"))


@unittest.skipUnless(HAVE_CV, "OpenCV not installed (pip install opencv-python-headless)")
class CvCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(HERE / "inspect_image.py"), *args], cwd=self.dir,
                              capture_output=True, text=True, encoding="utf-8")

    def test_find_compare_folder_and_fail_on_diff(self):
        rnd = random.Random(2)
        noise = [[(rnd.randrange(256), 120, 180) for _ in range(90)] for _ in range(70)]
        bg = lambda x, y: noise[y][x]  # noqa: E731
        (self.dir / "base").mkdir()
        (self.dir / "new").mkdir()
        (self.dir / "icon.png").write_bytes(make_png(24, 24, icon, 6, 8))
        (self.dir / "base" / "home.png").write_bytes(make_png(90, 70, lambda x, y: scene_pixel(x, y, [(5, 5)], bg), 2, 8))
        (self.dir / "new" / "home.png").write_bytes(
            make_png(90, 70, lambda x, y: scene_pixel(x, y, [(5, 5), (50, 30)], bg), 2, 8))
        p = self.cli("new", "--find", "icon.png", "--compare", "base", "--fail-on-diff", "1")
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        rep = json.loads((self.dir / "image-reports" / "home.json").read_text(encoding="utf-8"))
        self.assertEqual([(m["x"], m["y"]) for m in rep["find"][0]["matches"]], [(5, 5), (50, 30)])
        self.assertEqual(rep["comparison"]["reference"], str(Path("base") / "home.png"))
        r = rep["comparison"]["changed_regions"][0]
        self.assertTrue(50 <= r["x"] and r["x"] + r["width"] <= 74, r)
        self.assertTrue((self.dir / "image-reports" / "home.diff.png").is_file())
        self.assertIn("icon.png found 2 time(s)", rep["description"])
        p = self.cli("new", "--compare", "base", "--ignore", "45,25,40,40", "--fail-on-diff", "1", "--out", "o2")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_bad_options(self):
        (self.dir / "a.png").write_bytes(make_png(4, 4, lambda x, y: (1, 2, 3), 2, 8))
        self.assertIn("--scales", self.cli("a.png", "--find", "a.png", "--scales", "x").stderr)
        self.assertIn("--ignore", self.cli("a.png", "--compare", "a.png", "--ignore", "1,2").stderr)
        p = self.cli("a.png", "--find", "missing.png")
        self.assertEqual(p.returncode, 2)
        self.assertIn("template missing.png", p.stderr)


class WithoutOpenCvTests(unittest.TestCase):
    def test_clear_error_when_opencv_missing(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.png").write_bytes(make_png(4, 4, lambda x, y: (1, 2, 3), 2, 8))
            code = ("import sys; sys.modules['cv2'] = None; sys.path.insert(0, sys.argv[1]); "
                    "import inspect_image; sys.exit(inspect_image.main(['a.png', '--compare', 'a.png']))")
            p = subprocess.run([sys.executable, "-c", code, str(HERE)], cwd=d, capture_output=True, text=True)
            self.assertEqual(p.returncode, 2)
            self.assertIn("pip install opencv-python-headless", p.stderr)
            code = code.replace("['a.png', '--compare', 'a.png']", "['a.png']")
            p = subprocess.run([sys.executable, "-c", code, str(HERE)], cwd=d, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            rep = json.loads(Path(d, "image-reports", "a.json").read_text(encoding="utf-8"))
            self.assertNotIn("sharpness", rep["texture"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
