"""Video frames for video_inspector.py: decoding with the ffmpeg program (no Python package needed), with
OpenCV as a fallback when it is installed and ffmpeg is not, and per-frame analysis in pure Python.

    src = open_source(path)              # FfmpegSource or CvSource; raises DecodeError when neither works
    src.info                             # fps, frames, width, height (as displayed), codec, duration_s, ...
    for idx, data, w, h in src.read(targets, size=(320, 180)):   # RGB bytes, 3 per pixel
        ...

The analysis functions follow OpenCV's definitions (BGR2GRAY and BGR2HSV fixed-point formulas, calcHist,
L2-normalised histograms, Bhattacharyya distance, 3x3 Laplacian variance), so the numbers mean the same as
in the earlier OpenCV version.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import struct
import subprocess
import tempfile
import zlib
from fractions import Fraction
from operator import add, mul, sub
from itertools import repeat

FFMPEG_HINT = ("install the ffmpeg program (Windows: winget install Gyan.FFmpeg, macOS: brew install ffmpeg, "
               "Linux: apt install ffmpeg) or set FFMPEG to its path")
FRIENDLY = {"h264": "H.264 / AVC", "hevc": "H.265 / HEVC", "av1": "AV1", "vp9": "VP9", "vp8": "VP8",
            "mpeg4": "MPEG-4 Part 2", "mpeg2video": "MPEG-2", "mpeg1video": "MPEG-1", "mjpeg": "Motion JPEG",
            "prores": "ProRes", "theora": "Theora", "wmv3": "Windows Media Video 9", "vc1": "VC-1",
            "h263": "H.263", "dvvideo": "DV", "ffv1": "FFV1", "png": "PNG", "gif": "GIF"}
MED, SMALL = 320, 160            # analysis sizes (longest side)


class DecodeError(Exception):
    pass


def find_tool(name):
    env = os.environ.get(name.upper())
    if env and os.path.isfile(env):
        return env
    exe = shutil.which(name)
    if exe:
        return exe
    ff = os.environ.get("FFMPEG")
    if ff and name == "ffprobe":                          # ffprobe usually sits next to ffmpeg
        cand = os.path.join(os.path.dirname(ff), "ffprobe" + (".exe" if ff.lower().endswith(".exe") else ""))
        if os.path.isfile(cand):
            return cand
    return None


def _ratio(text):
    try:
        f = Fraction(text)
        return float(f) if f > 0 else 0.0
    except (ValueError, ZeroDivisionError, TypeError):
        return 0.0


def probe(path):
    """Stream facts from ffprobe, or None when ffprobe is missing or cannot read the file."""
    exe = find_tool("ffprobe")
    if not exe:
        return None
    try:
        res = subprocess.run([exe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                             capture_output=True, timeout=120)
        data = json.loads(res.stdout.decode("utf-8", "replace") or "{}")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    streams = data.get("streams") or []
    v = next((s for s in streams if s.get("codec_type") == "video"
              and not (s.get("disposition") or {}).get("attached_pic")), None)
    info = {"has_video": v is not None, "has_audio": any(s.get("codec_type") == "audio" for s in streams)}
    fmt_dur = _ratio((data.get("format") or {}).get("duration"))
    if fmt_dur:
        info["duration_s"] = round(fmt_dur, 3)
    if v is None:
        return info
    rot = 0
    for sd in v.get("side_data_list") or []:
        if "rotation" in sd:
            rot = int(round(float(sd["rotation"])))
    if not rot and (v.get("tags") or {}).get("rotate"):
        rot = -int((v["tags"])["rotate"])
    rot = (-rot) % 360                                    # clockwise degrees, like mp4info
    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    if rot in (90, 270):
        w, h = h, w                                       # ffmpeg rotates the decoded frames
    fps = _ratio(v.get("avg_frame_rate")) or _ratio(v.get("r_frame_rate"))
    dur = _ratio(v.get("duration")) or fmt_dur
    frames = int(v.get("nb_frames") or 0) or (int(round(dur * fps)) if dur and fps else 0)
    tag = v.get("codec_tag_string") or ""
    name = v.get("codec_name") or ""
    info.update({"width": w, "height": h, "fps": round(fps, 3) if fps else None, "frames": frames or None,
                 "codec": tag if tag and not tag.startswith("[") else name,
                 "codec_name": FRIENDLY.get(name, name), "rotation": rot})
    if dur:
        info["duration_s"] = round(dur, 3)
    return info


class FfmpegSource:
    """Frames through the ffmpeg program: one process per run of nearby frames, raw RGB on a pipe."""

    def __init__(self, path, info):
        self.path, self.info = path, info
        self.exe = find_tool("ffmpeg")
        self.backend = "ffmpeg"

    def read(self, targets, warnings, size=None, crop=None, gap=90):
        fps = self.info["fps"]
        W, H = self.info["width"], self.info["height"]
        if crop:
            ow, oh = crop[2], crop[3]
        elif size:
            ow, oh = size
        else:
            ow, oh = W, H
        fsize = ow * oh * 3
        chunks, cur = [], []
        for t in targets:
            if cur and t - cur[-1] > gap:
                chunks.append(cur)
                cur = []
            cur.append(t)
        if cur:
            chunks.append(cur)
        for chunk in chunks:
            start = chunk[0]
            rel = [t - start for t in chunk]
            filters = []
            if rel != list(range(len(rel))):
                filters.append("select=" + "+".join("eq(n\\,%d)" % r for r in rel))
            if crop:                     # RGB first: 4:2:0 video cannot be cropped to odd sizes or positions
                filters.append("format=rgb24,crop=%d:%d:%d:%d" % (crop[2], crop[3], crop[0], crop[1]))
            elif size and (ow, oh) != (W, H):
                filters.append("scale=%d:%d:flags=area" % (ow, oh))
            cmd = [self.exe, "-v", "error", "-nostdin"]
            if start > 0:
                cmd += ["-ss", "%.6f" % ((start - 0.5) / fps)]
            cmd += ["-i", str(self.path), "-map", "0:v:0", "-an", "-sn", "-dn"]
            if filters:
                cmd += ["-vf", ",".join(filters)]
            cmd += _passthrough(self.exe) + ["-frames:v", str(len(rel)), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
            with tempfile.TemporaryFile() as err:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err)
                got = 0
                try:
                    for t in chunk:
                        buf = _read_exact(proc.stdout, fsize)
                        if len(buf) < fsize:
                            break
                        got += 1
                        yield t, buf, ow, oh
                finally:
                    proc.stdout.close()
                    proc.wait()
                if got < len(chunk):
                    err.seek(0)
                    msg = err.read().decode("utf-8", "replace").strip().splitlines()
                    if got == 0 and start == 0 and msg:          # not even the first frame decodes
                        raise DecodeError("ffmpeg cannot decode this video: " + msg[-1])
                    raise _Ended(chunk[got])


_FPS_FLAG = {}


def _passthrough(exe):
    """'-fps_mode passthrough' (ffmpeg 5.1+), or '-vsync 0' for older versions (removed in ffmpeg 7+)."""
    if exe not in _FPS_FLAG:
        try:
            res = subprocess.run([exe, "-v", "error", "-hide_banner", "-f", "lavfi", "-i", "nullsrc=s=16x16:d=0.1",
                                  "-fps_mode", "passthrough", "-f", "null", "-"], capture_output=True, timeout=30)
            ok = res.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            ok = False
        _FPS_FLAG[exe] = ["-fps_mode", "passthrough"] if ok else ["-vsync", "0"]
    return _FPS_FLAG[exe]


class _Ended(Exception):
    """The stream ended before frame `args[0]`."""


def _read_exact(fh, n):
    parts, got = [], 0
    while got < n:
        b = fh.read(n - got)
        if not b:
            break
        parts.append(b)
        got += len(b)
    return b"".join(parts)


class CvSource:
    """Fallback when OpenCV is installed but ffmpeg is not."""

    def __init__(self, path, cap, cv2):
        self.path, self.cap, self.cv2 = path, cap, cv2
        self.backend = "opencv " + cv2.__version__
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        n = max(0, int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0))
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC) or 0)
        codec = "".join(chr((fourcc >> 8 * i) & 0xFF) for i in range(4)).strip("\x00")
        self.info = {"has_video": bool(w and h), "fps": round(fps, 3) if fps and w and h else None,
                     "frames": n or None, "width": w, "height": h, "codec": codec}
        if fps and n:
            self.info["duration_s"] = round(n / fps, 3)

    def read(self, targets, warnings, size=None, crop=None, gap=90):
        cv2, cap = self.cv2, self.cap
        pos = 0
        for t in targets:
            if t < pos or t - pos > gap:
                cap.set(cv2.CAP_PROP_POS_FRAMES, t)
                pos = t
            while pos < t:
                if not cap.grab():
                    raise _Ended(pos)
                pos += 1
            ok, frame = cap.read()
            if not ok or frame is None:
                raise _Ended(t)
            pos += 1
            if crop:
                x, y, w, h = crop
                frame = frame[y:y + h, x:x + w]
            elif size and (frame.shape[1], frame.shape[0]) != tuple(size):
                frame = cv2.resize(frame, tuple(size), interpolation=cv2.INTER_AREA)
            rgb = frame[:, :, ::-1]
            yield t, rgb.tobytes(), rgb.shape[1], rgb.shape[0]

    def close(self):
        self.cap.release()


def open_source(path):
    """FfmpegSource when ffmpeg is available, else CvSource when OpenCV is, else DecodeError."""
    if find_tool("ffmpeg"):
        info = probe(path)
        if info is None:
            raise DecodeError("ffprobe (part of ffmpeg) is needed next to ffmpeg to read the video's facts")
        return FfmpegSource(path, info)
    try:
        import cv2
    except ImportError:
        raise DecodeError("frame analysis needs the ffmpeg program: " + FFMPEG_HINT) from None
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise DecodeError("OpenCV cannot open this video (unsupported codec or damaged file). "
                          "Try converting it: ffmpeg -i in.ext -c:v libx264 out.mp4")
    return CvSource(path, cap, cv2)


# =========================================================================== pure-Python analysis

def analysis_sizes(w, h):
    f = min(1.0, MED / max(w, h))
    med = (max(1, round(w * f)), max(1, round(h * f)))
    f2 = min(1.0, SMALL / max(w, h))
    small = (max(1, round(w * f2)), max(1, round(h * f2)))
    return med, small


def gray(data):
    """cv2.COLOR_RGB2GRAY (8-bit): (R*9798 + G*19235 + B*3735 + 16384) >> 15, as OpenCV 4 computes it."""
    return [(r * 9798 + g * 19235 + b * 3735 + 16384) >> 15 for r, g, b in zip(data[0::3], data[1::3], data[2::3])]


def _weights(n_src, n_dst):
    scale = n_src / n_dst
    out = []
    for d in range(n_dst):
        a, b = d * scale, (d + 1) * scale
        ws, i = [], int(a)
        while i < b and i < n_src:
            lo, hi = max(a, i), min(b, i + 1)
            if hi > lo:
                ws.append((i, (hi - lo) / scale))
            i += 1
        out.append(ws)
    return out


def area_resize(data, w, h, nw, nh):
    """RGB bytes w x h -> nw x nh by area averaging (cv2.INTER_AREA for downscaling)."""
    if (nw, nh) == (w, h):
        return bytes(data)
    if nw * 2 == w and nh * 2 == h:                        # exact halving: fast path
        out = bytearray(nw * nh * 3)
        for y in range(nh):
            s = list(map(add, data[2 * y * w * 3:(2 * y + 1) * w * 3], data[(2 * y + 1) * w * 3:(2 * y + 2) * w * 3]))
            for c in range(3):
                out[y * nw * 3 + c:(y + 1) * nw * 3:3] = bytes((a + b + 2) >> 2 for a, b in zip(s[c::6], s[c + 3::6]))
        return bytes(out)
    wx, wy = _weights(w, nw), _weights(h, nh)
    rows = []
    for y in range(h):
        line = data[y * w * 3:(y + 1) * w * 3]
        ch = [line[c::3] for c in range(3)]
        rows.append([[sum(ch[c][i] * wt for i, wt in ws) for ws in wx] for c in range(3)])
    out = bytearray(nw * nh * 3)
    for j, ws in enumerate(wy):
        for c in range(3):
            acc = [0.0] * nw
            for i, wt in ws:
                acc = list(map(add, acc, map(mul, rows[i][c], repeat(wt))))
            out[j * nw * 3 + c:(j + 1) * nw * 3:3] = bytes(min(255, int(v + 0.5)) for v in acc)
    return bytes(out)


_SDIV = [0] + [int(round((255 << 12) / i)) for i in range(1, 256)]
_HDIV = [0] + [int(round((180 << 12) / (6.0 * i))) for i in range(1, 256)]


def hsv(data):
    """cv2.COLOR_RGB2HSV for 8-bit images: (H 0..179, S 0..255) per pixel, OpenCV's fixed-point formulas."""
    hs, ss = [], []
    for r, g, b in zip(data[0::3], data[1::3], data[2::3]):
        v = max(r, g, b)
        diff = v - min(r, g, b)
        s = (diff * _SDIV[v] + 2048) >> 12
        if v == r:
            h = g - b
        elif v == g:
            h = b - r + 2 * diff
        else:
            h = r - g + 4 * diff
        h = (h * _HDIV[diff] + 2048) >> 12
        if h < 0:
            h += 180
        hs.append(h)
        ss.append(s)
    return hs, ss


def hs_hist(hs, ss):
    """cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256]) then cv2.normalize (L2)."""
    hist = [0.0] * 128
    for h, s in zip(hs, ss):
        hist[min(15, h * 16 // 180) * 8 + (s >> 5)] += 1
    norm = math.sqrt(sum(v * v for v in hist)) or 1.0
    return [v / norm for v in hist]


def bhattacharyya(h1, h2):
    """cv2.compareHist(h1, h2, cv2.HISTCMP_BHATTACHARYYA)."""
    s = sum(h1) * sum(h2)
    k = 1.0 / math.sqrt(s) if abs(s) > 1.1920929e-07 else 1.0
    return math.sqrt(max(1.0 - sum(math.sqrt(a * b) for a, b in zip(h1, h2)) * k, 0.0))


def laplacian_var(g, w, h):
    """Variance of cv2.Laplacian(gray, CV_64F) (3x3 kernel, reflect-101 border)."""
    rows = [g[y * w:(y + 1) * w] for y in range(h)]
    total = sq = 0
    for y in range(h):
        row = rows[y]
        up = rows[y - 1] if y > 0 else (rows[1] if h > 1 else row)
        down = rows[y + 1] if y < h - 1 else (rows[h - 2] if h > 1 else row)
        left = [row[1]] + row[:-1] if w > 1 else row
        right = row[1:] + [row[-2]] if w > 1 else row
        lap = list(map(sub, map(add, map(add, up, down), map(add, left, right)), map(mul, row, repeat(4))))
        total += sum(lap)
        sq += sum(map(mul, lap, lap))
    n = w * h
    return sq / n - (total / n) ** 2


def channel_means(data, w, x0, y0, x1, y1):
    n = (x1 - x0) * (y1 - y0)
    if n <= 0:
        return None
    sr = sg = sb = 0
    for y in range(y0, y1):
        line = data[(y * w + x0) * 3:(y * w + x1) * 3]
        sr += sum(line[0::3])
        sg += sum(line[1::3])
        sb += sum(line[2::3])
    return (sr / n, sg / n, sb / n)


def encode_png(w, h, data):
    raw = b"".join(b"\x00" + data[y * w * 3:(y + 1) * w * 3] for y in range(h))

    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def encode_jpeg(w, h, data):
    """JPEG through the ffmpeg program (no pure-Python JPEG encoder here); None without ffmpeg."""
    exe = find_tool("ffmpeg")
    if not exe:
        return None
    res = subprocess.run([exe, "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (w, h),
                          "-i", "-", "-frames:v", "1", "-q:v", "2", "-f", "image2pipe", "-vcodec", "mjpeg", "-"],
                         input=bytes(data), capture_output=True, timeout=60)
    return res.stdout if res.returncode == 0 and res.stdout[:2] == b"\xff\xd8" else None
