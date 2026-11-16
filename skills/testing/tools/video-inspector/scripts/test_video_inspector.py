#!/usr/bin/env python3
"""Tests for video_inspector.py and mp4info.py. The MP4 metadata tests use only the standard library
(hand-built MP4 boxes); the frame tests generate a video with OpenCV and are skipped without it.
Run: python -m unittest discover -s scripts -p "test_*.py" """

import argparse
import csv
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mp4info  # noqa: E402
import video_inspector as vi  # noqa: E402

try:
    import cv2
    import numpy as np
    HAVE_CV = True
except ImportError:
    HAVE_CV = False


def box(kind, payload=b""):
    return struct.pack(">I", 8 + len(payload)) + kind + payload


def fake_mp4(rotation=0, with_audio=True, gps=b"+52.5200+013.4050/", moov_last=True, fps=25, seconds=4,
             with_video=True, movie_seconds=None):
    ts = 1000
    frames = fps * seconds
    mat = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}[rotation]
    tkhd = (b"\0\0\0\x03" + struct.pack(">IIIII", 0, 0, 1, 0, seconds * ts) + b"\0" * 16
            + struct.pack(">ii", mat[0] << 16, mat[1] << 16) + b"\0" * 28 + struct.pack(">II", 1280 << 16, 720 << 16))
    lang = (ord("e") - 0x60) << 10 | (ord("n") - 0x60) << 5 | (ord("g") - 0x60)

    def mdhd(scale, dur):
        return box(b"mdhd", b"\0" * 4 + struct.pack(">IIIIHH", 0, 0, scale, dur, lang, 0))

    def hdlr(h):
        return box(b"hdlr", b"\0" * 8 + h + b"\0" * 12 + b"handler\0")

    v_stsd = box(b"stsd", b"\0" * 4 + struct.pack(">I", 1) + box(b"avc1", b"\0" * 70))
    v_stbl = box(b"stbl", v_stsd + box(b"stts", b"\0" * 4 + struct.pack(">III", 1, frames, ts // fps))
                 + box(b"stsz", b"\0" * 4 + struct.pack(">II", 5000, frames)))
    video = box(b"trak", box(b"tkhd", tkhd) + box(b"mdia", mdhd(ts, seconds * ts) + hdlr(b"vide")
                                                  + box(b"minf", v_stbl)))
    traks = video if with_video else b""
    if with_audio:
        entry = b"\0" * 6 + struct.pack(">H", 1) + b"\0" * 8 + struct.pack(">HHHHI", 2, 16, 0, 0, 48000 << 16)
        a_stbl = box(b"stbl", box(b"stsd", b"\0" * 4 + struct.pack(">I", 1) + box(b"mp4a", entry))
                     + box(b"stts", b"\0" * 4 + struct.pack(">III", 1, 100, 1024)))
        traks += box(b"trak", box(b"mdia", mdhd(48000, seconds * 48000) + hdlr(b"soun") + box(b"minf", a_stbl)))
    mvhd = box(b"mvhd", b"\0" * 4 + struct.pack(">IIII", 3_800_000_000, 0, ts, int((movie_seconds or seconds) * ts)) + b"\0" * 80)
    udta = box(b"udta", box(b"\xa9xyz", struct.pack(">HH", len(gps), 0x15c7) + gps)) if gps else b""
    moov = box(b"moov", mvhd + traks + udta)
    parts = [box(b"ftyp", b"isom\0\0\x02\0isomiso2"), box(b"mdat", b"\0" * 4000)]
    return b"".join(parts + [moov] if moov_last else parts[:1] + [moov] + parts[1:])


def opts(**kw):
    base = dict(start=None, end=None, at=None, every_frame=False, frames=None, every=1.0, max_frames=300)
    base.update(kw)
    return argparse.Namespace(**base)


class TempDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args, no_cv=False):
        if no_cv:
            code = ("import sys; sys.modules['cv2'] = None; sys.path.insert(0, sys.argv[1]); "
                    "import video_inspector as v; sys.exit(v.main(sys.argv[2:]))")
            cmd = [sys.executable, "-c", code, str(HERE), *args]
        else:
            cmd = [sys.executable, str(HERE / "video_inspector.py"), *args]
        return subprocess.run(cmd, cwd=self.dir, capture_output=True, text=True, encoding="utf-8")


class Mp4InfoTests(TempDir):
    def test_tracks_rotation_audio_and_gps(self):
        p = self.dir / "phone.mp4"
        p.write_bytes(fake_mp4(rotation=90))
        info = mp4info.read(p)
        self.assertEqual((info["brand"], info["duration_s"], info["has_audio"]), ("isom", 4.0, True))
        self.assertEqual(info["creation_time"][:4], "2024")
        v, a = info["tracks"]
        self.assertEqual((v["type"], v["codec_name"], v["width"], v["height"], v["rotation"]),
                         ("video", "H.264 / AVC", 1280, 720, 90))
        self.assertEqual((v["frames"], v["fps"], v["variable_frame_rate"], v["language"]), (100, 25.0, False, "eng"))
        self.assertEqual(v["bitrate_kbps"], 1000.0)
        self.assertEqual((a["type"], a["codec_name"], a["channels"], a["sample_rate"]), ("audio", "AAC", 2, 48000))
        self.assertTrue(info["has_gps_location"])
        self.assertNotIn("gps", info)
        self.assertEqual(mp4info.read(p, include_gps=True)["gps"], {"latitude": 52.52, "longitude": 13.405})

    def test_moov_first_and_no_audio(self):
        p = self.dir / "a.mp4"
        p.write_bytes(fake_mp4(with_audio=False, gps=None, moov_last=False))
        info = mp4info.read(p)
        self.assertFalse(info["has_audio"])
        self.assertNotIn("has_gps_location", info)
        self.assertEqual(len(info["tracks"]), 1)

    def test_errors(self):
        (self.dir / "cut.mp4").write_bytes(box(b"ftyp", b"isom\0\0\0\0") + box(b"mdat", b"\0" * 100))
        with self.assertRaises(mp4info.Mp4Error) as cm:
            mp4info.read(self.dir / "cut.mp4")
        self.assertIn("incomplete", str(cm.exception))
        (self.dir / "x.mp4").write_bytes(b"GIF89a" + b"\0" * 64)
        with self.assertRaises(mp4info.Mp4Error):
            mp4info.read(self.dir / "x.mp4")


class HelperTests(unittest.TestCase):
    def test_parse_time(self):
        for text, want in (("12", 12), ("12.5s", 12.5), ("1:02", 62), ("0:01:02.5", 62.5), ("50%", 30),
                           ("250ms", 0.25)):
            self.assertAlmostEqual(vi.parse_time(text, 60), want)
        for bad in ("abc", "1:2:3:4", "-5"):
            with self.assertRaises(vi.VideoError):
                vi.parse_time(bad, 60)

    def test_choose_targets(self):
        w = []
        self.assertEqual(vi.choose_targets(opts(), 10, 80, 8.0, w), list(range(0, 80, 10)))
        self.assertEqual(vi.choose_targets(opts(frames=4), 10, 80, 8.0, w), [10, 30, 50, 70])
        self.assertEqual(vi.choose_targets(opts(at=["0:01,50%", "9"]), 10, 80, 8.0, w), [10, 40, 79])
        self.assertIn("after the end", w[-1])
        self.assertEqual(vi.choose_targets(opts(every_frame=True, start="2", end="2.5"), 10, 80, 8.0, w),
                         [20, 21, 22, 23, 24])
        w = []
        t = vi.choose_targets(opts(every=0.1, max_frames=20), 10, 800, 80.0, w)
        self.assertEqual(len(t), 20)
        self.assertIn("--max-frames", w[0])
        with self.assertRaises(vi.VideoError):
            vi.choose_targets(opts(start="5", end="4"), 10, 80, 8.0, [])

    def test_colour_runs_and_runs(self):
        r = vi.colour_runs([(0, (0, 0, 0)), (1, (3, 2, 1)), (2, (250, 220, 10)), (3, (0, 0, 0))])
        self.assertEqual([(x["name"], x["start"], x["end"]) for x in r],
                         [("black", 0, 1), ("yellow", 2, 2), ("black", 3, 3)])
        self.assertEqual(vi.runs([False, True, True, False, True]), [(1, 2), (4, 4)])


class NoOpenCvTests(TempDir):
    def test_info_works_and_analysis_explains(self):
        (self.dir / "clip.mp4").write_bytes(fake_mp4())
        p = self.cli("clip.mp4", "--info", no_cv=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        rep = json.loads((self.dir / "video-reports" / "clip" / "report.json").read_text(encoding="utf-8"))
        self.assertEqual((rep["video"]["width"], rep["video"]["fps"], rep["video"]["has_audio"]), (1280, 25.0, True))
        self.assertIn("1280x720 (landscape) H.264 / AVC video, 4.0 s at 25 fps (100 frames), with audio",
                      rep["description"])
        self.assertTrue(any("GPS" in w for w in rep["warnings"]))
        p = self.cli("clip.mp4", no_cv=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn("pip install opencv-python-headless", p.stderr)
        self.assertIn("--info", p.stderr)

    def test_audio_only_and_edit_list(self):
        (self.dir / "song.mp4").write_bytes(fake_mp4(with_video=False, gps=None))
        p = self.cli("song.mp4", "--info", "--stdout", no_cv=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        rep = json.loads(p.stdout)
        self.assertEqual(rep["description"], "song.mp4 has no video track (audio only), 4.0 s.")
        self.assertTrue(any("no video track" in w for w in rep["warnings"]))
        if HAVE_CV:                                     # used to hang; must now stop at once with a clear error
            p = self.cli("song.mp4")
            self.assertEqual(p.returncode, 2)
            self.assertIn("no video track", p.stderr)
        (self.dir / "cut.mp4").write_bytes(fake_mp4(gps=None, movie_seconds=2.5))
        rep = json.loads(self.cli("cut.mp4", "--info", "--stdout", no_cv=True).stdout)
        self.assertEqual((rep["video"]["duration_s"], rep["video"]["frames"]), (2.5, 62))
        self.assertTrue(any("edit list" in w for w in rep["warnings"]))

    def test_bad_inputs(self):
        (self.dir / "page.mp4").write_text("<!DOCTYPE html><html></html>")
        p = self.cli("page.mp4", "--info")
        self.assertEqual(p.returncode, 2)
        self.assertIn("HTML page", p.stderr)
        self.assertIn("only one of", self.cli("x.mp4", "--frames", "3", "--every-frame").stderr)
        (self.dir / "empty").mkdir()
        self.assertIn("no video files", self.cli("empty").stderr)


@unittest.skipUnless(HAVE_CV, "OpenCV not installed (pip install opencv-python-headless)")
class VideoTests(TempDir):
    """8 s at 10 fps: 0-2 s black, 2-4 s red, 4-6 s white with a moving blue square, 6-8 s static green.
    A yellow 'LED' at (5..15, 5..15) is on from 2 s to 5 s."""

    def setUp(self):
        super().setUp()
        w = cv2.VideoWriter(str(self.dir / "demo.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 10, (160, 120))
        for i in range(80):
            t = i / 10
            if t < 2:
                f = np.zeros((120, 160, 3), np.uint8)
            elif t < 4:
                f = np.full((120, 160, 3), (30, 30, 220), np.uint8)
            elif t < 6:
                f = np.full((120, 160, 3), 255, np.uint8)
                x = int((t - 4) * 60)
                cv2.rectangle(f, (x, 40), (x + 30, 70), (220, 80, 30), -1)
            else:
                f = np.full((120, 160, 3), (50, 160, 30), np.uint8)
            if 2 <= t < 5:
                cv2.rectangle(f, (5, 5), (15, 15), (0, 220, 250), -1)
            w.write(f)
        w.release()

    def report(self, out="video-reports"):
        return json.loads((self.dir / out / "demo" / "report.json").read_text(encoding="utf-8"))

    def test_scenes_black_static_and_led(self):
        p = self.cli("demo.mp4", "--every", "0.5", "--pixel", "10,10", "--region", "0,0,160,30")
        self.assertEqual(p.returncode, 0, p.stderr)
        rep = self.report()
        self.assertEqual([s["start"] for s in rep["scenes"]], [0.0, 2.0, 4.0, 6.0])
        self.assertEqual([s["description"].split("mostly ")[-1].split(",")[0] for s in rep["scenes"]],
                         ["black", "red", "white", "green"])
        self.assertEqual([(b["start"], b["end"]) for b in rep["black_segments"]], [(0.0, 2.0)])
        self.assertEqual([s["start"] for s in rep["frozen_segments"]], [2.0, 6.0])
        led = rep["tracks"][0]["runs"]
        self.assertEqual([(r["name"], r["start"]) for r in led],
                         [("black", 0.0), ("yellow", 2.0), ("white", 5.0), ("green", 6.0)])
        frames = sorted(os.listdir(self.dir / "video-reports" / "demo" / "frames"))
        self.assertEqual(frames, ["frame_000000_00000.000s.png", "frame_000020_00002.000s.png",
                                  "frame_000040_00004.000s.png", "frame_000060_00006.000s.png"])
        self.assertEqual(rep["scenes"][2]["key_frame_image"], str(Path("frames") / frames[2]))
        with open(self.dir / "video-reports" / "demo" / "timeline.csv", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 16)
        self.assertEqual(rows[4]["scene_change"], "1")
        tracks = (self.dir / "video-reports" / "demo" / "tracks.csv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(tracks), 1 + 16 * 2)
        txt = (self.dir / "video-reports" / "demo" / "report.txt").read_text(encoding="utf-8")
        self.assertIn("4 scenes", txt)
        self.assertIn("Black screen: 0:00.0-0:02.0", txt)
        self.assertIn("SCENE CHANGE", txt)

    def test_one_frame_in_depth(self):
        p = self.cli("demo.mp4", "--at", "4.5", "--save-frames", "--grid", "8", "--pixels-csv")
        self.assertEqual(p.returncode, 0, p.stderr)
        rep = self.report()
        f = rep["frames"][0]
        self.assertEqual((f["frame"], f["image"]), (45, str(Path("frames") / "frame_000045_00004.500s.png")))
        self.assertEqual((f["pixel_map"]["columns"], f["pixel_map"]["rows"]), (8, 6))
        rows = (self.dir / "video-reports" / "demo" / f["pixels_csv"]).read_text().splitlines()
        self.assertEqual(rows[0], "x,y,r,g,b")
        self.assertEqual(len(rows), 1 + 160 * 120)
        x, y, r, g, b = map(int, rows[1 + 10 * 160 + 10].split(","))
        self.assertEqual((x, y), (10, 10))
        self.assertTrue(r > 200 and g > 180 and b < 60, (r, g, b))          # the yellow LED

    def test_every_frame_range_frames_mode_and_stdout(self):
        p = self.cli("demo.mp4", "--every-frame", "--start", "4", "--end", "4.5", "--no-frames")
        self.assertEqual(p.returncode, 0, p.stderr)
        rep = self.report()
        self.assertEqual([f["frame"] for f in rep["frames"]], [40, 41, 42, 43, 44])
        self.assertFalse((self.dir / "video-reports" / "demo" / "frames").exists())
        p = self.cli("demo.mp4", "--frames", "4", "--stdout")
        rep = json.loads(p.stdout)
        self.assertEqual([f["frame"] for f in rep["frames"]], [10, 30, 50, 70])
        self.assertFalse((self.dir / "video-reports").exists() and
                         (self.dir / "video-reports" / "demo" / "frames").exists())

    def test_pixel_outside_frame(self):
        p = self.cli("demo.mp4", "--pixel", "500,10")
        self.assertEqual(p.returncode, 2)
        self.assertIn("outside the frame (160x120)", p.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
