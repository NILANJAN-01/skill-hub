# Audio stage: setup, engines and how it works

The audio stage is `scripts/yt_audio.py`. `yt_lecture.py fetch` runs it as a separate process in the **audio Python**. That interpreter is chosen in this order: `--audio-python <path>`, then the `YT_LECTURE_AUDIO_PYTHON` environment variable, then the same Python that runs `yt_lecture.py`. Because the stage runs separately, its heavy packages can live in their own virtual environment while the main script stays standard-library only.

## What it does

1. **Extract**: `yt-dlp -f "bestaudio[ext=m4a]/bestaudio" --no-playlist` downloads only the audio track (about 1 MB per minute) into a temporary folder. If Node.js is installed, `--js-runtimes node` is added so that yt-dlp can solve YouTube's player challenges. ffmpeg is not needed.
2. **Decode**: PyAV decodes the track and resamples it to 16 kHz mono. `--clip` seeks to the start and stops at the end, so only that part is processed.
3. **Analyse** (numpy): the loudness of every 0.5-second window is measured in dBFS. A window counts as speech when it is louder than a threshold between the noise floor and the speech level. The threshold is never closer than 12 dB to the speech level. The results:
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

5. **Clean up**: the temporary folder (with the audio) is removed unless `--keep-audio` is given.

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

## When `doctor` says an engine "cannot load"

`cannot load (DLL load failed ...)` or `(... blocked ...)` means the package is installed but its native library cannot run. The usual causes:

- **No build for this Python version yet.** Use an older Python (often one or two versions back) in a virtual environment, as shown above.
- **A security policy blocks the library**, for example Windows Smart App Control or an application-control policy on a managed machine. Do not try to get around the policy. Use another engine that is allowed (for example `--engine vosk`), or ask the machine's administrator.
- **A missing system library**, such as the Visual C++ runtime on Windows or libgomp on Linux. Install it from the vendor.

## Speed

Speech-to-text runs on the CPU unless a supported GPU is available. Rough guide for a one-hour lecture on a laptop CPU: Vosk small takes about 8 minutes, faster-whisper `base` 6 to 15, and `small` 15 to 40. `--clip` or a smaller model is the quickest fix. Downloading the audio takes seconds to a minute.
