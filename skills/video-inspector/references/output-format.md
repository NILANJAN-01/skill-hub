# video-inspector output format

One folder per video: `<out>/<video name without extension>/`. If two videos in one run have the same name (`a.mp4`, `a.mov`), the second gets its extension added (`a_mov/`).

## report.json

```json
{
  "generator": {"name": "video-inspector", "version": "1.0", "opencv": "5.0.0"},
  "file": {"name": "demo.mp4", "path": "demo.mp4", "bytes": 8390},
  "video": {
    "width": 160, "height": 120, "fps": 10.0, "frames": 80, "duration_s": 8.0,
    "codec": "mp4v", "codec_name": "MPEG-4 Part 2", "rotation": 0, "variable_frame_rate": false,
    "has_audio": false,
    "audio": {"codec_name": "AAC", "channels": 2, "sample_rate": 48000, "language": "eng"},
    "container": {"brand": "isom", "duration_s": 8.0, "creation_time": "2026-11-10T18:15:08Z", "bitrate_kbps": 8.4,
                  "tracks": ["... one entry per track ..."], "has_audio": false}
  },
  "sampling": {"mode": "one every 0.5 s", "frames_analysed": 16, "frames_saved": 4},
  "scenes": [
    {"start": 0.0, "start_frame": 0, "end": 2.0, "start_time": "0:00.0", "end_time": "0:02.0",
     "description": "black", "key_frame_image": "frames/frame_000000_00000.000s.png"}
  ],
  "black_segments": [{"start": 0.0, "end": 2.0, "start_time": "0:00.0", "end_time": "0:02.0"}],
  "frozen_segments": [{"start": 2.0, "end": 3.5, "start_time": "0:02.0", "end_time": "0:03.5"}],
  "tracks": [
    {"kind": "pixel", "box": [10, 10], "label": "pixel 10,10", "runs": [
      {"start": 0.0, "end": 1.5, "hex": "#000000", "name": "black", "start_time": "0:00.0", "end_time": "0:01.5"},
      {"start": 2.0, "end": 4.5, "hex": "#fad805", "name": "yellow", "start_time": "0:02.0", "end_time": "0:04.5"}]}
  ],
  "frames": [
    {"frame": 20, "t": 2.0, "time": "0:02.0",
     "brightness": 85.7, "brightness_level": "dark", "contrast": 9.2,
     "mean": {"hex": "#da1e1b", "name": "red"}, "saturation": 0.875,
     "dominant": [{"hex": "#dc1e1e", "name": "red", "percent": 99.2}],
     "grid_3x3": [["red", "red", "red"], ["red", "red", "red"], ["red", "red", "red"]],
     "sharpness": 56.3, "motion": 48.1, "motion_level": "high",
     "scene_change": true, "scene_difference": 0.98, "black": false, "flat": false, "frozen": false,
     "tracked": ["#fad805"],
     "pixel_map": {"columns": 8, "rows": 6, "hex": [["#dc1e1e", "..."]]},
     "image": "frames/frame_000020_00002.000s.png",
     "pixels_csv": "frames/frame_000020_00002.000s.pixels.csv"}
  ],
  "description": "demo.mp4 is a 160x120 (landscape) MPEG-4 Part 2 video, 8.0 s at 10 fps (80 frames), ...",
  "warnings": []
}
```

## Notes on the fields

| Field | Details |
|---|---|
| `video.container` | MP4/MOV/M4V/3GP only. Read directly from the file's `moov` box (standard library). Has `has_gps_location`, and `gps` only with `--include-gps` |
| `video.width`, `height` | As decoded by OpenCV, so a rotation flag (`rotation`) is already applied |
| `video.fps`, `frames` | From the container when available (more reliable), otherwise from OpenCV |
| `frames[].t` | Frame index / fps. With a variable frame rate, it is approximate |
| `frames[].brightness`, `contrast` | Mean and standard deviation of the grey level, 0..255 |
| `frames[].dominant` | Up to 3 colours, similar shades merged, with the share of the frame |
| `frames[].motion` | Mean absolute grey-level change from the previous analysed frame, at 160 px width. `null` for the first frame |
| `frames[].scene_difference` | Bhattacharyya distance of the hue/saturation histograms (0 = same, 1 = completely different). `scene_change` = above `--scene-threshold`, or motion above 40 |
| `frames[].black` | Brightness under 16 and contrast under 10 |
| `frames[].flat` | One flat colour (contrast under 3), for example a blank screen |
| `frames[].frozen` | Motion under `--freeze-motion`, and not black |
| `frames[].tracked` | The colour of each `--pixel` / `--region`, in the order given |
| `frames[].image` | Relative to the video's report folder. Name: `frame_<index>_<seconds>s.<ext>` |
| `scenes[].end` | The start of the next scene, or the end of the video |
| `black_segments` | From the first black analysed frame to the next non-black analysed frame (or the end) |
| `frozen_segments` | From the analysed frame before the first unchanged one, to the last unchanged one. At least `--freeze-min` seconds long |
| `tracks[].runs` | Consecutive analysed frames whose colours differ by less than a small tolerance |

## CSV files

- `timeline.csv`: `time_s, frame, brightness, contrast, mean_hex, mean_name, dominant ("#hex:pct% ..."), motion, scene_change (0/1), black (0/1), frozen (0/1), sharpness, image`
- `tracks.csv`: `time_s, frame, kind, box, hex, r, g, b, name`, one row per analysed frame and tracked pixel or region
- `frames/<frame>.pixels.csv`: `x, y, r, g, b`, one row per pixel, rows top to bottom
