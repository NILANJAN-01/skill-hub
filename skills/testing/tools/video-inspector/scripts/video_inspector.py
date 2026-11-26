#!/usr/bin/env python3
"""Analyse a video (MP4, MOV, MKV, WebM, AVI, ...): metadata, frames extracted as images, per-frame colours,
brightness, sharpness and motion, scenes, black and frozen sections, pixel colours over time, and a
plain-text description.

    python video_inspector.py clip.mp4                        # 1 frame per second -> video-reports/clip/
    python video_inspector.py clip.mp4 --every 0.5            # a frame every 0.5 s
    python video_inspector.py clip.mp4 --frames 12            # 12 frames spread over the video
    python video_inspector.py clip.mp4 --at 0:05,0:12.5,50%   # frames at given times
    python video_inspector.py clip.mp4 --every-frame --start 10 --end 12   # every frame of 10 s .. 12 s
    python video_inspector.py clip.mp4 --save-frames          # save every analysed frame as PNG
    python video_inspector.py clip.mp4 --pixel 50,900 --region 0,0,200,80  # colour over time (LEDs, icons)
    python video_inspector.py clip.mp4 --at 5 --save-frames --grid 32 --pixels-csv   # one frame in depth
    python video_inspector.py clip.mp4 --info                 # metadata only (MP4/MOV need nothing at all)
    python video_inspector.py videos/ --out reports           # every video in a folder

Output (per video, in <out>/<video name>/): report.json, report.txt (description + timeline),
timeline.csv, tracks.csv (with --pixel/--region), frames/ (scene key frames, or all with --save-frames).

No Python packages are needed (Python 3.8+). Frames are decoded by the ffmpeg program (OpenCV is used
instead when it is installed and ffmpeg is not); all analysis is pure Python (video_frames.py).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from operator import sub
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mp4info  # noqa: E402
import video_frames as vf  # noqa: E402

VERSION = "1.0"
VIDEO_EXTS = {".mp4", ".m4v", ".mov", ".3gp", ".3g2", ".mkv", ".webm", ".avi", ".wmv", ".flv", ".mpg", ".mpeg",
              ".ts", ".mts", ".m2ts", ".ogv"}
MP4_EXTS = {".mp4", ".m4v", ".mov", ".3gp", ".3g2"}


class VideoError(Exception):
    """The video could not be read. The message says why and what to do."""


# ------------------------------------------------------------------------------------------ colours

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
    rm = (c1[0] + c2[0]) / 2
    dr, dg, db = c1[0] - c2[0], c1[1] - c2[1], c1[2] - c2[2]
    return math.sqrt((2 + rm / 256) * dr * dr + 4 * dg * dg + (2 + (255 - rm) / 256) * db * db)


def color_name(rgb) -> str:
    return min(COLOR_NAMES, key=lambda nc: dist(rgb, nc[1]))[0]


def hexc(rgb) -> str:
    return "#{:02x}{:02x}{:02x}".format(*[int(round(v)) for v in rgb[:3]])


def level(value, bands):
    for limit, name in bands:
        if value < limit:
            return name
    return bands[-1][1]


BRIGHTNESS = ((50, "very dark"), (95, "dark"), (160, "medium"), (205, "bright"), (999, "very bright"))
MOTION = ((0.5, "none"), (3, "low"), (12, "medium"), (999, "high"))


def fmt_t(t: float) -> str:
    m, s = divmod(max(0.0, t), 60)
    h, m = divmod(int(m), 60)
    return f"{h}:{m:02d}:{s:04.1f}" if h else f"{m}:{s:04.1f}"


def parse_time(text: str, duration: float) -> float:
    """'12', '12.5', '12s', '1:02', '0:01:02.5', '50%' -> seconds."""
    s = text.strip().lower()
    try:
        if s.endswith("%"):
            if not duration:
                raise VideoError(f"'{text}': percentages need a known duration")
            return duration * float(s[:-1]) / 100
        if s.endswith("ms"):
            return float(s[:-2]) / 1000
        if s.endswith("s"):
            s = s[:-1]
        parts = [float(p) for p in s.split(":")]
    except ValueError:
        raise VideoError(f"cannot read the time '{text}' (use 12.5, 1:02, 0:01:02.5 or 50%)") from None
    if not 1 <= len(parts) <= 3 or any(p < 0 for p in parts):
        raise VideoError(f"cannot read the time '{text}'")
    t = 0.0
    for p in parts:
        t = t * 60 + p
    return t


# ------------------------------------------------------------------------------------- frame analysis

def dominant(data, k=3):
    """[(share, (r,g,b))] largest first; similar shades merged (same method as image-inspector)."""
    buckets = {}
    for r, g, b in zip(data[0::3], data[1::3], data[2::3]):
        key = (r >> 4) << 8 | (g >> 4) << 4 | (b >> 4)
        e = buckets.get(key)
        if e is None:
            buckets[key] = [1, r, g, b]
        else:
            e[0] += 1
            e[1] += r
            e[2] += g
            e[3] += b
    clusters = []
    for n, sr, sg, sb in sorted(buckets.values(), key=lambda e: -e[0]):
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
    total = float(len(data) // 3)
    clusters.sort(key=lambda c: -c[0])
    return [(c[0] / total, (c[1] / c[0], c[2] / c[0], c[3] / c[0])) for c in clusters[:k]]


class FrameAnalyser:
    """Per-frame numbers from the analysis-size frame (longest side 320 px; motion and the colour
    histogram use a 160 px version)."""

    def __init__(self, scene_threshold: float):
        self.scene_threshold = scene_threshold
        self.prev_tiny = None
        self.prev_hist = None

    def analyse(self, med: bytes, mw: int, mh: int, small_size) -> dict:
        sw, sh = small_size
        small = vf.area_resize(med, mw, mh, sw, sh)
        luma = vf.gray(med)
        tiny = vf.gray(small)
        hs, ss = vf.hsv(small)
        hist = vf.hs_hist(hs, ss)
        motion = scene_diff = None
        if self.prev_tiny is not None and len(self.prev_tiny) == len(tiny):
            motion = sum(abs(d) for d in map(sub, tiny, self.prev_tiny)) / len(tiny)
            scene_diff = vf.bhattacharyya(self.prev_hist, hist)
        self.prev_tiny, self.prev_hist = tiny, hist
        n = len(luma)
        mean_l = sum(luma) / n
        std_l = math.sqrt(max(0.0, sum(v * v for v in luma) / n - mean_l * mean_l))
        mean_rgb = (sum(med[0::3]) / n, sum(med[1::3]) / n, sum(med[2::3]) / n)
        grid = []
        for i in range(3):
            row = []
            for j in range(3):
                m = vf.channel_means(med, mw, j * mw // 3, i * mh // 3, (j + 1) * mw // 3, (i + 1) * mh // 3)
                row.append(color_name(m) if m else "")
            grid.append(row)
        sharp = vf.laplacian_var(luma, mw, mh)
        return {
            "brightness": round(mean_l, 1), "brightness_level": level(mean_l, BRIGHTNESS),
            "contrast": round(std_l, 1),
            "mean": {"hex": hexc(mean_rgb), "name": color_name(mean_rgb)},
            "saturation": round(sum(ss) / len(ss) / 255, 3),
            "dominant": [{"hex": hexc(c), "name": color_name(c), "percent": round(100 * s, 1)}
                         for s, c in dominant(med)],
            "grid_3x3": grid,
            "sharpness": round(sharp, 1),
            "motion": None if motion is None else round(motion, 2),
            "motion_level": None if motion is None else level(motion, MOTION),
            "scene_change": bool(scene_diff is not None and (scene_diff > self.scene_threshold or motion > 40)),
            "scene_difference": None if scene_diff is None else round(scene_diff, 3),
            "black": mean_l < 16 and std_l < 10,
            "flat": std_l < 3,
        }


def pixel_grid(med: bytes, mw: int, mh: int, full_w: int, cols: int):
    cols = max(1, min(cols, full_w, mw))
    rows = max(1, min(mh, round(cols * mh / mw)))
    small = vf.area_resize(med, mw, mh, cols, rows)
    return {"columns": cols, "rows": rows,
            "hex": [[hexc(small[(j * cols + i) * 3:(j * cols + i) * 3 + 3]) for i in range(cols)] for j in range(rows)]}


# ------------------------------------------------------------------------------------------ reading

def parse_box(spec: str, what: str, n: int):
    try:
        vals = [int(v) for v in spec.replace(" ", "").split(",")]
    except ValueError:
        vals = []
    if len(vals) != n or any(v < 0 for v in vals):
        raise VideoError(f"{what} must be {n} comma-separated non-negative integers, got '{spec}'")
    return tuple(vals)


NO_VIDEO = "this file has no video track (audio only), so there are no frames to analyse. --info shows its metadata"


def open_source(path: Path):
    try:
        return vf.open_source(path)
    except vf.DecodeError as e:
        if path.suffix.lower() in MP4_EXTS:
            info = mp4info.read(path, False)           # raises Mp4Error with the precise reason (e.g. no moov box)
            if not any(t.get("type") == "video" for t in info["tracks"]):
                raise VideoError(NO_VIDEO)
        raise VideoError(str(e)) from None


def choose_targets(opts, fps: float, nframes: int, duration: float, warnings):
    start = parse_time(opts.start, duration) if opts.start else 0.0
    end = parse_time(opts.end, duration) if opts.end else duration
    end = min(end, duration) if duration else end
    if end <= start:
        raise VideoError(f"--end ({end:.2f}s) must be after --start ({start:.2f}s)")
    last = max(0, nframes - 1)

    def idx(t):
        return min(last, max(0, int(round(t * fps))))

    if opts.at:
        times = [parse_time(t, duration) for t in ",".join(opts.at).split(",") if t.strip()]
        bad = [t for t in times if duration and t > duration + 0.5 / fps]
        if bad:
            warnings.append(f"--at times after the end of the video ({fmt_t(duration)}) were moved to the last frame: "
                            + ", ".join(fmt_t(t) for t in bad))
        targets = [idx(t) for t in times]
    elif opts.every_frame:
        targets = list(range(idx(start), min(last, int(math.ceil(end * fps)) - 1) + 1))
    elif opts.frames:
        n = max(1, opts.frames)
        span = end - start
        targets = [idx(start + span * (i + 0.5) / n) for i in range(n)]
    else:
        step = opts.every
        count = int((end - start) / step) + 1
        if count > opts.max_frames:
            step = (end - start) / opts.max_frames                 # samples stay inside the video
            warnings.append(f"Sampling every {opts.every:g}s would give {count} frames; using every {step:.2f}s "
                            f"to stay within --max-frames {opts.max_frames}.")
            count = opts.max_frames
        times = [start + i * step for i in range(count) if start + i * step <= end + 1e-9]
        targets = [idx(t) for t in times if round(t * fps) <= last] or [idx(start)]   # a time at the very end is past the last frame
        opts.effective_every = step
    targets = sorted(set(targets))
    if len(targets) > opts.max_frames:
        warnings.append(f"{len(targets)} frames requested; only the first {opts.max_frames} are analysed "
                        "(raise --max-frames).")
        targets = targets[:opts.max_frames]
    return targets


def read_frames(src, targets, warnings, nframes=0, **kw):
    """Yield (index, rgb_bytes, width, height) for the target frames; warn when the stream ends early."""
    try:
        yield from src.read(targets, warnings, **kw)
    except vf.DecodeError as e:
        raise VideoError(str(e)) from None
    except vf._Ended as e:
        at = e.args[0]
        if nframes and at >= nframes - max(5, nframes // 50):          # a few frames short: header estimate
            warnings.append(f"The video has {at} frames, slightly fewer than the {nframes} its header gives; "
                            "samples after the last frame were skipped.")
        else:
            warnings.append(f"The video stops at frame {at} of {nframes or '?'} (damaged or truncated file); "
                            "later samples were skipped.")


# ----------------------------------------------------------------------------------------- summaries

def runs(flags):
    """[(first_index, last_index)] of consecutive True flags."""
    out, s = [], None
    for i, f in enumerate(list(flags) + [False]):
        if f and s is None:
            s = i
        elif not f and s is not None:
            out.append((s, i - 1))
            s = None
    return out


def colour_runs(samples, tol=30):
    """Group consecutive colour samples [(t, (r,g,b))] into runs of the same colour."""
    out = []
    for t, rgb in samples:
        if out and dist(out[-1]["_rgb"], rgb) < tol:
            out[-1]["end"] = t
            continue
        out.append({"start": t, "end": t, "_rgb": rgb})
    for r in out:
        rgb = r.pop("_rgb")
        r.update({"hex": hexc(rgb), "name": color_name(rgb), "start_time": fmt_t(r["start"]), "end_time": fmt_t(r["end"])})
        r["start"], r["end"] = round(r["start"], 3), round(r["end"], 3)
    return out


def frame_line(f) -> str:
    dom = ", ".join(f"{d['name']} {d['percent']:g}%" for i, d in enumerate(f["dominant"]) if i == 0 or d["percent"] >= 1)
    bits = [f"{f['time']} (frame {f['frame']}): {f['brightness_level']}, {dom}"]
    if f["motion_level"] is not None:
        bits.append(f"motion {f['motion_level']}")
    if f["black"]:
        bits.append("BLACK")
    if f.get("frozen"):
        bits.append("same as previous")
    if f["scene_change"]:
        bits.append("SCENE CHANGE")
    return "; ".join(bits)


def describe(name, meta, frames, scenes, blacks, freezes, tracks, sampling) -> str:
    w, h = meta.get("width"), meta.get("height")
    v = []
    head = f"{name} is a"
    if meta.get("has_video") is False:
        head = f"{name} has no video track (audio only)"
        if meta.get("duration_s"):
            head += f", {meta['duration_s']:.1f} s"
        return head + "."
    if w and h:
        head += f" {w}x{h} ({'landscape' if w > h else 'portrait' if h > w else 'square'})"
    head += f" {meta.get('codec_name') or ''} video".replace("  ", " ")
    if meta.get("duration_s"):
        head += f", {meta['duration_s']:.1f} s"
    if meta.get("fps"):
        head += f" at {meta['fps']:g} fps"
    if meta.get("frames"):
        head += f" ({meta['frames']} frames)"
    head += ", with audio" if meta.get("has_audio") else (", no audio track" if meta.get("has_audio") is False else "")
    v.append(head + ".")
    if not frames:
        return v[0]
    v.append(f"{len(frames)} frame{'s' if len(frames) != 1 else ''} analysed ({sampling}).")
    bright = [f["brightness"] for f in frames]
    names = {}
    for f in frames:
        for d in f["dominant"]:
            names[d["name"]] = names.get(d["name"], 0) + d["percent"]
    top = sorted(names.items(), key=lambda kv: -kv[1])[:3]
    span = (f"brightness {min(bright):.0f}-{max(bright):.0f} (average {sum(bright) / len(bright):.0f}/255)"
            if len(frames) > 1 else f"brightness {bright[0]:.0f}/255")
    v.append(f"Overall colours: {', '.join(n for n, _ in top)}; {span}.")
    if len(scenes) > 1:
        v.append(f"{len(scenes)} scenes: " + "; ".join(
            f"{s['start_time']}-{s['end_time']} {s['description']}" for s in scenes[:8])
            + ("; ..." if len(scenes) > 8 else "") + ".")
    else:
        v.append(f"One continuous scene: {scenes[0]['description']}." if scenes else "")
    if blacks:
        v.append("Black screen: " + ", ".join(f"{fmt_t(a)}-{fmt_t(b)}" for a, b in blacks) + ".")
    if freezes:
        v.append("Static (no visible change): " + ", ".join(f"{fmt_t(a)}-{fmt_t(b)}" for a, b in freezes) + ".")
    moving = [f for f in frames if f["motion_level"] in ("medium", "high")]
    if moving:
        v.append(f"Noticeable motion in {len(moving)} of {len(frames) - 1} frame steps.")
    for tr in tracks:
        seq = " -> ".join(f"{r['name']} {r['hex']} ({r['start_time']}-{r['end_time']})" for r in tr["runs"][:6])
        v.append(f"{tr['label']}: " + (f"constant {seq}" if len(tr["runs"]) == 1 else f"changes {len(tr['runs']) - 1} time(s): {seq}") + ".")
    return " ".join(x for x in v if x)


# --------------------------------------------------------------------------------------------- main

def metadata(path: Path, src_info, include_gps: bool, warnings):
    meta = {}
    if path.suffix.lower() in MP4_EXTS:
        try:
            info = mp4info.read(path, include_gps)
            meta["container"] = info
            meta["has_video"] = any(t.get("type") == "video" for t in info["tracks"])
            vt = next((t for t in info["tracks"] if t.get("type") == "video"), {})
            at = next((t for t in info["tracks"] if t.get("type") == "audio"), {})
            meta.update({k: vt[k] for k in ("width", "height", "fps", "frames", "codec", "codec_name", "rotation",
                                              "variable_frame_rate") if k in vt})
            meta["duration_s"] = info.get("duration_s") or None      # 0 in fragmented files: unknown
            meta["has_audio"] = info["has_audio"]
            mdur, tdur, tfps = meta["duration_s"], vt.get("duration_s"), vt.get("fps")
            if mdur and tdur and tfps and meta.get("frames") and mdur < tdur - 1.5 / tfps:
                meta["frames"] = min(meta["frames"], int(round(mdur * tfps)))
                warnings.append(f"An edit list shortens the video track from {tdur:g} s to {mdur:g} s; "
                                "only the part that plays is analysed.")
            if not meta["duration_s"] and not vt.get("frames"):
                warnings.append("Fragmented MP4 (no index in the header): the frame count and duration are estimates.")
            if at:
                meta["audio"] = {k: at[k] for k in ("codec_name", "channels", "sample_rate", "language") if k in at}
            if info.get("has_gps_location") and not include_gps:
                warnings.append("The video contains a GPS location (left out of this report; --include-gps adds it). "
                                "Remove it before sharing the video publicly.")
            if vt.get("variable_frame_rate"):
                warnings.append("Variable frame rate: frame times are approximate (frame index / average fps).")
        except mp4info.Mp4Error as e:
            warnings.append(f"Container metadata: {e}")
        except (OSError, ValueError, IndexError) as e:
            warnings.append(f"Container metadata could not be read ({e.__class__.__name__})")
    if src_info:
        if not (src_info.get("width") and src_info.get("height")) or src_info.get("has_video") is False:
            meta.setdefault("has_video", False)                   # the decoder found no picture stream
        for key in ("fps", "frames", "codec"):
            if meta.get(key) is None and src_info.get(key) is not None:
                meta[key] = src_info[key]
        if not meta.get("codec_name") and meta.get("codec"):
            meta["codec_name"] = src_info.get("codec_name") or mp4info.CODECS.get(meta["codec"], meta["codec"])
        if not meta.get("duration_s") and src_info.get("duration_s"):
            meta["duration_s"] = src_info["duration_s"]
        if not meta.get("duration_s") and meta.get("fps") and meta.get("frames"):
            meta["duration_s"] = round(meta["frames"] / meta["fps"], 3)
        if src_info.get("width") and src_info.get("height"):
            meta["width"], meta["height"] = src_info["width"], src_info["height"]   # as decoded (rotation applied)
        if src_info.get("rotation") and "rotation" not in meta:
            meta["rotation"] = src_info["rotation"]
        if "has_audio" not in meta and "has_audio" in src_info:
            meta["has_audio"] = src_info["has_audio"]
    if meta.get("duration_s") is None:
        meta.pop("duration_s", None)
    return meta


def analyse_video(path: Path, opts, dest: Path):
    warnings = []
    report = {"generator": {"name": "video-inspector", "version": VERSION},
              "file": {"name": path.name, "path": str(path), "bytes": path.stat().st_size}}
    src, why = None, None
    try:
        src = open_source(path)
    except VideoError as e:
        why = e
    if src is None and not opts.info:
        meta = metadata(path, None, opts.include_gps, warnings)
        if str(why) == NO_VIDEO:
            raise why
        raise VideoError(f"{why}" + (f" (metadata without it: --info; this is a {meta.get('duration_s', '?')} s "
                                     f"{meta.get('codec_name', '')} video)" if meta else ""))
    if src is not None:
        report["generator"]["decoder"] = src.backend
    frames, track_samples, saved, boxes = [], {}, 0, []
    try:
        meta = metadata(path, src.info if src else None, opts.include_gps, warnings)
        report["video"] = meta
        if meta.get("has_video") is False:
            if opts.info:
                warnings.append("This file has no video track (audio only); there are no frames to analyse.")
            else:
                raise VideoError(NO_VIDEO)
        if opts.info:
            report["description"] = describe(path.name, meta, [], [], [], [], [], "")
            report["warnings"] = warnings
            return report
        fps = meta.get("fps") or 0
        nframes = meta.get("frames") or 0
        if not fps or not nframes:
            raise VideoError("the video reports no frame rate or frame count (damaged or a stream without an index)")
        W, H = src.info["width"], src.info["height"]
        duration = meta.get("duration_s") or nframes / fps
        targets = choose_targets(opts, fps, nframes, duration, warnings)
        boxes = [("pixel", parse_box(p, "--pixel", 2)) for p in opts.pixel or []] + \
                [("region", parse_box(r, "--region", 4)) for r in opts.region or []]
        clipped = []
        for kind, box in boxes:                                   # check every box before decoding
            if kind == "pixel":
                x, y = box
                if x >= W or y >= H:
                    raise VideoError(f"--pixel {x},{y} is outside the frame ({W}x{H})")
                clipped.append((x, y, 1, 1))
            else:
                x, y, w, h = box
                if x >= W or y >= H or w == 0 or h == 0:
                    raise VideoError(f"--region {x},{y},{w},{h} is outside the frame ({W}x{H})")
                clipped.append((x, y, min(w, W - x), min(h, H - y)))
        med_size, small_size = vf.analysis_sizes(W, H)
        analyser = FrameAnalyser(opts.scene_threshold)
        # pass 1: analysis frames, already scaled by the decoder
        for idx, med, mw, mh in read_frames(src, targets, warnings, nframes, size=med_size):
            t = idx / fps
            fr = {"frame": idx, "t": round(t, 3), "time": fmt_t(t)}
            fr.update(analyser.analyse(med, mw, mh, small_size))
            fr["frozen"] = fr["motion"] is not None and fr["motion"] < opts.freeze_motion and not fr["black"]
            if opts.grid:
                fr["pixel_map"] = pixel_grid(med, mw, mh, W, opts.grid)
            frames.append(fr)
        done = [f["frame"] for f in frames]
        # pass 2: tracked pixels and regions at full resolution (only the area that holds them)
        track_samples = {i: [] for i in range(len(boxes))}
        if boxes and frames:
            ux0, uy0 = min(b[0] for b in clipped), min(b[1] for b in clipped)
            ux1, uy1 = max(b[0] + b[2] for b in clipped), max(b[1] + b[3] for b in clipped)
            crop = (ux0, uy0, ux1 - ux0, uy1 - uy0)
            got = {idx: (data, cw) for idx, data, cw, _ in read_frames(src, done, [], nframes, crop=crop)}
            last = None
            for fr in frames:
                data, cw = got.get(fr["frame"], last or (None, 0))
                if data is None:
                    continue
                last = (data, cw)
                for i, (kind, _box) in enumerate(boxes):
                    x, y, w, h = clipped[i]
                    rgb = vf.channel_means(data, cw, x - ux0, y - uy0, x - ux0 + w, y - uy0 + h)
                    if kind == "pixel":
                        rgb = tuple(int(round(v)) for v in rgb)
                    track_samples[i].append((fr["t"], rgb))
                    fr.setdefault("tracked", []).append(hexc(rgb))
        # pass 3: frame images (scene key frames, or every frame with --save-frames) at full resolution
        keep = [fr for n, fr in enumerate(frames)
                if opts.save_frames or (not opts.no_frames and (n == 0 or fr["scene_change"]))][:opts.max_saved]
        if keep:
            by_idx = {fr["frame"]: fr for fr in keep}
            frames_dir = dest / "frames"
            for idx, img, w, h in read_frames(src, [fr["frame"] for fr in keep], [], nframes):
                fr = by_idx[idx]
                name = f"frame_{idx:06d}_{idx / fps:09.3f}s.{opts.image_format}"
                blob = vf.encode_jpeg(w, h, img) if opts.image_format == "jpg" else vf.encode_png(w, h, img)
                if blob is None:
                    warnings.append("JPEG frames need ffmpeg; saved PNG instead.")
                    name = name[:-3] + "png"
                    blob = vf.encode_png(w, h, img)
                frames_dir.mkdir(parents=True, exist_ok=True)
                (frames_dir / name).write_bytes(blob)
                fr["image"] = str(Path("frames") / name)
                saved += 1
                if opts.pixels_csv:
                    if w * h > opts.max_csv_pixels:
                        warnings.append(f"--pixels-csv skipped for frame {idx}: {w * h:,} pixels > --max-csv-pixels.")
                    else:
                        cpath = frames_dir / (Path(name).stem + ".pixels.csv")
                        with open(cpath, "w", encoding="utf-8", newline="\n") as fh:
                            fh.write("x,y,r,g,b\n")
                            for yy in range(h):
                                row = img[yy * w * 3:(yy + 1) * w * 3]
                                fh.write("".join("%d,%d,%d,%d,%d\n" % (xx, yy, row[3 * xx], row[3 * xx + 1], row[3 * xx + 2])
                                                 for xx in range(w)))
                        fr["pixels_csv"] = str(Path("frames") / cpath.name)
            n_keep = sum(1 for n, fr in enumerate(frames)
                         if opts.save_frames or (not opts.no_frames and (n == 0 or fr["scene_change"])))
            if n_keep > opts.max_saved:
                warnings.append(f"Only the first {opts.max_saved} frames were saved as images (--max-saved).")
    finally:
        if src is not None and hasattr(src, "close"):
            src.close()
    if not frames:
        raise VideoError("no frames could be decoded")
    times = [f["t"] for f in frames]
    scenes = []
    for i, f in enumerate(frames):
        if i == 0 or f["scene_change"]:
            scenes.append({"start": f["t"], "start_frame": f["frame"], "first": f})
    for i, s in enumerate(scenes):
        end_t = scenes[i + 1]["start"] if i + 1 < len(scenes) else meta.get("duration_s", frames[-1]["t"])
        f = s.pop("first")
        top = ", ".join([d["name"] for d in f["dominant"][:2] if d["percent"] >= 5] or [f["dominant"][0]["name"]])
        s.update({"end": round(end_t, 3), "start_time": fmt_t(s["start"]), "end_time": fmt_t(end_t),
                  "description": ("black" if f["black"] else f"{f['brightness_level']}, mostly {top}"),
                  "key_frame_image": f.get("image")})
    step = (times[-1] - times[0]) / max(1, len(times) - 1) if len(times) > 1 else 0
    end_t = meta.get("duration_s") or times[-1]
    # black: from the first black sample until the next (non-black) sample, or the end of the video
    blacks = [(times[a], times[b + 1] if b + 1 < len(times) else end_t) for a, b in runs(f["black"] for f in frames)]
    # static: unchanged from the sample before the run to the last unchanged sample
    freezes = [(times[a - 1], times[b]) for a, b in runs(f["frozen"] for f in frames)
               if times[b] - times[a - 1] >= opts.freeze_min - 1e-9]
    tracks = []
    for i, (kind, box) in enumerate(boxes):
        label = f"pixel {box[0]},{box[1]}" if kind == "pixel" else f"region {','.join(map(str, box))}"
        tracks.append({"kind": kind, "box": list(box), "label": label, "runs": colour_runs(track_samples[i])})
    if opts.every_frame:
        sampling = "every frame"
    elif opts.at:
        sampling = "at the requested times"
    elif opts.frames:
        sampling = f"{opts.frames} frames spread over the video"
    else:
        sampling = f"one every {getattr(opts, 'effective_every', step):.3g} s" if step else "one frame"
    report.update({
        "sampling": {"mode": sampling, "frames_analysed": len(frames), "frames_saved": saved},
        "scenes": scenes,
        "black_segments": [{"start": round(a, 3), "end": round(b, 3), "start_time": fmt_t(a), "end_time": fmt_t(b)}
                           for a, b in blacks],
        "frozen_segments": [{"start": round(a, 3), "end": round(b, 3), "start_time": fmt_t(a), "end_time": fmt_t(b)}
                            for a, b in freezes],
        "tracks": tracks,
        "frames": frames,
    })
    report["description"] = describe(path.name, meta, frames, scenes, blacks, freezes, tracks, sampling)
    report["warnings"] = warnings
    report["_track_samples"] = (boxes, track_samples)
    return report


def write_outputs(report, dest: Path, opts):
    dest.mkdir(parents=True, exist_ok=True)
    boxes, samples = report.pop("_track_samples", ([], {}))
    frames = report.get("frames", [])
    lines = [report["description"], ""]
    if frames:
        lines.append("Timeline:")
        lines += ["  " + frame_line(f) for f in frames]
    for w in report["warnings"]:
        lines.append(f"WARNING {w}")
    (dest / "report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    written = ["report.json", "report.txt"]
    if frames:
        with open(dest / "timeline.csv", "w", encoding="utf-8", newline="") as fh:
            wr = csv.writer(fh, lineterminator="\n")
            wr.writerow(["time_s", "frame", "brightness", "contrast", "mean_hex", "mean_name", "dominant", "motion",
                         "scene_change", "black", "frozen", "sharpness", "image"])
            for f in frames:
                wr.writerow([f["t"], f["frame"], f["brightness"], f["contrast"], f["mean"]["hex"], f["mean"]["name"],
                             " ".join(f"{d['hex']}:{d['percent']:g}%" for d in f["dominant"]),
                             "" if f["motion"] is None else f["motion"], int(f["scene_change"]), int(f["black"]),
                             int(f["frozen"]), f["sharpness"], f.get("image", "")])
        written.append("timeline.csv")
    if boxes:
        with open(dest / "tracks.csv", "w", encoding="utf-8", newline="") as fh:
            wr = csv.writer(fh, lineterminator="\n")
            wr.writerow(["time_s", "frame", "kind", "box", "hex", "r", "g", "b", "name"])
            for k, f in enumerate(frames):
                for i, (kind, box) in enumerate(boxes):
                    t, rgb = samples[i][k]
                    wr.writerow([f["t"], f["frame"], kind, ",".join(map(str, box)), hexc(rgb)]
                                + [int(round(v)) for v in rgb] + [color_name(rgb)])
        written.append("tracks.csv")
    (dest / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return written


def collect(inputs):
    files = []
    for raw in inputs:
        p = Path(raw)
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in VIDEO_EXTS)
        else:
            files.append(p)
    return files


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Analyse a video: metadata, frames, colours, scenes, motion, pixels over time.")
    ap.add_argument("inputs", nargs="+", help="video files or folders")
    ap.add_argument("--out", type=Path, default=Path("video-reports"), help="output folder (default ./video-reports)")
    ap.add_argument("--stdout", action="store_true", help="print the JSON report instead of writing files")
    ap.add_argument("--info", action="store_true", help="metadata only (MP4/MOV work without ffmpeg)")
    g = ap.add_argument_group("which frames")
    g.add_argument("--every", type=float, default=1.0, metavar="SECONDS", help="analyse a frame every N seconds (default 1)")
    g.add_argument("--frames", type=int, metavar="N", help="analyse N frames spread over the video")
    g.add_argument("--at", action="append", metavar="T1,T2", help="analyse frames at these times: 12.5, 1:02, 50%%")
    g.add_argument("--every-frame", action="store_true", help="analyse every frame (use with --start/--end)")
    g.add_argument("--start", metavar="TIME", help="start of the part to analyse")
    g.add_argument("--end", metavar="TIME", help="end of the part to analyse")
    g.add_argument("--max-frames", type=int, default=300, help="most frames to analyse (default 300)")
    o = ap.add_argument_group("frame images and pixels")
    o.add_argument("--save-frames", action="store_true", help="save every analysed frame as an image")
    o.add_argument("--no-frames", action="store_true", help="don't save scene key frames either")
    o.add_argument("--image-format", choices=["png", "jpg"], default="png", help="frame image format (default png)")
    o.add_argument("--max-saved", type=int, default=500, help="most frame images to save (default 500)")
    o.add_argument("--grid", type=int, default=0, metavar="N", help="per-frame pixel map with N columns in the JSON")
    o.add_argument("--pixels-csv", action="store_true", help="every pixel of each saved frame as CSV (x,y,r,g,b)")
    o.add_argument("--max-csv-pixels", type=int, default=2_100_000, help="skip --pixels-csv above this many pixels")
    o.add_argument("--pixel", action="append", metavar="X,Y", help="track this pixel's colour over time (repeatable)")
    o.add_argument("--region", action="append", metavar="X,Y,W,H", help="track this area's mean colour over time")
    d = ap.add_argument_group("detection")
    d.add_argument("--scene-threshold", type=float, default=0.35, help="colour-histogram change for a new scene (0..1)")
    d.add_argument("--freeze-motion", type=float, default=0.5, help="mean grey change (0..255) below which a frame counts as unchanged")
    d.add_argument("--freeze-min", type=float, default=1.0, help="shortest frozen section to report, in seconds")
    ap.add_argument("--include-gps", action="store_true", help="include the GPS location from the metadata")
    opts = ap.parse_args(argv)
    modes = sum(bool(x) for x in (opts.frames, opts.at, opts.every_frame))
    if modes > 1:
        print("ERROR use only one of --frames, --at and --every-frame", file=sys.stderr)
        return 2
    if opts.every <= 0:
        print("ERROR --every must be more than 0", file=sys.stderr)
        return 2

    files = collect(opts.inputs)
    if not files:
        print("ERROR no video files found in " + ", ".join(opts.inputs), file=sys.stderr)
        return 2
    if opts.stdout and not opts.save_frames:
        opts.no_frames = True                                   # --stdout writes nothing unless frames are asked for
    failed, used = 0, set()
    for path in files:
        stem = path.stem if path.stem not in used else f"{path.stem}_{path.suffix.lstrip('.').lower()}"
        used.add(stem)
        dest = opts.out / stem
        try:
            if not path.is_file():
                raise VideoError("file not found")
            with open(path, "rb") as fh:
                head = fh.read(64)
            if head.lstrip().lower().startswith((b"<!doctype html", b"<html")):
                raise VideoError("this is an HTML page, not a video. Download the video file itself")
            report = analyse_video(path, opts, dest)
        except (VideoError, mp4info.Mp4Error) as e:
            print(f"ERROR {path}: {e}", file=sys.stderr)
            failed += 1
            continue
        if opts.stdout:
            report.pop("_track_samples", None)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            continue
        written = write_outputs(report, dest, opts)
        print(f"Wrote {dest}{'/' if not str(dest).endswith('/') else ''} ({', '.join(written)}"
              + (f", {report['sampling']['frames_saved']} frame image(s)" if report.get("sampling", {}).get("frames_saved") else "") + ")")
        print("  " + report["description"])
        for w in report["warnings"]:
            print(f"  WARNING {w}")
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
