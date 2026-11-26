#!/usr/bin/env python3
"""Audio stage of yt-lecture-overview: extract a video's audio, analyse it, and turn the speech into text.

Runs in the "audio Python" (any interpreter that has the optional packages; yt_lecture.py starts it with
--audio-python or $YT_LECTURE_AUDIO_PYTHON, default: the same Python). Prints one JSON object on stdout.

  python yt_audio.py doctor
  python yt_audio.py process --url URL --workdir DIR [--clip 10:00-25:00] [--engine auto] [--model base]
                             [--lang en] [--keep-audio DIR] [--no-transcribe]
                             [--slides-dir DIR [--slides-height 720]] [--no-audio]

Tools (all optional, each step reports what is missing). Every step has a no-pip option:
  yt-dlp (program or package)  download the audio track (and, for slides, a low-resolution video-only stream)
  ffmpeg program, or PyAV      decode the audio; find and save the slides (yt_slides.py). The loudness
                               analysis (speech, pauses, pace) is pure Python
  faster-whisper | openai-whisper | vosk | whisper.cpp     speech to text (tried in that order with
                               --engine auto). whisper.cpp is a program (whisper-cli) plus a ggml model file
                               (--model or WHISPER_CPP_MODEL), so it needs no Python package either
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
import tempfile
import threading
import time
import wave
from array import array
from operator import mul
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

RATE = 16000          # speech-to-text engines want 16 kHz mono
WINDOW = 0.5          # seconds per loudness window for the analysis
ENGINES = ("faster-whisper", "whisper", "vosk", "whisper-cpp")
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


AUDIO_FORMAT = "bestaudio[ext=m4a][abr<=96]/bestaudio[ext=m4a]/bestaudio"   # speech needs no more than ~96 kbps


def video_format(height: int) -> str:
    """Video-only stream for slide capture; H.264 first because it decodes fastest."""
    return (f"bestvideo[height<={height}][vcodec^=avc1]/bestvideo[height<={height}]/"
            f"best[height<={height}]/worstvideo")


def _ytdlp(url, workdir: Path, stem: str, fmt: str, what: str) -> Path:
    base = ytdlp_base()
    if not base:
        raise RuntimeError("yt-dlp is not installed in the audio Python (pip install yt-dlp)")
    cmd = base + ["-f", fmt, "--no-playlist", "--no-progress", "--quiet", "--no-warnings",
                  "--concurrent-fragments", "4", "--http-chunk-size", "10M",   # parallel parts, less throttling
                  "-o", str(workdir / f"{stem}.%(ext)s"), "--print", "after_move:filepath"]
    if shutil.which("node"):
        cmd += ["--js-runtimes", "node"]   # lets yt-dlp solve YouTube's player challenges
    proc = subprocess.run(cmd + [url], capture_output=True, text=True, timeout=3600, check=False)
    lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    path = Path(lines[-1]) if lines else None
    if proc.returncode != 0 or not path or not path.is_file():
        found = sorted(workdir.glob(f"{stem}.*"))
        if proc.returncode == 0 and found:
            path = found[0]
        else:
            raise RuntimeError(f"yt-dlp could not download the {what}: " + (proc.stderr or proc.stdout or "")[-500:])
    return path


def download_audio(url, workdir: Path, start=0.0, end=None) -> dict:
    """Download only the audio track (m4a preferred, no ffmpeg needed). Returns file facts."""
    path = _ytdlp(url, workdir, "audio", AUDIO_FORMAT, "audio")
    return {"file": str(path), "format": path.suffix.lstrip("."), "size_bytes": path.stat().st_size,
            "clip": [start, end]}


def capture_slides(url, workdir: Path, slides_dir: Path, start=0.0, end=None, height=720) -> dict:
    """Download a video-only stream, save one image per slide into slides_dir, then delete the video.
    Decodes with PyAV when it is installed, otherwise with the ffmpeg program."""
    if not shutil.which("ffmpeg"):
        _need("av", "av (or install the ffmpeg program)")
        _need("numpy", "numpy (or install the ffmpeg program)")
    from yt_slides import extract_slides  # noqa: PLC0415
    began = time.time()
    video = _ytdlp(url, workdir, "video", video_format(height), "video for the slides")
    downloaded = round(time.time() - began, 1)
    try:
        rep = extract_slides(video, slides_dir, start, end)
    finally:
        video.unlink(missing_ok=True)
    rep["download_seconds"] = downloaded
    return rep


# ---------------------------------------------------------------- decode + analyse
def decode_pcm(path, start=0.0, end=None):
    """Yield (t_seconds, int16 mono 16 kHz bytes) chunks for [start, end): with PyAV when it is installed,
    otherwise with the ffmpeg program (no Python package needed)."""
    av, why = _try_import("av")
    if av is None:
        if shutil.which("ffmpeg"):
            yield from _decode_pcm_ffmpeg(path, start, end)
            return
        raise RuntimeError(f"PyAV {why}: install the ffmpeg program, or pip install av")
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


def _decode_pcm_ffmpeg(path, start=0.0, end=None, chunk_seconds=10):
    cmd = [shutil.which("ffmpeg"), "-v", "error", "-nostdin"]
    if start > 0:
        cmd += ["-ss", "%.3f" % start]
    cmd += ["-i", str(path)]
    if end is not None:
        cmd += ["-t", "%.3f" % (end - start)]
    cmd += ["-vn", "-sn", "-dn", "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    t, size = float(start), int(chunk_seconds * RATE) * 2
    try:
        while True:
            data = proc.stdout.read(size)
            if not data:
                break
            data = data[:len(data) - len(data) % 2]
            yield t, data
            t += len(data) / 2 / RATE
    finally:
        proc.stdout.close()
        proc.wait()
    if proc.returncode not in (0, None) and t == start:
        raise RuntimeError("ffmpeg could not decode the audio")


def _ffprobe_facts(path) -> dict:
    exe = shutil.which("ffprobe")
    if not exe:
        return {}
    try:
        res = subprocess.run([exe, "-v", "error", "-select_streams", "a:0", "-show_streams", "-show_format",
                              "-of", "json", str(path)], capture_output=True, text=True, timeout=60)
        data = json.loads(res.stdout or "{}")
    except (OSError, ValueError, subprocess.SubprocessError):
        return {}
    st = (data.get("streams") or [{}])[0]
    fm = data.get("format") or {}
    bitrate = int(st.get("bit_rate") or fm.get("bit_rate") or 0)
    dur = float(fm.get("duration") or st.get("duration") or 0)
    return {"codec": st.get("codec_name"), "sample_rate": int(st.get("sample_rate") or 0) or None,
            "channels": st.get("channels"), "bitrate_kbps": round(bitrate / 1000), "duration": round(dur, 2)}


def stream_facts(path) -> dict:
    av, why = _try_import("av")
    if av is None:
        return _ffprobe_facts(path)
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


def window_dbfs(pcm: bytes) -> float:
    """Loudness (dBFS) of one window of int16 little-endian mono samples. Pure Python, no numpy."""
    a = array("h")
    a.frombytes(pcm)
    if sys.byteorder == "big":
        a.byteswap()
    n = len(a) or 1
    rms = math.sqrt(sum(map(mul, a, a)) / n) / 32768.0 + 1e-9
    return 20 * math.log10(rms)


def analyse_audio(path, start=0.0, end=None) -> dict:
    levels, buf = [], b""
    win_bytes = int(WINDOW * RATE) * 2
    for _, data in decode_pcm(path, start, end):
        buf += data
        while len(buf) >= win_bytes:
            levels.append(window_dbfs(buf[:win_bytes]))
            buf = buf[win_bytes:]
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
            if name == "whisper-cpp":
                return _whisper_cpp(path, model, lang, start, end)
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
    # greedy decoding (beam 1) is ~2x faster on a CPU with little loss on clear lecture speech; not feeding the
    # previous text back in stops the repeated-phrase loops whisper can fall into on long recordings
    kwargs = {"language": None if lang == "auto" else lang, "vad_filter": True, "beam_size": 1,
              "condition_on_previous_text": False}
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
    audio = pcm_float32(path, start, end)          # decoded here (PyAV or the ffmpeg program)
    res = whisper.load_model(model).transcribe(audio, language=None if lang == "auto" else lang, fp16=False,
                                               condition_on_previous_text=False)
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


def whisper_cpp_program():
    """The whisper.cpp command-line program: $WHISPER_CPP, or whisper-cli / whisper-cpp on PATH."""
    env = os.environ.get("WHISPER_CPP")
    if env and os.path.isfile(env):
        return env
    return shutil.which("whisper-cli") or shutil.which("whisper-cpp")


def _whisper_cpp(path, model, lang, start, end):
    """Speech to text with the whisper.cpp program and a ggml model file: no Python package needed."""
    exe = whisper_cpp_program()
    if not exe:
        raise _Unavailable("the whisper.cpp program (whisper-cli) is not installed; or set WHISPER_CPP")
    model_path = model if model and os.path.isfile(model) else os.environ.get("WHISPER_CPP_MODEL")
    if not model_path or not os.path.isfile(model_path):
        raise _Unavailable("whisper.cpp needs a ggml model file: --model path/to/ggml-base.bin or WHISPER_CPP_MODEL")
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "audio.wav")
        with wave.open(wav, "wb") as w:                    # whisper.cpp reads 16 kHz mono WAV
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            for _, data in decode_pcm(path, start, end):
                w.writeframes(data)
        prefix = os.path.join(tmp, "out")
        cmd = [exe, "-m", model_path, "-f", wav, "-l", lang or "auto", "-oj", "-of", prefix, "-np"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=6 * 3600, check=False)
        try:
            with open(prefix + ".json", encoding="utf-8") as fh:
                res = json.load(fh)
        except (OSError, ValueError):
            raise _Unavailable("whisper.cpp failed: " + (proc.stderr or proc.stdout or "")[-300:]) from None
    segs = []
    for item in res.get("transcription") or []:
        off = item.get("offsets") or {}
        text = (item.get("text") or "").strip()
        if text:
            segs.append({"start": round(off.get("from", 0) / 1000 + start, 2),
                         "end": round(off.get("to", 0) / 1000 + start, 2), "text": " " + text})
    return {"engine": "whisper-cpp", "model": os.path.basename(model_path),
            "language": ((res.get("result") or {}).get("language")) or lang, "segments": segs}


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
    cpp = whisper_cpp_program()
    model = os.environ.get("WHISPER_CPP_MODEL")
    out["whisper-cpp"] = ("ok" if model and os.path.isfile(model) else "program found; set WHISPER_CPP_MODEL") \
        if cpp else "not installed"
    out["can_download"] = out["yt-dlp"] == "ok" or bool(shutil.which("yt-dlp"))
    decoder = out["av"] == "ok" or out["ffmpeg"]                 # PyAV, or the ffmpeg program
    out["can_analyse"] = bool(decoder)                           # the loudness analysis is pure Python
    out["can_capture_slides"] = out["can_download"] and (out["ffmpeg"] or (out["av"] == "ok" and out["numpy"] == "ok"))
    out["engines_ready"] = [e for e in ENGINES if out[e] == "ok"] if decoder else []
    return out


def process(args) -> dict:
    """Audio (and, with --slides-dir, slides) for one video. The slide video downloads and is scanned in a
    second thread while the audio is downloaded, analysed and transcribed, so slides add little time."""
    start, end = parse_clip(args.clip)
    work = Path(args.workdir)
    work.mkdir(parents=True, exist_ok=True)
    result = {"errors": []}
    slides_job = None
    if args.slides_dir:
        def job():
            try:
                result["slides"] = capture_slides(args.url, work, Path(args.slides_dir), start, end,
                                                  args.slides_height)
            except (RuntimeError, ValueError, OSError, subprocess.SubprocessError, _Unavailable) as exc:
                result["errors"].append(f"slides not captured: {exc}")
            except Exception as exc:  # noqa: BLE001 - a decoder error must not lose the audio result
                result["errors"].append(f"slides not captured: {type(exc).__name__}: {exc}")
        slides_job = threading.Thread(target=job, daemon=True)
        slides_job.start()
    try:
        if not args.no_audio:
            _process_audio(args, work, start, end, result)
    finally:
        if slides_job:
            slides_job.join()
    return result


def _process_audio(args, work: Path, start, end, result: dict) -> None:
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
    p.add_argument("--no-audio", action="store_true", help="skip the audio (slides only)")
    p.add_argument("--slides-dir", default="", help="also capture the slides into this folder")
    p.add_argument("--slides-height", type=int, default=720, help="video height used for the slides")
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
