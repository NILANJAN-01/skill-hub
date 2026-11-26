# Audio stage: setup, engines and how it works

The audio stage is `scripts/yt_audio.py`. `yt_lecture.py fetch` runs it as a separate process in the **audio Python**. That interpreter is chosen in this order: `--audio-python <path>`, then the `YT_LECTURE_AUDIO_PYTHON` environment variable, then the same Python that runs `yt_lecture.py`. Because the stage runs separately, its heavy packages can live in their own virtual environment while the main script stays standard-library only.

Every step can also run with **no Python package at all**: the yt-dlp program downloads, the ffmpeg program decodes, the analysis is pure Python, and the whisper.cpp program (`whisper-cli` with a ggml model file) turns speech into text. See [Without pip](#without-pip).

## What it does

1. **Extract**: `yt-dlp -f "bestaudio[ext=m4a][abr<=96]/bestaudio[ext=m4a]/bestaudio" --no-playlist` downloads only the audio track (under 1 MB per minute) into a temporary folder. Speech needs no more than about 96 kbps. `--concurrent-fragments 4 --http-chunk-size 10M` downloads in parallel parts and avoids YouTube's throttling of single long requests. If Node.js is installed, `--js-runtimes node` is added so that yt-dlp can solve YouTube's player challenges. ffmpeg is not needed.
2. **Decode**: PyAV (when installed) or the ffmpeg program decodes the track and resamples it to 16 kHz mono. `--clip` seeks to the start and stops at the end, so only that part is processed.
3. **Analyse** (pure Python): the loudness of every 0.5-second window is measured in dBFS. A window counts as speech when it is louder than a threshold between the noise floor and the speech level. The threshold is never closer than 12 dB to the speech level. The results:
   - `speech_ratio` and `speech_seconds` (and from them, words per minute)
   - `pauses` of 2 s or more (the longest 12) and `pause_count`
   - `speech_per_minute` (the chart on the page), mean and peak loudness, and the noise floor

   These are estimates. Background music counts as "speech", and a very quiet speaker may show as pauses.
4. **Speech to text**: the engines are tried in this order with `--engine auto`:

| Engine | Install | Quality / speed | Notes |
|---|---|---|---|
| faster-whisper | `pip install faster-whisper` | Best accuracy with punctuation. `base` is fast; `small`/`medium` are better and slower | Uses CTranslate2. Its optional voice filter needs `onnxruntime`; without it, the script runs without the filter |
| openai-whisper | `pip install openai-whisper` | Same models, slower on a CPU | Needs PyTorch. The script decodes the audio itself, so ffmpeg is not needed |
| vosk | `pip install vosk` | Lighter, no punctuation, all lower case | Works on any Python 3. Downloads a small model on first use, or set `VOSK_MODEL_PATH` / `--model <folder>` (models at alphacephei.com/vosk/models) |
| whisper.cpp | the `whisper-cli` program (no pip) and a ggml model file | Whisper quality, fast on a CPU | Set `WHISPER_CPP_MODEL` to the model file (e.g. `ggml-base.bin` from huggingface.co/ggerganov/whisper.cpp) or pass `--model <file>`; `WHISPER_CPP` points at the program if it is not on PATH |

   Whisper engines run greedy decoding (beam size 1) and do not feed the previous text back in. This is about twice as fast on a CPU, with little loss on clear lecture speech, and it avoids the repeated-phrase loops whisper can fall into on long recordings.
5. **Slides, in parallel** (`scripts/yt_slides.py`: PyAV + numpy when installed, otherwise the ffmpeg program; nothing extra to install). A second thread downloads a video-only stream of 720p or less, H.264 first because it decodes fastest (`--slides-height` changes the height). It then samples one frame a second and compares 64×36 grey thumbnails:
   - a change over 12% of the pixels starts a new scene;
   - a scene shown for 3 s or more is a slide, and its last frame is saved, so builds are complete;
   - a repeat of an earlier slide is recorded as `shown_again`;
   - blank frames are skipped;
   - camera shots are skipped: soft images with few sharp edges, or images that keep moving and have little flat area. Slides with a small webcam in a corner stay.

   On a laptop, a 10-minute 720p video took about 10 s to download and 12 s to scan, while speech-to-text ran at the same time. The video file is deleted right after the scan.
6. **Clean up**: the temporary folder (audio and video) is removed unless `--keep-audio` is given. Slide images go to `<folder>/slides/` only when the whole fetch succeeds.

## Setting up a separate audio Python

```bash
# Windows (py launcher). Use a Python version the packages publish wheels for.
py -3.12 -m venv .yt-audio
.yt-audio\Scripts\python -m pip install yt-dlp av numpy faster-whisper
set YT_LECTURE_AUDIO_PYTHON=%CD%\.yt-audio\Scripts\python.exe

# macOS / Linux
python3.12 -m venv .yt-audio
.yt-audio/bin/python -m pip install yt-dlp av numpy faster-whisper
export YT_LECTURE_AUDIO_PYTHON="$PWD/.yt-audio/bin/python"

python scripts/yt_lecture.py doctor        # should end with "ready": true
```

## Without pip

```bash
# Windows
winget install yt-dlp Gyan.FFmpeg
# macOS
brew install yt-dlp ffmpeg whisper-cpp
# Linux: yt-dlp and ffmpeg from the package manager; build whisper.cpp (github.com/ggml-org/whisper.cpp)

export WHISPER_CPP_MODEL="$PWD/ggml-base.bin"      # a ggml model file you downloaded
python scripts/yt_lecture.py doctor                  # should end with "ready": true
```

Without a speech-to-text engine, `fetch` still works: it uses the captions, and the audio analysis and slides still run.

## When `doctor` says an engine "cannot load"

`cannot load (DLL load failed ...)` or `(... blocked ...)` means the package is installed but its native library cannot run. The usual causes:

- **No build for this Python version yet.** Use an older Python (often one or two versions back) in a virtual environment, as shown above.
- **A security policy blocks the library**, for example Windows Smart App Control or an application-control policy on a managed machine. Do not try to get around the policy. Use another engine that is allowed (for example `--engine vosk`), or ask the machine's administrator.
- **A missing system library**, such as the Visual C++ runtime on Windows or libgomp on Linux. Install it from the vendor.

## Speed

Speech-to-text runs on the CPU unless a supported GPU is available. Rough guide for a one-hour lecture on a laptop CPU: Vosk small takes about 8 minutes, faster-whisper `base` 6 to 15, and `small` 15 to 40. `--clip` or a smaller model is the quickest fix. Downloading the audio takes seconds to a minute.
