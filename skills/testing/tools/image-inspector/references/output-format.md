# image-inspector report format

One JSON file per image: `<out>/<image name without extension>.json`. If two images in one run have the same name (`a.png`, `a.jpg`), the second one gets its extension added: `a_jpg.json`.

```json
{
  "generator": {"name": "image-inspector", "version": "1.0", "backend": "Pillow 13.0.0"},
  "file": {"name": "ui.png", "path": "shots/ui.png", "bytes": 48213, "format": "PNG"},
  "image": {
    "width": 1080, "height": 2400, "megapixels": 2.59, "aspect_ratio": "9:20", "orientation": "portrait",
    "mode": "RGB", "frames": 1, "has_alpha": false, "dpi": [72, 72],
    "exif": {"make": "...", "model": "...", "datetime_original": "...", "orientation": 1}
  },
  "sampling": {"step": 2, "sampled_pixels": 648000, "note": "statistics use every 2nd pixel in each direction"},
  "transparency": {"transparent_percent": 0.0, "translucent_percent": 0.0},
  "colors": {
    "mean": {"hex": "#eeeff5", "rgb": [238, 239, 245], "name": "off-white"},
    "grayscale": false,
    "saturation": {"mean": 0.07, "level": "almost none (near grayscale)"},
    "brightness": {"mean": 237.6, "min": 99, "max": 255, "level": "very bright"},
    "contrast": {"luma_std": 41.3, "level": "medium"},
    "luma_histogram_percent": [0, 0, 0, 5.2, 8.5, 0, 0, 86.3],
    "unique_colors_in_sample": 412,
    "dominant": [
      {"hex": "#ffffff", "rgb": [255, 255, 255], "name": "white", "percent": 86.3},
      {"hex": "#2196f3", "rgb": [33, 150, 243], "name": "sky blue", "percent": 8.5}
    ]
  },
  "layout": {
    "grid_3x3": [[{"hex": "#a8d4f9", "rgb": [168, 212, 249], "name": "light blue", "brightness": 202.1}, "..."]],
    "notes": ["brighter at the top than the bottom"]
  },
  "texture": {"edge_strength": 1.2, "detail": "very smooth (large flat areas)",
              "top10_colors_cover_percent": 99.1, "kind_guess": "a flat graphic (screenshot, UI, diagram, icon or logo)"},
  "pixel_map": {"columns": 16, "rows": 36, "cell_width": 67.5, "cell_height": 66.67,
                "format": "#rrggbb", "hex": [["#2196f3", "..."], ["..."]]},
  "pixels": [{"x": 120, "y": 48, "rgba": [33, 150, 243, 255], "hex": "#2196f3", "rgb": [33, 150, 243], "name": "sky blue"}],
  "regions": [{"x": 0, "y": 0, "width": 400, "height": 80, "mean": {"hex": "...", "name": "..."},
               "brightness": 126.0, "transparent_percent": 0.0, "dominant": ["..."]}],
  "ocr": {"engine": "tesseract", "lang": "eng", "text": "Sign in\nHelp",
          "words": [{"text": "Sign", "confidence": 96.0, "box": [10, 5, 40, 12]}]},
  "find": [{"template": "play_icon.png", "found": 3, "matches": [
    {"x": 100, "y": 400, "width": 64, "height": 64, "center": [132, 432], "score": 1.0, "scale": 1.0}]}],
  "comparison": {"reference": "before.png", "identical": false, "size_mismatch": false, "pixel_threshold": 25,
                 "changed_pixels": 133031, "changed_percent": 5.132, "max_difference": 179, "mean_difference": 5.1,
                 "changed_regions": [{"x": 100, "y": 1000, "width": 881, "height": 151, "center": [540, 1075],
                                      "changed_pixels": 133031, "max_difference": 179}],
                 "ignored_regions": [{"x": 880, "y": 0, "width": 200, "height": 60}],
                 "diff_image": "image-reports/after.diff.png"},
  "pixels_csv": "image-reports/ui.pixels.csv",
  "description": "ui.png is a 1080x2400 PNG image (2.6 MP, 9:20, portrait). Main colours: white (86.3%), ...",
  "warnings": []
}
```

## Notes on the fields

| Field | Details |
|---|---|
| `generator.backend` | `Pillow <version>`, or `standard library` (PNG and BMP only) |
| `image.mode` | The colour mode as stored (`RGB`, `RGBA`, `P`, `L`, `I;16`, `CMYK`, ...). Pixels are always reported as 8-bit RGBA |
| `image.bit_depth`, `color_type`, `interlaced` | PNG header facts (standard-library backend) |
| `image.exif_orientation_applied` | `true` when the image was rotated or flipped to match its EXIF orientation. Width, height and coordinates refer to the displayed image |
| `image.has_gps_location` | The file carries GPS data. The coordinates are added (as `exif.gps`) only with `--include-gps` |
| `sampling` | The statistics (`colors`, `layout`, `texture`) look at up to about 250,000 pixels on a regular grid. `pixels`, `regions` (up to 250,000 pixels each) and the CSV use exact pixels |
| `transparency` | `transparent` = alpha 0, `translucent` = alpha 1..254. Fully transparent pixels are left out of all colour statistics |
| `colors.dominant` | Colours are bucketed and similar shades merged. `percent` is of the non-transparent pixels |
| `colors.grayscale` | `true` when 99% of the pixels have R, G and B within 10 of each other |
| `colors.luma_histogram_percent` | 8 bins of 32 luminance levels each, from dark (0-31) to light (224-255) |
| `layout.grid_3x3` | Rows top to bottom, columns left to right. A cell with only transparent pixels has `"name": "transparent"` |
| `texture.edge_strength` | Mean luminance difference between neighbouring sampled pixels |
| `pixel_map` | `columns` x `rows` cells that keep the aspect ratio. `cell_width` and `cell_height` are in image pixels |
| `pixels[].hex` | `#rrggbb`, or `#rrggbbaa` when alpha is below 255 |
| `regions[].clipped_from` | Present when the requested rectangle went past the edge of the image |
| CSV | `x,y,r,g,b,a`, one line per pixel, rows top to bottom |
| `texture.sharpness` | OpenCV only. `laplacian_variance` (higher = sharper) and `level`. Flat graphics score low too |
| `find[].matches` | OpenCV `matchTemplate` (normalised correlation, in colour). Transparent template pixels are masked out. Overlapping hits are merged; matches are in reading order. `scale` is the template scale that matched (`--scales`) |
| `comparison` | Per pixel, the largest RGBA channel difference. `changed_*` counts pixels above `pixel_threshold`. Nearby changes are grouped into `changed_regions` (largest first, at most 100), each shrunk to its changed pixels. A reference of another size is resized first (`size_mismatch: true`) |
| `comparison.diff_image` | `<name>.diff.png`: the image dimmed, changed pixels red, change boxes yellow, ignored areas blue. Not written with `--stdout` |
