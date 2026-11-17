"""Offline tests for yt-lecture-overview (no network: YouTube responses come from fixtures/)."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import yt_audio as ya  # noqa: E402
import yt_lecture as yl  # noqa: E402
import yt_lecture_mcp as mcp  # noqa: E402
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


class FakeRun:
    """Stands in for subprocess.run of yt_audio.py; records the command."""
    def __init__(self, report):
        self.report, self.cmds = report, []

    def __call__(self, cmd, **kwargs):
        self.cmds.append(cmd)

        class P:
            returncode = 0
            stderr = ""
        P.stdout = json.dumps(self.report)
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
                           ("Music theory lecture for beginners", "Music")]:
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
        res = yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, source="captions")
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
        res = yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, source="captions")
        folder = Path(res["folder"])
        notes = json.loads((folder / "notes.json").read_text(encoding="utf-8"))
        notes.update(written_by="agent", summary="BFS uses a queue; DFS uses a stack.")
        yl.write_json(folder / "notes.json", notes)
        yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, source="captions")
        md = (folder / "overview.md").read_text(encoding="utf-8")
        self.assertIn("BFS uses a queue", md)
        self.assertNotIn("Automatic draft", md)

    def test_blocked_video_writes_nothing(self):
        with self.assertRaises(yl.Blocked):
            yl.fetch("https://www.youtube.com/watch?v=musicVID001", self.tmp, get=fake_get, source="captions")
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_render_refuses_unchecked_folder(self):
        res = yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, source="captions")
        folder = Path(res["folder"])
        info = json.loads((folder / "info.json").read_text(encoding="utf-8"))
        info["guardrail"]["allowed"] = False
        yl.write_json(folder / "info.json", info)
        with self.assertRaises(yl.Blocked):
            yl.render(folder)

    def test_transcript_file_used(self):
        res = yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=fake_get, source="captions",
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
                yl.fetch("https://youtu.be/abcDEF12345", self.tmp, get=no_captions, source="captions")
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
