"""Offline tests for yt-lecture-overview (no network: YouTube responses come from fixtures/)."""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import yt_audio as ya  # noqa: E402
import yt_html as yh  # noqa: E402
import yt_lecture as yl  # noqa: E402
import yt_lecture_mcp as mcp  # noqa: E402
import yt_slides as ys  # noqa: E402
from yt_guardrail import LinkError, classify_title, parse_youtube_url  # noqa: E402

FIX = HERE / "fixtures"


def fake_get(url, data=None, headers=None, timeout=25):
    if "/watch?v=abcDEF12345" in url:
        return (FIX / "watch_lecture.html").read_text(encoding="utf-8")
    if "/watch?v=musicVID001" in url:
        return (FIX / "watch_music.html").read_text(encoding="utf-8")
    if "/youtubei/v1/player" in url:
        return (FIX / "innertube_player.json").read_text(encoding="utf-8")
    if "/api/timedtext" in url:
        return (FIX / "captions.json3").read_text(encoding="utf-8")
    raise yl.FetchError(f"unexpected URL in test: {url}")


AUDIO_REPORT = {
    "audio": {"file": "audio.m4a", "format": "m4a", "size_bytes": 18126659, "codec": "aac", "sample_rate": 44100,
              "channels": 2, "bitrate_kbps": 129, "duration": 600.0, "clip": [0, None]},
    "analysis": {"analysed_seconds": 600.0, "speech_seconds": 480.0, "speech_ratio": 0.8, "mean_dbfs": -26.0,
                 "pause_count": 2, "longest_pause": 6.5, "pauses": [{"start": 250.0, "length": 6.5},
                                                                    {"start": 400.0, "length": 2.5}],
                 "speech_per_minute": [0.9, 0.8, 0.7, 0.9, 0.2, 0.9, 0.8, 0.9, 0.8, 0.9]},
    "transcript": {"engine": "vosk", "model": "small-en", "language": "en", "segments": [
        {"start": 1.0, "end": 9.0, "text": "welcome to lecture three on graph algorithms"},
        {"start": 125.0, "end": 140.0, "text": "breadth first search explores the graph level by level using a queue"},
        {"start": 305.0, "end": 320.0, "text": "depth first search goes deep first using a stack or recursion"}]},
    "errors": [],
}


SLIDE_TIMES = [(2.0, 60.0), (130.0, 200.0), (310.0, 400.0)]


class FakeRun:
    """Stands in for subprocess.run of yt_audio.py; records the command. With slides=True it also plays the
    slide stage: writes one small file per slide into --slides-dir and reports them."""
    def __init__(self, report, slides=False):
        self.report, self.cmds, self.slides = report, [], slides

    def __call__(self, cmd, **kwargs):
        self.cmds.append(cmd)
        report = dict(self.report)
        if self.slides and "--slides-dir" in cmd and "fatal" not in report:
            folder = Path(cmd[cmd.index("--slides-dir") + 1])
            folder.mkdir(parents=True, exist_ok=True)
            items = []
            for i, (start, end) in enumerate(SLIDE_TIMES, 1):
                (folder / f"slide-{i:03d}.jpg").write_bytes(b"\xff\xd8fake-jpeg-%d" % i)
                items.append({"file": f"slide-{i:03d}.jpg", "start": start, "end": end, "shown_again": []})
            report["slides"] = {"count": len(items), "slides": items, "camera_shots_skipped": 1}
            if "--no-audio" in cmd:
                report = {"errors": [], "slides": report["slides"]}

        class P:
            returncode = 0
            stderr = ""
        P.stdout = json.dumps(report)
        return P


class LinkTests(unittest.TestCase):
    def test_accepted_forms(self):
        for url in ["https://www.youtube.com/watch?v=abcDEF12345", "http://youtube.com/watch?v=abcDEF12345&t=1m5s",
                    "https://m.youtube.com/watch?feature=share&v=abcDEF12345", "https://youtu.be/abcDEF12345?si=x",
                    "https://www.youtube.com/shorts/abcDEF12345", "https://www.youtube.com/embed/abcDEF12345",
                    "https://www.youtube.com/live/abcDEF12345", "www.youtube.com/watch?v=abcDEF12345",
                    "https://www.youtube.com/watch?v=abcDEF12345&list=PL123"]:
            self.assertEqual(parse_youtube_url(url)["video_id"], "abcDEF12345", url)
        self.assertEqual(parse_youtube_url("https://youtu.be/abcDEF12345?t=65")["start"], 65)
        self.assertEqual(parse_youtube_url("https://youtube.com/watch?v=abcDEF12345&t=1m5s")["start"], 65)

    def test_rejected(self):
        for url in ["", "hello", "https://youtube.com.evil.com/watch?v=abcDEF12345",
                    "https://evilyoutube.com/watch?v=abcDEF12345", "https://vimeo.com/123",
                    "https://www.youtube.com/playlist?list=PL123", "https://www.youtube.com/watch?list=PL123",
                    "https://www.youtube.com/@somechannel", "https://www.youtube.com/watch?v=short",
                    "ftp://youtube.com/watch?v=abcDEF12345", "https://user:pw@youtube.com/watch?v=abcDEF12345",
                    "javascript:alert(1)"]:
            with self.assertRaises(LinkError, msg=url):
                parse_youtube_url(url)


class GuardrailTests(unittest.TestCase):
    def test_allows_study_and_tech(self):
        for title, cat in [("But what is a neural network? | Deep learning chapter 1", "Education"),
                           ("MIT 6.006 Lecture 1: Algorithms and Computation", ""),
                           ("Git and GitHub for Beginners - Crash Course", ""),
                           ("Organic Chemistry one shot | NEET", ""), ("How does a CPU work?", ""),
                           ("Python in 100 Seconds", "Science & Technology"),
                           ("Music theory lecture for beginners", "Music"),
                           ("Design PasteBin | Systems Design Questions 3.0 With Ex-Google SWE", ""),
                           ("HLD of a URL shortener", ""), ("Designing distributed systems: caching", "")]:
            self.assertTrue(classify_title(title, cat)["allowed"], title)

    def test_blocks_entertainment_and_unclear(self):
        for title, cat in [("Rick Astley - Never Gonna Give You Up (Official Video)", "Music"),
                           ("Minecraft gameplay part 3", "Gaming"), ("Late night talk show funny moments", ""),
                           ("Python snake attack", "Pets & Animals"), ("What is the best phone 2026", ""),
                           ("Taylor Swift drama explained", ""), ("", "Education"),
                           ("My trip to Goa", "Education")]:
            self.assertFalse(classify_title(title, cat)["allowed"], title)

    def test_category_alone_cannot_pass(self):
        r = classify_title("Weekend thoughts", "Education", ["lecture", "physics"])
        self.assertFalse(r["allowed"])
        self.assertEqual(r["matched"]["metadata_bonus"], 0)


class ParseTests(unittest.TestCase):
    def test_chapters(self):
        ch = yl.parse_chapters("intro\n0:00 Start\n1:30 - Middle part\n(1:02:03) End\n")
        self.assertEqual([c["start"] for c in ch], [0, 90, 3723])
        self.assertEqual(ch[1]["title"], "Middle part")
        self.assertEqual(yl.parse_chapters("1:00 a\n2:00 b\n3:00 c"), [])  # must start at 0:00

    def test_json3_and_cleaning(self):
        segs = yl.clean_segments(yl.parse_json3((FIX / "captions.json3").read_text(encoding="utf-8")))
        self.assertTrue(segs[0]["text"].startswith("Welcome"))  # [Music] removed
        self.assertNotIn("[Music]", " ".join(s["text"] for s in segs))

    def test_rolling_vtt_overlap_removed(self):
        segs = yl.clean_segments(yl.load_transcript_file(FIX / "rolling.vtt"))
        text = " ".join(s["text"] for s in segs)
        self.assertEqual(text, "so today we learn about binary trees and heaps")
        self.assertAlmostEqual(segs[-1]["end"], 7.5)

    def test_pick_track_prefers_human(self):
        tracks = [{"lang": "en", "kind": "asr", "base_url": "a"}, {"lang": "en", "kind": "", "base_url": "b"},
                  {"lang": "fr", "kind": "", "base_url": "c"}]
        self.assertEqual(yl.pick_track(tracks, "en")["base_url"], "b")
        self.assertEqual(yl.pick_track(tracks, "de")["base_url"], "b")
        self.assertIsNone(yl.pick_track([], "en"))

    def test_http_get_refuses_other_hosts(self):
        with self.assertRaises(yl.FetchError):
            yl.http_get("https://example.com/x")


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_fetch_writes_text_and_html(self):
        res = yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, source="captions", slides=False)
        folder = Path(res["folder"])
        for name in ("info.json", "transcript.json", "transcript.txt", "notes.json", "overview.md", "overview.html"):
            self.assertTrue((folder / name).is_file(), name)
        self.assertTrue(res["transcript_source"].startswith("youtube-captions:en (uploaded)"))
        page = (folder / "overview.html").read_text(encoding="utf-8")
        self.assertNotIn("<script>alert(1)</script>", page)  # title escaped
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("Breadth-first search", page)  # chapter title
        self.assertIn("Automatic draft", page)
        notes = json.loads((folder / "notes.json").read_text(encoding="utf-8"))
        self.assertEqual([s["start"] for s in notes["sections"]], [0, 120, 300])
        self.assertIn("[0:05] Welcome", (folder / "transcript.txt").read_text(encoding="utf-8"))

    def test_agent_notes_kept_on_refetch_and_render(self):
        res = yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, source="captions", slides=False)
        folder = Path(res["folder"])
        notes = json.loads((folder / "notes.json").read_text(encoding="utf-8"))
        notes.update(written_by="agent", summary="BFS uses a queue; DFS uses a stack.")
        yl.write_json(folder / "notes.json", notes)
        yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, source="captions", slides=False)
        md = (folder / "overview.md").read_text(encoding="utf-8")
        self.assertIn("BFS uses a queue", md)
        self.assertNotIn("Automatic draft", md)

    def test_blocked_video_writes_nothing(self):
        with self.assertRaises(yl.Blocked):
            yl.fetch("https://www.youtube.com/watch?v=musicVID001", self.tmp, get=fake_get, source="captions",
                     slides=False)
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_render_refuses_unchecked_folder(self):
        res = yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, source="captions", slides=False)
        folder = Path(res["folder"])
        info = json.loads((folder / "info.json").read_text(encoding="utf-8"))
        info["guardrail"]["allowed"] = False
        yl.write_json(folder / "info.json", info)
        with self.assertRaises(yl.Blocked):
            yl.render(folder)

    def test_transcript_file_used(self):
        res = yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, source="captions", slides=False,
                       transcript_file=str(FIX / "rolling.vtt"))
        self.assertEqual(res["transcript_source"], "file:rolling.vtt")

    def test_no_transcript_gives_clear_error(self):
        def no_captions(url, data=None, headers=None, timeout=25):
            if "/youtubei/" in url:
                return "{}"
            return fake_get(url, data, headers, timeout)
        orig = yl.ytdlp_command
        yl.ytdlp_command = lambda: None
        try:
            with self.assertRaises(yl.FetchError) as ctx:
                yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=no_captions, source="captions",
                         slides=False)
        finally:
            yl.ytdlp_command = orig
        self.assertIn("--transcript", str(ctx.exception))


class AudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_audio_is_the_default_source(self):
        run = FakeRun(AUDIO_REPORT)
        res = yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, runner=run)
        self.assertEqual(res["transcript_source"], "audio-speech-to-text (vosk small-en)")
        self.assertTrue(res["audio_processed"])
        cmd = run.cmds[0]
        self.assertIn("process", cmd)
        self.assertEqual(cmd[cmd.index("--url") + 1], "https://www.youtube.com/watch?v=abcDEF12345")
        folder = Path(res["folder"])
        page = (folder / "overview.html").read_text(encoding="utf-8")
        for text in ("About the audio", "How much of each minute is speech", "80%", "Longest pauses",
                     "words per minute", "Show the numbers as a table", "Outline"):
            self.assertIn(text, page)
        md = (folder / "overview.md").read_text(encoding="utf-8")
        self.assertIn("## About the audio", md)
        self.assertIn("&t=250s): 6.5 s", md)
        info = json.loads((folder / "info.json").read_text(encoding="utf-8"))
        self.assertEqual(info["audio"]["speech_to_text"]["engine"], "vosk")

    def test_audio_failure_falls_back_to_captions_with_a_warning(self):
        res = yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get,
                       runner=FakeRun({"fatal": "yt-dlp is not installed in the audio Python"}))
        self.assertTrue(res["transcript_source"].startswith("youtube-captions"))
        self.assertTrue(any("audio not processed" in w for w in res["warnings"]))
        page = (Path(res["folder"]) / "overview.html").read_text(encoding="utf-8")
        self.assertIn("yt-dlp is not installed", page)

    def test_analysis_kept_when_speech_to_text_fails(self):
        rep = dict(AUDIO_REPORT, transcript=None, errors=["speech-to-text: no speech-to-text engine could run"])
        res = yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, runner=FakeRun(rep))
        self.assertTrue(res["transcript_source"].startswith("youtube-captions"))
        self.assertEqual(res["audio_summary"]["speech_ratio"], 0.8)

    def test_audio_only_never_uses_captions(self):
        with self.assertRaises(yl.FetchError):
            yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, source="audio-only",
                     runner=FakeRun({"fatal": "no engine"}))
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_clip_is_passed_and_applied_to_captions(self):
        run = FakeRun({"fatal": "offline"})
        res = yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, clip="2:00-5:00", runner=run)
        self.assertIn("2:00-5:00", run.cmds[0])
        segs = json.loads((Path(res["folder"]) / "transcript.json").read_text(encoding="utf-8"))
        self.assertTrue(segs and all(120 <= s["start"] < 300 for s in segs))
        self.assertIn("part processed", (Path(res["folder"]) / "overview.html").read_text(encoding="utf-8"))

    def test_bad_clip(self):
        with self.assertRaises(ValueError):
            yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, clip="5:00-2:00", runner=FakeRun({}))

    def test_blocked_video_never_reaches_the_audio_stage(self):
        run = FakeRun(AUDIO_REPORT)
        with self.assertRaises(yl.Blocked):
            yl.fetch("https://youtu.be/musicVID001", self.tmp, get=fake_get, runner=run)
        self.assertEqual(run.cmds, [])

    def test_parse_clip_and_levels(self):
        self.assertEqual(ya.parse_clip("10:00-25:00"), (600.0, 1500.0))
        self.assertEqual(ya.parse_clip("1:00:00-"), (3600.0, None))
        self.assertEqual(ya.parse_clip(""), (0.0, None))
        with self.assertRaises(ValueError):
            ya.parse_clip("abc")
        # 30 s speech, 5 s silence, 25 s speech (0.5 s windows)
        levels = [-20.0] * 60 + [-60.0] * 10 + [-22.0] * 50
        r = ya.analyse_levels(levels, start=100)
        self.assertEqual(r["pause_count"], 1)
        self.assertEqual(r["pauses"][0], {"start": 130.0, "length": 5.0})
        self.assertAlmostEqual(r["speech_ratio"], 110 / 120, places=2)
        self.assertEqual(len(r["speech_per_minute"]), 1)

    def test_engine_order_and_clear_error(self):
        orig = ya._try_import
        ya._try_import = lambda name: (None, "not installed")
        try:
            with self.assertRaises(RuntimeError) as ctx:
                ya.transcribe("x.m4a")
        finally:
            ya._try_import = orig
        msg = str(ctx.exception)
        for engine in ("faster-whisper", "whisper", "vosk"):
            self.assertIn(engine, msg)


class StudyPageTests(unittest.TestCase):
    """The study aids on overview.html: term locations, progress, quiz, search and chart marks."""
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_first_mention(self):
        segs = [{"start": 1, "text": "welcome to the lecture on gradient"}, {"start": 5, "text": "descent today"},
                {"start": 9, "text": "Breadth-First Searches use a queue"}, {"start": 20, "text": "breadth first search"}]
        self.assertEqual(yh.first_mention("gradient descent (GD)", segs), 1)      # split across two segments
        self.assertEqual(yh.first_mention("breadth first search", segs), 9)       # hyphens, case, plural
        self.assertEqual(yh.first_mention("descent", segs), 5)
        self.assertIsNone(yh.first_mention("lecture three", segs))               # must not borrow the next segment
        self.assertIsNone(yh.first_mention("heap", segs))
        self.assertIsNone(yh.first_mention("", segs))

    def test_study_aids_rendered(self):
        res = yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, runner=FakeRun(AUDIO_REPORT))
        folder = Path(res["folder"])
        notes = json.loads((folder / "notes.json").read_text(encoding="utf-8"))
        notes.update(written_by="agent",
                     terms=[{"term": "depth first search", "meaning": "go deep first"},
                            {"term": "<b>heap</b>", "meaning": "not said in this lecture"}],
                     review_questions=[{"q": "What does BFS use?", "a": "A queue."}])
        yl.write_json(folder / "notes.json", notes)
        yl.render(folder)
        page = (folder / "overview.html").read_text(encoding="utf-8")
        md = (folder / "overview.md").read_text(encoding="utf-8")
        self.assertIn('data-vid="abcDEF12345"', page)
        self.assertIn("first said at 5:05", page)                                 # 305 s in AUDIO_REPORT
        self.assertIn("(first said at [5:05](https://www.youtube.com/watch?v=abcDEF12345&t=305s))", md)
        self.assertEqual(page.count("first said at"), 1)                           # unknown term: no link
        self.assertIn("&lt;b&gt;heap&lt;/b&gt;", page)
        self.assertEqual(page.count('class="studied"'), 3)
        self.assertIn('data-a="y"', page)
        self.assertIn('id="allq"', page)
        self.assertIn('data-find="graph"', page)                                   # common words search
        self.assertIn('class="mk"', page)                                          # part starts on the chart
        self.assertIn('class="tx"', page)
        self.assertNotIn("data-t=", page)                                          # transcript no longer doubled
        # every script-only control starts hidden, so the page reads fine without scripts
        for tag in re.findall(r"<[^>]*class=\"js[ \"][^>]*>", page):
            self.assertIn(" hidden", tag, tag)


class SlidesAndDesignTests(unittest.TestCase):
    """Slides captured while presenting, and the high-level design built from them."""
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pick_scenes(self):
        slide_a = [0] * 50 + [255] * 50                  # flat lists stand in for the 64x36 thumbnails
        build_a = [0] * 46 + [255] * 54                  # a bullet appears: 4% changed, same slide
        slide_b = [255] * 50 + [0] * 50
        blank = [10] * 100
        samples = [(0, slide_a, "a0"), (1, slide_a, "a1"), (2, build_a, "a2"), (3, build_a, "a3"), (4, build_a, "a4"),
                   (5, slide_b, "b0"), (6, slide_b, "b1"),            # shown 1 s only: not a slide
                   (7, blank, "x"), (8, blank, "x"), (9, blank, "x"), (10, blank, "x"), (11, blank, "x"),
                   (12, slide_a, "again"), (13, slide_a, "again"), (14, slide_a, "again"), (15, slide_a, "again")]
        scenes = ys.pick_scenes(samples)
        self.assertEqual(len(scenes), 1)                                 # blank skipped, flash skipped
        self.assertEqual(scenes[0]["payload"], "a4")                     # the complete build is kept
        self.assertEqual((scenes[0]["start"], scenes[0]["end"]), (0, 4))
        self.assertEqual(scenes[0]["shown_again"], [12])                 # going back is not a new slide
        self.assertLess(scenes[0]["motion"], 0.01)                       # a slide stands still

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "numpy not installed")
    def test_camera_shots_are_not_slides(self):
        import numpy as np
        rng = np.random.default_rng(1)
        slide = np.full((90, 160), 245, dtype=np.uint8)
        slide[20:24, 20:140] = 20                                        # flat page with lines of text
        slide[40:44, 20:120] = 20
        camera = (np.linspace(40, 160, 160)[None, :] + rng.normal(0, 4, (90, 160))).clip(0, 255).astype(np.uint8)
        self.assertFalse(ys.looks_like_camera(slide))
        self.assertFalse(ys.looks_like_camera(slide, motion=0.2))        # an animated slide stays a slide
        self.assertTrue(ys.looks_like_camera(camera))                    # soft shading, no sharp edges

    def test_camera_check_without_numpy(self):
        import random
        rnd = random.Random(1)
        slide = [245] * (160 * 90)
        for y in list(range(20, 24)) + list(range(40, 44)):              # lines of text on a flat page
            for x in range(20, 140):
                slide[y * 160 + x] = 20
        camera = [max(0, min(255, int(40 + 120 * x / 159 + rnd.gauss(0, 4)))) for y in range(90) for x in range(160)]
        self.assertFalse(ys.looks_like_camera((slide, 160)))
        self.assertFalse(ys.looks_like_camera((slide, 160), motion=0.2))
        self.assertTrue(ys.looks_like_camera((camera, 160)))

    @unittest.skipUnless(shutil.which("ffmpeg"), "the ffmpeg program is not installed")
    def test_slides_with_ffmpeg_and_no_packages(self):
        video = self.tmp / "talk.mp4"
        frames = []
        for i in range(28):                              # 14 s at 2 fps: slide A 0-5 s, B 5-9 s, A again 9-14 s
            page = [245] * (320 * 180)
            lines = (30, 60, 90) if (i < 10 or i >= 18) else (40, 120)
            for y0 in lines:
                for y in range(y0, y0 + 6):
                    for x in range(30, 290 if y0 != 120 else 160):
                        page[y * 320 + x] = 15
            frames.append(bytes(page))
        subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s",
                        "320x180", "-r", "2", "-i", "-", "-c:v", "mpeg4", "-q:v", "2", "-pix_fmt", "yuv420p",
                        str(video)], input=b"".join(frames), check=True, capture_output=True)
        orig = ys.extract_slides.__globals__.get("_extract_ffmpeg")
        self.assertIsNotNone(orig)
        rep = self._extract_without_av(video, self.tmp / "slides")
        self.assertEqual(rep["count"], 2, rep)
        self.assertEqual([s["start"] for s in rep["slides"]], [0.0, 5.0])
        self.assertEqual(rep["slides"][0]["shown_again"], [9.0])
        self.assertTrue((self.tmp / "slides" / "slide-001.jpg").read_bytes()[:2] == b"\xff\xd8")

    def _extract_without_av(self, video, out):
        saved = {m: sys.modules.get(m) for m in ("av", "numpy")}
        sys.modules["av"] = None                         # make the PyAV import fail: use the ffmpeg path
        try:
            return ys.extract_slides(video, out)
        finally:
            for m, mod in saved.items():
                if mod is None:
                    sys.modules.pop(m, None)
                else:
                    sys.modules[m] = mod

    @unittest.skipUnless(shutil.which("ffmpeg"), "the ffmpeg program is not installed")
    def test_audio_decode_and_pauses_with_ffmpeg(self):
        import math as m
        import struct
        import wave
        wav = self.tmp / "talk.wav"
        with wave.open(str(wav), "wb") as w:             # 3 s tone, 4 s silence, 3 s tone at 16 kHz
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            tone = struct.pack("<16000h", *[int(8000 * m.sin(2 * m.pi * 220 * i / 16000)) for i in range(16000)])
            w.writeframes(tone * 3 + b"\0\0" * 16000 * 4 + tone * 3)
        orig = ya._try_import
        ya._try_import = lambda name: (None, "not installed") if name == "av" else orig(name)
        try:
            pcm = b"".join(d for _, d in ya.decode_pcm(wav))
            res = ya.analyse_audio(wav)
            facts = ya.stream_facts(wav)
        finally:
            ya._try_import = orig
        self.assertEqual(len(pcm), 16000 * 10 * 2)
        self.assertEqual(res["pause_count"], 1)
        self.assertEqual((res["pauses"][0]["start"], res["pauses"][0]["length"]), (3.0, 4.0))
        self.assertEqual((facts["sample_rate"], facts["duration"]), (16000, 10.0))
        self.assertAlmostEqual(ya.window_dbfs(tone[:16000]), 20 * m.log10(8000 / 32768 / m.sqrt(2)), places=1)

    def test_whisper_cpp_engine_with_a_stand_in_program(self):
        import os
        import struct
        import wave
        wav = self.tmp / "a.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(struct.pack("<1600h", *([1000] * 1600)))
        model = self.tmp / "ggml-base.bin"
        model.write_bytes(b"model")
        fake = self.tmp / "whisper_cli.py"
        fake.write_text(
            "import json, sys\n"
            "a = sys.argv\n"
            "assert a[a.index('-m') + 1].endswith('ggml-base.bin') and '-oj' in a and a[a.index('-l') + 1] == 'en'\n"
            "out = a[a.index('-of') + 1] + '.json'\n"
            "json.dump({'result': {'language': 'en'}, 'transcription': ["
            "{'offsets': {'from': 0, 'to': 1500}, 'text': ' Hello there.'},"
            "{'offsets': {'from': 1500, 'to': 3000}, 'text': ' Next slide.'}]}, open(out, 'w'))\n", encoding="utf-8")
        runner = self.tmp / ("whisper-cli.bat" if os.name == "nt" else "whisper-cli")
        if os.name == "nt":
            runner.write_text('@"%s" "%s" %%*\n' % (sys.executable, fake), encoding="utf-8")
        else:
            runner.write_text('#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, fake), encoding="utf-8")
            runner.chmod(0o755)
        os.environ["WHISPER_CPP"] = str(runner)
        orig = ya.decode_pcm
        ya.decode_pcm = lambda path, start=0.0, end=None: iter([(0.0, b"\0\0" * 1600)])
        try:
            res = ya.transcribe(wav, engine="whisper-cpp", model=str(model), lang="en", start=10.0)
        finally:
            ya.decode_pcm = orig
            del os.environ["WHISPER_CPP"]
        self.assertEqual(res["engine"], "whisper-cpp")
        self.assertEqual(res["segments"], [{"start": 10.0, "end": 11.5, "text": " Hello there."},
                                           {"start": 11.5, "end": 13.0, "text": " Next slide."}])

    def test_hld_layout_and_svg(self):
        pos, back = yh.hld_layout(["Client", "API", "DB", "Cache"],
                                  [("Client", "API"), ("API", "DB"), ("API", "Cache"), ("Cache", "API")])
        self.assertEqual(pos["Client"][0], 0)
        self.assertEqual(pos["API"][0], 1)
        self.assertEqual({pos["DB"][0], pos["Cache"][0]}, {2})
        self.assertEqual(back, {("Cache", "API")})                       # the loop does not push columns
        svg = yh.hld_svg({"components": [{"name": "<Client>", "role": "browser"}],
                          "flow": [{"from": "<Client>", "to": "API", "label": "HTTPS"}, {"from": "API", "to": "API"}]})
        self.assertIn("&lt;Client&gt;", svg)
        self.assertNotIn("<Client>", svg)
        self.assertEqual(svg.count("<rect"), 2)
        self.assertEqual(svg.count('marker-end="url(#ah)"'), 1)          # the self-loop is dropped
        self.assertIn(">HTTPS</text>", svg)
        self.assertEqual(yh.hld_svg({}), "")

    def test_slides_captured_in_the_same_run_and_shown(self):
        run = FakeRun(AUDIO_REPORT, slides=True)
        res = yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, runner=run)
        self.assertEqual(len(run.cmds), 1)                               # one run: audio and slides together
        self.assertIn("--slides-dir", run.cmds[0])
        self.assertEqual(res["slides"], 3)
        folder = Path(res["folder"])
        self.assertEqual(sorted(p.name for p in (folder / "slides").iterdir()),
                         ["slide-001.jpg", "slide-002.jpg", "slide-003.jpg"])
        page = (folder / "overview.html").read_text(encoding="utf-8")
        for text in ('id="design"', "Slides (3)", ".im-3{background-image:url(data:image/jpeg;base64,",
                     'id="lb"', 'class="strip"', 'class="nav-group"', 'id="learn"', 'id="reference"'):
            self.assertIn(text, page)
        self.assertNotIn('id="practise"', page)                          # a draft has nothing to practise yet
        self.assertIn("draw the lecture", page)                          # draft: asks for the design

        notes = json.loads((folder / "notes.json").read_text(encoding="utf-8"))
        notes.update(written_by="agent", slides=[{"file": "slide-002.jpg", "caption": "BFS <queue>"},
                                                 {"file": "slide-003.jpg", "hide": True},
                                                 {"file": "../info.json", "caption": "ignored"}],
                     hld={"summary": "Graph search.", "components": [{"name": "Queue", "role": "holds the frontier",
                                                                      "slide": "slide-002.jpg"}],
                          "flow": [{"from": "Start node", "to": "Queue", "label": "enqueue"}]})
        yl.write_json(folder / "notes.json", notes)
        yl.render(folder)
        page = (folder / "overview.html").read_text(encoding="utf-8")
        md = (folder / "overview.md").read_text(encoding="utf-8")
        self.assertIn("Slides (2)", page)                                # one hidden
        self.assertNotIn(".im-3{", page)
        self.assertIn("BFS &lt;queue&gt;", page)
        self.assertIn('class="hld-svg"', page)
        self.assertIn('data-slide="2">see slide 2', page)
        self.assertIn("High-level design", page)
        self.assertIn("1. Start node → Queue: enqueue", md)
        self.assertIn("[slide-002.jpg](slides/slide-002.jpg): BFS <queue>", md)

    def test_slides_alone_when_text_comes_from_captions(self):
        run = FakeRun(AUDIO_REPORT, slides=True)
        res = yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, source="captions", runner=run)
        self.assertEqual(len(run.cmds), 1)
        self.assertIn("--no-audio", run.cmds[0])
        self.assertEqual(res["slides"], 3)

    def test_no_slides_skips_video_and_keeps_old_slides(self):
        yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, runner=FakeRun(AUDIO_REPORT, slides=True))
        run = FakeRun(AUDIO_REPORT, slides=True)
        res = yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, runner=run, slides=False)
        self.assertNotIn("--slides-dir", run.cmds[0])
        self.assertEqual(res["slides"], 3)                               # earlier capture kept
        self.assertIn("Slides (3)", (Path(res["folder"]) / "overview.html").read_text(encoding="utf-8"))

    def test_failed_fetch_leaves_no_slides_behind(self):
        with self.assertRaises(yl.FetchError):
            yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, source="audio-only",
                     runner=FakeRun({"fatal": "no engine"}, slides=True))
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_fix_advice_attached_when_audio_fails(self):
        res = yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get,
                       runner=FakeRun({"fatal": "yt-dlp is not installed in the audio Python"}))
        self.assertTrue(any("pip install" in line for line in res["fix"]))


class McpTests(unittest.TestCase):
    def call(self, method, params=None, mid=1):
        return mcp.handle({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})

    def test_initialize_and_list(self):
        init = self.call("initialize", {"protocolVersion": "2025-06-18"})["result"]
        self.assertEqual(init["protocolVersion"], "2025-06-18")
        names = [t["name"] for t in self.call("tools/list")["result"]["tools"]]
        self.assertEqual(names, ["yt_check_video", "yt_fetch_overview", "yt_read_transcript", "yt_render_overview"])
        self.assertIsNone(mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_bad_link_and_unknown_args_are_tool_errors(self):
        r = self.call("tools/call", {"name": "yt_check_video", "arguments": {"url": "https://vimeo.com/1"}})["result"]
        self.assertTrue(r["isError"])
        r = self.call("tools/call", {"name": "yt_check_video", "arguments": {"url": "x", "force": True}})["result"]
        self.assertTrue(r["isError"])
        self.assertIn("force", r["content"][0]["text"])

    def test_blocked_and_render_flow(self):
        tmp = Path(tempfile.mkdtemp())
        yl_fetch = yl.fetch
        try:

            def patched(url, out, *a, **kw):
                kw["get"] = fake_get
                return yl_fetch(url, out, *a, **kw)
            yl.fetch = patched
            r = self.call("tools/call", {"name": "yt_fetch_overview",
                                         "arguments": {"url": "https://youtu.be/musicVID001", "out_dir": str(tmp)}})
            self.assertTrue(r["result"]["isError"])
            self.assertIn("BLOCKED", r["result"]["content"][0]["text"])
            r = self.call("tools/call", {"name": "yt_fetch_overview", "arguments": {
                "url": "https://youtu.be/abcDEF12345", "out_dir": str(tmp), "source": "captions"}})["result"]
            self.assertFalse(r["isError"], r)
            folder = r["structuredContent"]["folder"]
            page = self.call("tools/call", {"name": "yt_read_transcript",
                                            "arguments": {"folder": folder, "limit": 1000}})["result"]
            self.assertIn("graph", page["structuredContent"]["text"])
            done = self.call("tools/call", {"name": "yt_render_overview", "arguments": {
                "folder": folder, "notes": {"summary": "Graph search basics.",
                                            "review_questions": [{"q": "Which structure does BFS use?", "a": "A queue."}]}}})
            self.assertFalse(done["result"]["isError"])
            html_text = Path(folder, "overview.html").read_text(encoding="utf-8")
            self.assertIn("Which structure does BFS use?", html_text)
            self.assertNotIn("Automatic draft", html_text)
        finally:
            yl.fetch = yl_fetch
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
