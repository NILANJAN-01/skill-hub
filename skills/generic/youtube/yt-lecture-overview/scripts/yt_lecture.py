#!/usr/bin/env python3
"""yt-lecture-overview: turn a YouTube study/tech video link into text and an HTML overview.

This script is standard library only (links, guardrail, captions, notes, HTML). The audio stage runs
yt_audio.py in the "audio Python" (--audio-python, $YT_LECTURE_AUDIO_PYTHON, or this Python), which needs:
  yt-dlp                                   extract the audio track (and a low-resolution video for the slides)
  av + numpy                               decode and analyse it (speech vs silence, pauses, loudness); slides
  faster-whisper | openai-whisper | vosk   turn the speech into text

Commands
  check  URL                 validate the link, read the real title, apply the study/tech guardrail
  fetch  URL [--out DIR]     check, extract + analyse + transcribe the audio (captions only as a fallback) and,
                             in parallel, capture the slides; then write info.json, transcript.json/.txt,
                             slides/, notes.json, overview.md, overview.html. One command does it all.
  render DIR                 rebuild overview.md and overview.html after editing notes.json
  doctor                     show which audio tools are ready and how to install the rest

Exit codes: 0 ok, 2 bad link or input, 3 blocked by the guardrail, 4 could not reach YouTube or
get any transcript, 5 video not playable (private, removed, age or region locked).
"""
from __future__ import annotations

import argparse
import base64
import collections
import datetime
import html
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from yt_guardrail import LinkError, classify_title, parse_youtube_url  # noqa: E402

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
INNERTUBE_CLIENTS = [
    ({"clientName": "ANDROID", "clientVersion": "20.10.38", "androidSdkVersion": 30},
     "com.google.android.youtube/20.10.38 (Linux; U; Android 11) gzip"),
    ({"clientName": "IOS", "clientVersion": "20.10.4", "deviceModel": "iPhone16,2"},
     "com.google.ios.youtube/20.10.4 (iPhone16,2; U; CPU iOS 18_3 like Mac OS X)"),
]
ALLOWED_HOSTS = {"www.youtube.com", "youtube.com", "m.youtube.com", "i.ytimg.com"}
MAX_BYTES = 8 * 1024 * 1024
NOISE_RE = re.compile(r"\[(?:music|applause|laughter|laughs|silence|inaudible|foreign|__)\]|♪+", re.I)


class FetchError(RuntimeError):
    """YouTube could not be reached or returned nothing usable."""


class Blocked(RuntimeError):
    """The guardrail refused the video."""


class NotPlayable(RuntimeError):
    """The video is private, removed, or age/region locked."""


# ---------------------------------------------------------------- network
def http_get(url: str, data: bytes | None = None, headers: dict | None = None, timeout: int = 25) -> str:
    """GET (or POST when data is given) and return text. Only https YouTube hosts are contacted."""
    host = re.match(r"^https://([^/]+)/", url)
    if not host or host.group(1).lower() not in ALLOWED_HOSTS:
        raise FetchError(f"refusing to contact a non-YouTube URL: {url[:80]}")
    hdrs = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9", "Cookie": "CONSENT=YES+1; SOCS=CAI"}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(MAX_BYTES).decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as exc:
        raise FetchError(f"could not reach YouTube: {exc}") from exc


# ---------------------------------------------------------------- metadata
def extract_json_after(text: str, marker: str):
    """Decode the JSON object that follows `marker` in a page, or None."""
    i = text.find(marker)
    if i < 0:
        return None
    j = text.find("{", i + len(marker))
    if j < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[j:])
        return obj
    except ValueError:
        return None


TS_LINE = re.compile(r"^\s*[\[(]?((?:\d{1,2}:)?\d{1,2}:\d{2})[\])]?\s*(?:[-–—:|.]\s*)?(.+?)\s*$")


def to_seconds(stamp: str) -> int:
    parts = [int(p) for p in stamp.split(":")]
    total = 0
    for p in parts:
        total = total * 60 + p
    return total


def parse_chapters(description: str) -> list:
    """Chapters from 'mm:ss Title' lines in a description (YouTube's own rule: first at 0:00, 3+ lines)."""
    out = []
    for line in (description or "").splitlines():
        m = TS_LINE.match(line)
        if m:
            title = re.sub(r"^[-–—:|.\s]+", "", m.group(2)).strip()
            if title:
                out.append({"start": to_seconds(m.group(1)), "title": title[:120]})
    out.sort(key=lambda c: c["start"])
    dedup = []
    for c in out:
        if not dedup or c["start"] > dedup[-1]["start"]:
            dedup.append(c)
    if len(dedup) < 3 or dedup[0]["start"] != 0:
        return []
    return dedup


def info_from_player(video_id: str, player: dict) -> dict:
    vd = player.get("videoDetails") or {}
    mf = (player.get("microformat") or {}).get("playerMicroformatRenderer") or {}
    ps = player.get("playabilityStatus") or {}
    desc = vd.get("shortDescription") or ""
    return {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "title": vd.get("title") or (mf.get("title") or {}).get("simpleText") or "",
        "channel": vd.get("author") or mf.get("ownerChannelName") or "",
        "channel_url": mf.get("ownerProfileUrl") or "",
        "duration": int(vd.get("lengthSeconds") or mf.get("lengthSeconds") or 0),
        "published": mf.get("publishDate") or mf.get("uploadDate") or "",
        "category": mf.get("category") or "",
        "keywords": list(vd.get("keywords") or [])[:40],
        "description": desc,
        "chapters": parse_chapters(desc),
        "is_live": bool(vd.get("isLiveContent")) and not vd.get("lengthSeconds"),
        "playability": ps.get("status") or "UNKNOWN",
        "playability_reason": ps.get("reason") or "",
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    }


def fetch_info(video_id: str, get=http_get) -> dict:
    """Video metadata from the watch page, with oEmbed as a fallback for the title."""
    info = None
    try:
        page = get(f"https://www.youtube.com/watch?v={video_id}&hl=en")
        player = extract_json_after(page, "ytInitialPlayerResponse")
        if player and player.get("videoDetails"):
            info = info_from_player(video_id, player)
    except FetchError:
        info = None
    if info is None or not info["title"]:
        try:
            emb = json.loads(get("https://www.youtube.com/oembed?format=json&url="
                                 f"https://www.youtube.com/watch?v={video_id}"))
        except (FetchError, ValueError) as exc:
            raise FetchError(f"could not read the video's title from YouTube ({exc}); the guardrail "
                             "needs the real title, so nothing was generated") from exc
        info = info or info_from_player(video_id, {})
        info.update(title=emb.get("title") or "", channel=emb.get("author_name") or info["channel"],
                    channel_url=emb.get("author_url") or info["channel_url"])
        if info["playability"] == "UNKNOWN":
            info["playability"] = "OK"
    return info


def check(url: str, get=http_get) -> dict:
    """Validate the link, read the real title from YouTube and apply the guardrail."""
    link = parse_youtube_url(url)
    info = fetch_info(link["video_id"], get)
    verdict = classify_title(info["title"], info.get("category", ""), info.get("keywords"))
    info["guardrail"] = verdict
    info["requested_url"] = url
    return info


# ---------------------------------------------------------------- transcripts
def caption_tracks(video_id: str, get=http_get) -> list:
    """Caption tracks from the YouTube player API (the web page's caption links need extra tokens)."""
    for client, agent in INNERTUBE_CLIENTS:
        body = json.dumps({"context": {"client": dict(client, hl="en")}, "videoId": video_id}).encode()
        try:
            player = json.loads(get("https://www.youtube.com/youtubei/v1/player?prettyPrint=false", body,
                                    {"Content-Type": "application/json", "User-Agent": agent}))
        except (FetchError, ValueError):
            continue
        tracks = (((player.get("captions") or {}).get("playerCaptionsTracklistRenderer") or {})
                  .get("captionTracks") or [])
        if tracks:
            return [{"lang": t.get("languageCode", ""), "kind": t.get("kind", ""),
                     "name": "".join(r.get("text", "") for r in (t.get("name") or {}).get("runs", []))
                     or (t.get("name") or {}).get("simpleText", ""),
                     "base_url": t.get("baseUrl", "")} for t in tracks if t.get("baseUrl")]
    return []


def pick_track(tracks: list, lang: str = "en"):
    """Prefer a human track in `lang`, then auto-generated `lang`, then any human track, then anything."""
    def is_lang(t):
        return t["lang"] == lang or t["lang"].split("-")[0] == lang
    for test in (lambda t: is_lang(t) and t["kind"] != "asr", lambda t: is_lang(t),
                 lambda t: t["kind"] != "asr", lambda t: True):
        for t in tracks:
            if test(t):
                return t
    return None


def parse_json3(text: str) -> list:
    data = json.loads(text)
    segs = []
    for ev in data.get("events") or []:
        words = "".join(s.get("utf8", "") for s in ev.get("segs") or [])
        if not words.strip():
            continue
        start = ev.get("tStartMs", 0) / 1000.0
        segs.append({"start": round(start, 2), "end": round(start + ev.get("dDurationMs", 0) / 1000.0, 2),
                     "text": words})
    return segs


def parse_timed_xml(text: str) -> list:
    segs = []
    for m in re.finditer(r'<(?:text|p) start="([\d.]+)"(?: dur="([\d.]+)")?[^>]*>(.*?)</(?:text|p)>', text, re.S):
        start, dur = float(m.group(1)), float(m.group(2) or 0)
        words = html.unescape(re.sub(r"<[^>]+>", "", m.group(3)))
        segs.append({"start": start, "end": start + dur, "text": words})
    return segs


VTT_TIME = re.compile(r"((?:\d+:)?\d{1,2}:\d{2}[.,]\d{3})\s*-->\s*((?:\d+:)?\d{1,2}:\d{2}[.,]\d{3})")


def _vtt_seconds(stamp: str) -> float:
    total = 0.0
    for part in stamp.replace(",", ".").split(":"):
        total = total * 60 + float(part)
    return total


def parse_vtt_or_srt(text: str) -> list:
    segs = []
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n"))
    for block in blocks:
        m = VTT_TIME.search(block)
        if not m:
            continue
        lines = block[m.end():].strip().splitlines()
        words = " ".join(re.sub(r"<[^>]+>", "", ln) for ln in lines).strip()
        if words:
            segs.append({"start": _vtt_seconds(m.group(1)), "end": _vtt_seconds(m.group(2)),
                         "text": html.unescape(words)})
    return segs


def parse_plain(text: str) -> list:
    """Plain text, optionally with 'mm:ss' or '[hh:mm:ss]' at the start of lines."""
    segs, last = [], 0.0
    for line in text.splitlines():
        if not line.strip():
            continue
        m = TS_LINE.match(line)
        if m:
            last = float(to_seconds(m.group(1)))
            line = m.group(2)
        segs.append({"start": last, "end": last, "text": line.strip()})
    return segs


def load_transcript_file(path: Path) -> list:
    text = path.read_text(encoding="utf-8", errors="replace")
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
        if isinstance(data, dict) and "events" in data:
            return parse_json3(text)
        items = data.get("segments", data) if isinstance(data, dict) else data
        return [{"start": float(s.get("start", 0)), "end": float(s.get("end", s.get("start", 0))),
                 "text": str(s.get("text", ""))} for s in items if isinstance(s, dict)]
    if suffix in (".vtt", ".srt") or VTT_TIME.search(text[:2000]):
        return parse_vtt_or_srt(text)
    if suffix == ".xml" or text.lstrip().startswith("<"):
        return parse_timed_xml(text)
    return parse_plain(text)


def clean_segments(segs: list) -> list:
    """Drop noise tags and the repeated text of rolling auto-captions; merge into tidy segments."""
    out, prev_words = [], []
    for s in sorted(segs, key=lambda x: x["start"]):
        text = NOISE_RE.sub(" ", html.unescape(s["text"])).replace("\n", " ")
        text = re.sub(r"\s+", " ", text).strip(" >-")
        if not text:
            continue
        words = text.split()
        # rolling captions repeat the tail of the previous line at the start of this one
        overlap = 0
        for k in range(min(len(words), len(prev_words)), 0, -1):
            if prev_words[-k:] == words[:k]:
                overlap = k
                break
        words = words[overlap:]
        if not words:
            continue
        prev_words = (prev_words + words)[-30:]
        out.append({"start": round(float(s["start"]), 2), "end": round(float(s.get("end") or s["start"]), 2),
                    "text": " ".join(words)})
    return out


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def ytdlp_command():
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    if _module_available("yt_dlp"):
        return [sys.executable, "-m", "yt_dlp"]
    return None


def subtitles_with_ytdlp(url: str, lang: str, workdir: Path) -> list:
    cmd = ytdlp_command()
    if not cmd:
        return []
    out = workdir / "subs"
    subprocess.run(cmd + ["--skip-download", "--write-subs", "--write-auto-subs", "--sub-format", "vtt",
                          "--sub-langs", f"{lang}.*,{lang}", "--no-playlist", "-o", str(out) + ".%(ext)s", url],
                   capture_output=True, text=True, timeout=300, check=False)
    for f in sorted(workdir.glob("subs*.vtt")):
        segs = parse_vtt_or_srt(f.read_text(encoding="utf-8", errors="replace"))
        if segs:
            return segs
    return []


AUDIO_SCRIPT = Path(__file__).resolve().parent / "yt_audio.py"


def audio_python(explicit: str | None = None) -> str:
    """The interpreter for the audio stage: --audio-python, then $YT_LECTURE_AUDIO_PYTHON, then this Python."""
    return explicit or os.environ.get("YT_LECTURE_AUDIO_PYTHON") or sys.executable


def run_audio_stage(url: str, workdir: Path, clip: str = "", engine: str = "auto", model: str = "base",
                    lang: str = "en", keep_audio: Path | None = None, python: str | None = None,
                    transcribe: bool = True, runner=subprocess.run, slides_dir: Path | None = None,
                    slides_height: int = 720, audio: bool = True) -> dict:
    """Run yt_audio.py: extract the audio track, analyse it and turn the speech into text. With slides_dir it
    also captures the slides, in parallel; audio=False captures only the slides."""
    cmd = [audio_python(python), str(AUDIO_SCRIPT), "process", "--url", url, "--workdir", str(workdir),
           "--engine", engine, "--model", model, "--lang", lang]
    if clip:
        cmd += ["--clip", clip]
    if keep_audio:
        cmd += ["--keep-audio", str(keep_audio)]
    if not transcribe:
        cmd.append("--no-transcribe")
    if slides_dir:
        cmd += ["--slides-dir", str(slides_dir), "--slides-height", str(slides_height)]
    if not audio:
        cmd.append("--no-audio")
    doing = (["the audio"] if audio else []) + (["the slides"] if slides_dir else [])
    print(f"extracting {' and '.join(doing)} (a long lecture can take a while)...", file=sys.stderr)
    try:
        proc = runner(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                      errors="replace", timeout=6 * 3600, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise FetchError(f"could not start the audio stage with {cmd[0]}: {exc}") from exc
    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip().startswith("{")]
    if not lines:
        raise FetchError("the audio stage gave no result: " + (proc.stderr or "")[-400:].strip())
    report = json.loads(lines[-1])
    if report.get("fatal"):
        raise FetchError(report["fatal"])
    return report


def clip_range(clip: str) -> tuple:
    if not clip:
        return 0.0, None
    m = re.match(r"^\s*([\d:.]*)\s*-\s*([\d:.]*)\s*$", clip)
    if not m:
        raise ValueError(f"bad --clip {clip!r}; use START-END like 10:00-25:00")

    def sec(s):
        total = 0.0
        for part in s.split(":"):
            total = total * 60 + float(part)
        return total
    start, end = (sec(m.group(1)) if m.group(1) else 0.0), (sec(m.group(2)) if m.group(2) else None)
    if end is not None and end <= start:
        raise ValueError("--clip end must be after its start")
    return start, end


def in_clip(segs: list, clip: str) -> list:
    start, end = clip_range(clip)
    return [s for s in segs if s["start"] >= start - 0.5 and (end is None or s["start"] < end)]


def captions_transcript(info: dict, lang: str, clip: str, get=http_get) -> tuple:
    """(segments, source, tried) from YouTube captions, then yt-dlp subtitles."""
    tried = []
    track = pick_track(caption_tracks(info["video_id"], get), lang)
    if track:
        base = re.sub(r"&fmt=[^&]*", "", track["base_url"])
        try:
            raw = get(base + "&fmt=json3")
            segs = clean_segments(parse_json3(raw) if raw.strip().startswith("{") else parse_timed_xml(raw))
        except (FetchError, ValueError):
            segs = []
        segs = in_clip(segs, clip)
        if segs:
            kind = "auto-generated" if track["kind"] == "asr" else "uploaded"
            return segs, f"youtube-captions:{track['lang']} ({kind})", tried
        tried.append("YouTube captions (empty)")
    else:
        tried.append("YouTube captions (none)")
    with tempfile.TemporaryDirectory() as tmp:
        segs = in_clip(clean_segments(subtitles_with_ytdlp(info["url"], lang, Path(tmp))), clip)
    if segs:
        return segs, "yt-dlp-subtitles", tried
    tried.append("yt-dlp subtitles" + ("" if ytdlp_command() else " (yt-dlp not installed)"))
    return [], "", tried


SOURCES = ("audio", "audio-only", "captions")


def get_transcript(info: dict, lang: str = "en", source: str = "audio", transcript_file: str | None = None,
                   model: str = "base", engine: str = "auto", clip: str = "", keep_audio: Path | None = None,
                   python: str | None = None, get=http_get, runner=subprocess.run,
                   slides_dir: Path | None = None, slides_height: int = 720) -> dict:
    """Return {'segments', 'source', 'audio', 'slides', 'warnings'}.

    source=audio (default): extract the audio and turn speech into text; if that fails, use captions and
    say so in 'warnings'. audio-only: fail instead of using captions. captions: captions first, then audio.
    A transcript file always wins, but the audio is still extracted and analysed unless source=captions.
    With slides_dir, the slides are captured once, in the same run as the audio (or alone, when no audio runs).
    """
    if source not in SOURCES:
        raise ValueError(f"source must be one of {', '.join(SOURCES)}")
    clip_range(clip)  # validate early
    warnings, audio_report, tried = [], None, []
    slides = {"report": None, "pending": bool(slides_dir)}

    def stage(transcribe=True, audio=True):
        """One run of yt_audio.py; takes the slides along the first time. Returns its report or None."""
        with_slides = slides_dir if slides["pending"] else None
        slides["pending"] = False
        with tempfile.TemporaryDirectory() as tmp:
            try:
                rep = run_audio_stage(info["url"], Path(tmp), clip, engine, model,
                                      lang if lang != "auto" else "auto", keep_audio, python, transcribe, runner,
                                      with_slides, slides_height, audio)
            except FetchError as exc:
                what = "audio not processed" if audio else "slides not captured"
                warnings.append(f"{what}: {exc}")
                tried.append(f"{'audio' if audio else 'slides'} ({exc})")
                return None
        slides["report"] = rep.get("slides") or slides["report"]
        warnings.extend(rep.get("errors") or [])
        return rep

    def slides_only():
        if slides["pending"]:
            stage(transcribe=False, audio=False)

    def result(segs, label):
        slides_only()
        return {"segments": segs, "source": label, "audio": audio_report, "slides": slides["report"],
                "warnings": warnings}

    def audio_stage(transcribe=True):
        nonlocal audio_report
        rep = stage(transcribe)
        if rep is None:
            return []
        tr = rep.get("transcript") or {}
        audio_report = {"audio": rep.get("audio") or {}, "analysis": rep.get("analysis") or {},
                        "speech_to_text": {k: v for k, v in tr.items() if k != "segments"}, "clip": clip}
        segs = clean_segments(tr.get("segments") or [])
        if transcribe and not segs:
            tried.append("audio speech-to-text (" + ("; ".join(rep.get("errors") or []) or "no speech found") + ")")
        return segs

    if transcript_file:
        segs = in_clip(clean_segments(load_transcript_file(Path(transcript_file))), clip)
        if not segs:
            raise FetchError(f"no text found in {transcript_file}")
        if source != "captions":
            audio_stage(transcribe=False)
        return result(segs, f"file:{Path(transcript_file).name}")

    def stt_label():
        stt = audio_report["speech_to_text"]
        return f"audio-speech-to-text ({stt.get('engine', '?')} {stt.get('model', '')})".replace(" )", ")")

    if source in ("audio", "audio-only"):
        segs = audio_stage()
        if segs:
            return result(segs, stt_label())
        if source == "audio-only":
            raise FetchError("the audio could not be turned into text: " + "; ".join(warnings or tried) +
                             ". Run `yt_lecture.py doctor` to see what is missing")
    segs, label, more = captions_transcript(info, lang if lang != "auto" else "en", clip, get)
    tried += more
    if segs:
        if source == "audio":
            warnings.append("the text comes from captions because the audio could not be turned into text")
        return result(segs, label)
    if source == "captions":
        segs = audio_stage()
        if segs:
            return result(segs, stt_label())
    raise FetchError("no transcript could be made. Tried: " + "; ".join(tried) +
                     ". Run `yt_lecture.py doctor`, install what it lists, or pass --transcript <file>")


# ---------------------------------------------------------------- automatic draft notes
STOP = set("""a about above after again against all also am an and any are as at be because been before being
below between both but by can could did do does doing down during each few for from further had has have having
he her here hers him his how i if in into is it its itself just let me more most my no nor not now of off on once
only or other our out over own same she should so some such than that the their them then there these they this
those through to too under until up very was we were what when where which while who whom why will with would you
your yours yourself okay ok yeah uh um so right gonna wanna like really actually basically going get got one two
thing things kind lot way well know see say said look little bit just mean want make sure let's we're it's that's
there's you're i'm don't can't isn't here's what's also us thats dont im youre theyre theres might next
zero three four five six seven eight nine ten eleven twelve twenty thirty forty fifty sixty seventy eighty
ninety hundred thousand million first second""".split())


def fmt_time(sec: float) -> str:
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def tokens(text: str) -> list:
    return [w for w in re.findall(r"[a-z][a-z0-9+#'-]{1,}", text.lower()) if w not in STOP and len(w) > 2]


def top_keywords(text: str, n: int = 20) -> list:
    words = tokens(text)
    counts = collections.Counter(words)
    bigrams = collections.Counter(zip(words, words[1:]))
    out = [(" ".join(b), c * 1.6) for b, c in bigrams.most_common(n) if c >= 3]
    out += [(w, float(c)) for w, c in counts.most_common(n * 2)]
    seen, result = set(), []
    for term, score in sorted(out, key=lambda x: -x[1]):
        parts = set(term.split())
        if term in seen or (len(parts) == 1 and any(term in s.split() for s in seen if " " in s)):
            continue
        seen.add(term)
        result.append({"term": term, "count": int(round(score / (1.6 if " " in term else 1)))})
        if len(result) >= n:
            break
    return result


def sentences(segs: list) -> list:
    """Split a segment list into sentence-like units with start times (auto-captions lack punctuation)."""
    units, cur, start = [], [], None
    sample = " ".join(s["text"] for s in segs[:40])
    punctuated = len(re.findall(r"[.!?]", sample)) >= max(2, len(sample.split()) // 60)
    limit = 28 if punctuated else 30
    for s in segs:
        if not punctuated and cur:      # no punctuation: a new segment starts after a pause, a natural break
            units.append({"start": start, "text": _tidy(" ".join(cur))})
            cur, start = [], None
        pieces = []
        for part in re.split(r"(?<=[.!?])\s+", s["text"]):
            w = part.split()
            pieces += [" ".join(w[i:i + limit]) for i in range(0, len(w), limit)] or [part]
        for piece in pieces:
            if not piece:
                continue
            if start is None:
                start = s["start"]
            cur.append(piece)
            words = sum(len(c.split()) for c in cur)
            if re.search(r"[.!?]$", piece) and words >= 6 or words >= limit:
                units.append({"start": start, "text": _tidy(" ".join(cur))})
                cur, start = [], None
    if cur:
        units.append({"start": start or 0, "text": _tidy(" ".join(cur))})
    return units


def _tidy(text: str) -> str:
    """Capitalise a sentence-like unit (speech-to-text output is often all lower case)."""
    text = text.strip()
    return text[:1].upper() + text[1:] if text else text


def key_sentences(units: list, k: int) -> list:
    if not units:
        return []
    freq = collections.Counter(w for u in units for w in tokens(u["text"]))
    top = max(freq.values()) if freq else 1

    def score(u):
        ws = tokens(u["text"])
        return sum(freq[w] / top for w in ws) / math.sqrt(len(ws) + 1) if ws else 0

    best = sorted(units, key=score, reverse=True)[:k]
    return sorted(best, key=lambda u: u["start"])


def make_sections(info: dict, segs: list) -> list:
    end = max(info.get("duration") or 0, int(segs[-1]["end"] or segs[-1]["start"]) + 1 if segs else 0)
    c_start, c_end = clip_range(info.get("clip") or "")
    first = int(c_start)
    if c_end is not None:
        end = min(end, int(c_end)) if end else int(c_end)
    if info.get("chapters"):
        marks = [(c["start"], c["title"]) for c in info["chapters"]]
    else:
        size = min(600, max(180, (end - first) // 8 or 180))
        marks = [(t, "") for t in range(first, max(end, first + 1), size)]
    sections = []
    for i, (start, title) in enumerate(marks):
        stop = marks[i + 1][0] if i + 1 < len(marks) else end + 1
        part = [s for s in segs if start <= s["start"] < stop]
        if not part:
            continue
        text = " ".join(s["text"] for s in part)
        kws = [k["term"] for k in top_keywords(text, 3)]
        sections.append({"start": start, "end": min(stop, end), "title": title or
                         ("Part %d: %s" % (len(sections) + 1, ", ".join(kws) if kws else "")).rstrip(": "),
                         "points": [u["text"] for u in key_sentences(sentences(part), 2)],
                         "words": len(text.split())})
    return sections


def draft_notes(info: dict, segs: list) -> dict:
    full = " ".join(s["text"] for s in segs)
    units = sentences(segs)
    return {
        "written_by": "auto-draft",
        "summary": " ".join(u["text"] for u in key_sentences(units, 3)),
        "key_takeaways": [u["text"] for u in key_sentences(units, 6)],
        "sections": make_sections(info, segs),
        "terms": [{"term": k["term"], "meaning": ""} for k in top_keywords(full, 12)],
        "prerequisites": [],
        "review_questions": [],
        "further_study": [],
    }


# ---------------------------------------------------------------- output
def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def paragraphs(segs: list, span: float = 30.0) -> list:
    """Group segments into (start, text) paragraphs of about `span` seconds."""
    out, block, start = [], [], None
    for s in segs:
        if block and s["start"] - start >= span:
            out.append((start, " ".join(block)))
            block = []
        if not block:
            start = s["start"]
        block.append(s["text"])
    if block:
        out.append((start, " ".join(block)))
    return out


def transcript_text(segs: list) -> str:
    return "\n\n".join(f"[{fmt_time(t)}] {txt}" for t, txt in paragraphs(segs)) + "\n"


def overview_markdown(info: dict, notes: dict, meta: dict) -> str:
    """The overview as plain text, in the same reading order as the HTML page."""
    from yt_html import fmt_length, nice_date, sentence
    link = info["url"]
    draft = notes.get("written_by") == "auto-draft"
    cut = 32 if draft else 0
    src = meta.get("source", "")
    duration = info.get("duration") or 0
    facts = [info.get("channel") or "", nice_date(info.get("published", "")), f"{fmt_length(duration)} long",
             f"{meta.get('words', 0):,} words spoken",
             "text from the audio" if src.startswith("audio") else
             "text from captions" if "caption" in src or "subtitle" in src else "text from a transcript file"]
    out = [f"# {info['title']}", "", " · ".join(x for x in facts if x), "", f"Watch: {link}", ""]
    if info.get("clip"):
        out += [f"Part processed: {info['clip']}", ""]
    if draft:
        out += ["> **Automatic draft.** The sentences below were picked from what was said, word for word, and "
                "have not been checked or rewritten yet.", ""]
    out += [f"> **Please note:** {sentence(w)}" for w in meta.get("warnings") or []]
    if meta.get("warnings"):
        out.append("")
    out += ["## Summary", "", sentence(notes.get("summary"), 60 if draft else 0) or "_Not written yet._", ""]
    take = (notes.get("key_takeaways") or [])[:5 if draft else 8]
    if take:
        out += ["**Remember these**", ""] + [f"{i}. {sentence(t, cut)}" for i, t in enumerate(take, 1)] + [""]
    sections = notes.get("sections") or []
    if sections:
        out += ["## Outline", "", "| # | Topic | Starts | Length |", "|---|---|---|---|"]
        for i, s in enumerate(sections):
            start = int(s.get("start", 0))
            end = s.get("end") or (sections[i + 1]["start"] if i + 1 < len(sections) else duration)
            out.append(f"| {i + 1} | {s.get('title', '')} | [{fmt_time(start)}]({link}&t={start}s) | "
                       f"{fmt_length(max(0, end - start))} |")
        out.append("")
    out += design_markdown(notes, meta.get("slides") or [], link)
    if sections:
        out += ["## Section notes", ""]
        for i, s in enumerate(sections):
            start = int(s.get("start", 0))
            out += [f"### {i + 1}. {s.get('title', '')} ([{fmt_time(start)}]({link}&t={start}s))", ""]
            out += [f"- {sentence(p, cut)}" for p in (s.get("points") or [])[:4]] + [""]
    terms = [t for t in notes.get("terms") or [] if t.get("term") and t.get("meaning")]
    if terms:
        said = meta.get("first_said") or {}
        out += ["## Key terms", ""]
        for t in terms:
            at = said.get(t["term"])
            where = f" (first said at [{fmt_time(at)}]({link}&t={int(at)}s))" if at is not None else ""
            out.append(f"- **{t['term']}**: {sentence(t['meaning'])}{where}")
        out.append("")
    questions = [q for q in notes.get("review_questions") or [] if q.get("q")]
    if questions:
        out += ["## Check yourself", ""]
        for i, q in enumerate(questions, 1):
            out += [f"{i}. {q['q']}"] + ([f"   - Answer: {q['a']}"] if q.get("a") else [])
        out.append("")
    if notes.get("prerequisites"):
        out += ["## Good to know before watching", ""] + [f"- {sentence(x)}" for x in notes["prerequisites"]] + [""]
    if notes.get("further_study"):
        out += ["## What to study next", ""] + [f"- {sentence(x)}" for x in notes["further_study"]] + [""]
    out += audio_markdown(meta.get("audio"), meta.get("words_per_minute", 0), link)
    return "\n".join(out)


def design_markdown(notes: dict, slides: list, link: str) -> list:
    """The high-level design and the slide list as Markdown (slide images are linked, not embedded)."""
    from yt_html import sentence
    hld = notes.get("hld") if isinstance(notes.get("hld"), dict) else {}
    comps = [c for c in hld.get("components") or [] if isinstance(c, dict) and c.get("name")]
    flow = [f for f in hld.get("flow") or [] if isinstance(f, dict) and f.get("from") and f.get("to")]
    if not (hld.get("summary") or comps or flow or slides):
        return []
    out = ["## Design and slides", ""]
    if hld.get("summary"):
        out += [sentence(hld["summary"]), ""]
    if comps:
        out += ["**Components**", ""] + [f"- **{c['name']}**: {sentence(c.get('role') or '')}" for c in comps] + [""]
    if flow:
        out += ["**How it flows**", ""] + [f"{i}. {f['from']} → {f['to']}" + (f": {f['label']}" if f.get("label") else "")
                                           for i, f in enumerate(flow, 1)] + [""]
    if slides:
        out += [f"**Slides** ({len(slides)}, in `slides/`)", ""]
        out += [f"- [{fmt_time(s['start'])}]({link}&t={int(s['start'])}s) [{s['file']}](slides/{s['file']})" +
                (f": {s['caption']}" if s.get("caption") else "") for s in slides] + [""]
    return out


def speaking_rate(segs: list, audio: dict | None) -> int:
    """Words per minute of speech: uses the measured speaking time when the audio was analysed."""
    words = sum(len(s["text"].split()) for s in segs)
    speech = ((audio or {}).get("analysis") or {}).get("speech_seconds")
    if not speech and segs:
        speech = max(1.0, (segs[-1]["end"] or segs[-1]["start"]) - segs[0]["start"])
    return int(round(words / (speech / 60.0))) if speech else 0


def audio_markdown(audio: dict | None, wpm: int, link: str) -> list:
    """The audio findings in plain words."""
    from yt_html import fmt_length, pace_label
    if not audio:
        return []
    a, f, stt = audio.get("analysis") or {}, audio.get("audio") or {}, audio.get("speech_to_text") or {}
    out = ["## About the audio", ""]
    if a:
        out.append(f"- Someone is speaking {round(100 * a.get('speech_ratio', 0))}% of the time "
                   f"({fmt_length(a.get('speech_seconds', 0))} of {fmt_length(a.get('analysed_seconds', 0))}).")
    if wpm:
        out.append(f"- Speaking pace: {wpm} words per minute ({pace_label(wpm)}; lectures are usually 120-160).")
    if a:
        out.append(f"- Pauses longer than 2 seconds: {a.get('pause_count', 0)}. Longest pauses (often a change of "
                   "topic or a demo):")
        out += [f"  - [{fmt_time(p['start'])}]({link}&t={int(p['start'])}s): {p['length']} s"
                for p in (a.get("pauses") or [])[:5]]
    if stt:
        out.append(f"- The speech was turned into text by {stt.get('engine', '?')} ({stt.get('model', '')}, "
                   f"language {stt.get('language', '?')}), so some words may be misheard.")
    if f:
        out.append(f"- Technical: {f.get('codec') or f.get('format', '?')} audio, {f.get('bitrate_kbps', '?')} kbps, "
                   f"{round((f.get('size_bytes') or 0) / 1e6, 1)} MB downloaded"
                   f"{' (a copy was kept)' if f.get('kept') else ' and deleted after processing'}.")
    return out + [""]


SLIDE_NAME = re.compile(r"^slide-\d{3}\.jpg$")


def load_slides(folder: Path, info: dict, notes: dict) -> list:
    """The captured slides to show, in time order, with the agent's captions; hidden ones are left out.

    notes.json may hold "slides": [{"file": "slide-003.jpg", "caption": "...", "hide": true}].
    Each entry carries the image as base64 so overview.html stays one self-contained file.
    """
    said = {str(s.get("file")): s for s in notes.get("slides") or [] if isinstance(s, dict)}
    out = []
    for s in (info.get("slides") or {}).get("slides") or []:
        name = str(s.get("file", ""))
        note = said.get(name, {})
        path = folder / "slides" / name
        if not SLIDE_NAME.match(name) or note.get("hide") or not path.is_file():
            continue
        out.append({"file": name, "start": float(s.get("start", 0)), "end": float(s.get("end", 0)),
                    "caption": str(note.get("caption") or ""),
                    "data": base64.b64encode(path.read_bytes()).decode("ascii")})
    return out


def render(folder: Path) -> dict:
    from yt_html import first_mention, render_html
    info = json.loads((folder / "info.json").read_text(encoding="utf-8"))
    if not (info.get("guardrail") or {}).get("allowed"):
        raise Blocked("this folder was not cleared by the study/tech guardrail; nothing rendered")
    segs = json.loads((folder / "transcript.json").read_text(encoding="utf-8"))
    notes = json.loads((folder / "notes.json").read_text(encoding="utf-8"))
    meta = {"source": info.get("transcript_source", ""), "words": sum(len(s["text"].split()) for s in segs),
            "generated": datetime.date.today().isoformat(), "audio": info.get("audio"),
            "warnings": info.get("warnings") or [], "clip": clip_range(info.get("clip") or "")}
    meta["words_per_minute"] = speaking_rate(segs, meta["audio"])
    meta["first_said"] = {t["term"]: first_mention(t["term"], segs) for t in notes.get("terms") or [] if t.get("term")}
    meta["slides"] = load_slides(folder, info, notes)
    keywords = top_keywords(" ".join(s["text"] for s in segs), 30)
    (folder / "overview.md").write_text(overview_markdown(info, notes, meta), encoding="utf-8")
    (folder / "overview.html").write_text(render_html(info, notes, segs, keywords, meta), encoding="utf-8")
    return {"folder": str(folder), "html": str(folder / "overview.html"), "markdown": str(folder / "overview.md"),
            "transcript": str(folder / "transcript.txt"), "notes": str(folder / "notes.json")}


def _place_slides(report: dict | None, captured: Path, folder: Path, old: dict | None, wanted: bool):
    """Move freshly captured slides into folder/slides; keep the previous ones when slides were not asked for."""
    dest = folder / "slides"
    if not wanted:
        return old if old and dest.is_dir() else None
    if dest.is_dir():
        shutil.rmtree(dest)
    if report and report.get("count"):
        shutil.move(str(captured), str(dest))
        return report
    return None


def fetch(url: str, out: Path, lang: str = "en", source: str = "audio", transcript_file: str | None = None,
          model: str = "base", force: bool = False, keep_audio: bool = False, engine: str = "auto",
          clip: str = "", python: str | None = None, get=http_get, runner=subprocess.run, slides: bool = True,
          slides_height: int = 720) -> dict:
    info = check(url, get)
    if not info["guardrail"]["allowed"]:
        raise Blocked(f"not generated: \"{info['title']}\": {info['guardrail']['reason']}. This skill only "
                      "makes overviews of study and technology videos")
    if info["playability"] not in ("OK", "UNKNOWN") and not transcript_file:
        raise NotPlayable(f"YouTube says the video is {info['playability']}: {info['playability_reason']}".strip(": "))
    folder = out / info["video_id"]
    old_info = {}
    if (folder / "info.json").is_file():
        old_info = json.loads((folder / "info.json").read_text(encoding="utf-8"))
    captured = Path(tempfile.mkdtemp(prefix="yt-slides-"))    # moved into the folder only when all went well
    try:
        tr = get_transcript(info, lang, source, transcript_file, model, engine, clip,
                            (folder / "audio") if keep_audio else None, python, get, runner,
                            captured if slides else None, slides_height)
        folder.mkdir(parents=True, exist_ok=True)
        info["slides"] = _place_slides(tr["slides"], captured, folder, old_info.get("slides"), slides)
    finally:
        shutil.rmtree(captured, ignore_errors=True)
    segs = tr["segments"]
    for w in tr["warnings"]:
        print(f"warning: {w}", file=sys.stderr)
    info["transcript_source"] = tr["source"]
    info["audio"] = tr["audio"]
    info["warnings"] = tr["warnings"]
    info["clip"] = clip
    info["fetched"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    write_json(folder / "info.json", info)
    write_json(folder / "transcript.json", segs)
    (folder / "transcript.txt").write_text(transcript_text(segs), encoding="utf-8")
    notes_path = folder / "notes.json"
    if force or not notes_path.exists():
        write_json(notes_path, draft_notes(info, segs))
    result = render(folder)
    result.update(video_id=info["video_id"], title=info["title"], transcript_source=tr["source"],
                  segments=len(segs), words=sum(len(s["text"].split()) for s in segs),
                  audio_processed=bool(tr["audio"]), warnings=tr["warnings"],
                  slides=(info["slides"] or {}).get("count", 0),
                  slides_folder=str(folder / "slides") if info["slides"] else None)
    if any(w.startswith(("audio not processed", "speech-to-text", "slides not captured")) for w in tr["warnings"]):
        fix = doctor(python, runner)            # saves the agent a second command: what to install, ready to run
        fix = fix.get("advice") or ([fix["error"]] if fix.get("error") else [])
        if fix:
            result["fix"] = fix
    if tr["audio"]:
        a = tr["audio"].get("analysis") or {}
        result["audio_summary"] = {k: a.get(k) for k in ("speech_ratio", "pause_count", "longest_pause")}
        result["audio_summary"].update(tr["audio"].get("speech_to_text") or {})
    return result


def doctor(python: str | None = None, runner=subprocess.run) -> dict:
    """What the audio stage can do with the chosen Python, and how to fix what is missing."""
    py = audio_python(python)
    try:
        proc = runner([py, str(AUDIO_SCRIPT), "doctor"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                      timeout=120, check=False)
        rep = json.loads((proc.stdout or "{}").strip().splitlines()[-1])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError) as exc:
        return {"audio_python": py, "error": f"could not run the audio Python: {exc}"}
    advice = []
    if not rep.get("can_download"):
        advice.append(f"{py} -m pip install yt-dlp")
    if not rep.get("can_analyse"):
        advice.append(f"{py} -m pip install av numpy")
    if not rep.get("engines_ready"):
        blocked = [k for k in ("faster-whisper", "whisper", "vosk") if str(rep.get(k, "")).startswith(("cannot", "ctranslate2"))]
        advice.append(f"{py} -m pip install faster-whisper   (best quality; or: vosk for a light engine)")
        if blocked:
            advice.append("an engine is installed but cannot load (" + ", ".join(blocked) + "): its native library is "
                          "missing or blocked by a security policy; try another engine, or a Python version "
                          "the package supports, passed with --audio-python")
    if not rep.get("node"):
        advice.append("optional: install Node.js so yt-dlp can solve YouTube's player challenges")
    rep["audio_python"] = py
    rep["ready"] = bool(rep.get("can_download") and rep.get("engines_ready"))
    rep["advice"] = advice
    return rep


# ---------------------------------------------------------------- CLI
def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="validate the link and apply the study/tech guardrail")
    c.add_argument("url")
    f = sub.add_parser("fetch", help="check, get the transcript, write text + HTML overview")
    f.add_argument("url")
    f.add_argument("--out", default="yt-lecture", help="output folder (default: ./yt-lecture)")
    f.add_argument("--source", choices=SOURCES, default="audio",
                   help="audio (default): extract the audio and turn speech into text, captions only if that "
                        "fails; audio-only: never use captions; captions: captions first (fast), audio if none")
    f.add_argument("--clip", default="", help="process only part of the video, e.g. 10:00-25:00 or 600-1500")
    f.add_argument("--lang", default="en", help="spoken language (en, hi, es...) or 'auto' to detect")
    f.add_argument("--engine", default="auto", choices=["auto", "faster-whisper", "whisper", "vosk"],
                   help="speech-to-text engine (auto tries faster-whisper, whisper, vosk)")
    f.add_argument("--model", default="base",
                   help="whisper size tiny|base|small|medium|large-v3, or a Vosk model folder (default base)")
    f.add_argument("--audio-python", help="Python that has the audio packages (default $YT_LECTURE_AUDIO_PYTHON "
                                          "or this Python)")
    f.add_argument("--transcript", help="use this .vtt/.srt/.txt/.json transcript for the text")
    f.add_argument("--keep-audio", action="store_true", help="keep the extracted audio clip in <folder>/audio")
    f.add_argument("--force", action="store_true", help="overwrite notes.json with a new automatic draft")
    f.add_argument("--no-slides", action="store_true",
                   help="do not capture the slides (skips the video download; audio only)")
    f.add_argument("--slides-height", type=int, default=720, choices=[360, 480, 720, 1080],
                   help="video height used to capture the slides (default 720; 480 downloads less)")
    r = sub.add_parser("render", help="rebuild overview.md and overview.html from a fetched folder")
    r.add_argument("folder")
    d = sub.add_parser("doctor", help="show which audio tools are ready and how to install the rest")
    d.add_argument("--audio-python")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "doctor":
            rep = doctor(args.audio_python)
            print(json.dumps(rep, indent=2, ensure_ascii=False))
            return 0 if rep.get("ready") else 1
        if args.cmd == "check":
            info = check(args.url)
            g = info["guardrail"]
            print(json.dumps({"video_id": info["video_id"], "title": info["title"], "channel": info["channel"],
                              "duration": fmt_time(info["duration"]), "category": info["category"],
                              "chapters": len(info["chapters"]), "playability": info["playability"],
                              "allowed": g["allowed"], "reason": g["reason"], "score": g["score"],
                              "matched": g["matched"]}, indent=2, ensure_ascii=False))
            return 0 if g["allowed"] else 3
        if args.cmd == "fetch":
            res = fetch(args.url, Path(args.out), args.lang, args.source, args.transcript, args.model,
                        args.force, args.keep_audio, args.engine, args.clip, args.audio_python,
                        slides=not args.no_slides, slides_height=args.slides_height)
        else:
            res = render(Path(args.folder))
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0
    except LinkError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Blocked as exc:
        print(f"blocked: {exc}", file=sys.stderr)
        return 3
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4
    except NotPlayable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 5
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
