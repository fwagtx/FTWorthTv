"""Trace the real skyline out of a clear-sky photo: for every column find where the sky ends, smooth it, simplify it
to a polygon, and write it as normalised points + an SVG path the logo can use.

Usage: python scripts/trace_skyline.py photo.jpg out.json [--left 0.0 --right 1.0 --top 0.0 --bottom 0.9]
  --left/--right/--top/--bottom crop the photo (fractions) before tracing; --bottom is where the silhouette's base sits.
Writes out.json, out.svg (preview silhouette) and out-overlay.jpg (the profile drawn on the photo).
"""
from __future__ import annotations

import argparse
import colorsys
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


def sky_mask(im: Image.Image) -> list[list[bool]]:
    """True where a pixel looks like sky: bright and either low-saturation or blue."""
    w, h = im.size
    px = im.load()
    mask = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y][:3]
            hh, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            blue = 0.5 <= hh <= 0.72
            mask[y][x] = (v > 0.52 and s < 0.33) or (blue and v > 0.35 and s < 0.85)
    return mask


def profile(mask: list[list[bool]], min_run: int = 7) -> list[int]:
    """For each column, the y of the first run of min_run non-sky pixels from the top (the skyline)."""
    h, w = len(mask), len(mask[0])
    ys = []
    for x in range(w):
        y_found = h - 1
        run = 0
        for y in range(h):
            if not mask[y][x]:
                run += 1
                if run >= min_run:
                    y_found = y - min_run + 1
                    break
            else:
                run = 0
        ys.append(y_found)
    # median filter over columns to drop antennas' single-pixel spikes and noise
    out = []
    k = 3
    for x in range(w):
        win = sorted(ys[max(0, x - k):x + k + 1])
        out.append(win[len(win) // 2])
    return out


def rdp(points: list[tuple[float, float]], eps: float) -> list[tuple[float, float]]:
    if len(points) < 3:
        return points
    (x1, y1), (x2, y2) = points[0], points[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = math.hypot(dx, dy) or 1e-9
    dmax, idx = 0.0, 0
    for i in range(1, len(points) - 1):
        px, py = points[i]
        d = abs(dy * px - dx * py + x2 * y1 - y2 * x1) / norm
        if d > dmax:
            dmax, idx = d, i
    if dmax > eps:
        left = rdp(points[: idx + 1], eps)
        right = rdp(points[idx:], eps)
        return left[:-1] + right
    return [points[0], points[-1]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("photo"); ap.add_argument("out")
    ap.add_argument("--left", type=float, default=0.0); ap.add_argument("--right", type=float, default=1.0)
    ap.add_argument("--top", type=float, default=0.0); ap.add_argument("--bottom", type=float, default=0.9)
    ap.add_argument("--eps", type=float, default=2.2, help="simplification tolerance in px at 1400 px width")
    a = ap.parse_args()
    im = Image.open(a.photo).convert("RGB")
    W, H = im.size
    box = (int(W * a.left), int(H * a.top), int(W * a.right), int(H * a.bottom))
    im = im.crop(box)
    scale = 1400 / im.width
    im = im.resize((1400, max(1, int(im.height * scale))), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.6))
    w, h = im.size
    mask = sky_mask(im)
    ys = profile(mask)
    pts = [(float(x), float(y)) for x, y in enumerate(ys)]
    simp = rdp(pts, a.eps)
    # normalise: x 0..1 across the crop, y 0 = top of crop, 1 = base (bottom of crop)
    norm = [(round(x / w, 4), round(y / h, 4)) for x, y in simp]
    out = Path(a.out)
    out.write_text(json.dumps({"source": Path(a.photo).name, "crop": [a.left, a.top, a.right, a.bottom], "points": norm}, indent=0), encoding="utf-8")
    # previews
    overlay = im.copy()
    d = ImageDraw.Draw(overlay)
    d.line([(x, y) for x, y in simp], fill=(255, 40, 40), width=3)
    overlay.save(out.with_name(out.stem + "-overlay.jpg"), quality=88)
    path = "M 0 1000 " + " ".join(f"L {x * 1000:.1f} {y * 1000:.1f}" for x, y in norm) + " L 1000 1000 Z"
    out.with_suffix(".svg").write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000"><path d="{path}" fill="#14182B"/></svg>', encoding="utf-8")
    print(f"traced {len(simp)} points from {w}x{h}; highest point at y={min(ys)} of {h}")


if __name__ == "__main__":
    main()
