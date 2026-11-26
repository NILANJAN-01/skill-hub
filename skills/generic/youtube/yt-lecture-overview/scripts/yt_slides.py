"""Slide capture for yt-lecture-overview: find the slides shown in a lecture video and save one image of each.

Runs in the "audio Python". Decodes with PyAV + numpy when they are installed, otherwise with the ffmpeg
program (no Python package needed). yt_audio.py downloads a low-resolution, video-only stream and calls
extract_slides(); the video file is deleted afterwards.

How a slide is found: frames are sampled about once a second and shrunk to a 64x36 grey thumbnail. When a
large share of the thumbnail changes, a new scene starts. A scene shown for at least MIN_HOLD seconds is a
slide; its LAST frame is saved, so slides that build up bullet by bullet are saved complete. A slide that
looks like one already saved (the speaker went back) is not saved twice; its time is added to `shown_again`.
Scenes that look like camera footage (the speaker, the room) are skipped: see looks_like_camera().
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

SIG_W, SIG_H = 64, 36     # thumbnail used to compare frames
PIXEL_DELTA = 32          # grey levels (0-255) a pixel must change by to count as changed
MOTION_DELTA = 12         # smaller change that still counts as movement (a speaker shifting, a camera)
CHANGE = 0.12             # share of changed pixels that starts a new scene (a bullet appearing is ~2-8%)
SAME = 0.06               # share below which two saved slides count as the same slide
MIN_HOLD = 3.0            # seconds a scene must stay on screen to count as a slide
MIN_CONTRAST = 6.0        # grey standard deviation below this is a blank, black or fading frame
MAX_WIDTH = 1280          # saved images are at most this wide
MAX_SLIDES = 120


def changed_share(a, b, delta=PIXEL_DELTA) -> float:
    """Share of pixels that differ by more than `delta` grey levels between two grey thumbnails.

    Takes numpy arrays (the real run) or flat lists of 0-255 values (tests, no numpy needed).
    """
    if hasattr(a, "astype"):
        return float((abs(a.astype("int16") - b.astype("int16")) > delta).mean())
    return sum(abs(x - y) > delta for x, y in zip(a, b)) / max(1, len(a))


def _median(values) -> float:
    values = sorted(values)
    return values[len(values) // 2] if values else 0.0


def contrast(sig) -> float:
    """Standard deviation of the grey values: near 0 for a blank, black or fading frame."""
    if hasattr(sig, "std"):
        return float(sig.std())
    mean = sum(sig) / max(1, len(sig))
    return (sum((v - mean) ** 2 for v in sig) / max(1, len(sig))) ** 0.5


def pick_scenes(samples, change=CHANGE, min_hold=MIN_HOLD, same=SAME, min_contrast=MIN_CONTRAST):
    """Group (t, signature, payload) samples into slides. Pure logic, so it is easy to test.

    Returns a list of {"start", "end", "payload", "signature", "shown_again", "motion"}: one per distinct slide,
    in order of first appearance. `payload` is the last sample of the scene (the complete build of the slide);
    `motion` is the median share of pixels that moved a little from one sample to the next (camera shots move
    all the time, slides almost never).
    """
    slides, run = [], None

    def close(r):
        if r is None or r["end"] - r["start"] < min_hold or contrast(r["signature"]) < min_contrast:
            return
        for s in slides:
            if changed_share(s["signature"], r["signature"]) < same:
                s["shown_again"].append(round(r["start"], 1))
                return
        slides.append({"start": round(r["start"], 1), "end": round(r["end"], 1), "payload": r["payload"],
                       "signature": r["signature"], "shown_again": [], "motion": round(_median(r["moves"]), 4)})

    for t, sig, payload in samples:
        if run is not None and changed_share(run["signature"], sig) < change:
            run["moves"].append(changed_share(run["signature"], sig, MOTION_DELTA))
            run.update(end=t, signature=sig, payload=payload)       # same scene: keep its latest frame
            continue
        close(run)
        run = {"start": t, "end": t, "signature": sig, "payload": payload, "moves": []}
    close(run)
    return slides


def looks_like_camera(gray, motion=0.0) -> bool:
    """True for camera footage (the speaker, the room) rather than a slide, from a ~160x90 grey image and the
    scene's median motion (see pick_scenes).

    Slides are drawn: large flat areas and sharp edges (text, lines), and they stand still. Camera shots are
    soft and keep moving. Measured on real lectures:
    - a soft shot (under 2% sharp-edge pixels, under 75% flat) was always a camera shot;
    - a shot that keeps moving (median motion 6% or more) with under 65% flat pixels was a camera shot, while
      animated slides that moved as much stayed above 65% flat, and slides with a small webcam in a corner
      moved under 1%.
    """
    if hasattr(gray, "astype"):
        g = gray.astype("int16")
        dx = abs(g[:, 1:] - g[:, :-1])[:-1, :]
        dy = abs(g[1:, :] - g[:-1, :])[:, :-1]
        grad = dx * (dx >= dy) + dy * (dy > dx)
        flat, strong = float((grad <= 2).mean()), float((grad >= 40).mean())
    else:                                         # (flat list of grey values, width): no numpy needed
        values, w = gray
        h = len(values) // w
        n = flat_n = strong_n = 0
        for y in range(h - 1):
            row, nxt = values[y * w:(y + 1) * w], values[(y + 1) * w:(y + 2) * w]
            for x in range(w - 1):
                g = max(abs(row[x + 1] - row[x]), abs(nxt[x] - row[x]))
                flat_n += g <= 2
                strong_n += g >= 40
                n += 1
        flat, strong = flat_n / max(1, n), strong_n / max(1, n)
    return (strong < 0.02 and flat < 0.75) or (motion >= 0.06 and flat < 0.65)


def _area(values, w, h, nw, nh):
    """Grey image (flat list) w x h -> nw x nh by area averaging."""
    def weights(n_src, n_dst):
        sc = n_src / n_dst
        out = []
        for d in range(n_dst):
            a, b = d * sc, (d + 1) * sc
            ws, i = [], int(a)
            while i < b and i < n_src:
                lo, hi = max(a, i), min(b, i + 1)
                if hi > lo:
                    ws.append((i, (hi - lo) / sc))
                i += 1
            out.append(ws)
        return out
    wx, wy = weights(w, nw), weights(h, nh)
    rows = [[sum(values[y * w + i] * k for i, k in ws) for ws in wx] for y in range(h)]
    return [int(sum(rows[j][x] * k for j, k in ws) + 0.5) for ws in wy for x in range(nw)]


def _extract_ffmpeg(video, out, start, end, every):
    """Find the scenes with the ffmpeg program instead of PyAV + numpy."""
    ff, fp = shutil.which("ffmpeg"), shutil.which("ffprobe")
    facts = {"size_bytes": Path(video).stat().st_size}
    if fp:
        try:
            res = subprocess.run([fp, "-v", "error", "-select_streams", "v:0", "-show_entries",
                                  "stream=codec_name,width,height", "-of", "json", str(video)],
                                 capture_output=True, text=True, timeout=60)
            st = (json.loads(res.stdout or "{}").get("streams") or [{}])[0]
            facts.update({"codec": st.get("codec_name"), "width": st.get("width"), "height": st.get("height")})
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    cw, ch = 160, 90
    cmd = [ff, "-v", "error", "-nostdin"] + (["-ss", "%.3f" % start] if start > 0 else []) + ["-i", str(video)]
    if end is not None:
        cmd += ["-t", "%.3f" % (end - start)]
    cmd += ["-an", "-sn", "-vf", "fps=1/%g,scale=%d:%d:flags=area,format=gray" % (every, cw, ch),
            "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def samples():
        k = 0
        while True:
            buf = proc.stdout.read(cw * ch)
            if len(buf) < cw * ch:
                return
            g = list(buf)
            yield start + k * every, _area(g, cw, ch, SIG_W, SIG_H), (start + k * every, g)
            k += 1
    try:
        scenes = pick_scenes(samples())
    finally:
        proc.stdout.close()
        proc.wait()
    camera = [s for s in scenes if looks_like_camera((s["payload"][1], cw), s["motion"])]
    scenes = [s for s in scenes if s not in camera]
    return scenes, camera, facts, lambda s, path: _jpeg_ffmpeg(ff, video, s["payload"][0], path)


def _jpeg_ffmpeg(ff, video, t, path: Path) -> int:
    """Save the frame at t seconds as JPEG, at most MAX_WIDTH wide."""
    subprocess.run([ff, "-v", "error", "-nostdin", "-y", "-ss", "%.3f" % t, "-i", str(video), "-frames:v", "1",
                    "-vf", "scale='min(%d,iw)':-2" % MAX_WIDTH, "-q:v", "3", str(path)],
                   capture_output=True, timeout=120, check=False)
    return path.stat().st_size if path.is_file() else 0


def _jpeg(av, frame, path: Path) -> int:
    """Write a VideoFrame as JPEG with PyAV's own encoder (no Pillow needed). Returns the file size."""
    w, h = frame.width, frame.height
    if w > MAX_WIDTH:
        w, h = MAX_WIDTH, int(round(h * MAX_WIDTH / w / 2)) * 2
    w, h = w - w % 2, h - h % 2
    cc = av.CodecContext.create("mjpeg", "w")
    cc.width, cc.height, cc.pix_fmt = w, h, "yuvj420p"
    cc.time_base = __import__("fractions").Fraction(1, 25)
    cc.options = {"qmin": "3", "qmax": "6"}
    packets = cc.encode(frame.reformat(width=w, height=h, format="yuvj420p")) + cc.encode(None)
    data = b"".join(bytes(p) for p in packets)
    path.write_bytes(data)
    return len(data)


def extract_slides(video, out_dir, start=0.0, end=None, every=1.0) -> dict:
    """Find the slides in `video` between start and end (seconds) and save them as out_dir/slide-NNN.jpg."""
    began = time.time()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("slide-*.jpg"):
        old.unlink()
    try:
        import av  # noqa: PLC0415 - optional package, only in the audio Python
        import numpy as np  # noqa: F401,PLC0415
    except ImportError:
        av = None
    if av is None:
        if not shutil.which("ffmpeg"):
            raise RuntimeError("slides need the ffmpeg program (or pip install av numpy)")
        scenes, camera, facts, save = _extract_ffmpeg(video, out, start, end, every)
        return _finish(scenes, camera, facts, save, out, every, began)
    with av.open(str(video)) as container:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        facts = {"codec": stream.codec_context.name, "width": stream.codec_context.width,
                 "height": stream.codec_context.height, "size_bytes": Path(video).stat().st_size}
        if start > 1:
            container.seek(int(max(0, start - 2) / stream.time_base), stream=stream)

        def samples():
            next_t = start
            for frame in container.decode(stream):
                if frame.pts is None:
                    continue
                t = float(frame.pts * stream.time_base)
                if t < next_t:
                    continue
                if end is not None and t >= end:
                    return
                next_t = t + every
                sig = frame.reformat(width=SIG_W, height=SIG_H, format="gray").to_ndarray()
                yield t, sig, frame

        scenes = pick_scenes(samples())
    camera = [s for s in scenes if looks_like_camera(
        s["payload"].reformat(width=160, height=90, format="gray").to_ndarray(), s["motion"])]
    scenes = [s for s in scenes if s not in camera]
    return _finish(scenes, camera, facts, lambda s, path: _jpeg(av, s["payload"], path), out, every, began)


def _finish(scenes, camera, facts, save, out, every, began):
    if len(scenes) > MAX_SLIDES:                       # keep the slides shown longest, in time order
        keep = sorted(sorted(scenes, key=lambda s: s["start"] - s["end"])[:MAX_SLIDES], key=lambda s: s["start"])
        scenes = keep
    slides, total = [], 0
    for i, s in enumerate(scenes, 1):
        name = f"slide-{i:03d}.jpg"
        total += save(s, out / name)
        slides.append({"file": name, "start": s["start"], "end": s["end"], "shown_again": s["shown_again"]})
    return {"count": len(slides), "slides": slides, "camera_shots_skipped": len(camera), "video": facts,
            "image_bytes": total,
            "sampled_every": every, "seconds": round(time.time() - began, 1),
            "method": f"scene change over {int(CHANGE * 100)}% of a {SIG_W}x{SIG_H} thumbnail, held "
                      f"{MIN_HOLD:g} s or more; the last frame of each scene is kept"}
