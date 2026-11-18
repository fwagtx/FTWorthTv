"""Upload-ready files for each identity direction: a 1024x1024 profile picture (opaque, mark centred inside the circle
that Facebook and Instagram crop to) and a 1640x624 Facebook cover (lockup inside the 1100 px centre slice phones show).

    python scripts/make_identity_uploads.py
Output: assets/brand/identity/upload/  +  fort-worth-daily-logos.zip
"""
from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_identity import DIRECTIONS, FONT_DIR, OUT as IDENTITY_OUT, ROOT, g, mono_a, mono_b, mono_c, svg, wordmark  # noqa: E402

OUT = IDENTITY_OUT / "upload"
MONO = {"A": mono_a, "B": mono_b, "C": mono_c}


def profile_square(key: str) -> str:
    d = DIRECTIONS[key]
    body, (w, h) = MONO[key](d["paper"], d["paper"] if key != "A" else d["accent"])
    S = 1024
    inner = {"A": 640, "B": 720, "C": 620}[key]          # inside the circle crop with breathing room
    s = min(inner / w, inner / h)
    return svg(S, S, g(body, (S - w * s) / 2, (S - h * s) / 2, s), bg=d["ink"])


def cover(key: str) -> str:
    d = DIRECTIONS[key]
    W, H = 1640, 624
    body, (w, h) = MONO[key](d["ink"], d["accent"])
    wm, (ww, wh) = wordmark(key, d["ink"], d["accent"], d["paper"])
    inner = wm[wm.index(">") + 1:wm.rindex("</svg>")]
    ms = 300 / h                                           # monogram 300 px tall
    ws = min(300 / wh, 620 / ww)                           # wordmark fits the rest of the safe zone
    total = w * ms + 70 + ww * ws
    x0 = (W - total) / 2
    b = g(body, x0, (H - h * ms) / 2, ms) + g(inner, x0 + w * ms + 70, (H - wh * ws) / 2, ws)
    return svg(W, H, b, bg=d["paper"])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*"):
        old.unlink()
    files = []
    for key in DIRECTIONS:
        p = OUT / f"{key}-profile-1024.svg"; p.write_text(profile_square(key), encoding="utf-8"); files.append(("1024", p))
        c = OUT / f"{key}-cover-1640x624.svg"; c.write_text(cover(key), encoding="utf-8"); files.append(("1640", c))
    node = ROOT / "scripts" / "render_svg_inline.js"
    for size in ("1024", "1640"):
        batch = [str(p) for s, p in files if s == size]
        subprocess.run(["node", str(node), str(FONT_DIR), size, str(OUT), *batch], check=True, stdout=subprocess.DEVNULL)
    # tidy names: A-profile-1024-1024.png -> A-profile-1024.png
    for png in OUT.glob("*-1024-1024.png"):
        png.rename(png.with_name(png.name.replace("-1024-1024", "-1024")))
    for png in OUT.glob("*-1640x624-1640.png"):
        png.rename(png.with_name(png.name.replace("-1640x624-1640", "-1640x624")))
    for p in OUT.glob("*.svg"):
        p.unlink()
    with zipfile.ZipFile(IDENTITY_OUT / "fort-worth-daily-logos.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.glob("*.png")):
            z.write(p, p.name)
        for key in DIRECTIONS:
            for part in ("mono", "mono-bw", "wordmark", "wordmark-bw", "lockup", "lockup-bw", "profile", "profile-bw"):
                src = IDENTITY_OUT / f"{key}-{part}-1600.png"
                if src.exists():
                    z.write(src, f"direction-{key}/{key}-{part}.png")
            for s in IDENTITY_OUT.glob(f"{key}-*.svg"):
                z.write(s, f"direction-{key}/vector/{s.name}")
    print("wrote", sorted(p.name for p in OUT.glob("*.png")))


if __name__ == "__main__":
    main()
