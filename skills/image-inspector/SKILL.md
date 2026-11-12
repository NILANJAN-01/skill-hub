---
name: image-inspector
description: "Inspect an image file (PNG, JPG, WebP, GIF, BMP, TIFF) with a ready-made Python script: pixel colours at coordinates, dominant colours and palette, transparency, size, EXIF, OCR text, finding an icon inside a screenshot, comparing two screenshots. Use when the user asks about an image or screenshot: its colours, size or text, where an icon is, or what changed between two."
license: Complete terms in the repository README
compatibility: Needs Python 3.8+. Pillow (pip install Pillow) is recommended and required for JPEG, WebP, GIF and TIFF; PNG and BMP also work with the standard library alone. OCR is optional and needs pytesseract plus the Tesseract program. Finding and comparing images needs OpenCV (pip install opencv-python-headless).
metadata:
  title: "Image inspector: pixels and description"
  category: image-tools
---

# Image inspector: pixels and text description

`scripts/inspect_image.py` reads an image and writes one JSON report per image into a **separate output folder** (default `image-reports/`). It also prints a plain-text description on the console. The report contains:

- `image`: width, height, megapixels, aspect ratio, orientation, format, colour mode, bit depth, DPI, frame count, and EXIF (camera, date, orientation).
- `colors`: mean colour, dominant colours (hex, RGB, colour name, percent), brightness, contrast, saturation, whether it is grayscale, a luminance histogram, and the number of distinct colours.
- `layout`: a 3x3 grid of average colours and notes such as "brighter at the top than the bottom".
- `texture`: how much fine detail there is, and a guess whether it is a photo or a flat graphic (screenshot, UI, logo).
- `pixel_map`: a downsampled grid of hex colours (16 columns by default).
- `pixels` / `regions`: exact values for the coordinates you ask for.
- `ocr`: text and word boxes, when `--ocr` is used and Tesseract is available.
- `find`: where a template image (icon, button) appears, with `--find` (OpenCV).
- `comparison`: what changed compared with a reference screenshot, with `--compare` (OpenCV). A diff image is written next to the report.
- `texture.sharpness`: a blur score, when OpenCV is installed.
- `description`: a few factual sentences built from the numbers above.
- `warnings`: for example, that a GPS location is present or that Pillow is missing.

The full field reference is in [references/output-format.md](references/output-format.md).

## When to use

- The user wants an image or screenshot described, or wants to know what is in it.
- The user needs exact pixel values: "what colour is the pixel at 120,48", "is this button #2196F3", or a check that a brand colour is used.
- The user wants the palette or dominant colours, the size or aspect ratio, transparency, or the EXIF metadata of an image.
- The user wants pixel data exported (CSV), a small pixel map, or the text in an image (OCR).
- The user wants to know where an icon, button or logo is on a screenshot, for example to get tap coordinates for a UI test when there is no resource-id.
- The user wants to know what changed between two screenshots, or to check screens against baseline images (visual regression).

## When NOT to use

- Vector files (SVG) or HTML pages: render or export them to PNG first.
- Editing images (resize, crop, convert). This skill only reads images.
- Recognising people. Don't identify real people from their faces.

## Procedure

`scripts/…` below means the `scripts` folder inside this skill's folder. Run the commands from the user's project, using the full path to the script, so that `image-reports/` is created there. Or pass `--out <folder>`.

1. **Check Python and Pillow.** Run `python -c "import PIL"`. If it fails and the image is not a PNG or BMP, ask the user before installing anything: `pip install Pillow`. Without Pillow, the script reports only the size of JPEG/WebP/GIF/TIFF files and warns about it.
2. **Run the script.**
   ```bash
   python scripts/inspect_image.py photo.jpg                     # -> image-reports/photo.json + description
   python scripts/inspect_image.py screenshots/ --out reports    # every image in a folder (and subfolders)
   python scripts/inspect_image.py ui.png --pixel 120,48 --pixel 10,10   # exact colour of pixels (x,y from the top-left)
   python scripts/inspect_image.py ui.png --region 0,0,400,80    # x,y,width,height: average and dominant colours
   python scripts/inspect_image.py ui.png --grid 32              # finer pixel map in the JSON (--grid 0 turns it off)
   python scripts/inspect_image.py icon.png --pixels-csv         # every pixel: image-reports/icon.pixels.csv
   python scripts/inspect_image.py scan.png --ocr --ocr-lang eng+deu    # text in the image
   python scripts/inspect_image.py photo.jpg --stdout            # print the JSON instead of writing files
   ```
   Other options:
   - `--colors K`: the number of dominant colours (default 6).
   - `--max-csv-pixels N`: the size limit for `--pixels-csv` (default 2,000,000 pixels).
   - `--include-gps`: add the GPS coordinates from EXIF. They are left out by default.
   - `--no-pillow`: use only the standard-library decoders.

   **With OpenCV** (`pip install opencv-python-headless`; ask the user first):
   ```bash
   python scripts/inspect_image.py screen.png --find play_icon.png              # where is the icon? box, centre, score
   python scripts/inspect_image.py screen.png --find icon.png --scales 0.75,1,1.5   # icon cut from a screen with another density
   python scripts/inspect_image.py after.png --compare before.png               # what changed? + image-reports/after.diff.png
   python scripts/inspect_image.py shots/ --compare baseline/ --ignore 900,0,180,60 --fail-on-diff 0.5
   ```
   - `--find` options: `--threshold` (minimum score 0..1, default 0.8; lower it if nothing is found, raise it on false hits) and `--max-matches` (default 20). Transparent pixels in the template are ignored, and colour matters.
   - `--compare` takes one image, or a folder with images of the same names (a baseline folder). Options: `--diff-threshold` (per-channel difference that counts as changed, default 25, which ignores JPEG noise), `--min-area`, `--ignore X,Y,W,H` (repeatable, for clocks and other live content) and `--fail-on-diff PERCENT` (exit code 1 when more changed, for CI).
   - In the diff image, changed pixels are red, change boxes yellow and ignored areas blue.

   The exit code is 0 on success, 1 when `--fail-on-diff` is exceeded, and 2 if an image could not be read or OpenCV is missing for `--find` / `--compare`. The error says why (truncated file, HTML page, SVG, unknown type).
3. **Describe the image.** Start from the `description` and the numbers in the report. They are measured, not guessed. If you can view images, also look at the image and add what the numbers can't show: objects, scene, layout of UI elements, and the meaning of visible text. Keep the two apart: give measured facts (size, exact colours, percentages) from the report, and describe content as what you see. Never invent details that are neither in the report nor visible.
4. **Answer pixel questions from the report only.** For "what colour is X", run with `--pixel` or `--region` and quote `hex` / `rgba` from the JSON. Don't estimate colours by eye. Coordinates are 0-based from the top-left. For JPEGs with an EXIF rotation, they refer to the image as it is displayed (`exif_orientation_applied: true`).
5. **Pass the warnings on.** In particular: GPS location data in the file (a privacy risk when sharing), an animated image (only the first frame is analysed), a missing Pillow install, or OCR that is not available.
6. **For find and compare, report the coordinates.** Give `center` for each match (the point to tap) and its `score`. For a comparison, give `changed_percent` and the boxes, and point to the diff image. Don't call two screens identical unless `identical` is true; small differences under `--diff-threshold` are not counted as changes.
7. **Hand over.** Show the description, the facts the user asked for, and the report path. For large outputs (CSV, pixel maps), point to the file instead of pasting it.

## How to read the results

| Field | Meaning |
|---|---|
| `colors.dominant[].percent` | Share of the non-transparent pixels. Similar shades are merged into one colour |
| `colors.dominant[].name` | Nearest of about 30 basic colour names. Use `hex` when precision matters |
| `brightness.mean` | Average luminance from 0 (black) to 255 (white) |
| `contrast.luma_std` | Spread of the luminance. Under 25 is low, over 60 is high |
| `texture.kind_guess` | A heuristic from the colour statistics. Treat it as a hint, not a fact |
| `sampling.step` | Above 1, the statistics use every Nth pixel in each direction (big images). `--pixel`, `--region` and `--pixels-csv` always use exact pixels |
| `find[].matches[].score` | 1.0 is a pixel-perfect match. Above 0.9 is a reliable match; 0.8–0.9 is worth checking |
| `comparison.changed_percent` | Share of pixels where some channel differs by more than `--diff-threshold` |
| `texture.sharpness.level` | `blurry`, `slightly soft` or `sharp`. Only meaningful for photos |
| `pixel_map.hex` | Rows of colours. Each cell averages the pixels inside it. `#rrggbbaa` appears only where pixels are partly transparent |

## Safety rules

- The script only reads images and writes reports into the output folder. It never changes the image.
- EXIF can contain a location, camera serial number or date. GPS coordinates stay out of the report unless the user asks (`--include-gps`). Mention the warning if the user plans to share the image.
- Don't identify real people from their faces. Describing what they wear or do is fine.
- Don't install packages (Pillow, pytesseract, Tesseract) without the user's agreement.

## Troubleshooting

| Problem | Fix |
|---|---|
| `JPEG pixels can't be decoded without Pillow` | `pip install Pillow`, then run again |
| `this is an HTML page, not an image` | The download saved a web page. Save the image itself |
| `this is an SVG (vector) file` | Export or render it to PNG first |
| `PNG pixel data is truncated` | The file was cut off. Get a complete copy |
| `OCR unavailable` | `pip install pytesseract` and install the Tesseract program, or read the text from the image directly |
| `OCR failed … Is the Tesseract program installed` | Install Tesseract and put it on PATH. For other languages, install their data and pass `--ocr-lang` |
| `--pixels-csv skipped` | The image is larger than `--max-csv-pixels`. Raise the limit, or use `--region` / `--grid` |
| `pixel x,y is outside the image` | Coordinates start at 0. The maximum is width-1, height-1 |
| `--find and --compare need OpenCV` | `pip install opencv-python-headless`, then run again |
| `--find` finds nothing | Lower `--threshold` (e.g. 0.7). If the template came from a screen with a different density, add `--scales 0.5,0.75,1,1.5,2` |
| `--find` matches in the wrong places | Raise `--threshold`. Crop the template tighter, with some detail in it (not one flat colour) |
| `--compare` reports changes everywhere | The screens differ in size or position (warning: different sizes), or are JPEGs with heavy compression: raise `--diff-threshold` |
| Slow on a very large PNG without Pillow | The pure-Python decoder is slow on images of tens of megapixels. Install Pillow |

## Run the tests

```bash
python -m unittest discover -s scripts -p "test_*.py"
```

The tests build their own PNG and BMP files (every PNG colour type, bit depth, filter and interlacing), so no fixture files are needed. Tests that need Pillow (JPEG, EXIF rotation, GPS, 16-bit, animated GIF) or OpenCV (find, compare, sharpness) are skipped when those are not installed.
