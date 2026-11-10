"""Optional OpenCV features for inspect_image.py: find a template image inside a screenshot, compare two
screenshots, and measure sharpness. Needs `pip install opencv-python-headless` (brings numpy).

Every function takes the Raster objects decoded by inspect_image.py, so EXIF rotation, 16-bit and palette
handling are the same as in the rest of the report.
"""

from __future__ import annotations

INSTALL_HINT = "pip install opencv-python-headless"


def available() -> bool:
    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
        return True
    except ImportError:
        return False


def _np():
    import cv2
    import numpy as np
    return cv2, np


def to_array(r, mode: str = "RGB"):
    """Raster -> numpy array (H, W, 3) RGB, (H, W, 4) RGBA or (H, W) gray."""
    cv2, np = _np()
    a = np.frombuffer(bytes(r.data), np.uint8).reshape(r.height, r.width, r.channels)
    if r.channels in (1, 2):                                   # L / LA
        gray, alpha = a[:, :, 0], (a[:, :, 1] if r.channels == 2 else np.full(a.shape[:2], 255, np.uint8))
        rgb = np.dstack([gray, gray, gray])
    else:
        rgb, alpha = a[:, :, :3], (a[:, :, 3] if r.channels == 4 else np.full(a.shape[:2], 255, np.uint8))
    if mode == "RGB":
        return np.ascontiguousarray(rgb)
    if mode == "RGBA":
        return np.ascontiguousarray(np.dstack([rgb, alpha]))
    if mode == "A":
        return np.ascontiguousarray(alpha)
    return cv2.cvtColor(np.ascontiguousarray(rgb), cv2.COLOR_RGB2GRAY)


# ------------------------------------------------------------------------------------------- sharpness

def sharpness(r) -> dict:
    """Variance of the Laplacian: low = blurry. Only meaningful for photos (flat graphics also score low)."""
    cv2, np = _np()
    gray = to_array(r, "L")
    if max(gray.shape) > 2000:                                 # comparable values for very large photos
        f = 2000 / max(gray.shape)
        gray = cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    lvl = "blurry" if var < 50 else ("slightly soft" if var < 200 else "sharp")
    return {"laplacian_variance": round(var, 1), "level": lvl,
            "note": "heuristic; meaningful for photos, flat graphics score low too"}


# ---------------------------------------------------------------------------------------------- find

def _iou(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix, iy = max(0, min(ax + aw, bx + bw) - max(ax, bx)), max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    return inter / float(aw * ah + bw * bh - inter) if inter else 0.0


def find_template(scene, template, threshold: float = 0.8, max_matches: int = 20, scales=(1.0,)):
    """Find `template` in `scene` (both Rasters). Returns (matches, warnings).

    Each match: x, y, width, height, center [x, y], score (0..1, 1 = identical), scale.
    Transparent template pixels are ignored (masked). Overlapping hits are merged.
    """
    cv2, np = _np()
    img = to_array(scene, "RGB")
    tpl = to_array(template, "RGB")
    alpha = to_array(template, "A")
    use_mask = bool((alpha < 255).any())
    warnings = []
    flat = float(tpl.reshape(-1, 3)[alpha.reshape(-1) > 0].std()) < 1.0 if (alpha > 0).any() else True
    if flat:
        warnings.append("The template is a single flat colour, so it matches any area of that colour. "
                        "Crop it so it includes some detail (edges, text or an icon).")
    H, W = img.shape[:2]
    cands = []
    for s in scales:
        t, m = tpl, alpha
        if s != 1.0:
            interp = cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR
            t = cv2.resize(tpl, None, fx=s, fy=s, interpolation=interp)
            m = cv2.resize(alpha, None, fx=s, fy=s, interpolation=cv2.INTER_NEAREST)
        th, tw = t.shape[:2]
        if th > H or tw > W or th < 2 or tw < 2:
            continue
        mask = cv2.merge([m, m, m]) if use_mask else None
        if flat:
            res = 1.0 - cv2.matchTemplate(img, t, cv2.TM_SQDIFF_NORMED, mask=mask)
        else:
            res = cv2.matchTemplate(img, t, cv2.TM_CCOEFF_NORMED, mask=mask)
        res = np.nan_to_num(res, nan=-1.0, posinf=-1.0, neginf=-1.0)
        ys, xs = np.where(res >= threshold)
        if len(xs) > 5000:                                     # keep the best candidates only
            best = np.argpartition(res[ys, xs], -5000)[-5000:]
            ys, xs = ys[best], xs[best]
        for x, y in zip(xs.tolist(), ys.tolist()):
            cands.append((float(res[y, x]), x, y, tw, th, s))
    cands.sort(key=lambda c: -c[0])
    kept = []
    for c in cands:
        box = c[1:5]
        if all(_iou(box, k[1:5]) < 0.3 for k in kept):
            kept.append(c)
            if len(kept) >= max_matches:
                break
    kept.sort(key=lambda c: (c[2], c[1]))                     # reading order: top to bottom, left to right
    matches = [{"x": x, "y": y, "width": w, "height": h, "center": [x + w // 2, y + h // 2],
                "score": round(min(1.0, sc), 4), "scale": s} for sc, x, y, w, h, s in kept]
    return matches, warnings


# ------------------------------------------------------------------------------------------- compare

def compare(current, reference, pixel_threshold: int = 25, min_area: int = 16, ignore=(), diff_path=None):
    """Compare two Rasters. Returns (result dict, warnings). Writes a diff PNG to `diff_path` if given.

    A pixel counts as changed when any RGBA channel differs by more than `pixel_threshold` (0..255).
    Changed pixels are grouped into boxes (`changed_regions`). `ignore` is a list of (x, y, w, h) to skip,
    e.g. a clock in the status bar.
    """
    cv2, np = _np()
    warnings = []
    a = to_array(current, "RGBA")
    b = to_array(reference, "RGBA")
    size_mismatch = a.shape[:2] != b.shape[:2]
    if size_mismatch:
        warnings.append(f"The images have different sizes ({current.width}x{current.height} vs "
                        f"{reference.width}x{reference.height}); the reference was resized to compare them.")
        b = cv2.resize(b, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_AREA)
    diff = cv2.absdiff(a, b).max(axis=2)
    for x, y, w, h in ignore:
        diff[max(0, y):max(0, y + h), max(0, x):max(0, x + w)] = 0
    changed = diff > pixel_threshold
    n_changed = int(changed.sum())
    total = diff.size
    regions = []
    if n_changed:
        mask = cv2.dilate(changed.astype(np.uint8) * 255, np.ones((5, 5), np.uint8), iterations=2)
        found = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = found[0] if len(found) == 2 else found[1]
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            sub = changed[y:y + h, x:x + w]
            rows, cols = np.where(sub.any(axis=1))[0], np.where(sub.any(axis=0))[0]
            if not len(rows):
                continue
            x, y = x + int(cols[0]), y + int(rows[0])               # shrink to the changed pixels themselves
            w, h = int(cols[-1] - cols[0]) + 1, int(rows[-1] - rows[0]) + 1
            px = int(changed[y:y + h, x:x + w].sum())
            if px and w * h >= min_area:
                regions.append({"x": x, "y": y, "width": w, "height": h, "center": [x + w // 2, y + h // 2],
                                "changed_pixels": px, "max_difference": int(diff[y:y + h, x:x + w].max())})
        regions.sort(key=lambda r: -r["changed_pixels"])
        if len(regions) > 100:
            warnings.append(f"{len(regions)} changed regions; only the 100 largest are listed.")
            regions = regions[:100]
    result = {
        "identical": int(diff.max()) == 0 and not size_mismatch,
        "size_mismatch": size_mismatch,
        "pixel_threshold": pixel_threshold,
        "changed_pixels": n_changed,
        "changed_percent": round(100.0 * n_changed / total, 3),
        "max_difference": int(diff.max()),
        "mean_difference": round(float(diff.mean()), 3),
        "changed_regions": regions,
    }
    if ignore:
        result["ignored_regions"] = [{"x": x, "y": y, "width": w, "height": h} for x, y, w, h in ignore]
    if diff_path is not None:
        bgr = cv2.cvtColor(np.ascontiguousarray(a[:, :, :3]), cv2.COLOR_RGB2BGR)
        out = (bgr * 0.45).astype(np.uint8)                    # dim the image, highlight changes in red
        out[changed] = (0, 0, 255)
        for r in regions:
            cv2.rectangle(out, (r["x"], r["y"]), (r["x"] + r["width"] - 1, r["y"] + r["height"] - 1),
                          (0, 255, 255), 2)
        for x, y, w, h in ignore:
            cv2.rectangle(out, (x, y), (x + w - 1, y + h - 1), (255, 128, 0), 1)
        ok, png = cv2.imencode(".png", out)                     # imencode + write: works with any path
        if ok:
            diff_path.parent.mkdir(parents=True, exist_ok=True)
            diff_path.write_bytes(png.tobytes())
            result["diff_image"] = str(diff_path)
    return result, warnings
