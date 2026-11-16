"""Read MP4 / MOV / M4V / 3GP container metadata with the standard library only.

    info = mp4info.read(Path("clip.mp4"))   # dict, or raises Mp4Error

Reports the brand, duration, creation time, and per track: type, codec, size, rotation, frame count,
frame rate (and whether it is variable), bitrate, language, audio channels and sample rate. Also whether
the file carries a GPS location (coordinates only on request). Only the `moov` box is read, so this is
fast even for large files.
"""

from __future__ import annotations

import re
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path

CONTAINERS = {b"moov", b"trak", b"mdia", b"minf", b"stbl", b"udta", b"edts", b"dinf"}
CODECS = {
    "avc1": "H.264 / AVC", "avc3": "H.264 / AVC", "hvc1": "H.265 / HEVC", "hev1": "H.265 / HEVC",
    "mp4v": "MPEG-4 Part 2", "av01": "AV1", "vp09": "VP9", "vp08": "VP8", "s263": "H.263", "jpeg": "Motion JPEG",
    "mjpa": "Motion JPEG", "apcn": "ProRes 422", "apch": "ProRes 422 HQ", "ap4h": "ProRes 4444",
    "mp4a": "AAC", "ac-3": "AC-3 (Dolby Digital)", "ec-3": "E-AC-3 (Dolby Digital Plus)", "Opus": "Opus",
    "alac": "Apple Lossless", "samr": "AMR-NB", "sawb": "AMR-WB", "fLaC": "FLAC", ".mp3": "MP3", "lpcm": "PCM",
    "sowt": "PCM", "twos": "PCM", "tx3g": "timed text", "wvtt": "WebVTT subtitles", "c608": "CEA-608 captions",
}
HANDLERS = {"vide": "video", "soun": "audio", "text": "text", "sbtl": "subtitle", "subt": "subtitle",
            "meta": "metadata", "tmcd": "timecode", "hint": "hint"}
EPOCH_1904 = datetime(1904, 1, 1, tzinfo=timezone.utc)


class Mp4Error(Exception):
    """Not an MP4/MOV file, or its metadata is damaged."""


def _boxes(data: bytes, start: int = 0, end: int = None):
    """Yield (type, payload_start, payload_end) for the boxes in data[start:end]."""
    end = len(data) if end is None else end
    pos = start
    while pos + 8 <= end:
        size, kind = struct.unpack(">I4s", data[pos:pos + 8])
        head = 8
        if size == 1:
            if pos + 16 > end:
                break
            size = struct.unpack(">Q", data[pos + 8:pos + 16])[0]
            head = 16
        elif size == 0:
            size = end - pos
        if size < head:
            break
        yield kind, pos + head, min(pos + size, end)
        pos += size


def _find_moov(path: Path):
    with open(path, "rb") as f:
        f.seek(0, 2)
        total = f.tell()
        pos, brand, moov = 0, "", None
        while pos + 8 <= total:
            f.seek(pos)
            head = f.read(16)
            size, kind = struct.unpack(">I4s", head[:8])
            hl = 8
            if size == 1:
                size, hl = struct.unpack(">Q", head[8:16])[0], 16
            elif size == 0:
                size = total - pos
            if size < hl:
                break
            if pos == 0 and kind != b"ftyp" and kind not in (b"moov", b"mdat", b"free", b"wide", b"skip"):
                raise Mp4Error("not an MP4/MOV file (no ftyp/moov box at the start)")
            if kind == b"ftyp":
                f.seek(pos + hl)
                brand = f.read(4).decode("latin-1").strip()
            elif kind == b"moov":
                if size > 512 * 1024 * 1024:
                    raise Mp4Error("moov box is unreasonably large (damaged file?)")
                f.seek(pos + hl)
                moov = f.read(size - hl)
            pos += size
        return brand, moov, total


def _fixed16(v: int) -> float:
    return (v - (1 << 32) if v & 0x80000000 else v) / 65536.0


def _when(seconds: int):
    if not seconds:
        return None
    try:
        return (EPOCH_1904 + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
    except OverflowError:
        return None


def _lang(code: int) -> str:
    s = "".join(chr(((code >> sh) & 0x1F) + 0x60) for sh in (10, 5, 0))
    return "" if s in ("und", "```") or not s.isalpha() else s


def _child(data, start, end, kind):
    for k, s, e in _boxes(data, start, end):
        if k == kind:
            return s, e
    return None


def _track(m: bytes, s: int, e: int) -> dict:
    t = {}
    tk = _child(m, s, e, b"tkhd")
    if tk:
        p = tk[0]
        v1 = m[p] == 1
        mat = p + (52 if v1 else 40)
        wh = p + (88 if v1 else 76)
        a, b = _fixed16(struct.unpack(">I", m[mat:mat + 4])[0]), _fixed16(struct.unpack(">I", m[mat + 4:mat + 8])[0])
        w, h = struct.unpack(">II", m[wh:wh + 8])
        t["width"], t["height"] = w >> 16, h >> 16
        t["rotation"] = {(1, 0): 0, (0, 1): 90, (-1, 0): 180, (0, -1): 270}.get((round(a), round(b)), 0)
    md = _child(m, s, e, b"mdia")
    if not md:
        return t
    mh = _child(m, md[0], md[1], b"mdhd")
    timescale = duration = 0
    if mh:
        p = mh[0]
        if m[p] == 1:
            timescale, duration = struct.unpack(">IQ", m[p + 20:p + 32])
            lang = struct.unpack(">H", m[p + 32:p + 34])[0]
        else:
            timescale, duration = struct.unpack(">II", m[p + 12:p + 20])
            lang = struct.unpack(">H", m[p + 20:p + 22])[0]
        if timescale:
            t["duration_s"] = round(duration / timescale, 3)
        if _lang(lang):
            t["language"] = _lang(lang)
    hd = _child(m, md[0], md[1], b"hdlr")
    if hd:
        h4 = m[hd[0] + 8:hd[0] + 12].decode("latin-1")
        t["type"] = HANDLERS.get(h4, h4)
    mi = _child(m, md[0], md[1], b"minf")
    st = _child(m, mi[0], mi[1], b"stbl") if mi else None
    if not st:
        return t
    sd = _child(m, st[0], st[1], b"stsd")
    if sd and sd[1] - sd[0] >= 16:
        entry = sd[0] + 8
        fourcc = m[entry + 4:entry + 8].decode("latin-1")
        t["codec"] = fourcc
        t["codec_name"] = CODECS.get(fourcc, fourcc)
        if t.get("type") == "audio" and entry + 36 <= sd[1]:
            ch, _bits = struct.unpack(">HH", m[entry + 24:entry + 28])
            rate = struct.unpack(">I", m[entry + 32:entry + 36])[0] >> 16
            t["channels"], t["sample_rate"] = ch, rate
    ts = _child(m, st[0], st[1], b"stts")
    if ts:
        n = struct.unpack(">I", m[ts[0] + 4:ts[0] + 8])[0]
        counts, deltas = 0, set()
        for i in range(min(n, 100000)):
            c, d = struct.unpack(">II", m[ts[0] + 8 + 8 * i:ts[0] + 16 + 8 * i])
            counts += c
            deltas.add(d)
        t["samples"] = counts
        if t.get("type") == "video" and duration and timescale:
            t["frames"] = counts
            t["fps"] = round(counts * timescale / duration, 3)
            t["variable_frame_rate"] = len(deltas) > 1
    sz = _child(m, st[0], st[1], b"stsz")
    if sz:
        p = sz[0]
        size, count = struct.unpack(">II", m[p + 4:p + 12])
        total = size * count if size else sum(struct.unpack(">%dI" % min(count, (sz[1] - p - 12) // 4),
                                                            m[p + 12:p + 12 + 4 * min(count, (sz[1] - p - 12) // 4)]))
        if duration and timescale:
            t["bitrate_kbps"] = round(total * 8 / (duration / timescale) / 1000, 1)
    return t


def _gps(moov: bytes):
    """ISO 6709 location string ('+52.5200+013.4050/'), from ©xyz or the QuickTime location key."""
    for pat in (rb"\xa9xyz.{4}([+-]\d+(?:\.\d+)?[+-]\d+(?:\.\d+)?(?:[+-]\d+(?:\.\d+)?)?/?)",
                rb"ISO6709.{0,64}?([+-]\d+(?:\.\d+)?[+-]\d+(?:\.\d+)?(?:[+-]\d+(?:\.\d+)?)?/)"):
        m = re.search(pat, moov, re.S)
        if m:
            return m.group(1).decode("ascii")
    return None


def parse_iso6709(s: str):
    m = re.match(r"([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)", s)
    return {"latitude": float(m.group(1)), "longitude": float(m.group(2))} if m else None


def read(path: Path, include_gps: bool = False) -> dict:
    brand, moov, total = _find_moov(path)
    if moov is None:
        raise Mp4Error("no moov box: the file is incomplete (recording interrupted or download cut off)")
    info = {"container": "MP4/MOV", "brand": brand, "file_bytes": total}
    mv = _child(moov, 0, len(moov), b"mvhd")
    if mv:
        p = mv[0]
        if moov[p] == 1:
            created, _mod, ts, dur = struct.unpack(">QQIQ", moov[p + 4:p + 32])
        else:
            created, _mod, ts, dur = struct.unpack(">IIII", moov[p + 4:p + 20])
        if ts:
            info["duration_s"] = round(dur / ts, 3)
        when = _when(created)
        if when:
            info["creation_time"] = when
    tracks = []
    for k, s, e in _boxes(moov):
        if k == b"trak":
            try:
                tracks.append(_track(moov, s, e))
            except (struct.error, IndexError):
                tracks.append({"type": "unknown", "error": "damaged track header"})
    info["tracks"] = tracks
    if "duration_s" not in info:
        durs = [t.get("duration_s", 0) for t in tracks]
        if durs:
            info["duration_s"] = max(durs)
    if info.get("duration_s"):
        info["bitrate_kbps"] = round(total * 8 / info["duration_s"] / 1000, 1)
    info["has_audio"] = any(t.get("type") == "audio" for t in tracks)
    loc = _gps(moov)
    if loc:
        info["has_gps_location"] = True
        if include_gps:
            info["gps"] = parse_iso6709(loc) or loc
    return info
