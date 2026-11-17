#!/usr/bin/env python3
"""Audio stage of yt-lecture-overview: extract a video's audio, analyse it, and turn the speech into text.

Runs in the "audio Python" (any interpreter that has the optional packages; yt_lecture.py starts it with
--audio-python or $YT_LECTURE_AUDIO_PYTHON, default: the same Python). Prints one JSON object on stdout.

  python yt_audio.py doctor
  python yt_audio.py process --url URL --workdir DIR [--clip 10:00-25:00] [--engine auto] [--model base]
                             [--lang en] [--keep-audio DIR] [--no-transcribe]

Packages (all optional, each step reports what is missing):
  yt-dlp                       download the audio track only (no video)
  av (PyAV) + numpy            decode the audio and analyse it (speech vs silence, pauses, loudness)
  faster-whisper | openai-whisper | vosk     speech to text (tried in that order with --engine auto)
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

RATE = 16000          # speech-to-text engines want 16 kHz mono
WINDOW = 0.5          # seconds per loudness window for the analysis
ENGINES = ("faster-whisper", "whisper", "vosk")
VOSK_LANGS = {"en": "en-us", "hi": "hi", "es": "es", "fr": "fr", "de": "de", "ru": "ru", "pt": "pt",
              "it": "it", "ja": "ja", "zh": "cn", "ko": "ko", "tr": "tr", "vi": "vn", "nl": "nl"}


def _try_import(name):
    """Import a module; return (module, None) or (None, reason). DLLs blocked by policy show up here."""
    try:
        return importlib.import_module(name), None
    except ImportError as exc:
        msg = str(exc)
        if "No module named" in msg:
            return None, "not installed"
        return None, f"cannot load ({msg.splitlines()[0][:160]})"
    except OSError as exc:
        return None, f"cannot load ({str(exc)[:160]})"


def parse_clip(text):
    """'10:00-25:00', '600-1500' or '1:02:00-' -> (start, end or None) in seconds."""
    if not text:
        return 0.0, None
    m = re.match(r"^\s*([\d:.]*)\s*-\s*([\d:.]*)\s*$", text)
    if not m:
        raise ValueError(f"bad --clip {text!r}; use START-END like 10:00-25:00")

    def sec(s):
        total = 0.0
        for part in s.split(":"):
            total = total * 60 + float(part)
        return total
    start = sec(m.group(1)) if m.group(1) else 0.0
    end = sec(m.group(2)) if m.group(2) else None
    if end is not None and end <= start:
        raise ValueError("--clip end must be after its start")
    return start, end


# ---------------------------------------------------------------- download
def ytdlp_base():
    mod, _ = _try_import("yt_dlp")
    if mod is not None:
        return [sys.executable, "-m", "yt_dlp"]
    exe = shutil.which("yt-dlp")
    return [exe] if exe else None


def download_audio(url, workdir: Path, start=0.0, end=None) -> dict:
    """Download only the audio track (m4a preferred, no ffmpeg needed). Returns file facts."""
    base = ytdlp_base()
    if not base:
        raise RuntimeError("yt-dlp is not installed in the audio Python (pip install yt-dlp)")
    cmd = base + ["-f", "bestaudio[ext=m4a]/bestaudio", "--no-playlist", "--no-progress", "--quiet",
                  "--no-warnings", "-o", str(workdir / "audio.%(ext)s"), "--print", "after_move:filepath"]
    if shutil.which("node"):
        cmd += ["--js-runtimes", "node"]   # lets yt-dlp solve YouTube's player challenges
    proc = subprocess.run(cmd + [url], capture_output=True, text=True, timeout=3600, check=False)
    lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    path = Path(lines[-1]) if lines else None
    if proc.returncode != 0 or not path or not path.is_file():
        found = sorted(workdir.glob("audio.*"))
        if proc.returncode == 0 and found:
            path = found[0]
        else:
            raise RuntimeError("yt-dlp could not download the audio: " + (proc.stderr or proc.stdout or "")[-500:])
    return {"file": str(path), "format": path.suffix.lstrip("."), "size_bytes": path.stat().st_size,
            "clip": [start, end]}


# ---------------------------------------------------------------- decode + analyse
def decode_pcm(path, start=0.0, end=None):
    """Yield (t_seconds, int16 mono 16 kHz bytes) chunks for [start, end) using PyAV."""
    av, why = _try_import("av")
    if av is None:
        raise RuntimeError(f"PyAV {why} (pip install av)")
    with av.open(str(path)) as container:
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="s16", layout="mono", rate=RATE)
        if start > 1:
            container.seek(int(max(0, start - 1) / stream.time_base), stream=stream)
        t = None
        for frame in container.decode(stream):
            for out in resampler.resample(frame) or []:
                if t is None:
                    t = float(frame.pts * stream.time_base) if frame.pts is not None else 0.0
                data = bytes(out.planes[0])[: out.samples * 2]
                seg_start, seg_end = t, t + out.samples / RATE
                t = seg_end
                if seg_end <= start:
                    continue
                if seg_start < start:   # trim the head of the first chunk
                    data = data[int((start - seg_start) * RATE) * 2:]
                    seg_start = start
                if end is not None and seg_start >= end:
                    return
                if end is not None and seg_end > end:
                    data = data[: int((end - seg_start) * RATE) * 2]
                yield seg_start, data


def stream_facts(path) -> dict:
    av, why = _try_import("av")
    if av is None:
        return {}
    with av.open(str(path)) as c:
        s = c.streams.audio[0]
        dur = float(c.duration / 1_000_000) if c.duration else (float(s.duration * s.time_base) if s.duration else 0)
        return {"codec": s.codec_context.name, "sample_rate": s.codec_context.sample_rate,
                "channels": s.codec_context.channels if hasattr(s.codec_context, "channels") else None,
                "bitrate_kbps": round((c.bit_rate or s.bit_rate or 0) / 1000), "duration": round(dur, 2)}


def analyse_levels(levels, start=0.0) -> dict:
    """Speech vs silence from per-window loudness (dBFS). Pure Python so it is easy to test."""
    if not levels:
        return {}
    ordered = sorted(levels)
    floor = ordered[int(len(ordered) * 0.10)]
    loud = ordered[int(len(ordered) * 0.90)]
    # between the noise floor and speech level, but never closer than 12 dB to speech: when a lecture has
    # little silence the 10th percentile is itself speech, and quieter speech must not count as a pause
    threshold = max(min(floor + 0.35 * (loud - floor), loud - 12.0), -55.0)
    speech = [db > threshold for db in levels]
    pauses, run = [], 0
    for i, s in enumerate(speech + [True]):
        if not s:
            run += 1
        elif run:
            length = run * WINDOW
            if length >= 2.0:
                pauses.append({"start": round(start + (i - run) * WINDOW, 1), "length": round(length, 1)})
            run = 0
    per_min = []
    step = int(60 / WINDOW)
    for i in range(0, len(speech), step):
        chunk = speech[i:i + step]
        per_min.append(round(sum(chunk) / len(chunk), 2))
    speech_s = sum(speech) * WINDOW
    total = len(levels) * WINDOW
    return {"analysed_seconds": round(total, 1), "speech_seconds": round(speech_s, 1),
            "speech_ratio": round(speech_s / total, 3) if total else 0,
            "mean_dbfs": round(sum(levels) / len(levels), 1), "peak_dbfs": round(ordered[-1], 1),
            "noise_floor_dbfs": round(floor, 1), "threshold_dbfs": round(threshold, 1),
            "pauses": sorted(pauses, key=lambda p: -p["length"])[:12], "pause_count": len(pauses),
            "longest_pause": max((p["length"] for p in pauses), default=0),
            "speech_per_minute": per_min, "method": "loudness windows of 0.5 s (estimate)"}


def analyse_audio(path, start=0.0, end=None) -> dict:
    np, why = _try_import("numpy")
    if np is None:
        raise RuntimeError(f"numpy {why} (pip install numpy)")
    levels, buf = [], b""
    win_bytes = int(WINDOW * RATE) * 2
    for _, data in decode_pcm(path, start, end):
        buf += data
        while len(buf) >= win_bytes:
            x = np.frombuffer(buf[:win_bytes], dtype=np.int16).astype(np.float32) / 32768.0
            buf = buf[win_bytes:]
            rms = float(np.sqrt(np.mean(x * x))) + 1e-9
            levels.append(20 * math.log10(rms))
    return analyse_levels(levels, start)


def pcm_float32(path, start=0.0, end=None):
    np, _ = _try_import("numpy")
    parts = [np.frombuffer(d, dtype=np.int16) for _, d in decode_pcm(path, start, end)]
    return (np.concatenate(parts).astype(np.float32) / 32768.0) if parts else np.zeros(0, dtype=np.float32)


# ---------------------------------------------------------------- speech to text
def transcribe(path, engine="auto", model="base", lang="en", start=0.0, end=None) -> dict:
    order = ENGINES if engine == "auto" else (engine,)
    reasons = {}
    for name in order:
        try:
            if name == "faster-whisper":
                return _faster_whisper(path, model, lang, start, end)
            if name == "whisper":
                return _openai_whisper(path, model, lang, start, end)
            if name == "vosk":
                return _vosk(path, model, lang, start, end)
            reasons[name] = "unknown engine"
        except _Unavailable as exc:
            reasons[name] = str(exc)
    raise RuntimeError("no speech-to-text engine could run: " +
                       "; ".join(f"{k}: {v}" for k, v in reasons.items()))


class _Unavailable(RuntimeError):
    pass


def _need(module, pip_name):
    mod, why = _try_import(module)
    if mod is None:
        raise _Unavailable(f"{why} (pip install {pip_name})")
    return mod


def _faster_whisper(path, model, lang, start, end):
    fw = _need("faster_whisper", "faster-whisper")
    _need("av", "av")
    m = fw.WhisperModel(model, device="auto", compute_type="int8")
    audio = str(path) if not start and end is None else pcm_float32(path, start, end)
    offset = start if not isinstance(audio, str) else 0.0
    kwargs = {"language": None if lang == "auto" else lang, "vad_filter": True}
    try:
        segs, info = m.transcribe(audio, **kwargs)
        segs = list(segs)
    except (ImportError, OSError):     # the VAD filter needs onnxruntime; run without it
        kwargs["vad_filter"] = False
        segs, info = m.transcribe(audio, **kwargs)
        segs = list(segs)
    return {"engine": "faster-whisper", "model": model, "language": info.language,
            "language_probability": round(float(info.language_probability or 0), 3),
            "segments": [{"start": round(s.start + offset, 2), "end": round(s.end + offset, 2), "text": s.text}
                         for s in segs]}


def _openai_whisper(path, model, lang, start, end):
    whisper = _need("whisper", "openai-whisper")
    _need("av", "av")
    audio = pcm_float32(path, start, end)          # decoded here, so ffmpeg is not needed
    res = whisper.load_model(model).transcribe(audio, language=None if lang == "auto" else lang, fp16=False)
    return {"engine": "whisper", "model": model, "language": res.get("language", lang),
            "segments": [{"start": round(s["start"] + start, 2), "end": round(s["end"] + start, 2), "text": s["text"]}
                         for s in res.get("segments", [])]}


def _vosk(path, model, lang, start, end):
    vosk = _need("vosk", "vosk")
    vosk.SetLogLevel(-1)
    model_path = model if model and os.path.isdir(model) else os.environ.get("VOSK_MODEL_PATH")
    if model_path:
        vm = vosk.Model(model_path=model_path)
    else:
        code = VOSK_LANGS.get((lang or "en").split("-")[0], "en-us")
        try:
            vm = vosk.Model(lang=code)      # vosk downloads its small model on first use
        except Exception as exc:  # noqa: BLE001 - vosk raises plain Exception
            raise _Unavailable(f"no Vosk model for '{code}' ({exc}); set VOSK_MODEL_PATH or --model <folder>")
    rec = vosk.KaldiRecognizer(vm, RATE)
    rec.SetWords(True)
    segs = []

    def take(result):
        r = json.loads(result)
        words = r.get("result") or []
        if words and r.get("text"):
            segs.append({"start": round(words[0]["start"] + start, 2), "end": round(words[-1]["end"] + start, 2),
                         "text": r["text"]})
    for _, data in decode_pcm(path, start, end):
        if rec.AcceptWaveform(data):
            take(rec.Result())
    take(rec.FinalResult())
    return {"engine": "vosk", "model": os.path.basename(model_path) if model_path else f"small-{lang}",
            "language": lang, "segments": segs}


# ---------------------------------------------------------------- commands
def doctor() -> dict:
    out = {"python": sys.executable, "version": sys.version.split()[0], "node": bool(shutil.which("node")),
           "ffmpeg": bool(shutil.which("ffmpeg"))}
    for label, module in (("yt-dlp", "yt_dlp"), ("av", "av"), ("numpy", "numpy"),
                          ("faster-whisper", "faster_whisper"), ("whisper", "whisper"), ("vosk", "vosk")):
        mod, why = _try_import(module)
        out[label] = "ok" if mod is not None else why
    if out["faster-whisper"] == "ok":
        _, why = _try_import("ctranslate2")
        if why:
            out["faster-whisper"] = f"ctranslate2 {why}"
    out["can_download"] = out["yt-dlp"] == "ok" or bool(shutil.which("yt-dlp"))
    out["can_analyse"] = out["av"] == "ok" and out["numpy"] == "ok"
    out["engines_ready"] = [e for e in ENGINES if out[e] == "ok"] if out["av"] == "ok" else []
    return out


def process(args) -> dict:
    start, end = parse_clip(args.clip)
    work = Path(args.workdir)
    work.mkdir(parents=True, exist_ok=True)
    result = {"errors": []}
    audio = download_audio(args.url, work, start, end)
    result["audio"] = audio
    result["audio"].update(stream_facts(audio["file"]))
    try:
        result["analysis"] = analyse_audio(audio["file"], start, end)
    except RuntimeError as exc:
        result["errors"].append(f"analysis skipped: {exc}")
    if not args.no_transcribe:
        try:
            result["transcript"] = transcribe(audio["file"], args.engine, args.model, args.lang, start, end)
        except RuntimeError as exc:
            result["errors"].append(f"speech-to-text: {exc}")
    if args.keep_audio:
        keep = Path(args.keep_audio)
        keep.mkdir(parents=True, exist_ok=True)
        target = keep / Path(audio["file"]).name
        shutil.copy2(audio["file"], target)
        result["audio"]["kept"] = str(target)
    result["audio"]["file"] = Path(audio["file"]).name
    return result


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="audio stage of yt-lecture-overview")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    p = sub.add_parser("process")
    p.add_argument("--url", required=True)
    p.add_argument("--workdir", required=True)
    p.add_argument("--clip", default="")
    p.add_argument("--engine", default="auto", choices=("auto",) + ENGINES)
    p.add_argument("--model", default="base")
    p.add_argument("--lang", default="en")
    p.add_argument("--keep-audio", default="")
    p.add_argument("--no-transcribe", action="store_true")
    args = ap.parse_args(argv)
    try:
        out = doctor() if args.cmd == "doctor" else process(args)
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"fatal": str(exc)}))
        return 1
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
