---
name: video-inspector
description: Analyse a video file (MP4, MOV, MKV, WebM, AVI) with a ready-made Python script, covering metadata (duration, fps, frame count, codec, resolution, rotation, audio, GPS), extracting frames as PNG/JPG images, per-frame colours, brightness, sharpness and motion, scene changes, black and frozen/static sections, the colour of a pixel or area over time, a per-frame pixel map or full pixel CSV, and a plain-text description and timeline (TXT, JSON, CSV). Use this skill whenever the user wants to analyse, describe or summarise a video or screen recording, split a video into frames or extract a frame at a time, check a recording for black screens, freezes or flicker, track an LED, icon or indicator colour over time, or get pixel data from video frames. Prefer it over writing one-off video code.
license: Complete terms in the repository README
compatibility: Needs Python 3.8+ and OpenCV (pip install opencv-python-headless, which includes numpy and FFmpeg decoding). Metadata of MP4/MOV files (--info) works with the standard library alone.
metadata:
  title: "Video inspector: frames, pixels and description"
  category: video-tools
---

# Video inspector: frames, pixels and text description

`scripts/video_inspector.py` samples frames from a video, analyses each one, and writes the results into a **separate output folder** per video (default `video-reports/<video name>/`):

| File | Contents |
|---|---|
| `report.txt` | Plain-text description of the video, then one line per analysed frame (the timeline) |
| `report.json` | Everything: metadata, every analysed frame, scenes, black and static sections, pixel tracks |
| `timeline.csv` | One row per analysed frame: time, brightness, contrast, mean and dominant colours, motion, scene change, black, frozen, sharpness, image |
| `tracks.csv` | With `--pixel` / `--region`: the colour at each analysed time |
| `frames/` | Frame images: the first frame of each scene by default, or every analysed frame with `--save-frames`. With `--pixels-csv`, a `x,y,r,g,b` CSV next to each saved frame |

Per analysed frame, the report has the time and frame number, brightness and level, contrast, mean colour, the top 3 colours with names and percentages, a 3x3 grid of colour names, sharpness, motion compared with the previous analysed frame, and flags for scene change, black and frozen. With `--grid N` it also has a pixel map. The full field reference is in [references/output-format.md](references/output-format.md).

## When to use

- The user wants a video or screen recording analysed, described or summarised.
- The user wants frames extracted: every N seconds, N frames in total, at given times, or every frame of a short part.
- The user wants to check a recording, for example an infotainment or app screen recording from a test run, for black screens, freezes, unexpected scene changes or flicker.
- The user wants the colour of a pixel or area over time: an LED, a status icon, a warning light, a progress bar.
- The user wants pixel data (a pixel map or a full CSV) for one or more frames.

## When NOT to use

- Editing or converting video (cutting, re-encoding, adding audio). This skill only reads videos.
- Audio analysis or speech transcription. The script only reports whether there is an audio track and its format.
- Recognising people. Don't identify real people from their faces.

## Procedure

`scripts/…` below means the `scripts` folder inside this skill's folder. Run the commands from the user's project with the full path to the script, so that `video-reports/` is created there. Or pass `--out <folder>`.

1. **Check OpenCV.** Run `python -c "import cv2"`. If it fails, ask the user before installing: `pip install opencv-python-headless`. Until then, `--info` still reports the metadata of MP4/MOV files.
2. **Start with the metadata** when the video is unknown or long:
   ```bash
   python scripts/video_inspector.py clip.mp4 --info      # duration, fps, frames, codec, size, rotation, audio
   ```
3. **Analyse.** Pick how frames are chosen (only one of `--frames`, `--at`, `--every-frame`):
   ```bash
   python scripts/video_inspector.py clip.mp4                       # one frame per second (default)
   python scripts/video_inspector.py clip.mp4 --every 0.25          # finer: 4 frames per second
   python scripts/video_inspector.py clip.mp4 --frames 12           # 12 frames spread over the video
   python scripts/video_inspector.py clip.mp4 --at 0:05,0:12.5,50%  # specific times (s, m:ss, h:mm:ss, %)
   python scripts/video_inspector.py clip.mp4 --every-frame --start 10 --end 12   # every frame of a short part
   python scripts/video_inspector.py recordings/ --out reports      # every video in a folder
   ```
   - **Frames to images:** `--save-frames` saves every analysed frame (`--image-format jpg` for smaller files). `--no-frames` saves none. By default, only the first frame of each scene is saved.
   - **Colour over time:** `--pixel X,Y` and `--region X,Y,W,H` (repeatable) track a pixel or the mean colour of an area. Coordinates are in the decoded frame, 0-based from the top-left.
   - **One frame in depth:** `--at 4.5 --save-frames --grid 32 --pixels-csv` gives the frame image, a 32-column pixel map and every pixel as CSV.
   - **Detection settings:** `--scene-threshold` (default 0.35; lower finds more scene changes), `--freeze-motion` (default 0.5) and `--freeze-min` (seconds, default 1).
   - **Limits:** `--max-frames` (default 300 analysed; a long video is sampled more sparsely, with a warning), `--max-saved` (default 500 images) and `--max-csv-pixels`.
   - `--stdout` prints the JSON and writes nothing (unless `--save-frames`). `--include-gps` adds the location from the metadata.
4. **Read `report.txt` first.** It has the description and the timeline. Use `report.json` or the CSVs for exact numbers.
5. **Look at the key frames** in `frames/` if you can view images, and describe what they show (screens, objects, text). Keep that apart from the measured facts. If the image-inspector skill is available, it can analyse a saved frame further (exact pixels, OCR, finding an icon).
6. **Report.** Give the description, the scenes with their times, any black or static sections, the pixel tracks, and the paths of the output files. Pass on the warnings: a GPS location in the file, a variable frame rate (times are approximate), sampling made sparser by `--max-frames`, or a video that ended early.

## How to read the results

| Field | Meaning |
|---|---|
| `scenes[]` | Starts where the colour histogram changes a lot from the previous analysed frame. Fast cuts between analysed frames are seen; changes inside one step are not |
| `black_segments` | Frames with average brightness under 16 and almost no contrast |
| `frozen_segments` | Analysed frames with (almost) no change from the previous one. For a UI recording, this can be a normal static screen, not a fault |
| `frames[].motion` | Mean grey-level change from the previous **analysed** frame (0..255). It depends on the sampling step |
| `frames[].sharpness` | Variance of the Laplacian: low = blurry. Compare frames of the same video, not different videos |
| `tracks[].runs` | Consecutive analysed frames with the same colour (within a small tolerance), with start and end times |

The detection only sees the analysed frames. To catch short events (a flicker, a 200 ms glitch), use `--every-frame` on the part in question, or a small `--every`.

## Safety rules

- The script only reads the video and writes into the output folder. It never changes the video.
- Phone videos often contain a GPS location. It stays out of the report unless the user asks (`--include-gps`). Mention the warning if the user plans to share the video.
- Screen recordings from vehicles or phones can show personal data (contacts, destinations, messages). Don't publish frames or reports without the user's agreement.
- Don't identify real people from their faces. Don't install packages without the user's agreement.

## Troubleshooting

| Problem | Fix |
|---|---|
| `frame analysis needs OpenCV` | `pip install opencv-python-headless`, or use `--info` for metadata only |
| `OpenCV cannot open this video` | Unsupported codec or damaged file. Convert it, e.g. with ffmpeg: `ffmpeg -i in.ext -c:v libx264 out.mp4` |
| `no moov box: the file is incomplete` | The recording was interrupted or the download was cut off. Some tools can repair it (e.g. `untrunc`); otherwise record again |
| `this is an HTML page, not a video` | The download saved a web page. Download the video file itself |
| `no video track (audio only)` | The file holds only sound (e.g. a voice memo or music saved as .mp4/.m4a). There are no frames; `--info` shows its metadata |
| `The video has N frames, slightly fewer than…` | The header's frame count was an estimate (common in fragmented or streamed MP4). Everything up to the end was analysed |
| `The video stops at frame …` | The file is damaged or truncated. The frames up to that point were analysed |
| `An edit list shortens the video track` | The file plays only part of its recorded frames (trimmed in an editor). Only the playing part is analysed |
| `Fragmented MP4` warning | Streamed or live-recorded files have no frame index in the header, so the duration and frame count are estimated |
| `Variable frame rate` warning | Frame times are estimated from the average frame rate and may be off by a few frames |
| Short glitches are missed | Use `--every-frame --start … --end …` around the glitch, or a smaller `--every` |
| Too many or too few scenes | Raise or lower `--scene-threshold` |
| `--pixel … is outside the frame` | Coordinates are in the decoded frame; check `video.width` / `video.height` (rotation is applied) |

## Run the tests

```bash
python -m unittest discover -s scripts -p "test_*.py"
```

The MP4 metadata tests build MP4 files by hand and need only the standard library. The frame tests generate an 8-second video with known content (black, red, a moving square, a static part, and an LED that turns on and off) and are skipped without OpenCV.
