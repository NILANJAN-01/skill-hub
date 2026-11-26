"""Find a template image inside a screenshot, compare two screenshots and measure sharpness, for
inspect_image.py. Pure Python (standard library only): no OpenCV or numpy needed.

The numbers follow OpenCV's definitions, so results match the earlier OpenCV version:
- find: score = TM_CCOEFF_NORMED (TM_SQDIFF_NORMED for flat templates), per colour channel, with the template's
  alpha as weights. The search runs coarse-to-fine on a grayscale pyramid, and every reported score is computed
  exactly at full resolution.
- compare: changed = any RGBA channel differs by more than the threshold; changed pixels are grouped like
  dilate(5x5, 2 iterations) + external contours.
- sharpness: variance of the 3x3 Laplacian (cv2.Laplacian, reflect-101 border) on the luma, after an area
  resize to at most 2000 px.

Every function takes the Raster objects decoded by inspect_image.py, so EXIF rotation, 16-bit and palette
handling are the same as in the rest of the report.
"""

from __future__ import annotations

import math
from array import array
from itertools import accumulate, repeat
from operator import add, mul, sub, truediv




def available() -> bool:
    return True


# ------------------------------------------------------------------------------------------- pixel planes

def _channels(r):
    """Raster -> (rgb rows as lists of interleaved ints, alpha rows as lists of 0..255)."""
    w, c, d = r.width, r.channels, r.data
    rgb, alpha = [], []
    for y in range(r.height):
        row = d[y * w * c:(y + 1) * w * c]
        if c == 1:
            g = list(row)
            rgb.append([v for v in g for _ in range(3)])
            alpha.append([255] * w)
        elif c == 2:
            g = list(row[0::2])
            rgb.append([v for v in g for _ in range(3)])
            alpha.append(list(row[1::2]))
        elif c == 3:
            rgb.append(list(row))
            alpha.append([255] * w)
        else:
            out = bytearray(3 * w)
            out[0::3], out[1::3], out[2::3] = row[0::4], row[1::4], row[2::4]
            rgb.append(list(out))
            alpha.append(list(row[3::4]))
    return rgb, alpha


def _gray_rows(rgb):
    """cv2.COLOR_RGB2GRAY for 8-bit images: (R*9798 + G*19235 + B*3735 + 16384) >> 15, as OpenCV 4 computes it."""
    out = []
    for row in rgb:
        out.append([(r * 9798 + g * 19235 + b * 3735 + 16384) >> 15 for r, g, b in zip(row[0::3], row[1::3], row[2::3])])
    return out


def _area_weights(n_src, n_dst):
    """For each destination index, [(source index, weight)] covering its area (INTER_AREA)."""
    scale = n_src / n_dst
    out = []
    for d in range(n_dst):
        a, b = d * scale, (d + 1) * scale
        ws = []
        i = int(a)
        while i < b and i < n_src:
            lo, hi = max(a, i), min(b, i + 1)
            if hi > lo:
                ws.append((i, (hi - lo) / scale))
            i += 1
        out.append(ws)
    return out


def _linear_weights(n_src, n_dst):
    scale = n_src / n_dst
    out = []
    for d in range(n_dst):
        f = (d + 0.5) * scale - 0.5
        i = int(math.floor(f))
        a = f - i
        if i < 0:
            i, a = 0, 0.0
        if i >= n_src - 1:
            i, a = n_src - 1, 0.0
        out.append([(i, 1 - a), (min(i + 1, n_src - 1), a)] if a else [(i, 1.0)])
    return out


def _resize(rows, w, h, nch, nw, nh, method="area"):
    """Resize interleaved integer rows; returns rows of ints (rounded like cv2's saturate_cast)."""
    pick = _area_weights if (method == "area" and (nw <= w and nh <= h)) else _linear_weights
    if method == "nearest":
        xs = [min(w - 1, int(x * w / nw)) for x in range(nw)]
        ys = [min(h - 1, int(y * h / nh)) for y in range(nh)]
        return [[rows[y][x * nch + k] for x in xs for k in range(nch)] for y in ys]
    wx, wy = pick(w, nw), pick(h, nh)
    tmp = []
    for row in rows:
        chans = [row[k::nch] for k in range(nch)]
        line = [0.0] * (nw * nch)
        for k in range(nch):
            ch = chans[k]
            line[k::nch] = [sum(ch[i] * wt for i, wt in ws) for ws in wx]
        tmp.append(line)
    out = []
    for ws in wy:
        acc = [0.0] * (nw * nch)
        for i, wt in ws:
            acc = list(map(add, acc, map(mul, tmp[i], repeat(wt))))
        out.append([min(255, max(0, int(v + 0.5))) for v in acc])
    return out


# ------------------------------------------------------------------------------------------- sharpness

def sharpness(r) -> dict:
    """Variance of the Laplacian: low = blurry. Only meaningful for photos (flat graphics also score low)."""
    rgb, _ = _channels(r)
    gray = _gray_rows(rgb)
    w, h = r.width, r.height
    if max(w, h) > 2000:                                       # comparable values for very large photos
        f = 2000 / max(w, h)
        nw, nh = max(1, int(round(w * f))), max(1, int(round(h * f)))
        gray = _resize(gray, w, h, 1, nw, nh, "area")
        w, h = nw, nh
    total = sq = 0
    n = w * h
    for y in range(h):
        row = gray[y]
        up = gray[y - 1] if y > 0 else (gray[1] if h > 1 else row)
        down = gray[y + 1] if y < h - 1 else (gray[h - 2] if h > 1 else row)
        if w > 1:
            left = [row[1]] + row[:-1]
            right = row[1:] + [row[-2]]
        else:
            left = right = row
        lap = list(map(sub, map(add, map(add, up, down), map(add, left, right)), map(mul, row, repeat(4))))
        total += sum(lap)
        sq += sum(map(mul, lap, lap))
    var = sq / n - (total / n) ** 2 if n else 0.0
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


def _half(rows, w, h):
    """2x2 average (one pyramid level); odd edges are dropped."""
    nw, nh = w // 2, h // 2
    out = []
    for y in range(nh):
        a, b = rows[2 * y], rows[2 * y + 1]
        s = list(map(add, a, b))
        out.append([(p + q + 2) >> 2 for p, q in zip(s[0:2 * nw:2], s[1:2 * nw:2])])
    return out, nw, nh


def _half_f(rows, w, h):
    nw, nh = w // 2, h // 2
    out = []
    for y in range(nh):
        a, b = rows[2 * y], rows[2 * y + 1]
        s = list(map(add, a, b))
        out.append([(p + q) / 4 for p, q in zip(s[0:2 * nw:2], s[1:2 * nw:2])])
    return out, nw, nh


def _correlate(scene, kernel, sw, sh, kw, kh):
    """out[y][x] = sum_j sum_i scene[y+j][x+i] * kernel[j][i] for non-negative integers, exactly.

    Each row is packed into one big integer (one value per 32- or 64-bit slot), so a row's whole
    correlation is a single big-integer multiplication done in C (Kronecker substitution)."""
    maxs = max((max(r) for r in scene[:sh]), default=0)
    bound = maxs * sum(sum(r) for r in kernel) + 1
    if bound >= 1 << 64:
        raise OverflowError("values too large for packed correlation")
    tc, nb = ("I", 4) if bound < 1 << 32 else ("Q", 8)
    if array(tc).itemsize != nb:                                  # platform without a 4-byte 'I'
        tc = next(t for t in "IHLQ" if array(t).itemsize == nb)
    packed = [int.from_bytes(array(tc, r).tobytes(), "little") for r in scene[:sh]]
    kern = [(j, int.from_bytes(array(tc, r[::-1]).tobytes(), "little")) for j, r in enumerate(kernel) if any(r)]
    nx, ny = sw - kw + 1, sh - kh + 1
    size = (sw + kw - 1) * nb
    out = []
    for y in range(ny):
        p = 0
        for j, k in kern:
            p += packed[y + j] * k
        a = array(tc)
        a.frombytes(p.to_bytes(size, "little"))
        out.append(a[kw - 1:kw - 1 + nx])
    return out


def _peaks(scene, sw, sh, tpl, wts, tw, th, flat, cmin, keep):
    """The `keep` best local maxima (score >= cmin) of the gray matching score, as [(score, x, y)].
    Scores come from exact integer correlations with the mask used as binary (weight >= 0.5); they only
    pick candidates, reported scores come from _exact_scorer."""
    m = [[1 if w >= 0.5 else 0 for w in r] for r in wts]
    n = sum(sum(r) for r in m)
    nx, ny = sw - tw + 1, sh - th + 1
    if n == 0 or nx <= 0 or ny <= 0:
        return []
    tm = [[int(t) * k for t, k in zip(tr, mr)] for tr, mr in zip(tpl, m)]
    st = sum(sum(r) for r in tm)
    stt = sum(sum(v * v for v in r) for r in tm)
    num = _correlate(scene, tm, sw, sh, tw, th)
    full = n == tw * th
    if full:                                                      # window sums from integral images
        i1, i2 = [[0] * (sw + 1)], [[0] * (sw + 1)]
        for r in scene[:sh]:
            i1.append(list(map(add, i1[-1], [0] + list(accumulate(r)))))
            i2.append(list(map(add, i2[-1], [0] + list(accumulate(map(mul, r, r))))))

        def box(ii, y):
            top, bot = ii[y], ii[y + th]
            return list(map(sub, map(sub, bot[tw:tw + nx], bot[:nx]), map(sub, top[tw:tw + nx], top[:nx])))
        s1 = [box(i1, y) for y in range(ny)]
        s2 = [box(i2, y) for y in range(ny)]
    else:
        s1 = _correlate(scene, m, sw, sh, tw, th)
        s2 = _correlate([list(map(mul, r, r)) for r in scene[:sh]], m, sw, sh, tw, th)
    mt = st / n
    tt = stt - st * mt                                            # sum M (T - mt)^2
    tiny, inv_n, flat_floor = 1e-9, 1.0 / n, 0.25 * n
    sqrt = math.sqrt

    def row_scores(y):
        nr, a, b = num[y], s1[y], s2[y]
        if flat:                                                  # 1 - sum M (T-I)^2 / sqrt(sum M T^2 * sum M I^2)
            diff = map(add, map(sub, repeat(stt), map(mul, nr, repeat(2))), b)
            den = map(sqrt, map(max, map(mul, b, repeat(stt)), repeat(tiny)))
            return list(map(sub, repeat(1.0), map(truediv, diff, den)))
        if tt <= 0:
            return [-1.0] * nx
        ii = map(sub, b, map(mul, map(mul, a, a), repeat(inv_n)))  # sum M (I - mi)^2
        # flat windows (std below half a grey level) would turn float rounding into fake scores
        den = map(sqrt, map(mul, map(max, ii, repeat(flat_floor)), repeat(tt)))
        return list(map(truediv, map(sub, nr, map(mul, a, repeat(mt))), den))

    peaks = []
    prev, cur = None, row_scores(0)
    for y in range(ny):
        nxt = row_scores(y + 1) if y + 1 < ny else None
        for x in [x for x, v in enumerate(cur) if v >= cmin]:      # local maxima of the candidates only
            v = cur[x]
            if (x > 0 and cur[x - 1] > v) or (x + 1 < nx and cur[x + 1] > v):
                continue
            lo, hi = max(0, x - 1), x + 2
            if (prev is not None and max(prev[lo:hi]) > v) or (nxt is not None and max(nxt[lo:hi]) > v):
                continue
            peaks.append((v, x, y))
            if len(peaks) > 4 * keep:
                peaks.sort(reverse=True)
                del peaks[keep:]
        prev, cur = cur, nxt
    peaks.sort(reverse=True)
    return peaks[:keep]


def _exact_scorer(img, tpl, wts, tw, th, flat, nch=3):
    """score(x, y) = OpenCV's TM_CCOEFF_NORMED (or 1 - TM_SQDIFF_NORMED) with mask weights M, summed over the
    nch interleaved channels (3 = RGB, 1 = gray):  T' = M (T - mean_M T),  I' = M (I - mean_M I),  R = sum T'I' / sqrt(sum T'^2 sum I'^2).
    The template-only sums are computed once, so each score is a few dot products per row."""
    sm = sum(sum(r) for r in wts)
    w2 = [[w * w for w in r] for r in wts]
    sw2 = sum(sum(r) for r in w2)
    chans = []
    for c in range(nch):
        tc = [row[c::nch] for row in tpl]
        mt = sum(sum(map(mul, wr, tr)) for wr, tr in zip(wts, tc)) / sm if sm else 0.0
        if flat:
            a = [list(map(mul, w2r, tr)) for w2r, tr in zip(w2, tc)]                  # M^2 T
            tt = sum(sum(map(mul, ar, tr)) for ar, tr in zip(a, tc))                   # sum (M T)^2
            sa = 0.0
        else:
            a = [[w * (t - mt) for w, t in zip(w2r, tr)] for w2r, tr in zip(w2, tc)]  # M^2 (T - mt)
            tt = sum(sum((w * (t - mt)) ** 2 for w, t in zip(wr, tr)) for wr, tr in zip(wts, tc))
            sa = sum(sum(r) for r in a)
        chans.append((a, tt, sa))
    binary = all(w in (0.0, 1.0) for r in wts for w in r)

    def score(x, y):
        if sm <= 0:
            return -1.0
        num = tts = iis = 0.0
        for c in range(nch):
            a, tt, sa = chans[c]
            s_wv = s_w2v = s_w2v2 = s_av = 0.0
            for j in range(th):
                seg = img[y + j][nch * x + c:nch * (x + tw) + c:nch]
                sq = list(map(mul, seg, seg))
                wr = wts[j]
                s_av += sum(map(mul, a[j], seg))
                if binary:
                    v = sum(map(mul, wr, seg))
                    s_wv += v
                    s_w2v += v
                    s_w2v2 += sum(map(mul, wr, sq))
                else:
                    s_wv += sum(map(mul, wr, seg))
                    s_w2v += sum(map(mul, w2[j], seg))
                    s_w2v2 += sum(map(mul, w2[j], sq))
            tts += tt
            if flat:
                num += tt - 2 * s_av + s_w2v2                        # sum M^2 (T - I)^2
                iis += s_w2v2
            else:
                mi = s_wv / sm
                num += s_av - mi * sa                               # sum M^2 (T - mt)(I - mi)
                iis += s_w2v2 - 2 * mi * s_w2v + mi * mi * sw2       # sum M^2 (I - mi)^2
        d = math.sqrt(max(0.0, tts * iis))
        if flat:
            return 1.0 - num / d if d > 0 else (1.0 if abs(num) < 1e-9 else -1.0)
        return num / d if d > 1e-12 else -1.0
    return score


def find_template(scene, template, threshold: float = 0.8, max_matches: int = 20, scales=(1.0,)):
    """Find `template` in `scene` (both Rasters). Returns (matches, warnings).

    Each match: x, y, width, height, center [x, y], score (0..1, 1 = identical), scale.
    Transparent template pixels are ignored (masked). Overlapping hits are merged.
    """
    img, _ = _channels(scene)
    tpl0, alpha0 = _channels(template)
    W, H = scene.width, scene.height
    vis = [v for row, arow in zip(tpl0, alpha0) for i, a in enumerate(arow) if a > 0 for v in row[3 * i:3 * i + 3]]
    warnings = []
    flat = True
    if vis:
        m = sum(vis) / len(vis)
        flat = math.sqrt(sum((v - m) ** 2 for v in vis) / len(vis)) < 1.0
    if flat:
        warnings.append("The template is a single flat colour, so it matches any area of that colour. "
                        "Crop it so it includes some detail (edges, text or an icon).")
    gray_scene = _gray_rows(img)
    pyramid = [(gray_scene, W, H)]
    cands = []
    for s in scales:
        tw0, th0 = template.width, template.height
        t, a = tpl0, alpha0
        tw, th = tw0, th0
        if s != 1.0:
            tw, th = max(1, int(round(tw0 * s))), max(1, int(round(th0 * s)))
            t = _resize(tpl0, tw0, th0, 3, tw, th, "area" if s < 1 else "linear")
            a = _resize(alpha0, tw0, th0, 1, tw, th, "nearest")
        if th > H or tw > W or th < 2 or tw < 2:
            continue
        wts = [[v / 255.0 for v in row] for row in a]
        # pyramid level: template at least 16 px, and a bounded amount of work at the coarse level
        level = 0
        while (min(tw, th) >> (level + 1)) >= 16 and \
                ((W >> level) * (H >> level) * (tw >> level) * (th >> level) > 2e8):
            level += 1
        while len(pyramid) <= level:
            g, gw, gh = pyramid[-1]
            pyramid.append(_half(g, gw, gh))
        tg, tgw, tgh = _gray_rows(t), tw, th
        wg = wts
        for _ in range(level):
            tg, tgw, tgh = _half(tg, tgw, tgh)
            wg, _, _ = _half_f(wg, len(wg[0]), len(wg))
        g, gw, gh = pyramid[level]
        # keep the best local maxima: misalignment with the coarse grid lowers coarse scores a lot, so
        # candidates are ranked rather than cut at the threshold (reported scores are exact)
        coarse_min = 0.05 if level else threshold - 0.05
        peaks = _peaks(g, gw, gh, tg, wg, tgw, tgh, flat, coarse_min, max(20, 3 * max_matches))
        if not peaks:
            continue
        pts = [(x, y) for _, x, y in peaks]
        for lv in range(level - 1, -1, -1):                     # refine level by level
            g, gw, gh = pyramid[lv]
            tl, tlw, tlh, wl = _gray_rows(t), tw, th, wts
            for _ in range(lv):
                tl, tlw, tlh = _half(tl, tlw, tlh)
                wl, _, _ = _half_f(wl, len(wl[0]), len(wl))
            nxt = set()
            fn = _exact_scorer(g, tl, wl, tlw, tlh, flat, 1)
            memo = {}

            def val(p):
                if p not in memo:
                    memo[p] = fn(*p) if (0 <= p[0] <= gw - tlw and 0 <= p[1] <= gh - tlh) else -2.0
                return memo[p]
            for x, y in pts:                                     # hill-climb from the upscaled position
                p = max(((2 * x + dx, 2 * y + dy) for dx in (0, 1) for dy in (0, 1)), key=val)
                for _ in range(16):
                    q = max(((p[0] + dx, p[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)), key=val)
                    if val(q) <= val(p):
                        break
                    p = q
                if val(p) > -2 and (lv or val(p) >= threshold - 0.25):   # full-res gray far below: drop
                    nxt.add(p)
            pts = sorted(nxt)
        exact = _exact_scorer(img, t, wts, tw, th, flat)
        memo = {}

        def ex(p):
            if p not in memo:
                memo[p] = exact(*p) if (0 <= p[0] <= W - tw and 0 <= p[1] <= H - th) else -2.0
            return memo[p]
        for p in pts:                                            # exact colour score, hill-climbed
            for _ in range(8):
                q = max(((p[0] + dx, p[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)), key=ex)
                if ex(q) <= ex(p):
                    break
                p = q
        cands.extend((v, px, py, tw, th, s) for (px, py), v in memo.items() if v >= threshold)
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

def _rgba_rows(r):
    w, c, d = r.width, r.channels, r.data
    rows = []
    for y in range(r.height):
        row = d[y * w * c:(y + 1) * w * c]
        if c == 4:
            rows.append(bytes(row))
            continue
        out = bytearray(4 * w)
        if c in (1, 2):
            g = row[0::c]
            out[0::4], out[1::4], out[2::4] = g, g, g
            out[3::4] = row[1::2] if c == 2 else b"\xff" * w
        else:
            out[0::4], out[1::4], out[2::4] = row[0::3], row[1::3], row[2::3]
            out[3::4] = b"\xff" * w
        rows.append(bytes(out))
    return rows


def _merge_runs(runs):
    runs.sort()
    out = []
    for s, e in runs:
        if out and s <= out[-1][1] + 1:
            if e > out[-1][1]:
                out[-1][1] = e
        else:
            out.append([s, e])
    return out


def compare(current, reference, pixel_threshold: int = 25, min_area: int = 16, ignore=(), diff_path=None):
    """Compare two Rasters. Returns (result dict, warnings). Writes a diff PNG to `diff_path` if given.

    A pixel counts as changed when any RGBA channel differs by more than `pixel_threshold` (0..255).
    Changed pixels are grouped into boxes (`changed_regions`). `ignore` is a list of (x, y, w, h) to skip,
    e.g. a clock in the status bar.
    """
    warnings = []
    W, H = current.width, current.height
    a = _rgba_rows(current)
    b = _rgba_rows(reference)
    size_mismatch = (reference.width, reference.height) != (W, H)
    if size_mismatch:
        warnings.append(f"The images have different sizes ({W}x{H} vs "
                        f"{reference.width}x{reference.height}); the reference was resized to compare them.")
        rows = _resize([list(r) for r in b], reference.width, reference.height, 4, W, H, "area")
        b = [bytes(r) for r in rows]
    ign = [(max(0, x), max(0, y), min(W, x + w), min(H, y + h)) for x, y, w, h in ignore]
    runs = {}                      # y -> [[x0, x1], ...] of changed pixels
    diff_rows = {}                 # y -> per-pixel max difference (only rows that differ)
    n_changed, total_diff, max_diff = 0, 0, 0
    for y in range(H):
        ra, rb = a[y], b[y]
        if ra == rb:
            continue
        d = [abs(v) for v in map(sub, ra, rb)]
        dm = list(map(max, d[0::4], d[1::4], d[2::4], d[3::4]))
        for x0, y0, x1, y1 in ign:
            if y0 <= y < y1:
                dm[x0:x1] = [0] * (x1 - x0)
        s = sum(dm)
        if not s:
            continue
        diff_rows[y] = dm
        total_diff += s
        max_diff = max(max_diff, max(dm))
        xs = [x for x, v in enumerate(dm) if v > pixel_threshold]
        if xs:
            n_changed += len(xs)
            row_runs, start, prev = [], xs[0], xs[0]
            for x in xs[1:]:
                if x != prev + 1:
                    row_runs.append([start, prev])
                    start = x
                prev = x
            row_runs.append([start, prev])
            runs[y] = row_runs
    total = W * H
    regions = []
    if n_changed:
        r = 4                                                   # dilate 5x5 twice = 9x9 square
        hruns = {y: _merge_runs([[max(0, s - r), min(W - 1, e + r)] for s, e in rr]) for y, rr in runs.items()}
        dil = {}
        for y, rr in hruns.items():
            for yy in range(max(0, y - r), min(H, y + r + 1)):
                dil.setdefault(yy, []).extend([list(x) for x in rr])
        dil = {y: _merge_runs(rr) for y, rr in dil.items()}
        parent = {}

        def find(k):
            while parent[k] != k:
                parent[k] = parent[parent[k]]
                k = parent[k]
            return k
        for y in sorted(dil):
            for i, run in enumerate(dil[y]):
                parent[(y, i)] = (y, i)
                for j, up in enumerate(dil.get(y - 1, [])):
                    if up[0] <= run[1] + 1 and run[0] <= up[1] + 1:            # 8-connected
                        ra_, rb_ = find((y, i)), find((y - 1, j))
                        if ra_ != rb_:
                            parent[ra_] = rb_
        boxes = {}
        for (y, i) in parent:
            k = find((y, i))
            s, e = dil[y][i]
            bx = boxes.get(k)
            boxes[k] = [s, y, e, y] if bx is None else [min(bx[0], s), min(bx[1], y), max(bx[2], e), max(bx[3], y)]
        blist = list(boxes.values())
        outer = [bx for bx in blist if not any(o is not bx and o[0] <= bx[0] and o[1] <= bx[1] and o[2] >= bx[2]
                                               and o[3] >= bx[3] and o != bx for o in blist)]
        for x0, y0, x1, y1 in outer:
            px, mnx, mxx, mny, mxy, md = 0, None, None, None, None, 0
            for y in range(y0, y1 + 1):
                for s, e in runs.get(y, []):
                    s2, e2 = max(s, x0), min(e, x1)
                    if s2 > e2:
                        continue
                    px += e2 - s2 + 1
                    mnx = s2 if mnx is None else min(mnx, s2)
                    mxx = e2 if mxx is None else max(mxx, e2)
                    mny = y if mny is None else mny
                    mxy = y
            if not px:
                continue
            w, h = mxx - mnx + 1, mxy - mny + 1
            for y in range(mny, mxy + 1):
                if y in diff_rows:
                    md = max(md, max(diff_rows[y][mnx:mxx + 1]))
            if w * h >= min_area:
                regions.append({"x": mnx, "y": mny, "width": w, "height": h, "center": [mnx + w // 2, mny + h // 2],
                                "changed_pixels": px, "max_difference": md})
        regions.sort(key=lambda rg: -rg["changed_pixels"])
        if len(regions) > 100:
            warnings.append(f"{len(regions)} changed regions; only the 100 largest are listed.")
            regions = regions[:100]
    result = {
        "identical": max_diff == 0 and not size_mismatch,
        "size_mismatch": size_mismatch,
        "pixel_threshold": pixel_threshold,
        "changed_pixels": n_changed,
        "changed_percent": round(100.0 * n_changed / total, 3),
        "max_difference": max_diff,
        "mean_difference": round(total_diff / total, 3),
        "changed_regions": regions,
    }
    if ignore:
        result["ignored_regions"] = [{"x": x, "y": y, "width": w, "height": h} for x, y, w, h in ignore]
    if diff_path is not None:
        import image_codecs
        dim = bytes(int(v * 0.45) for v in range(256))
        out = bytearray()
        for y in range(H):
            row = a[y]
            line = bytearray(3 * W)
            line[0::3], line[1::3], line[2::3] = row[0::4], row[1::4], row[2::4]
            line = bytearray(line.translate(dim))
            for s, e in runs.get(y, []):                     # changed pixels in red
                line[3 * s:3 * e + 3] = b"\xff\x00\x00" * (e - s + 1)
            out += line

        def rect(x0, y0, x1, y1, color, thick):
            for t in range(thick):
                for x in range(max(0, x0 - t), min(W, x1 + t + 1)):
                    for yy in (y0 - t, y1 + t):
                        if 0 <= yy < H:
                            out[3 * (yy * W + x):3 * (yy * W + x) + 3] = color
                for y in range(max(0, y0 - t), min(H, y1 + t + 1)):
                    for xx in (x0 - t, x1 + t):
                        if 0 <= xx < W:
                            out[3 * (y * W + xx):3 * (y * W + xx) + 3] = color
        for rg in regions:
            rect(rg["x"], rg["y"], rg["x"] + rg["width"] - 1, rg["y"] + rg["height"] - 1, b"\xff\xff\x00", 2)
        for x, y, w, h in ignore:
            rect(x, y, x + w - 1, y + h - 1, b"\x00\x80\xff", 1)
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        diff_path.write_bytes(image_codecs.encode_png(W, H, "RGB", out))
        result["diff_image"] = str(diff_path)
    return result, warnings
