"""Trace the real skyline out of a clear-sky photo: for every column find where the sky ends, smooth it, simplify it
to a polygon, and write it as normalised points + an SVG path the logo can use.

Usage: python scripts/trace_skyline.py photo.jpg out.json [--left 0.0 --right 1.0 --top 0.0 --bottom 0.9]
  --left/--right/--top/--bottom crop the photo (fractions) before tracing; --bottom is where the silhouette's base sits.
Writes out.json, out.svg (preview silhouette) and out-overlay.jpg (the profile drawn on the photo).
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


def profile(im: Image.Image, drop: int = 26, sat_jump: float = 0.22, min_run: int = 6, warm: bool = False) -> list[int]:
    """Walk down every column from the top (pure sky in the crop) and stop where the pixel gets clearly darker or more
    saturated than the running sky colour: that is the roofline, even for glass towers that reflect the sky. Clouds stay
    sky because they are brighter, not darker. The result is smoothed across columns to drop antennas and wires."""
    w, h = im.size
    px = im.load()
    ys = []
    for x in range(w):
        sky_bright: list[int] = []
        sky_sat: list[float] = []
        y_found = h - 1
        y = 0
        while y < h:
            r, g, b = px[x, y][:3]
            mx, mn = max(r, g, b), min(r, g, b)
            sat = 0.0 if mx == 0 else (mx - mn) / mx
            if len(sky_bright) < 6:
                sky_bright.append(mx); sky_sat.append(sat); y += 1
                continue
            ref_b = sorted(sky_bright[-24:])[len(sky_bright[-24:]) // 2]
            ref_s = sorted(sky_sat[-24:])[len(sky_sat[-24:]) // 2]
            darker = mx < ref_b - drop
            more_sat = sat > ref_s + sat_jump and mx < 235
            if warm:   # hand-tinted postcards: stone is warm (red over blue), sky and its pink clouds are not
                more_sat = (r - b) > 55
            if darker or more_sat:
                # confirm: the next pixels stay non-sky (skip wires / noise)
                ok = 0
                for yy in range(y, min(h, y + min_run)):
                    r2, g2, b2 = px[x, yy][:3]
                    mx2, mn2 = max(r2, g2, b2), min(r2, g2, b2)
                    s2 = 0.0 if mx2 == 0 else (mx2 - mn2) / mx2
                    if mx2 < ref_b - drop or ((r2 - b2) > 55 if warm else (s2 > ref_s + sat_jump and mx2 < 235)):
                        ok += 1
                if ok >= min_run - 1:
                    y_found = y
                    break
                y += 1
                continue
            sky_bright.append(mx); sky_sat.append(sat); y += 1
        ys.append(y_found)
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
    ap.add_argument("--warm", action="store_true", help="roofline = where warm (red over blue) pixels start; for tinted postcards")
    a = ap.parse_args()
    im = Image.open(a.photo).convert("RGB")
    W, H = im.size
    box = (int(W * a.left), int(H * a.top), int(W * a.right), int(H * a.bottom))
    im = im.crop(box)
    scale = 1400 / im.width
    im = im.resize((1400, max(1, int(im.height * scale))), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.6))
    w, h = im.size
    ys = profile(im, warm=a.warm)
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
